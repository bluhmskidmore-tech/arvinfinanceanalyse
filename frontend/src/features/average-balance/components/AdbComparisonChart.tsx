import { BaseChart } from "../../../components/charts/BaseChart";
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
 * 分类名走 y 轴整行可读，不再把 24+ 分类塞进 x 轴挤成墨团。
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
        return [
          row.label,
          `${SERIES_SPOT}：${formatYiValue(row.spot)} 亿元`,
          `${SERIES_AVG}：${formatYiValue(row.avg)} 亿元`,
          `偏离度：${formatSignedPct(row.deviationPct)}`,
        ].join("<br/>");
      },
    },
    legend: { data: [SERIES_SPOT, SERIES_AVG], top: 0, bottom: "auto" },
    grid: { left: 8, right: 64, top: 32, bottom: 8, containLabel: true },
    xAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${(value / YI).toFixed(0)}亿` },
    },
    yAxis: {
      type: "category",
      data: rows.map((row) => row.label),
      inverse: true,
    },
    series: [
      {
        name: SERIES_SPOT,
        type: "bar",
        data: rows.map((row) => row.spot),
        itemStyle: { color: nocturneChartTheme.palette[0] },
        barGap: "10%",
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
  /** 缺省时按展示行数自适应（Top10+其他 约 520px），避免行多标签挤压。 */
  height?: number;
};

export default function AdbComparisonChart({
  rows,
  height,
}: AdbComparisonChartProps) {
  const displayRows = buildComparisonDisplayRows(rows);
  const resolvedHeight = height ?? Math.max(280, displayRows.length * 40 + 80);
  return <BaseChart option={buildComparisonOption(displayRows)} height={resolvedHeight} />;
}
