import type {
  CrossAssetNcdProxyEvidence,
  CrossAssetTransmissionAxisRow,
} from "../lib/crossAssetDriversPageModel";

export function NcdProxyEvidencePanel({
  evidence,
  isLoading,
}: {
  evidence: CrossAssetNcdProxyEvidence;
  isLoading: boolean;
}) {
  return (
    <details open className="cross-asset-ncd-proxy" data-testid="cross-asset-ncd-proxy">
      <summary>
        <span>资金面证据</span>
        <strong>{isLoading ? "加载中" : evidence.proxyLabel}</strong>
      </summary>
      <div className="cross-asset-ncd-proxy__body">
        <p className="cross-asset-ncd-proxy__warning" data-testid="cross-asset-ncd-proxy-warning">
          {evidence.proxyWarning}
        </p>
        <ul className="cross-asset-ncd-proxy__rows" data-testid="cross-asset-ncd-proxy-rows">
          {evidence.rowCaptions.map((caption) => (
            <li key={caption}>{caption}</li>
          ))}
        </ul>
      </div>
    </details>
  );
}

export function TransmissionAxesPanel({ rows }: { rows: CrossAssetTransmissionAxisRow[] }) {
  return (
    <section className="cross-asset-transmission-axes" data-testid="cross-asset-transmission-axes">
      <div className="cross-asset-transmission-axes__grid">
        {rows.map((row) => (
          <article
            key={row.axisKey}
            className={`cross-asset-transmission-axes__card cross-asset-transmission-axes__card--${row.status}`}
            data-testid={`cross-asset-transmission-axis-${row.axisKey}`}
          >
            <strong>{row.label}</strong>
            <span className="cross-asset-transmission-axes__status">{row.status === "ready" ? "已就绪" : "待信号"}</span>
            <p className="cross-asset-transmission-axes__summary">{row.summary}</p>
            <div className="cross-asset-transmission-axes__meta">{row.stanceLabel}</div>
            <div className="cross-asset-transmission-axes__impact">{row.impactedViews.join("、")}</div>
          </article>
        ))}
      </div>
    </section>
  );
}
