import { AxeBuilder } from "@axe-core/playwright";
import { test, expect } from "@playwright/test";

const smokePages = [
  {
    slug: "dashboard",
    path: "/",
    readySelector: '[data-testid="dashboard-home-page"]',
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

test.describe("frontend accessibility + visual smoke", () => {
  for (const smokePage of smokePages) {
    test(`${smokePage.slug} has no critical axe violations`, async ({ page }, testInfo) => {
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
