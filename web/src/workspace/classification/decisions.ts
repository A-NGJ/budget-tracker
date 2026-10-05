// Category and type decisions for imported transactions.
//
// A transaction's bank record is immutable, so decisions live in their own
// encrypted records, one per transaction, keyed by the transaction id. No
// record (or a record whose current decision is null) means the transaction
// is uncategorized, which is distinct from a deliberate assignment to Other.
//
// Each record keeps the decision in force and, after an operator edit, the
// decision it replaced, so the most recent edit can be undone. There is no
// longer edit history. `source` says where a decision came from; later
// classification paths (rules, Jev) add their own sources.
import { CASH_CATEGORY, isCategoryId, isSpendingType, isTransactionType, type CategoryId, type NonSpendingType, type SpendingType } from "./categories";
import { looksLikeCashWithdrawal } from "./cash";
import { merchantLabel, type MerchantLabel } from "./merchant";
import type { Transaction } from "../import/statements";

/** Collection names are bound into each record's encryption; never rename them. */
export const DECISIONS_COLLECTION = "decisions";
export const MERCHANT_CHOICES_COLLECTION = "merchant-choices";

export type Classification = { type: SpendingType; category: CategoryId } | { type: NonSpendingType };

/** Who decided: the operator directly, or a remembered merchant choice applied at import. */
export type DecisionSource = "operator" | "remembered";

export interface Decision {
  classification: Classification;
  source: DecisionSource;
  decidedAt: string;
  /** The remembered merchant choice that produced this decision, when source is "remembered". */
  merchantChoiceId?: string;
}

export interface DecisionRecord {
  /** The transaction id. Opaque: a random statement id and a row number. */
  id: string;
  /** The decision in force, or null when the transaction is back to uncategorized. */
  current: Decision | null;
  /**
   * What the most recent operator edit replaced: a decision, or null for
   * uncategorized. Absent when there is nothing to undo.
   */
  previous?: Decision | null;
}

/** Money direction a remembered choice applies to; a purchase choice never classifies a refund. */
export type Direction = "out" | "in";

/**
 * A category or type the operator chose to remember for one merchant. Applied
 * only to transactions imported later that have no decision yet. The merchant
 * label is inside the encrypted record; the record id is random.
 */
export interface MerchantChoice {
  id: string;
  merchant: MerchantLabel;
  direction: Direction;
  classification: Classification;
  updatedAt: string;
}

export function directionOf(transaction: Pick<Transaction, "bank">): Direction {
  return transaction.bank.amount.startsWith("-") ? "out" : "in";
}

/** A valid classification, with cash withdrawals always counted under Other. */
export function normalizeClassification(value: unknown): Classification | null {
  if (typeof value !== "object" || value === null) return null;
  const { type, category } = value as { type?: unknown; category?: unknown };
  if (!isTransactionType(type)) return null;
  if (type === "cash-withdrawal") return { type, category: CASH_CATEGORY };
  if (isSpendingType(type)) return isCategoryId(category) ? { type, category } : null;
  return { type };
}

export function sameClassification(a: Classification | null | undefined, b: Classification | null | undefined): boolean {
  if (!a || !b) return !a && !b;
  return a.type === b.type && ("category" in a ? a.category : undefined) === ("category" in b ? b.category : undefined);
}

/** The decision in force for a transaction, or null when it is uncategorized. */
export function currentDecision(record: DecisionRecord | undefined): Decision | null {
  return record?.current ?? null;
}

export function isUncategorized(record: DecisionRecord | undefined): boolean {
  return currentDecision(record) === null;
}

export function canUndo(record: DecisionRecord | undefined): boolean {
  return record !== undefined && record.previous !== undefined;
}

/** Record an operator edit, keeping what it replaced for undo. */
export function operatorEdit(transactionId: string, existing: DecisionRecord | undefined, classification: Classification, now = new Date()): DecisionRecord {
  const normalized = normalizeClassification(classification);
  if (!normalized) throw new Error("That category or type is not valid.");
  return {
    id: transactionId,
    current: { classification: normalized, source: "operator", decidedAt: now.toISOString() },
    previous: existing?.current ?? null,
  };
}

/** Undo the most recent operator edit, restoring the decision it replaced. */
export function undoEdit(record: DecisionRecord): DecisionRecord {
  if (record.previous === undefined) throw new Error("There is no edit to undo for this transaction.");
  return { id: record.id, current: record.previous };
}

/** Remember a classification for a transaction's merchant, replacing an earlier choice for the same merchant and direction. */
export function rememberChoice(
  transaction: Transaction,
  classification: Classification,
  choices: readonly MerchantChoice[],
  now = new Date(),
): MerchantChoice | null {
  const merchant = merchantLabel(transaction.bank.description);
  const normalized = normalizeClassification(classification);
  if (!merchant || !normalized) return null;
  const direction = directionOf(transaction);
  const existing = choices.find((choice) => choice.merchant.key === merchant.key && choice.direction === direction);
  return { id: existing?.id ?? crypto.randomUUID(), merchant, direction, classification: normalized, updatedAt: now.toISOString() };
}

function choiceIndex(choices: readonly MerchantChoice[]): Map<string, MerchantChoice> {
  return new Map(choices.map((choice) => [`${choice.direction}:${choice.merchant.key}`, choice]));
}

/** The remembered choice that would apply to this transaction, if any. */
export function choiceFor(transaction: Transaction, choices: readonly MerchantChoice[] | Map<string, MerchantChoice>): MerchantChoice | undefined {
  const merchant = merchantLabel(transaction.bank.description);
  if (!merchant) return undefined;
  const index = choices instanceof Map ? choices : choiceIndex(choices);
  return index.get(`${directionOf(transaction)}:${merchant.key}`);
}

/**
 * Decisions for newly imported transactions from remembered merchant choices.
 * Only transactions without any decision are eligible, so already-reviewed
 * history is never reclassified.
 */
export function rememberedDecisions(
  transactions: readonly Transaction[],
  choices: readonly MerchantChoice[],
  existing: ReadonlyMap<string, DecisionRecord>,
  now = new Date(),
): DecisionRecord[] {
  if (!choices.length) return [];
  const index = choiceIndex(choices);
  const decidedAt = now.toISOString();
  const records: DecisionRecord[] = [];
  for (const transaction of transactions) {
    if (existing.has(transaction.id)) continue;
    const choice = choiceFor(transaction, index);
    if (!choice) continue;
    records.push({ id: transaction.id, current: { classification: choice.classification, source: "remembered", decidedAt, merchantChoiceId: choice.id } });
  }
  return records;
}

/**
 * Other uncategorized transactions from the same merchant and direction,
 * which the operator may explicitly resolve with the same choice.
 */
export function similarUncategorized(
  choice: Pick<MerchantChoice, "merchant" | "direction">,
  transactions: readonly Transaction[],
  decisions: ReadonlyMap<string, DecisionRecord>,
): Transaction[] {
  return transactions.filter((transaction) => {
    if (!isUncategorized(decisions.get(transaction.id)) || directionOf(transaction) !== choice.direction) return false;
    return merchantLabel(transaction.bank.description)?.key === choice.merchant.key;
  });
}

export type ReviewReason =
  | { kind: "cash-withdrawal" }
  | { kind: "remembered-later"; choice: MerchantChoice }
  | { kind: "money-in" }
  | { kind: "unfamiliar-merchant"; merchant: MerchantLabel }
  | { kind: "no-merchant" };

/** Why an uncategorized transaction needs the operator. */
export function reviewReason(transaction: Transaction, choices: readonly MerchantChoice[] = []): ReviewReason {
  if (looksLikeCashWithdrawal(transaction.bank)) return { kind: "cash-withdrawal" };
  // A choice remembered after this transaction was imported does not apply to it on its own.
  const choice = choiceFor(transaction, choices);
  if (choice) return { kind: "remembered-later", choice };
  if (directionOf(transaction) === "in") return { kind: "money-in" };
  const merchant = merchantLabel(transaction.bank.description);
  return merchant ? { kind: "unfamiliar-merchant", merchant } : { kind: "no-merchant" };
}

/** Decrypted decision records are checked before use; anything malformed fails loudly. */
export function parseDecisionRecord(value: unknown): DecisionRecord {
  const record = value as Partial<DecisionRecord>;
  const decision = (item: unknown): Decision | null => {
    if (item === null) return null;
    const candidate = item as Partial<Decision>;
    const classification = normalizeClassification(candidate.classification);
    if (!classification || (candidate.source !== "operator" && candidate.source !== "remembered") || typeof candidate.decidedAt !== "string") {
      throw new Error("Decision record is malformed.");
    }
    return { ...candidate, classification } as Decision;
  };
  if (typeof record.id !== "string" || record.current === undefined) throw new Error("Decision record is malformed.");
  const parsed: DecisionRecord = { id: record.id, current: decision(record.current) };
  if (record.previous !== undefined) parsed.previous = decision(record.previous);
  return parsed;
}

export function parseMerchantChoice(value: unknown): MerchantChoice {
  const choice = value as Partial<MerchantChoice>;
  const classification = normalizeClassification(choice.classification);
  if (
    typeof choice.id !== "string" ||
    typeof choice.merchant?.key !== "string" ||
    typeof choice.merchant?.name !== "string" ||
    (choice.direction !== "out" && choice.direction !== "in") ||
    !classification
  ) {
    throw new Error("Remembered merchant choice is malformed.");
  }
  return { ...(choice as MerchantChoice), classification };
}
