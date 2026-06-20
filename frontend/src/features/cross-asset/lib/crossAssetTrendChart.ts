import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";

import { crossAssetTrendLines, type ResolvedCrossAssetKpi, type CrossAssetKpiFormat } from "./crossAssetKpiModel";

/** Must match section copy on cross-asset ("近 N 日"). */
export const CROSS_ASSET_TREND_WINDOW_DAYS = 20;

const { color: c } = designTokens;

/**
 * Hand-picked palette: maximise hue separation across 12 series.
 * Avoids adjacent hues that collapse on projectors / f.lux screens.
 */
const CHART_COLORS = [
  "#1850a1", // deep institutional blue  (10Y国债)
  "#e85d3a", // warm vermilion            (10Y美债)
  "#2d8a5e", // forest green              (中美10Y利差)
  "#d97706", // amber                     (银拆7D)
  "#8b5cf6", // vivid purple              (金融条件指数)
  "#0891b2", // teal-cyan                 (沪深300市盈率)
  "#db2777", // deep pink                 (沪深300前十)
  "#475569", // slate grey                (沪深300前五)
  "#059669", // emerald                   (布油)
  "#b45309", // burnt sienna              (钢)
  "#6366f1", // indigo                    (USD/CNY)
  "#0369a1", // ocean blue                (spare)
];

/**
 * Stagger dash patterns so even colour-blind viewers can tell series apart.
 * First 4 solid, next 4 dashed, next 4 dot-dash.
 */
const DASH_PATTERNS: (number[] | undefined)[] = [
  undefined,            // solid
  undefined,            // solid
  undefined,            // solid
  undefined,            // solid
  [6, 4],               // short dash
  [6, 4],               // short dash
  [10, 3],              // long dash
  [10, 3],              // long dash
  [3, 3],               // dotted
  [3, 3],               // dotted
  [10, 3, 3, 3],        // dash-dot
  [10, 3, 3, 3],        // dash-dot
];

/**
 * Last observation carried forward on the **shared** date index.
 * US/CN/商品发布与休市日不同，轴上无值的日期并非"跳空"，不 LOCF 就会整段 `null` + connectNulls=false 变成碎线、不可读。
 */
export function locfForward(values: (number | null)[]): (number | null)[] {
  let last: number | null = null;
  return values.map((v) => {
    if (typeof v === "number" && !Number.isNaN(v)) {
      last = v;
    }
    return last;
  });
}

function normalizedAligned(values: (number | null)[]): (number | null)[] {
  const first = values.find((v) => v != null && !Number.isNaN(v));
  if (first == null || first === 0) {
    return values.map(() => (values.some((v) => v != null) ? 100 : null));
  }
  return values.map((v) => {
    if (v == null || Number.isNaN(v)) {
      return null;
    }
    return (v / first) * 100;
  });
}

export function buildCrossAssetTrendOption(series: ChoiceMacroLatestPoint[]): EChartsOption | null {
  const lineInputs = crossAssetTrendLines(series);
  if (lineInputs.length === 0) {
    return null;
  }

  const dates = new Set<string>();
  for (const line of lineInputs) {
    for (const d of line.dates) {
      dates.add(d);
    }
  }
  const allSorted = [...dates].sort((a, b) => a.localeCompare(b));
  const axisDates =
    allSorted.length > CROSS_ASSET_TREND_WINDOW_DAYS
      ? allSorted.slice(-CROSS_ASSET_TREND_WINDOW_DAYS)
      : allSorted;

  if (axisDates.length === 0) {
    return null;
  }

  const echartsSeries = lineInputs.map((line, idx) => {
    const byDate = new Map(line.dates.map((d, i) => [d, line.values[i]]));
    const aligned = axisDates.map((d) => byDate.get(d) ?? null);
    const leveled = locfForward(aligned);
    const display = normalizedAligned(leveled);
    const color = CHART_COLORS[idx % CHART_COLORS.length];
    const dash = DASH_PATTERNS[idx % DASH_PATTERNS.length];
    return {
      name: line.name,
      type: "line" as const,
      smooth: 0.15,
      showSymbol: false,
      connectNulls: true,
      symbol: "circle",
      symbolSize: 6,
      lineStyle: {
        width: 2,
        color,
        type: dash ? (dash as number[]) : ("solid" as const),
      },
      itemStyle: { color },
      data: display,
      emphasis: {
        focus: "series" as const,
        lineStyle: { width: 3.5 },
        itemStyle: { borderWidth: 2, borderColor: "#fff" },
      },
      blur: {
        lineStyle: { width: 1, opacity: 0.25 },
        itemStyle: { opacity: 0.2 },
      },
    };
  });

  const fs = designTokens.fontSize;
  return {
    color: CHART_COLORS,
    animation: true,
    animationDuration: 600,
    animationEasing: "cubicOut",
    grid: {
      left: 12,
      right: 20,
      top: 40,
      bottom: 120,
      containLabel: true,
    },
    legend: {
      type: "scroll",
      orient: "horizontal",
      bottom: 0,
      left: "center",
      width: "94%",
      itemWidth: 20,
      itemHeight: 3,
      itemGap: 14,
      pageIconSize: 12,
      pageButtonGap: 8,
      pageTextStyle: { fontSize: fs[12], color: c.neutral[600] },
      textStyle: {
        fontSize: fs[12],
        color: c.neutral[700],
        fontWeight: 500 as const,
        padding: [0, 0, 0, 2],
      },
      padding: [8, 8, 12, 8],
      icon: "roundRect",
      inactiveColor: c.neutral[300],
      inactiveBorderColor: "transparent",
      selector: false,
    },
    tooltip: {
      trigger: "axis",
      confine: true,
      order: "valueDesc",
      enterable: false,
      extraCssText: [
        "max-height: min(50vh, 320px)",
        "overflow-y: auto",
        "white-space: pre-line",
        "text-align: left",
        "border-radius: 8px",
        "box-shadow: 0 8px 24px rgba(15,23,42,0.12), 0 2px 6px rgba(15,23,42,0.08)",
        "backdrop-filter: blur(8px)",
        "padding: 10px 14px",
      ].join(";"),
      axisPointer: {
        type: "line",
        lineStyle: {
          color: c.neutral[400],
          width: 1,
          type: "dashed",
        },
        label: {
          show: true,
          backgroundColor: c.neutral[700],
          fontSize: fs[11],
          color: "#fff",
          padding: [4, 8],
          borderRadius: 4,
        },
      },
      backgroundColor: "rgba(255,255,255,0.96)",
      borderColor: c.neutral[200],
      borderWidth: 1,
      textStyle: { fontSize: fs[12], color: c.neutral[800] },
      position(point, _params, _dom, _rect, size) {
        if (!size?.viewSize) {
          return point;
        }
        const margin = 8;
        const tooltipWidth = Math.min(288, Math.max(0, size.viewSize[0] - margin * 2));
        const maxX = Math.max(margin, size.viewSize[0] - tooltipWidth - margin);
        const x = Math.min(Math.max(margin, point[0] - tooltipWidth / 2), maxX);
        return [x, margin];
      },
      formatter: (raw: unknown) => {
        if (!Array.isArray(raw) || raw.length === 0) {
          return "";
        }
        const first = raw[0] as { axisValueLabel?: string; axisValue?: string };
        const date = first.axisValueLabel ?? first.axisValue ?? "";
        const header = `<div style="font-weight:700;font-size:13px;margin-bottom:6px;color:${c.neutral[900]}">${date}</div>`;
        const rows = (raw as Array<{ marker?: string; seriesName?: string; value?: unknown }>).map((p) => {
          const v = p.value;
          const str =
            v == null || (typeof v === "number" && Number.isNaN(v))
              ? "—"
              : typeof v === "number"
                ? v.toFixed(1)
                : String(v);
          return `<div style="display:flex;align-items:center;gap:6px;line-height:1.7;font-size:12px">${p.marker ?? ""}<span style="flex:1;color:${c.neutral[700]}">${p.seriesName ?? ""}</span><span style="font-weight:600;font-variant-numeric:tabular-nums;color:${c.neutral[900]}">${str}</span></div>`;
        });
        return header + rows.join("");
      },
    },
    xAxis: {
      type: "category",
      data: axisDates,
      boundaryGap: false,
      axisLabel: {
        fontSize: fs[11],
        color: c.neutral[500],
        hideOverlap: true,
        margin: 12,
        formatter: (v: string) => {
          // Show MM-DD for cleaner x axis; full YYYY-MM-DD in tooltip
          return v.slice(5);
        },
      },
      axisLine: {
        lineStyle: { color: c.neutral[200], width: 1 },
      },
      axisTick: {
        alignWithLabel: true,
        lineStyle: { color: c.neutral[200] },
        length: 4,
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: {
        fontSize: fs[11],
        color: c.neutral[500],
        formatter: (v: number) => v.toFixed(0),
      },
      splitLine: {
        lineStyle: {
          color: c.neutral[100],
          width: 1,
          type: "dashed" as const,
        },
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    dataZoom: [
      {
        type: "inside",
        xAxisIndex: 0,
        filterMode: "none",
        zoomOnMouseWheel: false,
        moveOnMouseMove: false,
        moveOnMouseWheel: false,
      },
    ],
    series: echartsSeries,
  };
}

/* ─── Trend summary (one-line analytical headline) ───────── */

export type TrendSummaryTone = "friendly" | "tight" | "mixed" | "neutral";

export interface TrendSignalItem {
  label: string;
  description: string;
  tone: "positive" | "negative" | "neutral";
}

export interface TrendSummary {
  /** One-line headline, e.g. "国债利率小幅下行，资金面偏松，股债同涨，整体环境偏友好" */
  headline: string;
  tone: TrendSummaryTone;
  signals: TrendSignalItem[];
}

type SparkDir = "rising" | "falling" | "flat";

/**
 * Compute the recent direction from a sparkline.
 * Uses format-aware thresholds so rates (percent) and indices (plain) don't share the same sensitivity.
 */
function sparklineDirection(
  sparkline: number[],
  format: CrossAssetKpiFormat,
  lookback = 5,
): { direction: SparkDir; absChange: number } {
  if (sparkline.length < 2) {
    return { direction: "flat", absChange: 0 };
  }
  const start = Math.max(0, sparkline.length - lookback);
  const slice = sparkline.slice(start);
  const first = slice[0];
  const last = slice[slice.length - 1];
  const change = last - first;
  const absChange = Math.abs(change);

  // Format-aware significance thresholds
  let significant = false;
  switch (format) {
    case "percent": // yield in % — 3bp = 0.03
      significant = absChange > 0.03;
      break;
    case "bp": // spread in bp
      significant = absChange > 3;
      break;
    case "fx": // exchange rate
      significant = absChange > 0.005;
      break;
    case "plain":
    case "index":
    default:
      significant = first > 0 ? absChange / first > 0.005 : false; // 0.5%
      break;
  }

  if (!significant) {
    return { direction: "flat", absChange };
  }
  return { direction: change > 0 ? "rising" : "falling", absChange };
}

function dirLabel(dir: SparkDir, upWord: string, downWord: string, flatWord: string): string {
  if (dir === "rising") return upWord;
  if (dir === "falling") return downWord;
  return flatWord;
}

/**
 * Build an automatic one-line analytical summary from resolved KPI sparklines.
 * Covers: bond direction, liquidity, stock-bond relationship, external transmission, commodity signal.
 */
export function buildCrossAssetTrendSummary(kpis: ResolvedCrossAssetKpi[]): TrendSummary | null {
  if (kpis.length === 0) {
    return null;
  }

  const byKey = new Map(kpis.map((k) => [k.key, k]));

  function kpiDir(key: string): { direction: SparkDir; kpi: ResolvedCrossAssetKpi } | null {
    const kpi = byKey.get(key);
    if (!kpi || kpi.sparkline.length < 2) return null;
    const { direction } = sparklineDirection(kpi.sparkline, kpi.format);
    return { direction, kpi };
  }

  const bond = kpiDir("cn_gov_10y");
  const usBond = kpiDir("us_gov_10y");
  const money = kpiDir("money_market_7d");
  const equity = kpiDir("financial_conditions");
  const brent = kpiDir("brent");
  const steel = kpiDir("steel");
  const usdcny = kpiDir("usdcny");

  const parts: string[] = [];
  const signals: TrendSignalItem[] = [];

  // ① Bond yield direction
  if (bond) {
    const chg = bond.kpi.changeLabel;
    const desc = dirLabel(bond.direction, `利率上行(${chg})`, `利率下行(${chg})`, "利率持平");
    parts.push(desc);
    signals.push({
      label: "国债",
      description: desc,
      // Yield falling = good for bond holders
      tone: bond.direction === "falling" ? "positive" : bond.direction === "rising" ? "negative" : "neutral",
    });
  }

  // ② Liquidity
  if (money) {
    const desc = dirLabel(money.direction, "资金面趋紧", "资金面偏松", "资金面平稳");
    parts.push(desc);
    signals.push({
      label: "流动性",
      description: desc,
      tone: money.direction === "falling" ? "positive" : money.direction === "rising" ? "negative" : "neutral",
    });
  }

  // ③ Stock-bond relationship
  if (bond && equity) {
    let desc: string;
    let tone: TrendSignalItem["tone"] = "neutral";
    // Note: bond yield falling = bond price rising
    if (equity.direction === "rising" && bond.direction === "falling") {
      desc = "股涨债涨(流动性驱动)";
      tone = "positive";
    } else if (equity.direction === "rising" && bond.direction === "rising") {
      desc = "股涨债跌(风险偏好转暖)";
      tone = "neutral";
    } else if (equity.direction === "falling" && bond.direction === "falling") {
      desc = "股跌债涨(避险模式)";
      tone = "neutral";
    } else if (equity.direction === "falling" && bond.direction === "rising") {
      desc = "股债双杀";
      tone = "negative";
    } else {
      desc = "股债分化不明显";
    }
    parts.push(desc);
    signals.push({ label: "股债关系", description: desc, tone });
  }

  // ④ External: US rates
  if (usBond && usBond.direction !== "flat") {
    const desc = dirLabel(usBond.direction, "美债利率上行", "美债利率回落", "");
    if (desc) {
      // Check if CN bond follows US bond
      if (bond && bond.direction === usBond.direction) {
        parts.push(`${desc}·内外联动`);
      } else if (bond && bond.direction !== "flat") {
        parts.push(`${desc}·内外脱钩`);
      } else {
        parts.push(desc);
      }
      signals.push({
        label: "外部",
        description: desc,
        tone: usBond.direction === "falling" ? "positive" : "negative",
      });
    }
  }

  // ⑤ Commodity / inflation
  if (brent && steel && brent.direction !== "flat" && steel.direction !== "flat") {
    if (brent.direction === "rising" && steel.direction === "rising") {
      parts.push("商品走强·通胀预期升温");
      signals.push({ label: "通胀", description: "商品走强·通胀预期升温", tone: "negative" });
    } else if (brent.direction === "falling" && steel.direction === "falling") {
      parts.push("商品走弱·通胀预期回落");
      signals.push({ label: "通胀", description: "商品走弱·通胀预期回落", tone: "positive" });
    }
  }

  // ⑥ FX pressure
  if (usdcny && usdcny.direction !== "flat") {
    const desc = dirLabel(usdcny.direction, "人民币走弱", "人民币走强", "");
    if (desc) {
      signals.push({
        label: "汇率",
        description: desc,
        tone: usdcny.direction === "falling" ? "positive" : "negative",
      });
    }
  }

  // Overall tone
  const bondFriendly = bond ? bond.direction === "falling" : true;
  const liquidityFriendly = money ? money.direction !== "rising" : true;
  const externalFriendly = usBond ? usBond.direction !== "rising" : true;

  let tone: TrendSummaryTone;
  let toneLabel: string;
  if (bondFriendly && liquidityFriendly && externalFriendly) {
    tone = "friendly";
    toneLabel = "整体环境偏友好";
  } else if (!bondFriendly && !liquidityFriendly) {
    tone = "tight";
    toneLabel = "整体环境偏紧";
  } else if (parts.length === 0) {
    tone = "neutral";
    toneLabel = "各资产波动不大";
  } else {
    tone = "mixed";
    toneLabel = "环境信号分化";
  }
  parts.push(toneLabel);

  return {
    headline: "近期走势：" + parts.join("，") + "。",
    tone,
    signals,
  };
}
