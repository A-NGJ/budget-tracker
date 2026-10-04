import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { resetEmulators, signInWithGoogle } from "./helpers";

const PASSPHRASE = "lantern orchard vapour 42";

test.beforeEach(async ({ request }) => {
  await resetEmulators(request);
});

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((violation) => `${violation.id}: ${violation.nodes.map((node) => node.target.join(" ")).join(", ")}`)).toEqual([]);
}

test("the whole flow works from the keyboard", async ({ page, browserName }) => {
  // WebKit only moves Tab focus to links when the platform setting allows it,
  // so the keyboard-only part uses Chromium and Firefox.
  test.skip(browserName === "webkit", "WebKit tab order depends on the OS keyboard-navigation setting");
  await page.goto("/");
  await signInWithGoogle(page, "operator@example.com");

  // Onboarding: the passphrase field is focused, Enter submits.
  await expect(page.getByLabel("Unlock passphrase")).toBeFocused();
  await page.keyboard.type(PASSPHRASE);
  await page.keyboard.press("Tab");
  await page.keyboard.type(PASSPHRASE);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Your month, at a glance" })).toBeVisible();

  // Skip link, then reach "Add account" by tabbing.
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  const addAccount = page.getByRole("button", { name: "Add account" });
  for (let i = 0; i < 20 && !(await addAccount.evaluate((element) => element === document.activeElement)); i++) await page.keyboard.press("Tab");
  await expect(addAccount).toBeFocused();
  await page.keyboard.press("Enter");

  const dialog = page.getByRole("dialog", { name: "Add an account" });
  await expect(dialog.getByLabel("Account name")).toBeFocused();
  await page.keyboard.type("Everyday");
  await page.keyboard.press("Tab");
  await page.keyboard.type("Danske Bank");
  await page.keyboard.press("Enter");
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("list", { name: "Accounts" }).getByText("Everyday")).toBeVisible();
  await expect(addAccount).toBeFocused();

  // Escape closes dialogs and returns focus.
  const importButton = page.getByRole("banner").getByRole("button", { name: "Import statements" });
  await importButton.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Statement import is coming next" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(importButton).toBeFocused();
});

test("primary navigation has honest empty states and import on every page", async ({ page }) => {
  await page.goto("/");
  await signInWithGoogle(page, "operator@example.com");
  await page.getByLabel("Unlock passphrase").fill(PASSPHRASE);
  await page.getByLabel("Repeat passphrase").fill(PASSPHRASE);
  await page.getByRole("button", { name: "Create encrypted workspace" }).click();

  const navigation = page.getByRole("navigation", { name: "Main navigation" });
  await expect(navigation.getByRole("button")).toHaveText(["Overview", "Transactions", "Inbox", "Recurring"]);
  await expect(navigation.getByRole("button", { name: "Settings" })).toHaveCount(0);

  const pages = [
    ["Overview", "Your month, at a glance"],
    ["Transactions", "No transactions yet"],
    ["Inbox", "Nothing to review"],
    ["Recurring", "No recurring costs yet"],
  ] as const;
  for (const [item, heading] of pages) {
    await navigation.getByRole("button", { name: item }).click();
    await expect(navigation.getByRole("button", { name: item })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expect(page.getByRole("banner").getByRole("button", { name: "Import statements" })).toBeVisible();
    await expectNoAxeViolations(page);
  }
});

test("skip link moves focus to the content without changing the destination", async ({ page }) => {
  await page.goto("/");
  await signInWithGoogle(page, "operator@example.com");
  await page.getByLabel("Unlock passphrase").fill(PASSPHRASE);
  await page.getByLabel("Repeat passphrase").fill(PASSPHRASE);
  await page.getByRole("button", { name: "Create encrypted workspace" }).click();
  await expect(page.getByRole("heading", { name: "Your month, at a glance" })).toBeVisible();

  const navigation = page.getByRole("navigation", { name: "Main navigation" });
  const skip = page.getByRole("link", { name: "Skip to content" });
  const pages = [
    ["Overview", "Your month, at a glance", "#/overview"],
    ["Transactions", "No transactions yet", "#/transactions"],
    ["Inbox", "Nothing to review", "#/inbox"],
    ["Recurring", "No recurring costs yet", "#/recurring"],
  ] as const;
  for (const [item, heading, hash] of pages) {
    await navigation.getByRole("button", { name: item }).click();
    await page.evaluate(() => window.scrollTo(0, 0));
    const before = new URL(page.url()).hash;
    await skip.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("main#dk-main")).toBeFocused();
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expect(navigation.getByRole("button", { name: item })).toHaveAttribute("aria-current", "page");
    expect(new URL(page.url()).hash).toBe(before);
    if (item !== "Overview") expect(before).toBe(hash);
    // A second activation is still a no-op for routing.
    await skip.focus();
    await page.keyboard.press("Enter");
    await expect(navigation.getByRole("button", { name: item })).toHaveAttribute("aria-current", "page");
  }
});

for (const colorScheme of ["light", "dark"] as const) {
  test(`follows the system ${colorScheme} colour scheme without accessibility violations`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await page.goto("/");
    await expectNoAxeViolations(page);
    const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(background).toBe(colorScheme === "dark" ? "rgb(21, 30, 35)" : "rgb(245, 246, 248)");

    await signInWithGoogle(page, "operator@example.com");
    await expectNoAxeViolations(page);
    await page.getByLabel("Unlock passphrase").fill(PASSPHRASE);
    await page.getByLabel("Repeat passphrase").fill(PASSPHRASE);
    await page.getByRole("button", { name: "Create encrypted workspace" }).click();
    await expect(page.getByRole("heading", { name: "Your month, at a glance" })).toBeVisible();
    await expectNoAxeViolations(page);
    await page.getByRole("button", { name: "Add account" }).click();
    await expect(page.getByRole("dialog", { name: "Add an account" })).toBeVisible();
    await expectNoAxeViolations(page);
  });
}
