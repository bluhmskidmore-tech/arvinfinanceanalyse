import { describe, expect, it } from "vitest";

import {
  createBarChartOption,
  createBaseChartOption,
  createEmptyChartOption,
  createLineChartOption,
  mossChartPalette,
} from "../components/charts/chartTheme";
import { designTokens, ibTokens } from "../theme/designSystem";

describe("chartTheme", () => {
  it("builds chart defaults from design tokens", () => {
    const option = createBaseChartOption();

    expect(mossChartPalette[0]).toBe(ibTokens.color.accent);
    expect(mossChartPalette).toContain(ibTokens.color.gold);
    expect(option.color).toEqual([...mossChartPalette]);
    expect(option.textStyle).toMatchObject({ fontFamily: designTokens.fontFamily.sans });
    expect(option.tooltip).toMatchObject({
      trigger: "axis",
      backgroundColor: ibTokens.color.surface,
      borderColor: ibTokens.color.hairline,
    });
    expect(option.legend).toMatchObject({
      type: "scroll",
      textStyle: { color: ibTokens.color.inkMuted },
    });
    expect(option.grid).toMatchObject({ containLabel: true });
  });

  it("keeps caller data while applying line and bar axis defaults", () => {
    const lineOption = createLineChartOption({
      xAxis: { type: "category", data: ["Jan"] },
      yAxis: { type: "value" },
      series: [{ name: "A", type: "line", data: [1] }],
    });
    const barOption = createBarChartOption({
      xAxis: { type: "category", data: ["Jan"] },
      yAxis: { type: "value" },
      series: [{ name: "B", type: "bar", data: [2] }],
    });

    expect(lineOption.series).toEqual([{ name: "A", type: "line", data: [1] }]);
    expect(lineOption.xAxis).toMatchObject({
      boundaryGap: false,
      axisLabel: { color: ibTokens.color.inkMuted },
      axisLine: { lineStyle: { color: ibTokens.color.hairline } },
    });
    expect(lineOption.yAxis).toMatchObject({
      splitLine: { lineStyle: { color: ibTokens.color.hairline } },
    });
    expect(barOption.tooltip).toMatchObject({ axisPointer: { type: "shadow" } });
    expect(barOption.series).toEqual([{ name: "B", type: "bar", data: [2] }]);
  });

  it("can render a token-based empty chart option", () => {
    const option = createEmptyChartOption("No rows");

    expect(option.graphic).toMatchObject({
      type: "text",
      style: {
        text: "No rows",
        fill: ibTokens.color.inkMuted,
        fontFamily: designTokens.fontFamily.sans,
      },
    });
    expect(option.series).toEqual([]);
  });
});
