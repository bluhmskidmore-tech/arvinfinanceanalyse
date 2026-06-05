import { describe, expect, it } from "vitest";

import type {
  ChoiceMacroLatestPoint,
  FxAnalyticalGroup,
  MacroVendorSeries,
} from "../../../api/contracts";
import { buildMarketDataCategoryStore } from "./marketDataCategoryStore";

function makeCatalogSeries(
  series_id: string,
  refresh_tier: MacroVendorSeries["refresh_tier"] = "stable",
): MacroVendorSeries {
  return {
    series_id,
    series_name: series_id,
    vendor_name: "choice",
    vendor_version: "vv_test",
    frequency: "daily",
    unit: "%",
    refresh_tier,
    fetch_mode: "date_slice",
    fetch_granularity: "batch",
    policy_note: "test catalog",
  };
}

function makeLatestPoint(
  series_id: string,
  trade_date: string,
  refresh_tier: ChoiceMacroLatestPoint["refresh_tier"] = "stable",
): ChoiceMacroLatestPoint {
  return {
    series_id,
    series_name: series_id,
    trade_date,
    value_numeric: 1,
    frequency: "daily",
    unit: "%",
    source_version: "sv_test",
    vendor_version: "vv_test",
    refresh_tier,
    fetch_mode: "date_slice",
    fetch_granularity: "batch",
    policy_note: "test latest",
    quality_flag: "ok",
    latest_change: null,
    recent_points: [],
  };
}

describe("marketDataCategoryStore", () => {
  it("classifies macro latest rows and exposes derived read keys for the page", () => {
    const store = buildMarketDataCategoryStore({
      catalog: [
        makeCatalogSeries("M_STABLE_PRESENT"),
        makeCatalogSeries("M_STABLE_MISSING"),
        makeCatalogSeries("M_FALLBACK", "fallback"),
      ],
      latestSeries: [
        makeLatestPoint("M_STABLE_PRESENT", "2026-04-10", "stable"),
        makeLatestPoint("M_FALLBACK", "2026-04-09", "fallback"),
        makeLatestPoint("M_ISOLATED", "2026-04-11", "isolated"),
      ],
      fxAnalyticalGroups: [
        {
          group_key: "middle_rate",
          title: "Middle rate",
          description: "test",
          series: [
            {
              series_id: "FX_USDCNY",
              series_name: "FX_USDCNY",
              trade_date: "2026-04-08",
              value_numeric: 7.2,
              frequency: "daily",
              unit: "CNY/USD",
              source_version: "sv_fx_test",
              vendor_version: "vv_fx_test",
              refresh_tier: "stable",
              fetch_mode: "date_slice",
              fetch_granularity: "batch",
              policy_note: "test fx",
              quality_flag: "ok",
              latest_change: null,
              recent_points: [],
              group_key: "middle_rate",
            },
          ],
        } satisfies FxAnalyticalGroup,
      ],
    });

    expect(store.visibleLatestSeries.map((point) => point.series_id)).toEqual([
      "M_STABLE_PRESENT",
      "M_FALLBACK",
    ]);
    expect(store.stableSeries.map((point) => point.series_id)).toEqual(["M_STABLE_PRESENT"]);
    expect(store.fallbackSeries.map((point) => point.series_id)).toEqual(["M_FALLBACK"]);
    expect(store.stableCatalogSeries.map((series) => series.series_id)).toEqual([
      "M_STABLE_PRESENT",
      "M_STABLE_MISSING",
    ]);
    expect(store.missingStableSeries.map((series) => series.series_id)).toEqual([
      "M_STABLE_MISSING",
    ]);
    expect(store.stableLatestTradeDate).toBe("2026-04-10");
    expect(store.linkageReportDate).toBe("2026-04-10");
    expect(store.vendorVersions).toEqual(["vv_test"]);
    expect(store.fxAnalyticalSeriesCount).toBe(1);
    expect(store.stablePipelineTone).toBe("warning");
  });
});
