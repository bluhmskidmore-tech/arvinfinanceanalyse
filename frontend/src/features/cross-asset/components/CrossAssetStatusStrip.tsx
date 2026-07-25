import type { CrossAssetStatusStripFlag } from "../lib/crossAssetStatusStrip";

import "./CrossAssetStatusStrip.css";

export type CrossAssetStatusStripProps = {
  flags: CrossAssetStatusStripFlag[];
};

const UI = {
  label: "数据状态",
  empty: "暂无提示",
} as const;

export function CrossAssetStatusStrip({ flags }: CrossAssetStatusStripProps) {
  return (
    <div className="cross-asset-status-strip" data-testid="cross-asset-status-strip" role="status">
      <span className="cross-asset-status-strip__label">{UI.label}</span>
      {flags.length === 0 ? (
        <span className="cross-asset-status-strip__empty">{UI.empty}</span>
      ) : (
        <ul className="cross-asset-status-strip__chips">
          {flags.map((flag, index) => (
            <li
              key={`${flag.tone}|${flag.label}|${index}`}
              className={`cross-asset-status-strip__chip cross-asset-status-strip__chip--${flag.tone}`}
            >
              {flag.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
