import { expect, test, type Page } from "@playwright/test";
import { adminGet, documentsUrl, emulatorGoogleToken, persistentStorageDump, resetEmulators, signInWithGoogle } from "./helpers";

const PASSPHRASE = "lantern orchard vapour 42";
const ACCOUNT = { name: "Travel card", bank: "Revolut", currency: "EUR" };

test.beforeEach(async ({ request }) => {
  await resetEmulators(request);
});

async function createWorkspace(page: Page, email: string) {
  await page.goto("/");
  await signInWithGoogle(page, email);
  await expect(page.getByRole("heading", { name: "Protect your workspace" })).toBeVisible();
  await page.getByLabel("Unlock passphrase").fill(PASSPHRASE);
  await page.getByLabel("Repeat passphrase").fill(PASSPHRASE);
  await page.getByRole("button", { name: "Create encrypted workspace" }).click();
  await expect(page.getByRole("heading", { name: "Your month, at a glance" })).toBeVisible();
}

async function addAccount(page: Page) {
  await page.getByRole("button", { name: "Add account" }).click();
  const dialog = page.getByRole("dialog", { name: "Add an account" });
  await dialog.getByLabel("Account name").fill(ACCOUNT.name);
  await dialog.getByLabel("Bank").fill(ACCOUNT.bank);
  await dialog.getByLabel("Currency").fill(ACCOUNT.currency.toLowerCase());
  await dialog.getByRole("button", { name: "Save account" }).click();
  await expect(dialog).toBeHidden();
}

function accountList(page: Page) {
  return page.getByRole("list", { name: "Accounts" });
}

test("sign in, create a workspace, save an account and reopen it after a fresh load", async ({ page, request }) => {
  const apiCalls: string[] = [];
  page.on("request", (req) => {
    if (new URL(req.url()).pathname.startsWith("/api/")) apiCalls.push(req.url());
  });

  await createWorkspace(page, "operator@example.com");
  await expect(page.getByText("No accounts yet.")).toBeVisible();
  await addAccount(page);
  await expect(accountList(page).getByText(ACCOUNT.name)).toBeVisible();
  await expect(accountList(page).getByText("EUR")).toBeVisible();

  // Storage holds ciphertext only.
  const workspaces = await adminGet(request, "workspaces");
  expect(workspaces.documents).toHaveLength(1);
  const workspacePath = workspaces.documents[0].name.split("/documents/")[1];
  const records = await adminGet(request, `${workspacePath}/accounts`);
  expect(records.documents).toHaveLength(1);
  const stored = JSON.stringify([workspaces, records]);
  for (const text of [ACCOUNT.name, ACCOUNT.bank, "EUR", PASSPHRASE]) expect(stored).not.toContain(text);
  expect(Object.keys(records.documents[0].fields).sort()).toEqual(["ciphertext", "formatVersion", "iv", "keyId", "updatedAt"]);

  // A fresh load keeps the Google session but needs the passphrase again.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Unlock your workspace" })).toBeVisible();
  await expect(page.getByText(ACCOUNT.name)).toHaveCount(0);
  await page.getByLabel("Unlock passphrase").fill("not the passphrase");
  await page.getByRole("button", { name: "Unlock" }).click();
  await expect(page.getByText("That passphrase does not unlock this workspace.")).toBeVisible();
  await page.getByLabel("Unlock passphrase").fill(PASSPHRASE);
  await page.getByRole("button", { name: "Unlock" }).click();
  await expect(accountList(page).getByText(ACCOUNT.name)).toBeVisible();
  await expect(accountList(page).getByText(ACCOUNT.bank)).toBeVisible();

  // No readable account data in persistent browser storage, and no call to the plaintext API.
  const dump = JSON.stringify(await persistentStorageDump(page));
  for (const text of [ACCOUNT.name, PASSPHRASE]) expect(dump).not.toContain(text);
  expect(dump).not.toMatch(/firestore/i);
  expect(apiCalls).toEqual([]);
});

test("manual lock removes readable state; sign-out clears the persisted session", async ({ page }) => {
  await createWorkspace(page, "operator@example.com");
  await addAccount(page);

  await page.getByRole("button", { name: "Lock workspace" }).click();
  await expect(page.getByRole("heading", { name: "Unlock your workspace" })).toBeVisible();
  await expect(page.getByText("Workspace locked.")).toBeVisible();
  await expect(page.getByText(ACCOUNT.name)).toHaveCount(0);
  expect(await page.content()).not.toContain(ACCOUNT.name);

  await page.getByLabel("Unlock passphrase").fill(PASSPHRASE);
  await page.getByRole("button", { name: "Unlock" }).click();
  await expect(accountList(page).getByText(ACCOUNT.name)).toBeVisible();

  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByRole("dialog", { name: "Workspace settings" }).getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Sign in with Google" })).toBeVisible();
  const dump = await persistentStorageDump(page);
  expect(dump.local.filter((entry) => entry.startsWith("firebase:authUser"))).toEqual([]);
  expect(JSON.stringify(dump)).not.toContain(ACCOUNT.name);
  await page.reload();
  await expect(page.getByRole("button", { name: "Sign in with Google" })).toBeVisible();
});

test("locks after 15 minutes of inactivity", async ({ page }) => {
  await page.clock.install();
  await createWorkspace(page, "operator@example.com");
  await addAccount(page);
  await page.clock.fastForward("14:00");
  await expect(accountList(page).getByText(ACCOUNT.name)).toBeVisible();
  await page.clock.fastForward("01:30");
  await expect(page.getByRole("heading", { name: "Unlock your workspace" })).toBeVisible();
  await expect(page.getByText("Locked after 15 minutes without activity.")).toBeVisible();
  await expect(page.getByText(ACCOUNT.name)).toHaveCount(0);
});

test("storage rejects another Google account and unauthenticated access", async ({ page, request }) => {
  await createWorkspace(page, "operator@example.com");
  await addAccount(page);
  const workspaces = await adminGet(request, "workspaces");
  const workspacePath: string = workspaces.documents[0].name.split("/documents/")[1];

  const anonymous = await request.get(documentsUrl(`${workspacePath}/accounts`));
  expect(anonymous.status()).toBe(403);

  const other = await emulatorGoogleToken(request, "other-google-sub", "intruder@example.com");
  const headers = { Authorization: `Bearer ${other.idToken}` };
  expect((await request.get(documentsUrl(workspacePath), { headers })).status()).toBe(403);
  expect((await request.get(documentsUrl(`${workspacePath}/accounts`), { headers })).status()).toBe(403);
  const write = await request.patch(documentsUrl(`${workspacePath}/accounts/intruder`), {
    headers,
    data: { fields: { formatVersion: { integerValue: "1" } } },
  });
  expect(write.status()).toBe(403);

  // The same request shape succeeds for the other account's own path, proving the token is valid.
  const own = await request.get(documentsUrl(`workspaces/${other.uid}/accounts`), { headers });
  expect(own.status()).toBe(200);
});

test("a second Google account gets its own empty workspace", async ({ page, browser }) => {
  await createWorkspace(page, "operator@example.com");
  await addAccount(page);

  const context = await browser.newContext();
  const otherPage = await context.newPage();
  await createWorkspace(otherPage, "someone@example.com");
  await expect(otherPage.getByText("No accounts yet.")).toBeVisible();
  await expect(otherPage.getByText(ACCOUNT.name)).toHaveCount(0);
  await context.close();
});
