import { describe, expect, it } from "vitest";

import type { EChartsOption } from "../../../../lib/echarts";
import {
  buildDerivedSpreadsBarOption,
  buildLinkageEnvironmentBarOption,
  LINKAGE_BAR_MAX_WIDTH,
  truncateLinkageCategoryLabel,
} from "./linkageEnvironmentBarChartOption";
import { buildLinkageCorrelationBarOption } from "./linkageCorrelationBarChartOption";
import { marketDataChartTheme } from "./marketDataChartTheme";

type BarDataItem = {
  value: number | null;
  itemStyle: { color: string; borderRadius: number[] };
};

function firstSeries(option: EChartsOption | null) {
  const series = option?.series;
  if (Array.isArray(series)) {
    return series[0];
  }
  return series;
}

function seriesData(option: EChartsOption | null): BarDataItem[] {
  const series = firstSeries(option) as { data?: BarDataItem[] } | undefined;
  return Array.isArray(series?.data) ? series.data : [];
}

describe("linkage chart options", () => {
  it("builds environment score bars from API fields", () => {
    const option = buildLinkageEnvironmentBarOption({
      liquidity_score: 0.4,
      composite_score: 0.2,
    });
    const series = firstSeries(option);
    expect(Array.isArray(series?.data) ? series.data.length : 0).toBe(2);
  });

  it("colors environment bars by sign via theme fields with capped width", () => {
    const option = buildLinkageEnvironmentBarOption({
      liquidity_score: 0.4,
      composite_score: -0.2,
    });
    const [positive, negative] = seriesData(option);
    expect(positive.itemStyle.color).toBe(marketDataChartTheme.positiveBar);
    expect(negative.itemStyle.color).toBe(marketDataChartTheme.negativeBar);
    expect(positive.itemStyle.borderRadius).toEqual([2, 2, 0, 0]);
    expect(negative.itemStyle.borderRadius).toEqual([0, 0, 2, 2]);
    const series = firstSeries(option) as { barMaxWidth?: number };
    expect(series.barMaxWidth).toBe(LINKAGE_BAR_MAX_WIDTH);
  });

  it("builds derived spread bars when values exist", () => {
    const option = buildDerivedSpreadsBarOption({
      credit_spread_3y: 12,
      term_spread_10y_2y: 8,
    });
    expect(option?.yAxis).toBeTruthy();
  });

  it("keeps derived spread bars on the theme spread color with horizontal rounding", () => {
    const option = buildDerivedSpreadsBarOption({
      credit_spread_3y: 12,
      term_spread_10y_2y: -8,
    });
    const [positive, negative] = seriesData(option);
    expect(positive.itemStyle.color).toBe(marketDataChartTheme.derivedSpreadColor);
    expect(negative.itemStyle.color).toBe(marketDataChartTheme.negativeBar);
    expect(positive.itemStyle.borderRadius).toEqual([0, 2, 2, 0]);
    expect(negative.itemStyle.borderRadius).toEqual([2, 0, 0, 2]);
  });

  it("builds grouped correlation bars", () => {
    const option = buildLinkageCorrelationBarOption([
      {
        series_id: "CPI",
        series_name: "CPI YoY",
        target_family: "rates",
        target_tenor: "10Y",
        correlation_3m: 0.2,
        correlation_6m: 0.4,
        correlation_1y: 0.5,
        lead_lag_days: 3,
        direction: "positive",
      },
    ]);
    expect(Array.isArray(option?.series) ? option.series.length : 0).toBe(3);
  });

  it("maps correlation bar colors to theme sign fields and neutral for null", () => {
    const option = buildLinkageCorrelationBarOption([
      {
        series_id: "ALU",
        series_name: "铝主力期货收盘价（活跃合约）",
        target_family: "rates",
        target_tenor: "10Y",
        correlation_3m: 0.2,
        correlation_6m: -0.4,
        correlation_1y: null,
        lead_lag_days: 0,
        direction: "positive",
      },
    ]);
    const series = option?.series as Array<{ data: BarDataItem[]; barMaxWidth?: number }>;
    expect(series[0].data[0].itemStyle.color).toBe(marketDataChartTheme.positiveBar);
    expect(series[1].data[0].itemStyle.color).toBe(marketDataChartTheme.negativeBar);
    expect(series[2].data[0].itemStyle.color).toBe(marketDataChartTheme.neutralBar);
    expect(series[0].data[0].itemStyle.borderRadius).toEqual([2, 2, 0, 0]);
    expect(series[1].data[0].itemStyle.borderRadius).toEqual([0, 0, 2, 2]);
    expect(series.every((entry) => entry.barMaxWidth === LINKAGE_BAR_MAX_WIDTH)).toBe(true);

    const xAxis = option?.xAxis as {
      data: string[];
      axisLabel: { formatter: (value: string) => string };
    };
    // 类目全名保留给 tooltip，轴标签通过 formatter 截断。
    expect(xAxis.data[0]).toBe("铝主力期货收盘价（活跃合约）");
    expect(xAxis.axisLabel.formatter(xAxis.data[0])).toBe(
      `${"铝主力期货收盘价（活跃合约）".slice(0, 10)}…`,
    );
  });

  it("truncates only category labels longer than the budget", () => {
    expect(truncateLinkageCategoryLabel("短名", 10)).toBe("短名");
    expect(truncateLinkageCategoryLabel("0123456789A", 10)).toBe("0123456789…");
  });
});
