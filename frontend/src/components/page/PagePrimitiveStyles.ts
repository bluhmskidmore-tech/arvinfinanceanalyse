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
