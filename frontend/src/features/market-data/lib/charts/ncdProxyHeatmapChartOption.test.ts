import { describe, expect, it } from "vitest";

import type { EChartsOption } from "../../../../lib/echarts";
import { nocturneTokens } from "../../../../theme/designSystem";
import { buildNcdProxyHeatmapOption } from "./ncdProxyHeatmapChartOption";

type HeatmapCell = { value: [number, number, number | null]; label?: { color?: string } };

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

  it("uses the nocturne dark scheme with value-tiered label colors", () => {
    const option = buildNcdProxyHeatmapOption({
      rows: [
        {
          row_key: "shibor",
          label: "Shibor fixing",
          "1M": 1.2,
          "3M": 1.5,
          "6M": 1.9,
          "9M": null,
          "1Y": 2.4,
          quote_count: null,
        },
      ],
    });
    const series = firstSeries(option) as {
      itemStyle?: { borderColor?: string; borderWidth?: number };
      label?: { color?: string };
      data?: HeatmapCell[];
    };

    expect(series?.itemStyle?.borderColor).toBe(nocturneTokens.color.line);
    expect(series?.itemStyle?.borderWidth).toBe(1);
    expect(series?.label?.color).toBe(nocturneTokens.color.inkSoft);

    const visualMap = option?.visualMap as { show?: boolean } | undefined;
    expect(visualMap?.show).toBe(false);

    const cells = series?.data ?? [];
    const highCell = cells.find((cell) => cell.value[2] === 2.4);
    const lowCell = cells.find((cell) => cell.value[2] === 1.2);
    const nullCell = cells.find((cell) => cell.value[2] == null);
    expect(highCell?.label?.color).toBe(nocturneTokens.color.bg);
    expect(lowCell?.label).toBeUndefined();
    expect(nullCell?.label).toBeUndefined();
  });
});
