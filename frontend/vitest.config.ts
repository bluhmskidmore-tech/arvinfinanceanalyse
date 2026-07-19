import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { availableParallelism } from "node:os";

const maxWorkers = Math.max(1, Math.min(4, availableParallelism() - 1));

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
    exclude: ["tests/playwright/**", "node_modules/**", "dist/**"],
    testTimeout: 15000,
    // Cap workers to avoid Windows/thread-pool thrash on large page tests.
    maxWorkers,
    fileParallelism: true,
  },
});
