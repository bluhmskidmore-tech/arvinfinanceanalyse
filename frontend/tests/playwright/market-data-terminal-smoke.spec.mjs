import { test, expect } from "@playwright/test";

test.describe("market data terminal first screen", () => {
  test("shows tape, filter summary, and collapsed Livermore shell", async ({ page }) => {
    await page.goto("/market-data", { waitUntil: "domcontentloaded" });

    const pageRoot = page.locator('[data-testid="market-data-page"]');
    await expect(pageRoot).toBeVisible();
    await expect(pageRoot).toHaveAttribute("data-layout-rev", "2026-06-10e");

    const ticker = page.locator('[data-testid="market-data-terminal-ticker"]');
    await expect(ticker).toBeVisible({ timeout: 30_000 });

    const filterSummary = page.locator('[data-testid="market-data-active-filter-summary"]');
    await expect(filterSummary).toBeVisible();
    await expect(filterSummary).toContainText("全部");

    const livermoreCollapse = page.locator('[data-testid="market-data-livermore-collapse"]');
    await expect(livermoreCollapse).toBeVisible();
    await expect(page.locator('[data-testid="market-data-livermore-panel"]')).toHaveCount(0);

    const fxFormalCollapse = page.locator('[data-testid="market-data-fx-formal-collapse"]');
    await expect(fxFormalCollapse).toBeVisible();
    await expect(page.locator('[data-testid="market-data-fx-formal-panel"]')).toHaveCount(0);

    await expect(page.locator('[data-testid="market-data-source-pending-contract-note"]')).toContainText(
      "待契约",
    );
  });
});
