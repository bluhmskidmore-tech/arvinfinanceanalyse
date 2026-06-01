import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/playwright",
  timeout: 90_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  outputDir: "../.codex-tmp/playwright-results",
  webServer:
    process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
      ? {
          command: "npm run dev -- --host 127.0.0.1 --port 5888",
          url: process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888",
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        }
      : undefined,
  use: {
    baseURL: process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888",
    trace: "retain-on-failure",
    screenshot: "off",
    video: "off",
  },
});
