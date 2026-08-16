import { BaseChart } from "../../../components/charts/BaseChart";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import type { AdbTrendItem } from "../../../api/contracts";
import { nocturneTokens } from "../../../theme/designSystem";

const YI = 100_000_000;

export type AdbDailyTrendChartProps = {
  trend: AdbTrendItem[];
  height?: number;
};

function buildTrendOption(trend: AdbTrendItem[]) {
  const dates = trend.map((item) => item.date);
  const dailyValues = trend.map((item) => item.daily_balance / YI);
  const ma30Values = trend.map((item) => item.moving_average_30d / YI);
  const dailyColor = nocturneTokens.color.inkMuted;
  const maColor = nocturneChartTheme.palette[0];

  return nocturneChartTheme.createLineChartOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (params: unknown) => {
        const items = Array.isArray(params) ? params as Array<{ seriesName: string; value: number; dataIndex: number }> : [];
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
      bottom: "auto",
    },
    grid: { left: 60, right: 24, top: 44, bottom: 36 },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: {
        formatter: (value: string) => {
          const parts = value.split("-");
          return parts.length === 3 ? `${parts[1]}-${parts[2]}` : value;
        },
      },
      boundaryGap: false,
    },
    yAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${value.toFixed(0)}亿` },
    },
    series: [
      {
        name: "日余额",
        type: "line",
        data: dailyValues,
        symbol: "none",
        lineStyle: { width: 1, color: dailyColor },
        itemStyle: { color: dailyColor },
      },
      {
        name: "30日移动均线",
        type: "line",
        data: ma30Values,
        symbol: "none",
        lineStyle: { width: 2, color: maColor, type: "solid" },
        itemStyle: { color: maColor },
      },
    ],
  });
}

/**
 * 日均余额日度走势图。
 *
 * 消费后端 `/api/analysis/adb` 返回的 `trend[]` 字段，
 * 展示区间内每日余额与 30 日移动平均线。
 */
export default function AdbDailyTrendChart({ trend, height = 340 }: AdbDailyTrendChartProps) {
  if (!trend.length) return null;
  return <BaseChart option={buildTrendOption(trend)} height={height} />;
}
