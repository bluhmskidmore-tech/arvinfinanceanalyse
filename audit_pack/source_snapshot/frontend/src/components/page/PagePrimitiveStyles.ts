import { designTokens } from "../../theme/designSystem";
import { shellTokens } from "../../theme/tokens";

/** 与浅色工作台一致：白底块用浅阴影分层，避免与底同色的 1px 硬框线（含市场数据等内嵌卡） */
export const pageSurfacePanelStyle = {
  padding: 24,
  borderRadius: shellTokens.radiusPanel,
  background: shellTokens.colorBgSurface,
  border: "none",
  boxShadow: shellTokens.shadowPanel,
} as const;

export const pageInsetCardStyle = {
  padding: 16,
  borderRadius: 16,
  border: "none",
  background: shellTokens.colorBgCanvas,
  boxShadow: designTokens.shadow.card,
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
