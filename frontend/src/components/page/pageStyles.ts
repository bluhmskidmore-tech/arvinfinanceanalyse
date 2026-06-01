import { designTokens as dt } from "../../theme/designSystem";
import { shellTokens as t } from "../../theme/tokens";

export const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: dt.space[4],
} as const;

export const controlBarStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: dt.space[3],
  alignItems: "center",
  marginBottom: dt.space[5],
} as const;

export const tableShellStyle = {
  overflowX: "auto",
  borderRadius: dt.radius.lg,
  border: `1px solid ${dt.color.neutral[200]}`,
  background: t.colorBgSurface,
} as const;

export const tableStyle = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: dt.fontSize[13],
} as const;

export const thStyle = {
  textAlign: "left",
  padding: "10px 12px",
  borderBottom: `1px solid ${dt.color.neutral[200]}`,
  color: dt.color.neutral[600],
  fontSize: dt.fontSize[13],
} as const;

export const tdStyle = {
  padding: "12px",
  borderBottom: `1px solid ${dt.color.neutral[100]}`,
  color: dt.color.neutral[900],
} as const;

export const modeBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  fontSize: dt.fontSize[12],
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
} as const;
