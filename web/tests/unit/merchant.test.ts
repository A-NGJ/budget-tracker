import { describe, expect, it } from "vitest";
import { looksLikeCashWithdrawal } from "../../src/workspace/classification/cash";
import { merchantLabel } from "../../src/workspace/classification/merchant";

const key = (description: string) => merchantLabel(description)?.key ?? null;

describe("merchant labels", () => {
  it("strips card prefixes, dates, times, masked cards and reference numbers", () => {
    expect(merchantLabel("Dankort-nota Netto Ærø 12.09")).toEqual({ key: "netto ærø", name: "Netto Ærø" });
    expect(key("DK-NOTA NETTO ÆRØ 14.09")).toBe("netto ærø");
    expect(key("Visa/Dankort  Netto  Ærø 1234 ")).toBe("netto ærø");
    expect(key("VISA KØB DKK 89,00 Joe & The Juice 03.09")).toBe("joe & the juice");
    expect(key("MC/Maestro 7-Eleven 1047 ****4421 14:05")).toBe("7-eleven");
    expect(key("Kortkøb Spotify P2A3B4C5D6 Stockholm")).toBe("spotify stockholm");
    expect(key("Netflix.com Nr. 88213")).toBe("netflix.com");
    expect(key("Rejsekort 2026-09-12 Ref: 93AB11")).toBe("rejsekort");
    expect(key("Wolt #A12-998")).toBe("wolt");
    expect(key("Lidl 418,50")).toBe("lidl");
  });

  it("gives the same label to the same merchant on different days and terminals", () => {
    const same = ["Dankort-nota Føtex Vesterbro 01.09", "DANKORT-NOTA FØTEX VESTERBRO 23.09", "Visa køb Føtex Vesterbro 5521"];
    expect(new Set(same.map(key))).toEqual(new Set(["føtex vesterbro"]));
  });

  it("keeps store names apart rather than over-grouping", () => {
    expect(key("Netto Ærø")).not.toBe(key("Netto Nørrebro"));
    expect(key("Rema 1000 Amager")).toBe("rema amager");
    expect(key("Rema 1000 Amager")).not.toBe(key("Rema 1000 Valby"));
  });

  it("drops a trailing month that only marks the period", () => {
    expect(key("Husleje september")).toBe("husleje");
    expect(key("Husleje oktober")).toBe("husleje");
    // Abbreviations stay: they are too often part of a name.
    expect(key("Café Mar")).toBe("café mar");
  });

  it("refuses person-to-person payments and transfers, which name people or carry messages", () => {
    expect(merchantLabel("MobilePay Anna Hansen")).toBeNull();
    expect(merchantLabel("Mobile Pay: Tak for lån")).toBeNull();
    expect(merchantLabel("Overførsel Mads Jensen")).toBeNull();
    expect(merchantLabel("Til opsparing")).toBeNull();
    expect(merchantLabel("Fra Mor")).toBeNull();
    expect(merchantLabel("Dankort-nota MobilePay Anna")).toBeNull();
  });

  it("refuses descriptions with no business name left", () => {
    expect(merchantLabel("")).toBeNull();
    expect(merchantLabel("   ")).toBeNull();
    expect(merchantLabel("12.09.2026 1234567")).toBeNull();
    expect(merchantLabel("Dankort-nota 4421")).toBeNull();
    expect(merchantLabel("X 12345")).toBeNull();
  });

  it("does not mistake words beginning with a prefix for the prefix", () => {
    expect(key("Visaservice Kbh")).toBe("visaservice kbh");
    expect(key("Notabene Boghandel")).toBe("notabene boghandel");
    expect(key("Tilbudsavisen")).toBe("tilbudsavisen");
  });
});

describe("cash-withdrawal suggestions", () => {
  const out = (description: string) => looksLikeCashWithdrawal({ description, amount: "-500.00" });

  it("recognizes Danish and English withdrawal and ATM descriptions", () => {
    expect(out("Hævning Hæveautomat Nørreport")).toBe(true);
    expect(out("Kontanthævning 12.09")).toBe(true);
    expect(out("Kontant hævning Danske Bank")).toBe(true);
    expect(out("HÆVNING")).toBe(true);
    expect(out("Pengeautomat Strøget")).toBe(true);
    expect(out("Cash withdrawal Berlin")).toBe(true);
    expect(out("ATM Kastrup Lufthavn")).toBe(true);
    expect(out("Visa ATM 1234 Kraków")).toBe(true);
  });

  it("ignores money arriving, even with a withdrawal word", () => {
    expect(looksLikeCashWithdrawal({ description: "Hævning tilbageført", amount: "500.00" })).toBe(false);
  });

  it("does not match words that merely contain the keywords", () => {
    expect(out("Atmosfære Café")).toBe(false);
    expect(out("Matmarkedet")).toBe(false);
    expect(out("Cashback Shop")).toBe(false);
    expect(out("Cash & Carry Engros")).toBe(false);
    expect(out("Netto Hævningsvej")).toBe(false);
    expect(out("Husleje september")).toBe(false);
  });
});
