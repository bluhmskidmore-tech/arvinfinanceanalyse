import type { HomeMarketTickerClientMethods } from "./homeMarketTickerClient";
import type {
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  ResearchCalendarEvent,
} from "./contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import {
  buildMockChoiceNewsBatchEnvelope,
  buildMockChoiceNewsEnvelope,
} from "../mocks/choiceNewsMocks";

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
    macroPoint("EMM01843735", "China financial conditions index", -1.54, "z-score", -0.03, [
      -1.43, -1.48, -1.51, -1.54,
    ]),
    macroPoint("CA.CSI300", "沪深300指数收盘价", 4102.25, "index", 17.13, [
      4060.12, 4088.34, 4119.38, 4102.25,
    ]),
    macroPoint("CA.CSI300_PCT_CHG", "沪深300涨跌幅", -0.42, "%", -0.05, [
      0.31, 0.18, -0.12, -0.42,
    ]),
    macroPoint("CA.USDCNY", "USD/CNY spot", 7.14, "CNY/USD", 0.0064, [
      7.11, 7.12, 7.13, 7.14,
    ]),
  ],
};

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
      // Choice 新闻 mock 单一来源：与 marketDataMockClient 共用同一份事件集，
      // 避免首页轻量 ticker 与市场数据域各自漂移。
      return buildMockChoiceNewsEnvelope(options);
    },
    async getChoiceNewsEventsBatch(options) {
      await delay();
      return buildMockChoiceNewsBatchEnvelope(options);
    },
    async getResearchCalendarEvents(options) {
      await delay();
      return buildMockResearchCalendarEvents(
        options?.startDate ?? options?.reportDate ?? options?.endDate,
      );
    },
  };
}
