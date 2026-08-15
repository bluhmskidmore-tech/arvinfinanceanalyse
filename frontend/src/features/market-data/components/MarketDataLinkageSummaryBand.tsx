import type { MacroBondLinkageTopCorrelation } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { formatCorrelation } from "../lib/marketDataLinkageFormat";

type MarketDataLinkageSummaryBandProps = {
  compositeScore: number | null | undefined;
  compositeDetail?: string;
  /** 口径/极性等实现细节说明，收进 title 不占正文。 */
  compositeDetailTitle?: string;
  topCorrelation?: MacroBondLinkageTopCorrelation | null;
  onOpenSpreads: () => void;
  onOpenLinkage: () => void;
};

export function MarketDataLinkageSummaryBand({
  compositeScore,
  compositeDetail,
  compositeDetailTitle,
  topCorrelation,
  onOpenSpreads,
  onOpenLinkage,
}: MarketDataLinkageSummaryBandProps) {
  const scoreText =
    compositeScore != null && Number.isFinite(compositeScore)
      ? compositeScore.toFixed(2)
      : EM_DASH;

  return (
    <div className="market-data-linkage-summary-band" data-testid="market-data-linkage-summary-band">
      <div className="market-data-linkage-summary-metrics">
        <div>
          <span className="market-data-dim-label">环境综合分</span>
          <strong className="market-data-linkage-summary-score">{scoreText}</strong>
          {compositeDetail ? (
            <span
              className="market-data-linkage-summary-detail"
              title={compositeDetailTitle ? `${compositeDetail}\n${compositeDetailTitle}` : compositeDetail}
            >
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
              1Y {formatCorrelation(topCorrelation.correlation_1y)} · 滞后 {topCorrelation.lead_lag_days} 天
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
