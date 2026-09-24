import { test, expect } from "@playwright/test";

async function openMarketData(page) {
  await page.goto("/market-data", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("market-data-page")).toBeVisible({ timeout: 30_000 });
  await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => undefined);
}

async function activateWithKeyboard(locator) {
  await locator.scrollIntoViewIfNeeded();
  await locator.focus();
  await locator.press("Enter");
}

test.describe("market data workflow smoke", () => {
  test("spreads tab, linkage collapse, and tushare currency filter", async ({ page }) => {
    await openMarketData(page);

    await activateWithKeyboard(page.getByTestId("market-data-macro-tab-trigger-spreads"));
    const spreadsPanel = page.getByTestId("market-data-macro-tab-spreads");
    await expect(spreadsPanel).toBeVisible();
    const spreadTable = spreadsPanel.getByTestId("market-data-linkage-spread-table");
    await expect(spreadTable).toBeVisible({ timeout: 30_000 });
    await expect(spreadTable.locator(".market-data-spread-tenor-loading")).toHaveCount(0, { timeout: 30_000 });
    await expect(spreadTable.getByTestId("market-data-macro-spread-slot-5Y")).toBeVisible({ timeout: 30_000 });

    const linkageCollapse = page.getByTestId("market-data-linkage-collapse");
    await activateWithKeyboard(linkageCollapse.locator(".ant-collapse-header").first());
    await expect(linkageCollapse).toBeVisible();

    const auditBridge = page.getByTestId("market-data-linkage-spreads-audit");
    await expect(auditBridge).toBeVisible();
    await expect(page.getByTestId("market-data-linkage-spreads-audit-open")).toBeVisible();
    await page.getByTestId("market-data-linkage-spreads-audit-open").click();
    await expect(page.getByTestId("market-data-macro-tab-spreads")).toBeVisible();

    await activateWithKeyboard(
      page.getByTestId("market-data-tushare-collapse").locator(".ant-collapse-header").first(),
    );
    const tushareSection = page.getByTestId("market-data-tushare-supplement-section");
    await expect(tushareSection).toBeVisible();

    const currencyFilter = page.getByTestId("market-data-tushare-eco-currency-filter");
    await expect(currencyFilter).toBeVisible();
    const eurButton = currencyFilter.getByRole("button", { name: /EUR/ });
    if ((await eurButton.count()) > 0) {
      await eurButton.first().click();
      await expect(page.getByTestId("market-data-tushare-eco-summary")).toBeVisible();
    }
  });

  test("lower deck panels and tushare supplement render in the current shell", async ({ page }) => {
    await openMarketData(page);

    await expect(page.getByTestId("market-data-liquidity-deck")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("market-data-money-market-card")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("market-data-ncd-card")).toBeVisible({ timeout: 30_000 });

    await activateWithKeyboard(
      page.getByTestId("market-data-tushare-collapse").locator(".ant-collapse-header").first(),
    );
    await expect(page.getByTestId("market-data-tushare-supplement-section")).toBeVisible();
  });
});
