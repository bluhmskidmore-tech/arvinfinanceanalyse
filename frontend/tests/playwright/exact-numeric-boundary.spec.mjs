import { expect, test } from "@playwright/test";
import { createDemoBalanceAnalysisClient } from "../../src/mocks/balanceAnalysisMockClient.ts";
import { createDemoBondAnalyticsClient, createDemoBondDashboardClient } from "../../src/mocks/bondAnalyticsMockClient.ts";
import { bondDashboardDemoEndpoints } from "../../src/mocks/bondDashboardWorkbenchMockEndpoints.ts";
import { createDemoCashflowClient } from "../../src/mocks/cashflowMockClient.ts";
import { buildMockApiEnvelope } from "../../src/mocks/mockApiEnvelope.ts";

const REAL_STATE_BASE_URL = process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`;
const delay = async () => {};
const ensureBundle = async () => ({ buildMockApiEnvelope });
const fixtureClient = {
  ...createDemoBalanceAnalysisClient(delay, ensureBundle),
  ...createDemoBondAnalyticsClient(delay, ensureBundle),
  ...createDemoBondDashboardClient(delay, ensureBundle),
  ...bondDashboardDemoEndpoints(delay, ensureBundle),
  ...createDemoCashflowClient(delay),
};
test.use({ baseURL: REAL_STATE_BASE_URL });

async function fixtureResponse(url) {
  const options = {
    reportDate: url.searchParams.get("report_date") ?? "2025-12-31",
    positionScope: url.searchParams.get("position_scope") ?? "all",
    currencyBasis: url.searchParams.get("currency_basis") ?? "CNY",
  };
  switch (url.pathname) {
    case "/api/system-read-publication":
      return { enabled: false, generation: null, coverage_dates: {} };
    case "/api/bond-dashboard/dates": return fixtureClient.getBondDashboardDates();
    case "/api/bond-dashboard/bundle": return fixtureClient.fetchBondDashboardBundle(
      url.searchParams.get("report_date"), url.searchParams.get("sections").split(","),
    );
    case "/ui/balance-analysis/dates": return fixtureClient.getBalanceAnalysisDates();
    case "/ui/balance-analysis/publication-status": return fixtureClient.getBalanceAnalysisPublicationStatus();
    case "/ui/balance-analysis/current-user": return fixtureClient.getBalanceAnalysisCurrentUser();
    case "/ui/balance-analysis/overview": return fixtureClient.getBalanceAnalysisOverview(options);
    case "/ui/balance-analysis": return fixtureClient.getBalanceAnalysisDetail(options);
    case "/ui/balance-analysis/summary": return fixtureClient.getBalanceAnalysisSummary({ ...options,
      limit: Number(url.searchParams.get("limit") ?? 200), offset: Number(url.searchParams.get("offset") ?? 0),
    });
    case "/ui/balance-analysis/summary-by-basis": return fixtureClient.getBalanceAnalysisSummaryByBasis(options);
    case "/ui/balance-analysis/workbook": return fixtureClient.getBalanceAnalysisWorkbook(options);
    case "/ui/balance-analysis/decision-items": return fixtureClient.getBalanceAnalysisDecisionItems(options);
    case "/api/cashflow-projection": return fixtureClient.getCashflowProjection(options.reportDate);
    default: return undefined;
  }
}

test.beforeEach(async ({ page }) => {
  // Exercise the real HTTP adapter with synthetic responses. Mock-mode clients
  // return locally and never reach page.route, so they cannot test this boundary.
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (!/^\/(api|ui|health)(\/|$)/.test(url.pathname)) return route.continue();
    if (!["GET", "HEAD"].includes(route.request().method())) return route.abort();
    const json = await fixtureResponse(url);
    return json === undefined
      ? route.fulfill({ status: 503, json: { detail: "Not part of the numeric browser fixture" } })
      : route.fulfill({ json });
  });
});

async function interceptJson(route, mutate) {
  const body = await fixtureResponse(new URL(route.request().url()));
  if (body === undefined) throw new Error(`No numeric fixture for ${route.request().url()}`);
  await route.fulfill({
    json: mutate(body),
  });
}

async function prepareBondDashboardExactNumeric(page) {
  await page.route("**/api/bond-dashboard/dates", async (route) => {
    await interceptJson(route, (body) => ({
      ...body,
      result: {
        ...body.result,
        report_dates: ["2026-04-30"],
      },
    }));
  });

  await page.route("**/api/bond-dashboard/bundle**", async (route) => {
    await interceptJson(route, (body) => {
      const next = structuredClone(body);
      const sections = next?.result?.sections ?? {};
      const headline = sections["headline-kpis"];
      const risk = sections["risk-indicators"];
      if (sections.dates?.result) sections.dates.result.report_dates = ["2026-04-30"];

      if (headline?.result?.kpis?.weighted_ytm) {
        // This boundary needs two periods even when the demo date has no prior
        // period. Seed the comparison explicitly instead of silently skipping it.
        headline.result.prev_kpis ??= structuredClone(headline.result.kpis);
        headline.result.prev_report_date = "2026-03-31";
        headline.result.kpis.weighted_ytm.raw = 0.025;
        headline.result.kpis.weighted_ytm.raw_text = "0.03100000";
        headline.result.prev_kpis.weighted_ytm.raw = 0.03;
        headline.result.prev_kpis.weighted_ytm.raw_text = "0.03000000";
      }

      if (risk?.result?.credit_ratio) {
        risk.result.credit_ratio.raw = 0.49;
        risk.result.credit_ratio.raw_text = "0.50000000";
      }

      if (headline?.result_meta) {
        headline.result_meta.quality_flag = "ok";
        headline.result_meta.requested_report_date = "2026-04-30";
        headline.result_meta.resolved_report_date = "2026-04-30";
        headline.result_meta.as_of_date = "2026-04-30";
        headline.result_meta.fallback_date = null;
      }
      if (risk?.result_meta) {
        risk.result_meta.quality_flag = "ok";
        risk.result_meta.requested_report_date = "2026-04-30";
        risk.result_meta.resolved_report_date = "2026-04-30";
        risk.result_meta.as_of_date = "2026-04-30";
        risk.result_meta.fallback_date = null;
      }

      next.data_source = "bond_analytics_facts";
      return next;
    });
  });
}

async function prepareCashflowExactNumeric(page) {
  await page.route("**/ui/balance-analysis/dates", async (route) => {
    await interceptJson(route, (body) => ({
      ...body,
      result: {
        ...body.result,
        report_dates: ["2026-04-01"],
      },
    }));
  });

  await page.route("**/api/cashflow-projection**", async (route) => {
    await interceptJson(route, (body) => {
      const next = structuredClone(body);
      const result = next?.result;
      if (!result) return next;

      result.report_date = "2026-04-01";
      if (result.duration_gap) {
        result.duration_gap.raw = 0.04;
        result.duration_gap.raw_text = "0.06000000";
        result.duration_gap.display = "0.06";
      }
      if (result.asset_duration) result.asset_duration.raw_text = "3.50000000";
      if (result.liability_duration) result.liability_duration.raw_text = "3.46000000";
      if (result.equity_duration) result.equity_duration.raw_text = "0.04000000";
      if (result.rate_sensitivity_1bp) {
        result.rate_sensitivity_1bp.raw = 0;
        result.rate_sensitivity_1bp.raw_text = "-125000000.00000000";
        result.rate_sensitivity_1bp.display = "-125,000,000.00";
        result.rate_sensitivity_1bp.sign_aware = true;
      }
      if (result.reinvestment_risk_12m) result.reinvestment_risk_12m.raw_text = "0.12000000";

      result.monthly_buckets = [
        {
          year_month: "2026-04",
          asset_inflow: {
            raw: 10,
            raw_text: "10.00000000",
            unit: "yuan",
            display: "10.00",
            precision: 8,
            sign_aware: false,
          },
          liability_outflow: {
            raw: 40,
            raw_text: "40.00000000",
            unit: "yuan",
            display: "40.00",
            precision: 8,
            sign_aware: false,
          },
          net_cashflow: {
            raw: 0,
            raw_text: "0.00000000",
            unit: "yuan",
            display: "0.00",
            precision: 8,
            sign_aware: false,
          },
          cumulative_net: {
            raw: 100_499_999.9,
            raw_text: "-125000000.00000000",
            unit: "yuan",
            display: "-125,000,000.00",
            precision: 8,
            sign_aware: true,
          },
        },
        {
          year_month: "2026-05",
          asset_inflow: {
            raw: 20,
            raw_text: "20.00000000",
            unit: "yuan",
            display: "20.00",
            precision: 8,
            sign_aware: false,
          },
          liability_outflow: {
            raw: 12,
            raw_text: "12.00000000",
            unit: "yuan",
            display: "12.00",
            precision: 8,
            sign_aware: false,
          },
          net_cashflow: {
            raw: 8,
            raw_text: "8.00000000",
            unit: "yuan",
            display: "8.00",
            precision: 8,
            sign_aware: false,
          },
          cumulative_net: {
            raw: 9,
            raw_text: "9.00000000",
            unit: "yuan",
            display: "9.00",
            precision: 8,
            sign_aware: false,
          },
        },
      ];
      result.top_maturing_assets_12m = [];
      result.warnings = [];

      if (next.result_meta) {
        next.result_meta.quality_flag = "ok";
        next.result_meta.requested_report_date = "2026-04-01";
        next.result_meta.resolved_report_date = "2026-04-01";
        next.result_meta.as_of_date = "2026-04-01";
        next.result_meta.fallback_date = null;
        next.result_meta.fallback_mode = "none";
      }
      return next;
    });
  });
}

async function prepareBalanceAnalysisExactDisplay(page) {
  await page.route("**/ui/balance-analysis/overview**", async (route) => {
    await interceptJson(route, (body) => {
      const next = structuredClone(body);
      if (!next?.result) return next;

      next.result.asset_total_market_value_amount = "9007199250499999.5";
      return next;
    });
  });

  await page.route("**/ui/balance-analysis/workbook**", async (route) => {
    await interceptJson(route, (body) => {
      const next = structuredClone(body);
      const result = next?.result;
      if (!result) return next;

      const ratingTable = result.tables?.find((table) => table.key === "rating_analysis");
      if (ratingTable?.rows?.[0]) {
        ratingTable.rows[0].balance_amount = "9007199254740049.5";
      }
      const riskAlerts = result.operational_sections?.find(
        (section) => section.key === "risk_alerts",
      );
      const ratingAlert = riskAlerts?.rows?.find(
        (row) => row.rule_id === "bal_wb_risk_rating_001",
      );
      if (ratingAlert) {
        ratingAlert.reason = "Top rating bucket share reached 0.7550499999999999999.";
      } else if (riskAlerts) {
        riskAlerts.rows.push({
          title: "最高评级桶占比触及预警", severity: "high", source_section: "评级分析",
          rule_id: "bal_wb_risk_rating_001", rule_version: "v1",
          reason: "Top rating bucket share reached 0.7550499999999999999.",
        });
      }
      return next;
    });
  });
}

async function prepareRiskTensorExactNumeric(page) {
  const meta = (resultKind, traceId) => ({
    trace_id: traceId,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_risk_tensor_exact_browser",
    vendor_version: "vv_none",
    rule_version: "rv_risk_tensor_exact_browser",
    cache_version: "cv_risk_tensor_exact_browser",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T08:00:00Z",
  });
  const numeric = (raw, rawText) => ({
    raw,
    raw_text: rawText,
    unit: "yuan",
    display: rawText,
    precision: 8,
    sign_aware: true,
  });

  await page.route("**/api/risk/tensor/dates", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: {
        result_meta: meta("risk.tensor.dates", "tr_risk_tensor_exact_dates"),
        result: { report_dates: ["2026-02-28"] },
      },
    });
  });

  await page.route(/\/api\/risk\/tensor\?report_date=/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      json: {
        result_meta: meta("risk.tensor", "tr_risk_tensor_exact_payload"),
        result: {
          report_date: "2026-02-28",
          portfolio_dv01: "12.34",
          krd_1y: numeric(1, "1.00000000"),
          krd_3y: numeric(2, "2.00000000"),
          krd_5y: numeric(5, "1.00000000"),
          krd_7y: numeric(4, "6.00000000"),
          krd_10y: numeric(3, "6.00000000"),
          krd_30y: numeric(0.5, "0.50000000"),
          cs01: "8.88",
          portfolio_convexity: "0.42",
          portfolio_modified_duration: "4.2",
          issuer_concentration_hhi: "0.18",
          issuer_top5_weight: "0.35",
          asset_cashflow_30d: "300.3",
          asset_cashflow_90d: "500.5",
          liability_cashflow_30d: "200.2",
          liability_cashflow_90d: "300.3",
          liquidity_gap_30d: numeric(100, "-0.00000001"),
          liquidity_gap_90d: "200.2",
          liquidity_gap_30d_ratio: "0.05",
          total_market_value: numeric(100_499_999.9, "100500000.00000000"),
          rate_risk_market_value: "900.00",
          rate_risk_dv01: "11.11",
          rate_risk_modified_duration: "4.20",
          duration_excluded_market_value: "0",
          duration_excluded_count: 0,
          missing_maturity_market_value: "0",
          missing_maturity_count: 0,
          floating_rate_proxy_market_value: "0",
          floating_rate_proxy_count: 0,
          payment_frequency_fallback_market_value: "0",
          payment_frequency_fallback_count: 0,
          bullet_value_date_fallback_market_value: "0",
          bullet_value_date_fallback_count: 0,
          projection_quality_status: "available",
          bond_count: 12,
          quality_flag: "ok",
          warnings: [],
        },
      },
    });
  });
}

test.describe("exact numeric browser boundaries", () => {
  test("bond-dashboard conclusion and KPI delta follow raw_text at threshold boundaries", async ({ page }) => {
    await prepareBondDashboardExactNumeric(page);

    await page.goto("/bond-dashboard", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("bond-dashboard-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("bond-dashboard-conclusion")).toBeVisible({ timeout: 30_000 });

    await expect(page.getByTestId("bond-dashboard-conclusion")).toContainText("信用仓位偏高");
    await expect(page.getByTestId("bond-dashboard-kpi-weighted_ytm")).toContainText("+10.0bp");
  });

  test("cashflow-projection conclusion follows raw_text at the threshold boundary", async ({
    page,
  }) => {
    await prepareCashflowExactNumeric(page);

    await page.goto("/cashflow-projection", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("cashflow-projection-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("cashflow-conclusion")).toBeVisible({ timeout: 30_000 });

    await expect(page.getByTestId("cashflow-conclusion")).toContainText("正久期缺口");
    await expect(page.getByTestId("cashflow-conclusion")).not.toContainText("基本匹配");
    await expect(page.getByTestId("cashflow-risk-readout")).toContainText("1 个月累计净现金流为负");
    await expect(page.getByTestId("cashflow-risk-readout")).toContainText("累计净流风险读数");
    await expect(page.getByTestId("cashflow-risk-readout")).toContainText("-1.25 亿");
    await expect(page.getByTestId("cashflow-kpi-dv01")).toContainText("-1.25");
    await expect(page.getByTestId("cashflow-kpi-dv01")).toContainText("权益减少");
  });

  test("balance-analysis formal amount display preserves a plain-decimal boundary", async ({
    page,
  }) => {
    await prepareBalanceAnalysisExactDisplay(page);

    await page.goto("/balance-analysis", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("balance-analysis-overview-cards")).toBeVisible({
      timeout: 30_000,
    });

    await expect(page.getByTestId("balance-analysis-overview-cards")).toContainText(
      "90,071,992.50",
    );
    await expect(page.getByTestId("balance-analysis-cockpit-kpis")).toContainText(
      "90,071,992.50",
    );

    await page.getByRole("heading", { name: "完整工作簿明细", exact: true }).click();
    await expect(page.getByTestId("balance-analysis-workbook-table-rating_analysis")).toContainText(
      "900,719,925,474.00 亿元",
    );
    await expect(page.getByTestId("balance-analysis-right-rail-panel-risk_alerts")).toContainText(
      "最高评级桶占比达到 75.50%",
    );
  });

  test("risk-tensor first-screen decisions follow raw_text", async ({ page }) => {
    await prepareRiskTensorExactNumeric(page);

    await page.goto("/risk-tensor", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("risk-tensor-brief")).toBeVisible({ timeout: 30_000 });

    await expect(page.getByTestId("risk-tensor-brief")).toContainText("主风险桶 7Y");
    await expect(page.getByTestId("risk-tensor-brief")).toContainText("30 日缺口为负");
    await expect(page.getByTestId("risk-tensor-tenor-drill")).toContainText("7Y");
    const totalMarketValue = page
      .getByTestId("risk-tensor-kpi-grid")
      .locator(".kpi-card")
      .filter({ hasText: "总市值" });
    await expect(totalMarketValue).toContainText("1.01");
    await expect(totalMarketValue).toContainText("亿元");
  });
});
