import { ibChartTheme } from "../../../components/charts/chartTheme";
import ReactECharts from "../../../lib/echarts";
import { EM_DASH } from "../../../utils/format";

const YI = 100_000_000;
const SERIES_SPOT = "期末时点";
const SERIES_AVG = "区间日均";

export type AdbComparisonChartRow = {
  label: string;
  spot: number;
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
  return ibChartTheme.createBarChartOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: { dataIndex: number }[]) => {
        if (!items.length) return "";
        const row = rows[items[0].dataIndex];
        return [
          row.label,
          `${SERIES_SPOT}：${(row.spot / YI).toFixed(2)} 亿元`,
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
        itemStyle: { color: ibChartTheme.palette[0] },
        barGap: "10%",
      },
      {
        name: SERIES_AVG,
        type: "bar",
        data: rows.map((row) => row.avg),
        itemStyle: { color: ibChartTheme.palette[2] },
        label: {
          show: true,
          position: "top",
          formatter: ({ dataIndex }: { dataIndex: number }) =>
            formatSignedPct(rows[dataIndex]?.deviationPct),
          color: ibChartTheme.axisLabel.color,
          fontSize: ibChartTheme.axisLabel.fontSize,
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
  return <ReactECharts option={buildComparisonOption(rows)} style={{ height }} notMerge lazyUpdate />;
}
