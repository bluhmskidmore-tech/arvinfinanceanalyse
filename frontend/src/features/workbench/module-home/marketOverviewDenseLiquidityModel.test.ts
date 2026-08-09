import { describe, expect, it } from "vitest";

import type {
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
} from "../../../api/contracts";
import {
  buildDenseLiquidityChartSpec,
  buildDenseLiquiditySeries,
} from "./marketOverviewDenseLiquidityModel";

function ratePoint(
  seriesId: string,
  seriesName: string,
  latestValue: number,
  unit = "%",
): ChoiceMacroLatestPoint {
  return {
    series_id: seriesId,
    series_name: seriesName,
    trade_date: "2026-07-27",
    value_numeric: latestValue,
    unit,
    source_version: "source-v1",
    vendor_version: "vendor-v1",
    recent_points: [
      {
        trade_date: "2026-07-25",
        value_numeric: latestValue - 0.02,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-07-26",
        value_numeric: latestValue - 0.01,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
    ],
  };
}

function ratesPayload(): ChoiceMacroLatestPayload {
  return {
    read_target: "duckdb",
    series: [
      ratePoint("CA.DR007", "DR007", 1.42),
      ratePoint("EMM00088132", "公开市场操作:逆回购:7天:中标利率", 1.4),
      ratePoint("NCD.SHIBOR.1M", "SHIBOR:1M", 1.41),
      ratePoint("NCD.SHIBOR.3M", "SHIBOR:3M", 1.43),
    ],
  };
}

describe("marketOverviewDenseLiquidityModel", () => {
  it("selects only the four governed liquidity series in display order", () => {
    const series = buildDenseLiquiditySeries(ratesPayload());

    expect(series.map((item) => item.key)).toEqual([
      "dr007",
      "repo-7d",
      "shibor-1m",
      "shibor-3m",
    ]);
    expect(series[0].points).toEqual([
      { date: "2026-07-25", value: 1.4 },
      { date: "2026-07-26", value: 1.41 },
      { date: "2026-07-27", value: 1.42 },
    ]);
  });

  it("builds a source-backed chart without inventing a spread series", () => {
    const chart = buildDenseLiquidityChartSpec(ratesPayload());

    expect(chart.key).toBe("liquidity-tenor");
    expect(chart.title).toBe("流动性期限与资金利率");
    expect(chart.subtitle).toContain("4 条正式序列");
    expect(chart.option).not.toBeNull();
    expect(chart.footnote).toContain("不插值、不派生利差");
  });

  it("uses the shared backend unit for axis and tooltip formatting", () => {
    const chart = buildDenseLiquidityChartSpec({
      read_target: "duckdb",
      series: [
        ratePoint("CA.DR007", "DR007", 1.42, "bp"),
        ratePoint("EMM00088132", "公开市场操作:逆回购:7天:中标利率", 1.4, "bp"),
        ratePoint("NCD.SHIBOR.1M", "SHIBOR:1M", 1.41, "bp"),
        ratePoint("NCD.SHIBOR.3M", "SHIBOR:3M", 1.43, "bp"),
      ],
    });

    const yAxis = Array.isArray(chart.option?.yAxis)
      ? chart.option?.yAxis[0]
      : chart.option?.yAxis;
    const tooltip = Array.isArray(chart.option?.tooltip)
      ? chart.option?.tooltip[0]
      : chart.option?.tooltip;
    const formatValue = tooltip?.valueFormatter as
      | ((value: unknown, index: number) => string)
      | undefined;

    expect(chart.option).not.toBeNull();
    expect(chart.subtitle).toContain("· bp");
    expect(yAxis).toMatchObject({
      name: "bp",
    });
    expect(formatValue?.(1.42, 0)).toBe("1.4200bp");
  });

  it("fails closed instead of plotting mixed liquidity units on one axis", () => {
    const chart = buildDenseLiquidityChartSpec({
      read_target: "duckdb",
      series: [
        ratePoint("CA.DR007", "DR007", 1.42, "%"),
        ratePoint("EMM00088132", "公开市场操作:逆回购:7天:中标利率", 1.4, "bp"),
        ratePoint("NCD.SHIBOR.1M", "SHIBOR:1M", 1.41, "%"),
        ratePoint("NCD.SHIBOR.3M", "SHIBOR:3M", 1.43, "%"),
      ],
    });

    expect(chart.option).toBeNull();
    expect(chart.subtitle).toContain("单位缺失或不一致未绘制");
    expect(chart.footnote).toContain("不共轴绘制");
  });

  it("fails closed when any selected liquidity series omits its unit", () => {
    const chart = buildDenseLiquidityChartSpec({
      read_target: "duckdb",
      series: [
        ratePoint("CA.DR007", "DR007", 1.42, "%"),
        ratePoint("NCD.SHIBOR.3M", "SHIBOR:3M", 1.43, "unknown"),
      ],
    });

    expect(chart.option).toBeNull();
    expect(chart.subtitle).toContain("单位缺失或不一致未绘制");
  });
});
