import { ChartCard } from "../../../components/charts/ChartCard";
import {
  CHART_CARD_HEIGHTS,
  type ChartCardHeight,
} from "../../../components/charts/chartCardScale";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import {
  buildComparisonDisplayRows,
  isComparisonDeviationAlert,
  type AdbComparisonChartRow,
} from "./adbComparisonMetrics";

export type { AdbComparisonChartRow } from "./adbComparisonMetrics";

const YI = 100_000_000;
const SERIES_SPOT = "期末时点";
const SERIES_AVG = "区间日均";

function formatYiValue(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return (value / YI).toFixed(2);
}

function formatSignedPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

/**
 * 横向条形（yAxis 分类、inverse 让规模最大者在顶部）：
 * 分类名走 y 轴，长名称截断以保留绘图区，完整名称由 tooltip 展示。
 * 日均系列右侧标签为偏离度，|偏离|>5% 走 down 红（与 KPI 警示同判据）。
 */
function buildComparisonOption(rows: AdbComparisonChartRow[]) {
  return nocturneChartTheme.createBarChartOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const items = Array.isArray(params) ? params as Array<{ dataIndex: number }> : [];
        if (!items.length) return "";
        const row = rows[items[0].dataIndex];
        const content = document.createElement("div");
        content.append(
          row.label,
          document.createElement("br"),
          `${SERIES_SPOT}：${formatYiValue(row.spot)} 亿元`,
          document.createElement("br"),
          `${SERIES_AVG}：${formatYiValue(row.avg)} 亿元`,
          document.createElement("br"),
          `偏离度：${formatSignedPct(row.deviationPct)}`,
        );
        return content;
      },
    },
    legend: { data: [SERIES_SPOT, SERIES_AVG] },
    grid: { left: 8, right: 64, top: 32 },
    xAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${(value / YI).toFixed(0)}亿`, hideOverlap: true },
    },
    yAxis: {
      type: "category",
      data: rows.map((row) => row.label),
      inverse: true,
      axisLabel: { fontSize: 11, width: 88, overflow: "truncate" },
    },
    series: [
      {
        name: SERIES_SPOT,
        type: "bar",
        data: rows.map((row) => row.spot),
        itemStyle: { color: nocturneChartTheme.palette[0] },
        barGap: "10%",
        barMaxWidth: 14,
      },
      {
        name: SERIES_AVG,
        type: "bar",
        data: rows.map((row) => ({
          value: row.avg,
          label: {
            color: isComparisonDeviationAlert(row.deviationPct)
              ? nocturneTokens.color.red
              : nocturneChartTheme.axisLabel.color,
          },
        })),
        itemStyle: { color: nocturneTokens.color.inkSoft },
        barMaxWidth: 14,
        label: {
          show: true,
          position: "right",
          formatter: ({ dataIndex }: { dataIndex: number }) =>
            formatSignedPct(rows[dataIndex]?.deviationPct),
          fontSize: nocturneChartTheme.axisLabel.fontSize,
        },
      },
    ],
  });
}

type AdbComparisonChartProps = {
  rows: AdbComparisonChartRow[];
  title: string;
  height?: ChartCardHeight;
  flat?: boolean;
};

export default function AdbComparisonChart({
  rows,
  title,
  height = CHART_CARD_HEIGHTS.hero,
  flat = false,
}: AdbComparisonChartProps) {
  const displayRows = buildComparisonDisplayRows(rows);
  return (
    <ChartCard
      flat={flat}
      title={title}
      question="期末时点与区间日均"
      unit="亿元"
      height={height}
      option={displayRows.length ? buildComparisonOption(displayRows) : null}
    />
  );
}
