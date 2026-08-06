import { test, expect } from "@playwright/test";

test.describe("market data terminal first screen", () => {
  test("shows tape, filter controls, and collapsed Livermore shell", async ({ page }) => {
    await page.goto("/market-data", { waitUntil: "domcontentloaded" });

    const pageRoot = page.locator('[data-testid="market-data-page"]');
    await expect(pageRoot).toBeVisible();
    await expect(pageRoot).toHaveAttribute("data-layout-rev", "2026-07-01-redesign");

    const ticker = page.locator('[data-testid="market-data-terminal-ticker"]');
    await expect(ticker).toBeVisible({ timeout: 30_000 });

    await expect(page.getByTestId("market-data-curve-filter")).toBeVisible();
    await expect(page.getByTestId("market-data-source-filter")).toBeVisible();
    await expect(page.getByTestId("market-data-workbench-shared-meta")).toContainText("口径摘要");

    const livermoreCollapse = page.locator('[data-testid="market-data-livermore-collapse"]');
    await expect(livermoreCollapse).toBeVisible();
    await expect(page.locator('[data-testid="market-data-livermore-panel"]')).toHaveCount(0);

    const fxFormalCollapse = page.locator('[data-testid="market-data-fx-formal-collapse"]');
    await expect(fxFormalCollapse).toBeVisible();
    await expect(page.locator('[data-testid="market-data-fx-formal-panel"]')).toHaveCount(0);

    const extendedTerminalMount = page.locator('[data-lazy-mount="extended-terminal"]');
    await expect(extendedTerminalMount).toBeAttached();
    await extendedTerminalMount.scrollIntoViewIfNeeded();
    const extendedTerminalCollapse = page.getByTestId("market-data-extended-terminal-collapse");
    await expect(extendedTerminalCollapse).toBeVisible();
    await extendedTerminalCollapse.locator(".ant-collapse-header").first().click();

    const pendingSummary = page.getByTestId("market-data-source-pending-summary");
    await expect(pendingSummary).toBeVisible();
    const pendingNote = page.getByTestId("market-data-source-pending-contract-note");
    await expect(pendingNote).toBeVisible();
    await expect.poll(async () => ((await pendingNote.textContent()) ?? "").trim()).toMatch(/^\u00b7\s*\S.+$/);
  });
});
