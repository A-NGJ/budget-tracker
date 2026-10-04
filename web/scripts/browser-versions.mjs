// Print the browser builds the workspace suite runs against, so test results
// can be recorded with exact versions. Usage: node scripts/browser-versions.mjs [chrome,msedge]
import { chromium, firefox, webkit } from "@playwright/test";

const targets = [
  ["chromium", chromium, {}],
  ["firefox", firefox, {}],
  ["webkit", webkit, {}],
  ...(process.argv[2] ?? process.env.BRANDED_BROWSERS ?? "")
    .split(",")
    .filter(Boolean)
    .map((channel) => [channel, chromium, { channel }]),
];

let failed = false;
for (const [name, type, options] of targets) {
  try {
    const browser = await type.launch({ timeout: 60_000, ...options });
    console.log(`${name}: ${browser.version()} (${process.platform}-${process.arch})`);
    await browser.close();
  } catch (error) {
    failed = true;
    console.log(`${name}: failed to launch: ${String(error).split("\n")[0]}`);
  }
}
process.exit(failed ? 1 : 0);
