import type { CSSProperties } from "react";

import { mossChartCategoricalPalette } from "../../../components/charts/chartTheme";
import { designTokens, dhApiTokens, ibTokens } from "../../../theme/designSystem";
import type {
  BondAnalyticsPromotionDestination,
  BondAnalyticsTruthTone,
} from "../lib/bondAnalyticsOverviewModel";

const { color, fontSize, shadow } = designTokens;

export const IB_ACCENT_BAR = "var(--ib-accent)";
export const DONUT_CHART_COLORS = mossChartCategoricalPalette.slice(0, 5);
export const DISTRIBUTION_CHART_COLORS = [...DONUT_CHART_COLORS, ibTokens.color.gold];
export const cardBodyStyle = { padding: 14 } as const;

export const PERIOD_OPTIONS = [
  { value: "MoM", label: "月度环比" },
  { value: "YTD", label: "年初至今" },
  { value: "TTM", label: "近12个月" },
];

export const BOND_ANALYTICS_ASSET_CLASS_FILTER_OPTIONS = [
  { value: "all", label: "全部资产类" },
  { value: "rate", label: "利率债" },
  { value: "credit", label: "信用债" },
] as const;

export const BOND_ANALYTICS_ACCOUNTING_CLASS_FILTER_OPTIONS = [
  { value: "all", label: "全部口径" },
  { value: "AC", label: "AC" },
  { value: "OCI", label: "OCI" },
  { value: "TPL", label: "TPL" },
] as const;

export const BOND_ANALYTICS_SCENARIO_SET_OPTIONS = [
  { value: "standard", label: "标准情景" },
  { value: "custom", label: "自定义情景" },
] as const;

export const BOND_ANALYTICS_SPREAD_SCENARIO_PRESETS = [
  { value: "10,25,50", label: "10 / 25 / 50 bp" },
  { value: "25,50,100", label: "25 / 50 / 100 bp" },
] as const;

export const BORDER = color.neutral[100];
export const SHADOW = shadow.card;

export const EYEBROW: CSSProperties = {
  fontSize: fontSize[11],
  color: "var(--dh-api-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.14em",
  fontWeight: 700,
};

export const FIELD: CSSProperties = {
  marginBottom: 6,
  color: color.neutral[700],
  fontSize: fontSize[11],
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  fontWeight: 700,
};

export function panelStyle(background?: string): CSSProperties {
  // Shape Lock: bond-analytics cockpit is dark-terminal (--dh-api-radius = 6px).
  return { borderRadius: dhApiTokens.radius, border: "none", boxShadow: SHADOW, background };
}

/** 语义 tone 面（DOM style 消费）：深色页走 --dh-api-* 语义链的暗底软色（DESIGN.md §2.2）。 */
export function toneColor(tone: BondAnalyticsTruthTone) {
  if (tone === "success") {
    return {
      background: "color-mix(in srgb, var(--dh-api-green) 12%, var(--dh-api-panel))",
      color: "var(--dh-api-green)",
      borderColor: "color-mix(in srgb, var(--dh-api-green) 30%, transparent)",
      accent: "var(--dh-api-green)",
    };
  }
  if (tone === "warning") {
    return {
      background: "color-mix(in srgb, var(--dh-api-amber) 12%, var(--dh-api-panel))",
      color: "var(--dh-api-amber)",
      borderColor: "color-mix(in srgb, var(--dh-api-amber) 30%, transparent)",
      accent: "var(--dh-api-amber)",
    };
  }
  if (tone === "danger") {
    return {
      background: "color-mix(in srgb, var(--dh-api-red) 12%, var(--dh-api-panel))",
      color: "var(--dh-api-red)",
      borderColor: "color-mix(in srgb, var(--dh-api-red) 30%, transparent)",
      accent: "var(--dh-api-red)",
    };
  }
  return {
    background: "var(--dh-api-panel-2)",
    color: "var(--dh-api-soft)",
    borderColor: "var(--dh-api-line-soft)",
    accent: "var(--dh-api-muted)",
  };
}

export function readinessTagColor(statusLabel: string) {
  if (statusLabel === "eligible") return "success";
  if (statusLabel === "request-error") return "error";
  if (statusLabel === "placeholder-blocked" || statusLabel === "warning") return "warning";
  return "default";
}

/** 模块就绪状态面（DOM style 消费）：同 toneColor 的深色语义链。 */
export function readinessSurface(statusLabel: string) {
  if (statusLabel === "eligible") {
    return {
      background: "color-mix(in srgb, var(--dh-api-green) 12%, var(--dh-api-panel))",
      borderColor: "color-mix(in srgb, var(--dh-api-green) 30%, transparent)",
      accent: "var(--dh-api-green)",
      text: "var(--dh-api-green)",
    };
  }
  if (statusLabel === "request-error") {
    return {
      background: "color-mix(in srgb, var(--dh-api-red) 12%, var(--dh-api-panel))",
      borderColor: "color-mix(in srgb, var(--dh-api-red) 30%, transparent)",
      accent: "var(--dh-api-red)",
      text: "var(--dh-api-red)",
    };
  }
  if (statusLabel === "placeholder-blocked" || statusLabel === "warning") {
    return {
      background: "color-mix(in srgb, var(--dh-api-amber) 12%, var(--dh-api-panel))",
      borderColor: "color-mix(in srgb, var(--dh-api-amber) 30%, transparent)",
      accent: "var(--dh-api-amber)",
      text: "var(--dh-api-amber)",
    };
  }
  return {
    background: "var(--dh-api-panel-2)",
    borderColor: "var(--dh-api-line-soft)",
    accent: "var(--dh-api-muted)",
    text: "var(--dh-api-soft)",
  };
}

export function promotionLabel(destination: BondAnalyticsPromotionDestination) {
  if (destination === "headline") return "可进入头条";
  if (destination === "main-rail") return "可进入主栏";
  return "仅就绪/下钻";
}

export function readinessStatusLabel(statusLabel: string) {
  const labels: Record<string, string> = {
    loading: "加载中",
    "request-error": "暂不可用",
    pending: "待加载",
    eligible: "可提升",
    "placeholder-blocked": "占位阻止",
    warning: "预警",
    "detail-first": "先看明细",
    "detail-surface": "明细面板",
  };
  return labels[statusLabel] ?? statusLabel;
}
