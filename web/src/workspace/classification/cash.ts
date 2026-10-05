// Cash-withdrawal detection. Danske Bank exports have no transaction type
// field, so a likely withdrawal is recognized from its description and only
// ever suggested: the operator confirms it in the review inbox.
//
// Patterns are deliberately narrow. A withdrawal is money leaving the
// account, and the description must lead with a withdrawal keyword or name an
// ATM ("hæveautomat", "ATM") as a whole word, so "Hævning" in the middle of a
// merchant name or "Atmosfære" never matches.

const PATTERNS = [
  /^(?:kontanthævning|kontant hævning|hævning|hæv\.|udbetaling kontant)(?![\p{L}\p{N}])/iu,
  /^(?:cash withdrawal|atm withdrawal)(?![\p{L}\p{N}])/iu,
  /(?<![\p{L}\p{N}])(?:hæveautomat|pengeautomat|atm)(?![\p{L}\p{N}])/iu,
];

/** Whether this bank record looks like a cash withdrawal. A suggestion, never a decision. */
export function looksLikeCashWithdrawal(record: { description: string; amount: string }): boolean {
  if (!record.amount.startsWith("-")) return false;
  const text = record.description.normalize("NFC").replace(/\s+/gu, " ").trim();
  return PATTERNS.some((pattern) => pattern.test(text));
}
