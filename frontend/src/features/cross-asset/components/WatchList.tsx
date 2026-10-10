import { EvidencePanel } from "../../../components/page/PagePrimitives";
import { TONE_DH_CSS_VAR } from "../../../utils/tone";
import type { CrossAssetWatchRow } from "../lib/crossAssetDriversPageModel";

import "./WatchList.css";

/**
 * Token-colored dots; avoids emoji blocks that clash with antd + tabular UI.
 * 信号点着色走 Nocturne 语义链（页面固定深色终端，TONE_DH_CSS_VAR）。
 */
const SIGNAL_DOT: Record<CrossAssetWatchRow["signal"], { bg: string; hint: string }> = {
  green: { bg: TONE_DH_CSS_VAR.positive, hint: "偏多" },
  yellow: { bg: TONE_DH_CSS_VAR.warning, hint: "待确认" },
  red: { bg: TONE_DH_CSS_VAR.negative, hint: "偏空" },
};

export type WatchListProps = {
  rows: CrossAssetWatchRow[];
};

export function WatchList({ rows }: WatchListProps) {
  return (
    <div data-testid="cross-asset-watch-list">
      <EvidencePanel heading="观察名单">
        {rows.length === 0 ? (
          <p className="cross-asset-watch-list__empty">当前没有可用观察项。</p>
        ) : (
          <table className="cross-asset-watch-list__table">
            <thead>
              <tr>
                <th>品种</th>
                <th>当前</th>
                <th>观察理由</th>
                <th>信号</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.name}-${row.current}`}>
                  <td className="cross-asset-watch-list__name">{row.name}</td>
                  <td className="cross-asset-watch-list__current">{row.current}</td>
                  <td className="cross-asset-watch-list__note">{row.note}</td>
                  <td>
                    <div className="cross-asset-watch-list__signal">
                      <span
                        className="cross-asset-watch-list__signal-dot"
                        title={SIGNAL_DOT[row.signal].hint}
                        aria-label={SIGNAL_DOT[row.signal].hint}
                        style={{ background: SIGNAL_DOT[row.signal].bg }}
                      />
                      <span>{row.signalText}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </EvidencePanel>
    </div>
  );
}
