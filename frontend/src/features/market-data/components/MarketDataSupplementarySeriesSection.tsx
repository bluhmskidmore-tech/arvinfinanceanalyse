import type { ReactNode } from "react";

import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";

type MarketDataSupplementarySeriesSectionProps = {
  macroSeriesCount: number;
  stableSeriesCount: number;
  fallbackSeriesCount: number;
  fxGroupCount: number;
  macroChartFirst?: ReactNode;
  macroDeck: ReactNode;
  macroLoading: boolean;
  macroError: boolean;
  macroEmpty: boolean;
  onMacroRetry: () => void;
  fxDeck: ReactNode;
  fxLoading: boolean;
  fxError: boolean;
  fxEmpty: boolean;
  onFxRetry: () => void;
  missingStableDeck?: ReactNode;
  showFxSection?: boolean;
};

export function MarketDataSupplementarySeriesSection({
  macroSeriesCount,
  stableSeriesCount,
  fallbackSeriesCount,
  fxGroupCount,
  macroChartFirst,
  macroDeck,
  macroLoading,
  macroError,
  macroEmpty,
  onMacroRetry,
  fxDeck,
  fxLoading,
  fxError,
  fxEmpty,
  onFxRetry,
  missingStableDeck,
  showFxSection = true,
}: MarketDataSupplementarySeriesSectionProps) {
  const tierSummary = [
    stableSeriesCount > 0 ? `稳定 ${stableSeriesCount}` : null,
    fallbackSeriesCount > 0 ? `降级 ${fallbackSeriesCount}` : null,
    showFxSection && fxGroupCount > 0 ? `外汇 ${fxGroupCount} 组` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <section className="market-data-section-block" data-testid="market-data-supplementary-series-section">
      <div className="market-data-supplementary-head">
        <div>
          <span className="market-data-supplementary-kicker">更多读数</span>
          <h2 className="market-data-supplementary-title">宏观与外汇序列</h2>
        </div>
        <p className="market-data-supplementary-summary">
          {tierSummary || `分析口径 · ${macroSeriesCount} 条序列`}
          {tierSummary ? " · 正式利率见上方核心观察" : null}
        </p>
      </div>

      <div className="market-data-supplementary-panel" data-testid="market-data-supplementary-panel">
        <AsyncSection
          title=""
          isLoading={macroLoading}
          isError={macroError}
          isEmpty={macroEmpty}
          fillHeight={false}
          onRetry={onMacroRetry}
        >
          <div
            id="market-data-macro-series"
            className="market-data-supplementary-macro-body"
            data-testid="market-data-supplementary-macro-body"
          >
            {macroChartFirst ? (
              <div
                className="market-data-supplementary-chart-first"
                data-testid="market-data-macro-series-chart-first"
              >
                <h3 className="market-data-supplementary-chart-first-title">重点序列走势</h3>
                {macroChartFirst}
              </div>
            ) : null}
            {macroDeck}
          </div>
        </AsyncSection>

        {showFxSection ? (
          <>
            <div className="market-data-supplementary-tier-rail" data-testid="market-data-fx-tier-rail">
              外汇分析 · {fxGroupCount} 组
            </div>
            <AsyncSection
              title=""
              isLoading={fxLoading}
              isError={fxError}
              isEmpty={fxEmpty}
              fillHeight={false}
              onRetry={onFxRetry}
            >
              {fxDeck}
            </AsyncSection>
          </>
        ) : null}
      </div>

      {missingStableDeck ? (
        <div className="market-data-supplementary-missing">{missingStableDeck}</div>
      ) : null}
    </section>
  );
}
