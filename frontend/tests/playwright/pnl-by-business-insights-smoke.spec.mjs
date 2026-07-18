import { readFileSync } from "node:fs";

import { AxeBuilder } from "@axe-core/playwright";
import { test, expect } from "@playwright/test";

const FORMAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888");
const GOLDEN_SAMPLE_ID = "GS-PNL-BUSINESS-INSIGHTS-A";
const GOLDEN_RESPONSE = JSON.parse(
  readFileSync(
    new URL(
      `../../../tests/golden_samples/${GOLDEN_SAMPLE_ID}/response.json`,
      import.meta.url,
    ),
    "utf8",
  ),
);

test.describe("governed PnL by-business Insights browser smoke", () => {
  test("renders the governed formal conclusions and has no critical axe violations", async ({ page }) => {
    const requestedFilters = [];

    await page.route("**/api/pnl/by-business-insights?*", async (route) => {
      const requestUrl = new URL(route.request().url());
      requestedFilters.push({
        year: requestUrl.searchParams.get("year"),
        asOfDate: requestUrl.searchParams.get("as_of_date"),
      });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(GOLDEN_RESPONSE),
      });
    });

    await page.goto(
      `${FORMAL_STATE_BASE_URL}/pnl-by-business-insights?year=2026&as_of_date=2026-02-28`,
      { waitUntil: "domcontentloaded" },
    );

    const pageRoot = page.locator('[data-testid="pnl-by-business-insights-page"]');
    await expect(pageRoot).toBeVisible({ timeout: 60_000 });
    await expect(page.locator('[data-testid="pnl-by-business-insights-contract-review"]')).toHaveCount(0);
    await expect.poll(() => requestedFilters.at(-1)).toEqual({
      year: "2026",
      asOfDate: "2026-02-28",
    });

    const contractStatus = page.locator('[data-testid="pnl-by-business-insights-contract-status"]');
    await expect(contractStatus).toContainText("warning");
    await expect(contractStatus).toContainText("none");
    await expect(contractStatus).toContainText("2026-02-28");
    await expect(contractStatus).toContainText("tr_pnl_business_insights_gs_a");

    const concentration = page.locator(
      '[data-testid="pnl-by-business-insights-concentration-kpis"]',
    );
    await expect(concentration).toContainText("53.12%");
    await expect(concentration).toContainText("100.00%");

    const shareDrift = page.locator('[data-testid="pnl-by-business-insights-share-drift-table"]');
    await expect(shareDrift).toContainText("+7.50pp");
    await expect(shareDrift).toContainText("-7.50pp");

    const reconciliation = page.locator(
      '[data-testid="pnl-by-business-insights-reconciliation-section"]',
    );
    await expect(reconciliation).toBeVisible();
    await expect(reconciliation).toContainText("非业务结论");

    const accessibility = await new AxeBuilder({ page })
      .include('[data-testid="pnl-by-business-insights-page"]')
      .analyze();
    const criticalViolations = accessibility.violations.filter(
      (violation) => violation.impact === "critical",
    );
    expect(criticalViolations).toEqual([]);
  });
});
