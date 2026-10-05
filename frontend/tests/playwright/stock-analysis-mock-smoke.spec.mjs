import { test, expect } from "@playwright/test";

const dataSource = process.env.VITE_DATA_SOURCE ?? "real";

test.describe("stock analysis mock browser smoke", () => {
  test("renders the mock review state with readable Chinese labels", async ({ page }) => {
    test.skip(dataSource !== "mock", "Stock analysis mock smoke requires VITE_DATA_SOURCE=mock.");

    await page.goto("/stock-analysis", { waitUntil: "domcontentloaded" });

    const stockPage = page.getByTestId("stock-analysis-page");
    await expect(stockPage).toBeVisible();
    const reviewQueue = page.getByTestId("stock-analysis-review-queue");
    await expect(reviewQueue).toBeVisible({ timeout: 30_000 });
    await expect(reviewQueue).toContainText("多因子");

    const researchDesk = page.getByTestId("stock-analysis-research-desk");
    await expect(researchDesk).toContainText("盘前未闭合");
    await page.getByTestId("stock-analysis-deep-research-summary").click();

    // Mock qualification is unavailable: current observations remain readable,
    // while the qualified strategy workspace must stay unmounted.
    const readOnlyResearch = page.getByTestId("stock-analysis-readonly-research");
    await expect(readOnlyResearch).toBeVisible({ timeout: 30_000 });
    await expect(readOnlyResearch).toContainText("个股详情");
    await expect(readOnlyResearch).toContainText("K线观察");
    await expect(readOnlyResearch).toContainText("当前行业快照");
    await expect(readOnlyResearch).toContainText("详情 已就绪 / K线 已就绪 / 行业 已匹配");
    await expect(readOnlyResearch).toContainText("盘前资格未闭合，未读取");
    await expect(readOnlyResearch).toContainText("保持关闭");
    await expect(page.getByTestId("stock-analysis-stock-selection")).toHaveCount(0);
    await expect(page.getByTestId("stock-analysis-events-monitoring")).toHaveCount(0);

    const actionRail = page.getByTestId("stock-analysis-action-rail");
    await expect(actionRail).toContainText("风险与执行结论保持关闭");
    await expect(actionRail).toContainText("只读观察，不形成交易指令");
    await expect(stockPage).not.toContainText("concept membership table pending");
    await expect(readOnlyResearch).not.toContainText("读取失败");
  });
});
