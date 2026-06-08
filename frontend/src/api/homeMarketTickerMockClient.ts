import type { HomeMarketTickerClientMethods } from "./homeMarketTickerClient";
import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  ChoiceNewsEventsPayload,
  ResearchCalendarEvent,
} from "./contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";

const delay = async () => new Promise<void>((resolve) => setTimeout(resolve, 40));

function recentPoints(
  endDate: string,
  values: readonly number[],
): ChoiceMacroLatestPoint["recent_points"] {
  return values.map((value, index) => {
    const date = new Date(`${endDate}T12:00:00Z`);
    date.setUTCDate(date.getUTCDate() - (values.length - 1 - index));
    return {
      trade_date: date.toISOString().slice(0, 10),
      value_numeric: value,
      source_version: "sv_home_market_ticker_mock",
      vendor_version: "vv_home_market_ticker_mock",
      quality_flag: "ok",
    };
  });
}

function macroPoint(
  seriesId: string,
  seriesName: string,
  valueNumeric: number,
  unit: string,
  latestChange: number,
  recentValues: readonly number[],
): ChoiceMacroLatestPoint {
  return {
    series_id: seriesId,
    series_name: seriesName,
    trade_date: "2026-04-10",
    value_numeric: valueNumeric,
    frequency: "daily",
    unit,
    source_version: "sv_home_market_ticker_mock",
    vendor_version: "vv_home_market_ticker_mock",
    vendor_name: "mock",
    refresh_tier: "stable",
    fetch_mode: "date_slice",
    fetch_granularity: "batch",
    policy_note: "Home market ticker mock for startup fast path",
    latest_change: latestChange,
    recent_points: recentPoints("2026-04-10", recentValues),
  };
}

const MOCK_RATES_PAYLOAD: ChoiceMacroLatestPayload = {
  read_target: "duckdb",
  series: [
    macroPoint("EMM00166466", "China 10Y government bond yield", 2.31, "%", -0.02, [
      2.36, 2.34, 2.33, 2.31,
    ]),
    macroPoint("EMM00166502", "China 10Y policy bank bond yield", 2.47, "%", -0.01, [
      2.5, 2.49, 2.48, 2.47,
    ]),
    macroPoint("M001", "Open market 7D reverse repo rate", 1.75, "%", 0.2, [
      1.69, 1.71, 1.73, 1.75,
    ]),
    macroPoint("M002", "DR007", 1.83, "%", -0.05, [1.89, 1.88, 1.84, 1.83]),
    macroPoint("M003", "China 1Y government bond yield", 1.56, "%", 0.03, [
      1.51, 1.53, 1.54, 1.56,
    ]),
    macroPoint("EMM01843735", "China financial conditions index", 98.6, "index", 0.35, [
      97.9, 98.1, 98.3, 98.6,
    ]),
    macroPoint("CA.USDCNY", "USD/CNY spot", 7.14, "CNY/USD", 0.0064, [
      7.11, 7.12, 7.13, 7.14,
    ]),
  ],
};

const MOCK_NEWS_EVENTS: ChoiceNewsEventsPayload["events"] = [
  {
    event_key: "home_market_news_001",
    received_at: "2026-04-10T09:01:00Z",
    group_id: "home_market",
    content_type: "sectornews",
    serial_id: 1001,
    request_id: 501,
    error_code: 0,
    error_msg: "",
    topic_code: "S888010007API",
    item_index: 0,
    payload_text: "\u8d44\u91d1\u9762\u5e73\u7a33\uff0c\u957f\u7aef\u5229\u7387\u7a84\u5e45\u9707\u8361\u3002",
    payload_json: null,
  },
  {
    event_key: "home_market_news_002",
    received_at: "2026-04-10T10:15:00Z",
    group_id: "home_market",
    content_type: "bondnews",
    serial_id: 1002,
    request_id: 502,
    error_code: 0,
    error_msg: "",
    topic_code: "tushare.news",
    item_index: 0,
    payload_text: "\u503a\u5238\u4e00\u7ea7\u4f9b\u7ed9\u8282\u594f\u4fdd\u6301\u7a33\u5b9a\u3002",
    payload_json: null,
  },
];

function buildMockChoiceNewsEnvelope(options: {
  limit: number;
  offset: number;
  groupId?: string;
  topicCode?: string;
  stockCode?: string;
  errorOnly?: boolean;
  receivedFrom?: string;
  receivedTo?: string;
}): ApiEnvelope<ChoiceNewsEventsPayload> {
  const stockCode = options.stockCode?.trim().toUpperCase() || null;
  const filtered = MOCK_NEWS_EVENTS.filter((event) => {
    if (options.groupId?.trim() && event.group_id !== options.groupId.trim()) return false;
    if (options.topicCode?.trim() && event.topic_code !== options.topicCode.trim()) return false;
    if (options.errorOnly && event.error_code === 0) return false;
    if (options.receivedFrom?.trim() && event.received_at < options.receivedFrom.trim()) return false;
    if (options.receivedTo?.trim() && event.received_at > options.receivedTo.trim()) return false;
    if (stockCode) {
      const haystack = `${event.payload_text ?? ""}\n${event.payload_json ?? ""}`.toUpperCase();
      return haystack.includes(stockCode) || haystack.includes(stockCode.split(".", 1)[0]);
    }
    return true;
  });
  const result: ChoiceNewsEventsPayload = {
    total_rows: filtered.length,
    limit: options.limit,
    offset: options.offset,
    events: filtered.slice(options.offset, options.offset + options.limit),
  };
  if (stockCode) {
    result.stock_code = stockCode;
    result.stock_filter_mode = "payload_text_or_json_best_effort";
    result.stock_filter_tokens = [stockCode, stockCode.split(".", 1)[0]].filter(Boolean);
  }
  return buildMockApiEnvelope("news.choice.latest", result);
}

function buildMockResearchCalendarEvents(reportDate?: string): ResearchCalendarEvent[] {
  const baseDate = reportDate?.trim() || "2026-04-18";
  return [
    {
      id: "home_rc_supply_001",
      date: baseDate,
      title: "Government bond net financing",
      kind: "supply",
      severity: "low",
      amount_label: "180bn CNY",
      note: "Supply rhythm",
    },
    {
      id: "home_rc_auction_002",
      date: baseDate,
      title: "Policy bank bond auction",
      kind: "auction",
      severity: "high",
      amount_label: "42bn CNY",
      issuer: "CDB",
    },
  ];
}

export function createMockHomeMarketTickerClient(): HomeMarketTickerClientMethods {
  return {
    async getChoiceMacroLatest() {
      await delay();
      return buildMockApiEnvelope("choice_macro.latest", MOCK_RATES_PAYLOAD);
    },
    async getMarketDataRates() {
      await delay();
      return buildMockApiEnvelope("market_data.rates", MOCK_RATES_PAYLOAD, {
        basis: "formal",
        formal_use_allowed: true,
        source_version: "sv_home_market_ticker_mock",
        vendor_version: "vv_home_market_ticker_mock",
        rule_version: "rv_home_market_ticker_mock",
        cache_version: "cv_home_market_ticker_mock",
      });
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
  };
}
