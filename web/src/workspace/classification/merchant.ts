// Merchant labels (CONTEXT.md): a normalized name identifying the business a
// transaction paid, excluding payment references and personal messages.
//
// Labels group transactions for remembered choices here and are the only
// description text that classification may send off the device later (issue
// #9, ADR-0001), so extraction is deliberately conservative. When in doubt it
// keeps more of the text, which matches fewer transactions, or gives up and
// returns null so the transaction stays with the operator.

export interface MerchantLabel {
  /** Comparison key: case-folded and whitespace-normalized. Equal keys mean the same merchant. */
  key: string;
  /** The label as it reads in the description, for display. */
  name: string;
}

/**
 * Descriptions that name a person or carry a free-form message rather than a
 * business: person-to-person MobilePay, bank transfers. They get no label.
 */
const PERSONAL = [
  /^mobile ?pay\b/iu,
  /^(?:overførsel|overf\.|bankoverførsel|straksoverførsel|transfer)(?![\p{L}\p{N}])/iu,
  /^(?:til|fra|to|from)\s/iu,
];

/** Card and payment-method prefixes the bank puts before the merchant. Stripped repeatedly. */
const PREFIXES = [
  "dankort-nota",
  "dankort-køb",
  "dankortkøb",
  "dk-nota",
  "visa/dankort",
  "visa dankort",
  "visa-køb",
  "visa køb",
  "visa",
  "mastercard",
  "mc/maestro",
  "maestro",
  "kortkøb",
  "dankort",
  "bs-betaling",
  "bs betaling",
  "betalingsservice",
  "pbs",
  "apple pay",
  "google pay",
  "nota",
  "køb",
];

const BOUNDARY = "(?![\\p{L}\\p{N}])";
const PREFIX = new RegExp(`^(?:${PREFIXES.map((prefix) => prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})${BOUNDARY}[\\s:.,-]*`, "iu");
/** "DKK 123,45 " or "EUR 9.99 " that some card exports put after the prefix. */
const AMOUNT_PREFIX = /^[A-Z]{3}\s+-?\d[\d.,]*\s+/u;

// Full month names only: abbreviations such as "mar" or "may" are too often
// part of a name.
const MONTHS = "januar|februar|marts|april|maj|juni|juli|august|september|oktober|november|december|january|february|march|june|july|october";

/** Tokens that are references, dates or amounts, never part of a business name. */
const NOISE = [
  // Dates and times: 12.09, 12.09.26, 12/09/2026, 2026-09-12, 14:05.
  /(?<![\p{L}\p{N}])\d{1,4}[./-]\d{1,2}(?:[./-]\d{2,4})?(?![\p{L}\p{N}])/gu,
  /(?<![\p{L}\p{N}])\d{1,2}:\d{2}(?::\d{2})?(?![\p{L}\p{N}])/gu,
  // Labelled references: "Nr. 1234", "Ref: AB12", "Faktura 991", "#1234".
  /(?<![\p{L}\p{N}])(?:nr|ref|reference|faktura|fakt|ordre|order|kvit|kvittering|id|txn)(?!\p{L})\.?:?\s*[\p{L}\p{N}-]*\d[\p{L}\p{N}-]*/giu,
  /#\s*[\p{L}\p{N}-]+/gu,
  // Masked card numbers: XXXX1234, ****1234, *1234.
  /(?<![\p{L}\p{N}])(?:[x*]{2,}|\*)\d{2,}(?![\p{L}\p{N}])/giu,
  // Amounts with a decimal part: 123,45 or 1.234,50.
  /(?<![\p{L}\p{N}])-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2}(?![\p{L}\p{N}])/gu,
  // Runs of four or more digits (terminal, store or reference numbers), and
  // mixed codes with five or more digits such as "AB1234567".
  /(?<![\p{L}\p{N}])\d{4,}(?![\p{L}\p{N}])/gu,
  /(?<![\p{L}\p{N}])(?=[\p{L}\p{N}]*(?:\d[\p{L}\p{N}]*){5})[\p{L}\p{N}]+(?![\p{L}\p{N}])/gu,
];

/** A trailing month name ("Husleje september") is a period reference. */
const TRAILING_MONTH = new RegExp(`\\s+(?:${MONTHS})\\.?$`, "iu");

function collapse(text: string): string {
  return text.replace(/\s+/gu, " ").trim();
}

function trimPunctuation(text: string): string {
  return text.replace(/^[\s\-–:;,./*|]+|[\s\-–:;,/*|]+$/gu, "").trim();
}

/** The merchant label for a bank description, or null when no business name can be established. */
export function merchantLabel(description: string): MerchantLabel | null {
  let text = collapse(description.normalize("NFC"));
  if (!text || PERSONAL.some((pattern) => pattern.test(text))) return null;

  for (let previous = ""; previous !== text; ) {
    previous = text;
    text = text.replace(PREFIX, "").replace(AMOUNT_PREFIX, "");
    text = trimPunctuation(text);
  }
  if (PERSONAL.some((pattern) => pattern.test(text))) return null;

  for (const pattern of NOISE) text = text.replace(pattern, " ");
  text = trimPunctuation(collapse(text));
  text = trimPunctuation(text.replace(TRAILING_MONTH, ""));

  // Need at least two letters: a label of digits or one character is no name.
  if ((text.match(/\p{L}/gu) ?? []).length < 2) return null;
  return { key: text.toLocaleLowerCase("da"), name: text };
}
