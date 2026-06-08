import type { EChartsOption } from "../../../lib/echarts";
import type {
  StockSectorRow,
  StockSectorViewKind,
  StockSectorViewRow,
} from "./stockAnalysisPageModel";

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

export const stockChartPalette = {
  ink: "#0c1c33",
  muted: "#6b7d95",
  grid: "#e4e9f0",
  track: "#eef2f7",
  primary: "#1850a1",
  primaryLight: "#4d84cc",
  accent: "#2f68b8",
  success: "#1f7a55",
  successLight: "#86acdb",
  danger: "#b94743",
} as const;

export const sectorViewTabs: { key: StockSectorViewKind; label: string }[] = [
  { key: "score", label: "综合得分" },
  { key: "pctchange", label: "平均涨跌幅" },
  { key: "turnover", label: "换手活跃度" },
  { key: "amplitude", label: "波动振幅" },
];

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

export function buildSectorStrengthOption({
  rows,
  view,
  activeSectorCode,
}: {
  rows: StockSectorViewRow[];
  view: StockSectorViewKind;
  activeSectorCode: string | null;
}): EChartsOption {
  const values = rows.map((row) => resolveSectorMetricValue(row, view) ?? 0);
  const absMax = Math.max(...values.map((value) => Math.abs(value)), 0.0001);
  const xMin = view === "pctchange" ? -absMax * 1.08 : 0;
  const xMax =
    view === "score"
      ? 1
      : view === "pctchange"
        ? absMax * 1.08
        : absMax * 1.12;
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
      data: rows.map((row) => row.sectorName),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: stockChartPalette.ink,
        fontSize: 11,
        width: 74,
        overflow: "truncate",
      },
    },
    series: [
      {
        type: "bar",
        data: rows.map((row, index) => ({
          value: values[index],
          itemStyle: {
            color:
              row.sectorCode === activeSectorCode
                ? stockChartPalette.primary
                : stockChartPalette.primaryLight,
            borderRadius: [0, 3, 3, 0],
          },
        })),
        barWidth: 14,
        barMaxWidth: 18,
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
            const row = rows[Number(params.dataIndex ?? 0)];
            if (!row) return "";
            if (view === "score") return row.score;
            if (view === "pctchange") return row.pctChange;
            if (view === "turnover") return row.turnover;
            return row.amplitude;
          },
        },
      },
    ],
    tooltip: {
      trigger: "axis",
      confine: true,
      formatter: (params) => {
        const item = Array.isArray(params) ? params[0] : params;
        const row = rows[Number(item?.dataIndex ?? 0)];
        if (!row) return "";
        return `${row.rank}. ${row.sectorName}<br/>${sectorViewLabel(view)}: ${
          view === "score" ? row.score : view === "pctchange" ? row.pctChange : view === "turnover" ? row.turnover : row.amplitude
        }<br/>成分 ${row.constituentCount}`;
      },
    },
  };
}
