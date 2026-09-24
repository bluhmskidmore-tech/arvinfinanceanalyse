import { expect, test } from "@playwright/test";
import { buildMockApiEnvelope } from "../../src/mocks/mockApiEnvelope.ts";
import { mockHomeSnapshot } from "../../src/mocks/workbench.ts";

const GEOMETRY_TOLERANCE_PX = 1.5;
const REAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888");

function numeric(raw, unit, display) {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: false,
  };
}

async function installHoldingFixture(page) {
  const reportDate = "2026-04-30";
  const snapshot = buildMockApiEnvelope("home.snapshot", {
    ...mockHomeSnapshot,
    report_date: reportDate,
  });
  const holdings = buildMockApiEnvelope("bond_analytics.top_holdings", {
    report_date: reportDate,
    top_n: 14,
    items: [
      {
        instrument_code: "240001.IB",
        instrument_name: "测试国债01",
        issuer_name: "财政部",
        rating: "AAA",
        asset_class: "利率债",
        market_value: numeric(12_350_000_000, "yuan", "123.50 亿"),
        face_value: numeric(12_000_000_000, "yuan", "120.00 亿"),
        ytm: numeric(0.0236, "pct", "2.36%"),
        modified_duration: numeric(4.21, "ratio", "4.21"),
        weight: numeric(0.0961, "pct", "9.61%"),
      },
    ],
    total_market_value: numeric(12_350_000_000, "yuan", "123.50 亿"),
    warnings: [],
    computed_at: "2026-04-30T18:00:00Z",
  });

  await page.route("**/ui/home/snapshot**", async (route) => {
    await route.fulfill({
      body: JSON.stringify(snapshot),
      contentType: "application/json",
      status: 200,
    });
  });
  await page.route("**/api/bond-analytics/top-holdings?*", async (route) => {
    await route.fulfill({
      body: JSON.stringify(holdings),
      contentType: "application/json",
      status: 200,
    });
  });
}

async function readBox(locator, label) {
  const box = await locator.boundingBox();
  expect(box, `${label} must have measurable geometry`).not.toBeNull();
  return box;
}

test.describe("dashboard home holding detail drawer", () => {
  test("overlays the expanded work grid without shifting its x-position or width", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await installHoldingFixture(page);
    await page.goto(new URL("/", REAL_STATE_BASE_URL).toString(), {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("dashboard-home-page")).toBeVisible({
      timeout: 60_000,
    });

    await page.getByTestId("dashboard-home-deferred-sentinel").scrollIntoViewIfNeeded();

    const workGrid = page.getByTestId("dashboard-home-work-grid");
    const openHolding = page.getByTestId("dashboard-home-holding-open").first();
    await expect(workGrid).toBeVisible({ timeout: 60_000 });
    await expect(openHolding).toBeVisible({ timeout: 60_000 });
    await openHolding.scrollIntoViewIfNeeded();
    await page.evaluate(
      () =>
        new Promise((resolve) => {
          requestAnimationFrame(() => requestAnimationFrame(resolve));
        }),
    );

    const before = await readBox(workGrid, "work grid before opening the drawer");
    await openHolding.click();

    const drawer = page.getByTestId("dashboard-home-holding-detail-drawer");
    await expect(drawer).toBeVisible({ timeout: 60_000 });
    await page.evaluate(
      () =>
        new Promise((resolve) => {
          requestAnimationFrame(() => requestAnimationFrame(resolve));
        }),
    );
    const after = await readBox(workGrid, "work grid after opening the drawer");

    expect(Math.abs(after.x - before.x)).toBeLessThanOrEqual(GEOMETRY_TOLERANCE_PX);
    expect(Math.abs(after.width - before.width)).toBeLessThanOrEqual(
      GEOMETRY_TOLERANCE_PX,
    );

    const overlay = await page.evaluate(() => {
      const grid = document.querySelector('[data-testid="dashboard-home-work-grid"]');
      const drawerElement = document.querySelector(
        '[data-testid="dashboard-home-holding-detail-drawer"]',
      );
      if (!(grid instanceof HTMLElement) || !(drawerElement instanceof HTMLElement)) {
        return null;
      }

      const gridRect = grid.getBoundingClientRect();
      const drawerRect = drawerElement.getBoundingClientRect();
      const left = Math.max(gridRect.left, drawerRect.left, 0);
      const right = Math.min(gridRect.right, drawerRect.right, window.innerWidth);
      const top = Math.max(gridRect.top, drawerRect.top, 0);
      const bottom = Math.min(gridRect.bottom, drawerRect.bottom, window.innerHeight);
      const overlapWidth = Math.max(0, right - left);
      const overlapHeight = Math.max(0, bottom - top);
      const pointX = left + overlapWidth / 2;
      const pointY = top + overlapHeight / 2;
      const topElement =
        overlapWidth > 0 && overlapHeight > 0
          ? document.elementFromPoint(pointX, pointY)
          : null;

      return {
        isNestedInsideGrid: grid.contains(drawerElement),
        overlapWidth,
        overlapHeight,
        drawerOwnsOverlapPoint:
          topElement !== null && drawerElement.contains(topElement),
      };
    });

    expect(overlay, "drawer and work grid must both be measurable").not.toBeNull();
    expect(overlay.isNestedInsideGrid).toBe(false);
    expect(overlay.overlapWidth).toBeGreaterThan(0);
    expect(overlay.overlapHeight).toBeGreaterThan(0);
    expect(overlay.drawerOwnsOverlapPoint).toBe(true);
  });
});
