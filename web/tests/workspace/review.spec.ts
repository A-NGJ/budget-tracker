import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { adminGet, persistentStorageDump, resetEmulators, signInWithGoogle } from "./helpers";

// Category review, remembered merchant choices and ledger editing (issue #3),
// against the local emulators. Statements are synthetic Danske netbank CSVs.
const PASSPHRASE = "lantern orchard vapour 42";
const HEADER = "Dato;Kategori;Underkategori;Tekst;Beløb;Saldo;Status;Afstemt";
const row = (date: string, text: string, amount: string) => `${date};Diverse;Diverse;${text};${amount};0,00;Udført;Nej`;
const csv = (rows: string[]) => Buffer.from([HEADER, ...rows].join("\r\n") + "\r\n", "utf8");

const SEPTEMBER = csv([
  row("01.09.2026", "Løn fra Eksempel ApS", "32.500,00"),
  row("03.09.2026", "Dankort-nota Netto Ærø 03.09", "-418,50"),
  row("05.09.2026", "Dankort-nota Netto Ærø 05.09", "-129,00"),
  row("06.09.2026", "Visa køb Café Kragen 06.09", "-89,00"),
  row("08.09.2026", "Hævning Hæveautomat Nørreport", "-500,00"),
  row("09.09.2026", "Til opsparing", "-4.000,00"),
  row("16.09.2026", "Retur af køb Magasin", "350,00"),
]);
const OCTOBER = csv([row("02.10.2026", "DK-NOTA NETTO ÆRØ 02.10", "-212,00"), row("04.10.2026", "Visa køb Café Kragen 04.10", "-60,00")]);
const NOVEMBER = csv([row("02.11.2026", "DK-NOTA NETTO ÆRØ 02.11", "-315,00")]);

// Readable fixture text and decisions that must never reach storage or the network in readable form.
const SECRETS = ["Netto Ærø", "NETTO ÆRØ", "netto ærø", "Café Kragen", "Hævning", "Løn fra", "Groceries", "groceries", "Eating out", "eating-out", "cash-withdrawal", "contribution"];
const ENVELOPE = ["ciphertext", "formatVersion", "iv", "keyId", "updatedAt"];

test.beforeEach(async ({ request }) => {
  await resetEmulators(request);
});

async function createWorkspace(page: Page) {
  await page.goto("/");
  await signInWithGoogle(page, "operator@example.com");
  await page.getByLabel("Unlock passphrase").fill(PASSPHRASE);
  await page.getByLabel("Repeat passphrase").fill(PASSPHRASE);
  await page.getByRole("button", { name: "Create encrypted workspace" }).click();
  await expect(page.getByRole("heading", { name: "Your month, at a glance" })).toBeVisible();
}

/** Import one statement into a new account (by name) or an existing one (by its option label). */
async function importStatement(page: Page, name: string, buffer: Buffer, account: { create: string } | { existing: string }) {
  await page.getByRole("banner").getByRole("button", { name: "Import statements" }).click();
  await page.getByRole("dialog", { name: "Import bank statements" }).getByLabel("Choose statement files").setInputFiles({ name, mimeType: "text/csv", buffer });
  const preview = page.getByRole("dialog", { name: "Check before importing" });
  const select = preview.getByRole("region", { name }).getByLabel("Account for this file");
  if ("create" in account) {
    await select.selectOption({ label: "New account…" });
    await preview.getByLabel("Account name").fill(account.create);
    await preview.getByRole("button", { name: "Use this account" }).click();
  } else {
    await select.selectOption({ label: account.existing });
  }
  await preview.getByRole("button", { name: "Import statement" }).click();
  await expect(preview).toBeHidden();
}

const nav = (page: Page, item: string) => page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: item }).click();
const inboxCount = (page: Page) => page.getByRole("heading", { name: /^Uncategorized \d+$/ });
const item = (page: Page, description: string) => page.getByRole("list", { name: "Uncategorized transactions" }).getByRole("article", { name: new RegExp(description) });
const ledger = (page: Page) => page.getByRole("table", { name: "Transactions" });
const ledgerRow = (page: Page, description: string) => ledger(page).getByRole("row").filter({ hasText: description });

async function choose(target: Locator, type: string, category?: string) {
  await target.getByLabel("Type").selectOption({ label: type });
  if (category) await target.getByLabel("Category").selectOption({ label: category });
}

async function expectDecision(page: Page, description: string, type: string, category: string, source: "operator" | "remembered" = "operator") {
  const cells = ledgerRow(page, description).getByRole("cell");
  await expect(cells.nth(3)).toContainText(type);
  await expect(cells.nth(4)).toHaveText(category);
  await expect(cells.nth(3).getByText("Remembered choice")).toHaveCount(source === "remembered" ? 1 : 0);
}

async function editInLedger(page: Page, description: string, type: string, category?: string, remember = false) {
  await page.getByRole("button", { name: `Edit ${description}` }).click();
  const dialog = page.getByRole("dialog", { name: "Edit transaction" });
  await choose(dialog, type, category);
  if (remember) await dialog.getByRole("checkbox").check();
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toBeHidden();
}

async function workspacePath(request: APIRequestContext) {
  const workspaces = await adminGet(request, "workspaces");
  return workspaces.documents[0].name.split("/documents/")[1] as string;
}

async function collectionDocs(request: APIRequestContext, path: string) {
  return ((await adminGet(request, `${path}?pageSize=300`)).documents ?? []) as { name: string; fields: Record<string, unknown>; updateTime: string }[];
}

async function unlockAfterReload(page: Page) {
  await page.reload();
  await expect(page.getByRole("heading", { name: "Unlock your workspace" })).toBeVisible();
  await page.getByLabel("Unlock passphrase").fill(PASSPHRASE);
  await page.getByRole("button", { name: "Unlock" }).click();
}

test("each inbox item is assigned on its own, with a reason and a cash-withdrawal suggestion", async ({ page }) => {
  await createWorkspace(page);
  await importStatement(page, "september.csv", SEPTEMBER, { create: "Everyday" });
  await nav(page, "Inbox");
  await expect(inboxCount(page)).toHaveText("Uncategorized 7");
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: /^Inbox\s*7 to review$/ })).toBeVisible();

  // Each item shows its bank record, account and why it needs review, and has its own controls.
  const first = item(page, "Netto Ærø 03.09");
  const second = item(page, "Netto Ærø 05.09");
  const cafe = item(page, "Café Kragen 06.09");
  await expect(first).toContainText("3 Sep 2026 · Everyday · Danske Bank · −418.50 DKK");
  await expect(first).toContainText("No remembered choice for Netto Ærø yet.");
  await expect(first.getByRole("checkbox", { name: "Remember for Netto Ærø" })).not.toBeChecked();
  await expect(item(page, "Løn fra Eksempel ApS")).toContainText("Money arrived.");
  await expect(item(page, "Til opsparing")).toContainText("No merchant could be read");
  // Only items with a readable merchant offer to remember it.
  await expect(page.getByRole("checkbox")).toHaveCount(6);
  await expect(item(page, "Til opsparing")).toContainText("No merchant to remember");

  // Changing one item's selection leaves every other item's selection alone.
  await choose(first, "Purchase", "Groceries");
  await choose(cafe, "Purchase", "Eating out");
  await expect(first.getByLabel("Category")).toHaveValue("groceries");
  await expect(second.getByLabel("Category")).toHaveValue("");
  await expect(cafe.getByLabel("Category")).toHaveValue("eating-out");

  // Assigning one resolves only that item and updates the count.
  await cafe.getByRole("button", { name: "Assign Eating out" }).click();
  await expect(cafe).toHaveCount(0);
  await expect(inboxCount(page)).toHaveText("Uncategorized 6");
  await expect(first.getByLabel("Category")).toHaveValue("groceries");
  await expect(second.getByLabel("Category")).toHaveValue("");
  await expect(page.getByText("Assigned Eating out to Visa køb Café Kragen 06.09.")).toBeVisible();

  // The inbox can undo that assignment, returning the item.
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(inboxCount(page)).toHaveText("Uncategorized 7");
  await expect(cafe).toBeVisible();

  // A likely cash withdrawal is only suggested; it stays unresolved until confirmed.
  const cash = item(page, "Hævning Hæveautomat Nørreport");
  await expect(cash).toContainText("looks like a cash withdrawal");
  await expect(cash.getByText("Suggested · Cash withdrawal")).toBeVisible();
  await nav(page, "Transactions");
  await expectDecision(page, "Hævning Hæveautomat", "Unresolved", "Uncategorized");
  await nav(page, "Inbox");
  await cash.getByRole("button", { name: "Confirm cash withdrawal" }).click();
  await expect(cash).toHaveCount(0);
  await expect(inboxCount(page)).toHaveText("Uncategorized 6");

  // Choosing Cash withdrawal by hand also means Other.
  await choose(second, "Cash withdrawal");
  await expect(second.getByLabel("Category")).toHaveValue("other");
  await expect(second.getByLabel("Category")).toBeDisabled();

  await nav(page, "Transactions");
  await expectDecision(page, "Hævning Hæveautomat", "Cash withdrawal", "Other");
  await expectDecision(page, "Netto Ærø 03.09", "Unresolved", "Uncategorized");
});

test("a remembered choice classifies later imports without reclassifying reviewed history", async ({ page, request }) => {
  await createWorkspace(page);
  await importStatement(page, "september.csv", SEPTEMBER, { create: "Everyday" });
  await nav(page, "Inbox");

  // Review one Netto purchase as Shopping without remembering it.
  const reviewed = item(page, "Netto Ærø 05.09");
  await choose(reviewed, "Purchase", "Shopping");
  await reviewed.getByRole("button", { name: "Assign Shopping" }).click();
  await expect(inboxCount(page)).toHaveText("Uncategorized 6");

  // Remember Groceries for Netto on another item. The reviewed one is not
  // similar-and-uncategorized, so nothing else is offered.
  const remembered = item(page, "Netto Ærø 03.09");
  await choose(remembered, "Purchase", "Groceries");
  await remembered.getByRole("checkbox", { name: "Remember for Netto Ærø" }).check();
  await remembered.getByRole("button", { name: "Assign Groceries" }).click();
  await expect(page.getByText("Later imports from Netto Ærø will get it automatically.")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
  await expect(inboxCount(page)).toHaveText("Uncategorized 5");

  // A later statement for the same merchant (different case, date and card prefix) is classified on import.
  await importStatement(page, "october.csv", OCTOBER, { existing: "Everyday · Danske Bank · DKK" });
  await expectDecision(page, "NETTO ÆRØ 02.10", "Purchase", "Groceries", "remembered");
  await expectDecision(page, "Netto Ærø 05.09", "Purchase", "Shopping");
  await expectDecision(page, "Netto Ærø 03.09", "Purchase", "Groceries");
  await expectDecision(page, "Café Kragen 04.10", "Unresolved", "Uncategorized");
  await nav(page, "Inbox");
  await expect(inboxCount(page)).toHaveText("Uncategorized 6");
  await expect(item(page, "NETTO ÆRØ 02.10")).toHaveCount(0);

  // The automatic decision can be edited and the edit undone.
  await nav(page, "Transactions");
  await editInLedger(page, "DK-NOTA NETTO ÆRØ 02.10", "Purchase", "Eating out");
  await expectDecision(page, "NETTO ÆRØ 02.10", "Purchase", "Eating out");
  await page.getByRole("button", { name: "Undo edit of DK-NOTA NETTO ÆRØ 02.10" }).click();
  await expectDecision(page, "NETTO ÆRØ 02.10", "Purchase", "Groceries", "remembered");
  await expect(page.getByRole("button", { name: "Undo edit of DK-NOTA NETTO ÆRØ 02.10" })).toHaveCount(0);

  // Remembering a choice for a merchant whose other items are still waiting offers the explicit action.
  await nav(page, "Inbox");
  const cafe = item(page, "Café Kragen 06.09");
  await expect(item(page, "Café Kragen 04.10")).toBeVisible();
  await choose(cafe, "Purchase", "Eating out");
  await cafe.getByRole("checkbox", { name: "Remember for Café Kragen" }).check();
  await cafe.getByRole("button", { name: "Assign Eating out" }).click();
  await expect(inboxCount(page)).toHaveText("Uncategorized 5");
  await expect(item(page, "Café Kragen 04.10")).toBeVisible();
  await page.getByRole("button", { name: "Apply to 1 similar item" }).click();
  await expect(page.getByText("Assigned Eating out to 1 more item from Café Kragen.")).toBeVisible();
  await expect(item(page, "Café Kragen 04.10")).toHaveCount(0);
  await expect(inboxCount(page)).toHaveText("Uncategorized 4");

  // Both choices and every decision survive a reload, through encrypted storage only.
  const path = await workspacePath(request);
  const choices = await collectionDocs(request, `${path}/merchant-choices`);
  const decisions = await collectionDocs(request, `${path}/decisions`);
  expect(choices).toHaveLength(2);
  expect(decisions).toHaveLength(5);
  for (const doc of [...choices, ...decisions]) {
    expect(Object.keys(doc.fields).sort()).toEqual(ENVELOPE);
    expect(doc.name.split("/").pop()).toMatch(/^[0-9a-f-]{36}(-r\d+)?$/);
  }
  const stored = JSON.stringify([choices, decisions]);
  for (const text of SECRETS) expect(stored).not.toContain(text);

  await unlockAfterReload(page);
  await expect(inboxCount(page)).toHaveText("Uncategorized 4");
  await expect(item(page, "Netto Ærø")).toHaveCount(0);
  await nav(page, "Transactions");
  await expectDecision(page, "Café Kragen 04.10", "Purchase", "Eating out");
  await expectDecision(page, "Netto Ærø 05.09", "Purchase", "Shopping");
  await expectDecision(page, "NETTO ÆRØ 02.10", "Purchase", "Groceries", "remembered");

  // A remembered choice still classifies a new import after the reload, without
  // changing the earlier reviewed transaction.
  await importStatement(page, "november.csv", NOVEMBER, { existing: "Everyday · Danske Bank · DKK" });
  await expectDecision(page, "NETTO ÆRØ 02.11", "Purchase", "Groceries", "remembered");
  await expectDecision(page, "Netto Ærø 05.09", "Purchase", "Shopping");
});

test("types, search and filters in the ledger, with undo and the original record kept", async ({ page, request }) => {
  const uploads: string[] = [];
  page.on("request", (req) => {
    const body = req.postDataBuffer();
    if (body) uploads.push(body.toString("latin1"), body.toString("utf8"));
  });
  await createWorkspace(page);
  await importStatement(page, "september.csv", SEPTEMBER, { create: "Everyday" });
  await importStatement(page, "october.csv", OCTOBER, { create: "Travel card" });
  const path = await workspacePath(request);
  const chunksBefore = await collectionDocs(request, `${path}/transactions`);
  expect(chunksBefore).toHaveLength(2);

  // Income, transfers and contributions are types, not spending categories.
  await editInLedger(page, "Løn fra Eksempel ApS", "Income");
  await editInLedger(page, "Til opsparing", "Contribution");
  await editInLedger(page, "Retur af køb Magasin", "Refund", "Shopping");
  await editInLedger(page, "Dankort-nota Netto Ærø 03.09", "Purchase", "Groceries");
  await expectDecision(page, "Løn fra Eksempel ApS", "Income", "Not spending");
  await expectDecision(page, "Til opsparing", "Contribution", "Not spending");
  await expectDecision(page, "Retur af køb Magasin", "Refund", "Shopping");
  await page.getByRole("button", { name: "Edit Til opsparing" }).click();
  const dialog = page.getByRole("dialog", { name: "Edit transaction" });
  await expect(dialog.getByLabel("Category")).toBeDisabled();
  await choose(dialog, "Own-account transfer");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expectDecision(page, "Til opsparing", "Own-account transfer", "Not spending");

  // Undo restores the previous decision, one edit back.
  await page.getByRole("button", { name: "Undo edit of Til opsparing" }).click();
  await expectDecision(page, "Til opsparing", "Contribution", "Not spending");
  await expect(page.getByRole("button", { name: "Undo edit of Til opsparing" })).toHaveCount(0);
  // Undoing a first assignment returns the transaction to uncategorized.
  await page.getByRole("button", { name: "Undo edit of Dankort-nota Netto Ærø 03.09" }).click();
  await expectDecision(page, "Netto Ærø 03.09", "Unresolved", "Uncategorized");
  await editInLedger(page, "Dankort-nota Netto Ærø 03.09", "Purchase", "Groceries");

  // Search, account and category/type filters.
  const filters = page.getByRole("search", { name: "Filter transactions" });
  const rows = ledger(page).getByRole("row");
  await expect(rows).toHaveCount(10);
  await filters.getByLabel("Search").fill("netto");
  await expect(rows).toHaveCount(4);
  await expect(page.getByText("3 of 9 transactions match")).toBeVisible();
  await filters.getByLabel("Account").selectOption({ label: "Travel card · Danske Bank" });
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(1)).toContainText("Travel card · Danske Bank");
  await filters.getByLabel("Search").fill("");
  await expect(rows).toHaveCount(3);
  await filters.getByLabel("Account").selectOption({ label: "All accounts" });
  await filters.getByLabel("Category or type").selectOption({ label: "Groceries" });
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(1)).toContainText("Netto Ærø 03.09");
  await filters.getByLabel("Category or type").selectOption({ label: "Shopping" });
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(1)).toContainText("Refund");
  await filters.getByLabel("Category or type").selectOption({ label: "Income" });
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(1)).toContainText("Løn fra Eksempel ApS");
  await filters.getByLabel("Category or type").selectOption({ label: "Uncategorized" });
  await expect(rows).toHaveCount(6);
  await filters.getByLabel("Search").fill("ingen sådan butik");
  await expect(page.getByText("No transactions match these filters.")).toBeVisible();
  await filters.getByRole("button", { name: "Clear filters" }).click();
  await expect(rows).toHaveCount(10);

  // The bank record is untouched: the dialog shows it as imported and the stored chunks are unchanged.
  await page.getByRole("button", { name: "Edit Retur af køb Magasin" }).click();
  const original = page.getByRole("region", { name: "Original bank record" });
  await expect(original).toContainText("Retur af køb Magasin");
  await expect(original).toContainText("350.00 DKK");
  await expect(original).toContainText("Diverse · Diverse");
  await expect(page.getByRole("dialog", { name: "Edit transaction" })).toContainText("Currently: Refund · Shopping");
  await page.getByRole("dialog", { name: "Edit transaction" }).getByRole("button", { name: "Cancel" }).click();
  expect(await collectionDocs(request, `${path}/transactions`)).toEqual(chunksBefore);

  // Decisions are stored as envelopes only, and nothing readable left the browser.
  const decisions = await collectionDocs(request, `${path}/decisions`);
  expect(decisions).toHaveLength(4);
  for (const doc of decisions) expect(Object.keys(doc.fields).sort()).toEqual(ENVELOPE);
  expect(uploads.length).toBeGreaterThan(0);
  for (const body of uploads) for (const text of SECRETS) expect(body).not.toContain(text);

  await unlockAfterReload(page);
  await expect(rows).toHaveCount(10);
  await expectDecision(page, "Til opsparing", "Contribution", "Not spending");
  await expectDecision(page, "Netto Ærø 03.09", "Purchase", "Groceries");
  // The previous decision survives too, so undo still works after a reload.
  await page.getByRole("button", { name: "Undo edit of Retur af køb Magasin" }).click();
  await expectDecision(page, "Retur af køb Magasin", "Unresolved", "Uncategorized");
  expect(await collectionDocs(request, `${path}/transactions`)).toEqual(chunksBefore);

  const dump = JSON.stringify(await persistentStorageDump(page));
  for (const text of SECRETS) expect(dump).not.toContain(text);
});
