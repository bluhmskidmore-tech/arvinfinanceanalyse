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
const PRIOR_REPORT_DATE = "2026-01-31";

const DESKTOP_VIEWPORTS = [
  { name: "1280", width: 1280, height: 720 },
  { name: "1440", width: 1440, height: 720 },
];

const HEALTH_STATES = ["degraded", "empty", "error"];

async function installProductCategoryStateRoutes(page, state, options = {}) {
  let baselineFailuresRemaining = state === "error" ? 1 : 0;
  const reportDates = options.reportDates ?? [FIXED_REPORT_DATE];

  await page.route("**/ui/pnl/product-category/dates", async (route) => {
    await route.fulfill({
      json: buildMockApiEnvelope(
        "product_category_pnl.dates",
        { report_dates: reportDates },
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

async function installHeldDatesRoute(page) {
  let shouldHold = true;
  let releaseRequest = null;

  await page.route("**/ui/pnl/product-category/dates", async (route) => {
    if (!shouldHold) {
      await route.fallback();
      return;
    }
    shouldHold = false;
    await new Promise((resolve) => {
      releaseRequest = resolve;
    });
    await route.fallback();
  });

  return () => releaseRequest?.();
}

async function installDatesFailureRoute(page) {
  let failuresRemaining = 1;
  await page.route("**/ui/pnl/product-category/dates", async (route) => {
    if (failuresRemaining === 0) {
      await route.fallback();
      return;
    }
    failuresRemaining -= 1;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "desktop-dates-state-smoke" }),
    });
  });
}

async function installHeldBaselineRoute(page, predicate) {
  let armed = false;
  let requestIntercepted = Promise.resolve();
  let markRequestIntercepted = null;
  let waitForRelease = Promise.resolve();
  let releaseRequest = null;

  await page.route("**/ui/pnl/product-category?*", async (route) => {
    const url = new URL(route.request().url());
    const request = {
      reportDate: url.searchParams.get("report_date") ?? FIXED_REPORT_DATE,
      view: url.searchParams.get("view") ?? "monthly",
      scenarioRatePct: url.searchParams.get("scenario_rate_pct") ?? undefined,
    };
    if (!armed || !predicate(request)) {
      await route.fallback();
      return;
    }

    markRequestIntercepted?.();
    await waitForRelease;
    await route.fulfill({
      json: buildMockProductCategoryPnlEnvelope(request),
    });
  });

  return {
    arm() {
      armed = true;
      requestIntercepted = new Promise((resolve) => {
        markRequestIntercepted = resolve;
      });
      waitForRelease = new Promise((resolve) => {
        releaseRequest = resolve;
      });
    },
    waitUntilHeld() {
      return requestIntercepted;
    },
    release() {
      armed = false;
      releaseRequest?.();
    },
  };
}

async function expectFormalDerivedAnalysisHidden(page) {
  await expect(page.locator('[data-testid="product-category-formal-readiness-band"]')).toBeHidden();
  await expect(page.locator('[data-testid="product-category-summary"]')).toBeHidden();
  await expect(page.locator('[data-testid="product-category-attribution"]')).toBeHidden();
  await expect(page.locator('[data-testid="product-category-financial-workspace"]')).toBeHidden();
  await expect(page.locator('[data-testid="product-category-operating-workspace"]')).toBeHidden();
  await expect(page.locator('[data-testid="product-category-backtest-workspace"]')).toBeHidden();
  await expect(page.locator('[data-testid="product-category-footer-total"]')).toBeHidden();
  await expect(page.locator('[data-testid="product-category-diagnostics-workspace"]')).toBeHidden();
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

async function expectDesktopLoadingLayout(page, viewport, title) {
  const health = page.locator('[data-testid="product-category-data-health"]');
  await expect(health).toHaveAttribute("data-health-state", "loading");
  await expect(health).toContainText(title);
  await expect(
    health.locator('[data-testid="product-category-formal-judgement-status"]'),
  ).toHaveText("等待数据完成");
  await expectFormalDerivedAnalysisHidden(page);

  const controlsBox = await page
    .locator('[data-testid="product-category-unified-controls"]')
    .boundingBox();
  const healthBox = await health.boundingBox();
  expect(controlsBox).not.toBeNull();
  expect(healthBox).not.toBeNull();
  expect(healthBox.y).toBeGreaterThanOrEqual(controlsBox.y + controlsBox.height);
  expect(healthBox.y + healthBox.height).toBeLessThanOrEqual(viewport.height);

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
        await expectFormalDerivedAnalysisHidden(page);
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

for (const viewport of DESKTOP_VIEWPORTS) {
  test(`desktop report-date loading stays stable at ${viewport.name}px`, async ({ page }, testInfo) => {
    const consoleErrors = [];
    const pageErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await installProductCategoryStateRoutes(page, "ready");
    const releaseDates = await installHeldDatesRoute(page);
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto(`${FORMAL_STATE_BASE_URL}/product-category-pnl`, {
      waitUntil: "domcontentloaded",
    });

    await expectDesktopLoadingLayout(page, viewport, "报告月份加载中");
    await page.screenshot({
      path: testInfo.outputPath(`product-category-pnl-dates-loading-${viewport.name}.jpg`),
      type: "jpeg",
      quality: 90,
      fullPage: false,
      animations: "disabled",
    });

    releaseDates();
    await expect(page.locator('[data-testid="product-category-data-health"]')).toHaveAttribute(
      "data-health-state",
      "ready",
    );
    await expect(page.locator('[data-testid="product-category-formal-readiness-band"]')).toBeVisible();
    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);
  });

  test(`desktop report-date failure retries to ready at ${viewport.name}px`, async ({ page }, testInfo) => {
    const consoleErrors = [];
    const pageErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await installProductCategoryStateRoutes(page, "ready");
    await installDatesFailureRoute(page);
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto(`${FORMAL_STATE_BASE_URL}/product-category-pnl`, { waitUntil: "networkidle" });

    const health = page.locator('[data-testid="product-category-data-health"]');
    await expect(health).toHaveAttribute("data-health-state", "error");
    await expect(health).toContainText("报告月份加载失败");
    await expectFormalDerivedAnalysisHidden(page);
    await page.screenshot({
      path: testInfo.outputPath(`product-category-pnl-dates-error-${viewport.name}.jpg`),
      type: "jpeg",
      quality: 90,
      fullPage: false,
      animations: "disabled",
    });

    await page.getByRole("button", { name: "重试报告月份" }).click();
    await expect(health).toHaveAttribute("data-health-state", "ready");
    await expect(page.locator('[data-testid="product-category-formal-readiness-band"]')).toBeVisible();
    expect(consoleErrors.filter((message) => !message.includes("503"))).toEqual([]);
    expect(pageErrors).toEqual([]);
  });

  test(`desktop report-month switch hides the prior conclusion at ${viewport.name}px`, async ({ page }, testInfo) => {
    const consoleErrors = [];
    const pageErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await installProductCategoryStateRoutes(page, "ready", {
      reportDates: [FIXED_REPORT_DATE, PRIOR_REPORT_DATE],
    });
    const heldBaseline = await installHeldBaselineRoute(
      page,
      (request) =>
        request.reportDate === PRIOR_REPORT_DATE &&
        request.view === "monthly" &&
        !request.scenarioRatePct,
    );
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto(`${FORMAL_STATE_BASE_URL}/product-category-pnl`, { waitUntil: "networkidle" });
    await expect(page.locator('[data-testid="product-category-data-health"]')).toHaveAttribute(
      "data-health-state",
      "ready",
    );

    heldBaseline.arm();
    await Promise.all([
      heldBaseline.waitUntilHeld(),
      page.getByRole("combobox", { name: "选择报告月份" }).selectOption(PRIOR_REPORT_DATE),
    ]);
    await expectDesktopLoadingLayout(page, viewport, "正式基线加载中");
    await expect(page.locator('[data-testid="product-category-report-date-slot"]')).toContainText(
      `${PRIOR_REPORT_DATE} · 口径待确认`,
    );
    await page.screenshot({
      path: testInfo.outputPath(`product-category-pnl-month-switch-loading-${viewport.name}.jpg`),
      type: "jpeg",
      quality: 90,
      fullPage: false,
      animations: "disabled",
    });

    heldBaseline.release();
    await expect(page.locator('[data-testid="product-category-data-health"]')).toHaveAttribute(
      "data-health-state",
      "ready",
    );
    await expect(page.locator('[data-testid="product-category-formal-readiness-band"]')).toBeVisible();
    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);
  });

  test(`desktop summary-view switch hides the prior conclusion at ${viewport.name}px`, async ({ page }, testInfo) => {
    const consoleErrors = [];
    const pageErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await installProductCategoryStateRoutes(page, "ready");
    const heldBaseline = await installHeldBaselineRoute(
      page,
      (request) =>
        request.reportDate === FIXED_REPORT_DATE &&
        request.view === "ytd" &&
        !request.scenarioRatePct,
    );
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto(`${FORMAL_STATE_BASE_URL}/product-category-pnl`, { waitUntil: "networkidle" });
    await expect(page.locator('[data-testid="product-category-data-health"]')).toHaveAttribute(
      "data-health-state",
      "ready",
    );

    heldBaseline.arm();
    await Promise.all([
      heldBaseline.waitUntilHeld(),
      page.getByRole("button", { name: "汇总视图" }).click(),
    ]);
    await expectDesktopLoadingLayout(page, viewport, "正式基线加载中");
    await expect(page.locator('[data-testid="product-category-report-date-slot"]')).toContainText(
      "口径待确认 · 汇总视图",
    );
    await page.screenshot({
      path: testInfo.outputPath(`product-category-pnl-view-switch-loading-${viewport.name}.jpg`),
      type: "jpeg",
      quality: 90,
      fullPage: false,
      animations: "disabled",
    });

    heldBaseline.release();
    await expect(page.locator('[data-testid="product-category-data-health"]')).toHaveAttribute(
      "data-health-state",
      "ready",
    );
    await expect(page.locator('[data-testid="product-category-formal-readiness-band"]')).toBeVisible();
    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);
  });
}
