import { describe, expect, it } from "vitest";

import type { LivermoreStrategyPayload } from "../api/contracts";
import {
  buildBackendSupplyOverview,
  buildStatusCounts,
  cycleBoundaryLabel,
  cycleCadenceLabel,
  cycleConstraintLabel,
  cycleEvidenceLabel,
  cycleGapLabel,
  cycleInputLabel,
  cycleInputSummary,
  cycleLayerTitleLabel,
  cycleLayerWeightLabel,
  cycleRuleSummary,
  dataGapFamilyLabel,
  eventDetailLabel,
  eventImpactLabel,
  eventLevelLabel,
  eventNameLabel,
  eventSourceLabel,
  formatSupplyPercent,
  gapTone,
  outputKeyLabel,
  readinessTone,
} from "../features/stock-analysis/lib/stockAnalysisPageLabels";

const strategyPayload: LivermoreStrategyPayload = {
  as_of_date: "2026-04-29",
  requested_as_of_date: null,
  strategy_name: "Livermore A-Share Defended Trend",
  basis: "analytical",
  market_gate: {
    state: "WARM",
    exposure: 0.4,
    passed_conditions: 2,
    available_conditions: 3,
    required_conditions: 4,
    conditions: [],
  },
  rule_readiness: [
    {
      key: "market_gate",
      title: "Market gate",
      status: "ready",
      summary: "Ready.",
      required_inputs: [],
      missing_inputs: [],
    },
    {
      key: "sector_rank",
      title: "Sector rank",
      status: "partial",
      summary: "Partial.",
      required_inputs: [],
      missing_inputs: ["breadth"],
    },
  ],
  diagnostics: [],
  data_gaps: [
    {
      input_family: "breadth",
      status: "missing",
      evidence: "Breadth input is missing.",
    },
  ],
  supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
  unsupported_outputs: [
    {
      key: "theme_breakout",
      reason: "theme inputs missing",
    },
  ],
  module_states: [],
  sector_rank: {
    as_of_date: "2026-04-29",
    formula_version: "rv_livermore_sector_strength_observation_v1",
    is_provisional: false,
    formula_status: "signed_off",
    sector_count: 2,
    excluded_constituent_count: 0,
    excluded_sector_count: 0,
    items: [],
  },
  stock_candidates: {
    as_of_date: "2026-04-29",
    formula_version: "rv_livermore_stock_candidates_bundle_v1",
    market_state: "WARM",
    input_stock_count: 4,
    candidate_count: 3,
    excluded_stock_count: 1,
    insufficient_history_count: 0,
    items: [],
  },
  risk_exit: {
    as_of_date: "2026-04-29",
    formula_version: "rv_livermore_risk_exit_ema10_mvp_v1",
    position_count: 5,
    signal_count: 1,
    excluded_position_count: 0,
    insufficient_history_count: 0,
    items: [],
    watch_items: [
      {
        stock_code: "000001.SZ",
        stock_name: "Alpha",
        entry_cost: 8,
        bars_since_entry: 12,
        latest_close: 10,
        latest_ema10: 9,
        prior_close: 9.5,
        prior_ema10: 8.8,
        exit_watch_price: 9,
        triggered: false,
      },
    ],
  },
};

describe("stockAnalysisPageLabels", () => {
  it("maps event rows into localized event labels", () => {
    expect(eventSourceLabel("diagnostic")).toBe("诊断");
    expect(eventSourceLabel("unknown_source")).toBe("unknown_source");
    expect(eventLevelLabel("error")).toBe("高");
    expect(eventLevelLabel("warning")).toBe("中");
    expect(eventLevelLabel("info")).toBe("低");

    expect(eventImpactLabel({ source: "unsupported", impact: "theme_breakout" })).toBe("题材观察");
    expect(eventImpactLabel({ source: "risk_exit", impact: "risk_exit" })).toBe("风险退出");
    expect(eventImpactLabel({ source: "signal_confluence", impact: "entry_gate" })).toBe("联动观察");
    expect(eventImpactLabel({ source: "diagnostic", impact: "breadth" })).toBe("市场宽度");

    expect(eventNameLabel({ source: "data_gap", event: "missing", impact: "breadth" })).toBe("缺数据");
    expect(eventNameLabel({ source: "signal_confluence", event: "entry_gate", impact: "entry_gate" })).toBe(
      "联动诊断",
    );
    expect(eventNameLabel({ source: "diagnostic", event: "source_table_missing", impact: "breadth" })).toBe(
      "市场宽度诊断",
    );
    expect(eventDetailLabel({ source: "diagnostic", detail: "Breadth inputs are unavailable.", impact: "breadth" })).toBe(
      "市场宽度输入不可用。",
    );
  });

  it("builds output, tone, count, and percent labels", () => {
    expect(formatSupplyPercent(0.405, 1)).toBe("40.5%");
    expect(formatSupplyPercent(Number.NaN)).toBe("-");
    expect(readinessTone("ready")).toBe("positive");
    expect(readinessTone("stale")).toBe("warning");
    expect(readinessTone("blocked")).toBe("negative");
    expect(readinessTone("unknown")).toBe("neutral");
    expect(gapTone("ready")).toBe("positive");
    expect(gapTone("missing")).toBe("negative");
    expect(buildStatusCounts([{ status: "ready" }, { status: "ready" }, { status: "missing" }])).toEqual({
      ready: 2,
      missing: 1,
    });
    expect(outputKeyLabel("hybrid_fusion")).toBe("融合池");
    expect(outputKeyLabel("vendor_unknown")).toBe("输出待确认");
    expect(outputKeyLabel(null)).toBe("待补");
    expect(dataGapFamilyLabel("factor_screen_candidates")).toBe("多因子");
  });

  it("localizes cycle layer labels and evidence boundaries", () => {
    const macroLayer = {
      key: "macro_direction",
      title: "Macro Direction",
      status: "ready",
      weight: 0.35,
      evidence: "Market gate available while PMI and credit impulse are missing.",
      available_inputs: ["market_gate"],
      missing_inputs: ["pmi", "credit_impulse"],
    } as const;

    expect(cycleInputLabel("sector-rank")).toBe("板块强弱");
    expect(cycleInputLabel("external_vendor_cycle_feed")).toBe("输入待确认");
    expect(cycleInputSummary(["market_gate", "sector_rank", "stock_candidates", "pmi"], ["credit_impulse"])).toBe(
      "已有证据 市场门控、板块强弱、趋势候选 · 待补 信用脉冲",
    );
    expect(cycleLayerTitleLabel(macroLayer)).toBe("宏观方向");
    expect(cycleLayerWeightLabel(macroLayer)).toBe("35%");
    expect(cycleRuleSummary([macroLayer])).toBe("宏观方向 35%");
    expect(cycleCadenceLabel("monthly core review with weekly monitoring")).toBe("月度核心复核 · 周度跟踪");
    expect(cycleGapLabel("pmi(missing)")).toBe("PMI 缺数据");
    expect(cycleConstraintLabel("single stock cap 20%")).toBe("个股上限 20%");
    expect(cycleEvidenceLabel(macroLayer.evidence)).toBe("市场门控已有可用证据；PMI 与信用脉冲待补。");
    expect(
      cycleEvidenceLabel("Market gate is available; PMI and credit impulse are ready and landed."),
    ).toBe("市场门控、PMI 与信用脉冲已接入。");
    expect(cycleBoundaryLabel("proxy-reconstructed lifecourt layer")).toBe(
      "生命法庭层为量化重建口径，原始文本规则尚未完整接入。",
    );
  });

  it("summarizes backend supply without recalculating business metrics", () => {
    const overview = buildBackendSupplyOverview(strategyPayload, {
      quality_flag: "warning",
      vendor_status: "vendor_unavailable",
      fallback_mode: "latest_snapshot",
    });

    expect(overview.asOfLabel).toBe("2026-04-29");
    expect(overview.requestedAsOfLabel).toBe("默认");
    expect(overview.gateLabel).toBe("门控 温和");
    expect(overview.exposureLabel).toBe("暴露 40%");
    expect(overview.conditionLabel).toBe("条件 2/4");
    expect(overview.readinessLabel).toBe("就绪 1/2");
    expect(overview.dataGapLabel).toBe("缺口 1");
    expect(overview.supportedLabel).toBe("可用 3");
    expect(overview.unsupportedLabel).toBe("阻断 1");
    expect(overview.sectorSupplyLabel).toBe("板块 2");
    expect(overview.candidateSupplyLabel).toBe("候选 3");
    expect(overview.riskDetailLabel).toBe("持仓 5 / 触发 1 / 观察 1");
    expect(overview.qualityLabel).toBe("质量 需复核");
    expect(overview.vendorLabel).toBe("通道 异常");
    expect(overview.fallbackLabel).toBe("数据延迟");
    expect(overview.basisLabel).toBe("分析口径");
    expect(overview.readinessRows).toBe(strategyPayload.rule_readiness);
    expect(overview.dataGapRows).toBe(strategyPayload.data_gaps);
  });

  it("keeps known policy pauses out of backend supply blocker counts", () => {
    const overview = buildBackendSupplyOverview({
      ...strategyPayload,
      unsupported_outputs: [
        {
          key: "stock_candidates",
          reason: "Stock candidate policy exp3b is inactive in OVERHEAT; active market states are HOT/WARM.",
        },
        {
          key: "mean_reversion_candidates",
          reason:
            "Mean reversion watchlist is paused when the market gate is HOT or OVERHEAT because the defended-trend candidate bundle already covers overheated tape.",
        },
        {
          key: "theme_breakout",
          reason: "Theme breakout execution is paused in OVERHEAT; historical replay showed this bucket is draggy.",
        },
        {
          key: "hybrid_fusion",
          reason:
            "Hybrid fusion is observation-only and only emits candidates in WARM/HOT market states; current state is OVERHEAT.",
        },
      ],
    });

    expect(overview.unsupportedLabel).toBe("阻断 0");
    expect(overview.unsupportedValueLabel).toBe("0");
    expect(overview.unsupportedOutputs).toHaveLength(4);
  });

  it("treats ready rows with stale source tiers as degraded inputs", () => {
    const overview = buildBackendSupplyOverview(
      {
        ...strategyPayload,
        as_of_date: "2026-07-08",
        data_gaps: [
          {
            input_family: "turnover_persistence",
            status: "ready",
            evidence: "Turnover input is available from an older business date.",
            business_date: "2026-06-26",
            age_days: 12,
            tier: "stale",
          },
        ],
      },
      { fallback_mode: "none" },
    );

    expect(overview.dataGapLabel).toBe("缺口 1");
    expect(overview.staleSourceRows).toHaveLength(1);
    expect(overview.staleSourceDetailLabel).toBe("换手持续：源数据日 2026-06-26（滞后 12 天）");
    expect(overview.fallbackLabel).toBe("数据正常");
  });

  it("keeps unsupported risk exit distinct from a measured zero", () => {
    const overview = buildBackendSupplyOverview({
      ...strategyPayload,
      supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
      unsupported_outputs: [
        {
          key: "risk_exit",
          reason: "livermore_position_snapshot has no ACTIVE A-share rows.",
        },
      ],
      risk_exit: undefined,
    });

    expect(overview.riskSupplyLabel).toBe("风险 阻断");
    expect(overview.riskSupplyValueLabel).toBe("阻断");
    expect(overview.riskDetailLabel).toBe("持仓快照缺失");
  });

  it("keeps unsupported risk exit blocked when a contradictory payload is also present", () => {
    const overview = buildBackendSupplyOverview({
      ...strategyPayload,
      unsupported_outputs: [
        {
          key: "risk_exit",
          reason: "livermore_position_snapshot has no ACTIVE A-share rows.",
        },
      ],
    });

    expect(overview.riskSupplyValueLabel).toBe("阻断");
    expect(overview.riskDetailLabel).toBe("持仓快照缺失");
    expect(overview.risk).toBeUndefined();
    expect(overview.riskDetailLabel).not.toContain("触发");
  });
});
