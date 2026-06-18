import { describe, expect, it } from "vitest";

import type { EChartsOption } from "../../../../lib/echarts";
import { buildNcdProxyHeatmapOption } from "./ncdProxyHeatmapChartOption";

function firstSeries(option: EChartsOption | null) {
  const series = option?.series;
  if (Array.isArray(series)) {
    return series[0];
  }
  return series;
}

describe("buildNcdProxyHeatmapOption", () => {
  it("builds heatmap data for proxy rows", () => {
    const option = buildNcdProxyHeatmapOption({
      rows: [
        {
          row_key: "shibor",
          label: "Shibor fixing",
          "1M": 1.427,
          "3M": 1.414,
          "6M": 1.43,
          "9M": 1.45,
          "1Y": 1.43,
          quote_count: null,
        },
      ],
    });
    const series = firstSeries(option) as { type?: string; data?: unknown[] };
    expect(series?.type).toBe("heatmap");
    expect(series?.data).toHaveLength(5);
  });
});
