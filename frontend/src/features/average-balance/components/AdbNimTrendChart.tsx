import ReactECharts from "../../../lib/echarts";
import type { AdbMonthlyDataItem } from "../../../api/contracts";

export type AdbNimTrendChartProps = {
  months: AdbMonthlyDataItem[];
  height?: number;
};

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(2)}%`;
}

function buildNimTrendOption(months: AdbMonthlyDataItem[]) {
  const labels = months.map((m) => m.month_label);
  const yieldValues = months.map((m) => m.asset_yield);
  const costValues = months.map((m) => m.liability_cost);
  const nimValues = months.map((m) => m.net_interest_margin);

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (items: { seriesName: string; value: number | null; dataIndex: number }[]) => {
        if (!items.length) return "";
        const idx = items[0].dataIndex;
        const month = months[idx];
        const header = `<strong>${month.month_label}</strong>`;
        const lines = items.map(
          (item) => `${item.seriesName}：${formatPct(item.value)}`,
        );
        return [header, ...lines].join("<br/>");
      },
    },
    legend: {
      data: ["加权YTM", "加权票息", "NIM利差"],
      top: 0,
    },
    grid: { left: 52, right: 24, top: 48, bottom: 36 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { fontSize: 11 },
      boundaryGap: false,
    },
    yAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${value.toFixed(1)}%` },
      splitLine: { lineStyle: { type: "dashed", color: "#e5e7eb" } },
    },
    series: [
      {
        name: "加权YTM",
        type: "line",
        data: yieldValues,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { width: 2, color: "#2563eb" },
        itemStyle: { color: "#2563eb" },
      },
      {
        name: "加权票息",
        type: "line",
        data: costValues,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { width: 2, color: "#dc2626" },
        itemStyle: { color: "#dc2626" },
      },
      {
        name: "NIM利差",
        type: "line",
        data: nimValues,
        symbol: "diamond",
        symbolSize: 7,
        lineStyle: { width: 2.5, color: "#16a34a", type: "dashed" },
        itemStyle: { color: "#16a34a" },
        areaStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(22,163,74,0.12)" },
              { offset: 1, color: "rgba(22,163,74,0.01)" },
            ],
          },
        },
      },
    ],
  };
}

/**
 * NIM 利差月度走势图。
 *
 * 消费月度统计中已有的 asset_yield / liability_cost / net_interest_margin，
 * 用双轴折线图展示 YTM vs 票息 vs NIM 的月度变化趋势。
 */
export default function AdbNimTrendChart({ months, height = 320 }: AdbNimTrendChartProps) {
  if (!months.length) return null;
  return <ReactECharts option={buildNimTrendOption(months)} style={{ height }} notMerge lazyUpdate />;
}
