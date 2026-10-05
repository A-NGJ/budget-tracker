// A statement profile is a reusable description of how a bank's statement
// format represents transaction information (CONTEXT.md). It identifies a
// format, never an account: accounts are chosen separately for each file.

export type TextEncoding = "utf-8" | "windows-1252";

export interface DateInterpretation {
  /** Day, month and year tokens with literal separators, e.g. "DD.MM.YYYY". */
  format: string;
}

export interface AmountInterpretation {
  /** Amounts are signed: negative values left the account, positive arrived. */
  signed: true;
  decimalSeparator: "," | ".";
  /** Grouping separator inside the integer part, or "" when none is used. */
  thousandsSeparator: "." | "," | " " | "";
}

export type CurrencyInterpretation =
  /** The export has no currency field; every amount is in this currency. */
  | { kind: "fixed"; code: string }
  /** Each row names its currency in this column. */
  | { kind: "column"; column: string };

export interface StatementProfile {
  id: string;
  version: number;
  name: string;
  bank: string;
  /** Tried in order; UTF-8 is strict so a legacy 8-bit export falls through. */
  encodings: TextEncoding[];
  /** Candidate field separators, detected from the header row. */
  delimiters: string[];
  columns: {
    date: string;
    amount: string;
    description: string;
    /** Bank-assigned transaction identifier, when the export has one. */
    transactionId?: string;
    /** Account number or IBAN, when the export states which account it covers. */
    accountIdentifier?: string;
    /** Further bank-provided fields to keep with each record, by name. Optional in the file. */
    details?: Record<string, string>;
  };
  date: DateInterpretation;
  amount: AmountInterpretation;
  currency: CurrencyInterpretation;
}

/**
 * Danske Bank netbank CSV export ("Dato;Kategori;Underkategori;Tekst;Beløb;
 * Saldo;Status;Afstemt"). Exports are Windows-1252 and semicolon-separated
 * with quoted fields; re-saved copies may be UTF-8 or comma-separated, and
 * older exports carry only Dato, Beløb, Tekst, Kategori and Underkategori.
 * The export states neither a currency nor an account number nor transaction
 * identifiers, so amounts are read as DKK (as in config/banks/danske_bank.yaml)
 * and the operator always chooses the account.
 */
export const DANSKE_BANK_CSV: StatementProfile = {
  id: "danske-bank-netbank-csv",
  version: 1,
  name: "Danske Bank · netbank CSV",
  bank: "Danske Bank",
  encodings: ["utf-8", "windows-1252"],
  delimiters: [";", ","],
  columns: {
    date: "Dato",
    amount: "Beløb",
    description: "Tekst",
    details: { bankCategory: "Kategori", bankSubcategory: "Underkategori", balance: "Saldo", status: "Status", reconciled: "Afstemt" },
  },
  date: { format: "DD.MM.YYYY" },
  amount: { signed: true, decimalSeparator: ",", thousandsSeparator: "." },
  currency: { kind: "fixed", code: "DKK" },
};

export const STATEMENT_PROFILES: readonly StatementProfile[] = [DANSKE_BANK_CSV];

export function findProfile(id: string): StatementProfile | undefined {
  return STATEMENT_PROFILES.find((profile) => profile.id === id);
}

export function requiredColumns(profile: StatementProfile): string[] {
  const { date, amount, description, transactionId, accountIdentifier } = profile.columns;
  const currency = profile.currency.kind === "column" ? [profile.currency.column] : [];
  return [date, amount, description, ...currency, ...[transactionId, accountIdentifier].filter((column): column is string => Boolean(column))];
}
