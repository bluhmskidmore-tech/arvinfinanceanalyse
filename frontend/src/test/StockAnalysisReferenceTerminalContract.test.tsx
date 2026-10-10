import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../components/charts/BaseChart", () => ({
  BaseChart: () => <div data-testid="base-chart-stub" />,
}));

import { ResearchDeskActionRail } from "../features/stock-analysis/components/research-desk/ResearchDeskActionRail";
import { ResearchDeskSummary } from "../features/stock-analysis/components/research-desk/ResearchDeskSummary";
import type { StockCandidateReviewQueueItem } from "../features/stock-analysis/lib/stockAnalysisPageModel";
import {
  buildStockAnalysisResearchDeskModel,
  type ResearchDeskAuditRow,
  type ResearchDeskEndpointItem,
} from "../features/stock-analysis/lib/stockAnalysisResearchDeskModel";
import {
  StockAnalysisResearchDesk,
  type StockAnalysisResearchDeskProps,
} from "../features/stock-analysis/pages/StockAnalysisResearchDesk";

function expectElementBefore(first: HTMLElement, second: HTMLElement) {
  const relation = first.compareDocumentPosition(second);
  expect(relation & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
}

function buildCandidate(
  overrides: Partial<StockCandidateReviewQueueItem> = {},
): StockCandidateReviewQueueItem {
  return {
    rank: 1,
    stockCode: "300313.SZ",
    stockName: "天山生物",
    sectorCode: "801010",
    sectorName: "农林牧渔",
    headline: "最新信号已回补，仍需核实阻断证据。",
    sourcePool: "stock_candidates",
    sourcePoolLabel: "农林牧渔",
    walkForward: null,
    pattern: "阻断",
    patternNote: "最后信号证据不足，反拥挤门阻断。",
    distanceToBreakoutPct: "+1.66%",
    reviewFocus: "原始 10/10 有效观察候选，但最后信号证据不足，只读排查。",
    primaryEvidence: [],
    supportingEvidence: [],
    boundaryEvidence: [],
    invalidationFocus: "跌回 MA20 下方即降级。",
    invalidationRules: ["最后信号证据不足。", "跌回 MA20 下方即降级。"],
    rawFields: [
      { key: "fusion_score", label: "融合得分", value: "0.897" },
      { key: "pe_ttm", label: "市盈率(TTM)", value: "27.62" },
      { key: "roe", label: "ROE", value: "9.8%" },
      { key: "gross_margin", label: "毛利率", value: "21.4%" },
      { key: "attention_score", label: "情绪", value: "0.657" },
      { key: "liquidity_score", label: "流动性", value: "0.742" },
      { key: "amplitude", label: "振幅", value: "3.12" },
      { key: "pctchange", label: "涨跌幅", value: "1.66" },
      { key: "close", label: "收盘价", value: "14.23" },
      { key: "volume", label: "成交量", value: "1082万" },
      { key: "amount", label: "成交额", value: "15.4亿" },
      { key: "market_cap", label: "市值", value: "176亿" },
    ],
    ...overrides,
  };
}

const CHOICE_ENDPOINT_ITEM: ResearchDeskEndpointItem = {
  key: "choice",
  label: "Choice 信号库",
  statusLabel: "已就绪",
  businessDateLabel: "2026-08-24",
  description: "Choice 信号库 · 2026-08-24 15:10",
  tone: "positive",
};

const RESEARCHER_AUDIT_ROW: ResearchDeskAuditRow = {
  time: "2026-08-24 15:10",
  kind: "信号复核",
  subject: "天山生物 300313.SZ",
  detail: "最新信号已回补，仍需核实阻断证据。",
  source: "Choice 信号库",
  score: "0.897",
  status: "观察",
  owner: "研究员",
};

/** 研究台展示数据走真实模型，组件测试只手写交互/状态 props。 */
function buildDeskModel(candidate: StockCandidateReviewQueueItem | null) {
  return buildStockAnalysisResearchDeskModel({
    decisionStatusLabel: "阻断",
    decisionReason: "综合得分 0.897 / 1.000，最后信号证据不足，反拥挤门阻断。",
    candidateProgressionAllowed: false,
    poolTab: "queue",
    selectedSectorLabel: "农林牧渔",
    selectedCandidate: candidate,
    poolCandidates: candidate ? [candidate] : [],
    signalWindow: null,
    selectedRisk: null,
    detailQueryState: "idle",
    detailPayload: null,
    klineQueryState: "idle",
    klinePayload: null,
    newsQueryState: "idle",
    newsPayload: null,
    selectedHistoryRows: [],
    endpointItems: [CHOICE_ENDPOINT_ITEM],
    noteDraft: "",
    savedNote: "",
    auditRows: [RESEARCHER_AUDIT_ROW],
    analyticsAsOfDate: "2026-08-24",
  });
}

function buildDeskProps(
  overrides: Partial<StockAnalysisResearchDeskProps> = {},
): StockAnalysisResearchDeskProps {
  const candidate = buildCandidate();
  return {
    model: buildDeskModel(candidate),
    queueSearchText: "",
    onQueueSearchTextChange: vi.fn(),
    sectorOptions: [
      ["801010", "农林牧渔"],
      ["801020", "食品饮料"],
    ],
    selectedSectorCode: "801010",
    onSelectSector: vi.fn(),
    poolTab: "queue",
    onPoolTabChange: vi.fn(),
    dossierTab: "summary",
    onDossierTabChange: vi.fn(),
    poolCandidates: [candidate],
    queueVisibleCount: 1,
    queueTotalCount: 1,
    reviewQueueUsesHybridFusion: true,
    selectedCandidate: candidate,
    selectedCandidateCode: candidate.stockCode,
    onSelectCandidate: vi.fn(),
    watchlistCodes: [],
    onToggleWatchlist: vi.fn(),
    selectedRisk: null,
    noteDraft: "",
    onNoteDraftChange: vi.fn(),
    savedNote: "",
    onSaveNote: vi.fn(),
    onOpenDeepResearch: vi.fn(),
    onJumpToEvidence: vi.fn(),
    onOpenDetailDrawer: vi.fn(),
    onOpenHistory: vi.fn(),
    sectorLinkSummary: "主线拥挤、次线修复并存",
    sectorLinkFocus: "优先复核最后信号与拥挤门是否冲突",
    queueEmptyHeadline: "暂无候选",
    queueEmptyDetail: "等待候选接口返回。",
    historyLoading: false,
    historyLoaded: true,
    ...overrides,
  };
}

describe("StockAnalysis reference terminal contract", () => {
  it("keeps the summary research order aligned with the institutional terminal layout", () => {
    render(
      <ResearchDeskSummary
        selectedCandidate={{
          rank: 1,
          stockCode: "300313.SZ",
          stockName: "天山生物",
          sectorCode: "801010",
          sectorName: "农林牧渔",
          headline: "最新信号已回补，仍需核实阻断证据。",
          sourcePool: "stock_candidates",
          sourcePoolLabel: "农林牧渔",
          walkForward: null,
          pattern: "阻断",
          patternNote: "最后信号证据不足，反拥挤门阻断。",
          distanceToBreakoutPct: "+1.66%",
          reviewFocus: "原始 10/10 有效观察候选，但最后信号证据不足，只读排查。",
          primaryEvidence: [],
          supportingEvidence: [],
          boundaryEvidence: [],
          invalidationFocus: "跌回 MA20 下方即降级。",
          invalidationRules: ["最后信号证据不足。", "跌回 MA20 下方即降级。"],
          rawFields: [],
        }}
        selectedRisk={null}
        decisionStatusLabel="阻断"
        decisionReason="综合得分 0.897 / 1.000，最后信号证据不足，反拥挤门阻断。"
        compositeScore="0.897"
        compositeScoreNote={null}
        onJumpToEvidence={vi.fn()}
        onOpenFundamentals={vi.fn()}
        chartOption={null}
        keyFactItems={[
          { key: "turn", label: "换手率", value: "1.13%" },
          { key: "amp", label: "振幅", value: "3.12%" },
        ]}
        evidenceItems={[
          { key: "trigger", label: "主理由分项", value: "涨停扩板质量为足", rail: "primary" },
          { key: "breadth", label: "5日市场宽度", value: "0（-0.08）", rail: "supporting" },
        ]}
        factorCells={[
          { key: "composite", label: "综合分", value: "0.897", accent: "rose", percentile: "P90" },
          { key: "valuation", label: "估值", value: "0.717", accent: "green", percentile: "P72" },
          { key: "quality", label: "质量", value: "0.830", accent: "green", percentile: "P83" },
          { key: "momentum", label: "动量", value: "0.860", accent: "blue", percentile: "P86" },
          { key: "sentiment", label: "情绪", value: "0.657", accent: "amber", percentile: "P66" },
          { key: "crowding", label: "拥挤度", value: "0.897", accent: "rose", percentile: "P90" },
          { key: "liquidity", label: "流动性", value: "0.742", accent: "green", percentile: "P74" },
          { key: "volatility", label: "波动率", value: "0.601", accent: "amber", percentile: "P60" },
        ]}
        timelineItems={[
          { key: "1", time: "2026-08-24", detail: "更新信号：张停突破；证据包 20260819_天山生物。" },
        ]}
        financeItems={[{ key: "pe", label: "市盈率(TTM)", value: "27.62" }]}
        evidencePreviewItems={[
          {
            key: "choice",
            label: "Choice 信号库",
            statusLabel: "已就绪",
            businessDateLabel: "2026-08-24",
            description: "Choice 信号库 · 2026-08-24 15:10",
            tone: "positive",
          },
        ]}
      />,
    );

    const chart = screen.getByText("价格表现");
    const metrics = screen.getByText("关键数据");
    const conclusion = screen.getByText("综合结论");
    const evidence = screen.getByText("最新信号与关键证据");
    const factors = screen.getByLabelText("因子指标");
    const timeline = screen.getByText("事件时间线");

    expectElementBefore(chart, metrics);
    expectElementBefore(metrics, conclusion);
    expectElementBefore(conclusion, evidence);
    expectElementBefore(evidence, factors);
    expectElementBefore(factors, timeline);
  });

  it("keeps the action rail observational-only instead of drifting into trade execution language", () => {
    render(
      <ResearchDeskActionRail
        hardGateItems={["最后信号证据不足。", "原材料价格波动。"]}
        riskTags={["风险阻断", "只读观察"]}
        selectedRisk={null}
        endpointItems={[
          {
            key: "choice",
            label: "Choice 信号库",
            statusLabel: "已就绪",
            businessDateLabel: "2026-08-24",
            description: "Choice 信号库 · 2026-08-24 15:10",
            tone: "positive",
          },
        ]}
        selectedCandidate={{
          rank: 1,
          stockCode: "300313.SZ",
          stockName: "天山生物",
          sectorCode: "801010",
          sectorName: "农林牧渔",
          headline: "最新信号已回补，仍需核实阻断证据。",
          sourcePool: "stock_candidates",
          sourcePoolLabel: "农林牧渔",
          walkForward: null,
          pattern: "阻断",
          patternNote: "最后信号证据不足，反拥挤门阻断。",
          distanceToBreakoutPct: "+1.66%",
          reviewFocus: "原始 10/10 有效观察候选，但最后信号证据不足，只读排查。",
          primaryEvidence: [],
          supportingEvidence: [],
          boundaryEvidence: [],
          invalidationFocus: "跌回 MA20 下方即降级。",
          invalidationRules: ["最后信号证据不足。", "跌回 MA20 下方即降级。"],
          rawFields: [],
        }}
        selectedWatchlisted={false}
        onToggleWatchlist={vi.fn()}
        noteDraft=""
        onNoteDraftChange={vi.fn()}
        savedNote=""
        onSaveNote={vi.fn()}
        onOpenDeepResearch={vi.fn()}
        onJumpToEvidence={vi.fn()}
        onOpenDetailDrawer={vi.fn()}
        onOpenHistory={vi.fn()}
        actionsDisabled={false}
      />,
    );

    const rail = screen.getByTestId("stock-analysis-action-rail");
    expect(rail).toHaveTextContent("只读观察，不形成交易指令");
    for (const name of [
      "开始深度研究",
      "加入自选",
      "回溯该信号历史表现",
      "打开原始详情抽屉",
      "保存",
    ]) {
      expect(within(rail).getByRole("button", { name })).toBeEnabled();
    }
    expect(rail).not.toHaveTextContent("买入");
    expect(rail).not.toHaveTextContent("卖出");
    expect(rail).not.toHaveTextContent("调仓");
    expect(rail).not.toHaveTextContent("下单");
  });

  it("keeps the top pool controls and selected security header visible together", () => {
    render(<StockAnalysisResearchDesk {...buildDeskProps()} />);

    expect(screen.getByRole("heading", { name: "三窗研究台" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "标的池" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "精选池" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "自选股" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "历史回溯" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "搜索标的" })).toHaveAttribute("placeholder", "搜索代码/名称");
    expect(screen.getByTestId("stock-sector-filter-chips")).toHaveTextContent("1 / 1");
    expect(screen.getByTestId("stock-sector-filter-chips")).toHaveTextContent("农林牧渔");
    expect(screen.getByRole("heading", { name: "天山生物 300313.SZ" })).toBeInTheDocument();
  });

  it("keeps exactly eight factor cells in the dossier score band", () => {
    render(<StockAnalysisResearchDesk {...buildDeskProps()} />);

    const factorBand = screen.getByLabelText("因子指标");
    expect(factorBand.querySelectorAll("[data-accent]")).toHaveLength(8);
  });

  it("keeps the lower summary deck split into timeline finance and source sections", () => {
    render(<StockAnalysisResearchDesk {...buildDeskProps()} />);

    const timeline = screen.getByText("事件时间线");
    const finance = screen.getByText("关键财务指标");
    const source = screen.getByText("证据来源与时点");

    expectElementBefore(timeline, finance);
    expectElementBefore(finance, source);
    // 证据来源先列选中标的自身的溯源（详情 / K 线 / 事件），通用接口证据排在其后。
    const rail = screen.getByTestId("stock-analysis-action-rail");
    expect(rail).toHaveTextContent("个股详情");
    expect(rail).toHaveTextContent("Choice 信号库");
    expect(screen.getByTitle("Choice 信号库 · 2026-08-24 15:10")).toBeInTheDocument();
  });

  it("keeps the audit ledger tied to the selected stock and visible evidence rows", () => {
    render(<StockAnalysisResearchDesk {...buildDeskProps()} />);

    const audit = screen.getByTestId("stock-analysis-research-audit");
    expect(audit).toHaveTextContent("研究审计日志");
    expect(audit).toHaveTextContent("标的：天山生物");
    expect(audit).toHaveTextContent("Choice 信号库");
    // 候选选择行 + 两条接口状态行（个股详情 / K 线）+ 一条研究员复核行。
    expect(audit).toHaveTextContent("候选选择");
    expect(audit).toHaveTextContent("研究员");
    expect(audit).toHaveTextContent("共 4 条可见记录");
  });

  it("distinguishes history loading from an empty filtered history result", () => {
    const { rerender } = render(
      <StockAnalysisResearchDesk
        {...buildDeskProps({
          poolTab: "history",
          historyLoading: true,
          historyLoaded: false,
          poolCandidates: [],
        })}
      />,
    );

    expect(screen.getByText("历史回测读取中")).toBeInTheDocument();
    expect(screen.getByText("正在补齐候选历史，稍后会自动归档到左侧名单。")).toBeInTheDocument();

    rerender(
      <StockAnalysisResearchDesk
        {...buildDeskProps({
          poolTab: "history",
          historyLoading: false,
          historyLoaded: false,
          poolCandidates: [],
        })}
      />,
    );

    expect(screen.getByText("当前筛选暂无标的")).toBeInTheDocument();
    expect(screen.getByText("候选历史尚未加载。可点右侧动作区回溯信号历史。")).toBeInTheDocument();
  });
});
