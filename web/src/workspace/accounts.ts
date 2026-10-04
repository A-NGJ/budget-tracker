// An account is a distinct bank account or currency balance whose transactions
// are tracked separately (CONTEXT.md). Several accounts may share a bank.

export const ACCOUNTS_COLLECTION = "accounts";

/** Readable account content. Exists only in browser memory while unlocked. */
export interface Account {
  id: string;
  name: string;
  bank: string;
  currency: string;
  createdAt: string;
}

export type AccountDraft = Pick<Account, "name" | "bank" | "currency">;

/** The initial banks confirmed for statement import; others remain allowed. */
export const INITIAL_BANKS = ["Danske Bank", "mBank", "Revolut"] as const;

export const COMMON_CURRENCIES = ["DKK", "EUR", "PLN", "USD", "GBP", "SEK", "NOK", "CHF"] as const;

const MAX_NAME_LENGTH = 80;

export type AccountErrors = Partial<Record<keyof AccountDraft, string>>;

export function normalizeDraft(draft: AccountDraft): AccountDraft {
  return {
    name: draft.name.trim().replace(/\s+/g, " "),
    bank: draft.bank.trim().replace(/\s+/g, " "),
    currency: draft.currency.trim().toUpperCase(),
  };
}

export function validateDraft(draft: AccountDraft, existing: readonly Account[] = []): AccountErrors {
  const value = normalizeDraft(draft);
  const errors: AccountErrors = {};
  if (!value.name) errors.name = "Name the account.";
  else if (value.name.length > MAX_NAME_LENGTH) errors.name = `Use at most ${MAX_NAME_LENGTH} characters.`;
  if (!value.bank) errors.bank = "Enter the bank.";
  else if (value.bank.length > MAX_NAME_LENGTH) errors.bank = `Use at most ${MAX_NAME_LENGTH} characters.`;
  if (!/^[A-Z]{3}$/.test(value.currency)) errors.currency = "Use a three-letter currency code, such as DKK.";
  if (
    !errors.name &&
    existing.some((account) => account.name.toLowerCase() === value.name.toLowerCase() && account.bank.toLowerCase() === value.bank.toLowerCase())
  ) {
    errors.name = "An account with this name already exists at this bank.";
  }
  return errors;
}

export function newAccount(draft: AccountDraft, now = new Date()): Account {
  return { id: crypto.randomUUID(), ...normalizeDraft(draft), createdAt: now.toISOString() };
}

export function sortAccounts(accounts: readonly Account[]): Account[] {
  return [...accounts].sort((a, b) => a.bank.localeCompare(b.bank) || a.name.localeCompare(b.name) || a.currency.localeCompare(b.currency));
}
