import { designTokens } from "../../../theme/designSystem";

const s = designTokens.space;
const c = designTokens.color;

export const marketDataPanelStyle = {
  padding: s[4],
  borderRadius: designTokens.radius.md,
  background: "#ffffff",
  border: `1px solid ${c.neutral[200]}`,
  boxShadow: "0 4px 12px rgba(0, 0, 0, 0.03)",
} as const;

export const marketDataBlockTitleStyle = {
  margin: `0 0 ${s[3]}px`,
  fontSize: designTokens.fontSize[16],
  fontWeight: 600,
  color: c.neutral[900],
} as const;
