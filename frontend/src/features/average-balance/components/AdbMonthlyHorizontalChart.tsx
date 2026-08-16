import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import ReactECharts from "../../../lib/echarts";
import type { CSSProperties } from "react";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";

export type AdbMonthlyHorizontalChartRow = {
  category: string;
  /** null 表示上游缺数（区间日均/期末时点不可用）：不画柱，tooltip/标签显示 EM_DASH */
  avgYi: number | null;
  weightedRate: number | null;
};

function formatYi(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return value.toFixed(2);
}

export type AdbMonthlyHorizontalChartVariant = "asset" | "liability";

const VARIANT_BAR_COLOR: Record<AdbMonthlyHorizontalChartVariant, string> = {
  asset: nocturneTokens.color.blue,
  liability: nocturneTokens.color.red,
};

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value.toFixed(2)}%`;
}

function buildHorizontalOption(rows: AdbMonthlyHorizontalChartRow[], title: string, color: string) {
  return nocturneChartTheme.createBarChartOption({
    title: {
      text: title,
      left: 0,
      textStyle: {
        fontSize: 13,
        fontWeight: 600,
        color: nocturneChartTheme.axisLabel.color,
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
          `日均：${formatYi(row.avgYi)} 亿元`,
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
          formatter: ({ dataIndex }: { dataIndex: number }) => formatYi(rows[dataIndex]?.avgYi),
          color: nocturneChartTheme.axisLabel.color,
        },
      },
    ],
  });
}

type AdbMonthlyHorizontalChartProps = {
  rows: AdbMonthlyHorizontalChartRow[];
  title: string;
  /** 显式 color 优先于 variant；两者都缺省时回退 Nocturne 主题主色。 */
  color?: string;
  variant?: AdbMonthlyHorizontalChartVariant;
  height?: number;
  style?: CSSProperties;
  className?: string;
};

export default function AdbMonthlyHorizontalChart({
  rows,
  title,
  color,
  variant,
  height = 320,
  style,
  className,
}: AdbMonthlyHorizontalChartProps) {
  const barColor = color ?? (variant ? VARIANT_BAR_COLOR[variant] : nocturneChartTheme.palette[0]);
  return (
    <ReactECharts
      className={className}
      option={buildHorizontalOption(rows, title, barColor)}
      style={{ height, ...style }}
      notMerge
      lazyUpdate
    />
  );
}
