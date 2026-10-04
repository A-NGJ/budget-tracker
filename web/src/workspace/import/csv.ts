// Text decoding and RFC 4180 tokenising for bank statement CSVs. Runs in the
// browser only; nothing here performs network access.
import type { TextEncoding } from "./profiles";

export class UnreadableStatementError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UnreadableStatementError";
  }
}

/**
 * Decode with the first encoding that reads the bytes without error. UTF-8 is
 * decoded strictly, so a Windows-1252 export (where "ø" is the single byte
 * 0xF8) is not misread as UTF-8 replacement characters.
 */
export function decodeStatement(bytes: Uint8Array, encodings: readonly TextEncoding[]): { text: string; encoding: TextEncoding } {
  for (const encoding of encodings) {
    try {
      const text = new TextDecoder(encoding, { fatal: true }).decode(bytes);
      if (text.includes("\u0000")) continue;
      return { text, encoding };
    } catch {
      // Try the next encoding.
    }
  }
  throw new UnreadableStatementError("The file is not readable text in a supported encoding.");
}

export interface CsvRow {
  /** 1-based physical line on which the row starts. */
  line: number;
  fields: string[];
}

/** Split CSV text into rows. Quoted fields may contain delimiters, quotes ("") and line breaks. */
export function tokenizeCsv(text: string, delimiter: string): CsvRow[] {
  const rows: CsvRow[] = [];
  let fields: string[] = [];
  let field = "";
  let quoted = false;
  let fieldStarted = false;
  let line = 1;
  let rowLine = 1;

  const endField = () => {
    fields.push(field);
    field = "";
    fieldStarted = false;
  };
  const endRow = () => {
    endField();
    // A line holding nothing at all is not a row.
    if (!(fields.length === 1 && fields[0] === "")) rows.push({ line: rowLine, fields });
    fields = [];
  };

  for (let index = 0; index < text.length; index++) {
    const char = text[index];
    if (quoted) {
      if (char === '"') {
        if (text[index + 1] === '"') {
          field += '"';
          index++;
        } else {
          quoted = false;
        }
      } else {
        if (char === "\n") line++;
        field += char;
      }
      continue;
    }
    if (char === '"' && !fieldStarted) {
      quoted = true;
      fieldStarted = true;
    } else if (char === delimiter) {
      endField();
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && text[index + 1] === "\n") index++;
      endRow();
      line++;
      rowLine = line;
    } else {
      field += char;
      fieldStarted = true;
    }
  }
  if (quoted) throw new UnreadableStatementError(`A quoted field starting on line ${rowLine} is never closed.`);
  if (field !== "" || fields.length) endRow();
  return rows;
}
