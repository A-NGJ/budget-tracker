import { defineConfig, devices } from "@playwright/test";

// Encrypted-workspace end-to-end tests against local Firebase emulators only.
// The `demo-` project id keeps the Firebase CLI and SDK off real projects, so
// these runs need no credentials and cannot incur billing.
const APP_PORT = 5180;
const brandedChannels = (process.env.BRANDED_BROWSERS ?? "")
  .split(",")
  .map((channel) => channel.trim())
  .filter((channel) => channel === "chrome" || channel === "msedge");

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
  // Engine projects always run: Playwright's Chromium, Firefox and WebKit
  // (Safari's engine) builds. BRANDED_BROWSERS adds the installed Google Chrome
  // and Microsoft Edge (comma-separated channels, e.g. "chrome,msedge"); CI
  // sets both. Branded Safari cannot be driven by Playwright, so WebKit is the
  // Safari check.
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
    ...brandedChannels.map((channel) => ({ name: channel, use: { ...devices[channel === "msedge" ? "Desktop Edge" : "Desktop Chrome"], channel } })),
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
