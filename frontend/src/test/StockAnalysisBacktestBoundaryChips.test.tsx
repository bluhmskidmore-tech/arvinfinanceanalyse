import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BacktestBoundaryChips } from "../features/stock-analysis/components/StockAnalysisBacktestBoundaryChips";

describe("BacktestBoundaryChips", () => {
  it("summarizes non-empty missing inputs and localizes the first three chips", () => {
    render(
      <BacktestBoundaryChips
        label="组合回测"
        missingInputs={[
          "market_gate",
          "sector_rank",
          "factor_screen_candidates",
          " ",
          "external_vendor_cycle_feed",
        ]}
        testId="backtest-boundary"
      />,
    );

    const boundary = screen.getByTestId("backtest-boundary");
    expect(boundary).toHaveAttribute("role", "status");
    expect(boundary).toHaveAttribute("aria-label", "组合回测边界");
    expect(boundary).toHaveTextContent("代理口径");
    expect(boundary).toHaveTextContent("缺口 4");
    expect(boundary).toHaveTextContent("市场门控");
    expect(boundary).toHaveTextContent("板块强弱");
    expect(boundary).toHaveTextContent("多因子");
    expect(boundary).toHaveTextContent("+1");
    expect(boundary).not.toHaveTextContent("输入待确认");
  });

  it("shows zero gaps when every input is blank", () => {
    render(<BacktestBoundaryChips label="周期代理" missingInputs={["", "  "]} testId="empty-boundary" />);

    expect(screen.getByTestId("empty-boundary")).toHaveTextContent("缺口 0");
    expect(screen.getByTestId("empty-boundary")).not.toHaveTextContent("+");
  });
});
