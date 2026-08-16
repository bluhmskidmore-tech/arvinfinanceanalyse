import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StockAnalysisGateConditionsCard } from "./StockAnalysisGateConditionsCard";
import type { StockMarketStateCard } from "../lib/stockAnalysisPageModel";

const baseMarketState: StockMarketStateCard = {
  title: "市场状态",
  state: "温和",
  exposureLabel: "50%",
  passedLabel: "4 / 4 条件通过",
  basisLabel: "分析口径",
  warnings: [],
  conditions: [],
  macroDisclosure: null,
  macroDisclosureDetail: null,
};

describe("StockAnalysisGateConditionsCard macro overlay", () => {
  it("keeps the footer to the exposure label when the macro cap is not applied", () => {
    render(<StockAnalysisGateConditionsCard marketState={baseMarketState} />);

    expect(screen.getByText("观察暴露 50%")).toBeInTheDocument();
    expect(
      screen.queryByTestId("stock-analysis-gate-macro-overlay"),
    ).not.toBeInTheDocument();
  });

  it("explains the exposure cap when the macro overlay is applied", () => {
    render(
      <StockAnalysisGateConditionsCard
        marketState={{
          ...baseMarketState,
          exposureLabel: "25%",
          macroDisclosure: {
            adjustmentLabel: "宏观调节 50%→25%",
            cycleStateLabel: "衰退",
            statusMarker: null,
            lagLabel: null,
          },
          macroDisclosureDetail: "宏观调节 50%→25% · 衰退",
        }}
      />,
    );

    expect(screen.getByText("观察暴露 25%")).toBeInTheDocument();
    expect(
      screen.getByTestId("stock-analysis-gate-macro-overlay"),
    ).toHaveTextContent("宏观调节 50%→25% · 衰退");
  });

  it("omits the cycle suffix when the overlay lacks a cycle state", () => {
    render(
      <StockAnalysisGateConditionsCard
        marketState={{
          ...baseMarketState,
          macroDisclosure: {
            adjustmentLabel: "宏观调节 50%→25%",
            cycleStateLabel: null,
            statusMarker: null,
            lagLabel: null,
          },
          macroDisclosureDetail: "宏观调节 50%→25%",
        }}
      />,
    );

    expect(
      screen.getByTestId("stock-analysis-gate-macro-overlay"),
    ).toHaveTextContent(/^宏观调节 50%→25%$/);
  });
});
