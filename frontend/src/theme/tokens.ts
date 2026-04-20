import { designTokens } from "./designSystem";

/**
 * Legacy shell aliases — map design scales to existing consumer keys (WorkbenchShell, pages).
 */
export const shellTokens = {
  colorBgApp: designTokens.color.neutral[50],
  colorBgSurface: "#f7f7f2",
  colorBgCanvas: "#fcfbf8",
  colorBgMuted: designTokens.color.neutral[100],
  colorBgSuccessSoft: designTokens.color.success[50],
  colorBgWarningSoft: designTokens.color.warning[50],
  colorBgDangerSoft: designTokens.color.danger[50],
  colorBorder: designTokens.color.neutral[300],
  colorBorderSoft: designTokens.color.neutral[200],
  colorBorderStrong: designTokens.color.neutral[400],
  colorBorderWarning: "#e1cfaa",
  colorTextPrimary: designTokens.color.neutral[900],
  colorTextSecondary: designTokens.color.neutral[700],
  colorTextMuted: designTokens.color.neutral[600],
  colorTextWarning: "#785d24",
  colorAccent: designTokens.color.primary[600],
  colorAccentSoft: designTokens.color.primary[100],
  colorSuccess: designTokens.color.success[500],
  colorWarning: designTokens.color.warning[500],
  colorDanger: designTokens.color.danger[500],
  shadowPanel: designTokens.shadow.panel,
  radiusPanel: designTokens.radius.xl,
  radiusCard: designTokens.radius.lg,
} as const;
