import { test, expect } from "@playwright/test";

const dataSource = process.env.VITE_DATA_SOURCE ?? "real";

test.describe("stock analysis mock browser smoke", () => {
  test("renders the mock review state with readable Chinese labels", async ({ page }) => {
    test.skip(dataSource !== "mock", "Stock analysis mock smoke requires VITE_DATA_SOURCE=mock.");

    await page.goto("/stock-analysis", { waitUntil: "domcontentloaded" });

    await expect(page.getByTestId("stock-analysis-page")).toBeVisible();

    const observationPreview = page.getByTestId("stock-analysis-observation-preview");
    await expect(observationPreview).toBeVisible({ timeout: 30_000 });
    await expect(observationPreview).toContainText("多因子");
    await expect(observationPreview).toContainText("超跌");

    const eventsMonitor = page.getByTestId("stock-analysis-events-monitoring");
    await expect(eventsMonitor).toContainText("题材观察阻断");
    await expect(eventsMonitor).not.toContainText("concept membership table pending");
  });
});
