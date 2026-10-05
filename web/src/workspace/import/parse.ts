// Deterministic, browser-only parsing of a bank statement under a statement
// profile. Amounts stay decimal strings end to end, so no value passes
// through binary floating point.
import { decodeStatement, tokenizeCsv, UnreadableStatementError } from "./csv";
import { requiredColumns, STATEMENT_PROFILES, type AmountInterpretation, type StatementProfile, type TextEncoding } from "./profiles";

/** The original bank-record information for one statement entry. Never edited after import. */
export interface BankRecord {
  /** ISO calendar date, YYYY-MM-DD. */
  date: string;
  /** Signed canonical decimal, e.g. "-1234.50": negative left the account. Scale is kept as exported. */
  amount: string;
  currency: string;
  /** The description exactly as exported. */
  description: string;
  bankTransactionId?: string;
  /** Further bank-provided fields named by the profile, exactly as exported. */
  details: Record<string, string>;
}

export interface ParsedRecord {
  /** 1-based data row (the header is row 0). */
  row: number;
  /** 1-based physical line where the row starts. */
  line: number;
  record: BankRecord;
}

export interface ParsedStatement {
  profile: StatementProfile;
  encoding: TextEncoding;
  delimiter: string;
  records: ParsedRecord[];
  /** Account identifiers stated by the export itself, if the profile reads any. */
  accountIdentifiers: string[];
  period: { from: string; to: string };
}

export class UnsupportedStatementError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UnsupportedStatementError";
  }
}

export class InvalidRowsError extends Error {
  constructor(readonly problems: string[]) {
    super(`${problems.length === 1 ? "1 row" : `${problems.length} rows`} could not be read: ${problems.slice(0, 3).join(" ")}${problems.length > 3 ? " …" : ""}`);
    this.name = "InvalidRowsError";
  }
}

/**
 * A confirmed import is written in one atomic Firestore batch (10 MiB request
 * limit), together with its parsed transactions. 1 MiB is years of Danske
 * Bank history; larger files are refused rather than saved in parts.
 */
export const MAX_STATEMENT_BYTES = 1024 * 1024;

const DATE_TOKENS = /DD|MM|YYYY/g;

/** Parse a date under a "DD.MM.YYYY"-style pattern into YYYY-MM-DD, or null. */
export function parseStatementDate(value: string, format: string): string | null {
  const order: string[] = [];
  const pattern = format.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(DATE_TOKENS, (token) => {
    order.push(token);
    return token === "YYYY" ? "(\\d{4})" : "(\\d{2})";
  });
  const match = new RegExp(`^${pattern}$`).exec(value.trim());
  if (!match) return null;
  const parts: Record<string, string> = {};
  order.forEach((token, index) => (parts[token] = match[index + 1]));
  const year = Number(parts.YYYY);
  const month = Number(parts.MM);
  const day = Number(parts.DD);
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (month < 1 || month > 12 || day < 1 || day > daysInMonth) return null;
  return `${parts.YYYY}-${parts.MM}-${parts.DD}`;
}

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Parse a signed amount into a canonical decimal string ("-1234.50"), keeping
 * every exported digit, or null when the text is not an amount in this
 * interpretation. Grouping must be regular (1.234.567,89), not arbitrary.
 */
export function parseStatementAmount(value: string, interpretation: AmountInterpretation): string | null {
  const text = value.trim().replace(/\u2212/g, "-");
  const decimal = escape(interpretation.decimalSeparator);
  const grouped = interpretation.thousandsSeparator ? `\\d{1,3}(?:${escape(interpretation.thousandsSeparator)}\\d{3})+` : null;
  const integer = grouped ? `(?:${grouped}|\\d+)` : "\\d+";
  const match = new RegExp(`^([+-]?)(${integer})(?:${decimal}(\\d+))?$`).exec(text);
  if (!match) return null;
  const [, sign, rawInteger, fraction] = match;
  const digits = (interpretation.thousandsSeparator ? rawInteger.split(interpretation.thousandsSeparator).join("") : rawInteger).replace(/^0+(?=\d)/, "");
  const zero = /^0+$/.test(digits) && (!fraction || /^0+$/.test(fraction));
  return `${sign === "-" && !zero ? "-" : ""}${digits}${fraction ? `.${fraction}` : ""}`;
}

function findHeader(text: string, profile: StatementProfile): { delimiter: string; header: string[]; rows: ReturnType<typeof tokenizeCsv> } | null {
  const required = requiredColumns(profile);
  for (const delimiter of profile.delimiters) {
    const rows = tokenizeCsv(text, delimiter);
    if (!rows.length) continue;
    const header = rows[0].fields.map((name) => name.trim());
    if (required.every((column) => header.includes(column))) return { delimiter, header, rows };
  }
  return null;
}

/** Profiles whose header layout matches the file. Detection identifies a format, never an account. */
export function detectProfiles(bytes: Uint8Array, profiles: readonly StatementProfile[] = STATEMENT_PROFILES): StatementProfile[] {
  return profiles.filter((profile) => {
    try {
      const { text } = decodeStatement(bytes, profile.encodings);
      return findHeader(stripBom(text), profile) !== null;
    } catch {
      return false;
    }
  });
}

function stripBom(text: string): string {
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

/**
 * Parse every row of a statement under a profile. Throws
 * UnreadableStatementError, UnsupportedStatementError or InvalidRowsError; a
 * row is never skipped silently.
 */
export function parseStatement(bytes: Uint8Array, profile: StatementProfile): ParsedStatement {
  if (bytes.byteLength === 0) throw new UnreadableStatementError("The file is empty.");
  if (bytes.byteLength > MAX_STATEMENT_BYTES) throw new UnsupportedStatementError("The file is larger than 1 MB. Export a shorter period and import it in parts.");
  const { text, encoding } = decodeStatement(bytes, profile.encodings);
  const found = findHeader(stripBom(text), profile);
  if (!found) {
    throw new UnsupportedStatementError(`This is not a ${profile.name} file: its header needs the columns ${requiredColumns(profile).join(", ")}.`);
  }
  const { delimiter, header, rows } = found;
  const index = (column: string) => header.indexOf(column);
  const columns = profile.columns;
  const details = Object.entries(columns.details ?? {}).filter(([, column]) => index(column) >= 0);

  const records: ParsedRecord[] = [];
  const problems: string[] = [];
  const identifiers = new Set<string>();
  rows.slice(1).forEach(({ fields, line }, position) => {
    const row = position + 1;
    if (fields.every((field) => field.trim() === "")) return;
    const cell = (column: string) => fields[index(column)] ?? "";
    const rawDate = cell(columns.date);
    const rawAmount = cell(columns.amount);
    const date = parseStatementDate(rawDate, profile.date.format);
    const amount = parseStatementAmount(rawAmount, profile.amount);
    const currency = (profile.currency.kind === "fixed" ? profile.currency.code : cell(profile.currency.column)).trim().toUpperCase();
    const rowProblems: string[] = [];
    if (fields.length > header.length) rowProblems.push(`has ${fields.length} fields but the header has ${header.length}`);
    if (!date) rowProblems.push(`date "${rawDate.trim()}" is not ${profile.date.format}`);
    if (!amount) rowProblems.push(`amount "${rawAmount.trim()}" is not a signed amount`);
    if (!/^[A-Z]{3}$/.test(currency)) rowProblems.push(`currency "${currency}" is not a three-letter code`);
    if (rowProblems.length || !date || !amount) {
      problems.push(`Line ${line}: ${rowProblems.join("; ")}.`);
      return;
    }
    const record: BankRecord = { date, amount, currency, description: cell(columns.description), details: {} };
    if (columns.transactionId) {
      const id = cell(columns.transactionId).trim();
      if (id) record.bankTransactionId = id;
    }
    if (columns.accountIdentifier) {
      const identifier = cell(columns.accountIdentifier).trim();
      if (identifier) identifiers.add(identifier);
    }
    for (const [key, column] of details) record.details[key] = cell(column);
    records.push({ row, line, record });
  });

  if (problems.length) throw new InvalidRowsError(problems);
  if (!records.length) throw new UnsupportedStatementError("The file has a header but no transactions.");
  const dates = records.map((item) => item.record.date).sort();
  return { profile, encoding, delimiter, records, accountIdentifiers: [...identifiers], period: { from: dates[0], to: dates[dates.length - 1] } };
}
