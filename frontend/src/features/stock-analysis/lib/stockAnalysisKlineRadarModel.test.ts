import { describe, expect, it } from "vitest";

import type { LivermoreStrategyPayload } from "../../../api/contracts";
import { buildStockAnalysisKlineRadar } from "./stockAnalysisKlineRadarModel";

function buildPayload(overrides: Partial<LivermoreStrategyPayload> = {}): LivermoreStrategyPayload {
  return {
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
      conditions: [],
    },
    rule_readiness: [],
    diagnostics: [],
    data_gaps: [],
    supported_outputs: ["market_gate", "stock_candidates", "risk_exit"],
    unsupported_outputs: [],
    module_states: [],
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
          close_strength: 0.83,
          gap_norm: -0.11,
          abnormal_turnover: 1.39,
          factor_score: 0.48,
        },
      ],
    },
    fresh_trend_watchlist: {
      as_of_date: "2026-04-29",
      formula_version: "rv_fresh_trend_watchlist_v1",
      market_state: "WARM",
      observation_only: true,
      input_stock_count: 1,
      candidate_count: 1,
      excluded_stock_count: 0,
      insufficient_history_count: 0,
      items: [
        {
          rank: 1,
          stock_code: "000002.SZ",
          stock_name: "Beta",
          sector_code: "801002",
          sector_name: "新能源车",
          concepts: ["robotics"],
          close: 10,
          ma20: 9.8,
          ma60: 9.2,
          ma120: 8.5,
          return_20d: 0.12,
          return_60d: 0.2,
          return_120d: 0.28,
          close_to_ma20: 0.02,
          amount_ratio: 1.4,
          pctchange: 1.2,
          turn: 3.1,
          amplitude: 2.4,
          hlimitedays: null,
          score: 0.77,
        },
      ],
    },
    mean_reversion_candidates: {
      as_of_date: "2026-04-29",
      formula_version: "rv_mean_reversion_v1",
      market_state: "WARM",
      input_stock_count: 1,
      candidate_count: 1,
      excluded_stock_count: 0,
      insufficient_history_count: 0,
      items: [
        {
          rank: 1,
          stock_code: "000003.SZ",
          stock_name: "Gamma",
          sector_code: "801003",
          sector_name: "医药",
          close: 7.2,
          drawdown_20d: -0.18,
          drawdown_60d: -0.32,
          ma5: 7,
          ma10: 7.5,
          close_strength: 0.24,
          vol_ratio: 1.8,
          score: 0.71,
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
          stock_code: "000004.SZ",
          stock_name: "Delta",
          reason: "2d_below_ema10",
          entry_cost: 12,
          bars_since_entry: 5,
          latest_close: 10.8,
          latest_ema10: 11.2,
          prior_close: 11.1,
          prior_ema10: 11.3,
        },
      ],
      watch_items: [],
    },
    ...overrides,
  };
}

function queue(summary: ReturnType<typeof buildStockAnalysisKlineRadar>, key: string) {
  const found = summary.queues.find((item) => item.key === key);
  if (!found) throw new Error(`Missing queue ${key}`);
  return found;
}

describe("buildStockAnalysisKlineRadar", () => {
  it("derives k-line radar queues from the governed strategy snapshot", () => {
    const summary = buildStockAnalysisKlineRadar(buildPayload());

    expect(summary.asOfDate).toBe("2026-04-29");
    expect(summary.marketGateState).toBe("WARM");
    expect(summary.totalCount).toBe(4);
    expect(summary.opportunityCount).toBe(3);
    expect(summary.riskTriggerCount).toBe(1);
    expect(summary.riskWatchCount).toBe(0);
    expect(summary.topology).toMatchObject({
      moduleCount: 4,
      stockCount: 4,
      edgeCount: 9,
      multiSignalStockCount: 0,
    });
    expect(summary.topology.nodes).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "gate:market", kind: "gate" }),
        expect.objectContaining({ id: "module:stock_candidates", kind: "module" }),
        expect.objectContaining({ id: "queue:breakout", kind: "queue" }),
        expect.objectContaining({ id: "stock:000001.SZ", kind: "stock" }),
      ]),
    );
    expect(summary.topology.edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ from: "gate:market", to: "queue:mean_reversion", kind: "gates" }),
        expect.objectContaining({ from: "module:stock_candidates", to: "queue:breakout", kind: "feeds" }),
        expect.objectContaining({ from: "queue:risk_exit", to: "stock:000004.SZ", kind: "routes" }),
      ]),
    );
    expect(queue(summary, "breakout").items[0]).toMatchObject({
      stockCode: "000001.SZ",
      signalLabel: "平台突破",
      detailSource: "livermore",
    });
    expect(queue(summary, "trend_continuation").items[0]).toMatchObject({
      stockCode: "000002.SZ",
      detailSource: "fresh_trend_watchlist",
    });
    expect(queue(summary, "breakout").items[0]?.sourceModule).toBe("stock_candidates");
    expect(queue(summary, "mean_reversion").items[0]).toMatchObject({
      stockCode: "000003.SZ",
      detailSource: "mean_reversion",
    });
    expect(summary.focusItems[0]).toMatchObject({
      stockCode: "000004.SZ",
      queueKey: "risk_exit",
    });
  });

  it("pauses mean-reversion radar when market gate is not WARM", () => {
    const summary = buildStockAnalysisKlineRadar(
      buildPayload({
        market_gate: {
          state: "OFF",
          exposure: 0,
          passed_conditions: 0,
          available_conditions: 2,
          required_conditions: 4,
          conditions: [],
        },
      }),
    );

    expect(queue(summary, "mean_reversion").count).toBe(0);
    expect(summary.totalCount).toBe(3);
    expect(summary.opportunityCount).toBe(2);
    expect(summary.topology.edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ from: "gate:market", to: "queue:mean_reversion", label: "blocked:OFF" }),
      ]),
    );
  });

  it("marks stocks that are reached by multiple radar paths", () => {
    const payload = buildPayload();
    payload.fresh_trend_watchlist!.items[0] = {
      ...payload.fresh_trend_watchlist!.items[0],
      stock_code: "000001.SZ",
      stock_name: "Alpha",
    };

    const summary = buildStockAnalysisKlineRadar(payload);

    expect(summary.topology.multiSignalStockCount).toBe(1);
    expect(summary.topology.stockCount).toBe(3);
    expect(
      summary.topology.edges.filter((edge) => edge.kind === "routes" && edge.to === "stock:000001.SZ"),
    ).toHaveLength(2);
  });

  it("distinguishes missing hybrid evidence from a measured zero score", () => {
    const summary = buildStockAnalysisKlineRadar(
      buildPayload({
        hybrid_fusion_candidates: {
          as_of_date: "2026-04-29",
          formula_version: "rv_hybrid_fusion_candidates_v4",
          market_state: "WARM",
          observation_only: true,
          candidate_count: 4,
          items: [
            {
              rank: 1,
              stock_code: "000005.SZ",
              stock_name: "Factor Only",
              sector_code: "801005",
              sector_name: "Utilities",
              fusion_score: 0.35,
              cycle_score: 0.45,
              lifecourt_proxy_score: 0.18,
              attention_score: 0,
              price_confirm_score: 0,
              crowding_penalty: 0,
              confidence: "low",
              reason: "Factor-only evidence.",
              evidence: { source_kinds: ["factor_screen"] },
            },
            {
              rank: 2,
              stock_code: "000006.SZ",
              stock_name: "Observed Zero",
              sector_code: "801006",
              sector_name: "Industrials",
              fusion_score: 0.34,
              cycle_score: 0.44,
              lifecourt_proxy_score: 0.17,
              attention_score: 0,
              price_confirm_score: 0,
              crowding_penalty: 0,
              confidence: "low",
              reason: "Sources present with measured zero scores.",
              evidence: { source_kinds: ["stock_candidate", "factor_screen", "theme_breakout"] },
            },
            {
              rank: 3,
              stock_code: "000007.SZ",
              stock_name: "Unknown Sources",
              sector_code: "801007",
              sector_name: "Materials",
              fusion_score: 0.33,
              cycle_score: 0.43,
              lifecourt_proxy_score: 0.16,
              attention_score: 0,
              price_confirm_score: 0,
              crowding_penalty: 0,
              confidence: "low",
              reason: "Evidence source kinds were not returned.",
              evidence: {},
            },
            {
              rank: 4,
              stock_code: "000008.SZ",
              stock_name: "Invalid Sources",
              sector_code: "801008",
              sector_name: "Chemicals",
              fusion_score: 0.32,
              cycle_score: 0.42,
              lifecourt_proxy_score: 0.15,
              attention_score: 0,
              price_confirm_score: 0,
              crowding_penalty: 0,
              confidence: "low",
              reason: "Evidence source kinds used an invalid scalar.",
              evidence: { source_kinds: "stock_candidate" as unknown as string[] },
            },
          ],
        },
      }),
    );
    const trendItems = queue(summary, "trend_continuation").items;
    const factorOnly = trendItems.find((item) => item.stockCode === "000005.SZ");
    const observedZero = trendItems.find((item) => item.stockCode === "000006.SZ");
    const unknownSources = trendItems.find((item) => item.stockCode === "000007.SZ");
    const invalidSources = trendItems.find((item) => item.stockCode === "000008.SZ");

    expect(factorOnly?.evidence).toEqual(["价格确认 待补证", "关注度 待补证", "拥挤惩罚 待补证"]);
    expect(observedZero?.evidence).toEqual(["价格确认 0.00", "关注度 0.00", "拥挤惩罚 0.00"]);
    expect(unknownSources?.evidence).toEqual(["价格确认 待补证", "关注度 待补证", "拥挤惩罚 待补证"]);
    expect(invalidSources?.evidence).toEqual(["价格确认 待补证", "关注度 待补证", "拥挤惩罚 待补证"]);
  });

  it("keeps evidence-only hybrid rows out of primary opportunity counts", () => {
    const summary = buildStockAnalysisKlineRadar(
      buildPayload({
        hybrid_fusion_candidates: {
          as_of_date: "2026-04-29",
          formula_version: "rv_hybrid_fusion_candidates_v4",
          market_state: "WARM",
          observation_only: true,
          candidate_count: 1,
          items: [
            {
              rank: 1,
              stock_code: "000005.SZ",
              stock_name: "Factor Only",
              sector_code: "801005",
              sector_name: "Utilities",
              fusion_score: 0.35,
              cycle_score: 0.45,
              lifecourt_proxy_score: 0.18,
              attention_score: 0,
              price_confirm_score: 0,
              crowding_penalty: 0,
              confidence: "low",
              reason: "Factor-only evidence.",
              evidence: { source_kinds: ["factor_screen"] },
            },
          ],
        },
        module_states: [
          {
            key: "hybrid_fusion",
            state: "degraded",
            render_mode: "evidence_only",
            source_date: "2026-04-29",
            lag_days: 0,
            threshold_days: null,
            reasons: ["Price confirmation is missing."],
            evidence_scope: "detail",
            excludes_from_primary: true,
          },
        ],
      }),
    );

    expect(summary.opportunityCount).toBe(3);
    expect(summary.totalCount).toBe(4);
    expect(queue(summary, "trend_continuation").items).not.toEqual(
      expect.arrayContaining([expect.objectContaining({ stockCode: "000005.SZ" })]),
    );
    expect(summary.pendingEvidenceItems).toEqual([
      expect.objectContaining({ stockCode: "000005.SZ", signalLabel: "待补证观察" }),
    ]);
    expect(summary.focusItems).not.toEqual(
      expect.arrayContaining([expect.objectContaining({ stockCode: "000005.SZ" })]),
    );
  });

  it("reports unsupported risk exit as unavailable instead of zero", () => {
    const summary = buildStockAnalysisKlineRadar(
      buildPayload({
        supported_outputs: ["market_gate", "stock_candidates"],
        unsupported_outputs: [
          {
            key: "risk_exit",
            reason: "livermore_position_snapshot has no ACTIVE A-share rows.",
          },
        ],
        risk_exit: undefined,
      }),
    );

    expect(summary.riskTriggerCount).toBeNull();
    expect(summary.riskWatchCount).toBeNull();
    expect(summary.riskUnavailableReason).toBe("持仓快照缺失");
    expect(queue(summary, "risk_exit").count).toBe(0);
  });

  it("lets unsupported win over a contradictory risk payload", () => {
    const summary = buildStockAnalysisKlineRadar(
      buildPayload({
        unsupported_outputs: [
          {
            key: "risk_exit",
            reason: "livermore_position_snapshot has no ACTIVE A-share rows.",
          },
        ],
      }),
    );

    expect(summary.riskTriggerCount).toBeNull();
    expect(summary.riskWatchCount).toBeNull();
    expect(summary.riskUnavailableReason).toBe("持仓快照缺失");
    expect(queue(summary, "risk_exit").count).toBe(0);
    expect(summary.focusItems).not.toEqual(
      expect.arrayContaining([expect.objectContaining({ queueKey: "risk_exit" })]),
    );
  });

  it("keeps governed trigger and watch counts separate from visible risk rows", () => {
    const payload = buildPayload();
    payload.risk_exit = {
      ...payload.risk_exit!,
      signal_count: 0,
      items: [],
      watch_items: [
        {
          stock_code: "000008.SZ",
          stock_name: "Watch Only",
          entry_cost: 12,
          bars_since_entry: 5,
          latest_close: 11.1,
          latest_ema10: 11.2,
          prior_close: 11.3,
          prior_ema10: 11.1,
          exit_watch_price: 11.2,
          triggered: false,
        },
      ],
    };

    const summary = buildStockAnalysisKlineRadar(payload);

    expect(summary.riskTriggerCount).toBe(0);
    expect(summary.riskWatchCount).toBe(1);
    expect(queue(summary, "risk_exit").count).toBe(1);
  });
});
