import { designTokens } from "../../theme/designSystem";
import { shellTokens } from "../../theme/tokens";

/** 与首页驾驶舱一致：白底、浅边线、低阴影，控制页面面板密度。 */
export const pageSurfacePanelStyle = {
  padding: 16,
  borderRadius: designTokens.radius.sm,
  background: shellTokens.colorBgSurface,
  border: "1px solid rgba(115, 132, 153, 0.24)",
  boxShadow: "0 1px 5px rgba(15, 45, 80, 0.035)",
} as const;

export const pageInsetCardStyle = {
  padding: 12,
  borderRadius: designTokens.radius.sm,
  border: "1px solid rgba(115, 132, 153, 0.22)",
  background: shellTokens.colorBgSurface,
  boxShadow: "none",
} as const;

/** Opt-in Phase-1 primitives 使用 global.css class，此为稳定类名字符串供测试与消费者引用 */
export const PAGE_V2_CONTRACT = {
  decisionHeroRoot: "moss-page-v2-decision-hero",
  dataStatusRoot: "moss-page-v2-data-status",
  kpiBandRoot: "moss-page-v2-kpi-band",
  kpiMetricItem: "moss-page-v2-kpi-metric",
  evidencePanelRoot: "moss-page-v2-evidence-panel",
  analysisGridCols: {
    "1": "moss-page-v2-analysis-grid moss-page-v2-analysis-grid--cols-1",
    "2": "moss-page-v2-analysis-grid moss-page-v2-analysis-grid--cols-2",
    "3": "moss-page-v2-analysis-grid moss-page-v2-analysis-grid--cols-3",
  },
  stateSurfaceRoot: "moss-page-v2-state-surface",
} as const;
