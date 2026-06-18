import { test, expect } from "@playwright/test";

async function openMarketData(page) {
  await page.goto("/market-data", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("market-data-page")).toBeVisible({ timeout: 30_000 });
  await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => undefined);
}

test.describe("market data workflow smoke", () => {
  test("spreads tab, linkage audit bridge, and tushare currency filter", async ({ page }) => {
    await openMarketData(page);

    await page.getByTestId("market-data-macro-tab-trigger-spreads").click();
    const spreadsPanel = page.getByTestId("market-data-macro-tab-spreads");
    await expect(spreadsPanel).toBeVisible();
    const spreadTable = spreadsPanel.getByTestId("market-data-linkage-spread-table");
    await expect(spreadTable).toBeVisible({ timeout: 30_000 });
    await expect(spreadTable.locator(".market-data-spread-tenor-loading")).toHaveCount(0, {
      timeout: 30_000,
    });
    await expect(spreadTable.getByTestId("market-data-macro-spread-slot-5Y")).toBeVisible({
      timeout: 15_000,
    });

    await page.getByText("宏观-债市联动（分析口径，点击展开）").click();
    await expect(page.getByTestId("market-data-linkage-spreads-audit")).toBeVisible();
    await page.getByTestId("market-data-linkage-spreads-audit-open").click();
    await expect(page.getByTestId("market-data-macro-tab-spreads")).toBeVisible();

    const tushareSection = page.getByTestId("market-data-tushare-supplement-section");
    await tushareSection.scrollIntoViewIfNeeded();
    await expect(tushareSection).toBeVisible();

    const currencyFilter = page.getByTestId("market-data-tushare-eco-currency-filter");
    await expect(currencyFilter).toBeVisible();
    const eurButton = currencyFilter.getByRole("button", { name: /EUR/ });
    if ((await eurButton.count()) > 0) {
      await eurButton.first().click();
      await expect(page.getByTestId("market-data-tushare-eco-summary")).toBeVisible();
    }
  });

  test("lower deck panels render with unified section shells", async ({ page }) => {
    await openMarketData(page);

    await expect(page.getByTestId("market-data-liquidity-deck")).toBeVisible();
    await expect(page.getByTestId("market-data-money-market-card")).toBeVisible();
    await expect(page.getByTestId("market-data-ncd-card")).toBeVisible();

    const newsSection = page.getByTestId("market-data-news-calendar");
    await newsSection.scrollIntoViewIfNeeded();
    await expect(newsSection).toBeVisible();
    await expect(newsSection).toHaveClass(/market-data-lower-deck-panel/);
  });
});
