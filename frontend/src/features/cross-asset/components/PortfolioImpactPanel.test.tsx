import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { createRealMarketDataClient } from "../../../api/marketDataClient";
import { createRealMacroToolkitClient } from "../../../api/macroToolkitClient";
import { StrategySummaryCard } from "../../macro-toolkit/sections/MacroToolkitStrategySections";
import { buildMarketDataPageModel } from "../../market-data/pages/marketDataPageModel";
import { MarketDataLinkageSummaryCard } from "../../market-data/components/MarketDataLinkageSummaryCard";
import type { ComponentProps } from "react";
import { PortfolioImpactPanel } from "./PortfolioImpactPanel";
import macroResponse from "./macroPortfolioTruthfulness.fixture.json";
import strategyResponse from "./macroStrategyTruthfulness.fixture.json";
import scenarioResponses from "./macroScenarioSignalCoverage.fixture.json";

describe("macro HTTP to actual components", () => {
  it.each([[null, "无估算"], [0, "有估算"]] as const)("market summary distinguishes risk %s from real zero", async (value, text) => {
    const wire = { ...macroResponse, result: { ...macroResponse.result,
      portfolio_impact: { ...macroResponse.result.portfolio_impact, total_estimated_impact: value } } };
    const client = createRealMarketDataClient({ baseUrl: "", fetchImpl: vi.fn(async () => new Response(JSON.stringify(wire))) });
    const response = await client.getMacroBondLinkageAnalysis({ reportDate: "2026-10-06" });
    const model = buildMarketDataPageModel({ macroBondLinkageEnvelope: response });
    const query = { data: response, isLoading: false, isError: false } as ComponentProps<typeof MarketDataLinkageSummaryCard>["macroBondLinkageQuery"];
    render(<MemoryRouter><MarketDataLinkageSummaryCard macroBondLinkageQuery={query}
      macroBondLinkage={model.macroBondLinkage} macroBondLinkageWarnings={model.macroBondLinkageWarnings}
      hasPortfolioImpact={model.hasPortfolioImpact} requestedReportDate="2026-10-06" /></MemoryRouter>);
    expect(screen.getByTestId("market-data-linkage-summary-impact")).toHaveTextContent(text);
  });

  it("keeps missing risk unavailable and locates same-code entities by full available identity", async () => {
    const client = createRealMarketDataClient({ baseUrl: "", fetchImpl: vi.fn(async () => new Response(JSON.stringify(macroResponse))) });
    const response = await client.getMacroBondLinkageAnalysis({ reportDate: "2026-10-06" });
    const impact = response.result.portfolio_impact;
    render(<MemoryRouter><PortfolioImpactPanel impact={impact} /></MemoryRouter>);
    expect(screen.getByRole("status")).toHaveTextContent("风险输入不可用，合计估算不可用");
    expect(screen.getByText(/目标日 2026-10-06 · 风险日 2026-10-05/)).toHaveTextContent("最近可用日期");
    const details = screen.getByText("风险输入与实体证据").closest("details")!;
    fireEvent.click(within(details).getByText("风险输入与实体证据"));
    expect(within(details).getByText(/已观测行覆盖/)).toHaveTextContent("DV01 1/2");
    fireEvent.click(screen.getByRole("button", { name: "SYN001 · P2 · C2 · AC · USD" }));
    expect(screen.getByTestId("macro-risk-entity-detail")).toHaveTextContent("组合 P2 · 成本中心 C2 · 会计分类 AC · 原币 USD");
    expect(screen.getByRole("link", { name: "查看该券" })).toHaveAttribute("href", "/bond-trading-desk?bond_code=SYN001&report_date=2026-10-05");
    fireEvent.click(screen.getByRole("button", { name: "返回组合估算" }));
    expect(screen.queryByTestId("macro-risk-entity-detail")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SYN001 · P1 · C1 · FVOCI · CNY" })).toBeInTheDocument();
    expect(screen.getByText(/目标日 2026-10-06/)).toBeInTheDocument();
  });

  it("does not display a zero ratio for a zero market value and preserves a genuine zero impact", () => {
    render(<MemoryRouter><PortfolioImpactPanel impact={{
      total_estimated_impact: "0", impact_ratio_to_market_value: null,
      portfolio_market_value: "0", status: "available", risk_report_date: "2026-10-06",
      requested_report_date: "2026-10-06", ratio_unavailable_reason: "market_value_zero",
    }} /></MemoryRouter>);
    expect(screen.getByText(/组合市值为零，比例不可计算/)).toBeInTheDocument();
    expect(screen.queryByText(/0\.00%/)).not.toBeInTheDocument();
    const panel = screen.getByTestId("cross-asset-linkage-portfolio-impact");
    expect(panel.querySelector('[title="0 元"]')).toHaveTextContent(/0/);
  });

  it("discards selected evidence when the response moves to another risk scope", async () => {
    const client = createRealMarketDataClient({ baseUrl: "", fetchImpl: vi.fn(async () => new Response(JSON.stringify(macroResponse))) });
    const response = await client.getMacroBondLinkageAnalysis({ reportDate: "2026-10-06" });
    const impact = response.result.portfolio_impact;
    const { rerender } = render(<MemoryRouter><PortfolioImpactPanel impact={{ ...impact, status: "unavailable", entity_link_status: "aggregation_inputs" }} /></MemoryRouter>);
    fireEvent.click(screen.getByText("风险输入与实体证据"));
    fireEvent.click(screen.getByRole("button", { name: "SYN001 · P2 · C2 · AC · USD" }));
    rerender(<MemoryRouter><PortfolioImpactPanel impact={{ status: "unavailable", entities: [], risk_report_date: null }} /></MemoryRouter>);
    expect(screen.queryByTestId("macro-risk-entity-detail")).not.toBeInTheDocument();
    expect(screen.getByText("没有同日实体明细，不能逐券定位。")).toBeInTheDocument();
  });

  it("requires a new entity selection when a risk version changes despite reused entity IDs", () => {
    const impact = macroResponse.result.portfolio_impact as ComponentProps<typeof PortfolioImpactPanel>["impact"];
    const { rerender } = render(<MemoryRouter><PortfolioImpactPanel impact={impact} /></MemoryRouter>);
    fireEvent.click(screen.getByText("风险输入与实体证据"));
    fireEvent.click(screen.getByRole("button", { name: "SYN001 · P2 · C2 · AC · USD" }));
    expect(screen.getByTestId("macro-risk-entity-detail")).toBeInTheDocument();
    rerender(<MemoryRouter><PortfolioImpactPanel impact={{ ...impact, risk_source_version: "synthetic-next-version" }} /></MemoryRouter>);
    expect(screen.queryByTestId("macro-risk-entity-detail")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SYN001 · P2 · C2 · AC · USD" })).toBeInTheDocument();
  });

  it("distinguishes absent macro signals from absent portfolio risk", () => {
    render(<MemoryRouter><PortfolioImpactPanel impact={{ status: "unavailable",
      availability_reason: "macro_signal_unavailable", portfolio_dv01: "100", portfolio_cs01: "40",
      estimated_rate_change_bps: null, estimated_spread_widening_bps: null, total_estimated_impact: null,
    }} /></MemoryRouter>);
    expect(screen.getByRole("status")).toHaveTextContent("宏观信号不可用，合计估算不可用");
    expect(screen.queryByText("风险输入不可用，合计估算不可用。")).not.toBeInTheDocument();
  });

  it("does not render unverified NAV after the real strategy HTTP client", async () => {
    const client = createRealMacroToolkitClient({ baseUrl: "", fetchImpl: vi.fn(async () => new Response(JSON.stringify(strategyResponse))) });
    const response = await client.getMacroToolkitStrategySummaries();
    const summaries = response.result.strategy_summaries;
    const { container } = render(<>{summaries.map((strategy) => <StrategySummaryCard key={strategy.key} strategy={strategy} />)}</>);
    const cards = container.querySelectorAll(".macro-toolkit-strategy-card");
    expect(cards).toHaveLength(4);
    for (const card of Array.from(cards).slice(0, 2)) {
      expect(card.querySelector(".macro-toolkit-strategy-metric b")).toHaveTextContent("不可用");
      expect(card).toHaveTextContent("原始收盘价缺少复权与股息证据");
      expect(card).toHaveTextContent("昨日收盘仓位计今日收益");
      expect(card).toHaveTextContent("未配置比较基准");
    }
    expect(screen.queryByText("真实累计净值")).not.toBeInTheDocument();
    expect(cards[2]).toHaveTextContent("多因子选股");
    expect(cards[2]).toHaveTextContent("已完成");
  });
});


describe("scenario-axis HTTP coverage", () => {
  // These fixtures project actual synthetic HTTP responses to the consumed fields.
  it.each([
    ["inflation_only", "宏观信号不可用", "不可用", "不可用"],
    ["rate_only", "情景信号覆盖不完整", "+26.83 bp", "不可用"],
    ["liquidity_only", "情景信号覆盖不完整", "不可用", "+14.50 bp"],
    ["neutral_missing_rate_risk", "风险输入覆盖不完整", "0.00 bp", "0.00 bp"],
    ["neutral_missing_all_risk", "风险输入不可用", "0.00 bp", "0.00 bp"],
  ] as const)("keeps missing inputs distinct in %s", async (scenario, reason, rate, spread) => {
    const client = createRealMarketDataClient({ baseUrl: "", fetchImpl: vi.fn(async () => new Response(JSON.stringify(scenarioResponses[scenario]))) });
    const response = await client.getMacroBondLinkageAnalysis({ reportDate: "2026-10-06" });
    render(<MemoryRouter><PortfolioImpactPanel impact={response.result.portfolio_impact} /></MemoryRouter>);
    expect(screen.getByRole("status")).toHaveTextContent(`${reason}，合计估算不可用`);
    expect(screen.getByText("利率变动").parentElement?.querySelector(".cross-asset-linkage-portfolio-impact__value")).toHaveTextContent(rate);
    expect(screen.getByText("利差走阔").parentElement?.querySelector(".cross-asset-linkage-portfolio-impact__value")).toHaveTextContent(spread);
    expect(screen.getByText("合计估算").parentElement?.querySelector(".cross-asset-linkage-portfolio-impact__value")).toHaveTextContent("不可用");
    expect(screen.queryByText(/0\.00%/)).not.toBeInTheDocument();
    if (scenario === "rate_only" || scenario === "liquidity_only") {
      expect(screen.getByText(/占组合市值/)).toHaveTextContent("不可用（情景信号覆盖不完整）");
      expect(screen.queryByText(/风险输入覆盖不完整/)).not.toBeInTheDocument();
    }
  });

  it("preserves observed neutral scenario axes despite missing growth and inflation", async () => {
    const client = createRealMarketDataClient({ baseUrl: "", fetchImpl: vi.fn(async () => new Response(JSON.stringify(scenarioResponses.observed_neutral_axes))) });
    const response = await client.getMacroBondLinkageAnalysis({ reportDate: "2026-10-06" });
    expect(response.result.environment_score.signal_status).toBe("partial");
    render(<MemoryRouter><PortfolioImpactPanel impact={response.result.portfolio_impact} /></MemoryRouter>);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByText("合计估算").parentElement?.querySelector(".cross-asset-linkage-portfolio-impact__value")).toHaveTextContent("0.00元");
    expect(screen.getByText(/占组合市值/)).toHaveTextContent("+0.00%");
  });
});
