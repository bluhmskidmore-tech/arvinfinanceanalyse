import { describe, expect, it } from "vitest";

import type {
  BacktestWindowSummary,
  ConfluenceReplayStatus,
  LivermoreCandidateHistoryPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreModuleState,
  LivermoreOutputKey,
  LivermoreSectorRankSeriesPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyScorePayload,
  LivermoreStrategyPayload,
  ResultMeta,
} from "../api/contracts";
import {
  buildCandidateReviewQueue,
  buildCandidateEvidenceCards,
  buildClosedLoopSummary,
  buildCycleMacroLayerSummary,
  buildDataBoundarySummary,
  buildDecisionSummary,
  buildDeepAnalysisGateSummary,
  buildStockAnalysisPagePurpose,
  buildReviewQueueEmptyState,
  buildReviewQueueSectorFilterView,
  buildStockSectorOverviewState,
  localizeImplementationStage,
  buildDailyJudgmentStrip,
  buildInlineMetaSegments,
  buildDataBoundaryNotes,
  buildStockAnalysisEvidenceStatus,
  buildMarketStateCard,
  buildRiskExitRows,
  buildSectorRows,
  buildSectorRowsFromSectorSeries,
  buildSectorFilterSummary,
  buildSectorViewModel,
  buildSectorViewRows,
  buildStockAnalysisEventMonitorRows,
  buildStockAnalysisKpiStrip,
  buildWorkbenchDataDigest,
  buildObservationClosureSummary,
  buildStockEndpointEvidenceItems,
  buildStrategyLensItems,
  buildThemeBreakoutCards,
  buildThemeLeaderPreviewItems,
  buildSectorHeavyweightPreview,
  buildThemeBreakoutReviewItems,
  buildThemeEvidenceStateRows,
  buildConsensusReviewPanelSummary,
  buildCycleRotationPanelSummary,
  buildEventsMonitoringPanelSummary,
  buildObservationPoolsPanelSummary,
  buildThemeBreakoutPanelSummary,
  buildDeepZoneAuditRows,
  buildMarketPriorityPanelSummary,
  buildStrategyBacktestPanelSummary,
  buildStrategyOptimizationPanelSummary,
  localizeMarketDataStatus,
  localizeThemeSourceKind,
  localizeStockBackendText,
  mergeStockClosedLoopMeta,
  pickStockFreshnessMeta,
} from "../features/stock-analysis/lib/stockAnalysisPageModel";
import type { StockCandidateReviewQueueItem } from "../features/stock-analysis/lib/stockAnalysisPageModel";
import { buildConsensusSummary } from "../features/stock-analysis/lib/buildConsensusSummary";

const LIVERMORE_OUTPUT_KEYS: LivermoreOutputKey[] = [
  "market_gate",
  "sector_rank",
  "stock_candidates",
  "uptrend_momentum_candidates",
  "fresh_trend_watchlist",
  "mean_reversion_candidates",
  "factor_screen_candidates",
  "theme_breakout",
  "hybrid_fusion",
  "risk_exit",
];

function readyModuleStates(keys: LivermoreOutputKey[] = LIVERMORE_OUTPUT_KEYS): LivermoreModuleState[] {
  return keys.map((key) => ({
    key,
    state: "ready",
    render_mode: "primary",
    source_date: "2026-04-29",
    lag_days: 0,
    threshold_days: null,
    reasons: [],
    evidence_scope: "primary",
    excludes_from_primary: false,
  }));
}

const cycleRotationFrameworkFixture: NonNullable<LivermoreStrategyPayload["cycle_rotation_framework"]> = {
  strategy_name: "A-share cycle rotation research framework",
  display_name: "A股景气周期选股与行业轮动",
  observation_only: true,
  implementation_stage: "verification_pending",
  score_formula: "CycleScore = weighted evidence",
  rebalance_cadence: "Monthly review",
  layers: [],
  constraints: [],
  boundary: "observation-only",
};

const strategyPayload: LivermoreStrategyPayload = {
  as_of_date: "2026-04-29",
  requested_as_of_date: null,
  strategy_name: "Livermore A-Share Defended Trend",
  basis: "analytical",
  market_gate: {
    state: "WARM",
    exposure: 0.4,
    passed_conditions: 2,
    available_conditions: 2,
    required_conditions: 4,
    conditions: [
      {
        key: "csi300_close_gt_ma60",
        label: "CSI300 close > MA60",
        status: "pass",
        evidence: "Close is above MA60.",
        source_series_id: "CA.CSI300",
      },
      {
        key: "csi300_ma20_gt_ma60",
        label: "CSI300 MA20 > MA60",
        status: "pass",
        evidence: "MA20 is above MA60.",
        source_series_id: "CA.CSI300",
      },
      {
        key: "breadth_5d_positive",
        label: "5-day breadth > 0",
        status: "missing",
        evidence: "Breadth inputs are not landed for the Phase 1 slice.",
        source_series_id: null,
      },
      {
        key: "limit_up_quality_positive",
        label: "Limit-up seal/break quality positive",
        status: "missing",
        evidence: "Limit-up quality inputs are not landed for the Phase 1 slice.",
        source_series_id: null,
      },
    ],
  },
  rule_readiness: [
    {
      key: "market_gate",
      title: "Market gate",
      status: "partial",
      summary: "Trend-only market gate is available.",
      required_inputs: ["broad_index_history", "breadth"],
      missing_inputs: ["breadth"],
    },
  ],
  diagnostics: [
    {
      severity: "warning",
      code: "LIVERMORE_BREADTH_MISSING",
      message: "Breadth inputs are unavailable.",
      input_family: "breadth",
    },
  ],
  data_gaps: [
    {
      input_family: "breadth",
      status: "missing",
      evidence: "5-day breadth input family is not landed.",
    },
  ],
  supported_outputs: [
    "market_gate",
    "sector_rank",
    "stock_candidates",
    "uptrend_momentum_candidates",
    "fresh_trend_watchlist",
    "risk_exit",
  ],
  unsupported_outputs: [],
  module_states: readyModuleStates(),
  sector_rank: {
    as_of_date: "2026-04-29",
    formula_version: "rv_livermore_sector_strength_observation_v1",
    is_provisional: false,
    formula_status: "signed_off",
    formula_note:
      "Daily sector strength observation rank is a signed-off analytical formula: 50% pctchange percentile, 30% turn percentile, and 20% amplitude percentile; it supports review prioritization and sector filtering, not trading instructions; multi-day momentum persistence, sector money flow, and crowding are not part of this version.",
    formula_component_weights: {
      pctchange_percentile: 0.5,
      turn_percentile: 0.3,
      amplitude_percentile: 0.2,
    },
    sector_count: 2,
    excluded_constituent_count: 0,
    excluded_sector_count: 0,
    items: [
      {
        rank: 1,
        sector_code: "801001",
        sector_name: "AI",
        score: 1,
        avg_pctchange: 4.8,
        avg_turn: 3,
        avg_amplitude: 3.5,
        constituent_count: 12,
      },
      {
        rank: 2,
        sector_code: "801002",
        sector_name: "新能源车",
        score: 0.5,
        avg_pctchange: -1.2,
        avg_turn: 5,
        avg_amplitude: 2,
        constituent_count: 20,
      },
    ],
  },
  stock_candidates: {
    as_of_date: "2026-04-29",
    formula_version: "rv_livermore_stock_candidates_bundle_v1",
    market_state: "WARM",
    input_stock_count: 1,
    candidate_count: 1,
    excluded_stock_count: 0,
    insufficient_history_count: 0,
    items: [
      {
        rank: 1,
        stock_code: "000001.SZ",
        stock_name: "Alpha",
        sector_code: "801001",
        sector_name: "AI",
        sector_rank: 1,
        close: 21.9,
        breakout_level: 21.8,
        ema10: 20.6,
        ma20: 21.05,
        ma60: 19.05,
        ma120: 16.05,
        close_strength: 0.833333,
        gap_norm: -0.114679,
        breakout_extension_norm: 0.045872,
        abnormal_turnover: 1.386294,
        pe: 12.4,
        pb: 1.8,
        ps: 2.6,
        roe: 0.18,
        gross_margin: 0.32,
        three_month_return: 0.11,
        twelve_month_return: 0.24,
        factor_score: 0.4812,
        factor_overlay_rank: 1,
      },
    ],
  },
  uptrend_momentum_candidates: {
    as_of_date: "2026-04-29",
    formula_version: "rv_uptrend_momentum_candidates_v1",
    market_state: "WARM",
    observation_only: true,
    input_stock_count: 1,
    candidate_count: 1,
    excluded_stock_count: 0,
    insufficient_history_count: 0,
    items: [
      {
        rank: 1,
        stock_code: "000001.SZ",
        stock_name: "Alpha",
        sector_code: "801001",
        sector_name: "AI",
        close: 21.9,
        ma20: 21.05,
        ma60: 19.05,
        ma120: 16.05,
        return_20d: 0.12,
        return_60d: 0.26,
        return_120d: 0.48,
        close_to_ma20: 0.04,
        amount_ratio: 1.3,
        pctchange: 3.2,
        turn: 4.8,
        amplitude: 3.1,
        score: 0.88,
      },
    ],
  },
  fresh_trend_watchlist: {
    as_of_date: "2026-04-29",
    formula_version: "rv_fresh_trend_watchlist_candidates_v1",
    market_state: "WARM",
    observation_only: true,
    input_stock_count: 1,
    candidate_count: 1,
    excluded_stock_count: 0,
    insufficient_history_count: 0,
    items: [
      {
        rank: 1,
        stock_code: "000001.SZ",
        stock_name: "Alpha",
        sector_code: "801001",
        sector_name: "AI",
        concepts: ["AI hardware"],
        close: 21.9,
        ma20: 21.05,
        ma60: 19.05,
        ma120: 16.05,
        return_20d: 0.12,
        return_60d: 0.26,
        return_120d: 0.48,
        close_to_ma20: 0.04,
        amount_ratio: 1.3,
        pctchange: 3.2,
        turn: 4.8,
        amplitude: 3.1,
        hlimitedays: 0,
        score: 0.88,
      },
    ],
  },
  risk_exit: {
    as_of_date: "2026-04-29",
    formula_version: "rv_livermore_risk_exit_ema10_mvp_v1",
    position_count: 1,
    signal_count: 1,
    excluded_position_count: 0,
    insufficient_history_count: 0,
    items: [
      {
        stock_code: "000001.SZ",
        stock_name: "Alpha",
        reason: "2d_below_ema10",
        entry_cost: 10.5,
        bars_since_entry: 6,
        latest_close: 9.1,
        latest_ema10: 10.2,
        prior_close: 9.8,
        prior_ema10: 10.4,
      },
    ],
    watch_items: [
      {
        stock_code: "000777.SZ",
        stock_name: "Watch Alpha",
        entry_cost: 19.5,
        bars_since_entry: 4,
        latest_close: 19.8,
        latest_ema10: 20.1,
        prior_close: 20.4,
        prior_ema10: 20,
        exit_watch_price: 20.1,
        triggered: false,
      },
    ],
  },
};

const confluencePayload: LivermoreSignalConfluencePayload = {
  as_of_date: "2026-04-29",
  macro_context: {
    status: "neutral",
    composite_score: 0.05,
    multiplier: 0.5,
  },
  strategy_context: {
    market_gate_state: "WARM",
    market_gate_exposure: 0.4,
    allows_new_entry_observations: true,
  },
  position_size_hint: 0.2,
  entry_observations: [],
  exit_observations: [
    {
      stock_code: "000777.SZ",
      stock_name: "Watch Alpha",
      action: "observe_exit_watch",
      current_price: 19.8,
      exit_watch_price: 20.1,
      triggered: false,
      evidence: ["风险观察价来自 Livermore EMA10。"],
    },
  ],
  diagnostics: [],
  disclaimer: "Observation-only output.",
};

function buildReplayStatus(overrides: Partial<ConfluenceReplayStatus> = {}): ConfluenceReplayStatus {
  return {
    window_status: "valid",
    has_decision_usable_completed_stats: true,
    completed_dates: 2,
    pending_dates: 0,
    unsupported_dates: 0,
    proxy_only_dates: 0,
    completed_candidate_rows: 5,
    pending_candidate_rows: 0,
    unsupported_candidate_rows: 0,
    proxy_only_candidate_rows: 0,
    included_completed_stats_dates: ["2026-05-06", "2026-05-07"],
    blocked_dates: [],
    completed_zero_signal_dates: [],
    ...overrides,
  };
}

describe("stockAnalysisPageModel", () => {
  it("builds market state and sector rows from the Livermore strategy payload", () => {
    const card = buildMarketStateCard(strategyPayload);
    const sectors = buildSectorRows(strategyPayload);

    expect(card.title).toBe("市场状态");
    expect(card.state).toBe("温和");
    expect(card.exposureLabel).toBe("40%");
    expect(card.passedLabel).toBe("2 / 4 条件通过");
    expect(card.macroDisclosure).toBeNull();
    expect(card.macroDisclosureDetail).toBeNull();
    expect(card.warnings.join(" ")).toContain("市场宽度输入不可用");
    expect(card.warnings.join(" ")).toContain("5日市场宽度输入未落地");
    expect(card.conditions[0]).toMatchObject({
      label: "沪深300收盘价 > MA60",
      evidence: "收盘价高于 MA60。",
    });
    expect(`${card.conditions[0].label} ${card.conditions[0].evidence}`).not.toContain("CSI300 close");
    expect(card.conditions[0].evidence).not.toContain("Close is above");
    expect(card.conditions[1]).toMatchObject({
      label: "沪深300 MA20 > MA60",
      evidence: "MA20 高于 MA60。",
    });
    expect(card.conditions[2]).toMatchObject({
      label: "5日市场宽度 > 0",
      evidence: "5日市场宽度输入尚未落地，当前阶段不可用。",
    });
    expect(card.conditions[3]).toMatchObject({
      label: "涨停封板/破板质量为正",
      evidence: "涨停质量输入尚未落地，当前阶段不可用。",
    });
    const conditionText = card.conditions.map((condition) => `${condition.label} ${condition.evidence}`).join(" ");
    expect(conditionText).not.toContain("MA20 is above");
    expect(conditionText).not.toContain("5-day breadth");
    expect(conditionText).not.toContain("Breadth inputs");
    expect(conditionText).not.toContain("Limit-up");
    expect(conditionText).not.toContain("Phase 1 slice");
    expect(sectors[0].sectorName).toBe("AI");
    expect(sectors[0].pctChange).toBe("4.80%");
  });

  it("localizes unknown vendor market gate states before building page copy", () => {
    const vendorMarketState = "external_vendor_market_state";
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      market_gate: {
        ...strategyPayload.market_gate,
        state: vendorMarketState as LivermoreStrategyPayload["market_gate"]["state"],
      },
    };

    const marketCard = buildMarketStateCard(payload);
    const kpi = buildStockAnalysisKpiStrip(payload, confluencePayload, {
      quality_flag: "ok",
      vendor_status: "ok",
    }).find((item) => item.key === "market-state");
    const closedLoop = buildClosedLoopSummary(payload, {
      ...confluencePayload,
      closed_loop_state: {
        entry_gate: "open",
        exit_gate: "watch",
        replay_status: "available",
        lineage_status: "complete",
      },
    });
    const entryGate = closedLoop.items.find((item) => item.key === "entry_gate");
    const deepSummary = buildDeepAnalysisGateSummary({ gateState: vendorMarketState });
    const copy = [
      localizeMarketDataStatus(vendorMarketState),
      marketCard.state,
      kpi?.value,
      entryGate?.detail,
      deepSummary.line,
    ].join(" ");

    expect(localizeMarketDataStatus(vendorMarketState)).toBe("状态待确认");
    expect(marketCard.state).toBe("状态待确认");
    expect(kpi?.value).toBe("状态待确认");
    expect(entryGate?.detail).toContain("市场门控 状态待确认");
    expect(deepSummary.line).toContain("当前市场门控：状态待确认");
    expect(copy).not.toContain(vendorMarketState);
  });

  it("localizes unknown vendor strategy basis before building page copy", () => {
    const vendorBasis = "external_vendor_basis";
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      basis: vendorBasis as LivermoreStrategyPayload["basis"],
    };

    const decisionSummary = buildDecisionSummary(payload, {
      quality_flag: "ok",
      vendor_status: "ok",
    });
    const marketCard = buildMarketStateCard(payload);
    const evidenceStatus = buildStockAnalysisEvidenceStatus(payload, {
      quality_flag: "ok",
      vendor_status: "ok",
    });
    const basisEvidence = evidenceStatus.find((item) => item.key === "basis");
    const boundaryNotes = buildDataBoundaryNotes(payload);
    const copy = [
      decisionSummary.basisLabel,
      marketCard.basisLabel,
      basisEvidence?.statusLabel,
      basisEvidence?.detail,
      ...boundaryNotes,
    ].join(" ");

    expect(decisionSummary.basisLabel).toBe("口径待确认");
    expect(marketCard.basisLabel).toBe("口径待确认");
    expect(basisEvidence?.statusLabel).toBe("口径待确认");
    expect(basisEvidence?.detail).toBe("口径待确认");
    expect(boundaryNotes.join(" ")).toContain("口径：口径待确认");
    expect(copy).not.toContain(vendorBasis);
  });

  it("localizes unknown vendor market condition copy before building page copy", () => {
    const vendorCondition = "external_vendor_condition";
    const vendorEvidence = "external_vendor_condition_ready";
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      market_gate: {
        ...strategyPayload.market_gate,
        conditions: [
          {
            key: "external_vendor_gate",
            label: vendorCondition,
            status: "pass",
            evidence: vendorEvidence,
            source_series_id: "external_vendor_series",
          },
        ],
      },
    };

    const marketCard = buildMarketStateCard(payload);
    const copy = marketCard.conditions.map((condition) => `${condition.label} ${condition.evidence}`).join(" ");

    expect(marketCard.conditions[0]).toMatchObject({
      label: "条件待确认",
      evidence: "说明待确认",
    });
    expect(copy).not.toContain(vendorCondition);
    expect(copy).not.toContain(vendorEvidence);
    expect(copy).not.toContain("external_vendor_series");
  });

  it("builds candidate evidence with counter-evidence and invalidation rules", () => {
    const cards = buildCandidateEvidenceCards(strategyPayload);

    expect(cards[0].stockCode).toBe("000001.SZ");
    expect(cards[0].headline).toContain("观察候选");
    expect(cards[0].pattern).toBe("突破（参考）");
    expect(cards[0].patternNote).toContain("前端启发式");
    expect(cards[0].distanceToBreakoutPct).toMatch(/%/);
    expect(cards[0].evidence.join(" ")).toContain("行业排名第 1");
    expect(cards[0].evidence.join(" ")).toContain("收盘价 21.90");
    expect(cards[0].evidence.join(" ")).toContain("基本面因子");
    expect(cards[0].evidence.join(" ")).toContain("因子分 0.4812");
    expect(cards[0].evidence.join(" ")).toContain("ROE 18.0%");
    expect(cards[0].evidence.join(" ")).toContain("10EMA 失效观察");
    expect(cards[0].counterEvidence.join(" ")).toContain("基本面因子已纳入候选排序");
    expect(cards[0].counterEvidence.join(" ")).not.toContain("基本面 overlay");
    expect(cards[0].counterEvidence.join(" ")).toContain("新闻、公告、财报事件尚未进入候选卡");
    expect(cards[0].invalidationRules.join(" ")).toContain("10EMA");
    expect(cards[0].invalidationRules.join(" ")).toContain("涨跌停状态");
    expect(cards[0].rawFields.some((row) => row.key === "gap_norm")).toBe(true);
    expect(cards[0].rawFields.some((row) => row.key === "breakout_extension_norm")).toBe(true);
  });

  it("does not surface non-finite candidate raw field values", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      stock_candidates: {
        ...strategyPayload.stock_candidates!,
        items: [
          {
            ...strategyPayload.stock_candidates!.items[0],
            gap_norm: Number.POSITIVE_INFINITY,
            factor_overlay_rank: Number.NEGATIVE_INFINITY,
          },
        ],
      },
    };

    const [card] = buildCandidateEvidenceCards(payload);
    const rawFieldText = card.rawFields.map((row) => `${row.label}:${row.value}`).join(" ");

    expect(card.rawFields.find((row) => row.key === "gap_norm")?.value).toBe("待补");
    expect(card.rawFields.find((row) => row.key === "factor_overlay_rank")?.value).toBe("待补");
    expect(rawFieldText).not.toContain("Infinity");
    expect(rawFieldText).not.toContain("NaN");
  });

  it("builds a decision summary and review queue without inventing unavailable evidence", () => {
    const summary = buildDecisionSummary(strategyPayload, {
      quality_flag: "warning",
      vendor_status: "ok",
    });
    const queue = buildCandidateReviewQueue(strategyPayload);

    expect(summary.headline).toContain("今日市场状态：进攻");
    expect(summary.gateLabel).toBe("门控 2/4");
    expect(summary.exposureLabel).toBe("观察暴露 40%");
    expect(summary.dataFreshnessLabel).toBe("数据需复核 质量需复核 / 供数正常");
    expect(summary.nextReviewAction).toContain("先复核 Alpha");
    expect(summary.nextReviewAction).toContain("距观察位");
    expect(summary.boundaryLabel).toContain("2 条边界");
    expect(queue[0].reviewFocus).toContain("Alpha");
    expect(queue[0].primaryEvidence.map((item) => item.key)).toEqual([
      "sector_rank",
      "close_vs_break",
      "ma_curve",
    ]);
    expect(queue[0].supportingEvidence.map((item) => item.key)).toContain("fundamental_overlay");
    expect(queue[0].boundaryEvidence.join(" ")).toContain("基本面因子已纳入候选排序");
    expect(queue[0].invalidationFocus).toContain("10EMA");
    expect(queue[0].reviewFocus).not.toContain("买入");
  });

  it("uses the page-level missing data date label in decision summaries", () => {
    const summary = buildDecisionSummary(
      {
        ...strategyPayload,
        as_of_date: null,
        requested_as_of_date: "2026-05-08",
      },
      {
        quality_flag: "warning",
        vendor_status: "ok",
      },
    );

    expect(summary.asOfLabel).toBe("日期待补");
    expect(summary.asOfLabel).not.toBe("待补日期");
    expect(summary.asOfLabel).not.toBe("2026-05-08");
  });

  it("uses the page-level missing data date label in page purpose and inline meta", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      as_of_date: null,
      requested_as_of_date: "2026-05-08",
    };
    const purpose = buildStockAnalysisPagePurpose(payload, {
      quality_flag: "ok",
      vendor_status: "ok",
    });
    const inlineMeta = buildInlineMetaSegments(payload, {});
    const asOfMeta = inlineMeta.find((item) => item.key === "as_of");

    expect(purpose.asOfLine).toBe("观察日 日期待补");
    expect(purpose.dataStatusLine).toContain("日期待补");
    expect(purpose.asOfLine).not.toContain("2026-05-08");
    expect(purpose.dataStatusLine).not.toContain("2026-05-08");
    expect(asOfMeta?.text).toBe("日期待补");
    expect(asOfMeta?.text).not.toBe("待补日期");
    expect(asOfMeta?.text).not.toBe("2026-05-08");
  });

  it("localizes inline governance meta without exposing backend status codes", () => {
    const inlineMeta = buildInlineMetaSegments(strategyPayload, {
      quality_flag: "warning",
      vendor_status: "vendor_unavailable",
      fallback_mode: "external_vendor_snapshot",
      source_version: "sv_livermore_test",
      rule_version: "rv_livermore_market_gate_v1",
    });
    const copy = inlineMeta.map((item) => item.text).join(" ");

    expect(inlineMeta.find((item) => item.key === "quality_flag")?.text).toBe("质量需复核");
    expect(inlineMeta.find((item) => item.key === "vendor_status")?.text).toBe("供数待确认");
    expect(inlineMeta.find((item) => item.key === "fallback_mode")?.text).toBe("待确认");
    expect(copy).toContain("sv_livermore_test");
    expect(copy).toContain("rv_livermore_market_gate_v1");
    expect(copy).not.toContain("warning");
    expect(copy).not.toContain("vendor_unavailable");
    expect(copy).not.toContain("external_vendor_snapshot");
  });

  it("keeps requested dates separate from missing data dates in evidence status", () => {
    const rows = buildStockAnalysisEvidenceStatus(
      {
        ...strategyPayload,
        as_of_date: null,
        requested_as_of_date: "2026-05-08",
      },
      {},
    );
    const asOfRow = rows.find((item) => item.key === "as-of-date");

    expect(asOfRow?.label).toBe("数据日期");
    expect(asOfRow?.statusLabel).toBe("日期待补");
    expect(asOfRow?.statusLabel).not.toBe("待补");
    expect(asOfRow?.statusLabel).not.toBe("2026-05-08");
    expect(asOfRow?.detail).toBe("请求日期 2026-05-08");
  });

  it("does not use payload formula versions as the response rule-version lineage", () => {
    const rows = buildStockAnalysisEvidenceStatus(strategyPayload, {
      source_version: "sv_livermore_test",
    });
    const ruleRow = rows.find((item) => item.key === "rule-version");

    expect(ruleRow?.label).toBe("规则版本");
    expect(ruleRow?.statusLabel).toBe("规则待确认");
    expect(ruleRow?.tone).toBe("warning");
    expect(ruleRow?.statusLabel).not.toBe(strategyPayload.sector_rank?.formula_version);
  });

  it("marks healthy endpoint evidence as connected without inventing warnings", () => {
    const rows = buildStockEndpointEvidenceItems([
      {
        key: "strategy",
        label: "主策略快照",
        queryState: "success",
        meta: {
          trace_id: "trace-stock-20260429",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          resolved_report_date: "2026-04-29",
        },
        asOfDate: "2026-04-29",
        warningCount: 0,
        unsupportedCount: 0,
        missingInputCount: 0,
      },
    ]);

    expect(rows[0]).toMatchObject({
      statusLabel: "接通",
      tone: "positive",
      dateLabel: "日期：2026-04-29",
      issueLabel: "无新增提示",
      metaLabel: "数据正常",
      traceLabel: "链路：trace-stock-20260429",
    });
  });

  it("keeps fallback and endpoint business gaps in review state", () => {
    const rows = buildStockEndpointEvidenceItems([
      {
        key: "history",
        label: "策略回溯窗口",
        queryState: "success",
        meta: {
          trace_id: "trace-history",
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "latest_snapshot",
        },
        snapshotFrom: "2026-04-20",
        snapshotTo: "2026-04-29",
        warningCount: 2,
        unsupportedCount: 1,
        missingInputCount: 3,
      },
    ]);

    expect(rows[0].statusLabel).toBe("需复核");
    expect(rows[0].tone).toBe("warning");
    expect(rows[0].dateLabel).toBe("窗口：2026-04-20 至 2026-04-29");
    expect(rows[0].issueLabel).toBe("提示 2 / 阻断 1 / 缺输入 3");
    expect(rows[0].metaLabel).toBe("数据延迟");
  });

  it("does not present idle, failed, or meta-missing endpoints as ready", () => {
    const rows = buildStockEndpointEvidenceItems([
      {
        key: "score",
        label: "优先级评分",
        queryState: "idle",
      },
      {
        key: "history",
        label: "策略回溯窗口",
        queryState: "loading",
        asOfDate: "2026-04-29",
        meta: {
          trace_id: "trace-history",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      },
      {
        key: "confluence",
        label: "信号闭环",
        queryState: "error",
        meta: {
          trace_id: "trace-confluence",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      },
      {
        key: "sector-series",
        label: "板块支撑序列",
        queryState: "success",
        asOfDate: "2026-04-29",
        warningCount: 0,
        unsupportedCount: 0,
        missingInputCount: 0,
      },
    ]);

    expect(rows[0]).toMatchObject({
      statusLabel: "待触发",
      tone: "neutral",
      dateLabel: "",
      traceLabel: "",
      issueLabel: "",
      metaLabel: "",
    });
    expect(rows[1]).toMatchObject({
      statusLabel: "读取中",
      tone: "neutral",
      dateLabel: "",
      traceLabel: "",
      issueLabel: "",
      metaLabel: "",
    });
    expect(rows[2]).toMatchObject({
      statusLabel: "读取失败",
      tone: "negative",
      dateLabel: "",
      traceLabel: "",
      issueLabel: "",
      metaLabel: "",
    });
    expect(rows[3]).toMatchObject({
      statusLabel: "证据待补",
      tone: "warning",
      metaLabel: "证据待补",
    });
    expect(rows[3].detail).not.toContain("result_meta");
  });

  it("builds an observation closure summary without implying formal completion", () => {
    const endpoints = buildStockEndpointEvidenceItems([
      {
        key: "strategy",
        label: "主策略快照",
        queryState: "success",
        meta: {
          trace_id: "trace-strategy",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
        warningCount: 0,
        unsupportedCount: 0,
        missingInputCount: 0,
      },
      {
        key: "history",
        label: "策略回溯窗口",
        queryState: "success",
        meta: {
          trace_id: "trace-history",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "latest_snapshot",
        },
        warningCount: 1,
        unsupportedCount: 0,
        missingInputCount: 0,
      },
      {
        key: "sector-series",
        label: "板块支撑序列",
        queryState: "error",
      },
      {
        key: "optimization",
        label: "策略优化",
        queryState: "success",
      },
    ]);
    const summary = buildObservationClosureSummary({
      endpointItems: endpoints,
      formalUseAllowed: false,
      approvalStatus: "gap_or_observational",
      reasonInputs: [
        {
          endpointId: "history",
          endpointLabel: "策略回溯窗口",
          kind: "fallback",
          fieldPath: "history.result_meta.fallback_mode",
          displayText: "策略回溯窗口声明 fallback_mode：latest_snapshot",
          rawValueLabel: "latest_snapshot",
        },
      ],
    });

    expect(summary.endpointTotal).toBe(4);
    expect(summary.endpointLoadedCount).toBe(3);
    expect(summary.endpointErrorCount).toBe(1);
    expect(summary.metaMissingCount).toBe(1);
    expect(summary.formalUseAllowed).toBe(false);
    expect(summary.detail).toContain("正式用途：否");
    expect(summary.detail).toContain("gap_or_observational");
    expect(summary.headline).toBe("证据读取覆盖 3/4");
    expect(summary.headline).not.toContain("闭环完成");
    expect(summary.unresolvedReasons.map((item) => item.kind)).toEqual([
      "query-error",
      "meta-missing",
      "fallback",
    ]);
    expect(summary.nextEvidenceActions.map((item) => item.actionText).join(" ")).toContain("回退状态");
  });

  it("summarizes cycle macro layer landed state and macro gaps", () => {
    const landed = buildCycleMacroLayerSummary({
      ...strategyPayload,
      hybrid_fusion_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_hybrid_fusion_candidates_v4",
        market_state: "WARM",
        observation_only: true,
        candidate_count: 0,
        coverage_note: "Macro layer landed.",
        items: [],
      },
      cycle_rotation_framework: {
        strategy_name: "A-share cycle rotation research framework",
        display_name: "A股景气周期选股与行业轮动",
        observation_only: true,
        implementation_stage: "verification_pending",
        score_formula: "CycleScore = 0.30 Macro + 0.35 Industry + 0.20 MarketFlow + 0.15 ValuationSupport",
        rebalance_cadence: "Monthly core review with weekly satellite monitoring.",
        macro_layer: {
          macro_score: 0.753,
          ready: true,
          evidence: "MacroScore=0.753 from PMI/credit_impulse/price_spread.",
          available_inputs: ["pmi", "credit_impulse", "price_spread"],
          missing_inputs: [],
          lineage: { pmi_series_id: "M0017126" },
        },
        layers: [],
        constraints: [],
        boundary: "observation-only",
      },
      data_gaps: [
        {
          input_family: "breadth",
          status: "missing",
          evidence: "breadth missing",
        },
      ],
    });

    expect(landed?.statusLabel).toBe("已落地");
    expect(landed?.macroScoreLabel).toBe("0.7530");
    expect(landed?.formulaVersionLabel).toBe("rv_hybrid_fusion_candidates_v4");
    expect(landed?.macroGapLabels).toEqual([]);

    const missing = buildCycleMacroLayerSummary({
      ...strategyPayload,
      cycle_rotation_framework: {
        strategy_name: "A-share cycle rotation research framework",
        display_name: "A股景气周期选股与行业轮动",
        observation_only: true,
        implementation_stage: "verification_pending",
        score_formula: "CycleScore = 0.30 Macro + 0.35 Industry + 0.20 MarketFlow + 0.15 ValuationSupport",
        rebalance_cadence: "Monthly core review with weekly satellite monitoring.",
        macro_layer: {
          macro_score: null,
          ready: false,
          evidence: "PMI and credit impulse are not landed.",
          available_inputs: ["market_gate"],
          missing_inputs: ["pmi", "credit_impulse", "price_spread"],
          lineage: {},
        },
        layers: [],
        constraints: [],
        boundary: "observation-only",
      },
      data_gaps: [
        {
          input_family: "PMI",
          status: "missing",
          evidence: "M0017126 not landed.",
        },
        {
          input_family: "credit_impulse",
          status: "missing",
          evidence: "M5525763 not landed.",
        },
      ],
    });

    expect(missing?.statusLabel).toBe("部分就绪");
    expect(missing?.macroGapLabels).toEqual(["PMI 缺失", "信用脉冲 缺失"]);
    expect(missing?.detailLabel).toContain("可用 市场门控");
    expect(missing?.detailLabel).toContain("缺失 PMI、信用脉冲、价差");
    expect(missing?.detailLabel).not.toContain("credit_impulse");
    expect(missing?.detailLabel).not.toContain("(missing)");
    expect(missing?.formulaVersionLabel).toBe("rv_hybrid_fusion_candidates_v4");
  });

  it("uses hybrid fusion candidates as the primary review queue when present", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      supported_outputs: [...strategyPayload.supported_outputs, "hybrid_fusion"],
      hybrid_fusion_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_hybrid_fusion_candidates_v1",
        market_state: "WARM",
        observation_only: true,
        candidate_count: 1,
        coverage_note: "Hybrid fusion uses existing proxy inputs.",
        items: [
          {
            rank: 1,
            stock_code: "000009.SZ",
            stock_name: "Fusion Alpha",
            sector_code: "801009",
            sector_name: "机器人",
            fusion_score: 0.812345,
            cycle_score: 0.7,
            lifecourt_proxy_score: 0.6,
            attention_score: 0.55,
            price_confirm_score: 0.8,
            crowding_penalty: 0.1,
            fusion_action: "sourceTableFusionAction",
            confidence: "external_vendor_confidence",
            reason: "Fusion observation-only candidate",
            evidence: { source_kinds: ["factor_screen", "theme_breakout", "external_vendor_signal"] },
          },
        ],
      },
    };

    const cards = buildCandidateEvidenceCards(payload);
    const queue = buildCandidateReviewQueue(payload);
    const summary = buildDecisionSummary(payload, { quality_flag: "ok", vendor_status: "ok" });

    expect(cards[0].headline).toContain("融合策略");
    expect(cards[0].stockCode).toBe("000009.SZ");
    expect(cards[0].evidence.join(" ")).toContain("融合分");
    expect(cards[0].evidence.join(" ")).toContain("融合裁决：裁决待确认");
    expect(cards[0].evidence.join(" ")).not.toContain("sourceTableFusionAction");
    expect(cards[0].counterEvidence.join(" ")).toContain("代理信号");
    expect(cards[0].counterEvidence.join(" ")).toContain("来源待确认");
    expect(cards[0].counterEvidence.join(" ")).not.toContain("仓位建议");
    expect(cards[0].counterEvidence.join(" ")).not.toContain("external_vendor_signal");
    expect(cards[0].rawFields.map((row) => row.value).join(" ")).not.toContain("sourceTableFusionAction");
    const confidenceEvidence = cards[0].evidenceBullets.find((row) => row.key === "confidence");
    expect(confidenceEvidence).toBeDefined();
    expect(confidenceEvidence?.value).toBe("置信度待确认");
    expect(confidenceEvidence?.value).not.toContain("external_vendor_confidence");
    expect(queue[0].stockName).toBe("Fusion Alpha");
    expect(summary.candidateCountLabel).toBe("候选 1");
    expect(summary.nextReviewAction).toContain("Fusion Alpha");
    expect(summary.nextReviewAction).not.toContain("买入");
  });

  it("discloses factor_rank_available on hybrid fusion candidates when the backend reports it", () => {
    const basePayload: LivermoreStrategyPayload = {
      ...strategyPayload,
      supported_outputs: [...strategyPayload.supported_outputs, "hybrid_fusion"],
      hybrid_fusion_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_hybrid_fusion_candidates_v1",
        market_state: "WARM",
        observation_only: true,
        candidate_count: 1,
        coverage_note: "Hybrid fusion uses existing proxy inputs.",
        items: [
          {
            rank: 1,
            stock_code: "000009.SZ",
            stock_name: "Fusion Alpha",
            sector_code: "801009",
            sector_name: "机器人",
            fusion_score: 0.81,
            cycle_score: 0.7,
            lifecourt_proxy_score: 0.6,
            attention_score: 0.55,
            price_confirm_score: 0.8,
            crowding_penalty: 0.1,
            factor_rank_available: false,
            fusion_action: "monitor_only",
            confidence: "low",
            reason: "Fusion observation-only candidate",
            evidence: { source_kinds: ["factor_screen"] },
          },
        ],
      },
    };

    const missingCards = buildCandidateEvidenceCards(basePayload);
    expect(missingCards[0].evidenceBullets.find((row) => row.key === "factor_rank_available")).toMatchObject({
      value: "缺失，景气周期权重已重归一",
    });

    const legacyCards = buildCandidateEvidenceCards({
      ...basePayload,
      hybrid_fusion_candidates: {
        ...basePayload.hybrid_fusion_candidates!,
        items: [
          {
            ...basePayload.hybrid_fusion_candidates!.items[0],
            factor_rank_available: undefined,
          },
        ],
      },
    });
    expect(legacyCards[0].evidenceBullets.some((row) => row.key === "factor_rank_available")).toBe(false);
  });

  it("localizes signed hybrid fusion actions without turning them into trading instructions", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      supported_outputs: strategyPayload.supported_outputs.includes("hybrid_fusion")
        ? strategyPayload.supported_outputs
        : [...strategyPayload.supported_outputs, "hybrid_fusion" as LivermoreOutputKey],
      hybrid_fusion_candidates: {
        as_of_date: "2026-06-26",
        formula_version: "rv_hybrid_fusion_candidates_v4",
        market_state: "WARM",
        observation_only: true,
        candidate_count: 3,
        coverage_note: "Hybrid fusion uses signed observation inputs.",
        items: [
          {
            rank: 1,
            stock_code: "000001.SZ",
            stock_name: "Core Alpha",
            sector_code: "801001",
            sector_name: "AI",
            fusion_score: 0.36,
            cycle_score: 0.46,
            lifecourt_proxy_score: 0.18,
            attention_score: 0.22,
            price_confirm_score: 0.33,
            crowding_penalty: 0,
            fusion_action: "core_plus_trading",
            confidence: "low",
            reason: "Fusion observation-only candidate",
            evidence: { source_kinds: ["stock_candidate", "factor_screen"] },
          },
          {
            rank: 2,
            stock_code: "000002.SZ",
            stock_name: "Reduce Beta",
            sector_code: "801002",
            sector_name: "新能源车",
            fusion_score: 0.24,
            cycle_score: 0.29,
            lifecourt_proxy_score: 0.14,
            attention_score: 0.18,
            price_confirm_score: 0.24,
            crowding_penalty: 0,
            fusion_action: "core_reduce_trading",
            confidence: "medium",
            reason: "Fusion observation-only candidate",
            evidence: { source_kinds: ["factor_screen"] },
          },
          {
            rank: 3,
            stock_code: "000003.SZ",
            stock_name: "Satellite Gamma",
            sector_code: "801003",
            sector_name: "电子",
            fusion_score: 0.18,
            cycle_score: 0.2,
            lifecourt_proxy_score: 0.1,
            attention_score: 0.12,
            price_confirm_score: 0.2,
            crowding_penalty: 0,
            fusion_action: "satellite_trial",
            confidence: "high",
            reason: "Fusion observation-only candidate",
            evidence: { source_kinds: ["theme_breakout"] },
          },
        ],
      },
    };

    const cards = buildCandidateEvidenceCards(payload);
    const actionValues = cards.map((card) => card.rawFields.find((row) => row.key === "fusion_action")?.value);
    const confidenceValues = cards.map((card) => card.rawFields.find((row) => row.key === "confidence")?.value);

    expect(actionValues).toEqual(["重点复核", "降权观察", "卫星观察"]);
    expect(confidenceValues).toEqual(["低", "中", "高"]);
    expect(cards.map((card) => card.evidence.join(" ")).join(" ")).not.toContain("core_plus_trading");
    expect(cards.map((card) => card.evidence.join(" ")).join(" ")).not.toContain("trading");
    expect(cards.map((card) => card.evidence.join(" ")).join(" ")).not.toContain("买入");
  });

  it("treats fallback snapshots as data that needs review", () => {
    const summary = buildDecisionSummary(strategyPayload, {
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "latest_snapshot",
    });
    const purpose = buildStockAnalysisPagePurpose(strategyPayload, {
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "latest_snapshot",
    });

    expect(summary.dataFreshnessLabel).toBe("数据需复核 质量正常 / 供数正常 / 数据延迟");
    expect(purpose.dataStatusLine).toContain("数据延迟");
    expect(purpose.dataStatusLine).not.toContain("latest_snapshot");
  });

  it("keeps unknown fallback modes as business labels", () => {
    const unknownFallbackMeta = {
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "external_vendor_snapshot",
    } as Record<string, unknown> as Partial<Pick<ResultMeta, "quality_flag" | "vendor_status" | "fallback_mode">>;
    const summary = buildDecisionSummary(strategyPayload, unknownFallbackMeta);
    const purpose = buildStockAnalysisPagePurpose(strategyPayload, unknownFallbackMeta);

    expect(summary.dataFreshnessLabel).toContain("待确认");
    expect(purpose.dataStatusLine).toContain("待确认");
    expect(summary.dataFreshnessLabel).not.toContain("external_vendor_snapshot");
    expect(purpose.dataStatusLine).not.toContain("external_vendor_snapshot");
  });

  it("merges closed-loop result meta with confluence precedence only when closed-loop evidence exists", () => {
    const strategyMeta = {
      quality_flag: "warning",
      vendor_status: "vendor_unavailable",
      fallback_mode: "latest_snapshot",
      source_version: "strategy-source",
      rule_version: "strategy-rule",
    } satisfies Pick<ResultMeta, "quality_flag" | "vendor_status" | "fallback_mode" | "source_version" | "rule_version">;
    const confluenceMeta = {
      quality_flag: "ok",
      vendor_status: "ok",
      source_version: "confluence-source",
    } satisfies Partial<Pick<ResultMeta, "quality_flag" | "vendor_status" | "source_version">>;

    expect(mergeStockClosedLoopMeta(true, strategyMeta, confluenceMeta)).toEqual({
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "latest_snapshot",
      source_version: "confluence-source",
      rule_version: "strategy-rule",
    });

    expect(mergeStockClosedLoopMeta(false, strategyMeta, confluenceMeta)).toEqual(strategyMeta);
  });

  it("picks only freshness fields needed by first-screen page models", () => {
    expect(
      pickStockFreshnessMeta({
        quality_flag: "warning",
        vendor_status: "vendor_unavailable",
        fallback_mode: "latest_snapshot",
        source_version: "source-not-needed",
        rule_version: "rule-not-needed",
      }),
    ).toEqual({
      quality_flag: "warning",
      vendor_status: "vendor_unavailable",
      fallback_mode: "latest_snapshot",
    });

    expect(pickStockFreshnessMeta(null)).toEqual({});
  });

  it("builds page purpose and review-queue empty guidance in Chinese", () => {
    const purpose = buildStockAnalysisPagePurpose(strategyPayload, {
      quality_flag: "ok",
      vendor_status: "ok",
    });
    expect(purpose.title).toBe("股票策略复核台");
    expect(purpose.subtitle).toContain("只读复核");
    expect(purpose.dataStatusLine).toContain("已对齐");

    const empty = buildReviewQueueEmptyState({
      ...strategyPayload,
      stock_candidates: {
        ...strategyPayload.stock_candidates!,
        candidate_count: 0,
        items: [],
      },
      factor_screen_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "factor_v1",
        market_state: "WARM",
        input_stock_count: 1,
        candidate_count: 30,
        coverage_note: "ok",
        items: [],
      },
    });
    expect(empty.headline).toContain("没有进入复核队列");
    expect(empty.detail).toContain("多因子池 30 只");

    expect(localizeImplementationStage("verification_pending")).toBe("证据待齐");
    expect(localizeImplementationStage("external_vendor_pending")).toBe("阶段待确认");
    expect(localizeImplementationStage("external_vendor_pending")).not.toBe("external vendor pending");
    expect(localizeMarketDataStatus("unknown")).toBe("状态待确认");
    expect(localizeMarketDataStatus("unknown")).not.toBe("unknown");
    expect(localizeThemeSourceKind("choice_stock_intraday_movement_event", false)).toBe("来源待确认");
  });

  it("keeps the decision summary honest when candidates are unavailable", () => {
    const summary = buildDecisionSummary(
      {
        ...strategyPayload,
        stock_candidates: {
          ...strategyPayload.stock_candidates!,
          candidate_count: 0,
          items: [],
        },
        fresh_trend_watchlist: undefined,
        unsupported_outputs: [
          {
            key: "stock_candidates",
            reason: "choice_stock_daily_observation is not landed.",
          },
        ],
      },
      { quality_flag: "ok", vendor_status: "ok" },
    );

    expect(summary.candidateCountLabel).toBe("候选 0");
    expect(summary.nextReviewAction).toContain("深度分析");
    expect(summary.nextReviewAction).toContain("策略共振");
    expect(summary.nextReviewAction).toContain("多策略观察池");
    expect(summary.boundaryLabel).toContain("3 条边界");
    expect(summary.nextReviewAction).not.toContain("Alpha");
  });

  it("builds theme breakout cards as proxy-only observations", () => {
    const cards = buildThemeBreakoutCards({
      ...strategyPayload,
      theme_breakout: {
        as_of_date: "2026-05-08",
        formula_version: "rv_livermore_theme_breakout_proxy_v1",
        is_proxy: true,
        theme_count: 1,
        items: [
          {
            rank: 1,
            as_of_date: "2026-05-08",
            theme_key: "semiconductor_proxy",
            theme_name: "Semiconductor proxy",
            parent_sector_code: "801080",
            parent_sector_name: "Electronic",
            parent_sector_rank: 9,
            member_count: 3,
            advance_count: 3,
            advance_ratio: 1,
            strong_stock_count: 3,
            limit_stock_count: 2,
            avg_pctchange: 9.766667,
            avg_turn: 4.4,
            avg_amplitude: 7.3,
            observation_only: true,
            reason: "Observation-only proxy cluster: leaders 688001.SH, 688002.SH.",
            items: [
              {
                stock_code: "688001.SH",
                stock_name: "Alpha Semiconductor",
                sector_code: "801080",
                sector_name: "Electronic",
                sector_rank: 9,
                open: 9.6,
                high: 10.1,
                low: 9.4,
                close: 10,
                pctchange: 12.1,
                turn: 4.2,
                amplitude: 7,
                close_strength: 0.86,
                closed_up_limit: true,
                strong: true,
              },
            ],
          },
        ],
      },
    });

    expect(cards[0]).toMatchObject({
      themeKey: "semiconductor_proxy",
      parentSectorLabel: "电子 #9",
      strongCountLabel: "强势 3",
      limitCountLabel: "涨停 2",
      avgPctChangeLabel: "均涨跌 9.77%",
    });
    expect(cards[0].boundaryLabel).toContain("代理题材观察");
    expect(cards[0].leaders[0]).toMatchObject({
      stockCode: "688001.SH",
      pctChange: "12.10%",
      tags: ["涨停", "强势"],
    });
    expect(`${cards[0].summary} ${cards[0].boundaryLabel}`).not.toContain("买入");
  });

  it("builds flattened theme leader preview items from breakout cards", () => {
    const cards = buildThemeBreakoutCards({
      ...strategyPayload,
      theme_breakout: {
        as_of_date: "2026-05-08",
        formula_version: "rv_livermore_theme_breakout_proxy_v1",
        is_proxy: true,
        theme_count: 1,
        items: [
          {
            rank: 1,
            as_of_date: "2026-05-08",
            theme_key: "semiconductor_proxy",
            theme_name: "Semiconductor proxy",
            parent_sector_code: "801080",
            parent_sector_name: "Electronic",
            parent_sector_rank: 9,
            member_count: 2,
            advance_count: 2,
            advance_ratio: 1,
            strong_stock_count: 2,
            limit_stock_count: 1,
            avg_pctchange: 9.5,
            avg_turn: 4.2,
            avg_amplitude: 7,
            observation_only: true,
            reason: "Leaders 688001.SH, 688002.SH.",
            items: [
              {
                stock_code: "688001.SH",
                stock_name: "Alpha Semiconductor",
                sector_code: "801080",
                sector_name: "Electronic",
                sector_rank: 9,
                open: 9.6,
                high: 10.1,
                low: 9.4,
                close: 10,
                pctchange: 12.1,
                turn: 4.2,
                amplitude: 7,
                close_strength: 0.86,
                closed_up_limit: true,
                strong: true,
              },
              {
                stock_code: "688002.SH",
                stock_name: "Beta Semiconductor",
                sector_code: "801080",
                sector_name: "Electronic",
                sector_rank: 9,
                open: 8.6,
                high: 9.1,
                low: 8.4,
                close: 9,
                pctchange: 8.1,
                turn: 3.8,
                amplitude: 6,
                close_strength: 0.72,
                closed_up_limit: false,
                strong: true,
              },
            ],
          },
        ],
      },
    });

    expect(buildThemeLeaderPreviewItems(cards, 12)).toEqual([
      expect.objectContaining({
        stockCode: "688001.SH",
        stockName: "Alpha Semiconductor",
        themeName: "半导体",
        themeRank: 1,
        pctChange: "12.10%",
        tags: ["涨停", "强势"],
      }),
      expect.objectContaining({
        stockCode: "688002.SH",
        stockName: "Beta Semiconductor",
        themeName: "半导体",
        themeRank: 1,
        pctChange: "8.10%",
        tags: ["强势"],
      }),
    ]);
    expect(buildThemeLeaderPreviewItems(cards, 1)).toHaveLength(1);
  });

  it("builds sector heavyweight preview rows for top sectors", () => {
    const preview = buildSectorHeavyweightPreview({
      ...strategyPayload,
      theme_breakout: {
        as_of_date: "2026-05-08",
        formula_version: "rv_livermore_theme_breakout_proxy_v1",
        is_proxy: true,
        theme_count: 1,
        items: [
          {
            rank: 1,
            as_of_date: "2026-05-08",
            theme_key: "semiconductor_proxy",
            theme_name: "Semiconductor proxy",
            parent_sector_code: "801080",
            parent_sector_name: "Electronic",
            parent_sector_rank: 1,
            member_count: 2,
            advance_count: 2,
            advance_ratio: 1,
            strong_stock_count: 2,
            limit_stock_count: 1,
            avg_pctchange: 9.5,
            avg_turn: 4.2,
            avg_amplitude: 7,
            observation_only: true,
            reason: "Leaders 688001.SH.",
            items: [
              {
                stock_code: "688001.SH",
                stock_name: "Alpha Semiconductor",
                sector_code: "801001",
                sector_name: "新能源车",
                sector_rank: 1,
                open: 9.6,
                high: 10.1,
                low: 9.4,
                close: 10,
                pctchange: 12.1,
                turn: 4.2,
                amplitude: 7,
                close_strength: 0.86,
                closed_up_limit: true,
                strong: true,
              },
            ],
          },
        ],
      },
    });

    expect(preview.rows[0]).toMatchObject({
      sectorCode: "801001",
      sectorName: "AI",
      sectorRank: 1,
    });
    expect(preview.rows[0].stocks[0]).toMatchObject({
      stockCode: "688001.SH",
      pctChange: "12.10%",
      sourceLabel: "题材强势",
      detailSource: "theme_breakout",
    });
    expect(preview.sectorsWithSamples).toBe(1);
  });

  it("prefers backend sector leader constituents over strategy pool", () => {
    const preview = buildSectorHeavyweightPreview({
      ...strategyPayload,
      sector_rank: {
        ...strategyPayload.sector_rank!,
        leader_constituent_limit: 3,
        leader_constituent_method: "top_turn_same_day",
        items: strategyPayload.sector_rank!.items.map((item) =>
          item.sector_code === "801001"
            ? {
                ...item,
                leader_constituents: [
                  {
                    rank: 1,
                    stock_code: "688001.SH",
                    stock_name: "Leader Alpha",
                    pctchange: 8.2,
                    turn: 5.5,
                    amplitude: 6.1,
                  },
                ],
              }
            : item,
        ),
      },
    });

    expect(preview.rows[0].stocks[0]).toMatchObject({
      stockCode: "688001.SH",
      stockName: "Leader Alpha",
      pctChange: "8.20%",
      sourceLabel: "板块成分",
      detailSource: "sector_constituent",
      auxiliaryLabel: "振幅 6.10%",
    });
  });

  it("builds real concept theme breakout cards with movement evidence", () => {
    const cards = buildThemeBreakoutCards({
      ...strategyPayload,
      theme_breakout: {
        as_of_date: "2026-05-08",
        formula_version: "rv_livermore_theme_breakout_proxy_v1",
        is_proxy: false,
        theme_count: 1,
        items: [
          {
            rank: 1,
            as_of_date: "2026-05-08",
            theme_key: "concept:C001",
            theme_name: "Chiplet",
            source_kind: "real_concept",
            parent_sector_code: "801080",
            parent_sector_name: "Electronic",
            parent_sector_rank: 9,
            member_count: 3,
            advance_count: 3,
            advance_ratio: 1,
            strong_stock_count: 3,
            limit_stock_count: 2,
            avg_pctchange: 9.766667,
            avg_turn: 4.4,
            avg_amplitude: 7.3,
            movement_event_count: 2,
            latest_event_title: "Chiplet concept extends gains",
            latest_event_time: "2026-05-08 10:08:00",
            observation_only: true,
            reason: "Observation-only real concept cluster: leaders 688001.SH, 688002.SH.",
            items: [],
          },
        ],
      },
    });

    expect(cards[0].themeName).toBe("Chiplet");
    expect(cards[0].boundaryLabel).toContain("真实题材观察");
    expect(cards[0].movementLabel).toBe("异动 2");
    expect(cards[0].latestEventLabel).toContain("Chiplet concept extends gains");
    expect(`${cards[0].summary} ${cards[0].boundaryLabel}`).not.toContain("买入");
  });

  it("builds theme evidence state rows without treating missing inputs as neutral proof", () => {
    const rows = buildThemeEvidenceStateRows({
      ...strategyPayload,
      theme_breakout: {
        as_of_date: "2026-05-08",
        formula_version: "rv_livermore_theme_breakout_proxy_v1",
        is_proxy: true,
        theme_count: 0,
        evidence_state: {
          concept_membership: {
            input_family: "concept_membership",
            status: "catalog_unconfirmed",
            row_count: 0,
            matched_row_count: 0,
            message: "Optional concept membership is not confirmed in the Choice stock catalog.",
          },
          intraday_movement: {
            input_family: "intraday_movement",
            status: "table_missing",
            table: "choice_stock_intraday_movement_event",
            row_count: 0,
            matched_row_count: 0,
            message: "Intraday movement table is not landed for this environment.",
          },
        },
        items: [],
      },
    });

    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      key: "concept_membership",
      status: "catalog_unconfirmed",
    });
    expect(rows[0].statusLabel).toContain("目录待确认");
    expect(rows[1].detail).toContain("盘中异动");
    expect(rows[1].detail).toContain("数据源缺失");
    expect(rows.map((row) => row.detail).join(" ")).not.toContain("buy");
  });

  it("localizes theme evidence fallback labels before exposing source-table diagnostics", () => {
    const rows = buildThemeEvidenceStateRows({
      ...strategyPayload,
      theme_breakout: {
        as_of_date: "2026-05-08",
        formula_version: "rv_livermore_theme_breakout_proxy_v1",
        is_proxy: true,
        theme_count: 0,
        evidence_state: {
          inputs: [
            {
              input_family: "choice_stock_intraday_movement_event",
              status: "source_table_missing",
              table: "choice_stock_intraday_movement_event",
              row_count: 0,
              matched_row_count: 0,
              message: "source_table choice_stock_intraday_movement_event is missing.",
            },
            {
              input_family: "external_vendor_theme_feed",
              status: "vendor_sync_delayed",
              row_count: 0,
              matched_row_count: 0,
              message: "External vendor theme feed sync is delayed.",
            },
          ],
        },
        items: [],
      },
    });

    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      label: "盘中异动",
      statusLabel: "数据源缺失",
      detail: "盘中异动：数据源缺失",
    });
    expect(rows[1]).toMatchObject({
      label: "题材输入",
      statusLabel: "状态待确认",
      detail: "题材输入：状态待确认",
    });
    expect(`${rows[0].label} ${rows[0].statusLabel} ${rows[0].detail}`).not.toContain(
      "choice_stock_intraday_movement_event",
    );
    expect(`${rows[0].label} ${rows[0].statusLabel} ${rows[0].detail}`).not.toContain("source_table_missing");
    expect(`${rows[0].label} ${rows[0].statusLabel} ${rows[0].detail}`).not.toContain("source_table");
    expect(`${rows[1].label} ${rows[1].statusLabel} ${rows[1].detail}`).not.toContain("external_vendor_theme_feed");
    expect(`${rows[1].label} ${rows[1].statusLabel} ${rows[1].detail}`).not.toContain("vendor_sync_delayed");
  });

  it("builds theme breakout review items with failed gate codes as additive evidence", () => {
    const reviewItems = buildThemeBreakoutReviewItems({
      ...strategyPayload,
      theme_breakout: {
        as_of_date: "2026-05-08",
        formula_version: "rv_livermore_theme_breakout_proxy_v1",
        is_proxy: true,
        theme_count: 0,
        items: [],
        review_items: [
          {
            rank: 1,
            as_of_date: "2026-05-08",
            theme_key: "semiconductor_proxy",
            theme_name: "Semiconductor proxy",
            source_kind: "proxy",
            parent_sector_code: "801080",
            parent_sector_name: "Electronic",
            parent_sector_rank: 9,
            member_count: 2,
            advance_count: 2,
            advance_ratio: 1,
            strong_stock_count: 2,
            limit_stock_count: 0,
            avg_pctchange: 6.25,
            avg_turn: 4.1,
            avg_amplitude: 6.8,
            movement_event_count: 0,
            failed_gates: ["insufficient_cluster_strength", "liquidity_pressure_too_high"],
            observation_only: true,
            reason: "Observation-only near-miss: failed gates insufficient_cluster_strength.",
            items: [
              {
                stock_code: "688001.SH",
                stock_name: "Alpha Semiconductor",
                sector_code: "801080",
                sector_name: "Electronic",
                sector_rank: 9,
                open: 9.6,
                high: 10.1,
                low: 9.4,
                close: 10,
                pctchange: 6.5,
                turn: 4.2,
                amplitude: 7,
                close_strength: 0.86,
                closed_up_limit: false,
                strong: true,
              },
            ],
          },
        ],
      },
    });

    expect(reviewItems).toHaveLength(1);
    expect(reviewItems[0]).toMatchObject({
      themeKey: "semiconductor_proxy",
      sourceKindLabel: "代理主题",
    });
    expect(reviewItems[0].failedGateLabel).toContain("簇强度不足");
    expect(reviewItems[0].failedGateLabel).toContain("门槛待确认");
    expect(reviewItems[0].summary).toContain("2");
    expect(reviewItems[0].reason).toContain("强势样本未过门槛，保留观察");
    expect(`${reviewItems[0].reason} ${reviewItems[0].failedGateLabel}`).not.toContain("buy");
    expect(`${reviewItems[0].reason} ${reviewItems[0].failedGateLabel}`).not.toContain("Observation-only");
    expect(`${reviewItems[0].reason} ${reviewItems[0].failedGateLabel}`).not.toContain("failed gates");
    expect(`${reviewItems[0].reason} ${reviewItems[0].failedGateLabel}`).not.toContain("insufficient_cluster_strength");
    expect(`${reviewItems[0].reason} ${reviewItems[0].failedGateLabel}`).not.toContain("liquidity_pressure_too_high");
  });

  it("builds a closed-loop summary for complete pass states", () => {
    const summary = buildClosedLoopSummary(
      strategyPayload,
      {
        ...confluencePayload,
        adversarial_context: {
          status: "complete",
          mode: "anti_crowding_v1",
          risk_gate: "pass",
          position_scale: 0.75,
        },
        closed_loop_state: {
          entry_gate: "open",
          exit_gate: "watch",
          replay_status: "available",
          lineage_status: "complete",
        },
        replay_evidence: {
          status: "available",
          snapshot_as_of_date: "2026-04-29",
          row_count: 2,
          matched_entry_count: 1,
          sample_items: [
            {
              stock_code: "000001.SZ",
              stock_name: "Alpha",
              candidate_rank: 1,
              signal_kind: "stock_candidate",
              data_status: "complete",
            },
          ],
        },
      },
      {
        quality_flag: "ok",
        vendor_status: "ok",
        source_version: "sv_livermore_test",
        rule_version: "rv_livermore_market_gate_v1",
      },
    );

    expect(summary.boundaryCount).toBe(0);
    expect(summary.summaryLabel).toBe("全部通过");
    expect(summary.referenceRating).toMatchObject({
      code: "reviewable",
      label: "可复核",
      tone: "positive",
    });
    expect(summary.verdict).toMatchObject({
      code: "reviewable",
      label: "可复核",
      headline: "可进入人工复核队列",
      tone: "positive",
    });
    expect(summary.verdict.nextStep).toContain("不推导策略收益");
    expect(summary.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "entry_gate",
          label: "入场观察门",
          status: "open",
          tone: "positive",
        }),
        expect.objectContaining({
          key: "adversarial_gate",
          label: "反拥挤拦截",
          status: "pass",
          tone: "positive",
        }),
        expect.objectContaining({
          key: "risk_exit",
          label: "风险退出",
          status: "watch",
          tone: "positive",
        }),
        expect.objectContaining({
          key: "replay",
          label: "回放证据",
          status: "available",
          tone: "positive",
          detail: "候选历史回放已接通：2 条快照 / 覆盖 1 个当前候选",
        }),
        expect.objectContaining({
          key: "lineage",
          label: "血缘状态",
          status: "complete",
          tone: "positive",
        }),
      ]),
    );
  });

  it("keeps unknown vendor closed-loop statuses out of status labels", () => {
    const summary = buildClosedLoopSummary(
      strategyPayload,
      {
        ...confluencePayload,
        adversarial_context: {
          status: "external_vendor_adversarial_status",
          mode: "external_vendor_mode",
          risk_gate: "external_vendor_risk_gate",
          position_scale: null,
          strongest_block_reason: "vendor_quality_signal_pending",
        },
        closed_loop_state: {
          entry_gate: "external_vendor_entry_gate",
          exit_gate: "external_vendor_exit_gate",
          replay_status: "external_vendor_replay_state",
          lineage_status: "external_vendor_lineage_state",
        },
      },
      {
        quality_flag: "warning",
        vendor_status: "vendor_unavailable",
        fallback_mode: "latest_snapshot",
      },
    );

    const copy = [
      summary.summaryLabel,
      summary.referenceRating.label,
      summary.verdict.headline,
      summary.verdict.primaryReason,
      summary.verdict.nextStep,
      ...summary.items.flatMap((item) => [item.label, item.statusLabel, item.detail]),
    ].join(" ");

    expect(summary.items.map((item) => item.statusLabel)).toEqual(
      expect.arrayContaining(["状态待确认", "待确认"]),
    );
    expect(summary.items.find((item) => item.key === "adversarial_gate")?.detail).toBe("风险待确认");
    expect(copy).not.toContain("external_vendor_entry_gate");
    expect(copy).not.toContain("external_vendor_exit_gate");
    expect(copy).not.toContain("external_vendor_replay_state");
    expect(copy).not.toContain("external_vendor_lineage_state");
    expect(copy).not.toContain("external_vendor_adversarial_status");
    expect(copy).not.toContain("external_vendor_mode");
    expect(copy).not.toContain("external_vendor_risk_gate");
    expect(copy).not.toContain("vendor_quality_signal_pending");
  });

  it("keeps unknown vendor adversarial fallback details out of closed-loop copy", () => {
    const summary = buildClosedLoopSummary(
      strategyPayload,
      {
        ...confluencePayload,
        adversarial_context: {
          status: "external_vendor_adversarial_status",
          mode: "external_vendor_mode",
          risk_gate: "external_vendor_risk_gate",
          position_scale: null,
          strongest_block_reason: null,
        },
        closed_loop_state: {
          entry_gate: "open",
          exit_gate: "watch",
          replay_status: "available",
          lineage_status: "complete",
        },
      },
      {
        quality_flag: "ok",
        vendor_status: "ok",
      },
    );

    const adversarialGate = summary.items.find((item) => item.key === "adversarial_gate");
    const copy = [
      summary.verdict.primaryReason,
      ...summary.verdict.evidence,
      adversarialGate?.statusLabel,
      adversarialGate?.detail,
    ].join(" ");

    expect(adversarialGate).toMatchObject({
      statusLabel: "状态待确认",
      detail: "反拥挤状态待确认",
    });
    expect(copy).not.toContain("external_vendor_mode");
    expect(copy).not.toContain("external_vendor_adversarial_status");
    expect(copy).not.toContain("external_vendor_risk_gate");
  });

  it("builds a closed-loop summary that surfaces block states as blockers", () => {
    const summary = buildClosedLoopSummary(
      {
        ...strategyPayload,
        risk_exit: {
          ...strategyPayload.risk_exit!,
          items: [],
        },
      },
      {
        ...confluencePayload,
        exit_observations: [
          {
            stock_code: "000777.SZ",
            stock_name: "Watch Alpha",
            action: "exit_triggered",
            current_price: 18.9,
            exit_watch_price: 20.1,
            triggered: true,
            evidence: ["退出观察价来自 Livermore EMA10。"],
          },
        ],
        adversarial_context: {
          status: "complete",
          mode: "anti_crowding_v1",
          risk_gate: "block",
          position_scale: null,
          strongest_block_reason: "crowded leaders without breadth confirmation",
        },
        closed_loop_state: {
          entry_gate: "blocked",
          exit_gate: "triggered",
          replay_status: "available",
          lineage_status: "degraded",
        },
      },
      {
        quality_flag: "warning",
        vendor_status: "ok",
        fallback_mode: "latest_snapshot",
      },
    );

    expect(summary.boundaryCount).toBeGreaterThanOrEqual(3);
    expect(summary.summaryLabel).toContain("待复核");
    expect(summary.referenceRating).toMatchObject({
      code: "blocked",
      label: "拦截",
      tone: "negative",
    });
    expect(summary.verdict).toMatchObject({
      code: "blocked",
      label: "拦截",
      headline: "闭环阻断，先复核约束项",
      tone: "negative",
    });
    expect(summary.verdict.primaryReason).toContain("强势样本拥挤");
    expect(summary.verdict.primaryReason).toContain("市场宽度未确认");
    expect(summary.verdict.nextStep).toContain("仅观察");
    expect(summary.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "entry_gate",
          label: "入场观察门",
          status: "blocked",
          tone: "negative",
        }),
        expect.objectContaining({
          key: "adversarial_gate",
          label: "反拥挤拦截",
          status: "block",
          tone: "negative",
          detail: expect.stringContaining("强势样本拥挤"),
        }),
        expect.objectContaining({
          key: "risk_exit",
          label: "风险退出",
          status: "triggered",
          tone: "negative",
        }),
        expect.objectContaining({
          key: "lineage",
          label: "血缘状态",
          status: "degraded",
          tone: "warning",
        }),
      ]),
    );
    const riskExit = summary.items.find((item) => item.key === "risk_exit");
    expect(riskExit?.detail).toContain("1 条触发");
    expect(riskExit?.detail).not.toContain("0 条触发");
  });

  it("builds a closed-loop summary that treats missing adversarial evidence as boundary data", () => {
    const summary = buildClosedLoopSummary(strategyPayload, confluencePayload, {
      quality_flag: "warning",
      vendor_status: "vendor_unavailable",
      fallback_mode: "latest_snapshot",
      source_version: "sv_livermore_test",
      rule_version: "rv_livermore_market_gate_v1",
    });

    expect(summary.boundaryCount).toBeGreaterThanOrEqual(3);
    expect(summary.summaryLabel).toContain("待复核");
    expect(summary.referenceRating).toMatchObject({
      code: "insufficient_data",
      label: "数据不足",
      tone: "warning",
    });
    expect(summary.verdict).toMatchObject({
      code: "insufficient_data",
      label: "数据不足",
      headline: "证据不足，不形成有效观察结论",
      tone: "warning",
    });
    expect(summary.verdict.nextStep).toContain("补齐");
    expect(summary.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "entry_gate",
          label: "入场观察门",
          status: "missing",
          tone: "warning",
          detail: expect.stringContaining("闭环入场状态未接通"),
        }),
        expect.objectContaining({
          key: "adversarial_gate",
          label: "反拥挤拦截",
          status: "missing",
          tone: "warning",
          detail: expect.stringContaining("不能视为中性证明"),
        }),
        expect.objectContaining({
          key: "replay",
          label: "回放证据",
          status: "missing",
          tone: "warning",
        }),
        expect.objectContaining({
          key: "lineage",
          label: "血缘状态",
          status: "missing",
          tone: "warning",
        }),
      ]),
    );
  });

  it("builds a pause rating when evidence is present but degraded", () => {
    const summary = buildClosedLoopSummary(
      strategyPayload,
      {
        ...confluencePayload,
        adversarial_context: {
          status: "degraded",
          mode: "crowding_latest",
          risk_gate: "degraded",
          position_scale: 0,
        },
        closed_loop_state: {
          entry_gate: "open",
          exit_gate: "watch",
          replay_status: "available",
          lineage_status: "degraded",
        },
      },
      {
        quality_flag: "warning",
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
      },
    );

    expect(summary.referenceRating).toMatchObject({
      code: "pause",
      label: "暂缓",
      tone: "warning",
    });
    expect(summary.referenceRating.detail).toContain("降级");
    expect(summary.verdict).toMatchObject({
      code: "pause",
      label: "暂缓",
      headline: "暂缓复核，存在降级边界",
      tone: "warning",
    });
    expect(summary.verdict.nextStep).toContain("回退");
  });

  it("represents partial replay windows with unsupported, pending, proxy-only, and zero-signal dates", () => {
    const summary = buildClosedLoopSummary(
      strategyPayload,
      {
        ...confluencePayload,
        adversarial_context: {
          status: "complete",
          mode: "anti_crowding_v1",
          risk_gate: "pass",
          position_scale: 0.5,
        },
        closed_loop_state: {
          entry_gate: "open",
          exit_gate: "watch",
          replay_status: buildReplayStatus({
            window_status: "partial",
            completed_dates: 1,
            pending_dates: 1,
            unsupported_dates: 1,
            proxy_only_dates: 1,
            completed_candidate_rows: 0,
            pending_candidate_rows: 17,
            unsupported_candidate_rows: 0,
            proxy_only_candidate_rows: 2,
            included_completed_stats_dates: ["2026-05-06"],
            blocked_dates: [
              {
                trade_date: "2026-04-30",
                status: "unsupported",
                reason_code: "missing_daily_limit_flags",
                signal_kinds: ["stock_candidate", "theme_breakout"],
              },
              {
                trade_date: "2026-05-08",
                status: "pending",
                reason_code: "forward_returns_pending",
                signal_kinds: ["stock_candidate", "theme_breakout"],
              },
              {
                trade_date: "2026-05-07",
                status: "proxy_only",
                reason_code: "proxy_theme_only",
                signal_kinds: ["theme_breakout"],
              },
            ],
            completed_zero_signal_dates: ["2026-05-06"],
          }),
          lineage_status: "complete",
        },
      },
      {
        quality_flag: "ok",
        vendor_status: "ok",
      },
    );

    const replayItem = summary.items.find((item) => item.key === "replay");
    expect(summary.referenceRating).toMatchObject({
      code: "pause",
      tone: "warning",
    });
    expect(replayItem).toMatchObject({
      status: "partial",
      tone: "warning",
    });
    expect(replayItem?.detail).toContain("剔除日期：2026-04-30、2026-05-08、2026-05-07");
    expect(replayItem?.detail).toContain("2026-04-30 涨跌停标记缺失");
    expect(replayItem?.detail).toContain("2026-05-08 远期收益待成熟");
    expect(replayItem?.detail).toContain("2026-05-07 仅代理题材");
    expect(replayItem?.detail).toContain("完成但无信号日期：2026-05-06");
    expect(replayItem?.detail).toContain("不推导策略有效性");
    expect(replayItem?.badges).toEqual(
      expect.arrayContaining([
        "完成 1日",
        "待成熟 1日",
        "不可用 1日",
        "代理观察 1日",
        "完成样本 0",
      ]),
    );
  });

  it("treats replay windows with no completed stats as insufficient data", () => {
    const summary = buildClosedLoopSummary(
      strategyPayload,
      {
        ...confluencePayload,
        adversarial_context: {
          status: "complete",
          mode: "anti_crowding_v1",
          risk_gate: "pass",
          position_scale: 0.5,
        },
        closed_loop_state: {
          entry_gate: "open",
          exit_gate: "watch",
          replay_status: buildReplayStatus({
            window_status: "unsupported",
            has_decision_usable_completed_stats: false,
            completed_dates: 0,
            pending_dates: 1,
            unsupported_dates: 1,
            proxy_only_dates: 0,
            completed_candidate_rows: 0,
            pending_candidate_rows: 17,
            unsupported_candidate_rows: 0,
            proxy_only_candidate_rows: 0,
            included_completed_stats_dates: [],
            blocked_dates: [
              {
                trade_date: "2026-04-30",
                status: "unsupported",
                reason_code: "missing_daily_limit_flags",
                signal_kinds: ["stock_candidate", "theme_breakout"],
              },
              {
                trade_date: "2026-05-09",
                status: "unsupported",
                reason_code:
                  "source_table_choice_stock_intraday_movement_event_missing" as ConfluenceReplayStatus["blocked_dates"][number]["reason_code"],
                signal_kinds: ["stock_candidate"],
              },
              {
                trade_date: "2026-05-08",
                status: "pending",
                reason_code: "forward_returns_pending",
                signal_kinds: ["stock_candidate", "theme_breakout"],
              },
              {
                trade_date: "2026-05-10",
                status: "unsupported",
                reason_code: "external_vendor_replay_paused" as ConfluenceReplayStatus["blocked_dates"][number]["reason_code"],
                signal_kinds: ["theme_breakout"],
              },
            ],
            completed_zero_signal_dates: [],
          }),
          lineage_status: "complete",
        },
      },
      {
        quality_flag: "ok",
        vendor_status: "ok",
      },
    );

    const replayItem = summary.items.find((item) => item.key === "replay");
    expect(summary.referenceRating).toMatchObject({
      code: "insufficient_data",
      tone: "warning",
    });
    expect(replayItem).toMatchObject({
      status: "unsupported",
      tone: "warning",
    });
    expect(replayItem?.detail).toContain("暂无可用于判断的完成回放日");
    expect(replayItem?.detail).toContain("2026-04-30 涨跌停标记缺失");
    expect(replayItem?.detail).toContain("2026-05-09 数据源缺失");
    expect(replayItem?.detail).toContain("2026-05-08 远期收益待成熟");
    expect(replayItem?.detail).toContain("2026-05-10 原因待确认");
    expect(replayItem?.detail).not.toContain("missing required source table");
    expect(replayItem?.detail).not.toContain("source table");
    expect(replayItem?.detail).not.toContain("source_table_choice_stock_intraday_movement_event_missing");
    expect(replayItem?.detail).not.toContain("external_vendor_replay_paused");
    expect(replayItem?.detail).not.toContain("external vendor replay paused");
  });

  it("combines risk exits and confluence exit observations without trading labels", () => {
    const rows = buildRiskExitRows(strategyPayload, confluencePayload);

    expect(rows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          stockCode: "000001.SZ",
          status: "triggered",
          exitWatchPrice: "10.20",
        }),
        expect.objectContaining({
          stockCode: "000777.SZ",
          status: "watch",
          exitWatchPrice: "20.10",
        }),
      ]),
    );
    expect(rows.map((row) => row.reason).join(" ")).not.toContain("卖出");
    const triggered = rows.find((r) => r.stockCode === "000001.SZ");
    expect(triggered?.reason).toContain("连续 2 日收盘低于 10 日均线");
    expect(triggered?.reason).not.toContain("2d_below_ema10");
    const watch = rows.find((r) => r.stockCode === "000777.SZ");
    expect(watch?.distanceToExitPct).toContain("%");
    expect(watch?.exitDistanceBucket === "triggered" || watch?.exitDistanceBucket === "0-3%").toBe(true);
  });

  it("derives entryCostAvailable from the backend flag, defaulting from entry_cost when absent", () => {
    const rows = buildRiskExitRows(strategyPayload, confluencePayload);
    const triggered = rows.find((r) => r.stockCode === "000001.SZ");
    const watch = rows.find((r) => r.stockCode === "000777.SZ");
    // Legacy payload rows have entry_cost set and no explicit entry_cost_available flag.
    expect(triggered?.entryCostAvailable).toBe(true);
    expect(watch?.entryCostAvailable).toBe(true);

    const rowsWithMissingCost = buildRiskExitRows(
      {
        ...strategyPayload,
        risk_exit: {
          ...strategyPayload.risk_exit!,
          items: [
            {
              ...strategyPayload.risk_exit!.items[0],
              entry_cost: null,
              entry_cost_available: false,
            },
          ],
          watch_items: [
            {
              ...strategyPayload.risk_exit!.watch_items![0],
              entry_cost: null,
              entry_cost_available: false,
            },
          ],
        },
      },
      null,
    );
    expect(rowsWithMissingCost.find((r) => r.stockCode === "000001.SZ")?.entryCostAvailable).toBe(false);
    expect(rowsWithMissingCost.find((r) => r.stockCode === "000777.SZ")?.entryCostAvailable).toBe(false);
  });

  it("localizes confluence risk exit evidence before exposing row reasons", () => {
    const rows = buildRiskExitRows(strategyPayload, {
      ...confluencePayload,
      exit_observations: [
        {
          stock_code: "000888.SZ",
          stock_name: "Stale Position",
          action: "observe_exit_watch",
          current_price: 18.6,
          exit_watch_price: 18.4,
          triggered: false,
          evidence: ["Risk-exit evidence missing because position snapshot is stale."],
        },
      ],
    });

    const watch = rows.find((row) => row.stockCode === "000888.SZ");
    expect(watch?.reason).toBe("持仓快照已陈旧，风险退出证据待补。");
    expect(watch?.reason).not.toContain("Risk-exit evidence");
    expect(watch?.reason).not.toContain("position snapshot");
  });

  it("keeps unknown vendor confluence risk exit evidence out of row reasons", () => {
    const rows = buildRiskExitRows(strategyPayload, {
      ...confluencePayload,
      exit_observations: [
        {
          stock_code: "000999.SZ",
          stock_name: "Vendor Exit",
          action: "observe_exit_watch",
          current_price: 18.6,
          exit_watch_price: 18.4,
          triggered: false,
          evidence: ["external_vendor_exit_signal_ready"],
        },
      ],
    });

    const watch = rows.find((row) => row.stockCode === "000999.SZ");
    expect(watch?.reason).toBe("风险退出证据待确认");
    expect(watch?.reason).not.toContain("external_vendor_exit_signal_ready");
    expect(watch?.reason).not.toContain("external vendor exit signal ready");
  });

  it("surfaces data boundary notes and missing evidence", () => {
    const notes = buildDataBoundaryNotes(strategyPayload);
    const blockedNotes = buildDataBoundaryNotes({
      ...strategyPayload,
      supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
      unsupported_outputs: [
        {
          key: "risk_exit",
          reason: "livermore_position_snapshot has no ACTIVE A-share rows.",
        },
      ],
    });

    expect(notes.join(" ")).toContain("口径：分析口径（非交易）");
    expect(notes.join(" ")).toContain("策略：Livermore A-Share Defended Trend");
    expect(notes.join(" ")).toContain("数据日期：2026-04-29");
    expect(notes.join(" ")).toContain("板块强弱公式：rv_livermore_sector_strength_observation_v1");
    expect(notes.join(" ")).toContain("板块强弱规则状态：规则已签核 / rv_livermore_sector_strength_observation_v1");
    expect(notes.join(" ")).toContain(
      "板块强弱说明：板块强弱观察排名已按 50% 涨跌幅分位、30% 换手率分位、20% 振幅分位签核；用于复核优先级与行业过滤，不构成交易指令；多日动量、板块资金流与拥挤度不包含在当前版本内。",
    );
    expect(notes.join(" ")).toContain("可用输出：市场门控、板块强弱、趋势候选、上升趋势、新趋势观察、风险退出");
    expect(notes.join(" ")).toContain("预警 市场宽度诊断：市场宽度输入不可用。");
    expect(notes.join(" ")).toContain("市场宽度 缺数据：5日市场宽度输入未落地。");
    expect(notes.join(" ")).not.toContain("LIVERMORE_BREADTH_MISSING");
    expect(notes.join(" ")).toContain("rv_livermore_sector_strength_observation_v1");
    expect(notes.join(" ")).not.toContain("basis:");
    expect(notes.join(" ")).not.toContain("as_of_date:");
    expect(notes.join(" ")).not.toContain("sector_rank formula");
    expect(notes.join(" ")).not.toContain("stock_candidates formula");
    expect(notes.join(" ")).not.toContain("risk_exit formula");
    expect(notes.join(" ")).not.toContain("supported_outputs:");
    expect(notes.join(" ")).not.toContain("Breadth inputs are unavailable.");
    expect(notes.join(" ")).not.toContain("breadth missing");
    expect(blockedNotes.join(" ")).toContain("风险退出 阻断：持仓快照缺失，暂无可执行风险退出样本。");
    expect(blockedNotes.join(" ")).not.toContain("risk_exit unsupported");
    expect(blockedNotes.join(" ")).not.toContain("livermore_position_snapshot");
  });

  it("builds a four-strategy ledger with available and blocked strategy states", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      supported_outputs: ["market_gate", "factor_screen_candidates", "hybrid_fusion"],
      unsupported_outputs: [
        {
          key: "stock_candidates",
          reason: "choice stock materialized input coverage is incomplete for 2026-05-29; request items: price, turn",
        },
        {
          key: "mean_reversion_candidates",
          reason: "choice stock materialized input coverage is incomplete for 2026-05-29; request items: drawdown",
        },
      ],
      stock_candidates: undefined,
      factor_screen_candidates: {
        as_of_date: "2026-05-29",
        factor_snapshot_as_of_date: "2026-05-29",
        formula_version: "rv_factor_screen_candidates_v2",
        market_state: "WARM",
        observation_only: true,
        input_stock_count: 1510,
        candidate_count: 1,
        coverage_note: "factor_snapshot available",
        items: [
          {
            rank: 1,
            stock_code: "000001.SZ",
            stock_name: "Alpha",
            sector_code: "801001",
            sector_name: "AI",
            industry: "AI",
            score: 0.973,
            pe: 12.4,
            pb: 1.8,
            roe: 0.18,
            gross_margin: 0.32,
            three_month_return: 0.11,
            twelve_month_return: 0.24,
            dividend_yield: 0.02,
          },
        ],
      },
      hybrid_fusion_candidates: {
        as_of_date: "2026-05-29",
        formula_version: "rv_hybrid_fusion_candidates_v4",
        market_state: "WARM",
        observation_only: true,
        candidate_count: 1,
        coverage_note: "Fusion observation-only candidate",
        items: [
          {
            rank: 1,
            stock_code: "000001.SZ",
            stock_name: "Alpha",
            sector_code: "801001",
            sector_name: "AI",
            fusion_score: 0.91,
            cycle_score: 0.8,
            lifecourt_proxy_score: 0.7,
            attention_score: 0.6,
            price_confirm_score: 0.5,
            crowding_penalty: 0.1,
            confidence: "medium",
            reason: "research observation",
            evidence: {},
          },
        ],
      },
      mean_reversion_candidates: undefined,
    };

    const items = buildStrategyLensItems(payload, buildConsensusSummary(payload));

    expect(items.map((item) => item.label)).toEqual(["融合策略", "趋势突破", "新趋势观察", "多因子", "超跌反弹"]);
    expect(items.find((item) => item.key === "hybrid")?.state).toBe("ready");
    expect(items.find((item) => item.key === "hybrid")?.candidates[0]?.metricLabel).toBe("融合分 0.910");
    expect(items.find((item) => item.key === "factor")?.value).toBe("1");
    expect(items.find((item) => item.key === "livermore")?.state).toBe("blocked");
    expect(items.find((item) => item.key === "livermore")?.statusDetail).toContain("物化输入覆盖不完整");
    expect(items.find((item) => item.key === "mean_reversion")?.state).toBe("blocked");
  });

  it("shows known market-state strategy pauses without counting them as blocked", () => {
    const policyPauseUnsupportedOutputs: LivermoreStrategyPayload["unsupported_outputs"] = [
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
        key: "hybrid_fusion",
        reason:
          "Hybrid fusion is observation-only and only emits candidates in WARM/HOT market states; current state is OVERHEAT.",
      },
    ];
    const policyPauseReason = (key: string) =>
      policyPauseUnsupportedOutputs.find((output) => output.key === key)?.reason ?? "";
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      market_gate: {
        ...strategyPayload.market_gate,
        state: "OVERHEAT",
      },
      supported_outputs: ["market_gate", "sector_rank", "factor_screen_candidates", "risk_exit"],
      unsupported_outputs: policyPauseUnsupportedOutputs,
      module_states: readyModuleStates().map((item) =>
        ["stock_candidates", "mean_reversion_candidates", "hybrid_fusion"].includes(item.key)
          ? {
              ...item,
              state: "unsupported",
              render_mode: "evidence_only",
              excludes_from_primary: true,
              reasons: [policyPauseReason(item.key)],
            }
          : item,
      ),
      stock_candidates: undefined,
      mean_reversion_candidates: undefined,
      hybrid_fusion_candidates: {
        as_of_date: "2026-06-18",
        formula_version: "rv_hybrid_fusion_candidates_v4",
        market_state: "OVERHEAT",
        observation_only: true,
        candidate_count: 0,
        coverage_note:
          "Hybrid fusion is observation-only and only emits candidates in WARM/HOT market states; current state is OVERHEAT.",
        items: [],
      },
    };

    const items = buildStrategyLensItems(payload, buildConsensusSummary(payload));

    expect(items.find((item) => item.key === "livermore")).toMatchObject({
      state: "paused",
      tone: "neutral",
      statusLabel: "策略暂停",
    });
    expect(items.find((item) => item.key === "mean_reversion")?.state).toBe("paused");
    expect(items.find((item) => item.key === "hybrid")?.state).toBe("paused");
    expect(items.filter((item) => item.state === "blocked")).toHaveLength(0);
  });

  it("keeps evidence-only hybrid candidates out of the primary review queue", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      supported_outputs: ["market_gate", "factor_screen_candidates", "hybrid_fusion"],
      unsupported_outputs: [],
      stock_candidates: undefined,
      mean_reversion_candidates: undefined,
      factor_screen_candidates: {
        as_of_date: "2026-05-29",
        factor_snapshot_as_of_date: "2026-05-29",
        formula_version: "rv_factor_screen_candidates_v2",
        market_state: "WARM",
        observation_only: true,
        input_stock_count: 1510,
        candidate_count: 1,
        coverage_note: "factor-only stale snapshot",
        items: [
          {
            rank: 1,
            stock_code: "000001.SZ",
            stock_name: "Alpha",
            sector_code: "801001",
            sector_name: "AI",
            industry: "AI",
            score: 0.973,
            pe: null,
            pb: null,
            roe: null,
            gross_margin: null,
            three_month_return: null,
            twelve_month_return: null,
            dividend_yield: null,
          },
        ],
      },
      hybrid_fusion_candidates: {
        as_of_date: "2026-06-12",
        formula_version: "rv_hybrid_fusion_candidates_v4",
        market_state: "WARM",
        observation_only: true,
        candidate_count: 1,
        coverage_note: "factor-only hybrid",
        items: [
          {
            rank: 1,
            stock_code: "000001.SZ",
            stock_name: "Alpha",
            sector_code: "801001",
            sector_name: "AI",
            fusion_score: 0.91,
            cycle_score: 0,
            lifecourt_proxy_score: 0,
            attention_score: 0,
            price_confirm_score: 0,
            crowding_penalty: 0,
            confidence: "low",
            reason: "factor-only",
            evidence: { source_kinds: ["factor_screen"] },
          },
        ],
      },
      module_states: [
        {
          key: "factor_screen_candidates",
          state: "degraded",
          render_mode: "evidence_only",
          source_date: "2026-05-29",
          lag_days: 10,
          threshold_days: 3,
          reasons: ["factor snapshot is stale"],
          evidence_scope: "detail",
          excludes_from_primary: true,
        },
        {
          key: "hybrid_fusion",
          state: "degraded",
          render_mode: "evidence_only",
          source_date: "2026-05-29",
          lag_days: 10,
          threshold_days: 3,
          reasons: ["hybrid fusion is factor-only"],
          evidence_scope: "detail",
          excludes_from_primary: true,
        },
      ],
    };

    const queue = buildCandidateReviewQueue(payload);
    const kpi = buildStockAnalysisKpiStrip(payload, null);
    const items = buildStrategyLensItems(payload, buildConsensusSummary(payload));
    const empty = buildReviewQueueEmptyState(payload);
    const summary = buildDecisionSummary(payload, { quality_flag: "ok", vendor_status: "ok" });

    expect(queue).toHaveLength(0);
    expect(kpi.find((item) => item.key === "review-queue")).toMatchObject({
      value: "0",
      tone: "neutral",
    });
    expect(items.find((item) => item.key === "hybrid")?.state).not.toBe("ready");
    expect(items.find((item) => item.key === "factor")?.state).not.toBe("ready");
    expect(empty.detail).not.toContain("多因子池 1 只");
    expect(empty.detail).not.toContain("融合策略池 1 只");
    expect(empty.detail).toContain("深度分析");
    expect(summary.nextReviewAction).not.toContain("Alpha");
    expect(summary.nextReviewAction).toContain("深度分析");
    expect(summary.nextReviewAction).not.toContain("买入");
  });

  it("shows evidence-only module state even when a returned module has zero candidates", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      factor_screen_candidates: {
        as_of_date: "2026-05-29",
        factor_snapshot_as_of_date: "2026-05-29",
        formula_version: "rv_factor_screen_candidates_v2",
        market_state: "WARM",
        observation_only: true,
        input_stock_count: 1510,
        candidate_count: 0,
        coverage_note: "factor snapshot is stale",
        items: [],
      },
      module_states: [
        {
          key: "factor_screen_candidates",
          state: "partial",
          render_mode: "evidence_only",
          source_date: "2026-05-29",
          lag_days: 10,
          threshold_days: 3,
          reasons: ["factor snapshot is stale"],
          evidence_scope: "detail",
          excludes_from_primary: true,
        },
      ],
    };

    const factor = buildStrategyLensItems(payload, buildConsensusSummary(payload)).find((item) => item.key === "factor");

    expect(factor).toMatchObject({
      state: "paused",
      tone: "warning",
    });
    expect(factor?.statusLabel).not.toBe("0 候选");
  });

  it("fails closed when module states are missing or empty", () => {
    const legacyPayload = {
      ...strategyPayload,
      module_states: undefined,
    } as unknown as LivermoreStrategyPayload;
    const emptyModuleStatePayload: LivermoreStrategyPayload = {
      ...strategyPayload,
      supported_outputs: ["market_gate", "sector_rank", "hybrid_fusion"],
      stock_candidates: undefined,
      hybrid_fusion_candidates: {
        as_of_date: "2026-06-12",
        formula_version: "rv_hybrid_fusion_candidates_v4",
        market_state: "HOT",
        observation_only: true,
        candidate_count: 1,
        coverage_note: "Fusion observation-only candidate",
        items: [
          {
            rank: 1,
            stock_code: "000002.SZ",
            stock_name: "Beta",
            sector_code: "801002",
            sector_name: "新能源车",
            fusion_score: 0.38,
            cycle_score: 0.22,
            lifecourt_proxy_score: 0.11,
            attention_score: 0.04,
            price_confirm_score: 0.02,
            crowding_penalty: 0.01,
            fusion_action: "monitor_only",
            confidence: "low",
            reason: "research observation",
            evidence: { source_kinds: ["factor_screen"] },
          },
        ],
      },
      module_states: [],
    };

    const queue = buildCandidateReviewQueue(legacyPayload);
    const summary = buildDecisionSummary(legacyPayload, { quality_flag: "ok", vendor_status: "ok" });
    const consensus = buildConsensusSummary(legacyPayload);
    const hybridQueue = buildCandidateReviewQueue(emptyModuleStatePayload);

    expect(queue).toHaveLength(0);
    expect(summary.candidateCountLabel).toBe("候选 0");
    expect(summary.nextReviewAction).not.toContain("Alpha");
    expect(consensus.strategyCounts.livermore).toBe(0);
    expect(consensus.hasAnyStrategy).toBe(false);
    expect(hybridQueue).toHaveLength(0);
  });

  it("builds strategy ledger audit fields for blockers and review focus", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      stock_candidates: undefined,
      factor_screen_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_factor_screen_candidates_v1",
        market_state: "WARM",
        input_stock_count: 643,
        candidate_count: 1,
        coverage_note: "因子数据覆盖 643/5201 只",
        items: [
          {
            rank: 1,
            stock_code: "600000.SH",
            stock_name: "Factor Alpha",
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
          },
        ],
      },
      unsupported_outputs: [
        {
          key: "stock_candidates",
          reason: "choice_stock_candidate_history materialized input coverage incomplete",
        },
      ],
    };

    const items = buildStrategyLensItems(payload, buildConsensusSummary(payload));
    const trend = items.find((item) => item.key === "livermore");
    const factor = items.find((item) => item.key === "factor");

    expect(trend).toMatchObject({
      blockerLabel: expect.stringContaining("物化输入覆盖不完整"),
      focusLabel: expect.stringContaining("补齐"),
      actionLabel: "查看复核队列",
    });
    expect(factor).toMatchObject({
      blockerLabel: "无阻断",
      focusLabel: expect.stringContaining("Factor Alpha"),
      actionLabel: "查看观察池",
    });
    expect(factor?.candidateCountLabel).toBe("1 只候选");
    expect(factor?.candidates).toHaveLength(1);
  });

  it("discloses fundamental_overlay.factor_missing_count in the livermore card evidence when present", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      stock_candidates: {
        ...strategyPayload.stock_candidates!,
        fundamental_overlay: {
          status: "applied",
          input_candidate_count: 3,
          valid_factor_count: 1,
          selected_factor_count: 1,
          top_fraction: 0.5,
          factor_missing_count: 2,
        },
      },
    };

    const trend = buildStrategyLensItems(payload, buildConsensusSummary(payload)).find(
      (item) => item.key === "livermore",
    );

    expect(trend?.evidence).toEqual(
      expect.arrayContaining([{ key: "factor_missing", label: "缺因子", value: "2 只" }]),
    );
  });

  it("omits the factor_missing evidence row for legacy payloads without fundamental_overlay", () => {
    const trend = buildStrategyLensItems(strategyPayload, buildConsensusSummary(strategyPayload)).find(
      (item) => item.key === "livermore",
    );

    expect(trend?.evidence.some((row) => row.key === "factor_missing")).toBe(false);
  });

  it("uses backend candidate_count for strategy ledger counts instead of preview length", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      factor_screen_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_factor_screen_candidates_v1",
        market_state: "WARM",
        input_stock_count: 643,
        candidate_count: 30,
        coverage_note: "因子数据覆盖 643/5201 只",
        items: [
          {
            rank: 1,
            stock_code: "600000.SH",
            stock_name: "Factor Alpha",
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
          },
        ],
      },
    };

    const factor = buildStrategyLensItems(payload, buildConsensusSummary(payload)).find(
      (item) => item.key === "factor",
    );

    expect(factor).toMatchObject({
      state: "ready",
      value: "30",
      candidateCountLabel: "30 只候选",
    });
    expect(factor?.candidates).toHaveLength(1);
  });

  it("keeps explicit backend blockers ahead of local mean-reversion gate pauses", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      market_gate: {
        ...strategyPayload.market_gate,
        state: "OFF",
      },
      mean_reversion_candidates: undefined,
      unsupported_outputs: [
        {
          key: "mean_reversion_candidates",
          reason: "choice_stock_candidate_history materialized input coverage incomplete",
        },
      ],
    };

    const meanReversion = buildStrategyLensItems(payload, buildConsensusSummary(payload)).find(
      (item) => item.key === "mean_reversion",
    );

    expect(meanReversion).toMatchObject({
      state: "blocked",
      statusLabel: "被阻断",
      blockerLabel: expect.stringContaining("物化输入覆盖不完整"),
    });
    expect(meanReversion?.statusDetail).toContain("物化输入覆盖不完整");
    expect(meanReversion?.statusDetail).toContain("门控暂停");
    expect(meanReversion?.detail).toContain("物化输入覆盖不完整");
    expect(meanReversion?.detail).toContain("门控暂停");
  });

  it("builds daily judgment strip with sector poles", () => {
    const strip = buildDailyJudgmentStrip(strategyPayload);
    expect(strip.headline).toContain("今日市场状态");
    expect(strip.gateChip).toContain("2/4");
    expect(strip.strongestSectorChip).toContain("AI");
    expect(strip.weakestSectorChip).toContain("新能源车");
  });

  it("orders sector view model by selected metric without changing payload", () => {
    const byScore = buildSectorViewModel(strategyPayload, "score");
    expect(byScore[0].sectorName).toBe("AI");
    const byPct = buildSectorViewModel(strategyPayload, "pctchange");
    expect(byPct[0].sectorName).toBe("AI");
    const byTurn = buildSectorViewModel(strategyPayload, "turnover");
    expect(byTurn[0].sectorName).toBe("新能源车");
  });

  it("maps sector rank series API rows into the existing sector display model", () => {
    const rows = buildSectorRowsFromSectorSeries([
      {
        trade_date: "2026-04-29",
        sector_code: "801002",
        sector_name: "新能源车",
        score: 0.52,
        rank: 2,
        avg_pctchange: -1.2,
        avg_turn: 5.6,
        avg_amplitude: 2,
        constituent_count: 24,
        cum_pctchange_window: -6,
      },
      {
        trade_date: "2026-04-29",
        sector_code: "801001",
        sector_name: "AI",
        score: 0.91,
        rank: 1,
        avg_pctchange: 0.42,
        avg_turn: 2.2,
        avg_amplitude: 1.1,
        constituent_count: 12,
        cum_pctchange_window: 2.1,
      },
    ]);

    expect(rows.map((row) => row.sectorName)).toEqual(["AI", "新能源车"]);
    expect(rows[0]).toMatchObject({
      rank: 1,
      sectorCode: "801001",
      score: "0.910",
      pctChange: "0.42%",
      constituentCount: 12,
      isTop: true,
    });
    expect(buildSectorViewRows(rows, "turnover")[0].sectorName).toBe("新能源车");
  });

  it("flags top and bottom sector rows for charting", () => {
    const rows = buildSectorRows(strategyPayload);
    const top = rows.find((r) => r.sectorCode === "801001");
    const bottom = rows.find((r) => r.sectorCode === "801002");
    expect(top?.isTop).toBe(true);
    expect(bottom?.isBottom).toBe(true);
    expect(typeof top?.scoreNormalized).toBe("number");
  });

  it("builds sector overview state for first-screen leader, tail, coverage, and bar groups", () => {
    const rows = Array.from({ length: 7 }, (_, index) => ({
      rank: index + 1,
      sectorCode: `BK${index + 1}`,
      sectorName: `Sector ${index + 1}`,
      score: `${90 - index}`,
      pctChange: `${index}%`,
      turnover: `${index + 1}%`,
      amplitude: `${index + 2}%`,
      constituentCount: index + 10,
      scoreValue: 90 - index,
      pctChangeValue: index,
      turnoverValue: index + 1,
      amplitudeValue: index + 2,
      scoreNormalized: 1 - index / 10,
      pctChangeBar: 1 - index / 12,
      isTop: index < 3,
      isBottom: index >= 4,
      metricBarNormalized: 1 - index / 14,
    }));

    const overview = buildStockSectorOverviewState(rows);

    expect(overview.leaderRow?.sectorCode).toBe("BK1");
    expect(overview.tailRow?.sectorCode).toBe("BK7");
    expect(overview.coverageCount).toBe(91);
    expect(overview.topBars.map((row) => row.sectorCode)).toEqual(["BK1", "BK2", "BK3", "BK4", "BK5"]);
    expect(overview.bottomBars.map((row) => row.sectorCode)).toEqual(["BK3", "BK4", "BK5", "BK6", "BK7"]);
    expect(buildStockSectorOverviewState([])).toEqual({
      leaderRow: null,
      tailRow: null,
      coverageCount: 0,
      topBars: [],
      bottomBars: [],
    });
  });

  it("builds a boundary summary from existing payload evidence only", () => {
    const summary = buildDataBoundarySummary(
      {
        ...strategyPayload,
        unsupported_outputs: [
          {
            key: "risk_exit",
            reason: "position snapshot not landed",
          },
        ],
      },
      {
        quality_flag: "warning",
        vendor_status: "ok",
        fallback_mode: "latest_snapshot",
      },
    );

    expect(summary.boundaryCount).toBe(3);
    expect(summary.diagnosticsCount).toBe(1);
    expect(summary.dataGapCount).toBe(1);
    expect(summary.unsupportedCount).toBe(1);
    expect(summary.freshnessLabel).toBe("新鲜度 质量需复核 / 供数正常 / 数据延迟");
    expect(summary.summaryLabel).toBe("3 条边界");
    expect(summary.detailLabel).toContain("诊断 1 / 缺口 1 / 阻断 1");
    expect(summary.topMessages.join(" ")).toContain("市场宽度输入不可用");
    expect(summary.topMessages.join(" ")).toContain("5日市场宽度输入未落地");
    expect(summary.topMessages.join(" ")).toContain("持仓快照未落地");
    expect(summary.topMessages.join(" ")).not.toContain("position snapshot");
  });

  it("keeps ready inputs and policy pauses out of actionable boundary counts", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      diagnostics: [
        {
          severity: "info",
          code: "LIVERMORE_STOCK_PIVOT_PAUSED_BY_POLICY",
          message: "Stock candidate policy exp3b is inactive in OVERHEAT; active market states are HOT/WARM.",
          input_family: "stock_candidate_policy",
        },
      ],
      data_gaps: [
        {
          input_family: "breadth",
          status: "ready",
          evidence: "5-day breadth 0.6000 landed.",
        },
      ],
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
          key: "uptrend_momentum_candidates",
          reason: "Uptrend momentum watchlist is paused unless the market gate is WARM or HOT.",
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
        {
          key: "risk_exit",
          reason: "position snapshot not landed",
        },
      ],
    };

    const summary = buildDataBoundarySummary(payload, { quality_flag: "ok", vendor_status: "ok" });
    expect(summary.boundaryCount).toBe(1);
    expect(summary.diagnosticsCount).toBe(0);
    expect(summary.dataGapCount).toBe(0);
    expect(summary.unsupportedCount).toBe(1);
    expect(summary.topMessages.join(" ")).toContain("持仓快照未落地");
    expect(summary.topMessages.join(" ")).not.toContain("趋势突破策略");

    const digest = buildWorkbenchDataDigest({ main: payload });
    expect(digest.primaryFacts.find((fact) => fact.id === "open-issues")).toMatchObject({
      value: "1 项",
      tone: "warning",
    });
  });

  it("keeps the live OVERHEAT fresh-trend closure synchronized", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      market_gate: {
        ...strategyPayload.market_gate,
        state: "OVERHEAT",
      },
      diagnostics: [
        {
          severity: "info",
          code: "LIVERMORE_STOCK_PIVOT_PAUSED_BY_POLICY",
          message: "Stock candidate policy exp3b is inactive in OVERHEAT; active market states are HOT/WARM.",
          input_family: "stock_candidate_policy",
        },
      ],
      data_gaps: [
        {
          input_family: "breadth",
          status: "ready",
          evidence: "5-day breadth 0.6000 landed.",
        },
      ],
      supported_outputs: ["market_gate", "sector_rank", "fresh_trend_watchlist", "factor_screen_candidates", "risk_exit"],
      unsupported_outputs: [
        {
          key: "stock_candidates",
          reason: "Stock candidate policy exp3b is inactive in OVERHEAT; active market states are HOT/WARM.",
        },
        {
          key: "uptrend_momentum_candidates",
          reason: "Uptrend momentum watchlist is paused unless the market gate is WARM or HOT.",
        },
        {
          key: "mean_reversion_candidates",
          reason: "Mean reversion watchlist is paused when the market gate is HOT or OVERHEAT.",
        },
        {
          key: "theme_breakout",
          reason: "Theme breakout execution is paused in OVERHEAT; historical replay showed this bucket is draggy.",
        },
        {
          key: "hybrid_fusion",
          reason: "Hybrid fusion is observation-only and only emits candidates in WARM/HOT market states; current state is OVERHEAT.",
        },
      ],
      stock_candidates: undefined,
      uptrend_momentum_candidates: undefined,
      fresh_trend_watchlist: {
        ...strategyPayload.fresh_trend_watchlist!,
        market_state: "OVERHEAT",
        candidate_count: 20,
      },
      factor_screen_candidates: {
        as_of_date: "2026-06-18",
        factor_snapshot_as_of_date: "2026-06-18",
        formula_version: "rv_factor_screen_candidates_v2",
        market_state: "OVERHEAT",
        observation_only: true,
        input_stock_count: 1542,
        candidate_count: 30,
        coverage_note: "factor snapshot landed",
        items: [],
      },
    };

    const summary = buildDataBoundarySummary(payload, { quality_flag: "ok", vendor_status: "ok" });
    expect(summary.boundaryCount).toBe(0);
    expect(summary.unsupportedCount).toBe(0);

    const notes = buildDataBoundaryNotes(payload).join(" ");
    expect(notes).toContain("可用输出：市场门控、板块强弱、新趋势观察、多因子、风险退出");
    expect(notes).toContain("上升趋势 阻断：上升趋势策略在过热门控下暂停");
    expect(notes).not.toContain("fresh_trend_watchlist");
    expect(notes).not.toContain("uptrend_momentum_candidates");

    const queue = buildCandidateReviewQueue(payload);
    expect(queue[0].headline).toContain("新趋势观察");
    expect(queue[0].primaryEvidence.map((item) => item.key)).toEqual([
      "return_20d",
      "return_60d",
      "return_120d",
    ]);
    expect(queue[0].boundaryEvidence.join(" ")).toContain("不构成趋势突破交易指令");

    const lensItems = buildStrategyLensItems(payload, buildConsensusSummary(payload));
    expect(lensItems.find((item) => item.key === "fresh_trend")).toMatchObject({
      label: "新趋势观察",
      state: "ready",
      value: "20",
    });
  });

  it("keeps unknown data gap statuses out of the boundary summary", () => {
    const summary = buildDataBoundarySummary(
      {
        ...strategyPayload,
        data_gaps: [
          {
            input_family: "breadth",
            status: "vendor_sync_delayed",
            evidence: "外部通道同步延迟。",
          },
        ],
      } as unknown as LivermoreStrategyPayload,
      { quality_flag: "ok", vendor_status: "ok" },
    );

    expect(summary.topMessages.join(" ")).toContain("市场宽度 状态待确认");
    expect(summary.topMessages.join(" ")).not.toContain("vendor_sync_delayed");
  });

  it("keeps unknown data families out of the boundary summary", () => {
    const summary = buildDataBoundarySummary(
      {
        ...strategyPayload,
        data_gaps: [
          {
            input_family: "external_vendor_factor_feed",
            status: "missing",
            evidence: "external_vendor_factor_feed 未落地。",
          },
        ],
      } as unknown as LivermoreStrategyPayload,
      { quality_flag: "ok", vendor_status: "ok" },
    );

    expect(summary.topMessages.join(" ")).toContain("输入待确认 缺数据：输入待确认 未落地");
    expect(summary.topMessages.join(" ")).not.toContain("external_vendor_factor_feed");
    expect(summary.topMessages.join(" ")).not.toContain("external vendor factor feed");
  });

  it("builds current sector filter status for review queue stitching", () => {
    const filtered = buildSectorFilterSummary(strategyPayload, "801001");
    const unfiltered = buildSectorFilterSummary(strategyPayload, null);

    expect(filtered.isFiltered).toBe(true);
    expect(filtered.sectorLabel).toBe("AI");
    expect(filtered.visibleCount).toBe(1);
    expect(filtered.totalCount).toBe(1);
    expect(filtered.summaryLabel).toBe("行业 AI (801001) / 显示 1 / 1 个候选");

    expect(unfiltered.isFiltered).toBe(false);
    expect(unfiltered.sectorLabel).toBe("全部行业");
    expect(unfiltered.summaryLabel).toBe("行业 全部 / 显示 1 / 1 个候选");
  });

  it("builds sector filter view state from review queue candidates", () => {
    const queue: StockCandidateReviewQueueItem[] = [
      {
        rank: 1,
        stockCode: "000001.SZ",
        stockName: "Alpha",
        sectorCode: "BK002",
        sectorName: "Banking",
        headline: "观察候选 #1 · Alpha",
        pattern: "突破",
        patternNote: "UI 辅助归类标签，不构成正式结论",
        distanceToBreakoutPct: "2.4%",
        reviewFocus: "Alpha · Banking · 距观察位 2.4%",
        primaryEvidence: [{ key: "a", label: "A", value: "1" }],
        supportingEvidence: [],
        boundaryEvidence: [],
        invalidationFocus: "失效条件待补",
        invalidationRules: [],
        rawFields: [],
      },
      {
        rank: 2,
        stockCode: "000002.SZ",
        stockName: "Beta",
        sectorCode: "BK001",
        sectorName: "Tech",
        headline: "观察候选 #2 · Beta",
        pattern: "突破",
        patternNote: "UI 辅助归类标签，不构成正式结论",
        distanceToBreakoutPct: "3.1%",
        reviewFocus: "Beta · Tech · 距观察位 3.1%",
        primaryEvidence: [],
        supportingEvidence: [],
        boundaryEvidence: [],
        invalidationFocus: "失效条件待补",
        invalidationRules: [],
        rawFields: [],
      },
    ];

    const filtered = buildReviewQueueSectorFilterView({
      reviewQueue: queue,
      sectorFilterSectorCode: "BK002",
      selectedSectorLabel: "Banking",
    });
    const empty = buildReviewQueueSectorFilterView({
      reviewQueue: queue,
      sectorFilterSectorCode: "BK003",
      selectedSectorLabel: null,
    });
    const unfiltered = buildReviewQueueSectorFilterView({
      reviewQueue: queue,
      sectorFilterSectorCode: null,
      selectedSectorLabel: null,
    });

    expect(filtered.sectorOptions).toEqual([
      ["BK001", "Tech"],
      ["BK002", "Banking"],
    ]);
    expect(filtered.filteredCandidates.map((item) => item.stockCode)).toEqual(["000001.SZ"]);
    expect(filtered.selectedSectorLeadCandidate?.stockName).toBe("Alpha");
    expect(filtered.sectorLinkTone).toBe("active");
    expect(filtered.sectorLinkSummary).toBe("Banking \u00b7 1 \u4e2a\u5019\u9009");
    expect(filtered.sectorLinkFocus).toBe("\u9996\u4f4d Alpha \u00b7 \u8ddd\u89c2\u5bdf 2.4%");

    expect(empty.filteredCandidates).toEqual([]);
    expect(empty.sectorLinkTone).toBe("empty");
    expect(empty.sectorLinkSummary).toBe("BK003 \u00b7 \u65e0\u5019\u9009");
    expect(empty.sectorLinkFocus).toBe("\u8be5\u884c\u4e1a\u6682\u65e0\u7ebf\u7d22");

    expect(unfiltered.filteredCandidates).toHaveLength(2);
    expect(unfiltered.sectorLinkTone).toBe("all");
    expect(unfiltered.sectorLinkSummary).toBe("\u5168\u90e8\u884c\u4e1a \u00b7 2 \u4e2a\u5019\u9009");
    expect(unfiltered.sectorLinkFocus).toBe("\u9996\u4f4d Alpha \u00b7 \u8ddd\u89c2\u5bdf 2.4%");
  });

  it("builds first-screen KPI strip from existing strategy evidence only", () => {
    const items = buildStockAnalysisKpiStrip(strategyPayload, confluencePayload, {
      quality_flag: "warning",
      vendor_status: "ok",
      fallback_mode: "latest_snapshot",
    });

    expect(items.map((item) => item.key)).toEqual([
      "market-state",
      "review-queue",
      "sector-strength",
      "risk-observation",
      "closed-loop",
      "data-boundary",
    ]);
    expect(items.find((item) => item.key === "market-state")).toMatchObject({
      label: "市场状态",
      value: "温和",
      detail: "观察暴露 40%",
      tone: "warning",
    });
    expect(items.find((item) => item.key === "review-queue")).toMatchObject({
      label: "复核队列",
      value: "1",
    });
    expect(items.find((item) => item.key === "risk-observation")?.detail).toContain("触发 1");
    expect(items.find((item) => item.key === "data-boundary")).toMatchObject({
      value: "2",
      tone: "warning",
    });
    expect(items.map((item) => `${item.label}${item.value}${item.detail}`).join(" ")).not.toContain("买入");
  });

  it("builds evidence status and event monitor rows with explicit pending boundaries", () => {
    const payload = {
      ...strategyPayload,
      data_gaps: [
        {
          input_family: "external_vendor_factor_feed",
          status: "vendor_sync_delayed",
          evidence: "外部因子通道同步延迟。",
        },
      ],
      unsupported_outputs: [
        {
          key: "theme_breakout",
          reason: "concept membership table pending",
        },
      ],
    } as unknown as LivermoreStrategyPayload;
    const evidence = buildStockAnalysisEvidenceStatus(payload, {
      quality_flag: "warning",
      vendor_status: "vendor_stale",
      source_version: "sv_livermore_test",
      rule_version: "rv_livermore_market_gate_v1",
      fallback_mode: "latest_snapshot",
    });
    const events = buildStockAnalysisEventMonitorRows(payload, {
      ...confluencePayload,
      diagnostics: [
        {
          severity: "warning",
          code: "pending_signal_confluence",
          message: "Signal confluence diagnostic pending detail.",
        },
      ],
    });

    expect(evidence.map((item) => item.key)).toEqual([
      "as-of-date",
      "lineage",
      "basis",
      "rule-version",
      "quality",
      "exceptions",
    ]);
    expect(evidence.find((item) => item.key === "quality")).toMatchObject({
      label: "数据质量",
      statusLabel: "需复核",
      tone: "warning",
    });
    expect(evidence.find((item) => item.key === "exceptions")?.detail).toContain("诊断 1 / 缺口 1 / 阻断 1");
    expect(events.find((event) => event.source === "data_gap")).toMatchObject({
      event: "状态待确认",
      impact: "输入待确认",
      detail: "外部因子通道同步延迟。",
    });
    expect(events).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          source: "diagnostic",
          level: "warning",
          impact: "breadth",
        }),
        expect.objectContaining({
          source: "unsupported",
          level: "warning",
          event: "题材观察阻断",
          impact: "theme_breakout",
          detail: "概念归属待确认。",
        }),
        expect.objectContaining({
          source: "signal_confluence",
          level: "warning",
          impact: "signal_confluence",
          detail: "联动诊断待确认。",
        }),
      ]),
    );
    expect(events.map((event) => event.event).join(" ")).not.toContain("theme_breakout");
    expect(events.map((event) => `${event.event} ${event.impact}`).join(" ")).not.toContain("vendor_sync_delayed");
    expect(events.map((event) => `${event.event} ${event.impact}`).join(" ")).not.toContain(
      "external_vendor_factor_feed",
    );
    expect(events.map((event) => event.detail).join(" ")).not.toContain("concept membership table pending");
    expect(events.map((event) => event.detail).join(" ")).not.toContain("Signal confluence diagnostic pending detail");
  });

  it("keeps repeated diagnostic codes as distinct event monitor rows", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      diagnostics: [
        {
          severity: "warning",
          code: "LIVERMORE_INPUT_FRESHNESS_DEGRADED",
          message: "Stock daily observations are stale.",
          input_family: "turnover_persistence",
        },
        {
          severity: "warning",
          code: "LIVERMORE_INPUT_FRESHNESS_DEGRADED",
          message: "Factor snapshots are stale.",
          input_family: "valuation_percentile_history",
        },
      ],
    };

    const diagnostics = buildStockAnalysisEventMonitorRows(payload, null).filter(
      (event) => event.source === "diagnostic",
    );

    expect(diagnostics).toHaveLength(2);
    expect(new Set(diagnostics.map((event) => event.key)).size).toBe(2);
  });

  it("localizes real theme breakout overheat blocker in event details", () => {
    const reason = "Theme breakout execution is paused in OVERHEAT; historical replay showed this bucket is draggy.";
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      unsupported_outputs: [
        {
          key: "theme_breakout",
          reason,
        },
      ],
    };

    const events = buildStockAnalysisEventMonitorRows(payload, confluencePayload);
    const themeBlocker = events.find((event) => event.key === "unsupported:theme_breakout");
    const summary = buildThemeBreakoutPanelSummary({
      payload,
      cards: buildThemeBreakoutCards(payload),
      reviewCount: 0,
      unsupportedReason: reason,
    });

    expect(themeBlocker?.detail).toContain("市场过热门控下暂停题材观察");
    expect(themeBlocker?.detail).toContain("历史回放显示该桶拖累");
    expect(summary.detail).toContain("市场过热门控下暂停题材执行观察");
    expect(`${themeBlocker?.detail} ${summary.detail}`).not.toContain("Theme breakout execution is paused");
  });

  it("builds consensus review panel summary for empty resonance", () => {
    const summary = buildConsensusReviewPanelSummary(
      buildConsensusSummary({
        ...strategyPayload,
        stock_candidates: {
          ...strategyPayload.stock_candidates!,
          items: [
            {
              rank: 1,
              stock_code: "000001.SZ",
              stock_name: "平安",
              sector_code: "BK",
              sector_name: "银行",
              sector_rank: 1,
              close: 10,
              breakout_level: 11,
              ma20: 10.5,
              ma60: 10,
              ma120: 9.5,
              close_strength: 0.8,
              gap_norm: 0.02,
              abnormal_turnover: 1.1,
            },
          ],
          candidate_count: 1,
        },
        factor_screen_candidates: {
          as_of_date: "2026-04-29",
          formula_version: "factor_v1",
          market_state: "WARM",
          input_stock_count: 1,
          candidate_count: 1,
          coverage_note: "ok",
          items: [
            {
              rank: 1,
              stock_code: "600000.SH",
              stock_name: "浦发",
              sector_code: "BK",
              sector_name: "银行",
              industry: "银行",
              score: 0.9,
              pe: 10.2,
              pb: 1.1,
              roe: 0.12,
              gross_margin: 0.3,
              three_month_return: 0.08,
              twelve_month_return: 0.16,
              dividend_yield: 0.02,
            },
          ],
        },
      }),
    );
    expect(summary.headline).toContain("暂无 T+5 共振");
    expect(summary.badgeLabel).toBe("待复核");
    expect(summary.badgeLabel).not.toBe("待补");

    const noCandidateSummary = buildConsensusReviewPanelSummary(buildConsensusSummary(null));
    expect(noCandidateSummary.headline).toBe("暂无候选");
    expect(noCandidateSummary.badgeLabel).toBe("无候选");
    expect(noCandidateSummary.badgeLabel).not.toBe("待补");
  });

  it("builds deep-zone audit rows from panel summaries and visible counts", () => {
    expect(
      buildDeepZoneAuditRows({
        cycleRotationSummary: { badgeLabel: "Cycle", tone: "positive" },
        themeBreakoutSummary: { badgeLabel: "Theme", tone: "warning" },
        strategyBacktestSummary: { tone: "neutral" },
        strategyBacktestDateRangeLabel: "04-20 ~ 04-29",
        consensusItemCount: 3,
        reviewQueueCount: 5,
        consensusReviewSummary: { tone: "positive" },
        marketPrioritySummary: { tone: "warning" },
        eventsMonitoringSummary: {},
        eventMonitorCount: 2,
      }),
    ).toEqual([
      { key: "supply", label: "供数", value: "Cycle", tone: "positive" },
      { key: "replay", label: "回放", value: "04-20 ~ 04-29", tone: "neutral" },
      { key: "review", label: "候选", value: "3 / 5", tone: "positive" },
      { key: "events", label: "事件", value: "2", tone: "neutral" },
    ]);

    expect(
      buildDeepZoneAuditRows({
        cycleRotationSummary: null,
        themeBreakoutSummary: { badgeLabel: "Theme", tone: "warning" },
        strategyBacktestSummary: { badgeLabel: "Replay", tone: "positive" },
        strategyBacktestDateRangeLabel: "fallback",
        consensusItemCount: 0,
        reviewQueueCount: 0,
        consensusReviewSummary: {},
        marketPrioritySummary: { tone: "warning" },
        eventsMonitoringSummary: { badgeLabel: "Alerts", tone: "negative" },
        eventMonitorCount: 4,
      })[0],
    ).toEqual({ key: "supply", label: "供数", value: "Theme", tone: "warning" });
  });

  it("builds theme breakout and observation pool panel summaries from payload", () => {
    const themeSummary = buildThemeBreakoutPanelSummary({
      payload: strategyPayload,
      cards: buildThemeBreakoutCards(strategyPayload),
      reviewCount: 0,
    });
    expect(themeSummary.stats.some((stat) => stat.key === "coverage")).toBe(true);

    const poolSummary = buildObservationPoolsPanelSummary({
      gateState: "WARM",
      meanReversionCount: 2,
      factorScreenCount: 1,
      hybridFusionCount: 0,
      meanReversionActive: true,
    });
    expect(poolSummary.headline).toContain("多因子 1 只待复核");

    const events = buildEventsMonitoringPanelSummary(
      buildStockAnalysisEventMonitorRows(strategyPayload, confluencePayload),
    );
    expect(events.headline).toMatch(/条待复核/);

    const errorEvents = buildEventsMonitoringPanelSummary([
      {
        key: "diagnostic:failed",
        source: "diagnostic",
        level: "error",
        event: "诊断异常",
        impact: "data_quality",
        detail: "诊断返回错误，需要人工复核。",
      },
    ]);
    expect(errorEvents.badgeLabel).toBe("异常待核");
    expect(errorEvents.badgeLabel).not.toBe("待补");
  });

  it("localizes pending optimization summary copy when samples are insufficient", () => {
    const payload: LivermoreStrategyOptimizationPayload = {
      as_of_date: "2026-05-13",
      snapshot_from: "2026-05-01",
      snapshot_to: "2026-05-13",
      primary_horizon: "return_5d",
      min_sample: 20,
      current_market_state: "HOT",
      backtest_window_summary: null,
      strategy_summaries: [],
      slices: [],
      recommendations: [],
      pending_summary: {
        primary_horizon: "return_5d",
        pending_rows: 18,
        pending_dates: ["2026-05-13"],
        latest_pending_date: "2026-05-13",
        message: "T+5 仍有 18 条收益待成熟，最新 pending 日期 2026-05-13。",
      },
      sample_maturity: null,
    };

    const summary = buildStrategyOptimizationPanelSummary({
      payload,
      rows: [],
      queryState: "ready",
    });

    expect(summary.headline).toBe("优化样本不足");
    expect(summary.badgeLabel).toBe("待成熟");
    expect(summary.detail).toContain("最新待成熟日期 2026-05-13");
    expect(summary.detail).not.toContain("pending");
    expect(summary.stats).toContainEqual(
      expect.objectContaining({
        key: "pending",
        label: "待成熟",
        value: "18 行",
      }),
    );
  });

  it("localizes optimization panel summary recommendation detail", () => {
    const stats = {
      return_5d: {
        available_count: 30,
        missing_count: 0,
        positive_count: 20,
        non_positive_count: 10,
        avg_return: 0.0233,
        win_rate: 0.667,
      },
    };
    const dateWeightedStats = {
      return_5d: {
        available_day_count: 2,
        candidate_row_count: 30,
        avg_return: 0.0233,
        positive_day_rate: 1,
        worst_day_return: 0.01,
        best_day_return: 0.03,
      },
    };
    const payload: LivermoreStrategyOptimizationPayload = {
      as_of_date: "2026-05-13",
      snapshot_from: "2026-05-01",
      snapshot_to: "2026-05-13",
      primary_horizon: "return_5d",
      min_sample: 20,
      current_market_state: "HOT",
      backtest_window_summary: null,
      strategy_summaries: [
        {
          summary_key: "strategy:factor_screen",
          signal_kind: "factor_screen",
          strategy_label: "多因子",
          sample_status: "sufficient",
          stats,
          date_weighted_stats: dateWeightedStats,
          recommendation: {
            action: "promote",
            priority_label: "优先复核",
            reason: "T+5 sample 30, avg return +2.33%, win rate 66.7%, priority review ranking.",
            primary_horizon: "return_5d",
            available_count: 30,
            min_sample: 20,
            avg_return: 0.0233,
            win_rate: 0.667,
            score: 69,
          },
        },
      ],
      slices: [],
      recommendations: [],
      pending_summary: {
        primary_horizon: "return_5d",
        pending_rows: 0,
        pending_dates: [],
        latest_pending_date: null,
        message: "",
      },
      sample_maturity: null,
    };

    const summary = buildStrategyOptimizationPanelSummary({
      payload,
      rows: payload.strategy_summaries,
      queryState: "ready",
    });

    expect(summary.detail).toBe("T+5 样本 30，均值 +2.33%，胜率 66.7%，优先复核排序。");
    expect(summary.detail).not.toContain("sample 30");
    expect(summary.detail).not.toContain("priority review ranking");
  });

  it("localizes market priority panel summary reason detail", () => {
    const payload: LivermoreStrategyScorePayload = {
      as_of_date: "2026-05-13",
      snapshot_from: "2026-05-01",
      snapshot_to: "2026-05-13",
      primary_horizon: "return_5d",
      min_sample: 20,
      current_market_state: "HOT",
      rows: [
        {
          market_state: "HOT",
          signal_kind: "factor_screen",
          strategy_label: "多因子",
          sample_status: "sufficient",
          priority_score: 69,
          priority_rank: 1,
          priority_label: "优先复核",
          reason: "T+5 sample 30, avg return +2.33%, win rate 66.7%, priority review ranking.",
          stats: {
            return_1d: {
              available_count: 30,
              missing_count: 0,
              positive_count: 18,
              non_positive_count: 12,
              avg_return: 0.006,
              win_rate: 0.6,
            },
            return_5d: {
              available_count: 30,
              missing_count: 0,
              positive_count: 20,
              non_positive_count: 10,
              avg_return: 0.0233,
              win_rate: 0.667,
            },
            return_10d: {
              available_count: 30,
              missing_count: 0,
              positive_count: 18,
              non_positive_count: 12,
              avg_return: 0.028,
              win_rate: 0.6,
            },
            return_20d: {
              available_count: 30,
              missing_count: 0,
              positive_count: 16,
              non_positive_count: 14,
              avg_return: 0.031,
              win_rate: 0.533,
            },
          },
        },
      ],
      current_market_state_rows: [],
    };

    const summary = buildMarketPriorityPanelSummary({
      payload,
      rows: payload.rows,
      marketState: "HOT",
      queryState: "ready",
    });

    expect(summary.detail).toBe("T+5 样本 30，均值 +2.33%，胜率 66.7%，优先复核排序。");
    expect(summary.detail).not.toContain("sample 30");
    expect(summary.detail).not.toContain("priority review ranking");
  });

  it("keeps market priority insufficient-sample summaries read-only", () => {
    const payload: LivermoreStrategyScorePayload = {
      as_of_date: "2026-05-13",
      snapshot_from: "2026-05-01",
      snapshot_to: "2026-05-13",
      primary_horizon: "return_5d",
      min_sample: 20,
      current_market_state: "HOT",
      rows: [
        {
          market_state: "HOT",
          signal_kind: "factor_screen",
          strategy_label: "多因子",
          sample_status: "insufficient",
          priority_score: null,
          priority_rank: null,
          priority_label: "样本不足",
          reason: "sample pending",
          stats: {
            return_1d: {
              available_count: 0,
              missing_count: 6,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
            },
            return_5d: {
              available_count: 0,
              missing_count: 6,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
            },
            return_10d: {
              available_count: 0,
              missing_count: 6,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
            },
            return_20d: {
              available_count: 0,
              missing_count: 6,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
            },
          },
        },
      ],
      current_market_state_rows: [],
    };

    const summary = buildMarketPriorityPanelSummary({
      payload,
      rows: payload.rows,
      marketState: "HOT",
      queryState: "ready",
    });

    expect(summary.headline).toBe("样本不足");
    expect(summary.badgeLabel).toBe("样本不足");
    expect(summary.detail).toBe("阈值 20 · 只读排序");
    expect(summary.detail).not.toContain("交易动作");
    expect(summary.detail).not.toContain("不输出");
  });

  it("keeps unknown vendor strategy labels and statuses out of strategy panel headlines", () => {
    const stats = {
      return_1d: {
        available_count: 30,
        missing_count: 0,
        positive_count: 18,
        non_positive_count: 12,
        avg_return: 0.006,
        win_rate: 0.6,
      },
      return_5d: {
        available_count: 30,
        missing_count: 0,
        positive_count: 20,
        non_positive_count: 10,
        avg_return: 0.0233,
        win_rate: 0.667,
      },
      return_10d: {
        available_count: 30,
        missing_count: 0,
        positive_count: 18,
        non_positive_count: 12,
        avg_return: 0.028,
        win_rate: 0.6,
      },
      return_20d: {
        available_count: 30,
        missing_count: 0,
        positive_count: 16,
        non_positive_count: 14,
        avg_return: 0.031,
        win_rate: 0.533,
      },
    };
    const priorityPayload: LivermoreStrategyScorePayload = {
      as_of_date: "2026-05-13",
      snapshot_from: "2026-05-01",
      snapshot_to: "2026-05-13",
      primary_horizon: "return_5d",
      min_sample: 20,
      current_market_state: "HOT",
      rows: [
        {
          market_state: "HOT",
          signal_kind: "factor_screen",
          strategy_label: "sourceTableAlphaSignal",
          sample_status: "sufficient",
          priority_score: 69,
          priority_rank: 1,
          priority_label: "external_vendor_priority_state",
          reason: "vendor_quality_signal_pending",
          stats,
        },
      ],
      current_market_state_rows: [],
    };
    const optimizationPayload: LivermoreStrategyOptimizationPayload = {
      as_of_date: "2026-05-13",
      snapshot_from: "2026-05-01",
      snapshot_to: "2026-05-13",
      primary_horizon: "return_5d",
      min_sample: 20,
      current_market_state: "HOT",
      backtest_window_summary: null,
      strategy_summaries: [
        {
          summary_key: "strategy:sourceTableAlphaSignal",
          signal_kind: "factor_screen",
          strategy_label: "sourceTableAlphaSignal",
          sample_status: "sufficient",
          stats,
          date_weighted_stats: {},
          recommendation: {
            action: "promote",
            priority_label: "external_vendor_priority_state",
            reason: "vendor_quality_signal_pending",
            primary_horizon: "return_5d",
            available_count: 30,
            min_sample: 20,
            avg_return: 0.0233,
            win_rate: 0.667,
            score: 69,
          },
        },
      ],
      slices: [],
      recommendations: [],
      pending_summary: {
        primary_horizon: "return_5d",
        pending_rows: 0,
        pending_dates: [],
        latest_pending_date: null,
        message: "",
      },
      sample_maturity: null,
    };

    const priority = buildMarketPriorityPanelSummary({
      payload: priorityPayload,
      rows: priorityPayload.rows,
      marketState: "HOT",
      queryState: "ready",
    });
    const optimization = buildStrategyOptimizationPanelSummary({
      payload: optimizationPayload,
      rows: optimizationPayload.strategy_summaries,
      queryState: "ready",
    });

    expect(priority.headline).toBe("状态待确认 · 多因子");
    expect(priority.badgeLabel).toBe("待确认");
    expect(priority.tone).toBe("warning");
    expect(optimization.headline).toBe("状态待确认 · 多因子");
    expect(optimization.badgeLabel).toBe("待确认");
    expect(optimization.tone).toBe("warning");
    expect(`${priority.headline} ${optimization.headline}`).not.toContain("sourceTableAlphaSignal");
    expect(`${priority.headline} ${optimization.headline}`).not.toContain("external_vendor_priority_state");
  });

  it("localizes strategy panel error summaries before exposing request failures", () => {
    const errorMessage = "Failed to fetch market priority because source_table livermore_signal_snapshots is missing.";
    const priority = buildMarketPriorityPanelSummary({
      payload: null,
      rows: [],
      marketState: "HOT",
      queryState: "error",
      errorMessage,
    });
    const backtest = buildStrategyBacktestPanelSummary({
      payload: null,
      sampleCount: 0,
      window: null,
      dateRangeLabel: "",
      rows: [],
      queryState: "error",
      errorMessage,
    });
    const optimization = buildStrategyOptimizationPanelSummary({
      payload: null,
      rows: [],
      queryState: "error",
      errorMessage,
    });

    const copy = [priority.detail, backtest.detail, optimization.detail].join(" ");
    expect(priority.detail).toBe("请求失败：必需数据源缺失，稍后复核供数状态。");
    expect(backtest.detail).toBe("请求失败：必需数据源缺失，稍后复核供数状态。");
    expect(optimization.detail).toBe("请求失败：必需数据源缺失，稍后复核供数状态。");
    expect([priority.badgeLabel, backtest.badgeLabel, optimization.badgeLabel]).toEqual([
      "读取失败",
      "读取失败",
      "读取失败",
    ]);
    expect(copy).not.toContain("Failed to fetch");
    expect(copy).not.toContain("source_table");
    expect(copy).not.toContain("livermore_signal_snapshots");
  });

  it("keeps deferred strategy panels in an explicit not-triggered state", () => {
    const priority = buildMarketPriorityPanelSummary({
      payload: null,
      rows: [],
      marketState: "WARM",
      queryState: "idle",
    });
    const backtest = buildStrategyBacktestPanelSummary({
      payload: null,
      sampleCount: 0,
      window: null,
      dateRangeLabel: "",
      rows: [],
      queryState: "idle",
    });
    const optimization = buildStrategyOptimizationPanelSummary({
      payload: null,
      rows: [],
      queryState: "idle",
    });
    const cycle = buildCycleRotationPanelSummary({
      framework: {
        strategy_name: "A-share cycle rotation research framework",
        display_name: "A股景气周期选股与行业轮动",
        observation_only: true,
        implementation_stage: "verification_pending",
        score_formula: "CycleScore = weighted evidence",
        rebalance_cadence: "Monthly review",
        layers: [],
        constraints: [],
        boundary: "observation-only",
      },
      macroLayer: null,
      portfolioBacktest: null,
      proxyBacktest: null,
      portfolioQueryState: "idle",
      proxyQueryState: "idle",
    });

    expect([priority, backtest, optimization].map((summary) => summary.headline)).toEqual([
      "待触发",
      "待触发",
      "待触发",
    ]);
    expect([priority, backtest, optimization].map((summary) => summary.badgeLabel)).toEqual([
      "待触发",
      "待触发",
      "待触发",
    ]);
    expect(cycle.stats).toContainEqual(
      expect.objectContaining({ key: "backtest", label: "回测", value: "待触发" }),
    );
  });

  it("discloses the execution-first cycle proxy return composition", () => {
    const proxyBacktest: LivermoreCycleProxyBacktestPayload = {
      status: "proxy",
      full_strategy_status: "blocked_missing_inputs",
      formula_version: "fv_livermore_cycle_proxy_backtest_execution_first_v4",
      proxy_signal_kind: "stock_candidate",
      proxy_rule: "execution-first",
      execution_blocked_rows_in_window: 40,
      snapshot_from: "2024-09-24",
      snapshot_to: "2026-03-02",
      missing_full_strategy_inputs: [],
      warnings: [],
      summary: {
        sample_days: 225,
        candidate_rows: 546,
        return_field_used: "return_5d_net_adj",
        return_field_fallback: "return_5d_adj",
        return_field_second_fallback: "return_5d",
        execution_return_costs_already_applied: true,
        return_rows_execution_net_adjusted: 433,
        return_rows_adjusted: 23,
        return_rows_adjusted_fallback: 23,
        return_rows_gross_fallback: 90,
        cumulative_return: -0.297,
        annualized_return: -0.4801,
        max_gain: { return: 0.9185 },
        max_drawdown: { return: -0.6342 },
      },
      nav_series: [],
    };

    const cycle = buildCycleRotationPanelSummary({
      framework: cycleRotationFrameworkFixture,
      macroLayer: null,
      portfolioBacktest: null,
      proxyBacktest,
      portfolioQueryState: "ready",
      proxyQueryState: "ready",
    });

    expect(cycle.proxyBacktestBasisDisclosure).toBe(
      "入场口径：优先字段 return_5d_net_adj（次日开盘净收益）；可执行入场覆盖 433/546（79%）。回退构成：return_5d_adj 23 行；return_5d 90 行。阻断剔除 40 行；公式版本 fv_livermore_cycle_proxy_backtest_execution_first_v4。",
    );
  });

  it("uses pending placeholders for legacy cycle proxy payloads", () => {
    const legacyProxyBacktest: LivermoreCycleProxyBacktestPayload = {
      status: "proxy",
      full_strategy_status: "blocked_missing_inputs",
      proxy_signal_kind: "stock_candidate",
      proxy_rule: "legacy",
      snapshot_from: "2024-09-24",
      snapshot_to: "2026-03-02",
      missing_full_strategy_inputs: [],
      warnings: [],
      summary: {
        sample_days: 225,
        candidate_rows: 546,
        cumulative_return: -0.297,
        annualized_return: -0.4801,
        max_gain: { return: 0.9185 },
        max_drawdown: { return: -0.6342 },
      },
      nav_series: [],
    };

    const cycle = buildCycleRotationPanelSummary({
      framework: cycleRotationFrameworkFixture,
      macroLayer: null,
      portfolioBacktest: null,
      proxyBacktest: legacyProxyBacktest,
      portfolioQueryState: "ready",
      proxyQueryState: "ready",
    });

    expect(cycle.proxyBacktestBasisDisclosure).toBe(
      "入场口径：优先字段待补；可执行入场覆盖待补。回退构成：第一档待补；第二档待补。阻断剔除待补；公式版本待补。",
    );
    expect(cycle.proxyBacktestBasisDisclosure).not.toMatch(/NaN|undefined/);
  });

  it("keeps cycle backtest request failures distinct from business no-sample states", () => {
    const cycle = buildCycleRotationPanelSummary({
      framework: {
        strategy_name: "A-share cycle rotation research framework",
        display_name: "A股景气周期选股与行业轮动",
        observation_only: true,
        implementation_stage: "verification_pending",
        score_formula: "CycleScore = weighted evidence",
        rebalance_cadence: "Monthly review",
        layers: [],
        constraints: [],
        boundary: "observation-only",
      },
      macroLayer: null,
      portfolioBacktest: null,
      proxyBacktest: null,
      portfolioQueryState: "error",
      proxyQueryState: "idle",
    });

    expect(cycle.stats).toContainEqual(
      expect.objectContaining({ key: "backtest", label: "回测", value: "读取失败" }),
    );
    expect(cycle.detail).toContain("读取失败");
    expect(cycle.detail).not.toContain("各层只读证据已接入");
  });

  it("keeps independently triggered cycle endpoints distinct from a completed no-sample result", () => {
    const cycle = buildCycleRotationPanelSummary({
      framework: {
        strategy_name: "A-share cycle rotation research framework",
        display_name: "A股景气周期选股与行业轮动",
        observation_only: true,
        implementation_stage: "verification_pending",
        score_formula: "CycleScore = weighted evidence",
        rebalance_cadence: "Monthly review",
        layers: [],
        constraints: [],
        boundary: "observation-only",
      },
      macroLayer: null,
      portfolioBacktest: null,
      proxyBacktest: null,
      portfolioQueryState: "ready",
      proxyQueryState: "idle",
    });

    expect(cycle.stats).toContainEqual(
      expect.objectContaining({ key: "backtest", label: "回测", value: "部分触发" }),
    );
    expect(cycle.detail).toContain("部分回测端点尚未触发");
    expect(cycle.detail).not.toContain("各层只读证据已接入");
    expect(cycle.detail).not.toContain("无样本");
  });

  it("does not mark the backtest panel ready when only short-horizon returns are mature", () => {
    const matureT1 = {
      available_count: 12,
      missing_count: 0,
      positive_count: 8,
      non_positive_count: 4,
      avg_return: 0.02,
      win_rate: 0.667,
    };
    const pendingT5 = {
      available_count: 0,
      missing_count: 12,
      positive_count: 0,
      non_positive_count: 0,
      avg_return: null,
      win_rate: null,
    };
    const payload: LivermoreCandidateHistoryPayload = {
      stock_code: null,
      snapshot_from: "2026-07-01",
      snapshot_to: "2026-07-10",
      limit: 100,
      items: [],
      summary: {
        row_count: 12,
        horizon_usable_stats: {
          return_1d: matureT1,
          return_5d: pendingT5,
          return_10d: pendingT5,
          return_20d: pendingT5,
        },
        by_signal_kind: { stock_candidate: 12 },
        by_signal_kind_horizon_usable_stats: {
          stock_candidate: {
            return_1d: matureT1,
            return_5d: pendingT5,
            return_10d: pendingT5,
            return_20d: pendingT5,
          },
        },
      },
      backtest_window_summary: {
        status: "partial",
        snapshot_from: "2026-07-01",
        snapshot_to: "2026-07-10",
        replay_dates_total: 1,
        replay_dates_completed: 0,
        replay_dates_pending: 1,
        replay_dates_unsupported: 0,
        replay_dates_proxy_only: 0,
        completed_rows: 0,
        pending_rows: 12,
        unsupported_rows: 0,
        proxy_only_rows: 0,
        included_completed_stats_dates: [],
        excluded_from_completed_stats_dates: ["2026-07-10"],
        date_reasons: [
          {
            trade_date: "2026-07-10",
            status: "pending",
            reason_code: "forward_returns_pending",
            message: "pending",
            affects_completed_stats: false,
            signal_kinds: ["stock_candidate"],
          },
        ],
      },
    };

    const summary = buildStrategyBacktestPanelSummary({
      payload,
      sampleCount: 12,
      window: payload.backtest_window_summary ?? null,
      dateRangeLabel: "2026-07-01 ~ 2026-07-10",
      rows: [
        {
          kind: "stock_candidate",
          label: "趋势突破",
          count: 12,
          stats: {
            return_1d: "66.7% / +2.00% / 12条",
            return_5d: "自然待成熟 · 1日",
          },
        },
      ],
      queryState: "ready",
    });

    expect(summary.headline).toBe("短窗可见，T+5 待成熟");
    expect(summary.badgeLabel).toBe("部分成熟");
    expect(summary.tone).toBe("warning");
  });

  it("surfaces historical source gaps separately from visible return samples and natural maturity", () => {
    const sourceGapWindow: BacktestWindowSummary = {
      status: "partial",
      snapshot_from: "2026-06-30",
      snapshot_to: "2026-07-10",
      replay_dates_total: 9,
      replay_dates_completed: 0,
      replay_dates_pending: 2,
      replay_dates_unsupported: 7,
      replay_dates_proxy_only: 0,
      completed_rows: 0,
      pending_rows: 150,
      unsupported_rows: 210,
      proxy_only_rows: 0,
      included_completed_stats_dates: [],
      excluded_from_completed_stats_dates: ["2026-06-30", "2026-07-10"],
      date_reasons: Array.from({ length: 7 }, (_, index) => ({
        trade_date: `2026-07-0${index + 1}`,
        status: "unsupported",
        reason_code: "missing_required_source_table",
        message: "Required source coverage is incomplete.",
        affects_completed_stats: false,
        signal_kinds: ["factor_screen"],
      })),
    };
    const priorityPayload: LivermoreStrategyScorePayload = {
      as_of_date: "2026-07-10",
      snapshot_from: "2026-06-30",
      snapshot_to: "2026-07-10",
      primary_horizon: "return_5d",
      min_sample: 20,
      current_market_state: "WARM",
      backtest_window_summary: sourceGapWindow,
      rows: [],
      current_market_state_rows: [],
    };
    const optimizationPayload: LivermoreStrategyOptimizationPayload = {
      as_of_date: "2026-07-10",
      snapshot_from: "2026-06-30",
      snapshot_to: "2026-07-10",
      primary_horizon: "return_5d",
      min_sample: 20,
      current_market_state: "WARM",
      backtest_window_summary: sourceGapWindow,
      strategy_summaries: [],
      slices: [],
      recommendations: [],
      pending_summary: {
        primary_horizon: "return_5d",
        pending_rows: 150,
        pending_dates: ["2026-07-08", "2026-07-10"],
        latest_pending_date: "2026-07-10",
        message: "T+5 仍有 150 条收益待成熟。",
      },
      sample_maturity: null,
    };

    const priority = buildMarketPriorityPanelSummary({
      payload: priorityPayload,
      rows: [],
      marketState: "WARM",
      queryState: "ready",
    });
    const backtest = buildStrategyBacktestPanelSummary({
      payload: null,
      sampleCount: 84,
      window: sourceGapWindow,
      dateRangeLabel: "2026-06-30 ~ 2026-07-10",
      rows: [
        {
          kind: "factor_screen",
          label: "多因子",
          count: 60,
          stats: {
            return_1d: "51.2% / +2.42% / 84条",
            return_5d: "自然待成熟 · 60条",
            return_10d: "自然待成熟 · 60条",
            return_20d: "自然待成熟 · 60条",
          },
        },
      ],
      queryState: "ready",
    });
    const optimization = buildStrategyOptimizationPanelSummary({
      payload: optimizationPayload,
      rows: [],
      queryState: "ready",
    });

    expect(priority).toMatchObject({ headline: "历史样本源不足", badgeLabel: "历史源不足", tone: "warning" });
    expect(backtest).toMatchObject({ headline: "可见收益样本 84 条", badgeLabel: "历史源不足", tone: "warning" });
    expect(backtest.stats).toContainEqual(
      expect.objectContaining({ key: "unsupported", label: "历史源不足", value: "7 日" }),
    );
    expect(optimization).toMatchObject({ headline: "历史样本源不足", badgeLabel: "历史源不足", tone: "warning" });
    expect(optimization.stats).toContainEqual(
      expect.objectContaining({ key: "unsupported", label: "历史源不足", value: "7 日" }),
    );
  });

  it("keeps aggregate-only unsupported replay counts at panel scope", () => {
    const window: BacktestWindowSummary = {
      status: "unsupported",
      snapshot_from: "2026-07-01",
      snapshot_to: "2026-07-03",
      replay_dates_total: 3,
      replay_dates_completed: 0,
      replay_dates_pending: 0,
      replay_dates_unsupported: 3,
      replay_dates_proxy_only: 0,
      completed_rows: 0,
      pending_rows: 0,
      unsupported_rows: 30,
      proxy_only_rows: 0,
      included_completed_stats_dates: [],
      excluded_from_completed_stats_dates: ["2026-07-01", "2026-07-02", "2026-07-03"],
      date_reasons: [],
    };

    const summary = buildStrategyBacktestPanelSummary({
      payload: null,
      sampleCount: 0,
      window,
      dateRangeLabel: "2026-07-01 ~ 2026-07-03",
      rows: [],
      queryState: "ready",
    });

    expect(summary).toMatchObject({
      headline: "回放窗口不支持",
      badgeLabel: "窗口不支持",
      tone: "warning",
    });
    expect(summary.stats).toContainEqual(
      expect.objectContaining({ key: "window", label: "窗口不支持", value: "3 日" }),
    );
  });

  it("labels strategy backtest panel summary with execution return basis", () => {
    const executionPayload: LivermoreCandidateHistoryPayload = {
      stock_code: null,
      snapshot_from: "2026-06-01",
      snapshot_to: "2026-06-12",
      limit: 50,
      items: [],
      summary: {
        row_count: 2,
        execution_usable_stats: {
          metric_basis: "net_next_open_adj",
          row_count: 2,
          horizon_usable_stats: {
            return_1d: {
              available_count: 2,
              missing_count: 0,
              positive_count: 1,
              non_positive_count: 1,
              avg_return: 0.01,
              win_rate: 0.5,
            },
            return_5d: {
              available_count: 2,
              missing_count: 0,
              positive_count: 2,
              non_positive_count: 0,
              avg_return: 0.04,
              win_rate: 1,
            },
            return_10d: {
              available_count: 0,
              missing_count: 2,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
            },
            return_20d: {
              available_count: 0,
              missing_count: 2,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
            },
          },
          by_signal_kind_horizon_usable_stats: {
            stock_candidate: {
              return_1d: {
                available_count: 2,
                missing_count: 0,
                positive_count: 1,
                non_positive_count: 1,
                avg_return: 0.01,
                win_rate: 0.5,
              },
              return_5d: {
                available_count: 2,
                missing_count: 0,
                positive_count: 2,
                non_positive_count: 0,
                avg_return: 0.04,
                win_rate: 1,
              },
              return_10d: {
                available_count: 0,
                missing_count: 2,
                positive_count: 0,
                non_positive_count: 0,
                avg_return: null,
                win_rate: null,
              },
              return_20d: {
                available_count: 0,
                missing_count: 2,
                positive_count: 0,
                non_positive_count: 0,
                avg_return: null,
                win_rate: null,
              },
            },
          },
        },
      },
    };

    const summary = buildStrategyBacktestPanelSummary({
      payload: executionPayload,
      sampleCount: 2,
      window: null,
      dateRangeLabel: "2026-06-01 ~ 2026-06-12",
      rows: [
        {
          kind: "stock_candidate",
          label: "趋势突破",
          count: 2,
          stats: { return_1d: "legacy", return_5d: "legacy", return_10d: "legacy", return_20d: "legacy" },
        },
      ],
      queryState: "ready",
    });

    expect(summary.detail).toBe("2026-06-01 ~ 2026-06-12 · T+1开盘成交·含费·复权");
    expect(summary.stats[0].value).toBe("胜率 100.0% / 均收益 +4.0% / 2条");
  });

  it("does not mark legacy aggregates ready under an execution basis", () => {
    const legacyStats = {
      available_count: 6,
      missing_count: 0,
      positive_count: 4,
      non_positive_count: 2,
      avg_return: 0.03,
      win_rate: 0.667,
    };
    const payload: LivermoreCandidateHistoryPayload = {
      stock_code: null,
      snapshot_from: "2026-06-01",
      snapshot_to: "2026-06-12",
      limit: 50,
      items: [],
      summary: {
        row_count: 6,
        horizon_stats: {
          return_1d: legacyStats,
          return_5d: legacyStats,
          return_10d: legacyStats,
          return_20d: legacyStats,
        },
        by_signal_kind: { stock_candidate: 6 },
        by_signal_kind_horizon_stats: {
          stock_candidate: {
            return_1d: legacyStats,
            return_5d: legacyStats,
            return_10d: legacyStats,
            return_20d: legacyStats,
          },
        },
        execution_usable_stats: {
          metric_basis: "net_next_open_adj",
          row_count: 0,
        },
      },
    };

    const summary = buildStrategyBacktestPanelSummary({
      payload,
      sampleCount: 0,
      window: null,
      dateRangeLabel: "2026-06-01 ~ 2026-06-12",
      rows: [
        {
          kind: "stock_candidate",
          label: "趋势突破",
          count: 0,
          stats: {
            return_1d: "接口未提供",
            return_5d: "接口未提供",
            return_10d: "接口未提供",
            return_20d: "接口未提供",
          },
        },
      ],
      queryState: "ready",
    });

    expect(summary.headline).toBe("暂无回溯样本");
    expect(summary.badgeLabel).toBe("暂无样本");
    expect(summary.stats[0].value).toBe("接口未提供");
    expect(summary.detail).toContain("T+1开盘成交·含费·复权");
  });

  it("keeps generic backend pending copy as confirmation status, not return maturity", () => {
    const copy = localizeStockBackendText("Signal confluence diagnostic pending detail.", "signal_confluence");

    expect(copy).toContain("待确认");
    expect(copy).not.toContain("待成熟");
  });

  it("localizes unknown vendor code-only diagnostics as pending explanation copy", () => {
    const copy = localizeStockBackendText(
      "vendor_quality_signal_pending",
      "external_vendor_quality_signal",
    );

    expect(copy).toBe("说明待确认");
    expect(copy).not.toContain("vendor_quality_signal_pending");
  });

  it("distinguishes ready PMI and credit impulse evidence from missing inputs", () => {
    expect(
      localizeStockBackendText(
        "Market gate is available; PMI and credit impulse are not landed.",
        "macro_score",
      ),
    ).toBe("市场门控已有可用证据，PMI 与信用脉冲待补。");
    expect(
      localizeStockBackendText(
        "Market gate is available; PMI and credit impulse are ready and landed.",
        "macro_score",
      ),
    ).toBe("市场门控、PMI 与信用脉冲已接入。");
  });

  it("localizes strategy sample and observation-only backend reasons", () => {
    const insufficient = localizeStockBackendText(
      "Current market sample is insufficient: T+5 available 6/20, observation only.",
      "stock_candidate",
    );
    const fusion = localizeStockBackendText("Fusion observation-only candidate", "hybrid_fusion");
    const maturity = localizeStockBackendText(
      "T+5 matured snapshots 2/4, waiting for more mature days.",
      "stock_candidate",
    );
    const optimization = localizeStockBackendText(
      "T+5 sample 30, avg return +2.33%, win rate 66.7%, priority review ranking.",
      "factor_screen",
    );
    const coverage = localizeStockBackendText("factor_snapshot 无数据", "factor_screen_candidates");
    const hybridPaused = localizeStockBackendText(
      "Hybrid fusion is observation-only and only emits candidates in WARM/HOT market states; current state is OVERHEAT.",
      "hybrid_fusion",
    );
    const trendPaused = localizeStockBackendText(
      "Stock candidate policy exp3b is inactive in OVERHEAT; active market states are HOT/WARM.",
      "stock_candidates",
    );
    const meanPaused = localizeStockBackendText(
      "Mean reversion watchlist is paused when the defended-trend candidate bundle already covers overheated tape.",
      "mean_reversion_candidates",
    );
    const replayUnsupported = localizeStockBackendText(
      "daily_limit_flags absent; Livermore strategy replay unsupported for 2026-05-29.",
      "candidate_history",
    );
    const sectorFormula = localizeStockBackendText(
      "Sector rank currently uses the provisional percentile formula over pctchange, turn, and amplitude.",
      "sector_rank",
    );

    expect(insufficient).toBe("样本不足 T+5 6/20");
    expect(insufficient).not.toContain("Current market sample");
    expect(fusion).toBe("融合池仅观察候选。");
    expect(fusion).not.toContain("Fusion observation-only candidate");
    expect(maturity).toBe("T+5 已成熟快照 2/4，等待更多成熟日。");
    expect(maturity).not.toContain("matured snapshots");
    expect(optimization).toBe("T+5 样本 30，均值 +2.33%，胜率 66.7%，优先复核排序。");
    expect(optimization).not.toContain("priority review ranking");
    expect(coverage).toBe("因子快照无数据。");
    expect(coverage).not.toContain("factor_snapshot");
    expect(hybridPaused).toContain("融合策略");
    expect(hybridPaused).not.toContain("Hybrid fusion");
    expect(trendPaused).toContain("趋势突破策略");
    expect(trendPaused).not.toContain("Stock candidate policy");
    expect(meanPaused).toContain("超跌反弹观察池");
    expect(meanPaused).not.toContain("Mean reversion watchlist");
    expect(replayUnsupported).toBe("涨停封单标记缺失；2026-05-29 回放不可用。");
    expect(replayUnsupported).not.toContain("daily_limit_flags");
    expect(sectorFormula).toBe("板块强弱仍使用涨跌幅、换手率与振幅的临时分位公式，需按观测口径复核。");
    expect(sectorFormula).not.toContain("Sector rank");
    expect(sectorFormula).not.toContain("pctchange");
  });

  it("localizes choice stock coverage and limit-up quality backend warnings", () => {
    const limitUp = localizeStockBackendText(
      "Choice limit-up quality catalog is confirmed, but landed inputs are unavailable; the market gate is capped at the trend-only slice.",
      "limit_up_quality",
    );
    const coverage = localizeStockBackendText(
      "Choice stock materialized input coverage is incomplete for 2026-06-11; missing request items: sector membership:sw2021 industry membership, sector strength:daily return turnover amplitude.",
      "choice_stock",
    );

    expect(limitUp).toBe("涨停质量目录已确认，但落地输入不可用；市场门控已限制为仅趋势切片。");
    expect(coverage).toContain("Choice 股票物化输入覆盖不完整（2026-06-11）");
    expect(coverage).toContain("缺数据项");
    expect(coverage).not.toContain("missing request items");
  });

  it("localizes rule readiness backend summaries", () => {
    expect(
      localizeStockBackendText(
        "All broad-index and supplement gate inputs are landed for the resolved trade date.",
        "market_gate",
      ),
    ).toBe("宽基指数与补充门控输入已落地，可用于当前交易日。");
    expect(
      localizeStockBackendText("Sector ranking is available from landed Choice sector inputs.", "sector_rank"),
    ).toBe("板块排名已接入 Choice 板块输入。");
    expect(
      localizeStockBackendText(
        "Daily sector strength observation rank is a signed-off analytical formula: 50% pctchange percentile, 30% turn percentile, and 20% amplitude percentile; it supports review prioritization and sector filtering, not trading instructions; multi-day momentum persistence, sector money flow, and crowding are not part of this version.",
        "sector_strength",
      ),
    ).toBe(
      "板块强弱观察排名已按 50% 涨跌幅分位、30% 换手率分位、20% 振幅分位签核；用于复核优先级与行业过滤，不构成交易指令；多日动量、板块资金流与拥挤度不包含在当前版本内。",
    );
    expect(
      localizeStockBackendText(
        "Daily sector score is an analytical observation formula pending metric-definition sign-off; multi-day momentum persistence and sector money flow are not part of this formula.",
        "sector_strength",
      ),
    ).toBe("板块强弱为分析观察公式，仍待指标定义签核；多日动量持续性与板块资金流不包含在当前公式内。");
    expect(
      localizeStockBackendText(
        "candidate screening is available for landed Choice stock inputs.",
        "stock_pivot",
      ),
    ).toBe("候选筛选已接入 Choice 个股输入。");
    expect(
      localizeStockBackendText(
        "Risk and exit output is available from landed position snapshots and close history.",
        "risk_exit",
      ),
    ).toBe("风险退出已接入持仓快照与收盘历史。");
  });

  it("builds a first-screen workbench digest from real returned fields", () => {
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      factor_screen_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_factor_screen_candidates_v2",
        market_state: "WARM",
        input_stock_count: 1,
        candidate_count: 1,
        coverage_note: "ok",
        items: [
          {
            rank: 1,
            stock_code: "600000.SH",
            stock_name: "浦发银行",
            sector_code: "801780",
            sector_name: "银行",
            industry: "银行",
            score: 0.82,
            pe: 5.2,
            pb: 0.6,
            roe: 0.12,
            gross_margin: 0.31,
            three_month_return: 0.08,
            twelve_month_return: 0.18,
            dividend_yield: 0.04,
          },
        ],
      },
      hybrid_fusion_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_hybrid_fusion_candidates_v4",
        market_state: "WARM",
        observation_only: true,
        candidate_count: 1,
        items: [
          {
            rank: 1,
            stock_code: "000001.SZ",
            stock_name: "平安银行",
            sector_code: "801780",
            sector_name: "银行",
            fusion_score: 0.8,
            cycle_score: 0.7,
            lifecourt_proxy_score: 0.6,
            attention_score: 0.5,
            price_confirm_score: 0.4,
            crowding_penalty: 0.1,
            confidence: "medium",
            reason: "Observation-only fusion candidate.",
            evidence: {},
          },
        ],
      },
    };
    const sectorSeries: LivermoreSectorRankSeriesPayload = {
      basis: "analytical",
      state: "ok",
      as_of_date: "2026-04-29",
      window_days: 20,
      top_k: 10,
      sector_code_filter: null,
      formula_version: "rv_sector_series_v1",
      series: [
        {
          trade_date: "2026-04-29",
          sector_code: "801780",
          sector_name: "银行",
          score: 0.91,
          rank: 1,
          avg_pctchange: 0.02,
          avg_turn: 0.03,
          avg_amplitude: 0.04,
          constituent_count: 12,
          cum_pctchange_window: 0.08,
        },
      ],
      unsupported_notes: [],
    };

    const digest = buildWorkbenchDataDigest({
      main: payload,
      signalConfluence: {
        ...confluencePayload,
        closed_loop_state: {
          entry_gate: "open",
          exit_gate: "watch",
          replay_status: "available",
          lineage_status: "complete",
        },
        replay_evidence: {
          status: "available",
          snapshot_as_of_date: "2026-04-29",
          row_count: 7,
          matched_entry_count: 1,
          sample_items: [{ stock_code: "000001.SZ", candidate_rank: 1 }],
        },
      },
      sectorRankSeries: sectorSeries,
    });

    expect(digest.primaryFacts.find((fact) => fact.id === "candidate-depth")).toMatchObject({
      value: "1 / 1",
      tone: "read",
    });
    expect(digest.candidateFacts.find((fact) => fact.id === "factor-candidates")).toMatchObject({
      value: "1 只",
      sourcePath: "strategy.result.factor_screen_candidates.items",
    });
    expect(digest.candidateFacts.find((fact) => fact.id === "sector-rank")).toMatchObject({
      subValue: "规则已签核 / rv_livermore_sector_strength_observation_v1",
    });
    expect(digest.evidenceFacts.find((fact) => fact.id === "sector-series")).toMatchObject({
      value: "1 条",
      tone: "read",
    });
    expect(digest.evidenceFacts.find((fact) => fact.id === "replay-evidence")).toMatchObject({
      value: "7 行",
      tone: "read",
    });
    expect(JSON.stringify(digest)).not.toContain("position_size_hint");
  });

  it("keeps missing candidate data distinct from real empty candidate arrays", () => {
    const missingDigest = buildWorkbenchDataDigest({
      main: {
        ...strategyPayload,
        factor_screen_candidates: undefined,
      },
    });
    expect(missingDigest.candidateFacts.find((fact) => fact.id === "factor-candidates")).toMatchObject({
      value: "未返回",
      tone: "missing",
    });

    const emptyDigest = buildWorkbenchDataDigest({
      main: {
        ...strategyPayload,
        factor_screen_candidates: {
          as_of_date: "2026-04-29",
          formula_version: "rv_factor_screen_candidates_v2",
          market_state: "WARM",
          input_stock_count: 1,
          candidate_count: 0,
          coverage_note: "ok",
          items: [],
        },
      },
    });
    expect(emptyDigest.candidateFacts.find((fact) => fact.id === "factor-candidates")).toMatchObject({
      value: "0 只",
      tone: "empty",
    });
  });

  it("summarizes slow evidence slots without calling them no data", () => {
    const loadingDigest = buildWorkbenchDataDigest({
      main: strategyPayload,
      candidateHistoryState: "loading",
      strategyScoreState: "slow",
    });
    expect(loadingDigest.slowFacts.find((fact) => fact.id === "candidate-history")).toMatchObject({
      value: "读取中",
      tone: "slow",
    });
    expect(loadingDigest.slowFacts.find((fact) => fact.id === "candidate-history")?.subValue).toContain("首屏不阻塞");
    expect(loadingDigest.slowFacts.find((fact) => fact.id === "strategy-score")).toMatchObject({
      value: "读取较慢",
      tone: "slow",
    });

    const candidateHistory: LivermoreCandidateHistoryPayload = {
      stock_code: null,
      snapshot_from: "2026-05-01",
      snapshot_to: "2026-05-13",
      limit: 500,
      summary: null,
      backtest_window_summary: null,
      items: [
        {
          snapshot_as_of_date: "2026-05-13",
          stock_code: "000001.SZ",
          stock_name: "平安银行",
          signal_kind: "factor_screen",
          candidate_rank: 1,
          sector_code: "801780",
          sector_name: "银行",
          selection_close: 10,
          forward_trade_date_1d: null,
          forward_trade_date_5d: null,
          forward_trade_date_20d: null,
          return_1d: null,
          return_5d: null,
          return_20d: null,
          data_status: "pending",
        },
      ],
    };
    const successDigest = buildWorkbenchDataDigest({
      main: strategyPayload,
      candidateHistory,
      strategyScore: {
        as_of_date: "2026-05-13",
        snapshot_from: "2026-05-01",
        snapshot_to: "2026-05-13",
        primary_horizon: "return_5d",
        min_sample: 30,
        current_market_state: "WARM",
        backtest_window_summary: null,
        rows: [],
        current_market_state_rows: [],
        stock_candidate_state_scopes: { WARM: {} },
      },
      candidateHistoryState: "success",
      strategyScoreState: "success",
    });

    expect(successDigest.slowFacts.find((fact) => fact.id === "candidate-history")).toMatchObject({
      value: "1 行",
      tone: "read",
    });
    expect(successDigest.slowFacts.find((fact) => fact.id === "strategy-score")).toMatchObject({
      value: "0 / 0",
      tone: "empty",
    });
  });

});
