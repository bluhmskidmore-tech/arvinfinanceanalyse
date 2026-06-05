import { describe, expect, it } from "vitest";

import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  FxAnalyticalGroup,
  MacroBondLinkagePayload,
  MacroVendorPayload,
  MacroVendorSeries,
  ResultMeta,
} from "../../../api/contracts";
import { buildMarketDataPageModel } from "./marketDataPageModel";

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
        { read_target: "duckdb", groups: [fxGroup] },
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
    expect(model.fxAnalyticalGroups).toHaveLength(1);
    expect(model.fxAnalyticalSeriesCount).toBe(1);
    expect(model.isFormalBasis).toBe(true);
    expect(model.statusBadges.readinessVerdict).toBe("读面就绪");
    expect(model.sourcePendingCount).toBe(3);
    expect(model.hasPortfolioImpact).toBe(true);
    expect(model.macroBondLinkageWarnings).toEqual(["lineage pending"]);
    expect(model.evidenceLines).toEqual({
      formalRates:
        "formal rates: basis=formal formal_use_allowed=true quality=ok fallback=none vendor_status=ok source=sv_formal_rates",
      macroLatest:
        "macro latest: basis=analytical formal_use_allowed=false quality=ok fallback=none vendor_status=ok source=sv_market_data_page_model",
      fxAnalytical:
        "FX analytical: basis=analytical formal_use_allowed=false quality=ok fallback=none vendor_status=ok source=sv_fx_analytical",
      ncdProxy:
        "NCD proxy: basis=pending formal_use_allowed=pending quality=pending fallback=pending vendor_status=pending source=pending",
      livermore:
        "Livermore: basis=pending formal_use_allowed=pending quality=pending fallback=pending vendor_status=pending source=pending",
      linkage:
        "macro-bond linkage: basis=analytical formal_use_allowed=false quality=ok fallback=none vendor_status=ok source=sv_linkage",
    });
    expect(model.spreadSlots.find((slot) => slot.tenor === "5Y")?.point?.series_id).toBe(
      "SPREAD_HIGH",
    );
    expect(model.nonSpreadTopCorrelations.map((point) => point.series_id)).toEqual(["RATE_10Y"]);
    expect(model.overviewMetrics.map((metric) => [metric.testId, metric.value, metric.tone])).toEqual([
      ["market-data-catalog-count", "3", undefined],
      ["market-data-stable-count", "1 / 2", "warning"],
      ["market-data-fallback-count", "1", "warning"],
      ["market-data-stable-trade-date", "2026-04-10", "default"],
      ["market-data-missing-stable-count", "1", "warning"],
      ["market-data-fx-analytical-group-count", "1", undefined],
      ["market-data-fx-analytical-series-count", "1", undefined],
      ["market-data-linkage-report-date", "2026-04-12", "default"],
    ]);
    const metricDetails = new Map(
      model.overviewMetrics.map((metric) => [metric.testId, metric.detail]),
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
      "formal rates: basis=pending formal_use_allowed=pending quality=pending fallback=pending vendor_status=pending source=pending",
      "macro latest: basis=pending formal_use_allowed=pending quality=pending fallback=pending vendor_status=pending source=pending",
      "FX analytical: basis=pending formal_use_allowed=pending quality=pending fallback=pending vendor_status=pending source=pending",
      "NCD proxy: basis=pending formal_use_allowed=pending quality=pending fallback=pending vendor_status=pending source=pending",
      "Livermore: basis=pending formal_use_allowed=pending quality=pending fallback=pending vendor_status=pending source=pending",
      "macro-bond linkage: basis=pending formal_use_allowed=pending quality=pending fallback=pending vendor_status=pending source=pending",
    ]);
    expect(model.statusBadges.readinessVerdict).toBe("读面就绪");
    expect(model.stableLatestTradeDate).toBe("—");
    expect(model.linkageReportDate).toBe("");
    expect(model.sourcePendingCount).toBe(3);
    expect(model.overviewMetrics.map((metric) => [metric.testId, metric.value, metric.tone])).toEqual([
      ["market-data-catalog-count", "0", undefined],
      ["market-data-stable-count", "0 / 0", "default"],
      ["market-data-fallback-count", "0", "default"],
      ["market-data-stable-trade-date", "—", "warning"],
      ["market-data-missing-stable-count", "0", "default"],
      ["market-data-fx-analytical-group-count", "0", undefined],
      ["market-data-fx-analytical-series-count", "0", undefined],
      ["market-data-linkage-report-date", "—", "warning"],
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
      "formal rates: basis=analytical formal_use_allowed=false quality=ok fallback=latest_snapshot vendor_status=ok source=sv_analytical_rates",
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
      "formal rates: basis=formal formal_use_allowed=false quality=ok fallback=none vendor_status=ok source=sv_candidate_rates",
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
      "formal rates: basis=formal formal_use_allowed=true quality=stale fallback=none vendor_status=ok source=sv_stale_rates",
    );
  });
});
