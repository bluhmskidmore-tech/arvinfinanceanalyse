/**
 * 展示层统一色与区块样式 — 供 DataSection、AsyncSection、KpiCard、全局 CSS 等复用。
 * 数值与 `designSystem` / `shellTokens` 对齐，避免页面各自硬编码 hex。
 */
import { designTokens } from "./designSystem";
import { shellTokens } from "./tokens";

const { color, shadow, radius } = designTokens;

export const displayTokens = {
  text: {
    primary: shellTokens.colorTextPrimary,
    secondary: shellTokens.colorTextSecondary,
    muted: shellTokens.colorTextMuted,
    onWarning: color.warning[800],
    onWarningSoft: color.warning[700],
    error: color.danger[600],
  },
  surface: {
    /** 主内容卡片 / 区块底 */
    section: "#ffffff",
    sectionBorder: `1px solid ${color.neutral[200]}`,
    sectionShadow: shadow.card,
    /** 轻微抬升的浅底（骨架屏轨道等） */
    track: color.neutral[200],
    trackAlt: color.neutral[100],
  },
  interactive: {
    retryBorder: `1px solid ${shellTokens.colorBorderSoft}`,
    retryBg: "#ffffff",
    retryText: shellTokens.colorTextPrimary,
  },
  banner: {
    staleBg: color.warning[50],
    staleText: color.warning[800],
    staleBorder: `1px solid ${color.warning[200]}`,
    fallbackBg: color.warning[50],
    fallbackText: color.warning[700],
    fallbackBorder: `1px solid ${color.warning[200]}`,
  },
  statusPill: {
    normal: { bg: color.success[50], fg: color.success[600], border: color.success[200] },
    caution: { bg: color.warning[50], fg: color.warning[600], border: color.warning[200] },
    warning: { bg: color.warning[50], fg: color.warning[700], border: color.warning[300] },
    danger: { bg: color.danger[50], fg: color.danger[600], border: color.danger[200] },
  },
  kpi: {
    label: color.neutral[600],
    unit: color.neutral[500],
    detail: color.neutral[500],
    valueDefault: color.neutral[900],
    valuePositive: color.semantic.profit,
    valueNegative: color.semantic.loss,
    valueWarning: color.warning[600],
    sparklineStroke: color.neutral[400],
    cardBg: "#ffffff",
    cardBorder: `1px solid ${color.neutral[200]}`,
    iconBg: color.neutral[100],
    iconFg: color.neutral[600],
    cardShadow:
      "0 1px 2px rgba(31, 41, 55, 0.06), 0 4px 12px rgba(31, 41, 55, 0.05)",
  },
  /** 数据源模式角标：真实链路 / Mock */
  apiMode: {
    realForeground: color.semantic.profit,
    mockForeground: color.info[500],
  },
  hover: {
    border: color.neutral[300],
    shadow: "0 4px 12px rgba(22, 35, 46, 0.06)",
  },
  radius: {
    /** 与 DataSection / AsyncSection 历史圆角一致 */
    section: 20,
    control: radius.md,
  },
} as const;
