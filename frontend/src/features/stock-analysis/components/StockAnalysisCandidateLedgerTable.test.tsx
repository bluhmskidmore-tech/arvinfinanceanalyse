import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { StockCandidateReviewQueueItem } from "../lib/stockAnalysisPageModel";
import { StockAnalysisCandidateLedgerTable } from "./StockAnalysisCandidateLedgerTable";

function buildCandidate(overrides: Partial<StockCandidateReviewQueueItem> = {}): StockCandidateReviewQueueItem {
  return {
    rank: 1,
    stockCode: "000001.SZ",
    stockName: "Alpha",
    sectorCode: "801001",
    sectorName: "AI",
    headline: "观察候选 #1 · Alpha",
    pattern: "突破",
    patternNote: "量价结构已返回。",
    distanceToBreakoutPct: "+1.2%",
    reviewFocus: "核实公告催化后再确认候选状态。",
    primaryEvidence: [{ key: "close_vs_break", label: "收盘 vs 观察位", value: "21.9 / 21.8" }],
    supportingEvidence: [],
    boundaryEvidence: [],
    invalidationFocus: "跌回 MA20 下方即降级观察。",
    invalidationRules: ["跌回 MA20 下方即降级观察。"],
    rawFields: [],
    ...overrides,
  };
}

describe("StockAnalysisCandidateLedgerTable", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the same stock from two source modules without duplicate React keys", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    // 后端 review_queue 按 (source_module, stock_code) 去重：同一股票可在
    // 趋势候选与多因子候选各占一行，且都携带模块内 rank=1。
    const candidates = [
      buildCandidate({ headline: "趋势候选 #1 · Alpha" }),
      buildCandidate({ headline: "多因子候选 #1 · Alpha" }),
    ];

    render(
      <StockAnalysisCandidateLedgerTable
        candidates={candidates}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    expect(screen.getAllByTestId("stock-candidate-000001.SZ")).toHaveLength(2);

    const duplicateKeyWarnings = consoleError.mock.calls.filter((call) =>
      call.some(
        (arg) =>
          typeof arg === "string" && arg.includes("Encountered two children with the same key"),
      ),
    );
    expect(duplicateKeyWarnings).toEqual([]);
  });

  it("shows the low-liquidity badge with the daily amount as a tooltip when liquidityFloorPass is false", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[buildCandidate({ liquidityFloorPass: false, dailyAmountLabel: "日成交 0.80 亿" })]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const badge = screen.getByText("低流动");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("title", "日成交 0.80 亿");
  });

  it("hides the badge when the row passes the liquidity floor", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[buildCandidate({ liquidityFloorPass: true, dailyAmountLabel: "日成交 5.00 亿" })]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    expect(screen.queryByText("低流动")).not.toBeInTheDocument();
  });

  it("hides the badge when liquidity data is missing (null)", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[buildCandidate({ liquidityFloorPass: null, dailyAmountLabel: null })]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    expect(screen.queryByText("低流动")).not.toBeInTheDocument();
  });

  it("shows the equal-weight primary badge with the demoted risk_budget detail as a tooltip", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[
          buildCandidate({
            sizeHintLabel: "等权 20.0%",
            sizeHintDetail:
              "建议仓位以等权为主参考（当日门控敞口÷候选数，已含门控敞口）\n实验参考（样本外未支持）：risk_budget 仓位 ≤ 8.4%（EMA10 止损距离折算）",
          }),
        ]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const badge = screen.getByText("等权 20.0%");
    expect(badge).toBeInTheDocument();
    expect(badge.closest("[title]")).toHaveAttribute(
      "title",
      "建议仓位以等权为主参考（当日门控敞口÷候选数，已含门控敞口）\n实验参考（样本外未支持）：risk_budget 仓位 ≤ 8.4%（EMA10 止损距离折算）",
    );
  });

  it("keeps rendering the legacy raw-weight badge for pre-primary_basis responses", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[
          buildCandidate({
            sizeHintLabel: "仓位 ≤ 8.4%",
            sizeHintDetail: "建议仓位为单票权重上限参考（EMA10 止损距离折算）\n样本外验证：仅供参考",
          }),
        ]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const badge = screen.getByText("仓位 ≤ 8.4%");
    expect(badge).toBeInTheDocument();
    expect(badge.closest("[title]")).toHaveAttribute(
      "title",
      "建议仓位为单票权重上限参考（EMA10 止损距离折算）\n样本外验证：仅供参考",
    );
  });

  it("hides the position size hint badge when the backend omits the hint", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[buildCandidate({ sizeHintLabel: null, sizeHintDetail: null })]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    expect(screen.queryByText(/仓位 ≤/)).not.toBeInTheDocument();
  });
});
