import { describe, expect, it } from "vitest";

import {
  buildMarketDataMultiSeriesTimeChartOption,
  buildMarketDataSeriesTimeChartOption,
} from "./marketDataSeriesTimeChartOption";

describe("marketDataSeriesTimeChartOption", () => {
  it("builds a line chart from recent_points", () => {
    const option = buildMarketDataSeriesTimeChartOption({
      series_id: "S1",
      series_name: "DR007",
      unit: "%",
      quality_flag: "ok",
      recent_points: [
        { trade_date: "2026-06-11", value_numeric: 1.8, quality_flag: "ok", source_version: "sv", vendor_version: "vv" },
        { trade_date: "2026-06-12", value_numeric: 1.83, quality_flag: "ok", source_version: "sv", vendor_version: "vv" },
      ],
    });
    expect(option?.series).toHaveLength(1);
    expect((option?.xAxis as { data?: string[] }).data).toEqual(["2026-06-11", "2026-06-12"]);
  });

  it("returns null when recent_points are missing", () => {
    expect(
      buildMarketDataSeriesTimeChartOption({
        series_id: "S1",
        series_name: "Empty",
        unit: "%",
        quality_flag: "ok",
      }),
    ).toBeNull();
  });

  it("supports a sheet variant for dense market-data preview charts", () => {
    const option = buildMarketDataSeriesTimeChartOption(
      {
        series_id: "DR007",
        series_name: "存款类机构质押式回购加权利率:DR007",
        unit: "%",
        quality_flag: "ok",
        recent_points: [
          { trade_date: "2026-06-11", value_numeric: 1.4, quality_flag: "ok", source_version: "sv", vendor_version: "vv" },
          { trade_date: "2026-06-12", value_numeric: 1.46, quality_flag: "ok", source_version: "sv", vendor_version: "vv" },
        ],
      },
      { variant: "sheet" },
    );

    expect(option?.title).toBeUndefined();
    expect(option?.grid).toMatchObject({ left: 34, right: 20, top: 12, bottom: 28 });

    const series = option?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected sheet chart to expose a series array");
    }
    expect(series[0]).toMatchObject({
      type: "line",
      symbolSize: 4,
      lineStyle: { width: 2 },
      areaStyle: undefined,
    });
  });

  it("merges multiple series onto a shared timeline", () => {
    const option = buildMarketDataMultiSeriesTimeChartOption([
      {
        series_id: "A",
        series_name: "A",
        unit: "%",
        quality_flag: "ok",
        recent_points: [{ trade_date: "2026-06-11", value_numeric: 1.1, quality_flag: "ok", source_version: "sv", vendor_version: "vv" }],
      },
      {
        series_id: "B",
        series_name: "B",
        unit: "%",
        quality_flag: "ok",
        recent_points: [{ trade_date: "2026-06-12", value_numeric: 2.2, quality_flag: "ok", source_version: "sv", vendor_version: "vv" }],
      },
    ]);
    expect(Array.isArray(option?.series) ? option.series.length : 0).toBe(2);
    expect((option?.xAxis as { data?: string[] }).data).toEqual(["2026-06-11", "2026-06-12"]);
  });

  it("weights the default rate trend lines like a market desk chart", () => {
    const option = buildMarketDataMultiSeriesTimeChartOption([
      {
        series_id: "CGB10Y",
        series_name: "10年国债",
        unit: "%",
        quality_flag: "ok",
        recent_points: [
          { trade_date: "2026-06-11", value_numeric: 1.71, quality_flag: "ok", source_version: "sv", vendor_version: "vv" },
          { trade_date: "2026-06-12", value_numeric: 1.75, quality_flag: "ok", source_version: "sv", vendor_version: "vv" },
        ],
      },
      {
        series_id: "CDB5Y",
        series_name: "5年国开",
        unit: "%",
        quality_flag: "ok",
        recent_points: [
          { trade_date: "2026-06-11", value_numeric: 1.44, quality_flag: "ok", source_version: "sv", vendor_version: "vv" },
          { trade_date: "2026-06-12", value_numeric: 1.48, quality_flag: "ok", source_version: "sv", vendor_version: "vv" },
        ],
      },
    ]);

    expect(option?.grid).toMatchObject({ left: 48, right: 56, top: 20 });
    expect((option?.tooltip as { axisPointer?: { type?: string } }).axisPointer?.type).toBe("line");

    const series = option?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected rate trend chart to expose series array");
    }

    expect(series[0]).toMatchObject({
      type: "line",
      symbol: "circle",
      symbolSize: 7,
      lineStyle: { width: 2.2 },
      endLabel: { show: true, formatter: "10Y CGB" },
    });
    expect(series[1]).toMatchObject({
      type: "line",
      lineStyle: { width: 1.7, opacity: 0.72 },
      endLabel: { show: true, formatter: "5Y CDB" },
    });
  });
});
