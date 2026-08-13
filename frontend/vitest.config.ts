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
    // 覆盖率仅在显式传 `--coverage` 时启用（Vitest 默认 enabled=false），常规 `vitest run` 零开销。
    coverage: {
      provider: "v8",
      reporter: ["text-summary", "text", "html", "json-summary"],
      reportsDirectory: "./coverage",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/test/**", "src/**/*.test.{ts,tsx}", "src/**/*.d.ts", "src/mocks/**"],
      // 个别用例抖动失败时仍产出覆盖率报告，避免基线/门禁观测被吞。
      reportOnFailure: true,
      // 宽松底线：2026-08-13 全量基线 statements 86.01 / branches 76.77 / functions 88.24 / lines 87.01，
      // 各维度向下取整再减 2 个百分点。仅 --coverage 时校验。
      thresholds: {
        statements: 84,
        branches: 74,
        functions: 86,
        lines: 85,
      },
    },
  },
});
