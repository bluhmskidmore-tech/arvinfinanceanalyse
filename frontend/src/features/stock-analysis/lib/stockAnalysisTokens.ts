import type { CSSProperties } from "react";

import { designTokens } from "../../../theme/designSystem";

const { color, space, radius, fontFamily } = designTokens;

/**
 * Page-scoped CSS variables — designTokens 与 dashboard-home 色板同源。
 */
const dhTokens = {
  pageBg: "#f4f7fb",
  card: "#ffffff",
  cardSoft: "#f7f9fc",
  line: "#e4e9f0",
  lineSoft: "#eef2f7",
  ink: "#0c1c33",
  ink2: "#2c3e5a",
  muted: "#6b7d95",
  muted2: "#8a99af",
  blue: color.primary[600],
  blueDeep: color.primary[800],
  blueSoft: color.primary[50],
  green: "#1f7a55",
  greenSoft: "#eef7f2",
  red: "#b94743",
} as const;

export const stockAnalysisPageCssVars: CSSProperties = {
  "--sa-dh-page-bg": dhTokens.pageBg,
  "--sa-dh-card": dhTokens.card,
  "--sa-dh-card-soft": dhTokens.cardSoft,
  "--sa-dh-line": dhTokens.line,
  "--sa-dh-line-soft": dhTokens.lineSoft,
  "--sa-dh-ink": dhTokens.ink,
  "--sa-dh-ink-2": dhTokens.ink2,
  "--sa-dh-muted": dhTokens.muted,
  "--sa-dh-muted-2": dhTokens.muted2,
  "--sa-dh-blue": dhTokens.blue,
  "--sa-dh-blue-deep": dhTokens.blueDeep,
  "--sa-dh-blue-soft": dhTokens.blueSoft,
  "--sa-dh-green": dhTokens.green,
  "--sa-dh-green-soft": dhTokens.greenSoft,
  "--sa-dh-red": dhTokens.red,
  "--sa-dh-shadow-card":
    "0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px rgba(15, 23, 42, 0.06)",
  "--sa-space-2": `${space[2]}px`,
  "--sa-space-3": `${space[3]}px`,
  "--sa-space-4": `${space[4]}px`,
  "--sa-radius-md": `${radius.md}px`,
  "--sa-color-surface": dhTokens.pageBg,
  "--sa-color-card": dhTokens.card,
  "--sa-color-border": color.neutral[200],
  "--sa-color-border-subtle": color.neutral[100],
  "--sa-color-text": color.neutral[900],
  "--sa-color-muted": color.neutral[600],
  "--sa-color-eyebrow": color.neutral[500],
  "--sa-table-header-bg": color.neutral[50],
  "--sa-accent-bg-soft": color.primary[50],
  "--sa-accent-border": color.primary[200],
  "--sa-accent-text": color.primary[700],
  "--sa-accent-line": color.primary[600],
  "--sa-sem-up-soft": color.success[50],
  "--sa-sem-up-border": color.success[200],
  "--sa-sem-up-text": color.success[800],
  "--sa-sem-down-soft": "#fef2f2",
  "--sa-sem-down-border": color.danger[200],
  "--sa-sem-down-text": color.danger[800],
  "--sa-sem-loss": color.semantic.down,
  "--sa-sem-profit": color.semantic.up,
  "--sa-warning-fg": color.warning[800],
  "--sa-warning-soft-bg": color.warning[50],
  "--sa-warning-border": color.warning[200],
  "--sa-danger-soft-bg": color.danger[50],
  "--sa-danger-border": color.danger[200],
  "--sa-danger-text": color.danger[800],
  "--sa-chart-track": color.neutral[100],
  "--sa-font-tabular": fontFamily.tabular,
} as CSSProperties;
