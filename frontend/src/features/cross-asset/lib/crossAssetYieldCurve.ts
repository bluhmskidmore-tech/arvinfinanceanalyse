/**
 * Yield curve (full tenor) builder for the cross-asset workbench.
 *
 * Maps Choice macro series (GET /ui/macro/choice-series/latest → result.series[])
 * onto the fixed 9-tenor CCDC yield-curve families:
 *   国债 / 国开债(政策性金融债) / AAA 企业债 / AA 企业债
 *
 * Family series_name conventions differ:
 *   - 国债:   中债国债到期收益率:10年            (colon-separated)
 *   - 国开债: 中债政策性金融债到期收益率(国开行)10年  (no colon)
 *   - 企业债: 中债企业债到期收益率(AAA):10年 / (AA):10年
 *
 * Points may carry mixed trade_date values (e.g. 10Y fresh, others stale);
 * the builder surfaces earliest/latest/mixed flags for the panel hint.
 *
 * Pure and stateless; no side effects.
 */

import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import { designTokens, ibTokens } from "../../../theme/designSystem";

import {
  resolveCrossAssetChartPalette,
  type CrossAssetChartPalette,
  type CrossAssetChartTheme,
} from "./crossAssetChartTheme";

/** Fixed tenor order on the x axis (CCDC quote convention). */
export const YIELD_CURVE_TENORS = [
  "3个月",
  "6个月",
  "1年",
  "2年",
  "3年",
  "5年",
  "7年",
  "10年",
  "30年",
] as const;

/** Compact tenor labels for the category axis. */
export const YIELD_CURVE_TENOR_LABELS = [
  "3M",
  "6M",
  "1Y",
  "2Y",
  "3Y",
  "5Y",
  "7Y",
  "10Y",
  "30Y",
] as const;

export type YieldCurveFamilyKey = "gov" | "policy" | "aaa" | "aa";

export type YieldCurveFamily = {
  key: YieldCurveFamilyKey;
  name: string;
  /** Yield in %, null for tenors missing upstream. */
  data: (number | null)[];
  /** Per-tenor trade_date of the matched point; "" when the tenor is missing. */
  dates: string[];
  pointCount: number;
};

export type YieldCurveSeriesResult = {
  labels: string[];
  families: YieldCurveFamily[];
  /** True when matched points carry more than one distinct trade_date. */
  mixedDates: boolean;
  latestDate: string | null;
  earliestDate: string | null;
};

const FAMILY_DEFS: Array<{
  key: YieldCurveFamilyKey;
  name: string;
  seriesName: (tenor: string) => string;
}> = [
  { key: "gov", name: "国债", seriesName: (tenor) => `中债国债到期收益率:${tenor}` },
  { key: "policy", name: "国开债", seriesName: (tenor) => `中债政策性金融债到期收益率(国开行)${tenor}` },
  { key: "aaa", name: "AAA 企业债", seriesName: (tenor) => `中债企业债到期收益率(AAA):${tenor}` },
  { key: "aa", name: "AA 企业债", seriesName: (tenor) => `中债企业债到期收益率(AA):${tenor}` },
];

/**
 * Build full-tenor yield curve families from Choice latest macro rows.
 * Exact series_name match per tenor; missing tenors stay null.
 * Values are already quoted in % (unit === "%"), used verbatim.
 */
export function buildYieldCurveSeries(series: ChoiceMacroLatestPoint[]): YieldCurveSeriesResult {
  const byName = new Map<string, ChoiceMacroLatestPoint>();
  for (const row of series ?? []) {
    if (!row || typeof row.series_name !== "string") continue;
    // Last occurrence wins on duplicate names.
    byName.set(row.series_name, row);
  }

  const families: YieldCurveFamily[] = [];
  const allDates: string[] = [];

  for (const def of FAMILY_DEFS) {
    const data: (number | null)[] = [];
    const dates: string[] = [];
    let pointCount = 0;

    for (const tenor of YIELD_CURVE_TENORS) {
      const row = byName.get(def.seriesName(tenor));
      const value = row?.value_numeric;
      if (row && typeof value === "number" && Number.isFinite(value)) {
        data.push(value);
        const date = typeof row.trade_date === "string" ? row.trade_date : "";
        dates.push(date);
        if (date) allDates.push(date);
        pointCount += 1;
      } else {
        data.push(null);
        dates.push("");
      }
    }

    if (pointCount > 0) {
      families.push({ key: def.key, name: def.name, data, dates, pointCount });
    }
  }

  const sortedDates = [...new Set(allDates)].sort((a, b) => a.localeCompare(b));
  return {
    labels: [...YIELD_CURVE_TENOR_LABELS],
    families,
    mixedDates: sortedDates.length > 1,
    latestDate: sortedDates[sortedDates.length - 1] ?? null,
    earliestDate: sortedDates[0] ?? null,
  };
}

/* ─── ECharts option ─────────────────────────────────────── */

const ib = ibTokens.color;
const fs = designTokens.fontSize;

/** IB light palette, aligned with the page trend chart token set. */
const FAMILY_COLORS: Record<YieldCurveFamilyKey, string> = {
  gov: ib.accent,
  policy: designTokens.color.primary[700],
  aaa: ib.gold,
  aa: designTokens.color.warm.slateBlue,
};

/** Terminal family colors come from the palette categorical ladder (blue/green/amber/red). */
function familyColorsFor(theme: CrossAssetChartTheme, palette: CrossAssetChartPalette): Record<YieldCurveFamilyKey, string> {
  if (theme !== "terminal") {
    return FAMILY_COLORS;
  }
  return {
    gov: palette.series[0]!,
    policy: palette.series[1]!,
    aaa: palette.series[2]!,
    aa: palette.series[3]!,
  };
}

/** 国债为无风险基准，线宽略粗。 */
const FAMILY_LINE_WIDTH: Record<YieldCurveFamilyKey, number> = {
  gov: 3,
  policy: 2,
  aaa: 2,
  aa: 2,
};

function compactPointDate(date: string): string {
  return date.length >= 10 ? date.slice(5) : date;
}

/**
 * Build the ECharts option for the full-tenor yield curve panel.
 * Returns null when no family has any point (panel shows the empty state).
 */
export function buildYieldCurveOption(
  curves: YieldCurveSeriesResult,
  theme: CrossAssetChartTheme = "light",
): EChartsOption | null {
  if (curves.families.length === 0) {
    return null;
  }

  const palette = resolveCrossAssetChartPalette(theme);
  const familyColors = familyColorsFor(theme, palette);
  const familyByName = new Map(curves.families.map((family) => [family.name, family]));

  const series = curves.families.map((family) => {
    const color = familyColors[family.key];
    const width = FAMILY_LINE_WIDTH[family.key];
    return {
      name: family.name,
      type: "line" as const,
      smooth: 0.2,
      showSymbol: true,
      symbol: "circle",
      symbolSize: 5,
      connectNulls: true,
      data: family.data,
      lineStyle: { width, color },
      itemStyle: { color },
      emphasis: {
        focus: "series" as const,
        lineStyle: { width: width + 1.5 },
        itemStyle: { borderWidth: 2, borderColor: palette.emphasisBorder },
      },
      blur: {
        lineStyle: { width: 1, opacity: 0.25 },
        itemStyle: { opacity: 0.2 },
      },
    };
  });

  return {
    color: curves.families.map((family) => familyColors[family.key]),
    animation: true,
    animationDuration: 500,
    animationEasing: "cubicOut",
    grid: { left: 12, right: 20, top: 40, bottom: 56, containLabel: true },
    legend: {
      type: "scroll",
      orient: "horizontal",
      bottom: 0,
      left: "center",
      width: "94%",
      itemWidth: 20,
      itemHeight: 3,
      itemGap: 14,
      icon: "roundRect",
      textStyle: {
        fontSize: fs[12],
        color: palette.textSoft,
        fontWeight: 500 as const,
        padding: [0, 0, 0, 2],
      },
      inactiveColor: palette.legendInactive,
      selector: false,
    },
    tooltip: {
      trigger: "axis",
      confine: true,
      order: "valueDesc",
      extraCssText: [
        "text-align: left",
        "border-radius: 2px",
        "box-shadow: var(--ib-shadow)",
        "padding: 10px 14px",
      ].join(";"),
      axisPointer: {
        type: "line",
        lineStyle: { color: palette.axisLine, width: 1, type: "dashed" },
        label: {
          show: true,
          backgroundColor: palette.axisPointerLabelBg,
          fontSize: fs[11],
          color: palette.axisPointerLabelText,
          padding: [4, 8],
          borderRadius: 2,
        },
      },
      backgroundColor: palette.tooltipBg,
      borderColor: palette.tooltipBorder,
      borderWidth: 1,
      textStyle: { fontSize: fs[12], color: palette.text },
      formatter: (raw: unknown) => {
        if (!Array.isArray(raw) || raw.length === 0) {
          return "";
        }
        const first = raw[0] as { axisValueLabel?: string; axisValue?: string };
        const tenor = first.axisValueLabel ?? first.axisValue ?? "";
        const header = `<div style="font-weight:700;font-size:13px;margin-bottom:6px;color:${palette.text}">${tenor}</div>`;
        const rows = (
          raw as Array<{ marker?: string; seriesName?: string; dataIndex?: number; value?: unknown }>
        ).map((p) => {
          const v = p.value;
          const str =
            v == null || (typeof v === "number" && Number.isNaN(v))
              ? "—"
              : typeof v === "number"
                ? `${v.toFixed(4)}%`
                : String(v);
          const family = p.seriesName ? familyByName.get(p.seriesName) : undefined;
          const date =
            family && typeof p.dataIndex === "number" ? family.dates[p.dataIndex] ?? "" : "";
          const dateLabel = date ? ` <span style="color:${palette.textMuted}">(${compactPointDate(date)})</span>` : "";
          return `<div style="display:flex;align-items:center;gap:6px;line-height:1.7;font-size:12px">${p.marker ?? ""}<span style="flex:1;color:${palette.textSoft}">${p.seriesName ?? ""}</span><span style="font-weight:600;font-variant-numeric:tabular-nums;color:${palette.text}">${str}</span>${dateLabel}</div>`;
        });
        return header + rows.join("");
      },
    },
    xAxis: {
      type: "category",
      data: curves.labels,
      boundaryGap: false,
      axisLabel: { fontSize: fs[11], color: palette.textMuted, margin: 12 },
      axisLine: { lineStyle: { color: palette.axisLine, width: 1 } },
      axisTick: { alignWithLabel: true, lineStyle: { color: palette.axisLine }, length: 4 },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      scale: true,
      name: "单位：%",
      nameTextStyle: { fontSize: fs[11], color: palette.textMuted, align: "left" as const },
      nameGap: 8,
      axisLabel: {
        fontSize: fs[11],
        color: palette.textMuted,
        formatter: (v: number) => v.toFixed(2),
      },
      splitLine: { lineStyle: { color: palette.splitLine, width: 1, type: "dashed" as const } },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series,
  };
}
