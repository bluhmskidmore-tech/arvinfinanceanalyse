import type { ReactNode } from "react";

import { MarketDataSeriesCategoryCard } from "./MarketDataSeriesCategoryCard";

type MarketDataLiquidityDeckProps = {
  moneyMarketCount: number;
  ncdRowCount: number;
  moneyMarketSlot: ReactNode;
  ncdSlot: ReactNode;
};

export function MarketDataLiquidityDeck({
  moneyMarketCount,
  ncdRowCount,
  moneyMarketSlot,
  ncdSlot,
}: MarketDataLiquidityDeckProps) {
  return (
    <div
      id="market-data-liquidity-deck"
      className="market-data-category-deck-grid market-data-liquidity-deck"
      data-testid="market-data-liquidity-deck"
    >
      <MarketDataSeriesCategoryCard
        title="资金市场"
        caption="DR007、回购与 Shibor 等资金利率；下方 mini 图默认展示 DR007。"
        count={moneyMarketCount}
        tone="liquidity"
        testId="market-data-money-market-card"
      >
        {moneyMarketSlot}
      </MarketDataSeriesCategoryCard>

      <MarketDataSeriesCategoryCard
        title="同业存单"
        caption="Shibor 资金 proxy 矩阵；表格与热力并列（窄屏默认仅表）。"
        count={ncdRowCount}
        tone="liquidity"
        testId="market-data-ncd-card"
      >
        {ncdSlot}
      </MarketDataSeriesCategoryCard>
    </div>
  );
}
