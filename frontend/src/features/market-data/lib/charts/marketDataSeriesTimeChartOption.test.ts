import { describe, expect, it } from "vitest";

import type { ChoiceMacroRecentPoint } from "../../../../api/contracts";
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
  name?: string;
  position?: string;
  splitLine?: { show?: boolean };
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

    expect(option?.grid).toMatchObject({ left: 8, right: 12, top: 16 });
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

  it("splits series with different units onto separate y axes", () => {
    const option = buildMarketDataMultiSeriesTimeChartOption([
      {
        series_id: "GDP",
        series_name: "GDP:现价:累计值",
        unit: "亿元",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-03-31", 1301879.2), recentPoint("2026-06-30", 1401879.2)],
      },
      {
        series_id: "GDP_YOY",
        series_name: "GDP:不变价:当季同比",
        unit: "%",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-03-31", 5.4), recentPoint("2026-06-30", 5.3)],
      },
      {
        series_id: "IVA_YOY",
        series_name: "工业增加值:当月同比",
        unit: "%",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-03-31", 6.1), recentPoint("2026-06-30", 5.8)],
      },
    ]);

    const yAxis = option?.yAxis as AxisShape[];
    expect(Array.isArray(yAxis)).toBe(true);
    expect(yAxis).toHaveLength(2);
    // 序列数多的 % 簇占主轴，亿元簇走右轴且不画分割线。
    expect(yAxis[0]?.name).toBe("%");
    expect(yAxis[1]?.name).toBe("亿元");
    expect(yAxis[1]?.position).toBe("right");
    expect(yAxis[1]?.splitLine?.show).toBe(false);
    expect(option?.grid).toMatchObject({ top: 30 });

    const series = option?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected dual-axis chart to expose series array");
    }
    expect(series.map((item) => (item as { yAxisIndex?: number }).yAxisIndex)).toEqual([1, 0, 0]);
  });

  it("splits same-unit series whose magnitudes span more than 100x", () => {
    const option = buildMarketDataMultiSeriesTimeChartOption([
      {
        series_id: "OMO",
        series_name: "公开市场操作:投放量",
        unit: "亿元",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-11", 1800), recentPoint("2026-06-12", 3000)],
      },
      {
        series_id: "M2",
        series_name: "货币供应量M2",
        unit: "亿元",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-05-31", 3050000), recentPoint("2026-06-30", 3120000)],
      },
    ]);

    const yAxis = option?.yAxis as AxisShape[];
    expect(Array.isArray(yAxis)).toBe(true);
    expect(yAxis).toHaveLength(2);
    expect(yAxis[0]?.name).toBe("亿元");
    expect(yAxis[1]?.name).toBe("亿元");
  });

  it("hides placeholder units like unknown from axis names", () => {
    const option = buildMarketDataMultiSeriesTimeChartOption([
      {
        series_id: "M0",
        series_name: "M0",
        unit: "unknown",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-05-31", 140000), recentPoint("2026-06-30", 147364)],
      },
      {
        series_id: "M0_YOY",
        series_name: "M0:同比",
        unit: "unknown",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-05-31", 11.3), recentPoint("2026-06-30", 11.8)],
      },
    ]);

    // unit 为占位值 "unknown" 时仍按数量级拆轴，但轴名不显示占位字面量。
    const yAxis = option?.yAxis as AxisShape[];
    expect(Array.isArray(yAxis)).toBe(true);
    expect(yAxis).toHaveLength(2);
    expect(yAxis[0]?.name).toBe("");
    expect(yAxis[1]?.name).toBe("");
  });

  it("keeps only the two largest unit clusters and drops the rest from the chart", () => {
    const option = buildMarketDataMultiSeriesTimeChartOption([
      {
        series_id: "BRENT",
        series_name: "布伦特原油期货结算价",
        unit: "USD/bbl",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-11", 95.2), recentPoint("2026-06-12", 96.1)],
      },
      {
        series_id: "RB",
        series_name: "螺纹钢主力期货收盘价",
        unit: "CNY/t",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-11", 3103), recentPoint("2026-06-12", 3120)],
      },
      {
        series_id: "AU",
        series_name: "黄金主力期货收盘价",
        unit: "CNY/g",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-11", 552.4), recentPoint("2026-06-12", 548.9)],
      },
    ]);

    const series = option?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected chart to expose a series array");
    }
    // 三个单位簇并列（各 1 条）时按出现顺序保留前两簇，其余不入图。
    expect(series.map((item) => (item as { name?: string }).name)).toEqual([
      "布伦特原油期货结算价",
      "螺纹钢主力期货收盘价",
    ]);
    // 未入图序列不应把日期并进时间轴。
    expect((option?.xAxis as AxisShape).data).toEqual(["2026-06-11", "2026-06-12"]);
  });

  it("keeps a single y axis for same-unit series within the magnitude span", () => {
    const option = buildMarketDataMultiSeriesTimeChartOption([
      {
        series_id: "A",
        series_name: "DR007",
        unit: "%",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-11", 1.71)],
      },
      {
        series_id: "B",
        series_name: "R007",
        unit: "%",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-12", 1.92)],
      },
    ]);

    expect(Array.isArray(option?.yAxis)).toBe(false);
    expect(option?.grid).toMatchObject({ top: 16 });
  });

  it("prefers cleaned display_name for series names and legend keys", () => {
    const single = buildMarketDataSeriesTimeChartOption({
      series_id: "DR007",
      series_name: "存款类机构质押式回购加权利率:DR007",
      display_name: "存款类机构质押式回购加权利率",
      unit: "%",
      quality_flag: "ok",
      recent_points: [recentPoint("2026-06-11", 1.4), recentPoint("2026-06-12", 1.46)],
    });
    expect(single?.title).toBeUndefined();
    expect(((single?.series as Array<{ name?: string }>)[0]?.name)).toBe(
      "存款类机构质押式回购加权利率",
    );

    const manySeries: MarketDataSeriesTimeInput[] = ["A", "B", "C", "D", "E"].map((name, index) => ({
      series_id: name,
      series_name: `原始:${name}`,
      display_name: index === 0 ? `清洗:${name}` : undefined,
      unit: "%",
      quality_flag: "ok",
      recent_points: [recentPoint("2026-06-11", 1 + index)],
    }));
    const multi = buildMarketDataMultiSeriesTimeChartOption(manySeries);
    const series = multi?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected chart to expose a series array");
    }
    // 系列名与图例开关键都用 display_name ?? series_name，保证图例选中态能对上。
    expect((series[0] as { name?: string }).name).toBe("清洗:A");
    expect((series[1] as { name?: string }).name).toBe("原始:B");
    const selected = (multi?.legend as { selected?: Record<string, boolean> }).selected ?? {};
    expect(selected["清洗:A"]).toBe(true);
    expect(selected["原始:E"]).toBe(false);
  });

  it("keeps full series names in the data passed to ChartCard", () => {
    const option = buildMarketDataMultiSeriesTimeChartOption([
      {
        series_id: "DR007",
        series_name: "存款类机构质押式回购加权利率:DR007",
        unit: "%",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-11", 1.4), recentPoint("2026-06-12", 1.46)],
      },
      {
        series_id: "R007",
        series_name: "银行间质押式回购加权利率:R007",
        unit: "%",
        quality_flag: "ok",
        recent_points: [recentPoint("2026-06-11", 1.6), recentPoint("2026-06-12", 1.66)],
      },
    ]);

    const series = option?.series as Array<{ name?: string }>;
    expect(series.map((item) => item.name)).toEqual([
      "存款类机构质押式回购加权利率:DR007",
      "银行间质押式回购加权利率:R007",
    ]);
  });

  it("lights only the leading series by default and leaves legend chrome to ChartCard", () => {
    const manySeries: MarketDataSeriesTimeInput[] = ["A", "B", "C", "D", "E", "F"].map((name, index) => ({
      series_id: name,
      series_name: name,
      unit: "%",
      quality_flag: "ok",
      recent_points: [recentPoint("2026-06-11", 1 + index), recentPoint("2026-06-12", 1.1 + index)],
    }));
    const option = buildMarketDataMultiSeriesTimeChartOption(manySeries);

    const legend = option?.legend as { selected?: Record<string, boolean> };
    expect(legend.selected).toEqual({ A: true, B: true, C: true, D: true, E: false, F: false });
    expect(Object.values(legend.selected ?? {}).filter(Boolean)).toHaveLength(
      MARKET_DATA_MULTI_SERIES_DEFAULT_VISIBLE,
    );

    const fewSeries = buildMarketDataMultiSeriesTimeChartOption(manySeries.slice(0, 2));
    expect((fewSeries?.legend as { selected?: Record<string, boolean> }).selected).toBeUndefined();
  });
});
