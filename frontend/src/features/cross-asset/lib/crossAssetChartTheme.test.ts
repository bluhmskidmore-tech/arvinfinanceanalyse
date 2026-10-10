import { describe, expect, it } from "vitest";

import { ibTokens, nocturneTokens } from "../../../theme/designSystem";

import {
  heatmapColorFor,
  resolveCrossAssetChartPalette,
  waterfallBarColorFor,
} from "./crossAssetChartTheme";

const nct = nocturneTokens.color;

describe("resolveCrossAssetChartPalette", () => {
  it("defaults to the light theme and preserves the historical IB colors", () => {
    const palette = resolveCrossAssetChartPalette();
    expect(palette.text).toBe(ibTokens.color.ink);
    expect(palette.textSoft).toBe(ibTokens.color.inkSecondary);
    expect(palette.textMuted).toBe(ibTokens.color.inkMuted);
    expect(palette.axisLine).toBe(ibTokens.color.hairline);
    expect(palette.tooltipBg).toBe(ibTokens.color.surface);
    expect(palette.tooltipBorder).toBe(ibTokens.color.hairline);
    expect(resolveCrossAssetChartPalette("light")).toEqual(palette);
  });

  it("resolves the terminal theme from the nocturne dark token values", () => {
    const palette = resolveCrossAssetChartPalette("terminal");
    expect(palette.text).toBe(nct.ink);
    expect(palette.textSoft).toBe(nct.inkSoft);
    expect(palette.textMuted).toBe(nct.inkMuted);
    expect(palette.axisLine).toBe(nct.line);
    expect(palette.splitLine).toBe(nct.lineSoft);
    expect(palette.tooltipBg).toBe(nct.panel2);
    expect(palette.tooltipBorder).toBe(nct.line);
    expect(palette.series.slice(0, 4)).toEqual([nct.blue, nct.green, nct.amber, nct.red]);
    expect(palette.up).toBe(nct.red);
    expect(palette.down).toBe(nct.green);
  });
});

describe("heatmapColorFor", () => {
  const terminal = resolveCrossAssetChartPalette("terminal");

  it("ramps the green base for positive correlation on terminal", () => {
    expect(heatmapColorFor(0.8, terminal)).toBe("rgba(90, 189, 153, 0.62)");
  });

  it("ramps the red base for negative correlation on terminal", () => {
    expect(heatmapColorFor(-0.7, terminal)).toBe("rgba(217, 123, 108, 0.55)");
  });

  it("returns the mid fill verbatim for missing values", () => {
    expect(heatmapColorFor(null, terminal)).toBe(terminal.heatmapMid);
  });
});

describe("waterfallBarColorFor", () => {
  const terminal = resolveCrossAssetChartPalette("terminal");

  it("keeps the ±0.05 business thresholds with terminal hues", () => {
    expect(waterfallBarColorFor(0.12, "factor", terminal)).toBe(nct.red);
    expect(waterfallBarColorFor(-0.12, "factor", terminal)).toBe(nct.green);
    expect(waterfallBarColorFor(0, "total", terminal)).toBe(terminal.neutral);
    expect(waterfallBarColorFor(0.02, "factor", terminal)).toBe(terminal.neutralSoft);
  });
});
