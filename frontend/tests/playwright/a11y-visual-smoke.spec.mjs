import { AxeBuilder } from "@axe-core/playwright";
import { test, expect } from "@playwright/test";

const smokePages = [
  {
    slug: "dashboard",
    path: "/",
    readySelector: '[data-testid="fixed-income-dashboard-page"]',
  },
  {
    slug: "balance-analysis",
    path: "/balance-analysis",
    readySelector: '[data-testid="balance-analysis-page"]',
    excludeSelectors: [".ag-theme-alpine", ".ag-root"],
  },
  {
    slug: "product-category-pnl",
    path: "/product-category-pnl",
    readySelector: '[data-testid="product-category-page"]',
  },
  {
    slug: "ledger-pnl",
    path: "/ledger-pnl",
    readySelector: '[data-testid="ledger-pnl-page"]',
    axeSelector: '[data-testid="ledger-pnl-page-title"], [data-testid="ledger-pnl-monthly-analysis-overview"]',
    screenshotFullPage: false,
  },
];

async function probeServer(baseURL) {
  try {
    const response = await fetch(baseURL, { method: "GET" });
    if (!response.ok) {
      return {
        ok: false,
        reason: `Skipping smoke: frontend server at ${baseURL} returned HTTP ${response.status}.`,
      };
    }
    return { ok: true, reason: "" };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      ok: false,
      reason: `Skipping smoke: frontend server at ${baseURL} is unavailable (${message}).`,
    };
  }
}

test.describe("frontend accessibility + visual smoke", () => {
  let serverCheck;

  test.beforeAll(async ({ baseURL }) => {
    serverCheck = await probeServer(baseURL ?? "http://127.0.0.1:5888");
  });

  for (const smokePage of smokePages) {
    test(`${smokePage.slug} has no critical axe violations`, async ({ page }, testInfo) => {
      test.skip(!serverCheck.ok, serverCheck.reason);

      await page.goto(smokePage.path, { waitUntil: "networkidle" });
      const pageRoot = page.locator(smokePage.readySelector);
      await expect(pageRoot).toBeVisible();

      let axeBuilder = new AxeBuilder({ page }).include(smokePage.axeSelector ?? smokePage.readySelector);
      for (const selector of smokePage.excludeSelectors ?? []) {
        axeBuilder = axeBuilder.exclude(selector);
      }
      const { violations } = await axeBuilder.analyze();
      const criticalViolations = violations.filter((violation) => violation.impact === "critical");

      await page.screenshot({
        path: testInfo.outputPath(`${smokePage.slug}.png`),
        fullPage: smokePage.screenshotFullPage ?? true,
      });

      expect(
        criticalViolations,
        criticalViolations
          .map((violation) => `${violation.id}: ${violation.help}`)
          .join("\n"),
      ).toEqual([]);
    });
  }
});
