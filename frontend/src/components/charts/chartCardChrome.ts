import type { EChartsOption } from "../../lib/echarts";
import { designTokens, nocturneTokens } from "../../theme/designSystem";
import { nocturneChartTheme } from "./chartTheme";
import { chartCardLegendReservedBottom } from "./chartCardScale";

type PlainObject = Record<string, unknown>;

export type ChartCardLegendMode = "bottom-left" | "none";

/**
 * ChartCard 统一铬件：只覆盖图例位置、tooltip 底色、全局文字色与网格边距，
 * series / 轴 / 数据 / markLine 一律不动（视觉方案 §7.2「图表铬件唯一」）。
 * canvas 读不到 CSS 变量，取色只从 nocturneTokens / nocturneChartTheme（DESIGN 结论 12）。
 */
export function applyChartCardChrome(
  option: EChartsOption,
  options: { legend?: ChartCardLegendMode; legendRows?: number } = {},
): EChartsOption {
  const record = option as PlainObject;
  const legendMode = options.legend ?? "bottom-left";
  const legendRows = options.legendRows ?? (legendMode === "none" ? 0 : 1);
  const reservedBottom = chartCardLegendReservedBottom(legendRows);

  const legend =
    legendMode === "none"
      ? { show: false }
      : {
          ...(isPlainObject(record.legend) ? record.legend : {}),
          show: true,
          type: "plain",
          left: 0,
          bottom: 0,
          itemWidth: 12,
          itemHeight: 8,
          itemGap: 12,
          textStyle: { ...nocturneChartTheme.axisLabel },
        };

  const tooltip = {
    ...(isPlainObject(record.tooltip) ? record.tooltip : {}),
    backgroundColor: nocturneTokens.color.panel2,
    borderColor: nocturneTokens.color.line,
    borderWidth: 1,
    textStyle: {
      ...(isPlainObject((record.tooltip as PlainObject | undefined)?.textStyle)
        ? ((record.tooltip as PlainObject).textStyle as PlainObject)
        : {}),
      color: nocturneTokens.color.ink,
      fontSize: designTokens.fontSize[12],
      fontFamily: designTokens.fontFamily.sans,
    },
  };

  // left / right / top 允许调用方按轴名、旋转标签微调；bottom 与 containLabel 由铬件按图例行数独占，
  // 否则调用方残留的 bottom: 4 会让图例盖住 x 轴标签。
  const grid = {
    left: 8,
    right: 8,
    top: 12,
    ...(isPlainObject(record.grid) ? record.grid : {}),
    bottom: reservedBottom + 4,
    containLabel: true,
  };

  return {
    ...option,
    textStyle: {
      ...(isPlainObject(record.textStyle) ? record.textStyle : {}),
      color: nocturneTokens.color.inkSoft,
      fontFamily: designTokens.fontFamily.sans,
    },
    legend,
    tooltip,
    grid: Array.isArray(record.grid) ? record.grid : grid,
  } as EChartsOption;
}

/**
 * 视觉方案 §7 禁止项的开发态提示：一页多环、圆角柱 > 2px、非单色渐变面积。
 * 只 warn 不抛错——铬件不能因为规范检查让业务图消失。
 */
export function detectChartCardWarnings(option: EChartsOption): string[] {
  const warnings: string[] = [];
  const series = normalizeSeries(option);
  const pieCount = series.filter((item) => item.type === "pie").length;
  if (pieCount > 1) {
    warnings.push(`ChartCard 内有 ${pieCount} 个环形/饼图：一张图最多一个环（视觉方案 §7.1）。`);
  }
  for (const item of series) {
    const radius = (item.itemStyle as PlainObject | undefined)?.borderRadius;
    const values = Array.isArray(radius) ? radius : typeof radius === "number" ? [radius] : [];
    if (values.some((value) => typeof value === "number" && value > 2)) {
      warnings.push(`系列「${String(item.name ?? item.type)}」柱圆角超过 2px（视觉方案 §7.2）。`);
    }
    const area = item.areaStyle as PlainObject | undefined;
    const color = area?.color as PlainObject | undefined;
    const stops = color?.colorStops as Array<{ color?: string }> | undefined;
    if (Array.isArray(stops) && stops.length > 1) {
      const hues = new Set(stops.map((stop) => String(stop.color ?? "").replace(/[0-9a-f]{2}$/i, "").toLowerCase()));
      if (hues.size > 1) {
        warnings.push(`系列「${String(item.name ?? item.type)}」面积渐变不是单色透明度渐变（视觉方案 §7.2）。`);
      }
    }
  }
  return warnings;
}

export function isChartCardOptionEmpty(option: EChartsOption | null | undefined): boolean {
  if (!option) return true;
  const series = (option as PlainObject).series;
  if (series === undefined || series === null) return true;
  if (Array.isArray(series)) return series.length === 0;
  return false;
}

function normalizeSeries(option: EChartsOption): PlainObject[] {
  const series = (option as PlainObject).series;
  if (Array.isArray(series)) return series.filter(isPlainObject);
  return isPlainObject(series) ? [series] : [];
}

function isPlainObject(value: unknown): value is PlainObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
