import type { NcdFundingProxyPayload } from "../../../../api/contracts";
import type { EChartsOption } from "../../../../lib/echarts";
import { buildMarketDataChartTooltip, marketDataChartTheme } from "./marketDataChartTheme";

const TENORS = ["1M", "3M", "6M", "9M", "1Y"] as const;

function cellValue(value: number | string | null | undefined): number | null {
  if (value == null || value === "") {
    return null;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function buildNcdProxyHeatmapOption(
  payload: Pick<NcdFundingProxyPayload, "rows"> | undefined,
): EChartsOption | null {
  const rows = payload?.rows ?? [];
  if (rows.length === 0) {
    return null;
  }

  const yLabels = rows.map((row) => row.label);
  const data: Array<[number, number, number | null]> = [];

  rows.forEach((row, yIndex) => {
    TENORS.forEach((tenor, xIndex) => {
      data.push([xIndex, yIndex, cellValue(row[tenor])]);
    });
  });

  const numericValues = data.map((item) => item[2]).filter((value): value is number => value != null);
  const min = numericValues.length ? Math.min(...numericValues) : 0;
  const max = numericValues.length ? Math.max(...numericValues) : 1;

  return {
    tooltip: buildMarketDataChartTooltip({
      position: "top",
      formatter(params: unknown) {
        const item = params as { data?: [number, number, number | null] };
        const tuple = item.data;
        if (!tuple) {
          return "";
        }
        const [xIndex, yIndex, value] = tuple;
        const label = yLabels[yIndex] ?? "";
        const tenor = TENORS[xIndex] ?? "";
        return `${label} · ${tenor}<br/>${value == null ? "—" : value.toFixed(3)}`;
      },
    }),
    grid: { left: 96, right: 54, top: 18, bottom: 28, containLabel: true },
    xAxis: {
      type: "category",
      data: [...TENORS],
      splitArea: { show: true, areaStyle: { color: ["#ffffff", "#f8fafc"] } },
      axisLabel: marketDataChartTheme.axisLabel,
      axisLine: marketDataChartTheme.axisLine,
      axisTick: { show: false },
    },
    yAxis: {
      type: "category",
      data: yLabels,
      splitArea: { show: true, areaStyle: { color: ["#ffffff", "#f8fafc"] } },
      axisLabel: marketDataChartTheme.axisLabel,
      axisLine: marketDataChartTheme.axisLine,
      axisTick: { show: false },
    },
    visualMap: {
      min,
      max: min === max ? min + 0.01 : max,
      calculable: false,
      orient: "vertical",
      right: 0,
      top: "center",
      inRange: { color: [...marketDataChartTheme.heatmapRange] },
      outOfRange: { color: marketDataChartTheme.heatmapEmptyColor },
      textStyle: marketDataChartTheme.axisLabel,
      itemWidth: 10,
      itemHeight: 96,
    },
    series: [
      {
        name: "NCD proxy",
        type: "heatmap",
        label: {
          show: true,
          formatter(params: unknown) {
            const value = (params as { data?: [number, number, number | null] }).data?.[2];
            return value == null ? "—" : value.toFixed(3);
          },
          fontSize: 10,
          color: "#17324d",
          fontWeight: 600,
        },
        itemStyle: {
          borderColor: "#ffffff",
          borderWidth: 1,
        },
        emphasis: {
          itemStyle: { borderColor: "#1850a1", borderWidth: 1, shadowBlur: 6, shadowColor: "rgba(24,80,161,0.14)" },
        },
        data,
      },
    ],
  };
}
