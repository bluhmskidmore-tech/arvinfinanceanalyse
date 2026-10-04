import type { PropsWithChildren } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
  useQueries,
  useQuery,
} from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import type { ProductCategoryRefreshPayload } from "../../../api/contracts";
import { useProductCategoryRefresh } from "./useProductCategoryRefresh";

const completed: ProductCategoryRefreshPayload = {
  status: "completed",
  run_id: "product-category-refresh-test",
  job_name: "product_category_pnl",
  trigger_mode: "async",
  cache_key: "product_category_pnl.formal",
};

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity, gcTime: Infinity },
    },
  });
  const client = {
    mode: "mock" as const,
    refreshProductCategoryPnl: vi.fn(async () => completed),
    getProductCategoryRefreshStatus: vi.fn(async () => completed),
  };
  function wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return { queryClient, client, wrapper };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

describe("product-category refresh data synchronization", () => {
  it("updates every enabled page family once while isolating other modes and features", async () => {
    const { client, wrapper, queryClient } = setup();
    let version = 1;
    const keys = [
      ["product-category-pnl", "dates", "mock"],
      ["product-category-pnl", "baseline", "mock", "2026-02-28", "monthly"],
      ["product-category-pnl", "adjustments", "mock", "2026-02-28"],
      ["product-category-pnl", "liability-matrix-history", "mock", "2026-01-31", "ytd", ""],
      ["product-category-pnl", "trend-history-batch", "mock", "2026-01-31", "monthly", ""],
      ["product-category-pnl", "management-history-batch", "mock", "2026-01-31"],
      ["product-category-pnl", "scenario", "mock", "2026-02-28", "monthly", "1.6"],
      ["product-category-pnl", "scenario-sensitivity", "mock", "2026-02-28", "monthly", "1.6"],
      ["product-category-pnl", "trend-history-attribution-batch", "mock", "2026-01-31", "mom"],
    ];
    const reads = keys.map(() => vi.fn(async () => version));
    const attributionKey = ["product-category-pnl", "attribution", "mock", "2026-02-28", "mom"];
    const attributionRead = vi.fn(async () => version);
    const otherKeys = [
      ["product-category-pnl", "baseline", "real", "2026-02-28", "monthly"],
      ["monthly-operating-analysis", "baseline", "mock"],
      // Cross-page caches have separate owners; this page-local slice must not
      // guess their dependency rules from a matching word inside their keys.
      ["operations-entry", "product-category-pnl", "mock", "2026-02-28"],
    ];
    const otherReads = otherKeys.map(() => vi.fn(async () => version));
    const { result } = renderHook(() => ({
      refresh: useProductCategoryRefresh(client),
      queries: useQueries({ queries: keys.map((queryKey, i) => ({ queryKey, queryFn: reads[i]! })) }),
      attribution: useQuery({ queryKey: attributionKey, queryFn: attributionRead }),
      managementAttribution: useQuery({ queryKey: attributionKey, queryFn: attributionRead }),
      other: useQueries({ queries: otherKeys.map((queryKey, i) => ({ queryKey, queryFn: otherReads[i]! })) }),
    }), { wrapper });
    await waitFor(() => expect(result.current.queries.every((query) => query.data === 1)).toBe(true));
    await waitFor(() => expect(result.current.other.every((query) => query.data === 1)).toBe(true));

    version = 2;
    await act(async () => { await result.current.refresh.runRefreshWorkflow(); });

    await waitFor(() => expect(result.current.queries.every((query) => query.data === 2)).toBe(true));
    expect(result.current.attribution.data).toBe(2);
    expect(result.current.managementAttribution.data).toBe(2);
    for (const read of [...reads, attributionRead]) expect(read).toHaveBeenCalledTimes(2);
    for (const read of otherReads) expect(read).toHaveBeenCalledTimes(1);
    for (const key of otherKeys) expect(queryClient.getQueryState(key)?.isInvalidated).toBe(false);
  });

  it("keeps closed panels lazy and refreshes their stale cache when enabled later", async () => {
    const { client, wrapper, queryClient } = setup();
    const cachedKey = ["product-category-pnl", "trend-history-batch", "mock", "2026-01-31", "monthly", ""];
    const unrequestedKey = ["product-category-pnl", "scenario-sensitivity", "mock", "2026-02-28", "monthly", "1.6"];
    const inactiveKey = ["product-category-pnl", "baseline", "mock", "2025-12-31", "monthly"];
    queryClient.setQueryData(cachedKey, 1);
    queryClient.setQueryData(inactiveKey, 1);
    const historyRead = vi.fn(async () => 2);
    const scenarioRead = vi.fn(async () => 2);
    const { result, rerender } = renderHook(({ enabled }) => ({
      refresh: useProductCategoryRefresh(client),
      history: useQuery({ queryKey: cachedKey, queryFn: historyRead, enabled }),
      scenario: useQuery({ queryKey: unrequestedKey, queryFn: scenarioRead, enabled }),
    }), { wrapper, initialProps: { enabled: false } });

    await act(async () => { await result.current.refresh.runRefreshWorkflow(); });

    expect(historyRead).not.toHaveBeenCalled();
    expect(scenarioRead).not.toHaveBeenCalled();
    expect(queryClient.getQueryState(cachedKey)?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(inactiveKey)?.isInvalidated).toBe(true);
    expect(result.current.history.data).toBe(1);
    rerender({ enabled: true });
    await waitFor(() => expect(result.current.history.data).toBe(2));
    await waitFor(() => expect(result.current.scenario.data).toBe(2));
    expect(historyRead).toHaveBeenCalledTimes(1);
    expect(scenarioRead).toHaveBeenCalledTimes(1);
  });

  it("synchronizes the date and scenario selected at task completion", async () => {
    const { client, wrapper, queryClient } = setup();
    const terminal = deferred<ProductCategoryRefreshPayload>();
    client.refreshProductCategoryPnl.mockResolvedValue({ ...completed, status: "queued" });
    client.getProductCategoryRefreshStatus.mockReturnValue(terminal.promise);
    const firstKey = ["product-category-pnl", "baseline", "mock", "2026-01-31", "monthly"];
    const nextKey = ["product-category-pnl", "scenario", "mock", "2026-02-28", "monthly", "1.6"];
    queryClient.setQueryData(firstKey, 1);
    queryClient.setQueryData(nextKey, 1);
    const read = vi.fn(async () => 2);
    const { result, rerender } = renderHook(({ queryKey }) => ({
      refresh: useProductCategoryRefresh(client),
      query: useQuery({ queryKey, queryFn: read }),
    }), { wrapper, initialProps: { queryKey: firstKey } });
    let work!: Promise<void>;
    act(() => { work = result.current.refresh.runRefreshWorkflow(); });
    await waitFor(() => expect(client.getProductCategoryRefreshStatus).toHaveBeenCalledOnce());
    await waitFor(() => expect(result.current.refresh.isRefreshing).toBe(true));
    rerender({ queryKey: nextKey });

    await act(async () => { terminal.resolve(completed); await work; });

    await waitFor(() => expect(result.current.query.data).toBe(2));
    expect(queryClient.getQueryData(firstKey)).toBe(1);
    expect(queryClient.getQueryState(firstKey)?.isInvalidated).toBe(true);
    expect(read).toHaveBeenCalledOnce();
    await waitFor(() => expect(result.current.refresh.isRefreshing).toBe(false));
  });

  it("discards a pre-refresh first response instead of accepting it as fresh data", async () => {
    const { client, wrapper } = setup();
    const oldRead = deferred<number>();
    const read = vi.fn(async () => 2).mockImplementationOnce(() => oldRead.promise);
    const { result } = renderHook(() => ({
      refresh: useProductCategoryRefresh(client),
      query: useQuery({
        queryKey: ["product-category-pnl", "baseline", "mock", "2026-02-28", "monthly"],
        queryFn: read,
      }),
    }), { wrapper });
    await waitFor(() => expect(read).toHaveBeenCalledOnce());

    await act(async () => { await result.current.refresh.runRefreshWorkflow(); });
    await waitFor(() => expect(result.current.query.data).toBe(2));
    await act(async () => { oldRead.resolve(1); await oldRead.promise; });

    expect(read).toHaveBeenCalledTimes(2);
    expect(result.current.query.data).toBe(2);
  });

  it("preserves cached reads on task failure and clears the error on a successful retry", async () => {
    const { client, wrapper, queryClient } = setup();
    const queryKey = ["product-category-pnl", "baseline", "mock", "2026-02-28", "monthly"];
    queryClient.setQueryData(queryKey, 1);
    client.refreshProductCategoryPnl.mockResolvedValueOnce({
      ...completed, status: "failed", detail: "materialization failed",
    });
    const read = vi.fn(async () => 2);
    const { result } = renderHook(() => ({
      refresh: useProductCategoryRefresh(client),
      query: useQuery({ queryKey, queryFn: read }),
    }), { wrapper });

    await act(async () => {
      await expect(result.current.refresh.runRefreshWorkflow()).rejects.toThrow("materialization failed");
    });
    await waitFor(() => expect(result.current.refresh.refreshError).toBe("materialization failed"));
    expect(read).not.toHaveBeenCalled();
    expect(queryClient.getQueryState(queryKey)?.isInvalidated).toBe(false);
    expect(result.current.refresh.lastRefreshRunId).toBe(completed.run_id);

    await act(async () => { await result.current.refresh.runRefreshWorkflow(); });
    await waitFor(() => expect(result.current.refresh.refreshError).toBeNull());
    expect(result.current.query.data).toBe(2);
    expect(read).toHaveBeenCalledOnce();
  });

  it("keeps read failure on the query error surface after successful materialization", async () => {
    const { client, wrapper, queryClient } = setup();
    const queryKey = ["product-category-pnl", "adjustments", "mock", "2026-02-28"];
    queryClient.setQueryData(queryKey, 1);
    const { result } = renderHook(() => ({
      refresh: useProductCategoryRefresh(client),
      query: useQuery({ queryKey, queryFn: async () => { throw new Error("read unavailable"); } }),
    }), { wrapper });

    await act(async () => { await result.current.refresh.runRefreshWorkflow(); });

    await waitFor(() => expect(result.current.query.isError).toBe(true));
    expect(result.current.query.error?.message).toBe("read unavailable");
    expect(result.current.refresh.refreshError).toBeNull();
    await waitFor(() => expect(result.current.refresh.isRefreshing).toBe(false));
  });
});
