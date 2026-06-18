import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarketDataCoreObservationDeck } from "./MarketDataCoreObservationDeck";

describe("MarketDataCoreObservationDeck", () => {
  it("renders rate quote and macro depth as separate category cards", () => {
    render(
      <MarketDataCoreObservationDeck
        rateQuoteCount={3}
        rateQuoteSlot={<div data-testid="rate-slot">rate</div>}
        macroDepthSlot={<div data-testid="macro-slot">macro</div>}
        footer={<div data-testid="footer-slot">footer</div>}
      />,
    );

    expect(screen.getByTestId("market-data-macro-workbench")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-quote-card")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-macro-depth-card")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-quote-card")).toHaveAttribute("id", "market-data-term-structure");
    expect(screen.getByTestId("rate-slot")).toBeInTheDocument();
    expect(screen.getByTestId("macro-slot")).toBeInTheDocument();
    expect(screen.getByTestId("footer-slot")).toBeInTheDocument();
  });
});
