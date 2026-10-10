import { test, expect } from "@playwright/test";

test.describe("market data terminal first screen", () => {
  test("shows the KPI band, filter controls, and the retired-surface nav cards", async ({ page }) => {
    await page.goto("/market-data", { waitUntil: "domcontentloaded" });

    const pageRoot = page.locator('[data-testid="market-data-page"]');
    await expect(pageRoot).toBeVisible();
    await expect(pageRoot).toHaveAttribute("data-layout-rev", "2026-07-01-redesign");

    await expect(page.getByTestId("market-data-kpi-band")).toBeVisible({ timeout: 30_000 });
    // The former tape duplicated the KPI band and was intentionally removed.
    await expect(page.getByTestId("market-data-terminal-ticker")).toHaveCount(0);

    await expect(page.getByTestId("market-data-curve-filter")).toBeVisible();
    await expect(page.getByTestId("market-data-source-filter")).toBeVisible();
    await expect(page.getByTestId("market-data-workbench-shared-meta")).toContainText("口径摘要");

    // 02 区三 Tab 与 Livermore 折叠区已退役（IA 阶段 2）：主列只留纯导航证据卡。
    await expect(page.locator('[data-testid="market-data-macro-depth-card"]')).toHaveCount(0);
    await expect(page.locator('[data-testid="market-data-livermore-collapse"]')).toHaveCount(0);
    await expect(page.locator('[data-testid="market-data-livermore-panel"]')).toHaveCount(0);
    await expect(page.getByTestId("market-data-rate-trend-panel")).toContainText("收益率走势");

    const strategyEvidenceCard = page.getByTestId("market-data-strategy-evidence-card");
    await strategyEvidenceCard.scrollIntoViewIfNeeded();
    await expect(strategyEvidenceCard).toBeVisible();
    await expect(page.getByTestId("market-data-strategy-evidence-link")).toHaveAttribute(
      "href",
      "/cross-asset#cross-asset-zone-linkage",
    );

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
