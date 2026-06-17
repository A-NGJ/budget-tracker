import { test, expect } from "@playwright/test";

// Known computed values from web/tests/fixtures/transactions.json, as serialized
// by the real /api/analytics endpoint (Decimal -> string):
//   income  = 5000.00  (single +5000.00 salary)
//   expenses = -500.00 (-150 + -300 + -50)
//   net      = 4500.00 (income + expenses)
const EXPECTED = {
  income: "5000.00",
  expenses: "-500.00",
  net: "4500.00",
};

test.describe("Stats dashboard", () => {
  test("renders summary totals from the live backend", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByTestId("dashboard")).toBeVisible();

    await expect(page.getByTestId("summary-income-value")).toHaveText(EXPECTED.income);
    await expect(page.getByTestId("summary-expenses-value")).toHaveText(EXPECTED.expenses);
    await expect(page.getByTestId("summary-net-value")).toHaveText(EXPECTED.net);
  });

  test("renders an ECharts canvas for each of the three chart sections", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByTestId("dashboard")).toBeVisible();

    for (const section of ["chart-category", "chart-monthly", "chart-source"]) {
      const canvas = page.getByTestId(section).locator("canvas");
      await expect(canvas).toBeVisible();
    }
  });
});
