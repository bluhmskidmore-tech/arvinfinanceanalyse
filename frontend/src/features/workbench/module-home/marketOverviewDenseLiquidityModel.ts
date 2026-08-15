import type {
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
} from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import {
  MARKET_CHART_STATIC_PALETTE,
  type MarketChartPalette,
} from "./marketChartPalette";
import type { MarketFinancialChartSpec } from "./marketFinancialChartsModel";

import { EM_DASH } from "../../../utils/format";
export type DenseLiquidityPoint = {
  date: string;
  value: number;
};

export type DenseLiquiditySeriesRole =
  | "市场资金利率"
  | "政策操作利率"
  | "期限报价";

export type DenseLiquiditySeriesStatus =
  | "ready"
  | "insufficient-observations";

export type DenseLiquiditySeries = {
  key: string;
  label: string;
  role: DenseLiquiditySeriesRole;
  readingHint: string;
  status: DenseLiquiditySeriesStatus;
  unit: string;
  latestDate: string;
  points: DenseLiquidityPoint[];
};

export type DenseLiquidityChartStatus =
  | "ready"
  | "partial"
  | "no-data"
  | "insufficient-observations"
  | "incompatible-units";

export type DenseLiquiditySeriesRoleItem = Pick<
  DenseLiquiditySeries,
  "key" | "label" | "role" | "readingHint" | "status"
> & {
  observationCount: number;
};

export type DenseLiquidityChartSpec = MarketFinancialChartSpec & {
  status: DenseLiquidityChartStatus;
  readingHint: string;
  seriesRoles: DenseLiquiditySeriesRoleItem[];
};

const LIQUIDITY_SERIES = [
  {
    key: "dr007",
    label: "DR007",
    role: "市场资金利率",
    readingHint: "观察 DR007 市场资金利率走势",
    matches: (point: ChoiceMacroLatestPoint) =>
      point.series_id === "CA.DR007" ||
      /\bDR\s*0?07\b/i.test(`${point.series_id} ${point.series_name}`),
  },
  {
    key: "repo-7d",
    label: "7D逆回购",
    role: "政策操作利率",
    readingHint: "观察公开市场操作7天中标利率",
    matches: (point: ChoiceMacroLatestPoint) =>
      point.series_id === "EMM00088132" ||
      /逆回购.*7天|7天.*逆回购/i.test(point.series_name),
  },
  {
    key: "shibor-1m",
    label: "SHIBOR 1M",
    role: "期限报价",
    readingHint: "观察1个月期限报价",
    matches: (point: ChoiceMacroLatestPoint) =>
      point.series_id === "NCD.SHIBOR.1M",
  },
  {
    key: "shibor-3m",
    label: "SHIBOR 3M",
    role: "期限报价",
    readingHint: "观察3个月期限报价",
    matches: (point: ChoiceMacroLatestPoint) =>
      point.series_id === "NCD.SHIBOR.3M",
  },
] as const;

function normalizeDenseLiquidityUnit(unit: string | null | undefined) {
  const normalized = unit?.trim() ?? "";
  return normalized && normalized.toLowerCase() !== "unknown"
    ? normalized
    : "";
}

function sharedLiquidityUnit(
  liquiditySeries: readonly DenseLiquiditySeries[],
): string | null {
  if (liquiditySeries.length === 0) return "";
  const normalizedUnits = liquiditySeries.map((series) =>
    normalizeDenseLiquidityUnit(series.unit),
  );
  if (normalizedUnits.some((unit) => !unit)) return null;
  const units = [...new Set(normalizedUnits)];
  return units.length === 1 ? units[0] : null;
}

function formatLiquidityValue(value: number, unit: string) {
  return `${value.toFixed(4)}${unit}`;
}

function toDenseLiquiditySeries(
  point: ChoiceMacroLatestPoint,
  key: string,
  label: string,
  role: DenseLiquiditySeriesRole,
  readingHint: string,
): DenseLiquiditySeries {
  const observations = new Map(
    (point.recent_points ?? []).map((recent) => [
      recent.trade_date,
      recent.value_numeric,
    ]),
  );
  observations.set(point.trade_date, point.value_numeric);
  const points = [...observations.entries()]
    .map(([date, value]) => ({ date, value }))
    .sort((left, right) => left.date.localeCompare(right.date));
  return {
    key,
    label,
    role,
    readingHint,
    status: points.length >= 2 ? "ready" : "insufficient-observations",
    unit: point.unit,
    latestDate: point.trade_date,
    points,
  };
}

export function buildDenseLiquiditySeries(
  rates: ChoiceMacroLatestPayload | undefined,
): DenseLiquiditySeries[] {
  const points = rates?.series ?? [];
  return LIQUIDITY_SERIES.flatMap((definition) => {
    const point = points.find(definition.matches);
    return point
      ? [
          toDenseLiquiditySeries(
            point,
            definition.key,
            definition.label,
            definition.role,
            definition.readingHint,
          ),
        ]
      : [];
  });
}

export function buildDenseLiquidityChartSpec(
  rates: ChoiceMacroLatestPayload | undefined,
  palette: MarketChartPalette = MARKET_CHART_STATIC_PALETTE,
): DenseLiquidityChartSpec {
  const liquiditySeries = buildDenseLiquiditySeries(rates);
  const plottableSeries = liquiditySeries.filter(
    (series) => series.status === "ready",
  );
  const insufficientSeriesCount =
    liquiditySeries.length - plottableSeries.length;
  const unit = sharedLiquidityUnit(liquiditySeries);
  const dates = [
    ...new Set(
      liquiditySeries.flatMap((series) =>
        series.points.map((point) => point.date),
      ),
    ),
  ].sort();
  const colors = [
    palette.accent,
    palette.amber,
    palette.green,
    palette.red,
  ];
  const lineTypes = ["solid", "dashed", "solid", "solid"] as const;
  const status: DenseLiquidityChartStatus =
    liquiditySeries.length === 0
      ? "no-data"
      : unit == null
        ? "incompatible-units"
        : plottableSeries.length === 0
          ? "insufficient-observations"
          : insufficientSeriesCount > 0
            ? "partial"
            : "ready";
  const dateRange = `${dates[0] ?? "日期未返回"}–${
    dates.at(-1) ?? "日期未返回"
  }`;
  const readingHint =
    "DR007 看市场资金利率；7D逆回购看政策操作利率；SHIBOR 看期限报价。";
  const seriesRoles = liquiditySeries.map(
    ({
      key,
      label,
      role,
      readingHint: seriesReadingHint,
      status: seriesStatus,
      points,
    }) => ({
      key,
      label,
      role,
      readingHint: seriesReadingHint,
      observationCount: points.length,
      status: seriesStatus,
    }),
  );
  const option: EChartsOption | null =
    dates.length === 0 || unit == null || plottableSeries.length === 0
      ? null
      : {
          animationDuration: 320,
          color: colors,
          tooltip: {
            trigger: "axis",
            confine: true,
            backgroundColor: palette.panel2,
            borderColor: palette.lineSoft,
            textStyle: {
              color: palette.ink,
              fontSize: 10,
              fontFamily: '"Cascadia Mono", monospace',
            },
            valueFormatter: (value: unknown) =>
              typeof value === "number" && Number.isFinite(value)
                ? formatLiquidityValue(value, unit)
                : EM_DASH,
          },
          legend: {
            top: 0,
            left: 6,
            itemWidth: 12,
            itemHeight: 6,
            textStyle: {
              color: palette.inkSoft,
              fontSize: 8,
            },
          },
          grid: {
            left: 34,
            right: 18,
            top: 32,
            bottom: 25,
            containLabel: true,
          },
          xAxis: {
            type: "category",
            boundaryGap: false,
            data: dates,
            axisLabel: {
              color: palette.inkMuted,
              fontSize: 8,
              hideOverlap: true,
              formatter: (value: string) => value.slice(5),
            },
            axisLine: {
              lineStyle: {
                color: palette.lineSoft,
              },
            },
            axisTick: { show: false },
          },
          yAxis: {
            type: "value",
            scale: true,
            name: unit,
            nameTextStyle: {
              color: palette.inkMuted,
              fontSize: 8,
            },
            axisLabel: {
              color: palette.inkMuted,
              fontSize: 8,
              formatter: (value: number) => value.toFixed(2),
            },
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: {
              lineStyle: {
                color: palette.lineSoft,
                type: "dashed",
              },
            },
          },
          series: plottableSeries.map((series) => {
            const displayIndex = liquiditySeries.findIndex(
              (candidate) => candidate.key === series.key,
            );
            const color = colors[displayIndex] ?? colors[0];
            const byDate = new Map(
              series.points.map((point) => [point.date, point.value]),
            );
            const hasVisibleLineSegment = dates.some(
              (date, dateIndex) =>
                dateIndex > 0 &&
                byDate.has(dates[dateIndex - 1]) &&
                byDate.has(date),
            );
            return {
              name: series.label,
              type: "line",
              connectNulls: false,
              showSymbol: !hasVisibleLineSegment,
              symbol: "circle",
              symbolSize: 5,
              smooth: false,
              lineStyle: {
                width: 1.5,
                type: lineTypes[displayIndex] ?? "solid",
                color,
              },
              itemStyle: { color },
              emphasis: {
                focus: "series",
              },
              data: dates.map((date) => byDate.get(date) ?? null),
            };
          }),
        };
  // 副标题单行最多 1 个 `·`（DESIGN.md §7）：只保留日期与单位/状态之一，
  // 序列条数等明细移入脚注（C17）。
  return {
    key: "liquidity-tenor",
    title: "流动性期限与资金利率",
    subtitle:
      status === "no-data"
        ? "日期未返回 · 未绘制"
        : status === "incompatible-units"
          ? `${dateRange} · 单位缺失或不一致未绘制`
          : status === "insufficient-observations"
            ? `${dateRange} · 观测不足未绘制`
            : `${dateRange}${unit ? ` · ${unit}` : ""}`,
    footnote:
      status === "incompatible-units"
        ? `共 ${liquiditySeries.length} 条正式序列；单位缺失或不一致时不共轴绘制、不推导换算。`
        : status === "insufficient-observations"
          ? `共 ${liquiditySeries.length} 条正式序列，均少于 2 个观测不绘制，避免不可见假线。`
          : status === "no-data"
            ? "后端暂未返回可绘制的利率序列。"
            : status === "partial"
              ? `共 ${liquiditySeries.length} 条正式序列，已绘制 ${plottableSeries.length} 条、观测不足 ${insufficientSeriesCount} 条；直接使用 recent_points，空值不插值、不派生利差。`
              : `共 ${liquiditySeries.length} 条正式序列；直接使用 recent_points，空值不插值、不派生利差。`,
    option,
    height: 232,
    status,
    readingHint,
    seriesRoles,
  };
}
