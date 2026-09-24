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

/** 与 `designSystem` 语义色一致，供点、标签、图表注记等复用 */
export const TONE_COLOR: Record<Tone, string> = {
  positive: designTokens.color.semantic.profit,
  neutral: designTokens.color.neutral[600],
  warning: designTokens.color.warning[700],
  negative: designTokens.color.semantic.loss,
};

/**
 * 主题感知 tone 色（CSS 变量入口）。深色路由（`.theme-dh-api` 等）会在
 * `src/styles/tokens.css` 里重映射 `--ib-*`，因此深色页的盈亏着色必须走本入口，
 * 禁止把浅色 `semantic.profit/loss` 十六进制直灌深色页。
 * 仅适用于能解析 CSS 变量的场景（DOM style / CSS）；canvas/ECharts 等无法解析
 * CSS 变量的代码仍使用 `TONE_COLOR` 或页面主题 TS 镜像 token。
 */
export const TONE_CSS_VAR: Record<Tone, string> = {
  positive: "var(--ib-up)",
  neutral: "var(--ib-ink-muted)",
  warning: "var(--ib-warn)",
  negative: "var(--ib-down)",
};

/**
 * Nocturne scope 页面的 tone 入口。`--ib-*` 在 ThemedRouteBoundary 上被算成
 * dh-api 钢蓝字面值再继承，页根的 Nocturne scope 翻不动它们；挂了
 * `data-moss-theme-scope` Nocturne 别名的页面必须走 `--dh-api-*` 家族，
 * scope 内会解析为 `--nct-*` 色板（避免同页同语义出现两种绿/红，DESIGN.md §4）。
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
