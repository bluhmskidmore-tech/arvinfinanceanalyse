import type { NcdFundingProxyPayload } from "../../../../api/contracts";
import type { EChartsOption } from "../../../../lib/echarts";
import { nocturneTokens } from "../../../../theme/designSystem";
import { EM_DASH } from "../../../../utils/format";
import { buildMarketDataChartTooltip, marketDataChartTheme } from "./marketDataChartTheme";

const TENORS = ["1M", "3M", "6M", "9M", "1Y"] as const;

/** 色阶高于该分位的格子已接近 accent 亮底，数值 label 翻成页面深底色保证对比度。 */
const LABEL_FLIP_RATIO = 0.55;

type HeatmapCellItem = {
  value: [number, number, number | null];
  label?: { color: string };
};

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

function tupleFromParams(params: unknown): [number, number, number | null] | undefined {
  const value = (params as { value?: unknown }).value;
  return Array.isArray(value) ? (value as [number, number, number | null]) : undefined;
}

export function buildNcdProxyHeatmapOption(
  payload: Pick<NcdFundingProxyPayload, "rows"> | undefined,
): EChartsOption | null {
  const rows = payload?.rows ?? [];
  if (rows.length === 0) {
    return null;
  }

  const yLabels = rows.map((row) => row.label);
  const cells: Array<[number, number, number | null]> = [];

  rows.forEach((row, yIndex) => {
    TENORS.forEach((tenor, xIndex) => {
      cells.push([xIndex, yIndex, cellValue(row[tenor])]);
    });
  });

  const numericValues = cells.map((item) => item[2]).filter((value): value is number => value != null);
  const min = numericValues.length ? Math.min(...numericValues) : 0;
  const max = numericValues.length ? Math.max(...numericValues) : 1;
  const span = max - min;

  const data: HeatmapCellItem[] = cells.map((value) =>
    span > 0 && value[2] != null && value[2] >= min + span * LABEL_FLIP_RATIO
      ? { value, label: { color: nocturneTokens.color.bg } }
      : { value },
  );

  const splitAreaDark = {
    show: true,
    areaStyle: { color: [nocturneTokens.color.panel2] },
  };

  return {
    tooltip: buildMarketDataChartTooltip({
      position: "top",
      formatter(params: unknown) {
        const tuple = tupleFromParams(params);
        if (!tuple) {
          return "";
        }
        const [xIndex, yIndex, value] = tuple;
        const label = yLabels[yIndex] ?? "";
        const tenor = TENORS[xIndex] ?? "";
        return `${label} · ${tenor}<br/>${value == null ? EM_DASH : value.toFixed(3)}`;
      },
    }),
    grid: { left: 96, right: 12, top: 18, bottom: 28, containLabel: true },
    xAxis: {
      type: "category",
      data: [...TENORS],
      splitArea: splitAreaDark,
      axisLabel: marketDataChartTheme.axisLabel,
      axisLine: marketDataChartTheme.axisLine,
      axisTick: { show: false },
    },
    yAxis: {
      type: "category",
      data: yLabels,
      splitArea: splitAreaDark,
      axisLabel: marketDataChartTheme.axisLabel,
      axisLine: marketDataChartTheme.axisLine,
      axisTick: { show: false },
    },
    // 色条隐藏：tooltip 与格内数值已提供读数，右侧留白还给矩阵本体。
    visualMap: {
      show: false,
      min,
      max: min === max ? min + 0.01 : max,
      inRange: { color: [...marketDataChartTheme.heatmapRange] },
      outOfRange: { color: marketDataChartTheme.heatmapEmptyColor },
    },
    series: [
      {
        name: "NCD proxy",
        type: "heatmap",
        label: {
          show: true,
          formatter(params: unknown) {
            const value = tupleFromParams(params)?.[2];
            return value == null ? EM_DASH : value.toFixed(3);
          },
          fontSize: 10,
          color: nocturneTokens.color.inkSoft,
          fontWeight: 600,
        },
        itemStyle: {
          borderColor: nocturneTokens.color.line,
          borderWidth: 1,
        },
        emphasis: {
          itemStyle: {
            borderColor: nocturneTokens.color.blue,
            borderWidth: 1,
            shadowBlur: 6,
            shadowColor: nocturneTokens.color.blueSoft,
          },
        },
        data,
      },
    ],
  };
}
