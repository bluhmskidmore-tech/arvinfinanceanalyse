import type { CSSProperties } from "react";

import type { EChartsOption } from "../../lib/echarts";
import { designTokens, ibTokens } from "../../theme/designSystem";

type PlainObject = Record<string, unknown>;

export const mossChartPalette = [
  ibTokens.color.accent,
  designTokens.color.info[600],
  ibTokens.color.gold,
  ibTokens.color.up,
  ibTokens.color.down,
  designTokens.color.warm.slateBlue,
  designTokens.color.primary[400],
  designTokens.color.warning[500],
] as const;

export const mossChartCategoricalPalette = [
  ibTokens.color.accent,
  designTokens.color.primary[700],
  designTokens.color.warm.slateBlue,
  designTokens.color.primary[200],
  designTokens.color.neutral[300],
  ibTokens.color.gold,
] as const;

export const mossChartAxisLabel = {
  color: ibTokens.color.inkMuted,
  fontSize: designTokens.fontSize[11],
  fontFamily: designTokens.fontFamily.sans,
};

export const mossChartAxisLine = {
  lineStyle: {
    color: ibTokens.color.hairline,
  },
};

export const mossChartSplitLine = {
  lineStyle: {
    color: ibTokens.color.hairline,
  },
};

export const mossChartLoadingMaskStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: `color-mix(in srgb, ${designTokens.color.institutional.surface} 72%, transparent)`,
  zIndex: 1,
};

export const mossChartEmptyStateStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: ibTokens.color.inkMuted,
  fontSize: designTokens.fontSize[13],
  border: `1px dashed ${ibTokens.color.hairline}`,
  borderRadius: designTokens.radius.md,
  background: ibTokens.color.surface,
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
  backgroundColor: ibTokens.color.surface,
  borderColor: ibTokens.color.hairline,
  borderWidth: 1,
  padding: [8, 10],
  textStyle: {
    color: ibTokens.color.ink,
    fontSize: designTokens.fontSize[12],
    fontFamily: designTokens.fontFamily.sans,
  },
  axisPointer: {
    type: "line",
    lineStyle: {
      color: ibTokens.color.gold,
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
  textStyle: mossChartAxisLabel,
};

const categoryAxis = {
  type: "category",
  axisLabel: mossChartAxisLabel,
  axisLine: mossChartAxisLine,
};

const valueAxis = {
  type: "value",
  axisLabel: mossChartAxisLabel,
  axisLine: mossChartAxisLine,
  splitLine: mossChartSplitLine,
};

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

export function createBaseChartOption(overrides: EChartsOption = {}): EChartsOption {
  return mergePlainObjects(
    {
      color: [...mossChartPalette],
      textStyle: {
        color: ibTokens.color.ink,
        fontFamily: designTokens.fontFamily.sans,
      },
      tooltip: baseTooltip,
      legend: baseLegend,
      grid: baseGrid,
    },
    overrides,
  ) as EChartsOption;
}

export function createLineChartOption(overrides: EChartsOption = {}): EChartsOption {
  const overrideRecord = overrides as PlainObject;
  return createBaseChartOption({
    ...withoutAxis(overrides),
    xAxis: mergeAxis({ ...categoryAxis, boundaryGap: false }, overrideRecord.xAxis),
    yAxis: mergeAxis(valueAxis, overrideRecord.yAxis),
  } as EChartsOption);
}

export function createBarChartOption(overrides: EChartsOption = {}): EChartsOption {
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

export function createEmptyChartOption(text = "暂无数据"): EChartsOption {
  return createBaseChartOption({
    graphic: {
      type: "text",
      left: "center",
      top: "middle",
      style: {
        text,
        fill: ibTokens.color.inkMuted,
        fontSize: designTokens.fontSize[13],
        fontFamily: designTokens.fontFamily.sans,
      },
    },
    series: [],
  } as EChartsOption);
}
