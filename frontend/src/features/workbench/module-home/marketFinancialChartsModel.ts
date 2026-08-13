import type {
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  ChoiceNewsEventsPayload,
  MacroVendorPayload,
} from "../../../api/contracts";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitStrategySummariesPayload,
} from "../../../api/macroToolkitClient";
import type { EChartsOption } from "../../../lib/echarts";
import {
  MARKET_CHART_STATIC_PALETTE,
  type MarketChartPalette,
} from "./marketChartPalette";

import { EM_DASH } from "../../../utils/format";
type MarketChartColors = {
  lavender: string;
  blueDeep: string;
  risk: string;
  contrast: string;
  gold: string;
  green: string;
  ink: string;
  muted: string;
  grid: string;
  surface: string;
  /** 强调色柱面内标签的墨色：取页面底色以保证对比。 */
  labelOnAccent: string;
};

type MarketChartTheme = {
  colors: MarketChartColors;
  lineColors: readonly string[];
  axisLabel: { color: string; fontSize: number; fontFamily: string };
  splitLine: {
    lineStyle: { color: string; opacity: number; type: "solid" };
  };
  axisLine: { lineStyle: { color: string } };
  tooltip: {
    trigger: "axis";
    confine: boolean;
    backgroundColor: string;
    borderColor: string;
    borderWidth: number;
    textStyle: { color: string; fontSize: number };
  };
};

/**
 * 图表配色从调用方注入的 palette 构造（Nocturne scope 下由页根 CSS 变量
 * 运行时解析），不再固定引用钢蓝静态令牌；未注入时回退 dhApiTokens 静态值。
 */
function createMarketChartTheme(palette: MarketChartPalette): MarketChartTheme {
  const colors: MarketChartColors = {
    lavender: palette.accent,
    blueDeep: palette.accentDeep,
    risk: palette.red,
    contrast: palette.ink,
    gold: palette.amber,
    green: palette.green,
    ink: palette.inkSoft,
    muted: palette.inkMuted,
    grid: palette.lineSoft,
    surface: palette.panel2,
    labelOnAccent: palette.canvas,
  };
  return {
    colors,
    /**
     * 分类系列不使用 green/red：暗色令牌把它们定义为方向语义色，用来区分资产会让
     * 「红线上行」这类组合产生误读（参见 DESIGN.md 2026-07-19 久期缺口色决议）。
     */
    lineColors: [
      colors.lavender,
      colors.gold,
      colors.contrast,
      colors.ink,
      colors.blueDeep,
    ],
    axisLabel: {
      color: colors.muted,
      fontSize: 10,
      fontFamily: '"Cascadia Mono", "SFMono-Regular", monospace',
    },
    splitLine: {
      lineStyle: {
        color: colors.grid,
        opacity: 0.55,
        type: "solid" as const,
      },
    },
    axisLine: {
      lineStyle: {
        color: colors.grid,
      },
    },
    tooltip: {
      trigger: "axis" as const,
      confine: true,
      backgroundColor: colors.surface,
      borderColor: colors.grid,
      borderWidth: 1,
      textStyle: {
        color: palette.ink,
        fontSize: 11,
      },
    },
  };
}

/**
 * 线条只用颜色区分系列。虚线在固收语境里表示外推或基准，不能当作装饰性区分手段。
 */
const lineSeries = {
  type: "line" as const,
  smooth: false,
  symbol: "none" as const,
  showSymbol: false,
  connectNulls: false,
};

const legend = {
  top: 0,
  left: 0,
  itemWidth: 14,
  itemHeight: 2,
  itemGap: 14,
  icon: "roundRect",
};

export type MarketFinancialChartSpec = {
  key: string;
  title: string;
  subtitle: string;
  footnote: string;
  readingGuide?: string;
  yieldCurveDisplay?: MarketYieldCurveDisplay;
  option: EChartsOption | null;
  height?: number;
};

export type MarketYieldCurveComparisonRow = {
  curve: string;
  tenorLabel: string;
  tradeDate: string;
  value: number;
  unit: "%";
};

export type MarketYieldCurveDisplay =
  | {
      kind: "curve";
      uniqueTenorCount: number;
    }
  | {
      kind: "single-tenor";
      message: string;
      rows: MarketYieldCurveComparisonRow[];
      tenorLabel: string;
      uniqueTenorCount: 1;
    }
  | {
      kind: "sparse-tenors";
      message: string;
      rows: MarketYieldCurveComparisonRow[];
      uniqueTenorCount: number;
    };

export type MarketFinancialChartSection = {
  key: "rates" | "cross" | "macro" | "strategy" | "news" | "coverage";
  kicker: string;
  title: string;
  description: string;
  charts: MarketFinancialChartSpec[];
};

export type MarketFinancialChartsInput = {
  latest?: ChoiceMacroLatestPayload;
  rates?: ChoiceMacroLatestPayload;
  catalog?: MacroVendorPayload;
  macro?: MacroToolkitAnalysisPayload;
  strategies?: MacroToolkitStrategySummariesPayload;
  news?: ChoiceNewsEventsPayload;
  /** 运行时解析的页面色板；缺省回退 dhApiTokens 静态值（jsdom/测试路径）。 */
  palette?: MarketChartPalette;
};

type LineInput = {
  name: string;
  values: Map<string, number>;
};

type YieldCurveRow = {
  curve: string;
  tenor: number;
  tenorLabel: string;
  value: number;
  tradeDate: string;
};

function finiteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function sortedRecentPoints(series: ChoiceMacroLatestPoint) {
  return [...(series.recent_points ?? [])]
    .filter((point) => finiteNumber(point.value_numeric))
    .sort((left, right) => left.trade_date.localeCompare(right.trade_date));
}

function timelineRange(series: ChoiceMacroLatestPoint[]) {
  const dates = series.flatMap((item) =>
    sortedRecentPoints(item).map((point) => point.trade_date),
  );
  if (dates.length === 0) return "日期未返回";
  dates.sort((left, right) => left.localeCompare(right));
  return `${dates[0]}–${dates.at(-1)}`;
}

function compactSeriesName(series: ChoiceMacroLatestPoint) {
  const name = series.series_name;
  const tenor = name.match(/(\d+(?:\.\d+)?)\s*年/)?.[1];
  if (/DR\s*0?07/i.test(name)) return "DR007";
  if (/逆回购/.test(name) && /7\s*天/.test(name)) return "7D 逆回购";
  if (/国开|政策性金融债/i.test(name)) return tenor ? `国开 ${tenor}Y` : "国开";
  if (/国债/i.test(name) && !/美国|英国|日本/.test(name))
    return tenor ? `国债 ${tenor}Y` : "国债";
  if (/沪深300.*收盘/i.test(name)) return "沪深300";
  if (/铜主力/i.test(name)) return "铜";
  if (/铝主力/i.test(name)) return "铝";
  if (/Brent/i.test(name)) return "Brent";
  if (/USD\/CNY|美元兑人民币/i.test(name)) return "USD/CNY";
  return name.length > 14 ? `${name.slice(0, 14)}…` : name;
}

function buildMultiLineOption(
  theme: MarketChartTheme,
  lines: LineInput[],
  options: {
    unit: string;
    decimals?: number;
    scale?: boolean;
  },
): EChartsOption | null {
  const { lineColors: LINE_COLORS, axisLabel, axisLine, splitLine, tooltip } =
    theme;
  if (lines.length === 0) return null;
  const dates = [
    ...new Set(lines.flatMap((line) => [...line.values.keys()])),
  ].sort((left, right) => left.localeCompare(right));
  if (dates.length < 2) return null;
  const decimals = options.decimals ?? 2;
  return {
    animationDuration: 420,
    color: [...LINE_COLORS],
    tooltip: {
      ...tooltip,
      valueFormatter: (value: unknown) =>
        finiteNumber(value) ? `${value.toFixed(decimals)}${options.unit}` : EM_DASH,
    },
    legend: {
      ...legend,
      textStyle: axisLabel,
    },
    grid: {
      left: 0,
      right: 6,
      top: 26,
      bottom: 0,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: dates,
      axisLabel: {
        ...axisLabel,
        hideOverlap: true,
      },
      axisLine,
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      scale: options.scale ?? true,
      axisLabel: {
        ...axisLabel,
        formatter: (value: number) => value.toFixed(decimals),
      },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine,
    },
    series: lines.map((line, index) => ({
      ...lineSeries,
      name: line.name,
      lineStyle: {
        color: LINE_COLORS[index % LINE_COLORS.length],
        width: index === 0 ? 1.8 : 1.4,
      },
      itemStyle: {
        color: LINE_COLORS[index % LINE_COLORS.length],
      },
      emphasis: { focus: "series" },
      data: dates.map((date) => line.values.get(date) ?? null),
    })),
  };
}

function latestCoherentYieldCurveRows(rows: YieldCurveRow[]) {
  const tenorsByDateAndCurve = new Map<string, Map<string, Set<number>>>();
  for (const row of rows) {
    const curves = tenorsByDateAndCurve.get(row.tradeDate) ?? new Map();
    const tenors = curves.get(row.curve) ?? new Set<number>();
    tenors.add(row.tenor);
    curves.set(row.curve, tenors);
    tenorsByDateAndCurve.set(row.tradeDate, curves);
  }
  const sortedDates = [...tenorsByDateAndCurve.keys()].sort((left, right) =>
    right.localeCompare(left),
  );
  const selectedDate =
    sortedDates.find((date) =>
      [...(tenorsByDateAndCurve.get(date)?.values() ?? [])].some(
        (tenors) => tenors.size >= 2,
      ),
    ) ??
    sortedDates[0];
  return {
    selectedDate,
    selectedRows: selectedDate
      ? rows.filter((row) => row.tradeDate === selectedDate)
      : [],
  };
}

function buildYieldCurveChart(
  theme: MarketChartTheme,
  rates: ChoiceMacroLatestPayload | undefined,
): MarketFinancialChartSpec {
  const { colors: COLORS, axisLabel, axisLine, splitLine, tooltip } = theme;
  let rows = (rates?.series ?? [])
    .map((series) => {
      const name = series.series_name;
      const tenor = Number(name.match(/(\d+(?:\.\d+)?)\s*年/)?.[1]);
      if (!Number.isFinite(tenor) || series.unit !== "%") return null;
      if (/美国|英国|日本/.test(name)) return null;
      const curve = /国开|政策性金融债/i.test(name)
        ? "国开"
        : /国债/i.test(name)
          ? "国债"
          : null;
      if (!curve || !finiteNumber(series.value_numeric)) return null;
      return {
        curve,
        tenor,
        tenorLabel: `${tenor}Y`,
        value: series.value_numeric,
        tradeDate: series.trade_date,
      };
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item));
  const { selectedDate, selectedRows } = latestCoherentYieldCurveRows(rows);
  rows = selectedRows;
  const tenors = [...new Set(selectedRows.map((row) => row.tenor))].sort(
    (left, right) => left - right,
  );
  const curves = ["国债", "国开"].filter((curve) =>
    selectedRows.some((row) => row.curve === curve),
  );
  const comparisonRows = curves.flatMap((curve) =>
    tenors.flatMap((tenor) => {
      const row = selectedRows.find(
        (item) => item.curve === curve && item.tenor === tenor,
      );
      return row
        ? [
            {
              curve: row.curve,
              tenorLabel: row.tenorLabel,
              tradeDate: row.tradeDate,
              value: row.value,
              unit: "%" as const,
            },
          ]
        : [];
    }),
  );
  const hasRenderableCurve = curves.some(
    (curve) =>
      new Set(
        selectedRows
          .filter((row) => row.curve === curve)
          .map((row) => row.tenor),
      ).size >= 2,
  );
  const singleTenorMessage = "当前仅返回一个期限，暂不能判断曲线形态。";
  const sparseTenorsMessage =
    "当前报价未形成同一条曲线的多个期限，暂不能判断曲线形态。";
  const yieldCurveDisplay: MarketYieldCurveDisplay | undefined =
    hasRenderableCurve
      ? { kind: "curve", uniqueTenorCount: tenors.length }
      : tenors.length === 1
        ? {
            kind: "single-tenor",
            message: singleTenorMessage,
            rows: comparisonRows,
            tenorLabel: `${tenors[0]}Y`,
            uniqueTenorCount: 1,
          }
        : tenors.length >= 2
          ? {
              kind: "sparse-tenors",
              message: sparseTenorsMessage,
              rows: comparisonRows,
              uniqueTenorCount: tenors.length,
            }
          : undefined;
  const latestDate = selectedDate ??
    [...rows.map((row) => row.tradeDate)].sort().at(-1) ?? "日期未返回";
  const option: EChartsOption | null =
    selectedRows.length === 0
      ? null
      : !hasRenderableCurve
        ? {
            animationDuration: 420,
            color: [COLORS.lavender],
            tooltip: {
              ...tooltip,
              trigger: "item",
              valueFormatter: (value: unknown) =>
                finiteNumber(value) ? `${value.toFixed(3)}%` : EM_DASH,
            },
            grid: {
              left: 48,
              right: 28,
              top: 16,
              bottom: 30,
              containLabel: true,
            },
            xAxis: {
              type: "category",
              data: comparisonRows.map(
                (row) => `${row.curve} ${row.tenorLabel}`,
              ),
              axisLabel,
              axisLine,
              axisTick: { show: false },
            },
            yAxis: {
              type: "value",
              scale: true,
              name: "收益率 (%)",
              nameTextStyle: axisLabel,
              axisLabel: {
                ...axisLabel,
                formatter: (value: number) => value.toFixed(2),
              },
              splitLine,
            },
            series: [
              {
                name: "收益率报价",
                type: "bar",
                barMaxWidth: 42,
                itemStyle: {
                  color: COLORS.lavender,
                },
                label: {
                  show: true,
                  position: "top",
                  color: COLORS.ink,
                  fontSize: 10,
                  formatter: ({ value }: { value: unknown }) =>
                    finiteNumber(value) ? `${value.toFixed(3)}%` : EM_DASH,
                },
                data: comparisonRows.map((row) => row.value),
              },
            ],
          }
      : {
          animationDuration: 420,
          color: [COLORS.lavender, COLORS.gold],
          tooltip: {
            ...tooltip,
            valueFormatter: (value: unknown) =>
              finiteNumber(value) ? `${value.toFixed(3)}%` : EM_DASH,
          },
          legend: {
            ...legend,
            textStyle: axisLabel,
          },
          grid: {
            left: 0,
            right: 10,
            top: 26,
            bottom: 0,
            containLabel: true,
          },
          xAxis: {
            type: "category",
            boundaryGap: false,
            data: tenors.map((tenor) => `${tenor}Y`),
            axisLabel,
            axisLine,
            axisTick: { show: false },
          },
          yAxis: {
            type: "value",
            scale: true,
            axisLabel: {
              ...axisLabel,
              formatter: (value: number) => value.toFixed(2),
            },
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine,
          },
          series: curves.map((curve, index) => ({
            ...lineSeries,
            name: curve,
            // 期限缺口处保留断点，但用小圆点标出孤立观测，避免只剩一个悬空的点。
            symbol: "circle",
            symbolSize: 4,
            showSymbol: true,
            lineStyle: {
              color: index === 0 ? COLORS.lavender : COLORS.gold,
              width: index === 0 ? 1.9 : 1.5,
            },
            itemStyle: {
              color: index === 0 ? COLORS.lavender : COLORS.gold,
            },
            data: tenors.map(
              (tenor) =>
                selectedRows.find(
                  (row) => row.curve === curve && row.tenor === tenor,
                )?.value ?? null,
            ),
          })),
        };
  return {
    key: "yield-curve",
    title: "国债与国开期限结构",
    subtitle: `${latestDate} · ${tenors.length} 个唯一期限 · 收益率 %`,
    footnote:
      tenors.length === 0
        ? "后端未返回可用的国债或国开收益率报价。"
        : tenors.length === 1
          ? `${singleTenorMessage} 数值直接取自后端最新收益率。`
          : !hasRenderableCurve && tenors.length >= 2
            ? `${sparseTenorsMessage} 数值直接取自后端最新收益率。`
            : "直接绘制后端最新收益率；纵轴采用聚焦刻度以辨识期限结构。",
    readingGuide:
      tenors.length === 0
        ? "等待同一报告日的有效收益率报价；不补点、不插值。"
        : tenors.length === 1 && comparisonRows.length >= 2
          ? "比较同一期限的国债与国开收益率，不据此判断曲线陡峭或平坦。"
          : tenors.length === 1
            ? "读取当前期限的已返回收益率；缺少其他期限，不能判断期限结构。"
            : !hasRenderableCurve && tenors.length >= 2
              ? "逐项核对已返回报价；不同曲线的单个期限不能连成一条曲线。"
              : "比较同一日期各期限的斜率，以及国债与国开的相对水平。",
    yieldCurveDisplay,
    option,
    height: 300,
  };
}

function pickKeyRateSeries(
  latest: ChoiceMacroLatestPayload | undefined,
  rates: ChoiceMacroLatestPayload | undefined,
) {
  const merged = new Map<string, ChoiceMacroLatestPoint>();
  [...(rates?.series ?? []), ...(latest?.series ?? [])].forEach((series) => {
    merged.set(series.series_id, series);
  });
  const all = [...merged.values()].filter(
    (series) => series.unit === "%" && (series.recent_points?.length ?? 0) >= 8,
  );
  const patterns = [
    /国债到期收益率.*10\s*年|国债.*10Y/i,
    /国债到期收益率.*2\s*年|国债.*2Y/i,
    /DR\s*0?07/i,
    /7\s*天.*逆回购|逆回购.*7\s*天/i,
  ];
  const selected: ChoiceMacroLatestPoint[] = [];
  for (const pattern of patterns) {
    const match = all.find(
      (series) =>
        pattern.test(series.series_name) &&
        !/美国|英国|日本|国开|政策性金融债/.test(series.series_name),
    );
    if (match && !selected.some((item) => item.series_id === match.series_id))
      selected.push(match);
  }
  return selected;
}

function buildKeyRateTrend(
  theme: MarketChartTheme,
  latest: ChoiceMacroLatestPayload | undefined,
  rates: ChoiceMacroLatestPayload | undefined,
): MarketFinancialChartSpec {
  const selected = pickKeyRateSeries(latest, rates);
  const lines = selected.map((series) => ({
    name: compactSeriesName(series),
    values: new Map(
      sortedRecentPoints(series).map((point) => [
        point.trade_date,
        point.value_numeric,
      ]),
    ),
  }));
  return {
    key: "key-rate-trend",
    title: "关键利率近 20 期走势",
    subtitle: `${timelineRange(selected)} · ${selected.length} 条同单位利率序列 · %`,
    footnote: "仅比较百分比利率原值；不同日期缺口保持为空，不做前端插值。",
    option: buildMultiLineOption(theme, lines, {
      unit: "%",
      decimals: 3,
    }),
    height: 300,
  };
}

function pickCrossAssetSeries(latest: ChoiceMacroLatestPayload | undefined) {
  const all = (latest?.series ?? []).filter(
    (series) => (series.recent_points?.length ?? 0) >= 8,
  );
  const patterns = [
    /沪深300指数收盘价/i,
    /铜主力期货收盘价/i,
    /铝主力期货收盘价/i,
    /Brent.*(?:spot|close|price)/i,
    /USD\/CNY|美元兑人民币/i,
  ];
  return patterns
    .map((pattern) => all.find((series) => pattern.test(series.series_name)))
    .filter((series): series is ChoiceMacroLatestPoint => Boolean(series));
}

function buildIndexedCrossAsset(
  theme: MarketChartTheme,
  latest: ChoiceMacroLatestPayload | undefined,
): MarketFinancialChartSpec {
  const selected = pickCrossAssetSeries(latest);
  const lines = selected
    .map((series) => {
      const points = sortedRecentPoints(series);
      const base = points[0]?.value_numeric;
      if (!finiteNumber(base) || base === 0) return null;
      return {
        name: compactSeriesName(series),
        values: new Map(
          points.map((point) => [
            point.trade_date,
            (point.value_numeric / base) * 100,
          ]),
        ),
      };
    })
    .filter((line): line is LineInput => Boolean(line));
  return {
    key: "cross-asset-index",
    title: "跨资产观察指数",
    subtitle: `${timelineRange(selected)} · ${lines.length} 类资产 · 首个可用观测=100`,
    footnote:
      "观察性归一化：指数=当期后端值÷该序列首个可用值×100；仅用于比较方向，不是正式收益指标。",
    option: buildMultiLineOption(theme, lines, {
      unit: "指数",
      decimals: 1,
    }),
    height: 320,
  };
}

function buildLatestCrossAssetMove(
  theme: MarketChartTheme,
  latest: ChoiceMacroLatestPayload | undefined,
): MarketFinancialChartSpec {
  const { colors: COLORS, axisLabel, axisLine, splitLine, tooltip } = theme;
  const selected = pickCrossAssetSeries(latest)
    .map((series) => {
      const points = sortedRecentPoints(series);
      const latestPoint = points.at(-1);
      const previousPoint = points.at(-2);
      if (!latestPoint || !previousPoint || previousPoint.value_numeric === 0)
        return null;
      return {
        name: compactSeriesName(series),
        value:
          ((latestPoint.value_numeric - previousPoint.value_numeric) /
            Math.abs(previousPoint.value_numeric)) *
          100,
      };
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
    .sort((left, right) => left.value - right.value);
  const option: EChartsOption | null =
    selected.length === 0
      ? null
      : {
          animationDuration: 380,
          tooltip: {
            ...tooltip,
            valueFormatter: (value: unknown) =>
              finiteNumber(value)
                ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
                : EM_DASH,
          },
          grid: {
            left: 82,
            right: 30,
            top: 16,
            bottom: 30,
            containLabel: true,
          },
          xAxis: {
            type: "value",
            name: "%",
            nameTextStyle: axisLabel,
            axisLabel,
            axisLine,
            splitLine,
          },
          yAxis: {
            type: "category",
            data: selected.map((item) => item.name),
            axisLabel,
            axisLine: { show: false },
            axisTick: { show: false },
          },
          series: [
            {
              type: "bar",
              barMaxWidth: 14,
              data: selected.map((item) => ({
                value: item.value,
                itemStyle: {
                  color:
                    item.value >= 0 ? COLORS.lavender : COLORS.risk,
                  borderColor:
                    item.value >= 0 ? COLORS.lavender : COLORS.risk,
                  borderWidth: 1,
                  borderRadius: item.value >= 0 ? [0, 3, 3, 0] : [3, 0, 0, 3],
                },
              })),
              label: {
                show: true,
                position: "right",
                color: COLORS.ink,
                fontSize: 9,
                formatter: (params: { value?: unknown }) =>
                  finiteNumber(params.value)
                    ? `${params.value >= 0 ? "+" : ""}${params.value.toFixed(2)}%`
                    : EM_DASH,
              },
            },
          ],
        };
  return {
    key: "cross-asset-move",
    title: "最新一期跨资产变动",
    subtitle: `${selected.length} 类资产 · 相邻两个后端观测的百分比变化`,
    footnote: "显示变化率而非绝对点差；正负以实心/开放填充和零轴共同区分。",
    option,
    height: 280,
  };
}

function buildMacroIndicatorChange(
  theme: MarketChartTheme,
  macro: MacroToolkitAnalysisPayload | undefined,
): MarketFinancialChartSpec {
  const { colors: COLORS, axisLabel, axisLine, splitLine, tooltip } = theme;
  const rows = (macro?.indicators ?? [])
    .filter((indicator) => finiteNumber(indicator.change_pct))
    .map((indicator) => ({
      name: indicator.label,
      value: indicator.change_pct as number,
    }))
    .sort((left, right) => left.value - right.value);
  const option: EChartsOption | null =
    rows.length === 0
      ? null
      : {
          animationDuration: 380,
          tooltip: {
            ...tooltip,
            valueFormatter: (value: unknown) =>
              finiteNumber(value)
                ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
                : EM_DASH,
          },
          grid: {
            left: 116,
            right: 42,
            top: 14,
            bottom: 30,
            containLabel: true,
          },
          xAxis: {
            type: "value",
            name: "%",
            nameTextStyle: axisLabel,
            axisLabel,
            axisLine,
            splitLine,
          },
          yAxis: {
            type: "category",
            data: rows.map((row) => row.name),
            axisLabel: {
              ...axisLabel,
              width: 104,
              overflow: "truncate",
            },
            axisLine: { show: false },
            axisTick: { show: false },
          },
          series: [
            {
              type: "bar",
              barMaxWidth: 12,
              data: rows.map((row) => ({
                value: row.value,
                itemStyle: {
                  color: row.value >= 0 ? COLORS.gold : COLORS.risk,
                  borderColor: row.value >= 0 ? COLORS.gold : COLORS.risk,
                  borderWidth: 1,
                },
              })),
            },
          ],
        };
  return {
    key: "macro-change",
    title: "宏观指标最新变化",
    subtitle: `${macro?.as_of_date ?? "日期未返回"} · ${rows.length} 项 · 后端 change_pct`,
    footnote:
      "直接使用宏观 full analysis 返回的 change_pct；零线用于区分方向。",
    option,
    height: 320,
  };
}

function buildCapabilityStatus(
  theme: MarketChartTheme,
  macro: MacroToolkitAnalysisPayload | undefined,
): MarketFinancialChartSpec {
  const { colors: COLORS, axisLabel, axisLine, splitLine, tooltip } = theme;
  const statuses = ["complete", "degraded", "unavailable"] as const;
  const counts = statuses.map(
    (status) =>
      (macro?.capability_results ?? []).filter((item) => item.status === status)
        .length,
  );
  const total = counts.reduce((sum, value) => sum + value, 0);
  const labels = ["完整", "降级", "不可用"];
  const colors = [COLORS.green, COLORS.gold, COLORS.risk];
  const option: EChartsOption | null =
    total === 0
      ? null
      : {
          animationDuration: 380,
          tooltip: {
            ...tooltip,
            valueFormatter: (value: unknown) =>
              finiteNumber(value) ? `${value} 项` : EM_DASH,
          },
          legend: {
            top: 0,
            left: 0,
            itemWidth: 14,
            itemHeight: 8,
            textStyle: axisLabel,
          },
          grid: {
            left: 70,
            right: 28,
            top: 42,
            bottom: 26,
            containLabel: true,
          },
          xAxis: {
            type: "value",
            min: 0,
            max: total,
            axisLabel,
            axisLine,
            splitLine,
          },
          yAxis: {
            type: "category",
            data: ["能力结果"],
            axisLabel,
            axisLine: { show: false },
            axisTick: { show: false },
          },
          series: counts.map((count, index) => ({
            name: labels[index],
            type: "bar",
            stack: "capability",
            barMaxWidth: 28,
            itemStyle: {
              color: colors[index],
              borderColor: index === 2 ? COLORS.risk : colors[index],
              borderWidth: index === 2 ? 1 : 0,
            },
            label: {
              show: count > 0,
              position: "inside",
              color: COLORS.labelOnAccent,
              fontSize: 10,
              fontWeight: 700,
              formatter: `${count}`,
            },
            data: [count],
          })),
        };
  return {
    key: "capability-status",
    title: "宏观能力状态构成",
    subtitle: `${total} 项 capability_results · 完整/降级/不可用`,
    footnote: "按后端 status 枚举计数；不将降级能力视为完整结果。",
    option,
    height: 240,
  };
}

function buildStrategyPeriodTrend(
  theme: MarketChartTheme,
  strategies: MacroToolkitStrategySummariesPayload | undefined,
): MarketFinancialChartSpec {
  const report = strategies?.shadow_portfolio_report;
  const grouped = new Map<string, Map<string, number>>();
  for (const row of report?.period_returns ?? []) {
    if (!finiteNumber(row.excess_return)) continue;
    const series = grouped.get(row.portfolio_key) ?? new Map<string, number>();
    series.set(row.end_date, row.excess_return * 100);
    grouped.set(row.portfolio_key, series);
  }
  const lines = [...grouped.entries()].map(([name, values]) => ({
    name,
    values,
  }));
  return {
    key: "strategy-period",
    title: "影子组合期间超额收益",
    subtitle: `${report?.as_of_date ?? "日期未返回"} · ${report?.period_returns.length ?? 0} 个期间 · %`,
    footnote: "将后端 excess_return 小数比例转换为百分比展示；不做前端累计。",
    option: buildMultiLineOption(theme, lines, {
      unit: "%",
      decimals: 2,
      scale: true,
    }),
    height: 310,
  };
}

function buildStrategyPortfolioComparison(
  theme: MarketChartTheme,
  strategies: MacroToolkitStrategySummariesPayload | undefined,
): MarketFinancialChartSpec {
  const { colors: COLORS, axisLabel, axisLine, splitLine, tooltip } = theme;
  const portfolios = strategies?.shadow_portfolio_report?.portfolios ?? [];
  const labels = portfolios.map((portfolio) => portfolio.label);
  const measures = [
    { name: "总收益", key: "total_return", color: COLORS.lavender },
    { name: "超额收益", key: "excess_return", color: COLORS.gold },
    { name: "最大回撤", key: "max_drawdown", color: COLORS.risk },
  ] as const;
  const option: EChartsOption | null =
    portfolios.length === 0
      ? null
      : {
          animationDuration: 380,
          color: measures.map((measure) => measure.color),
          tooltip: {
            ...tooltip,
            valueFormatter: (value: unknown) =>
              finiteNumber(value) ? `${value.toFixed(2)}%` : EM_DASH,
          },
          legend: {
            top: 0,
            left: 0,
            itemWidth: 14,
            itemHeight: 8,
            textStyle: axisLabel,
          },
          grid: {
            left: 48,
            right: 24,
            top: 42,
            bottom: 52,
            containLabel: true,
          },
          xAxis: {
            type: "category",
            data: labels,
            axisLabel: {
              ...axisLabel,
              interval: 0,
              width: 84,
              overflow: "truncate",
            },
            axisLine,
            axisTick: { show: false },
          },
          yAxis: {
            type: "value",
            name: "%",
            nameTextStyle: axisLabel,
            axisLabel,
            axisLine,
            splitLine,
          },
          series: measures.map((measure, index) => ({
            name: measure.name,
            type: "bar",
            barMaxWidth: 18,
            itemStyle: {
              color: measure.color,
              borderColor: index === 2 ? COLORS.risk : measure.color,
              borderWidth: index === 2 ? 1 : 0,
            },
            data: portfolios.map((portfolio) => {
              const value = portfolio[measure.key];
              return finiteNumber(value) ? value * 100 : null;
            }),
          })),
        };
  return {
    key: "strategy-portfolio",
    title: "影子组合收益与回撤",
    subtitle: `${portfolios.length} 个组合 · 总收益/超额收益/最大回撤 · %`,
    footnote: "后端小数比例统一换算为百分比；回撤保留后端符号。",
    option,
    height: 300,
  };
}

function countBy<T>(items: T[], key: (item: T) => string) {
  const counts = new Map<string, number>();
  items.forEach((item) => {
    const label = key(item).trim() || "未分类";
    counts.set(label, (counts.get(label) ?? 0) + 1);
  });
  return [...counts.entries()].map(([name, value]) => ({ name, value }));
}

function buildRankedBar(
  theme: MarketChartTheme,
  rows: Array<{ name: string; value: number }>,
  color: string,
): EChartsOption | null {
  const { colors: COLORS, axisLabel, axisLine, splitLine, tooltip } = theme;
  const selected = [...rows]
    .sort((left, right) => right.value - left.value)
    .slice(0, 10)
    .reverse();
  if (selected.length === 0) return null;
  const maxValue = Math.max(...selected.map((row) => row.value), 1);
  return {
    animationDuration: 380,
    tooltip: {
      ...tooltip,
      valueFormatter: (value: unknown) =>
        finiteNumber(value) ? `${value.toLocaleString("zh-CN")} 条` : EM_DASH,
    },
    grid: { left: 102, right: 36, top: 14, bottom: 28, containLabel: true },
    xAxis: {
      type: "value",
      min: 0,
      axisLabel,
      axisLine,
      splitLine,
    },
    yAxis: {
      type: "category",
      data: selected.map((row) => row.name),
      axisLabel: {
        ...axisLabel,
        width: 94,
        overflow: "truncate",
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 13,
        data: selected.map((row) => ({
          value: row.value,
          itemStyle: {
            color,
            opacity: 0.45 + (row.value / maxValue) * 0.55,
            borderRadius: [0, 3, 3, 0],
          },
        })),
        label: {
          show: true,
          position: "right",
          color: COLORS.ink,
          fontSize: 9,
        },
      },
    ],
  };
}

function buildNewsTopicChart(
  theme: MarketChartTheme,
  news: ChoiceNewsEventsPayload | undefined,
): MarketFinancialChartSpec {
  const rows = countBy(
    news?.events ?? [],
    (event) => event.topic_code || event.group_id || "未分类",
  );
  return {
    key: "news-topic",
    title: "新闻主题分布",
    subtitle: `最新 ${news?.events.length ?? 0} 条样本 / 全库 ${news?.total_rows.toLocaleString("zh-CN") ?? EM_DASH} 条`,
    footnote: "按事件 topic_code 计数，展示最新样本 Top 10；不外推为全库占比。",
    option: buildRankedBar(theme, rows, theme.colors.lavender),
    height: 310,
  };
}

function buildNewsDateChart(
  theme: MarketChartTheme,
  news: ChoiceNewsEventsPayload | undefined,
): MarketFinancialChartSpec {
  const { colors: COLORS, axisLabel, axisLine, splitLine, tooltip } = theme;
  const rows = countBy(news?.events ?? [], (event) =>
    event.received_at.slice(0, 10),
  )
    .sort((left, right) => left.name.localeCompare(right.name))
    .slice(-20);
  const option: EChartsOption | null =
    rows.length === 0
      ? null
      : {
          animationDuration: 380,
          tooltip: {
            ...tooltip,
            valueFormatter: (value: unknown) =>
              finiteNumber(value) ? `${value} 条` : EM_DASH,
          },
          grid: {
            left: 44,
            right: 24,
            top: 18,
            bottom: 42,
            containLabel: true,
          },
          xAxis: {
            type: "category",
            data: rows.map((row) => row.name),
            axisLabel: {
              ...axisLabel,
              rotate: rows.length > 10 ? 35 : 0,
              hideOverlap: true,
            },
            axisLine,
            axisTick: { show: false },
          },
          yAxis: {
            type: "value",
            min: 0,
            minInterval: 1,
            name: "条",
            nameTextStyle: axisLabel,
            axisLabel,
            axisLine,
            splitLine,
          },
          series: [
            {
              type: "bar",
              barMaxWidth: 18,
              itemStyle: {
                color: COLORS.contrast,
                borderRadius: [3, 3, 0, 0],
              },
              data: rows.map((row) => row.value),
            },
          ],
        };
  return {
    key: "news-date",
    title: "新闻接收日期分布",
    subtitle: `${rows.length} 个日期 · 最新 ${news?.events.length ?? 0} 条事件样本`,
    footnote: "按 received_at 自然日计数；只描述当前最新样本的时间密度。",
    option,
    height: 310,
  };
}

function buildCatalogVendorChart(
  theme: MarketChartTheme,
  catalog: MacroVendorPayload | undefined,
): MarketFinancialChartSpec {
  const rows = countBy(
    catalog?.series ?? [],
    (series) => series.vendor_name || "未标注",
  );
  return {
    key: "catalog-vendor",
    title: "目录供应商覆盖",
    subtitle: `${catalog?.series.length ?? 0} 条目录序列 · vendor_name`,
    footnote: "按后端目录 vendor_name 计数；同一序列仅计一次。",
    option: buildRankedBar(theme, rows, theme.colors.contrast),
    height: 290,
  };
}

function buildCatalogTierChart(
  theme: MarketChartTheme,
  catalog: MacroVendorPayload | undefined,
): MarketFinancialChartSpec {
  const rows = countBy(
    catalog?.series ?? [],
    (series) => series.refresh_tier || "未标注",
  );
  return {
    key: "catalog-tier",
    title: "刷新层级分布",
    subtitle: `${catalog?.series.length ?? 0} 条目录序列 · refresh_tier`,
    footnote: "stable / fallback / isolated 沿用后端目录定义；未标注单独保留。",
    option: buildRankedBar(theme, rows, theme.colors.gold),
    height: 290,
  };
}

export function buildMarketFinancialChartSections({
  latest,
  rates,
  catalog,
  macro,
  strategies,
  news,
  palette,
}: MarketFinancialChartsInput): MarketFinancialChartSection[] {
  const theme = createMarketChartTheme(palette ?? MARKET_CHART_STATIC_PALETTE);
  return [
    {
      key: "rates",
      kicker: "RATES / LIQUIDITY",
      title: "利率与流动性",
      description: "期限结构回答曲线形态，关键利率趋势回答资金与长端方向。",
      charts: [
        buildYieldCurveChart(theme, rates),
        buildKeyRateTrend(theme, latest, rates),
      ],
    },
    {
      key: "cross",
      kicker: "CROSS ASSET",
      title: "跨资产",
      description:
        "用透明的观察性归一化比较不同单位资产的方向，再看最新一期变动。",
      charts: [
        buildIndexedCrossAsset(theme, latest),
        buildLatestCrossAssetMove(theme, latest),
      ],
    },
    {
      key: "macro",
      kicker: "MACRO SIGNALS",
      title: "宏观信号",
      description: "后端指标变化与能力状态并列，避免把降级结果包装成完整信号。",
      charts: [
        buildMacroIndicatorChange(theme, macro),
        buildCapabilityStatus(theme, macro),
      ],
    },
    {
      key: "strategy",
      kicker: "STRATEGY / RISK",
      title: "策略与风险",
      description: "影子组合期间超额收益、总收益和最大回撤使用同一百分比口径。",
      charts: [
        buildStrategyPeriodTrend(theme, strategies),
        buildStrategyPortfolioComparison(theme, strategies),
      ],
    },
    {
      key: "news",
      kicker: "EVENT FLOW",
      title: "新闻事件",
      description:
        "从最新事件样本查看主题集中度与接收时间密度，同时保留全库总量。",
      charts: [
        buildNewsTopicChart(theme, news),
        buildNewsDateChart(theme, news),
      ],
    },
    {
      key: "coverage",
      kicker: "DATA COVERAGE",
      title: "数据覆盖",
      description: "目录供应商与刷新层级揭示当前数据可用边界和 fallback 暴露。",
      charts: [
        buildCatalogVendorChart(theme, catalog),
        buildCatalogTierChart(theme, catalog),
      ],
    },
  ];
}
