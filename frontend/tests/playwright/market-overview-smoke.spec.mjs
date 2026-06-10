import { test, expect } from "@playwright/test";

const MARKET_READY_SELECTOR = '[data-testid="module-workbench-home"]';
const REQUIRED_MARKET_SURFACES = [
  "module-home-market-macro-ticker",
  "module-home-kpi-strip",
  "module-home-market-matrix",
  "module-home-market-terminal",
  "module-home-yield-curve",
  "module-home-macro-snapshot",
  "module-home-market-actions",
  "module-home-observation",
];

const suspiciousTextPattern = /[\uFFFD]|\u93C3|\u9359|\u5BF0|\u9215/;

async function openMarketOverview(page, viewport) {
  await page.setViewportSize(viewport);
  await page.goto("/market-overview", { waitUntil: "domcontentloaded" });
  await expect(page.locator(MARKET_READY_SELECTOR)).toBeVisible({ timeout: 60_000 });
  await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => undefined);
}

test.describe("market overview browser smoke", () => {
  test("renders the market ticker, KPI trend cues, and action queue on desktop", async ({ page }) => {
    await openMarketOverview(page, { width: 1440, height: 1100 });

    for (const testId of REQUIRED_MARKET_SURFACES) {
      await expect(page.getByTestId(testId), `${testId} should render`).toBeVisible();
    }

    const root = page.getByTestId("module-workbench-home");
    await expect(root).not.toHaveText(suspiciousTextPattern);

    const ticker = page.getByTestId("module-home-market-macro-ticker");
    await expect(ticker.locator("svg").first()).toBeVisible();
    await expect(ticker).toContainText("DR007");

    const kpis = page.getByTestId("module-home-kpi-strip");
    await expect(kpis.locator("svg")).toHaveCount(3);
    await expect(page.getByTestId("module-home-market-kpi-cross-asset-detail")).toHaveAttribute(
      "data-change",
      "down",
    );
    await expect(page.getByTestId("module-home-market-matrix-cell-rates-summary")).toHaveAttribute(
      "data-change",
      "down",
    );

    const rateRows = page.locator('[data-testid^="module-home-rate-"]');
    if ((await rateRows.count()) > 0) {
      await expect(rateRows.first().locator("[data-change]")).toHaveAttribute(
        "data-change",
        /^(up|down|flat)$/,
      );
    }

    const actionQueue = page.getByTestId("module-home-market-actions");
    await expect(actionQueue).toContainText("\u786E\u8BA4\u5173\u952E\u5229\u7387\u53D8\u52A8");
    await expect(actionQueue).toContainText("\u8DDF\u8E2A\u8DE8\u8D44\u4EA7\u4F20\u5BFC");
    await expect(page.getByTestId("module-home-observation").locator("a")).toHaveCount(6);
  });

  test("keeps the market overview first-screen surfaces inside a mobile viewport", async ({ page }) => {
    await openMarketOverview(page, { width: 390, height: 844 });

    const overflow = await page.evaluate(() =>
      Array.from(document.querySelectorAll("[data-testid]"))
        .filter((element) => !element.closest('[data-testid="module-home-market-macro-ticker"]'))
        .map((element) => {
          const rect = element.getBoundingClientRect();
          return {
            id: element.getAttribute("data-testid"),
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            width: Math.round(rect.width),
          };
        })
        .filter((box) => box.width > 0 && (box.left < -2 || box.right > window.innerWidth + 2))
        .slice(0, 20),
    );

    expect(overflow, JSON.stringify(overflow, null, 2)).toEqual([]);
    const ticker = page.getByTestId("module-home-market-macro-ticker");
    await expect(ticker).toBeVisible();
    const tickerBox = await ticker.boundingBox();
    expect(tickerBox?.x ?? 0).toBeGreaterThanOrEqual(0);
    expect((tickerBox?.x ?? 0) + (tickerBox?.width ?? 0)).toBeLessThanOrEqual(390);
    await expect(ticker).toContainText("DR007");
    await expect(page.getByTestId("module-home-kpi-strip")).toBeVisible();
    await expect(page.getByTestId("module-home-market-actions")).toBeVisible();
  });
});
