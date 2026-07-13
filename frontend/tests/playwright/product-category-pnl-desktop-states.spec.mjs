import { test, expect } from "@playwright/test";
import { buildMockApiEnvelope } from "../../src/mocks/mockApiEnvelope.ts";
import {
  buildMockProductCategoryAttributionEnvelope,
  buildMockProductCategoryPnlEnvelope,
} from "../../src/mocks/productCategoryPnl.ts";

const FORMAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888");
const FIXED_REPORT_DATE = "2026-02-28";

const DESKTOP_VIEWPORTS = [
  { name: "1280", width: 1280, height: 720 },
  { name: "1440", width: 1440, height: 720 },
];

const HEALTH_STATES = ["degraded", "empty", "error"];

async function installProductCategoryStateRoutes(page, state) {
  let baselineFailuresRemaining = state === "error" ? 1 : 0;

  await page.route("**/ui/pnl/product-category/dates", async (route) => {
    await route.fulfill({
      json: buildMockApiEnvelope(
        "product_category_pnl.dates",
        { report_dates: [FIXED_REPORT_DATE] },
        { basis: "formal", formal_use_allowed: true },
      ),
    });
  });

  await page.route("**/ui/pnl/product-category/manual-adjustments?*", async (route) => {
    await route.fulfill({
      json: {
        report_date: FIXED_REPORT_DATE,
        adjustment_count: 0,
        adjustment_limit: 20,
        adjustment_offset: 0,
        event_total: 0,
        event_limit: 20,
        event_offset: 0,
        adjustments: [],
        events: [],
      },
    });
  });

  await page.route("**/ui/pnl/product-category/attribution?*", async (route) => {
    const url = new URL(route.request().url());
    await route.fulfill({
      json: buildMockProductCategoryAttributionEnvelope({
        reportDate: url.searchParams.get("report_date") ?? FIXED_REPORT_DATE,
        compare: url.searchParams.get("compare") === "yoy" ? "yoy" : "mom",
      }),
    });
  });

  await page.route("**/ui/pnl/product-category?*", async (route) => {
    const url = new URL(route.request().url());
    const reportDate = url.searchParams.get("report_date") ?? FIXED_REPORT_DATE;
    const view = url.searchParams.get("view") ?? "monthly";
    const scenarioRatePct = url.searchParams.get("scenario_rate_pct") ?? undefined;
    const isSelectedBaseline = reportDate === FIXED_REPORT_DATE && !scenarioRatePct;

    if (isSelectedBaseline && baselineFailuresRemaining > 0) {
      baselineFailuresRemaining -= 1;
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "desktop-state-smoke" }),
      });
      return;
    }

    const envelope = buildMockProductCategoryPnlEnvelope({
      reportDate,
      view,
      scenarioRatePct,
    });
    if (isSelectedBaseline && state === "degraded") {
      await route.fulfill({
        json: {
          ...envelope,
          result_meta: {
            ...envelope.result_meta,
            quality_flag: "warning",
            vendor_status: "vendor_stale",
            fallback_mode: "latest_snapshot",
          },
        },
      });
      return;
    }
    if (isSelectedBaseline && state === "empty") {
      await route.fulfill({
        json: {
          ...envelope,
          result: {
            ...envelope.result,
            rows: [],
          },
        },
      });
      return;
    }
    await route.fulfill({ json: envelope });
  });
}

async function expectDesktopStateLayout(page, viewport, state) {
  const health = page.locator('[data-testid="product-category-data-health"]');
  await expect(health).toHaveAttribute("data-health-state", state);
  await expect(
    health.locator('[data-testid="product-category-formal-judgement-status"]'),
  ).toHaveText("正式判断阻断");

  const healthBox = await health.boundingBox();
  expect(healthBox).not.toBeNull();
  expect(healthBox.y).toBeLessThan(viewport.height);
  expect(healthBox.y + healthBox.height).toBeLessThanOrEqual(viewport.height);

  const governance = page.locator('[data-testid="product-category-governance-evidence"]');
  const governanceSummary = governance.locator("summary");
  await expect(governanceSummary).toBeVisible();
  await governanceSummary.click();
  await expect(governance).toHaveAttribute("open", "");
  await governanceSummary.click();
  await expect(governance).not.toHaveAttribute("open", "");

  const viewportMetrics = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(viewportMetrics.scrollWidth).toBeLessThanOrEqual(viewportMetrics.clientWidth);
}

for (const viewport of DESKTOP_VIEWPORTS) {
  for (const state of HEALTH_STATES) {
    test(`desktop ${state} state stays decision-safe at ${viewport.name}px`, async ({ page }, testInfo) => {
      const consoleErrors = [];
      const pageErrors = [];
      page.on("console", (message) => {
        if (message.type() === "error") {
          consoleErrors.push(message.text());
        }
      });
      page.on("pageerror", (error) => pageErrors.push(error.message));

      await installProductCategoryStateRoutes(page, state);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(`${FORMAL_STATE_BASE_URL}/product-category-pnl`, { waitUntil: "networkidle" });

      await expectDesktopStateLayout(page, viewport, state);
      if (state === "degraded") {
        await expect(page.locator('[data-testid="product-category-formal-readiness-band"]')).toBeVisible();
        await expect(page.locator('[data-testid="product-category-attribution"]')).toBeVisible();
        await expect(page.locator('[data-testid="product-category-footer-total"]')).toBeAttached();
      } else {
        await expect(page.locator('[data-testid="product-category-formal-readiness-band"]')).toBeHidden();
        await expect(page.locator('[data-testid="product-category-summary"]')).toBeHidden();
        await expect(page.locator('[data-testid="product-category-attribution"]')).toBeHidden();
        await expect(page.locator('[data-testid="product-category-financial-workspace"]')).toBeHidden();
        await expect(page.locator('[data-testid="product-category-operating-workspace"]')).toBeHidden();
        await expect(page.locator('[data-testid="product-category-backtest-workspace"]')).toBeHidden();
        await expect(page.locator('[data-testid="product-category-footer-total"]')).toBeHidden();
        await expect(page.locator('[data-testid="product-category-diagnostics-workspace"]')).toBeHidden();
      }

      await page.screenshot({
        path: testInfo.outputPath(`product-category-pnl-${state}-${viewport.name}.jpg`),
        type: "jpeg",
        quality: 90,
        fullPage: false,
        animations: "disabled",
      });

      if (state === "error") {
        await page.getByRole("button", { name: "重试正式基线" }).click();
        await expect(page.locator('[data-testid="product-category-data-health"]')).toHaveAttribute(
          "data-health-state",
          "ready",
        );
        await expect(page.locator('[data-testid="product-category-formal-readiness-band"]')).toBeVisible();
        await page.screenshot({
          path: testInfo.outputPath(`product-category-pnl-error-recovered-${viewport.name}.jpg`),
          type: "jpeg",
          quality: 90,
          fullPage: false,
          animations: "disabled",
        });
      }

      const unexpectedConsoleErrors = consoleErrors.filter(
        (message) => state !== "error" || !message.includes("503"),
      );
      expect(unexpectedConsoleErrors).toEqual([]);
      expect(pageErrors).toEqual([]);
    });
  }
}
