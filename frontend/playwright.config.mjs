import { defineConfig } from "@playwright/test";

const playwrightPort = process.env.MOSS_PLAYWRIGHT_PORT ?? "5888";
const playwrightBaseURL =
  process.env.MOSS_PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${playwrightPort}`;
const playwrightOutputDir =
  process.env.MOSS_PLAYWRIGHT_OUTPUT_DIR ?? "../.codex-tmp/playwright-results";

export default defineConfig({
  testDir: "./tests/playwright",
  timeout: 90_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  outputDir: playwrightOutputDir,
  webServer:
    process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
      ? {
          command: `npm run dev -- --host 127.0.0.1 --port ${playwrightPort}`,
          url: playwrightBaseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          env: {
            ...process.env,
            VITE_DATA_SOURCE: process.env.VITE_DATA_SOURCE ?? "real",
          },
        }
      : undefined,
  use: {
    baseURL: playwrightBaseURL,
    trace: "retain-on-failure",
    screenshot: "off",
    video: "off",
  },
});
