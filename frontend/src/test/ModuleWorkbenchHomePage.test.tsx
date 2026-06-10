import { cleanup, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import type {
  ApiEnvelope,
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisOverviewPayload,
  BondDashboardHomeSummaryPayload,
  ChoiceMacroLatestPayload,
  MacroVendorPayload,
  PnlAttributionAnalysisSummary,
  ResultMeta,
} from "../api/contracts";
import { createApiClient, type ApiClient } from "../api/client";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitStrategySummariesPayload,
} from "../api/macroToolkitClient";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";
import { PORTFOLIO_MODULE_DRILLDOWN_COUNT } from "../features/workbench/module-home/portfolioModuleDrilldowns";
import { MARKET_MODULE_DRILLDOWN_COUNT } from "../features/workbench/module-home/marketModuleDrilldowns";
import { formatRawAsNumeric } from "../utils/format";

vi.mock("../lib/echarts", () => ({
  default: ({ style }: { style?: { height?: number | string } }) => (
    <div data-testid="module-home-echarts-stub" data-chart-height={String(style?.height ?? "")} />
  ),
}));

vi.mock("../app/ThemedRouteBoundary", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

beforeAll(async () => {
  await preloadWorkbenchRouteModules("market-overview", "module-home");
}, 20_000);

afterEach(() => {
  cleanup();
});

function renderAt(path: string, client?: ApiClient) {
  return renderWorkbenchApp([path], {
    client: client ?? createApiClient({ mode: "mock" }),
  });
}

function createRealModeDemoClient(): ApiClient {
  return {
    ...createApiClient({ mode: "mock" }),
    mode: "real",
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((innerResolve, innerReject) => {
    resolve = innerResolve;
    reject = innerReject;
  });
  return { promise, resolve, reject };
}

function testMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `${resultKind}_trace`,
    basis: "analytical",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_test",
    vendor_version: "vv_test",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-06-01T00:00:00Z",
  };
}

function coreMacroAnalysisEnvelope(): ApiEnvelope<MacroToolkitAnalysisPayload> {
  return {
    result_meta: testMeta("macro_toolkit.analysis"),
    result: {
      default_data_sources: ["choice"],
      as_of_date: "2026-04-30",
      conclusion: {
        stance: "中性观察",
        tone: "neutral",
        summary: "核心宏观信号已返回。",
        recommended_action: "等待候选策略摘要补齐。",
      },
      coverage: {
        indicator_count: 8,
        hit_count: 7,
        hit_rate: 0.875,
        script_count: 24,
        output_file_count: 0,
      },
      indicators: [],
      signal_cards: [],
      capability_results: [],
      strategy_summaries: [],
      output_files: [],
      source_checks: [],
      capabilities: [],
      warnings: [],
    },
  };
}

function strategySummariesEnvelope(): ApiEnvelope<MacroToolkitStrategySummariesPayload> {
  return {
    result_meta: testMeta("macro_toolkit.analysis.strategy_summaries"),
    result: {
      strategy_summaries: [],
    },
  };
}

function realPortfolioMeta(resultKind: string, overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: `${resultKind}_real_trace`,
    basis: "analytical",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_real_bond_analytics",
    vendor_version: "vv_none",
    rule_version: "rv_bond_analytics_formal_materialize_v1",
    cache_version: "cv_real_bond_analytics",
    quality_flag: "warning",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    requested_report_date: "2026-05-31",
    resolved_report_date: "2026-05-31",
    as_of_date: "2026-05-31",
    date_basis: "bond_dashboard_report_date",
    fallback_date: null,
    generated_at: "2026-06-05T01:29:44.597898Z",
    tables_used: ["fact_formal_bond_analytics_daily"],
    evidence_rows: 1710,
    ...overrides,
  };
}

function envelopeWithMeta<T>(
  resultKind: string,
  result: T,
  overrides: Partial<ResultMeta> = {},
): ApiEnvelope<T> {
  return {
    result_meta: realPortfolioMeta(resultKind, overrides),
    result,
  };
}

function n(raw: number, unit: Parameters<typeof formatRawAsNumeric>[0]["unit"], signAware = false) {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
}

function realPortfolioHomeSummary(): BondDashboardHomeSummaryPayload {
  const reportDate = "2026-05-31";
  return {
    report_date: reportDate,
    headline: {
      report_date: reportDate,
      prev_report_date: "2026-04-30",
      kpis: {
        total_market_value: n(332_281_921_064.45, "yuan"),
        unrealized_pnl: n(8_202_912_484.65, "yuan", true),
        weighted_ytm: n(0.02561294, "pct", true),
        weighted_duration: n(4.4484273, "ratio"),
        weighted_coupon: n(0.01871629, "pct", true),
        credit_spread_median: n(0.023682, "pct", true),
        total_dv01: n(105_628_442.39590558, "dv01"),
        bond_count: 1710,
      },
      prev_kpis: {
        total_market_value: n(330_000_000_000, "yuan"),
        unrealized_pnl: n(8_100_000_000, "yuan", true),
        weighted_ytm: n(0.0251, "pct", true),
        weighted_duration: n(4.35, "ratio"),
        weighted_coupon: n(0.0185, "pct", true),
        credit_spread_median: n(0.0235, "pct", true),
        total_dv01: n(104_000_000, "dv01"),
        bond_count: 1700,
      },
    },
    risk: {
      report_date: reportDate,
      total_market_value: n(332_281_921_064.45, "yuan"),
      total_dv01: n(105_628_442.39590558, "dv01"),
      weighted_duration: n(4.4484273, "ratio"),
      credit_ratio: n(0.29955411, "ratio"),
      weighted_convexity: n(28.73609304, "ratio"),
      total_spread_dv01: n(25_862_175.57270329, "dv01"),
      reinvestment_ratio_1y: n(0.3448817, "ratio"),
    },
    asset_type: {
      report_date: reportDate,
      group_by: "bond_type",
      total_market_value: n(332_281_921_064.45, "yuan"),
      items: [
        {
          category: "政策性金融债",
          total_market_value: n(67_535_152_800.52, "yuan"),
          bond_count: 109,
          percentage: n(0.20324655, "pct"),
        },
      ],
    },
    asset_rating: {
      report_date: reportDate,
      group_by: "rating",
      total_market_value: n(332_281_921_064.45, "yuan"),
      items: [
        {
          category: "AAA",
          total_market_value: n(220_000_000_000, "yuan"),
          bond_count: 900,
          percentage: n(0.6621, "pct"),
        },
      ],
    },
    maturity: {
      report_date: reportDate,
      total_market_value: n(332_281_921_064.45, "yuan"),
      items: [
        {
          maturity_bucket: "3-5年",
          total_market_value: n(81_000_000_000, "yuan"),
          bond_count: 320,
          percentage: n(0.2438, "pct"),
        },
      ],
    },
    industry: {
      report_date: reportDate,
      items: [
        {
          industry_name: "金融",
          total_market_value: n(150_000_000_000, "yuan"),
          bond_count: 720,
          percentage: n(0.4514, "pct"),
        },
      ],
    },
    yield_distribution: {
      report_date: reportDate,
      weighted_ytm: n(0.02561294, "pct", true),
      items: [
        {
          yield_bucket: "2%-3%",
          total_market_value: n(210_000_000_000, "yuan"),
          bond_count: 1110,
        },
      ],
    },
    portfolio_comparison: {
      report_date: reportDate,
      items: [
        {
          portfolio_name: "固收组合",
          total_market_value: n(332_281_921_064.45, "yuan"),
          weighted_ytm: n(0.02561294, "pct", true),
          weighted_duration: n(4.4484273, "ratio"),
          total_dv01: n(105_628_442.39590558, "dv01"),
          bond_count: 1710,
        },
      ],
    },
    spread: {
      report_date: reportDate,
      items: [
        {
          bond_type: "政策性金融债",
          median_yield: n(0.022645, "pct", true),
          bond_count: 109,
          total_market_value: n(67_535_152_800.52, "yuan"),
        },
      ],
    },
    business_type: {
      report_date: reportDate,
      items: [
        {
          name: "政策性金融债",
          market_value: "67535152800.52",
          weighted_avg_ytm_pct: "2.26451445",
          weighted_avg_duration: "3.83902881",
          duration_source: "",
        },
      ],
    },
  };
}

function realPortfolioClient(overrides: Partial<ApiClient> = {}): ApiClient {
  const base = createApiClient({ mode: "mock" });
  const reportDate = "2026-05-31";
  const balanceOverview: BalanceAnalysisOverviewPayload = {
    report_date: reportDate,
    position_scope: "all",
    currency_basis: "CNY",
    detail_row_count: 1710,
    summary_row_count: 2,
    total_market_value_amount: "332281921064.45",
    total_amortized_cost_amount: "321000000000.00",
    total_accrued_interest_amount: "1280000000.00",
    asset_total_market_value_amount: "332281921064.45",
    liability_total_market_value_amount: "0.00",
    asset_total_amortized_cost_amount: "321000000000.00",
    liability_total_amortized_cost_amount: "0.00",
    asset_total_accrued_interest_amount: "1280000000.00",
    liability_total_accrued_interest_amount: "0.00",
  };
  const balanceBasis: BalanceAnalysisBasisBreakdownPayload = {
    report_date: reportDate,
    position_scope: "all",
    currency_basis: "CNY",
    rows: [
      {
        source_family: "zqtz",
        invest_type_std: "债券投资",
        accounting_basis: "FVTPL",
        position_scope: "asset",
        currency_basis: "CNY",
        detail_row_count: 1710,
        market_value_amount: "332281921064.45",
        amortized_cost_amount: "321000000000.00",
        accrued_interest_amount: "1280000000.00",
      },
    ],
  };
  const pnlSummary: PnlAttributionAnalysisSummary = {
    report_date: reportDate,
    primary_driver: "market",
    primary_driver_pct: n(0.58, "ratio"),
    key_findings: ["市值变动主要来自市场重估。"],
    tpl_market_aligned: true,
    tpl_market_note: "与 TPL 市场变动方向一致。",
  };
  return {
    ...base,
    mode: "real",
    getBalanceAnalysisDates: async () =>
      envelopeWithMeta("balance-analysis.dates", { report_dates: [reportDate] }, {
        basis: "formal",
        formal_use_allowed: true,
        quality_flag: "ok",
        tables_used: ["fact_formal_zqtz_balance_daily"],
      }),
    getBalanceAnalysisOverview: async () =>
      envelopeWithMeta("balance-analysis.overview", balanceOverview, {
        basis: "formal",
        formal_use_allowed: true,
        quality_flag: "ok",
        tables_used: ["fact_formal_zqtz_balance_daily"],
        evidence_rows: 1710,
      }),
    getBondDashboardDates: async () =>
      envelopeWithMeta("bond_dashboard.dates", { report_dates: [reportDate] }, {
        basis: "formal",
        formal_use_allowed: true,
        quality_flag: "ok",
      }),
    getBondDashboardHomeSummary: async () =>
      ({
        ...envelopeWithMeta("bond_dashboard.home_summary", realPortfolioHomeSummary(), {
          basis: "formal",
          formal_use_allowed: true,
          quality_flag: "ok",
          tables_used: ["fact_formal_bond_analytics_daily"],
          evidence_rows: 1710,
        }),
        data_source: "bond_analytics_facts",
      }),
    getBondDashboardRiskIndicators: async () =>
      envelopeWithMeta("bond_dashboard.risk_indicators", realPortfolioHomeSummary().risk, {
        basis: "formal",
        formal_use_allowed: true,
        quality_flag: "ok",
        tables_used: ["fact_formal_bond_analytics_daily"],
        evidence_rows: 1710,
      }),
    getBalanceAnalysisSummaryByBasis: async () =>
      envelopeWithMeta("balance-analysis.summary-by-basis", balanceBasis, {
        basis: "formal",
        formal_use_allowed: true,
        quality_flag: "ok",
        tables_used: ["fact_formal_zqtz_balance_daily"],
        evidence_rows: 1710,
      }),
    getPnlAttributionAnalysisSummary: async () =>
      envelopeWithMeta("pnl-attribution.summary", pnlSummary, {
        basis: "formal",
        formal_use_allowed: true,
        quality_flag: "ok",
        tables_used: ["fact_formal_pnl_fi"],
        evidence_rows: 1710,
      }),
    getRiskTensorDates: async () =>
      envelopeWithMeta("risk.tensor.dates", { report_dates: [reportDate] }, {
        basis: "formal",
        formal_use_allowed: true,
        quality_flag: "ok",
        tables_used: ["fact_risk_tensor_daily"],
        evidence_rows: 1,
      }),
    ...overrides,
  };
}

function emptyChoiceMacroEnvelope(resultKind: string): ApiEnvelope<ChoiceMacroLatestPayload> {
  return {
    result_meta: testMeta(resultKind),
    result: {
      read_target: "duckdb",
      series: [],
    },
  };
}

function emptyMacroVendorEnvelope(): ApiEnvelope<MacroVendorPayload> {
  return {
    result_meta: testMeta("market_data.catalog"),
    result: {
      read_target: "duckdb",
      series: [],
    },
  };
}

function oneRateSeriesEnvelope(): ApiEnvelope<ChoiceMacroLatestPayload> {
  return {
    result_meta: testMeta("market_data.rates"),
    result: {
      read_target: "duckdb",
      series: [
        {
          series_id: "CA.CN_GOV_10Y",
          series_name: "10Y 国债",
          trade_date: "2026-05-29",
          value_numeric: 1.71,
          unit: "%",
          source_version: "sv_test",
          vendor_version: "vv_test",
          latest_change: -0.01,
          recent_points: [],
        },
      ],
    },
  };
}

describe("ModuleWorkbenchHomePage", () => {
  it.each([
    ["/risk-overview", "风险工作台"],
    ["/performance", "绩效工作台"],
    ["/reports", "报表与数据"],
  ])("renders the dedicated module home for %s", async (path, title) => {
    renderAt(path);

    const page = await screen.findByTestId("module-workbench-home", {}, { timeout: 10000 });
    expect(within(page).getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-kpi-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-status-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-briefing")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-drilldowns")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-data-note")).toBeInTheDocument();
  });

  it("shows explicit fallback states when a source query fails", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getRiskTensorDates: async () => {
        throw new Error("risk dates unavailable");
      },
    };

    renderAt("/risk-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    expect(page).toHaveTextContent("读取失败");
    expect(page).toHaveTextContent("不使用前端补数");
  });

  it("renders risk tensor and cashflow detail cards from backend reads", async () => {
    renderAt("/risk-overview");

    const page = await screen.findByTestId("module-workbench-home");
    expect(within(page).getByTestId("module-home-decision")).toHaveTextContent("风险处置判断");
    expect(within(page).getByTestId("module-home-risk-tensor")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-cashflow")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-risk-evidence")).toBeInTheDocument();
    expect(page).toHaveTextContent("风险张量明细");
    expect(page).toHaveTextContent("现金流与缺口");
    await waitFor(() => {
      expect(page).toHaveTextContent("监管 DV01");
      expect(page).toHaveTextContent("KRD 5Y");
      expect(page).toHaveTextContent("CS01");
      expect(page).toHaveTextContent("久期缺口");
    });
    expect(page).toHaveTextContent("来源 risk-tensor");
    expect(page).toHaveTextContent("来源 cashflow-projection");
  });

  it("does not use portfolio DV01 as a fallback for missing regulatory DV01", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getRiskTensor: vi.fn(async (reportDate: string) => {
        const envelope = await base.getRiskTensor(reportDate);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            regulatory_dv01: null,
            warnings: [],
          },
        };
      }),
    };

    renderAt("/risk-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    const decision = within(page).getByTestId("module-home-decision");
    const kpis = within(page).getByTestId("module-home-kpi-strip");
    await waitFor(() => {
      expect(decision).toHaveTextContent("监管 DV01 待接入");
    });
    expect(kpis).toHaveTextContent("监管 DV01");
    expect(kpis).toHaveTextContent("待接入");
    expect(kpis).toHaveTextContent("估值 DV01");
    expect(kpis).toHaveTextContent("12.00 万元");
  });

  it("keeps risk tensor readable when the auxiliary cashflow read fails", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getCashflowProjection: vi.fn(async () => {
        throw new Error("cashflow unavailable");
      }),
    };

    renderAt("/risk-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(page).toHaveTextContent("部分失败");
      expect(page).toHaveTextContent("风险张量已返回，现金流等辅助链路需单独复核。");
      expect(page).toHaveTextContent("监管 DV01");
      expect(page).toHaveTextContent("12.00 万元");
    });
    expect(page).toHaveTextContent("现金流预测");
    expect(page).toHaveTextContent("读取失败");
    expect(page).toHaveTextContent("不使用前端补数");
  });

  it("renders performance kpi detail and business pnl cards from backend reads", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getKpiValuesSummary: async () => ({
        owner_id: 1,
        owner_name: "固定收益部",
        year: 2026,
        period_type: "YEAR",
        period_label: "2026年度",
        period_start_date: "2026-01-01",
        period_end_date: "2026-05-31",
        metrics: [
          {
            metric_id: 101,
            metric_code: "KPI_BOND_YIELD",
            metric_name: "债券投资收益率",
            major_category: "收益类",
            target_value: "4.50",
            unit: "%",
            score_weight: "15.00",
            period_actual_value: "4.20",
            period_score_value: "12.50",
            period_start_date: "2026-01-01",
            period_end_date: "2026-05-31",
            data_date: "2026-05-31",
          },
        ],
        total: 1,
        total_weight: "100.00",
        total_score: "12.50",
      }),
      getPnlByBusinessYtd: async (year) => ({
        result_meta: {
          trace_id: "perf_home_pnl",
          basis: "formal",
          result_kind: "pnl.by_business_ytd",
          formal_use_allowed: true,
          source_version: "sv_test",
          vendor_version: "vv_test",
          rule_version: "rv_test",
          cache_version: "cv_test",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-06-01T00:00:00Z",
        },
        result: {
          year,
          period_type: "yearly",
          period_label: "2026年累计",
          period_start_date: "2026-01-01",
          period_end_date: "2026-05-31",
          total_pnl: "100000000",
          source_tables: ["fact_formal_pnl_fi"],
          items: [
            {
              row_key: "zqtz",
              sort_order: 1,
              business_type: "债券投资",
              interest_income: "80000000",
              fair_value_change: "10000000",
              capital_gain: "10000000",
              manual_adjustment: "0",
              total_pnl: "100000000",
              avg_balance: "5000000000",
              current_balance: "5000000000",
              balance_yield_pct: "0.02",
              annualized_yield_pct: null,
              ftp_rate_pct: "1.60",
              ftp_cost: null,
              ftp_net_pnl: null,
              ftp_net_annualized_yield_pct: null,
              proportion: "0.65",
              assets_count: 120,
            },
          ],
        },
      }),
    };

    renderAt("/performance", client);

    const page = await screen.findByTestId("module-workbench-home");
    expect(within(page).getByTestId("module-home-kpi-detail")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-business-pnl")).toBeInTheDocument();
    expect(page).toHaveTextContent("KPI 指标明细");
    expect(page).toHaveTextContent("业务种类损益");
    await waitFor(() => {
      expect(page).toHaveTextContent("债券投资收益率");
      expect(page).toHaveTextContent("债券投资");
      expect(page).toHaveTextContent("1 亿元");
    });
    expect(page).toHaveTextContent("来源 kpi");
    expect(page).toHaveTextContent("来源 pnl/by-business");
  });

  it("renders governance source status and cube dimension cards from backend reads", async () => {
    renderAt("/reports");

    const page = await screen.findByTestId("module-workbench-home");
    expect(within(page).getByTestId("module-home-source-status")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-cube-dimensions")).toBeInTheDocument();
    expect(page).toHaveTextContent("数据源状态");
    expect(page).toHaveTextContent("Cube 维度与度量");
    expect(page).toHaveTextContent("规划中");
    await waitFor(() => {
      expect(page).toHaveTextContent("ZQTZ");
      expect(page).toHaveTextContent("asset_class_std");
      expect(page).toHaveTextContent("bond_analytics");
    });
    expect(page).toHaveTextContent("来源 source-foundation");
    expect(page).toHaveTextContent("来源 cube / bond_analytics");
  });
});

describe("PortfolioHomePage", () => {
  it("renders portfolio-specific home content, not dashboard-home blocks", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    expect(page).toHaveTextContent("组合工作台");
    const cockpit = within(page).getByTestId("module-home-portfolio-cockpit");
    const firstScreen = within(cockpit).getByTestId("module-home-portfolio-first-screen");
    expect(within(page).getByTestId("module-home-toolbar")).toBeInTheDocument();
    expect(firstScreen).toContainElement(within(page).getByTestId("module-home-decision"));
    expect(firstScreen).toContainElement(within(page).getByTestId("module-home-briefing"));
    expect(firstScreen).toContainElement(within(page).getByTestId("module-home-kpi-strip"));
    expect(firstScreen).toContainElement(within(page).getByTestId("module-home-portfolio-ai-rail"));
    expect(firstScreen).not.toContainElement(within(page).getByTestId("module-home-status-strip"));
    expect(within(page).getByTestId("module-home-kpi-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-briefing")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-status-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-drilldowns")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-data-note")).toBeInTheDocument();
    expect(within(page).queryByTestId("dashboard-home-hero")).not.toBeInTheDocument();
    expect(within(page).queryByTestId("dashboard-home-work-grid")).not.toBeInTheDocument();
  });

  it("renders mock portfolio guard summaries instead of decision-grade sample summaries", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(page).toHaveTextContent("模拟数据防误用");
      expect(page).toHaveTextContent("当前仅验证页面结构");
      expect(page).toHaveTextContent("不可用于业务决策");
      expect(page).toHaveTextContent("不生成调仓或风险动作");
    });
  });

  it("guards the mock portfolio first screen from decision-grade sample numbers", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    const decision = await within(page).findByTestId("module-home-decision");
    await waitFor(() => {
      expect(page).toHaveTextContent("模拟数据");
      expect(decision).toHaveTextContent("模拟数据防误用");
      expect(decision).toHaveTextContent("不可用于业务决策");
      expect(decision).not.toHaveTextContent("42.00%");
      expect(decision).not.toHaveTextContent("-12.54");
      expect(decision).not.toHaveTextContent("428");
      expect(page).not.toHaveTextContent("42.00%");
      expect(page).not.toHaveTextContent("-12.54");
      expect(within(decision).queryByRole("link", { name: /信用结构复核/ })).not.toBeInTheDocument();
    });
  });

  it("renders real portfolio data with explicit source evidence instead of the mock guard", async () => {
    renderAt("/portfolio", realPortfolioClient());

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(page).toHaveTextContent("已接入");
      expect(page).toHaveTextContent("2026-05-31");
      expect(page).toHaveTextContent("3,322.82 亿元");
      expect(page).toHaveTextContent("1,710 只");
      expect(page).toHaveTextContent("29.96%");
      expect(page).toHaveTextContent("10,562.84 万元");
      expect(page).toHaveTextContent("bond_dashboard.home_summary");
      expect(page).toHaveTextContent("fact_formal_bond_analytics_daily");
      expect(page).toHaveTextContent("1710 行");
      expect(page).toHaveTextContent("无回退");
    });

    const dataNote = within(page).getByTestId("module-home-data-note");
    const decision = within(page).getByTestId("module-home-decision");
    expect(dataNote).toHaveTextContent("formal_use_allowed=true");
    expect(dataNote).toHaveTextContent("basis=formal");
    expect(dataNote).toHaveTextContent("fact_formal_bond_analytics_daily");
    expect(decision).toHaveTextContent("风险指标: basis=formal, formal_use_allowed=true, quality=ok");
    expect(decision).not.toHaveTextContent("风险指标 formal_use_allowed=false");
    expect(page).not.toHaveTextContent("模拟数据防误用");
    expect(page).not.toHaveTextContent("不可用于业务决策");
  });

  it("renders portfolio terminal kpi sparklines from prev_kpis and a risk ticker strip", async () => {
    renderAt("/portfolio", realPortfolioClient());

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(within(page).getByTestId("module-home-portfolio-risk-ticker")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-kpi-strip").querySelectorAll("svg").length).toBeGreaterThanOrEqual(
        2,
      );
      expect(within(page).getByTestId("module-home-portfolio-kpi-bond-market-detail")).toHaveTextContent("环比");
      expect(within(page).getByTestId("module-home-portfolio-ticker-risk-total-dv01")).toHaveTextContent("万元");
    });
  });

  it("renders portfolio holdings hero table and quick access tiles from API-backed panels", async () => {
    renderAt("/portfolio", realPortfolioClient());

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(within(page).getByTestId("module-home-portfolio-holdings-hero")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-portfolio-holdings-row-政策性金融债")).toHaveTextContent(
        "675.35",
      );
      expect(within(page).getByTestId("module-home-portfolio-comparison-hero-table")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-portfolio-comparison-row-portfolio-固收组合")).toHaveTextContent(
        "固收组合",
      );
      expect(within(page).getByTestId("module-home-portfolio-quick-access")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-portfolio-quick-bond-dashboard")).toHaveAttribute(
        "href",
        "/bond-dashboard",
      );
      expect(within(page).getByTestId("module-home-portfolio-quick-positions")).toHaveAttribute("href", "/positions");
    });
  });

  it("keeps portfolio quick access after the first-screen block in cockpit DOM order", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    const cockpit = within(page).getByTestId("module-home-portfolio-cockpit");
    const firstScreen = within(cockpit).getByTestId("module-home-portfolio-first-screen");
    const quickAccess = within(cockpit).getByTestId("module-home-portfolio-quick-access");

    expect(
      firstScreen.compareDocumentPosition(quickAccess) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(within(firstScreen).getByTestId("module-home-kpi-strip")).toBeInTheDocument();
  });

  it("renders normal portfolio action queue only when all evidence is same-day formal", async () => {
    renderAt("/portfolio", realPortfolioClient());

    const page = await screen.findByTestId("module-workbench-home");
    const decision = await within(page).findByTestId("module-home-decision");
    await waitFor(() => {
      expect(decision).toHaveTextContent("同日闭合 2026-05-31");
      expect(decision).toHaveTextContent("子组合分层核验");
    });
    expect(within(decision).queryByRole("link", { name: /来源证据复核/ })).not.toBeInTheDocument();
    expect(within(decision).queryByRole("link", { name: /风险张量日期复核/ })).not.toBeInTheDocument();
  });

  it("checks portfolio risk closure with dates only and never fetches the full tensor", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () =>
      envelopeWithMeta(
        "risk.tensor.dates",
        { report_dates: ["2026-04-30"] },
        {
          basis: "formal",
          formal_use_allowed: true,
          quality_flag: "ok",
        },
      ),
    );
    const getRiskTensor = vi.fn<ApiClient["getRiskTensor"]>((reportDate) => base.getRiskTensor(reportDate));

    renderAt(
      "/portfolio",
      realPortfolioClient({
        getRiskTensorDates,
        getRiskTensor,
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    const decision = await within(page).findByTestId("module-home-decision");
    await waitFor(() => {
      expect(getRiskTensorDates).toHaveBeenCalledTimes(1);
      expect(decision).toHaveTextContent("风险张量未闭合至 2026-05-31");
      expect(decision).toHaveTextContent("最新 2026-04-30");
    });
    expect(getRiskTensor).not.toHaveBeenCalled();
    expect(page).toHaveTextContent("3,322.82 亿元");
  });

  it("downgrades real portfolio conclusions when pnl summary is not formal while preserving values", async () => {
    renderAt(
      "/portfolio",
      realPortfolioClient({
        getPnlAttributionAnalysisSummary: async () =>
          envelopeWithMeta(
            "pnl-attribution.summary",
            {
              report_date: "2026-05-31",
              primary_driver: "market",
              primary_driver_pct: n(0.58, "ratio"),
              key_findings: ["市值变动主要来自市场重估。"],
              tpl_market_aligned: true,
              tpl_market_note: "与 TPL 市场变动方向一致。",
            },
            {
              basis: "analytical",
              formal_use_allowed: false,
              quality_flag: "warning",
              tables_used: ["fact_formal_pnl_fi"],
              evidence_rows: 1710,
            },
          ),
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    const decision = await within(page).findByTestId("module-home-decision");
    await waitFor(() => {
      expect(page).toHaveTextContent("3,322.82 亿元");
      expect(decision).toHaveTextContent("仅供分析");
      expect(decision).toHaveTextContent("损益归因 basis=analytical");
    });
    expect(within(decision).queryByRole("link", { name: /信用结构复核/ })).not.toBeInTheDocument();
    expect(within(decision).queryByRole("link", { name: /久期 DV01 复核/ })).not.toBeInTheDocument();
  });

  it("downgrades real portfolio conclusions when bond home summary is not formal while preserving values", async () => {
    renderAt(
      "/portfolio",
      realPortfolioClient({
        getBondDashboardHomeSummary: async () => ({
          ...envelopeWithMeta("bond_dashboard.home_summary", realPortfolioHomeSummary(), {
            basis: "analytical",
            formal_use_allowed: false,
            quality_flag: "warning",
          }),
          data_source: "bond_analytics_facts",
        }),
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    const decision = await within(page).findByTestId("module-home-decision");
    await waitFor(() => {
      expect(page).toHaveTextContent("3,322.82 亿元");
      expect(decision).toHaveTextContent("仅供分析");
      expect(decision).toHaveTextContent("债券总览 basis=analytical");
    });
    expect(within(decision).queryByRole("link", { name: /信用结构复核/ })).not.toBeInTheDocument();
    expect(within(decision).queryByRole("link", { name: /久期 DV01 复核/ })).not.toBeInTheDocument();
  });

  it("downgrades real portfolio conclusions when bond result metadata date differs while preserving values", async () => {
    renderAt(
      "/portfolio",
      realPortfolioClient({
        getBondDashboardHomeSummary: async () => ({
          ...envelopeWithMeta("bond_dashboard.home_summary", realPortfolioHomeSummary(), {
            basis: "formal",
            formal_use_allowed: true,
            quality_flag: "ok",
            resolved_report_date: "2026-05-30",
            as_of_date: "2026-05-30",
          }),
          data_source: "bond_analytics_facts",
        }),
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    const decision = await within(page).findByTestId("module-home-decision");
    await waitFor(() => {
      expect(page).toHaveTextContent("3,322.82 亿元");
      expect(decision).toHaveTextContent("仅供分析");
      expect(decision).toHaveTextContent("债券总览 meta_date=2026-05-30");
    });
    expect(within(decision).queryByRole("link", { name: /信用结构复核/ })).not.toBeInTheDocument();
    expect(within(decision).queryByRole("link", { name: /久期 DV01 复核/ })).not.toBeInTheDocument();
  });

  it("does not mark portfolio risk closure as same-day closed when risk date evidence fails", async () => {
    const getRiskTensorDates = vi.fn(async () => {
      throw new Error("risk dates unavailable");
    });

    renderAt(
      "/portfolio",
      realPortfolioClient({
        getRiskTensorDates,
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    const decision = await within(page).findByTestId("module-home-decision");
    await waitFor(() => {
      expect(getRiskTensorDates).toHaveBeenCalledTimes(1);
      expect(page).toHaveTextContent("3,322.82 亿元");
      expect(decision).toHaveTextContent("风险闭合证据读取失败");
    });
    expect(decision).not.toHaveTextContent("同日闭合 2026-05-31");
  });

  it("fails closed in real portfolio mode when the bond summary read fails", async () => {
    const getBondDashboardHomeSummary = vi.fn(async () => {
      throw new Error("real bond summary unavailable");
    });

    renderAt(
      "/portfolio",
      realPortfolioClient({
        getBondDashboardHomeSummary,
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(page).toHaveTextContent("读取失败");
      expect(page).toHaveTextContent("不使用前端补数");
      expect(getBondDashboardHomeSummary).toHaveBeenCalledWith("2026-05-31");
    });

    expect(page).not.toHaveTextContent("模拟数据防误用");
    expect(page).not.toHaveTextContent("3,287.09");
    expect(page).not.toHaveTextContent("42.00%");
    expect(page).not.toHaveTextContent("-12.54");
  });

  it("renders portfolio holdings structure and depth panels", async () => {
    renderAt("/portfolio", createRealModeDemoClient());

    const page = await screen.findByTestId("module-workbench-home");
    expect(within(page).getByTestId("module-home-holdings-structure")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-portfolio-terminal")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-portfolio-risk")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-pnl-summary")).toBeInTheDocument();
    await waitFor(() => {
      expect(page).toHaveTextContent("券种分布");
      expect(page).toHaveTextContent("评级分布");
      expect(page).toHaveTextContent("行业分布");
      expect(page).toHaveTextContent("期限分布");
      expect(page).toHaveTextContent("收益率分布");
    });
    const hero = within(page).getByTestId("module-home-portfolio-holdings-hero");
    expect(hero).toHaveTextContent("券种分布");
    const holdings = within(page).getByTestId("module-home-holdings-structure");
    expect(within(holdings).getByTestId("module-home-distribution-yield")).toBeInTheDocument();
    expect(within(holdings).queryByTestId("module-home-distribution-asset-type")).not.toBeInTheDocument();
    expect(within(holdings).getAllByRole("link", { name: "查看全部" }).length).toBeGreaterThanOrEqual(4);
    expect(within(holdings).getByRole("link", { name: "持仓透视" })).toHaveAttribute("href", "/positions");
  });

  it("renders structure tab chart beside portfolio comparison list", async () => {
    renderAt("/portfolio", createRealModeDemoClient());

    const page = await screen.findByTestId("module-workbench-home");
    const terminal = within(page).getByTestId("module-home-portfolio-terminal");
    await waitFor(() => {
      expect(within(terminal).getByTestId("module-home-structure-chart")).toBeInTheDocument();
      expect(within(terminal).getByTestId("module-home-echarts-stub")).toHaveAttribute("data-chart-height", "280");
    });
  });

  it("renders all portfolio module drilldown links", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    const drilldowns = within(page).getByTestId("module-home-drilldowns");
    const links = within(drilldowns).getAllByRole("link");
    expect(links).toHaveLength(PORTFOLIO_MODULE_DRILLDOWN_COUNT);
    expect(page).toHaveTextContent("债券分析");
    expect(page).toHaveTextContent("余额变动分析");
    expect(page).toHaveTextContent("负债结构分析");
    expect(page).toHaveTextContent("日均分析");
    expect(page).toHaveTextContent("总账损益");
    expect(page).toHaveTextContent("银行台账");
    expect(page).toHaveTextContent("产品分析");
    expect(page).toHaveTextContent("收益分析");
    expect(page).toHaveTextContent("损益桥接");
    expect(page).toHaveTextContent("业务种类损益");
  });

  it("renders portfolio drilldown links to balance and attribution pages", async () => {
    renderAt("/portfolio");

    const page = await screen.findByTestId("module-workbench-home");
    expect(page).toHaveTextContent("资产负债分析");
    expect(page).toHaveTextContent("收益归因");
    expect(page).toHaveTextContent("持仓透视");
  });
  it("uses the compact bond home summary for depth reads while fetching formal risk evidence", async () => {
    const base = createApiClient({ mode: "mock" });
    const getBondDashboardHomeSummary = vi.fn<ApiClient["getBondDashboardHomeSummary"]>(
      (reportDate) => base.getBondDashboardHomeSummary(reportDate),
    );
    const getBondDashboardHeadlineKpis = vi.fn<ApiClient["getBondDashboardHeadlineKpis"]>(
      (reportDate) => base.getBondDashboardHeadlineKpis(reportDate),
    );
    const getBondDashboardRiskIndicators = vi.fn<ApiClient["getBondDashboardRiskIndicators"]>(
      (reportDate) => base.getBondDashboardRiskIndicators(reportDate),
    );
    const getBondDashboardAssetStructure = vi.fn<ApiClient["getBondDashboardAssetStructure"]>(
      (reportDate, groupBy) => base.getBondDashboardAssetStructure(reportDate, groupBy),
    );
    const getBondDashboardMaturityStructure = vi.fn<ApiClient["getBondDashboardMaturityStructure"]>(
      (reportDate) => base.getBondDashboardMaturityStructure(reportDate),
    );
    const getBondDashboardIndustryDistribution = vi.fn<ApiClient["getBondDashboardIndustryDistribution"]>(
      (reportDate) => base.getBondDashboardIndustryDistribution(reportDate),
    );
    const getBondDashboardYieldDistribution = vi.fn<ApiClient["getBondDashboardYieldDistribution"]>(
      (reportDate) => base.getBondDashboardYieldDistribution(reportDate),
    );
    const getBondDashboardPortfolioComparison = vi.fn<ApiClient["getBondDashboardPortfolioComparison"]>(
      (reportDate) => base.getBondDashboardPortfolioComparison(reportDate),
    );
    const getBondDashboardSpreadAnalysis = vi.fn<ApiClient["getBondDashboardSpreadAnalysis"]>(
      (reportDate) => base.getBondDashboardSpreadAnalysis(reportDate),
    );
    const getBondBusinessTypeMetrics = vi.fn<ApiClient["getBondBusinessTypeMetrics"]>(
      (params) => base.getBondBusinessTypeMetrics(params),
    );
    const client: ApiClient = {
      ...base,
      getBondDashboardHomeSummary,
      getBondDashboardHeadlineKpis,
      getBondDashboardRiskIndicators,
      getBondDashboardAssetStructure,
      getBondDashboardMaturityStructure,
      getBondDashboardIndustryDistribution,
      getBondDashboardYieldDistribution,
      getBondDashboardPortfolioComparison,
      getBondDashboardSpreadAnalysis,
      getBondBusinessTypeMetrics,
    };

    renderAt("/portfolio", client);

    await waitFor(() => {
      expect(getBondDashboardHomeSummary).toHaveBeenCalledWith("2026-03-31");
      expect(getBondDashboardRiskIndicators).toHaveBeenCalledWith("2026-03-31");
      expect(screen.getByTestId("module-workbench-home")).toHaveTextContent("模拟数据防误用");
    });
    expect(getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
    expect(getBondDashboardAssetStructure).not.toHaveBeenCalled();
    expect(getBondDashboardMaturityStructure).not.toHaveBeenCalled();
    expect(getBondDashboardIndustryDistribution).not.toHaveBeenCalled();
    expect(getBondDashboardYieldDistribution).not.toHaveBeenCalled();
    expect(getBondDashboardPortfolioComparison).not.toHaveBeenCalled();
    expect(getBondDashboardSpreadAnalysis).not.toHaveBeenCalled();
    expect(getBondBusinessTypeMetrics).not.toHaveBeenCalled();
  });
});

describe("MarketHomePage", () => {
  it("requests full macro analysis before deferred strategy summaries", async () => {
    const base = createApiClient({ mode: "mock" });
    const analysis = deferred<ApiEnvelope<MacroToolkitAnalysisPayload>>();
    const getMacroToolkitAnalysis = vi.fn(() => analysis.promise);
    const getMacroToolkitStrategySummaries = vi.fn(async () => strategySummariesEnvelope());
    const client: ApiClient = {
      ...base,
      getMacroToolkitAnalysis,
      getMacroToolkitStrategySummaries,
    };

    renderAt("/market-overview", client);

    await waitFor(() => {
      expect(getMacroToolkitAnalysis).toHaveBeenCalledWith({ detail: "full" });
    });
    expect(getMacroToolkitStrategySummaries).not.toHaveBeenCalled();

    analysis.resolve(coreMacroAnalysisEnvelope());

    await waitFor(() => {
      expect(getMacroToolkitStrategySummaries).toHaveBeenCalledTimes(1);
    });
  });

  it("renders market-specific home content with portfolio-style layout", async () => {
    renderAt("/market-overview");

    const page = await screen.findByTestId("module-workbench-home");
    expect(page).toHaveTextContent("市场工作台");
    expect(within(page).getByTestId("module-home-toolbar")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-kpi-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-briefing")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-status-strip")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-drilldowns")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-data-note")).toBeInTheDocument();
    expect(within(page).queryByTestId("dashboard-home-hero")).not.toBeInTheDocument();
  });

  it("renders the market overview as an institutional cockpit with an evidence rail", async () => {
    renderAt("/market-overview");

    const page = await screen.findByTestId("module-workbench-home");
    const cockpit = within(page).getByTestId("module-home-market-cockpit");
    const primaryGrid = within(page).getByTestId("module-home-market-primary-grid");
    const evidenceRail = within(page).getByTestId("module-home-market-evidence-rail");

    expect(cockpit.className).toEqual(expect.stringContaining("marketInstitutionalCockpit"));
    expect(cockpit.className).toEqual(expect.stringContaining("marketCockpitCohesion"));
    expect(within(page).getByTestId("module-home-market-macro-ticker")).toBeInTheDocument();
    expect(primaryGrid).toContainElement(within(page).getByTestId("module-home-briefing"));
    expect(
      within(page).getByTestId("module-home-briefing").querySelector('[class*="marketJudgementHero"]'),
    ).toBeTruthy();
    expect(primaryGrid).toContainElement(evidenceRail);
    expect(within(evidenceRail).getByText("市场快照")).toBeVisible();
    const evidenceRailMetrics = within(evidenceRail).getByTestId("module-home-market-evidence-rail-metrics");
    expect(within(evidenceRailMetrics).getByText("10Y国债")).toBeVisible();
    expect(within(evidenceRailMetrics).getByText("流动性")).toBeVisible();
    expect(within(evidenceRailMetrics).getByText("跨资产")).toBeVisible();
    const kpiStrip = within(page).getByTestId("module-home-kpi-strip");
    expect(kpiStrip).toHaveTextContent("10Y国债");
    expect(kpiStrip).toHaveTextContent("流动性");
    expect(kpiStrip).toHaveTextContent("跨资产");
    expect(kpiStrip).toHaveTextContent("宏观信号");
    expect(kpiStrip).not.toHaveTextContent("最新行情");
    expect(kpiStrip).not.toHaveTextContent("正式利率");
    expect(kpiStrip).not.toHaveTextContent("目录序列");
    expect(kpiStrip).not.toHaveTextContent("工具命中率");
    const evidenceRailState = within(evidenceRail).getByTestId("module-home-market-evidence-rail-state");
    expect(evidenceRailState).toHaveAttribute("hidden");
    expect(evidenceRailState).not.toBeVisible();
    const auditStatus = within(evidenceRail).getByTestId("module-home-market-audit-status");
    expect(auditStatus).toHaveAttribute("hidden");
    expect(auditStatus).not.toBeVisible();
    expect(auditStatus).toHaveTextContent("约束检查结果");
    expect(evidenceRail).not.toHaveTextContent("AI 决策舱");
    expect(within(page).getByTestId("module-home-toolbar")).toHaveTextContent(
      "先看利率曲线与流动性，再看跨资产传导，必要时进入下钻复核。",
    );
    const topbarAuditMeta = within(page).getByTestId("module-home-market-topbar-audit-meta");
    expect(topbarAuditMeta).toHaveAttribute("hidden");
    expect(within(topbarAuditMeta).getByText("读取中")).toHaveAttribute("data-tone", "muted");
    expect(within(topbarAuditMeta).getByText("读取中")).not.toBeVisible();
    const sourceGate = within(page).getByTestId("module-home-status-strip");
    expect(sourceGate).toHaveAttribute("hidden");
    expect(sourceGate).not.toBeVisible();
    expect(sourceGate).toHaveTextContent("来源闸门");
    expect(within(evidenceRail).getByRole("link", { name: "市场数据" })).toHaveAttribute("href", "/market-data");
    expect(within(evidenceRail).getByRole("link", { name: "宏观工具" })).toHaveAttribute("href", "/macro-toolkit");
    expect(within(evidenceRail).getByRole("link", { name: "跨资产" })).toHaveAttribute("href", "/cross-asset");
  });

  it("renders market key rate snapshot and terminal tabs from market-data reads", async () => {
    const user = userEvent.setup();
    renderAt("/market-overview");

    const page = await screen.findByTestId("module-workbench-home");
    expect(within(page).queryByTestId("module-home-rate-snapshot")).not.toBeInTheDocument();
    expect(within(page).getByTestId("module-home-market-depth-zone")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-market-analysis-grid")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-market-distribution-grid")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-market-terminal").className).toEqual(
      expect.stringContaining("marketDeskPanel"),
    );
    expect(within(page).getByTestId("module-home-yield-curve").className).toEqual(
      expect.stringContaining("marketDeskPanel"),
    );
    expect(within(page).getByTestId("module-home-market-terminal")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-market-matrix")).toBeInTheDocument();
    const decisionMatrix = within(page).getByTestId("module-home-market-matrix");
    expect(decisionMatrix.className).toEqual(expect.stringContaining("marketDeskPanel"));
    expect(decisionMatrix).toHaveTextContent("市场决策要点");
    expect(decisionMatrix).toHaveTextContent("维度");
    expect(decisionMatrix).toHaveTextContent("读数");
    expect(decisionMatrix).toHaveTextContent("变动");
    expect(decisionMatrix).toHaveTextContent("待曲线核验");
    const decisionMatrixAuditLabel = within(decisionMatrix).getByTestId("module-home-market-matrix-audit-label");
    expect(decisionMatrixAuditLabel).toHaveAttribute("hidden");
    expect(decisionMatrixAuditLabel).not.toBeVisible();
    expect(within(page).queryByTestId("module-home-market-command")).not.toBeInTheDocument();
    expect(within(page).getByTestId("module-home-status-strip")).toHaveAttribute("hidden");
    expect(within(page).getByTestId("module-home-status-strip")).not.toBeVisible();
    const actionQueue = within(page).getByTestId("module-home-market-actions");
    expect(actionQueue.className).toEqual(expect.stringContaining("marketDeskPanel"));
    expect(actionQueue).toHaveTextContent("下一步动作");
    expect(actionQueue).toHaveTextContent("只保留今天需要看的事");
    expect(actionQueue).toHaveTextContent("优先级");
    expect(actionQueue).toHaveTextContent("事项");
    expect(actionQueue).toHaveTextContent("证据");
    expect(actionQueue).toHaveTextContent("入口");
    expect(actionQueue).toHaveTextContent("补齐国债/国开曲线核验");
    const actionQueueAuditLabel = within(actionQueue).getByTestId("module-home-market-actions-audit-label");
    expect(actionQueueAuditLabel).toHaveAttribute("hidden");
    expect(actionQueueAuditLabel).not.toBeVisible();
    expect(within(page).getByTestId("module-home-market-hero-evidence")).toBeInTheDocument();
    const heroMeta = within(page).getByTestId("module-home-market-hero-meta");
    expect(heroMeta).toBeInTheDocument();
    expect(heroMeta).toHaveAttribute("hidden");
    expect(heroMeta).toHaveTextContent("Choice/Tushare 市场数据 / 跨资产");
    expect(heroMeta).not.toHaveTextContent("ChoiceTushare");
    const matrixRateCell = within(page).getByTestId("module-home-market-matrix-cell-rates");
    expect(within(matrixRateCell).getByTestId("module-home-market-matrix-cell-rates-headline")).toBeInTheDocument();
    const matrixRateMeta = within(matrixRateCell).getByTestId("module-home-market-matrix-cell-rates-meta");
    const matrixRateEvidence = within(matrixRateCell).getByTestId("module-home-market-matrix-cell-rates-evidence");
    expect(matrixRateMeta).toBeInTheDocument();
    expect(matrixRateMeta).toHaveAttribute("hidden");
    expect(matrixRateMeta).not.toBeVisible();
    expect(matrixRateMeta.textContent).toContain(" / ");
    expect(matrixRateEvidence).toBeInTheDocument();
    expect(matrixRateEvidence).toHaveAttribute("hidden");
    expect(matrixRateEvidence).not.toBeVisible();
    expect(within(page).getByTestId("module-home-market-matrix-cell-data")).toHaveAttribute("hidden");
    expect(within(page).getByTestId("module-home-market-matrix-cell-data")).not.toBeVisible();
    const marketDataAction = within(actionQueue).getByTestId("module-home-market-action-curve-check");
    const curveCheckEvidence = within(marketDataAction).getByTestId("module-home-market-action-curve-check-evidence");
    expect(curveCheckEvidence).toBeInTheDocument();
    const curveCheckTaskMeta = within(marketDataAction).getByTestId("module-home-market-action-curve-check-task-meta");
    const curveCheckGate = within(marketDataAction).getByTestId("module-home-market-action-curve-check-gate");
    const curveCheckEvidencePack = within(marketDataAction).getByTestId(
      "module-home-market-action-curve-check-evidence-pack",
    );
    expect(curveCheckTaskMeta).toHaveTextContent(
      "Owner 市场数据岗 / SLA T+0 收盘前 / 状态 待核验",
    );
    expect(curveCheckGate).toHaveTextContent(
      "触发 曲线缺口 / 核验 国债/国开曲线 / 下一步 市场数据",
    );
    expect(curveCheckEvidencePack).toHaveTextContent(
      "Evidence Pack 曲线报价缺口 / 等待既有 API 返回。 / market-data",
    );
    expect(curveCheckTaskMeta).not.toBeVisible();
    expect(curveCheckGate).not.toBeVisible();
    expect(curveCheckEvidencePack).not.toBeVisible();
    expect(within(marketDataAction).getByTestId("module-home-market-action-curve-check-target")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-yield-curve")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-macro-snapshot")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-macro-toolkit")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-market-bottom-nav")).toBeInTheDocument();
    expect(within(page).getAllByTestId(/^module-home-drill-/).length).toBe(MARKET_MODULE_DRILLDOWN_COUNT);
    expect(within(page).getByTestId("module-home-drill-market-data")).toHaveTextContent("MD");
    expect(page).not.toHaveTextContent("关键利率快照");
    expect(page).toHaveTextContent("正式利率序列");
    expect(page).toHaveTextContent("跨资产快讯");
    expect(page).toHaveTextContent("国债与国开曲线");
    await waitFor(() => {
      expect(page).toHaveTextContent("DR007");
      expect(page.textContent).not.toMatch(/\dindex/);
      expect(within(page).getByTestId("module-home-market-kpi-cross-asset-detail")).toHaveTextContent("日变动");
      expect(within(page).getByTestId("module-home-market-kpi-cross-asset-detail")).toHaveAttribute("data-change", "down");
      expect(within(page).getByTestId("module-home-kpi-strip").querySelectorAll("svg").length).toBeGreaterThanOrEqual(2);
      expect(within(page).getByTestId("module-home-market-macro-ticker").querySelectorAll("svg").length).toBeGreaterThanOrEqual(2);
      expect(within(page).getByTestId("module-home-market-macro-ticker")).toHaveTextContent("DR007");
      expect(within(page).getByTestId("module-home-market-matrix-cell-rates-summary")).toHaveAttribute("data-change", "down");
      const tenYearTicker = within(page).getByTestId("module-home-market-ticker-gov-10y");
      expect(tenYearTicker.querySelector("[data-change]")).toBeTruthy();
      expect(within(page).getByTestId("module-home-market-evidence-rail-ten-year")).toHaveAttribute("data-change");
      const macroSnapshot = within(page).getByTestId("module-home-macro-snapshot");
      expect(macroSnapshot.querySelector("[data-change]")).toBeTruthy();
      expect(within(page).getByTestId("module-home-market-terminal").querySelector('[data-chart-height="190"]')).toBeTruthy();
      expect(within(page).getByTestId("module-home-market-terminal")).toHaveTextContent("图表");
      expect(within(page).getByTestId("module-home-yield-curve")).toHaveTextContent("来源");
      expect(within(page).getByTestId("module-home-macro-signals")).toBeInTheDocument();
      expect(
        within(page).getByTestId("module-home-macro-signal-risk_appetite").querySelector('[data-change="up"]'),
      ).toBeTruthy();
      expect(within(page).getByTestId("module-home-macro-signal-risk_appetite").querySelector("svg")).toBeTruthy();
      expect(within(page).getByTestId("module-home-drill-market-overview")).toHaveTextContent("HO");
      expect(within(page).getByTestId("module-home-market-evidence-rail-metrics-scroll")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-market-evidence-rail-actions-scroll")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-macro-signals-scroll")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-market-evidence-rail-metrics")).toHaveAttribute("tabindex", "0");
      expect(within(page).getByTestId("module-home-macro-signals")).toHaveAttribute("tabindex", "0");
      expect(within(page).getByTestId("module-home-market-macro-ticker-scroll")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-market-macro-ticker").querySelector('[role="region"]')).toHaveAttribute(
        "tabindex",
        "0",
      );
      expect(within(page).getByTestId("module-home-macro-groups")).toBeInTheDocument();
      expect(page).toHaveTextContent("核心归因");
      expect(page).toHaveTextContent("工具明细");
      expect(page).toHaveTextContent("组合运行");
      expect(page).toHaveTextContent("中性观察");
      expect(page).toHaveTextContent("流动性");
      expect(within(page).queryByTestId("module-home-macro-a-share-risk")).not.toBeInTheDocument();
      expect(page).toHaveTextContent("橙色风险");
      expect(within(page).getByTestId("module-home-market-actions")).toHaveTextContent("复核A股踩踏风险");
      expect(within(page).getByTestId("module-home-market-actions")).toHaveTextContent("跟踪跨资产传导");
      const crossAssetAction = within(page).getByTestId("module-home-market-action-cross-asset-path");
      const crossAssetEvidence = within(crossAssetAction).getByTestId(
        "module-home-market-action-cross-asset-path-evidence",
      );
      expect(crossAssetEvidence.querySelector('[data-change="down"]')).toBeTruthy();
    });
    const macroGroups = within(page).getByTestId("module-home-macro-groups");
    await user.click(within(macroGroups).getByRole("button", { name: /展开明细/ }));
    await waitFor(() => {
      expect(within(page).getByTestId("module-home-macro-a-share-risk")).toBeInTheDocument();
      expect(
        within(page).getByTestId("module-home-macro-a-share-risk").querySelector('[class*="terminalTableHead"]'),
      ).toBeTruthy();
    });
    await user.click(within(macroGroups).getByRole("tab", { name: "工具明细" }));
    await user.click(within(macroGroups).getByRole("button", { name: /展开明细/ }));
    await waitFor(() => {
      const compactPanel = within(page).getByTestId("module-home-macro-capabilities");
      expect(compactPanel.querySelector('[class*="terminalTableHeadCompact"]')).toBeTruthy();
      expect(compactPanel).toHaveTextContent("Δ");
    });
    await user.click(within(macroGroups).getByRole("tab", { name: "组合运行" }));
    await waitFor(() => {
      expect(within(page).queryByTestId("module-home-macro-hason")).not.toBeInTheDocument();
    });
    await user.click(within(macroGroups).getByRole("button", { name: /展开明细/ }));
    await waitFor(() => {
      expect(within(page).getByTestId("module-home-macro-hason")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-macro-shadow")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-macro-runtime")).toBeInTheDocument();
      expect(page).toHaveTextContent("影子组合报告");
    });
  });

  it("hides macro group tabs when grouped macro detail panels have no rows", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getMacroToolkitAnalysis: async () => coreMacroAnalysisEnvelope(),
      getMacroToolkitStrategySummaries: async () => strategySummariesEnvelope(),
    };

    renderAt("/market-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(page).toHaveTextContent("中性观察");
      expect(within(page).queryByTestId("module-home-macro-groups")).not.toBeInTheDocument();
    });
  });

  it("keeps empty market workbench and depth cards compact", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getChoiceMacroLatest: async () => emptyChoiceMacroEnvelope("macro.choice.latest"),
      getMarketDataRates: async () => emptyChoiceMacroEnvelope("market_data.rates"),
      getMarketDataCatalog: async () => emptyMacroVendorEnvelope(),
      getMacroToolkitAnalysis: async () => coreMacroAnalysisEnvelope(),
      getMacroToolkitStrategySummaries: async () => strategySummariesEnvelope(),
    };

    renderAt("/market-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(within(page).getByTestId("module-home-market-terminal").className).toEqual(
        expect.stringContaining("marketCompactEmptyTerminal"),
      );
      expect(within(page).getByTestId("module-home-yield-curve").className).toEqual(
        expect.stringContaining("marketCompactEmptyPanel"),
      );
      expect(within(page).getByTestId("module-home-macro-snapshot").className).toEqual(
        expect.stringContaining("marketCompactEmptyPanel"),
      );
      expect(within(page).queryByTestId("module-home-panel-summary")).not.toBeInTheDocument();
    });
  });

  it("keeps populated market terminal rows in a bounded scroll surface", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getChoiceMacroLatest: async () => emptyChoiceMacroEnvelope("macro.choice.latest"),
      getMarketDataRates: async () => oneRateSeriesEnvelope(),
      getMarketDataCatalog: async () => emptyMacroVendorEnvelope(),
      getMacroToolkitAnalysis: async () => coreMacroAnalysisEnvelope(),
      getMacroToolkitStrategySummaries: async () => strategySummariesEnvelope(),
    };

    renderAt("/market-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(within(page).getByTestId("module-home-market-terminal").querySelector('[class*="terminalTableScroll"]')).toBeTruthy();
    });
    const matrixRateCell = within(page).getByTestId("module-home-market-matrix-cell-rates");
    expect(within(matrixRateCell).getByTestId("module-home-market-matrix-cell-rates-meta")).toHaveTextContent(
      "1 条 / 1 源 / 2026-05-29",
    );
    expect(within(matrixRateCell).getByTestId("module-home-market-matrix-cell-rates-evidence")).toHaveTextContent(
      "2026-05-29 / -1bp / CA.CN_GOV_10Y",
    );
    expect(within(matrixRateCell).getByTestId("module-home-market-matrix-cell-rates-headline")).toHaveTextContent(
      "10Y 国债 1.71%",
    );
    expect(within(matrixRateCell).getByTestId("module-home-market-matrix-cell-rates-summary")).toHaveTextContent("-1bp");
    expect(matrixRateCell).toHaveTextContent("利率曲线");
    const keyRateAction = within(page).getByTestId("module-home-market-action-key-rate-check");
    const keyRateEvidence = within(keyRateAction).getByTestId("module-home-market-action-key-rate-check-evidence");
    const keyRateTaskMeta = within(keyRateAction).getByTestId("module-home-market-action-key-rate-check-task-meta");
    const keyRateGate = within(keyRateAction).getByTestId("module-home-market-action-key-rate-check-gate");
    const keyRateEvidencePack = within(keyRateAction).getByTestId(
      "module-home-market-action-key-rate-check-evidence-pack",
    );
    expect(keyRateEvidence).toHaveTextContent(
      "10Y 国债 / 1.71% / -1bp / 2026-05-29",
    );
    expect(keyRateEvidence.querySelector('[data-change="down"]')).toBeTruthy();
    expect(keyRateEvidence).not.toHaveTextContent("CA.CN_GOV_10Y");
    expect(keyRateTaskMeta).not.toBeVisible();
    expect(keyRateGate).not.toBeVisible();
    expect(keyRateEvidencePack).not.toBeVisible();
    expect(keyRateEvidencePack).toHaveTextContent("Evidence Pack 10Y 国债 / CA.CN_GOV_10Y");
    expect(within(keyRateAction).getByTestId("module-home-market-action-key-rate-check-target")).toHaveTextContent(
      "利率序列",
    );
    expect(keyRateAction).toHaveTextContent("10Y 国债 / 1.71%");
    expect(keyRateAction.textContent).not.toContain("事项10Y 国债");
  });

  it("renders all market module drilldown links", async () => {
    renderAt("/market-overview");

    const page = await screen.findByTestId("module-workbench-home");
    const drilldowns = within(page).getByTestId("module-home-drilldowns");
    const links = within(drilldowns).getAllByRole("link");
    expect(links).toHaveLength(MARKET_MODULE_DRILLDOWN_COUNT);
    expect(page).toHaveTextContent("宏观工具");
    expect(page).toHaveTextContent("股票分析");
  });
});
