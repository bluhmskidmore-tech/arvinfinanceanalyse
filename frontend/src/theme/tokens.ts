import { designTokens } from "./designSystem";

/**
 * Legacy shell aliases map design scales to existing consumer keys.
 * Keep these aliases aligned with the homepage blue-gray visual contract.
 */
export const shellTokens = {
  colorBgApp: designTokens.color.institutional.canvas,
  colorBgSurface: designTokens.color.institutional.surfaceRaised,
  colorBgCanvas: designTokens.color.institutional.surface,
  railBg: designTokens.color.institutional.railTop,
  railBorder: "rgba(125, 169, 213, 0.24)",
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
  colorBgMuted: designTokens.color.institutional.surfaceMuted,
  colorBgSuccessSoft: designTokens.color.success[50],
  colorBgWarningSoft: designTokens.color.warning[50],
  colorBgDangerSoft: designTokens.color.danger[50],
  colorBorder: designTokens.color.institutional.border,
  colorBorderSoft: designTokens.color.cockpit.border150,
  colorBorderStrong: designTokens.color.institutional.borderStrong,
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
  shadowPanel: "0 1px 2px rgba(15, 37, 68, 0.06), 0 14px 30px rgba(15, 37, 68, 0.07)",
  shadowCard: "0 1px 2px rgba(15, 37, 68, 0.045), 0 6px 14px rgba(15, 37, 68, 0.04)",
  shadowRail: "10px 0 30px rgba(5, 18, 31, 0.22)",
  appBackdrop:
    "linear-gradient(180deg, #edf2f7 0%, #dfe7f0 100%)",
  radiusPanel: designTokens.radius.sm,
  radiusCard: designTokens.radius.sm,
  railMarkGlow: "linear-gradient(145deg, rgba(184, 138, 45, 0.28), rgba(47, 128, 168, 0.20))",
  terminalBarBg:
    "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(244,247,250,0.98) 100%)",
  terminalBarBorder: "rgba(159, 177, 196, 0.72)",
  marketPulseBg:
    "linear-gradient(90deg, rgba(251, 252, 254, 0.96) 0%, rgba(244, 247, 250, 0.94) 100%)",
  marketPulseBorder: "rgba(159, 177, 196, 0.58)",
  canvasPaperBg:
    "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(251,252,254,0.96) 100%)",
  canvasPaperShade:
    "linear-gradient(90deg, rgba(47, 128, 168, 0.045) 0%, rgba(47, 128, 168, 0) 34%)",
} as const;
