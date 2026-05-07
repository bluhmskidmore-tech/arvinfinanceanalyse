import { pageInsetCardStyle } from "../../../components/page/PagePrimitiveStyles";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import { shellTokens } from "../../../theme/tokens";

const r = designTokens.radius;
const s = designTokens.space;
const fs = designTokens.fontSize;
const c = designTokens.color;

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
  borderRadius: r.xl + s[1],
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: c.neutral[50],
  boxShadow: designTokens.shadow.card,
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
  borderRadius: r.lg,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: displayTokens.surface.section,
  display: "grid",
  gap: s[1],
} as const;

export const priorityBoardStyle = {
  display: "grid",
  gap: s[3],
  padding: `${s[4]}px`,
  borderRadius: r.xl + s[1],
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: c.neutral[50],
  boxShadow: designTokens.shadow.card,
} as const;

export const priorityCardStyle = {
  display: "grid",
  gap: s[2],
  padding: `${s[3] + s[1]}px ${s[4]}px`,
  borderRadius: r.lg,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: displayTokens.surface.section,
} as const;

export const stagedScenarioShellStyle = {
  display: "grid",
  gap: s[4],
  marginTop: s[6],
  padding: `${s[5] - s[1]}px ${s[5]}px 0`,
  borderRadius: r.xl + s[1],
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: `linear-gradient(180deg, ${c.neutral[50]}f5 0%, ${c.primary[50]}eb 100%)`,
} as const;

export const controlBarStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: s[3],
  alignItems: "center",
  marginBottom: s[5],
} as const;

export const controlStyle = {
  minWidth: 180,
  padding: `${s[3] - s[1]}px ${s[3]}px`,
  borderRadius: r.md,
  border: `1px solid ${c.neutral[300]}`,
  background: c.primary[50],
  color: c.neutral[900],
} as const;

export const actionButtonStyle = {
  padding: `${s[3] - s[1]}px ${s[3] + s[1]}px`,
  borderRadius: r.md,
  border: `1px solid ${c.info[200]}`,
  background: c.info[50],
  color: c.info[600],
  fontWeight: 600,
  cursor: "pointer",
} as const;

export const tableShellStyle = {
  overflowX: "auto",
  minWidth: 0,
  borderRadius: s[4],
  border: `1px solid ${c.neutral[200]}`,
  background: c.primary[50],
} as const;

export const workbookPanelStyle = {
  borderRadius: r.lg,
  border: `1px solid ${c.neutral[200]}`,
  background: c.primary[50],
  padding: s[4],
  boxShadow: designTokens.shadow.card,
} as const;

export const workbookPanelHeaderStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: s[3],
  marginBottom: s[3] + s[1],
} as const;

export const workbookPanelBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: `${s[1]}px ${s[2]}px`,
  borderRadius: 999,
  background: c.primary[100],
  color: c.neutral[600],
  fontSize: fs[12],
  fontWeight: 600,
} as const;

export const workbookSecondaryGridStyle = {
  display: "grid",
  gap: s[5],
  marginTop: s[5],
} as const;

export const rightRailFilterRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: s[3],
} as const;

export const rightRailFilterStyle = {
  minWidth: 120,
  padding: `${s[2]}px ${s[3] - s[1]}px`,
  borderRadius: r.md,
  border: `1px solid ${c.neutral[300]}`,
  background: c.primary[50],
  color: c.neutral[900],
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
  borderRadius: r.sm + s[1],
  border: `1px solid ${c.neutral[300]}`,
  background: c.primary[50],
  color: c.neutral[900],
  fontSize: fs[12],
  fontWeight: 600,
  cursor: "pointer",
} as const;

export const currentUserCardStyle = {
  marginBottom: s[3],
  ...pageInsetCardStyle,
  borderRadius: r.md,
  border: `1px solid ${c.neutral[300]}`,
  background: c.info[50],
  color: c.neutral[800],
  padding: s[3],
  fontSize: fs[12],
  lineHeight: designTokens.lineHeight.relaxed,
} as const;

export const barTrackStyle = {
  width: "100%",
  height: s[2],
  borderRadius: 999,
  background: c.neutral[100],
  overflow: "hidden",
} as const;
