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
  test("linkage summary card, cross-asset handoff, and tushare currency filter", async ({ page }) => {
    await openMarketData(page);

    // IA 阶段 2：02 区利差 Tab 与联动折叠区退役，明细读面由 /cross-asset 承接。
    await expect(page.getByTestId("market-data-macro-tab-trigger-spreads")).toHaveCount(0);
    await expect(page.getByTestId("market-data-linkage-collapse")).toHaveCount(0);
    await expect(page.getByTestId("market-data-linkage-spreads-audit")).toHaveCount(0);

    const linkageSummary = page.getByTestId("market-data-linkage-summary-card");
    await linkageSummary.scrollIntoViewIfNeeded();
    await expect(linkageSummary).toBeVisible();
    await expect(page.getByTestId("market-data-linkage-caveat")).toContainText("分析口径");
    // 摘要卡近视口才发联动请求：等载荷回来后报告日期必须显式可读。
    await expect
      .poll(
        async () =>
          ((await page.getByTestId("market-data-linkage-summary-report-date").textContent()) ?? "").trim(),
        { timeout: 30_000 },
      )
      .toMatch(/报告日期\s*\d{4}-\d{2}-\d{2}/);
    await expect(page.getByTestId("market-data-linkage-summary-link")).toHaveAttribute(
      "href",
      "/cross-asset#cross-asset-zone-linkage",
    );

    await page.getByTestId("market-data-linkage-summary-link").click();
    await expect(page.getByTestId("cross-asset-zone-linkage")).toBeVisible({ timeout: 30_000 });

    await openMarketData(page);
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
