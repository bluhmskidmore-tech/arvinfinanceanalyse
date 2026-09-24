import type { CSSProperties } from "react";

import { designTokens } from "../../../theme/designSystem";

const s = designTokens.space;

export const marketDataPanelStyle = {
  padding: s[3],
  borderRadius: 8,
  background: "var(--dh-api-panel)",
  border: "1px solid var(--dh-api-line)",
  boxShadow: "none",
} as const;

export const marketDataBlockTitleStyle = {
  margin: `0 0 ${s[2]}px`,
  fontSize: designTokens.fontSize[14],
  fontWeight: 600,
  color: "var(--dh-api-ink)",
} as const;

/** 卡片内小表格共用滚动高度，避免多处重复字面量 */
export const marketDataTableScrollWrapStyle: CSSProperties = {
  maxHeight: 320,
  overflow: "auto",
};
