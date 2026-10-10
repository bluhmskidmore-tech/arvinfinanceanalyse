import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  StockCandidateReviewQueueItem,
  StockSectorRow,
} from "../lib/stockAnalysisPageModel";
import type { StockAnalysisResearchDeskModel } from "../lib/stockAnalysisResearchDeskModel";
import { StockAnalysisReadOnlyResearchZone } from "./StockAnalysisReadOnlyResearchZone";

vi.mock("../../../components/charts/BaseChart", () => ({
  BaseChart: () => <div data-testid="base-chart-stub" />,
}));

function candidate(
  stockCode: string,
  stockName: string,
  sectorCode: string,
  sectorName: string,
): StockCandidateReviewQueueItem {
  return {
    rank: 1,
    stockCode,
    stockName,
    sectorCode,
    sectorName,
    headline: `${stockName}只读候选`,
    sourcePool: "factor_screen_candidates",
    sourcePoolLabel: "多因子初筛",
    walkForward: null,
    pattern: "观察",
    patternNote: "仅使用当前观察证据。",
    distanceToBreakoutPct: "-7.06%",
    reviewFocus: "核对详情与K线。",
    primaryEvidence: [],
    supportingEvidence: [],
    boundaryEvidence: [],
    invalidationFocus: "待确认",
    invalidationRules: [],
    rawFields: [],
  };
}

function model(name: string, quote: string, pe: string): StockAnalysisResearchDeskModel {
  const sourceItems = [
    {
      key: "selected-stock-detail",
      label: "个股详情",
      statusLabel: "已就绪",
      businessDateLabel: "2026-09-16",
      description: "详情接口已返回。",
      tone: "positive" as const,
    },
    {
      key: "selected-kline",
      label: "K线观察",
      statusLabel: "已就绪",
      businessDateLabel: "2026-09-16",
      description: "K线接口已返回。",
      tone: "positive" as const,
    },
  ];
  return {
    statusLabel: "研究可用",
    decisionReason: "只读候选可复核。",
    progressionLabel: "允许复核",
    progressionTone: "positive",
    selectedSectorLabel: "当前行业",
    poolLabel: "精选池",
    selectedCandidateTitle: name,
    selectedCandidateSubtitle: "当前观察",
    selectedHeaderItems: [],
    selectedWatchlisted: false,
    hardGateItems: [],
    riskTags: ["研究可复核", "盘前资格未闭合"],
    riskSummary: "风险与执行结论未读取。",
    summary: {
      chartState: "ready",
      chartMessage: null,
      chartOption: { series: [{ type: "line", data: [1, 2] }] },
      chartFootnote: "来自个股详情日频收盘。",
      quoteValue: quote,
      dailyChangeLabel: "+1.20%",
      dailyChangeTone: "positive",
      compositeScoreLabel: "0.786",
      compositeScoreNote: null,
      marketSnapshotItems: [],
      keyFactsTitle: "关键数据（2026-09-16）",
      keyFacts: [{ key: "pe", label: "市盈率(TTM)", value: pe }],
      conclusionTitle: "研究观察",
      conclusionTone: "warning",
      conclusionBadge: "只读",
      conclusionBody: "不形成交易结论。",
      conclusionBullets: [],
      conclusionFootnote: "观察证据",
      researchHeadline: "研究观点（摘要）",
      researchSummary: "K线详情已读取",
      researchDetail: "当前价格序列可读。",
      evidenceHeadline: "关键证据",
      evidenceItems: [],
      factorCells: [],
      timelineItems: [],
      financeItems: [],
      sourceItems,
    },
    valuationCards: [],
    momentumCards: [{ key: "ma20", label: "MA20", value: "25.60", detail: "详情接口", accent: "neutral" }],
    financeCards: [],
    signalWindow: null,
    fundamentalsLines: [],
    invalidationRules: [],
    eventBoundaryLines: [],
    rawFieldRows: [],
    historyRows: [],
    sourceItems,
    displayAuditRows: [],
    auditVisibleCount: 0,
    auditTotalCount: 0,
  };
}

function sector(
  sectorCode: string,
  sectorName: string,
  rank: number,
): StockSectorRow {
  return {
    rank,
    sectorCode,
    sectorName,
    score: "0.82",
    pctChange: "+2.02%",
    turnover: "4.44",
    amplitude: "4.29%",
    constituentCount: 138,
    scoreValue: 0.82,
    pctChangeValue: 2.02,
    turnoverValue: 4.44,
    amplitudeValue: 4.29,
    scoreNormalized: 0.82,
    pctChangeBar: 0.5,
    isTop: true,
    isBottom: false,
  };
}

describe("StockAnalysisReadOnlyResearchZone", () => {
  it("shows selected-stock detail, K-line and current sector while keeping restricted modules closed", () => {
    render(
      <StockAnalysisReadOnlyResearchZone
        analyticsAsOf="2026-09-16"
        model={model("神火股份", "26.87", "15.09")}
        sectorRows={[sector("S240000", "有色金属", 3)]}
        selectedCandidate={candidate("000933.SZ", "神火股份", "S240000", "有色金属")}
      />,
    );

    const zone = screen.getByTestId("stock-analysis-readonly-research");
    expect(zone).toHaveTextContent("神火股份");
    expect(zone).toHaveTextContent("000933.SZ");
    expect(zone).toHaveTextContent("26.87");
    expect(zone).toHaveTextContent("市盈率(TTM)15.09");
    expect(zone).toHaveTextContent("MA2025.60");
    expect(zone).toHaveTextContent("有色金属");
    expect(zone).toHaveTextContent("第 3 名");
    expect(zone).toHaveTextContent("平均换手（%）4.44");
    expect(zone).toHaveTextContent("详情 已就绪 / K线 已就绪 / 行业 已匹配");
    expect(zone).toHaveTextContent("盘前资格未闭合，未读取");
    expect(zone).toHaveTextContent("风险与执行保持关闭");
    expect(within(zone).getByLabelText("价格图例")).toHaveTextContent("收盘MA5MA20");
    expect(zone).toHaveTextContent("来自个股详情日频收盘。");
    expect(screen.getByTestId("base-chart-stub")).toBeInTheDocument();
    expect(zone).not.toHaveTextContent("历史收益");
  });

  it("replaces selected-stock and date evidence without retaining the previous candidate", () => {
    const { rerender } = render(
      <StockAnalysisReadOnlyResearchZone
        analyticsAsOf="2026-09-16"
        model={model("神火股份", "26.87", "15.09")}
        sectorRows={[sector("S240000", "有色金属", 3)]}
        selectedCandidate={candidate("000933.SZ", "神火股份", "S240000", "有色金属")}
      />,
    );

    rerender(
      <StockAnalysisReadOnlyResearchZone
        analyticsAsOf="2026-09-17"
        model={model("新候选", "18.20", "11.40")}
        sectorRows={[sector("S270000", "电子", 1)]}
        selectedCandidate={candidate("000823.SZ", "新候选", "S270000", "电子")}
      />,
    );

    const zone = screen.getByTestId("stock-analysis-readonly-research");
    expect(zone).toHaveTextContent("新候选");
    expect(zone).toHaveTextContent("000823.SZ");
    expect(zone).toHaveTextContent("2026-09-17");
    expect(zone).toHaveTextContent("18.20");
    expect(zone).not.toHaveTextContent("神火股份");
    expect(zone).not.toHaveTextContent("26.87");
  });

  it("shows failed and unmatched evidence without marking the current sources ready", () => {
    const failedModel = model("神火股份", "26.87", "15.09");
    failedModel.sourceItems = failedModel.sourceItems.map((item) =>
      item.key === "selected-stock-detail"
        ? { ...item, statusLabel: "失败", tone: "negative" }
        : { ...item, statusLabel: "读取中", tone: "neutral" },
    );

    render(
      <StockAnalysisReadOnlyResearchZone
        analyticsAsOf="2026-09-16"
        model={failedModel}
        sectorRows={[]}
        selectedCandidate={candidate("000933.SZ", "神火股份", "S240000", "有色金属")}
      />,
    );

    const zone = screen.getByTestId("stock-analysis-readonly-research");
    expect(zone).toHaveTextContent("详情 失败 / K线 读取中 / 行业 待匹配");
    expect(zone).toHaveTextContent("行业快照待匹配");
    expect(zone.querySelector('[aria-label="只读研究边界"] article')).toHaveAttribute(
      "data-tone",
      "negative",
    );
  });

  it("renders an explicit closed state when no review candidate is available", () => {
    render(
      <StockAnalysisReadOnlyResearchZone
        analyticsAsOf="2026-09-16"
        model={model("", "—", "—")}
        sectorRows={[]}
        selectedCandidate={null}
      />,
    );

    expect(screen.getByTestId("stock-analysis-readonly-research")).toHaveTextContent(
      "只读深研暂不可用",
    );
  });
});
