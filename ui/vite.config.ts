import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const APP_SERVER = process.env.REACHY_APP_SERVER ?? "http://127.0.0.1:8042";

export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../src/everything_agent/web",
    emptyOutDir: true,
    license: { fileName: "THIRD_PARTY_LICENSES.md" },
  },
  server: {
    proxy: {
      "/api": { target: APP_SERVER, ws: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
