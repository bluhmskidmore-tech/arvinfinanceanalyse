import { BaseChart } from "../../../components/charts/BaseChart";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";

const YI = 100_000_000;
const SERIES_SPOT = "期末时点";
const SERIES_AVG = "区间日均";

export type AdbComparisonChartRow = {
  label: string;
  /** null 表示缺数：系列不画柱，tooltip 显示 EM_DASH */
  spot: number | null;
  avg: number | null;
  deviationPct: number | null;
};

function formatYiValue(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return (value / YI).toFixed(2);
}

function formatSignedPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

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
    grid: { left: 24, right: 24, top: 44, bottom: 76 },
    xAxis: {
      type: "category",
      data: rows.map((row) => row.label),
      axisLabel: { interval: 0, rotate: 20 },
    },
    yAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${(value / YI).toFixed(0)}亿` },
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
        data: rows.map((row) => row.avg),
        itemStyle: { color: nocturneTokens.color.inkSoft },
        label: {
          show: true,
          position: "top",
          formatter: ({ dataIndex }: { dataIndex: number }) =>
            formatSignedPct(rows[dataIndex]?.deviationPct),
          color: nocturneChartTheme.axisLabel.color,
          fontSize: nocturneChartTheme.axisLabel.fontSize,
        },
      },
    ],
  });
}

type AdbComparisonChartProps = {
  rows: AdbComparisonChartRow[];
  height?: number;
};

export default function AdbComparisonChart({
  rows,
  height = 420,
}: AdbComparisonChartProps) {
  return <BaseChart option={buildComparisonOption(rows)} height={height} />;
}
