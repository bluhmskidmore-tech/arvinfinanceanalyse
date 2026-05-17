import { describe, expect, it } from "vitest";

import type { LivermoreStrategyPayload } from "../../../api/contracts";
import { buildConsensusSummary } from "./buildConsensusSummary";

function payloadForConsensus(): LivermoreStrategyPayload {
  return {
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
});
