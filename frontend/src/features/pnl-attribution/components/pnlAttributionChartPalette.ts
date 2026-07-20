import { designTokens } from "../../../theme/designSystem";

/**
 * PnL attribution chart series / tone colors.
 * All values resolve through designTokens (token-equal); no bare hex.
 */
export const pnlCompositionSeriesColors = {
  positive: designTokens.color.success[600],
  neutral: designTokens.color.neutral[600],
  negative: designTokens.color.danger[500],
  interest: designTokens.color.success[500],
  fairValue: designTokens.color.info[500],
  capital: designTokens.color.warning[500],
  other: designTokens.color.neutral[500],
} as const;

/** ECharts bar label on filled bars — equals cockpit white / IB surface. */
export const pnlChartLabelOnFill = designTokens.color.cockpit.white;
