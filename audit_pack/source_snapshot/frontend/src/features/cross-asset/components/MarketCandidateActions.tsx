import { SectionCard } from "../../../components/SectionCard";
import { designTokens } from "../../../theme/designSystem";
import type { CrossAssetCandidateAction } from "../lib/crossAssetDriversPageModel";

const t = designTokens;

type ActionTone = CrossAssetCandidateAction["tone"];

const TONE_DOT: Record<ActionTone, { bg: string; label: string }> = {
  bull: { bg: t.color.success[500], label: "关注" },
  warning: { bg: t.color.warning[500], label: "观察" },
  bear: { bg: t.color.danger[500], label: "谨慎" },
};

export type MarketCandidateActionsProps = {
  rows: CrossAssetCandidateAction[];
};

export function MarketCandidateActions({ rows }: MarketCandidateActionsProps) {
  return (
    <div data-testid="cross-asset-candidate-actions">
      <SectionCard title="市场候选动作">
        {rows.length === 0 ? (
          <p style={{ margin: 0, color: t.color.neutral[600], fontSize: t.fontSize[13] }}>
            当前没有足够证据形成候选动作。
          </p>
        ) : (
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
                  <th style={{ padding: `${t.space[2]}px 0 ${t.space[2]}px ${t.space[3]}px`, fontWeight: 600 }}>证据</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.action}-${row.evidence}`} style={{ borderTop: `1px solid ${t.color.neutral[100]}`, verticalAlign: "top" }}>
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
                      {row.evidence}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
