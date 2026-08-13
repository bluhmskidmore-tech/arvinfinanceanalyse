import type { MacroBondLinkageTopCorrelation } from "../../../api/contracts";
import { formatCorrelation } from "../lib/marketDataLinkageFormat";

type MarketDataLinkageSummaryBandProps = {
  compositeScore: number | null | undefined;
  compositeDetail?: string;
  topCorrelation?: MacroBondLinkageTopCorrelation | null;
  onOpenSpreads: () => void;
  onOpenLinkage: () => void;
};

export function MarketDataLinkageSummaryBand({
  compositeScore,
  compositeDetail,
  topCorrelation,
  onOpenSpreads,
  onOpenLinkage,
}: MarketDataLinkageSummaryBandProps) {
  const scoreText =
    compositeScore != null && Number.isFinite(compositeScore)
      ? compositeScore.toFixed(2)
      : "—";

  return (
    <div className="market-data-linkage-summary-band" data-testid="market-data-linkage-summary-band">
      <div className="market-data-linkage-summary-metrics">
        <div>
          <span className="market-data-dim-label">环境综合分</span>
          <strong className="market-data-linkage-summary-score">{scoreText}</strong>
          {compositeDetail ? (
            <span className="market-data-linkage-summary-detail" title={compositeDetail}>
              {compositeDetail}
            </span>
          ) : null}
        </div>
        {topCorrelation ? (
          <div>
            <span className="market-data-dim-label">Top 相关</span>
            <strong
              className="market-data-linkage-summary-score"
              title={topCorrelation.series_name}
            >
              {topCorrelation.series_name}
            </strong>
            <span className="market-data-linkage-summary-detail">
              1Y {formatCorrelation(topCorrelation.correlation_1y)} · lag {topCorrelation.lead_lag_days}d
            </span>
          </div>
        ) : null}
      </div>
      <div className="market-data-linkage-summary-actions">
        <button type="button" className="market-data-linkage-summary-link" onClick={onOpenSpreads}>
          看信用利差图 →
        </button>
        <button type="button" className="market-data-linkage-summary-link" onClick={onOpenLinkage}>
          看环境柱图 →
        </button>
      </div>
    </div>
  );
}
