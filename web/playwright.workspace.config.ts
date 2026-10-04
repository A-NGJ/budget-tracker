import { defineConfig, devices } from "@playwright/test";

// Encrypted-workspace end-to-end tests against local Firebase emulators only.
// The `demo-` project id keeps the Firebase CLI and SDK off real projects, so
// these runs need no credentials and cannot incur billing.
const APP_PORT = 5180;

export default defineConfig({
  testDir: "./tests/workspace",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: `http://127.0.0.1:${APP_PORT}`,
    trace: "retain-on-failure",
  },
  // Edge shares Chromium's engine; Playwright's Chromium build stands in for
  // both Chrome and Edge. Firefox and WebKit (Safari's engine) run as-is.
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  webServer: [
    {
      command: "npx firebase emulators:start --only auth,firestore --project demo-budget-tracker --config ../firebase.json",
      // Auth starts after Firestore, so its port signals both are ready.
      url: "http://127.0.0.1:9099/",
      reuseExistingServer: false,
      timeout: 120_000,
      // SIGINT lets the Firebase CLI stop the Java emulator; SIGKILL orphans it.
      gracefulShutdown: { signal: "SIGINT", timeout: 15_000 },
    },
    {
      command: `npx vite build --mode emulator --outDir dist-emulator && npx vite preview --mode emulator --outDir dist-emulator --port ${APP_PORT} --strictPort`,
      url: `http://127.0.0.1:${APP_PORT}/`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
