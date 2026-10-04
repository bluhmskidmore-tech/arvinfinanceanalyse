import { describe, expect, it } from "vitest";

import type { LivermoreStockDetailPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../pageModel";
import type { StockCandidateReviewQueueItem } from "./stockAnalysisPageModel";
import {
  buildStockAnalysisResearchDeskModel,
  type BuildStockAnalysisResearchDeskModelInput,
} from "./stockAnalysisResearchDeskModel";

function buildCandidate(
  rawFields: StockCandidateReviewQueueItem["rawFields"],
): StockCandidateReviewQueueItem {
  return {
    rank: 1,
    stockCode: "000001.SZ",
    stockName: "Alpha",
    sectorCode: "801010",
    sectorName: "银行",
    headline: "趋势候选 #1 · Alpha",
    sourcePool: "stock_candidates",
    sourcePoolLabel: "趋势候选",
    walkForward: null,
    pattern: "突破",
    patternNote: "观察口径",
    distanceToBreakoutPct: "0.46%",
    reviewFocus: "Alpha（银行） · 趋势候选",
    primaryEvidence: [],
    supportingEvidence: [],
    boundaryEvidence: [],
    invalidationFocus: "跌回 MA20 下方即降级。",
    invalidationRules: [],
    rawFields,
  };
}

function buildInput(
  candidate: StockCandidateReviewQueueItem,
  detailPayload: LivermoreStockDetailPayload | null = null,
): BuildStockAnalysisResearchDeskModelInput {
  return {
    decisionStatusLabel: "可复核",
    decisionReason: "闭环检查已通过。",
    candidateProgressionAllowed: true,
    poolTab: "queue",
    selectedSectorLabel: "全部行业",
    selectedCandidate: candidate,
    signalWindow: null,
    selectedRisk: null,
    detailQueryState: detailPayload ? "success" : "idle",
    detailPayload,
    klineQueryState: "idle",
    klinePayload: null,
    newsQueryState: "idle",
    newsPayload: null,
    selectedHistoryRows: [],
    noteDraft: "",
    savedNote: "",
    auditRows: [],
    analyticsAsOfDate: "2026-08-24",
  };
}

function buildDetailPayload(
  factor: Partial<LivermoreStockDetailPayload["factor"]>,
): LivermoreStockDetailPayload {
  return {
    basis: "analytical",
    state: "ok",
    stock_code: "000001.SZ",
    requested_as_of_date: "2026-08-24",
    as_of_date: "2026-08-24",
    lookback: 60,
    candles: [],
    factor: {
      as_of_date: "2026-08-24",
      pe: null,
      pb: null,
      roe: null,
      dividend_yield: null,
      total_mv: null,
      circ_mv: null,
      ...factor,
    },
  };
}

function financeValue(model: ReturnType<typeof buildStockAnalysisResearchDeskModel>, key: string) {
  return model.summary.financeItems.find((item) => item.key === key)?.value;
}

function keyFactValue(model: ReturnType<typeof buildStockAnalysisResearchDeskModel>, key: string) {
  return model.summary.keyFacts.find((item) => item.key === key)?.value;
}

describe("stockAnalysisResearchDeskModel numeric units", () => {
  it("shows stock-detail ROE and dividend yield as ratio percentages, matching the detail drawer", () => {
    const model = buildStockAnalysisResearchDeskModel(
      buildInput(buildCandidate([]), buildDetailPayload({ roe: 0.143, dividend_yield: 0.021 })),
    );

    expect(financeValue(model, "roe")).toBe("14.30%");
    expect(financeValue(model, "dividend-yield")).toBe("2.10%");
    expect(keyFactValue(model, "roe")).toBe("14.30%");
    expect(model.summary.factorCells.find((cell) => cell.key === "quality")?.value).toBe("14.30%");
  });

  it("prefers the numeric raw field over its display string and converts ratio keys to percent", () => {
    // Strategy cards store ratio-valued fields as plain strings ("0.1430"); the numeric
    // must win so the desk never treats "0.1430" as 0.14%.
    const candidate = buildCandidate([
      { key: "roe", label: "ROE", value: "0.1430", numeric: 0.143 },
      { key: "gross_margin", label: "毛利率", value: "0.3200", numeric: 0.32 },
      { key: "dividend_yield", label: "股息率", value: "2.10%", numeric: 0.021 },
      { key: "turn", label: "个股换手", value: "1.2345", numeric: 1.2345 },
      { key: "amplitude", label: "个股振幅", value: "3.1200", numeric: 3.12 },
      { key: "pctchange", label: "个股涨幅", value: "1.6600", numeric: 1.66 },
      { key: "pe", label: "PE", value: "12.4000", numeric: 12.4 },
    ]);

    const model = buildStockAnalysisResearchDeskModel(buildInput(candidate));

    expect(financeValue(model, "roe")).toBe("14.30%");
    expect(financeValue(model, "gross-margin")).toBe("32.00%");
    expect(financeValue(model, "dividend-yield")).toBe("2.10%");
    expect(financeValue(model, "pe")).toBe("12.40");
    expect(keyFactValue(model, "turnover")).toBe("1.23%");
    expect(keyFactValue(model, "amplitude")).toBe("3.12%");
    expect(model.summary.dailyChangeLabel).toBe("+1.66%");
    expect(model.summary.dailyChangeTone).toBe("positive");
  });

  it("does not multiply a workbench percent string twice when no numeric is attached", () => {
    const candidate = buildCandidate([
      { key: "roe", label: "ROE", value: "14.30%" },
      { key: "return_20d", label: "20日动量", value: "12.3%" },
    ]);

    const model = buildStockAnalysisResearchDeskModel(buildInput(candidate));

    expect(financeValue(model, "roe")).toBe("14.30%");
    expect(model.momentumCards.find((card) => card.key === "momentum")?.value).toBe("+12.30%");
  });

  it("keeps scale-changing unit strings as text while accepting plain multipliers", () => {
    const candidate = buildCandidate([
      { key: "close", label: "收盘价", value: "15.4亿" },
      { key: "ma20", label: "MA20", value: "1,234.50" },
      { key: "amount_ratio", label: "量能", value: "2.31x" },
    ]);

    const model = buildStockAnalysisResearchDeskModel(buildInput(candidate));

    // 亿 changes the scale, so the string is shown verbatim rather than parsed as 15.4.
    expect(model.summary.quoteValue).toBe("15.4亿");
    expect(model.momentumCards.find((card) => card.key === "liquidity")?.value).toBe("2.3x");
    expect(model.momentumCards.find((card) => card.key === "crowding")?.value).toBe(EM_DASH);
  });
});
