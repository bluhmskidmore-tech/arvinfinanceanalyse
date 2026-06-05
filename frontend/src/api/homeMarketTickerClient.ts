import type { ApiClient } from "./client";
import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  ChoiceNewsEventsPayload,
  ResearchCalendarEvent,
  ResearchCalendarResultPayload,
} from "./contracts";
import { readHttpJsonDetail } from "./httpResponseError";
import { mapResearchCalendarApiEvent } from "../lib/researchCalendarApiEvent";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";

type FetchLike = typeof fetch;

export type HomeMarketTickerClientMethods = Pick<
  ApiClient,
  | "getChoiceMacroLatest"
  | "getMarketDataRates"
  | "getChoiceNewsEvents"
  | "getResearchCalendarEvents"
>;

type HomeMarketTickerClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

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

const MOCK_RATES_PAYLOAD: ChoiceMacroLatestPayload = {
  read_target: "duckdb",
  series: [
    {
      series_id: "CGB10Y",
      series_name: "10Y Treasury Yield",
      trade_date: "2026-04-10",
      value_numeric: 2.31,
      frequency: "daily",
      unit: "%",
      source_version: "sv_home_market_ticker_mock",
      vendor_version: "vv_home_market_ticker_mock",
      vendor_name: "mock",
      refresh_tier: "stable",
      fetch_mode: "latest",
      fetch_granularity: "batch",
      policy_note: "Home market ticker mock for startup fast path",
      latest_change: -0.02,
      recent_points: recentPoints("2026-04-10", [2.36, 2.34, 2.33, 2.31]),
    },
    {
      series_id: "CDB10Y",
      series_name: "10Y CDB Yield",
      trade_date: "2026-04-10",
      value_numeric: 2.47,
      frequency: "daily",
      unit: "%",
      source_version: "sv_home_market_ticker_mock",
      vendor_version: "vv_home_market_ticker_mock",
      vendor_name: "mock",
      refresh_tier: "stable",
      fetch_mode: "latest",
      fetch_granularity: "batch",
      policy_note: "Home market ticker mock for startup fast path",
      latest_change: -0.01,
      recent_points: recentPoints("2026-04-10", [2.5, 2.49, 2.48, 2.47]),
    },
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
    payload_text: "资金面平稳，长端利率窄幅震荡。",
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
    payload_text: "债券一级供给节奏保持稳定。",
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

export function createRealHomeMarketTickerClient({
  fetchImpl,
  baseUrl,
}: HomeMarketTickerClientFactoryOptions): HomeMarketTickerClientMethods {
  return {
    getChoiceMacroLatest: () =>
      requestJson<ChoiceMacroLatestPayload>(fetchImpl, baseUrl, "/ui/macro/choice-series/latest"),
    getMarketDataRates: () =>
      requestJson<ChoiceMacroLatestPayload>(fetchImpl, baseUrl, "/ui/market-data/rates"),
    getChoiceNewsEvents: ({
      limit,
      offset,
      groupId,
      topicCode,
      stockCode,
      errorOnly,
      receivedFrom,
      receivedTo,
    }) => {
      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      if (groupId?.trim()) params.set("group_id", groupId.trim());
      if (topicCode?.trim()) params.set("topic_code", topicCode.trim());
      if (stockCode?.trim()) params.set("stock_code", stockCode.trim());
      if (errorOnly) params.set("error_only", "true");
      if (receivedFrom?.trim()) params.set("received_from", receivedFrom.trim());
      if (receivedTo?.trim()) params.set("received_to", receivedTo.trim());
      return requestJson<ChoiceNewsEventsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/news/choice-events/latest?${params.toString()}`,
      );
    },
    getResearchCalendarEvents: (options) => {
      const params = new URLSearchParams();
      if (options?.startDate?.trim()) params.set("start_date", options.startDate.trim());
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
  };
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
