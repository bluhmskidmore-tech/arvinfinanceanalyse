/**
 * Cross-asset chart theme palette.
 *
 * The cross-asset drivers page now mounts the dh-api dark terminal theme,
 * but ECharts renders on canvas and cannot read CSS variables — chart
 * options need concrete color strings. This module centralizes them:
 *
 *   - "light"    : the historical hard-coded values, referenced through
 *                  designTokens/ibTokens so they stay token-equal.
 *   - "terminal" : the --dh-api-* dark palette (mirrors tokens.css §dh-api
 *                  and dhApiTokens in theme/designSystem).
 *
 * Builders take an optional `theme` param defaulting to "light" so existing
 * light consumers and tests are unaffected.
 */

import { mossChartCategoricalPalette } from "../../../components/charts/chartTheme";
import { designTokens, dhApiTokens, ibTokens } from "../../../theme/designSystem";

export type CrossAssetChartTheme = "light" | "terminal";

export type CrossAssetChartPalette = {
  /** Primary text (tooltip header/values). */
  text: string;
  /** Secondary text (legend, tooltip series names). */
  textSoft: string;
  /** Muted text (axis labels, page buttons). */
  textMuted: string;
  /** Axis line / tick / axis-pointer line. */
  axisLine: string;
  /** y splitLine (softer than axisLine on dark). */
  splitLine: string;
  /** Axis-pointer floating label background. */
  axisPointerLabelBg: string;
  /** Axis-pointer floating label text. */
  axisPointerLabelText: string;
  tooltipBg: string;
  tooltipBorder: string;
  /** Legend inactive swatch. */
  legendInactive: string;
  /** Emphasis symbol border (matches the surface behind the chart). */
  emphasisBorder: string;
  /** Categorical series colors (trend chart; yield-curve families use [0..3] on terminal). */
  series: string[];
  /** Waterfall positive contribution (偏紧/不利债市). */
  up: string;
  /** Waterfall negative contribution (偏松/利好债市). */
  down: string;
  /** Waterfall neutral total bar. */
  neutral: string;
  /** Waterfall neutral factor bar (softer than total). */
  neutralSoft: string;
  /** Heatmap negative-correlation base (hex; alpha ramp applied). */
  heatmapLow: string;
  /** Heatmap no-data fill (used verbatim). */
  heatmapMid: string;
  /** Heatmap positive-correlation base (hex; alpha ramp applied). */
  heatmapHigh: string;
};

const ib = ibTokens.color;
const dh = dhApiTokens.color;

/** Historical light categorical ladder, identical to crossAssetTrendChart.CHART_COLORS. */
const LIGHT_SERIES: string[] = [
  ...mossChartCategoricalPalette,
  ib.up,
  ib.down,
  ib.inkSecondary,
  ib.inkMuted,
  ib.ink,
  mossChartCategoricalPalette[0]!,
];

/**
 * Terminal categorical ladder: dh-api blue/green/amber/red first, then muted
 * variants so up to 12 lines stay distinguishable on the dark panel.
 * Alpha variants derive from dh token hues (audit: no new bare hex hues).
 */
const TERMINAL_SERIES: string[] = [
  dh.blue,
  dh.green,
  dh.amber,
  dh.red,
  dh.inkSoft,
  dh.inkMuted,
  "rgba(114, 167, 220, 0.55)",
  "rgba(102, 185, 139, 0.55)",
  "rgba(201, 165, 101, 0.55)",
  "rgba(212, 122, 114, 0.55)",
  "rgba(169, 182, 199, 0.75)",
  "rgba(133, 147, 168, 0.6)",
];

const LIGHT_PALETTE: CrossAssetChartPalette = {
  text: ib.ink,
  textSoft: ib.inkSecondary,
  textMuted: ib.inkMuted,
  axisLine: ib.hairline,
  splitLine: ib.hairline,
  axisPointerLabelBg: ib.ink,
  axisPointerLabelText: ib.surface,
  tooltipBg: ib.surface,
  tooltipBorder: ib.hairline,
  legendInactive: designTokens.color.neutral[300],
  emphasisBorder: ib.surface,
  series: LIGHT_SERIES,
  up: designTokens.color.danger[600],
  down: ib.up,
  neutral: designTokens.color.cockpit.ink600,
  neutralSoft: designTokens.color.cockpit.ink450,
  heatmapLow: ib.down,
  heatmapMid: "rgba(100, 116, 139, 0.12)",
  heatmapHigh: ib.up,
};

const TERMINAL_PALETTE: CrossAssetChartPalette = {
  text: dh.ink,
  textSoft: dh.inkSoft,
  textMuted: dh.inkMuted,
  axisLine: dh.line,
  splitLine: dh.lineSoft,
  axisPointerLabelBg: dh.ink,
  axisPointerLabelText: dh.panel,
  tooltipBg: dh.panel2,
  tooltipBorder: dh.line,
  legendInactive: "rgba(133, 147, 168, 0.4)",
  emphasisBorder: dh.panel,
  series: TERMINAL_SERIES,
  up: dh.red,
  down: dh.green,
  neutral: dh.inkMuted,
  neutralSoft: "rgba(133, 147, 168, 0.55)",
  heatmapLow: dh.red,
  heatmapMid: "rgba(133, 147, 168, 0.16)",
  heatmapHigh: dh.green,
};

/** Resolve the chart palette for a theme; defaults to the historical light look. */
export function resolveCrossAssetChartPalette(theme: CrossAssetChartTheme = "light"): CrossAssetChartPalette {
  return theme === "terminal" ? TERMINAL_PALETTE : LIGHT_PALETTE;
}

function hexToRgb(hex: string): [number, number, number] {
  const value = parseInt(hex.slice(1), 16);
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff];
}

/**
 * Theme-aware correlation heatmap cell color. Mirrors the alpha ramp of
 * crossAssetAnalytics.correlationColor (0.1 + |r| * 0.65) so only the hue
 * family changes between themes.
 */
export function heatmapColorFor(r: number | null, palette: CrossAssetChartPalette): string {
  if (r == null) return palette.heatmapMid;
  const clamped = Math.max(-1, Math.min(1, r));
  const t = Math.abs(clamped);
  const [rr, gg, bb] = hexToRgb(clamped >= 0 ? palette.heatmapHigh : palette.heatmapLow);
  return `rgba(${rr}, ${gg}, ${bb}, ${(0.1 + t * 0.65).toFixed(2)})`;
}

/**
 * Theme-aware waterfall bar color. Keeps the ±0.05 business thresholds of
 * crossAssetAnalytics.waterfallColor; only the hue family changes.
 */
export function waterfallBarColorFor(
  value: number,
  kind: "factor" | "total",
  palette: CrossAssetChartPalette,
): string {
  if (value > 0.05) return palette.up;
  if (value < -0.05) return palette.down;
  return kind === "total" ? palette.neutral : palette.neutralSoft;
}
