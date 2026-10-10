import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../../../api/client";
import { useStockSelectionRefresh } from "./useStockSelectionRefresh";

describe("useStockSelectionRefresh", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("polls a queued choice-stock refresh to completed Livermore closure", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient();
    const refreshStatusSpy = vi.spyOn(client, "getChoiceStockRefreshStatus").mockResolvedValue({
      result_meta: {},
      result: {
        refresh: {
          status: "completed",
          run_id: "choice_stock_refresh:mock",
          livermore_closure_status: "completed",
          history_row_count: 31,
          factor_row_count: 18,
        },
      },
    } as Awaited<ReturnType<typeof client.getChoiceStockRefreshStatus>>);
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

    expect(refreshStatusSpy).toHaveBeenCalledWith("choice_stock_refresh:mock");
    expect(result.current.refreshStatusTone).toBe("positive");
    expect(result.current.refreshStatusMessage).toContain("选股已重新计算并完成闭环");
    expect(result.current.refreshStatusMessage).toContain("choice_stock_refresh:mock");
    expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ["stock-analysis"] });

    queryClient.clear();
  });

  it("keeps failed choice-stock closure evidence and skips refetch", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient();
    vi.spyOn(client, "refreshChoiceStock").mockResolvedValue({
      result_meta: {},
      result: { refresh: { status: "queued", run_id: "choice_stock_refresh:failed" } },
    } as Awaited<ReturnType<typeof client.refreshChoiceStock>>);
    const refreshStatusSpy = vi.spyOn(client, "getChoiceStockRefreshStatus").mockResolvedValue({
      result_meta: {},
      result: {
        refresh: {
          status: "failed",
          run_id: "choice_stock_refresh:failed",
          livermore_closure_status: "failed",
          livermore_closure_reason: "livermore_signal_confluence_not_completed",
          failure_category: "source_unavailable",
        },
      },
    } as Awaited<ReturnType<typeof client.getChoiceStockRefreshStatus>>);
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

    expect(refreshStatusSpy).toHaveBeenCalledTimes(1);
    expect(result.current.refreshStatusTone).toBe("negative");
    expect(result.current.refreshStatusMessage).toContain("livermore_signal_confluence_not_completed");
    expect(result.current.refreshStatusMessage).toContain("choice_stock_refresh:failed");
    expect(invalidateQueriesSpy).not.toHaveBeenCalled();

    queryClient.clear();
  });

  it.each([
    ["no_rows", "warning", "选股刷新无可用数据", "target_date_no_rows"],
    ["blocked", "negative", "选股刷新被阻断", "upstream_not_ready"],
  ] as const)(
    "treats %s as terminal, preserves public evidence, and skips refetch",
    async (terminalStatus, expectedTone, expectedLabel, publicReason) => {
      vi.useFakeTimers();
      const client = createApiClient({ mode: "mock" });
      const queryClient = new QueryClient();
      const terminalResponse = {
        result_meta: {},
        result: {
          refresh: {
            status: terminalStatus,
            run_id: `choice_stock_refresh:${terminalStatus}`,
            livermore_closure_status: terminalStatus,
            livermore_closure_reason: publicReason,
          },
        },
      } as Awaited<ReturnType<typeof client.getChoiceStockRefreshStatus>>;
      const completedResponse = {
        result_meta: {},
        result: {
          refresh: {
            status: "completed",
            run_id: `choice_stock_refresh:${terminalStatus}`,
            livermore_closure_status: "completed",
          },
        },
      } as Awaited<ReturnType<typeof client.getChoiceStockRefreshStatus>>;
      vi.spyOn(client, "refreshChoiceStock").mockResolvedValue({
        result_meta: {},
        result: {
          refresh: {
            status: "queued",
            run_id: `choice_stock_refresh:${terminalStatus}`,
          },
        },
      } as Awaited<ReturnType<typeof client.refreshChoiceStock>>);
      const refreshStatusSpy = vi
        .spyOn(client, "getChoiceStockRefreshStatus")
        .mockResolvedValueOnce(terminalResponse)
        .mockResolvedValueOnce(completedResponse);
      const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

      const { result } = renderHook(() =>
        useStockSelectionRefresh({
          client,
          queryClient,
          asOfDate: "2026-04-29",
        }),
      );

      let refreshPromise = Promise.resolve();
      act(() => {
        refreshPromise = result.current.refreshStockSelection();
      });
      await act(async () => {
        await vi.runAllTimersAsync();
        await refreshPromise;
      });

      expect(refreshStatusSpy).toHaveBeenCalledTimes(1);
      expect(result.current.refreshStatusTone).toBe(expectedTone);
      expect(result.current.refreshStatusMessage).toContain(expectedLabel);
      expect(result.current.refreshStatusMessage).toContain(publicReason);
      expect(result.current.refreshStatusMessage).toContain(`choice_stock_refresh:${terminalStatus}`);
      expect(invalidateQueriesSpy).not.toHaveBeenCalled();

      queryClient.clear();
    },
  );

  it("cancels in-flight polling on unmount and skips post-unmount refetches", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient();
    const refreshSpy = vi.spyOn(client, "refreshChoiceStock").mockResolvedValue({
      result_meta: {},
      result: { refresh: { status: "queued", run_id: "choice_stock_refresh:cancel" } },
    } as Awaited<ReturnType<typeof client.refreshChoiceStock>>);
    const statusSpy = vi.spyOn(client, "getChoiceStockRefreshStatus").mockResolvedValue({
      result_meta: {},
      result: { refresh: { status: "running", run_id: "choice_stock_refresh:cancel" } },
    } as Awaited<ReturnType<typeof client.getChoiceStockRefreshStatus>>);
    const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result, unmount } = renderHook(() =>
      useStockSelectionRefresh({
        client,
        queryClient,
        asOfDate: "2026-04-29",
      }),
    );

    let refreshPromise: Promise<void> = Promise.resolve();
    act(() => {
      refreshPromise = result.current.refreshStockSelection();
    });
    await waitFor(() => expect(statusSpy).toHaveBeenCalledTimes(1));

    unmount();
    // 轮询间隔为 5s：卸载中断后必须立即结束，而不是等计时器走完再继续轮询。
    await refreshPromise;

    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(statusSpy).toHaveBeenCalledTimes(1);
    expect(invalidateQueriesSpy).not.toHaveBeenCalled();

    queryClient.clear();
  });
});
