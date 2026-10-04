import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    projects: [
      {
        test: {
          name: "unit",
          include: ["tests/unit/**/*.test.ts"],
          environment: "node",
        },
      },
      {
        test: {
          name: "rules",
          include: ["tests/rules/**/*.test.ts"],
          environment: "node",
          testTimeout: 20_000,
          hookTimeout: 30_000,
          fileParallelism: false,
        },
      },
    ],
  },
});
