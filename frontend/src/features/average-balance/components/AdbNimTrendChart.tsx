import { BaseChart } from "../../../components/charts/BaseChart";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import type { AdbMonthlyDataItem } from "../../../api/contracts";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";

export type AdbNimTrendChartProps = {
  months: AdbMonthlyDataItem[];
  height?: number;
};

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value.toFixed(2)}%`;
}

function buildNimTrendOption(months: AdbMonthlyDataItem[]) {
  const labels = months.map((m) => m.month_label);
  const yieldValues = months.map((m) => m.asset_yield);
  const costValues = months.map((m) => m.liability_cost);
  const nimValues = months.map((m) => m.net_interest_margin);
  const assetYieldColor = nocturneChartTheme.palette[0];
  const liabilityCostColor = nocturneTokens.color.red;
  const nimColor = nocturneTokens.color.green;

  return nocturneChartTheme.createLineChartOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (params: unknown) => {
        const items = Array.isArray(params)
          ? (params as { seriesName: string; value: number | null; dataIndex: number }[])
          : [];
        if (!items.length) return "";
        const idx = items[0].dataIndex;
        const month = months[idx];
        const header = `<strong>${month.month_label}</strong>`;
        const lines = items.map((item) => `${item.seriesName}：${formatPct(item.value)}`);
        return [header, ...lines].join("<br/>");
      },
    },
    legend: {
      data: ["资产收益率", "负债成本率", "NIM利差"],
      top: 0,
      bottom: "auto",
    },
    grid: { left: 52, right: 24, top: 48, bottom: 36 },
    xAxis: {
      type: "category",
      data: labels,
      boundaryGap: false,
    },
    yAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${value.toFixed(1)}%` },
      splitLine: { lineStyle: { type: "dashed" } },
    },
    series: [
      {
        name: "资产收益率",
        type: "line",
        data: yieldValues,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { width: 2, color: assetYieldColor },
        itemStyle: { color: assetYieldColor },
      },
      {
        name: "负债成本率",
        type: "line",
        data: costValues,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { width: 2, color: liabilityCostColor },
        itemStyle: { color: liabilityCostColor },
      },
      {
        name: "NIM利差",
        type: "line",
        data: nimValues,
        symbol: "diamond",
        symbolSize: 7,
        lineStyle: { width: 2.5, color: nimColor, type: "dashed" },
        itemStyle: { color: nimColor },
      },
    ],
  });
}

/**
 * NIM 利差月度走势图。
 *
 * 消费月度统计中已有的 asset_yield / liability_cost / net_interest_margin，
 * 用双轴折线图展示 YTM vs 票息 vs NIM 的月度变化趋势。
 */
export default function AdbNimTrendChart({ months, height = 320 }: AdbNimTrendChartProps) {
  if (!months.length) return null;
  return <BaseChart option={buildNimTrendOption(months)} height={height} />;
}
