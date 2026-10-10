import type { ChoiceMacroLatestPoint, ChoiceMacroRecentPoint } from "../../../../api/contracts";
import { nocturneChartTheme } from "../../../../components/charts/chartTheme";
import type { EChartsOption } from "../../../../lib/echarts";
import { EM_DASH } from "../../../../utils/format";
import { seriesDisplayName } from "../marketDataFormat";
import { buildMarketDataChartTooltip, marketDataChartTheme } from "./marketDataChartTheme";

/*
 * 市场数据页是 Nocturne scope（DESIGN 结论 8/12）：基底改走 nocturneChartTheme，原先用的
 * 共享别名 createLineChartOption 是 IB 浅色默认，未被 marketDataChartTheme 覆盖的字段
 * （全局 textStyle、tooltip 底色等）会以浅色 ink 落进深色画布。
 */
const { createLineChartOption } = nocturneChartTheme;

export type MarketDataSeriesTimeInput = Pick<
  ChoiceMacroLatestPoint,
  "series_id" | "series_name" | "display_name" | "unit" | "recent_points" | "quality_flag"
>;

/** 多系列时默认点亮的主系列数量；其余进图例（legend.selected=false），可点开关。 */
export const MARKET_DATA_MULTI_SERIES_DEFAULT_VISIBLE = 4;

function sortedRecentPoints(points: ChoiceMacroRecentPoint[] | undefined): ChoiceMacroRecentPoint[] {
  return [...(points ?? [])].sort((left, right) => left.trade_date.localeCompare(right.trade_date));
}

function formatAxisMagnitude(scaled: number): string {
  const rounded = Math.round(scaled * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

/** y 轴大数缩写：≥1e8 → 亿、≥1e4 → 万（保留 1 位小数，整数不带小数位），小数值原样。 */
function formatMarketDataAxisValue(value: number): string {
  if (!Number.isFinite(value)) {
    return "";
  }
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e8) {
    return `${sign}${formatAxisMagnitude(abs / 1e8)}亿`;
  }
  if (abs >= 1e4) {
    return `${sign}${formatAxisMagnitude(abs / 1e4)}万`;
  }
  return String(value);
}

/** 日期标签 MM-DD；时间轴跨年时，起点及每次跨年处补 YYYY-MM 标出年份切换。 */
function buildDateAxisLabelFormatter(categories: readonly string[]) {
  const spansMultipleYears = new Set(categories.map((date) => date.slice(0, 4))).size > 1;
  return (value: string, index: number): string => {
    if (!spansMultipleYears) {
      return value.slice(5);
    }
    const previousYear = index > 0 ? categories[index - 1]?.slice(0, 4) : undefined;
    return previousYear === value.slice(0, 4) ? value.slice(5) : value.slice(0, 7);
  };
}

function buildDateCategoryAxis(categories: string[], axisLabel: object) {
  return {
    type: "category" as const,
    boundaryGap: false,
    data: categories,
    axisTick: { show: false },
    axisLine: marketDataChartTheme.axisLine,
    axisLabel: {
      ...axisLabel,
      interval: "auto" as const,
      hideOverlap: true,
      formatter: buildDateAxisLabelFormatter(categories),
    },
  };
}

function buildCompactValueAxis(
  axisLabel: object,
  options: {
    unitName?: string;
    splitNumber?: number;
    position?: "left" | "right";
    showSplitLine?: boolean;
  } = {},
) {
  return {
    type: "value" as const,
    scale: true,
    ...(options.position ? { position: options.position } : {}),
    ...(options.unitName !== undefined
      ? {
          name: options.unitName,
          nameTextStyle: {
            color: marketDataChartTheme.axisLabel.color,
            fontFamily: marketDataChartTheme.axisLabel.fontFamily,
            fontSize: 11,
          },
        }
      : {}),
    splitNumber: options.splitNumber ?? 4,
    axisLabel: { ...axisLabel, formatter: formatMarketDataAxisValue },
    // 双轴时次轴不画分割线，避免两套网格线互相干扰。
    splitLine: options.showSplitLine === false ? { show: false as const } : marketDataChartTheme.splitLine,
  };
}

function buildSoftAreaGradient(color: string) {
  return {
    color: {
      type: "linear" as const,
      x: 0,
      y: 0,
      x2: 0,
      y2: 1,
      colorStops: [
        { offset: 0, color: `${color}22` },
        { offset: 1, color: `${color}00` },
      ],
    },
  };
}

type MarketDataSeriesTimeChartVariant = "default" | "sheet";

export function buildMarketDataSeriesTimeChartOption(
  series: MarketDataSeriesTimeInput,
  options: { variant?: MarketDataSeriesTimeChartVariant } = {},
): EChartsOption | null {
  const timeline = sortedRecentPoints(series.recent_points);
  if (timeline.length === 0) {
    return null;
  }

  const isSheetVariant = options.variant === "sheet";
  const categories = timeline.map((point) => point.trade_date);
  const values = timeline.map((point) => point.value_numeric != null && Number.isFinite(point.value_numeric) ? point.value_numeric : null);
  const unit = displayAxisUnit(series.unit) || undefined;
  const axisLabel = isSheetVariant
    ? { ...marketDataChartTheme.axisLabel, fontSize: 10, fontWeight: 600 }
    : marketDataChartTheme.axisLabel;
  const lineColor = marketDataChartTheme.multiSeriesPalette[0]!;

  return createLineChartOption({
    color: [lineColor],
    tooltip: buildMarketDataChartTooltip({
      trigger: "axis",
      axisPointer: marketDataChartTheme.axisPointerLine,
    }),
    legend: undefined,
    grid: isSheetVariant
      ? { left: 8, right: 12, top: 10 }
      : { left: 8, right: 12, top: 32 },
    xAxis: buildDateCategoryAxis(categories, axisLabel),
    yAxis: buildCompactValueAxis(axisLabel, {
      unitName: isSheetVariant ? "" : unit,
      splitNumber: isSheetVariant ? 3 : 4,
    }),
    series: [
      {
        name: seriesDisplayName(series),
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: isSheetVariant ? 4 : 5,
        showSymbol: false,
        connectNulls: !values.some((value) => value == null),
        lineStyle: { width: isSheetVariant ? 1.5 : 2 },
        itemStyle: { borderColor: marketDataChartTheme.chartSurface, borderWidth: 1.2 },
        areaStyle: isSheetVariant ? undefined : buildSoftAreaGradient(lineColor),
        data: values,
      },
    ],
  });
}

/** 同 unit 序列共轴时允许的最大数量级跨度：最大/最小代表值超过 100 倍则拆轴。 */
export const MARKET_DATA_MULTI_SERIES_MAGNITUDE_SPAN = 100;
/** 多系列图最多保留两根 Y 轴（左/右）；聚类更多时只画序列数最多的前两组。 */
const MARKET_DATA_MULTI_SERIES_MAX_AXES = 2;

type MultiSeriesAxisMember = {
  input: MarketDataSeriesTimeInput;
  index: number;
  magnitude: number;
};

type MultiSeriesAxisCluster = {
  unitLabel: string;
  firstIndex: number;
  items: MultiSeriesAxisMember[];
};

/**
 * 轴名显示用 unit：后端未定义单位时事实表会下发字面量 "unknown"/"pending"，
 * 这类占位值不是单位，轴名留空（分簇仍按原始 unit 分组，数量级兜底拆轴）。
 */
export function displayAxisUnit(unit: string | null | undefined): string {
  const trimmed = unit?.trim() ?? "";
  const lowered = trimmed.toLowerCase();
  if (lowered === "unknown" || lowered === "pending") {
    return "";
  }
  return trimmed;
}

/** 序列的数量级代表值：近期点的最大绝对值。 */
function seriesMagnitude(input: MarketDataSeriesTimeInput): number {
  let max = 0;
  for (const point of input.recent_points ?? []) {
    const abs = Math.abs(point.value_numeric ?? Number.NaN);
    if (Number.isFinite(abs) && abs > max) {
      max = abs;
    }
  }
  return max;
}

/**
 * Y 轴聚类：不同 unit 一律不共轴；同 unit 内按数量级升序贪心分簇，
 * 跨度超过 `MARKET_DATA_MULTI_SERIES_MAGNITUDE_SPAN` 时另起一簇。
 * 返回按「序列数多者优先、并列按出现顺序」排序的簇列表。
 */
function clusterSeriesByAxis(usable: MarketDataSeriesTimeInput[]): MultiSeriesAxisCluster[] {
  const byUnit = new Map<string, MultiSeriesAxisMember[]>();
  usable.forEach((input, index) => {
    const unitLabel = input.unit?.trim() ?? "";
    const members = byUnit.get(unitLabel) ?? [];
    members.push({ input, index, magnitude: seriesMagnitude(input) });
    byUnit.set(unitLabel, members);
  });

  const clusters: MultiSeriesAxisCluster[] = [];
  for (const [unitLabel, members] of byUnit) {
    const sorted = [...members].sort((left, right) => left.magnitude - right.magnitude);
    let current: MultiSeriesAxisCluster | null = null;
    let currentBase = 0;
    for (const member of sorted) {
      const fitsCurrent =
        current !== null &&
        (currentBase === 0 ||
          member.magnitude <= currentBase * MARKET_DATA_MULTI_SERIES_MAGNITUDE_SPAN);
      if (current && fitsCurrent) {
        current.items.push(member);
        current.firstIndex = Math.min(current.firstIndex, member.index);
        if (currentBase === 0) {
          currentBase = member.magnitude;
        }
      } else {
        current = { unitLabel, firstIndex: member.index, items: [member] };
        currentBase = member.magnitude;
        clusters.push(current);
      }
    }
  }

  return clusters.sort(
    (left, right) => right.items.length - left.items.length || left.firstIndex - right.firstIndex,
  );
}

export function buildMarketDataMultiSeriesTimeChartOption(
  seriesList: MarketDataSeriesTimeInput[],
): EChartsOption | null {
  const usable = seriesList.filter((item) => (item.recent_points?.length ?? 0) > 0);
  if (usable.length === 0) {
    return null;
  }

  // 数量级/单位聚类：最多两簇上图（左/右轴），其余序列不入图（仍留在卡内表格），
  // 避免千亿级投放量把 1.4% 的 SHIBOR 压成贴地直线。
  const axisClusters = clusterSeriesByAxis(usable).slice(0, MARKET_DATA_MULTI_SERIES_MAX_AXES);
  const charted = axisClusters
    .flatMap((cluster, axisIndex) => cluster.items.map((member) => ({ ...member, axisIndex })))
    .sort((left, right) => left.index - right.index);
  const isDualAxis = axisClusters.length > 1;

  const dateSet = new Set<string>();
  const timelineByMember = new Map<number, Map<string, number | null>>();
  for (const member of charted) {
    const timeline = new Map<string, number | null>();
    for (const point of sortedRecentPoints(member.input.recent_points)) {
      timeline.set(point.trade_date, point.value_numeric != null && Number.isFinite(point.value_numeric) ? point.value_numeric : null);
      dateSet.add(point.trade_date);
    }
    timelineByMember.set(member.index, timeline);
  }
  const categories = [...dateSet].sort((left, right) => left.localeCompare(right));
  const legendSelected =
    charted.length > MARKET_DATA_MULTI_SERIES_DEFAULT_VISIBLE
      ? Object.fromEntries(
          charted.map((member, order) => [
            seriesDisplayName(member.input),
            order < MARKET_DATA_MULTI_SERIES_DEFAULT_VISIBLE,
          ]),
        )
      : undefined;
  return createLineChartOption({
    color: marketDataChartTheme.multiSeriesPalette,
    tooltip: buildMarketDataChartTooltip({
      trigger: "axis",
      axisPointer: marketDataChartTheme.axisPointerLine,
      valueFormatter: (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : EM_DASH),
    }),
    legend: {
      ...(legendSelected ? { selected: legendSelected } : {}),
    },
    // 双轴时顶部留出轴名（unit）的空间。
    grid: {
      left: 8,
      right: 12,
      top: isDualAxis ? 30 : 16,
    },
    xAxis: buildDateCategoryAxis(categories, marketDataChartTheme.axisLabel),
    yAxis: isDualAxis
      ? axisClusters.map((cluster, axisIndex) =>
          buildCompactValueAxis(marketDataChartTheme.axisLabel, {
            splitNumber: 4,
            unitName: displayAxisUnit(cluster.unitLabel),
            ...(axisIndex > 0 ? { position: "right" as const, showSplitLine: false } : {}),
          }),
        )
      : buildCompactValueAxis(marketDataChartTheme.axisLabel, { splitNumber: 4 }),
    // 系列只用颜色区分（虚线保留给「预测/代理」语义，当前多系列无此语义）。
    // Mixed-frequency dates may connect, but an explicitly missing source
    // observation must stay a visible gap rather than suggest continuity.
    series: charted.map((member, order) => {
      const color =
        marketDataChartTheme.multiSeriesPalette[order % marketDataChartTheme.multiSeriesPalette.length]!;
      const isPrimary = order === 0;
      return {
        name: seriesDisplayName(member.input),
        type: "line" as const,
        yAxisIndex: member.axisIndex,
        smooth: true,
        symbol: "circle",
        symbolSize: 5,
        showSymbol: false,
        connectNulls: !member.input.recent_points?.some((point) => point.value_numeric == null || !Number.isFinite(point.value_numeric)),
        lineStyle: {
          color,
          width: isPrimary ? 2 : 1.5,
        },
        itemStyle: {
          color,
          borderColor: marketDataChartTheme.chartSurface,
          borderWidth: 1.2,
        },
        areaStyle: isPrimary ? buildSoftAreaGradient(color) : undefined,
        emphasis: { focus: "series" as const },
        data: categories.map((date) => timelineByMember.get(member.index)?.get(date) ?? null),
      };
    }),
  });
}
