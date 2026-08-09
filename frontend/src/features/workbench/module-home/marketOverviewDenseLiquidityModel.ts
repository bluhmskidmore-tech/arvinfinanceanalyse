import type {
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
} from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import { dhApiTokens } from "../../../theme/designSystem";
import type { MarketFinancialChartSpec } from "./marketFinancialChartsModel";

export type DenseLiquidityPoint = {
  date: string;
  value: number;
};

export type DenseLiquiditySeries = {
  key: string;
  label: string;
  unit: string;
  latestDate: string;
  points: DenseLiquidityPoint[];
};

const LIQUIDITY_SERIES = [
  {
    key: "dr007",
    label: "DR007",
    matches: (point: ChoiceMacroLatestPoint) =>
      point.series_id === "CA.DR007" ||
      /\bDR\s*0?07\b/i.test(`${point.series_id} ${point.series_name}`),
  },
  {
    key: "repo-7d",
    label: "7D逆回购",
    matches: (point: ChoiceMacroLatestPoint) =>
      point.series_id === "EMM00088132" ||
      /逆回购.*7天|7天.*逆回购/i.test(point.series_name),
  },
  {
    key: "shibor-1m",
    label: "SHIBOR 1M",
    matches: (point: ChoiceMacroLatestPoint) =>
      point.series_id === "NCD.SHIBOR.1M",
  },
  {
    key: "shibor-3m",
    label: "SHIBOR 3M",
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
): DenseLiquiditySeries {
  const observations = new Map(
    (point.recent_points ?? []).map((recent) => [
      recent.trade_date,
      recent.value_numeric,
    ]),
  );
  observations.set(point.trade_date, point.value_numeric);
  return {
    key,
    label,
    unit: point.unit,
    latestDate: point.trade_date,
    points: [...observations.entries()]
      .map(([date, value]) => ({ date, value }))
      .sort((left, right) => left.date.localeCompare(right.date)),
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
          ),
        ]
      : [];
  });
}

export function buildDenseLiquidityChartSpec(
  rates: ChoiceMacroLatestPayload | undefined,
): MarketFinancialChartSpec {
  const liquiditySeries = buildDenseLiquiditySeries(rates);
  const unit = sharedLiquidityUnit(liquiditySeries);
  const dates = [
    ...new Set(
      liquiditySeries.flatMap((series) =>
        series.points.map((point) => point.date),
      ),
    ),
  ].sort();
  const colors = [
    dhApiTokens.color.blue,
    dhApiTokens.color.amber,
    dhApiTokens.color.green,
    dhApiTokens.color.red,
  ];
  const lineTypes = ["solid", "dashed", "solid", "solid"] as const;
  const option: EChartsOption | null =
    dates.length === 0 || unit == null
      ? null
      : {
          animationDuration: 320,
          color: colors,
          tooltip: {
            trigger: "axis",
            confine: true,
            backgroundColor: dhApiTokens.color.panel2,
            borderColor: dhApiTokens.color.lineSoft,
            textStyle: {
              color: dhApiTokens.color.ink,
              fontSize: 10,
              fontFamily: '"Cascadia Mono", monospace',
            },
            valueFormatter: (value: unknown) =>
              typeof value === "number" && Number.isFinite(value)
                ? formatLiquidityValue(value, unit)
                : "—",
          },
          legend: {
            top: 0,
            left: 6,
            itemWidth: 12,
            itemHeight: 6,
            textStyle: {
              color: dhApiTokens.color.inkSoft,
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
              color: dhApiTokens.color.inkMuted,
              fontSize: 8,
              hideOverlap: true,
              formatter: (value: string) => value.slice(5),
            },
            axisLine: {
              lineStyle: {
                color: dhApiTokens.color.lineSoft,
              },
            },
            axisTick: { show: false },
          },
          yAxis: {
            type: "value",
            scale: true,
            name: unit,
            nameTextStyle: {
              color: dhApiTokens.color.inkMuted,
              fontSize: 8,
            },
            axisLabel: {
              color: dhApiTokens.color.inkMuted,
              fontSize: 8,
              formatter: (value: number) => value.toFixed(2),
            },
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: {
              lineStyle: {
                color: dhApiTokens.color.lineSoft,
                type: "dashed",
              },
            },
          },
          series: liquiditySeries.map((series, index) => {
            const byDate = new Map(
              series.points.map((point) => [point.date, point.value]),
            );
            return {
              name: series.label,
              type: "line",
              connectNulls: false,
              showSymbol: false,
              symbol: "circle",
              smooth: false,
              lineStyle: {
                width: 1.5,
                type: lineTypes[index] ?? "solid",
              },
              emphasis: {
                focus: "series",
              },
              data: dates.map((date) => byDate.get(date) ?? null),
            };
          }),
        };
  return {
    key: "liquidity-tenor",
    title: "流动性期限与资金利率",
    subtitle:
      unit == null
        ? `${dates[0] ?? "日期未返回"}–${
          dates.at(-1) ?? "日期未返回"
          } · ${liquiditySeries.length} 条正式序列 · 单位缺失或不一致未绘制`
        : `${dates[0] ?? "日期未返回"}–${
            dates.at(-1) ?? "日期未返回"
          } · ${liquiditySeries.length} 条正式序列${unit ? ` · ${unit}` : ""}`,
    footnote:
      unit == null
        ? "直接使用正式利率接口 recent_points；若所选流动性序列单位缺失或不一致，则前端不共轴绘制、不推导换算。"
        : "直接使用正式利率接口 recent_points；不同报告日保留空值，不插值、不派生利差。",
    option,
    height: 232,
  };
}
