import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ibTokens } from "../../../theme/designSystem";
import type { CorrelationMatrix, WaterfallBar } from "../lib/crossAssetAnalytics";
import { resolveCrossAssetChartPalette } from "../lib/crossAssetChartTheme";

import { CorrelationHeatmapPanel } from "./CorrelationAndRegimePanels";
import { DriverWaterfallPanel } from "./DriverWaterfallPanel";

vi.mock("./CrossAssetECharts", () => ({
  LazyCrossAssetECharts: ({ option }: { option: unknown }) => <div data-chart-option={JSON.stringify(option)} />,
}));

const MATRIX: CorrelationMatrix = {
  keys: ["csi300", "cn_gov_10y"],
  labels: ["沪深300", "10Y国债"],
  cells: [
    [
      { rowKey: "csi300", colKey: "csi300", value: 1 },
      { rowKey: "csi300", colKey: "cn_gov_10y", value: 0.8 },
    ],
    [
      { rowKey: "cn_gov_10y", colKey: "csi300", value: 0.8 },
      { rowKey: "cn_gov_10y", colKey: "cn_gov_10y", value: 1 },
    ],
  ],
};

const BARS: WaterfallBar[] = [
  { key: "liquidity", label: "流动性", value: 0.2, cumulative: 0.2, kind: "factor", color: ibTokens.color.down },
  { key: "rate", label: "海外利率", value: -0.1, cumulative: 0.1, kind: "factor", color: ibTokens.color.up },
  { key: "composite", label: "综合", value: 0.1, cumulative: 0.1, kind: "total", color: ibTokens.color.down },
];

describe("CorrelationHeatmapPanel terminal theme", () => {
  it("uses the selected chart palette without changing correlation values", () => {
    const { container: light } = render(<CorrelationHeatmapPanel matrix={MATRIX} />);
    const lightOption = JSON.parse(light.querySelector<HTMLElement>("[data-chart-option]")!.dataset.chartOption!);
    const lightPalette = resolveCrossAssetChartPalette("light");
    expect(lightOption.visualMap.inRange.color).toEqual([
      lightPalette.heatmapLow, lightPalette.heatmapMid, lightPalette.heatmapHigh,
    ]);

    const { container: dark } = render(<CorrelationHeatmapPanel matrix={MATRIX} theme="terminal" />);
    const darkOption = JSON.parse(dark.querySelector<HTMLElement>("[data-chart-option]")!.dataset.chartOption!);
    const darkPalette = resolveCrossAssetChartPalette("terminal");
    expect(darkOption.visualMap.inRange.color).toEqual([
      darkPalette.heatmapLow, darkPalette.heatmapMid, darkPalette.heatmapHigh,
    ]);
    expect(darkOption.tooltip.textStyle.color).toBe(darkPalette.text);
    expect(darkOption.series[0].data).toEqual(lightOption.series[0].data);
    expect(darkOption.series[0].data).toContainEqual([1, 0, 0.8]);
  });
});

describe("DriverWaterfallPanel terminal theme", () => {
  it("replaces bar colors with the terminal up/down hues, keeping business signs", () => {
    const { container: light } = render(<DriverWaterfallPanel bars={BARS} env={{}} />);
    const lightBars = light.querySelectorAll<HTMLElement>(".ca-waterfall__bar");
    expect(lightBars[0]!.style.background).toBe("rgb(180, 35, 24)");

    const { container: dark } = render(<DriverWaterfallPanel bars={BARS} env={{}} theme="terminal" />);
    const darkBars = dark.querySelectorAll<HTMLElement>(".ca-waterfall__bar");
    expect(darkBars[0]!.style.background).toBe("rgb(217, 123, 108)");
    expect(darkBars[1]!.style.background).toBe("rgb(90, 189, 153)");
    expect(darkBars[2]!.style.background).toBe("rgb(217, 123, 108)");
  });
});
