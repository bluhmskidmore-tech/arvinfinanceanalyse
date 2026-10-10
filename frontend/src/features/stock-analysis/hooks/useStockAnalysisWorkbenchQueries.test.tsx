import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../../api/client";
import { useStockAnalysisWorkbenchQueries } from "./useStockAnalysisWorkbenchQueries";

vi.mock("../../../hooks/useDeferredSectionSeen", () => ({
  useDeferredSectionSeen: () => ({ ref: vi.fn(), seen: true }),
}));

function workbenchEnvelope(canReviewCandidates: boolean) {
  return {
    result_meta: {
      formal_use_allowed: false,
    },
    result: {
      as_of_date: "2026-09-16",
      formal_use_allowed: false,
      decision_summary: {
        can_review_candidates: canReviewCandidates,
      },
      pretrade_qualification: {
        status: "unavailable",
        reason: "system_read_generation_missing",
      },
      modules: {
        main: {
          status: "ready",
          endpoint: "/ui/market-data/livermore",
          result: {
            as_of_date: "2026-09-16",
            basis: "analytical",
            market_gate: { state: "WARM" },
            supported_outputs: [],
          },
        },
      },
    },
  };
}

function buildClient(canReviewCandidates: boolean) {
  return {
    getStockAnalysisWorkbench: vi.fn().mockResolvedValue(workbenchEnvelope(canReviewCandidates)),
    getLivermoreSignalConfluence: vi.fn(),
    getLivermoreStrategyScore: vi.fn(),
    getLivermoreStrategyOptimization: vi.fn(),
    getLivermoreCandidateHistory: vi.fn().mockResolvedValue({ result: null }),
    getLivermoreCycleProxyBacktest: vi.fn(),
    getLivermoreCandidateHistoryPortfolioBacktest: vi.fn(),
  };
}

function wrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return function QueryWrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useStockAnalysisWorkbenchQueries", () => {
  it("allows user-requested candidate history for a reviewable read-only queue and keeps formal research queries closed", async () => {
    const client = buildClient(true);
    const { result } = renderHook(
      () =>
        useStockAnalysisWorkbenchQueries({
          client: client as unknown as ApiClient,
          asOfOverride: "2026-09-16",
          candidateHistoryEndpointRequested: true,
          cycleProxyEndpointRequested: true,
          portfolioProxyEndpointRequested: true,
          firstScreenPriorityRequested: true,
          firstScreenOptimizationRequested: true,
        }),
      { wrapper: wrapper() },
    );

    await waitFor(() => expect(result.current.strategyQuery.isSuccess).toBe(true));
    await waitFor(() => expect(client.getLivermoreCandidateHistory).toHaveBeenCalledOnce());

    expect(result.current.researchReviewReady).toBe(true);
    expect(result.current.pretradeDecisionReady).toBe(false);
    expect(client.getLivermoreSignalConfluence).not.toHaveBeenCalled();
    expect(client.getLivermoreStrategyScore).not.toHaveBeenCalled();
    expect(client.getLivermoreStrategyOptimization).not.toHaveBeenCalled();
    expect(client.getLivermoreCycleProxyBacktest).not.toHaveBeenCalled();
    expect(client.getLivermoreCandidateHistoryPortfolioBacktest).not.toHaveBeenCalled();
  });

  it("keeps candidate history closed when the workbench does not authorize candidate review", async () => {
    const client = buildClient(false);
    const { result } = renderHook(
      () =>
        useStockAnalysisWorkbenchQueries({
          client: client as unknown as ApiClient,
          asOfOverride: "2026-09-16",
          candidateHistoryEndpointRequested: true,
          cycleProxyEndpointRequested: false,
          portfolioProxyEndpointRequested: false,
          firstScreenPriorityRequested: false,
          firstScreenOptimizationRequested: false,
        }),
      { wrapper: wrapper() },
    );

    await waitFor(() => expect(result.current.strategyQuery.isSuccess).toBe(true));

    expect(result.current.researchReviewReady).toBe(false);
    expect(client.getLivermoreCandidateHistory).not.toHaveBeenCalled();
  });
});
