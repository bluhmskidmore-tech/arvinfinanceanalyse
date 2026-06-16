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
});
