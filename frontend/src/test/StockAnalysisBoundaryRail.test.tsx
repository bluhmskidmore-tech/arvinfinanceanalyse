import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StockAnalysisBoundaryRail } from "../features/stock-analysis/components/StockAnalysisBoundaryRail";
import type {
  StockAnalysisEvidenceStatusItem,
  StockDataBoundarySummary,
} from "../features/stock-analysis/lib/stockAnalysisPageModel";
import type { LivermoreStrategyPayload } from "../api/contracts";

const boundaryItems: StockAnalysisEvidenceStatusItem[] = [
  {
    key: "as-of-date",
    label: "数据日期",
    statusLabel: "2026-06-05",
    tone: "positive",
    detail: "使用最新可用交易日",
  },
  {
    key: "rule-version",
    label: "规则版本",
    statusLabel: "rv-test",
    tone: "positive",
    detail: "可用 3 / 阻断 1",
  },
  {
    key: "quality",
    label: "数据质量",
    statusLabel: "需复核",
    tone: "warning",
    detail: "供应商降级",
  },
  {
    key: "exceptions",
    label: "例外状态",
    statusLabel: "3 条边界",
    tone: "warning",
    detail: "诊断 1 / 缺口 1 / 阻断 1",
  },
];

const boundarySummary: StockDataBoundarySummary = {
  boundaryCount: 3,
  diagnosticsCount: 1,
  dataGapCount: 1,
  unsupportedCount: 1,
  freshnessLabel: "T+0",
  summaryLabel: "3 条边界",
  detailLabel: "诊断 1 / 缺口 1 / 阻断 1 / T+0",
  topMessages: [],
};

const strategyPayload = {
  diagnostics: [
    {
      code: "breadth_missing",
      severity: "warning",
      message: "Breadth inputs are unavailable.",
      input_family: "market_breadth",
    },
  ],
  data_gaps: [
    {
      input_family: "market_breadth",
      status: "missing",
      evidence: "Breadth table is empty.",
    },
  ],
  supported_outputs: ["market_gate", "sector_rank"],
  unsupported_outputs: [
    {
      key: "risk_exit",
      reason: "position snapshot missing",
    },
  ],
} as LivermoreStrategyPayload;

describe("StockAnalysisBoundaryRail", () => {
  it("renders compact boundary status and opens the full diagnostic drawer from the inline action by default", async () => {
    render(
      <StockAnalysisBoundaryRail
        boundaryItems={boundaryItems}
        boundarySummary={boundarySummary}
        strategyPayload={strategyPayload}
      />,
    );

    const rail = screen.getByTestId("stock-analysis-boundary-rail");
    expect(rail).toHaveTextContent("数据口径与边界");
    expect(rail).toHaveTextContent("数据日期");
    expect(rail).toHaveTextContent("规则版本");
    expect(rail).toHaveTextContent("数据质量");
    expect(rail).toHaveTextContent("例外状态");
    expect(rail).not.toHaveTextContent("Breadth inputs are unavailable.");

    const summary = screen.getByTestId("stock-analysis-boundary-summary");
    expect(summary).toHaveTextContent("3 条边界");
    expect(summary).toHaveTextContent("诊断 1 / 缺口 1 / 阻断 1");

    fireEvent.click(within(rail).getByRole("button", { name: "查看完整诊断" }));

    expect(await screen.findByText("数据口径诊断")).toBeInTheDocument();
    expect(screen.getByText("警告")).toBeInTheDocument();
    expect(screen.getByText("市场宽度输入不可用。")).toBeInTheDocument();
    expect(screen.queryByText("Breadth inputs are unavailable.")).not.toBeInTheDocument();
    expect(screen.getByText("数据缺口")).toBeInTheDocument();
    expect(screen.getByText("可用输出")).toBeInTheDocument();
    expect(screen.getByText("阻断输出")).toBeInTheDocument();
    expect(screen.queryByText("warning / Warning")).not.toBeInTheDocument();
  });

  it("supports controlled drawer state and can hide the inline diagnostics action", async () => {
    const onOpenDiagnostics = vi.fn();
    const onCloseDiagnostics = vi.fn();
    const { rerender } = render(
      <StockAnalysisBoundaryRail
        boundaryItems={boundaryItems}
        boundarySummary={boundarySummary}
        strategyPayload={strategyPayload}
        diagnosticsDrawerOpen={false}
        onOpenDiagnostics={onOpenDiagnostics}
        onCloseDiagnostics={onCloseDiagnostics}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "查看完整诊断" }));
    expect(onOpenDiagnostics).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("数据口径诊断")).not.toBeInTheDocument();

    rerender(
      <StockAnalysisBoundaryRail
        boundaryItems={boundaryItems}
        boundarySummary={boundarySummary}
        strategyPayload={strategyPayload}
        diagnosticsDrawerOpen
        onOpenDiagnostics={onOpenDiagnostics}
        onCloseDiagnostics={onCloseDiagnostics}
        showInlineDiagnosticsAction={false}
      />,
    );

    expect(screen.queryByRole("button", { name: "查看完整诊断" })).not.toBeInTheDocument();
    expect(await screen.findByText("数据口径诊断")).toBeInTheDocument();

    const closeButton = document.querySelector(".ant-drawer-close");
    expect(closeButton).not.toBeNull();
    fireEvent.click(closeButton as Element);
    expect(onCloseDiagnostics).toHaveBeenCalledTimes(1);
  });
});
