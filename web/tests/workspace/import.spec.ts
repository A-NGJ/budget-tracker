import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { adminGet, persistentStorageDump, resetEmulators, signInWithGoogle } from "./helpers";

// Synthetic Netbank export: Windows-1252, semicolons, quoted fields, CRLF.
const FIXTURE = fileURLToPath(new URL("../fixtures/danske-netbank-synthetic.csv", import.meta.url));
const FIXTURE_NAME = "danske-netbank-synthetic.csv";
const PASSPHRASE = "lantern orchard vapour 42";
const ACCOUNT = { name: "Everyday", bank: "Danske Bank", currency: "DKK" };
// Readable values from the fixture that must never reach storage.
const SECRETS = ["Husleje september", "Løn fra Eksempel ApS", "Købmand Ærø", "32.500,00", "-7800.00", "Everyday", FIXTURE_NAME];

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

async function openFixture(page: Page) {
  await page.getByRole("banner").getByRole("button", { name: "Import statements" }).click();
  const dialog = page.getByRole("dialog", { name: "Import bank statements" });
  await dialog.getByLabel("Choose statement files").setInputFiles(FIXTURE);
  const preview = page.getByRole("dialog", { name: "Check before importing" });
  await expect(preview.getByRole("region", { name: FIXTURE_NAME })).toBeVisible();
  return preview;
}

async function workspacePath(request: Parameters<typeof adminGet>[0]) {
  const workspaces = await adminGet(request, "workspaces");
  return workspaces.documents[0].name.split("/documents/")[1] as string;
}

async function collectionDocs(request: Parameters<typeof adminGet>[0], path: string) {
  return ((await adminGet(request, path)).documents ?? []) as { name: string; fields: Record<string, unknown> }[];
}

const ledger = (page: Page) => page.getByRole("table", { name: "Transactions" });

test("preview, choose an account, confirm, and reopen the encrypted ledger after reload", async ({ page, request }) => {
  const uploads: string[] = [];
  page.on("request", (req) => {
    const body = req.postDataBuffer();
    if (body) uploads.push(body.toString("latin1"), body.toString("utf8"));
    if (new URL(req.url()).pathname.startsWith("/api/")) uploads.push(`plaintext api: ${req.url()}`);
  });
  await createWorkspace(page);
  const preview = await openFixture(page);
  const file = preview.getByRole("region", { name: FIXTURE_NAME });

  // The preview shows the parsed records with Danish text and exact amounts.
  await expect(file.getByText("5 transactions · 1 Sep 2026 – 16 Sep 2026")).toBeVisible();
  await expect(file.getByText("Danske Bank · netbank CSV")).toBeVisible();
  const rows = file.getByRole("table", { name: `Preview of ${FIXTURE_NAME}` }).getByRole("row");
  await expect(rows).toHaveCount(6);
  await expect(rows.nth(2)).toContainText("Husleje september");
  await expect(rows.nth(2)).toContainText("−7,800.00 DKK");
  await expect(rows.nth(3)).toContainText("Købmand Ærø");

  // Danske exports do not name the account, so nothing is guessed.
  const select = file.getByLabel("Account for this file");
  await expect(select).toHaveValue("");
  await expect(file.getByText("This export does not name its account")).toBeVisible();
  const confirm = preview.getByRole("button", { name: "Import statement" });
  await expect(confirm).toBeDisabled();

  // Nothing is stored while previewing.
  const path = await workspacePath(request);
  expect(await collectionDocs(request, `${path}/statements`)).toEqual([]);

  // A new account created in the preview is saved with the import.
  await select.selectOption({ label: "New account…" });
  const form = file.getByRole("form", { name: "New account" });
  await expect(form.getByLabel("Bank")).toHaveValue(ACCOUNT.bank);
  await expect(form.getByLabel("Currency")).toHaveValue(ACCOUNT.currency);
  await form.getByLabel("Account name").fill(ACCOUNT.name);
  await form.getByRole("button", { name: "Use this account" }).click();
  await expect(select).toHaveValue(/.+/);
  await confirm.click();
  await expect(preview).toBeHidden();
  await expect(page.getByRole("status")).toContainText("Imported 5 transactions from 1 statement");

  // The ledger shows the bank records, uncategorized rather than Other.
  await expect(page.getByRole("heading", { name: "Every movement, in context" })).toBeVisible();
  await expect(ledger(page).getByRole("row")).toHaveCount(6);
  const newest = ledger(page).getByRole("row").nth(1);
  await expect(newest).toContainText("16 Sep 2026");
  await expect(newest).toContainText("Retur af køb");
  await expect(newest).toContainText("Everyday · Danske Bank");
  await expect(newest).toContainText("Uncategorized");
  await expect(newest).toContainText("350.00 DKK");
  await expect(ledger(page).getByText("Other", { exact: true })).toHaveCount(0);

  // Storage holds envelopes only: statement, transaction chunk, original and account.
  const docs = await Promise.all(["accounts", "statements", "transactions", "originals"].map((name) => collectionDocs(request, `${path}/${name}`)));
  expect(docs.map((items) => items.length)).toEqual([1, 1, 1, 1]);
  for (const item of docs.flat()) expect(Object.keys(item.fields).sort()).toEqual(["ciphertext", "formatVersion", "iv", "keyId", "updatedAt"]);
  const stored = JSON.stringify(docs);
  for (const text of SECRETS) expect(stored).not.toContain(text);

  // Nothing readable left the browser in any request body.
  expect(uploads.length).toBeGreaterThan(0);
  for (const body of uploads) for (const text of SECRETS) expect(body).not.toContain(text);
  expect(uploads.filter((body) => body.startsWith("plaintext api"))).toEqual([]);

  // After a reload the passphrase is needed again, then the history is back.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Unlock your workspace" })).toBeVisible();
  await page.getByLabel("Unlock passphrase").fill(PASSPHRASE);
  await page.getByRole("button", { name: "Unlock" }).click();
  // The destination survives the reload.
  await expect(ledger(page).getByRole("row")).toHaveCount(6);
  await expect(ledger(page).getByRole("row").nth(5)).toContainText("Løn fra Eksempel ApS");
  await expect(ledger(page).getByRole("row").nth(5)).toContainText("32,500.00 DKK");

  // The retained original downloads byte for byte.
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: `Download original ${FIXTURE_NAME}` }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(FIXTURE_NAME);
  const downloaded = await download.path();
  expect(readFileSync(downloaded)).toEqual(readFileSync(FIXTURE));

  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Overview" }).click();
  await expect(page.getByText("Statement coverage: 1 statement imported")).toBeVisible();

  const dump = JSON.stringify(await persistentStorageDump(page));
  for (const text of SECRETS) expect(dump).not.toContain(text);
});

test("cancelling a preview stores nothing", async ({ page, request }) => {
  await createWorkspace(page);
  const preview = await openFixture(page);
  await preview.getByRole("region", { name: FIXTURE_NAME }).getByLabel("Account for this file").selectOption({ label: "New account…" });
  await preview.getByLabel("Account name").fill(ACCOUNT.name);
  await preview.getByRole("button", { name: "Use this account" }).click();
  await preview.getByRole("button", { name: "Cancel" }).click();
  await expect(preview).toBeHidden();

  const path = await workspacePath(request);
  for (const name of ["accounts", "statements", "transactions", "originals"]) expect(await collectionDocs(request, `${path}/${name}`)).toEqual([]);
  await expect(page.getByText("No accounts yet.")).toBeVisible();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Transactions" }).click();
  await expect(page.getByRole("heading", { name: "No transactions yet" })).toBeVisible();
});

test("unsupported and unreadable files are rejected with a reason", async ({ page }) => {
  await createWorkspace(page);
  await page.getByRole("banner").getByRole("button", { name: "Import statements" }).click();
  await page
    .getByRole("dialog", { name: "Import bank statements" })
    .getByLabel("Choose statement files")
    .setInputFiles([
      { name: "other-bank.csv", mimeType: "text/csv", buffer: Buffer.from("Date,Description,Amount\n2026-09-01,Coffee,-3.50\n") },
      { name: "broken.csv", mimeType: "text/csv", buffer: Buffer.from("Dato;Beløb;Tekst\n31.09.2026;-1,00;Kiosk\n") },
      { name: "empty.csv", mimeType: "text/csv", buffer: Buffer.alloc(0) },
    ]);
  const preview = page.getByRole("dialog", { name: "Check before importing" });
  await expect(preview.getByRole("region", { name: "other-bank.csv" }).getByRole("alert")).toContainText("not in a supported statement format");
  const broken = preview.getByRole("region", { name: "broken.csv" });
  await expect(broken.getByRole("alert")).toContainText("1 row could not be read, so nothing from this file will be imported.");
  await expect(broken.getByText('Line 2: date "31.09.2026" is not DD.MM.YYYY.')).toBeVisible();
  await expect(preview.getByRole("region", { name: "empty.csv" }).getByRole("alert")).toContainText("The file is empty.");
  await expect(preview.getByRole("button", { name: /^Import/ })).toBeDisabled();
});

test("deleting the retained original keeps the imported history", async ({ page, request }) => {
  await createWorkspace(page);
  const preview = await openFixture(page);
  await preview.getByLabel("Account for this file").selectOption({ label: "New account…" });
  await preview.getByLabel("Account name").fill(ACCOUNT.name);
  await preview.getByRole("button", { name: "Use this account" }).click();
  await preview.getByRole("button", { name: "Import statement" }).click();
  await expect(ledger(page).getByRole("row")).toHaveCount(6);

  await page.getByRole("button", { name: `Delete original ${FIXTURE_NAME}` }).click();
  const dialog = page.getByRole("dialog", { name: "Delete the original file?" });
  await expect(dialog).toContainText("Its 5 transactions stay in your history");
  await dialog.getByRole("button", { name: "Delete original" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText("Original deleted")).toBeVisible();

  const path = await workspacePath(request);
  expect(await collectionDocs(request, `${path}/originals`)).toEqual([]);
  expect(await collectionDocs(request, `${path}/statements`)).toHaveLength(1);
  expect(await collectionDocs(request, `${path}/transactions`)).toHaveLength(1);

  await page.reload();
  await page.getByLabel("Unlock passphrase").fill(PASSPHRASE);
  await page.getByRole("button", { name: "Unlock" }).click();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Transactions" }).click();
  await expect(ledger(page).getByRole("row")).toHaveCount(6);
  await expect(page.getByText("Original deleted")).toBeVisible();
  await expect(page.getByRole("button", { name: `Download original ${FIXTURE_NAME}` })).toHaveCount(0);
});
