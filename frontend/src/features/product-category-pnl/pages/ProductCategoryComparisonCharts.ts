import type { EChartsOption } from "../../../lib/echarts";
import { designTokens, dhApiTokens } from "../../../theme/designSystem";
import { formatProductCategoryChartNumberTwoDecimals } from "./productCategoryPnlPageModel";

export const PRODUCT_CATEGORY_DARK_CHART_THEME = {
  canvas: "transparent",
  panel: dhApiTokens.color.panel2,
  ink: dhApiTokens.color.ink,
  muted: dhApiTokens.color.inkMuted,
  grid: "rgba(103,119,142,0.22)",
  border: "rgba(103,119,142,0.34)",
  blue: dhApiTokens.color.blue,
  green: dhApiTokens.color.green,
  amber: dhApiTokens.color.amber,
  red: dhApiTokens.color.red,
} as const;

function buildDarkChartTooltip(unit: string): EChartsOption["tooltip"] {
  return {
    trigger: "axis",
    formatter: buildAxisTooltipFormatter(unit),
    backgroundColor: PRODUCT_CATEGORY_DARK_CHART_THEME.panel,
    borderColor: PRODUCT_CATEGORY_DARK_CHART_THEME.border,
    borderWidth: 1,
    textStyle: {
      color: PRODUCT_CATEGORY_DARK_CHART_THEME.ink,
      fontFamily: designTokens.fontFamily.tabular,
      fontSize: 11,
    },
    confine: true,
  };
}

function buildDarkChartLegend(seriesNames: string[]): EChartsOption["legend"] {
  return {
    bottom: 0,
    data: seriesNames,
    itemWidth: 10,
    itemHeight: 8,
    textStyle: {
      color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
      fontFamily: designTokens.fontFamily.tabular,
      fontSize: 11,
    },
  };
}

function buildAxisLabelFormatter(unit = "") {
  return (value: unknown) =>
    `${formatProductCategoryChartNumberTwoDecimals(value)}${unit}`;
}

function buildAxisTooltipFormatter(unit: string) {
  return (params: unknown) => {
    const items = Array.isArray(params) ? params : [params];
    const axisLabel =
      (items[0] as { axisValueLabel?: string; name?: string } | undefined)
        ?.axisValueLabel ??
      (items[0] as { name?: string } | undefined)?.name ??
      "";
    const lines = items
      .map((item) => {
        const point = item as {
          marker?: string;
          seriesName?: string;
          value?: unknown;
        };
        return `${point.marker ?? ""}${point.seriesName ?? ""}: ${formatProductCategoryChartNumberTwoDecimals(point.value)}${unit}`;
      })
      .filter((line) => line.trim().length > 0);
    return [axisLabel, ...lines].filter(Boolean).join("<br/>");
  };
}

export function buildDualAxisChartOption(input: {
  labels: string[];
  leftAxisName: string;
  rightAxisName: string;
  series: Array<{
    name: string;
    type: "bar" | "line";
    data: number[];
    yAxisIndex: 0 | 1;
    color: string;
  }>;
}): EChartsOption | null {
  if (
    !input.labels.length ||
    input.series.every((series) => series.data.length === 0)
  ) {
    return null;
  }
  return {
    backgroundColor: PRODUCT_CATEGORY_DARK_CHART_THEME.canvas,
    tooltip: buildDarkChartTooltip(""),
    legend: buildDarkChartLegend(input.series.map((series) => series.name)),
    grid: {
      left: 56,
      right: 56,
      top: 20,
      bottom: input.labels.length > 6 ? 64 : 52,
    },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: {
        interval: 0,
        rotate: input.labels.length > 6 ? 24 : 0,
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
      },
      axisLine: {
        lineStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.border },
      },
    },
    yAxis: [
      {
        type: "value",
        name: input.leftAxisName,
        nameTextStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted },
        axisLabel: {
          formatter: buildAxisLabelFormatter(),
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
        },
        splitLine: {
          lineStyle: {
            type: "dashed",
            color: PRODUCT_CATEGORY_DARK_CHART_THEME.grid,
          },
        },
      },
      {
        type: "value",
        name: input.rightAxisName,
        nameTextStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted },
        axisLabel: {
          formatter: buildAxisLabelFormatter(),
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
        },
        splitLine: { show: false },
      },
    ],
    series: input.series.map((series) => ({
      name: series.name,
      type: series.type,
      yAxisIndex: series.yAxisIndex,
      data: series.data,
      smooth: series.type === "line",
      itemStyle: { color: series.color },
      lineStyle: {
        color: series.color,
        width: series.type === "line" ? 3 : undefined,
      },
      barMaxWidth: series.type === "bar" ? 26 : undefined,
    })),
  };
}

export function buildSingleAxisChartOption(input: {
  labels: string[];
  axisName: string;
  series: Array<{
    name: string;
    type: "bar" | "line";
    data: number[];
    color: string;
  }>;
}): EChartsOption | null {
  if (
    !input.labels.length ||
    input.series.every((series) => series.data.length === 0)
  ) {
    return null;
  }
  return {
    backgroundColor: PRODUCT_CATEGORY_DARK_CHART_THEME.canvas,
    tooltip: buildDarkChartTooltip(""),
    legend: buildDarkChartLegend(input.series.map((series) => series.name)),
    grid: {
      left: 56,
      right: 24,
      top: 20,
      bottom: input.labels.length > 6 ? 64 : 52,
    },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: {
        interval: 0,
        rotate: input.labels.length > 6 ? 24 : 0,
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
      },
      axisLine: {
        lineStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.border },
      },
    },
    yAxis: {
      type: "value",
      name: input.axisName,
      nameTextStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted },
      axisLabel: {
        formatter: buildAxisLabelFormatter(),
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
      },
      splitLine: {
        lineStyle: {
          type: "dashed",
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.grid,
        },
      },
    },
    series: input.series.map((series) => ({
      name: series.name,
      type: series.type,
      data: series.data,
      smooth: series.type === "line",
      itemStyle: { color: series.color },
      lineStyle: {
        color: series.color,
        width: series.type === "line" ? 3 : undefined,
      },
      barMaxWidth: series.type === "bar" ? 26 : undefined,
    })),
  };
}

export function buildInterestEarningAssetLiabilityScaleChartOption(input: {
  labels: string[];
  series: Array<{
    name: string;
    data: number[];
    color: string;
    borderColor: string;
  }>;
}): EChartsOption | null {
  if (
    !input.labels.length ||
    input.series.every((series) => series.data.length === 0)
  ) {
    return null;
  }
  return {
    backgroundColor: PRODUCT_CATEGORY_DARK_CHART_THEME.canvas,
    tooltip: {
      ...buildDarkChartTooltip("亿元"),
      borderWidth: 1,
      axisPointer: {
        type: "shadow",
        shadowStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.grid },
      },
    },
    legend: {
      top: 4,
      right: 8,
      data: input.series.map((series) => series.name),
      itemWidth: 10,
      itemHeight: 10,
      textStyle: {
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
        fontSize: 11,
      },
    },
    grid: { left: 18, right: 16, top: 46, bottom: 18, containLabel: true },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: {
        interval: 0,
        rotate: input.labels.length > 6 ? 24 : 0,
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
        fontFamily: designTokens.fontFamily.tabular,
        fontSize: 11,
      },
      axisLine: {
        lineStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.border },
      },
    },
    yAxis: {
      type: "value",
      name: "亿元",
      scale: true,
      splitNumber: 4,
      nameTextStyle: {
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
        fontSize: 11,
        padding: [0, 0, 0, -18],
      },
      axisLabel: {
        formatter: buildAxisLabelFormatter(),
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
        fontFamily: designTokens.fontFamily.tabular,
        fontSize: 11,
      },
      splitLine: {
        lineStyle: {
          type: "solid",
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.grid,
        },
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: input.series.map((series, index) => ({
      name: series.name,
      type: "bar",
      data: series.data,
      barMaxWidth: 12,
      barGap: index === 0 ? "36%" : undefined,
      barMinHeight: 2,
      itemStyle: {
        color: series.color,
        borderColor: series.borderColor,
        borderWidth: 1,
        borderRadius: [2, 2, 0, 0],
      },
      emphasis: {
        focus: "series",
        itemStyle: {
          opacity: 0.92,
        },
      },
    })),
  };
}

export function buildInterestSpreadChartOption(input: {
  labels: string[];
  series: Array<{
    name: string;
    data: Array<number | null>;
    color: string;
  }>;
}): EChartsOption | null {
  const values = input.series
    .flatMap((series) => series.data)
    .filter(
      (value): value is number =>
        typeof value === "number" && Number.isFinite(value),
    );
  if (!input.labels.length || values.length === 0) {
    return null;
  }
  const minValue = values.length ? Math.min(...values) : 0;
  const maxValue = values.length ? Math.max(...values) : 0;
  const range = maxValue - minValue;
  const padding = Math.max(
    range * 0.12,
    Math.abs(maxValue || minValue) * 0.08,
    0.1,
  );
  const yAxisMin = Number((minValue - padding).toFixed(2));
  const yAxisMax = Number((maxValue + padding).toFixed(2));
  const lineWidths = [4, 3.4, 4];
  const symbolSizes = [8, 7, 8];
  return {
    backgroundColor: PRODUCT_CATEGORY_DARK_CHART_THEME.canvas,
    tooltip: buildDarkChartTooltip("%"),
    legend: buildDarkChartLegend(input.series.map((series) => series.name)),
    grid: {
      left: 56,
      right: 72,
      top: 20,
      bottom: input.labels.length > 6 ? 64 : 52,
    },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: {
        interval: 0,
        rotate: input.labels.length > 6 ? 24 : 0,
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
      },
      axisLine: {
        lineStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.border },
      },
    },
    yAxis: {
      type: "value",
      name: "%",
      min: yAxisMin,
      max: yAxisMax,
      scale: true,
      nameTextStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted },
      axisLabel: {
        formatter: buildAxisLabelFormatter("%"),
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
      },
      splitLine: {
        lineStyle: {
          type: "dashed",
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.grid,
        },
      },
    },
    series: input.series.map((series, index) => ({
      name: series.name,
      type: "line",
      data: series.data,
      smooth: true,
      showSymbol: true,
      symbol: "circle",
      symbolSize: symbolSizes[index] ?? 7,
      itemStyle: {
        color: series.color,
        borderColor: PRODUCT_CATEGORY_DARK_CHART_THEME.panel,
        borderWidth: 2,
      },
      lineStyle: { color: series.color, width: lineWidths[index] ?? 3.4 },
      endLabel: {
        show: true,
        color: series.color,
        formatter: (params: { value?: unknown }) =>
          `${formatProductCategoryChartNumberTwoDecimals(params.value)}%`,
        fontWeight: 700,
      },
      labelLayout: { moveOverlap: "shiftY" },
      emphasis: { focus: "series" },
    })),
  };
}

function latestComparableDataIndex(
  series: Array<{ data: Array<number | null> }>,
): number | null {
  if (series.length < 2) {
    return null;
  }
  const prior = series[series.length - 2]?.data ?? [];
  const current = series[series.length - 1]?.data ?? [];
  for (
    let index = Math.min(prior.length, current.length) - 1;
    index >= 0;
    index -= 1
  ) {
    if (
      typeof prior[index] === "number" &&
      Number.isFinite(prior[index]) &&
      typeof current[index] === "number" &&
      Number.isFinite(current[index])
    ) {
      return index;
    }
  }
  return null;
}

function latestFiniteDataIndex(data: Array<number | null>): number | null {
  for (let index = data.length - 1; index >= 0; index -= 1) {
    if (typeof data[index] === "number" && Number.isFinite(data[index])) {
      return index;
    }
  }
  return null;
}

export type ProductCategoryComparisonReadout = {
  monthLabel: string;
  priorPeriodLabel: string;
  priorValueLabel: string;
  currentPeriodLabel: string;
  currentValueLabel: string;
  deltaLabel: string;
  deltaTone: "positive" | "negative" | "neutral";
};

export function buildProductCategoryComparisonReadout(input: {
  labels: string[] | undefined;
  series:
    | Array<{
        year: string;
        data: Array<number | null>;
      }>
    | undefined;
  valueUnit: "%" | "亿元";
  deltaUnit: "bp" | "亿元";
  deltaScale: number;
}): ProductCategoryComparisonReadout | null {
  if (!input.labels || !input.series || input.series.length < 2) {
    return null;
  }
  const comparableIndex = latestComparableDataIndex(input.series);
  if (comparableIndex === null) {
    return null;
  }
  const prior = input.series[input.series.length - 2];
  const current = input.series[input.series.length - 1];
  const priorValue = prior?.data[comparableIndex];
  const currentValue = current?.data[comparableIndex];
  if (
    typeof priorValue !== "number" ||
    !Number.isFinite(priorValue) ||
    typeof currentValue !== "number" ||
    !Number.isFinite(currentValue)
  ) {
    return null;
  }
  const delta = (currentValue - priorValue) * input.deltaScale;
  const signedDelta = `${delta > 0 ? "+" : ""}${formatProductCategoryChartNumberTwoDecimals(delta)} ${input.deltaUnit}`;
  return {
    monthLabel: input.labels[comparableIndex] ?? "最新可比月",
    priorPeriodLabel: prior?.year ?? "上年",
    priorValueLabel: `${formatProductCategoryChartNumberTwoDecimals(priorValue)}${input.valueUnit}`,
    currentPeriodLabel: current?.year ?? "当前年",
    currentValueLabel: `${formatProductCategoryChartNumberTwoDecimals(currentValue)}${input.valueUnit}`,
    deltaLabel: signedDelta,
    deltaTone: delta > 0 ? "positive" : delta < 0 ? "negative" : "neutral",
  };
}

export function countProductCategoryComparableReportMonths(
  snapshots: Array<{ reportDate: string }>,
  currentYear: number,
): number {
  const currentMonths = new Set<number>();
  const priorMonths = new Set<number>();
  snapshots.forEach((snapshot) => {
    const match = /^(\d{4})-(\d{2})/.exec(snapshot.reportDate);
    if (!match) {
      return;
    }
    const year = Number(match[1]);
    const month = Number(match[2]);
    if (!Number.isInteger(month) || month < 1 || month > 12) {
      return;
    }
    if (year === currentYear) {
      currentMonths.add(month);
    } else if (year === currentYear - 1) {
      priorMonths.add(month);
    }
  });
  return Array.from(currentMonths).filter((month) => priorMonths.has(month))
    .length;
}

export function buildInterestSpreadYearComparisonChartOption(input: {
  labels: string[];
  currentSeriesName: string | null;
  series: Array<{
    name: string;
    data: Array<number | null>;
    color: string;
  }>;
}): EChartsOption | null {
  const values = input.series
    .flatMap((series) => series.data)
    .filter(
      (value): value is number =>
        typeof value === "number" && Number.isFinite(value),
    );
  if (!input.labels.length || values.length === 0) {
    return null;
  }
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue;
  const padding = Math.max(range * 0.12, 0.03);
  const yAxisMin = Number((minValue - padding).toFixed(2));
  const yAxisMax = Number((maxValue + padding).toFixed(2));
  const currentSeriesIndex = input.currentSeriesName
    ? input.series.findIndex(
        (series) => series.name === input.currentSeriesName,
      )
    : -1;
  const priorSeriesIndex = input.series.reduce(
    (lastIndex, _, index) => (index !== currentSeriesIndex ? index : lastIndex),
    -1,
  );
  const currentSeries =
    currentSeriesIndex >= 0 ? input.series[currentSeriesIndex] : undefined;
  const priorSeries =
    priorSeriesIndex >= 0 ? input.series[priorSeriesIndex] : undefined;
  const currentCutoffIndex = latestFiniteDataIndex(currentSeries?.data ?? []);
  const referenceStartIndex =
    currentCutoffIndex !== null && currentCutoffIndex + 1 < input.labels.length
      ? currentCutoffIndex + 1
      : null;
  const deltaSeriesName = "同比差（bp）";
  const deltaData = input.labels.map((_, index) => {
    const priorValue = priorSeries?.data[index];
    const currentValue = currentSeries?.data[index];
    if (
      typeof priorValue !== "number" ||
      !Number.isFinite(priorValue) ||
      typeof currentValue !== "number" ||
      !Number.isFinite(currentValue)
    ) {
      return null;
    }
    return Number(((currentValue - priorValue) * 100).toFixed(2));
  });
  const deltaValues = deltaData.filter(
    (value): value is number =>
      typeof value === "number" && Number.isFinite(value),
  );
  const deltaMinValue =
    deltaValues.length > 0 ? Math.min(0, ...deltaValues) : 0;
  const deltaMaxValue =
    deltaValues.length > 0 ? Math.max(0, ...deltaValues) : 0;
  const deltaRange = deltaMaxValue - deltaMinValue;
  const deltaPadding = Math.max(deltaRange * 0.12, 1);
  const deltaAxisMin =
    deltaMinValue < 0 ? Number((deltaMinValue - deltaPadding).toFixed(1)) : -1;
  const deltaAxisMax =
    deltaMaxValue > 0
      ? Number((deltaMaxValue + deltaPadding).toFixed(1))
      : Math.max(1, Number(deltaPadding.toFixed(1)));
  const hasComparisonSeries = Boolean(priorSeries && currentSeries);
  const legendNames = [
    ...(priorSeries ? [priorSeries.name] : []),
    ...(currentSeries ? [currentSeries.name] : []),
    ...(hasComparisonSeries ? [deltaSeriesName] : []),
  ];
  const chartSeries: Array<Record<string, unknown>> = [];

  if (priorSeries) {
    const comparablePriorData =
      referenceStartIndex === null
        ? priorSeries.data
        : priorSeries.data.map((value, index) =>
            currentCutoffIndex !== null && index <= currentCutoffIndex
              ? value
              : null,
          );
    chartSeries.push({
      name: priorSeries.name,
      type: "line",
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: comparablePriorData,
      smooth: 0.16,
      connectNulls: false,
      showSymbol: true,
      symbol: "circle",
      symbolSize: 7,
      itemStyle: {
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.panel,
        borderColor: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
        borderWidth: 2,
      },
      lineStyle: {
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
        width: 2,
        type: "dashed",
      },
      label: { show: false },
      endLabel: { show: false },
      emphasis: { focus: "series" },
    });
  }

  if (
    priorSeries &&
    referenceStartIndex !== null &&
    currentCutoffIndex !== null
  ) {
    chartSeries.push({
      name: `${priorSeries.name} · 上年参考`,
      type: "line",
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: priorSeries.data.map((value, index) =>
        index >= referenceStartIndex ? value : null,
      ),
      smooth: 0.16,
      connectNulls: false,
      showSymbol: false,
      silent: true,
      tooltip: { show: false },
      lineStyle: {
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
        width: 1.4,
        type: "dotted",
        opacity: 0.52,
      },
      markArea: {
        silent: true,
        itemStyle: { color: "rgba(133,147,168,0.055)" },
        label: {
          show: true,
          formatter: `上年参考 ${input.labels[referenceStartIndex]}–${input.labels[input.labels.length - 1]}`,
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
          fontSize: 11,
          position: "insideTop",
        },
        data: [
          [
            { xAxis: input.labels[referenceStartIndex] },
            { xAxis: input.labels[input.labels.length - 1] },
          ],
        ],
      },
      emphasis: { disabled: true },
    });
  }

  if (currentSeries) {
    chartSeries.push({
      name: currentSeries.name,
      type: "line",
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: currentSeries.data,
      smooth: 0.16,
      connectNulls: false,
      showSymbol: true,
      symbol: "circle",
      symbolSize: 8,
      itemStyle: {
        color: currentSeries.color,
        borderColor: currentSeries.color,
        borderWidth: 1,
      },
      lineStyle: {
        color: currentSeries.color,
        width: 3,
        type: "solid",
      },
      label: { show: false },
      endLabel: { show: false },
      emphasis: { focus: "series" },
      z: 3,
    });
  }

  if (hasComparisonSeries) {
    chartSeries.push({
      name: deltaSeriesName,
      type: "bar",
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: deltaData.map((value) =>
        value === null
          ? null
          : {
              value,
              itemStyle: {
                color:
                  value > 0
                    ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                    : value < 0
                      ? PRODUCT_CATEGORY_DARK_CHART_THEME.amber
                      : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
                borderColor:
                  value > 0
                    ? PRODUCT_CATEGORY_DARK_CHART_THEME.green
                    : value < 0
                      ? PRODUCT_CATEGORY_DARK_CHART_THEME.amber
                      : PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
                borderWidth: 1,
                borderRadius: [2, 2, 2, 2],
                opacity: 0.92,
              },
            },
      ),
      barMaxWidth: 14,
      barMinHeight: 2,
      itemStyle: {
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.amber,
      },
      markLine: {
        silent: true,
        symbol: "none",
        lineStyle: {
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.border,
          type: "solid",
          width: 1,
        },
        label: { show: false },
        data: [{ yAxis: 0 }],
      },
      emphasis: { focus: "series" },
      z: 2,
    });
  }

  return {
    backgroundColor: PRODUCT_CATEGORY_DARK_CHART_THEME.canvas,
    tooltip: {
      ...buildDarkChartTooltip(""),
      formatter: (params: unknown) => {
        const items = (Array.isArray(params) ? params : [params]).filter(
          Boolean,
        );
        const axisLabel =
          (items[0] as { axisValueLabel?: string; name?: string } | undefined)
            ?.axisValueLabel ??
          (items[0] as { name?: string } | undefined)?.name ??
          "";
        const lines = items
          .map((item) => {
            const point = item as {
              marker?: string;
              seriesName?: string;
              value?: unknown;
            };
            if (
              point.seriesName?.endsWith("· 上年参考") ||
              point.value === null ||
              point.value === undefined
            ) {
              return null;
            }
            const numericValue = Number(point.value);
            if (!Number.isFinite(numericValue)) {
              return null;
            }
            const isDelta = point.seriesName === deltaSeriesName;
            const sign = isDelta && numericValue > 0 ? "+" : "";
            return `${point.marker ?? ""}${point.seriesName ?? ""}: ${sign}${formatProductCategoryChartNumberTwoDecimals(numericValue)}${isDelta ? "bp" : "%"}`;
          })
          .filter((line): line is string => Boolean(line));
        return [axisLabel, ...lines].join("<br/>");
      },
    },
    legend: buildDarkChartLegend(legendNames),
    grid: [
      { left: 56, right: 28, top: 18, height: 92 },
      { left: 56, right: 28, top: 132, height: 36 },
    ],
    xAxis: [
      {
        type: "category",
        gridIndex: 0,
        data: input.labels,
        boundaryGap: false,
        axisTick: { show: false },
        axisLabel: { show: false },
        axisLine: {
          lineStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.border },
        },
      },
      {
        type: "category",
        gridIndex: 1,
        data: input.labels,
        boundaryGap: false,
        axisTick: { show: false },
        axisLabel: {
          interval: 0,
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
          formatter: (value: string, index: number) =>
            [0, 2, 5, 8, 11].includes(index) ? value : "",
        },
        axisLine: {
          lineStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.border },
        },
      },
    ],
    yAxis: [
      {
        type: "value",
        gridIndex: 0,
        name: "利差（%）",
        min: yAxisMin,
        max: yAxisMax,
        scale: true,
        nameGap: 8,
        nameTextStyle: {
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
          fontSize: 11,
        },
        axisLabel: {
          formatter: buildAxisLabelFormatter("%"),
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
          fontSize: 11,
        },
        splitLine: {
          lineStyle: {
            type: "solid",
            color: PRODUCT_CATEGORY_DARK_CHART_THEME.grid,
          },
        },
      },
      {
        type: "value",
        gridIndex: 1,
        name: "同比差（bp）",
        min: deltaAxisMin,
        max: deltaAxisMax,
        scale: true,
        nameGap: 8,
        nameTextStyle: {
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
          fontSize: 11,
        },
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: { show: false },
        splitNumber: 2,
        splitLine: { show: false },
      },
    ],
    series: chartSeries as EChartsOption["series"],
  };
}

export function buildIncomeYearComparisonChartOption(input: {
  labels: string[];
  currentSeriesName: string | null;
  series: Array<{
    name: string;
    data: Array<number | null>;
    color: string;
  }>;
}): EChartsOption | null {
  const values = input.series
    .flatMap((series) => series.data)
    .filter(
      (value): value is number =>
        typeof value === "number" && Number.isFinite(value),
    );
  if (!input.labels.length || values.length === 0) {
    return null;
  }
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const domainMin = Math.min(0, minValue);
  const domainMax = Math.max(0, maxValue);
  const range = domainMax - domainMin;
  const padding = Math.max(range * 0.18, 0.02);
  const yAxisMin = domainMin < 0 ? Number((domainMin - padding).toFixed(2)) : 0;
  const yAxisMax = Number((domainMax + padding).toFixed(2));
  const currentSeriesIndex = input.currentSeriesName
    ? input.series.findIndex(
        (series) => series.name === input.currentSeriesName,
      )
    : -1;
  const priorSeriesIndex = input.series.reduce(
    (lastIndex, _, index) => (index !== currentSeriesIndex ? index : lastIndex),
    -1,
  );
  const comparableIndex = latestComparableDataIndex(input.series);
  const currentCutoffIndex = latestFiniteDataIndex(
    currentSeriesIndex >= 0
      ? (input.series[currentSeriesIndex]?.data ?? [])
      : [],
  );
  const referenceStartIndex =
    currentCutoffIndex !== null && currentCutoffIndex + 1 < input.labels.length
      ? currentCutoffIndex + 1
      : null;
  return {
    backgroundColor: PRODUCT_CATEGORY_DARK_CHART_THEME.canvas,
    tooltip: buildDarkChartTooltip("亿元"),
    legend: buildDarkChartLegend(input.series.map((series) => series.name)),
    grid: { left: 56, right: 28, top: 20, bottom: 58 },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: {
        interval: 0,
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
      },
      axisLine: {
        lineStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.border },
      },
    },
    yAxis: {
      type: "value",
      name: "亿元",
      min: yAxisMin,
      max: yAxisMax,
      scale: true,
      nameTextStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted },
      axisLabel: {
        formatter: buildAxisLabelFormatter(),
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
      },
      splitLine: {
        lineStyle: {
          type: "solid",
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.grid,
        },
      },
    },
    series: input.series.map((series, index) => {
      const isPrior = index === priorSeriesIndex;
      const isCurrent = index === currentSeriesIndex;
      const seriesColor = isPrior
        ? PRODUCT_CATEGORY_DARK_CHART_THEME.muted
        : series.color;
      return {
        name: series.name,
        type: "bar",
        data: series.data,
        barMaxWidth: 24,
        barGap: "18%",
        barCategoryGap: "38%",
        itemStyle: {
          color: seriesColor,
          opacity: isPrior ? 0.58 : 0.9,
          borderColor: seriesColor,
          borderWidth: isPrior ? 1 : 0,
          borderRadius: [2, 2, 0, 0],
        },
        label: {
          show: comparableIndex !== null,
          formatter: (params: { dataIndex?: number; value?: unknown }) =>
            params.dataIndex === comparableIndex
              ? formatProductCategoryChartNumberTwoDecimals(params.value)
              : "",
          color: seriesColor,
          position: "top",
          distance: 4,
          fontWeight: isCurrent ? 700 : 500,
        },
        markLine: isCurrent
          ? {
              silent: true,
              symbol: "none",
              lineStyle: {
                color: PRODUCT_CATEGORY_DARK_CHART_THEME.border,
                width: 1,
              },
              label: { show: false },
              data: [
                { yAxis: 0 },
                ...(currentCutoffIndex !== null
                  ? [
                      {
                        xAxis: input.labels[currentCutoffIndex],
                        label: {
                          show: true,
                          formatter: `截至 ${input.labels[currentCutoffIndex] ?? ""}`,
                          color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
                          fontSize: 11,
                          position: "insideEndTop" as const,
                        },
                        lineStyle: { type: "dashed" as const },
                      },
                    ]
                  : []),
              ],
            }
          : undefined,
        markArea:
          isPrior && referenceStartIndex !== null
            ? {
                silent: true,
                itemStyle: { color: "rgba(133,147,168,0.07)" },
                label: {
                  show: true,
                  formatter: "上年参考区",
                  color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
                  fontSize: 11,
                  position: "insideTop",
                },
                data: [
                  [
                    { xAxis: input.labels[referenceStartIndex] },
                    { xAxis: input.labels[input.labels.length - 1] },
                  ],
                ],
              }
            : undefined,
        emphasis: { focus: "series" },
      };
    }),
  };
}

export function buildLiabilitySideTrendChartOption(input: {
  labels: string[];
  averageDaily: Array<number | null>;
  rate: Array<number | null>;
}): EChartsOption | null {
  if (!input.labels.length) {
    return null;
  }
  const finiteAverageDaily = input.averageDaily.filter(
    (value): value is number =>
      typeof value === "number" && Number.isFinite(value),
  );
  const leftAxisRange =
    finiteAverageDaily.length > 0
      ? (() => {
          const minValue = Math.min(...finiteAverageDaily);
          const maxValue = Math.max(...finiteAverageDaily);
          const span = Math.max(
            maxValue - minValue,
            Math.max(Math.abs(minValue), Math.abs(maxValue)) * 0.08,
            1,
          );
          const padding = span * 0.08;
          return {
            min: Number(Math.min(0, minValue - padding).toFixed(2)),
            max: Number(Math.max(0, maxValue + padding).toFixed(2)),
          };
        })()
      : undefined;
  return {
    backgroundColor: PRODUCT_CATEGORY_DARK_CHART_THEME.canvas,
    tooltip: buildDarkChartTooltip(""),
    legend: buildDarkChartLegend(["负债端日均额（亿元）", "负债端利率（%）"]),
    grid: {
      left: 56,
      right: 64,
      top: 20,
      bottom: input.labels.length > 6 ? 64 : 52,
    },
    xAxis: {
      type: "category",
      data: input.labels,
      axisTick: { show: false },
      axisLabel: {
        interval: 0,
        rotate: input.labels.length > 6 ? 24 : 0,
        color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
      },
      axisLine: {
        onZero: false,
        lineStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.border },
      },
    },
    yAxis: [
      {
        type: "value",
        name: "亿元",
        min: leftAxisRange?.min,
        max: leftAxisRange?.max,
        nameTextStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted },
        axisLabel: {
          formatter: buildAxisLabelFormatter(),
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted,
        },
        splitLine: {
          lineStyle: {
            type: "dashed",
            color: PRODUCT_CATEGORY_DARK_CHART_THEME.grid,
          },
        },
      },
      {
        type: "value",
        name: "%",
        scale: true,
        nameTextStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted },
        axisLabel: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.muted },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "负债端日均额（亿元）",
        type: "bar",
        yAxisIndex: 0,
        data: input.averageDaily,
        itemStyle: { color: PRODUCT_CATEGORY_DARK_CHART_THEME.blue },
        barMaxWidth: 28,
      },
      {
        name: "负债端利率（%）",
        type: "line",
        yAxisIndex: 1,
        data: input.rate,
        smooth: true,
        showSymbol: true,
        symbol: "circle",
        symbolSize: 7,
        itemStyle: {
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.amber,
          borderColor: PRODUCT_CATEGORY_DARK_CHART_THEME.panel,
          borderWidth: 2,
        },
        lineStyle: {
          color: PRODUCT_CATEGORY_DARK_CHART_THEME.amber,
          width: 3.4,
        },
        emphasis: { focus: "series" },
      },
    ],
  };
}

