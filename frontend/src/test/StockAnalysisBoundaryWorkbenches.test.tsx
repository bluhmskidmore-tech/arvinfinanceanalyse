import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  StockAnalysisErrorWorkbench,
  StockAnalysisLoadingWorkbench,
} from "../features/stock-analysis/components/StockAnalysisBoundaryWorkbenches";

describe("StockAnalysisBoundaryWorkbenches", () => {
  it("renders the stock-analysis loading skeleton with stable test id", () => {
    render(<StockAnalysisLoadingWorkbench />);

    expect(screen.getByTestId("stock-analysis-loading-workbench")).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders the stock-analysis error workbench as an alert with the provided message", () => {
    render(<StockAnalysisErrorWorkbench message="backend unavailable" />);

    expect(screen.getByTestId("stock-analysis-error-workbench")).toHaveAttribute("role", "alert");
    expect(screen.getByRole("alert")).toHaveTextContent("backend unavailable");
  });
});
