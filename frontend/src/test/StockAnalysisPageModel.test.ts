import { describe, expect, it } from "vitest";

import type {
  ConfluenceReplayStatus,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
} from "../api/contracts";
import {
  buildCandidateReviewQueue,
  buildCandidateEvidenceCards,
  buildClosedLoopSummary,
  buildDataBoundarySummary,
  buildDecisionSummary,
  buildDailyJudgmentStrip,
  buildDataBoundaryNotes,
  buildMarketStateCard,
  buildRiskExitRows,
  buildSectorRows,
  buildSectorFilterSummary,
  buildSectorViewModel,
  buildStockAnalysisEvidenceStatus,
  buildStockAnalysisEventMonitorRows,
  buildStockAnalysisKpiStrip,
  buildThemeBreakoutCards,
  buildThemeBreakoutReviewItems,
  buildThemeEvidenceStateRows,
} from "../features/stock-analysis/lib/stockAnalysisPageModel";

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
  supported_outputs: ["market_gate", "sector_rank", "stock_candidates", "risk_exit"],
  unsupported_outputs: [],
  sector_rank: {
    as_of_date: "2026-04-29",
    formula_version: "rv_livermore_sector_rank_provisional_v1",
    is_provisional: true,
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
    expect(card.state).toBe("WARM");
    expect(card.exposureLabel).toBe("40%");
    expect(card.passedLabel).toBe("2 / 4 条件通过");
    expect(card.warnings.join(" ")).toContain("Breadth inputs are unavailable");
    expect(sectors[0].sectorName).toBe("AI");
    expect(sectors[0].pctChange).toBe("4.80%");
  });

  it("builds candidate evidence with counter-evidence and invalidation rules", () => {
    const cards = buildCandidateEvidenceCards(strategyPayload);

    expect(cards[0].stockCode).toBe("000001.SZ");
    expect(cards[0].headline).toContain("观察候选");
    expect(cards[0].pattern).toBe("突破");
    expect(cards[0].distanceToBreakoutPct).toMatch(/%/);
    expect(cards[0].evidence.join(" ")).toContain("行业排名第 1");
    expect(cards[0].evidence.join(" ")).toContain("收盘价 21.90");
    expect(cards[0].evidence.join(" ")).toContain("基本面 overlay");
    expect(cards[0].evidence.join(" ")).toContain("因子分 0.4812");
    expect(cards[0].evidence.join(" ")).toContain("ROE 18.0%");
    expect(cards[0].evidence.join(" ")).toContain("10EMA 失效观察");
    expect(cards[0].counterEvidence.join(" ")).toContain("基本面 overlay 已接入候选排序");
    expect(cards[0].counterEvidence.join(" ")).toContain("新闻、公告、财报事件尚未进入候选卡");
    expect(cards[0].invalidationRules.join(" ")).toContain("10EMA");
    expect(cards[0].invalidationRules.join(" ")).toContain("涨跌停状态");
    expect(cards[0].rawFields.some((row) => row.key === "gap_norm")).toBe(true);
    expect(cards[0].rawFields.some((row) => row.key === "breakout_extension_norm")).toBe(true);
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
    expect(summary.dataFreshnessLabel).toBe("数据需复核 warning / ok");
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
    expect(queue[0].boundaryEvidence.join(" ")).toContain("基本面 overlay 已接入候选排序");
    expect(queue[0].invalidationFocus).toContain("10EMA");
    expect(queue[0].reviewFocus).not.toContain("买入");
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
            confidence: "medium",
            reason: "Fusion observation-only candidate",
            evidence: { source_kinds: ["factor_screen", "theme_breakout"] },
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
    expect(cards[0].counterEvidence.join(" ")).toContain("代理信号");
    expect(queue[0].stockName).toBe("Fusion Alpha");
    expect(summary.candidateCountLabel).toBe("候选 1");
    expect(summary.nextReviewAction).toContain("Fusion Alpha");
    expect(summary.nextReviewAction).not.toContain("买入");
  });

  it("treats fallback snapshots as data that needs review", () => {
    const summary = buildDecisionSummary(strategyPayload, {
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "latest_snapshot",
    });

    expect(summary.dataFreshnessLabel).toBe("数据需复核 ok / ok / fallback latest_snapshot");
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
    expect(summary.nextReviewAction).toBe("暂无候选股，先核对门控、板块强弱和数据边界。");
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
      parentSectorLabel: "Electronic #9",
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
    expect(rows[0].statusLabel).toContain("catalog");
    expect(rows[1].detail).toContain("Intraday movement table");
    expect(rows.map((row) => row.detail).join(" ")).not.toContain("buy");
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
            failed_gates: ["insufficient_cluster_strength"],
            observation_only: true,
            reason: "Review-only proxy cluster missed selection: strong rows 2 below gate 3.",
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
      sourceKindLabel: "proxy",
    });
    expect(reviewItems[0].failedGateLabel).toContain("insufficient_cluster_strength");
    expect(reviewItems[0].summary).toContain("2");
    expect(`${reviewItems[0].reason} ${reviewItems[0].failedGateLabel}`).not.toContain("buy");
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
    expect(summary.verdict.primaryReason).toContain("crowded leaders without breadth confirmation");
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
          detail: expect.stringContaining("crowded leaders without breadth confirmation"),
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
    expect(summary.verdict.nextStep).toContain("fallback");
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
    expect(replayItem?.detail).toContain("excluded from completed stats: 2026-04-30, 2026-05-08, 2026-05-07");
    expect(replayItem?.detail).toContain("2026-04-30 missing_daily_limit_flags");
    expect(replayItem?.detail).toContain("2026-05-08 forward_returns_pending");
    expect(replayItem?.detail).toContain("2026-05-07 proxy_theme_only");
    expect(replayItem?.detail).toContain("completed zero-signal dates: 2026-05-06");
    expect(replayItem?.detail).toContain("do not infer strategy efficacy");
    expect(replayItem?.badges).toEqual(
      expect.arrayContaining([
        "completed dates 1",
        "pending dates 1",
        "unsupported dates 1",
        "proxy-only dates 1",
        "completed rows 0",
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
                trade_date: "2026-05-08",
                status: "pending",
                reason_code: "forward_returns_pending",
                signal_kinds: ["stock_candidate", "theme_breakout"],
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
    expect(replayItem?.detail).toContain("no decision-usable completed replay dates");
    expect(replayItem?.detail).toContain("2026-04-30 missing_daily_limit_flags");
    expect(replayItem?.detail).toContain("2026-05-08 forward_returns_pending");
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
    const watch = rows.find((r) => r.stockCode === "000777.SZ");
    expect(watch?.distanceToExitPct).toContain("%");
    expect(watch?.exitDistanceBucket === "triggered" || watch?.exitDistanceBucket === "0-3%").toBe(true);
  });

  it("surfaces data boundary notes and missing evidence", () => {
    const notes = buildDataBoundaryNotes(strategyPayload);

    expect(notes.join(" ")).toContain("basis: analytical");
    expect(notes.join(" ")).toContain("breadth missing");
    expect(notes.join(" ")).toContain("LIVERMORE_BREADTH_MISSING");
    expect(notes.join(" ")).toContain("rv_livermore_sector_rank_provisional_v1");
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

  it("flags top and bottom sector rows for charting", () => {
    const rows = buildSectorRows(strategyPayload);
    const top = rows.find((r) => r.sectorCode === "801001");
    const bottom = rows.find((r) => r.sectorCode === "801002");
    expect(top?.isTop).toBe(true);
    expect(bottom?.isBottom).toBe(true);
    expect(typeof top?.scoreNormalized).toBe("number");
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
    expect(summary.freshnessLabel).toBe("新鲜度 warning / ok / 回退 latest_snapshot");
    expect(summary.summaryLabel).toBe("3 条边界");
    expect(summary.detailLabel).toContain("诊断 1 / 缺口 1 / 未支持 1");
    expect(summary.topMessages.join(" ")).toContain("Breadth inputs are unavailable.");
    expect(summary.topMessages.join(" ")).toContain("position snapshot not landed");
  });

  it("builds current sector filter status for review queue stitching", () => {
    const filtered = buildSectorFilterSummary(strategyPayload, "801001");
    const unfiltered = buildSectorFilterSummary(strategyPayload, null);

    expect(filtered.isFiltered).toBe(true);
    expect(filtered.sectorLabel).toBe("AI");
    expect(filtered.visibleCount).toBe(1);
    expect(filtered.totalCount).toBe(1);
    expect(filtered.summaryLabel).toContain("sector AI (801001)");

    expect(unfiltered.isFiltered).toBe(false);
    expect(unfiltered.sectorLabel).toBe("all sectors");
    expect(unfiltered.summaryLabel).toBe("sector all sectors / showing 1 of 1");
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
      value: "WARM",
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
    const payload: LivermoreStrategyPayload = {
      ...strategyPayload,
      unsupported_outputs: [
        {
          key: "theme_breakout",
          reason: "concept membership table pending",
        },
      ],
    };
    const evidence = buildStockAnalysisEvidenceStatus(payload, {
      quality_flag: "warning",
      vendor_status: "vendor_stale",
      source_version: "sv_livermore_test",
      rule_version: "rv_livermore_market_gate_v1",
      fallback_mode: "latest_snapshot",
    });
    const events = buildStockAnalysisEventMonitorRows(payload, confluencePayload);

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
    expect(evidence.find((item) => item.key === "exceptions")?.detail).toContain("诊断 1 / 缺口 1 / 未支持 1");
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
          event: expect.stringContaining("theme_breakout"),
        }),
      ]),
    );
  });

});
