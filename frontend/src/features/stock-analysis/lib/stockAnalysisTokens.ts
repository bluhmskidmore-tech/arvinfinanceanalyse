import type { CSSProperties } from "react";

import { designTokens } from "../../../theme/designSystem";

const { color, space, radius, fontFamily } = designTokens;

/**
 * Page-scoped CSS variables derived from designTokens（与 global `--moss-color-*` 同源数值）。
 */
export const stockAnalysisPageCssVars: CSSProperties = {
  "--sa-space-2": `${space[2]}px`,
  "--sa-space-3": `${space[3]}px`,
  "--sa-space-4": `${space[4]}px`,
  "--sa-radius-md": `${radius.md}px`,
  "--sa-color-surface": color.neutral[50],
  "--sa-color-card": "#ffffff",
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
