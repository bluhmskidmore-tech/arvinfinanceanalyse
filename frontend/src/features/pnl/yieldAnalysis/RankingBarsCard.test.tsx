import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RankingBarsCard } from "./RankingBarsCard";

describe("RankingBarsCard", () => {
  it("renders total PnL and the three governed PnL components as readable parts", () => {
    render(
      <RankingBarsCard
        title="按投资组合"
        rows={[
          {
            key: "Route FI",
            total_pnl: 130_000,
            interest_income: 100_000,
            fair_value_change: 10_000,
            capital_gain: 20_000,
            proportion: 1,
          },
        ]}
      />,
    );

    const row = screen.getByTestId("yield-ranking-row-0");
    expect(within(row).getByText("13.00 万")).toBeInTheDocument();
    expect(within(row).getByText("514 利息")).toBeInTheDocument();
    expect(within(row).getByText("10.00 万")).toBeInTheDocument();
    expect(within(row).getByText("516 公允")).toBeInTheDocument();
    expect(within(row).getByText("1.00 万")).toBeInTheDocument();
    expect(within(row).getByText("517 投资收益")).toBeInTheDocument();
    expect(within(row).getByText("2.00 万")).toBeInTheDocument();
  });
});
