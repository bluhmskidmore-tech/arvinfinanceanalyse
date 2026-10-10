import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StockAnalysisStrategyLensSection } from "../features/stock-analysis/components/StockAnalysisStrategyLensSection";
import type { StockStrategyLensItem } from "../features/stock-analysis/lib/stockAnalysisPageModel";

function lensItem(overrides: Partial<StockStrategyLensItem>): StockStrategyLensItem {
  return {
    key: "sample",
    label: "样例策略",
    subtitle: "样例",
    value: "0",
    unitLabel: "候选",
    detail: "样例详情",
    tone: "neutral",
    state: "empty",
    statusLabel: "0 候选",
    statusDetail: "无命中",
    blockerLabel: "无阻断",
    focusLabel: "继续观察",
    actionLabel: "查看观察池",
    candidateCountLabel: "0 只候选",
    dateLabel: "2026-04-29",
    formulaLabel: "rv_sample",
    evidence: [],
    candidates: [],
    verdict: null,
    scrollTarget: "target",
    progress: 0,
    ...overrides,
  };
}

describe("StockAnalysisStrategyLensSection", () => {
  it("keeps paused strategies separate from blocked strategy count", () => {
    render(
      <StockAnalysisStrategyLensSection
        items={[
          lensItem({ key: "ready", label: "可用策略", value: "3", state: "ready", statusLabel: "已返回" }),
          lensItem({ key: "blocked", label: "阻断策略", state: "blocked", statusLabel: "被阻断" }),
          lensItem({ key: "paused", label: "暂停策略", state: "paused", statusLabel: "门控暂停" }),
        ]}
        onScrollToSection={vi.fn()}
      />,
    );

    const section = screen.getByTestId("stock-analysis-strategy-lens");
    expect(section).toHaveTextContent("可用 1/3");
    expect(section).toHaveTextContent("候选 3");
    expect(section).toHaveTextContent("阻断 1");
    expect(section).toHaveTextContent("暂停 1");
  });

  it("renders the walk-forward verdict badge and ledger row when present", () => {
    render(
      <StockAnalysisStrategyLensSection
        items={[
          lensItem({
            key: "livermore",
            label: "趋势突破",
            verdict: {
              key: "weakened",
              label: "样本外削弱",
              detail: "5 个验证窗仅 1 窗正超额，链式超额 -54.58%。（2026-08-13 walk-forward 复验）",
            },
          }),
          lensItem({ key: "plain", label: "无判定策略", verdict: null }),
        ]}
        onScrollToSection={vi.fn()}
      />,
    );

    const badge = screen.getByTestId("stock-analysis-strategy-lens-livermore-verdict");
    expect(badge).toHaveTextContent("样本外削弱");
    expect(badge).toHaveAttribute("data-verdict", "weakened");
    expect(badge).toHaveAttribute("title", expect.stringContaining("walk-forward 复验"));
    expect(screen.queryByTestId("stock-analysis-strategy-lens-plain-verdict")).toBeNull();
  });

  it("keeps a weakened pool out of the primary card slot when another pool has candidates", () => {
    const candidate = {
      key: "c",
      rankLabel: "#1",
      stockCode: "300888.SZ",
      stockName: "候选",
      sectorName: "电子",
      metricLabel: "分 1.0",
    };
    render(
      <StockAnalysisStrategyLensSection
        items={[
          lensItem({
            key: "weak",
            label: "削弱池",
            candidates: [candidate],
            verdict: { key: "weakened", label: "样本外削弱", detail: "链式超额 -54.58%。" },
          }),
          lensItem({
            key: "theme",
            label: "题材突破",
            candidates: [candidate],
            verdict: { key: "supported", label: "样本外支持", detail: "5/5 窗正超额。" },
          }),
        ]}
        onScrollToSection={vi.fn()}
      />,
    );

    // 主卡位给样本外支持的池，削弱池落到"更多候选策略"折叠区。
    const grid = screen.getByTestId("stock-analysis-strategy-lens").querySelector(
      ".stock-analysis-page__strategy-lens-grid",
    );
    expect(grid).toHaveTextContent("题材突破");
    expect(grid).not.toHaveTextContent("削弱池");
    expect(screen.getByTestId("stock-analysis-strategy-lens-more-strategies")).toHaveTextContent(
      "削弱池",
    );
  });

  it("falls back to showing a weakened pool when it is the only one with candidates", () => {
    render(
      <StockAnalysisStrategyLensSection
        items={[
          lensItem({
            key: "weak",
            label: "削弱池",
            candidates: [
              {
                key: "c",
                rankLabel: "#1",
                stockCode: "300888.SZ",
                stockName: "候选",
                sectorName: "电子",
                metricLabel: "分 1.0",
              },
            ],
            verdict: { key: "weakened", label: "样本外削弱", detail: "链式超额 -54.58%。" },
          }),
          lensItem({ key: "empty", label: "空池", candidates: [] }),
        ]}
        onScrollToSection={vi.fn()}
      />,
    );

    const grid = screen.getByTestId("stock-analysis-strategy-lens").querySelector(
      ".stock-analysis-page__strategy-lens-grid",
    );
    expect(grid).toHaveTextContent("削弱池");
  });
});
