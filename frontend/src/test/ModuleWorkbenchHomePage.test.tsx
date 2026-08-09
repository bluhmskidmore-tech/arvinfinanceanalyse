import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import type {
  ApiEnvelope,
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisOverviewPayload,
  BondAnalyticsDatesPayload,
  BondDashboardHomeSummaryPayload,
  ChoiceNewsEventsPayload,
  ChoiceMacroLatestPayload,
  DV01RiskPayload,
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
import type { ModuleHomeDistributionPanel } from "../features/workbench/module-home/moduleHomeModel";
import { PortfolioDistributionPanel } from "../features/workbench/module-home/PortfolioDistributionPanel";
import { PORTFOLIO_MODULE_DRILLDOWN_COUNT } from "../features/workbench/module-home/portfolioModuleDrilldowns";
import { MARKET_HOME_CRISIS_SCORE_HISTORY_LIMIT } from "../features/workbench/module-home/useMarketHomeQueries";
import { formatRawAsNumeric } from "../utils/format";

const MARKET_HOME_NOCTURNE_CSS_PATH = resolve(
  process.cwd(),
  "src/features/workbench/module-home/marketHomeNocturne.module.css",
);

vi.mock("../mocks/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../mocks/navigation")>()),
  isAgentFrontendEnabled: () => true,
}));

vi.mock("../lib/echarts", () => ({
  default: ({
    option,
    style,
  }: {
    option?: { xAxis?: { data?: string[] }; yAxis?: { data?: string[] } };
    style?: { height?: number | string };
  }) => (
    <div
      data-testid="module-home-echarts-stub"
      data-chart-height={String(style?.height ?? "")}
      data-chart-categories={JSON.stringify(option?.yAxis?.data ?? option?.xAxis?.data ?? [])}
    />
  ),
}));

vi.mock("../features/agent/AgentPanel", () => ({
  AgentPanel: function MockAgentPanel({
    pageId,
    reportDate = null,
    currentFilters = {},
    defaultFilters = {},
    selectedRows = [],
    contextNote = null,
  }: {
    pageId: string;
    reportDate?: string | null;
    currentFilters?: Record<string, unknown>;
    defaultFilters?: Record<string, unknown>;
    selectedRows?: Array<Record<string, unknown>>;
    contextNote?: string | null;
  }) {
    const pageContext = {
      page_id: pageId,
      current_filters:
        reportDate != null
          ? { ...defaultFilters, ...currentFilters, report_date: reportDate }
          : { ...defaultFilters, ...currentFilters },
      selected_rows: selectedRows,
      context_note: contextNote,
    };
    return (
      <div data-testid="agent-panel">
        <code data-testid="agent-panel-page-context">{JSON.stringify(pageContext)}</code>
      </div>
    );
  },
}));

vi.mock("../app/ThemedRouteBoundary", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

beforeAll(async () => {
  await preloadWorkbenchRouteModules("market-overview", "risk-overview", "module-home");
}, 120_000);

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
  const totalMarketValue = 332_281_921_064.45;
  return {
    report_date: reportDate,
    headline: {
      report_date: reportDate,
      prev_report_date: "2026-04-30",
      kpis: {
        total_market_value: n(totalMarketValue, "yuan"),
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
      total_market_value: n(totalMarketValue, "yuan"),
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
      total_market_value: n(totalMarketValue, "yuan"),
      items: [
        {
          category: "政策性金融债",
          total_market_value: n(67_535_152_800.52, "yuan"),
          bond_count: 109,
          percentage: n(0.20324655, "pct"),
        },
        {
          category: "地方政府债",
          total_market_value: n(63_000_000_000, "yuan"),
          bond_count: 214,
          percentage: n(0.18959791, "pct"),
        },
        {
          category: "同业存单",
          total_market_value: n(58_000_000_000, "yuan"),
          bond_count: 438,
          percentage: n(0.17454911, "pct"),
        },
        {
          category: "信用债-企业",
          total_market_value: n(47_000_000_000, "yuan"),
          bond_count: 312,
          percentage: n(0.14144161, "pct"),
        },
        {
          category: "国债",
          total_market_value: n(38_000_000_000, "yuan"),
          bond_count: 186,
          percentage: n(0.1143532, "pct"),
        },
        {
          category: "其他",
          total_market_value: n(58_746_768_263.93, "yuan"),
          bond_count: 451,
          percentage: n(0.17681162, "pct"),
        },
      ],
    },
    asset_rating: {
      report_date: reportDate,
      group_by: "rating",
      total_market_value: n(totalMarketValue, "yuan"),
      items: [
        {
          category: "AAA",
          total_market_value: n(220_000_000_000, "yuan"),
          bond_count: 900,
          percentage: n(0.6621, "pct"),
        },
        {
          category: "AA+",
          total_market_value: n(54_000_000_000, "yuan"),
          bond_count: 276,
          percentage: n(0.16251254, "pct"),
        },
        {
          category: "AA",
          total_market_value: n(31_000_000_000, "yuan"),
          bond_count: 188,
          percentage: n(0.09329429, "pct"),
        },
        {
          category: "未评级",
          total_market_value: n(17_000_000_000, "yuan"),
          bond_count: 206,
          percentage: n(0.05116139, "pct"),
        },
        {
          category: "A+",
          total_market_value: n(10_281_921_064.45, "yuan"),
          bond_count: 140,
          percentage: n(0.03093255, "pct"),
        },
      ],
    },
    maturity: {
      report_date: reportDate,
      total_market_value: n(totalMarketValue, "yuan"),
      items: [
        {
          maturity_bucket: "1年以内",
          total_market_value: n(39_000_000_000, "yuan"),
          bond_count: 302,
          percentage: n(0.1173702, "pct"),
        },
        {
          maturity_bucket: "1-3年",
          total_market_value: n(96_000_000_000, "yuan"),
          bond_count: 548,
          percentage: n(0.28891008, "pct"),
        },
        {
          maturity_bucket: "3-5年",
          total_market_value: n(81_000_000_000, "yuan"),
          bond_count: 320,
          percentage: n(0.2438, "pct"),
        },
        {
          maturity_bucket: "5-7年",
          total_market_value: n(62_000_000_000, "yuan"),
          bond_count: 236,
          percentage: n(0.18658857, "pct"),
        },
        {
          maturity_bucket: "7年以上",
          total_market_value: n(54_281_921_064.45, "yuan"),
          bond_count: 304,
          percentage: n(0.16333115, "pct"),
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
        {
          industry_name: "城投",
          total_market_value: n(61_000_000_000, "yuan"),
          bond_count: 284,
          percentage: n(0.18357885, "pct"),
        },
        {
          industry_name: "交通运输",
          total_market_value: n(48_000_000_000, "yuan"),
          bond_count: 198,
          percentage: n(0.14445504, "pct"),
        },
        {
          industry_name: "电力",
          total_market_value: n(36_000_000_000, "yuan"),
          bond_count: 168,
          percentage: n(0.10834128, "pct"),
        },
        {
          industry_name: "其他",
          total_market_value: n(37_281_921_064.45, "yuan"),
          bond_count: 340,
          percentage: n(0.11221349, "pct"),
        },
      ],
    },
    yield_distribution: {
      report_date: reportDate,
      weighted_ytm: n(0.02561294, "pct", true),
      items: [
        {
          yield_bucket: "<2%",
          total_market_value: n(36_000_000_000, "yuan"),
          bond_count: 256,
        },
        {
          yield_bucket: "2%-3%",
          total_market_value: n(210_000_000_000, "yuan"),
          bond_count: 1110,
        },
        {
          yield_bucket: "3%-4%",
          total_market_value: n(62_000_000_000, "yuan"),
          bond_count: 246,
        },
        {
          yield_bucket: ">4%",
          total_market_value: n(24_281_921_064.45, "yuan"),
          bond_count: 98,
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
        {
          portfolio_name: "银行账户",
          total_market_value: n(185_000_000_000, "yuan"),
          weighted_ytm: n(0.0248, "pct", true),
          weighted_duration: n(4.82, "ratio"),
          total_dv01: n(70_200_000, "dv01"),
          bond_count: 942,
        },
        {
          portfolio_name: "交易账户",
          total_market_value: n(98_000_000_000, "yuan"),
          weighted_ytm: n(0.0295, "pct", true),
          weighted_duration: n(3.88, "ratio"),
          total_dv01: n(24_900_000, "dv01"),
          bond_count: 486,
        },
        {
          portfolio_name: "OCI账户",
          total_market_value: n(49_281_921_064.45, "yuan"),
          weighted_ytm: n(0.0264, "pct", true),
          weighted_duration: n(4.36, "ratio"),
          total_dv01: n(10_528_442.39590558, "dv01"),
          bond_count: 282,
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
        {
          bond_type: "地方政府债",
          median_yield: n(0.0242, "pct", true),
          bond_count: 214,
          total_market_value: n(63_000_000_000, "yuan"),
        },
        {
          bond_type: "信用债-企业",
          median_yield: n(0.0321, "pct", true),
          bond_count: 312,
          total_market_value: n(47_000_000_000, "yuan"),
        },
        {
          bond_type: "同业存单",
          median_yield: n(0.0268, "pct", true),
          bond_count: 438,
          total_market_value: n(58_000_000_000, "yuan"),
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
        {
          name: "地方政府债",
          market_value: "63000000000.00",
          weighted_avg_ytm_pct: "2.42000000",
          weighted_avg_duration: "4.18000000",
          duration_source: "formal",
        },
        {
          name: "同业存单",
          market_value: "58000000000.00",
          weighted_avg_ytm_pct: "2.68000000",
          weighted_avg_duration: "0.74000000",
          duration_source: "formal",
        },
        {
          name: "信用债-企业",
          market_value: "47000000000.00",
          weighted_avg_ytm_pct: "3.21000000",
          weighted_avg_duration: "2.95000000",
          duration_source: "formal",
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

const BOND_EXACT_MONTH_ENDS = [
  "2026-01-31",
  "2026-02-28",
  "2026-03-31",
  "2026-04-30",
  "2026-05-31",
  "2026-06-30",
  "2025-06-30",
] as const;

const BOND_DAILY_DATES = ["2026-06-29", "2026-05-30", "2026-04-29"] as const;

type BondEvidenceSnapshot = {
  faceYi: number;
  marketYi: number;
  duration: number;
  dv01Wan: number;
  positions: number;
};

const BOND_EVIDENCE_SNAPSHOTS: Record<
  "OCI" | "TPL",
  Record<string, BondEvidenceSnapshot>
> = {
  OCI: {
    "2025-06-30": { faceYi: 900, marketYi: 920, duration: 3.1, dv01Wan: 3_000, positions: 500 },
    "2026-01-31": { faceYi: 950, marketYi: 960, duration: 3, dv01Wan: 3_000, positions: 520 },
    "2026-02-28": { faceYi: 960, marketYi: 970, duration: 3.1, dv01Wan: 3_100, positions: 530 },
    "2026-03-31": { faceYi: 970, marketYi: 980, duration: 3.2, dv01Wan: 3_200, positions: 540 },
    "2026-04-30": { faceYi: 980, marketYi: 995, duration: 3.3, dv01Wan: 3_300, positions: 550 },
    "2026-05-31": { faceYi: 1_000, marketYi: 1_010, duration: 3.4, dv01Wan: 3_400, positions: 560 },
    "2026-06-30": {
      faceYi: 1_024.157080168109,
      marketYi: 1_042.7175064967316,
      duration: 3.4402454024836793,
      dv01Wan: 3_523.351686667407,
      positions: 570,
    },
  },
  TPL: {
    "2025-06-30": { faceYi: 800, marketYi: 805, duration: 0.65, dv01Wan: 550, positions: 280 },
    "2026-01-31": { faceYi: 790, marketYi: 795, duration: 0.6, dv01Wan: 500, positions: 270 },
    "2026-02-28": { faceYi: 800, marketYi: 805, duration: 0.62, dv01Wan: 520, positions: 275 },
    "2026-03-31": { faceYi: 810, marketYi: 815, duration: 0.65, dv01Wan: 540, positions: 280 },
    "2026-04-30": { faceYi: 830, marketYi: 835, duration: 0.68, dv01Wan: 570, positions: 290 },
    "2026-05-31": { faceYi: 850, marketYi: 852, duration: 0.7, dv01Wan: 600, positions: 300 },
    "2026-06-30": {
      faceYi: 876.3657975151494,
      marketYi: 878.1892778028958,
      duration: 0.7429124269979362,
      dv01Wan: 651.063041665647,
      positions: 305,
    },
  },
};

function bondAnalyticsDatesEnvelope(): ApiEnvelope<BondAnalyticsDatesPayload> {
  return envelopeWithMeta(
    "bond_analytics.dates",
    {
      report_dates: [
        "2026-06-30",
        BOND_DAILY_DATES[0],
        "2026-05-31",
        BOND_DAILY_DATES[1],
        "2026-04-30",
        BOND_DAILY_DATES[2],
        "2026-03-31",
        "2026-02-28",
        "2026-01-31",
        "2025-06-30",
      ],
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
    },
  );
}

function bondDv01EvidenceEnvelope(
  accountingClass: "OCI" | "TPL",
  reportDate = "2026-06-30",
): ApiEnvelope<DV01RiskPayload> {
  const snapshot = BOND_EVIDENCE_SNAPSHOTS[accountingClass][reportDate];
  if (!snapshot) {
    throw new Error("unexpected bond snapshot " + accountingClass + " " + reportDate);
  }
  return envelopeWithMeta(
    "bond_analytics.dv01_risk",
    {
      report_date: reportDate,
      accounting_class: accountingClass,
      dv01_basis: "face_value_modified_duration",
      scenario_pnl_basis: "face_value_dv01_linear",
      total_face_value: n(snapshot.faceYi * 100_000_000, "yuan"),
      total_market_value: n(snapshot.marketYi * 100_000_000, "yuan"),
      face_weighted_modified_duration: n(snapshot.duration, "ratio"),
      total_dv01: n(snapshot.dv01Wan * 10_000, "dv01"),
      position_count: snapshot.positions,
      shock_scenarios: [],
      tenor_buckets: [],
      top_bonds: [],
      top_issuers: [],
      warnings: [],
      computed_at: "2026-07-01T00:00:00Z",
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      requested_report_date: reportDate,
      resolved_report_date: reportDate,
      as_of_date: reportDate,
      fallback_date: null,
      source_version: "sv_a583ab603b92",
      rule_version: "rv_bond_analytics_formal_materialize_v1",
    },
  );
}

function unsortedMarketSeriesEnvelope(
  resultKind: string,
  dates: readonly string[],
): ApiEnvelope<ChoiceMacroLatestPayload> {
  return {
    result_meta: testMeta(resultKind),
    result: {
      read_target: "duckdb",
      series: dates.map((tradeDate, index) => ({
        series_id: `${resultKind}.${index}`,
        series_name: `Series ${index + 1}`,
        trade_date: tradeDate,
        value_numeric: 1 + index,
        unit: "%",
        source_version: "sv_test",
        vendor_version: "vv_test",
        latest_change: 0,
        recent_points: [],
      })),
    },
  };
}

describe("ModuleWorkbenchHomePage", () => {
  it.each([
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

  it("renders the dedicated risk overview page for /risk-overview", async () => {
    renderAt("/risk-overview");

    const page = await screen.findByTestId("risk-overview-page", {}, { timeout: 10000 });
    expect(page).toHaveTextContent("MOSS 利率风险总览");
    await waitFor(() => {
      expect(within(page).getByTestId("risk-overview-kpi-strip")).toBeInTheDocument();
      expect(within(page).getByTestId("risk-overview-status-strip")).toBeInTheDocument();
      expect(within(page).getByTestId("risk-overview-briefings")).toBeInTheDocument();
      expect(within(page).getByTestId("risk-overview-drilldowns")).toBeInTheDocument();
      expect(within(page).getByTestId("risk-overview-data-note")).toBeInTheDocument();
    });
  });

  it("opens the review copilot drawer with the risk-overview page context", { timeout: 45_000 }, async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getRiskTensorDates: async () => {
        const envelope = await base.getRiskTensorDates();
        return {
          ...envelope,
          result: {
            report_dates: ["2026-06-30"],
            blocked_report_dates: [],
          },
        };
      },
    };

    renderAt("/risk-overview", client);

    const page = await screen.findByTestId("risk-overview-page", {}, { timeout: 10000 });
    await within(page).findByTestId("risk-overview-decision");
    await waitFor(() => {
      expect(page).toHaveTextContent("报告日 2026-06-30");
    });

    await user.click(within(page).getByTestId("risk-overview-agent-open"));

    expect(
      await screen.findByTestId("risk-overview-agent-drawer", undefined, { timeout: 30_000 }),
    ).toBeInTheDocument();

    const contextCode = await screen.findByTestId("agent-panel-page-context", undefined, {
      timeout: 10_000,
    });
    const pageContext = JSON.parse(contextCode.textContent ?? "{}") as {
      page_id: string;
      current_filters: Record<string, unknown>;
      selected_rows: unknown[];
      context_note: string | null;
    };

    expect(pageContext.page_id).toBe("risk-overview");
    expect(pageContext.current_filters.report_date).toBe("2026-06-30");
    expect(pageContext.current_filters.kind).toBe("risk");
    expect(pageContext.current_filters.shock_bps).toBe("1");
    expect(pageContext.current_filters.top_n).toBe(1);
    expect(pageContext.current_filters.accounting_classes).toEqual(["OCI", "TPL"]);
    expect(pageContext.selected_rows).toEqual([]);
    expect(pageContext.context_note).toContain("利率风险总览");
  });

  it("renders OCI and TPL current values, exact-month comparisons, and six-month trends", async () => {
    const base = createApiClient({ mode: "mock" });
    const getBondAnalyticsDv01Risk = vi.fn(
      async (
        reportDate: string,
        options?: { accountingClass?: string; topN?: number; shockBps?: string },
      ) => {
        const accountingClass = options?.accountingClass;
        if (accountingClass !== "OCI" && accountingClass !== "TPL") {
          throw new Error("unexpected accounting class");
        }
        return bondDv01EvidenceEnvelope(accountingClass, reportDate);
      },
    );
    const client: ApiClient = {
      ...base,
      getRiskTensorDates: async () => {
        const envelope = await base.getRiskTensorDates();
        return {
          ...envelope,
          result: {
            report_dates: ["2026-06-30"],
            blocked_report_dates: [],
          },
        };
      },
      getBondAnalyticsDates: async () => bondAnalyticsDatesEnvelope(),
      getBondAnalyticsDv01Risk,
    };

    renderAt("/risk-overview", client);

    const page = await screen.findByTestId("risk-overview-page");
    const evidence = await within(page).findByTestId("risk-overview-bond-evidence");
    const ociCard = within(evidence).getByTestId("risk-overview-bond-oci");
    const tplCard = within(evidence).getByTestId("risk-overview-bond-tpl");

    expect(evidence).toHaveAttribute("data-manual-comparison", "blocked");
    expect(evidence).toHaveTextContent("债券分析正式口径");
    expect(evidence).toHaveTextContent(
      "与上方 Risk Tensor 正式风险结论分开展示；本区只反映系统债券分析口径。",
    );
    expect(evidence).toHaveTextContent(
      "不可直接比较：金额列定义不同，TPL 还缺分账簿与市值型基金正式源。",
    );
    expect(evidence).toHaveTextContent(
      "以下数值、环比、同比和趋势仅代表系统正式债券分析口径，不替代 630 手工小计或监管 DV01。",
    );
    expect(within(evidence).getByRole("link", { name: /查看债券分析明细/ })).toHaveAttribute(
      "href",
      "/bond-analysis",
    );
    await waitFor(() => {
      expect(ociCard).toHaveTextContent("OCI 债券（系统正式口径）");
      expect(ociCard).toHaveTextContent("总面值（DV01 基数）");
      expect(ociCard).toHaveTextContent("公允价值（不含应计）");
      expect(ociCard).toHaveTextContent("正式 DV01（面值基数）");
      expect(ociCard).toHaveTextContent("1,024.16 亿元");
      expect(ociCard).toHaveTextContent("1,042.72 亿元");
      expect(ociCard).toHaveTextContent("3.44 年");
      expect(ociCard).toHaveTextContent("3,523.35 万元/bp");
      expect(ociCard).toHaveTextContent("570 只");
      expect(tplCard).toHaveTextContent("TPL 债券（系统全量口径）");
      expect(tplCard).toHaveTextContent("876.37 亿元");
      expect(tplCard).toHaveTextContent("878.19 亿元");
      expect(tplCard).toHaveTextContent("0.74 年");
      expect(tplCard).toHaveTextContent("651.06 万元/bp");
      expect(tplCard).toHaveTextContent("305 只");
      expect(ociCard).toHaveTextContent("不按手工同名列直接比较");
      expect(tplCard).toHaveTextContent("不可用本卡替代 630 小计");
    });

    const basisText =
      "系统口径快照比较：环比 2026-05-31；同比 2025-06-30；趋势为近 6 个精确自然月末。缺失日期不以邻近日期替代。";
    expect(ociCard).toHaveTextContent(basisText);
    expect(tplCard).toHaveTextContent(basisText);
    const comparisonStatus = within(evidence).getByTestId(
      "risk-overview-bond-comparison-status",
    );
    expect(comparisonStatus).toHaveAttribute("data-state", "review");
    expect(comparisonStatus).toHaveTextContent(basisText);

    const expectComparison = (
      classKey: "oci" | "tpl",
      metricKey: string,
      period: "mom" | "yoy",
      absoluteText: string,
      percentText: string,
    ) => {
      const readout = within(evidence).getByTestId(
        "risk-overview-bond-" + classKey + "-" + metricKey + "-" + period,
      );
      expect(readout).toHaveAttribute("data-state", "review");
      expect(readout).toHaveTextContent(period === "mom" ? "系统环比" : "系统同比");
      expect(readout).toHaveTextContent(absoluteText);
      expect(readout).toHaveTextContent(percentText);
    };

    expectComparison("oci", "total-face-value", "mom", "+24.16 亿元", "+2.42%");
    expectComparison("oci", "total-face-value", "yoy", "+124.16 亿元", "+13.80%");
    expectComparison("oci", "total-market-value", "mom", "+32.72 亿元", "+3.24%");
    expectComparison("oci", "total-market-value", "yoy", "+122.72 亿元", "+13.34%");
    expectComparison("oci", "modified-duration", "mom", "+0.04 年", "—");
    expectComparison("oci", "modified-duration", "yoy", "+0.34 年", "—");
    expectComparison("oci", "total-dv01", "mom", "+123.35 万元/bp", "+3.63%");
    expectComparison("oci", "total-dv01", "yoy", "+523.35 万元/bp", "+17.45%");
    expectComparison("oci", "position-count", "mom", "+10 只", "+1.79%");
    expectComparison("oci", "position-count", "yoy", "+70 只", "+14.00%");

    expectComparison("tpl", "total-face-value", "mom", "+26.37 亿元", "+3.10%");
    expectComparison("tpl", "total-face-value", "yoy", "+76.37 亿元", "+9.55%");
    expectComparison("tpl", "total-market-value", "mom", "+26.19 亿元", "+3.07%");
    expectComparison("tpl", "total-market-value", "yoy", "+73.19 亿元", "+9.09%");
    expectComparison("tpl", "modified-duration", "mom", "+0.04 年", "—");
    expectComparison("tpl", "modified-duration", "yoy", "+0.09 年", "—");
    expectComparison("tpl", "total-dv01", "mom", "+51.06 万元/bp", "+8.51%");
    expectComparison("tpl", "total-dv01", "yoy", "+101.06 万元/bp", "+18.38%");
    expectComparison("tpl", "position-count", "mom", "+5 只", "+1.67%");
    expectComparison("tpl", "position-count", "yoy", "+25 只", "+8.93%");

    const ociTrend = within(evidence).getByTestId("risk-overview-bond-oci-dv01-trend");
    const tplTrend = within(evidence).getByTestId("risk-overview-bond-tpl-dv01-trend");
    for (const trend of [ociTrend, tplTrend]) {
      expect(trend).toHaveAttribute("data-state", "review");
      expect(trend).toHaveAttribute("data-point-count", "6");
      expect(trend).toHaveAttribute("data-expected-points", "6");
      expect(trend).toHaveAttribute("data-segment-count", "1");
      expect(trend).toHaveTextContent("系统口径 · 近 6 个报告月 DV01 趋势");
      expect(trend).toHaveTextContent("2026-01-31 → 2026-06-30");
      expect(trend).toHaveTextContent("6/6 点");
      expect(trend).toHaveTextContent("期初 → 本期");
      expect(within(trend).getByRole("img")).toBeInTheDocument();
    }
    expect(
      within(ociTrend).getByTestId("risk-overview-bond-oci-dv01-trend-plot"),
    ).toBeInTheDocument();
    expect(
      within(tplTrend).getByTestId("risk-overview-bond-tpl-dv01-trend-plot"),
    ).toBeInTheDocument();
    expect(ociTrend).toHaveTextContent("3,000.00 → 3,523.35 万元/bp");
    expect(tplTrend).toHaveTextContent("500.00 → 651.06 万元/bp");

    await waitFor(() => {
      expect(getBondAnalyticsDv01Risk).toHaveBeenCalledTimes(14);
    });
    const requestKeys = getBondAnalyticsDv01Risk.mock.calls.map(
      ([reportDate, options]) => options?.accountingClass + ":" + reportDate,
    );
    const exactRequestKeys = BOND_EXACT_MONTH_ENDS.flatMap((reportDate) => [
      "OCI:" + reportDate,
      "TPL:" + reportDate,
    ]);
    expect(new Set(requestKeys)).toEqual(new Set(exactRequestKeys));
    for (const dailyDate of BOND_DAILY_DATES) {
      expect(getBondAnalyticsDv01Risk.mock.calls.some(([reportDate]) => reportDate === dailyDate))
        .toBe(false);
    }
    expect(
      getBondAnalyticsDv01Risk.mock.calls.every(
        ([, options]) => options?.topN === 1 && options.shockBps === "1",
      ),
    ).toBe(true);
    expect(getBondAnalyticsDv01Risk).toHaveBeenCalledWith("2026-06-30", {
      accountingClass: "OCI",
      topN: 1,
      shockBps: "1",
    });
    expect(getBondAnalyticsDv01Risk).toHaveBeenCalledWith("2026-06-30", {
      accountingClass: "TPL",
      topN: 1,
      shockBps: "1",
    });
  });

  it("keeps an OCI current fallback visible while disabling only OCI comparisons and trend", async () => {
    const base = createApiClient({ mode: "mock" });
    const getBondAnalyticsDv01Risk = vi.fn(
      async (
        reportDate: string,
        options?: { accountingClass?: string; topN?: number; shockBps?: string },
      ): Promise<ApiEnvelope<DV01RiskPayload>> => {
        const accountingClass = options?.accountingClass;
        if (accountingClass !== "OCI" && accountingClass !== "TPL") {
          throw new Error("unexpected accounting class");
        }
        const snapshot = bondDv01EvidenceEnvelope(accountingClass, reportDate);
        if (accountingClass !== "OCI" || reportDate !== "2026-06-30") {
          return snapshot;
        }
        return {
          ...snapshot,
          result_meta: {
            ...snapshot.result_meta,
            fallback_mode: "latest_snapshot",
            fallback_date: "2026-06-29",
            requested_report_date: "2026-06-30",
            resolved_report_date: "2026-06-29",
            as_of_date: "2026-06-29",
          },
          result: {
            ...snapshot.result,
            report_date: "2026-06-29",
          },
        };
      },
    );
    const client: ApiClient = {
      ...base,
      getRiskTensorDates: async () => {
        const envelope = await base.getRiskTensorDates();
        return {
          ...envelope,
          result: {
            report_dates: ["2026-06-30"],
            blocked_report_dates: [],
          },
        };
      },
      getBondAnalyticsDates: async () => bondAnalyticsDatesEnvelope(),
      getBondAnalyticsDv01Risk,
    };

    renderAt("/risk-overview", client);

    const page = await screen.findByTestId("risk-overview-page");
    const evidence = await within(page).findByTestId("risk-overview-bond-evidence");
    const ociCard = within(evidence).getByTestId("risk-overview-bond-oci");
    const tplCard = within(evidence).getByTestId("risk-overview-bond-tpl");
    const comparisonStatus = within(evidence).getByTestId(
      "risk-overview-bond-comparison-status",
    );

    await waitFor(() => {
      expect(comparisonStatus).toHaveAttribute("data-state", "review");
      expect(comparisonStatus).not.toHaveAttribute("data-state", "ready");
      expect(comparisonStatus).toHaveTextContent(
        /OCI 当前快照为回退或日期与请求月末不一致；OCI 系统环比、系统同比和趋势已禁用，TPL 仍可使用系统比较与趋势。/,
      );
      expect(
        within(evidence).getByTestId("risk-overview-bond-tpl-total-dv01-mom"),
      ).toHaveAttribute("data-state", "review");
    });

    expect(ociCard).toHaveTextContent("OCI 债券");
    expect(ociCard).toHaveTextContent("1,024.16 亿元");
    expect(ociCard).toHaveTextContent("1,042.72 亿元");
    expect(ociCard).toHaveTextContent("3.44 年");
    expect(ociCard).toHaveTextContent("3,523.35 万元/bp");
    expect(ociCard).toHaveTextContent("570 只");
    expect(ociCard).toHaveTextContent("待复核");
    expect(ociCard).toHaveTextContent(/报告日\s*2026-06-29/);
    expect(ociCard).toHaveTextContent(
      "使用回退快照（2026-06-29），结论待复核。",
    );
    expect(ociCard).toHaveTextContent(
      "解析报告日 2026-06-29 与请求报告日不一致，系统口径快照比较已禁用。",
    );
    expect(ociCard).toHaveTextContent(
      "系统口径快照比较未启用：当前快照为回退或日期与请求月末不一致。",
    );

    const metricKeys = [
      "total-face-value",
      "total-market-value",
      "modified-duration",
      "total-dv01",
      "position-count",
    ];
    for (const metricKey of metricKeys) {
      for (const period of ["mom", "yoy"]) {
        const ociReadout = within(evidence).getByTestId(
          "risk-overview-bond-oci-" + metricKey + "-" + period,
        );
        expect(ociReadout).toHaveAttribute("data-state", "unavailable");
        expect(ociReadout).toHaveTextContent("基期不可用");

        const tplReadout = within(evidence).getByTestId(
          "risk-overview-bond-tpl-" + metricKey + "-" + period,
        );
        expect(tplReadout).toHaveAttribute("data-state", "review");
      }
    }

    const ociTrend = within(evidence).getByTestId("risk-overview-bond-oci-dv01-trend");
    expect(ociTrend).toHaveAttribute("data-state", "unavailable");
    expect(ociTrend).toHaveAttribute("data-point-count", "0");
    expect(ociTrend).toHaveAttribute("data-expected-points", "6");
    expect(ociTrend).toHaveAttribute("data-segment-count", "0");
    expect(ociTrend).toHaveTextContent("系统口径近 6 个报告月趋势待接入。");
    expect(
      within(ociTrend).queryByTestId("risk-overview-bond-oci-dv01-trend-plot"),
    ).not.toBeInTheDocument();

    expect(tplCard).toHaveTextContent("TPL 债券（系统全量口径）");
    expect(tplCard).toHaveTextContent("待复核");
    expect(tplCard).toHaveTextContent("不可用本卡替代 630 小计");
    expect(tplCard).toHaveTextContent(/报告日\s*2026-06-30/);
    expect(
      within(evidence).getByTestId("risk-overview-bond-tpl-total-dv01-mom"),
    ).toHaveTextContent("+51.06 万元/bp");
    expect(
      within(evidence).getByTestId("risk-overview-bond-tpl-total-dv01-yoy"),
    ).toHaveTextContent("+101.06 万元/bp");
    const tplTrend = within(evidence).getByTestId("risk-overview-bond-tpl-dv01-trend");
    expect(tplTrend).toHaveAttribute("data-state", "review");
    expect(tplTrend).toHaveAttribute("data-point-count", "6");
    expect(tplTrend).toHaveAttribute("data-segment-count", "1");
    expect(
      within(tplTrend).getByTestId("risk-overview-bond-tpl-dv01-trend-plot"),
    ).toBeInTheDocument();
  });

  it("keeps both current cards and the OCI trend when one TPL history point fails", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getRiskTensorDates: async () => {
        const envelope = await base.getRiskTensorDates();
        return {
          ...envelope,
          result: {
            report_dates: ["2026-06-30"],
            blocked_report_dates: [],
          },
        };
      },
      getBondAnalyticsDates: async () => bondAnalyticsDatesEnvelope(),
      getBondAnalyticsDv01Risk: vi.fn(async (reportDate, options) => {
        const accountingClass = options?.accountingClass;
        if (accountingClass !== "OCI" && accountingClass !== "TPL") {
          throw new Error("unexpected accounting class");
        }
        if (accountingClass === "TPL" && reportDate === "2026-03-31") {
          throw new Error("tpl history unavailable");
        }
        return bondDv01EvidenceEnvelope(accountingClass, reportDate);
      }),
    };

    renderAt("/risk-overview", client);

    const page = await screen.findByTestId("risk-overview-page");
    const evidence = await within(page).findByTestId("risk-overview-bond-evidence");
    const ociCard = within(evidence).getByTestId("risk-overview-bond-oci");
    const tplCard = within(evidence).getByTestId("risk-overview-bond-tpl");
    await waitFor(() => {
      expect(ociCard).toHaveTextContent("OCI 债券（系统正式口径）");
      expect(ociCard).toHaveTextContent("3,523.35 万元/bp");
      expect(ociCard).toHaveTextContent("待复核");
      expect(tplCard).toHaveTextContent("TPL 债券（系统全量口径）");
      expect(tplCard).toHaveTextContent("651.06 万元/bp");
      expect(tplCard).toHaveTextContent("待复核");
      expect(tplCard).toHaveTextContent(
        "2026-03-31：历史月末快照读取失败：tpl history unavailable",
      );
    });
    const ociTrend = within(evidence).getByTestId("risk-overview-bond-oci-dv01-trend");
    expect(ociTrend).toHaveAttribute("data-state", "review");
    expect(ociTrend).toHaveAttribute("data-point-count", "6");
    expect(ociTrend).toHaveAttribute("data-expected-points", "6");
    expect(ociTrend).toHaveAttribute("data-segment-count", "1");
    expect(ociTrend).toHaveTextContent("6/6 点");
    expect(within(ociTrend).getByRole("img")).toBeInTheDocument();

    const tplTrend = within(evidence).getByTestId("risk-overview-bond-tpl-dv01-trend");
    expect(tplTrend).toHaveAttribute("data-state", "review");
    expect(tplTrend).toHaveAttribute("data-point-count", "5");
    expect(tplTrend).toHaveAttribute("data-expected-points", "6");
    expect(tplTrend).toHaveAttribute("data-segment-count", "2");
    expect(tplTrend).toHaveTextContent("5/6 点");
    expect(tplTrend).toHaveTextContent("首个有效点 → 最近有效点");
    expect(tplTrend).toHaveTextContent("500.00 → 651.06 万元/bp");
    expect(tplTrend).toHaveTextContent(
      "2026-03-31：历史月末快照读取失败：tpl history unavailable",
    );
    expect(
      within(tplTrend).getByTestId("risk-overview-bond-tpl-dv01-trend-plot"),
    ).toBeInTheDocument();
    const tplSegments = within(tplTrend).getAllByTestId(
      /risk-overview-bond-tpl-dv01-trend-segment-/,
    );
    expect(tplSegments).toHaveLength(2);
    expect(tplSegments[0]).toHaveAttribute("data-segment-index", "0");
    expect(tplSegments[1]).toHaveAttribute("data-segment-index", "1");
    const tplPoints = within(tplTrend).getAllByTestId(
      /risk-overview-bond-tpl-dv01-trend-point-/,
    );
    expect(tplPoints).toHaveLength(5);
    expect(tplPoints.map((point) => point.getAttribute("data-slot-index"))).toEqual([
      "0",
      "1",
      "3",
      "4",
      "5",
    ]);
    expect(tplPoints.map((point) => point.getAttribute("data-report-date"))).toEqual([
      "2026-01-31",
      "2026-02-28",
      "2026-04-30",
      "2026-05-31",
      "2026-06-30",
    ]);
    expect(
      within(tplTrend).queryByTestId("risk-overview-bond-tpl-dv01-trend-point-2"),
    ).not.toBeInTheDocument();
    expect(
      within(tplTrend).queryByTestId("risk-overview-bond-tpl-dv01-trend-segment-2"),
    ).not.toBeInTheDocument();
    expect(
      within(evidence).getByTestId("risk-overview-bond-tpl-total-dv01-mom"),
    ).toHaveTextContent("+51.06 万元/bp");
    expect(
      within(evidence).getByTestId("risk-overview-bond-oci-total-dv01-yoy"),
    ).toHaveTextContent("+523.35 万元/bp");
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

    const page = await screen.findByTestId("risk-overview-page");
    await waitFor(() => {
      expect(page).toHaveTextContent("读取失败");
      expect(page).toHaveTextContent("不使用前端补数");
    });
  });

  it("renders risk tensor and cashflow detail cards from backend reads", async () => {
    renderAt("/risk-overview");

    const page = await screen.findByTestId("risk-overview-page");
    expect(within(page).getByTestId("risk-overview-decision")).toHaveTextContent("风险处置判断");
    await waitFor(() => {
      expect(within(page).getByTestId("risk-overview-evidence")).toBeInTheDocument();
      expect(within(page).getByTestId("risk-overview-krd-panel")).toBeInTheDocument();
      expect(within(page).getByTestId("risk-overview-cashflow-panel")).toBeInTheDocument();
      expect(
        within(page).getByTestId("risk-overview-table-portfolio-duration"),
      ).toBeInTheDocument();
      expect(
        within(page).getByTestId("risk-overview-table-credit-concentration"),
      ).toBeInTheDocument();
      expect(within(page).getByTestId("risk-overview-briefings")).toBeInTheDocument();
      expect(page).toHaveTextContent("监管 DV01");
      expect(page).toHaveTextContent("监管口径 DV01");
      expect(page).toHaveTextContent("利率风险口径 DV01");
      expect(page).toHaveTextContent("久期缺口");
      expect(page).toHaveTextContent("KRD 分布");
    });
    expect(within(page).getByTestId("risk-overview-lineage")).toHaveTextContent(
      "sv_risk_tensor_fact_mock_v3",
    );
    expect(within(page).getByTestId("risk-overview-lineage")).toHaveTextContent(
      "rv_risk_tensor_formal_materialize_v5",
    );
  });

  it("surfaces liquidity and cashflow evidence already returned by the risk reads", async () => {
    renderAt("/risk-overview");

    const page = await screen.findByTestId("risk-overview-page");
    const evidenceBoard = await within(page).findByTestId("risk-overview-evidence");

    await waitFor(() => {
      expect(evidenceBoard).toHaveTextContent("现金流窗口");
      expect(evidenceBoard).toHaveTextContent("资产流入");
      expect(evidenceBoard).toHaveTextContent("负债流出");
      expect(evidenceBoard).toHaveTextContent("30D 净缺口");
      expect(evidenceBoard).toHaveTextContent("久期缺口");
      expect(evidenceBoard).toHaveTextContent("12M 再投资风险");
    });
  });

  it("balances risk evidence panels across the detail grid", async () => {
    renderAt("/risk-overview");

    const page = await screen.findByTestId("risk-overview-page");
    await waitFor(() => {
      expect(page).toHaveTextContent("利率风险口径 DV01");
    });

    const krdPanel = within(page).getByTestId("risk-overview-krd-panel");
    const cashflowPanel = within(page).getByTestId("risk-overview-cashflow-panel");
    const portfolioTable = within(page).getByTestId("risk-overview-table-portfolio-duration");
    const creditTable = within(page).getByTestId("risk-overview-table-credit-concentration");

    expect(within(krdPanel).getByText("10Y")).toBeInTheDocument();
    expect(within(portfolioTable).getByText("监管口径 DV01")).toBeInTheDocument();
    expect(within(portfolioTable).getByText("久期剔除项")).toBeInTheDocument();
    expect(within(creditTable).getByText("发行人集中度 HHI")).toBeInTheDocument();
    expect(within(cashflowPanel).getByText("30D 净缺口")).toBeInTheDocument();
    expect(within(cashflowPanel).queryByText("监管口径 DV01")).not.toBeInTheDocument();
  });

  it("lays out risk overview as a compact review desk", async () => {
    renderAt("/risk-overview");

    const page = await screen.findByTestId("risk-overview-page");
    const decision = within(page).getByTestId("risk-overview-decision");
    expect(decision).toHaveTextContent("风险处置判断");

    const statusStrip = within(page).getByTestId("risk-overview-status-strip");
    await waitFor(() => {
      expect(statusStrip).toHaveTextContent("风险张量");
      expect(statusStrip).toHaveTextContent("现金流预测");
    });

    const kpiStrip = within(page).getByTestId("risk-overview-kpi-strip");
    await waitFor(() => {
      expect(kpiStrip).toHaveTextContent("监管 DV01");
      expect(kpiStrip).toHaveTextContent("估值 DV01");
      expect(decision).toHaveTextContent("报告日");
      expect(decision).toHaveTextContent("质量标记");
    });

    expect(within(page).getByTestId("risk-overview-evidence")).toHaveTextContent("风险证据板");
    expect(within(page).getByTestId("risk-overview-drilldowns")).toHaveTextContent("风险张量");
  });

  it("surfaces rule-version blocked report dates in a dedicated governance band", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getRiskTensorDates: async () => {
        const envelope = await base.getRiskTensorDates();
        return {
          ...envelope,
          result: {
            report_dates: [],
            blocked_report_dates: [
              {
                report_date: "2026-06-30",
                reason:
                  "Risk tensor stale against rule version for report_date=2026-06-30; expected rv_risk_tensor_formal_materialize_v3, got rv_risk_tensor_formal_materialize_v2. Rematerialize required.",
              },
              {
                report_date: "2026-05-31",
                reason:
                  "Risk tensor stale against rule version for report_date=2026-05-31; expected rv_risk_tensor_formal_materialize_v3, got rv_risk_tensor_formal_materialize_v2. Rematerialize required.",
              },
            ],
          },
        };
      },
    };

    renderAt("/risk-overview", client);

    const page = await screen.findByTestId("risk-overview-page");
    const band = await within(page).findByTestId("risk-overview-blocked-band");
    expect(band).toHaveTextContent("数据陈旧");
    expect(band).toHaveTextContent("2 个报告日被规则版本拦截，最新 2026-06-30");
    expect(band).toHaveTextContent("Rematerialize required");
    expect(within(band).getByRole("link", { name: /前往风险张量页/ })).toHaveAttribute(
      "href",
      "/risk-tensor",
    );

    await waitFor(() => {
      expect(within(page).getByTestId("risk-overview-decision")).toHaveTextContent(
        "2 个报告日被规则版本拦截",
      );
      expect(within(page).getByTestId("risk-overview-status-strip")).toHaveTextContent(
        "全部拦截",
      );
    });
  });

  it("hides the blocked band when every report date is usable", async () => {
    renderAt("/risk-overview");

    const page = await screen.findByTestId("risk-overview-page");
    await waitFor(() => {
      expect(page).toHaveTextContent("监管 DV01");
    });
    expect(within(page).queryByTestId("risk-overview-blocked-band")).not.toBeInTheDocument();
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

    const page = await screen.findByTestId("risk-overview-page");
    const decision = within(page).getByTestId("risk-overview-decision");
    const kpis = within(page).getByTestId("risk-overview-kpi-strip");
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

    const page = await screen.findByTestId("risk-overview-page");
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
    expect(firstScreen).toContainElement(within(page).getByTestId("module-home-kpi-strip"));
    expect(firstScreen).toContainElement(within(page).getByTestId("module-home-portfolio-risk-ticker"));
    expect(within(page).queryByTestId("module-home-portfolio-ai-rail")).not.toBeInTheDocument();
    expect(firstScreen).not.toContainElement(within(page).getByTestId("module-home-portfolio-holdings-hero"));
    expect(firstScreen).not.toContainElement(within(page).getByTestId("module-home-briefing"));
    expect(firstScreen).not.toContainElement(within(page).getByTestId("module-home-portfolio-quick-access"));
    expect(firstScreen).not.toContainElement(within(page).getByTestId("module-home-status-strip"));
    expect(within(page).getByTestId("module-home-kpi-strip")).toBeInTheDocument();
    const dataWorkbench = within(page).getByTestId("module-home-portfolio-data-workbench");
    expect(cockpit).toContainElement(dataWorkbench);
    expect(within(dataWorkbench).getByTestId("module-home-portfolio-data-nav")).toHaveTextContent("持仓结构");
    expect(within(dataWorkbench).getByTestId("module-home-portfolio-holdings-workbench")).toBeInTheDocument();
    expect(within(dataWorkbench).getByTestId("module-home-portfolio-exposure-workbench")).toBeInTheDocument();
    expect(within(dataWorkbench).getByTestId("module-home-portfolio-source-workbench")).toBeInTheDocument();
    expect(within(dataWorkbench).getByTestId("module-home-portfolio-action-workbench")).toBeInTheDocument();
    expect(cockpit).toContainElement(within(page).getByTestId("module-home-portfolio-holdings-hero"));
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

  it("renders portfolio review modules as one compact review band", async () => {
    renderAt("/portfolio", realPortfolioClient());

    const page = await screen.findByTestId("module-workbench-home");
    const reviewBand = await within(page).findByTestId("module-home-portfolio-review-band");

    await waitFor(() => {
      expect(reviewBand).toContainElement(within(page).getByTestId("module-home-decision"));
      expect(reviewBand).toContainElement(within(page).getByTestId("module-home-briefing"));
      expect(reviewBand).toContainElement(within(page).getByTestId("module-home-status-strip"));
      expect(reviewBand).toHaveClass(/portfolioReviewBand/);
      expect(reviewBand).toHaveTextContent("组合复核");
      expect(reviewBand).toHaveTextContent("风险暴露");
      expect(reviewBand).toHaveTextContent("核心读数");
      expect(reviewBand).toHaveTextContent("数据链路");
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
      expect(within(page).getByTestId("module-home-portfolio-kpi-bond-count")).toHaveTextContent("1,710");
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

  it("renders portfolio terminal kpi deltas from prev_kpis and a risk supplement strip", async () => {
    renderAt("/portfolio", realPortfolioClient());

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(within(page).getByTestId("module-home-portfolio-risk-ticker")).toBeInTheDocument();
      const kpiStrip = within(page).getByTestId("module-home-kpi-strip");
      expect(
        kpiStrip.querySelectorAll("article[data-testid^='module-home-portfolio-kpi-']").length,
      ).toBeGreaterThanOrEqual(10);
      expect(within(page).getByTestId("module-home-portfolio-kpi-bond-market-detail")).toHaveTextContent("+0.69%");
      expect(within(page).getByTestId("module-home-portfolio-ticker-risk-spread-dv01")).toHaveTextContent("万元");
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
      expect(within(page).getByTestId("module-home-portfolio-holdings-bars")).toHaveTextContent("政策性金融债");
      expect(within(page).getByTestId("module-home-portfolio-holdings-lead")).toHaveTextContent("政策性金融债");
      expect(within(page).getByTestId("module-home-portfolio-comparison-hero-table")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-portfolio-comparison-row-portfolio-固收组合")).toHaveTextContent(
        "固收组合",
      );
      expect(within(page).getByTestId("module-home-analysis-tab-portfolio-comparison")).toHaveTextContent("4");
      expect(within(page).getByTestId("module-home-analysis-tab-yield-distribution")).toHaveTextContent("5");
      expect(within(page).getByTestId("module-home-analysis-tab-spread-analysis")).toHaveTextContent("4");
      expect(within(page).getByTestId("module-home-analysis-tab-business-type-metrics")).toHaveTextContent("4");
      expect(within(page).getByTestId("module-home-structure-status-summary")).toHaveTextContent("4/4 个结构就绪");
      expect(within(page).queryByTestId("module-home-structure-gap-actions")).not.toBeInTheDocument();
      expect(within(page).getByTestId("module-home-portfolio-quick-access")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-portfolio-action-loop")).toHaveTextContent("子组合分层核验");
      expect(within(page).getByTestId("module-home-portfolio-action-loop-primary")).toHaveTextContent(
        "子组合分层核验",
      );
      expect(within(page).getByTestId("module-home-portfolio-quick-bond-dashboard")).toHaveAttribute(
        "href",
        "/bond-dashboard",
      );
      expect(within(page).getByTestId("module-home-portfolio-quick-positions")).toHaveAttribute("href", "/positions");
    });
  });

  it("renders the rating distribution summary in the compact structure overview", async () => {
    renderAt("/portfolio", realPortfolioClient());

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      const ratingPanel = within(page).getByTestId("module-home-distribution-rating");
      expect(ratingPanel).toHaveTextContent("评级分布");
      expect(ratingPanel).toHaveTextContent("来源 bond-dashboard");
      expect(ratingPanel).toHaveTextContent("AAA");
      expect(ratingPanel).toHaveTextContent("66.21%");
      expect(ratingPanel).toHaveTextContent("16.25%");
    });
  });

  it("keeps the standalone distribution view-all link styled", () => {
    const panel: ModuleHomeDistributionPanel = {
      key: "rating",
      title: "评级分布",
      meta: "来源 bond-dashboard",
      subtitle: "Top5",
      totalDisplay: "100.00 亿",
      stateLabel: "已返回",
      stateDetail: "正式数据已返回。",
      tone: "ok",
      viewAllPath: "/bond-dashboard",
      rows: [
        {
          key: "aaa",
          label: "AAA",
          marketValue: "66.21 亿元",
          share: "66.21%",
          barPct: 66.21,
          tone: "ok",
        },
      ],
    };

    render(
      <MemoryRouter>
        <PortfolioDistributionPanel panel={panel} />
      </MemoryRouter>,
    );

    const viewAllLink = screen.getByRole("link", { name: "查看全部" });
    expect(viewAllLink).toHaveAttribute("href", "/bond-dashboard");
    expect(viewAllLink.getAttribute("class")).toContain("distViewAll");
  });

  it("fails closed when holdings structure returns no asset type rows", async () => {
    const summary = realPortfolioHomeSummary();
    const summaryWithEmptyAssetType: BondDashboardHomeSummaryPayload = {
      ...summary,
      asset_type: {
        ...summary.asset_type,
        items: [],
      },
    };

    renderAt(
      "/portfolio",
      realPortfolioClient({
        getBondDashboardHomeSummary: async () => ({
          ...envelopeWithMeta("bond_dashboard.home_summary", summaryWithEmptyAssetType, {
            basis: "formal",
            formal_use_allowed: true,
            quality_flag: "ok",
          }),
          data_source: "bond_analytics_facts",
        }),
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    const hero = within(page).getByTestId("module-home-portfolio-holdings-hero");
    await waitFor(() => {
      expect(hero).toHaveAttribute("data-tone", "watch");
      expect(hero).toHaveTextContent("券种分布明细为空");
      expect(hero).toHaveTextContent("复核源表过滤条件");
      expect(within(hero).queryByTestId("module-home-portfolio-holdings-row-政策性金融债")).not.toBeInTheDocument();
      expect(within(hero).queryByTestId("module-home-portfolio-holdings-bars")).not.toBeInTheDocument();
      expect(within(hero).getByTestId("module-home-portfolio-comparison-hero-table")).toHaveTextContent("固收组合");
    });
  });

  it("keeps zero-market-value portfolio comparison rows visible for review", async () => {
    const summary = realPortfolioHomeSummary();
    const summaryWithZeroPortfolio: BondDashboardHomeSummaryPayload = {
      ...summary,
      portfolio_comparison: {
        ...summary.portfolio_comparison,
        items: [
          ...summary.portfolio_comparison.items,
          {
            portfolio_name: "ZERO_TEST",
            total_market_value: n(0, "yuan"),
            weighted_ytm: n(0, "pct", true),
            weighted_duration: n(0, "ratio"),
            total_dv01: n(0, "dv01"),
            bond_count: 0,
          },
        ],
      },
    };
    const getBondDashboardHomeSummary = vi.fn<ApiClient["getBondDashboardHomeSummary"]>(async () => ({
      ...envelopeWithMeta("bond_dashboard.home_summary", summaryWithZeroPortfolio, {
        basis: "formal",
        formal_use_allowed: true,
        quality_flag: "ok",
      }),
      data_source: "bond_analytics_facts",
    }));
    const getBondDashboardPortfolioComparison = vi.fn<ApiClient["getBondDashboardPortfolioComparison"]>();

    renderAt(
      "/portfolio",
      realPortfolioClient({
        getBondDashboardHomeSummary,
        getBondDashboardPortfolioComparison,
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(getBondDashboardHomeSummary).toHaveBeenCalledWith("2026-05-31");
      const zeroRow = within(page).getByTestId("module-home-portfolio-comparison-row-portfolio-ZERO_TEST");
      expect(zeroRow).toHaveTextContent("ZERO_TEST");
      expect(zeroRow).toHaveTextContent("0.00 亿");
      expect(zeroRow).toHaveTextContent("0.00 年");
      expect(zeroRow).toHaveTextContent("0.00%");
      expect(zeroRow).toHaveTextContent("0.00 万");
      expect(zeroRow).toHaveTextContent("0");
      expect(zeroRow).not.toHaveTextContent("—");
    });
    expect(getBondDashboardPortfolioComparison).not.toHaveBeenCalled();
  });

  it("labels unnamed portfolio comparison rows instead of rendering blank groups", async () => {
    const summary = realPortfolioHomeSummary();
    const summaryWithUnnamedPortfolio: BondDashboardHomeSummaryPayload = {
      ...summary,
      portfolio_comparison: {
        ...summary.portfolio_comparison,
        items: [
          {
            portfolio_name: "   ",
            total_market_value: n(96_000, "yuan"),
            weighted_ytm: n(0.021, "pct", true),
            weighted_duration: n(0.18, "ratio"),
            total_dv01: n(9_600, "dv01"),
            bond_count: 1,
          },
          ...summary.portfolio_comparison.items,
        ],
      },
    };

    renderAt(
      "/portfolio",
      realPortfolioClient({
        getBondDashboardHomeSummary: async () => ({
          ...envelopeWithMeta("bond_dashboard.home_summary", summaryWithUnnamedPortfolio, {
            basis: "formal",
            formal_use_allowed: true,
            quality_flag: "ok",
          }),
          data_source: "bond_analytics_facts",
        }),
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(
        within(page).getByTestId("module-home-portfolio-comparison-row-portfolio-未命名组合 1"),
      ).toHaveTextContent("未命名组合 1");
    });
    const terminal = within(page).getByTestId("module-home-portfolio-terminal");
    const chartStub = within(terminal)
      .getAllByTestId("module-home-echarts-stub")
      .find((node) => node.getAttribute("data-chart-categories")?.includes("未命名组合 1"));
    expect(chartStub).toBeDefined();
    expect(chartStub).toHaveAttribute("data-chart-categories", expect.stringContaining("未命名组合 1"));
  });

  it("fails closed when portfolio comparison returns no sub-portfolios", async () => {
    const summary = realPortfolioHomeSummary();
    const summaryWithEmptyPortfolioComparison: BondDashboardHomeSummaryPayload = {
      ...summary,
      portfolio_comparison: {
        ...summary.portfolio_comparison,
        items: [],
      },
    };

    renderAt(
      "/portfolio",
      realPortfolioClient({
        getBondDashboardHomeSummary: async () => ({
          ...envelopeWithMeta("bond_dashboard.home_summary", summaryWithEmptyPortfolioComparison, {
            basis: "formal",
            formal_use_allowed: true,
            quality_flag: "ok",
          }),
          data_source: "bond_analytics_facts",
        }),
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(page).toHaveTextContent("子组合对比为空");
      expect(within(page).queryByTestId("module-home-portfolio-comparison-hero-table")).not.toBeInTheDocument();
      expect(within(page).getByTestId("module-home-decision")).toHaveTextContent("子组合对比未返回，先确认组合分层读链路");
      expect(within(page).getByTestId("module-home-portfolio-action-loop-primary")).toHaveTextContent(
        "子组合分层核验",
      );
      expect(within(page).getByTestId("module-home-analysis-tab-portfolio-comparison")).toHaveTextContent("空");
      expect(within(page).getByTestId("module-home-structure-gap-action-portfolio-comparison")).toHaveAttribute(
        "href",
        "/bond-dashboard?report_date=2026-05-31#portfolio-comparison",
      );
      expect(within(page).queryByTestId("module-home-business-review-row-子组合分层核验")).not.toBeInTheDocument();
      expect(within(page).queryByTestId("module-home-business-review-row-子组合返回为空")).not.toBeInTheDocument();
      expect(within(page).queryByTestId("module-home-business-review-row-business-use")).not.toBeInTheDocument();
    });
  });

  it("fails closed when yield distribution returns no buckets", async () => {
    const summary = realPortfolioHomeSummary();
    const summaryWithEmptyYieldDistribution: BondDashboardHomeSummaryPayload = {
      ...summary,
      yield_distribution: {
        ...summary.yield_distribution,
        items: [],
      },
    };
    const user = userEvent.setup();

    renderAt(
      "/portfolio",
      realPortfolioClient({
        getBondDashboardHomeSummary: async () => ({
          ...envelopeWithMeta("bond_dashboard.home_summary", summaryWithEmptyYieldDistribution, {
            basis: "formal",
            formal_use_allowed: true,
            quality_flag: "ok",
          }),
          data_source: "bond_analytics_facts",
        }),
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    const terminal = within(page).getByTestId("module-home-portfolio-terminal");
    await user.click(within(terminal).getByRole("tab", { name: /收益率/ }));

    await waitFor(() => {
      expect(within(terminal).getByTestId("module-home-structure-status-summary")).toHaveTextContent("1 个结构为空");
      expect(within(terminal).getByTestId("module-home-structure-status-summary")).toHaveTextContent("收益率");
      expect(within(terminal).getByTestId("module-home-analysis-tab-yield-distribution")).toHaveTextContent("空");
      const gapActions = within(terminal).getByTestId("module-home-structure-gap-actions");
      expect(gapActions).toHaveTextContent("收益率为空");
      expect(gapActions).toHaveTextContent("去债券总览复核");
      expect(within(gapActions).getByTestId("module-home-structure-gap-action-yield-distribution")).toHaveAttribute(
        "href",
        "/bond-dashboard?report_date=2026-05-31#yield-distribution",
      );
      expect(terminal).toHaveTextContent("收益率分布为空");
      expect(terminal).toHaveTextContent("无收益率桶明细");
      expect(terminal).toHaveTextContent("复核源表过滤条件");
      expect(terminal).not.toHaveTextContent("2%-3%");
      expect(terminal).not.toHaveTextContent("组合加权 YTM");
      expect(terminal).not.toHaveTextContent("收益率桶市值分布");
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
    const actionLoop = await within(decision).findByTestId("module-home-portfolio-action-loop");
    await waitFor(() => {
      expect(decision).toHaveTextContent("同日闭合 2026-05-31");
      expect(decision).toHaveTextContent("核心读数");
      expect(actionLoop).toHaveTextContent("子组合分层核验");
    });
    expect(within(decision).queryByRole("link", { name: /来源证据复核/ })).not.toBeInTheDocument();
    expect(within(decision).queryByRole("link", { name: /风险张量日期复核/ })).not.toBeInTheDocument();
    expect(decision).not.toHaveTextContent("来源证据复核");
    expect(decision).not.toHaveTextContent("债券总览核对");
    expect(decision).not.toHaveTextContent("收益归因复核");
  });

  it("renders portfolio evidence facts without legacy business-review rows", async () => {
    renderAt("/portfolio", realPortfolioClient());

    const page = await screen.findByTestId("module-workbench-home");
    const evidenceConsole = await within(page).findByTestId("module-home-evidence-console");

    await waitFor(() => {
      expect(evidenceConsole).toHaveTextContent("证据口径");
      expect(evidenceConsole).toHaveTextContent("来源 / 日期 / 闭合");
      expect(evidenceConsole).toHaveTextContent("证据样本");
      expect(evidenceConsole).toHaveTextContent("子组合");
    });
    expect(within(evidenceConsole).queryByTestId("module-home-evidence-loop-item-source")).not.toBeInTheDocument();
    expect(within(evidenceConsole).queryByTestId("module-home-evidence-loop-item-risk")).not.toBeInTheDocument();
    expect(within(evidenceConsole).queryByTestId("module-home-business-review-row-yield-concentration")).not.toBeInTheDocument();
    expect(within(evidenceConsole).queryByTestId("module-home-business-review-row-spread-structure")).not.toBeInTheDocument();
    expect(within(evidenceConsole).queryByTestId("module-home-business-review-row-business-type")).not.toBeInTheDocument();
    expect(within(evidenceConsole).queryByTestId("module-home-business-review-row-basis-scale")).not.toBeInTheDocument();
    expect(within(evidenceConsole).queryByTestId("module-home-business-review-row-business-use")).not.toBeInTheDocument();
    expect(within(evidenceConsole).queryByTestId("module-home-business-review-row-信用占比")).not.toBeInTheDocument();
    expect(within(evidenceConsole).queryByTestId("module-home-business-review-row-DV01")).not.toBeInTheDocument();
    expect(evidenceConsole).not.toHaveTextContent("业务用途");
    expect(evidenceConsole).not.toHaveTextContent("信用暴露处于观察区间");
    expect(evidenceConsole).not.toHaveTextContent("利率敏感度核心读数");
    expect(evidenceConsole).not.toHaveTextContent("来源证据复核");
    expect(evidenceConsole).not.toHaveTextContent("债券总览核对");
    expect(evidenceConsole).not.toHaveTextContent("收益归因复核");
    expect(evidenceConsole).not.toHaveTextContent("下钻");
    expect(evidenceConsole).not.toHaveTextContent("入口");
    expect(evidenceConsole).not.toHaveTextContent("formal_use_allowed");
    expect(evidenceConsole).not.toHaveTextContent("basis=");
    expect(evidenceConsole).not.toHaveTextContent("quality=");
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
      expect(within(page).getByTestId("module-home-portfolio-kpi-bond-count")).toHaveTextContent("1,710");
      expect(within(page).getByTestId("module-home-portfolio-kpi-scope-note")).toHaveTextContent(
        "分析/复核口径",
      );
      expect(within(page).getByTestId("module-home-portfolio-kpi-scope-note")).toHaveTextContent(
        "不形成调仓建议",
      );
      expect(within(page).getByTestId("module-home-portfolio-kpi-bond-count-detail")).toHaveAttribute(
        "title",
        expect.stringContaining("分析/复核口径"),
      );
    });
    expect(within(decision).queryByRole("link", { name: /信用结构复核/ })).not.toBeInTheDocument();
    expect(within(decision).queryByRole("link", { name: /久期 DV01 复核/ })).not.toBeInTheDocument();
  });

  it("isolates analytical risk indicators from ticker and closure semantics", async () => {
    renderAt(
      "/portfolio",
      realPortfolioClient({
        getBondDashboardRiskIndicators: async () =>
          envelopeWithMeta("bond_dashboard.risk_indicators", realPortfolioHomeSummary().risk, {
            basis: "analytical",
            formal_use_allowed: false,
            quality_flag: "warning",
            tables_used: ["fact_formal_bond_analytics_daily"],
            evidence_rows: 1710,
          }),
      }),
    );

    const page = await screen.findByTestId("module-workbench-home");
    const decision = await within(page).findByTestId("module-home-decision");
    await waitFor(() => {
      expect(decision).toHaveTextContent("风险指标 basis=analytical");
      expect(within(page).getByTestId("module-home-portfolio-kpi-bond-credit-ratio")).toHaveTextContent(
        /29\.96\s*%/,
      );
      expect(within(page).getByTestId("module-home-portfolio-kpi-scope-note")).toHaveTextContent(
        "仅展示读数",
      );
      expect(within(page).getByTestId("module-home-portfolio-kpi-bond-credit-ratio-detail")).toHaveAttribute(
        "title",
        expect.stringContaining("仅展示读数"),
      );
    });

    const ticker = within(page).getByTestId("module-home-portfolio-risk-ticker");
    expect(ticker).toHaveTextContent("风险读数不可用");
    expect(ticker).toHaveTextContent("不参与风险 ticker");
    expect(within(ticker).queryByTestId("module-home-portfolio-ticker-risk-total-dv01")).not.toBeInTheDocument();
    expect(within(ticker).queryByTestId("module-home-portfolio-ticker-risk-spread-dv01")).not.toBeInTheDocument();
    const riskPanel = within(page).getByTestId("module-home-portfolio-risk");
    expect(riskPanel).toHaveTextContent("信用占比");
    expect(riskPanel).toHaveTextContent(/29\.96\s*%/);

    const closureGate = within(page).getByTestId("module-home-portfolio-closure-gate");
    expect(closureGate).toHaveAttribute("data-state", "source-review");
    expect(closureGate).toHaveTextContent("决策口径未通过");
    expect(closureGate).toHaveTextContent("分析口径已隔离");
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
    const closureGate = within(page).getByTestId("module-home-portfolio-closure-gate");
    expect(closureGate).toHaveAttribute("data-state", "blocked");
    expect(closureGate).toHaveTextContent("风险张量不可用");
    expect(closureGate).toHaveTextContent("闭合状态已阻断");
    expect(closureGate).toHaveTextContent("风险闭合证据读取失败");
    const ticker = within(page).getByTestId("module-home-portfolio-risk-ticker");
    expect(ticker).toHaveTextContent("风险张量不可用");
    expect(ticker).toHaveTextContent("闭合状态已阻断");
    expect(within(ticker).queryByTestId("module-home-portfolio-ticker-risk-total-dv01")).not.toBeInTheDocument();
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
    const structureWorkbench = within(page).getByTestId("module-home-portfolio-structure-workbench");
    expect(within(structureWorkbench).getByTestId("module-home-portfolio-terminal")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-holdings-structure")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-portfolio-terminal")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-portfolio-risk")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-pnl-summary")).toBeInTheDocument();
    await waitFor(() => {
      expect(page).toHaveTextContent("持仓结构全景");
      expect(page).toHaveTextContent("评级分布");
      expect(page).toHaveTextContent("行业分布");
      expect(page).toHaveTextContent("期限分布");
      expect(page).toHaveTextContent("结构拆解工作台");
    });
    const hero = within(page).getByTestId("module-home-portfolio-holdings-hero");
    expect(hero).toHaveTextContent("持仓结构全景");
    const exposureWorkbench = within(page).getByTestId("module-home-portfolio-exposure-workbench");
    expect(within(exposureWorkbench).getByTestId("module-home-portfolio-exposure-ledger")).toHaveTextContent("信用占比");
    expect(exposureWorkbench).toHaveTextContent("关键暴露账本");
    expect(within(structureWorkbench).getByTestId("module-home-analysis-tab-portfolio-comparison")).toHaveTextContent("子组合");
    expect(within(structureWorkbench).getByTestId("module-home-analysis-tab-yield-distribution")).toHaveTextContent("收益率");
    expect(within(structureWorkbench).getByTestId("module-home-structure-gap-actions")).toBeInTheDocument();
    const holdings = within(page).getByTestId("module-home-holdings-structure");
    expect(within(holdings).getByTestId("module-home-distribution-rating")).toBeInTheDocument();
    expect(within(holdings).getByTestId("module-home-distribution-maturity")).toBeInTheDocument();
    expect(within(holdings).getByTestId("module-home-distribution-industry")).toBeInTheDocument();
    expect(within(holdings).queryByTestId("module-home-distribution-asset-type")).not.toBeInTheDocument();
    expect(within(page).getByTestId("module-home-briefing-ledger")).toHaveTextContent("balance-analysis");
    expect(within(page).getByTestId("module-home-status-ledger")).toHaveTextContent("暂无数据");
    expect(structureWorkbench).toHaveTextContent("结构拆解工作台");
  });

  it("renders structure tab chart beside portfolio comparison list", async () => {
    renderAt("/portfolio", realPortfolioClient());

    const page = await screen.findByTestId("module-workbench-home");
    const terminal = within(page).getByTestId("module-home-portfolio-terminal");
    await waitFor(() => {
      const structureChart = within(terminal).getByTestId("module-home-structure-chart");
      expect(structureChart).toBeInTheDocument();
      expect(terminal).toHaveTextContent("固收组合");
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

  it("renders risk closure and the action matrix inside the portfolio data workbench", async () => {
    renderAt("/portfolio", realPortfolioClient());

    const page = await screen.findByTestId("module-workbench-home");
    const dataWorkbench = await within(page).findByTestId("module-home-portfolio-data-workbench");
    const closureBand = await within(page).findByTestId("module-home-portfolio-closure-band");
    const actionWorkbench = await within(page).findByTestId("module-home-portfolio-action-workbench");

    await waitFor(() => {
      expect(dataWorkbench).toContainElement(closureBand);
      expect(dataWorkbench).toContainElement(actionWorkbench);
      expect(closureBand).toContainElement(within(page).getByTestId("module-home-portfolio-risk"));
      expect(closureBand).toContainElement(within(page).getByTestId("module-home-pnl-summary"));
      expect(closureBand).toContainElement(within(page).getByTestId("module-home-balance-basis"));
      expect(actionWorkbench).toContainElement(within(page).getByTestId("module-home-portfolio-quick-access"));
      expect(actionWorkbench).toContainElement(within(page).getByTestId("module-home-drilldowns"));
      expect(actionWorkbench).toContainElement(within(page).getByTestId("module-home-data-note"));
    });
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
  it("requests full macro analysis and strategy summaries independently when another primary query fails", async () => {
    const base = createApiClient({ mode: "mock" });
    const analysis = deferred<ApiEnvelope<MacroToolkitAnalysisPayload>>();
    const getMacroToolkitAnalysis = vi.fn(() => analysis.promise);
    const getMarketDataCatalog = vi.fn(async () => {
      throw new Error("catalog unavailable");
    });
    const getMacroToolkitStrategySummaries = vi.fn(async () => strategySummariesEnvelope());
    const client: ApiClient = {
      ...base,
      getMacroToolkitAnalysis,
      getMarketDataCatalog,
      getMacroToolkitStrategySummaries,
    };

    renderAt("/market-overview", client);

    await waitFor(() => {
      expect(getMacroToolkitAnalysis).toHaveBeenCalledWith({
        detail: "full",
        historyLimit: MARKET_HOME_CRISIS_SCORE_HISTORY_LIMIT,
      });
      expect(getMarketDataCatalog).toHaveBeenCalledTimes(1);
      expect(getMacroToolkitStrategySummaries).toHaveBeenCalledTimes(1);
    });

    analysis.resolve(coreMacroAnalysisEnvelope());
  });

  it("surfaces abnormal envelope states in the 6-source verification workbench", async () => {
    const base = createApiClient({ mode: "mock" });
    const choice = unsortedMarketSeriesEnvelope("macro.choice.latest", [
      "2026-06-01",
      "2026-06-02",
    ]);
    choice.result_meta = {
      ...choice.result_meta,
      quality_flag: "warning",
      vendor_status: "vendor_unavailable",
      fallback_mode: "latest_snapshot",
      as_of_date: "2026-06-02",
      fallback_date: "2026-05-30",
    };
    choice.result.series[0].latest_change = null;
    choice.result.series[1].latest_change = 0;
    choice.result.series[1].policy_note = "";
    const client: ApiClient = {
      ...base,
      getChoiceMacroLatest: async () => choice,
      getMarketDataRates: async () => emptyChoiceMacroEnvelope("market_data.rates"),
      getMarketDataCatalog: async () => {
        throw new Error("catalog unavailable");
      },
      getMacroToolkitStrategySummaries: async () => strategySummariesEnvelope(),
    };

    renderAt("/market-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    const backend = within(page).getByTestId("module-home-market-backend-data");
    await waitFor(() => {
      expect(backend).toHaveTextContent("6");
      expect(backend).toHaveTextContent("最新行情");
      expect(backend).toHaveTextContent("正式利率");
      expect(backend).toHaveTextContent("数据目录");
      expect(backend).toHaveTextContent("宏观全量");
      expect(backend).toHaveTextContent("策略全量");
      expect(backend).toHaveTextContent("新闻事件");
      expect(backend).toHaveTextContent("macro.choice.latest_trace");
      expect(backend).toHaveTextContent("latest_snapshot");
      expect(backend).toHaveTextContent("供应方不可用");
      expect(backend).toHaveTextContent("回退模式");
    });
  });

  it("keeps report evidence visible without exposing technical warnings or internal paths", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const macro = coreMacroAnalysisEnvelope();
    macro.result_meta = {
      ...macro.result_meta,
      source_surface: "/api/internal/macro-toolkit/full",
    };
    macro.result.output_files = [
      {
        name: "performance_results.csv",
        path: "F:\MOSS-V3\backend\private\performance_results.csv",
        size_bytes: 2048,
        modified_at: "2026-06-01T00:00:00Z",
      },
    ];
    macro.result.warnings = [
      "gate_supplement_failed: livermore gate supplement refresh failed",
    ];
    const client: ApiClient = {
      ...base,
      getMacroToolkitAnalysis: async () => macro,
    };

    renderAt("/market-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    const backend = within(page).getByTestId("module-home-market-backend-data");
    await user.click((await within(backend).findAllByRole("tab"))[3]!);
    await waitFor(() => {
      expect(backend).toHaveTextContent("performance_results.csv");
      expect(backend).toHaveTextContent("补充数据获取失败，当前结果可能不完整");
      expect(backend).toHaveTextContent("内部数据地址或标识已隐藏");
    });
    expect(backend).not.toHaveTextContent("gate_supplement_failed");
    expect(backend).not.toHaveTextContent("/api/internal/macro-toolkit/full");
  });

  it("renders market-overview with four option-3 chapters", async () => {
    renderAt("/market-overview");

    const page = await screen.findByTestId("module-workbench-home");
    const subpageNav = within(page).getByTestId("module-home-market-subpage-nav");
    const chapterNav = within(page).getByTestId("module-home-market-chapter-nav");
    const subpageLinks = within(subpageNav).getAllByRole("link");
    const chapterLinks = within(chapterNav).getAllByRole("link");

    expect(subpageLinks.map((link) => link.getAttribute("href"))).toEqual([
      "/market-overview",
      "/market-data",
      "/cross-asset",
      "/macro-observation",
      "/macro-toolkit",
      "/stock-analysis",
      "/news-events",
    ]);
    expect(subpageLinks.map((link) => link.textContent)).toEqual([
      "市场总览",
      "市场数据",
      "跨资产",
      "宏观观察",
      "宏观工具",
      "股票分析",
      "新闻事件",
    ]);
    expect(subpageLinks[0]).toHaveAttribute("aria-current", "page");
    expect(subpageLinks[0]).toHaveAttribute("data-active", "true");
    expect(chapterLinks.map((link) => link.getAttribute("href"))).toEqual([
      "#market-overview-judgment",
      "#market-overview-evidence",
      "#market-financial-charts-all",
      "#market-backend-data-all",
    ]);
    expect(document.getElementById("market-overview-judgment")).toBeTruthy();
    expect(document.getElementById("market-overview-evidence")).toBeTruthy();
    expect(document.getElementById("market-financial-charts-all")).toBeTruthy();
    expect(document.getElementById("market-backend-data-all")).toBeTruthy();
  });

  it("syncs the option-3 active chapter from the route hash", async () => {
    renderAt("/market-overview#market-financial-charts-all");

    const page = await screen.findByTestId("module-workbench-home");
    const chapterNav = within(page).getByTestId("module-home-market-chapter-nav");

    expect(
      within(chapterNav).getByRole("link", { name: "金融图表 12" }),
    ).toHaveAttribute("aria-current", "location");
    expect(
      within(chapterNav).getByRole("link", { name: "分析观察" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("locks the option-3 navigation rail and search overlay geometry", () => {
    const css = readFileSync(MARKET_HOME_NOCTURNE_CSS_PATH, "utf8");

    expect(css).toMatch(
      /\.chapterNav\s*\{[\s\S]*?grid-template-rows:\s*20px 26px;[\s\S]*?height:\s*46px;/,
    );
    expect(css).toMatch(
      /\.subpageNav\s*\{[\s\S]*?height:\s*20px;[\s\S]*?padding:\s*0 76px 0 4px;[\s\S]*?grid-template-columns:\s*repeat\(7, minmax\(0, 1fr\)\);/,
    );
    expect(css).toMatch(
      /\[data-testid="module-home-market-dense-search"\]:focus-within\)\s*\{[\s\S]*?top:\s*48px;[\s\S]*?width:\s*220px;/,
    );
    expect(css).toMatch(
      /@media \(max-width: 720px\)[\s\S]*?\.chapterNav\s*\{[\s\S]*?grid-template-rows:\s*18px 20px;[\s\S]*?height:\s*38px;/,
    );
    expect(css).not.toContain("> div > div:first-child");
  });

  it("exposes dense refresh from the option-3 top rail", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const refreshChoiceMacro = vi.fn(async () => ({
      status: "completed",
      run_id: "market-home-refresh:test-run",
    }));
    const client: ApiClient = {
      ...base,
      refreshChoiceMacro,
      getChoiceMacroRefreshStatus: vi.fn(async () => ({
        status: "completed",
        run_id: "market-home-refresh:test-run",
      })),
    };

    renderAt("/market-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    const refreshButton = within(page).getByTestId("module-home-market-dense-refresh");
    await user.click(refreshButton);
    await waitFor(() => expect(refreshChoiceMacro).toHaveBeenCalled());
  });

  it("treats partial market refresh as accepted and keeps option-3 sections mounted", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const refreshChoiceMacro = vi.fn(async () => ({
      status: "partial",
      run_id: "market-home-refresh:partial",
      warnings: ["Choice macro refresh failed"],
    }));
    const client: ApiClient = { ...base, refreshChoiceMacro };

    renderAt("/market-overview", client);
    const page = await screen.findByTestId("module-workbench-home");
    await user.click(within(page).getByTestId("module-home-market-dense-refresh"));
    await waitFor(() => expect(refreshChoiceMacro).toHaveBeenCalled());
    expect(within(page).getByTestId("module-home-market-dense")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-market-financial-charts")).toBeInTheDocument();
    expect(within(page).getByTestId("module-home-market-backend-data")).toBeInTheDocument();
  });

  it("treats degraded market refresh as accepted and keeps Chinese feedback user-safe", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const refreshChoiceMacro = vi.fn(async () => ({
      status: "degraded",
      run_id: "market-home-refresh:degraded",
      quality_flag: "warning",
      warning_code: "gate_supplement_failed",
      warnings: ["gate_supplement_failed: livermore gate supplement refresh failed"],
    }));
    const client: ApiClient = { ...base, refreshChoiceMacro };

    renderAt("/market-overview", client);
    const page = await screen.findByTestId("module-workbench-home");
    await user.click(within(page).getByTestId("module-home-market-dense-refresh"));
    await waitFor(() => expect(refreshChoiceMacro).toHaveBeenCalled());
    expect(page.textContent).not.toContain("gate_supplement_failed");
    expect(page.textContent).not.toContain("livermore gate supplement refresh failed");
  });

  it("explains missing market refresh permission without exposing raw backend wording", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const refreshChoiceMacro = vi.fn(async () => {
      throw new Error("User is not allowed to refresh macro_vendor.choice_series.");
    });
    const client: ApiClient = { ...base, refreshChoiceMacro };

    renderAt("/market-overview", client);
    const page = await screen.findByTestId("module-workbench-home");
    await user.click(within(page).getByTestId("module-home-market-dense-refresh"));
    await waitFor(() => expect(refreshChoiceMacro).toHaveBeenCalled());
    expect(page.textContent).not.toContain("macro_vendor.choice_series");
    expect(page.textContent).not.toContain("User is not allowed");
  });

  it("uses the maximum returned market trade dates in the dense top rail", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getChoiceMacroLatest: async () =>
        unsortedMarketSeriesEnvelope("macro.choice.latest", ["2026-04-30", "2026-05-29", "2026-05-30"]),
      getMarketDataRates: async () =>
        unsortedMarketSeriesEnvelope("market_data.rates", ["2026-04-30", "2026-05-29"]),
      getMarketDataCatalog: async () => emptyMacroVendorEnvelope(),
      getMacroToolkitAnalysis: async () => coreMacroAnalysisEnvelope(),
      getMacroToolkitStrategySummaries: async () => strategySummariesEnvelope(),
    };

    renderAt("/market-overview", client);
    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(page).toHaveTextContent("2026-05-30");
      expect(page).toHaveTextContent("2026-05-29");
    });
  });

  it("keeps KPI strip structure and independent date fields visible in option-3", async () => {
    renderAt("/market-overview");
    const page = await screen.findByTestId("module-workbench-home");
    const chapterNav = within(page).getByTestId("module-home-market-chapter-nav");
    const dense = within(page).getByTestId("module-home-market-dense");
    const refreshButton = within(page).getByTestId("module-home-market-dense-refresh");

    expect(chapterNav).toBeInTheDocument();
    expect(dense).toBeInTheDocument();
    expect(refreshButton).toBeInTheDocument();
    expect(within(chapterNav).getAllByRole("link")).toHaveLength(4);
    expect(page).toHaveTextContent("数据日期");
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
      expect(within(page).queryByTestId("module-home-macro-groups")).not.toBeInTheDocument();
    });
  });

  it("keeps empty option-3 charts and backend sections mounted when market data is empty", async () => {
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
      expect(within(page).getByTestId("module-home-market-financial-charts")).toBeInTheDocument();
      expect(within(page).getByTestId("module-home-market-backend-data")).toBeInTheDocument();
    });
  });

  it("exposes failed reads and retained-data refresh failures on the real market route", async () => {
    const user = userEvent.setup();
    const base = createRealModeDemoClient();
    const getMarketDataCatalog = vi
      .fn()
      .mockResolvedValueOnce(emptyMacroVendorEnvelope())
      .mockRejectedValueOnce(new Error("catalog refresh unavailable"));
    const client: ApiClient = {
      ...base,
      getMarketDataRates: vi.fn(async () => {
        throw new Error("rates unavailable");
      }),
      getMarketDataCatalog,
      refreshChoiceMacro: vi.fn(async () => ({
        status: "completed",
        run_id: "market-home-refresh:status-contract",
      })),
      getChoiceMacroRefreshStatus: vi.fn(async () => ({
        status: "completed",
        run_id: "market-home-refresh:status-contract",
      })),
    };

    renderAt("/market-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    await waitFor(() => {
      expect(
        within(page).getByTestId("module-home-market-section-status-rates"),
      ).toHaveTextContent("读取失败");
    });

    await user.click(
      within(page).getByTestId("module-home-market-dense-refresh"),
    );
    await waitFor(() => expect(getMarketDataCatalog).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      expect(
        within(page).getByTestId("module-home-market-section-status-coverage"),
      ).toHaveTextContent("刷新失败 · 保留旧数据");
    });
  });

  it("keeps 12 charts and 6 backend tabs visible when only one formal rate series exists", async () => {
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
      expect(within(page).getByTestId("module-home-market-financial-charts").querySelectorAll('[data-testid^="module-home-market-chart-"]')).toHaveLength(12);
      expect(within(page).getByTestId("module-home-market-backend-data").querySelectorAll('[role="tab"]').length).toBe(6);
    });
  });

  it("keeps 50-row news pagination visible in the 6-source verification workbench", async () => {
    const base = createApiClient({ mode: "mock" });
    const newsEnvelope: ApiEnvelope<ChoiceNewsEventsPayload> = {
      result: {
        total_rows: 11_108,
        limit: 50,
        offset: 0,
        as_of_date: "2026-07-28",
        excluded_future_rows: 0,
        payload_json_included: true,
        compare: {
          basis: "analytical",
          rule_version: "news-rule-v1",
          same_direction: [],
          conflicting: [],
          review_needed: [],
          candidate_scenarios: [],
        },
        events: [
          {
            event_key: "event-1",
            received_at: "2026-07-28T08:00:00Z",
            group_id: "market",
            content_type: "news",
            serial_id: 1,
            request_id: 2,
            error_code: 0,
            error_msg: "",
            topic_code: "rates",
            item_index: 0,
            payload_text: "完整新闻正文",
            payload_json: '{"headline":"完整新闻正文"}',
          },
        ],
      },
      result_meta: testMeta("choice.news.events"),
    };
    const client: ApiClient = {
      ...base,
      getChoiceNewsEvents: vi.fn(async () => newsEnvelope),
    };

    renderAt("/market-overview", client);

    const page = await screen.findByTestId("module-workbench-home");
    const backend = within(page).getByTestId("module-home-market-backend-data");
    const backendTabs = within(backend).getAllByRole("tab");

    await userEvent.click(backendTabs[5]!);
    await waitFor(() => {
      expect(backend).toHaveTextContent("50");
      expect(backend).toHaveTextContent("11,108");
    });
  });
});
