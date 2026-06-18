import type { ReactNode } from "react";

import { MarketDataSeriesCategoryCard } from "./MarketDataSeriesCategoryCard";

type MarketDataCoreObservationDeckProps = {
  rateQuoteCount: number;
  rateQuoteSlot: ReactNode;
  macroDepthSlot: ReactNode;
  footer?: ReactNode;
};

export function MarketDataCoreObservationDeck({
  rateQuoteCount,
  rateQuoteSlot,
  macroDepthSlot,
  footer,
}: MarketDataCoreObservationDeckProps) {
  return (
    <div
      id="market-data-core-workbench"
      className="market-data-category-deck-grid market-data-core-observation-deck"
      data-testid="market-data-macro-workbench"
    >
      <MarketDataSeriesCategoryCard
        id="market-data-term-structure"
        title="利率行情"
        caption="国债 / 国开 formal rates；表与期限结构图并列，sparkline 见「走势」列。"
        count={rateQuoteCount}
        tone="formal"
        testId="market-data-rate-quote-card"
      >
        {rateQuoteSlot}
      </MarketDataSeriesCategoryCard>

      <MarketDataSeriesCategoryCard
        title="宏观深度"
        caption="曲线走势、信用利差与联动环境；Tab 切换不同分析视图。"
        tone="analytical"
        testId="market-data-macro-depth-card"
      >
        {macroDepthSlot}
      </MarketDataSeriesCategoryCard>

      {footer ? <div className="market-data-core-observation-deck__footer">{footer}</div> : null}
    </div>
  );
}
