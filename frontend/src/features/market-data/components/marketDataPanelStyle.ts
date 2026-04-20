import { designTokens } from "../../../theme/designSystem";

const s = designTokens.space;
const c = designTokens.color;

export const marketDataPanelStyle = {
  padding: s[6],
  borderRadius: s[5],
  background: c.primary[50],
  border: `1px solid ${c.primary[200]}`,
  boxShadow: designTokens.shadow.card,
} as const;

export const marketDataBlockTitleStyle = {
  margin: `0 0 ${s[3]}px`,
  fontSize: designTokens.fontSize[16],
  fontWeight: 600,
  color: c.neutral[900],
} as const;
