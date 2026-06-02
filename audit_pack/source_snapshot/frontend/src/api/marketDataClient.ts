import { readHttpJsonDetail } from "./httpResponseError";
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
  ResearchCalendarEvent,
  ResearchCalendarResultPayload,
  SourcePreviewColumn,
  SourcePreviewHistoryPayload,
  SourcePreviewPayload,
  SourcePreviewRefreshPayload,
  SourcePreviewRowsPayload,
  SourcePreviewSummary,
  SourcePreviewTracesPayload,
} from "./contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { mapResearchCalendarApiEvent } from "../lib/researchCalendarApiEvent";
import { MOCK_CHOICE_MACRO_TUSHARE_EQUITY_SERIES } from "./marketDataMocks";

type FetchLike = typeof fetch;

type MarketDataClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

/**
 * Market Data domain methods and their mock/real factories.
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
  getResearchCalendarEvents: (options?: {
    reportDate?: string;
    startDate?: string;
    endDate?: string;
  }) => Promise<ResearchCalendarEvent[]>;
};

export type MarketDataDomainClientMethods = MarketDataClientMethods;

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

const MOCK_SOURCE_FOUNDATION_SUMMARIES: SourcePreviewSummary[] = [
  {
    source_family: "tyw",
    report_date: "2025-12-31",
    source_file: "TYWLSHOW-20251231.xls",
    total_rows: 2395,
    manual_review_count: 18,
    source_version: "sv_mock_tyw_preview",
    rule_version: "rv_phase1_source_preview_v1",
    group_counts: {
      "回购类": 1060,
      "拆借类": 97,
      "存放类": 1238,
    },
  },
  {
    source_family: "zqtz",
    report_date: "2025-12-31",
    source_file: "ZQTZSHOW-20251231.xls",
    total_rows: 1724,
    manual_review_count: 0,
    source_version: "sv_mock_zqtz_preview",
    rule_version: "rv_phase1_source_preview_v1",
    group_counts: {
      "债券类": 1571,
      "基金类": 127,
      "特定目的载体及其他非标类": 26,
    },
  },
];

const MOCK_CHOICE_NEWS_EVENTS: ChoiceNewsEventsPayload["events"] = [
  {
    event_key: "ce_mock_001",
    received_at: "2026-04-10T09:01:00Z",
    group_id: "news_cmd1",
    content_type: "sectornews",
    serial_id: 1001,
    request_id: 501,
    error_code: 0,
    error_msg: "",
    topic_code: "S888010007API",
    item_index: 0,
    payload_text: "Macro data release calendar updated for CPI and industrial production.",
    payload_json: null,
  },
  {
    event_key: "ce_mock_002",
    received_at: "2026-04-10T08:58:00Z",
    group_id: "news_cmd1",
    content_type: "sectornews",
    serial_id: 1001,
    request_id: 501,
    error_code: 0,
    error_msg: "",
    topic_code: "C000003006",
    item_index: 0,
    payload_text: null,
    payload_json:
      "{\"headline\":\"Policy follow-up\",\"summary\":\"PBOC open-market operation commentary stream.\"}",
  },
  {
    event_key: "ce_mock_003",
    received_at: "2026-04-10T08:50:00Z",
    group_id: "news_cmd1",
    content_type: "sectornews",
    serial_id: 1002,
    request_id: 502,
    error_code: 101,
    error_msg: "vendor callback timeout",
    topic_code: "__callback__",
    item_index: -1,
    payload_text: null,
    payload_json: null,
  },
  {
    event_key: "ce_mock_ts_policy",
    received_at: "2026-04-21T15:00:00Z",
    group_id: "tushare_policy",
    content_type: "npr",
    serial_id: 2001,
    request_id: 601,
    error_code: 0,
    error_msg: "",
    topic_code: "tushare.npr",
    item_index: 0,
    payload_text: "【政策 mock】示例：宏观与监管要闻占位（本地 mock，非实时）。",
    payload_json: null,
  },
  {
    event_key: "ce_mock_ts_news",
    received_at: "2026-04-21T14:30:00Z",
    group_id: "tushare_news",
    content_type: "news",
    serial_id: 2002,
    request_id: 602,
    error_code: 0,
    error_msg: "",
    topic_code: "tushare.news",
    item_index: 0,
    payload_text: "【快讯 mock】示例：市场快讯占位。",
    payload_json: null,
  },
  {
    event_key: "ce_mock_ts_cctv",
    received_at: "2026-04-21T14:00:00Z",
    group_id: "tushare_cctv",
    content_type: "cctv_news",
    serial_id: 2003,
    request_id: 603,
    error_code: 0,
    error_msg: "",
    topic_code: "tushare.cctv",
    item_index: 0,
    payload_text: "【联播 mock】示例：新闻联播摘要占位。",
    payload_json: null,
  },
  {
    event_key: "ce_mock_ts_major",
    received_at: "2026-04-21T13:30:00Z",
    group_id: "tushare_major",
    content_type: "major_news",
    serial_id: 2004,
    request_id: 604,
    error_code: 0,
    error_msg: "",
    topic_code: "tushare.major",
    item_index: 0,
    payload_text: "【长篇 mock】示例：长篇报道占位。",
    payload_json: null,
  },
  {
    event_key: "ce_mock_ts_research",
    received_at: "2026-04-21T13:00:00Z",
    group_id: "tushare_research",
    content_type: "research_report",
    serial_id: 2005,
    request_id: 605,
    error_code: 0,
    error_msg: "",
    topic_code: "tushare.research",
    item_index: 0,
    payload_text: "【研报 mock】示例：研报标题与摘要占位。",
    payload_json: '{"title":"Mock 研报","abstr":"占位摘要","_url":"https://example.com/mock-report"}',
  },
];

function buildMockResearchCalendarEvents(reportDate?: string): ResearchCalendarEvent[] {
  const baseDate = reportDate?.trim() || "2026-04-18";
  return [
    {
      id: "rc_supply_001",
      date: baseDate,
      title: "国债净融资节奏",
      kind: "supply",
      severity: "low",
      amount_label: "净融资 180 亿元",
      note: "供给节奏",
    },
    {
      id: "rc_auction_002",
      date: baseDate,
      title: "政策性金融债招标",
      kind: "auction",
      severity: "high",
      amount_label: "420 亿元",
      issuer: "国开行",
    },
    {
      id: "rc_macro_003",
      date: baseDate,
      title: "CPI 数据公布",
      kind: "macro",
      severity: "medium",
      amount_label: "同比观察",
      note: "宏观数据",
    },
  ];
}

function buildMockSourcePreviewColumns(rows: Array<Record<string, unknown>>): SourcePreviewColumn[] {
  const firstRow = rows[0];
  if (!firstRow) {
    return [];
  }
  return Object.keys(firstRow).map((key) => ({
    key,
    label: buildMockSourcePreviewLabel(key),
    type: key === "row_locator" || key === "trace_step"
      ? "number"
      : key === "manual_review_needed"
        ? "boolean"
        : "string",
  }));
}

function buildMockSourcePreviewLabel(key: string) {
  const labels: Record<string, string> = {
    ingest_batch_id: "批次ID",
    row_locator: "行号",
    report_date: "报告日期",
    business_type_primary: "业务种类1",
    business_type_final: "业务种类2归类",
    asset_group: "资产分组",
    instrument_code: "债券代码",
    instrument_name: "债券名称",
    account_category: "账户类别",
    product_group: "产品分组",
    institution_category: "机构类型",
    special_nature: "特殊性质",
    counterparty_name: "对手方名称",
    investment_portfolio: "投资组合",
    manual_review_needed: "需人工复核",
    trace_step: "轨迹步骤",
    field_name: "字段名",
    field_value: "字段值",
    derived_label: "归类标签",
  };
  return labels[key] ?? key;
}

function buildMockChoiceNewsEnvelope(options: {
  limit: number;
  offset: number;
  groupId?: string;
  topicCode?: string;
  errorOnly?: boolean;
  receivedFrom?: string;
  receivedTo?: string;
}): ApiEnvelope<ChoiceNewsEventsPayload> {
  const filtered = MOCK_CHOICE_NEWS_EVENTS.filter((event) => {
    if (options.groupId?.trim() && event.group_id !== options.groupId.trim()) {
      return false;
    }
    if (options.topicCode?.trim() && event.topic_code !== options.topicCode.trim()) {
      return false;
    }
    if (options.errorOnly && event.error_code === 0) {
      return false;
    }
    if (options.receivedFrom?.trim() && event.received_at < options.receivedFrom.trim()) {
      return false;
    }
    if (options.receivedTo?.trim() && event.received_at > options.receivedTo.trim()) {
      return false;
    }
    return true;
  });

  return buildMockApiEnvelope("news.choice.latest", {
    total_rows: filtered.length,
    limit: options.limit,
    offset: options.offset,
    events: filtered.slice(options.offset, options.offset + options.limit),
  });
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
        status: "ready",
        summary: "Sector ranking is available from landed Choice sector inputs.",
        required_inputs: ["sector_membership", "sector_strength"],
        missing_inputs: [],
      },
      {
        key: "stock_pivot",
        title: "Stock pivot filters",
        status: "ready",
        summary: "Stock pivot candidate screening is available for landed Choice stock inputs.",
        required_inputs: [
          "stock_universe",
          "stock_ohlcv",
          "stock_status",
          "limit_up_quality",
          "sector_rank",
          "market_gate",
        ],
        missing_inputs: [],
      },
      {
        key: "risk_exit",
        title: "Risk and exit rules",
        status: "ready",
        summary: "Risk and exit output is available from landed position snapshots and close history.",
        required_inputs: ["positions", "entry_cost", "bars_since_entry", "close_history"],
        missing_inputs: [],
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
        code: "LIVERMORE_SECTOR_RANK_PROVISIONAL_FORMULA",
        message: "Sector rank currently uses the provisional percentile formula over pctchange, turn, and amplitude.",
        input_family: "sector_strength",
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
    ],
    supported_outputs: ["market_gate", "sector_rank", "stock_candidates", "risk_exit"],
    unsupported_outputs: [],
    sector_rank: {
      as_of_date: resolvedDate,
      formula_version: "rv_livermore_sector_rank_provisional_v1",
      is_provisional: true,
      sector_count: 3,
      excluded_constituent_count: 0,
      excluded_sector_count: 0,
      items: [
        {
          rank: 1,
          sector_code: "801001",
          sector_name: "AI",
          score: 1,
          avg_pctchange: 4.8,
          avg_turn: 3,
          avg_amplitude: 3.5,
          constituent_count: 12,
        },
        {
          rank: 2,
          sector_code: "801002",
          sector_name: "Bank",
          score: 0.74,
          avg_pctchange: 3.1,
          avg_turn: 2.2,
          avg_amplitude: 2.4,
          constituent_count: 10,
        },
      ],
    },
    stock_candidates: {
      as_of_date: resolvedDate,
      formula_version: "rv_livermore_stock_candidates_bundle_v1",
      market_state: "WARM",
      input_stock_count: 4,
      candidate_count: 2,
      excluded_stock_count: 2,
      insufficient_history_count: 0,
      items: [
        {
          rank: 1,
          stock_code: "000001.SZ",
          stock_name: "Alpha",
          sector_code: "801001",
          sector_name: "AI",
          sector_rank: 1,
          close: 21.9,
          breakout_level: 21.8,
          ma20: 21.05,
          ma60: 19.05,
          ma120: 16.05,
          close_strength: 0.833333,
          gap_norm: -0.114679,
          abnormal_turnover: 1.386294,
        },
        {
          rank: 2,
          stock_code: "000002.SZ",
          stock_name: "Beta",
          sector_code: "801002",
          sector_name: "Bank",
          sector_rank: 2,
          close: 19.52,
          breakout_level: 19.44,
          ma20: 18.76,
          ma60: 17.16,
          ma120: 14.76,
          close_strength: 0.78125,
          gap_norm: -0.098,
          abnormal_turnover: 1.417067,
        },
      ],
    },
    risk_exit: {
      as_of_date: resolvedDate,
      formula_version: "rv_livermore_risk_exit_ema10_mvp_v1",
      position_count: 2,
      signal_count: 1,
      excluded_position_count: 0,
      insufficient_history_count: 0,
      items: [
        {
          stock_code: "000001.SZ",
          stock_name: "Alpha",
          reason: "2d_below_ema10",
          entry_cost: 10.5,
          bars_since_entry: 6,
          latest_close: 9.1,
          latest_ema10: 10.2,
          prior_close: 9.8,
          prior_ema10: 10.4,
        },
      ],
    },
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

class ActionRequestError extends Error {
  readonly status: number;
  readonly runId?: string;
  readonly errorMessage?: string;
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
    const nested = detail as Record<string, unknown>;
    const nestedMsg = nested.error_message;
    if (typeof nestedMsg === "string" && nestedMsg.trim()) {
      return nestedMsg;
    }
    const nestedDetail = nested.detail;
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
    const joined = parts.filter((part) => part.trim()).join("; ");
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

export function createMockMarketDataClient(): MarketDataDomainClientMethods {
  return {
    async getSourceFoundation() {
      await delay();
      return buildMockApiEnvelope("preview.source-foundation", {
        sources: MOCK_SOURCE_FOUNDATION_SUMMARIES,
      });
    },
    async refreshSourcePreview() {
      await delay();
      return {
        status: "queued",
        run_id: "source_preview_refresh:mock-run",
        job_name: "source_preview_refresh",
        trigger_mode: "async",
        cache_key: "source_preview.foundation",
        preview_sources: ["zqtz", "tyw"],
      };
    },
    async getSourcePreviewRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "source_preview_refresh",
        trigger_mode: "terminal",
        cache_key: "source_preview.foundation",
        preview_sources: ["zqtz", "tyw"],
        ingest_batch_id: "ib_mock_preview",
        source_version: "sv_mock_preview_refresh",
      };
    },
    async getSourceFoundationHistory({ sourceFamily, limit, offset }) {
      await delay();
      const rows = sourceFamily
        ? MOCK_SOURCE_FOUNDATION_SUMMARIES.filter(
            (summary) => summary.source_family === sourceFamily,
          )
        : MOCK_SOURCE_FOUNDATION_SUMMARIES;
      return buildMockApiEnvelope("preview.source-foundation.history", {
        limit,
        offset,
        total_rows: rows.length,
        rows: rows.slice(offset, offset + limit),
      });
    },
    async getSourceFoundationRows({ sourceFamily, ingestBatchId, limit, offset }) {
      await delay();
      const rows =
        sourceFamily === "zqtz"
          ? [
              {
                ingest_batch_id: ingestBatchId,
                row_locator: 1,
                report_date: "2025-12-31",
                business_type_primary: "其他债券",
                business_type_final: "公募基金",
                asset_group: "基金类",
                instrument_code: "SA0001",
                instrument_name: "MOCK-ZQTZ",
                account_category: "银行账户",
                manual_review_needed: false,
              },
            ]
          : [
              {
                ingest_batch_id: ingestBatchId,
                row_locator: 1,
                report_date: "2025-12-31",
                business_type_primary: "同业拆入",
                product_group: "拆借类",
                institution_category: "bank",
                special_nature: "普通",
                counterparty_name: "MOCK-TYW",
                investment_portfolio: "拆借自营",
                manual_review_needed: false,
              },
            ];
      return buildMockApiEnvelope(`preview.${sourceFamily}.rows`, {
        source_family: sourceFamily,
        ingest_batch_id: ingestBatchId,
        limit,
        offset,
        total_rows: rows.length,
        columns: buildMockSourcePreviewColumns(rows),
        rows,
      });
    },
    async getSourceFoundationTraces({ sourceFamily, ingestBatchId, limit, offset }) {
      await delay();
      const rows = [
        {
          ingest_batch_id: ingestBatchId,
          row_locator: 1,
          trace_step: 1,
          field_name: sourceFamily === "zqtz" ? "业务种类1" : "产品类型",
          field_value: sourceFamily === "zqtz" ? "其他债券" : "同业拆入",
          derived_label: sourceFamily === "zqtz" ? "公募基金" : "拆借类",
          manual_review_needed: false,
        },
      ];
      return buildMockApiEnvelope(`preview.${sourceFamily}.traces`, {
        source_family: sourceFamily,
        ingest_batch_id: ingestBatchId,
        limit,
        offset,
        total_rows: rows.length,
        columns: buildMockSourcePreviewColumns(rows),
        rows,
      });
    },
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
    async getChoiceNewsEvents(options) {
      await delay();
      return buildMockChoiceNewsEnvelope(options);
    },
    async getResearchCalendarEvents(options) {
      await delay();
      return buildMockResearchCalendarEvents(
        options?.startDate ?? options?.reportDate ?? options?.endDate,
      );
    },
    async ingestTushareNprNews(_options?: { limit?: number }) {
      await delay();
      return {
        status: "completed",
        inserted: 0,
        skipped_duplicates: 0,
        fetched: 0,
        npr: { inserted: 0, skipped_duplicates: 0, fetched: 0 },
        news: { inserted: 0, skipped_duplicates: 0, fetched: 0, src: "mock" },
      };
    },
  };
}

export function createRealMarketDataClient({
  fetchImpl,
  baseUrl,
}: MarketDataClientFactoryOptions): MarketDataDomainClientMethods {
  return {
    getSourceFoundation: () =>
      requestJson<SourcePreviewPayload>(
        fetchImpl,
        baseUrl,
        "/ui/preview/source-foundation",
      ),
    refreshSourcePreview: () =>
      requestActionJson<SourcePreviewRefreshPayload>(
        fetchImpl,
        baseUrl,
        "/ui/preview/source-foundation/refresh",
        {
          method: "POST",
        },
      ),
    getSourcePreviewRefreshStatus: (runId: string) =>
      requestActionJson<SourcePreviewRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    getSourceFoundationHistory: ({ sourceFamily, limit, offset }) => {
      const params = new URLSearchParams();
      if (sourceFamily?.trim()) {
        params.set("source_family", sourceFamily);
      }
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      return requestJson<SourcePreviewHistoryPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/history?${params.toString()}`,
      );
    },
    getSourceFoundationRows: ({ sourceFamily, ingestBatchId, limit, offset }) =>
      requestJson<SourcePreviewRowsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/${encodeURIComponent(sourceFamily)}/rows?ingest_batch_id=${encodeURIComponent(ingestBatchId)}&limit=${limit}&offset=${offset}`,
      ),
    getSourceFoundationTraces: ({ sourceFamily, ingestBatchId, limit, offset }) =>
      requestJson<SourcePreviewTracesPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/${encodeURIComponent(sourceFamily)}/traces?ingest_batch_id=${encodeURIComponent(ingestBatchId)}&limit=${limit}&offset=${offset}`,
      ),
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
    getChoiceNewsEvents: ({
      limit,
      offset,
      groupId,
      topicCode,
      errorOnly,
      receivedFrom,
      receivedTo,
    }) => {
      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      if (groupId?.trim()) {
        params.set("group_id", groupId.trim());
      }
      if (topicCode?.trim()) {
        params.set("topic_code", topicCode.trim());
      }
      if (errorOnly) {
        params.set("error_only", "true");
      }
      if (receivedFrom?.trim()) {
        params.set("received_from", receivedFrom.trim());
      }
      if (receivedTo?.trim()) {
        params.set("received_to", receivedTo.trim());
      }
      return requestJson<ChoiceNewsEventsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/news/choice-events/latest?${params.toString()}`,
      );
    },
    getResearchCalendarEvents: (options) => {
      const params = new URLSearchParams();
      if (options?.startDate?.trim()) {
        params.set("start_date", options.startDate.trim());
      }
      if (options?.endDate?.trim()) {
        params.set("end_date", options.endDate.trim());
      } else if (options?.reportDate?.trim()) {
        params.set("end_date", options.reportDate.trim());
      }
      const query = params.toString();
      return requestJson<ResearchCalendarResultPayload>(
        fetchImpl,
        baseUrl,
        `/ui/calendar/supply-auctions${query ? `?${query}` : ""}`,
      ).then((payload) => payload.result.events.map(mapResearchCalendarApiEvent));
    },
    ingestTushareNprNews: (options?: { limit?: number }) => {
      const params = new URLSearchParams();
      if (options?.limit != null) {
        params.set("limit", String(options.limit));
      }
      const query = params.toString();
      return requestActionJson<{
        status: string;
        inserted: number;
        skipped_duplicates: number;
        fetched: number;
        npr: { inserted: number; skipped_duplicates: number; fetched: number };
        news: { inserted: number; skipped_duplicates: number; fetched: number; src: string; error?: string };
      }>(
        fetchImpl,
        baseUrl,
        `/api/news/tushare-npr/ingest${query ? `?${query}` : ""}`,
        { method: "POST" },
      );
    },
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
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
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
    const errorMessage =
      topErrorMessage ??
      (typeof nestedDetail === "string" && nestedDetail.trim() ? nestedDetail : undefined);
    throw new ActionRequestError(detailText, {
      status: response.status,
      runId,
      errorMessage,
      detail: rawDetail,
    });
  }
  return (await response.json()) as TResponse;
}
