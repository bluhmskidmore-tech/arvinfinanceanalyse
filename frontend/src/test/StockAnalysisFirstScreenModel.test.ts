import { describe, expect, it } from "vitest";

import type { LivermoreStrategyPayload } from "../api/contracts";
import type { StockClosedLoopSummary } from "../features/stock-analysis/lib/stockAnalysisPageModel";
import {
  buildStockFirstScreenDecisionGate,
  buildStockMacroCycleCard,
} from "../features/stock-analysis/lib/stockAnalysisFirstScreenModel";

function buildClosedLoopSummary(
  code: StockClosedLoopSummary["referenceRating"]["code"],
): StockClosedLoopSummary {
  const labels = {
    reviewable: "可复核",
    pause: "暂缓",
    blocked: "拦截",
    insufficient_data: "数据不足",
  } as const;
  const tones = {
    reviewable: "positive",
    pause: "warning",
    blocked: "negative",
    insufficient_data: "warning",
  } as const;
  return {
    summaryLabel: "测试闭环",
    boundaryCount: code === "reviewable" ? 0 : 1,
    referenceRating: {
      code,
      label: labels[code],
      tone: tones[code],
      detail: "测试判级",
    },
    verdict: {
      code,
      tone: tones[code],
      label: labels[code],
      headline: "测试结论",
      primaryReason: `${labels[code]}原因`,
      nextStep: "仅供人工复核",
      evidence: [],
    },
    items: [],
  };
}

describe("buildStockFirstScreenDecisionGate", () => {
  it("blocks before confluence when sealed pretrade qualification is unavailable", () => {
    const gate = buildStockFirstScreenDecisionGate({
      pretradeQualificationStatus: "unavailable",
      pretradeQualificationReason: "当前读取未绑定已发布数据代际",
      workbenchReviewAllowed: true,
      strategyAsOf: "2026-04-29",
      confluenceAsOf: "2026-04-29",
      confluenceLoading: false,
      confluenceError: false,
      confluenceFreshnessIssue: null,
      workbenchBlockerReason: null,
      closedLoopSummary: buildClosedLoopSummary("reviewable"),
      entryObservationCount: 10,
    });

    expect(gate).toMatchObject({
      status: "pretrade_unavailable",
      statusLabel: "来源资格未就绪",
      candidateProgressionAllowed: false,
      effectiveCandidateCount: 0,
      primaryReason: "当前读取未绑定已发布数据代际",
    });
  });

  it("keeps an attested ready-empty run empty without waiting for confluence", () => {
    const gate = buildStockFirstScreenDecisionGate({
      pretradeQualificationStatus: "ready_empty",
      pretradeQualificationReason: null,
      workbenchReviewAllowed: false,
      strategyAsOf: "2026-04-29",
      confluenceAsOf: null,
      confluenceLoading: false,
      confluenceError: false,
      confluenceFreshnessIssue: null,
      workbenchBlockerReason: null,
      closedLoopSummary: null,
      entryObservationCount: 0,
    });

    expect(gate).toMatchObject({
      status: "no_valid_candidate",
      statusLabel: "资格就绪，无候选",
      candidateProgressionAllowed: false,
      effectiveCandidateCount: 0,
    });
  });

  it("fails closed while confluence is unresolved", () => {
    const gate = buildStockFirstScreenDecisionGate({
      pretradeQualificationStatus: "ready",
      pretradeQualificationReason: null,
      workbenchReviewAllowed: true,
      strategyAsOf: "2026-04-29",
      confluenceAsOf: null,
      confluenceLoading: true,
      confluenceError: false,
      confluenceFreshnessIssue: null,
      workbenchBlockerReason: null,
      closedLoopSummary: null,
      entryObservationCount: 10,
    });

    expect(gate).toMatchObject({
      status: "unresolved",
      reviewAllowed: false,
      candidateProgressionAllowed: false,
      executionAllowed: false,
      effectiveCandidateCount: null,
      primaryReason: "结论核对中",
    });
  });

  it("keeps raw candidates visible but sets effective candidates to zero when blocked", () => {
    const gate = buildStockFirstScreenDecisionGate({
      pretradeQualificationStatus: "ready",
      pretradeQualificationReason: null,
      workbenchReviewAllowed: true,
      strategyAsOf: "2026-04-29",
      confluenceAsOf: "2026-04-29",
      confluenceLoading: false,
      confluenceError: false,
      confluenceFreshnessIssue: null,
      workbenchBlockerReason: null,
      closedLoopSummary: buildClosedLoopSummary("blocked"),
      entryObservationCount: 10,
    });

    expect(gate).toMatchObject({
      status: "blocked",
      reviewAllowed: false,
      candidateProgressionAllowed: false,
      executionAllowed: false,
      effectiveCandidateCount: 0,
      primaryReason: "拦截原因",
    });
  });

  it("requires at least one valid entry observation before allowing progression", () => {
    const gate = buildStockFirstScreenDecisionGate({
      pretradeQualificationStatus: "ready",
      pretradeQualificationReason: null,
      workbenchReviewAllowed: true,
      strategyAsOf: "2026-04-29",
      confluenceAsOf: "2026-04-29",
      confluenceLoading: false,
      confluenceError: false,
      confluenceFreshnessIssue: null,
      workbenchBlockerReason: null,
      closedLoopSummary: buildClosedLoopSummary("reviewable"),
      entryObservationCount: 0,
    });

    expect(gate).toMatchObject({
      status: "no_valid_candidate",
      candidateProgressionAllowed: false,
      executionAllowed: false,
      effectiveCandidateCount: 0,
    });
  });

  it("allows only observation progression when the closed loop is reviewable", () => {
    const gate = buildStockFirstScreenDecisionGate({
      pretradeQualificationStatus: "ready",
      pretradeQualificationReason: null,
      workbenchReviewAllowed: true,
      strategyAsOf: "2026-04-29",
      confluenceAsOf: "2026-04-29",
      confluenceLoading: false,
      confluenceError: false,
      confluenceFreshnessIssue: null,
      workbenchBlockerReason: null,
      closedLoopSummary: buildClosedLoopSummary("reviewable"),
      entryObservationCount: 3,
    });

    expect(gate).toMatchObject({
      status: "reviewable",
      candidateProgressionAllowed: true,
      executionAllowed: false,
      effectiveCandidateCount: 3,
    });
  });

  it("does not allow progression when the workbench review gate is closed", () => {
    const gate = buildStockFirstScreenDecisionGate({
      pretradeQualificationStatus: "ready",
      pretradeQualificationReason: null,
      workbenchReviewAllowed: false,
      strategyAsOf: "2026-04-29",
      confluenceAsOf: "2026-04-29",
      confluenceLoading: false,
      confluenceError: false,
      confluenceFreshnessIssue: null,
      workbenchBlockerReason: "数据缺口状态未闭合",
      closedLoopSummary: buildClosedLoopSummary("reviewable"),
      entryObservationCount: 3,
    });

    expect(gate).toMatchObject({
      status: "workbench_blocked",
      statusLabel: "复核门禁未放行",
      reviewAllowed: false,
      candidateProgressionAllowed: false,
      effectiveCandidateCount: 0,
      primaryReason: "数据缺口状态未闭合",
    });
  });

  it("fails closed when confluence freshness metadata is unhealthy", () => {
    const gate = buildStockFirstScreenDecisionGate({
      pretradeQualificationStatus: "ready",
      pretradeQualificationReason: null,
      workbenchReviewAllowed: true,
      strategyAsOf: "2026-04-29",
      confluenceAsOf: "2026-04-29",
      confluenceLoading: false,
      confluenceError: false,
      confluenceFreshnessIssue: "闭环供数未通过新鲜度检查（供数陈旧）",
      workbenchBlockerReason: null,
      closedLoopSummary: buildClosedLoopSummary("reviewable"),
      entryObservationCount: 3,
    });

    expect(gate).toMatchObject({
      status: "insufficient_data",
      reviewAllowed: false,
      candidateProgressionAllowed: false,
      effectiveCandidateCount: 0,
      primaryReason: "闭环供数未通过新鲜度检查（供数陈旧）",
    });
  });
});

describe("buildStockMacroCycleCard", () => {
  it("keeps PMI and credit-expansion proxy lineage visible without parsing evidence into values", () => {
    const payload = {
      market_gate: {
        macro_context: {
          status: "ready",
          cycle_state: "neutral",
          macro_score: 0.57,
          evidence: "PMI 49.2 (M0017126); credit_expansion_proxy +0.00ppt (M0001385).",
          components: [
            {
              input_family: "PMI",
              input: "M0017126",
              cadence: "monthly",
              business_date: "2026-07-31",
              value_numeric: 49.2,
              unit: "index",
              value_kind: "index",
              age_days: 18,
              tier: "fresh",
            },
            {
              input_family: "credit_impulse",
              input: "M0001385",
              cadence: "monthly",
              business_date: "2026-07-31",
              value_numeric: 0,
              unit: "ppt",
              value_kind: "ppt",
              age_days: 18,
              tier: "fresh",
            },
          ],
        },
      },
    } as LivermoreStrategyPayload;

    const model = buildStockMacroCycleCard(payload);

    expect(model?.inputs).toEqual([
      expect.objectContaining({
        key: "pmi",
        valueLabel: "49.2 index",
        seriesLabel: "M0017126",
        dateLabel: "2026-07-31",
        freshnessLabel: "新鲜 · 18 天",
        basisLabel: "PMI 原序列",
      }),
      expect.objectContaining({
        key: "credit_impulse",
        valueLabel: "+0.00 ppt",
        seriesLabel: "M0001385",
        dateLabel: "2026-07-31",
        freshnessLabel: "新鲜 · 18 天",
        basisLabel: "M2 同比月差代理",
      }),
    ]);
    expect(model?.evidence).toContain("PMI 49.2");
  });

  it("shows explicit pending rows when structured macro components are absent", () => {
    const payload = {
      market_gate: {
        macro_context: {
          status: "missing_inputs",
          evidence: "Macro inputs are not landed.",
        },
      },
    } as LivermoreStrategyPayload;

    const model = buildStockMacroCycleCard(payload);

    expect(model?.inputs).toEqual([
      expect.objectContaining({ key: "pmi", seriesLabel: "序列待补", dateLabel: "日期待补" }),
      expect.objectContaining({
        key: "credit_impulse",
        seriesLabel: "序列待补",
        basisLabel: "代理口径待补",
      }),
    ]);
    expect(model).toMatchObject({ statusLabel: "部分就绪", tone: "warning" });
  });

  it("keeps legacy payloads on placeholder values when structured numeric fields are absent", () => {
    const payload = {
      market_gate: {
        macro_context: {
          status: "ready",
          components: [
            {
              input_family: "PMI",
              input: "M0017126",
              cadence: "monthly",
              business_date: "2026-07-31",
              age_days: 18,
              tier: "fresh",
            },
          ],
        },
      },
    } as LivermoreStrategyPayload;

    const model = buildStockMacroCycleCard(payload);

    expect(model?.inputs[0]).toMatchObject({
      key: "pmi",
      valueLabel: "数值待补",
      seriesLabel: "M0017126",
    });
  });

  it("does not inherit framework-ready when required PMI and credit inputs are missing", () => {
    const payload = {
      market_gate: { macro_context: { status: "ready", components: [] } },
      cycle_rotation_framework: { macro_layer: { ready: true } },
    } as unknown as LivermoreStrategyPayload;

    expect(buildStockMacroCycleCard(payload)).toMatchObject({
      statusLabel: "部分就绪",
      tone: "warning",
    });
  });
});
