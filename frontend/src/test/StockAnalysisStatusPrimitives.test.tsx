import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  CompactStatusTile,
  StatusIcon,
} from "../features/stock-analysis/components/StockAnalysisStatusPrimitives";

describe("StockAnalysisStatusPrimitives", () => {
  it("renders status icons as decorative elements with tone classes", () => {
    const { container } = render(<StatusIcon tone="warning">!</StatusIcon>);
    const icon = container.querySelector("span");

    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(icon).toHaveClass("text-warning-700");
    expect(icon).toHaveTextContent("!");
  });

  it("builds compact status tile aria labels from text value and detail", () => {
    render(
      <CompactStatusTile
        icon={<span>i</span>}
        label="优化"
        value="待查"
        detail="T+5"
        tone="negative"
        testId="status-tile"
        title="优化诊断"
        className="extra-class"
      />,
    );

    const tile = screen.getByTestId("status-tile");
    expect(tile).toHaveAttribute("role", "status");
    expect(tile).toHaveAttribute("aria-label", "优化 待查 T+5");
    expect(tile).toHaveAttribute("title", "优化诊断");
    expect(tile).toHaveClass("extra-class");
    expect(screen.getByText("优化")).toHaveClass("text-danger-600");
    expect(screen.getByText("待查")).toBeInTheDocument();
    expect(screen.getByText("T+5")).toBeInTheDocument();
  });

  it("omits non-text React nodes from compact tile aria label", () => {
    render(
      <CompactStatusTile
        icon={<span>i</span>}
        label="共振"
        value={<span data-testid="node-value">3 组</span>}
        detail={<span data-testid="node-detail">多策略</span>}
        testId="node-tile"
      />,
    );

    expect(screen.getByTestId("node-tile")).toHaveAttribute("aria-label", "共振");
    expect(screen.getByTestId("node-value")).toHaveTextContent("3 组");
    expect(screen.getByTestId("node-detail")).toHaveTextContent("多策略");
  });
});
