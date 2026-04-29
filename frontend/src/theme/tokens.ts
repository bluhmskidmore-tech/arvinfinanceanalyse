import { designTokens } from "./designSystem";

/**
 * Legacy shell aliases — map design scales to existing consumer keys (WorkbenchShell, pages).
 */
export const shellTokens = {
  /** 与总览工作台大背景一致 */
  colorBgApp: designTokens.color.neutral[50],
  colorBgSurface: "#ffffff",
  colorBgCanvas: "#ffffff",
  colorBgMuted: designTokens.color.neutral[100],
  colorBgSuccessSoft: designTokens.color.success[50],
  colorBgWarningSoft: designTokens.color.warning[50],
  colorBgDangerSoft: designTokens.color.danger[50],
  /** 默认描边：与 DESIGN「细边框」一致，避免 #d1d5db 主内容区显脏 */
  colorBorder: designTokens.color.neutral[200],
  colorBorderSoft: designTokens.color.neutral[100],
  colorBorderStrong: designTokens.color.neutral[300],
  colorBorderWarning: designTokens.color.warning[200],
  colorTextPrimary: designTokens.color.neutral[900],
  colorTextSecondary: designTokens.color.neutral[600],
  colorTextMuted: designTokens.color.neutral[500],
  colorTextWarning: designTokens.color.warning[700],
  colorAccent: designTokens.color.primary[600],
  colorAccentSoft: designTokens.color.primary[100],
  colorSuccess: designTokens.color.success[500],
  colorWarning: designTokens.color.warning[500],
  colorDanger: designTokens.color.danger[500],
  shadowPanel: designTokens.shadow.panel,
  radiusPanel: designTokens.radius.xl,
  radiusCard: designTokens.radius.lg,
} as const;
