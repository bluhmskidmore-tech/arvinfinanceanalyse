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

test("refresh synchronizes an alternate liability view and preserves closed-panel loading", async ({ page }) => {
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.addInitScript(() => {
    window.localStorage.setItem("moss.product-category-pnl.trend-workspace-open", "0");
  });
  // This browser check uses synthetic read and task receipts; no refresh reaches
  // the local backend or writes financial data.
  await page.route("**/ui/**", async (route) => {
    if (!["GET", "HEAD"].includes(route.request().method())) {
      await route.abort("blockedbyclient");
      return;
    }
    await route.fallback();
  });
  await installProductCategoryStateRoutes(page, "ready", {
    reportDates: [FIXED_REPORT_DATE, PRIOR_REPORT_DATE],
  });
  const historyReads = [];
  let sourceVersion = 1;
  let refreshCount = 0;
  let releaseTask;
  let taskRequested = false;
  await page.route("**/ui/pnl/product-category/history?*", async (route) => {
    const url = new URL(route.request().url());
    historyReads.push({ view: url.searchParams.get("view"), sourceVersion });
    await route.fallback();
  });
  await page.route("**/ui/pnl/product-category/refresh", async (route) => {
    refreshCount += 1;
    await route.fulfill({ json: {
      status: "queued", run_id: `refresh-browser-${refreshCount}`,
      job_name: "product_category_pnl", trigger_mode: "async",
    } });
  });
  await page.route("**/ui/pnl/product-category/refresh-status?*", async (route) => {
    taskRequested = true;
    await new Promise((resolve) => { releaseTask = resolve; });
    sourceVersion += 1;
    await route.fulfill({ json: {
      status: "completed", run_id: `refresh-browser-${refreshCount}`,
      job_name: "product_category_pnl", trigger_mode: "async",
    } });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${FORMAL_STATE_BASE_URL}/product-category-pnl`, { waitUntil: "networkidle" });
  await expect(page.getByTestId("product-category-table")).toBeVisible();
  const refreshButton = page.getByTestId("product-category-refresh-button");
  await refreshButton.click();
  await expect.poll(() => taskRequested).toBe(true);
  await expect(refreshButton).toBeDisabled();
  await expect(page.getByTestId("product-category-refresh-status")).toContainText("queued");
  releaseTask();
  await expect(refreshButton).toBeEnabled();
  // The visible management monitor already consumes monthly history. Its data
  // must refresh even while the optional diagnostics and trend panels are shut.
  expect(historyReads).toEqual([
    { view: "monthly", sourceVersion: 1 },
    { view: "monthly", sourceVersion: 2 },
  ]);

  await page.getByTestId("product-category-diagnostics-workspace").locator("summary").first().click();
  const liabilityView = page.getByTestId("product-category-liability-matrix-display-mode");
  await expect(liabilityView).toBeVisible();
  await liabilityView.getByRole("button", { name: "累进值" }).click();
  await expect.poll(() => historyReads.filter((read) => read.view === "ytd").length).toBe(1);
  await expect(page.getByTestId("product-category-liability-matrix-caliber-note")).not.toContainText("加载中");
  const backtest = page.getByTestId("product-category-backtest-workspace");
  await backtest.locator("summary").first().click();
  await expect(backtest).toHaveAttribute("open", "");

  taskRequested = false;
  await refreshButton.click();
  await expect.poll(() => taskRequested).toBe(true);
  releaseTask();
  await expect(refreshButton).toBeEnabled();
  const ytdReads = historyReads.filter((read) => read.view === "ytd");
  expect(ytdReads).toEqual([
    { view: "ytd", sourceVersion: 2 },
    { view: "ytd", sourceVersion: 3 },
  ]);
  await expect(liabilityView.getByRole("button", { name: "累进值" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("product-category-diagnostics-workspace")).toHaveAttribute("open", "");
  await expect(backtest).toHaveAttribute("open", "");
  await expect(page.getByTestId("product-category-data-health")).toHaveAttribute("data-health-state", "ready");
  expect(refreshCount).toBe(2);
  expect(pageErrors).toEqual([]);
});

for (const field of [
  "all_currency_spread_pct",
  "all_currency_asset_yield_pct",
  "all_currency_liability_yield_pct",
]) {
  test(`spread attribution discloses a missing prior ${field}`, async ({ page }, testInfo) => {
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.addInitScript(() => {
      window.localStorage.setItem("moss.product-category-pnl.trend-workspace-open", "1");
    });
    // All business reads below are synthetic, and no request may reach the backend.
    await page.route((url) => url.pathname.startsWith("/api/"), (route) => route.abort("blockedbyclient"));
    await page.route((url) => url.pathname.startsWith("/ui/"), (route) => route.abort("blockedbyclient"));
    await installProductCategoryStateRoutes(page, "ready", {
      reportDates: [FIXED_REPORT_DATE, PRIOR_REPORT_DATE],
      missingPriorSpreadField: field,
    });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${FORMAL_STATE_BASE_URL}/product-category-pnl`, {
      waitUntil: "networkidle",
    });
    const attribution = page.getByTestId("product-category-trend-spread-attribution");
    await expect(attribution).toContainText("2026年01月");
    await expect(attribution).toContainText("缺少可比上期趋势快照，无法完成利差变动归因。");
    await attribution.scrollIntoViewIfNeeded();
    await expect(attribution).toBeVisible();
    expect(pageErrors).toEqual([]);
    await attribution.screenshot({
      path: testInfo.outputPath(`missing-prior-${field}.png`),
      animations: "disabled",
    });
  });
}

async function installProductCategoryStateRoutes(page, state, options = {}) {
  let baselineFailuresRemaining = state === "error" ? 1 : 0;
  const reportDates = options.reportDates ?? [FIXED_REPORT_DATE];

  await page.route("**/ui/macro/choice-series/latest", async (route) => {
    await route.fulfill({
      json: buildMockApiEnvelope("choice_macro.latest", {
        read_target: "duckdb",
        series: [],
      }),
    });
  });

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
        // A terminal read failure exercises the manual retry surface; 503 is
        // transient and is retried automatically by the production read policy.
        status: 500,
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

  await page.route("**/ui/pnl/product-category/history?*", async (route) => {
    const url = new URL(route.request().url());
    const view = url.searchParams.get("view") ?? "monthly";
    const scenarioRatePct = url.searchParams.get("scenario_rate_pct") ?? undefined;
    const items = (url.searchParams.get("report_dates") ?? "")
      .split(",")
      .filter(Boolean)
      .map((reportDate) => {
        const envelope = buildMockProductCategoryPnlEnvelope({
          reportDate,
          view,
          scenarioRatePct,
        });
        if (reportDate === PRIOR_REPORT_DATE && options.missingPriorSpreadField) {
          envelope.result.interest_spread[options.missingPriorSpreadField] = null;
        }
        return {
          report_date: reportDate,
          status: "ok",
          detail: null,
          result: envelope.result,
          result_meta: envelope.result_meta,
        };
      });
    await route.fulfill({
      json: buildMockApiEnvelope("product_category_pnl.history", {
        view,
        scenario_rate_pct: scenarioRatePct ?? null,
        items,
      }),
    });
  });

  await page.route("**/ui/pnl/product-category/attribution/history?*", async (route) => {
    const url = new URL(route.request().url());
    const compare = url.searchParams.get("compare") === "yoy" ? "yoy" : "mom";
    const items = (url.searchParams.get("report_dates") ?? "")
      .split(",")
      .filter(Boolean)
      .map((reportDate) => {
        const envelope = buildMockProductCategoryAttributionEnvelope({
          reportDate,
          compare,
        });
        return {
          report_date: reportDate,
          status: "ok",
          detail: null,
          result: envelope.result,
          result_meta: envelope.result_meta,
        };
      });
    await route.fulfill({
      json: buildMockApiEnvelope("product_category_pnl.attribution_history", {
        compare,
        items,
      }),
    });
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
      status: 500,
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
        (message) => state !== "error" || !message.includes("500"),
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
    expect(consoleErrors.filter((message) => !message.includes("500"))).toEqual([]);
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
    // The selected date remains in the date control; the hero slot only names
    // the basis and view, and its title identifies the same requested date.
    const dateSlot = page.locator('[data-testid="product-category-report-date-slot"]');
    await expect(dateSlot).toHaveText("口径待确认 | 月度视图");
    await expect(dateSlot).toHaveAttribute("title", `报告日期 ${PRIOR_REPORT_DATE}`);
    await expect(page.getByRole("combobox", { name: "选择报告月份" })).toHaveValue(PRIOR_REPORT_DATE);
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
    const dateSlot = page.locator('[data-testid="product-category-report-date-slot"]');
    await expect(dateSlot).toHaveText("口径待确认 | 汇总视图");
    await expect(dateSlot).toHaveAttribute("title", `报告日期 ${FIXED_REPORT_DATE}`);
    await expect(page.getByRole("combobox", { name: "选择报告月份" })).toHaveValue(FIXED_REPORT_DATE);
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
