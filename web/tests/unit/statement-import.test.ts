import { describe, expect, it } from "vitest";
import type { Account } from "../../src/workspace/accounts";
import { MIN_PBKDF2_ITERATIONS, createWorkspace, decryptBytes, encryptBytes } from "../../src/workspace/crypto/vault";
import { UnsupportedStatementError, parseStatement } from "../../src/workspace/import/parse";
import { DANSKE_BANK_CSV } from "../../src/workspace/import/profiles";
import {
  CHUNK_BYTES,
  accountForIdentifiers,
  accountIdentityProblem,
  buildImportBatch,
  chunkTransactionsOf,
  joinChunks,
  sortTransactions,
  type Transaction,
} from "../../src/workspace/import/statements";

const everyday: Account = { id: "everyday", name: "Everyday", bank: "Danske Bank", currency: "DKK", createdAt: "2026-10-01T00:00:00.000Z" };
const savings: Account = { id: "savings", name: "Savings", bank: "Danske Bank", currency: "DKK", createdAt: "2026-10-01T00:00:00.000Z" };

const statementBytes = (rows: string[]) =>
  new TextEncoder().encode(["Dato;Beløb;Tekst", ...rows].join("\n") + "\n");

function item(rows: string[], account: Account, name = "konto.csv", identifiers: string[] = []) {
  const bytes = statementBytes(rows);
  const parsed = { ...parseStatement(bytes, DANSKE_BANK_CSV), accountIdentifiers: identifiers };
  return { parsed, file: { name, type: "text/csv", bytes }, account };
}

describe("import batches", () => {
  it("keeps the bank record, provenance and the original file together", async () => {
    const one = item(["01.09.2026;-100,00;Rent", "01.09.2026;-50,00;Lunch"], everyday);
    const batch = await buildImportBatch([one], [everyday], new Date("2026-10-04T10:00:00.000Z"));
    const [statement] = batch.statements;
    expect(statement).toMatchObject({
      accountId: "everyday",
      profileId: DANSKE_BANK_CSV.id,
      importedAt: "2026-10-04T10:00:00.000Z",
      recordCount: 2,
      period: { from: "2026-09-01", to: "2026-09-01" },
      original: { fileName: "konto.csv", byteLength: one.file.bytes.byteLength, sha256: expect.stringMatching(/^[0-9a-f]{64}$/) },
    });
    const transactions = batch.transactionChunks.flatMap(chunkTransactionsOf);
    expect(transactions[1]).toEqual({
      id: `${statement.id}-r2`,
      accountId: "everyday",
      bank: { date: "2026-09-01", amount: "-50.00", currency: "DKK", description: "Lunch", details: {} },
      provenance: { statementId: statement.id, row: 2, line: 3, profileId: DANSKE_BANK_CSV.id, profileVersion: DANSKE_BANK_CSV.version },
    });
    // No category or type is stored with a fresh import: it is uncategorized.
    expect(Object.keys(transactions[1])).not.toContain("category");
    expect(joinChunks(batch.originalChunks.map((chunk) => chunk.bytes))).toEqual(one.file.bytes);
    expect(batch.accounts).toEqual([]);
  });

  it("saves an account created during the preview with its first import", async () => {
    const created: Account = { ...savings, id: "new-savings" };
    const batch = await buildImportBatch([item(["02.09.2026;10,00;Interest"], created)], [everyday]);
    expect(batch.accounts).toEqual([created]);
  });

  it("splits large originals into chunks that reassemble byte for byte", async () => {
    const rows = Array.from({ length: 18_000 }, (_, index) => `01.09.2026;-${index},00;Purchase number ${index}`);
    const big = item(rows, everyday);
    expect(big.file.bytes.byteLength).toBeGreaterThan(CHUNK_BYTES);
    const batch = await buildImportBatch([big], [everyday]);
    expect(batch.originalChunks.length).toBeGreaterThan(1);
    expect(batch.originalChunks.every((chunk) => chunk.bytes.byteLength <= CHUNK_BYTES)).toBe(true);
    expect(joinChunks(batch.originalChunks.map((chunk) => chunk.bytes))).toEqual(big.file.bytes);
    expect(batch.transactionChunks.flatMap(chunkTransactionsOf)).toHaveLength(18_000);
    for (const chunk of batch.transactionChunks) expect(new TextEncoder().encode(JSON.stringify(chunk)).byteLength).toBeLessThan(CHUNK_BYTES);
  });
});

describe("account identity", () => {
  const known: Account = { ...everyday, statementIdentifiers: ["3456-1234567"] };

  it("proposes an account only from identifiers the export states", () => {
    expect(accountForIdentifiers([known, savings], ["3456-1234567"])).toBe(known);
    expect(accountForIdentifiers([known, savings], [])).toBeUndefined();
    expect(accountForIdentifiers([known, savings], ["9999-0000000"])).toBeUndefined();
  });

  it("refuses a statement whose identifiers belong elsewhere", () => {
    expect(accountIdentityProblem([known, savings], savings, ["3456-1234567"])).toMatch(/Everyday/);
    expect(accountIdentityProblem([known, savings], known, ["9999-0000000"])).toMatch(/different account number/);
    expect(accountIdentityProblem([known, savings], savings, [])).toBeNull();
  });

  it("remembers newly stated identifiers on the chosen account", async () => {
    const batch = await buildImportBatch([item(["01.09.2026;1,00;x"], savings, "a.csv", ["1111-2222222"])], [everyday, savings]);
    expect(batch.accounts).toEqual([{ ...savings, statementIdentifiers: ["1111-2222222"] }]);
    await expect(buildImportBatch([item(["01.09.2026;1,00;x"], savings, "a.csv", ["3456-1234567"])], [known, savings])).rejects.toThrow(
      UnsupportedStatementError,
    );
  });
});

describe("ledger order", () => {
  it("is newest first and keeps file order within a day", () => {
    const tx = (id: string, date: string, row: number): Transaction => ({
      id,
      accountId: "a",
      bank: { date, amount: "1", currency: "DKK", description: id, details: {} },
      provenance: { statementId: "s", row, line: row + 1, profileId: "p", profileVersion: 1 },
    });
    expect(sortTransactions([tx("a", "2026-09-01", 1), tx("b", "2026-09-02", 2), tx("c", "2026-09-01", 0)]).map((t) => t.id)).toEqual([
      "b",
      "c",
      "a",
    ]);
  });
});

describe("byte envelopes", () => {
  it("round-trip raw bytes bound to their record", async () => {
    const { workspaceKey } = await createWorkspace("uid", "correct horse battery staple", MIN_PBKDF2_ITERATIONS);
    const bytes = Uint8Array.of(0xc6, 0xf8, 0xe5, 0x00, 0xff);
    const envelope = await encryptBytes(workspaceKey, "originals", "s-0", bytes);
    expect(await decryptBytes(workspaceKey, "originals", "s-0", envelope)).toEqual(bytes);
    await expect(decryptBytes(workspaceKey, "originals", "s-1", envelope)).rejects.toThrow();
  });
});
