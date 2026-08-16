import type { CSSProperties } from "react";

import type { EChartsOption } from "../../lib/echarts";
import { designTokens, dhApiTokens, ibTokens, nocturneTokens } from "../../theme/designSystem";

type PlainObject = Record<string, unknown>;

/*
 * Dual chart themes per DESIGN.md §2: IB light workbench (default) and
 * dh-api dark terminal. Pages must use the variant matching their page
 * theme instead of hard-coding chart colors.
 */

type ChartThemeColors = {
  palette: readonly string[];
  categoricalPalette: readonly string[];
  ink: string;
  inkMuted: string;
  hairline: string;
  surface: string;
  accentPointer: string;
  emptyRadius: number;
  loadingMaskBase: string;
};

const ibThemeColors: ChartThemeColors = {
  palette: [
    ibTokens.color.accent,
    designTokens.color.info[600],
    ibTokens.color.gold,
    ibTokens.color.up,
    ibTokens.color.down,
    designTokens.color.warm.slateBlue,
    designTokens.color.primary[400],
    designTokens.color.warning[500],
  ],
  categoricalPalette: [
    ibTokens.color.accent,
    designTokens.color.primary[700],
    designTokens.color.warm.slateBlue,
    designTokens.color.primary[200],
    designTokens.color.neutral[300],
    ibTokens.color.gold,
  ],
  ink: ibTokens.color.ink,
  inkMuted: ibTokens.color.inkMuted,
  hairline: ibTokens.color.hairline,
  surface: ibTokens.color.surface,
  accentPointer: ibTokens.color.gold,
  emptyRadius: ibTokens.radius,
  loadingMaskBase: designTokens.color.institutional.surface,
};

const dhApiThemeColors: ChartThemeColors = {
  palette: [
    dhApiTokens.color.blue,
    dhApiTokens.color.green,
    dhApiTokens.color.amber,
    dhApiTokens.color.red,
    dhApiTokens.color.inkSoft,
    dhApiTokens.color.inkMuted,
  ],
  categoricalPalette: [
    dhApiTokens.color.blue,
    dhApiTokens.color.inkSoft,
    dhApiTokens.color.amber,
    dhApiTokens.color.green,
    dhApiTokens.color.inkMuted,
    dhApiTokens.color.red,
  ],
  ink: dhApiTokens.color.ink,
  inkMuted: dhApiTokens.color.inkMuted,
  hairline: dhApiTokens.color.lineSoft,
  surface: dhApiTokens.color.panel2,
  accentPointer: dhApiTokens.color.amber,
  emptyRadius: dhApiTokens.radius,
  loadingMaskBase: dhApiTokens.color.panel,
};

/* Nocturne（首页色系）scope 页面的 canvas 取色：与 dhApiThemeColors 同构、
 * 仅换 nocturneTokens 常量组（canvas 不消费 CSS 变量，组合工作台先例）。 */
const nocturneThemeColors: ChartThemeColors = {
  palette: [
    nocturneTokens.color.blue,
    nocturneTokens.color.green,
    nocturneTokens.color.amber,
    nocturneTokens.color.red,
    nocturneTokens.color.inkSoft,
    nocturneTokens.color.inkMuted,
  ],
  categoricalPalette: [
    nocturneTokens.color.blue,
    nocturneTokens.color.inkSoft,
    nocturneTokens.color.amber,
    nocturneTokens.color.green,
    nocturneTokens.color.inkMuted,
    nocturneTokens.color.red,
  ],
  ink: nocturneTokens.color.ink,
  inkMuted: nocturneTokens.color.inkMuted,
  hairline: nocturneTokens.color.lineSoft,
  surface: nocturneTokens.color.panel2,
  accentPointer: nocturneTokens.color.amber,
  emptyRadius: nocturneTokens.radius,
  loadingMaskBase: nocturneTokens.color.panel,
};

function buildChartTheme(colors: ChartThemeColors) {
  const axisLabel = {
    color: colors.inkMuted,
    fontSize: designTokens.fontSize[11],
    fontFamily: designTokens.fontFamily.sans,
  };

  const axisLine = {
    lineStyle: {
      color: colors.hairline,
    },
  };

  const splitLine = {
    lineStyle: {
      color: colors.hairline,
    },
  };

  const loadingMaskStyle: CSSProperties = {
    position: "absolute",
    inset: 0,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: `color-mix(in srgb, ${colors.loadingMaskBase} 72%, transparent)`,
    zIndex: 1,
  };

  const emptyStateStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: colors.inkMuted,
    fontSize: designTokens.fontSize[13],
    border: `1px dashed ${colors.hairline}`,
    borderRadius: colors.emptyRadius,
    background: colors.surface,
    fontFamily: designTokens.fontFamily.sans,
  };

  const baseGrid = {
    left: designTokens.space[7],
    right: designTokens.space[5],
    top: designTokens.space[6],
    bottom: designTokens.space[6],
    containLabel: true,
  };

  const baseTooltip = {
    trigger: "axis",
    confine: true,
    backgroundColor: colors.surface,
    borderColor: colors.hairline,
    borderWidth: 1,
    padding: [8, 10],
    textStyle: {
      color: colors.ink,
      fontSize: designTokens.fontSize[12],
      fontFamily: designTokens.fontFamily.sans,
    },
    axisPointer: {
      type: "line",
      lineStyle: {
        color: colors.accentPointer,
        width: 1,
        type: "dashed",
      },
    },
  };

  const baseLegend = {
    type: "scroll",
    bottom: 0,
    itemWidth: 18,
    itemHeight: 8,
    textStyle: axisLabel,
  };

  const categoryAxis = {
    type: "category",
    axisLabel,
    axisLine,
  };

  const valueAxis = {
    type: "value",
    axisLabel,
    axisLine,
    splitLine,
  };

  function createBaseChartOption(overrides: EChartsOption = {}): EChartsOption {
    return mergePlainObjects(
      {
        color: [...colors.palette],
        textStyle: {
          color: colors.ink,
          fontFamily: designTokens.fontFamily.sans,
        },
        tooltip: baseTooltip,
        legend: baseLegend,
        grid: baseGrid,
      },
      overrides,
    ) as EChartsOption;
  }

  function createLineChartOption(overrides: EChartsOption = {}): EChartsOption {
    const overrideRecord = overrides as PlainObject;
    return createBaseChartOption({
      ...withoutAxis(overrides),
      xAxis: mergeAxis({ ...categoryAxis, boundaryGap: false }, overrideRecord.xAxis),
      yAxis: mergeAxis(valueAxis, overrideRecord.yAxis),
    } as EChartsOption);
  }

  function createBarChartOption(overrides: EChartsOption = {}): EChartsOption {
    const overrideRecord = overrides as PlainObject;
    const barTooltip = mergePlainObjects(
      mergePlainObjects(baseTooltip, { axisPointer: { type: "shadow" } }),
      overrideRecord.tooltip,
    );
    return createBaseChartOption({
      ...withoutAxis(overrides),
      tooltip: barTooltip,
      xAxis: mergeAxis({ ...categoryAxis, boundaryGap: true }, overrideRecord.xAxis),
      yAxis: mergeAxis(valueAxis, overrideRecord.yAxis),
    } as EChartsOption);
  }

  function createEmptyChartOption(text = "暂无数据"): EChartsOption {
    return createBaseChartOption({
      graphic: {
        type: "text",
        left: "center",
        top: "middle",
        style: {
          text,
          fill: colors.inkMuted,
          fontSize: designTokens.fontSize[13],
          fontFamily: designTokens.fontFamily.sans,
        },
      },
      series: [],
    } as EChartsOption);
  }

  return {
    palette: colors.palette,
    categoricalPalette: colors.categoricalPalette,
    axisLabel,
    axisLine,
    splitLine,
    loadingMaskStyle,
    emptyStateStyle,
    createBaseChartOption,
    createLineChartOption,
    createBarChartOption,
    createEmptyChartOption,
  };
}

function isPlainObject(value: unknown): value is PlainObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function mergePlainObjects(base: PlainObject, overrides?: unknown): PlainObject {
  if (!isPlainObject(overrides)) {
    return { ...base };
  }

  const merged: PlainObject = { ...base };
  for (const [key, value] of Object.entries(overrides)) {
    const baseValue = merged[key];
    merged[key] = isPlainObject(baseValue) && isPlainObject(value) ? mergePlainObjects(baseValue, value) : value;
  }
  return merged;
}

function mergeAxis(defaults: PlainObject, axis?: unknown): unknown {
  if (Array.isArray(axis)) {
    return axis.map((item) => mergePlainObjects(defaults, item));
  }
  return mergePlainObjects(defaults, axis);
}

function withoutAxis(overrides: EChartsOption): PlainObject {
  const { xAxis: _xAxis, yAxis: _yAxis, ...rest } = overrides as PlainObject;
  return rest;
}

/** IB light workbench chart theme (default). */
export const ibChartTheme = buildChartTheme(ibThemeColors);

/** Dark terminal (Decision Desk) chart theme for `theme-dh-api` pages. */
export const dhApiChartTheme = buildChartTheme(dhApiThemeColors);

/** Nocturne chart theme for pages under a Nocturne `data-moss-theme-scope`. */
export const nocturneChartTheme = buildChartTheme(nocturneThemeColors);

// ---- Legacy named exports (IB light) — kept for existing consumers -------

export const mossChartPalette = ibChartTheme.palette;
export const mossChartCategoricalPalette = ibChartTheme.categoricalPalette;
export const mossChartAxisLabel = ibChartTheme.axisLabel;
export const mossChartAxisLine = ibChartTheme.axisLine;
export const mossChartSplitLine = ibChartTheme.splitLine;
export const mossChartLoadingMaskStyle = ibChartTheme.loadingMaskStyle;
export const mossChartEmptyStateStyle = ibChartTheme.emptyStateStyle;
export const createBaseChartOption = ibChartTheme.createBaseChartOption;
export const createLineChartOption = ibChartTheme.createLineChartOption;
export const createBarChartOption = ibChartTheme.createBarChartOption;
export const createEmptyChartOption = ibChartTheme.createEmptyChartOption;
