import { describe, expect, it } from "vitest";

import type { ChoiceMacroRecentPoint } from "../../../../api/contracts";
import { nocturneTokens } from "../../../../theme/designSystem";
import { marketDataChartTheme } from "./marketDataChartTheme";
import {
  buildMarketDataMultiSeriesTimeChartOption,
  buildMarketDataSeriesTimeChartOption,
  MARKET_DATA_MULTI_SERIES_DEFAULT_VISIBLE,
  type MarketDataSeriesTimeInput,
} from "./marketDataSeriesTimeChartOption";

function recentPoint(tradeDate: string, value: number): ChoiceMacroRecentPoint {
  return {
    trade_date: tradeDate,
    value_numeric: value,
    quality_flag: "ok",
    source_version: "sv",
    vendor_version: "vv",
  };
}

type AxisShape = {
  data?: string[];
  splitNumber?: number;
  axisTick?: { show?: boolean };
  axisLabel?: {
    hideOverlap?: boolean;
    formatter?: (value: never, index?: number) => string;
  };
};

describe("marketDataSeriesTimeChartOption", () => {
  it("builds a line chart from recent_points", () => {
    const option = buildMarketDataSeriesTimeChartOption({
      series_id: "S1",
      series_name: "DR007",
      unit: "%",
      quality_flag: "ok",
      recent_points: [recentPoint("2026-06-11", 1.8), recentPoint("2026-06-12", 1.83)],
    });
    expect(option?.series).toHaveLength(1);
    expect((option?.xAxis as AxisShape).data).toEqual(["2026-06-11", "2026-06-12"]);
    expect(option?.color).toEqual([marketDataChartTheme.multiSeriesPalette[0]]);

    const series = option?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected chart to expose a series array");
    }
    expect(series[0]).toMatchObject({
      type: "line",
      showSymbol: false,
      lineStyle: { width: 2 },
    });
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
        recent_points: [recentPoint("2026-06-11", 1.4), recentPoint("2026-06-12", 1.46)],
      },
      { variant: "sheet" },
    );

    expect(option?.title).toBeUndefined();
    expect(option?.grid).toMatchObject({ left: 8, right: 12, containLabel: true });

    const series = option?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected sheet chart to expose a series array");
    }
    expect(series[0]).toMatchObject({
      type: "line",
      symbolSize: 4,
      showSymbol: false,
      lineStyle: { width: 1.5 },
      areaStyle: undefined,
    });
  });

  it("abbreviates large y-axis labels with 万/亿 and keeps sparse splits", () => {
    const option = buildMarketDataSeriesTimeChartOption({
      series_id: "M2",
      series_name: "货币供应量M2",
      unit: "亿元",
      quality_flag: "ok",
      recent_points: [recentPoint("2026-05-31", 3050000), recentPoint("2026-06-30", 3120000)],
    });

    const yAxis = option?.yAxis as AxisShape;
    const formatter = yAxis.axisLabel?.formatter as (value: number) => string;
    expect(formatter(120000)).toBe("12万");
    expect(formatter(8_000_000)).toBe("800万");
    expect(formatter(123_450_000)).toBe("1.2亿");
    expect(formatter(-15_000)).toBe("-1.5万");
    expect(formatter(1.75)).toBe("1.75");
    expect(yAxis.splitNumber).toBe(4);
  });

  it("sparsifies date labels as MM-DD with YYYY-MM at year switches and hides axis ticks", () => {
    const sameYear = buildMarketDataSeriesTimeChartOption({
      series_id: "S1",
      series_name: "DR007",
      unit: "%",
      quality_flag: "ok",
      recent_points: [recentPoint("2026-06-11", 1.8), recentPoint("2026-06-12", 1.83)],
    });
    const sameYearAxis = sameYear?.xAxis as AxisShape;
    const sameYearFormatter = sameYearAxis.axisLabel?.formatter as (value: string, index: number) => string;
    expect(sameYearFormatter("2026-06-12", 1)).toBe("06-12");
    expect(sameYearAxis.axisTick?.show).toBe(false);
    expect(sameYearAxis.axisLabel?.hideOverlap).toBe(true);

    const crossYear = buildMarketDataSeriesTimeChartOption({
      series_id: "S1",
      series_name: "DR007",
      unit: "%",
      quality_flag: "ok",
      recent_points: [
        recentPoint("2025-12-30", 1.7),
        recentPoint("2026-01-05", 1.72),
        recentPoint("2026-01-06", 1.74),
      ],
    });
    const crossYearFormatter = (crossYear?.xAxis as AxisShape).axisLabel?.formatter as (
      value: string,
      index: number,
    ) => string;
    expect(crossYearFormatter("2025-12-30", 0)).toBe("2025-12");
    expect(crossYearFormatter("2026-01-05", 1)).toBe("2026-01");
    expect(crossYearFormatter("2026-01-06", 2)).toBe("01-06");
  });

  it("merges multiple series onto a shared timeline", () => {
    const option = buildMarketDataMultiSeriesTimeChartOption([
      {
        series_id: "A",
        series_name: "A",
        unit: "%",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-11", 1.1)],
      },
      {
        series_id: "B",
        series_name: "B",
        unit: "%",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-12", 2.2)],
      },
    ]);
    expect(Array.isArray(option?.series) ? option.series.length : 0).toBe(2);
    expect((option?.xAxis as AxisShape).data).toEqual(["2026-06-11", "2026-06-12"]);
  });

  it("weights the default rate trend lines like a market desk chart", () => {
    const option = buildMarketDataMultiSeriesTimeChartOption([
      {
        series_id: "CGB10Y",
        series_name: "10年国债",
        unit: "%",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-11", 1.71), recentPoint("2026-06-12", 1.75)],
      },
      {
        series_id: "CDB5Y",
        series_name: "5年国开",
        unit: "%",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-11", 1.44), recentPoint("2026-06-12", 1.48)],
      },
    ]);

    expect(option?.grid).toMatchObject({ left: 8, right: 12, bottom: 28, containLabel: true });
    expect((option?.tooltip as { axisPointer?: { type?: string } }).axisPointer?.type).toBe("line");

    const series = option?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected rate trend chart to expose series array");
    }

    expect(series[0]).toMatchObject({
      type: "line",
      symbol: "circle",
      showSymbol: false,
      lineStyle: { width: 2, color: marketDataChartTheme.multiSeriesPalette[0] },
    });
    expect(series[1]).toMatchObject({
      type: "line",
      showSymbol: false,
      lineStyle: { width: 1.5, color: marketDataChartTheme.multiSeriesPalette[1] },
    });
  });

  it("keeps a plain legend and lights only the leading series by default", () => {
    const manySeries: MarketDataSeriesTimeInput[] = ["A", "B", "C", "D", "E", "F"].map((name, index) => ({
      series_id: name,
      series_name: name,
      unit: "%",
      quality_flag: "ok",
      recent_points: [recentPoint("2026-06-11", 1 + index), recentPoint("2026-06-12", 1.1 + index)],
    }));
    const option = buildMarketDataMultiSeriesTimeChartOption(manySeries);

    const legend = option?.legend as {
      type?: string;
      itemWidth?: number;
      selected?: Record<string, boolean>;
      textStyle?: { color?: string; fontSize?: number; overflow?: string };
    };
    expect(legend.type).toBe("plain");
    expect(legend.itemWidth).toBe(12);
    expect(legend.textStyle).toMatchObject({
      color: nocturneTokens.color.inkSoft,
      fontSize: 11,
      overflow: "truncate",
    });
    expect(legend.selected).toEqual({ A: true, B: true, C: true, D: true, E: false, F: false });
    expect(Object.values(legend.selected ?? {}).filter(Boolean)).toHaveLength(
      MARKET_DATA_MULTI_SERIES_DEFAULT_VISIBLE,
    );

    const fewSeries = buildMarketDataMultiSeriesTimeChartOption(manySeries.slice(0, 2));
    expect((fewSeries?.legend as { selected?: Record<string, boolean> }).selected).toBeUndefined();
  });
});
