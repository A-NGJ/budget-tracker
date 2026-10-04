import { describe, expect, it } from "vitest";
import { newAccount, sortAccounts, validateDraft, type Account } from "../../src/workspace/accounts";

const existing: Account[] = [{ id: "1", name: "Everyday", bank: "Danske Bank", currency: "DKK", createdAt: "" }];

describe("account drafts", () => {
  it("accepts a named account with bank and currency", () => {
    expect(validateDraft({ name: "Everyday", bank: "Revolut", currency: "eur" })).toEqual({});
  });

  it("requires name, bank and a three-letter currency", () => {
    expect(validateDraft({ name: " ", bank: "", currency: "EURO" })).toEqual({
      name: expect.any(String),
      bank: expect.any(String),
      currency: expect.any(String),
    });
  });

  it("allows several accounts at one bank but not the same name twice", () => {
    expect(validateDraft({ name: "Savings", bank: "Danske Bank", currency: "DKK" }, existing)).toEqual({});
    expect(validateDraft({ name: "everyday", bank: "danske bank", currency: "DKK" }, existing).name).toMatch(/already exists/);
    expect(validateDraft({ name: "Everyday", bank: "Revolut", currency: "DKK" }, existing)).toEqual({});
  });

  it("normalises whitespace and currency case", () => {
    const account = newAccount({ name: "  Travel   card ", bank: " Revolut ", currency: "eur" }, new Date("2026-10-04T10:00:00Z"));
    expect(account).toMatchObject({ name: "Travel card", bank: "Revolut", currency: "EUR", createdAt: "2026-10-04T10:00:00.000Z" });
    expect(account.id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("sorts by bank, then name, then currency", () => {
    const sorted = sortAccounts([
      { id: "a", name: "Main", bank: "Revolut", currency: "EUR", createdAt: "" },
      { id: "b", name: "Main", bank: "Revolut", currency: "DKK", createdAt: "" },
      { id: "c", name: "Everyday", bank: "Danske Bank", currency: "DKK", createdAt: "" },
    ]);
    expect(sorted.map((item) => item.id)).toEqual(["c", "b", "a"]);
  });
});
