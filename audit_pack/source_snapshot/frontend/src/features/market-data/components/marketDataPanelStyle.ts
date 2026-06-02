import { designTokens } from "../../../theme/designSystem";

const s = designTokens.space;
const c = designTokens.color;

export const marketDataPanelStyle = {
  padding: s[3],
  borderRadius: designTokens.radius.sm,
  background: "#ffffff",
  border: `1px solid ${c.neutral[200]}`,
  boxShadow: "0 2px 8px rgba(0, 0, 0, 0.025)",
} as const;

export const marketDataBlockTitleStyle = {
  margin: `0 0 ${s[2]}px`,
  fontSize: designTokens.fontSize[14],
  fontWeight: 600,
  color: c.neutral[900],
} as const;
