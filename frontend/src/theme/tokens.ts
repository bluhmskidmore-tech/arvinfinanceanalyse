import { designTokens } from "./designSystem";

/**
 * Legacy shell aliases — map design scales to existing consumer keys (WorkbenchShell, pages).
 */
export const shellTokens = {
  /** 与总览工作台大背景一致 */
  colorBgApp: designTokens.color.warm.porcelain,
  /**
   * 卡片 / 面板衬底：与 Ant Design 默认容器白一致；设计尺度未单独挂 neutral[0]，此处与 colorBgCanvas 对齐。
   */
  colorBgSurface: designTokens.color.warm.paper,
  colorBgCanvas: "#fffdf9",
  /**
   * 工作台左侧轻量暖色导航轨（WorkbenchShell aside）。专用色，非 neutral 尺度派生。
   * @see DESIGN Warm Cockpit Contract
   */
  railBg: designTokens.color.warm.rail,
  /** 暖色 rail 上的分割线、轻描边 */
  railBorder: "rgba(92, 68, 52, 0.14)",
  /** 主导航项激活态衬底 */
  railNavActiveBg: "rgba(184, 92, 56, 0.12)",
  /** Logo 区与轨内强调底 */
  railSurfaceTint: "rgba(184, 92, 56, 0.12)",
  railBrandText: designTokens.color.warm.ink,
  railTextOnNavActive: designTokens.color.warm.ink,
  railTextNavIdle: "rgba(47, 40, 36, 0.76)",
  railTextSupportIdle: "rgba(47, 40, 36, 0.62)",
  railTextSectionIdle: "rgba(47, 40, 36, 0.68)",
  railIconBorderActive: "rgba(184, 92, 56, 0.24)",
  railIconFgActive: designTokens.color.warm.terracotta,
  railIconFgIdle: "rgba(47, 40, 36, 0.54)",
  railCountFgActive: "rgba(47, 40, 36, 0.82)",
  railCountFgIdle: "rgba(47, 40, 36, 0.48)",
  /**
   * 占位 readiness 徽章：浅紫系，与 institutional primary 蓝区分；集中为语义 token 供壳层使用。
   */
  readinessBadgePlaceholderBg: "#f6edea",
  readinessBadgePlaceholderFg: designTokens.color.warm.burgundy,
  readinessBadgePlaceholderBorder: "#e4c9c9",
  colorBgMuted: "#f0e7db",
  colorBgSuccessSoft: designTokens.color.success[50],
  colorBgWarningSoft: designTokens.color.warning[50],
  colorBgDangerSoft: designTokens.color.danger[50],
  /** 默认描边：与 DESIGN「细边框」一致，避免 #d1d5db 主内容区显脏 */
  colorBorder: "#dbcdbd",
  colorBorderSoft: "#e8ddd0",
  colorBorderStrong: "#c9b7a5",
  colorBorderWarning: designTokens.color.warning[200],
  colorTextPrimary: designTokens.color.warm.charcoal,
  colorTextSecondary: "#6d5f54",
  colorTextMuted: designTokens.color.warm.taupe,
  colorTextWarning: designTokens.color.warning[700],
  colorAccent: designTokens.color.warm.terracotta,
  colorAccentSoft: "#f2ddd1",
  colorSuccess: designTokens.color.warm.sage,
  colorWarning: "#b8874a",
  colorDanger: designTokens.color.warm.burgundy,
  colorInfo: designTokens.color.warm.slateBlue,
  shadowPanel: "0 20px 42px rgba(76, 58, 44, 0.12)",
  shadowCard: "0 14px 28px rgba(76, 58, 44, 0.08)",
  shadowRail: "8px 0 28px rgba(86, 68, 52, 0.08)",
  appBackdrop:
    "radial-gradient(circle at top left, rgba(184, 92, 56, 0.10) 0%, rgba(184, 92, 56, 0) 34%), radial-gradient(circle at top right, rgba(102, 122, 150, 0.08) 0%, rgba(102, 122, 150, 0) 30%), linear-gradient(180deg, #f6f1e8 0%, #efe4d6 100%)",
  radiusPanel: designTokens.radius.xl,
  radiusCard: designTokens.radius.lg,
  railMarkGlow: "linear-gradient(145deg, rgba(184, 92, 56, 0.22), rgba(102, 122, 150, 0.16))",
  terminalBarBg:
    "linear-gradient(180deg, rgba(255,253,249,0.98) 0%, rgba(246,241,232,0.94) 100%)",
  terminalBarBorder: "rgba(201, 183, 165, 0.72)",
  marketPulseBg:
    "linear-gradient(90deg, rgba(244, 236, 224, 0.84) 0%, rgba(255, 253, 249, 0.92) 100%)",
  marketPulseBorder: "rgba(201, 183, 165, 0.6)",
  canvasPaperBg:
    "linear-gradient(180deg, rgba(255,253,249,0.98) 0%, rgba(251,247,240,0.94) 100%)",
  canvasPaperShade:
    "radial-gradient(circle at top right, rgba(184, 92, 56, 0.08) 0%, rgba(184, 92, 56, 0) 36%)",
} as const;
