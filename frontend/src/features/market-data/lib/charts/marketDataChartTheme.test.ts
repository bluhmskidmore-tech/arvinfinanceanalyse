import { describe, expect, it } from "vitest";

import { nocturneTokens } from "../../../../theme/designSystem";
import { buildMarketDataChartTooltip, marketDataChartTheme } from "./marketDataChartTheme";

describe("marketDataChartTheme", () => {
  it("exposes a multi-series palette and axis tokens", () => {
    expect(marketDataChartTheme.multiSeriesPalette.length).toBeGreaterThanOrEqual(3);
    expect(marketDataChartTheme.axisLabel.fontSize).toBe(11);
    expect(marketDataChartTheme.heatmapRange).toHaveLength(2);
  });

  it("draws the multi-series palette and semantic colors from Nocturne tokens only", () => {
    const nocturneColors = Object.values(nocturneTokens.color) as string[];
    for (const color of marketDataChartTheme.multiSeriesPalette) {
      expect(nocturneColors).toContain(color);
    }
    expect(marketDataChartTheme.multiSeriesPalette[0]).toBe(nocturneTokens.color.blue);
    expect(marketDataChartTheme.positiveBar).toBe(nocturneTokens.color.green);
    expect(marketDataChartTheme.negativeBar).toBe(nocturneTokens.color.red);
    expect(marketDataChartTheme.neutralBar).toBe(nocturneTokens.color.inkMuted);
    expect(marketDataChartTheme.derivedSpreadColor).toBe(nocturneTokens.color.accent400);
    expect(marketDataChartTheme.chartSurface).toBe(nocturneTokens.color.panel);
  });

  it("keeps axes, pointer, and heatmap on the dark Nocturne ramp", () => {
    expect(marketDataChartTheme.axisLabel.color).toBe(nocturneTokens.color.inkMuted);
    expect(marketDataChartTheme.axisLine.lineStyle.color).toBe(nocturneTokens.color.lineSoft);
    expect(marketDataChartTheme.splitLine.lineStyle.color).toBe(nocturneTokens.color.lineSoft);
    expect(marketDataChartTheme.axisPointerLine.lineStyle.color).toBe(nocturneTokens.color.blue);
    expect(marketDataChartTheme.axisPointerShadow.shadowStyle.color).toBe(nocturneTokens.color.blueSoft);
    expect(marketDataChartTheme.heatmapRange).toEqual([
      nocturneTokens.color.panel2,
      nocturneTokens.color.blue,
    ]);
    expect(marketDataChartTheme.heatmapEmptyColor).toBe(nocturneTokens.color.panel2);
    expect(marketDataChartTheme.titleMuted.color).toBe(nocturneTokens.color.inkSoft);
  });

  it("builds dark tooltips on panel3 with Nocturne ink and radius", () => {
    const tooltip = buildMarketDataChartTooltip();
    expect(tooltip.backgroundColor).toBe(nocturneTokens.color.panel3);
    expect(tooltip.borderColor).toBe(nocturneTokens.color.line);
    expect(tooltip.textStyle?.color).toBe(nocturneTokens.color.ink);
    expect(tooltip.extraCssText).toContain(`border-radius: ${nocturneTokens.radius}px`);

    const merged = buildMarketDataChartTooltip({ trigger: "axis", textStyle: { fontSize: 11 } });
    expect(merged.trigger).toBe("axis");
    expect(merged.textStyle?.fontSize).toBe(11);
    expect(merged.textStyle?.color).toBe(nocturneTokens.color.ink);
  });
});
