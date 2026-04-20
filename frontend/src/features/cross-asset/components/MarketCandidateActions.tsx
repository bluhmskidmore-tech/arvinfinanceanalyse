import { SectionCard } from "../../../components/SectionCard";
import { designTokens } from "../../../theme/designSystem";

const t = designTokens;

type ActionTone = "bull" | "warning" | "bear";

const TONE_DOT: Record<ActionTone, { bg: string; label: string }> = {
  bull: { bg: t.color.success[500], label: "关注" },
  warning: { bg: t.color.warning[500], label: "观察" },
  bear: { bg: t.color.danger[500], label: "谨慎" },
};

const ROWS: { tone: ActionTone; action: string; reason: string; trigger: string }[] = [
  {
    tone: "bull",
    action: "关注 5Y 国债",
    reason: "中段中期率优于长端",
    trigger: "利差回归至 14bp+",
  },
  {
    tone: "warning",
    action: "观察 1Y AAA 存单",
    reason: "等待供给落地",
    trigger: "分位回到 60% 以下",
  },
  {
    tone: "bear",
    action: "暂不追 10Y 长端",
    reason: "海外约束+供给压力",
    trigger: "美债回落至 4.0%",
  },
  {
    tone: "warning",
    action: "信用仅做票息",
    reason: "利差偏拥挤",
    trigger: "AAA 3Y > 50bp",
  },
];

export function MarketCandidateActions() {
  return (
    <SectionCard title="市场候选动作">
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: t.fontSize[13] }}>
          <thead>
            <tr style={{ color: t.color.neutral[500], textAlign: "left" }}>
              <th
                style={{ padding: `${t.space[2]}px ${t.space[3]}px ${t.space[2]}px 0`, fontWeight: 600, width: 36 }}
                aria-hidden
              >
                {/* dot column */}
              </th>
              <th style={{ padding: `${t.space[2]}px ${t.space[3]}px ${t.space[2]}px 0`, fontWeight: 600 }}>动作</th>
              <th style={{ padding: `${t.space[2]}px ${t.space[3]}px`, fontWeight: 600 }}>理由</th>
              <th style={{ padding: `${t.space[2]}px 0 ${t.space[2]}px ${t.space[3]}px`, fontWeight: 600 }}>触发条件</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.action} style={{ borderTop: `1px solid ${t.color.neutral[100]}`, verticalAlign: "top" }}>
                <td style={{ padding: `${t.space[3]}px ${t.space[3]}px ${t.space[3]}px 0` }}>
                  <span
                    title={TONE_DOT[row.tone].label}
                    style={{
                      display: "inline-block",
                      width: t.space[2],
                      height: t.space[2],
                      borderRadius: "50%",
                      background: TONE_DOT[row.tone].bg,
                      flexShrink: 0,
                    }}
                  />
                </td>
                <td
                  style={{
                    padding: `${t.space[3]}px ${t.space[3]}px ${t.space[3]}px 0`,
                    fontWeight: 600,
                    color: t.color.neutral[800],
                    whiteSpace: "nowrap",
                  }}
                >
                  {row.action}
                </td>
                <td
                  style={{
                    padding: t.space[3],
                    color: t.color.neutral[700],
                    lineHeight: t.lineHeight.normal,
                  }}
                >
                  {row.reason}
                </td>
                <td
                  style={{
                    padding: `${t.space[3]}px 0 ${t.space[3]}px ${t.space[3]}px`,
                    color: t.color.neutral[600],
                    lineHeight: t.lineHeight.normal,
                  }}
                >
                  {row.trigger}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}
