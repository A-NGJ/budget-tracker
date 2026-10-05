import { describe, expect, it } from "vitest";
import { decodeStatement, tokenizeCsv, UnreadableStatementError } from "../../src/workspace/import/csv";
import {
  InvalidRowsError,
  UnsupportedStatementError,
  detectProfiles,
  parseStatement,
  parseStatementAmount,
  parseStatementDate,
} from "../../src/workspace/import/parse";
import { DANSKE_BANK_CSV } from "../../src/workspace/import/profiles";

/** Encode text as Windows-1252 for the Latin-1 range used by Danish exports. */
function windows1252(text: string): Uint8Array {
  return Uint8Array.from(text, (char) => {
    const code = char.charCodeAt(0);
    if (code > 0xff) throw new Error(`not in test range: ${char}`);
    return code;
  });
}

const utf8 = (text: string) => new TextEncoder().encode(text);

const NETBANK_HEADER = '"Dato";"Kategori";"Underkategori";"Tekst";"Beløb";"Saldo";"Status";"Afstemt"';
const netbank = (...rows: string[]) => [NETBANK_HEADER, ...rows].join("\r\n") + "\r\n";

describe("statement decoding", () => {
  it("prefers UTF-8 and falls back to Windows-1252", () => {
    expect(decodeStatement(utf8("Beløb"), ["utf-8", "windows-1252"])).toEqual({ text: "Beløb", encoding: "utf-8" });
    expect(decodeStatement(windows1252("Beløb"), ["utf-8", "windows-1252"])).toEqual({ text: "Beløb", encoding: "windows-1252" });
  });

  it("rejects binary content", () => {
    expect(() => decodeStatement(Uint8Array.of(0x50, 0x4b, 0x03, 0x04, 0x00), ["utf-8", "windows-1252"])).toThrow(UnreadableStatementError);
  });
});

describe("CSV tokenizing", () => {
  it("handles quotes, escaped quotes, embedded delimiters and line breaks", () => {
    const rows = tokenizeCsv('"a";"b ""x""";"c;d"\r\n"multi\nline";2;3\n', ";");
    expect(rows).toEqual([
      { fields: ["a", 'b "x"', "c;d"], line: 1 },
      { fields: ["multi\nline", "2", "3"], line: 2 },
    ]);
  });

  it("rejects an unclosed quote", () => {
    expect(() => tokenizeCsv('"open;1\n', ";")).toThrow(/never closed/);
  });
});

describe("statement dates and amounts", () => {
  it("reads Danish dates strictly", () => {
    expect(parseStatementDate("05.09.2026", "DD.MM.YYYY")).toBe("2026-09-05");
    expect(parseStatementDate("29.02.2028", "DD.MM.YYYY")).toBe("2028-02-29");
    expect(parseStatementDate("29.02.2027", "DD.MM.YYYY")).toBeNull();
    expect(parseStatementDate("2026-09-05", "DD.MM.YYYY")).toBeNull();
    expect(parseStatementDate("5.9.2026", "DD.MM.YYYY")).toBeNull();
  });

  it("keeps every exported digit of Danish amounts", () => {
    const danish = DANSKE_BANK_CSV.amount;
    expect(parseStatementAmount("-5.000,00", danish)).toBe("-5000.00");
    expect(parseStatementAmount("1.234.567,89", danish)).toBe("1234567.89");
    expect(parseStatementAmount("0,1", danish)).toBe("0.1");
    expect(parseStatementAmount("-0,00", danish)).toBe("0.00");
    expect(parseStatementAmount("12345678901234567,01", danish)).toBe("12345678901234567.01");
    expect(parseStatementAmount("−42,50", danish)).toBe("-42.50");
  });

  it("rejects irregular grouping and foreign notation", () => {
    const danish = DANSKE_BANK_CSV.amount;
    expect(parseStatementAmount("12.34,00", danish)).toBeNull();
    expect(parseStatementAmount("1,234.00", danish)).toBeNull();
    expect(parseStatementAmount("", danish)).toBeNull();
    expect(parseStatementAmount("kr 10,00", danish)).toBeNull();
  });
});

describe("Danske Bank statements", () => {
  it("parses a Netbank export in Windows-1252", () => {
    const bytes = windows1252(
      netbank(
        '"02.09.2026";"Bolig      ";"Husleje";"Husleje september";"-7.800,00";"24.700,00";"Udført";"Nej"',
        '"01.09.2026";"Indtægt";"Løn";"Løn fra Arbejdsgiver ApS";"32.500,00";"32.500,00";"Udført";"Nej"',
      ),
    );
    expect(detectProfiles(bytes)).toEqual([DANSKE_BANK_CSV]);
    const parsed = parseStatement(bytes, DANSKE_BANK_CSV);
    expect(parsed.encoding).toBe("windows-1252");
    expect(parsed.delimiter).toBe(";");
    expect(parsed.period).toEqual({ from: "2026-09-01", to: "2026-09-02" });
    expect(parsed.accountIdentifiers).toEqual([]);
    expect(parsed.records[0]).toEqual({
      row: 1,
      line: 2,
      record: {
        date: "2026-09-02",
        amount: "-7800.00",
        currency: "DKK",
        description: "Husleje september",
        details: {
          bankCategory: "Bolig      ",
          bankSubcategory: "Husleje",
          balance: "24.700,00",
          status: "Udført",
          reconciled: "Nej",
        },
      },
    });
    expect(parsed.records[1].record.description).toBe("Løn fra Arbejdsgiver ApS");
  });

  it("parses the shorter UTF-8 layout with a byte order mark", () => {
    const bytes = utf8("\ufeffDato;Beløb;Tekst;Kategori;Underkategori\n15.09.2026;-89,95;NETTO;Dagligvarer;Supermarked\n");
    const parsed = parseStatement(bytes, DANSKE_BANK_CSV);
    expect(parsed.encoding).toBe("utf-8");
    expect(parsed.records.map((item) => item.record.amount)).toEqual(["-89.95"]);
  });

  it("is deterministic", () => {
    const bytes = windows1252(netbank('"03.09.2026";"";"";"Kiosk";"-25,00";"0,00";"Udført";"Nej"'));
    expect(parseStatement(bytes, DANSKE_BANK_CSV)).toEqual(parseStatement(bytes, DANSKE_BANK_CSV));
  });

  it("rejects files that are not Danske statements", () => {
    const other = utf8("Date,Description,Amount\n2026-09-01,Coffee,-3.50\n");
    expect(detectProfiles(other)).toEqual([]);
    expect(() => parseStatement(other, DANSKE_BANK_CSV)).toThrow(UnsupportedStatementError);
    expect(() => parseStatement(new Uint8Array(), DANSKE_BANK_CSV)).toThrow(UnreadableStatementError);
    expect(() => parseStatement(windows1252(netbank()), DANSKE_BANK_CSV)).toThrow(/no transactions/);
  });

  it("refuses the whole file when any row cannot be read", () => {
    const bytes = windows1252(
      netbank('"01.09.2026";"";"";"Ok";"-1,00";"0,00";"Udført";"Nej"', '"31.09.2026";"";"";"Bad date";"1.00";"0,00";"Udført";"Nej"'),
    );
    try {
      parseStatement(bytes, DANSKE_BANK_CSV);
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(InvalidRowsError);
      expect((error as InvalidRowsError).problems).toEqual([expect.stringMatching(/^Line 3: date "31\.09\.2026".*amount "1\.00"/)]);
    }
  });
});
