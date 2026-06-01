import { designTokens } from "./designSystem";

/**
 * Legacy shell aliases map design scales to existing consumer keys.
 * Keep these aliases aligned with the homepage blue-gray visual contract.
 */
export const shellTokens = {
  colorBgApp: designTokens.color.neutral[50],
  colorBgSurface: "#ffffff",
  colorBgCanvas: "#ffffff",
  railBg: designTokens.color.cockpit.navy950,
  railBorder: "rgba(96, 165, 250, 0.20)",
  railNavActiveBg: "rgba(24, 80, 161, 0.24)",
  railSurfaceTint: "rgba(59, 130, 246, 0.18)",
  railBrandText: designTokens.color.cockpit.blue50,
  railTextOnNavActive: "#ffffff",
  railTextNavIdle: "rgba(234, 242, 251, 0.82)",
  railTextSupportIdle: "rgba(234, 242, 251, 0.62)",
  railTextSectionIdle: "rgba(234, 242, 251, 0.70)",
  railIconBorderActive: "rgba(96, 165, 250, 0.36)",
  railIconFgActive: designTokens.color.info[300],
  railIconFgIdle: "rgba(234, 242, 251, 0.56)",
  railCountFgActive: "#ffffff",
  railCountFgIdle: "rgba(234, 242, 251, 0.48)",
  readinessBadgePlaceholderBg: designTokens.color.neutral[100],
  readinessBadgePlaceholderFg: designTokens.color.neutral[700],
  readinessBadgePlaceholderBorder: designTokens.color.neutral[200],
  colorBgMuted: designTokens.color.neutral[100],
  colorBgSuccessSoft: designTokens.color.success[50],
  colorBgWarningSoft: designTokens.color.warning[50],
  colorBgDangerSoft: designTokens.color.danger[50],
  colorBorder: designTokens.color.neutral[200],
  colorBorderSoft: designTokens.color.cockpit.border150,
  colorBorderStrong: designTokens.color.neutral[300],
  colorBorderWarning: designTokens.color.warning[200],
  colorTextPrimary: designTokens.color.neutral[900],
  colorTextSecondary: designTokens.color.neutral[600],
  colorTextMuted: designTokens.color.neutral[500],
  colorTextWarning: designTokens.color.warning[700],
  colorAccent: designTokens.color.primary[600],
  colorAccentSoft: designTokens.color.primary[50],
  colorSuccess: designTokens.color.success[500],
  colorWarning: designTokens.color.warning[500],
  colorDanger: designTokens.color.danger[500],
  colorInfo: designTokens.color.info[500],
  shadowPanel: "0 20px 42px rgba(15, 37, 68, 0.10)",
  shadowCard: "0 14px 28px rgba(15, 37, 68, 0.07)",
  shadowRail: "8px 0 28px rgba(6, 24, 45, 0.16)",
  appBackdrop:
    "radial-gradient(circle at top left, rgba(24, 80, 161, 0.10) 0%, rgba(24, 80, 161, 0) 34%), radial-gradient(circle at top right, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0) 30%), linear-gradient(180deg, #f5f7f9 0%, #eceff3 100%)",
  radiusPanel: designTokens.radius.xl,
  radiusCard: designTokens.radius.lg,
  railMarkGlow: "linear-gradient(145deg, rgba(96, 165, 250, 0.28), rgba(24, 80, 161, 0.20))",
  terminalBarBg:
    "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(245,247,249,0.96) 100%)",
  terminalBarBorder: "rgba(203, 213, 225, 0.86)",
  marketPulseBg:
    "linear-gradient(90deg, rgba(239, 246, 255, 0.82) 0%, rgba(255, 255, 255, 0.94) 100%)",
  marketPulseBorder: "rgba(203, 213, 225, 0.72)",
  canvasPaperBg:
    "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(248,251,255,0.96) 100%)",
  canvasPaperShade:
    "radial-gradient(circle at top right, rgba(24, 80, 161, 0.07) 0%, rgba(24, 80, 161, 0) 36%)",
} as const;
