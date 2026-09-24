/**
 * Choice 新闻事件 mock 单一数据源。
 *
 * marketDataMockClient 与 homeMarketTickerMockClient 共用这份事件集与
 * envelope/batch/compare 构造器，消除两份 mock 各自漂移的风险。
 * 本模块只被 mock 客户端（懒加载 chunk）引用，不进入 real 模式 bundle。
 */
import type {
  ApiEnvelope,
  ChoiceNewsEventsBatchPayload,
  ChoiceNewsEventsPayload,
} from "../api/contracts";
import { buildMockApiEnvelope } from "./mockApiEnvelope";

export const MOCK_CHOICE_NEWS_EVENTS: ChoiceNewsEventsPayload["events"] = [
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

export function buildMockChoiceNewsEnvelope(options: {
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

/** 批量端点 mock：把单查 mock 按 topic/group 分桶，batches 顺序与请求一致（先 topics 后 groups）。 */
export function buildMockChoiceNewsBatchEnvelope(options: {
  topics?: readonly { topicCode: string; limit: number }[];
  groups?: readonly { groupId: string; limit: number }[];
}): ApiEnvelope<ChoiceNewsEventsBatchPayload> {
  const batches: ChoiceNewsEventsBatchPayload["batches"] = [
    ...(options.topics ?? []).map(({ topicCode, limit }) => ({
      key: `topic:${topicCode}`,
      topic_code: topicCode,
      group_id: null,
      events: buildMockChoiceNewsEnvelope({ limit, offset: 0, topicCode }).result.events,
    })),
    ...(options.groups ?? []).map(({ groupId, limit }) => ({
      key: `group:${groupId}`,
      topic_code: null,
      group_id: groupId,
      events: buildMockChoiceNewsEnvelope({ limit, offset: 0, groupId }).result.events,
    })),
  ];
  return buildMockApiEnvelope("news.choice.latest_batch", { batches });
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
