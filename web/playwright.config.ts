import { defineConfig, devices } from "@playwright/test";

const PORT = 5179;
const BASE_URL = `http://127.0.0.1:${PORT}`;

// Self-contained E2E (spec Scenario 5, Option A): the webServer builds the SPA,
// then launches uvicorn serving web/dist + /api/* on a single 127.0.0.1 origin,
// with the backend pointed at a seeded transactions fixture. No manual server
// start, no CORS/proxy layer.
export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: BASE_URL,
    trace: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command:
      'npm run build && cd .. && BUDGET_TRACKER_TRANSACTIONS_FILE="$PWD/web/tests/fixtures/transactions.json" ' +
      `uv run uvicorn budget_tracker.api.app:app --host 127.0.0.1 --port ${PORT}`,
    url: `${BASE_URL}/api/health`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
