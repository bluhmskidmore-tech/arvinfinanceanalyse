import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroRecentPoint,
  ChoiceMacroRefreshPayload,
  ChoiceNewsEventsPayload,
  ExternalDataWatermarkLedger,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  MarketDataCoverageSummaryPayload,
  LivermoreCandidateHistoryHorizonKey,
  LivermoreManualPositionInput,
  LivermoreSectorRankSeriesPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyScorePayload,
  LivermoreModuleState,
  LivermoreOutputKey,
  LivermoreStrategyPayload,
  MacroBondLinkagePayload,
  MacroVendorPayload,
  NcdFundingProxyPayload,
  ResearchCalendarEvent,
  SourcePreviewColumn,
  SourcePreviewSummary,
  StockAnalysisWorkbenchPayload,
} from "./contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { MOCK_CHOICE_MACRO_TUSHARE_EQUITY_SERIES } from "./marketDataMocks";
import type { MarketDataDomainClientMethods } from "./marketDataClient";

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
  stockCode?: string;
  includePayloadJson?: boolean;
  errorOnly?: boolean;
  receivedFrom?: string;
  receivedTo?: string;
}): ApiEnvelope<ChoiceNewsEventsPayload> {
  const stockCode = options.stockCode?.trim().toUpperCase() || null;
  const includePayloadJson = options.includePayloadJson !== false;
  const stockFilterTokens = buildChoiceNewsStockFilterTokens(stockCode);
  const filtered = MOCK_CHOICE_NEWS_EVENTS.filter((event) => {
    if (options.groupId?.trim() && event.group_id !== options.groupId.trim()) {
      return false;
    }
    if (options.topicCode?.trim() && event.topic_code !== options.topicCode.trim()) {
      return false;
    }
    if (stockFilterTokens.length > 0 && !choiceNewsEventMatchesStockTokens(event, stockFilterTokens)) {
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
  const pageEvents = filtered
    .slice(options.offset, options.offset + options.limit)
    .map((event) =>
      includePayloadJson ? event : { ...event, payload_json: null },
    );

  const result: ChoiceNewsEventsPayload = {
    total_rows: filtered.length,
    limit: options.limit,
    offset: options.offset,
    as_of_date: "2026-04-23",
    excluded_future_rows: 0,
    payload_json_included: includePayloadJson,
    compare: buildMockChoiceNewsCompare(pageEvents),
    events: pageEvents,
  };
  if (stockCode) {
    result.stock_code = stockCode;
    result.stock_filter_mode = "payload_text_or_json_best_effort";
    result.stock_filter_tokens = stockFilterTokens;
  }
  return buildMockApiEnvelope("news.choice.latest", result);
}

function buildMockChoiceNewsCompare(
  events: ChoiceNewsEventsPayload["events"],
): NonNullable<ChoiceNewsEventsPayload["compare"]> {
  const sourceEventIds = events.slice(0, 3).map((event) => event.event_key);
  return {
    basis: "analytical",
    rule_version: "rv_research_radar_mapping_registry_v1b_mock",
    same_direction: [
      {
        event_family: "rates",
        factor_tags: ["rates", "duration"],
        event_count: sourceEventIds.length,
        source_event_ids: sourceEventIds,
        summary: "mock 事件共同指向利率与久期复核。",
      },
    ],
    conflicting: [],
    review_needed: [
      {
        event_family: "fx",
        factor_tags: ["fx"],
        event_count: 1,
        source_event_ids: sourceEventIds.slice(0, 1),
        review_reason: "mock 数据未接入汇率敞口，需人工确认。",
      },
    ],
    candidate_scenarios: [
      {
        event_family: "rates",
        match_rule: "keyword_any",
        factor_tags: ["rates", "duration"],
        scenario_template_id: "rate_parallel_up_candidate",
        default_shocks: ["parallel_up_25bp_candidate"],
        rule_version: "rv_research_radar_mapping_registry_v1b_mock",
        human_review_required: true,
        mapping_rule_id: "mock_rates_duration",
        source_event_ids: sourceEventIds,
      },
    ],
  };
}

function buildChoiceNewsStockFilterTokens(stockCode: string | null): string[] {
  if (!stockCode) return [];
  const tokens = [stockCode];
  const stem = stockCode.split(".", 1)[0];
  if (/^\d{6}$/.test(stem)) {
    tokens.push(stem);
  }
  return Array.from(new Set(tokens));
}

function choiceNewsEventMatchesStockTokens(
  event: ChoiceNewsEventsPayload["events"][number],
  tokens: string[],
): boolean {
  const haystack = `${event.payload_text ?? ""}\n${event.payload_json ?? ""}`.toUpperCase();
  return tokens.some((token) => haystack.includes(token.toUpperCase()));
}

function buildMockNcdFundingProxyPayload(reportDate?: string): NcdFundingProxyPayload {
  return {
    as_of_date: reportDate?.trim() || "2026-04-23",
    proxy_label: "Tushare Shibor funding proxy (not NCD issuance matrix)",
    is_actual_ncd_matrix: false,
    formal_ncd_matrix_status: {
      status: "blocked",
      required_shape: "tenor_rating_matrix",
      current_proxy_basis: "shibor_funding_proxy",
      choice_status: "shibor_landed; formal_ncd_matrix_unconfirmed",
      tushare_status: "shibor_landed; formal_ncd_matrix_unconfirmed",
      missing_requirements: [
        "governed NCD tenor-rating source contract",
        "issuer/rating tenor matrix rows",
        "unit/date semantics and golden sample approval",
      ],
    },
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

const MOCK_LIVERMORE_OUTPUT_KEYS: LivermoreOutputKey[] = [
  "market_gate",
  "sector_rank",
  "stock_candidates",
  "uptrend_momentum_candidates",
  "fresh_trend_watchlist",
  "mean_reversion_candidates",
  "factor_screen_candidates",
  "theme_breakout",
  "hybrid_fusion",
  "risk_exit",
];

function buildMockLivermoreModuleStates(
  asOfDate: string,
  supportedOutputs: LivermoreOutputKey[] = MOCK_LIVERMORE_OUTPUT_KEYS,
  unsupportedOutputs: LivermoreStrategyPayload["unsupported_outputs"] = [],
): LivermoreModuleState[] {
  const supported = new Set(supportedOutputs);
  const unsupportedReasonByKey = new Map(unsupportedOutputs.map((output) => [output.key, output.reason]));
  return MOCK_LIVERMORE_OUTPUT_KEYS.map((key) => ({
    key,
    state: unsupportedReasonByKey.has(key) ? "unsupported" : supported.has(key) ? "ready" : "blocked",
    render_mode: unsupportedReasonByKey.has(key) || !supported.has(key) ? "evidence_only" : "primary",
    source_date: unsupportedReasonByKey.has(key) || !supported.has(key) ? null : asOfDate,
    lag_days: unsupportedReasonByKey.has(key) || !supported.has(key) ? null : 0,
    threshold_days: null,
    reasons: unsupportedReasonByKey.has(key)
      ? [unsupportedReasonByKey.get(key)!]
      : supported.has(key)
        ? []
        : ["Mock Livermore output has no representative payload."],
    evidence_scope: unsupportedReasonByKey.has(key) || !supported.has(key) ? "detail" : "primary",
    excludes_from_primary: unsupportedReasonByKey.has(key) || !supported.has(key),
  }));
}

function buildMockLivermoreStrategyPayload(asOfDate?: string): LivermoreStrategyPayload {
  const resolvedDate = asOfDate?.trim() || "2026-04-29";
  const supportedOutputs: LivermoreOutputKey[] = [
    "market_gate",
    "sector_rank",
    "fresh_trend_watchlist",
    "factor_screen_candidates",
    "risk_exit",
  ];
  const unsupportedOutputs: LivermoreStrategyPayload["unsupported_outputs"] = [
    {
      key: "stock_candidates",
      reason: "Stock candidate policy exp3b is inactive in OVERHEAT; active market states are HOT/WARM.",
    },
    {
      key: "uptrend_momentum_candidates",
      reason: "Uptrend momentum watchlist is paused unless the market gate is WARM or HOT.",
    },
    {
      key: "mean_reversion_candidates",
      reason: "Mean reversion watchlist is paused when the market gate is HOT or OVERHEAT because the defended-trend candidate bundle already covers overheated tape.",
    },
    {
      key: "theme_breakout",
      reason: "Theme breakout execution is paused in OVERHEAT; historical replay showed this bucket is draggy.",
    },
    {
      key: "hybrid_fusion",
      reason: "Hybrid fusion is observation-only and only emits candidates in WARM/HOT market states; current state is OVERHEAT.",
    },
  ];

  return {
    as_of_date: resolvedDate,
    requested_as_of_date: asOfDate?.trim() || null,
    strategy_name: "Livermore A-Share Defended Trend",
    basis: "analytical",
    market_gate: {
      state: "OVERHEAT",
      exposure: 1,
      passed_conditions: 4,
      available_conditions: 4,
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
          status: "pass",
          evidence: "5-day breadth is positive in the mock OVERHEAT closure.",
          source_series_id: null,
        },
        {
          key: "limit_up_quality_positive",
          label: "Limit-up seal/break quality positive",
          status: "pass",
          evidence: "Limit-up quality is positive in the mock OVERHEAT closure.",
          source_series_id: null,
        },
      ],
    },
    rule_readiness: [
      {
        key: "market_gate",
        title: "Market gate",
        status: "ready",
        summary: "All mock market gate inputs are landed for the resolved trade date.",
        required_inputs: ["broad_index_history", "breadth", "limit_up_quality"],
        missing_inputs: [],
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
        status: "blocked",
        summary: "Stock candidate policy exp3b is inactive in OVERHEAT; active market states are HOT/WARM.",
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
        code: "LIVERMORE_INPUT_FRESHNESS_DEGRADED",
        message: "breadth breadth_close data lagged 8 days (stale), signal quality degraded",
        input_family: "breadth",
      },
      {
        severity: "info",
        code: "LIVERMORE_STOCK_PIVOT_PAUSED_BY_POLICY",
        message: "Stock candidate policy exp3b is inactive in OVERHEAT; active market states are HOT/WARM.",
        input_family: "stock_candidate_policy",
      },
    ],
    data_gaps: [
      {
        input_family: "breadth",
        status: "stale",
        evidence: "5-day breadth input family is landed for the mock OVERHEAT closure.",
        input: "breadth_close",
        business_date: "2026-04-02",
        age_days: 8,
        tier: "stale",
      },
      {
        input_family: "limit_up_quality",
        status: "ready",
        evidence: "Limit-up seal/break quality input family is landed for the mock OVERHEAT closure.",
        input: "limit_up_quality",
        business_date: resolvedDate,
        age_days: 0,
        tier: "fresh",
      },
    ],
    supported_outputs: supportedOutputs,
    unsupported_outputs: unsupportedOutputs,
    module_states: buildMockLivermoreModuleStates(resolvedDate, supportedOutputs, unsupportedOutputs),
    sector_rank: {
      as_of_date: resolvedDate,
      formula_version: "rv_livermore_sector_strength_observation_v1",
      is_provisional: false,
      formula_status: "signed_off",
      formula_note:
        "Daily sector strength observation rank is a signed-off analytical formula: 50% pctchange percentile, 30% turn percentile, and 20% amplitude percentile; it supports review prioritization and sector filtering, not trading instructions; multi-day momentum persistence, sector money flow, and crowding are not part of this version.",
      formula_component_weights: {
        pctchange_percentile: 0.5,
        turn_percentile: 0.3,
        amplitude_percentile: 0.2,
      },
      sector_count: 3,
      excluded_constituent_count: 0,
      excluded_sector_count: 0,
      leader_constituent_limit: 3,
      leader_constituent_method: "top_turn_same_day",
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
          leader_constituents: [
            {
              rank: 1,
              stock_code: "000001.SZ",
              stock_name: "Alpha",
              pctchange: 5.2,
              turn: 4.8,
              amplitude: 3.1,
            },
          ],
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
          leader_constituents: [
            {
              rank: 1,
              stock_code: "000002.SZ",
              stock_name: "Beta",
              pctchange: 2.4,
              turn: 3.6,
              amplitude: 2.8,
            },
          ],
        },
      ],
    },
    fresh_trend_watchlist: {
      as_of_date: resolvedDate,
      formula_version: "rv_fresh_trend_watchlist_candidates_v1",
      market_state: "OVERHEAT",
      observation_only: true,
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
          concepts: ["Chiplet", "AI hardware"],
          close: 21.9,
          ma20: 21.05,
          ma60: 19.05,
          ma120: 16.05,
          return_20d: 0.18,
          return_60d: 0.34,
          return_120d: 0.68,
          close_to_ma20: 0.04,
          amount_ratio: 1.32,
          pctchange: 3.2,
          turn: 4.8,
          amplitude: 3.1,
          hlimitedays: 0,
          score: 0.91,
        },
        {
          rank: 2,
          stock_code: "000002.SZ",
          stock_name: "Beta",
          sector_code: "801002",
          sector_name: "Advanced Manufacturing",
          concepts: ["Robot", "Industrial AI"],
          close: 19.52,
          ma20: 18.76,
          ma60: 17.16,
          ma120: 14.76,
          return_20d: 0.14,
          return_60d: 0.28,
          return_120d: 0.52,
          close_to_ma20: 0.041,
          amount_ratio: 1.28,
          pctchange: 2.4,
          turn: 3.6,
          amplitude: 2.8,
          hlimitedays: 0,
          score: 0.83,
        },
      ],
    },
    factor_screen_candidates: {
      as_of_date: resolvedDate,
      factor_snapshot_as_of_date: resolvedDate,
      formula_version: "rv_factor_screen_candidates_v2",
      market_state: "OVERHEAT",
      observation_only: true,
      input_stock_count: 2,
      coverage_count: 2,
      coverage_denominator: 2,
      coverage_denominator_as_of_date: resolvedDate,
      coverage_ratio: 1,
      coverage_threshold: 0.8,
      candidate_count: 1,
      coverage_note: "Mock factor snapshot coverage is complete.",
      items: [
        {
          rank: 1,
          stock_code: "000001.SZ",
          stock_name: "Alpha",
          sector_code: "801001",
          sector_name: "AI",
          industry: "AI",
          score: 0.91,
          pe: 12.4,
          pb: 1.8,
          roe: 0.18,
          gross_margin: 0.32,
          three_month_return: 0.11,
          twelve_month_return: 0.24,
          dividend_yield: 0.02,
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
      watch_items: [
        {
          stock_code: "000001.SZ",
          stock_name: "Alpha",
          entry_cost: 10.5,
          bars_since_entry: 6,
          latest_close: 9.1,
          latest_ema10: 10.2,
          prior_close: 9.8,
          prior_ema10: 10.4,
          exit_watch_price: 10.2,
          triggered: true,
        },
        {
          stock_code: "000777.SZ",
          stock_name: "Watch Alpha",
          entry_cost: 19.5,
          bars_since_entry: 4,
          latest_close: 19.8,
          latest_ema10: 20.1,
          prior_close: 20.4,
          prior_ema10: 20.0,
          exit_watch_price: 20.1,
          triggered: false,
        },
      ],
    },
  };
}

function buildMockStockAnalysisWorkbenchPayload(options?: {
  asOfDate?: string;
  include?: string[];
  sectorWindowDays?: number;
  topK?: number;
}): StockAnalysisWorkbenchPayload {
  const strategy = buildMockLivermoreStrategyPayload(options?.asOfDate);
  const topK = options?.topK ?? 10;
  const reviewQueue = [
    ...(strategy.fresh_trend_watchlist?.items ?? []).map((item) => ({
      ...item,
      source_module: "fresh_trend_watchlist",
    })),
    ...(strategy.factor_screen_candidates?.items ?? []).map((item) => ({
      ...item,
      source_module: "factor_screen_candidates",
    })),
  ].slice(0, topK);
  const include = new Set(["main", "evidence_summary", ...(options?.include ?? [])]);
  const modules: StockAnalysisWorkbenchPayload["modules"] = {
    main: {
      key: "main",
      label: "Livermore strategy snapshot",
      endpoint: "/ui/market-data/livermore",
      status: "ready",
      result: strategy,
      summary: strategy.workbench_summary ?? {},
      meta: {
        source_version: "sv_livermore_mock",
        rule_version: "rv_livermore_market_gate_v1",
        cache_version: "cv_livermore_market_gate_v1",
        quality_flag: "ok",
        vendor_status: "ok",
        fallback_mode: "none",
      },
      issues: [],
    },
  };
  if (include.has("signal_confluence")) {
    modules.signal_confluence = {
      key: "signal_confluence",
      label: "signal confluence",
      endpoint: "/ui/market-data/livermore/signal-confluence",
      status: "deferred",
      result: null,
      summary: { as_of_date: strategy.as_of_date },
      meta: {},
      issues: [
        {
          severity: "info",
          code: "module_deferred",
          message: "Deferred from the default workbench response to keep first-screen data bounded.",
          source_module: "signal_confluence",
        },
      ],
    };
  }
  return {
    page_id: "GAP-STOCK-ANALYSIS-PAGE",
    route: "/stock-analysis",
    basis: "analytical",
    contract_status: "observational_only",
    formal_use_allowed: false,
    requested_as_of_date: strategy.requested_as_of_date,
    as_of_date: strategy.as_of_date,
    fallback_date: null,
    stale: false,
    page_question: {
      question: "Can the stock analysis workbench continue candidate review today, and who should be reviewed first?",
      answer_state: reviewQueue.length > 0 ? "review_ready" : "no_data",
      answer_label: reviewQueue.length > 0 ? "review_ready" : "no_data",
      reason:
        reviewQueue.length > 0
          ? "Mock candidates and first-screen evidence are available for observational review."
          : "No mock review candidates are present.",
    },
    decision_summary: {
      gate_state: strategy.market_gate.state,
      gate_label: strategy.market_gate.state,
      can_review_candidates: reviewQueue.length > 0,
      top_review_stock_code: String(reviewQueue[0]?.stock_code ?? "") || null,
      top_review_stock_name: String(reviewQueue[0]?.stock_name ?? "") || null,
      review_queue_count: reviewQueue.length,
      evidence_closure_label: "review_ready",
      primary_blocker: null,
      quality_flag: "ok",
    },
    data_status: {
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      source_version: "sv_livermore_mock",
      rule_version: "rv_livermore_market_gate_v1",
      cache_version: "cv_livermore_market_gate_v1",
      tables_used: [],
      evidence_rows: 0,
    },
    first_screen: {
      market_gate: strategy.market_gate,
      review_queue: reviewQueue,
      sector_snapshot: (strategy.sector_rank?.items ?? []).slice(0, topK),
      risk_exit_snapshot: [
        ...(strategy.risk_exit?.items ?? []),
        ...(strategy.risk_exit?.watch_items ?? []),
      ].slice(0, topK),
      data_gaps: strategy.data_gaps.map((gap) => ({
        ...gap,
        blocks_review:
          ([
            "broad_index_history",
            "breadth",
            "limit_up_quality",
            "sector_strength",
            "stock_universe",
            "position_risk",
          ].includes(gap.input_family) &&
            gap.status !== "ready") ||
          gap.status === "stale" ||
          gap.status === "look_ahead" ||
          gap.tier === "stale" ||
          gap.tier === "expired",
      })),
      diagnostics: strategy.diagnostics,
      supported_outputs: strategy.supported_outputs,
      unsupported_outputs: strategy.unsupported_outputs,
    },
    modules,
    endpoint_evidence: Object.values(modules).map((module) => ({
      key: module.key,
      label: module.label,
      endpoint: module.endpoint,
      status: module.status,
      as_of_date: strategy.as_of_date,
      rows: module.key === "main" ? 0 : null,
      warning: module.issues[0]?.message ?? null,
    })),
    issues: [],
    links: {
      stock_detail: "/ui/market-data/livermore/stock-detail",
      kline_analysis: "/ui/market-data/stock-analysis/kline-analysis",
      candidate_history: "/ui/market-data/livermore/candidate-history",
      sector_rank_series: "/ui/market-data/livermore/sector-rank-series",
      strategy_score: "/ui/market-data/livermore/strategy-score",
      strategy_optimization: "/ui/market-data/livermore/strategy-optimization",
      cycle_proxy_backtest: "/ui/market-data/livermore/cycle-proxy-backtest",
      portfolio_backtest: "/ui/market-data/livermore/candidate-history-portfolio-backtest",
    },
    include: {
      requested: Array.from(include).sort(),
      unknown: [],
      sector_window_days: options?.sectorWindowDays ?? 20,
      top_k: topK,
    },
  };
}

function buildMockLivermoreSignalConfluencePayload(
  asOfDate?: string,
): LivermoreSignalConfluencePayload {
  const resolvedDate = asOfDate?.trim() || "2026-04-29";
  return {
    as_of_date: resolvedDate,
    macro_context: {
      status: "neutral",
      composite_score: 0.05,
      multiplier: 0.5,
    },
    strategy_context: {
      market_gate_state: "WARM",
      market_gate_exposure: 0.4,
      allows_new_entry_observations: true,
    },
    position_size_hint: 0.2,
    entry_observations: [
      {
        stock_code: "000001.SZ",
        stock_name: "Alpha",
        action: "observe_entry_setup",
        trigger_price: 21.8,
        current_price: 21.9,
        invalidation_reference_price: 20.6,
        position_size_hint: 0.2,
        evidence: [
          "候选触发价来自 Livermore breakout_level。",
          "失效参考价来自候选股 EMA10。",
        ],
      },
    ],
    exit_observations: [
      {
        stock_code: "000777.SZ",
        stock_name: "Watch Alpha",
        action: "observe_exit_watch",
        current_price: 19.8,
        exit_watch_price: 20.1,
        triggered: false,
        evidence: ["退出观察价来自 Livermore EMA10。"],
      },
    ],
    diagnostics: [
      "Observation-only output. This service does not generate trading instructions.",
    ],
    disclaimer: "Observation-only output. This service does not generate trading instructions.",
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
      theme: "rates",
      tags: ["rates", "liquidity"],
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
      theme: "rates",
      tags: ["rates", "liquidity"],
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
      theme: "rates",
      tags: ["rates", "chinabond"],
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
    },
  ],
};

const MOCK_CHOICE_MACRO_LATEST_PAYLOAD: ChoiceMacroLatestPayload = {
  read_target: "duckdb",
  derived_spreads: {
    term_spread_10y_2y: 10.0,
    term_spread_10y_1y: 15.0,
    term_spread_10y_5y: null,
  },
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
      series_id: "EMM00588704",
      series_name: "中债国债到期收益率:2年",
      trade_date: "2026-04-10",
      value_numeric: 1.61,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "2Y treasury lane for term-spread display",
      latest_change: 0.02,
      recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 1.61, 0.03),
    },
    {
      series_id: "EMM00166466",
      series_name: "中债国债到期收益率:10年",
      trade_date: "2026-04-10",
      value_numeric: 1.71,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "10Y treasury lane for market home sparkline",
      latest_change: -0.01,
      recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 1.71, 0.03),
    },
    {
      series_id: "EMM01843735",
      series_name: "China financial conditions index",
      trade_date: "2026-03-01",
      value_numeric: -1.54,
      unit: "z-score",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "zero-centered financial-conditions score; analytical evidence only",
      latest_change: -0.03,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, -1.54, 0.08),
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

const MOCK_EXTERNAL_DATA_WATERMARK_LEDGER: ExternalDataWatermarkLedger = {
  summary: {
    catalog_count: 4,
    available_count: 3,
    no_data_count: 1,
    unavailable_count: 0,
    oldest_available_business_date: "2026-03-01",
    newest_available_business_date: "2026-04-10",
    last_successful_ingest: "2026-04-10T09:05:00Z",
  },
  entries: [
    {
      series_id: "M001",
      series_name: "Open Market 7D Reverse Repo",
      vendor_name: "choice",
      source_family: "choice_macro",
      domain: "macro",
      frequency: "daily",
      unit: "%",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      relation_name: "choice_macro_series",
      date_column: "trade_date",
      row_count: 20,
      latest_business_date: "2026-04-10",
      latest_loaded_at: "2026-04-10T09:05:00Z",
      age_days: 0,
      freshness_tier: "fresh",
      data_status: "available",
      error_message: null,
    },
    {
      series_id: "M002",
      series_name: "DR007",
      vendor_name: "choice",
      source_family: "choice_macro",
      domain: "macro",
      frequency: "daily",
      unit: "%",
      refresh_tier: "fallback",
      fetch_mode: "latest",
      relation_name: "choice_macro_series",
      date_column: "trade_date",
      row_count: 20,
      latest_business_date: "2026-02-21",
      latest_loaded_at: "2026-04-10T08:55:00Z",
      age_days: 48,
      freshness_tier: "stale",
      data_status: "available",
      error_message: null,
    },
    {
      series_id: "CA.BRENT",
      series_name: "Brent crude oil futures close",
      vendor_name: "choice",
      source_family: "choice_macro",
      domain: "macro",
      frequency: "daily",
      unit: "USD/bbl",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      relation_name: "choice_macro_series",
      date_column: "trade_date",
      row_count: 20,
      latest_business_date: "2026-02-07",
      latest_loaded_at: "2026-04-09T17:40:00Z",
      age_days: 62,
      freshness_tier: "expired",
      data_status: "available",
      error_message: null,
    },
    {
      series_id: "CA.USDCNY",
      series_name: "USD/CNY spot",
      vendor_name: "choice",
      source_family: "choice_macro",
      domain: "macro",
      frequency: null,
      unit: "CNY/USD",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      relation_name: null,
      date_column: null,
      row_count: 0,
      latest_business_date: null,
      latest_loaded_at: null,
      age_days: null,
      freshness_tier: "unknown",
      data_status: "no_data",
      error_message: null,
    },
  ],
};

const MOCK_MACRO_BOND_LINKAGE_PAYLOAD: MacroBondLinkagePayload = {
  report_date: "2026-04-10",
  environment_score: {
    report_date: "2026-04-10",
    rate_direction: "falling",
    rate_direction_score: -0.1,
    liquidity_score: 0.31,
    growth_score: 0.075,
    inflation_score: 0.08,
    composite_score: -0.11,
    composite_contributions: [
      { component: "rate_direction", raw_score: -0.1, weight: 0.4, signed_contribution: -0.04 },
      { component: "liquidity", raw_score: 0.31, weight: -0.3, signed_contribution: -0.093 },
      { component: "growth", raw_score: 0.075, weight: 0.2, signed_contribution: 0.015 },
      { component: "inflation", raw_score: 0.08, weight: 0.1, signed_contribution: 0.008 },
    ],
    composite_formula_version: "macro_env_composite_v2_liquidity_inverted",
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
      return buildMockApiEnvelope("market_data.catalog", MOCK_MACRO_FOUNDATION_PAYLOAD, {
        basis: "formal",
        formal_use_allowed: true,
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
    async getExternalDataWatermarks() {
      await delay();
      return MOCK_EXTERNAL_DATA_WATERMARK_LEDGER;
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
    async getBondFuturesRankings() {
      await delay();
      return buildMockApiEnvelope(
        "market_data.bond_futures_rankings",
        {
          read_target: "duckdb",
          as_of_date: null,
          requested_trade_date: null,
          contract: "T.CFE",
          rows: [],
          warnings: ["Mock client does not include CFFEX member-rank rows."],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_cffex_member_rank_mock_empty",
          vendor_version: "vv_none",
          rule_version: "rv_cffex_member_rank_choice_tushare_v1",
          cache_version: "cv_market_data_bond_futures_rankings_v1",
          quality_flag: "warning",
          vendor_status: "vendor_unavailable",
          fallback_mode: "none",
          source_surface: "market_data",
        },
      );
    },
    async getMarketDataCoverageSummary() {
      await delay();
      const stableSeries = MOCK_CHOICE_MACRO_LATEST_PAYLOAD.series.filter(
        (series) => series.refresh_tier === "stable",
      );
      const fxAnalyticalSeriesCount = MOCK_FX_ANALYTICAL_PAYLOAD.groups.reduce(
        (total, group) => total + group.series.length,
        0,
      );
      return buildMockApiEnvelope(
        "market_data.coverage_summary",
        {
          read_target: "duckdb",
          as_of_date: "2026-04-10",
          generated_at: "2026-04-10T09:30:00Z",
          headline: {
            readiness_label:
              "mixed-source supply map: formal rates fragment plus analytical/proxy/source-pending sections",
            formal_fragment_ready: true,
            formal_use_allowed: false,
            analytical_warning_count: 6,
            source_pending_count: 3,
            proxy_only_count: 1,
          },
          sections: [
            {
              key: "formal_rates",
              label: "Formal rates fragment",
              status: "ready",
              basis: "formal",
              formal_use_allowed: true,
              quality_flag: "ok",
              fallback_mode: "none",
              vendor_status: "ok",
              series_count: stableSeries.length,
              latest_trade_date: "2026-04-10",
              source_pending: false,
              proxy_only: false,
              message: "Stable rate series returned by the formal market-data rates fragment.",
            },
            {
              key: "macro_latest",
              label: "Macro latest observations",
              status: "warning",
              basis: "analytical",
              formal_use_allowed: false,
              quality_flag: "warning",
              fallback_mode: "latest_snapshot",
              vendor_status: "ok",
              series_count: MOCK_CHOICE_MACRO_LATEST_PAYLOAD.series.length,
              latest_trade_date: "2026-04-10",
              source_pending: false,
              proxy_only: false,
              message: "Analytical Choice macro latest snapshot used for market observation.",
            },
            {
              key: "fx_formal",
              label: "FX formal status",
              status: "warning",
              basis: "formal",
              formal_use_allowed: true,
              quality_flag: "warning",
              fallback_mode: "latest_snapshot",
              vendor_status: "ok",
              row_count: MOCK_FX_FORMAL_STATUS_PAYLOAD.materialized_count,
              series_count: MOCK_FX_FORMAL_STATUS_PAYLOAD.candidate_count,
              latest_trade_date: MOCK_FX_FORMAL_STATUS_PAYLOAD.latest_trade_date,
              source_pending: false,
              proxy_only: false,
              message: "Formal FX candidate/materialization status.",
            },
            {
              key: "fx_analytical",
              label: "FX analytical groups",
              status: "warning",
              basis: "analytical",
              formal_use_allowed: false,
              quality_flag: "warning",
              fallback_mode: "latest_snapshot",
              vendor_status: "ok",
              row_count: fxAnalyticalSeriesCount,
              group_count: MOCK_FX_ANALYTICAL_PAYLOAD.groups.length,
              source_pending: false,
              proxy_only: false,
              message: "Analytical FX groups for observation only.",
            },
            {
              key: "ncd_proxy",
              label: "NCD funding proxy",
              status: "proxy_only",
              basis: "analytical",
              formal_use_allowed: false,
              quality_flag: "warning",
              fallback_mode: "none",
              vendor_status: "ok",
              row_count: 1,
              as_of_date: "2026-04-23",
              source_pending: false,
              proxy_only: true,
              message: "Shibor funding proxy only; not an actual NCD tenor-rating matrix.",
            },
            {
              key: "bond_futures",
              label: "Bond futures rankings",
              status: "source_pending",
              basis: "analytical",
              formal_use_allowed: false,
              quality_flag: "warning",
              fallback_mode: "none",
              vendor_status: "vendor_unavailable",
              row_count: 0,
              source_pending: true,
              proxy_only: false,
              message: "CFFEX member rankings are not materialized in mock mode.",
            },
            {
              key: "cash_bond_trades",
              label: "Cash bond trades",
              status: "source_pending",
              basis: "analytical",
              formal_use_allowed: false,
              quality_flag: "warning",
              fallback_mode: "none",
              vendor_status: "vendor_unavailable",
              source_pending: true,
              proxy_only: false,
              message: "Outward cash-bond trade contract is still source-pending.",
            },
            {
              key: "credit_trades",
              label: "Credit trades",
              status: "source_pending",
              basis: "analytical",
              formal_use_allowed: false,
              quality_flag: "warning",
              fallback_mode: "none",
              vendor_status: "vendor_unavailable",
              source_pending: true,
              proxy_only: false,
              message: "Outward credit-trade contract is still source-pending.",
            },
            {
              key: "livermore",
              label: "Livermore",
              status: "deferred",
              basis: "analytical",
              formal_use_allowed: false,
              quality_flag: "warning",
              fallback_mode: "none",
              vendor_status: "ok",
              source_pending: false,
              proxy_only: false,
              message: "Analytical endpoint is loaded only after expansion.",
            },
            {
              key: "macro_bond_linkage",
              label: "Macro-bond linkage",
              status: "deferred",
              basis: "analytical",
              formal_use_allowed: false,
              quality_flag: "warning",
              fallback_mode: "none",
              vendor_status: "ok",
              source_pending: false,
              proxy_only: false,
              message: "Analytical linkage endpoint is date-gated and loaded on demand.",
            },
          ],
          actions: [
            {
              key: "ncd_proxy",
              label: "Keep NCD displayed as proxy-only.",
              severity: "warning",
              target_anchor: "market-data-liquidity-deck",
            },
            {
              key: "cash_bond_trades",
              label: "Cash bond trade outward contract remains pending.",
              severity: "warning",
              target_anchor: "market-data-source-pending-deck",
            },
          ],
        } satisfies MarketDataCoverageSummaryPayload,
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_market_data_coverage_summary_mock",
          vendor_version: "vv_market_data_coverage_summary_mock",
          rule_version: "rv_market_data_coverage_summary_v1",
          cache_version: "cv_market_data_coverage_summary_v1",
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "none",
          source_surface: "market_data",
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
    async getTushareSupplement() {
      await delay();
      return buildMockApiEnvelope(
        "market_data.tushare_supplement",
        {
          money_supply_rows: [
            {
              month: "2026-04-01",
              m0: 147477.38,
              m0_yoy: 12.2,
              m0_mom: 0.27,
              m1: 1145833.73,
              m1_yoy: 5.0,
              m1_mom: -3.97,
              m2: 3530425.21,
              m2_yoy: 8.6,
              m2_mom: -0.23,
            },
          ],
          eco_cal_rows: [
            {
              event_id: "mock-eco-1",
              event_date: "20260613",
              event_time: "09:30",
              currency: "CNY",
              country: "China",
              event: "Mock 中国CPI同比",
              value: "1.2",
              pre_value: "1.0",
              fore_value: "1.1",
            },
          ],
          warnings: [],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_tushare_supplement_mock",
          vendor_version: "vv_tushare_supplement_v1",
          rule_version: "rv_market_data_tushare_supplement_v1",
          cache_version: "cv_market_data_tushare_supplement_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          source_surface: "market_data",
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
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      );
    },
    async getStockAnalysisWorkbench(options?: {
      asOfDate?: string;
      include?: string[];
      sectorWindowDays?: number;
      topK?: number;
    }) {
      await delay();
      return buildMockApiEnvelope(
        "market_data.stock_analysis.workbench",
        buildMockStockAnalysisWorkbenchPayload(options),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_stock_analysis_workbench_mock",
          vendor_version: "vv_livermore_mock",
          rule_version: "rv_stock_analysis_workbench_v1",
          cache_version: "cv_stock_analysis_workbench_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      );
    },
    async getLivermoreStockDetail(options: { stockCode: string; asOfDate?: string; lookback?: number }) {
      await delay();
      const lookback = options.lookback ?? 60;
      const candles = [
        {
          trade_date: "2026-04-08",
          open_value: 10.0,
          high_value: 10.4,
          low_value: 9.9,
          close_value: 10.2,
          volume: 1_200_000,
          amount: 12_000_000,
        },
        {
          trade_date: "2026-04-09",
          open_value: 10.2,
          high_value: 10.5,
          low_value: 10.1,
          close_value: 10.35,
          volume: 1_100_000,
          amount: 11_500_000,
        },
      ].slice(-lookback);
      return buildMockApiEnvelope(
        "market_data.livermore.stock_detail",
        {
          basis: "analytical",
          state: "ok",
          stock_code: options.stockCode.trim(),
          requested_as_of_date: options.asOfDate ?? null,
          as_of_date: options.asOfDate ?? "2026-04-09",
          lookback,
          candles,
          factor: {
            as_of_date: options.asOfDate ?? "2026-04-09",
            pe: 18.2,
            pb: 2.1,
            roe: 0.09,
            dividend_yield: 0.02,
          },
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_stock_detail_mock",
          vendor_version: "vv_livermore_stock_detail_mock",
          rule_version: "rv_livermore_stock_detail_v1",
          cache_version: "cv_livermore_stock_detail_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      );
    },
    async getLivermoreSectorRankSeries(options?: {
      asOfDate?: string;
      windowDays?: number;
      sectorCode?: string;
      topK?: number;
    }) {
      await delay();
      const wd = options?.windowDays ?? 20;
      const asOf = options?.asOfDate?.trim() || "2026-04-29";
      const rowA: LivermoreSectorRankSeriesPayload["series"][number] = {
        trade_date: asOf,
        sector_code: "801001",
        sector_name: "AI",
        score: 0.91,
        rank: 1,
        avg_pctchange: 0.42,
        avg_turn: 2.2,
        avg_amplitude: 1.1,
        constituent_count: 12,
        cum_pctchange_window: Number((wd * 0.42).toFixed(6)),
      };
      return buildMockApiEnvelope(
        "market_data.livermore.sector_rank_series",
        {
          basis: "analytical",
          state: "ok",
          as_of_date: asOf,
          window_days: wd,
          top_k: options?.topK ?? 10,
          sector_code_filter: options?.sectorCode?.trim() ?? null,
          formula_version: "rv_livermore_sector_rank_series_v1",
          series: [rowA],
          unsupported_notes: [
            "momentum_persistence: needs metric definition review (P1)",
            "sector_money_flow: needs vendor approval & new schema (P1)",
          ],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_sector_series_mock",
          vendor_version: "vv_livermore_sector_series_mock",
          rule_version: "rv_livermore_sector_rank_series_v1",
          cache_version: "cv_livermore_sector_rank_series_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      );
    },
    async getStockKlineAnalysis(options: { stockCode: string; asOfDate?: string; lookback?: number }) {
      await delay();
      const asOfDate = options.asOfDate ?? "2026-04-09";
      return buildMockApiEnvelope(
        "market_data.stock_analysis.kline",
        {
          basis: "analytical",
          state: "ok",
          contract_status: "observational_only",
          formal_use_allowed: false,
          trading_instruction_allowed: false,
          stock_code: options.stockCode.trim(),
          requested_as_of_date: options.asOfDate ?? null,
          as_of_date: asOfDate,
          lookback: options.lookback ?? 60,
          engine: {
            name: "moss_stock_kline_analysis",
            source: "kline-analysis zip deterministic OHLCV subset",
            rule_version: "rv_stock_kline_analysis_observation_v1",
            coverage: ["daily_patterns", "moving_average_trend", "volume_context", "validity_check"],
          },
          latest_candle: {
            trade_date: asOfDate,
            open_value: 10.2,
            high_value: 10.5,
            low_value: 10.1,
            close_value: 10.35,
            volume: 1_100_000,
            amount: 11_500_000,
            pctchange: 1.47,
            turn: 1.2,
            amplitude: 3.9,
          },
          indicators: {
            latest_close: 10.35,
            ma5: 10.18,
            ma20: 9.92,
            ma60: 9.64,
            return_5d: 0.041,
            return_20d: 0.087,
            volume_ratio_20d: 1.4,
            latest_turnover: 1.2,
            latest_amplitude: 3.9,
          },
          patterns: [
            {
              key: "wide_body",
              label: "wide_body",
              tone: "positive",
              evidence: "body/range >= 65%",
            },
          ],
          validity: {
            state: "usable",
            usable: true,
            bar_count: 60,
            required_bar_count: 30,
            recommended_bar_count: 60,
            data_health: { state: "ok", invalid_candle_count: 0, zero_volume_count: 0 },
            liquidity: { state: "ok", latest_volume: 1_100_000, average_volume_20d: 900_000 },
            warnings: [],
          },
          observation_signal: {
            level: "constructive_watch",
            label: "constructive_watch",
            score: 72,
            confidence: "high",
            reasons: ["close_above_ma20", "ma20_above_ma60", "positive_20d_return"],
            risks: [],
          },
          diagnostics: [
            {
              severity: "info",
              code: "observation_only",
              message: "K-line output is observational evidence only and is not a trading instruction.",
            },
          ],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_stock_kline_analysis_mock",
          vendor_version: "vv_stock_kline_analysis_mock",
          rule_version: "rv_stock_kline_analysis_observation_v1",
          cache_version: "cv_stock_kline_analysis_observation_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      );
    },
    async getLivermoreCandidateHistory(options?: {
      stockCode?: string;
      snapshotFrom?: string;
      snapshotTo?: string;
      limit?: number;
    }) {
      await delay();
      const limit = options?.limit ?? 100;
      const code = options?.stockCode?.trim() ?? "";
      return buildMockApiEnvelope(
        "market_data.livermore.candidate_history",
        {
          stock_code: code || null,
          snapshot_from: options?.snapshotFrom?.trim() ?? null,
          snapshot_to: options?.snapshotTo?.trim() ?? null,
          limit,
          items: [
            {
              snapshot_as_of_date: "2026-04-10",
              stock_code: code || "000001.SZ",
              stock_name: "MockHist",
              signal_kind: "stock_candidate",
              candidate_rank: 1,
              sector_code: "MOCK",
              sector_name: "样例板块",
              selection_close: 10.5,
              forward_trade_date_1d: "2026-04-11",
              forward_trade_date_5d: "2026-04-16",
              forward_trade_date_20d: "2026-05-15",
              return_1d: 0.01,
              return_5d: -0.02,
              return_20d: 0.08,
              data_status: "complete",
              formula_version: "fv_mock",
              source_version: "sv_candidate_mock",
              vendor_version: "vv_candidate_mock",
              rule_version: "rv_livermore_candidate_history_v1",
              run_id: "mock",
            },
            {
              snapshot_as_of_date: "2026-04-03",
              stock_code: code || "000001.SZ",
              stock_name: "MockHist",
              signal_kind: "factor_screen",
              candidate_rank: 2,
              sector_code: null,
              sector_name: null,
              selection_close: 10.4,
              forward_trade_date_1d: "2026-04-04",
              forward_trade_date_5d: "2026-04-09",
              forward_trade_date_20d: null,
              return_1d: 0.009,
              return_5d: null,
              return_20d: null,
              data_status: "pending",
              formula_version: "fv_mock",
              source_version: "sv_candidate_mock",
              vendor_version: "vv_candidate_mock",
              rule_version: "rv_livermore_candidate_history_v1",
              run_id: "mock_b",
            },
          ],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_candidate_history_mock",
          vendor_version: "vv_candidate_history_mock",
          rule_version: "rv_livermore_candidate_history_v1",
          cache_version: "cv_livermore_candidate_history_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      );
    },
    async getLivermoreStrategyScore(options?: {
      snapshotFrom?: string;
      snapshotTo?: string;
      currentMarketState?: string;
      minSample?: number;
      primaryHorizon?: LivermoreCandidateHistoryHorizonKey;
    }) {
      await delay();
      const state = options?.currentMarketState?.trim() || "WARM";
      const primaryHorizon = options?.primaryHorizon ?? "return_5d";
      const primaryHorizonLabel =
        primaryHorizon === "return_1d"
          ? "T+1"
          : primaryHorizon === "return_10d"
            ? "T+10"
            : primaryHorizon === "return_20d"
              ? "T+20"
              : "T+5";
      const minSample = Math.max(options?.minSample ?? 30, 30);
      const stats = {
        return_1d: {
          available_count: 30,
          missing_count: 0,
          positive_count: 17,
          non_positive_count: 13,
          avg_return: 0.008,
          median_return: 0.006,
          win_rate: 0.566667,
        },
        return_5d: {
          available_count: 30,
          missing_count: 0,
          positive_count: 18,
          non_positive_count: 12,
          avg_return: 0.024,
          median_return: 0.024,
          win_rate: 0.6,
        },
        return_10d: {
          available_count: 30,
          missing_count: 0,
          positive_count: 18,
          non_positive_count: 12,
          avg_return: 0.028,
          median_return: 0.025,
          win_rate: 0.6,
        },
        return_20d: {
          available_count: 30,
          missing_count: 0,
          positive_count: 18,
          non_positive_count: 12,
          avg_return: 0.031,
          median_return: 0.026,
          win_rate: 0.6,
        },
      };
      const row: LivermoreStrategyScorePayload["rows"][number] = {
        market_state: state,
        signal_kind: "factor_screen",
        strategy_label: "多因子",
        sample_status: "sufficient",
        priority_score: 62.4,
        priority_rank: 1,
        priority_label: "优先复核",
        reason: `${primaryHorizonLabel} sample 30, avg return +2.40%, win rate 60.0%, priority review ranking.`,
        stats,
        diagnostics: {
          priority_scope: null,
          priority_scope_label: null,
          priority_scope_stats: null,
          maturity: null,
          rank_buckets: [],
          risk_flags: [],
        },
      };
      return buildMockApiEnvelope(
        "market_data.livermore.strategy_score",
        {
          as_of_date: options?.snapshotTo?.trim() ?? "2026-04-29",
          snapshot_from: options?.snapshotFrom?.trim() ?? null,
          snapshot_to: options?.snapshotTo?.trim() ?? "2026-04-29",
          primary_horizon: primaryHorizon,
          min_sample: minSample,
          current_market_state: state,
          rows: [row],
          current_market_state_rows: [row],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_strategy_score_mock",
          vendor_version: "vv_livermore_strategy_score_mock",
          rule_version: "rv_livermore_strategy_score_v1",
          cache_version: "cv_livermore_strategy_score_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      );
    },
    async getLivermoreStrategyOptimization(options?: {
      snapshotFrom?: string;
      snapshotTo?: string;
      currentMarketState?: string;
      minSample?: number;
      primaryHorizon?: LivermoreCandidateHistoryHorizonKey;
    }) {
      await delay();
      const state = options?.currentMarketState?.trim() || "WARM";
      const primaryHorizon = options?.primaryHorizon ?? "return_5d";
      return buildMockApiEnvelope(
        "market_data.livermore.strategy_optimization",
        {
          as_of_date: options?.snapshotTo?.trim() ?? "2026-04-29",
          snapshot_from: options?.snapshotFrom?.trim() ?? null,
          snapshot_to: options?.snapshotTo?.trim() ?? "2026-04-29",
          primary_horizon: primaryHorizon,
          min_sample: Math.max(options?.minSample ?? 30, 30),
          current_market_state: state,
          strategy_summaries: [],
          slices: [],
          recommendations: [],
          pending_summary: {
            primary_horizon: primaryHorizon,
            pending_rows: 0,
            pending_dates: [],
            latest_pending_date: null,
            message: "mock",
          },
          sample_maturity: null,
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_strategy_optimization_mock",
          vendor_version: "vv_livermore_strategy_optimization_mock",
          rule_version: "rv_livermore_strategy_optimization_v1",
          cache_version: "cv_livermore_strategy_optimization_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      );
    },
    async getLivermoreCycleProxyBacktest(options?: {
      snapshotFrom?: string;
      snapshotTo?: string;
    }) {
      await delay();
      return buildMockApiEnvelope(
        "market_data.livermore.cycle_proxy_backtest",
        {
          status: "proxy",
          full_strategy_status: "blocked_missing_inputs",
          formula_version: "fv_livermore_cycle_proxy_backtest_execution_first_v4",
          proxy_signal_kind: "stock_candidate",
          proxy_rule: "execution-first next-open T+5 proxy",
          execution_blocked_rows_in_window: 40,
          snapshot_from: options?.snapshotFrom?.trim() ?? null,
          snapshot_to: options?.snapshotTo?.trim() ?? "2026-04-29",
          missing_full_strategy_inputs: [],
          warnings: [
            "Executable next-open return_5d_net_adj is preferred and already includes formal transaction costs.",
            "When unavailable, return_5d_adj is used with read-side costs, followed by gross return_5d.",
            "Execution-blocked entries are excluded from the proxy backtest.",
          ],
          summary: {
            sample_days: 2,
            candidate_rows: 546,
            return_field_used: "return_5d_net_adj",
            return_field_fallback: "return_5d_adj",
            return_field_second_fallback: "return_5d",
            execution_return_costs_already_applied: true,
            return_rows_execution_net_adjusted: 433,
            return_rows_adjusted: 23,
            return_rows_adjusted_fallback: 23,
            return_rows_gross_fallback: 90,
            cumulative_return: 0.008148,
            annualized_return: 0.2559,
            max_gain: {
              return: 0.0124,
              start_date: "2026-04-16",
              end_date: "2026-04-23",
            },
            max_drawdown: {
              return: -0.0042,
              peak_date: "2026-04-23",
              trough_date: "2026-04-29",
            },
          },
          nav_series: [
            {
              date: "2026-04-16",
              exit_date: "2026-04-23",
              period_return: 0.0124,
              period_return_gross: 0.0145,
              nav: 1.0124,
              candidate_count: 6,
            },
            {
              date: "2026-04-24",
              exit_date: "2026-04-29",
              period_return: -0.0042,
              period_return_gross: -0.0021,
              nav: 1.008148,
              candidate_count: 6,
            },
          ],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_cycle_proxy_backtest_mock",
          vendor_version: "vv_livermore_cycle_proxy_backtest_mock",
          rule_version: "rv_livermore_cycle_proxy_backtest_v1",
          cache_version: "cv_livermore_cycle_proxy_backtest_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          tables_used: [
            "livermore_candidate_history",
            "livermore_candidate_execution_history",
          ],
          evidence_rows: 546,
        },
      );
    },
    async getLivermoreCandidateHistoryPortfolioBacktest(options?: {
      snapshotFrom?: string;
      snapshotTo?: string;
    }) {
      await delay();
      return buildMockApiEnvelope(
        "market_data.livermore.candidate_history_portfolio_backtest",
        {
          status: "portfolio_proxy",
          full_strategy_status: "blocked_missing_inputs",
          signal_kind: "stock_candidate",
          rebalance_rule: "mock",
          weighting_rule: "mock",
          snapshot_from: options?.snapshotFrom?.trim() ?? null,
          snapshot_to: options?.snapshotTo?.trim() ?? "2026-04-29",
          missing_full_strategy_inputs: [],
          warnings: [],
          summary: null,
          nav_series: [],
          rebalance_log: [],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_candidate_history_portfolio_backtest_mock",
          vendor_version: "vv_livermore_candidate_history_portfolio_backtest_mock",
          rule_version: "rv_livermore_candidate_history_portfolio_backtest_v1",
          cache_version: "cv_livermore_candidate_history_portfolio_backtest_v1",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      );
    },
    async getLivermoreSignalConfluence(options?: { asOfDate?: string }) {
      await delay();
      return buildMockApiEnvelope(
        "market_data.livermore.signal_confluence",
        buildMockLivermoreSignalConfluencePayload(options?.asOfDate),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_signal_confluence_mock",
          vendor_version: "vv_livermore_signal_confluence_mock",
          rule_version: "rv_livermore_signal_confluence_v1",
          cache_version: "cv_livermore_signal_confluence_v1",
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "latest_snapshot",
        },
      );
    },
    async materializeLivermorePositionSnapshot(options: { asOfDate: string; csvPath: string }) {
      await delay();
      return {
        status: "completed",
        fact_source: "livermore_position_snapshot",
        input_mode: "csv",
        as_of_date: options.asOfDate,
        row_count: 1,
        run_id: `livermore_position_snapshot:${options.asOfDate}:mock`,
        source_file_hash: "sha256:mock",
        source_systems: ["mock_position_book"],
        source_version: "sv_livermore_position_mock",
        vendor_version: "vv_livermore_position_csv_mock",
        csv_path: options.csvPath,
        risk_exit_input_status: "ready",
        risk_exit_input_block_reason: "",
      };
    },
    async materializeLivermoreManualPositionSnapshot(options: {
      asOfDate: string;
      positions: LivermoreManualPositionInput[];
    }) {
      await delay();
      return {
        status: "completed",
        fact_source: "livermore_position_snapshot",
        input_mode: "manual",
        as_of_date: options.asOfDate,
        row_count: options.positions.length,
        run_id: `livermore_position_snapshot:${options.asOfDate}:mock`,
        source_file_hash: "sha256:mock-manual",
        source_systems: ["livermore_position_snapshot_manual"],
        source_version: "sv_livermore_position_manual_mock",
        vendor_version: "vv_livermore_position_manual_mock",
        csv_path: null,
        risk_exit_input_status: "ready",
        risk_exit_input_block_reason: "",
      };
    },
    async getLivermoreGateSupplementRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed" as const,
        run_id: runId,
        trigger_mode: "terminal" as const,
        as_of_date: "2026-04-29",
        lookback_days: 30,
        queued_at: "2026-04-29T09:30:00Z",
        started_at: "2026-04-29T09:30:05Z",
        finished_at: "2026-04-29T09:30:12Z",
        computed_rows: 15,
        first_date: "2026-04-10",
        last_date: "2026-04-29",
        basis: "csi300_proxy",
        message: null,
        failure_category: null,
        failure_reason: null,
        error_message: null,
        idempotency_key: null,
        idempotency_replay: false,
      };
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
    async refreshGateSupplement(_options?: { asOfDate?: string; lookbackDays?: number }) {
      await delay();
      return {
        status: "queued" as const,
        run_id: "livermore_gate_supplement_refresh:2026-04-29:mock",
        trigger_mode: "async" as const,
        as_of_date: "2026-04-29",
        lookback_days: 30,
        queued_at: "2026-04-29T09:30:00Z",
        idempotency_key: null,
        idempotency_replay: false,
      };
    },
    async getMarketDataRates() {
      await delay();
      // Mock returns stable-only series with formal basis
      const stableSeries = MOCK_CHOICE_MACRO_LATEST_PAYLOAD.series.filter(
        (s) => s.refresh_tier === "stable",
      );
      return buildMockApiEnvelope("market_data.rates", {
        ...MOCK_CHOICE_MACRO_LATEST_PAYLOAD,
        series: stableSeries,
      }, {
        basis: "formal",
        formal_use_allowed: true,
        source_version: "sv_market_data_rates_mock",
        vendor_version: "vv_choice_macro_20260410",
        rule_version: "rv_market_data_rates_formal_v1",
        cache_version: "cv_market_data_rates_formal_v1",
      });
    },
    async getMarketDataCatalog() {
      await delay();
      return buildMockApiEnvelope("market_data.catalog", MOCK_MACRO_FOUNDATION_PAYLOAD, {
        basis: "formal",
        formal_use_allowed: true,
        source_version: "sv_macro_vendor_mock",
        vendor_version: "vv_choice_catalog_v1",
        rule_version: "rv_phase1_macro_vendor_v1",
        cache_version: "cv_phase1_macro_vendor_v1",
      });
    },
  };
}
