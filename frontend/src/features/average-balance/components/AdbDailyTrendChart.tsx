import ReactECharts from "../../../lib/echarts";
import type { AdbTrendItem } from "../../../api/contracts";
import { mossChartCategoricalPalette } from "../../../components/charts/chartTheme";
import { ibTokens } from "../../../theme/designSystem";

const YI = 100_000_000;

export type AdbDailyTrendChartProps = {
  trend: AdbTrendItem[];
  height?: number;
};

function buildTrendOption(trend: AdbTrendItem[]) {
  const dates = trend.map((item) => item.date);
  const dailyValues = trend.map((item) => item.daily_balance / YI);
  const ma30Values = trend.map((item) => item.moving_average_30d / YI);

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (items: { seriesName: string; value: number; dataIndex: number }[]) => {
        if (!items.length) return "";
        const idx = items[0].dataIndex;
        const row = trend[idx];
        const header = `<strong>${row.date}</strong>`;
        const lines = items.map(
          (item) => `${item.seriesName}：${Number(item.value).toFixed(2)} 亿元`,
        );
        return [header, ...lines].join("<br/>");
      },
    },
    legend: {
      data: ["日余额", "30日移动均线"],
      top: 0,
    },
    grid: { left: 60, right: 24, top: 44, bottom: 36 },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: {
        fontSize: 11,
        formatter: (value: string) => {
          /* Show only MM-DD for compactness */
          const parts = value.split("-");
          return parts.length === 3 ? `${parts[1]}-${parts[2]}` : value;
        },
      },
      boundaryGap: false,
    },
    yAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${value.toFixed(0)}亿` },
      splitLine: { lineStyle: { color: ibTokens.color.hairline } },
    },
    series: [
      {
        name: "日余额",
        type: "line",
        data: dailyValues,
        symbol: "none",
        lineStyle: { width: 1.5, color: mossChartCategoricalPalette[3] },
      },
      {
        name: "30日移动均线",
        type: "line",
        data: ma30Values,
        symbol: "none",
        lineStyle: { width: 2, color: ibTokens.color.accent, type: "solid" },
      },
    ],
  };
}

/**
 * 日均余额日度走势图。
 *
 * 消费后端 `/api/analysis/adb` 返回的 `trend[]` 字段，
 * 展示区间内每日余额与 30 日移动平均线。
 */
export default function AdbDailyTrendChart({ trend, height = 340 }: AdbDailyTrendChartProps) {
  if (!trend.length) return null;
  return <ReactECharts option={buildTrendOption(trend)} style={{ height }} notMerge lazyUpdate />;
}
