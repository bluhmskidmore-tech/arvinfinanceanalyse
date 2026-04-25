import { SectionCard } from "../../../components/SectionCard";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import type { CrossAssetWatchRow } from "../lib/crossAssetDriversPageModel";

const t = designTokens;

const SIGNAL = {
  yellow: "\u{1F7E1}",
  green: "\u{1F7E2}",
  red: "\u{1F534}",
} as const;

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
                    <span aria-hidden style={{ fontSize: t.fontSize[16], lineHeight: 1, marginRight: t.space[2] }}>
                      {SIGNAL[row.signal]}
                    </span>
                    {row.signalText}
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
