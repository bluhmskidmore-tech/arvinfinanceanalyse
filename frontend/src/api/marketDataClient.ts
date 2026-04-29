import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroRecentPoint,
  ChoiceMacroRefreshPayload,
  ChoiceNewsEventsPayload,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  LivermoreStrategyPayload,
  MacroBondLinkagePayload,
  MacroVendorPayload,
  NcdFundingProxyPayload,
  SourcePreviewHistoryPayload,
  SourcePreviewPayload,
  SourcePreviewRefreshPayload,
  SourcePreviewRowsPayload,
  SourcePreviewTracesPayload,
} from "./contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { MOCK_CHOICE_MACRO_TUSHARE_EQUITY_SERIES } from "./marketDataMocks";

type FetchLike = typeof fetch;

type MarketDataClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

/**
 * Market Data domain methods. `client.ts` still owns source-preview, news, and
 * research-calendar composition, while this module owns the concrete market-data
 * analytical read endpoints and their mock/real factories.
 */
export type MarketDataClientMethods = {
  getSourceFoundation: () => Promise<ApiEnvelope<SourcePreviewPayload>>;
  refreshSourcePreview: () => Promise<SourcePreviewRefreshPayload>;
  getSourcePreviewRefreshStatus: (runId: string) => Promise<SourcePreviewRefreshPayload>;
  getSourceFoundationHistory: (options: {
    sourceFamily?: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewHistoryPayload>>;
  getSourceFoundationRows: (options: {
    sourceFamily: string;
    ingestBatchId: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewRowsPayload>>;
  getSourceFoundationTraces: (options: {
    sourceFamily: string;
    ingestBatchId: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewTracesPayload>>;
  getMacroFoundation: () => Promise<ApiEnvelope<MacroVendorPayload>>;
  getChoiceMacroLatest: () => Promise<ApiEnvelope<ChoiceMacroLatestPayload>>;
  getMacroBondLinkageAnalysis: (options: {
    reportDate: string;
  }) => Promise<ApiEnvelope<MacroBondLinkagePayload>>;
  getNcdFundingProxy: () => Promise<ApiEnvelope<NcdFundingProxyPayload>>;
  getFxFormalStatus: () => Promise<ApiEnvelope<FxFormalStatusPayload>>;
  getFxAnalytical: () => Promise<ApiEnvelope<FxAnalyticalPayload>>;
  refreshChoiceMacro: (backfillDays?: number) => Promise<ChoiceMacroRefreshPayload>;
  getChoiceMacroRefreshStatus: (runId: string) => Promise<ChoiceMacroRefreshPayload>;
  getLivermoreStrategy: (options?: {
    asOfDate?: string;
  }) => Promise<ApiEnvelope<LivermoreStrategyPayload>>;
  getChoiceNewsEvents: (options: {
    limit: number;
    offset: number;
    groupId?: string;
    topicCode?: string;
    errorOnly?: boolean;
    receivedFrom?: string;
    receivedTo?: string;
  }) => Promise<ApiEnvelope<ChoiceNewsEventsPayload>>;
  ingestTushareNprNews: (options?: { limit?: number }) => Promise<{
    status: string;
    inserted: number;
    skipped_duplicates: number;
    fetched: number;
    npr: { inserted: number; skipped_duplicates: number; fetched: number };
    news: { inserted: number; skipped_duplicates: number; fetched: number; src: string; error?: string };
  }>;
};

export type MarketDataDomainClientMethods = Pick<
  MarketDataClientMethods,
  | "getMacroFoundation"
  | "getChoiceMacroLatest"
  | "getMacroBondLinkageAnalysis"
  | "getNcdFundingProxy"
  | "getFxFormalStatus"
  | "getFxAnalytical"
  | "refreshChoiceMacro"
  | "getChoiceMacroRefreshStatus"
  | "getLivermoreStrategy"
>;

const delay = async () => new Promise((resolve) => setTimeout(resolve, 40));

function buildMockChoiceMacroRecentPoints(
  endDate: string,
  count: number,
  finalValue: number,
  amplitude: number,
): ChoiceMacroRecentPoint[] {
  const out: ChoiceMacroRecentPoint[] = [];
  for (let i = 0; i < count; i += 1) {
    const dayOffset = -(count - 1 - i);
    const date = new Date(`${endDate}T12:00:00Z`);
    date.setUTCDate(date.getUTCDate() + dayOffset);
    const tradeDate = date.toISOString().slice(0, 10);
    const t = count > 1 ? i / (count - 1) : 1;
    const wobble = Math.sin(i * 0.8 + amplitude) * amplitude * 0.15;
    const valueNumeric = Number((finalValue + (t - 1) * amplitude * 0.35 + wobble).toFixed(4));
    out.push({
      trade_date: tradeDate,
      value_numeric: valueNumeric,
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      quality_flag: "ok",
    });
  }
  if (out.length > 0) {
    out[out.length - 1] = {
      ...out[out.length - 1],
      value_numeric: finalValue,
    };
  }
  return out;
}

function buildMockNcdFundingProxyPayload(reportDate?: string): NcdFundingProxyPayload {
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

function buildMockLivermoreStrategyPayload(asOfDate?: string): LivermoreStrategyPayload {
  const resolvedDate = asOfDate?.trim() || "2026-04-29";
  return {
    as_of_date: resolvedDate,
    requested_as_of_date: asOfDate?.trim() || null,
    strategy_name: "Livermore A-Share Defended Trend",
    basis: "analytical",
    market_gate: {
      state: "WARM",
      exposure: 0.4,
      passed_conditions: 2,
      available_conditions: 2,
      required_conditions: 4,
      conditions: [
        {
          key: "csi300_close_gt_ma60",
          label: "CSI300 close > MA60",
          status: "pass",
          evidence: "Close is above MA60.",
          source_series_id: "CA.CSI300",
        },
        {
          key: "csi300_ma20_gt_ma60",
          label: "CSI300 MA20 > MA60",
          status: "pass",
          evidence: "MA20 is above MA60.",
          source_series_id: "CA.CSI300",
        },
        {
          key: "breadth_5d_positive",
          label: "5-day breadth > 0",
          status: "missing",
          evidence: "Breadth inputs are not landed for the Phase 1 slice.",
          source_series_id: null,
        },
        {
          key: "limit_up_quality_positive",
          label: "Limit-up seal/break quality positive",
          status: "missing",
          evidence: "Limit-up quality inputs are not landed for the Phase 1 slice.",
          source_series_id: null,
        },
      ],
    },
    rule_readiness: [
      {
        key: "market_gate",
        title: "Market gate",
        status: "partial",
        summary: "Trend-only market gate is available; breadth and limit-up quality remain missing.",
        required_inputs: ["broad_index_history", "breadth", "limit_up_quality"],
        missing_inputs: ["breadth", "limit_up_quality"],
      },
      {
        key: "sector_rank",
        title: "Sector ranking",
        status: "missing",
        summary: "Sector membership and sector-strength inputs are not landed yet.",
        required_inputs: ["sector_membership", "sector_strength"],
        missing_inputs: ["sector_membership", "sector_strength"],
      },
      {
        key: "stock_pivot",
        title: "Stock pivot filters",
        status: "blocked",
        summary: "Stock pivot output is blocked until sector rank and stock-universe inputs land.",
        required_inputs: ["stock_ohlcv", "stock_status", "sector_rank"],
        missing_inputs: ["stock_ohlcv", "stock_status", "sector_rank"],
      },
      {
        key: "risk_exit",
        title: "Risk and exit rules",
        status: "blocked",
        summary: "Risk and exit output is blocked until position and entry-cost inputs land.",
        required_inputs: ["positions", "entry_cost", "bars_since_entry"],
        missing_inputs: ["positions", "entry_cost", "bars_since_entry"],
      },
    ],
    diagnostics: [
      {
        severity: "warning",
        code: "LIVERMORE_BREADTH_MISSING",
        message: "Breadth inputs are unavailable; the market gate is capped at the trend-only slice.",
        input_family: "breadth",
      },
      {
        severity: "warning",
        code: "LIVERMORE_LIMIT_UP_QUALITY_MISSING",
        message: "Limit-up quality inputs are unavailable; the market gate is capped at the trend-only slice.",
        input_family: "limit_up_quality",
      },
      {
        severity: "warning",
        code: "LIVERMORE_SECTOR_INPUTS_MISSING",
        message: "Sector membership and sector-strength inputs are unavailable.",
        input_family: "sector_strength",
      },
      {
        severity: "warning",
        code: "LIVERMORE_STOCK_INPUTS_MISSING",
        message: "Stock-universe inputs are unavailable, so no candidates are produced.",
        input_family: "stock_universe",
      },
      {
        severity: "warning",
        code: "LIVERMORE_RISK_INPUTS_MISSING",
        message: "Position and entry-cost inputs are unavailable, so risk/exit output is blocked.",
        input_family: "position_risk",
      },
    ],
    data_gaps: [
      {
        input_family: "breadth",
        status: "missing",
        evidence: "5-day breadth input family is not landed in DuckDB for this slice.",
      },
      {
        input_family: "limit_up_quality",
        status: "missing",
        evidence: "Limit-up seal/break quality input family is not landed in DuckDB for this slice.",
      },
      {
        input_family: "sector_strength",
        status: "missing",
        evidence: "Sector membership and ranking inputs are not landed in DuckDB for this slice.",
      },
      {
        input_family: "stock_universe",
        status: "missing",
        evidence: "Stock OHLCV, status, and candidate-filter inputs are not landed in DuckDB for this slice.",
      },
      {
        input_family: "position_risk",
        status: "missing",
        evidence: "Position and entry-cost inputs are not landed in DuckDB for this slice.",
      },
    ],
    supported_outputs: ["market_gate"],
    unsupported_outputs: [
      {
        key: "sector_rank",
        reason: "Sector membership and sector-strength inputs are not landed yet.",
      },
      {
        key: "stock_candidates",
        reason: "Stock-level OHLCV, status, and candidate filters are not landed yet.",
      },
      {
        key: "risk_exit",
        reason: "Position and entry-cost inputs are not landed yet.",
      },
    ],
  };
}

const MOCK_MACRO_FOUNDATION_PAYLOAD: MacroVendorPayload = {
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

const MOCK_CHOICE_MACRO_LATEST_PAYLOAD: ChoiceMacroLatestPayload = {
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
      series_id: "EMM01843735",
      series_name: "China financial conditions index",
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
    ...MOCK_CHOICE_MACRO_TUSHARE_EQUITY_SERIES,
    {
      series_id: "CA.BRENT",
      series_name: "Brent crude oil futures close",
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
      series_name: "Rebar main contract settlement",
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
      series_name: "USD/CNY spot",
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

const MOCK_MACRO_BOND_LINKAGE_PAYLOAD: MacroBondLinkagePayload = {
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
  warnings: ["仅为分析信号，不要把估算影响当作正式归因。"],
  computed_at: "2026-04-13T00:00:00Z",
};

const MOCK_FX_FORMAL_STATUS_PAYLOAD: FxFormalStatusPayload = {
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

const MOCK_FX_ANALYTICAL_PAYLOAD: FxAnalyticalPayload = {
  read_target: "duckdb",
  groups: [
    {
      group_key: "middle_rate",
      title: "外汇分析：中间价",
      description: "目录观察到的中间价序列仍是分析视图，不重定义正式口径。",
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
          ],
        },
      ],
    },
    {
      group_key: "fx_index",
      title: "外汇分析：指数",
      description: "人民币指数和估算指数序列仅用于分析口径，不流入正式外汇。",
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
  ],
};

function buildLivermoreQuery(options?: { asOfDate?: string }) {
  const asOfDate = options?.asOfDate?.trim();
  if (!asOfDate) {
    return "";
  }
  return `?as_of_date=${encodeURIComponent(asOfDate)}`;
}

export function createMockMarketDataClient(): MarketDataDomainClientMethods {
  return {
    async getMacroFoundation() {
      await delay();
      return buildMockApiEnvelope("preview.macro-foundation", MOCK_MACRO_FOUNDATION_PAYLOAD, {
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "sv_macro_vendor_mock",
        vendor_version: "vv_choice_catalog_v1",
        rule_version: "rv_phase1_macro_vendor_v1",
        cache_version: "cv_phase1_macro_vendor_v1",
      });
    },
    async getChoiceMacroLatest() {
      await delay();
      return buildMockApiEnvelope("macro.choice.latest", MOCK_CHOICE_MACRO_LATEST_PAYLOAD, {
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "sv_choice_macro_mock",
        vendor_version: "vv_choice_macro_20260410",
        rule_version: "rv_choice_macro_thin_slice_v1",
        cache_version: "cv_choice_macro_thin_slice_v1",
      });
    },
    async getMacroBondLinkageAnalysis({ reportDate }) {
      await delay();
      return buildMockApiEnvelope(
        "macro_bond_linkage.analysis",
        { ...MOCK_MACRO_BOND_LINKAGE_PAYLOAD, report_date: reportDate },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_macro_bond_linkage_mock",
          vendor_version: "vv_choice_macro_mock",
          rule_version: "rv_macro_bond_linkage_v1",
          cache_version: "cv_macro_bond_linkage_v1",
          quality_flag: "warning",
        },
      );
    },
    async getNcdFundingProxy() {
      await delay();
      return buildMockApiEnvelope(
        "market_data.ncd_proxy",
        buildMockNcdFundingProxyPayload(),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_ncd_proxy_mock",
          vendor_version: "vv_tushare_shibor",
          rule_version: "rv_ncd_proxy_v1",
          cache_version: "cv_ncd_proxy_v1",
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      );
    },
    async getFxFormalStatus() {
      await delay();
      return buildMockApiEnvelope("fx.formal.status", MOCK_FX_FORMAL_STATUS_PAYLOAD, {
        basis: "formal",
        formal_use_allowed: true,
        source_version: "sv_fx_formal_mock",
        vendor_version: "vv_fx_formal_mock",
        rule_version: "rv_fx_formal_mid_v1",
        cache_version: "cv_fx_formal_mid_v1",
        quality_flag: "warning",
        vendor_status: "ok",
        fallback_mode: "latest_snapshot",
      });
    },
    async getFxAnalytical() {
      await delay();
      return buildMockApiEnvelope("fx.analytical.groups", MOCK_FX_ANALYTICAL_PAYLOAD, {
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "sv_fx_analytical_mock",
        vendor_version: "vv_fx_analytical_mock",
        rule_version: "rv_fx_analytical_v1",
        cache_version: "cv_fx_analytical_v1",
        quality_flag: "warning",
        vendor_status: "ok",
        fallback_mode: "latest_snapshot",
      });
    },
    async refreshChoiceMacro() {
      await delay();
      return {
        status: "completed",
        run_id: "choice_macro_refresh:mock-run",
      } as ChoiceMacroRefreshPayload;
    },
    async getChoiceMacroRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
      } as ChoiceMacroRefreshPayload;
    },
    async getLivermoreStrategy(options?: { asOfDate?: string }) {
      await delay();
      return buildMockApiEnvelope(
        "market_data.livermore",
        buildMockLivermoreStrategyPayload(options?.asOfDate),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_mock",
          vendor_version: "vv_livermore_mock",
          rule_version: "rv_livermore_market_gate_v1",
          cache_version: "cv_livermore_market_gate_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      );
    },
  };
}

export function createRealMarketDataClient({
  fetchImpl,
  baseUrl,
}: MarketDataClientFactoryOptions): MarketDataDomainClientMethods {
  return {
    getMacroFoundation: () =>
      requestJson<MacroVendorPayload>(fetchImpl, baseUrl, "/ui/preview/macro-foundation"),
    getChoiceMacroLatest: () =>
      requestJson<ChoiceMacroLatestPayload>(fetchImpl, baseUrl, "/ui/macro/choice-series/latest"),
    getMacroBondLinkageAnalysis: ({ reportDate }) =>
      requestJson<MacroBondLinkagePayload>(
        fetchImpl,
        baseUrl,
        `/api/macro-bond-linkage/analysis?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getNcdFundingProxy: () =>
      requestJson<NcdFundingProxyPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/ncd-funding-proxy",
      ),
    getFxFormalStatus: () =>
      requestJson<FxFormalStatusPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/fx/formal-status",
      ),
    getFxAnalytical: () =>
      requestJson<FxAnalyticalPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/fx/analytical",
      ),
    refreshChoiceMacro: (backfillDays?: number) => {
      const query = backfillDays ? `?backfill_days=${backfillDays}` : "";
      return requestActionJson<ChoiceMacroRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/macro/choice-series/refresh${query}`,
        { method: "POST" },
      );
    },
    getChoiceMacroRefreshStatus: (runId: string) =>
      requestActionJson<ChoiceMacroRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/macro/choice-series/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    getLivermoreStrategy: (options?: { asOfDate?: string }) =>
      requestJson<LivermoreStrategyPayload>(
        fetchImpl,
        baseUrl,
        `/ui/market-data/livermore${buildLivermoreQuery(options)}`,
      ),
  };
}

async function requestJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<TData>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<TData>;
}

async function requestActionJson<TResponse>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<TResponse> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as TResponse;
}
