import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  StockAnalysisRiskExitRows,
  StockAnalysisRiskExitSection,
} from "../features/stock-analysis/components/StockAnalysisRiskExitRows";
import type { StockRiskExitRow } from "../features/stock-analysis/lib/stockAnalysisPageModel";

function riskRow(overrides: Partial<StockRiskExitRow> = {}): StockRiskExitRow {
  return {
    stockCode: "000001.SZ",
    stockName: "Alpha Bank",
    status: "triggered",
    latestClose: "9.10",
    exitWatchPrice: "9.80",
    reason: "Close stayed below the exit watch line.",
    distanceToExitPct: "-7.14%",
    exitDistanceBucket: "triggered",
    ...overrides,
  };
}

describe("StockAnalysisRiskExitRows", () => {
  it("renders compact risk rows and opens the selected risk detail", () => {
    const triggered = riskRow();
    const watch = riskRow({
      stockCode: "000002.SZ",
      stockName: "Beta Bank",
      status: "watch",
      distanceToExitPct: "+1.30%",
      exitDistanceBucket: "0-3%",
    });
    const onOpenRiskDetail = vi.fn();

    render(
      <StockAnalysisRiskExitRows
        rows={[triggered, watch]}
        unsupported={false}
        onOpenRiskDetail={onOpenRiskDetail}
      />,
    );

    expect(screen.getByTestId("stock-risk-row-000001.SZ")).toHaveAttribute("data-tone", "negative");
    expect(screen.getByTestId("stock-risk-row-000002.SZ")).toHaveAttribute("data-tone", "warning");
    expect(screen.getByText("Alpha Bank")).toBeInTheDocument();
    expect(screen.getByText("Beta Bank")).toBeInTheDocument();
    expect(screen.getAllByText("供数原因")).toHaveLength(2);
    expect(screen.queryByText("Close stayed below the exit watch line.")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("stock-risk-row-000002.SZ"));
    expect(onOpenRiskDetail).toHaveBeenCalledWith(watch);

    fireEvent.keyDown(screen.getByTestId("stock-risk-row-000001.SZ"), { key: "Enter" });
    expect(onOpenRiskDetail).toHaveBeenCalledWith(triggered);
  });

  it("caps visible risk rows at five and shows the appropriate empty state", () => {
    const rows = Array.from({ length: 6 }, (_, index) =>
      riskRow({
        stockCode: `00000${index + 1}.SZ`,
        stockName: `Risk ${index + 1}`,
      }),
    );

    const { rerender } = render(
      <StockAnalysisRiskExitRows rows={rows} unsupported={false} onOpenRiskDetail={vi.fn()} />,
    );

    expect(screen.getByText("Risk 5")).toBeInTheDocument();
    expect(screen.queryByText("Risk 6")).not.toBeInTheDocument();

    rerender(<StockAnalysisRiskExitRows rows={[]} unsupported onOpenRiskDetail={vi.fn()} />);
    expect(screen.getByText("持仓快照待补")).toBeInTheDocument();

    rerender(<StockAnalysisRiskExitRows rows={[]} unsupported={false} onOpenRiskDetail={vi.fn()} />);
    expect(screen.getByText("风险 0")).toBeInTheDocument();
  });

  it("renders the risk exit section with supply blocker and confluence failure state", () => {
    const row = riskRow();
    const onOpenRiskDetail = vi.fn();

    render(
      <StockAnalysisRiskExitSection
        rows={[row]}
        riskTriggeredCount={1}
        riskWatchCount={2}
        confluenceError
        unsupportedOutput={{
          key: "risk_exit",
          reason: "livermore_position_snapshot has no ACTIVE A-share rows.",
        }}
        onOpenRiskDetail={onOpenRiskDetail}
      />,
    );

    const section = screen.getByTestId("stock-analysis-risk-section");
    const strip = screen.getByTestId("stock-analysis-risk-strip");

    expect(section).toHaveTextContent("风险退出观察");
    expect(section).toHaveTextContent("1 触发 · 2 观察");
    expect(strip).toHaveTextContent("触发");
    expect(strip).toHaveTextContent("观察");
    expect(strip).toHaveTextContent("供数");
    expect(strip).toHaveTextContent("待补");
    expect(section).toHaveTextContent("联动观察暂不可用。");
    expect(section).toHaveTextContent("风险退出待补");
    expect(section).toHaveTextContent("持仓快照缺失");
    expect(section).not.toHaveTextContent("livermore_position_snapshot has no ACTIVE A-share rows.");

    fireEvent.click(screen.getByTestId("stock-risk-row-000001.SZ"));
    expect(onOpenRiskDetail).toHaveBeenCalledWith(row);
  });
});
