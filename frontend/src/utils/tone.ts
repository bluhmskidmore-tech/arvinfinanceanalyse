/**
 * Single source of truth for tone (semantic color) across governed pages.
 *
 * Components MUST NOT define local tone/color maps. Pages that need a custom
 * palette must add it here under a new exported const, never inline inside a
 * component file.
 */
import type { Numeric } from "../api/contracts";
import { designTokens } from "../theme/designSystem";

export type Tone = "positive" | "neutral" | "warning" | "negative";

/** 浅色语义色镜像；深色 canvas / 图表使用 nocturneTokens 或 nocturneChartTheme。 */
export const TONE_COLOR: Record<Tone, string> = {
  positive: designTokens.color.semantic.profit,
  neutral: designTokens.color.neutral[600],
  warning: designTokens.color.warning[700],
  negative: designTokens.color.semantic.loss,
};

/**
 * IB 浅色及既有兼容消费者的 CSS 变量入口，仅供 DOM style / CSS 使用。
 * canonical 深色 boundary 已将 --ib-* 映射为 Nocturne；深色路由新代码仍统一
 * 使用 TONE_DH_CSS_VAR，直接表达深色主题语义，见 DESIGN.md §4.1。
 * canvas / ECharts 不使用 CSS 变量，按主题选择对应的 TS 镜像。
 */
export const TONE_CSS_VAR: Record<Tone, string> = {
  positive: "var(--ib-up)",
  neutral: "var(--ib-ink-muted)",
  warning: "var(--ib-warn)",
  negative: "var(--ib-down)",
};

/**
 * 深色路由的 DOM tone 入口。已登记的 Nocturne scope 通过 --dh-api-* 解析
 * 为 --nct-* 色板；未登记 scope 仍使用既有兼容回退。
 * 业务方向如何映射 tone 遵守 DESIGN.md §4.1；本表不推导业务含义。
 */
export const TONE_DH_CSS_VAR: Record<Tone, string> = {
  positive: "var(--dh-api-green)",
  neutral: "var(--dh-api-muted)",
  warning: "var(--dh-api-amber)",
  negative: "var(--dh-api-red)",
};

/**
 * Derive a tone from a Numeric's sign. Returns ``neutral`` for ``raw=null``,
 * zero, or ``sign_aware=false`` values (the latter are absolute-valued by
 * design and must not be colored by sign).
 */
export function toneFromNumeric(n: Numeric): Tone {
  if (!n.sign_aware) return "neutral";
  if (n.raw === null) return "neutral";
  if (n.raw > 0) return "positive";
  if (n.raw < 0) return "negative";
  return "neutral";
}

const STATUS_TONE: Record<string, Tone> = {
  ok: "positive",
  stable: "positive",
  warning: "warning",
  watch: "warning",
  stale: "warning",
  vendor_stale: "warning",
  error: "negative",
  vendor_unavailable: "negative",
  explicit_miss: "negative",
};

/**
 * Map an arbitrary governance / UI status string to a tone. Unknown strings
 * resolve to ``neutral``; callers should not branch on the string themselves.
 */
export function toneForStatus(status: string): Tone {
  return STATUS_TONE[status] ?? "neutral";
}
