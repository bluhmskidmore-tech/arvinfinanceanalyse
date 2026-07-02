import { describe, expect, it } from "vitest";

import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  FxAnalyticalGroup,
  FxFormalStatusPayload,
  MacroBondLinkagePayload,
  MacroBondLinkageTopCorrelation,
  MarketDataCoverageSummaryPayload,
  MacroVendorPayload,
  MacroVendorSeries,
  ResultMeta,
} from "../../../api/contracts";
import {
  buildBridgeKpiMetrics,
  buildFxFormalStatusCollapseLabel,
  buildMarketDataBasisChipLabel,
  buildMarketDataPageModel,
  buildSpreadSlots,
  formatMarketWorkbenchSourceSummary,
  pickRailHighlightMetric,
} from "./marketDataPageModel";

function meta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_market_data_page_model",
    basis: "formal",
    result_kind: "market-data",
    formal_use_allowed: true,
    source_version: "sv_market_data_page_model",
    vendor_version: "vv_market_data_page_model",
    rule_version: "rv_market_data_page_model",
    cache_version: "cv_market_data_page_model",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-30T09:00:00Z",
    ...partial,
  };
}

function catalogSeries(
  series_id: string,
  refresh_tier: MacroVendorSeries["refresh_tier"] = "stable",
): MacroVendorSeries {
  return {
    series_id,
    series_name: series_id,
    vendor_name: "choice",
    vendor_version: "vv_catalog",
    frequency: "daily",
    unit: "%",
    refresh_tier,
    fetch_mode: refresh_tier === "fallback" ? "latest" : "date_slice",
    fetch_granularity: refresh_tier === "fallback" ? "single" : "batch",
    policy_note: "test catalog",
  };
}

function latestPoint(
  series_id: string,
  trade_date: string,
  refresh_tier: ChoiceMacroLatestPoint["refresh_tier"] = "stable",
  partial: Partial<ChoiceMacroLatestPoint> = {},
): ChoiceMacroLatestPoint {
  return {
    series_id,
    series_name: series_id,
    trade_date,
    value_numeric: 2,
    frequency: "daily",
    unit: "%",
    source_version: "sv_latest",
    vendor_version: `vv_${trade_date}`,
    refresh_tier,
    fetch_mode: refresh_tier === "fallback" ? "latest" : "date_slice",
    fetch_granularity: refresh_tier === "fallback" ? "single" : "batch",
    policy_note: "test latest",
    quality_flag: refresh_tier === "fallback" ? "warning" : "ok",
    latest_change: 0.01,
    recent_points: [],
    ...partial,
  };
}

function envelope<T>(result: T, partialMeta: Partial<ResultMeta> = {}): ApiEnvelope<T> {
  return {
    result_meta: meta(partialMeta),
    result,
  };
}

const NON_FORMAL_OVERVIEW_METRIC_IDS = [
  "market-data-stable-count",
  "market-data-fallback-count",
  "market-data-stable-trade-date",
  "market-data-missing-stable-count",
  "market-data-fx-formal-materialized",
  "market-data-fx-analytical-group-count",
  "market-data-fx-analytical-series-count",
  "market-data-linkage-report-date",
];

function expectNoFormalMetricClaim(detail: string) {
  expect(detail).not.toMatch(/\bformal\b|MTR-|golden sample|capture-ready|正式指标|黄金样本/i);
}

describe("marketDataPageModel", () => {
  it("normalizes market-data envelopes into the page read model without inventing business values", () => {
    const catalogEnvelope = envelope<MacroVendorPayload>(
      {
        read_target: "duckdb",
        series: [
          catalogSeries("M_STABLE_PRESENT"),
          catalogSeries("M_STABLE_MISSING"),
          catalogSeries("M_FALLBACK", "fallback"),
        ],
      },
      { basis: "analytical", formal_use_allowed: false, result_kind: "macro.foundation" },
    );
    const latestEnvelope = envelope<ChoiceMacroLatestPayload>(
      {
        read_target: "duckdb",
        series: [
          latestPoint("M_STABLE_PRESENT", "2026-04-10", "stable", {
            recent_points: [
              {
                trade_date: "2026-04-10",
                value_numeric: 2,
                source_version: "sv_latest",
                vendor_version: "vv_2026-04-10",
                quality_flag: "ok",
              },
            ],
          }),
          latestPoint("M_FALLBACK", "2026-04-12", "fallback"),
          latestPoint("M_ISOLATED", "2026-04-13", "isolated"),
        ],
      },
      {
        basis: "analytical",
        formal_use_allowed: false,
        result_kind: "macro.choice.latest",
        vendor_version: "vv_latest",
      },
    );
    const fxGroup: FxAnalyticalGroup = {
      group_key: "middle_rate",
      title: "Analytical FX: middle-rates",
      description: "test fx",
      series: [
        {
          group_key: "middle_rate",
          series_id: "FX_USDCNY",
          series_name: "FX_USDCNY",
          trade_date: "2026-04-10",
          value_numeric: 7.1,
          frequency: "daily",
          unit: "CNY/USD",
          source_version: "sv_fx",
          vendor_version: "vv_fx",
          refresh_tier: "stable",
          fetch_mode: "date_slice",
          fetch_granularity: "batch",
          policy_note: "test fx",
          quality_flag: "ok",
          latest_change: null,
          recent_points: [],
        },
      ],
    };
    const fxEventGroup: FxAnalyticalGroup = {
      group_key: "fx_event_calendar",
      title: "Analytical FX: event calendar",
      description:
        "Tushare economic-calendar events for major FX currencies are analytical-only event context.",
      series: [],
      events: [
        {
          group_key: "fx_event_calendar",
          event_id: "eco-cny-trade",
          event_date: "20260612",
          event_time: "10:30",
          currency: "CNY",
          country: "China",
          event: "China trade balance",
          value: "105.43",
          pre_value: "84.8",
          fore_value: "92.1",
          source_version: "sv_tushare_eco",
          vendor_version: "vv_tushare_supplement_v1",
          quality_flag: "ok",
        },
      ],
    };
    const linkageEnvelope = envelope<MacroBondLinkagePayload>(
      {
        report_date: "2026-04-12",
        environment_score: { composite_score: 0.2 },
        portfolio_impact: { total_estimated_impact: 12 },
        top_correlations: [
          {
            series_id: "SPREAD_LOW",
            series_name: "Spread low",
            target_family: "credit_spread",
            target_tenor: "5Y",
            correlation_3m: 0.1,
            correlation_6m: 0.2,
            correlation_1y: 0.3,
            lead_lag_days: 1,
            direction: "positive",
          },
          {
            series_id: "SPREAD_HIGH",
            series_name: "Spread high",
            target_family: "credit_spread",
            target_tenor: "5Y",
            correlation_3m: -0.8,
            correlation_6m: 0.1,
            correlation_1y: 0.2,
            lead_lag_days: 2,
            direction: "negative",
          },
          {
            series_id: "RATE_10Y",
            series_name: "Rate 10Y",
            target_family: "treasury",
            target_tenor: "10Y",
            correlation_3m: 0.4,
            correlation_6m: 0.5,
            correlation_1y: 0.6,
            lead_lag_days: 0,
            direction: "positive",
          },
        ],
        warnings: ["lineage pending"],
        computed_at: "2026-04-12T09:00:00Z",
      },
      {
        basis: "analytical",
        formal_use_allowed: false,
        result_kind: "market_data.macro_bond_linkage",
        source_version: "sv_linkage",
      },
    );

    const model = buildMarketDataPageModel({
      catalogEnvelope,
      latestEnvelope,
      fxAnalyticalEnvelope: envelope(
        { read_target: "duckdb", groups: [fxGroup, fxEventGroup] },
        {
          basis: "analytical",
          formal_use_allowed: false,
          result_kind: "fx.analytical.groups",
          source_version: "sv_fx_analytical",
        },
      ),
      formalRatesEnvelope: envelope<ChoiceMacroLatestPayload>(
        { read_target: "duckdb", series: [latestPoint("EMM00166466", "2026-04-10")] },
        { basis: "formal", formal_use_allowed: true, source_version: "sv_formal_rates" },
      ),
      fxFormalStatusEnvelope: envelope<FxFormalStatusPayload>(
        {
          read_target: "duckdb",
          vendor_priority: ["choice"],
          candidate_count: 3,
          materialized_count: 2,
          latest_trade_date: "2026-04-10",
          carry_forward_count: 1,
          rows: [],
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          result_kind: "fx.formal.status",
          source_version: "sv_fx_formal",
        },
      ),
      macroBondLinkageEnvelope: linkageEnvelope,
    });

    expect(model.catalog).toHaveLength(3);
    expect(model.visibleLatestSeries.map((point) => point.series_id)).toEqual([
      "M_STABLE_PRESENT",
      "M_FALLBACK",
    ]);
    expect(model.stableSeries.map((point) => point.series_id)).toEqual(["M_STABLE_PRESENT"]);
    expect(model.fallbackSeries.map((point) => point.series_id)).toEqual(["M_FALLBACK"]);
    expect(model.missingStableSeries.map((series) => series.series_id)).toEqual([
      "M_STABLE_MISSING",
    ]);
    expect(model.stableLatestTradeDate).toBe("2026-04-10");
    expect(model.linkageReportDate).toBe("2026-04-12");
    expect(model.fxAnalyticalGroups).toHaveLength(2);
    expect(model.fxAnalyticalSeriesCount).toBe(2);
    expect(model.isFormalBasis).toBe(true);
    expect(model.statusBadges.readinessVerdict).toBe("数据正常");
    expect(model.sourcePendingCount).toBe(3);
    expect(model.hasPortfolioImpact).toBe(true);
    expect(model.macroBondLinkageWarnings).toEqual(["lineage pending"]);
    expect(model.evidenceLines).toEqual({
      formalRates:
        "formal rates: 正式可用 / 数据正常 / 可正式使用",
      macroLatest:
        "macro latest: 仅分析使用 / 数据正常 / 暂不可用于正式决策",
      fxFormal:
        "FX formal: 正式可用 / 数据正常 / 可正式使用",
      fxAnalytical:
        "FX analytical: 仅分析使用 / 数据正常 / 暂不可用于正式决策",
      ncdProxy:
        "NCD proxy: 未接入 / 部分缺失 / 查看数据诊断",
      livermore:
        "Livermore: 未接入 / 部分缺失 / 查看数据诊断",
      linkage:
        "macro-bond linkage: 仅分析使用 / 数据正常 / 暂不可用于正式决策",
    });
    expect(model.spreadSlots.find((slot) => slot.tenor === "5Y")?.point?.series_id).toBe(
      "SPREAD_HIGH",
    );
    expect(model.nonSpreadTopCorrelations.map((point) => point.series_id)).toEqual(["RATE_10Y"]);
    expect(model.terminalTickerItems.map((item) => [item.key, item.value, item.delta])).toEqual([
      ["cgb10y", "2%", "+1bp"],
    ]);
    expect(model.terminalKpiMetrics.map((metric) => [metric.testId, metric.value, metric.tone])).toEqual([
      ["market-data-terminal-kpi-cgb10y", "2%", "negative"],
    ]);
    expect(model.pipelineOverviewMetrics.map((metric) => [metric.testId, metric.value, metric.tone])).toEqual([
      ["market-data-catalog-count", "3", undefined],
      ["market-data-stable-count", "1 / 2", "warning"],
      ["market-data-fallback-count", "1", "warning"],
      ["market-data-stable-trade-date", "2026-04-10", "default"],
      ["market-data-missing-stable-count", "1", "warning"],
      ["market-data-fx-formal-materialized", "2 / 3", "default"],
      ["market-data-fx-analytical-group-count", "2", undefined],
      ["market-data-fx-analytical-series-count", "2", undefined],
      ["market-data-linkage-report-date", "2026-04-12", "default"],
    ]);
    const metricDetails = new Map(
      model.pipelineOverviewMetrics.map((metric) => [metric.testId, metric.detail]),
    );
    for (const metricId of NON_FORMAL_OVERVIEW_METRIC_IDS) {
      const detail = metricDetails.get(metricId);
      expect(detail, `${metricId} should expose display/status context`).toBeTruthy();
      expectNoFormalMetricClaim(detail ?? "");
    }
  });

  it("keeps empty and pending states explicit when envelopes have not loaded", () => {
    const model = buildMarketDataPageModel({});

    expect(model.catalog).toEqual([]);
    expect(model.latestSeries).toEqual([]);
    expect(model.rateTrendChartOption).toBeNull();
    expect(model.livermoreStrategy).toBeNull();
    expect(model.macroMeta).toBeUndefined();
    expect(model.isFormalBasis).toBe(false);
    expect(Object.values(model.evidenceLines)).toEqual([
      "formal rates: 未接入 / 部分缺失 / 查看数据诊断",
      "macro latest: 未接入 / 部分缺失 / 查看数据诊断",
      "FX formal: 未接入 / 部分缺失 / 查看数据诊断",
      "FX analytical: 未接入 / 部分缺失 / 查看数据诊断",
      "NCD proxy: 未接入 / 部分缺失 / 查看数据诊断",
      "Livermore: 未接入 / 部分缺失 / 查看数据诊断",
      "macro-bond linkage: 未接入 / 部分缺失 / 查看数据诊断",
    ]);
    expect(model.statusBadges.readinessVerdict).toBe("接入中");
    expect(model.statusBadges.overviewReadinessLabel).toBe("待确认");
    expect(model.statusBadges.secondaryLabel).toBe("查看数据诊断");
    expect(model.stableLatestTradeDate).toBe("—");
    expect(model.linkageReportDate).toBe("");
    expect(model.sourcePendingCount).toBe(3);
    expect(model.terminalKpiMetrics).toEqual([]);
    expect(model.pipelineOverviewMetrics.map((metric) => [metric.testId, metric.value, metric.tone])).toEqual([
      ["market-data-catalog-count", "0", undefined],
      ["market-data-stable-count", "0 / 0", "default"],
      ["market-data-fallback-count", "0", "default"],
      ["market-data-stable-trade-date", "—", "warning"],
      ["market-data-missing-stable-count", "0", "default"],
      ["market-data-fx-formal-materialized", "0 / 0", "warning"],
      ["market-data-fx-analytical-group-count", "0", undefined],
      ["market-data-fx-analytical-series-count", "0", undefined],
      ["market-data-linkage-report-date", "—", "warning"],
    ]);
  });

  it("counts bond futures as connected when the CFFEX rankings envelope is present", () => {
    const model = buildMarketDataPageModel({
      bondFuturesRankingsEnvelope: envelope(
        {
          read_target: "duckdb",
          as_of_date: "2026-06-11",
          requested_trade_date: null,
          contract: "T.CFE",
          rows: [
            {
              trade_date: "2026-06-11",
              contract: "T.CFE",
              product_code: "T",
              exchange: "CFFEX",
              member_name: "中信期货",
              source_vendor: "tushare",
              source_row_no: 1,
              volume: 12345,
              volume_change: 101,
              long_holding: 23456,
              long_change: 202,
              short_holding: 21000,
              short_change: -50,
              source_version: "sv_test_cffex_rank",
              vendor_version: "vv_test_tushare",
              rule_version: "rv_cffex_member_rank_choice_tushare_v1",
            },
          ],
          warnings: [],
        },
        {
          basis: "analytical",
          result_kind: "market_data.bond_futures_rankings",
          formal_use_allowed: false,
          source_version: "sv_test_cffex_rank",
          vendor_version: "vv_test_tushare",
          rule_version: "rv_cffex_member_rank_choice_tushare_v1",
          cache_version: "cv_market_data_bond_futures_rankings_v1",
          source_surface: "market_data",
        },
      ),
    });

    expect(model.sourcePendingCount).toBe(2);
    const bondFutures = model.terminalModel.bondFutures;
    expect(bondFutures.status).toBe("ready");
    if (bondFutures.status === "source-pending") {
      throw new Error("Expected bond futures rankings to be connected");
    }
    expect(bondFutures.rows[0].memberName).toBe("中信期货");
  });

  it("prefers the backend coverage summary for supply gaps when present", () => {
    const coverageEnvelope = envelope<MarketDataCoverageSummaryPayload>(
      {
        read_target: "duckdb",
        as_of_date: "2026-06-15",
        generated_at: "2026-06-15T09:30:00Z",
        headline: {
          readiness_label: "mixed-source supply map",
          formal_fragment_ready: true,
          formal_use_allowed: false,
          analytical_warning_count: 1,
          source_pending_count: 2,
          proxy_only_count: 1,
        },
        sections: [
          {
            key: "bond_futures",
            label: "Bond futures",
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
          {
            key: "cash_bond_trades",
            label: "Cash trades",
            status: "source_pending",
            basis: "analytical",
            formal_use_allowed: false,
            quality_flag: "warning",
            fallback_mode: "none",
            vendor_status: "vendor_unavailable",
            source_pending: true,
            proxy_only: false,
            message: "contract pending",
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
            message: "contract pending",
          },
        ],
        actions: [],
      },
      {
        basis: "analytical",
        formal_use_allowed: false,
        result_kind: "market_data.coverage_summary",
      },
    );

    const model = buildMarketDataPageModel({ coverageSummaryEnvelope: coverageEnvelope });

    expect(model.coverageSummary?.headline.source_pending_count).toBe(2);
    expect(model.sourcePendingCount).toBe(2);
    expect(model.coverageSections.map((section) => section.key)).toEqual([
      "bond_futures",
      "cash_bond_trades",
      "credit_trades",
    ]);
  });

  it("does not treat analytical rates as formal page basis", () => {
    const model = buildMarketDataPageModel({
      formalRatesEnvelope: envelope<ChoiceMacroLatestPayload>(
        { read_target: "duckdb", series: [latestPoint("EMM00166466", "2026-04-10")] },
        {
          basis: "analytical",
          formal_use_allowed: false,
          fallback_mode: "latest_snapshot",
          source_version: "sv_analytical_rates",
        },
      ),
    });

    expect(model.isFormalBasis).toBe(false);
    expect(model.evidenceLines.formalRates).toBe(
      "formal rates: 仅分析使用 / 数据正常 / 暂不可用于正式决策 / 数据延迟",
    );
  });

  it("does not treat formal-labeled rates as formal when formal use is forbidden", () => {
    const model = buildMarketDataPageModel({
      formalRatesEnvelope: envelope<ChoiceMacroLatestPayload>(
        { read_target: "duckdb", series: [latestPoint("EMM00166466", "2026-04-10")] },
        {
          basis: "formal",
          formal_use_allowed: false,
          result_kind: "market_data.rates",
          source_version: "sv_candidate_rates",
        },
      ),
    });

    expect(model.isFormalBasis).toBe(false);
    expect(model.evidenceLines.formalRates).toBe(
      "formal rates: 暂不可正式使用 / 数据正常 / 暂不可用于正式决策",
    );
  });

  it("surfaces stale result quality in evidence lines", () => {
    const model = buildMarketDataPageModel({
      formalRatesEnvelope: envelope<ChoiceMacroLatestPayload>(
        { read_target: "duckdb", series: [latestPoint("EMM00166466", "2026-04-10")] },
        {
          basis: "formal",
          formal_use_allowed: true,
          quality_flag: "stale",
          source_version: "sv_stale_rates",
        },
      ),
    });

    expect(model.evidenceLines.formalRates).toBe(
      "formal rates: 正式可用 / 数据延迟 / 需复核",
    );
  });

  it("builds FX formal collapse label from materialized counts", () => {
    expect(
      buildFxFormalStatusCollapseLabel({
        payload: {
          read_target: "duckdb",
          vendor_priority: ["choice"],
          candidate_count: 3,
          materialized_count: 2,
          latest_trade_date: "2026-04-10",
          carry_forward_count: 1,
          rows: [],
        },
        isLoading: false,
        isError: false,
      }),
    ).toContain("物化 2/3");
  });

  it("prefers spread_tenor_correlations over top_correlations filtering", () => {
    const spreadTenorCorrelations: MacroBondLinkageTopCorrelation[] = [
      {
        series_id: "DEDICATED_5Y",
        series_name: "Dedicated spread 5Y",
        target_family: "credit_spread",
        target_tenor: "5Y",
        correlation_3m: 0.5,
        correlation_6m: 0.6,
        correlation_1y: 0.7,
        lead_lag_days: 1,
        direction: "positive",
      },
    ];
    const topCorrelations: MacroBondLinkageTopCorrelation[] = [
      {
        series_id: "RATE_ONLY",
        series_name: "Rate only",
        target_family: "treasury",
        target_tenor: "10Y",
        correlation_3m: 0.9,
        correlation_6m: 0.9,
        correlation_1y: 0.9,
        lead_lag_days: 0,
        direction: "positive",
      },
    ];

    expect(
      buildSpreadSlots(topCorrelations, "both", spreadTenorCorrelations).find((slot) => slot.tenor === "5Y")?.point
        ?.series_id,
    ).toBe("DEDICATED_5Y");
  });

  it("filters spread slots by credit segment from linkage series names", () => {
    const correlations: MacroBondLinkageTopCorrelation[] = [
      {
        series_id: "MTN_5Y",
        series_name: "中票AAA 5Y",
        target_family: "credit_spread",
        target_tenor: "5Y",
        correlation_3m: 0.1,
        correlation_6m: 0.2,
        correlation_1y: 0.9,
        lead_lag_days: 1,
        direction: "positive",
      },
      {
        series_id: "URBAN_5Y",
        series_name: "城投AA 5Y",
        target_family: "credit_spread",
        target_tenor: "5Y",
        correlation_3m: 0.4,
        correlation_6m: 0.5,
        correlation_1y: 0.2,
        lead_lag_days: 2,
        direction: "negative",
      },
    ];

    expect(buildSpreadSlots(correlations, "mtn").find((slot) => slot.tenor === "5Y")?.point?.series_id).toBe(
      "MTN_5Y",
    );
    expect(buildSpreadSlots(correlations, "urban").find((slot) => slot.tenor === "5Y")?.point?.series_id).toBe(
      "URBAN_5Y",
    );
  });
});

describe("bridge helpers", () => {
  const metrics = [
    {
      testId: "market-data-terminal-kpi-cdb10y",
      title: "10年国开",
      value: "1.82%",
      detail: "0bp",
    },
    {
      testId: "market-data-terminal-kpi-cgb10y",
      title: "10年国债",
      value: "1.75%",
      detail: "-1bp",
    },
    {
      testId: "market-data-terminal-kpi-dr007",
      title: "DR007",
      value: "1.44%",
      detail: "+3bp",
    },
  ];

  it("prioritizes bridge metrics for trader-relevant keys", () => {
    expect(buildBridgeKpiMetrics(metrics).map((item) => item.testId)).toEqual([
      "market-data-terminal-kpi-cgb10y",
      "market-data-terminal-kpi-dr007",
      "market-data-terminal-kpi-cdb10y",
    ]);
    expect(pickRailHighlightMetric(metrics)?.testId).toBe("market-data-terminal-kpi-dr007");
    expect(
      buildMarketDataBasisChipLabel({
        basisLabel: "formal",
        formalUseAllowedLabel: "是",
        formalUseBlocked: false,
        watchDate: "2026-06-11",
      }),
    ).toBe("formal · 正式使用 是 · 观察日 2026-06-11");
  });
});

describe("formatMarketWorkbenchSourceSummary", () => {
  it("summarizes multiple vendor versions for the page header", () => {
    const result = formatMarketWorkbenchSourceSummary(
      ["vv_a", "vv_b", "vv_c"],
      "source-pending",
    );
    expect(result.value).toBe("3 路供应商版本");
    expect(result.hint).toBe("vv_a / vv_b / vv_c");
  });

  it("returns fallback when no vendor versions are present", () => {
    expect(formatMarketWorkbenchSourceSummary([], "source-pending")).toEqual({
      value: "source-pending",
    });
  });
});
