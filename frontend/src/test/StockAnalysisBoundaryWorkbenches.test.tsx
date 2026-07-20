import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  StockAnalysisErrorWorkbench,
  StockAnalysisLoadingWorkbench,
} from "../features/stock-analysis/components/StockAnalysisBoundaryWorkbenches";

describe("StockAnalysisBoundaryWorkbenches", () => {
  it("renders the stock-analysis loading skeleton with stable test id", () => {
    render(<StockAnalysisLoadingWorkbench />);

    const loadingWorkbench = screen.getByTestId("stock-analysis-loading-workbench");
    expect(loadingWorkbench).toBeInTheDocument();
    expect(loadingWorkbench).toHaveClass(
      "stock-analysis-boundary-workbench",
      "stock-analysis-boundary-workbench--loading",
    );
    expect(loadingWorkbench).toHaveAttribute("aria-label", "股票分析加载态");
    expect(loadingWorkbench.outerHTML).not.toMatch(
      /animate-pulse|bg-zinc|rounded-(?:xl|2xl)|shadow-sm/,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders the stock-analysis error workbench as an alert with the provided message", () => {
    render(<StockAnalysisErrorWorkbench message="backend unavailable" />);

    const errorWorkbench = screen.getByTestId("stock-analysis-error-workbench");
    expect(errorWorkbench).toHaveAttribute("role", "alert");
    expect(errorWorkbench).toHaveAttribute("aria-label", "股票分析错误态");
    expect(errorWorkbench).toHaveClass(
      "stock-analysis-boundary-workbench",
      "stock-analysis-boundary-workbench--error",
    );
    expect(errorWorkbench.outerHTML).not.toMatch(
      /bg-white|(?:bg|border|text)-(?:zinc|red|amber)-|rounded-(?:xl|2xl)|shadow-sm/,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("backend unavailable");
    expect(screen.getByTestId("stock-analysis-error-decision-panel")).toHaveClass(
      "stock-analysis-boundary-workbench__decision-panel",
    );
    const supplement = screen.getByTestId("stock-analysis-error-supplement");
    expect(supplement).toHaveAttribute("aria-label", "错误态补充信息");
    expect(supplement).toHaveTextContent("策略复核主接口");
    expect(supplement).toHaveTextContent("GAP-STOCK-ANALYSIS-PAGE");
    expect(supplement).toHaveTextContent("恢复供数后复核");
    expect(supplement).not.toHaveTextContent("livermore");
  });

  it("keeps retry behavior and exposes the retrying state", () => {
    const onRetry = vi.fn();
    const { rerender } = render(
      <StockAnalysisErrorWorkbench message="backend unavailable" onRetry={onRetry} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
    expect(onRetry).toHaveBeenCalledTimes(1);

    rerender(
      <StockAnalysisErrorWorkbench
        message="backend unavailable"
        onRetry={onRetry}
        isRetrying
      />,
    );
    expect(screen.getByRole("button", { name: "读取中" })).toBeDisabled();
  });
});
