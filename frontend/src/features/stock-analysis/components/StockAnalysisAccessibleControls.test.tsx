import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import type { FactorScreenCandidateItem } from "../../../api/contracts";
import type { StockStrategyLensItem } from "../lib/stockAnalysisPageModel";
import { StockAnalysisObservationPreview } from "./StockAnalysisObservationPreview";
import { StockAnalysisStrategyLensSection } from "./StockAnalysisStrategyLensSection";
import { StockAnalysisTab, StockAnalysisTabs } from "./StockAnalysisTabs";

function TabsHarness({ onSelectionChange }: { onSelectionChange: (key: string) => void }) {
  const [selectedKey, setSelectedKey] = useState("alpha");

  return (
    <StockAnalysisTabs
      aria-label="策略视图"
      selectedKey={selectedKey}
      onSelectionChange={(key) => {
        const nextKey = String(key);
        setSelectedKey(nextKey);
        onSelectionChange(nextKey);
      }}
    >
      <StockAnalysisTab key="alpha" title="甲策略">甲内容</StockAnalysisTab>
      <StockAnalysisTab key="beta" title="乙策略">乙内容</StockAnalysisTab>
      <StockAnalysisTab key="gamma" title="丙策略">丙内容</StockAnalysisTab>
    </StockAnalysisTabs>
  );
}

const factorCandidate: FactorScreenCandidateItem = {
  rank: 1,
  stock_code: "600000.SH",
  stock_name: "因子甲",
  sector_code: "801730",
  sector_name: "电力设备",
  industry: "电力设备",
  score: 0.8123,
  pe: 12.4,
  pb: 1.6,
  roe: 0.143,
  gross_margin: 0.32,
  three_month_return: 0.056,
  twelve_month_return: 0.184,
  dividend_yield: 0.021,
};

function strategyItem(key: string, label: string): StockStrategyLensItem {
  return {
    key,
    label,
    subtitle: "候选复核策略",
    value: "1",
    unitLabel: "只候选",
    detail: "仅供观察，不生成交易指令。",
    tone: "positive",
    state: "ready",
    statusLabel: "可观察",
    statusDetail: "证据已返回",
    blockerLabel: "无新增阻断",
    focusLabel: "价格确认",
    actionLabel: "查看策略区",
    candidateCountLabel: "1 只候选",
    dateLabel: "数据日 2026-07-08",
    formulaLabel: "规则已记录",
    evidence: [{ key: "price", label: "价格", value: "已返回" }],
    candidates: [
      {
        key: `${key}-candidate`,
        rankLabel: "#1",
        stockCode: "600000.SH",
        stockName: "因子甲",
        sectorName: "电力设备",
        metricLabel: "评分 0.81",
      },
    ],
    scrollTarget: `${key}-section`,
    progress: 0.8,
  };
}

describe("stock-analysis accessible controls", () => {
  it("moves tab focus and selection with arrows, Home, End, and wrapping", async () => {
    const user = userEvent.setup();
    const onSelectionChange = vi.fn();
    render(<TabsHarness onSelectionChange={onSelectionChange} />);

    const alpha = screen.getByRole("tab", { name: "甲策略" });
    alpha.focus();

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "乙策略" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "乙策略" })).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "丙策略" })).toHaveFocus();

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "甲策略" })).toHaveFocus();

    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "丙策略" })).toHaveFocus();

    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "甲策略" })).toHaveFocus();
    expect(onSelectionChange.mock.calls.map(([key]) => key)).toEqual([
      "beta",
      "gamma",
      "alpha",
      "gamma",
      "alpha",
    ]);
  });

  it("uses unique tab and panel IDs for every labeled tablist instance", () => {
    render(
      <>
        <TabsHarness onSelectionChange={() => undefined} />
        <StockAnalysisTabs aria-label="诊断视图" selectedKey="alpha">
          <StockAnalysisTab key="alpha" title="甲诊断">甲诊断内容</StockAnalysisTab>
        </StockAnalysisTabs>
      </>,
    );

    expect(screen.getByRole("tablist", { name: "策略视图" })).toBeInTheDocument();
    expect(screen.getByRole("tablist", { name: "诊断视图" })).toBeInTheDocument();
    const tabs = screen.getAllByRole("tab");
    const tabIds = tabs.map((tab) => tab.id);
    const controlledPanelIds = tabs.map((tab) => tab.getAttribute("aria-controls"));
    expect(new Set(tabIds).size).toBe(tabIds.length);
    expect(new Set(controlledPanelIds).size).toBe(controlledPanelIds.length);
    tabs.forEach((tab) => {
      const panel = document.getElementById(tab.getAttribute("aria-controls") ?? "");
      expect(panel).not.toBeNull();
      expect(panel).toHaveAttribute("role", "tabpanel");
      expect(panel).toHaveAttribute("aria-labelledby", tab.id);
      if (tab.getAttribute("aria-selected") === "true") {
        expect(panel).not.toHaveAttribute("hidden");
        expect(panel).not.toBeEmptyDOMElement();
      } else {
        expect(panel).toHaveAttribute("hidden");
        expect(panel).toBeEmptyDOMElement();
      }
    });
    expect(screen.getByRole("tabpanel", { name: "甲策略" })).toHaveTextContent("甲内容");
    expect(screen.getAllByRole("tabpanel", { hidden: true })).toHaveLength(tabs.length);
  });

  it("opens a factor candidate once from a named native button while preserving four columns", async () => {
    const user = userEvent.setup();
    const onOpenFactorDetail = vi.fn();
    render(
      <StockAnalysisObservationPreview
        factorScreenPayload={{
          as_of_date: "2026-07-08",
          formula_version: "rv_factor_v1",
          market_state: "WARM",
          input_stock_count: 1,
          candidate_count: 1,
          coverage_note: "因子覆盖 1/1 只",
          items: [factorCandidate],
        }}
        factorPreviewItems={[factorCandidate]}
        factorScreenCoverageNote={null}
        meanReversionMarketActive={false}
        meanReversionPayload={undefined}
        meanReversionPreviewItems={[]}
        onOpenFactorDetail={onOpenFactorDetail}
        onOpenMeanReversionDetail={() => undefined}
      />,
    );

    expect(screen.getAllByRole("columnheader")).toHaveLength(4);
    const row = screen.getByTestId("factor-preview-row-600000.SH");
    expect(row).not.toHaveAttribute("role", "button");
    const detailButton = within(row).getByRole("button", { name: "查看因子甲（600000.SH）详情" });
    detailButton.focus();
    expect(detailButton).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onOpenFactorDetail).toHaveBeenCalledTimes(1);
    expect(onOpenFactorDetail).toHaveBeenCalledWith(factorCandidate);
  });

  it("keeps strategy cards semantic and separates navigation from details disclosure", async () => {
    const user = userEvent.setup();
    const onScrollToSection = vi.fn();
    render(
      <StockAnalysisStrategyLensSection
        items={[strategyItem("alpha", "策略甲"), strategyItem("beta", "策略乙")]}
        onScrollToSection={onScrollToSection}
      />,
    );

    expect(screen.getByRole("heading", { name: "2 策略台账" })).toBeInTheDocument();
    const card = screen.getByTestId("stock-analysis-strategy-lens-alpha");
    expect(card.tagName).toBe("ARTICLE");
    expect(card).not.toHaveAttribute("role", "button");
    expect(card).not.toHaveAttribute("tabindex");

    fireEvent.click(within(card).getByText("证据口径"));
    expect(onScrollToSection).not.toHaveBeenCalled();

    await user.click(within(card).getByRole("button", { name: "前往策略甲复核区" }));
    expect(onScrollToSection).toHaveBeenCalledTimes(1);
    expect(onScrollToSection).toHaveBeenCalledWith("alpha-section");
  });
});
