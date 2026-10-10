import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarketDataLiquidityDeck } from "./MarketDataLiquidityDeck";

describe("MarketDataLiquidityDeck", () => {
  it("renders money market and ncd as separate category cards", () => {
    render(
      <MarketDataLiquidityDeck
        moneyMarketCount={2}
        ncdRowCount={4}
        moneyMarketSlot={<div data-testid="money-slot">money</div>}
        ncdSlot={<div data-testid="ncd-slot">ncd</div>}
      />,
    );

    expect(screen.getByTestId("market-data-liquidity-deck")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-money-market-card")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-ncd-card")).toBeInTheDocument();
    expect(screen.getByTestId("money-slot")).toBeInTheDocument();
    expect(screen.getByTestId("ncd-slot")).toBeInTheDocument();
    expect(screen.getByText("2 条")).toBeInTheDocument();
    expect(screen.getByText("4 条")).toBeInTheDocument();
  });
});
