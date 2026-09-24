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

/*
 * 表格样式走 --ib-* 变量链、浅色字面量降级为回退值（KpiCard.css 同款主题感知
 * 模式）：浅色路由 --ib-* 未定义时取回退、渲染与历史逐像素一致；深色/Nocturne
 * scope 页由边界或页根桥接提供 --ib-*，表格随主题翻转，路由内无需再叠
 * !important 校正层。
 */
export const tableShellStyle = {
  overflowX: "auto",
  /* IB light Shape Lock: 2px 锐角为浅色回退（DESIGN.md §5）；深色 scope 页由 --ib-radius 接管圆角制度。 */
  borderRadius: "var(--ib-radius, 2px)",
  border: `1px solid var(--ib-hairline, ${dt.color.neutral[200]})`,
  background: `var(--ib-surface, ${t.colorBgSurface})`,
} as const;

export const tableStyle = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: dt.fontSize[13],
} as const;

export const thStyle = {
  textAlign: "left",
  padding: "10px 12px",
  borderBottom: `1px solid var(--ib-rule-strong, ${dt.color.neutral[200]})`,
  color: `var(--ib-ink-muted, ${dt.color.neutral[600]})`,
  fontSize: dt.fontSize[13],
} as const;

export const tdStyle = {
  padding: "12px",
  borderBottom: `1px solid var(--ib-hairline, ${dt.color.neutral[100]})`,
  color: `var(--ib-ink, ${dt.color.neutral[900]})`,
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
