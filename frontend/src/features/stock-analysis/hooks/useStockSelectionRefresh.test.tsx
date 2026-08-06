import { act, renderHook } from "@testing-library/react";
import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../../../api/client";
import { useStockSelectionRefresh } from "./useStockSelectionRefresh";

describe("useStockSelectionRefresh", () => {
  it("polls a queued gate supplement refresh to terminal completion", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient();
    const gateRefreshSpy = vi.spyOn(client, "refreshGateSupplement");
    const gateRefreshStatusSpy = vi.spyOn(client, "getLivermoreGateSupplementRefreshStatus");
    const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() =>
      useStockSelectionRefresh({
        client,
        queryClient,
        asOfDate: "2026-04-29",
      }),
    );

    await act(async () => {
      await result.current.refreshStockSelection();
    });

    expect(gateRefreshSpy).toHaveBeenCalledWith({ asOfDate: "2026-04-29" });
    expect(gateRefreshStatusSpy).toHaveBeenCalledWith(
      "livermore_gate_supplement_refresh:2026-04-29:mock",
    );
    expect(result.current.refreshStatusTone).toBe("positive");
    expect(result.current.refreshStatusMessage).toContain("选股已重新计算");
    expect(result.current.refreshStatusMessage).toContain("门禁补充已刷新 15 行");
    expect(result.current.refreshStatusMessage).toContain(
      "livermore_gate_supplement_refresh:2026-04-29:mock",
    );
    expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ["stock-analysis"] });

    queryClient.clear();
  });

  it("stops gate supplement polling on failed terminal status", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient();
    const gateRefreshSpy = vi.spyOn(client, "refreshGateSupplement").mockResolvedValue({
      status: "queued",
      run_id: "livermore_gate_supplement_refresh:2026-04-29:stale",
      trigger_mode: "async",
      as_of_date: "2026-04-29",
      lookback_days: 30,
      queued_at: "2026-04-29T09:00:00Z",
      idempotency_replay: false,
      idempotency_key: null,
    });
    const gateRefreshStatusSpy = vi
      .spyOn(client, "getLivermoreGateSupplementRefreshStatus")
      .mockResolvedValue({
        status: "failed",
        run_id: "livermore_gate_supplement_refresh:2026-04-29:stale",
        trigger_mode: "terminal",
        as_of_date: "2026-04-29",
        lookback_days: 30,
        queued_at: "2026-04-29T09:00:00Z",
        finished_at: "2026-04-29T09:05:00Z",
        failure_category: "stale_inflight",
        error_message: "Marked stale Livermore gate-supplement refresh as failed.",
        idempotency_replay: false,
        idempotency_key: null,
      });
    const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() =>
      useStockSelectionRefresh({
        client,
        queryClient,
        asOfDate: "2026-04-29",
      }),
    );

    await act(async () => {
      await result.current.refreshStockSelection();
    });

    expect(gateRefreshSpy).toHaveBeenCalledWith({ asOfDate: "2026-04-29" });
    expect(gateRefreshStatusSpy).toHaveBeenCalledTimes(1);
    expect(result.current.refreshStatusTone).toBe("negative");
    expect(result.current.refreshStatusMessage).toContain("stale_inflight");
    expect(invalidateQueriesSpy).not.toHaveBeenCalled();

    queryClient.clear();
  });
});
