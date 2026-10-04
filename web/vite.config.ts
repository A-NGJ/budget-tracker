import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Two pages share one build:
//   index.html  encrypted workspace (Firebase Hosting serves this)
//   stats.html  legacy read-only stats over the plaintext FastAPI backend,
//               which FastAPI serves from web/dist on 127.0.0.1
// A relative base keeps asset URLs working under either origin.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { host: "127.0.0.1" },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        stats: resolve(__dirname, "stats.html"),
      },
    },
  },
});
