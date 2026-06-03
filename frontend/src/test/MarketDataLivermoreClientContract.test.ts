import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../api/client";
import { createRealMarketDataClient } from "../api/marketDataClient";
import type {
  ApiEnvelope,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyScorePayload,
} from "../api/contracts";

function okEnvelope(result: unknown): Response {
  const body: ApiEnvelope<unknown> = {
    result,
    result_meta: {
      basis: "analytical",
      formal_use_allowed: false,
      result_kind: "market_data.livermore.test",
      trace_id: "test",
      as_of_date: null,
      generated_at: "2026-06-03T00:00:00Z",
      source_version: "sv_test",
      vendor_version: "vv_test",
      rule_version: "rv_test",
      cache_version: "cv_test",
      scenario_flag: false,
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      filters_applied: {},
      tables_used: [],
      evidence_rows: 0,
    },
  };
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Livermore market-data client contract", () => {
  it("keeps T+10 accepted for strategy score and optimization client calls", () => {
    const scoreOptions: Parameters<ApiClient["getLivermoreStrategyScore"]>[0] = {
      primaryHorizon: "return_10d",
    };
    const optimizationOptions: Parameters<ApiClient["getLivermoreStrategyOptimization"]>[0] = {
      primaryHorizon: "return_10d",
    };
    const scorePrimaryHorizon: LivermoreStrategyScorePayload["primary_horizon"] = "return_10d";
    const optimizationPrimaryHorizon: LivermoreStrategyOptimizationPayload["primary_horizon"] = "return_10d";

    expect(scoreOptions?.primaryHorizon).toBe("return_10d");
    expect(optimizationOptions?.primaryHorizon).toBe("return_10d");
    expect(scorePrimaryHorizon).toBe("return_10d");
    expect(optimizationPrimaryHorizon).toBe("return_10d");
  });

  it("calls the Livermore advanced read-only routes with expected query parameters", async () => {
    const fetchImpl = vi.fn(async () => okEnvelope({}));
    const client = createRealMarketDataClient({
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });

    await client.getLivermoreStrategyOptimization({
      snapshotFrom: "2026-05-01",
      snapshotTo: "2026-05-31",
      currentMarketState: "HOT",
      minSample: 12,
      primaryHorizon: "return_10d",
    });
    await client.getLivermoreCycleProxyBacktest({
      snapshotFrom: "2026-05-01",
      snapshotTo: "2026-05-31",
    });
    await client.getLivermoreCandidateHistoryPortfolioBacktest({
      snapshotFrom: "2026-05-01",
      snapshotTo: "2026-05-31",
    });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/ui/market-data/livermore/strategy-optimization?snapshot_from=2026-05-01&snapshot_to=2026-05-31&current_market_state=HOT&min_sample=12&primary_horizon=return_10d",
      { headers: { Accept: "application/json" } },
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/ui/market-data/livermore/cycle-proxy-backtest?snapshot_from=2026-05-01&snapshot_to=2026-05-31",
      { headers: { Accept: "application/json" } },
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/ui/market-data/livermore/candidate-history-portfolio-backtest?snapshot_from=2026-05-01&snapshot_to=2026-05-31",
      { headers: { Accept: "application/json" } },
    );
  });
});
