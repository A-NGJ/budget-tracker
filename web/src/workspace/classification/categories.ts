// Transaction types and the seeded spending categories (CONTEXT.md:
// Category, Spending, Refund, Own-account transfer, Contribution).
//
// Categories are referenced everywhere by stable id, never by display name,
// so renaming or merging (issue #8) changes only this list. The seed is a
// code constant rather than a stored record: every workspace starts with the
// same list, nothing has to be written at onboarding, and #8 can introduce a
// stored category list keyed by these same ids without migrating decisions.

export const CATEGORIES = [
  { id: "home", name: "Home" },
  { id: "groceries", name: "Groceries" },
  { id: "eating-out", name: "Eating out" },
  { id: "transport", name: "Transport" },
  { id: "shopping", name: "Shopping" },
  { id: "leisure", name: "Leisure" },
  { id: "travel", name: "Travel" },
  { id: "health", name: "Health" },
  { id: "financial-costs", name: "Financial costs" },
  { id: "other", name: "Other" },
] as const;

export type CategoryId = (typeof CATEGORIES)[number]["id"];

/** Cash withdrawals count as spending under Other until a cash ledger exists. */
export const CASH_CATEGORY: CategoryId = "other";

/**
 * What kind of movement a transaction is. Only spending types carry a
 * category; income, own-account transfers and contributions are types, not
 * spending categories.
 */
export const TRANSACTION_TYPES = ["purchase", "refund", "cash-withdrawal", "income", "transfer", "contribution"] as const;
export type TransactionType = (typeof TRANSACTION_TYPES)[number];

export const SPENDING_TYPES = ["purchase", "refund", "cash-withdrawal"] as const satisfies readonly TransactionType[];
export type SpendingType = (typeof SPENDING_TYPES)[number];
export type NonSpendingType = Exclude<TransactionType, SpendingType>;
export const NON_SPENDING_TYPES = ["income", "transfer", "contribution"] as const satisfies readonly NonSpendingType[];

export const TYPE_NAMES: Record<TransactionType, string> = {
  purchase: "Purchase",
  refund: "Refund",
  "cash-withdrawal": "Cash withdrawal",
  income: "Income",
  transfer: "Own-account transfer",
  contribution: "Contribution",
};

const names = new Map<string, string>(CATEGORIES.map((category) => [category.id, category.name]));

export function isCategoryId(value: unknown): value is CategoryId {
  return typeof value === "string" && names.has(value);
}

export function isTransactionType(value: unknown): value is TransactionType {
  return typeof value === "string" && (TRANSACTION_TYPES as readonly string[]).includes(value);
}

export function isSpendingType(type: TransactionType): type is SpendingType {
  return (SPENDING_TYPES as readonly string[]).includes(type);
}

export function categoryName(id: CategoryId): string {
  return names.get(id) ?? id;
}
