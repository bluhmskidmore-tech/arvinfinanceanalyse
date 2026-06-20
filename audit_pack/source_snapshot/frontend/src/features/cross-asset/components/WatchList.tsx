import { SectionCard } from "../../../components/SectionCard";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import type { CrossAssetWatchRow } from "../lib/crossAssetDriversPageModel";

const t = designTokens;

/** Token-colored dots; avoids emoji blocks that clash with antd + tabular UI. */
const SIGNAL_DOT: Record<CrossAssetWatchRow["signal"], { bg: string; hint: string }> = {
  green: { bg: t.color.semantic.profit, hint: "偏多" },
  yellow: { bg: t.color.warning[500], hint: "待确认" },
  red: { bg: t.color.semantic.loss, hint: "偏空" },
};

export type WatchListProps = {
  rows: CrossAssetWatchRow[];
};

export function WatchList({ rows }: WatchListProps) {
  return (
    <div data-testid="cross-asset-watch-list">
      <SectionCard title="观察名单">
        {rows.length === 0 ? (
          <p style={{ margin: 0, color: t.color.neutral[600], fontSize: t.fontSize[13] }}>
            当前没有可用观察项。
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: t.fontSize[13] }}>
            <thead>
              <tr style={{ color: t.color.neutral[500], textAlign: "left" }}>
                <th style={{ padding: `${t.space[2]}px ${t.space[2]}px ${t.space[2]}px 0`, fontWeight: 600 }}>品种</th>
                <th style={{ padding: t.space[2], fontWeight: 600 }}>当前</th>
                <th style={{ padding: t.space[2], fontWeight: 600 }}>观察理由</th>
                <th style={{ padding: `${t.space[2]}px 0 ${t.space[2]}px ${t.space[2]}px`, fontWeight: 600 }}>信号</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.name}-${row.current}`} style={{ borderTop: `1px solid ${t.color.neutral[100]}` }}>
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
                    {row.note}
                  </td>
                  <td
                    style={{
                      padding: `${t.space[3]}px 0 ${t.space[3]}px ${t.space[2]}px`,
                      color: t.color.neutral[700],
                      lineHeight: t.lineHeight.normal,
                    }}
                  >
                    <div style={{ display: "inline-flex", alignItems: "flex-start", gap: t.space[2] }}>
                      <span
                        title={SIGNAL_DOT[row.signal].hint}
                        aria-label={SIGNAL_DOT[row.signal].hint}
                        style={{
                          display: "inline-block",
                          width: 8,
                          height: 8,
                          marginTop: 5,
                          borderRadius: "50%",
                          background: SIGNAL_DOT[row.signal].bg,
                          flexShrink: 0,
                          boxShadow: `0 0 0 1px ${t.color.neutral[200]}`,
                        }}
                      />
                      <span>{row.signalText}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>
    </div>
  );
}
