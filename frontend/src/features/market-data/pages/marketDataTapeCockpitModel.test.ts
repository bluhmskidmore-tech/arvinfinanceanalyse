import { describe, expect, it } from "vitest";

import type {
  ChoiceMacroLatestPoint,
  FxFormalStatusPayload,
  LivermoreCandidateHistoryPayload,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreSectorRankSeriesPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyScorePayload,
  MarketDataCoverageSummaryPayload,
  NcdFundingProxyPayload,
  ResultMeta,
  TushareSupplementPayload,
} from "../../../api/contracts";
import type { MacroToolkitAnalysisPayload } from "../../../api/macroToolkitClient";
import type { MarketDataTerminalModel } from "../lib/marketDataTerminalModel";
import { buildMarketDataTapeCockpitModel, type BuildMarketDataTapeCockpitInput } from "./marketDataTapeCockpitModel";

const terminalModel: MarketDataTerminalModel = {
  rateQuotes: {
    status: "ready",
    rows: [],
    source: null,
    emptyReason: "",
  },
  moneyMarket: {
    status: "ready",
    rows: [
      {
        key: "dr007",
        seriesId: "CA.DR007",
        seriesName: "DR007",
        name: "DR007",
        rateText: "1.46%",
        deltaText: "0bp",
        tradeDate: "2026-06-18",
        origin: "rates_bundle",
        basis: "formal",
        formalUseAllowed: true,
        fallbackMode: "none",
        vendorStatus: "ok",
        sourceVersion: "test",
        vendorVersion: "test",
        qualityFlag: "ok",
        sourceMode: "real",
        sparklineValues: [1.44, 1.46],
      },
    ],
    source: null,
    emptyReason: "",
  },
  bondFutures: {
    status: "source-pending",
    rows: [],
    source: null,
    emptyReason: "not connected",
  },
  bondTrades: {
    status: "source-pending",
    rows: [],
    source: null,
    emptyReason: "not connected",
  },
  creditTrades: {
    status: "source-pending",
    rows: [],
    source: null,
    emptyReason: "not connected",
  },
};

function macroPoint(overrides: Partial<ChoiceMacroLatestPoint>): ChoiceMacroLatestPoint {
  return {
    series_id: "macro-1",
    series_name: "Macro latest point",
    trade_date: "2026-06-18",
    value_numeric: 1.23,
    unit: "%",
    source_version: "test",
    vendor_version: "test",
    quality_flag: "ok",
    latest_change: 0.1,
    ...overrides,
  };
}

function resultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr-test",
    basis: "analytical",
    result_kind: "test.result",
    formal_use_allowed: false,
    source_version: "sv-test",
    vendor_version: "vv-test",
    rule_version: "rv-test",
    cache_version: "cv-test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-06-18T09:30:00Z",
    ...overrides,
  };
}

function baseInput(overrides: Partial<BuildMarketDataTapeCockpitInput> = {}): BuildMarketDataTapeCockpitInput {
  return {
    catalog: [],
    latestSeries: [],
    formalRateSeries: [],
    terminalModel,
    fxFormalStatus: null,
    fxAnalyticalGroups: [],
    watchDate: "2026-06-18",
    ratesBasisLabel: "analytical",
    formalRatesSeriesCount: null,
    livermoreIsLoading: false,
    livermoreIsError: false,
    newsPayload: null,
    newsIsLoading: false,
    newsIsError: false,
    calendarRows: [],
    calendarIsLoading: false,
    calendarIsError: false,
    ...overrides,
  };
}

describe("buildMarketDataTapeCockpitModel", () => {
  it("exposes supported FX, macro latest, and NCD rows for the first-screen market tape", () => {
    const fxFormalStatus: FxFormalStatusPayload = {
      read_target: "duckdb",
      vendor_priority: ["Choice"],
      candidate_count: 1,
      materialized_count: 1,
      latest_trade_date: "2026-06-18",
      carry_forward_count: 0,
      rows: [
        {
          base_currency: "USD",
          quote_currency: "CNY",
          pair_label: "USD/CNY",
          series_id: "fx-usdcny",
          series_name: "USD/CNY",
          vendor_series_code: "USDCNY",
          trade_date: "2026-06-18",
          observed_trade_date: "2026-06-18",
          mid_rate: 7.185,
          source_name: "Choice",
          vendor_name: "Choice",
          vendor_version: "test",
          source_version: "test",
          is_business_day: true,
          is_carry_forward: false,
          status: "ok",
        },
      ],
    };
    const ncdFundingProxy: NcdFundingProxyPayload = {
      as_of_date: "2026-06-18",
      proxy_label: "Shibor proxy",
      is_actual_ncd_matrix: false,
      rows: [
        {
          row_key: "aaa",
          label: "AAA",
          "1M": 1.9,
          "3M": 2.1,
          "6M": 2.2,
          "9M": 2.3,
          "1Y": 2.4,
          quote_count: 12,
        },
      ],
      warnings: [],
    };

    const model = buildMarketDataTapeCockpitModel({
      catalog: [],
      latestSeries: [
        macroPoint({ series_id: "macro-stable", series_name: "China macro stable" }),
        macroPoint({ series_id: "M0017127", series_name: "PMI", trade_date: "2026-05-01", value_numeric: 49.5, unit: "" }),
        macroPoint({ series_id: "CA.CSI300", series_name: "CSI300", trade_date: "2026-06-18", value_numeric: 3888.12, unit: "point" }),
        macroPoint({ series_id: "CA.COPPER", series_name: "Copper", trade_date: "2026-06-18", value_numeric: 80000, unit: "CNY/t" }),
      ],
      formalRateSeries: [],
      terminalModel,
      fxFormalStatus,
      fxAnalyticalGroups: [],
      watchDate: "2026-06-18",
      ratesBasisLabel: "formal",
      formalRatesSeriesCount: 1,
      ncdFundingProxy,
      livermoreSignalConfluence: {
        as_of_date: "2026-06-18",
        entry_observations: [{ key: "entry" }],
        exit_observations: [{ key: "exit" }],
      } as unknown as LivermoreSignalConfluencePayload,
      livermoreStrategyScore: {
        as_of_date: "2026-06-18",
        rows: [{ strategy_label: "momentum" }],
      } as unknown as LivermoreStrategyScorePayload,
      livermoreSectorRankSeries: {
        as_of_date: "2026-06-18",
        series: [{ sector_name: "Banking" }, { sector_name: "Brokerage" }],
      } as unknown as LivermoreSectorRankSeriesPayload,
      livermoreCandidateHistory: {
        snapshot_to: "2026-06-18",
        items: [{ stock_code: "000001.SZ" }, { stock_code: "000002.SZ" }, { stock_code: "600000.SH" }],
      } as unknown as LivermoreCandidateHistoryPayload,
      livermoreStrategyOptimization: {
        as_of_date: "2026-06-18",
        snapshot_to: "2026-06-18",
        recommendations: [{ label: "prioritize momentum" }, { label: "review breakout" }],
        slices: [{ label: "warm market" }],
      } as unknown as LivermoreStrategyOptimizationPayload,
      livermoreCycleProxyBacktest: {
        snapshot_to: "2026-06-18",
        nav_series: [{ date: "2026-06-18", nav: 1.03 }],
      } as unknown as LivermoreCycleProxyBacktestPayload,
      livermorePortfolioBacktest: {
        snapshot_to: "2026-06-18",
        rebalance_log: [{ date: "2026-06-18", target_count: 8 }],
      } as unknown as LivermoreCandidateHistoryPortfolioBacktestPayload,
      tushareSupplement: {
        money_supply_rows: [
          {
            month: "2026-04-01",
            m0: 1200,
            m0_yoy: 1.2,
            m0_mom: 0.1,
            m1: 2400,
            m1_yoy: 2.4,
            m1_mom: 0.2,
            m2: 3600,
            m2_yoy: 3.6,
            m2_mom: 0.3,
          },
        ],
        eco_cal_rows: [
          {
            event_id: "cn-cpi",
            event_date: "20260613",
            event_time: "09:30:00",
            currency: "CNY",
            country: "CN",
            event: "CPI",
            value: "0.1",
            pre_value: "0.2",
            fore_value: "0.3",
          },
        ],
        warnings: [],
      } satisfies TushareSupplementPayload,
      macroToolkitAnalysis: {
        default_data_sources: ["choice"],
        as_of_date: "2026-06-18",
        conclusion: {
          stance: "Neutral",
          tone: "neutral",
          summary: "core signals available",
          recommended_action: "observe",
        },
        coverage: {
          indicator_count: 8,
          hit_count: 7,
          hit_rate: 0.875,
          script_count: 24,
          output_file_count: 3,
        },
        indicators: [],
        signal_cards: [{ key: "liquidity" }, { key: "growth" }],
        readiness_summary: {
          total_count: 4,
          artifact_backed_count: 1,
          degraded_count: 3,
          status_counts: { artifact_backed: 1, degraded: 3 },
          observation_only: true,
          formal_use_allowed: false,
        },
        capability_results: [],
        strategy_summaries: [],
        output_files: [],
        source_checks: [],
        capabilities: [],
        warnings: [],
      } as unknown as MacroToolkitAnalysisPayload,
      coverageSummary: {
        read_target: "duckdb",
        as_of_date: "2026-06-18",
        generated_at: "2026-06-18T09:30:00Z",
        headline: {
          readiness_label: "coverage summary readable",
          formal_fragment_ready: true,
          formal_use_allowed: false,
          analytical_warning_count: 1,
          source_pending_count: 2,
          proxy_only_count: 1,
        },
        sections: [
          {
            key: "bond_futures",
            label: "Bond futures rankings",
            status: "ready",
            basis: "analytical",
            formal_use_allowed: false,
            quality_flag: "ok",
            fallback_mode: "none",
            vendor_status: "ok",
            row_count: 10,
            source_pending: false,
            proxy_only: false,
            message: "connected",
          },
        ],
        actions: [],
      } satisfies MarketDataCoverageSummaryPayload,
      livermoreIsLoading: false,
      livermoreIsError: false,
      newsPayload: null,
      newsIsLoading: false,
      newsIsError: false,
      calendarRows: [],
      calendarIsLoading: false,
      calendarIsError: false,
    });

    expect(model.fxRows).toEqual([
      expect.objectContaining({ pairLabel: "USD/CNY", rateText: "7.1850", dateText: "2026-06-18" }),
    ]);
    expect(model.macroLatestRows).toEqual(expect.arrayContaining([
      expect.objectContaining({ key: "macro-stable", name: "China macro stable", tierText: "数据正常" }),
    ]));
    expect(model.ncdProxyRows).toEqual([
      expect.objectContaining({ label: "AAA", threeMonthText: "2.100", oneYearText: "2.400", quoteCountText: "12" }),
    ]);
    expect(model.sourceGapRows.map((row) => row.code)).not.toContain("404");
    expect(model.sourceGapRows.map((row) => row.key)).not.toContain("tushare-supplement");
    expect(model.sourceGapRows.map((row) => row.key)).not.toContain("coverage-summary");
    expect(model.sourceGapRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "bond-futures-rankings", code: "未接入", status: "暂不可用于正式决策" }),
        expect.objectContaining({ key: "cash-bond-trades", code: "未接入", status: "暂不可用于正式决策" }),
        expect.objectContaining({ key: "credit-trades", code: "未接入", status: "暂不可用于正式决策" }),
      ]),
    );
    expect(model.endpointCoverageRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "livermore-signal",
          endpoint: "/ui/market-data/livermore/signal-confluence",
          status: "已接入",
          count: "2 obs",
        }),
        expect.objectContaining({
          key: "livermore-score",
          endpoint: "/ui/market-data/livermore/strategy-score",
          status: "已接入",
          count: "1 rows",
        }),
        expect.objectContaining({
          key: "livermore-sector-series",
          endpoint: "/ui/market-data/livermore/sector-rank-series",
          status: "已接入",
          count: "2 points",
        }),
        expect.objectContaining({
          key: "livermore-candidate-history",
          endpoint: "/ui/market-data/livermore/candidate-history",
          status: "已接入",
          count: "3 rows",
        }),
        expect.objectContaining({
          key: "livermore-strategy-optimization",
          endpoint: "/ui/market-data/livermore/strategy-optimization",
          status: "已接入",
          count: "2 recs",
        }),
        expect.objectContaining({
          key: "livermore-cycle-proxy-backtest",
          endpoint: "/ui/market-data/livermore/cycle-proxy-backtest",
          status: "已接入",
          count: "1 nav",
        }),
        expect.objectContaining({
          key: "livermore-portfolio-backtest",
          endpoint: "/ui/market-data/livermore/candidate-history-portfolio-backtest",
          status: "已接入",
          count: "1 rebal",
        }),
        expect.objectContaining({
          key: "tushare-supplement",
          endpoint: "/ui/market-data/tushare-supplement",
          status: "已接入",
          count: "1 money / 1 events",
        }),
        expect.objectContaining({
          key: "macro-toolkit-core",
          endpoint: "/ui/macro/toolkit/analysis?detail=core",
          status: "已接入",
          count: "7/8 indicators",
        }),
        expect.objectContaining({
          key: "coverage-summary",
          endpoint: "/ui/market-data/coverage-summary",
          status: "已接入",
          count: "1 sections",
        }),
        expect.objectContaining({
          key: "bond-futures-rankings",
          endpoint: "/ui/market-data/bond-futures/rankings",
          status: "未接入",
          count: "0 rows",
        }),
      ]),
    );
    expect(model.tushareSupplementRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "money-supply", countText: "1 months", statusText: "已接入" }),
        expect.objectContaining({ key: "eco-calendar", countText: "1 events", statusText: "已接入", dateText: "2026-06-13" }),
      ]),
    );
    expect(model.tushareSignalTiles).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "m2-yoy", label: "M2 YoY", value: "3.60%", detail: "latest 2026-04" }),
        expect.objectContaining({ key: "m2-m1-spread", label: "M2 - M1", value: "+1.20pp" }),
        expect.objectContaining({ key: "eco-calendar", value: "1", detail: "2026-06-13 CNY" }),
        expect.objectContaining({ key: "tushare-lineage", value: "已接入" }),
      ]),
    );
    expect(model.externalComparisonPlacements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "macro-rates",
          targetSurface: "/macro-toolkit + rates",
          evidence: "M2 3.60% / PMI 49.50",
          dateText: "2026-05-01",
          statusText: expect.stringContaining("数据正常"),
        }),
        expect.objectContaining({
          key: "equity-theme",
          targetSurface: "/stock-analysis",
          evidence: "CSI300 3888.12 point",
          dateText: "2026-06-18",
          statusText: expect.stringContaining("数据正常"),
        }),
        expect.objectContaining({
          key: "commodity-cycle",
          targetSurface: "/cross-asset + /risk-tensor",
          evidence: "Copper 80000.00 CNY/t",
          tone: "proxy",
          statusText: expect.stringContaining("数据正常"),
        }),
        expect.objectContaining({
          key: "event-reaction",
          targetSurface: "/news-events + /risk-tensor",
          statusText: expect.stringContaining("数据正常"),
        }),
      ]),
    );
    expect(model.macroToolkitRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "indicator-coverage", countText: "7/8", statusText: "88%" }),
        expect.objectContaining({ key: "signal-cards", countText: "2 cards", statusText: "Neutral" }),
        expect.objectContaining({ key: "model-readiness", countText: "1/4", statusText: "3 degraded" }),
      ]),
    );
    expect(model.livermoreDeepRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "candidate-history", countText: "3 rows", statusText: "已接入" }),
        expect.objectContaining({ key: "strategy-optimization", countText: "2 rec / 1 slices", statusText: "已接入" }),
        expect.objectContaining({ key: "cycle-proxy-backtest", countText: "1 nav", statusText: "已接入" }),
        expect.objectContaining({ key: "portfolio-proxy-backtest", countText: "1 rebal", statusText: "已接入" }),
      ]),
    );
  });

  it("keeps stale and fallback lineage visible in external comparison placements", () => {
    const model = buildMarketDataTapeCockpitModel(baseInput({
      latestSeries: [
        macroPoint({ series_id: "CA.CSI300", series_name: "CSI300", quality_flag: "stale" }),
        macroPoint({ series_id: "CA.CSI300_PE", series_name: "CSI300 PE", value_numeric: 14.2, unit: "x" }),
        macroPoint({ series_id: "CA.COPPER", series_name: "Copper", value_numeric: 80000, unit: "CNY/t", quality_flag: "warning" }),
      ],
      tushareSupplement: {
        money_supply_rows: [
          {
            month: "2026-04-01",
            m0: 1200,
            m0_yoy: 1.2,
            m0_mom: 0.1,
            m1: 2400,
            m1_yoy: 2.4,
            m1_mom: 0.2,
            m2: 3600,
            m2_yoy: 3.6,
            m2_mom: 0.3,
          },
        ],
        eco_cal_rows: [
          {
            event_id: "cn-cpi",
            event_date: "20260613",
            event_time: "09:30:00",
            currency: "CNY",
            country: "CN",
            event: "CPI",
            value: "0.1",
            pre_value: "0.2",
            fore_value: "0.3",
          },
        ],
        warnings: [],
      },
      tushareSupplementMeta: resultMeta({
        quality_flag: "stale",
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
      }),
      newsPayload: {
        total_rows: 2,
        limit: 2,
        offset: 0,
        as_of_date: "2026-06-10",
        excluded_future_rows: 0,
        events: [
          {
            event_key: "older",
            received_at: "2026-06-10T09:00:00Z",
            group_id: "policy",
            content_type: "text",
            serial_id: 1,
            request_id: 1,
            error_code: 0,
            error_msg: "",
            topic_code: "macro",
            item_index: 0,
            payload_text: "older policy item",
            payload_json: null,
          },
          {
            event_key: "newer",
            received_at: "2026-06-21T09:00:00Z",
            group_id: "policy",
            content_type: "text",
            serial_id: 2,
            request_id: 1,
            error_code: 0,
            error_msg: "",
            topic_code: "macro",
            item_index: 1,
            payload_text: "newer policy item",
            payload_json: null,
          },
        ],
      },
      calendarRows: [
        {
          id: "calendar-1",
          date: "2026-06-18",
          title: "Supply calendar A",
          kind: "supply",
          severity: "medium",
        },
        {
          id: "calendar-2",
          date: "2026-06-20",
          title: "Supply calendar B",
          kind: "supply",
          severity: "medium",
        },
        {
          id: "calendar-3",
          date: "2026-06-22",
          title: "Supply calendar C",
          kind: "supply",
          severity: "medium",
        },
        {
          id: "calendar-4",
          date: "2026-06-30",
          title: "Supply calendar D",
          kind: "supply",
          severity: "medium",
        },
      ],
    }));

    expect(model.externalComparisonPlacements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "macro-rates",
          tone: "proxy",
          statusText: expect.stringContaining("数据延迟"),
        }),
        expect.objectContaining({
          key: "macro-rates",
          statusText: expect.stringContaining("数据延迟"),
        }),
        expect.objectContaining({
          key: "equity-theme",
          tone: "proxy",
          statusText: expect.stringContaining("数据延迟"),
        }),
        expect.objectContaining({
          key: "commodity-cycle",
          tone: "proxy",
          statusText: expect.stringContaining("部分缺失"),
        }),
        expect.objectContaining({
          key: "event-reaction",
          dateText: "2026-06-30",
          evidence: "7 event rows",
          statusText: expect.stringContaining("数据延迟"),
        }),
      ]),
    );
    expect(model.sourceLedgerRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "macro-latest",
          quality: "数据延迟",
        }),
      ]),
    );
  });

  it("keeps error and not-read comparison placement states explicit", () => {
    const model = buildMarketDataTapeCockpitModel(baseInput({
      latestSeries: [
        macroPoint({ series_id: "CA.COPPER", series_name: "Copper", value_numeric: 80000, unit: "CNY/t" }),
      ],
      tushareSupplementIsError: true,
      newsIsError: true,
    }));

    expect(model.externalComparisonPlacements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "macro-rates",
          tone: "gap",
          statusText: "技术异常",
        }),
        expect.objectContaining({
          key: "equity-theme",
          evidence: "pending equity source",
          statusText: "未接入",
        }),
        expect.objectContaining({
          key: "commodity-cycle",
          evidence: "Copper 80000.00 CNY/t",
          tone: "proxy",
          statusText: expect.stringContaining("数据正常"),
        }),
        expect.objectContaining({
          key: "event-reaction",
          tone: "gap",
          statusText: "技术异常",
        }),
      ]),
    );
  });

  it("surfaces latest-series query errors for macro, equity, and commodity placements", () => {
    const model = buildMarketDataTapeCockpitModel(baseInput({
      latestSeriesIsError: true,
      latestSeries: [],
    }));

    expect(model.externalComparisonPlacements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "macro-rates", tone: "gap", statusText: "技术异常" }),
        expect.objectContaining({ key: "equity-theme", tone: "gap", statusText: "技术异常" }),
        expect.objectContaining({ key: "commodity-cycle", tone: "gap", statusText: "技术异常" }),
      ]),
    );
    expect(model.endpointCoverageRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "macro-latest",
          tone: "gap",
          status: "技术异常",
          note: "技术异常",
        }),
      ]),
    );
    expect(model.sourceLedgerRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "macro-latest",
          quality: "技术异常",
          note: "技术异常",
        }),
      ]),
    );
  });

  it("rolls the worst successful latest-series row quality into the macro-latest ledger", () => {
    const model = buildMarketDataTapeCockpitModel(baseInput({
      latestSeries: [
        macroPoint({ series_id: "M0017127", series_name: "PMI", quality_flag: "warning" }),
        macroPoint({ series_id: "CA.CSI300", series_name: "CSI300", quality_flag: "stale" }),
        macroPoint({ series_id: "CA.COPPER", series_name: "Copper", quality_flag: "error" }),
      ],
    }));

    expect(model.sourceLedgerRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "macro-latest",
          quality: "不可用",
          note: "已接入",
        }),
      ]),
    );
  });

  it("normalizes macro-latest coverage and ledger loading and not-read states", () => {
    const loadingModel = buildMarketDataTapeCockpitModel(baseInput({
      latestSeriesIsLoading: true,
    }));
    expect(loadingModel.endpointCoverageRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "macro-latest", status: "接入中", note: "接入中" }),
      ]),
    );
    expect(loadingModel.sourceLedgerRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "macro-latest", quality: "接入中", note: "接入中" }),
      ]),
    );

    const notReadModel = buildMarketDataTapeCockpitModel(baseInput());
    expect(notReadModel.endpointCoverageRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "macro-latest", status: "未接入", note: "未接入" }),
      ]),
    );
    expect(notReadModel.sourceLedgerRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "macro-latest", quality: "未接入", note: "未接入" }),
      ]),
    );
  });

  it("prefers canonical series ids over misleading newer series names", () => {
    const model = buildMarketDataTapeCockpitModel(baseInput({
      latestSeries: [
        macroPoint({
          series_id: "FAKE.CSI300",
          series_name: "CSI300 misleading newer row",
          trade_date: "2026-06-25",
          value_numeric: 9999,
          unit: "fake",
        }),
        macroPoint({
          series_id: "FAKE.CSI300_PE",
          series_name: "CSI300 PE misleading newer row",
          trade_date: "2026-06-25",
          value_numeric: 99,
          unit: "fake",
        }),
        macroPoint({
          series_id: "FAKE.COPPER",
          series_name: "Copper misleading newer row",
          trade_date: "2026-06-25",
          value_numeric: 1,
          unit: "fake",
        }),
        macroPoint({
          series_id: "CA.CSI300",
          series_name: "CSI300 canonical",
          trade_date: "2026-06-18",
          value_numeric: 3888.12,
          unit: "point",
        }),
        macroPoint({
          series_id: "CA.CSI300_PE",
          series_name: "CSI300 PE canonical",
          trade_date: "2026-06-18",
          value_numeric: 14.2,
          unit: "x",
        }),
        macroPoint({
          series_id: "CA.COPPER",
          series_name: "Copper canonical",
          trade_date: "2026-06-18",
          value_numeric: 80000,
          unit: "CNY/t",
        }),
      ],
    }));

    expect(model.externalComparisonPlacements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "equity-theme",
          evidence: "CSI300 canonical 3888.12 point / CSI300 PE canonica... 14.20 x",
          dateText: "2026-06-18",
        }),
        expect.objectContaining({
          key: "commodity-cycle",
          evidence: "Copper canonical 80000.00 CNY/t",
          dateText: "2026-06-18",
        }),
      ]),
    );
  });

  it("falls back to precise series names when canonical external ids are absent", () => {
    const model = buildMarketDataTapeCockpitModel(baseInput({
      latestSeries: [
        macroPoint({
          series_id: "ALT.CSI300_CLOSE",
          series_name: "沪深300指数收盘价",
          trade_date: "2026-06-19",
          value_numeric: 3901.23,
          unit: "index",
        }),
        macroPoint({
          series_id: "ALT.CSI300_PE",
          series_name: "沪深300市盈率",
          trade_date: "2026-06-19",
          value_numeric: 14.8,
          unit: "x",
        }),
        macroPoint({
          series_id: "ALT.COPPER_MAIN",
          series_name: "铜主力期货收盘价",
          trade_date: "2026-06-19",
          value_numeric: 81234.5,
          unit: "CNY/t",
        }),
      ],
    }));

    expect(model.externalComparisonPlacements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "equity-theme",
          evidence: "沪深300指数收盘价 3901.23 index / 沪深300市盈率 14.80 x",
          dateText: "2026-06-19",
        }),
        expect.objectContaining({
          key: "commodity-cycle",
          evidence: "铜主力期货收盘价 81234.50 CNY/t",
          dateText: "2026-06-19",
        }),
      ]),
    );
  });

  it("uses the series id in evidence labels when latest-series names are blank", () => {
    const model = buildMarketDataTapeCockpitModel(baseInput({
      latestSeries: [
        macroPoint({
          series_id: "CA.CSI300",
          series_name: "",
          trade_date: "2026-06-20",
          value_numeric: 3901.23,
          unit: "index",
        }),
        macroPoint({
          series_id: "CA.COPPER",
          series_name: "",
          trade_date: "2026-06-20",
          value_numeric: 81234.5,
          unit: "CNY/t",
        }),
      ],
    }));

    expect(model.externalComparisonPlacements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "equity-theme",
          evidence: "CA.CSI300 3901.23 index",
        }),
        expect.objectContaining({
          key: "commodity-cycle",
          evidence: "CA.COPPER 81234.50 CNY/t",
        }),
      ]),
    );
    expect(model.macroLatestRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "CA.CSI300",
          name: "CA.CSI300",
        }),
      ]),
    );
  });
});
