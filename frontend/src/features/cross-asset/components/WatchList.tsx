import { SectionCard } from "../../../components/SectionCard";

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
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ color: "#94a3b8", textAlign: "left" }}>
            <th style={{ padding: "8px 8px 8px 0", fontWeight: 600 }}>品种</th>
            <th style={{ padding: "8px 8px", fontWeight: 600 }}>当前</th>
            <th style={{ padding: "8px 8px", fontWeight: 600 }}>分位</th>
            <th style={{ padding: "8px 0 8px 8px", fontWeight: 600, width: 48 }}>信号</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.name} style={{ borderTop: "1px solid #f1f5f9" }}>
              <td style={{ padding: "10px 8px 10px 0", fontWeight: 600, color: "#1e293b" }}>{row.name}</td>
              <td style={{ padding: "10px 8px", color: "#475569" }}>{row.current}</td>
              <td style={{ padding: "10px 8px", color: "#64748b", lineHeight: 1.5 }}>{row.pctLabel}</td>
              <td style={{ padding: "10px 0 10px 8px", fontSize: 16, lineHeight: 1 }} aria-hidden>
                {row.signal}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </SectionCard>
  );
}
