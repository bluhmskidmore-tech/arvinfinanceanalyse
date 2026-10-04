import type { EChartsOption } from "../../../lib/echarts";
import { nocturneTokens } from "../../../theme/designSystem";
import type {
  StockSectorRow,
  StockSectorViewKind,
  StockSectorViewRow,
} from "./stockAnalysisPageModel";
import type { SectorSeriesTrendLine } from "./stockAnalysisSectorSeriesModel";

export type SectorSortKey =
  | "rank"
  | "sectorCode"
  | "sectorName"
  | "score"
  | "pctChange"
  | "turnover"
  | "amplitude"
  | "constituentCount";

/**
 * ECharts（canvas）取色走 nocturneTokens 常量组（数值源 = tokens.css 的
 * Nocturne scope 色板；页面 DOM 侧由 data-moss-theme-scope="stock-analysis"
 * 翻转，canvas 无法消费 CSS 变量故取常量镜像，先例见组合工作台）。
 */
export const stockChartPalette = {
  ink: nocturneTokens.color.ink,
  muted: nocturneTokens.color.inkMuted,
  grid: nocturneTokens.color.lineSoft,
  track: nocturneTokens.color.line,
  primary: nocturneTokens.color.blue,
  primaryLight: nocturneTokens.color.inkMuted,
  accent: nocturneTokens.color.inkSoft,
  success: nocturneTokens.color.green,
  successLight: nocturneTokens.color.greenSoft,
  danger: nocturneTokens.color.red,
  gold: nocturneTokens.color.amber,
} as const;

export const sectorViewTabs: { key: StockSectorViewKind; label: string }[] = [
  { key: "score", label: "综合得分" },
  { key: "pctchange", label: "平均涨跌幅" },
  { key: "turnover", label: "换手活跃度" },
  { key: "amplitude", label: "波动振幅" },
];

export const SECTOR_STRENGTH_VISIBLE_LIMIT = 10;

export function resolveSectorMetricValue(row: StockSectorRow, view: StockSectorViewKind): number | null {
  if (view === "pctchange") return row.pctChangeValue;
  if (view === "turnover") return row.turnoverValue;
  if (view === "amplitude") return row.amplitudeValue;
  return row.scoreValue;
}

export function sectorViewLabel(view: StockSectorViewKind): string {
  const tab = sectorViewTabs.find((item) => item.key === view);
  return tab?.label ?? "综合得分";
}

/** X 轴范围口径：首屏 SVG 条形与深研 ECharts 图共用，防止两处渲染漂移。 */
function resolveSectorStrengthScale(
  values: number[],
  view: StockSectorViewKind,
): { xMin: number; xMax: number } {
  const absMax = Math.max(...values.map((value) => Math.abs(value)), 0.0001);
  const xMin = view === "pctchange" ? -absMax * 1.08 : 0;
  const xMax =
    view === "score"
      ? 1
      : view === "pctchange"
        ? absMax * 1.08
        : absMax * 1.12;
  return { xMin, xMax };
}

/** 当前视角对应的后端格式化文本；不在前端重算业务数值。 */
function sectorMetricDisplayLabel(row: StockSectorViewRow, view: StockSectorViewKind): string {
  if (view === "score") return row.score;
  if (view === "pctchange") return row.pctChange;
  if (view === "turnover") return row.turnover;
  return row.amplitude;
}

export function buildSectorStrengthOption({
  rows,
  view,
  activeSectorCode,
}: {
  rows: StockSectorViewRow[];
  view: StockSectorViewKind;
  activeSectorCode: string | null;
}): EChartsOption {
  const visibleRows = rows.slice(0, SECTOR_STRENGTH_VISIBLE_LIMIT);
  const values = visibleRows.map((row) => resolveSectorMetricValue(row, view) ?? 0);
  const { xMin, xMax } = resolveSectorStrengthScale(values, view);
  return {
    animation: false,
    grid: { top: 6, right: 12, bottom: 4, left: 78, containLabel: false },
    xAxis: {
      type: "value",
      min: xMin,
      max: xMax,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: stockChartPalette.muted,
        fontSize: 10,
      },
      splitLine: {
        lineStyle: { color: stockChartPalette.grid, type: "dashed" },
      },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: visibleRows.map((row) => row.sectorName),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: stockChartPalette.ink,
        fontSize: 10,
        interval: 0,
      },
    },
    series: [
      {
        type: "bar",
        data: visibleRows.map((row, index) => ({
          value: values[index],
          itemStyle: {
            color:
              row.sectorCode === activeSectorCode
                ? stockChartPalette.primary
                : stockChartPalette.primaryLight,
            borderRadius: [0, 3, 3, 0],
          },
        })),
        barCategoryGap: "18%",
        barMaxWidth: 12,
        showBackground: true,
        backgroundStyle: { color: stockChartPalette.track, borderRadius: [0, 3, 3, 0] },
        label: {
          show: true,
          position: "insideRight",
          color: stockChartPalette.ink,
          fontSize: 10,
          fontWeight: 600,
          padding: [0, 6, 0, 0],
          formatter: (params) => {
            const row = visibleRows[Number(params.dataIndex ?? 0)];
            return row ? sectorMetricDisplayLabel(row, view) : "";
          },
        },
      },
    ],
    tooltip: {
      trigger: "axis",
      confine: true,
      formatter: (params) => {
        const item = Array.isArray(params) ? params[0] : params;
        const row = visibleRows[Number(item?.dataIndex ?? 0)];
        if (!row) return "";
        return `${row.rank}. ${row.sectorName}<br/>${sectorViewLabel(view)}: ${sectorMetricDisplayLabel(row, view)}<br/>成分 ${row.constituentCount}`;
      },
    },
  };
}

const sectorSeriesTrendColors = [
  stockChartPalette.primary,
  stockChartPalette.accent,
  stockChartPalette.gold,
  stockChartPalette.success,
  stockChartPalette.danger,
] as const;

export function buildSectorSeriesTrendOption(lines: SectorSeriesTrendLine[]): EChartsOption {
  const tradeDates = [...new Set(lines.flatMap((line) => line.dates))].sort();
  if (tradeDates.length === 0 || lines.length === 0) {
    return { animation: false, series: [] };
  }

  return {
    animation: false,
    legend: {
      bottom: 0,
      type: "scroll",
      textStyle: { color: stockChartPalette.muted, fontSize: 10 },
    },
    grid: { top: 12, right: 12, bottom: 48, left: 48, containLabel: false },
    xAxis: {
      type: "category",
      data: tradeDates,
      axisLine: { lineStyle: { color: stockChartPalette.grid } },
      axisTick: { show: false },
      axisLabel: { color: stockChartPalette.muted, fontSize: 10 },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 1,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: stockChartPalette.muted, fontSize: 10 },
      splitLine: { lineStyle: { color: stockChartPalette.grid, type: "dashed" } },
    },
    series: lines.map((line, index) => ({
      name: line.sectorName,
      type: "line",
      smooth: false,
      symbol: "circle",
      symbolSize: 5,
      data: tradeDates.map((tradeDate) => {
        const pointIndex = line.dates.indexOf(tradeDate);
        return pointIndex >= 0 ? line.scores[pointIndex] : null;
      }),
      itemStyle: { color: sectorSeriesTrendColors[index % sectorSeriesTrendColors.length] },
      lineStyle: { width: 2 },
      connectNulls: false,
    })),
    tooltip: {
      trigger: "axis",
      confine: true,
    },
  };
}
