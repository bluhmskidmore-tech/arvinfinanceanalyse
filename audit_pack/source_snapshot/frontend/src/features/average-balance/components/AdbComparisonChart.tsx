import ReactECharts from "../../../lib/echarts";

const YI = 100_000_000;

export type AdbComparisonChartRow = {
  label: string;
  spot: number;
  avg: number;
  deviationPct: number;
};

function formatSignedPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function buildComparisonOption(rows: AdbComparisonChartRow[]) {
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: { dataIndex: number }[]) => {
        if (!items.length) return "";
        const row = rows[items[0].dataIndex];
        return [
          row.label,
          `Spot: ${(row.spot / YI).toFixed(2)} 亿元`,
          `ADB: ${(row.avg / YI).toFixed(2)} 亿元`,
          `偏离度: ${formatSignedPct(row.deviationPct)}`,
        ].join("<br/>");
      },
    },
    legend: { data: ["Spot（期末）", "ADB（日均）"], top: 0 },
    grid: { left: 24, right: 24, top: 44, bottom: 76 },
    xAxis: {
      type: "category",
      data: rows.map((row) => row.label),
      axisLabel: { interval: 0, rotate: 20, fontSize: 11 },
    },
    yAxis: { type: "value", axisLabel: { formatter: (value: number) => `${(value / YI).toFixed(0)}亿` } },
    series: [
      {
        name: "Spot（期末）",
        type: "bar",
        data: rows.map((row) => row.spot),
        itemStyle: { color: "#3b82f6" },
        barGap: "10%",
      },
      {
        name: "ADB（日均）",
        type: "bar",
        data: rows.map((row) => row.avg),
        itemStyle: { color: "#f97316" },
        label: {
          show: true,
          position: "top",
          formatter: ({ dataIndex }: { dataIndex: number }) =>
            formatSignedPct(rows[dataIndex]?.deviationPct ?? 0),
          color: "#475569",
          fontSize: 11,
        },
      },
    ],
  };
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
