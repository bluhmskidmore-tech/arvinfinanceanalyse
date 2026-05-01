import { designTokens } from "./designSystem";

/**
 * Legacy shell aliases — map design scales to existing consumer keys (WorkbenchShell, pages).
 */
export const shellTokens = {
  /** 与总览工作台大背景一致 */
  colorBgApp: designTokens.color.neutral[50],
  /**
   * 卡片 / 面板衬底：与 Ant Design 默认容器白一致；设计尺度未单独挂 neutral[0]，此处与 colorBgCanvas 对齐。
   */
  colorBgSurface: "#ffffff",
  colorBgCanvas: "#ffffff",
  /**
   * 工作台左侧深色导航轨（WorkbenchShell aside）。专用色，非 neutral 尺度派生。
   * @see DESIGN 侧栏参照
   */
  railBg: "#121d2a",
  /** 深色轨上的分割线、轻描边 */
  railBorder: "rgba(255, 255, 255, 0.08)",
  /** 主导航项激活态衬底 */
  railNavActiveBg: "rgba(255, 255, 255, 0.06)",
  /** Logo 区与轨内强调底（半透明白） */
  railSurfaceTint: "rgba(255, 255, 255, 0.1)",
  railBrandText: "#f5f7fa",
  railTextOnNavActive: "#f4f7fb",
  railTextNavIdle: "rgba(220, 228, 236, 0.88)",
  railTextSupportIdle: "rgba(184, 197, 210, 0.82)",
  railTextSectionIdle: "rgba(205, 215, 224, 0.88)",
  railIconBorderActive: "rgba(255, 255, 255, 0.22)",
  railIconFgActive: "#ffffff",
  railIconFgIdle: "rgba(184, 197, 210, 0.76)",
  railCountFgActive: "rgba(223, 235, 255, 0.94)",
  railCountFgIdle: "rgba(184, 197, 210, 0.62)",
  /**
   * 占位 readiness 徽章：浅紫系，与 institutional primary 蓝区分；集中为语义 token 供壳层使用。
   */
  readinessBadgePlaceholderBg: "#f2edf8",
  readinessBadgePlaceholderFg: "#654594",
  readinessBadgePlaceholderBorder: "#ddd2ee",
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
