import type {
  ApiEnvelope,
  AdvancedAttributionSummary,
  CampisiAttributionPayload,
  CampisiEnhancedPayload,
  CampisiFourEffectsPayload,
  CampisiMaturityBucketsPayload,
  CashflowProjectionPayload,
  CarryRollDownPayload,
  KRDAttributionPayload,
  LedgerPnlDataPayload,
  LedgerPnlDatesPayload,
  LedgerPnlSummaryPayload,
  ChoiceMacroLatestPayload,
  ChoiceMacroRecentPoint,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  FormalPnlRefreshPayload,
  MacroBondLinkagePayload,
  MacroVendorPayload,
  NumericUnit,
  NcdFundingProxyPayload,
  PnlBridgePayload,
  PnlBasis,
  PnlDataPayload,
  PnlDatesPayload,
  PnlOverviewPayload,
  QdbGlMonthlyAnalysisDatesPayload,
  QdbGlMonthlyAnalysisWorkbookPayload,
  PnlAttributionPayload,
  PnlAttributionAnalysisSummary,
  PnlCompositionPayload,
  SpreadAttributionPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "./contracts";
import { formatRawAsNumeric } from "../utils/format";
import {
  createDemoBalanceAnalysisClient,
  createRealBalanceAnalysisClient,
  type BalanceAnalysisClientMethods,
} from "./balanceAnalysisClient";
import {
  createDemoBondAnalyticsClient,
  createDemoBondDashboardClient,
  createRealBondAnalyticsClient,
  createRealBondDashboardClient,
  type BondAnalyticsClientMethods,
} from "./bondAnalyticsClient";
import {
  createDemoExecutiveClient,
  createRealExecutiveClient,
  type ExecutiveClientMethods,
} from "./executiveClient";
import {
  createDemoHealthClient,
  createRealHealthClient,
  type HealthClientMethods,
} from "./healthClient";
import {
  createDemoLiabilityAdbClient,
  createRealLiabilityAdbClient,
  type LiabilityAdbClientMethods,
} from "./liabilityAdbClient";
import type { MarketDataClientMethods } from "./marketDataClient";
import type { MacroToolkitClientMethods } from "./macroToolkitClient";
import {
  createMockPnlBusinessClient,
  createRealPnlBusinessClient,
  type PnlClientMethods,
} from "./pnlClient";
import {
  createDemoProductCategoryClient,
  createRealProductCategoryClient,
  type ProductCategoryClientMethods,
} from "./productCategoryClient";
import {
  createDemoPositionsClient,
  createRealPositionsClient,
  type PositionsClientMethods,
} from "./positionsClient";
import { MOCK_CHOICE_MACRO_TUSHARE_EQUITY_SERIES } from "./marketDataMocks";
import {
  createMockBalanceMovementClient,
  createRealBalanceMovementClient,
  type BalanceMovementClientMethods,
} from "./balanceMovementClient";
import {
  createMockLedgerClient,
  createRealLedgerClient,
  type LedgerClientMethods,
} from "./ledgerClient";
import {
  createMockMarketDataClient,
  createRealMarketDataClient,
} from "./marketDataClient";
import {
  createMockMacroToolkitClient,
  createRealMacroToolkitClient,
} from "./macroToolkitClient";
import {
  createMockKpiClient,
  createRealKpiClient,
  type KpiClientMethods,
} from "./kpiClient";
import {
  createMockCubeClient,
  createRealCubeClient,
  type CubeClientMethods,
} from "./cubeClient";
import {
  createDemoAgentClient,
  createRealAgentClient,
  type AgentClientMethods,
} from "./agentClient";
import {
  dashboardWorkbenchDemoEndpoints,
  dashboardWorkbenchLiveEndpoints,
  type DashboardClientMethods,
} from "./workbenchDashboardApi";
import {
  bondDashboardDemoEndpoints,
  bondDashboardLiveEndpoints,
} from "./bondDashboardWorkbenchEndpoints";

export type DataSourceMode = "mock" | "real";
export { ApiClientProvider, useApiClient } from "./clientContext";
// Re-export domain method types for consumers who want fine-grained imports
export type { BalanceAnalysisClientMethods } from "./balanceAnalysisClient";
export type { BondAnalyticsClientMethods } from "./bondAnalyticsClient";
export type { DashboardClientMethods } from "./workbenchDashboardApi";
export type { ExecutiveClientMethods } from "./executiveClient";
export type { MarketDataClientMethods } from "./marketDataClient";
export type { MacroToolkitClientMethods } from "./macroToolkitClient";
export type { PnlClientMethods } from "./pnlClient";
export type { ProductCategoryClientMethods } from "./productCategoryClient";
export type { PositionsClientMethods } from "./positionsClient";
export type { LedgerClientMethods } from "./ledgerClient";
export type { KpiClientMethods } from "./kpiClient";
export type { CubeClientMethods } from "./cubeClient";
export type { AgentClientMethods } from "./agentClient";
export type { HealthClientMethods } from "./healthClient";
export type { LiabilityAdbClientMethods } from "./liabilityAdbClient";

export type ApiClient = {
  mode: DataSourceMode;
} & HealthClientMethods
  & ExecutiveClientMethods
  & DashboardClientMethods
  & PnlClientMethods
  & ProductCategoryClientMethods
  & BalanceMovementClientMethods
  & BondAnalyticsClientMethods
  & BalanceAnalysisClientMethods
  & PositionsClientMethods & LiabilityAdbClientMethods
  & MarketDataClientMethods
  & MacroToolkitClientMethods
  & LedgerClientMethods
  & KpiClientMethods
  & CubeClientMethods
  & AgentClientMethods;

export type ApiClientOptions = {
  mode?: DataSourceMode;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
};

const defaultFetch = (...args: Parameters<typeof fetch>) => fetch(...args);

const delay = async () => new Promise<void>((resolve) => setTimeout(resolve, 40));

type MockClientBundle = Pick<typeof import("../mocks/mockApiEnvelope"), "buildMockApiEnvelope"> & typeof import("../mocks/workbench") & typeof import("../mocks/pnlAttributionWorkbench") & typeof import("../mocks/campisiMocks") & typeof import("../mocks/ledgerPnlMocks");
let mockClientBundleCache: MockClientBundle | null = null;

async function loadMockClientBundle(): Promise<MockClientBundle> {
  const [apiEnvelopeModule, workbench, pnlAttribution, campisi, ledgerPnl] =
    await Promise.all([
      import("../mocks/mockApiEnvelope"),
      import("../mocks/workbench"),
      import("../mocks/pnlAttributionWorkbench"),
      import("../mocks/campisiMocks"),
      import("../mocks/ledgerPnlMocks"),
    ]);
  return {
    buildMockApiEnvelope: apiEnvelopeModule.buildMockApiEnvelope,
    ...workbench,
    ...pnlAttribution,
    ...campisi,
    ...ledgerPnl,
  };
}

async function ensureMockClientBundle(): Promise<MockClientBundle> {
  mockClientBundleCache ??= await loadMockClientBundle();
  return mockClientBundleCache;
}

function isFiniteNumber(value: number | undefined): value is number {
  return value !== undefined && Number.isFinite(value);
}

function buildPnlBasisQuerySegment(basis?: PnlBasis) {
  return basis && basis !== "formal" ? `&basis=${encodeURIComponent(basis)}` : "";
}

function buildCampisiQuery(options?: {
  startDate?: string;
  endDate?: string;
  lookbackDays?: number;
}) {
  const params = new URLSearchParams();
  if (options?.startDate?.trim()) {
    params.set("start_date", options.startDate.trim());
  }
  if (options?.endDate?.trim()) {
    params.set("end_date", options.endDate.trim());
  }
  if (Number.isFinite(options?.lookbackDays)) {
    params.set("lookback_days", String(options?.lookbackDays));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}


function _buildMockNcdFundingProxyPayload(reportDate?: string): NcdFundingProxyPayload {
  return {
    as_of_date: reportDate?.trim() || "2026-04-23",
    proxy_label: "Tushare Shibor funding proxy (not NCD issuance matrix)",
    is_actual_ncd_matrix: false,
    rows: [
      {
        row_key: "shibor_fixing",
        label: "Shibor fixing",
        "1M": 1.405,
        "3M": 1.4275,
        "6M": 1.4505,
        "9M": 1.464,
        "1Y": 1.478,
        quote_count: null,
      },
    ],
    warnings: [
      "Proxy only; not actual NCD issuance matrix.",
      "Using landed external warehouse Shibor; quote medians unavailable.",
    ],
  };
}

const _MOCK_MACRO_FOUNDATION_PAYLOAD: MacroVendorPayload = {
  read_target: "duckdb",
  series: [
    {
      series_id: "M001",
      series_name: "公开市场7天逆回购利率",
      vendor_name: "choice",
      vendor_version: "vv_choice_catalog_v1",
      frequency: "daily",
      unit: "%",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
    },
    {
      series_id: "M002",
      series_name: "DR007",
      vendor_name: "choice",
      vendor_version: "vv_choice_catalog_v1",
      frequency: "daily",
      unit: "%",
      refresh_tier: "fallback",
      fetch_mode: "latest",
      fetch_granularity: "single",
      policy_note: "low-frequency latest-only lane",
    },
    {
      series_id: "M003",
      series_name: "1年期国债到期收益率",
      vendor_name: "choice",
      vendor_version: "vv_choice_catalog_v1",
      frequency: "daily",
      unit: "%",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
    },
  ],
};

function buildMockChoiceMacroRecentPoints(
  endDate: string,
  count: number,
  finalValue: number,
  amplitude: number,
): ChoiceMacroRecentPoint[] {
  const out: ChoiceMacroRecentPoint[] = [];
  for (let i = 0; i < count; i++) {
    const dayOffset = -(count - 1 - i);
    const d = new Date(`${endDate}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + dayOffset);
    const trade_date = d.toISOString().slice(0, 10);
    const t = count > 1 ? i / (count - 1) : 1;
    const wobble = Math.sin(i * 0.8 + amplitude) * amplitude * 0.15;
    const value_numeric = Number((finalValue + (t - 1) * amplitude * 0.35 + wobble).toFixed(4));
    out.push({
      trade_date,
      value_numeric,
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      quality_flag: "ok",
    });
  }
  out[out.length - 1] = {
    ...out[out.length - 1],
    value_numeric: finalValue,
  };
  return out;
}

const _MOCK_CHOICE_MACRO_LATEST_PAYLOAD: ChoiceMacroLatestPayload = {
  read_target: "duckdb",
  series: [
    {
      series_id: "M001",
      series_name: "公开市场7天逆回购利率",
      trade_date: "2026-04-10",
      value_numeric: 1.75,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
      latest_change: 0.2,
      recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 1.75, 0.06),
    },
    {
      series_id: "M002",
      series_name: "DR007",
      trade_date: "2026-04-10",
      value_numeric: 1.83,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
      refresh_tier: "fallback",
      fetch_mode: "latest",
      fetch_granularity: "single",
      policy_note: "low-frequency latest-only lane",
      latest_change: -0.05,
      recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 1.83, 0.05),
    },
    {
      series_id: "M003",
      series_name: "1年期国债到期收益率",
      trade_date: "2026-04-10",
      value_numeric: 1.56,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
      latest_change: 0.03,
      recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 1.56, 0.04),
    },
    {
      series_id: "E1000180",
      series_name: "中债国债到期收益率:10年",
      trade_date: "2026-03-01",
      value_numeric: 1.94,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "edb chinabond cross-asset",
      latest_change: -0.011,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 1.94, 0.04),
    },
    {
      series_id: "E1003238",
      series_name: "美国国债收益率曲线:10年",
      trade_date: "2026-03-01",
      value_numeric: 4.1,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "edb fed cross-asset",
      latest_change: 0.05,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 4.1, 0.12),
    },
    {
      series_id: "EM1",
      series_name: "10Y中国国债-10Y美国国债",
      trade_date: "2026-03-01",
      value_numeric: -210,
      unit: "bp",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "edb chinabond spread",
      latest_change: -3,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, -210, 8),
    },
    {
      series_id: "EMM00166466",
      series_name: "中债国债到期收益率:10年",
      trade_date: "2026-03-01",
      value_numeric: 1.94,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "catalog-aligned cross-asset",
      latest_change: -0.011,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 1.94, 0.04),
    },
    {
      series_id: "EMM00166502",
      series_name: "中债政策性金融债到期收益率(国开行)10年",
      trade_date: "2026-03-01",
      value_numeric: 2.09,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "catalog-aligned cross-asset",
      latest_change: 0.015,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 2.09, 0.05),
    },
    {
      series_id: "EMM00167613",
      series_name: "银行间同业拆借加权利率:7天",
      trade_date: "2026-03-01",
      value_numeric: 1.82,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "catalog-aligned cross-asset",
      latest_change: 0.021,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 1.82, 0.06),
    },
    {
      series_id: "EMM01843735",
      series_name: "第一财经研究院中国金融条件指数(日)",
      trade_date: "2026-03-01",
      value_numeric: 98.6,
      unit: "index",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "catalog-aligned cross-asset",
      latest_change: 0.35,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 98.6, 0.8),
    },
    {
      series_id: "EMM00058124",
      series_name: "中间价:美元兑人民币",
      trade_date: "2026-03-01",
      value_numeric: 7.14,
      unit: "CNY/USD",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "catalog-aligned cross-asset",
      latest_change: 0.0064,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 7.14, 0.02),
    },
    {
      series_id: "CA.CN_GOV_10Y",
      series_name: "中债国债到期收益率:10年",
      trade_date: "2026-03-01",
      value_numeric: 1.94,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: -0.011,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 1.94, 0.04),
    },
    {
      series_id: "EMG00001310",
      series_name: "美国:国债收益率:10年",
      trade_date: "2026-03-01",
      value_numeric: 4.1,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "edb us treasury — catalog-aligned",
      latest_change: 0.05,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 4.1, 0.12),
    },
    {
      series_id: "CA.US_GOV_10Y",
      series_name: "美国10年期国债收益率",
      trade_date: "2026-03-01",
      value_numeric: 4.1,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: 0.05,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 4.1, 0.12),
    },
    {
      series_id: "CA.CN_US_SPREAD",
      series_name: "中美国债利差(10Y)",
      trade_date: "2026-03-01",
      value_numeric: -210,
      unit: "bp",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: -3,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, -210, 8),
    },
    {
      series_id: "CA.DR007",
      series_name: "存款类机构质押式回购加权利率:DR007",
      trade_date: "2026-03-01",
      value_numeric: 1.82,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: 0.021,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 1.82, 0.06),
    },
    ...MOCK_CHOICE_MACRO_TUSHARE_EQUITY_SERIES,
    {
      series_id: "CA.BRENT",
      series_name: "ICE布伦特原油期货收盘价",
      trade_date: "2026-03-01",
      value_numeric: 82.3,
      unit: "USD/bbl",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: 4.8,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 82.3, 2.2),
    },
    {
      series_id: "CA.STEEL",
      series_name: "螺纹钢主力合约结算价",
      trade_date: "2026-03-01",
      value_numeric: 8500,
      unit: "CNY/t",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: 3.2,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 8500, 120),
    },
    {
      series_id: "CA.USDCNY",
      series_name: "即期汇率:美元兑人民币",
      trade_date: "2026-03-01",
      value_numeric: 7.14,
      unit: "CNY/USD",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: 0.0064,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 7.14, 0.02),
    },
  ],
};

const _MOCK_MACRO_BOND_LINKAGE_PAYLOAD: MacroBondLinkagePayload = {
  report_date: "2026-04-10",
  environment_score: {
    report_date: "2026-04-10",
    rate_direction: "falling",
    rate_direction_score: -0.42,
    liquidity_score: 0.31,
    growth_score: -0.14,
    inflation_score: 0.08,
    composite_score: -0.11,
    signal_description:
      "资金面维持宽松，长端对海外利率与风险偏好更敏感：国内短端利率稳定，权益与商品反弹带来增长预期修复，但美债高位约束利差压缩空间。建议以流动性为锚、用海外约束做上限、用增长预期做节奏。",
    contributing_factors: [
      {
        category: "rate",
        series_id: "EMM00166466",
        series_name: "10Y treasury yield",
        latest_value: 1.56,
        delta: -0.18,
        score: -1,
      },
    ],
    warnings: [],
  },
  portfolio_impact: {
    estimated_rate_change_bps: "-12.6",
    estimated_spread_widening_bps: "-6.2",
    estimated_rate_pnl_impact: "1820000.50",
    estimated_spread_pnl_impact: "410000.25",
    total_estimated_impact: "2230000.75",
    impact_ratio_to_market_value: "0.0041",
  },
  top_correlations: [
    {
      series_id: "EMM00166466",
      series_name: "10Y treasury yield",
      target_family: "credit_spread",
      target_tenor: "5Y",
      target_yield: "credit_spread_5Y",
      correlation_3m: -0.41,
      correlation_6m: -0.58,
      correlation_1y: -0.63,
      lead_lag_days: -4,
      direction: "negative",
    },
    {
      series_id: "EMM00166253",
      series_name: "DR007",
      target_family: "treasury",
      target_tenor: "10Y",
      target_yield: "treasury_10Y",
      correlation_3m: 0.32,
      correlation_6m: 0.47,
      correlation_1y: 0.51,
      lead_lag_days: 2,
      direction: "positive",
    },
    {
      series_id: "EMM00072301",
      series_name: "CPI YoY",
      target_family: "aaa_credit",
      target_tenor: "3Y",
      target_yield: "aaa_credit_3Y",
      correlation_3m: 0.11,
      correlation_6m: 0.26,
      correlation_1y: 0.29,
      lead_lag_days: 7,
      direction: "positive",
    },
  ],
  warnings: [
    "仅为分析信号，不要把估算影响当作正式归因。",
  ],
  computed_at: "2026-04-13T00:00:00Z",
};

const _MOCK_FX_FORMAL_STATUS_PAYLOAD: FxFormalStatusPayload = {
  read_target: "duckdb",
  vendor_priority: ["choice", "akshare", "fail_closed"],
  candidate_count: 3,
  materialized_count: 2,
  latest_trade_date: "2026-04-10",
  carry_forward_count: 1,
  rows: [
    {
      base_currency: "USD",
      quote_currency: "CNY",
      pair_label: "USD/CNY",
      series_id: "FX.USD.CNY",
      series_name: "USD/CNY 中间价",
      vendor_series_code: "USD/CNY",
      trade_date: "2026-04-10",
      observed_trade_date: "2026-04-09",
      mid_rate: 7.2,
      source_name: "fx_daily_mid",
      vendor_name: "choice",
      vendor_version: "vv_fx_formal_mock",
      source_version: "sv_fx_formal_mock",
      is_business_day: false,
      is_carry_forward: true,
      status: "ok",
    },
    {
      base_currency: "EUR",
      quote_currency: "CNY",
      pair_label: "EUR/CNY",
      series_id: "FX.EUR.CNY",
      series_name: "EUR/CNY 中间价",
      vendor_series_code: "EUR/CNY",
      trade_date: "2026-04-10",
      observed_trade_date: "2026-04-10",
      mid_rate: 7.88,
      source_name: "fx_daily_mid",
      vendor_name: "akshare",
      vendor_version: "vv_fx_formal_mock",
      source_version: "sv_fx_formal_mock",
      is_business_day: true,
      is_carry_forward: false,
      status: "ok",
    },
    {
      base_currency: "JPY",
      quote_currency: "CNY",
      pair_label: "JPY/CNY",
      series_id: "FX.JPY.CNY",
      series_name: "JPY/CNY middle rate",
      vendor_series_code: "JPY/CNY",
      trade_date: null,
      observed_trade_date: null,
      mid_rate: null,
      source_name: null,
      vendor_name: null,
      vendor_version: null,
      source_version: null,
      is_business_day: null,
      is_carry_forward: null,
      status: "missing",
    },
  ],
};

const _MOCK_FX_ANALYTICAL_PAYLOAD: FxAnalyticalPayload = {
  read_target: "duckdb",
  groups: [
    {
      group_key: "middle_rate",
      title: "外汇分析：中间价",
      description:
        "目录观察到的中间价序列仍是分析视图，不重定义正式口径。",
      series: [
        {
          group_key: "middle_rate",
          series_id: "FX.USD.CNY.OBS",
          series_name: "USD/CNY 中间价观察",
          trade_date: "2026-04-10",
          value_numeric: 7.2,
          frequency: "daily",
          unit: "CNY",
          source_version: "sv_fx_analytical_mock",
          vendor_version: "vv_fx_analytical_mock",
          refresh_tier: "stable",
          fetch_mode: "date_slice",
          fetch_granularity: "batch",
          policy_note: "仅分析口径中间价观察",
          quality_flag: "ok",
          latest_change: 0.02,
          recent_points: [
            {
              trade_date: "2026-04-10",
              value_numeric: 7.2,
              source_version: "sv_fx_analytical_mock",
              vendor_version: "vv_fx_analytical_mock",
              quality_flag: "ok",
            },
            {
              trade_date: "2026-04-09",
              value_numeric: 7.18,
              source_version: "sv_fx_analytical_prev",
              vendor_version: "vv_fx_analytical_prev",
              quality_flag: "ok",
            },
          ],
        },
      ],
    },
    {
      group_key: "fx_index",
      title: "外汇分析：指数",
      description:
        "人民币指数和估算指数序列仅用于分析口径，不流入正式外汇。",
      series: [
        {
          group_key: "fx_index",
          series_id: "FX.CFETS.RMB",
          series_name: "CFETS 人民币篮子指数",
          trade_date: "2026-04-10",
          value_numeric: 101.3,
          frequency: "daily",
          unit: "index",
          source_version: "sv_fx_analytical_mock",
          vendor_version: "vv_fx_analytical_mock",
          refresh_tier: "fallback",
          fetch_mode: "latest",
          fetch_granularity: "single",
          policy_note: "仅分析口径指数观察",
          quality_flag: "warning",
          latest_change: null,
          recent_points: [],
        },
      ],
    },
    {
      group_key: "fx_swap_curve",
      title: "外汇分析：掉期曲线",
      description:
        "外汇掉期与 C-Swap 序列仅用于分析口径，不写入正式外汇。",
      series: [
        {
          group_key: "fx_swap_curve",
          series_id: "FX.SWAP.1Y",
          series_name: "USD/CNY 1年外汇掉期",
          trade_date: "2026-04-10",
          value_numeric: 125.0,
          frequency: "daily",
          unit: "bp",
          source_version: "sv_fx_analytical_mock",
          vendor_version: "vv_fx_analytical_mock",
          refresh_tier: "stable",
          fetch_mode: "date_slice",
          fetch_granularity: "batch",
          policy_note: "analytical swap observation only",
          quality_flag: "ok",
          latest_change: -3,
          recent_points: [
            {
              trade_date: "2026-04-10",
              value_numeric: 125.0,
              source_version: "sv_fx_analytical_mock",
              vendor_version: "vv_fx_analytical_mock",
              quality_flag: "ok",
            },
          ],
        },
      ],
    },
  ],
};

const normalizeBaseUrl = (value?: string) =>
  value ? value.replace(/\/$/, "") : "";

const parseEnvMode = (): DataSourceMode => {
  const raw = import.meta.env.VITE_DATA_SOURCE;
  const envValue = typeof raw === "string" ? raw.trim().toLowerCase() : "";

  if (envValue === "real") return "real";
  if (envValue === "mock") return "mock";

  // Not explicitly set (or invalid value)
  const isProd = import.meta.env.PROD === true;
  if (isProd) {
    throw new Error(
      "VITE_DATA_SOURCE must be explicitly set to 'real' or 'mock' in production build. " +
        "Refusing to silently fall back to mock. " +
        "See docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md § 9.1.",
    );
  }

  // dev / test: default to mock with warning
  console.warn(
    "[client] VITE_DATA_SOURCE not set (raw=%o). Defaulting to 'mock' in dev mode. " +
      "Production build will fail fast; always declare explicitly in production.",
    raw,
  );
  return "mock";
};

const parseBaseUrl = () => {
  const raw = import.meta.env.VITE_API_BASE_URL;
  return normalizeBaseUrl(typeof raw === "string" ? raw.trim() : undefined);
};


export class ActionRequestError extends Error {
  readonly status: number;
  readonly runId?: string;
  /** Top-level `error_message` from the JSON body when present. */
  readonly errorMessage?: string;
  /** Raw `detail` field from the JSON body (string, object, or array). */
  readonly detail?: unknown;

  constructor(
    message: string,
    opts: {
      status: number;
      runId?: string;
      errorMessage?: string;
      detail?: unknown;
    },
  ) {
    super(message);
    this.name = "ActionRequestError";
    this.status = opts.status;
    this.runId = opts.runId;
    this.errorMessage = opts.errorMessage;
    this.detail = opts.detail;
  }
}

function extractApiRunId(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const top = body.run_id;
  if (typeof top === "string" && top.trim()) {
    return top;
  }
  const detail = body.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const nested = (detail as Record<string, unknown>).run_id;
    if (typeof nested === "string" && nested.trim()) {
      return nested;
    }
  }
  return undefined;
}

function extractTopLevelErrorMessage(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const errMsg = (payload as Record<string, unknown>).error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  return undefined;
}

function extractApiErrorDetail(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const errMsg = body.error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  const detail = body.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as Record<string, unknown>;
    const nestedMsg = d.error_message;
    if (typeof nestedMsg === "string" && nestedMsg.trim()) {
      return nestedMsg;
    }
    const nestedDetail = d.detail;
    if (typeof nestedDetail === "string" && nestedDetail.trim()) {
      return nestedDetail;
    }
  }
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (typeof item === "string") {
        return item;
      }
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg: unknown }).msg);
      }
      try {
        return JSON.stringify(item);
      } catch {
        return String(item);
      }
    });
    const joined = parts.filter((p) => p.trim()).join("; ");
    return joined || undefined;
  }
  return undefined;
}

function extractRawDetail(payload: unknown): unknown {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  if (!("detail" in (payload as Record<string, unknown>))) {
    return undefined;
  }
  return (payload as Record<string, unknown>).detail;
}

const requestJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<T>> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as ApiEnvelope<T>;
};

const requestActionJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    const detailText =
      extractApiErrorDetail(body) ?? `Request failed: ${path} (${response.status})`;
    const runId = extractApiRunId(body);
    const rawDetail = extractRawDetail(body);
    const topErrorMessage = extractTopLevelErrorMessage(body);
    const nestedDetail =
      rawDetail && typeof rawDetail === "object" && !Array.isArray(rawDetail)
        ? (rawDetail as Record<string, unknown>).error_message
        : undefined;
    const errorMessageField =
      topErrorMessage ??
      (typeof nestedDetail === "string" && nestedDetail.trim() ? nestedDetail : undefined);
    throw new ActionRequestError(detailText, {
      status: response.status,
      runId,
      errorMessage: errorMessageField,
      detail: rawDetail,
    });
  }

  return (await response.json()) as T;
};

const requestText = async (
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  fallbackFilename = "download.csv",
): Promise<{ content: string; filename: string }> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "text/csv, text/plain;q=0.9, */*;q=0.8",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  const contentDisposition = response.headers.get("Content-Disposition") ?? "";
  return {
    content: await response.text(),
    filename: parseDownloadFilename(contentDisposition, fallbackFilename),
  };
};

function parseDownloadFilename(contentDisposition: string, fallbackFilename: string) {
  const utf8Match = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(contentDisposition);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const filenameMatch = /filename=\"?([^\";]+)\"?/i.exec(contentDisposition);
  return filenameMatch?.[1] ?? fallbackFilename;
}

const requestBlob = async (
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  fallbackFilename = "download.bin",
): Promise<{ content: Blob; filename: string }> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/octet-stream;q=0.9, */*;q=0.8",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  const contentDisposition = response.headers.get("Content-Disposition") ?? "";
  return {
    content: await response.blob(),
    filename: parseDownloadFilename(contentDisposition, fallbackFilename),
  };
};

const requestActionWithBody = async <TResponse, TBody>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  body: TBody,
): Promise<TResponse> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as TResponse;
};

export function createApiClient(options: ApiClientOptions = {}): ApiClient {
  const mode = options.mode ?? parseEnvMode();
  const baseUrl = normalizeBaseUrl(options.baseUrl ?? parseBaseUrl());
  const fetchImpl = options.fetchImpl ?? defaultFetch;

  const mockClient: ApiClient = {
    mode: "mock",
    ...createDemoHealthClient(delay),
    ...createMockBalanceMovementClient(),
    ...createMockLedgerClient(),
    ...createMockMarketDataClient(),
    ...createMockMacroToolkitClient(),
    ...createMockKpiClient(),
    ...createMockCubeClient(),
    ...createMockPnlBusinessClient(),
    ...createDemoAgentClient(delay),
    ...createDemoExecutiveClient(delay, ensureMockClientBundle),
    ...dashboardWorkbenchDemoEndpoints(delay, ensureMockClientBundle),
    ...bondDashboardDemoEndpoints(delay, ensureMockClientBundle),
    ...createDemoBondAnalyticsClient(delay, ensureMockClientBundle),
    ...createDemoBondDashboardClient(delay, ensureMockClientBundle),
    async getFormalPnlDates(basis = "formal") {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "pnl.dates",
        {
          report_dates: [],
          formal_fi_report_dates: [],
          nonstd_bridge_report_dates: [],
        },
        { basis, formal_use_allowed: basis === "formal" },
      );
    },
    async getFormalPnlData(date: string, basis = "formal") {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "pnl.data",
        {
          report_date: date,
          formal_fi_rows: [],
          nonstd_bridge_rows: [],
        },
        { basis, formal_use_allowed: basis === "formal" },
      );
    },
    async getFormalPnlOverview(reportDate: string, basis = "formal") {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "pnl.overview",
        {
          report_date: reportDate,
          formal_fi_row_count: 0,
          nonstd_bridge_row_count: 0,
          interest_income_514: "0.00",
          fair_value_change_516: "0.00",
          capital_gain_517: "0.00",
          manual_adjustment: "0.00",
          total_pnl: "0.00",
        },
        { basis, formal_use_allowed: basis === "formal" },
      );
    },
    async getLedgerPnlDates() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("ledger_pnl.dates", (await ensureMockClientBundle()).mockLedgerPnlDates, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
    async getLedgerPnlData(reportDate: string, currency) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "ledger_pnl.data",
        {
          ...(await ensureMockClientBundle()).mockLedgerPnlData,
          report_date: reportDate,
          items: currency
            ? (await ensureMockClientBundle()).mockLedgerPnlData.items.filter((item: LedgerPnlDataPayload["items"][number]) => item.currency === currency)
            : (await ensureMockClientBundle()).mockLedgerPnlData.items,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getLedgerPnlSummary(reportDate: string, currency) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "ledger_pnl.summary",
        {
          ...(await ensureMockClientBundle()).mockLedgerPnlSummary,
          report_date: reportDate,
          by_currency: currency
            ? (await ensureMockClientBundle()).mockLedgerPnlSummary.by_currency.filter((item: LedgerPnlSummaryPayload["by_currency"][number]) => item.currency === currency)
            : (await ensureMockClientBundle()).mockLedgerPnlSummary.by_currency,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPnlBridge(reportDate: string) {
      await delay();
      const z = (unit: NumericUnit, sign_aware: boolean) =>
        formatRawAsNumeric({ raw: 0, unit, sign_aware });
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "pnl.bridge",
        {
          report_date: reportDate,
          rows: [],
          summary: {
            row_count: 0,
            ok_count: 0,
            warning_count: 0,
            error_count: 0,
            total_beginning_dirty_mv: z("yuan", false),
            total_ending_dirty_mv: z("yuan", false),
            total_carry: z("yuan", true),
            total_roll_down: z("yuan", true),
            total_treasury_curve: z("yuan", true),
            total_credit_spread: z("yuan", true),
            total_fx_translation: z("yuan", true),
            total_realized_trading: z("yuan", true),
            total_unrealized_fv: z("yuan", true),
            total_manual_adjustment: z("yuan", true),
            total_explained_pnl: z("yuan", true),
            total_actual_pnl: z("yuan", true),
            total_residual: z("yuan", true),
            quality_flag: "ok",
          },
          warnings: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async refreshFormalPnl(reportDate?: string) {
      await delay();
      return {
        status: "queued",
        run_id: "pnl_materialize:mock-run",
        job_name: "pnl_materialize",
        trigger_mode: "async",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: reportDate ?? "2026-02-28",
      };
    },
    async getFormalPnlImportStatus(runId?: string) {
      await delay();
      return {
        status: runId ? "completed" : "idle",
        run_id: runId ?? "pnl_materialize:mock-run",
        job_name: "pnl_materialize",
        trigger_mode: runId ? "terminal" : "idle",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: "2026-02-28",
        source_version: "sv_mock_dashboard_v2",
      };
    },
    async getPnlAttribution(_reportDate?: string) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("executive.pnl-attribution", (await ensureMockClientBundle()).pnlAttributionPayload);
    },
    async getVolumeRateAttribution(options) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("pnl_attribution.volume_rate", {
        ...(await ensureMockClientBundle()).mockVolumeRateAttribution,
        compare_type: options?.compareType ?? (await ensureMockClientBundle()).mockVolumeRateAttribution.compare_type,
      });
    },
    async getTplMarketCorrelation(_options) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("pnl_attribution.tpl_market", (await ensureMockClientBundle()).mockTplMarketCorrelation);
    },
    async getPnlCompositionBreakdown(_options) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("pnl_attribution.composition", (await ensureMockClientBundle()).mockPnlComposition);
    },
    async getPnlAttributionAnalysisSummary(_reportDate) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "pnl_attribution.summary",
        (await ensureMockClientBundle()).mockPnlAttributionAnalysisSummary,
      );
    },
    async getPnlCarryRollDown(_reportDate) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("pnl_attribution.carry_rolldown", (await ensureMockClientBundle()).mockCarryRollDown);
    },
    async getPnlSpreadAttribution(_options) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("pnl_attribution.spread", (await ensureMockClientBundle()).mockSpreadAttribution);
    },
    async getPnlKrdAttribution(_options) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("pnl_attribution.krd", (await ensureMockClientBundle()).mockKrdAttribution);
    },
    async getPnlAdvancedAttributionSummary(_reportDate) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "pnl_attribution.advanced_summary",
        (await ensureMockClientBundle()).mockAdvancedAttributionSummary,
      );
    },
    async getPnlCampisiAttribution(_options) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("pnl_attribution.campisi", (await ensureMockClientBundle()).mockCampisiAttribution);
    },
    async getPnlCampisiFourEffects(_options) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("campisi.four_effects", (await ensureMockClientBundle()).mockCampisiFourEffects, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
    async getPnlCampisiEnhanced(_options) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("campisi.enhanced", (await ensureMockClientBundle()).mockCampisiEnhanced, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
    async getPnlCampisiMaturityBuckets(_options) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("campisi.maturity_buckets", (await ensureMockClientBundle()).mockCampisiMaturityBuckets, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
    ...createDemoProductCategoryClient(delay),
    async getQdbGlMonthlyAnalysisDates() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "qdb-gl-monthly-analysis.dates",
        { report_months: [] },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_qdb_gl_mock",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
        },
      );
    },
    async getQdbGlMonthlyAnalysisWorkbook({ reportMonth }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "qdb-gl-monthly-analysis.workbook",
        { report_month: reportMonth, sheets: [] },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_qdb_gl_mock",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
        },
      );
    },
    async exportQdbGlMonthlyAnalysisWorkbookXlsx({ reportMonth }) {
      await delay();
      return {
        filename: `analysis_report_${reportMonth}.xlsx`,
        content: new Blob(["mock-qdb-workbook"], {
          type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }),
      };
    },
    async refreshQdbGlMonthlyAnalysis({ reportMonth }) {
      await delay();
      return {
        status: "completed",
        run_id: `qdb_gl_monthly_analysis:${reportMonth}`,
        job_name: "qdb_gl_monthly_analysis",
        trigger_mode: "sync",
        cache_key: "qdb_gl_monthly_analysis.analytical",
        report_month: reportMonth,
      };
    },
    async getQdbGlMonthlyAnalysisRefreshStatus(runId) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "qdb_gl_monthly_analysis",
        trigger_mode: "terminal",
        cache_key: "qdb_gl_monthly_analysis.analytical",
      };
    },
    async getQdbGlMonthlyAnalysisScenario({
      reportMonth,
      scenarioName,
      deviationWarn,
      deviationAlert,
      deviationCritical,
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "qdb-gl-monthly-analysis.scenario",
        {
          report_month: reportMonth,
          scenario_name: scenarioName,
          applied_overrides: {
            ...(deviationWarn === undefined ? {} : { DEVIATION_WARN: deviationWarn }),
            ...(deviationAlert === undefined ? {} : { DEVIATION_ALERT: deviationAlert }),
            ...(deviationCritical === undefined ? {} : { DEVIATION_CRITICAL: deviationCritical }),
          },
          sheets: [],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_qdb_gl_mock",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
        },
      );
    },
    async createQdbGlMonthlyAnalysisManualAdjustment(payload) {
      await delay();
      return {
        adjustment_id: "moa-mock-1",
        event_type: "created",
        created_at: "2026-04-12T00:00:00Z",
        stream: "monthly_operating_analysis_adjustments",
        ...payload,
      };
    },
    async updateQdbGlMonthlyAnalysisManualAdjustment(adjustmentId, payload) {
      await delay();
      return {
        adjustment_id: adjustmentId,
        event_type: "edited",
        created_at: "2026-04-12T00:10:00Z",
        stream: "monthly_operating_analysis_adjustments",
        ...payload,
      };
    },
    async revokeQdbGlMonthlyAnalysisManualAdjustment(adjustmentId) {
      await delay();
      return {
        adjustment_id: adjustmentId,
        event_type: "revoked",
        created_at: "2026-04-12T00:20:00Z",
        stream: "monthly_operating_analysis_adjustments",
        report_month: "202602",
        adjustment_class: "analysis_adjustment",
        target: {},
        operator: "OVERRIDE",
        value: "",
        approval_status: "rejected",
      };
    },
    async restoreQdbGlMonthlyAnalysisManualAdjustment(adjustmentId) {
      await delay();
      return {
        adjustment_id: adjustmentId,
        event_type: "restored",
        created_at: "2026-04-12T00:30:00Z",
        stream: "monthly_operating_analysis_adjustments",
        report_month: "202602",
        adjustment_class: "analysis_adjustment",
        target: {},
        operator: "OVERRIDE",
        value: "",
        approval_status: "approved",
      };
    },
    async getQdbGlMonthlyAnalysisManualAdjustments(reportMonth) {
      await delay();
      return {
        report_month: reportMonth,
        adjustment_count: 0,
        adjustments: [],
        events: [],
      };
    },
    async exportQdbGlMonthlyAnalysisManualAdjustmentsCsv(reportMonth) {
      await delay();
      return {
        filename: `monthly-operating-analysis-audit-${reportMonth}.csv`,
        content: "adjustment_id,event_type\n",
      };
    },
    ...createDemoBalanceAnalysisClient(delay, ensureMockClientBundle),
    ...createDemoPositionsClient(delay, ensureMockClientBundle),
    ...createDemoLiabilityAdbClient(delay, ensureMockClientBundle),
    async getCashflowProjection(reportDate: string) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "cashflow_projection.overview",
        {
          report_date: reportDate,
          duration_gap: formatRawAsNumeric({ raw: 1.25, unit: "ratio", sign_aware: true }),
          asset_duration: formatRawAsNumeric({ raw: 3.8, unit: "ratio", sign_aware: false }),
          liability_duration: formatRawAsNumeric({ raw: 2.55, unit: "ratio", sign_aware: false }),
          equity_duration: formatRawAsNumeric({ raw: 5.2, unit: "ratio", sign_aware: true }),
          rate_sensitivity_1bp: formatRawAsNumeric({ raw: 125_000, unit: "yuan", sign_aware: true }),
          reinvestment_risk_12m: formatRawAsNumeric({ raw: 0.185, unit: "pct", sign_aware: false }),
          monthly_buckets: [],
          top_maturing_assets_12m: [],
          warnings: [],
          computed_at: new Date().toISOString(),
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
  };

  if (mode === "mock") {
    void ensureMockClientBundle();
    return mockClient;
  }

  return {
    mode,
    ...createRealHealthClient({ fetchImpl, baseUrl }),
    ...createRealBalanceMovementClient({ fetchImpl, baseUrl }),
    ...createRealLedgerClient({ fetchImpl, baseUrl }),
    ...createRealMarketDataClient({ fetchImpl, baseUrl }),
    ...createRealMacroToolkitClient({ fetchImpl, baseUrl }),
    ...createRealKpiClient({ fetchImpl, baseUrl }),
    ...createRealCubeClient({ fetchImpl, baseUrl }),
    ...createRealPnlBusinessClient({ fetchImpl, baseUrl }),
    ...createRealAgentClient({ fetchImpl, baseUrl }),
    ...createRealExecutiveClient({
      fetchImpl,
      baseUrl,
      requestJson,
      getPlaceholderSnapshot: mockClient.getPlaceholderSnapshot,
    }),
    ...dashboardWorkbenchLiveEndpoints({ fetchImpl, baseUrl, requestJson }),
    ...bondDashboardLiveEndpoints({ fetchImpl, baseUrl, requestJson }),
    ...createRealBondAnalyticsClient({ fetchImpl, baseUrl, requestJson, requestActionJson }),
    ...createRealBondDashboardClient({ fetchImpl, baseUrl, requestJson }),
    getFormalPnlDates: (basis = "formal") =>
      requestJson<PnlDatesPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/dates${basis !== "formal" ? `?basis=${encodeURIComponent(basis)}` : ""}`,
      ),
    getFormalPnlData: (date: string, basis = "formal") =>
      requestJson<PnlDataPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/data?date=${encodeURIComponent(date)}${buildPnlBasisQuerySegment(basis)}`,
      ),
    getFormalPnlOverview: (reportDate: string, basis = "formal") =>
      requestJson<PnlOverviewPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/overview?report_date=${encodeURIComponent(reportDate)}${buildPnlBasisQuerySegment(basis)}`,
      ),
    getLedgerPnlDates: () =>
      requestJson<LedgerPnlDatesPayload>(fetchImpl, baseUrl, "/api/ledger-pnl/dates"),
    getLedgerPnlData: (reportDate: string, currency?: string) => {
      const params = new URLSearchParams({
        date: reportDate,
      });
      if (currency?.trim()) {
        params.set("currency", currency.trim());
      }
      return requestJson<LedgerPnlDataPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/data?${params.toString()}`,
      );
    },
    getLedgerPnlSummary: (reportDate: string, currency?: string) => {
      const params = new URLSearchParams({
        date: reportDate,
      });
      if (currency?.trim()) {
        params.set("currency", currency.trim());
      }
      return requestJson<LedgerPnlSummaryPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/summary?${params.toString()}`,
      );
    },
    getPnlBridge: (reportDate: string) =>
      requestJson<PnlBridgePayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/bridge?report_date=${encodeURIComponent(reportDate)}`,
      ),
    refreshFormalPnl: (reportDate?: string) =>
      requestActionJson<FormalPnlRefreshPayload>(
        fetchImpl,
        baseUrl,
        reportDate
          ? `/api/data/refresh_pnl?report_date=${encodeURIComponent(reportDate)}`
          : "/api/data/refresh_pnl",
        {
          method: "POST",
        },
      ),
    getFormalPnlImportStatus: (runId?: string) =>
      requestActionJson<FormalPnlRefreshPayload>(
        fetchImpl,
        baseUrl,
        runId
          ? `/api/data/import_status/pnl?run_id=${encodeURIComponent(runId)}`
          : "/api/data/import_status/pnl",
      ),
    getPnlAttribution: (reportDate?: string) =>
      requestJson<PnlAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/attribution${reportDate?.trim() ? `?report_date=${encodeURIComponent(reportDate.trim())}` : ""}`,
      ),
    getVolumeRateAttribution: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.compareType) {
        params.set("compare_type", options.compareType);
      }
      const q = params.toString();
      return requestJson<VolumeRateAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/volume-rate${q ? `?${q}` : ""}`,
      );
    },
    getTplMarketCorrelation: (options) => {
      const params = new URLSearchParams();
      if (options?.months !== undefined) {
        params.set("months", String(options.months));
      }
      const q = params.toString();
      return requestJson<TPLMarketCorrelationPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/tpl-market${q ? `?${q}` : ""}`,
      );
    },
    getPnlCompositionBreakdown: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.includeTrend === false) {
        params.set("include_trend", "false");
      }
      if (options?.trendMonths !== undefined) {
        params.set("trend_months", String(options.trendMonths));
      }
      const q = params.toString();
      return requestJson<PnlCompositionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/composition${q ? `?${q}` : ""}`,
      );
    },
    getPnlAttributionAnalysisSummary: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<PnlAttributionAnalysisSummary>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/summary${q ? `?${q}` : ""}`,
      );
    },
    getPnlCarryRollDown: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<CarryRollDownPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/carry-rolldown${q ? `?${q}` : ""}`,
      );
    },
    getPnlSpreadAttribution: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.lookbackDays !== undefined) {
        params.set("lookback_days", String(options.lookbackDays));
      }
      const q = params.toString();
      return requestJson<SpreadAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/spread${q ? `?${q}` : ""}`,
      );
    },
    getPnlKrdAttribution: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.lookbackDays !== undefined) {
        params.set("lookback_days", String(options.lookbackDays));
      }
      const q = params.toString();
      return requestJson<KRDAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/krd${q ? `?${q}` : ""}`,
      );
    },
    getPnlAdvancedAttributionSummary: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<AdvancedAttributionSummary>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/summary${q ? `?${q}` : ""}`,
      );
    },
    getPnlCampisiAttribution: (options) => {
      const q = buildCampisiQuery(options);
      return requestJson<CampisiAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/campisi${q}`,
      );
    },
    getPnlCampisiFourEffects: (options) =>
      requestJson<CampisiFourEffectsPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/campisi/four-effects${buildCampisiQuery(options)}`,
      ),
    getPnlCampisiEnhanced: (options) =>
      requestJson<CampisiEnhancedPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/campisi/enhanced${buildCampisiQuery(options)}`,
      ),
    getPnlCampisiMaturityBuckets: (options) =>
      requestJson<CampisiMaturityBucketsPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/campisi/maturity-buckets${buildCampisiQuery(options)}`,
      ),
    ...createRealPositionsClient({ fetchImpl, baseUrl, requestJson }),
    getCashflowProjection: (reportDate: string) =>
      requestJson<CashflowProjectionPayload>(
        fetchImpl,
        baseUrl,
        `/api/cashflow-projection?report_date=${encodeURIComponent(reportDate)}`,
      ),
    ...createRealLiabilityAdbClient({ fetchImpl, baseUrl, requestJson }),
    ...createRealProductCategoryClient({
      fetchImpl,
      baseUrl,
      requestJson,
      requestActionJson,
      requestText,
      requestActionWithBody,
    }),
    getQdbGlMonthlyAnalysisDates: () =>
      requestJson<QdbGlMonthlyAnalysisDatesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/qdb-gl-monthly-analysis/dates",
      ),
    getQdbGlMonthlyAnalysisWorkbook: ({ reportMonth }) =>
      requestJson<QdbGlMonthlyAnalysisWorkbookPayload>(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/workbook?report_month=${encodeURIComponent(reportMonth)}`,
      ),
    exportQdbGlMonthlyAnalysisWorkbookXlsx: ({ reportMonth }) =>
      requestBlob(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/workbook/export?report_month=${encodeURIComponent(reportMonth)}`,
        "qdb-gl-monthly-analysis.xlsx",
      ),
    refreshQdbGlMonthlyAnalysis: ({ reportMonth }) =>
      requestActionJson(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/refresh?report_month=${encodeURIComponent(reportMonth)}`,
        { method: "POST" },
      ),
    getQdbGlMonthlyAnalysisRefreshStatus: (runId) =>
      requestActionJson(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    getQdbGlMonthlyAnalysisScenario: ({
      reportMonth,
      scenarioName,
      deviationWarn,
      deviationAlert,
      deviationCritical,
    }) => {
      const params = new URLSearchParams({
        report_month: reportMonth,
        scenario_name: scenarioName,
      });
      if (isFiniteNumber(deviationWarn)) {
        params.set("deviation_warn", String(deviationWarn));
      }
      if (isFiniteNumber(deviationAlert)) {
        params.set("deviation_alert", String(deviationAlert));
      }
      if (isFiniteNumber(deviationCritical)) {
        params.set("deviation_critical", String(deviationCritical));
      }
      return requestJson(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/scenario?${params.toString()}`,
      );
    },
    createQdbGlMonthlyAnalysisManualAdjustment: (payload) =>
      requestActionWithBody(
        fetchImpl,
        baseUrl,
        "/ui/qdb-gl-monthly-analysis/manual-adjustments",
        payload,
      ),
    updateQdbGlMonthlyAnalysisManualAdjustment: (adjustmentId, payload) =>
      requestActionWithBody(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments/${encodeURIComponent(adjustmentId)}/edit`,
        payload,
      ),
    revokeQdbGlMonthlyAnalysisManualAdjustment: (adjustmentId) =>
      requestActionJson(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments/${encodeURIComponent(adjustmentId)}/revoke`,
        { method: "POST" },
      ),
    restoreQdbGlMonthlyAnalysisManualAdjustment: (adjustmentId) =>
      requestActionJson(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments/${encodeURIComponent(adjustmentId)}/restore`,
        { method: "POST" },
      ),
    getQdbGlMonthlyAnalysisManualAdjustments: (reportMonth) =>
      requestActionJson(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments?report_month=${encodeURIComponent(reportMonth)}`,
      ),
    exportQdbGlMonthlyAnalysisManualAdjustmentsCsv: (reportMonth) =>
      requestText(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments/export?report_month=${encodeURIComponent(reportMonth)}`,
        "monthly-operating-analysis-audit.csv",
      ),
    ...createRealBalanceAnalysisClient({
      fetchImpl,
      baseUrl,
      requestJson,
      requestActionJson,
      requestText,
      requestBlob,
    }),
  };
}
