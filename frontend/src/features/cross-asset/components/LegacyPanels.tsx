import type {
  CrossAssetNcdProxyEvidence,
  CrossAssetTransmissionAxisRow,
} from "../lib/crossAssetDriversPageModel";

/** 行标签整句英文 caption 中文化（§7 语域）；未登记原样透出，原文保留在 title。 */
const NCD_ROW_LABEL_ZH: Record<string, string> = {
  "shibor fixing": "Shibor 定盘",
};

/**
 * rowCaption 形如 "Shibor fixing: 1M 1.405 · 3M 1.4275 · …"（模型契约保持不变）；
 * 展示层拆成「标签 + 期限单元格」，避免单行 4 个 `·`（§7 配额）。
 */
function splitNcdRowCaption(caption: string): { label: string; cells: string[] } {
  const separatorIndex = caption.indexOf(": ");
  if (separatorIndex < 0) {
    return { label: caption, cells: [] };
  }
  const rawLabel = caption.slice(0, separatorIndex).trim();
  const label = NCD_ROW_LABEL_ZH[rawLabel.toLowerCase()] ?? rawLabel;
  const cells = caption
    .slice(separatorIndex + 2)
    .split(" · ")
    .map((cell) => cell.trim())
    .filter(Boolean);
  return { label, cells };
}

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
          {evidence.rowCaptions.map((caption) => {
            const { label, cells } = splitNcdRowCaption(caption);
            return (
              <li key={caption} title={caption}>
                <strong className="cross-asset-ncd-proxy__row-label">{label}</strong>
                {cells.length > 0 ? (
                  <span className="cross-asset-ncd-proxy__row-cells">
                    {cells.map((cell) => (
                      <span key={cell} className="cross-asset-ncd-proxy__row-cell">
                        {cell}
                      </span>
                    ))}
                  </span>
                ) : null}
              </li>
            );
          })}
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
