import { test, expect } from "@playwright/test";

test.describe("stock analysis mock browser smoke", () => {
  test("renders candidate filters with readable Chinese labels", async ({ page }) => {
    await page.goto("/stock-analysis", { waitUntil: "domcontentloaded" });

    await expect(page.getByTestId("stock-analysis-page")).toBeVisible();

    const filterStatus = page.getByTestId("stock-review-filter-status");
    await expect(filterStatus).toBeVisible({ timeout: 30_000 });
    await expect(filterStatus).toContainText("全部行业");
    await expect(filterStatus).toContainText("显示 2 / 2 个候选");
    await expect(page.getByTestId("stock-candidate-000001.SZ")).toBeVisible();

    await page.getByTestId("sector-filter-chip-801002").click();

    await expect(page.getByTestId("stock-candidate-000001.SZ")).toHaveCount(0);
    await expect(page.getByTestId("stock-candidate-000002.SZ")).toBeVisible();
    await expect(filterStatus).toContainText("显示 1 / 2 个候选");

    const eventsMonitor = page.getByTestId("stock-analysis-events-monitoring");
    await expect(eventsMonitor).toContainText("题材观察阻断");
    await expect(eventsMonitor).toContainText("概念归属表待确认");
    await expect(eventsMonitor).not.toContainText("concept membership table pending");
  });
});
