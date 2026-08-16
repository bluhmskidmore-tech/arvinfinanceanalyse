import type { EChartsOption } from "../../../lib/echarts";
import { nocturneTokens } from "../../../theme/designSystem";
import type {
  StockSectorRow,
  StockSectorViewKind,
  StockSectorViewRow,
} from "./stockAnalysisPageModel";
import type { SectorSeriesTrendLine } from "./stockAnalysisSectorSeriesModel";

export type CompactChartRow = {
  key: string;
  label: string;
  value: number;
  detail?: string;
};

type ReviewQueueChartCandidate = {
  stockCode: string;
  stockName: string;
  rank: number;
  sectorName: string;
  distanceToBreakoutPct: string;
  primaryEvidence: unknown[];
  supportingEvidence: unknown[];
};

type OutputChartCounts = {
  supportedCount: number;
  unsupportedCount: number;
};

type RiskSupplyChartInput = {
  position_count: number;
  signal_count: number;
  watch_items?: unknown[] | null;
};

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

export function buildCompactBarOption({
  labels,
  values,
  color = stockChartPalette.primary,
  valueSuffix = "",
}: {
  labels: string[];
  values: number[];
  color?: string;
  valueSuffix?: string;
}): EChartsOption {
  return {
    animation: false,
    grid: { top: 2, right: 4, bottom: 2, left: 2, containLabel: false },
    xAxis: { type: "value", show: false, splitLine: { show: false } },
    yAxis: {
      type: "category",
      inverse: true,
      data: labels,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
    },
    series: [
      {
        type: "bar",
        data: values,
        barWidth: 8,
        itemStyle: { color, borderRadius: [2, 2, 2, 2] },
        backgroundStyle: { color: stockChartPalette.track, borderRadius: 2 },
        showBackground: true,
      },
    ],
    tooltip: {
      trigger: "axis",
      confine: true,
      formatter: (params) => {
        const item = Array.isArray(params) ? params[0] : params;
        const index = Number(item?.dataIndex ?? 0);
        return `${labels[index] ?? ""}: ${Number(item?.value ?? 0).toFixed(2)}${valueSuffix}`;
      },
    },
  };
}

export function buildReviewQueueChartRows(
  candidates: ReviewQueueChartCandidate[],
): CompactChartRow[] {
  const visible = candidates.slice(0, 6);
  return visible.map((card, index) => {
    const evidenceCount = card.primaryEvidence.length + card.supportingEvidence.length;
    return {
      key: card.stockCode,
      label: `#${card.rank} ${card.stockName}`,
      value: visible.length - index,
      detail: `${card.sectorName} \u00b7 \u8ddd\u89c2\u5bdf\u4f4d ${card.distanceToBreakoutPct} \u00b7 \u8bc1\u636e ${evidenceCount}`,
    };
  });
}

export function buildSectorChartRows(rows: StockSectorViewRow[]): CompactChartRow[] {
  return rows.slice(0, 5).map((row) => ({
    key: row.sectorCode,
    label: `${row.rank}. ${row.sectorName}`,
    value: row.scoreValue ?? 0,
    detail: `${row.score} / ${row.pctChange}`,
  }));
}

export function buildOutputChartRows(counts: OutputChartCounts | null): CompactChartRow[] {
  return counts
    ? [
        { key: "supported", label: "\u53ef\u7528", value: counts.supportedCount },
        { key: "unsupported", label: "\u963b\u65ad", value: counts.unsupportedCount },
      ]
    : [];
}

export function buildRiskSupplyChartRows(risk: RiskSupplyChartInput | null): CompactChartRow[] {
  if (!risk) {
    return [
      { key: "position", label: "\u6301\u4ed3", value: 0 },
      { key: "signal", label: "\u89e6\u53d1", value: 0 },
      { key: "watch", label: "\u89c2\u5bdf", value: 0 },
    ];
  }
  return [
    { key: "position", label: "\u6301\u4ed3", value: risk.position_count },
    { key: "signal", label: "\u89e6\u53d1", value: risk.signal_count },
    { key: "watch", label: "\u89c2\u5bdf", value: risk.watch_items?.length ?? 0 },
  ];
}

export function buildReviewQueueRankingOption(rows: CompactChartRow[]): EChartsOption {
  return {
    animation: false,
    grid: { top: 3, right: 4, bottom: 3, left: 2, containLabel: false },
    xAxis: { type: "value", show: false, splitLine: { show: false } },
    yAxis: {
      type: "category",
      inverse: true,
      data: rows.map((row) => row.label),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
    },
    series: [
      {
        type: "bar",
        data: rows.map((row) => row.value),
        barWidth: 9,
        itemStyle: { color: stockChartPalette.success, borderRadius: [2, 2, 2, 2] },
        backgroundStyle: { color: stockChartPalette.track, borderRadius: 2 },
        showBackground: true,
      },
    ],
    tooltip: {
      trigger: "axis",
      confine: true,
      formatter: (params) => {
        const item = Array.isArray(params) ? params[0] : params;
        const index = Number(item?.dataIndex ?? 0);
        const row = rows[index];
        return row ? `${row.label}<br/>${row.detail ?? ""}` : "";
      },
    },
  };
}

export function buildEventSummaryOption(rows: Array<{ label: string; count: number }>): EChartsOption {
  return {
    animation: false,
    grid: { top: 4, right: 4, bottom: 4, left: 2, containLabel: false },
    xAxis: { type: "value", show: false, splitLine: { show: false } },
    yAxis: { type: "category", show: false, data: ["输出"] },
    series: rows.map((row, index) => ({
      name: row.label,
      type: "bar",
      stack: "events",
      data: [row.count],
      barWidth: 10,
      itemStyle: {
        color: [
          stockChartPalette.primary,
          stockChartPalette.accent,
          stockChartPalette.danger,
          stockChartPalette.primaryLight,
        ][index],
        borderRadius: index === 0 ? [2, 0, 0, 2] : index === rows.length - 1 ? [0, 2, 2, 0] : 0,
      },
    })),
    tooltip: { trigger: "item", confine: true },
  };
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

export type SectorStrengthBarRow = {
  key: string;
  name: string;
  rank: number;
  /** 右端数值标签：直接透出后端格式化文本 */
  valueLabel: string;
  /** 原生 title 悬停文本，内容对齐 ECharts 版 tooltip */
  title: string;
  active: boolean;
  /** 条形起点，轨道宽度的 0-1 分数（pctchange 负值自零轴向左） */
  barStartFraction: number;
  /** 条形跨度，轨道宽度的 0-1 分数 */
  barSpanFraction: number;
};

/**
 * 首屏「板块强度」轻量 SVG 条形的视图模型。
 * 口径与 buildSectorStrengthOption 完全一致：前 10 行、同一 X 轴范围、
 * 同一数值标签与 active 高亮语义；仅渲染载体从 ECharts 换成内联 SVG。
 */
export function buildSectorStrengthBarRows({
  rows,
  view,
  activeSectorCode,
}: {
  rows: StockSectorViewRow[];
  view: StockSectorViewKind;
  activeSectorCode: string | null;
}): SectorStrengthBarRow[] {
  const visibleRows = rows.slice(0, SECTOR_STRENGTH_VISIBLE_LIMIT);
  const values = visibleRows.map((row) => resolveSectorMetricValue(row, view) ?? 0);
  const { xMin, xMax } = resolveSectorStrengthScale(values, view);
  const range = xMax - xMin;
  const zeroFraction = (0 - xMin) / range;
  return visibleRows.map((row, index) => {
    const value = Math.min(Math.max(values[index] ?? 0, xMin), xMax);
    const valueFraction = (value - xMin) / range;
    const valueLabel = sectorMetricDisplayLabel(row, view);
    return {
      key: row.sectorCode,
      name: row.sectorName,
      rank: row.rank,
      valueLabel,
      title: `${row.rank}. ${row.sectorName}\n${sectorViewLabel(view)}: ${valueLabel}\n成分 ${row.constituentCount}`,
      active: row.sectorCode === activeSectorCode,
      barStartFraction: Math.min(zeroFraction, valueFraction),
      barSpanFraction: Math.abs(valueFraction - zeroFraction),
    };
  });
}

export type SectorStrengthCardModel = {
  state: "ready" | "loading" | "empty" | "error";
  bars: SectorStrengthBarRow[];
  sectorCount: number;
  sourceLabel: string;
  leaderLabel: string | null;
  emptyReason: string | null;
  errorMessage: string | null;
};

/**
 * 首屏「板块强度」卡完整视图模型。
 * 状态优先级沿用页面原有口径：有行即 ready；否则按支撑序列回退查询的
 * loading / error / empty 判定。空态与错误文案仅在对应状态给出。
 */
export function buildSectorStrengthCardModel({
  rows,
  view,
  activeSectorCode,
  sourceLabel,
  leaderName,
  seriesLoading,
  seriesErrored,
  seriesErrorMessage,
}: {
  rows: StockSectorViewRow[];
  view: StockSectorViewKind;
  activeSectorCode: string | null;
  sourceLabel: string;
  leaderName: string | null;
  seriesLoading: boolean;
  seriesErrored: boolean;
  seriesErrorMessage: string | null;
}): SectorStrengthCardModel {
  const state =
    rows.length > 0 ? "ready" : seriesLoading ? "loading" : seriesErrored ? "error" : "empty";
  return {
    state,
    bars: state === "ready" ? buildSectorStrengthBarRows({ rows, view, activeSectorCode }) : [],
    sectorCount: rows.length,
    sourceLabel,
    leaderLabel: leaderName,
    emptyReason: state === "empty" ? "板块强度暂无可用样本，等待快照或支撑序列补全" : null,
    errorMessage: state === "error" ? seriesErrorMessage : null,
  };
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
          fontWeight: 700,
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
