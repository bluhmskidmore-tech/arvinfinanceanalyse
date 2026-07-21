import { ibChartTheme } from "../../../components/charts/chartTheme";
import ReactECharts from "../../../lib/echarts";
import type { CSSProperties } from "react";
import { EM_DASH } from "../../../utils/format";

export type AdbMonthlyHorizontalChartRow = {
  category: string;
  avgYi: number;
  weightedRate: number | null;
};

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value.toFixed(2)}%`;
}

function buildHorizontalOption(rows: AdbMonthlyHorizontalChartRow[], title: string, color: string) {
  return ibChartTheme.createBarChartOption({
    title: {
      text: title,
      left: 0,
      textStyle: {
        fontSize: 13,
        fontWeight: 600,
        color: ibChartTheme.axisLabel.color,
      },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const items = Array.isArray(params) ? params as Array<{ dataIndex: number }> : [];
        if (!items.length) return "";
        const row = rows[items[0].dataIndex];
        return [
          row.category,
          `日均：${row.avgYi.toFixed(2)} 亿元`,
          `加权利率：${formatPct(row.weightedRate)}`,
        ].join("<br/>");
      },
    },
    legend: { show: false },
    grid: { left: 120, right: 24, top: 44, bottom: 24 },
    xAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${value.toFixed(0)}亿` },
    },
    yAxis: {
      type: "category",
      data: rows.map((row) => row.category),
    },
    series: [
      {
        type: "bar",
        data: rows.map((row) => row.avgYi),
        itemStyle: { color },
        label: {
          show: true,
          position: "right",
          formatter: ({ dataIndex }: { dataIndex: number }) =>
            rows[dataIndex]?.avgYi.toFixed(2) ?? "0.00",
          color: ibChartTheme.axisLabel.color,
        },
      },
    ],
  });
}

type AdbMonthlyHorizontalChartProps = {
  rows: AdbMonthlyHorizontalChartRow[];
  title: string;
  color: string;
  height?: number;
  style?: CSSProperties;
  className?: string;
};

export default function AdbMonthlyHorizontalChart({
  rows,
  title,
  color,
  height = 320,
  style,
  className,
}: AdbMonthlyHorizontalChartProps) {
  return (
    <ReactECharts
      className={className}
      option={buildHorizontalOption(rows, title, color)}
      style={{ height, ...style }}
      notMerge
      lazyUpdate
    />
  );
}
