import { test, expect } from "@playwright/test";

// Keep in sync with frontend/src/mocks/bondTradingDeskDrillFixtures.ts
const MOCK_BOND_TRADING_DESK_INSTRUMENT_CODE = "230210.IB";
const MOCK_POSITIONS_BOND_TRADING_DESK_CODE = "149001.SZ";

test.describe.configure({ mode: "serial" });

const dataSource = process.env.VITE_DATA_SOURCE ?? "real";
const usesMockDrillFixtures =
  dataSource === "mock" || process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1";

async function openBondAnalysis(page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/bond-analysis", { waitUntil: "domcontentloaded" });
  await expect(page.locator('[data-testid="bond-analysis-overview"]')).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.locator('[data-testid="bond-analysis-cockpit-conclusion"]')).toBeVisible({
    timeout: 60_000,
  });
}

test.describe("bond trading desk drill paths", () => {
  test.beforeAll(() => {
    test.skip(
      !usesMockDrillFixtures,
      "深钻回归需要 mock 样例：请设置 VITE_DATA_SOURCE=mock 或 MOSS_PLAYWRIGHT_USE_WEB_SERVER=1。",
    );
  });

  test("opens trading desk from bond-analysis holding link when data is available", async ({
    page,
  }) => {
    await openBondAnalysis(page);

    const link = page
      .getByTestId("bond-analysis-holdings-raw-grid")
      .getByTestId(`bond-trading-desk-link-${MOCK_BOND_TRADING_DESK_INSTRUMENT_CODE}`);
    await expect(link).toBeVisible({ timeout: 60_000 });

    const href = await link.getAttribute("href");
    expect(href).toMatch(
      new RegExp(`/bond-trading-desk\\?bond_code=${MOCK_BOND_TRADING_DESK_INSTRUMENT_CODE}`),
    );
    await link.click();

    await expect(page.getByTestId("bond-trading-desk-page")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("bond-trading-desk-conclusion")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("bond-trading-desk-compose-strip")).toBeVisible();
  });

  test("opens trading desk from positions bond table when rows are available", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/positions", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("positions-page")).toBeVisible({ timeout: 60_000 });

    const link = page.locator(
      `[data-testid="positions-bond-trading-desk-link-${MOCK_POSITIONS_BOND_TRADING_DESK_CODE}"]`,
    );
    await expect(link).toBeVisible({ timeout: 60_000 });

    const href = await link.getAttribute("href");
    expect(href).toMatch(
      new RegExp(`/bond-trading-desk\\?bond_code=${MOCK_POSITIONS_BOND_TRADING_DESK_CODE}`),
    );
    await link.click();

    await expect(page.getByTestId("bond-trading-desk-page")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("bond-trading-desk-conclusion")).toBeVisible({ timeout: 60_000 });
  });
});
