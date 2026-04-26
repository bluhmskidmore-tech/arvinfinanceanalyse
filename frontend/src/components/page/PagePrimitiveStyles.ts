import { shellTokens } from "../../theme/tokens";

export const pageSurfacePanelStyle = {
  padding: 24,
  borderRadius: shellTokens.radiusPanel,
  background: shellTokens.colorBgSurface,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  boxShadow: shellTokens.shadowPanel,
} as const;

export const pageInsetCardStyle = {
  padding: 16,
  borderRadius: 16,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: shellTokens.colorBgCanvas,
} as const;
