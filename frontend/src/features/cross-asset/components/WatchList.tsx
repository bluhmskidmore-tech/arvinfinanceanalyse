import { SectionCard } from "../../../components/SectionCard";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";

const t = designTokens;

/** Mock信号：黄 / 绿 / 红圆点（与 atomic 文档一致） */
const SIGNAL = {
  yellow: "\u{1F7E1}",
  green: "\u{1F7E2}",
  red: "\u{1F534}",
} as const;

const ROWS: { name: string; current: string; pctLabel: string; signal: string }[] = [
  { name: "5Y 国开", current: "分位 74%", pctLabel: "等待供给落地", signal: SIGNAL.yellow },
  { name: "1Y AAA 存单", current: "分位 81%", pctLabel: "偏高可观察", signal: SIGNAL.green },
  { name: "AA+ 3Y 城投", current: "分位 41%", pctLabel: "不宜追涨", signal: SIGNAL.red },
];

export function WatchList() {
  return (
    <SectionCard title="观察名单">
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: t.fontSize[13] }}>
        <thead>
          <tr style={{ color: t.color.neutral[500], textAlign: "left" }}>
            <th style={{ padding: `${t.space[2]}px ${t.space[2]}px ${t.space[2]}px 0`, fontWeight: 600 }}>品种</th>
            <th style={{ padding: t.space[2], fontWeight: 600 }}>当前</th>
            <th style={{ padding: t.space[2], fontWeight: 600 }}>分位</th>
            <th
              style={{
                padding: `${t.space[2]}px 0 ${t.space[2]}px ${t.space[2]}px`,
                fontWeight: 600,
                width: t.space[9],
              }}
            >
              信号
            </th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.name} style={{ borderTop: `1px solid ${t.color.neutral[100]}` }}>
              <td
                style={{
                  padding: `${t.space[3]}px ${t.space[2]}px ${t.space[3]}px 0`,
                  fontWeight: 600,
                  color: t.color.neutral[800],
                }}
              >
                {row.name}
              </td>
              <td style={{ ...tabularNumsStyle, padding: t.space[3], color: t.color.neutral[700] }}>{row.current}</td>
              <td
                style={{
                  padding: t.space[3],
                  color: t.color.neutral[600],
                  lineHeight: t.lineHeight.normal,
                }}
              >
                {row.pctLabel}
              </td>
              <td
                style={{
                  padding: `${t.space[3]}px 0 ${t.space[3]}px ${t.space[2]}px`,
                  fontSize: t.fontSize[16],
                  lineHeight: 1,
                }}
                aria-hidden
              >
                {row.signal}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </SectionCard>
  );
}
