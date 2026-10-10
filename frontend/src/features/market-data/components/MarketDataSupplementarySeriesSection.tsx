import type { ReactNode } from "react";

import { PageAsyncSection } from "../../../components/page/PageAsyncSection";

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
  const tierSummaryParts = [
    stableSeriesCount > 0 ? `稳定 ${stableSeriesCount} 条` : null,
    fallbackSeriesCount > 0 ? `降级 ${fallbackSeriesCount} 条` : null,
  ].filter(Boolean);
  // §7「·」配额：可见元信息最多 1 个分隔符；外汇组数在下方外汇轨已有（§6 去重），
  // 其余字段收进 title 全文。
  const tierSummary = tierSummaryParts.join(" · ");
  const summaryDetail = [
    ...tierSummaryParts,
    showFxSection && fxGroupCount > 0 ? `外汇 ${fxGroupCount} 组` : null,
    "正式利率见上方核心观察",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <section
      id="market-data-macro-series"
      className="market-data-section-block"
      data-testid="market-data-supplementary-series-section"
    >
      <div className="market-data-supplementary-head">
        <div>
          <span className="market-data-supplementary-kicker">更多读数</span>
          <h2 className="market-data-supplementary-title">04 宏观与外汇序列</h2>
        </div>
        <p className="market-data-supplementary-summary" title={summaryDetail}>
          {tierSummary || `分析口径 · ${macroSeriesCount} 条序列`}
        </p>
      </div>

      <div className="market-data-supplementary-panel" data-testid="market-data-supplementary-panel">
        <PageAsyncSection
          title=""
          isLoading={macroLoading}
          isError={macroError}
          isEmpty={macroEmpty}
          fillHeight={false}
          onRetry={onMacroRetry}
        >
          <div
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
        </PageAsyncSection>

        {showFxSection ? (
          <>
            <div className="market-data-supplementary-tier-rail" data-testid="market-data-fx-tier-rail">
              外汇分析 · {fxGroupCount} 组
            </div>
            <PageAsyncSection
              title=""
              isLoading={fxLoading}
              isError={fxError}
              isEmpty={fxEmpty}
              fillHeight={false}
              onRetry={onFxRetry}
            >
              {fxDeck}
            </PageAsyncSection>
          </>
        ) : null}
      </div>

      {missingStableDeck ? (
        <div className="market-data-supplementary-missing">{missingStableDeck}</div>
      ) : null}
    </section>
  );
}
