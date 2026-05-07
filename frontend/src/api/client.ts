import {
  createContext,
  createElement,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

import type {
  AlertsPayload,
  ApiEnvelope,
  BalanceAnalysisCurrentUserPayload,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisDecisionStatusRecord,
  BalanceAnalysisOverviewPayload,
  BalanceAnalysisDatesPayload,
  BalanceCurrencyBasis,
  BalanceAnalysisAdvancedAttributionBundlePayload,
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisPayload,
  BalanceAnalysisWorkbookPayload,
  BalancePositionScope,
  BalanceAnalysisRefreshPayload,
  BondPositionItem,
  BondAnalyticsDatesPayload,
  BondAnalyticsRefreshPayload,
  BondPortfolioHeadlinesPayload,
  BondTopHoldingsPayload,
  YieldCurveTermStructurePayload,
  BenchmarkExcessPayload,
  BalanceAnalysisSummaryExportPayload,
  BalanceAnalysisSummaryTablePayload,
  AssetStructurePayload,
  BalanceAnalysisTableRow,
  BondDashboardHeadlinePayload,
  CreditSpreadAnalysisPayload,
  CreditSpreadMigrationPayload,
  ActionAttributionPayload,
  AccountingClassAuditPayload,
  AdvancedAttributionSummary,
  CampisiAttributionPayload,
  CampisiEnhancedPayload,
  CampisiFourEffectsPayload,
  CampisiMaturityBucketsPayload,
  CashflowProjectionPayload,
  CarryRollDownPayload,
  KRDCurveRiskPayload,
  KRDAttributionPayload,
  LedgerPnlDataPayload,
  LedgerPnlDatesPayload,
  LedgerPnlSummaryPayload,
  ChoiceMacroLatestPayload,
  ChoiceMacroRecentPoint,
  CockpitWarningsPayload,
  ContributionPayload,
  ContributionSplitPayload,
  CounterpartyStatsResponse,
  CustomerBalanceTrendResponse,
  AdbComparisonResponse,
  AdbAccountingBasisDailyAvgTrendItem,
  AdbMonthlyResponse,
  AdbCoveragePayload,
  AdbPayload,
  LiabilitiesMonthlyPayload,
  LiabilityCounterpartyPayload,
  LiabilityKnowledgeBriefPayload,
  LiabilityRiskBucketsPayload,
  LiabilityYieldMetricsPayload,
  YieldByPeriodPayload,
  CustomerBondDetailsResponse,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  FormalPnlRefreshPayload,
  GetHomeSnapshotOptions,
  HealthResponse,
  HealthStatusResponse,
  IndustryDistPayload,
  IndustryStatsResponse,
  InterbankCounterpartySplitResponse,
  InterbankPositionItem,

  MacroBondLinkagePayload,
  MacroVendorPayload,
  MaturityStructurePayload,
  NumericUnit,
  NcdFundingProxyPayload,
  PageResponse,
  OverviewPayload,
  PnlBridgePayload,
  PnlBasis,
  PnlDataPayload,
  PnlDatesPayload,
  PnlOverviewPayload,
  PositionDirection,
  ProductCategoryAttributionPayload,
  ProductCategoryDatesPayload,
  QdbGlMonthlyAnalysisDatesPayload,
  QdbGlMonthlyAnalysisWorkbookPayload,
  ProductCategoryManualAdjustmentListPayload,
  ProductCategoryManualAdjustmentPayload,
  ProductCategoryManualAdjustmentQuery,
  ProductCategoryManualAdjustmentRequest,
  ProductCategoryRefreshPayload,
  ProductCategoryPnlPayload,
  ProductTypesResponse,
  PnlAttributionPayload,
  PnlAttributionAnalysisSummary,
  PortfolioComparisonPayload,
  PnlCompositionPayload,
  ReturnDecompositionPayload,
  ResultMeta,
  RiskIndicatorsPayload,
  RatingStatsResponse,
  RiskOverviewPayload,
  RiskTensorDatesPayload,
  RiskTensorPayload,
  SpreadAnalysisPayload,
  SpreadAttributionPayload,
  SubTypesResponse,
  SummaryPayload,
  TPLMarketCorrelationPayload,
  YieldDistributionPayload,
  VolumeRateAttributionPayload,
} from "./contracts";
import { formatRawAsNumeric } from "../utils/format";
import type { BalanceAnalysisClientMethods } from "./balanceAnalysisClient";
import type { BondAnalyticsClientMethods } from "./bondAnalyticsClient";
import { mockBondAnalyticsYieldCurveTermStructure } from "./bondAnalyticsYieldCurveTermStructureMock";
import type { ExecutiveClientMethods } from "./executiveClient";
import { fetchHomeSnapshotEnvelope } from "./executiveHomeSnapshotFetch";
import type { MarketDataClientMethods } from "./marketDataClient";
import type { MacroToolkitClientMethods } from "./macroToolkitClient";
import {
  createMockPnlBusinessClient,
  createRealPnlBusinessClient,
  type PnlClientMethods,
} from "./pnlClient";
import type { PositionsClientMethods } from "./positionsClient";
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
  buildStableDemoAgentEnvelope,
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

// Re-export domain method types for consumers who want fine-grained imports
export type { BalanceAnalysisClientMethods } from "./balanceAnalysisClient";
export type { BondAnalyticsClientMethods } from "./bondAnalyticsClient";
export type { DashboardClientMethods } from "./workbenchDashboardApi";
export type { ExecutiveClientMethods } from "./executiveClient";
export type { MarketDataClientMethods } from "./marketDataClient";
export type { MacroToolkitClientMethods } from "./macroToolkitClient";
export type { PnlClientMethods } from "./pnlClient";
export type { PositionsClientMethods } from "./positionsClient";
export type { LedgerClientMethods } from "./ledgerClient";
export type { KpiClientMethods } from "./kpiClient";
export type { CubeClientMethods } from "./cubeClient";
export type { AgentClientMethods } from "./agentClient";

export type ApiClient = {
  mode: DataSourceMode;
} & ExecutiveClientMethods
  & DashboardClientMethods
  & PnlClientMethods
  & BalanceMovementClientMethods
  & BondAnalyticsClientMethods
  & BalanceAnalysisClientMethods
  & PositionsClientMethods
  & MarketDataClientMethods
  & MacroToolkitClientMethods
  & LedgerClientMethods
  & KpiClientMethods
  & CubeClientMethods
  & AgentClientMethods
  & {
  getHealthLive: () => Promise<HealthStatusResponse>;
  getHealthSummary: () => Promise<HealthStatusResponse>;
};

type ApiClientOptions = {
  mode?: DataSourceMode;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
};

type ApiClientProviderProps = {
  children: ReactNode;
  client?: ApiClient;
};

const defaultFetch = (...args: Parameters<typeof fetch>) => fetch(...args);

const delay = async () => new Promise((resolve) => setTimeout(resolve, 40));

type MockClientBundle = Pick<typeof import("../mocks/mockApiEnvelope"), "buildMockApiEnvelope"> & Pick<typeof import("../mocks/productCategoryPnl"), "buildMockProductCategoryPnlEnvelope" | "buildMockProductCategoryAttributionEnvelope"> & typeof import("../mocks/workbench") & typeof import("../mocks/pnlAttributionWorkbench") & typeof import("../mocks/campisiMocks") & typeof import("../mocks/ledgerPnlMocks");
let mockClientBundleCache: MockClientBundle | null = null;

async function loadMockClientBundle(): Promise<MockClientBundle> {
  const [apiEnvelopeModule, workbench, pnlAttribution, productCategory, campisi, ledgerPnl] =
    await Promise.all([
      import("../mocks/mockApiEnvelope"),
      import("../mocks/workbench"),
      import("../mocks/pnlAttributionWorkbench"),
      import("../mocks/productCategoryPnl"),
      import("../mocks/campisiMocks"),
      import("../mocks/ledgerPnlMocks"),
    ]);
  return {
    buildMockApiEnvelope: apiEnvelopeModule.buildMockApiEnvelope,
    buildMockProductCategoryPnlEnvelope: productCategory.buildMockProductCategoryPnlEnvelope,
    buildMockProductCategoryAttributionEnvelope:
      productCategory.buildMockProductCategoryAttributionEnvelope,
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

function reduceLatestManualAdjustments<
  T extends { adjustment_id: string; created_at: string }
>(records: T[]): T[] {
  const latestById = new Map<string, T>();
  for (const record of records) {
    const existing = latestById.get(record.adjustment_id);
    if (!existing || record.created_at >= existing.created_at) {
      latestById.set(record.adjustment_id, record);
    }
  }
  return Array.from(latestById.values());
}

function filterManualAdjustments<
  T extends {
    adjustment_id: string;
    created_at: string;
    account_code: string;
    approval_status: string;
    event_type: string;
  }
>(
  records: T[],
  options: ProductCategoryManualAdjustmentQuery = {},
  applyEventType = true,
): T[] {
  const adjustmentId = options.adjustmentId?.trim() ?? "";
  const adjustmentIdExact = options.adjustmentIdExact ?? false;
  const accountCode = options.accountCode?.trim() ?? "";
  const approvalStatus = options.approvalStatus?.trim() ?? "";
  const eventType = options.eventType?.trim() ?? "";
  const createdAtFrom = options.createdAtFrom?.trim() ?? "";
  const createdAtTo = options.createdAtTo?.trim() ?? "";

  return records.filter((record) => {
    if (adjustmentId) {
      if (adjustmentIdExact) {
        if (record.adjustment_id !== adjustmentId) {
          return false;
        }
      } else if (!record.adjustment_id.includes(adjustmentId)) {
        return false;
      }
    }
    if (accountCode && !record.account_code.includes(accountCode)) {
      return false;
    }
    if (approvalStatus && record.approval_status !== approvalStatus) {
      return false;
    }
    if (applyEventType && eventType && record.event_type !== eventType) {
      return false;
    }
    if (createdAtFrom && record.created_at < createdAtFrom) {
      return false;
    }
    if (createdAtTo && record.created_at > createdAtTo) {
      return false;
    }
    return true;
  });
}

function sortManualAdjustments<
  T extends {
    adjustment_id: string;
    created_at: string;
    account_code: string;
    approval_status: string;
    event_type: string;
  }
>(
  records: T[],
  field:
    | "created_at"
    | "adjustment_id"
    | "event_type"
    | "approval_status"
    | "account_code",
  direction: "asc" | "desc",
) {
  const sorted = [...records].sort((left, right) => {
    const leftValue = String(left[field] ?? "").toLowerCase();
    const rightValue = String(right[field] ?? "").toLowerCase();
    return leftValue.localeCompare(rightValue);
  });
  return direction === "desc" ? sorted.reverse() : sorted;
}

function buildManualAdjustmentSearchParams(
  reportDate: string,
  options: ProductCategoryManualAdjustmentQuery = {},
) {
  const params = new URLSearchParams({
    report_date: reportDate,
  });
  if (options.adjustmentId?.trim()) {
    params.set("adjustment_id", options.adjustmentId.trim());
  }
  if (options.adjustmentIdExact) {
    params.set("adjustment_id_exact", "true");
  }
  if (options.accountCode?.trim()) {
    params.set("account_code", options.accountCode.trim());
  }
  if (options.approvalStatus?.trim()) {
    params.set("approval_status", options.approvalStatus.trim());
  }
  if (options.eventType?.trim()) {
    params.set("event_type", options.eventType.trim());
  }
  if (options.currentSortField) {
    params.set("current_sort_field", options.currentSortField);
  }
  if (options.currentSortDir) {
    params.set("current_sort_dir", options.currentSortDir);
  }
  if (options.eventSortField) {
    params.set("event_sort_field", options.eventSortField);
  }
  if (options.eventSortDir) {
    params.set("event_sort_dir", options.eventSortDir);
  }
  if (options.createdAtFrom?.trim()) {
    params.set("created_at_from", options.createdAtFrom.trim());
  }
  if (options.createdAtTo?.trim()) {
    params.set("created_at_to", options.createdAtTo.trim());
  }
  if (options.adjustmentLimit !== undefined) {
    params.set("adjustment_limit", String(options.adjustmentLimit));
  }
  if (options.adjustmentOffset !== undefined) {
    params.set("adjustment_offset", String(options.adjustmentOffset));
  }
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (options.offset !== undefined) {
    params.set("offset", String(options.offset));
  }
  return params;
}

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

function buildBalanceAnalysisTableRows(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): BalanceAnalysisTableRow[] {
  const rows: BalanceAnalysisTableRow[] = [
    {
      row_key: "zqtz:240001.IB:portfolio-a:cc-1:CNY:asset:A:FVOCI",
      source_family: "zqtz",
      display_name: "240001.IB",
      owner_name: "利率债组合",
      category_name: "交易账户",
      position_scope: "asset",
      currency_basis: "CNY",
      invest_type_std: "A",
      accounting_basis: "FVOCI",
      detail_row_count: 3,
      market_value_amount: "72000000000.00",
      amortized_cost_amount: "64800000000.00",
      accrued_interest_amount: "3600000000.00",
    },
    {
      row_key: "tyw:repo-1:CNY:liability:H:AC",
      source_family: "tyw",
      display_name: "repo-1",
      owner_name: "同业负债池",
      category_name: "卖出回购",
      position_scope: "liability",
      currency_basis: "CNY",
      invest_type_std: "H",
      accounting_basis: "AC",
      detail_row_count: 1,
      market_value_amount: "7200000000.00",
      amortized_cost_amount: "7200000000.00",
      accrued_interest_amount: "1440000000.00",
    },
    {
      row_key: "zqtz:240002.IB:portfolio-b:cc-2:CNY:asset:H:AC",
      source_family: "zqtz",
      display_name: "240002.IB",
      owner_name: "高等级组合",
      category_name: "摊余成本",
      position_scope: "asset",
      currency_basis: "CNY",
      invest_type_std: "H",
      accounting_basis: "AC",
      detail_row_count: 2,
      market_value_amount: "41000000000.00",
      amortized_cost_amount: "40300000000.00",
      accrued_interest_amount: "2000000000.00",
    },
  ];
  return rows.filter((row) => {
    const matchesScope = positionScope === "all" || row.position_scope === positionScope;
    const matchesBasis = row.currency_basis === currencyBasis;
    return matchesScope && matchesBasis;
  });
}

type BalanceAnalysisAmountField =
  | "market_value_amount"
  | "amortized_cost_amount"
  | "accrued_interest_amount";

function parseBalanceAmount(raw: BalanceAnalysisTableRow[BalanceAnalysisAmountField]): number {
  const parsed = Number.parseFloat(String(raw));
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatBalanceAmountDecimal(value: number): string {
  return value.toFixed(2);
}

function sumBalanceAmount(
  rows: readonly BalanceAnalysisTableRow[],
  field: BalanceAnalysisAmountField,
): number {
  return rows.reduce((sum, row) => sum + parseBalanceAmount(row[field]), 0);
}

function divideBalanceAmount(
  row: BalanceAnalysisTableRow,
  field: BalanceAnalysisAmountField,
): string {
  const divisor = Math.max(1, row.detail_row_count);
  return formatBalanceAmountDecimal(parseBalanceAmount(row[field]) / divisor);
}

function buildBalanceAnalysisOverviewPayload(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): BalanceAnalysisOverviewPayload {
  const rows = buildBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
  const assetRows = rows.filter((row) => row.position_scope === "asset");
  const liabilityRows = rows.filter((row) => row.position_scope === "liability");
  return {
    report_date: reportDate,
    position_scope: positionScope,
    currency_basis: currencyBasis,
    detail_row_count: rows.reduce((sum, row) => sum + row.detail_row_count, 0),
    summary_row_count: rows.length,
    total_market_value_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(rows, "market_value_amount"),
    ),
    total_amortized_cost_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(rows, "amortized_cost_amount"),
    ),
    total_accrued_interest_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(rows, "accrued_interest_amount"),
    ),
    asset_total_market_value_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(assetRows, "market_value_amount"),
    ),
    liability_total_market_value_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(liabilityRows, "market_value_amount"),
    ),
    asset_total_amortized_cost_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(assetRows, "amortized_cost_amount"),
    ),
    liability_total_amortized_cost_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(liabilityRows, "amortized_cost_amount"),
    ),
    asset_total_accrued_interest_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(assetRows, "accrued_interest_amount"),
    ),
    liability_total_accrued_interest_amount: formatBalanceAmountDecimal(
      sumBalanceAmount(liabilityRows, "accrued_interest_amount"),
    ),
  };
}

function buildBalanceAnalysisDetailRows(
  reportDate: string,
  rows: readonly BalanceAnalysisTableRow[],
): BalanceAnalysisPayload["details"] {
  return rows.flatMap((row) => {
    const count = Math.max(1, row.detail_row_count);
    return Array.from({ length: count }, (_, index) => ({
      source_family: row.source_family,
      report_date: reportDate,
      row_key: `${row.row_key}:detail-${index + 1}`,
      display_name: count === 1 ? row.display_name : `${row.display_name} #${index + 1}`,
      position_scope: row.position_scope,
      currency_basis: row.currency_basis,
      invest_type_std: row.invest_type_std,
      accounting_basis: row.accounting_basis,
      market_value_amount: divideBalanceAmount(row, "market_value_amount"),
      amortized_cost_amount: divideBalanceAmount(row, "amortized_cost_amount"),
      accrued_interest_amount: divideBalanceAmount(row, "accrued_interest_amount"),
      is_issuance_like: row.source_family === "zqtz" ? false : null,
    }));
  });
}

function buildBalanceAnalysisDetailSummary(
  rows: readonly BalanceAnalysisTableRow[],
): BalanceAnalysisPayload["summary"] {
  return rows.map((row) => ({
    source_family: row.source_family,
    position_scope: row.position_scope,
    currency_basis: row.currency_basis,
    row_count: row.detail_row_count,
    market_value_amount: row.market_value_amount,
    amortized_cost_amount: row.amortized_cost_amount,
    accrued_interest_amount: row.accrued_interest_amount,
  }));
}

function buildBalanceAnalysisBasisRows(
  rows: readonly BalanceAnalysisTableRow[],
): BalanceAnalysisBasisBreakdownPayload["rows"] {
  return rows.map((row) => ({
    source_family: row.source_family,
    invest_type_std: row.invest_type_std,
    accounting_basis: row.accounting_basis,
    position_scope: row.position_scope,
    currency_basis: row.currency_basis,
    detail_row_count: row.detail_row_count,
    market_value_amount: row.market_value_amount,
    amortized_cost_amount: row.amortized_cost_amount,
    accrued_interest_amount: row.accrued_interest_amount,
  }));
}

async function buildMockBalanceAnalysisSummaryTable(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
  limit: number,
  offset: number,
): Promise<ApiEnvelope<BalanceAnalysisSummaryTablePayload>> {
  const rows = buildBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
  const wrap = (await import("../mocks/mockApiEnvelope")).buildMockApiEnvelope;
  return wrap(
    "balance-analysis.summary",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      limit,
      offset,
      total_rows: rows.length,
      rows: rows.slice(offset, offset + limit),
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

function buildMockBalanceAnalysisSummaryCsv(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): BalanceAnalysisSummaryExportPayload {
  const rows = buildBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
  const headers = [
    "row_key",
    "source_family",
    "display_name",
    "owner_name",
    "category_name",
    "position_scope",
    "currency_basis",
    "invest_type_std",
    "accounting_basis",
    "detail_row_count",
    "market_value_amount",
    "amortized_cost_amount",
    "accrued_interest_amount",
    "report_date",
    "source_version",
    "rule_version",
  ];
  const lines = rows.map((row) =>
    [
      row.row_key,
      row.source_family,
      row.display_name,
      row.owner_name,
      row.category_name,
      row.position_scope,
      row.currency_basis,
      row.invest_type_std,
      row.accounting_basis,
      String(row.detail_row_count),
      String(row.market_value_amount),
      String(row.amortized_cost_amount),
      String(row.accrued_interest_amount),
      reportDate,
      "sv_balance_mock",
      "rv_balance_analysis_formal_materialize_v1",
    ].join(","),
  );
  return {
    filename: `balance-analysis-summary-${reportDate}-${positionScope}-${currencyBasis}.csv`,
    content: [headers.join(","), ...lines].join("\n"),
  };
}

async function buildMockBalanceAnalysisWorkbook(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): Promise<ApiEnvelope<BalanceAnalysisWorkbookPayload>> {
  const wrap = (await import("../mocks/mockApiEnvelope")).buildMockApiEnvelope;
  return wrap(
    "balance-analysis.workbook",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      cards: [
        {
          key: "bond_assets_excluding_issue",
          label: "债券资产(剔除发行类)",
          value: "720.00",
          note: "ZQTZ 资产端剔除发行类后的余额。",
        },
        {
          key: "interbank_assets",
          label: "同业资产",
          value: "36.00",
          note: "TYW 资产端余额。",
        },
        {
          key: "interbank_liabilities",
          label: "同业负债",
          value: "72.00",
          note: "TYW 负债端余额。",
        },
        {
          key: "issuance_liabilities",
          label: "发行类负债",
          value: "18.00",
          note: "ZQTZ 发行类单列余额。",
        },
        {
          key: "net_position",
          label: "净头寸",
          value: "648.00",
          note: "资产端合计 - 同业负债。",
        },
      ],
      tables: [
        {
          key: "bond_business_types",
          title: "债券业务种类",
          section_kind: "table",
          columns: [
            { key: "bond_type", label: "业务种类" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              bond_type: "政策性金融债",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "maturity_gap",
          title: "期限缺口分析",
          section_kind: "table",
          columns: [
            { key: "bucket", label: "期限分类" },
            { key: "gap_amount", label: "缺口" },
          ],
          rows: [
            {
              bucket: "1-2年",
              gap_amount: "648.00",
            },
          ],
        },
        {
          key: "rating_analysis",
          title: "信用评级分析",
          section_kind: "table",
          columns: [
            { key: "rating", label: "评级" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              rating: "AAA",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "issuance_business_types",
          title: "发行类分析",
          section_kind: "table",
          columns: [
            { key: "bond_type", label: "业务种类" },
            { key: "balance_amount", label: "金额" },
          ],
          rows: [
            {
              bond_type: "同业存单",
              balance_amount: "180.00",
            },
          ],
        },
        {
          key: "industry_distribution",
          title: "行业分布",
          section_kind: "table",
          columns: [
            { key: "industry_name", label: "行业" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              industry_name: "金融业",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "rate_distribution",
          title: "利率分布分析",
          section_kind: "table",
          columns: [
            { key: "bucket", label: "利率区间" },
            { key: "bond_amount", label: "债券面值" },
            { key: "interbank_asset_amount", label: "同业资产" },
            { key: "interbank_liability_amount", label: "同业负债" },
          ],
          rows: [
            {
              bucket: "1.5%-2.0%",
              bond_amount: "9900.75",
              interbank_asset_amount: "958.00",
              interbank_liability_amount: "2206.08",
            },
          ],
        },
        {
          key: "counterparty_types",
          title: "对手方类型",
          section_kind: "table",
          columns: [
            { key: "counterparty_type", label: "对手方类型" },
            { key: "asset_amount", label: "资产金额" },
            { key: "liability_amount", label: "负债金额" },
            { key: "net_position_amount", label: "净头寸" },
          ],
          rows: [
            {
              counterparty_type: "股份制银行",
              asset_amount: "120.00",
              liability_amount: "86.08",
              net_position_amount: "33.92",
            },
          ],
        },
        {
          key: "interest_modes",
          title: "计息方式",
          section_kind: "table",
          columns: [
            { key: "interest_mode", label: "计息方式" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              interest_mode: "固定",
              balance_amount: "32874.42",
            },
          ],
        },
      ],
      operational_sections: [
        {
          key: "decision_items",
          title: "决策事项",
          section_kind: "decision_items",
          columns: [
            { key: "title", label: "标题" },
            { key: "action_label", label: "动作" },
            { key: "severity", label: "等级" },
            { key: "reason", label: "原因" },
          ],
          rows: [
            {
              title: "复核 1-2 年期限缺口配置",
              action_label: "复核缺口",
              severity: "high",
              reason: "期限桶缺口为 648.00 万元。",
              source_section: "期限缺口",
              rule_id: "bal_wb_decision_gap_001",
              rule_version: "v1",
            },
          ],
        },
        {
          key: "event_calendar",
          title: "事件日历",
          section_kind: "event_calendar",
          columns: [
            { key: "event_date", label: "事件日期" },
            { key: "event_type", label: "事件类型" },
            { key: "title", label: "标题" },
            { key: "impact_hint", label: "影响提示" },
          ],
          rows: [
            {
              event_date: "2026-01-31",
              event_type: "asset_maturity",
              title: "资产一到期",
              source: "内部治理日程",
              impact_hint: "资产账簿 / 拆放同业",
              source_section: "期限缺口",
            },
            {
              event_date: "2026-02-05",
              event_type: "funding_rollover",
              title: "回购一到期",
              source: "内部治理日程",
              impact_hint: "负债账簿 / 卖出回购",
              source_section: "期限缺口",
            },
          ],
        },
        {
          key: "risk_alerts",
          title: "风险预警",
          section_kind: "risk_alerts",
          columns: [
            { key: "title", label: "标题" },
            { key: "severity", label: "等级" },
            { key: "reason", label: "原因" },
          ],
          rows: [
            {
              title: "发行负债余额仍在账",
              severity: "medium",
              reason: "发行账簿合计 18.00 万元。",
              source_section: "发行类业务",
              rule_id: "bal_wb_risk_issuance_001",
              rule_version: "v1",
            },
            {
              title: "1-2 年期限桶为负缺口",
              severity: "high",
              reason: "缺口降至 -128.00 万元。",
              source_section: "期限缺口",
              rule_id: "bal_wb_risk_gap_001",
              rule_version: "v1",
            },
          ],
        },
      ],
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

async function buildMockBalanceAnalysisDecisionItems(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): Promise<ApiEnvelope<BalanceAnalysisDecisionItemsPayload>> {
  const wrap = (await import("../mocks/mockApiEnvelope")).buildMockApiEnvelope;
  return wrap(
    "balance-analysis.decision-items",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      columns: [
        { key: "title", label: "标题" },
        { key: "action_label", label: "动作" },
        { key: "severity", label: "等级" },
        { key: "reason", label: "原因" },
        { key: "source_section", label: "来源区块" },
        { key: "rule_id", label: "规则编号" },
        { key: "rule_version", label: "规则版本" },
      ],
      rows: [
        {
          decision_key: "bal_wb_decision_gap_001::maturity_gap::Review 1-2 year gap positioning",
          title: "复核 1-2 年期限缺口配置",
          action_label: "复核缺口",
          severity: "high",
          reason: "期限桶缺口为 648.00 万元。",
          source_section: "期限缺口",
          rule_id: "bal_wb_decision_gap_001",
          rule_version: "v1",
          latest_status: {
            decision_key:
              "bal_wb_decision_gap_001::maturity_gap::Review 1-2 year gap positioning",
            status: "pending",
            updated_at: null,
            updated_by: null,
            comment: null,
          },
        },
      ],
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

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

/** V1 风格：响应体即为业务 JSON，无 `ApiEnvelope` 包裹（负债结构等接口待迁移）。 */
const requestPlainJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
): Promise<T> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as T;
};

const requestEnvelopeOrPlainJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
): Promise<T> => {
  const payload = await requestPlainJson<Record<string, unknown>>(fetchImpl, baseUrl, path);
  if (
    payload &&
    typeof payload === "object" &&
    "result_meta" in payload &&
    "result" in payload
  ) {
    return payload.result as T;
  }
  return payload as T;
};

const requestEnvelopeOrPlainJsonWithMeta = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
): Promise<{ result: T; result_meta?: ResultMeta }> => {
  const payload = await requestPlainJson<Record<string, unknown>>(fetchImpl, baseUrl, path);
  if (
    payload &&
    typeof payload === "object" &&
    "result_meta" in payload &&
    "result" in payload
  ) {
    return {
      result: payload.result as T,
      result_meta: payload.result_meta as ResultMeta,
    };
  }
  return { result: payload as T };
};

function normalizeAccountingBasisTrendItem(item: unknown): AdbAccountingBasisDailyAvgTrendItem {
  const basis = item as Record<string, unknown>;
  const rows = Array.isArray(basis.rows) ? basis.rows : [];
  return {
    report_date: String(basis.report_date ?? ""),
    report_month: String(basis.report_month ?? String(basis.report_date ?? "").slice(0, 7)),
    currency_basis: String(basis.currency_basis ?? ""),
    daily_avg_total: Number(basis.daily_avg_total ?? 0),
    rows: rows.map((entry) => {
      const row = entry as Record<string, unknown>;
      return {
        basis_bucket: String(row.basis_bucket ?? ""),
        daily_avg_balance: Number(row.daily_avg_balance ?? 0),
        daily_avg_pct:
          row.daily_avg_pct === null || row.daily_avg_pct === undefined
            ? null
            : Number(row.daily_avg_pct),
        source_account_patterns: Array.isArray(row.source_account_patterns)
          ? row.source_account_patterns.map(String)
          : [],
      };
    }),
    accounting_controls: Array.isArray(basis.accounting_controls)
      ? basis.accounting_controls.map(String)
      : [],
    excluded_controls: Array.isArray(basis.excluded_controls)
      ? basis.excluded_controls.map(String)
      : [],
  };
}

function normalizeAdbComparisonResponse(
  raw: Record<string, unknown>,
  resultMeta?: ResultMeta,
): AdbComparisonResponse {
  const mapBreakdown = (items: unknown[]) =>
    items.map((item) => {
      const row = item as Record<string, unknown>;
      return {
        category: String(row.category ?? ""),
        spot_balance: Number(row.spot_balance ?? 0),
        avg_balance: Number(row.avg_balance ?? 0),
        proportion: Number(row.proportion ?? 0),
        weighted_rate:
          row.weighted_rate === null || row.weighted_rate === undefined
            ? null
            : Number(row.weighted_rate),
      };
    });

  const assetsBreakdown = mapBreakdown(
    Array.isArray(raw.assets_breakdown) ? raw.assets_breakdown : [],
  );
  const liabilitiesBreakdown = mapBreakdown(
    Array.isArray(raw.liabilities_breakdown) ? raw.liabilities_breakdown : [],
  );
  const accountingBasisRaw =
    raw.accounting_basis_daily_avg && typeof raw.accounting_basis_daily_avg === "object"
      ? (raw.accounting_basis_daily_avg as Record<string, unknown>)
      : null;
  const accountingBasisRows = accountingBasisRaw?.rows;

  return {
    result_meta: resultMeta,
    report_date: String(raw.report_date ?? raw.end_date ?? ""),
    start_date: String(raw.start_date ?? ""),
    end_date: String(raw.end_date ?? ""),
    calendar_days_inclusive: Number(raw.calendar_days_inclusive ?? raw.num_days ?? 0),
    adb_denominator_basis: String(raw.adb_denominator_basis ?? "snapshot_calendar") as
      | "formal_calendar"
      | "snapshot_distinct_days"
      | "snapshot_calendar"
      | "ledger_weighted",
    num_days: Number(raw.num_days ?? 0),
    coverage_days:
      raw.coverage_days === null || raw.coverage_days === undefined
        ? undefined
        : Number(raw.coverage_days),
    sample_filled: raw.sample_filled === true || raw.sample_filled === "true" ? true : undefined,
    sample_fill_method: raw.sample_fill_method ? String(raw.sample_fill_method) : undefined,
    simulated: Boolean(raw.simulated),
    total_spot_assets: Number(raw.total_spot_assets ?? 0),
    total_avg_assets: Number(raw.total_avg_assets ?? 0),
    total_spot_liabilities: Number(raw.total_spot_liabilities ?? 0),
    total_avg_liabilities: Number(raw.total_avg_liabilities ?? 0),
    total_avg_interbank_assets: Number(raw.total_avg_interbank_assets ?? 0),
    total_avg_interbank_liabilities: Number(raw.total_avg_interbank_liabilities ?? 0),
    asset_yield:
      raw.asset_yield === null || raw.asset_yield === undefined ? null : Number(raw.asset_yield),
    liability_cost:
      raw.liability_cost === null || raw.liability_cost === undefined
        ? null
        : Number(raw.liability_cost),
    net_interest_margin:
      raw.net_interest_margin === null || raw.net_interest_margin === undefined
        ? null
        : Number(raw.net_interest_margin),
    assets_breakdown: assetsBreakdown,
    liabilities_breakdown: liabilitiesBreakdown,
    accounting_basis_daily_avg: accountingBasisRaw
      ? {
          report_date: String(accountingBasisRaw.report_date ?? ""),
          currency_basis: String(accountingBasisRaw.currency_basis ?? ""),
          daily_avg_total: Number(accountingBasisRaw.daily_avg_total ?? 0),
          rows: (Array.isArray(accountingBasisRows) ? accountingBasisRows : []).map((item) => {
            const row = item as Record<string, unknown>;
            return {
              basis_bucket: String(row.basis_bucket ?? ""),
              daily_avg_balance: Number(row.daily_avg_balance ?? 0),
              daily_avg_pct:
                row.daily_avg_pct === null || row.daily_avg_pct === undefined
                  ? null
                  : Number(row.daily_avg_pct),
              source_account_patterns: Array.isArray(row.source_account_patterns)
                ? row.source_account_patterns.map(String)
                : [],
            };
          }),
          accounting_controls: Array.isArray(accountingBasisRaw.accounting_controls)
            ? accountingBasisRaw.accounting_controls.map(String)
            : [],
          excluded_controls: Array.isArray(accountingBasisRaw.excluded_controls)
            ? accountingBasisRaw.excluded_controls.map(String)
            : [],
        }
      : undefined,
    accounting_basis_daily_avg_trend: Array.isArray(raw.accounting_basis_daily_avg_trend)
      ? raw.accounting_basis_daily_avg_trend.map(normalizeAccountingBasisTrendItem)
      : undefined,
    detail: raw.detail ? String(raw.detail) : undefined,
  };
}

function normalizeAdbMonthlyResponse(
  raw: Record<string, unknown>,
  resultMeta?: ResultMeta,
): AdbMonthlyResponse {
  const months = Array.isArray(raw.months) ? raw.months : [];
  const accountingBasisTrend = Array.isArray(raw.accounting_basis_daily_avg_trend)
    ? raw.accounting_basis_daily_avg_trend
    : [];
  return {
    result_meta: resultMeta,
    year: Number(raw.year ?? 0),
    months: months.map((item) => {
      const row = item as Record<string, unknown>;
      const breakdownAssets = Array.isArray(row.breakdown_assets) ? row.breakdown_assets : [];
      const breakdownLiabilities = Array.isArray(row.breakdown_liabilities)
        ? row.breakdown_liabilities
        : [];
      const mapBreakdown = (entries: unknown[]) =>
        entries.map((entry) => {
          const breakdown = entry as Record<string, unknown>;
          return {
            category: String(breakdown.category ?? ""),
            avg_balance: Number(breakdown.avg_balance ?? 0),
            proportion:
              breakdown.proportion === null || breakdown.proportion === undefined
                ? null
                : Number(breakdown.proportion),
            weighted_rate:
              breakdown.weighted_rate === null || breakdown.weighted_rate === undefined
                ? null
                : Number(breakdown.weighted_rate),
          };
        });

      return {
        month: String(row.month ?? ""),
        month_label: String(row.month_label ?? row.month ?? ""),
        num_days: Number(row.num_days ?? 0),
        avg_assets: Number(row.avg_assets ?? 0),
        avg_liabilities: Number(row.avg_liabilities ?? 0),
        asset_yield:
          row.asset_yield === null || row.asset_yield === undefined
            ? null
            : Number(row.asset_yield),
        liability_cost:
          row.liability_cost === null || row.liability_cost === undefined
            ? null
            : Number(row.liability_cost),
        net_interest_margin:
          row.net_interest_margin === null || row.net_interest_margin === undefined
            ? null
            : Number(row.net_interest_margin),
        mom_change_assets:
          row.mom_change_assets === null || row.mom_change_assets === undefined
            ? null
            : Number(row.mom_change_assets),
        mom_change_pct_assets:
          row.mom_change_pct_assets === null || row.mom_change_pct_assets === undefined
            ? null
            : Number(row.mom_change_pct_assets),
        mom_change_liabilities:
          row.mom_change_liabilities === null || row.mom_change_liabilities === undefined
            ? null
            : Number(row.mom_change_liabilities),
        mom_change_pct_liabilities:
          row.mom_change_pct_liabilities === null || row.mom_change_pct_liabilities === undefined
            ? null
            : Number(row.mom_change_pct_liabilities),
        breakdown_assets: mapBreakdown(breakdownAssets),
        breakdown_liabilities: mapBreakdown(breakdownLiabilities),
      };
    }),
    accounting_basis_daily_avg_trend: accountingBasisTrend.map(normalizeAccountingBasisTrendItem),
    ytd_avg_assets: Number(raw.ytd_avg_assets ?? 0),
    ytd_avg_liabilities: Number(raw.ytd_avg_liabilities ?? 0),
    ytd_asset_yield:
      raw.ytd_asset_yield === null || raw.ytd_asset_yield === undefined
        ? null
        : Number(raw.ytd_asset_yield),
    ytd_liability_cost:
      raw.ytd_liability_cost === null || raw.ytd_liability_cost === undefined
        ? null
        : Number(raw.ytd_liability_cost),
    ytd_nim:
      raw.ytd_nim === null || raw.ytd_nim === undefined ? null : Number(raw.ytd_nim),
    unit: raw.unit ? String(raw.unit) : undefined,
  };
}

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
  const mockManualAdjustments: ProductCategoryManualAdjustmentPayload[] = [];
  let mockManualAdjustmentSeq = 0;

  const mockClient: ApiClient = {
    mode: "mock",
    ...createMockBalanceMovementClient(),
    ...createMockLedgerClient(),
    ...createMockMarketDataClient(),
    ...createMockMacroToolkitClient(),
    ...createMockKpiClient(),
    ...createMockCubeClient(),
    ...createMockPnlBusinessClient(),
    ...dashboardWorkbenchDemoEndpoints(delay, ensureMockClientBundle),
    ...bondDashboardDemoEndpoints(delay, ensureMockClientBundle),
    async getHealth() {
      await delay();
      return { status: "ok" };
    },
    async getHealthLive() {
      await delay();
      return { status: "ok" };
    },
    async getHealthSummary() {
      await delay();
      return { status: "ok" };
    },
    async queryAgent(_request) {
      await delay();
      return buildStableDemoAgentEnvelope();
    },
    async getOverview(_reportDate?: string) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("executive.overview", (await ensureMockClientBundle()).overviewPayload);
    },
    async getHomeSnapshot(_options?: GetHomeSnapshotOptions) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("home.snapshot", (await ensureMockClientBundle()).mockHomeSnapshot);
    },
    async getSummary() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("executive.summary", (await ensureMockClientBundle()).summaryPayload);
    },
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
    async getRiskOverview() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("executive.risk-overview", (await ensureMockClientBundle()).riskOverviewPayload);
    },
    async getRiskTensorDates() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "risk.tensor.dates",
        {
          report_dates: ["2026-02-28", "2026-01-31", "2025-12-31"],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getRiskTensor(reportDate: string) {
      await delay();
      const zero = "0.00000000";
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "risk.tensor",
        {
          report_date: reportDate,
          portfolio_dv01: zero,
          krd_1y: zero,
          krd_3y: zero,
          krd_5y: zero,
          krd_7y: zero,
          krd_10y: zero,
          krd_30y: zero,
          cs01: zero,
          portfolio_convexity: zero,
          portfolio_modified_duration: zero,
          issuer_concentration_hhi: zero,
          issuer_top5_weight: zero,
          liquidity_gap_30d: zero,
          liquidity_gap_90d: zero,
          liquidity_gap_30d_ratio: zero,
          total_market_value: zero,
          bond_count: 0,
          quality_flag: "ok",
          warnings: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getContribution() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("executive.contribution", (await ensureMockClientBundle()).contributionPayload);
    },
    async getAlerts() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope("executive.alerts", (await ensureMockClientBundle()).alertsPayload);
    },
    async getPlaceholderSnapshot(key: string) {
      await delay();
      const $m = await ensureMockClientBundle();
      return $m.buildMockApiEnvelope(
        `workbench.${key}`,
        $m.placeholderSnapshots[key] ?? $m.placeholderSnapshots.dashboard,
      );
    },
    async getProductCategoryDates() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "product_category_pnl.dates",
        {
          report_dates: ["2026-02-28", "2026-01-31"],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async refreshProductCategoryPnl() {
      await delay();
      return {
        status: "queued",
        run_id: "product_category_pnl:mock-run",
        job_name: "product_category_pnl",
        trigger_mode: "async",
        cache_key: "product_category_pnl.formal",
      };
    },
    async getProductCategoryRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "product_category_pnl",
        trigger_mode: "async",
        cache_key: "product_category_pnl.formal",
        month_count: 2,
        report_dates: ["2026-01-31", "2026-02-28"],
        rule_version: "rv_product_category_pnl_v1",
        source_version: "sv_mock_dashboard_v2",
      };
    },
    async createProductCategoryManualAdjustment(payload) {
      await delay();
      mockManualAdjustmentSeq += 1;
      const record = {
        adjustment_id: `pca-mock-${mockManualAdjustmentSeq}`,
        event_type: "created",
        created_at: "2026-04-10T09:30:00Z",
        stream: "product_category_pnl_adjustments",
        report_date: payload.report_date,
        operator: payload.operator,
        approval_status: payload.approval_status,
        account_code: payload.account_code,
        currency: payload.currency,
        account_name: payload.account_name ?? "",
        beginning_balance: payload.beginning_balance ?? null,
        ending_balance: payload.ending_balance ?? null,
        monthly_pnl: payload.monthly_pnl ?? null,
        daily_avg_balance: payload.daily_avg_balance ?? null,
        annual_avg_balance: payload.annual_avg_balance ?? null,
      };
      mockManualAdjustments.unshift(record);
      return record;
    },
    async getProductCategoryManualAdjustments(reportDate, options = {}) {
      await delay();
      const allEvents = mockManualAdjustments.filter(
        (item) => item.report_date === reportDate,
      );
      const events = sortManualAdjustments(
        filterManualAdjustments(allEvents, options, true),
        options.eventSortField ?? "created_at",
        options.eventSortDir ?? "desc",
      );
      const limit = options.limit ?? 20;
      const offset = options.offset ?? 0;
      const adjustmentLimit = options.adjustmentLimit ?? 20;
      const adjustmentOffset = options.adjustmentOffset ?? 0;
      const pagedEvents = events.slice(offset, offset + limit);
      const adjustments = sortManualAdjustments(
        filterManualAdjustments(reduceLatestManualAdjustments(allEvents), options, false),
        options.currentSortField ?? "created_at",
        options.currentSortDir ?? "desc",
      );
      return {
        report_date: reportDate,
        adjustment_count: adjustments.length,
        adjustment_limit: adjustmentLimit,
        adjustment_offset: adjustmentOffset,
        event_total: events.length,
        event_limit: limit,
        event_offset: offset,
        adjustments: adjustments.slice(
          adjustmentOffset,
          adjustmentOffset + adjustmentLimit,
        ),
        events: pagedEvents,
      };
    },
    async exportProductCategoryManualAdjustmentsCsv(reportDate, options = {}) {
      await delay();
      const allEvents = mockManualAdjustments.filter(
        (item) => item.report_date === reportDate,
      );
      const filteredEvents = sortManualAdjustments(
        filterManualAdjustments(allEvents, options, true),
        options.eventSortField ?? "created_at",
        options.eventSortDir ?? "desc",
      );
      const filteredAdjustments = sortManualAdjustments(
        filterManualAdjustments(reduceLatestManualAdjustments(allEvents), options, false),
        options.currentSortField ?? "created_at",
        options.currentSortDir ?? "desc",
      );
      const headers = [
        "adjustment_id",
        "event_type",
        "created_at",
        "report_date",
        "operator",
        "approval_status",
        "account_code",
        "currency",
        "account_name",
      ];
      const toCsv = (rows: ProductCategoryManualAdjustmentPayload[]) =>
        rows
          .map((row) =>
            headers
              .map((header) => {
                const value = String(
                  (row as Record<string, string | number | null | undefined>)[header] ?? "",
                ).replace(/"/g, '""');
                return `"${value}"`;
              })
              .join(","),
          )
          .join("\n");
      return {
        filename: `product-category-audit-${reportDate}.csv`,
        content: [
          "Current State",
          headers.join(","),
          toCsv(filteredAdjustments),
          "",
          "Event Timeline",
          headers.join(","),
          toCsv(filteredEvents),
        ].join("\n"),
      };
    },
    async updateProductCategoryManualAdjustment(adjustmentId, payload) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const updated = {
        ...mockManualAdjustments[index],
        ...payload,
        event_type: "edited",
        created_at: "2026-04-10T09:40:00Z",
      };
      mockManualAdjustments.unshift(updated);
      return updated;
    },
    async revokeProductCategoryManualAdjustment(adjustmentId) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const revoked = {
        ...mockManualAdjustments[index],
        event_type: "revoked",
        approval_status: "rejected",
        created_at: "2026-04-10T09:45:00Z",
      };
      mockManualAdjustments.unshift(revoked);
      return revoked;
    },
    async restoreProductCategoryManualAdjustment(adjustmentId) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const restored = {
        ...mockManualAdjustments[index],
        event_type: "restored",
        approval_status: "approved",
        created_at: "2026-04-10T09:50:00Z",
      };
      mockManualAdjustments.unshift(restored);
      return restored;
    },
    async getProductCategoryPnl(options) {
      await delay();
      return (await ensureMockClientBundle()).buildMockProductCategoryPnlEnvelope(options);
    },
    async getProductCategoryAttribution(options) {
      await delay();
      return (await ensureMockClientBundle()).buildMockProductCategoryAttributionEnvelope(options);
    },
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
    async getBalanceAnalysisDates() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "balance-analysis.dates",
        {
          report_dates: ["2025-12-31"],
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisOverview({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "balance-analysis.overview",
        buildBalanceAnalysisOverviewPayload(reportDate, positionScope, currencyBasis),
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisDetail({ reportDate, positionScope, currencyBasis }) {
      await delay();
      const rows = buildBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
      const baseDetails = buildBalanceAnalysisDetailRows(reportDate, rows);
      const summary = buildBalanceAnalysisDetailSummary(rows);
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "balance-analysis.detail",
        {
          report_date: reportDate,
          position_scope: positionScope,
          currency_basis: currencyBasis,
          details: baseDetails,
          summary,
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisSummaryByBasis({ reportDate, positionScope, currencyBasis }) {
      await delay();
      const rows = buildBalanceAnalysisBasisRows(
        buildBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis),
      );
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "balance-analysis.basis_breakdown",
        {
          report_date: reportDate,
          position_scope: positionScope,
          currency_basis: currencyBasis,
          rows,
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisAdvancedAttribution({ reportDate }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "balance-analysis.advanced_attribution_bundle",
        {
          report_date: reportDate,
          mode: "analytical",
          scenario_name: null,
          scenario_inputs: {},
          upstream_summaries: {},
          status: "not_ready",
          missing_inputs: ["phase3_yield_curves_aligned_to_instruments"],
          blocked_components: ["roll_down", "rate_effect"],
          warnings: [
            "债券分析三期：骑乘与利率效应需要三期曲线和交易数据",
            "资产负债高级归因包：状态未就绪；未返回归因数值",
          ],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          source_version: "sv_advanced_attribution_not_ready",
          rule_version: "rv_advanced_attribution_bundle_v0",
          cache_version: "cv_advanced_attribution_v0",
        },
      );
    },
    async getBalanceAnalysisSummary({ reportDate, positionScope, currencyBasis, limit, offset }) {
      await delay();
      return await buildMockBalanceAnalysisSummaryTable(
        reportDate,
        positionScope,
        currencyBasis,
        limit,
        offset,
      );
    },
    async getBalanceAnalysisWorkbook({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return await buildMockBalanceAnalysisWorkbook(reportDate, positionScope, currencyBasis);
    },
    async getBalanceAnalysisCurrentUser() {
      await delay();
      return {
        user_id: "phase1-dev-user",
        role: "admin",
        identity_source: "fallback",
      };
    },
    async getBalanceAnalysisDecisionItems({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return await buildMockBalanceAnalysisDecisionItems(reportDate, positionScope, currencyBasis);
    },
    async updateBalanceAnalysisDecisionStatus({
      decisionKey,
      status,
      comment,
    }) {
      await delay();
      return {
        decision_key: decisionKey,
        status,
        updated_at: "2026-04-12T08:00:00Z",
        updated_by: "phase1-dev-user",
        comment: comment ?? null,
      };
    },
    async exportBalanceAnalysisSummaryCsv({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return buildMockBalanceAnalysisSummaryCsv(reportDate, positionScope, currencyBasis);
    },
    async exportBalanceAnalysisWorkbookXlsx({ reportDate }) {
      await delay();
      return {
        filename: `资产负债分析_${reportDate}.xlsx`,
        content: new Blob(["mock-workbook"], {
          type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }),
      };
    },
    async refreshBalanceAnalysis(reportDate: string) {
      await delay();
      return {
        status: "queued",
        run_id: "balance_analysis_materialize:mock-run",
        job_name: "balance_analysis_materialize",
        trigger_mode: "async",
        cache_key: "balance_analysis:materialize:formal",
        report_date: reportDate,
      };
    },
    async getBalanceAnalysisRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "balance_analysis_materialize",
        trigger_mode: "terminal",
        cache_key: "balance_analysis:materialize:formal",
        report_date: "2025-12-31",
        source_version: "sv_balance_mock",
        rule_version: "rv_balance_analysis_formal_materialize_v1",
      };
    },
    async refreshBondAnalytics(reportDate: string) {
      await delay();
      return {
        status: "queued",
        run_id: "bond_analytics_refresh:mock-run",
        job_name: "bond_analytics_refresh",
        cache_key: "bond_analytics:materialize",
        report_date: reportDate,
      };
    },
    async getBondAnalyticsDates() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.dates",
        {
          report_dates: ["2026-03-31", "2026-02-28", "2025-12-31"],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondDashboardDates() {
      await delay();
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.dates",
          { report_dates: ["2026-03-31", "2026-02-28", "2025-12-31"] },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardHeadlineKpis(reportDate: string) {
      await delay();
      const zy = (raw: number, sign_aware = false) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware });
      const zp = (raw: number, sign_aware = true) => formatRawAsNumeric({ raw, unit: "pct", sign_aware });
      const zr = (raw: number, sign_aware = false) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware });
      const zd = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.headline_kpis",
          {
            report_date: reportDate,
            prev_report_date: "2026-02-28",
            kpis: {
              total_market_value: zy(328_709_000_000),
              unrealized_pnl: zy(1_850_000_000, true),
              weighted_ytm: zp(0.0285),
              weighted_duration: zr(3.45),
              weighted_coupon: zp(0.0312),
              credit_spread_median: zp(0.0085),
              total_dv01: zd(-125_430.5),
              bond_count: 428,
            },
            prev_kpis: {
              total_market_value: zy(320_000_000_000),
              unrealized_pnl: zy(1_600_000_000, true),
              weighted_ytm: zp(0.0281),
              weighted_duration: zr(3.52),
              weighted_coupon: zp(0.0308),
              credit_spread_median: zp(0.0089),
              total_dv01: zd(-128_900),
              bond_count: 415,
            },
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardAssetStructure(reportDate: string, groupBy: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.asset_structure",
          {
            report_date: reportDate,
            group_by: groupBy,
            total_market_value: zy(328_709_000_000),
            items: [
              {
                category: "政策性金融债",
                total_market_value: zy(98_500_000_000),
                bond_count: 42,
                percentage: zp(29.96428571),
              },
              {
                category: "地方政府债",
                total_market_value: zy(82_000_000_000),
                bond_count: 56,
                percentage: zp(24.94571429),
              },
              {
                category: "同业存单",
                total_market_value: zy(71_000_000_000),
                bond_count: 120,
                percentage: zp(21.6),
              },
              {
                category: "信用债-企业",
                total_market_value: zy(49_209_000_000),
                bond_count: 150,
                percentage: zp(14.97),
              },
              {
                category: "其他",
                total_market_value: zy(26_000_000_000),
                bond_count: 60,
                percentage: zp(7.91),
              },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardYieldDistribution(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: true });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.yield_distribution",
          {
            report_date: reportDate,
            weighted_ytm: zp(0.0285),
            items: [
              { yield_bucket: "<1.5%", total_market_value: zy(12_000_000_000), bond_count: 12 },
              { yield_bucket: "1.5%-2.0%", total_market_value: zy(45_000_000_000), bond_count: 88 },
              { yield_bucket: "2.0%-2.5%", total_market_value: zy(98_000_000_000), bond_count: 142 },
              { yield_bucket: "2.5%-3.0%", total_market_value: zy(110_000_000_000), bond_count: 118 },
              { yield_bucket: "3.0%-3.5%", total_market_value: zy(42_000_000_000), bond_count: 48 },
              { yield_bucket: "3.5%-4.0%", total_market_value: zy(15_000_000_000), bond_count: 15 },
              { yield_bucket: ">4.0%", total_market_value: zy(6_709_000_000), bond_count: 5 },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardPortfolioComparison(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: true });
      const zr = (raw: number) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
      const zd = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.portfolio_comparison",
          {
            report_date: reportDate,
            items: [
              {
                portfolio_name: "银行账户",
                total_market_value: zy(185_000_000_000),
                weighted_ytm: zp(0.0278),
                weighted_duration: zr(3.21),
                total_dv01: zd(-70_200),
                bond_count: 220,
              },
              {
                portfolio_name: "交易账户",
                total_market_value: zy(98_000_000_000),
                weighted_ytm: zp(0.0295),
                weighted_duration: zr(3.88),
                total_dv01: zd(-40_200),
                bond_count: 128,
              },
              {
                portfolio_name: "OCI 账户",
                total_market_value: zy(45_709_000_000),
                weighted_ytm: zp(0.0289),
                weighted_duration: zr(3.55),
                total_dv01: zd(-15_030.5),
                bond_count: 80,
              },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardSpreadAnalysis(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: true });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.spread_analysis",
          {
            report_date: reportDate,
            items: [
              {
                bond_type: "国债",
                median_yield: zp(0.0245),
                bond_count: 45,
                total_market_value: zy(52_000_000_000),
              },
              {
                bond_type: "政金债",
                median_yield: zp(0.0272),
                bond_count: 62,
                total_market_value: zy(78_000_000_000),
              },
              {
                bond_type: "企业债",
                median_yield: zp(0.0341),
                bond_count: 88,
                total_market_value: zy(91_000_000_000),
              },
              {
                bond_type: "NCD",
                median_yield: zp(0.0268),
                bond_count: 130,
                total_market_value: zy(87_000_000_000),
              },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardMaturityStructure(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.maturity_structure",
          {
            report_date: reportDate,
            total_market_value: zy(328_709_000_000),
            items: [
              { maturity_bucket: "7天内", total_market_value: zy(2_100_000_000), bond_count: 8, percentage: zp(0.63871429) },
              { maturity_bucket: "8-30天", total_market_value: zy(8_900_000_000), bond_count: 22, percentage: zp(2.707) },
              { maturity_bucket: "31-90天", total_market_value: zy(18_500_000_000), bond_count: 35, percentage: zp(5.62857143) },
              { maturity_bucket: "91天-1年", total_market_value: zy(62_000_000_000), bond_count: 90, percentage: zp(18.86285714) },
              { maturity_bucket: "1-3年", total_market_value: zy(128_000_000_000), bond_count: 145, percentage: zp(38.94285714) },
              { maturity_bucket: "3-5年", total_market_value: zy(72_000_000_000), bond_count: 78, percentage: zp(21.90428571) },
              { maturity_bucket: "5年以上", total_market_value: zy(55_209_000_000), bond_count: 50, percentage: zp(16.79571429) },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardIndustryDistribution(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.industry_distribution",
          {
            report_date: reportDate,
            items: [
              { industry_name: "银行", total_market_value: zy(82_000_000_000), bond_count: 95, percentage: zp(24.94571429) },
              { industry_name: "城投", total_market_value: zy(61_000_000_000), bond_count: 72, percentage: zp(18.55714286) },
              { industry_name: "交通运输", total_market_value: zy(48_000_000_000), bond_count: 48, percentage: zp(14.60428571) },
              { industry_name: "电力", total_market_value: zy(39_000_000_000), bond_count: 40, percentage: zp(11.86571429) },
              { industry_name: "房地产", total_market_value: zy(28_000_000_000), bond_count: 35, percentage: zp(8.51714286) },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardRiskIndicators(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zd = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });
      const zr = (raw: number) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.risk_indicators",
          {
            report_date: reportDate,
            total_market_value: zy(328_709_000_000),
            total_dv01: zd(-125_430.5),
            weighted_duration: zr(3.45),
            credit_ratio: zr(0.42),
            weighted_convexity: zr(0.085),
            total_spread_dv01: zd(-45_200),
            reinvestment_ratio_1y: zr(0.18),
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondAnalyticsReturnDecomposition(
      reportDate: string,
      periodType: string,
      _options?: { assetClass?: string; accountingClass?: string },
    ) {
      await delay();
      void _options;
      const zy = (sign_aware: boolean) => formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware });
      const zp = (sign_aware: boolean) => formatRawAsNumeric({ raw: 0, unit: "pct", sign_aware });
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.return_decomposition",
        {
          report_date: reportDate,
          period_type: periodType,
          period_start: reportDate,
          period_end: reportDate,
          carry: zy(true),
          roll_down: zy(true),
          rate_effect: zy(true),
          spread_effect: zy(true),
          trading: zy(true),
          fx_effect: zy(true),
          convexity_effect: zy(true),
          explained_pnl: zy(true),
          explained_pnl_accounting: zy(true),
          explained_pnl_economic: zy(true),
          oci_reserve_impact: zy(true),
          actual_pnl: zy(true),
          recon_error: zy(true),
          recon_error_pct: zp(true),
          by_asset_class: [],
          by_accounting_class: [],
          bond_details: [],
          bond_count: 0,
          total_market_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsBenchmarkExcess(
      reportDate: string,
      periodType: string,
      benchmarkId: string,
    ) {
      await delay();
      const zPct = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "pct", sign_aware: s });
      const zBp = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "bp", sign_aware: s });
      const zRatio = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "ratio", sign_aware: s });
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.benchmark_excess",
        {
          report_date: reportDate,
          period_type: periodType,
          period_start: reportDate,
          period_end: reportDate,
          portfolio_return: zPct(true),
          benchmark_return: zPct(true),
          excess_return: zBp(true),
          tracking_error: null,
          information_ratio: null,
          duration_effect: zBp(true),
          curve_effect: zBp(true),
          spread_effect: zBp(true),
          selection_effect: zBp(true),
          allocation_effect: zBp(true),
          explained_excess: zBp(true),
          recon_error: zBp(true),
          portfolio_duration: zRatio(false),
          benchmark_duration: zRatio(false),
          duration_diff: zRatio(true),
          excess_sources: [],
          benchmark_id: benchmarkId,
          benchmark_name: benchmarkId,
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsKrdCurveRisk(
      reportDate: string,
      _options?: { scenarioSet?: string },
    ) {
      await delay();
      void _options;
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.krd_curve_risk",
        {
          report_date: reportDate,
          portfolio_duration: formatRawAsNumeric({ raw: 3.8, unit: "ratio", sign_aware: false }),
          portfolio_modified_duration: formatRawAsNumeric({ raw: 3.6, unit: "ratio", sign_aware: false }),
          portfolio_dv01: formatRawAsNumeric({ raw: 120, unit: "dv01", sign_aware: false }),
          portfolio_convexity: formatRawAsNumeric({ raw: 0.8, unit: "ratio", sign_aware: false }),
          krd_buckets: [],
          scenarios: [],
          by_asset_class: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsActionAttribution(reportDate: string, periodType: string) {
      await delay();
      const zy = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: s });
      const zr = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "ratio", sign_aware: s });
      const zd = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: s });
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.action_attribution",
        {
          report_date: reportDate,
          period_type: periodType,
          period_start: reportDate,
          period_end: reportDate,
          total_actions: 0,
          total_pnl_from_actions: zy(true),
          by_action_type: [],
          action_details: [],
          period_start_duration: zr(false),
          period_end_duration: zr(false),
          duration_change_from_actions: zr(true),
          period_start_dv01: zd(false),
          period_end_dv01: zd(false),
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsAccountingClassAudit(reportDate: string) {
      await delay();
      const zm = () => formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false });
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.accounting_class_audit",
        {
          report_date: reportDate,
          total_positions: 0,
          total_market_value: zm(),
          distinct_asset_classes: 0,
          divergent_asset_classes: 0,
          divergent_position_count: 0,
          divergent_market_value: zm(),
          map_unclassified_asset_classes: 0,
          map_unclassified_position_count: 0,
          map_unclassified_market_value: zm(),
          rows: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsCreditSpreadMigration(
      reportDate: string,
      _options?: { spreadScenarios?: string },
    ) {
      await delay();
      void _options;
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.credit_spread_migration",
        {
          report_date: reportDate,
          credit_bond_count: 12,
          credit_market_value: formatRawAsNumeric({ raw: 1_500_000_000, unit: "yuan", sign_aware: false }),
          credit_weight: formatRawAsNumeric({ raw: 0.25, unit: "ratio", sign_aware: false }),
          spread_dv01: formatRawAsNumeric({ raw: 25_000, unit: "dv01", sign_aware: false }),
          weighted_avg_spread: formatRawAsNumeric({ raw: 80, unit: "bp", sign_aware: false }),
          weighted_avg_spread_duration: formatRawAsNumeric({ raw: 4.2, unit: "ratio", sign_aware: false }),
          spread_scenarios: [],
          migration_scenarios: [],
          oci_credit_exposure: formatRawAsNumeric({ raw: 800_000_000, unit: "yuan", sign_aware: false }),
          oci_spread_dv01: formatRawAsNumeric({ raw: 12_000, unit: "dv01", sign_aware: false }),
          oci_sensitivity_25bp: formatRawAsNumeric({ raw: -300_000, unit: "yuan", sign_aware: true }),
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsPortfolioHeadlines(reportDate: string) {
      await delay();
      const zy = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: s });
      const zPct = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "pct", sign_aware: s });
      const zRatio = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "ratio", sign_aware: s });
      const zDv = () => formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: false });
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.portfolio_headlines",
        {
          report_date: reportDate,
          total_market_value: zy(false),
          weighted_ytm: zPct(true),
          weighted_duration: zRatio(false),
          weighted_coupon: zPct(true),
          total_dv01: zDv(),
          bond_count: 0,
          credit_weight: zRatio(false),
          issuer_hhi: zRatio(false),
          issuer_top5_weight: zRatio(false),
          by_asset_class: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsTopHoldings(reportDate: string, topN = 20) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.top_holdings",
        {
          report_date: reportDate,
          top_n: topN,
          items: [],
          total_market_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsYieldCurveTermStructure(
      reportDate: string,
      _options?: { curveTypes?: string },
    ) {
      await delay();
      void _options;
      return mockBondAnalyticsYieldCurveTermStructure(reportDate);
    },
    async getCreditSpreadAnalysisDetail(reportDate: string) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "credit_spread_analysis.detail",
        {
          report_date: reportDate,
          credit_bond_count: 12,
          total_credit_market_value: "1500000000",
          weighted_avg_spread_bps: "80.00000000",
          spread_term_structure: [],
          top_spread_bonds: [],
          bottom_spread_bonds: [],
          historical_context: null,
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsBondSubTypes(_reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.bonds.sub_types",
        { sub_types: ["利率债", "信用债"] },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsBondsList(options: {
      reportDate?: string | null;
      subType?: string | null;
      page: number;
      pageSize: number;
      includeIssued?: boolean;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.bonds.list",
        {
          items: [],
          total: 0,
          page: options.page,
          page_size: options.pageSize,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCounterpartyBonds(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
      topN?: number;
      page?: number;
      pageSize?: number;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.counterparty.bonds",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
          total_weighted_rate: null,
          total_weighted_coupon_rate: null,
          total_customers: 0,
          cr10_ratio: "62.34%",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsInterbankProductTypes(_reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.interbank.product_types",
        { product_types: ["拆借", "存放"] },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsInterbankList(options: {
      reportDate?: string | null;
      productType?: string | null;
      direction?: PositionDirection | "ALL" | null;
      page: number;
      pageSize: number;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.interbank.list",
        {
          items: [],
          total: 0,
          page: options.page,
          page_size: options.pageSize,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCounterpartyInterbankSplit(options: {
      startDate: string;
      endDate: string;
      productType?: string | null;
      topN?: number;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.counterparty.interbank.split",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          asset_total_amount: "0",
          asset_total_avg_daily: "0",
          asset_total_weighted_rate: null,
          asset_customer_count: 0,
          liability_total_amount: "0",
          liability_total_avg_daily: "0",
          liability_total_weighted_rate: null,
          liability_customer_count: 0,
          asset_items: [],
          liability_items: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsStatsRating(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.stats.rating",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsStatsIndustry(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
      topN?: number;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.stats.industry",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCustomerDetails(options: {
      customerName: string;
      reportDate?: string | null;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.customer.details",
        {
          customer_name: options.customerName,
          report_date: options.reportDate ?? "",
          total_market_value: "0",
          bond_count: 0,
          items: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCustomerTrend(options: {
      customerName: string;
      endDate?: string | null;
      days?: number;
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "positions.customer.trend",
        {
          customer_name: options.customerName,
          start_date: options.endDate ?? "",
          end_date: options.endDate ?? "",
          days: options.days ?? 30,
          items: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
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
    async getLiabilityRiskBuckets(reportDate?: string | null) {
      await delay();
      return {
        report_date: reportDate?.trim() || "",
        liabilities_structure: [],
        liabilities_term_buckets: [],
        interbank_liabilities_structure: [],
        interbank_liabilities_term_buckets: [],
        issued_liabilities_structure: [],
        issued_liabilities_term_buckets: [],
      };
    },
    async getLiabilityYieldMetrics(reportDate?: string | null) {
      await delay();
      return {
        report_date: reportDate?.trim() || "",
        kpi: {
          asset_yield: null,
          liability_cost: null,
          market_liability_cost: null,
          nim: null,
        },
        history: [],
        scatter: [],
      };
    },
    async getYieldByPeriod(options: { year: number; periodType?: "monthly" | "quarterly" | "yearly" }) {
      await delay();
      const y = options.year;
      const pt = options.periodType ?? "monthly";
      return {
        year: y,
        period_type: pt,
        periods: [
          {
            period: `${y}-12`,
            period_type: pt,
            start_date: `${y}-12-01`,
            end_date: `${y}-12-31`,
            num_days: 31,
            total_avg_balance: 1_000_000_000,
            total_pnl: 1_300_000,
            overall_yield: 0.13,
            overall_annualized_yield: 1.53,
            weighted_portfolio_yield: 0.13,
            weighted_portfolio_annualized_yield: 1.53,
            items: [
              {
                business_type_primary: "政策性金融债",
                total_pnl: 1_300_000,
                scale_amount: 1_000_000_000,
                yield_pct: 0.13,
              },
            ],
          },
        ],
      };
    },
    async getLiabilityCounterparty(options: { reportDate?: string | null; topN?: number }) {
      await delay();
      return {
        report_date: options.reportDate?.trim() || "",
        total_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
        top_10: [],
        by_type: [],
      };
    },
    async getLiabilityKnowledgeBrief() {
      await delay();
      return {
        result_meta: {
          trace_id: "tr_liability_knowledge_mock",
          basis: "analytical",
          result_kind: "liability.page_knowledge",
          formal_use_allowed: false,
          source_version: "sv_liability_knowledge_mock",
          vendor_version: "vv_none",
          rule_version: "rv_liability_knowledge_v1",
          cache_version: "cv_liability_knowledge_v1",
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: new Date().toISOString(),
        },
        result: {
          page_id: "liability-analytics",
          available: false,
          vault_path: null,
          status_note: "mock-no-obsidian",
          notes: [],
        },
      };
    },
    async getCockpitWarnings(reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "liability.cockpit_warnings",
        {
          report_date: reportDate?.trim() || "",
          watch_items: [],
          alert_events: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getContributionSplit(reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "liability.contribution_split",
        {
          report_date: reportDate?.trim() || "",
          contributions: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getLiabilitiesMonthly(year: number) {
      await delay();
      return {
        year,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      };
    },
    async getLiabilityAdbMonthly(year: number) {
      await delay();
      return {
        year,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      };
    },
    async getAdb(_params: { startDate: string; endDate: string }) {
      await delay();
      return {
        summary: {
          total_avg_assets: 0,
          total_avg_liabilities: 0,
          end_spot_assets: 0,
          end_spot_liabilities: 0,
        },
        trend: [],
        breakdown: [],
      };
    },
    async getAdbComparison(_startDate: string, _endDate: string, _options?: { topN?: number }) {
      await delay();
      return {
        report_date: "",
        start_date: "",
        end_date: "",
        calendar_days_inclusive: 0,
        adb_denominator_basis: "snapshot_calendar" as const,
        num_days: 0,
        coverage_days: 0,
        simulated: false,
        total_spot_assets: 0,
        total_avg_assets: 0,
        total_spot_liabilities: 0,
        total_avg_liabilities: 0,
        total_avg_interbank_assets: 0,
        total_avg_interbank_liabilities: 0,
        asset_yield: null,
        liability_cost: null,
        net_interest_margin: null,
        assets_breakdown: [],
        liabilities_breakdown: [],
      };
    },
    async getAdbMonthly(year: number) {
      await delay();
      return {
        year,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      };
    },
    async getAdbCoverage(_startDate: string, _endDate: string) {
      await delay();
      return {
        start_date: _startDate,
        end_date: _endDate,
        calendar_days: 0,
        snapshot_tables: {},
        formal_tables: {},
        snapshot_date_count: 0,
        formal_date_count: 0,
        missing_dates: [],
        missing_count: 0,
        coverage_pct: 0,
      };
    },
    async getBondAnalyticsRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "bond_analytics_refresh",
        cache_key: "bond_analytics:materialize",
        report_date: "2025-12-31",
      };
    },

  };

  if (mode === "mock") {
    void ensureMockClientBundle();
    return mockClient;
  }

  return {
    mode,
    ...createRealBalanceMovementClient({ fetchImpl, baseUrl }),
    ...createRealLedgerClient({ fetchImpl, baseUrl }),
    ...createRealMarketDataClient({ fetchImpl, baseUrl }),
    ...createRealMacroToolkitClient({ fetchImpl, baseUrl }),
    ...createRealKpiClient({ fetchImpl, baseUrl }),
    ...createRealCubeClient({ fetchImpl, baseUrl }),
    ...createRealPnlBusinessClient({ fetchImpl, baseUrl }),
    ...createRealAgentClient({ fetchImpl, baseUrl }),
    ...dashboardWorkbenchLiveEndpoints({ fetchImpl, baseUrl, requestJson }),
    ...bondDashboardLiveEndpoints({ fetchImpl, baseUrl, requestJson }),
    async getHealth() {
      const response = await fetchImpl(`${baseUrl}/health/ready`, {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(`Request failed: /health/ready (${response.status})`);
      }

      return (await response.json()) as HealthResponse;
    },
    async getHealthLive() {
      const response = await fetchImpl(`${baseUrl}/health/live`, {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(`Request failed: /health/live (${response.status})`);
      }

      return (await response.json()) as HealthStatusResponse;
    },
    async getHealthSummary() {
      const response = await fetchImpl(`${baseUrl}/health`, {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(`Request failed: /health (${response.status})`);
      }

      return (await response.json()) as HealthStatusResponse;
    },
    getOverview: (reportDate?: string) =>
      requestJson<OverviewPayload>(
        fetchImpl,
        baseUrl,
        `/ui/home/overview${reportDate?.trim() ? `?report_date=${encodeURIComponent(reportDate.trim())}` : ""}`,
      ),
    getHomeSnapshot: (options?: GetHomeSnapshotOptions) =>
      fetchHomeSnapshotEnvelope(fetchImpl, baseUrl, options),
    getSummary: () =>
      requestJson<SummaryPayload>(fetchImpl, baseUrl, "/ui/home/summary"),
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
    getRiskOverview: () =>
      requestJson<RiskOverviewPayload>(
        fetchImpl,
        baseUrl,
        "/ui/risk/overview",
      ),
    getRiskTensorDates: () =>
      requestJson<RiskTensorDatesPayload>(
        fetchImpl,
        baseUrl,
        "/api/risk/tensor/dates",
      ),
    getRiskTensor: (reportDate: string) =>
      requestJson<RiskTensorPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/tensor?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondAnalyticsDates: () =>
      requestJson<BondAnalyticsDatesPayload>(
        fetchImpl,
        baseUrl,
        "/api/bond-analytics/dates",
      ),
    getBondDashboardDates: () =>
      requestJson<BondAnalyticsDatesPayload>(fetchImpl, baseUrl, "/api/bond-dashboard/dates"),
    getBondDashboardHeadlineKpis: (reportDate: string) =>
      requestJson<BondDashboardHeadlinePayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/headline-kpis?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondDashboardAssetStructure: (reportDate: string, groupBy: string) =>
      requestJson<AssetStructurePayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/asset-structure?report_date=${encodeURIComponent(reportDate)}&group_by=${encodeURIComponent(groupBy)}`,
      ),
    getBondDashboardYieldDistribution: (reportDate: string) =>
      requestJson<YieldDistributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/yield-distribution?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondDashboardPortfolioComparison: (reportDate: string) =>
      requestJson<PortfolioComparisonPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/portfolio-comparison?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondDashboardSpreadAnalysis: (reportDate: string) =>
      requestJson<SpreadAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/spread-analysis?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondDashboardMaturityStructure: (reportDate: string) =>
      requestJson<MaturityStructurePayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/maturity-structure?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondDashboardIndustryDistribution: (reportDate: string) =>
      requestJson<IndustryDistPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/industry-distribution?report_date=${encodeURIComponent(reportDate)}&top_n=10`,
      ),
    getBondDashboardRiskIndicators: (reportDate: string) =>
      requestJson<RiskIndicatorsPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/risk-indicators?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondAnalyticsReturnDecomposition: (
      reportDate: string,
      periodType: string,
      options?: { assetClass?: string; accountingClass?: string },
    ) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        period_type: periodType,
      });
      if (options?.assetClass) params.set("asset_class", options.assetClass);
      if (options?.accountingClass) params.set("accounting_class", options.accountingClass);
      return requestJson<ReturnDecompositionPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/return-decomposition?${params.toString()}`,
      );
    },
    getBondAnalyticsBenchmarkExcess: (
      reportDate: string,
      periodType: string,
      benchmarkId: string,
    ) =>
      requestJson<BenchmarkExcessPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/benchmark-excess?report_date=${encodeURIComponent(reportDate)}&period_type=${encodeURIComponent(periodType)}&benchmark_id=${encodeURIComponent(benchmarkId)}`,
      ),
    getBondAnalyticsKrdCurveRisk: (reportDate: string, options?: { scenarioSet?: string }) => {
      const params = new URLSearchParams({ report_date: reportDate });
      if (options?.scenarioSet) params.set("scenario_set", options.scenarioSet);
      return requestJson<KRDCurveRiskPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/krd-curve-risk?${params.toString()}`,
      );
    },
    getBondAnalyticsActionAttribution: (reportDate: string, periodType: string) =>
      requestJson<ActionAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/action-attribution?report_date=${encodeURIComponent(reportDate)}&period_type=${encodeURIComponent(periodType)}`,
      ),
    getBondAnalyticsAccountingClassAudit: (reportDate: string) =>
      requestJson<AccountingClassAuditPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/accounting-class-audit?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondAnalyticsCreditSpreadMigration: (
      reportDate: string,
      options?: { spreadScenarios?: string },
    ) => {
      const params = new URLSearchParams({ report_date: reportDate });
      if (options?.spreadScenarios) params.set("spread_scenarios", options.spreadScenarios);
      return requestJson<CreditSpreadMigrationPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/credit-spread-migration?${params.toString()}`,
      );
    },
    getBondAnalyticsPortfolioHeadlines: (reportDate: string) =>
      requestJson<BondPortfolioHeadlinesPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/portfolio-headlines?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondAnalyticsTopHoldings: (reportDate: string, topN = 20) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        top_n: String(topN),
      });
      return requestJson<BondTopHoldingsPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/top-holdings?${params.toString()}`,
      );
    },
    getBondAnalyticsYieldCurveTermStructure: (
      reportDate: string,
      options?: { curveTypes?: string },
    ) => {
      const params = new URLSearchParams({ report_date: reportDate });
      if (options?.curveTypes?.trim()) {
        params.set("curve_types", options.curveTypes.trim());
      }
      return requestJson<YieldCurveTermStructurePayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/yield-curve-term-structure?${params.toString()}`,
      );
    },
    getCreditSpreadAnalysisDetail: (reportDate: string) =>
      requestJson<CreditSpreadAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/api/credit-spread-analysis/detail?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getPositionsBondSubTypes: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<SubTypesResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/bonds/sub_types${q ? `?${q}` : ""}`,
      );
    },
    getPositionsBondsList: ({
      reportDate,
      subType,
      page,
      pageSize,
      includeIssued,
    }) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      if (includeIssued) {
        params.set("include_issued", "true");
      }
      return requestJson<PageResponse<BondPositionItem>>(
        fetchImpl,
        baseUrl,
        `/api/positions/bonds?${params.toString()}`,
      );
    },
    getPositionsCounterpartyBonds: ({
      startDate,
      endDate,
      subType,
      topN,
      page,
      pageSize,
    }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      params.set("page", String(page ?? 1));
      params.set("page_size", String(pageSize ?? 50));
      return requestJson<CounterpartyStatsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/counterparty/bonds?${params.toString()}`,
      );
    },
    getPositionsInterbankProductTypes: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<ProductTypesResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/interbank/product_types${q ? `?${q}` : ""}`,
      );
    },
    getPositionsInterbankList: ({
      reportDate,
      productType,
      direction,
      page,
      pageSize,
    }) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      if (productType?.trim()) {
        params.set("product_type", productType.trim());
      }
      if (direction && direction !== "ALL") {
        params.set("direction", direction);
      }
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      return requestJson<PageResponse<InterbankPositionItem>>(
        fetchImpl,
        baseUrl,
        `/api/positions/interbank?${params.toString()}`,
      );
    },
    getPositionsCounterpartyInterbankSplit: ({
      startDate,
      endDate,
      productType,
      topN,
    }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (productType?.trim()) {
        params.set("product_type", productType.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      return requestJson<InterbankCounterpartySplitResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/counterparty/interbank/split?${params.toString()}`,
      );
    },
    getPositionsStatsRating: ({ startDate, endDate, subType }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      return requestJson<RatingStatsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/stats/rating?${params.toString()}`,
      );
    },
    getPositionsStatsIndustry: ({ startDate, endDate, subType, topN }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      return requestJson<IndustryStatsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/stats/industry?${params.toString()}`,
      );
    },
    getPositionsCustomerDetails: ({ customerName, reportDate }) => {
      const params = new URLSearchParams({
        customer_name: customerName,
      });
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      return requestJson<CustomerBondDetailsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/customer/details?${params.toString()}`,
      );
    },
    getPositionsCustomerTrend: ({ customerName, endDate, days }) => {
      const params = new URLSearchParams({
        customer_name: customerName,
      });
      if (endDate?.trim()) {
        params.set("end_date", endDate.trim());
      }
      if (days !== undefined) {
        params.set("days", String(days));
      }
      return requestJson<CustomerBalanceTrendResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/customer/trend?${params.toString()}`,
      );
    },
    getCashflowProjection: (reportDate: string) =>
      requestJson<CashflowProjectionPayload>(
        fetchImpl,
        baseUrl,
        `/api/cashflow-projection?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getLiabilityRiskBuckets: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestEnvelopeOrPlainJson<LiabilityRiskBucketsPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/buckets${q ? `?${q}` : ""}`,
      );
    },
    getLiabilityYieldMetrics: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestEnvelopeOrPlainJson<LiabilityYieldMetricsPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/yield_metrics${q ? `?${q}` : ""}`,
      );
    },
    getYieldByPeriod: ({ year, periodType }) => {
      const params = new URLSearchParams();
      params.set("year", String(year));
      if (periodType) {
        params.set("period_type", periodType);
      }
      return requestEnvelopeOrPlainJson<YieldByPeriodPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/yield-by-period?${params.toString()}`,
      );
    },
    getLiabilityCounterparty: ({ reportDate, topN }) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      const q = params.toString();
      return requestEnvelopeOrPlainJson<LiabilityCounterpartyPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/liabilities/counterparty${q ? `?${q}` : ""}`,
      );
    },
    getLiabilityKnowledgeBrief: () =>
      requestJson<LiabilityKnowledgeBriefPayload>(
        fetchImpl,
        baseUrl,
        "/ui/liability/business-context",
      ),
    getCockpitWarnings: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<CockpitWarningsPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/liabilities/cockpit-warnings${q ? `?${q}` : ""}`,
      );
    },
    getContributionSplit: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<ContributionSplitPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/liabilities/contribution-split${q ? `?${q}` : ""}`,
      );
    },
    getLiabilitiesMonthly: (year) =>
      requestEnvelopeOrPlainJson<LiabilitiesMonthlyPayload>(
        fetchImpl,
        baseUrl,
        `/api/liabilities/monthly?year=${encodeURIComponent(String(year))}`,
      ),
    getLiabilityAdbMonthly: (year) =>
      requestEnvelopeOrPlainJson<AdbMonthlyResponse>(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/monthly?year=${encodeURIComponent(String(year))}`,
      ),
    getAdb: ({ startDate, endDate }) => {
      const params = new URLSearchParams();
      params.set("start_date", startDate.trim());
      params.set("end_date", endDate.trim());
      return requestEnvelopeOrPlainJson<AdbPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb?${params.toString()}`,
      );
    },
    getAdbComparison: async (startDate, endDate, options) => {
      const params = new URLSearchParams();
      params.set("start_date", startDate.trim());
      params.set("end_date", endDate.trim());
      const topN = options?.topN;
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      const { result, result_meta } = await requestEnvelopeOrPlainJsonWithMeta<
        Record<string, unknown>
      >(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/comparison?${params.toString()}`,
      );
      return normalizeAdbComparisonResponse(result, result_meta);
    },
    getAdbMonthly: async (year) => {
      const { result, result_meta } = await requestEnvelopeOrPlainJsonWithMeta<
        Record<string, unknown>
      >(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/monthly?year=${encodeURIComponent(String(year))}`,
      );
      return normalizeAdbMonthlyResponse(result, result_meta);
    },
    getAdbCoverage: (startDate, endDate) => {
      const params = new URLSearchParams();
      params.set("start_date", startDate.trim());
      params.set("end_date", endDate.trim());
      return requestPlainJson<AdbCoveragePayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/coverage?${params.toString()}`,
      );
    },
    getContribution: () =>
      requestJson<ContributionPayload>(
        fetchImpl,
        baseUrl,
        "/ui/home/contribution",
      ),
    getAlerts: () =>
      requestJson<AlertsPayload>(fetchImpl, baseUrl, "/ui/home/alerts"),
    getPlaceholderSnapshot: mockClient.getPlaceholderSnapshot,
    getProductCategoryDates: () =>
      requestJson<ProductCategoryDatesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/dates",
      ),
    refreshProductCategoryPnl: () =>
      requestActionJson<ProductCategoryRefreshPayload>(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/refresh",
        {
          method: "POST",
        },
      ),
    getProductCategoryRefreshStatus: (runId: string) =>
      requestActionJson<ProductCategoryRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    createProductCategoryManualAdjustment: (payload) =>
      requestActionWithBody<
        ProductCategoryManualAdjustmentPayload,
        ProductCategoryManualAdjustmentRequest
      >(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/manual-adjustments",
        payload,
      ),
    getProductCategoryManualAdjustments: (reportDate, options = {}) => {
      const params = buildManualAdjustmentSearchParams(reportDate, options);
      return requestActionJson<ProductCategoryManualAdjustmentListPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments?${params.toString()}`,
      );
    },
    exportProductCategoryManualAdjustmentsCsv: (reportDate, options = {}) => {
      const params = buildManualAdjustmentSearchParams(reportDate, options);
      return requestText(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/export?${params.toString()}`,
        "product-category-audit.csv",
      );
    },
    updateProductCategoryManualAdjustment: (adjustmentId, payload) =>
      requestActionWithBody<
        ProductCategoryManualAdjustmentPayload,
        ProductCategoryManualAdjustmentRequest
      >(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/edit`,
        payload,
      ),
    revokeProductCategoryManualAdjustment: (adjustmentId) =>
      requestActionJson<ProductCategoryManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/revoke`,
        {
          method: "POST",
        },
      ),
    restoreProductCategoryManualAdjustment: (adjustmentId) =>
      requestActionJson<ProductCategoryManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/restore`,
        {
          method: "POST",
        },
      ),
    getProductCategoryPnl: ({ reportDate, view, scenarioRatePct }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        view,
      });
      if (scenarioRatePct?.trim()) {
        params.set("scenario_rate_pct", scenarioRatePct);
      }
      return requestJson<ProductCategoryPnlPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category?${params.toString()}`,
      );
    },
    getProductCategoryAttribution: ({ reportDate, compare = "mom" }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        compare,
      });
      return requestJson<ProductCategoryAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/attribution?${params.toString()}`,
      );
    },
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
    getBalanceAnalysisDates: () =>
      requestJson<BalanceAnalysisDatesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/dates",
      ),
    getBalanceAnalysisOverview: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisOverviewPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/overview?${params.toString()}`,
      );
    },
    getBalanceAnalysisSummary: ({
      reportDate,
      positionScope,
      currencyBasis,
      limit,
      offset,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
        limit: String(limit),
        offset: String(offset),
      });
      return requestJson<BalanceAnalysisSummaryTablePayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/summary?${params.toString()}`,
      );
    },
    getBalanceAnalysisWorkbook: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisWorkbookPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/workbook?${params.toString()}`,
      );
    },
    getBalanceAnalysisCurrentUser: () =>
      requestActionJson<BalanceAnalysisCurrentUserPayload>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/current-user",
      ),
    getBalanceAnalysisDecisionItems: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisDecisionItemsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/decision-items?${params.toString()}`,
      );
    },
    updateBalanceAnalysisDecisionStatus: ({
      reportDate,
      positionScope,
      currencyBasis,
      decisionKey,
      status,
      comment,
    }) =>
      requestActionJson<BalanceAnalysisDecisionStatusRecord>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/decision-items/status",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            report_date: reportDate,
            position_scope: positionScope,
            currency_basis: currencyBasis,
            decision_key: decisionKey,
            status,
            comment,
          }),
        },
      ),
    getBalanceAnalysisDetail: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis?${params.toString()}`,
      );
    },
    getBalanceAnalysisSummaryByBasis: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisBasisBreakdownPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/summary-by-basis?${params.toString()}`,
      );
    },
    getBalanceAnalysisAdvancedAttribution: ({
      reportDate,
      scenarioName,
      treasuryShiftBp,
      spreadShiftBp,
    }) => {
      const params = new URLSearchParams({ report_date: reportDate });
      if (scenarioName) {
        params.set("scenario_name", scenarioName);
      }
      if (treasuryShiftBp !== undefined) {
        params.set("treasury_shift_bp", String(treasuryShiftBp));
      }
      if (spreadShiftBp !== undefined) {
        params.set("spread_shift_bp", String(spreadShiftBp));
      }
      return requestJson<BalanceAnalysisAdvancedAttributionBundlePayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/advanced-attribution?${params.toString()}`,
      );
    },
    exportBalanceAnalysisSummaryCsv: ({
      reportDate,
      positionScope,
      currencyBasis,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestText(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/summary/export?${params.toString()}`,
        "balance-analysis-summary.csv",
      );
    },
    exportBalanceAnalysisWorkbookXlsx: ({
      reportDate,
      positionScope,
      currencyBasis,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestBlob(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/workbook/export?${params.toString()}`,
        "balance-analysis-workbook.xlsx",
      );
    },
    refreshBalanceAnalysis: (reportDate: string) =>
      requestActionJson<BalanceAnalysisRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/refresh?report_date=${encodeURIComponent(reportDate)}`,
        {
          method: "POST",
        },
      ),
    getBalanceAnalysisRefreshStatus: (runId: string) =>
      requestActionJson<BalanceAnalysisRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    refreshBondAnalytics: (reportDate: string) =>
      requestActionJson<BondAnalyticsRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/refresh?report_date=${encodeURIComponent(reportDate)}`,
        {
          method: "POST",
        },
      ),
    getBondAnalyticsRefreshStatus: (runId: string) =>
      requestActionJson<BondAnalyticsRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),

  };
}

const ApiClientContext = createContext<ApiClient | null>(null);

export function ApiClientProvider({
  children,
  client,
}: ApiClientProviderProps) {
  const resolvedClient = useMemo(
    () => client ?? createApiClient(),
    [client],
  );

  return createElement(
    ApiClientContext.Provider,
    { value: resolvedClient },
    children,
  );
}

export function useApiClient(): ApiClient {
  const client = useContext(ApiClientContext);

  if (!client) {
    throw new Error("ApiClientProvider is missing");
  }

  return client;
}
