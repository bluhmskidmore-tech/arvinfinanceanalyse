import { describe, expect, it } from "vitest";

import type { EChartsOption } from "../../../../lib/echarts";
import {
  buildDerivedSpreadsBarOption,
  buildLinkageEnvironmentBarOption,
} from "./linkageEnvironmentBarChartOption";
import { buildLinkageCorrelationBarOption } from "./linkageCorrelationBarChartOption";

function firstSeries(option: EChartsOption | null) {
  const series = option?.series;
  if (Array.isArray(series)) {
    return series[0];
  }
  return series;
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

  it("builds derived spread bars when values exist", () => {
    const option = buildDerivedSpreadsBarOption({
      credit_spread_3y: 12,
      term_spread_10y_2y: 8,
    });
    expect(option?.yAxis).toBeTruthy();
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
});
