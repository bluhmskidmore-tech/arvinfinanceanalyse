import ReactECharts from "../../../lib/echarts";
import type { CSSProperties } from "react";

export type AdbMonthlyHorizontalChartRow = {
  category: string;
  avgYi: number;
  weightedRate: number | null;
};

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(2)}%`;
}

function buildHorizontalOption(rows: AdbMonthlyHorizontalChartRow[], title: string, color: string) {
  return {
    title: { text: title, left: 0, textStyle: { fontSize: 13, fontWeight: 600 } },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: { dataIndex: number }[]) => {
        if (!items.length) return "";
        const row = rows[items[0].dataIndex];
        return [
          row.category,
          `日均: ${row.avgYi.toFixed(2)} 亿元`,
          `加权利率: ${formatPct(row.weightedRate)}`,
        ].join("<br/>");
      },
    },
    grid: { left: 120, right: 24, top: 44, bottom: 24 },
    xAxis: { type: "value", axisLabel: { formatter: (value: number) => `${value.toFixed(0)}亿` } },
    yAxis: { type: "category", data: rows.map((row) => row.category), axisLabel: { fontSize: 11 } },
    series: [
      {
        type: "bar",
        data: rows.map((row) => row.avgYi),
        itemStyle: { color },
        label: {
          show: true,
          position: "right",
          formatter: ({ dataIndex }: { dataIndex: number }) => rows[dataIndex]?.avgYi.toFixed(2) ?? "0.00",
        },
      },
    ],
  };
}

type AdbMonthlyHorizontalChartProps = {
  rows: AdbMonthlyHorizontalChartRow[];
  title: string;
  color: string;
  height?: number;
  style?: CSSProperties;
};

export default function AdbMonthlyHorizontalChart({
  rows,
  title,
  color,
  height = 320,
  style,
}: AdbMonthlyHorizontalChartProps) {
  return (
    <ReactECharts
      option={buildHorizontalOption(rows, title, color)}
      style={{ height, ...style }}
      notMerge
      lazyUpdate
    />
  );
}
