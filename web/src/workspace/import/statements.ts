// Imported history: statements, the transactions they contributed, and the
// retained original files. Readable forms exist only in browser memory.
import type { Account } from "../accounts";
import type { DecisionRecord } from "../classification/decisions";
import { UnsupportedStatementError, type BankRecord, type ParsedStatement } from "./parse";

export const STATEMENTS_COLLECTION = "statements";
export const TRANSACTIONS_COLLECTION = "transactions";
export const ORIGINALS_COLLECTION = "originals";

/** Plaintext budget per stored document, kept well below the rules' 900,000-byte ciphertext limit. */
export const CHUNK_BYTES = 640 * 1024;
/**
 * One import is one atomic Firestore batch, limited to a 10 MiB request.
 * Ciphertext travels base64-encoded (4/3 larger), so plaintext stays below
 * this budget with headroom for envelopes and framing.
 */
export const MAX_IMPORT_PLAINTEXT_BYTES = 6 * 1024 * 1024;

const encoder = new TextEncoder();

/** Which statement and statement entry a transaction came from (import provenance). */
export interface ImportProvenance {
  statementId: string;
  /** 1-based data row in the original file. */
  row: number;
  /** 1-based physical line in the original file. */
  line: number;
  profileId: string;
  profileVersion: number;
}

/**
 * A transaction as imported. `bank` and `provenance` are the immutable bank
 * record; category and type decisions are stored separately and never
 * overwrite them. With no decision a transaction is uncategorized, which is
 * distinct from a deliberate assignment to Other.
 */
export interface Transaction {
  id: string;
  accountId: string;
  bank: BankRecord;
  provenance: ImportProvenance;
}

export interface RetainedOriginal {
  fileName: string;
  mediaType: string;
  byteLength: number;
  sha256: string;
  chunkIds: string[];
  /** Set when the operator deleted the retained file; history and provenance remain. */
  deletedAt?: string;
}

/** One confirmed import of a bank statement. */
export interface StatementImport {
  id: string;
  accountId: string;
  profileId: string;
  profileVersion: number;
  encoding: string;
  delimiter: string;
  importedAt: string;
  period: { from: string; to: string };
  recordCount: number;
  transactionChunkIds: string[];
  original: RetainedOriginal;
}

/**
 * Stored batch of one statement's transactions, keeping document count and
 * writes low. Fields shared by the whole statement are stored once.
 */
export interface TransactionChunk {
  id: string;
  statementId: string;
  accountId: string;
  profileId: string;
  profileVersion: number;
  entries: { row: number; line: number; bank: BankRecord }[];
}

export function transactionId(statementId: string, row: number): string {
  return `${statementId}-r${row}`;
}

export function chunkTransactionsOf(chunk: TransactionChunk): Transaction[] {
  const { statementId, accountId, profileId, profileVersion } = chunk;
  return chunk.entries.map(({ row, line, bank }) => ({
    id: transactionId(statementId, row),
    accountId,
    bank,
    provenance: { statementId, row, line, profileId, profileVersion },
  }));
}

export interface OriginalChunk {
  id: string;
  bytes: Uint8Array;
}

/** One file in a confirmed import, with the account the operator chose for it. */
export interface ImportItem {
  parsed: ParsedStatement;
  file: { name: string; type: string; bytes: Uint8Array };
  /** An existing account, or a new one created in the preview and saved with the import. */
  account: Account;
}

/** Everything one confirmed import writes, built in memory before anything is stored. */
export interface ImportBatch {
  statements: StatementImport[];
  transactionChunks: TransactionChunk[];
  originalChunks: OriginalChunk[];
  /** New accounts, and accounts with newly verified statement identifiers. */
  accounts: Account[];
  /** Decisions for the new transactions from remembered merchant choices, saved in the same batch. */
  decisions: DecisionRecord[];
}

/** Stored size of one small record beyond its plaintext: envelope fields, IV, tag and base64 framing. */
const RECORD_OVERHEAD_BYTES = 256;

export async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new Uint8Array(bytes));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function chunkTransactions(statement: Pick<StatementImport, "id" | "accountId" | "profileId" | "profileVersion">, parsed: ParsedStatement): TransactionChunk[] {
  const chunks: TransactionChunk[] = [];
  const start = (): TransactionChunk => ({
    id: `${statement.id}-${chunks.length}`,
    statementId: statement.id,
    accountId: statement.accountId,
    profileId: statement.profileId,
    profileVersion: statement.profileVersion,
    entries: [],
  });
  let current = start();
  let size = 0;
  for (const { row, line, record } of parsed.records) {
    const entry = { row, line, bank: record };
    // The array adds a comma per entry; the chunk's own fields fit in the margin.
    const length = encoder.encode(JSON.stringify(entry)).byteLength + 1;
    if (current.entries.length && size + length > CHUNK_BYTES - 512) {
      chunks.push(current);
      current = start();
      size = 0;
    }
    current.entries.push(entry);
    size += length;
  }
  if (current.entries.length) chunks.push(current);
  return chunks;
}

/**
 * Remember identifiers the export itself states for the account, so a later
 * export carrying them can propose the same account. Bank name and file name
 * are never used as identity.
 */
export function rememberIdentifiers(account: Account, identifiers: readonly string[]): Account | undefined {
  const known = new Set(account.statementIdentifiers ?? []);
  const added = identifiers.filter((identifier) => !known.has(identifier));
  if (!added.length) return undefined;
  return { ...account, statementIdentifiers: [...known, ...added].sort() };
}

/** The account a statement verifiably belongs to, or undefined when the operator must choose. */
export function accountForIdentifiers(accounts: readonly Account[], identifiers: readonly string[]): Account | undefined {
  if (!identifiers.length) return undefined;
  const matches = accounts.filter((account) => identifiers.every((identifier) => account.statementIdentifiers?.includes(identifier)));
  return matches.length === 1 ? matches[0] : undefined;
}

/**
 * Why a statement stating these identifiers cannot go into this account, or
 * null. An identifier remembered for another account, or an account already
 * known by different identifiers, means the money moved somewhere else.
 */
export function accountIdentityProblem(accounts: readonly Account[], account: Account, identifiers: readonly string[]): string | null {
  if (!identifiers.length) return null;
  const owner = accounts.find((other) => other.id !== account.id && identifiers.some((identifier) => other.statementIdentifiers?.includes(identifier)));
  if (owner) return `This statement names an account number already verified for ${owner.name} (${owner.bank}).`;
  const known = account.statementIdentifiers ?? [];
  if (known.length && identifiers.some((identifier) => !known.includes(identifier))) {
    return `${account.name} is verified with a different account number than this statement names.`;
  }
  return null;
}

/**
 * Build every record a confirmed import writes. Accounts are resolved in
 * file order, so two files for one new account remember both files'
 * identifiers on the same account.
 */
export async function buildImportBatch(
  items: readonly ImportItem[],
  existing: readonly Account[],
  now = new Date(),
  classify: (transactions: Transaction[]) => DecisionRecord[] = () => [],
): Promise<ImportBatch> {
  const batch: ImportBatch = { statements: [], transactionChunks: [], originalChunks: [], accounts: [], decisions: [] };
  const accounts = new Map(existing.map((account) => [account.id, account]));
  const changed = new Map<string, Account>();
  for (const { parsed, file, account: chosen } of items) {
    const isNew = !accounts.has(chosen.id);
    const account = accounts.get(chosen.id) ?? chosen;
    const problem = accountIdentityProblem([...accounts.values()], account, parsed.accountIdentifiers);
    if (problem) throw new UnsupportedStatementError(problem);
    const updated = rememberIdentifiers(account, parsed.accountIdentifiers) ?? account;
    accounts.set(updated.id, updated);
    if (isNew || updated !== account || changed.has(updated.id)) changed.set(updated.id, updated);

    const statementId = crypto.randomUUID();
    const { profile } = parsed;
    const transactionChunks = chunkTransactions({ id: statementId, accountId: account.id, profileId: profile.id, profileVersion: profile.version }, parsed);
    const originalChunks: OriginalChunk[] = [];
    for (let offset = 0; offset < file.bytes.byteLength; offset += CHUNK_BYTES) {
      originalChunks.push({ id: `${statementId}-${originalChunks.length}`, bytes: file.bytes.slice(offset, offset + CHUNK_BYTES) });
    }
    batch.statements.push({
      id: statementId,
      accountId: account.id,
      profileId: profile.id,
      profileVersion: profile.version,
      encoding: parsed.encoding,
      delimiter: parsed.delimiter,
      importedAt: now.toISOString(),
      period: parsed.period,
      recordCount: parsed.records.length,
      transactionChunkIds: transactionChunks.map((chunk) => chunk.id),
      original: {
        fileName: file.name,
        mediaType: file.type || "text/csv",
        byteLength: file.bytes.byteLength,
        sha256: await sha256Hex(file.bytes),
        chunkIds: originalChunks.map((chunk) => chunk.id),
      },
    });
    batch.transactionChunks.push(...transactionChunks);
    batch.originalChunks.push(...originalChunks);
  }
  batch.accounts = [...changed.values()];
  batch.decisions = classify(batch.transactionChunks.flatMap(chunkTransactionsOf));
  const plaintextBytes =
    batch.originalChunks.reduce((total, chunk) => total + chunk.bytes.byteLength, 0) +
    batch.transactionChunks.reduce((total, chunk) => total + encoder.encode(JSON.stringify(chunk)).byteLength, 0) +
    batch.decisions.reduce((total, record) => total + encoder.encode(JSON.stringify(record)).byteLength + RECORD_OVERHEAD_BYTES, 0);
  if (plaintextBytes > MAX_IMPORT_PLAINTEXT_BYTES) {
    throw new UnsupportedStatementError("These statements are too large to save in one import. Import fewer files at a time, or export a shorter period.");
  }
  return batch;
}

export function joinChunks(chunks: readonly Uint8Array[]): Uint8Array {
  const joined = new Uint8Array(chunks.reduce((total, chunk) => total + chunk.byteLength, 0));
  let offset = 0;
  for (const chunk of chunks) {
    joined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return joined;
}

/** Ledger order: newest first, then by statement and original row so equal dates stay in file order. */
export function sortTransactions(transactions: readonly Transaction[]): Transaction[] {
  return [...transactions].sort(
    (a, b) =>
      b.bank.date.localeCompare(a.bank.date) ||
      a.provenance.statementId.localeCompare(b.provenance.statementId) ||
      a.provenance.row - b.provenance.row,
  );
}

export function sortStatements(statements: readonly StatementImport[]): StatementImport[] {
  return [...statements].sort((a, b) => b.importedAt.localeCompare(a.importedAt) || a.id.localeCompare(b.id));
}
