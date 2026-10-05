import { describe, expect, it } from "vitest";
import { CATEGORIES, TYPE_NAMES } from "../../src/workspace/classification/categories";
import {
  canUndo,
  currentDecision,
  isUncategorized,
  normalizeClassification,
  operatorEdit,
  parseDecisionRecord,
  rememberChoice,
  rememberedDecisions,
  reviewReason,
  similarUncategorized,
  undoEdit,
  type DecisionRecord,
} from "../../src/workspace/classification/decisions";
import type { Transaction } from "../../src/workspace/import/statements";

const NOW = new Date("2026-10-05T12:00:00.000Z");

function transaction(id: string, description: string, amount = "-100.00"): Transaction {
  return {
    id,
    accountId: "everyday",
    bank: { date: "2026-09-01", amount, currency: "DKK", description, details: {} },
    provenance: { statementId: "s1", row: 1, line: 2, profileId: "danske-bank-netbank-csv", profileVersion: 1 },
  };
}

const decisions = (...records: DecisionRecord[]) => new Map(records.map((record) => [record.id, record]));

describe("seeded categories and types", () => {
  it("seeds the flat initial list with stable ids, ending in Other", () => {
    expect(CATEGORIES.map((category) => category.name)).toEqual([
      "Home",
      "Groceries",
      "Eating out",
      "Transport",
      "Shopping",
      "Leisure",
      "Travel",
      "Health",
      "Financial costs",
      "Other",
    ]);
    expect(CATEGORIES.map((category) => category.name)).not.toContain("Uncategorized");
    expect(Object.values(TYPE_NAMES)).toEqual(["Purchase", "Refund", "Cash withdrawal", "Income", "Own-account transfer", "Contribution"]);
  });

  it("gives spending types a category and keeps income, transfers and contributions category-free", () => {
    expect(normalizeClassification({ type: "purchase", category: "groceries" })).toEqual({ type: "purchase", category: "groceries" });
    expect(normalizeClassification({ type: "refund", category: "shopping" })).toEqual({ type: "refund", category: "shopping" });
    expect(normalizeClassification({ type: "purchase" })).toBeNull();
    expect(normalizeClassification({ type: "purchase", category: "Groceries" })).toBeNull();
    expect(normalizeClassification({ type: "income", category: "groceries" })).toEqual({ type: "income" });
    expect(normalizeClassification({ type: "transfer" })).toEqual({ type: "transfer" });
    expect(normalizeClassification({ type: "contribution" })).toEqual({ type: "contribution" });
    expect(normalizeClassification({ type: "split" })).toBeNull();
  });

  it("always counts cash withdrawals as spending under Other", () => {
    expect(normalizeClassification({ type: "cash-withdrawal" })).toEqual({ type: "cash-withdrawal", category: "other" });
    expect(normalizeClassification({ type: "cash-withdrawal", category: "travel" })).toEqual({ type: "cash-withdrawal", category: "other" });
  });
});

describe("decision resolution", () => {
  it("treats no decision as uncategorized, not Other", () => {
    expect(currentDecision(undefined)).toBeNull();
    expect(isUncategorized(undefined)).toBe(true);
    expect(isUncategorized({ id: "t1", current: null })).toBe(true);
    const other = operatorEdit("t1", undefined, { type: "purchase", category: "other" }, NOW);
    expect(isUncategorized(other)).toBe(false);
    expect(currentDecision(other)?.classification).toEqual({ type: "purchase", category: "other" });
  });

  it("records operator edits with what they replaced, and undo restores it", () => {
    const first = operatorEdit("t1", undefined, { type: "purchase", category: "groceries" }, NOW);
    expect(first).toEqual({
      id: "t1",
      current: { classification: { type: "purchase", category: "groceries" }, source: "operator", decidedAt: NOW.toISOString() },
      previous: null,
    });
    expect(canUndo(first)).toBe(true);

    const second = operatorEdit("t1", first, { type: "transfer" }, NOW);
    expect(second.previous).toEqual(first.current);
    expect(second.current?.classification).toEqual({ type: "transfer" });

    // Undo reaches back one edit only.
    const undone = undoEdit(second);
    expect(undone).toEqual({ id: "t1", current: first.current });
    expect(canUndo(undone)).toBe(false);
    expect(() => undoEdit(undone)).toThrow("no edit to undo");

    // Undoing the first assignment returns the transaction to uncategorized.
    const back = undoEdit(first);
    expect(back).toEqual({ id: "t1", current: null });
    expect(isUncategorized(back)).toBe(true);
  });

  it("lets the operator edit and undo a remembered (automatic) decision", () => {
    const remembered: DecisionRecord = {
      id: "t1",
      current: { classification: { type: "purchase", category: "groceries" }, source: "remembered", decidedAt: NOW.toISOString(), merchantChoiceId: "c1" },
    };
    expect(canUndo(remembered)).toBe(false);
    const edited = operatorEdit("t1", remembered, { type: "purchase", category: "eating-out" }, NOW);
    expect(edited.current?.source).toBe("operator");
    expect(undoEdit(edited).current).toEqual(remembered.current);
  });

  it("rejects malformed stored decisions", () => {
    expect(() => parseDecisionRecord({ id: "t1" })).toThrow();
    expect(() => parseDecisionRecord({ id: "t1", current: { classification: { type: "purchase" }, source: "operator", decidedAt: "x" } })).toThrow();
    expect(() => parseDecisionRecord({ id: "t1", current: { classification: { type: "income" }, source: "jev", decidedAt: "x" } })).toThrow();
    expect(parseDecisionRecord({ id: "t1", current: null, previous: null })).toEqual({ id: "t1", current: null, previous: null });
  });
});

describe("remembered merchant choices", () => {
  const netto = transaction("t1", "Dankort-nota Netto Ærø 01.09");
  const groceries = { type: "purchase", category: "groceries" } as const;

  it("remembers by merchant label and money direction, reusing the id for the same merchant", () => {
    const choice = rememberChoice(netto, groceries, [], NOW);
    expect(choice).toMatchObject({ merchant: { key: "netto ærø", name: "Netto Ærø" }, direction: "out", classification: groceries });
    expect(choice!.id).toMatch(/^[0-9a-f-]{36}$/);
    const again = rememberChoice(transaction("t2", "DK-NOTA NETTO ÆRØ 20.09"), { type: "purchase", category: "other" }, [choice!], NOW);
    expect(again!.id).toBe(choice!.id);
    expect(again!.classification).toEqual({ type: "purchase", category: "other" });
    expect(rememberChoice(transaction("t3", "MobilePay Anna"), groceries, [], NOW)).toBeNull();
  });

  it("applies only to transactions with no decision, never reclassifying reviewed history", () => {
    const choice = rememberChoice(netto, groceries, [], NOW)!;
    const reviewed = operatorEdit("t-old", undefined, { type: "purchase", category: "shopping" }, NOW);
    const backToUncategorized: DecisionRecord = { id: "t-undone", current: null };
    const later = [
      transaction("t-new", "Dankort-nota Netto Ærø 15.10"),
      transaction("t-old", "Dankort-nota Netto Ærø 01.09"),
      transaction("t-undone", "Dankort-nota Netto Ærø 02.09"),
      transaction("t-refund", "Netto Ærø", "25.00"),
      transaction("t-other", "Netto Nørrebro"),
    ];
    const records = rememberedDecisions(later, [choice], decisions(reviewed, backToUncategorized), NOW);
    expect(records).toEqual([
      { id: "t-new", current: { classification: groceries, source: "remembered", decidedAt: NOW.toISOString(), merchantChoiceId: choice.id } },
    ]);
  });

  it("finds similar uncategorized items for the explicit apply-to-similar action", () => {
    const choice = rememberChoice(netto, groceries, [], NOW)!;
    const decided = operatorEdit("t1", undefined, groceries, NOW);
    const items = [netto, transaction("t2", "Netto Ærø 1234"), transaction("t3", "Netto Ærø", "10.00"), transaction("t4", "Lidl")];
    expect(similarUncategorized(choice, items, decisions(decided)).map((item) => item.id)).toEqual(["t2"]);
  });
});

describe("review reasons", () => {
  it("explains why each item needs the operator", () => {
    expect(reviewReason(transaction("t1", "Hævning Hæveautomat Nørreport", "-500.00"))).toEqual({ kind: "cash-withdrawal" });
    expect(reviewReason(transaction("t2", "Løn fra Eksempel ApS", "32500.00"))).toEqual({ kind: "money-in" });
    expect(reviewReason(transaction("t3", "Dankort-nota Netto 01.09"))).toEqual({ kind: "unfamiliar-merchant", merchant: { key: "netto", name: "Netto" } });
    expect(reviewReason(transaction("t4", "MobilePay Anna"))).toEqual({ kind: "no-merchant" });
    const choice = rememberChoice(transaction("t5", "Netto"), { type: "purchase", category: "groceries" }, [], NOW)!;
    expect(reviewReason(transaction("t6", "Dankort-nota Netto 02.09"), [choice])).toEqual({ kind: "remembered-later", choice });
  });
});
