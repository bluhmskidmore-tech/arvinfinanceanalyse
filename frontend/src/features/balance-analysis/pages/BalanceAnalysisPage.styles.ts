import { pageInsetCardStyle } from "../../../components/page/PagePrimitiveStyles";
import { designTokens, ibTokens } from "../../../theme/designSystem";

const s = designTokens.space;
const fs = designTokens.fontSize;
const ib = ibTokens;

export const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 220px), 1fr))",
  gap: s[3],
} as const;

export const firstScreenGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))",
  gap: s[4],
  alignItems: "start",
} as const;

export const formalHeroStyle = {
  display: "grid",
  gap: s[4],
  padding: `${s[5]}px ${s[5]}px`,
  borderRadius: ib.radius,
  border: `1px solid ${ib.color.hairline}`,
  borderTop: `2px solid ${ib.color.accent}`,
  background: ib.color.surface,
  boxShadow: ibTokens.shadow,
} as const;

export const heroMetaRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: s[3],
} as const;

export const heroDetailGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
  gap: s[3],
} as const;

export const heroDetailCardStyle = {
  padding: `${s[3] + s[1]}px ${s[4]}px`,
  borderRadius: ib.radius,
  border: `1px solid ${ib.color.hairline}`,
  background: ib.color.surface,
  display: "grid",
  gap: s[1],
} as const;

export const priorityBoardStyle = {
  display: "grid",
  gap: s[3],
  padding: `${s[4]}px`,
  borderRadius: ib.radius,
  border: `1px solid ${ib.color.hairline}`,
  background: ib.color.surface,
  boxShadow: ibTokens.shadow,
} as const;

export const priorityCardStyle = {
  display: "grid",
  gap: s[2],
  padding: `${s[3] + s[1]}px ${s[4]}px`,
  borderRadius: ib.radius,
  border: `1px solid ${ib.color.hairline}`,
  background: ib.color.surface,
} as const;

export const stagedScenarioShellStyle = {
  display: "grid",
  gap: s[4],
  marginTop: s[6],
  padding: `${s[5] - s[1]}px ${s[5]}px 0`,
  borderRadius: ib.radius,
  border: `1px solid ${ib.color.hairline}`,
  background: ib.color.paper,
} as const;

export const controlBarStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: s[2],
  alignItems: "center",
  justifyContent: "flex-end",
  marginBottom: 0,
} as const;

export const controlStyle = {
  minWidth: 132,
  padding: `${s[2]}px ${s[3]}px`,
  borderRadius: ib.radius,
  border: `1px solid ${ib.color.hairline}`,
  background: ib.color.surface,
  color: ib.color.ink,
} as const;

export const actionButtonStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: `${s[2]}px ${s[3]}px`,
  // ibTokens JS 常量是浅色字面量，页面深色 scope 内改走 CSS 变量链（带同语义兜底）。
  borderRadius: "var(--ib-radius, 2px)",
  border: "1px solid var(--ib-hairline)",
  background: "var(--ib-surface)",
  color: "var(--ib-accent)",
  fontWeight: 600,
  cursor: "pointer",
} as const;

export const tableShellStyle = {
  overflowX: "auto",
  minWidth: 0,
  borderRadius: ib.radius,
  border: `1px solid ${ib.color.hairline}`,
  background: ib.color.surface,
} as const;

export const rightRailFilterRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: s[3],
} as const;

export const rightRailFilterStyle = {
  minWidth: 120,
  padding: `${s[2]}px ${s[3] - s[1]}px`,
  borderRadius: ib.radius,
  border: `1px solid ${ib.color.hairline}`,
  background: ib.color.surface,
  color: ib.color.ink,
} as const;

export const rightRailItemButtonStyle = {
  width: "100%",
  textAlign: "left",
  border: "none",
  background: "transparent",
  padding: 0,
  cursor: "pointer",
} as const;

export const decisionActionRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: s[2],
} as const;

export const decisionActionButtonStyle = {
  padding: `${s[2]}px ${s[3]}px`,
  borderRadius: ib.radius,
  border: `1px solid ${ib.color.hairline}`,
  background: ib.color.surface,
  color: ib.color.ink,
  fontSize: fs[12],
  fontWeight: 600,
  cursor: "pointer",
} as const;

export const currentUserCardStyle = {
  marginBottom: s[3],
  ...pageInsetCardStyle,
  borderRadius: ib.radius,
  border: `1px solid ${ib.color.hairline}`,
  borderLeft: `2px solid ${ib.color.accent}`,
  background: ib.color.paper,
  color: ib.color.inkSecondary,
  padding: s[3],
  fontSize: fs[12],
  lineHeight: designTokens.lineHeight.relaxed,
} as const;

export const barTrackStyle = {
  width: "100%",
  height: s[2] - 1,
  borderRadius: ib.radius,
  background: ib.color.hairline,
  overflow: "hidden",
} as const;
