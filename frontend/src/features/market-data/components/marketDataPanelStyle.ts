import type { CSSProperties } from "react";

import { designTokens, ibTokens } from "../../../theme/designSystem";

const s = designTokens.space;
const c = designTokens.color;

export const marketDataPanelStyle = {
  padding: s[3],
  borderRadius: 2,
  background: ibTokens.color.surface,
  border: `1px solid ${ibTokens.color.hairline}`,
  boxShadow: "none",
} as const;

export const marketDataBlockTitleStyle = {
  margin: `0 0 ${s[2]}px`,
  fontSize: designTokens.fontSize[14],
  fontWeight: 600,
  color: c.neutral[900],
} as const;

/** 卡片内小表格共用滚动高度，避免多处重复字面量 */
export const marketDataTableScrollWrapStyle: CSSProperties = {
  maxHeight: 320,
  overflow: "auto",
};
