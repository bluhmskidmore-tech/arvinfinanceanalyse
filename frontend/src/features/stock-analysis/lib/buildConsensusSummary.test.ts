import { describe, expect, it } from "vitest";

import type { LivermoreModuleState, LivermoreOutputKey, LivermoreStrategyPayload } from "../../../api/contracts";
import { buildConsensusSummary } from "./buildConsensusSummary";

const LIVERMORE_OUTPUT_KEYS: LivermoreOutputKey[] = [
  "market_gate",
  "sector_rank",
  "stock_candidates",
  "mean_reversion_candidates",
  "factor_screen_candidates",
  "theme_breakout",
  "hybrid_fusion",
  "risk_exit",
];

function readyModuleStates(): LivermoreModuleState[] {
  return LIVERMORE_OUTPUT_KEYS.map((key) => ({
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

function payloadForConsensus(): LivermoreStrategyPayload {
  return {
    module_states: readyModuleStates(),
    stock_candidates: {
      items: [
        {
          stock_code: "000001.SZ",
          stock_name: "TrendAndReversion",
          sector_name: "SectorA",
          rank: 1,
        },
        {
          stock_code: "000002.SZ",
          stock_name: "TrendAndFactor",
          sector_name: "SectorB",
          rank: 2,
        },
      ],
    },
    mean_reversion_candidates: {
      items: [
        {
          stock_code: "000001.SZ",
          stock_name: "TrendAndReversion",
          sector_name: "SectorA",
          rank: 1,
        },
        {
          stock_code: "000002.SZ",
          stock_name: "TrendAndFactor",
          sector_name: "SectorB",
          rank: 3,
        },
      ],
    },
    factor_screen_candidates: {
      items: [
        {
          stock_code: "000002.SZ",
          stock_name: "TrendAndFactor",
          sector_name: "SectorB",
          rank: 1,
        },
      ],
    },
    hybrid_fusion_candidates: {
      items: [
        {
          stock_code: "000002.SZ",
          stock_name: "TrendAndFactor",
          sector_name: "SectorB",
          rank: 1,
        },
        {
          stock_code: "000003.SZ",
          stock_name: "FusionOnly",
          sector_name: "SectorC",
          rank: 2,
        },
      ],
    },
  } as unknown as LivermoreStrategyPayload;
}

describe("buildConsensusSummary", () => {
  it("does not let mean reversion create T+5 consensus by itself", () => {
    const summary = buildConsensusSummary(payloadForConsensus());

    expect(summary.doubleCount).toBe(1);
    expect(summary.tripleCount).toBe(1);
    expect(summary.strategyCounts.hybrid_fusion).toBe(2);
    expect(summary.strategyCounts.mean_reversion).toBe(2);
    expect(summary.totalUnion).toBe(3);
    expect(summary.items).toHaveLength(1);
    expect(summary.items[0]).toMatchObject({
      stockCode: "000002.SZ",
      consensusCount: 3,
      livermoreRank: 2,
      meanReversionRank: 3,
      factorScreenRank: 1,
      hybridFusionRank: 1,
    });
    expect(summary.items[0].strategies).toEqual(["hybrid_fusion", "livermore", "factor_screen"]);
  });

  it("excludes evidence-only modules from primary consensus", () => {
    const payload = {
      ...payloadForConsensus(),
      module_states: readyModuleStates().map((state) => {
        if (state.key === "factor_screen_candidates") {
          return {
            ...state,
            state: "degraded",
            render_mode: "evidence_only",
            source_date: "2026-05-29",
            lag_days: 10,
            threshold_days: 3,
            reasons: ["factor snapshot is stale"],
            evidence_scope: "detail",
            excludes_from_primary: true,
          };
        }
        if (state.key === "hybrid_fusion") {
          return {
            ...state,
            state: "degraded",
            render_mode: "evidence_only",
            source_date: "2026-05-29",
            lag_days: 10,
            threshold_days: 3,
            reasons: ["hybrid fusion is factor-only"],
            evidence_scope: "detail",
            excludes_from_primary: true,
          };
        }
        return state;
      }),
    } as unknown as LivermoreStrategyPayload;

    const summary = buildConsensusSummary(payload);

    expect(summary.strategyCounts.factor_screen).toBe(0);
    expect(summary.strategyCounts.hybrid_fusion).toBe(0);
    expect(summary.doubleCount).toBe(0);
    expect(summary.items).toHaveLength(0);
    expect(summary.totalUnion).toBe(2);
  });

  it("fails closed when module states are missing", () => {
    const payload = {
      ...payloadForConsensus(),
      module_states: undefined,
    } as unknown as LivermoreStrategyPayload;

    const summary = buildConsensusSummary(payload);

    expect(summary.strategyCounts.livermore).toBe(0);
    expect(summary.strategyCounts.factor_screen).toBe(0);
    expect(summary.strategyCounts.hybrid_fusion).toBe(0);
    expect(summary.hasAnyStrategy).toBe(false);
    expect(summary.items).toHaveLength(0);
  });
});
