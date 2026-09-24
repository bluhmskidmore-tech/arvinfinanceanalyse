import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StockAnalysisBacktestCaliberDisclosure } from "./StockAnalysisBacktestCaliberDisclosure";

describe("StockAnalysisBacktestCaliberDisclosure", () => {
  it("renders nothing when the model is null (field missing or fully empty)", () => {
    const { container } = render(<StockAnalysisBacktestCaliberDisclosure model={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the warning banner, sample split, and basis notes when present", () => {
    render(
      <StockAnalysisBacktestCaliberDisclosure
        model={{
          entryPriceWarning: "旧代际样本入场价为近似值，非真实成交价。",
          sampleGenerationLabel: "样本构成：旧源 12 笔 / 新源 8 笔",
          basisNotes: ["旧源按收盘价近似。", "新源按 T+1 开盘价计算。"],
        }}
      />,
    );

    expect(screen.getByTestId("stock-analysis-strategy-backtest-caliber-disclosure")).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-strategy-backtest-caliber-warning")).toHaveTextContent(
      "旧代际样本入场价为近似值，非真实成交价。",
    );
    expect(screen.getByTestId("stock-analysis-strategy-backtest-caliber-sample")).toHaveTextContent(
      "样本构成：旧源 12 笔 / 新源 8 笔",
    );
    expect(screen.getByTestId("stock-analysis-strategy-backtest-caliber-notes")).toHaveTextContent(
      "旧源按收盘价近似。",
    );
  });

  it("omits the warning banner when there is no entry price warning", () => {
    render(
      <StockAnalysisBacktestCaliberDisclosure
        model={{
          entryPriceWarning: null,
          sampleGenerationLabel: "样本构成：旧源 0 笔 / 新源 5 笔",
          basisNotes: [],
        }}
      />,
    );

    expect(screen.getByTestId("stock-analysis-strategy-backtest-caliber-disclosure")).toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-strategy-backtest-caliber-warning")).not.toBeInTheDocument();
  });
});
