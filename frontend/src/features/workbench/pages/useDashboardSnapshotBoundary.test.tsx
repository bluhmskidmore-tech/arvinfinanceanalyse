import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  ApiClientProvider,
  createApiClient,
  type ApiClient,
  type DataSourceMode,
} from "../../../api/client";
import { useDashboardSnapshotBoundary } from "./useDashboardSnapshotBoundary";

function createWrapper(client: ApiClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          staleTime: 0,
          gcTime: 0,
          refetchOnWindowFocus: false,
        },
      },
    });

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  };
}

function buildClientWithSnapshotOverride(options: {
  mode: DataSourceMode;
  getHomeSnapshot: ApiClient["getHomeSnapshot"];
}): ApiClient {
  const base = createApiClient({ mode: options.mode });
  return {
    ...base,
    getHomeSnapshot: options.getHomeSnapshot,
  };
}

describe("useDashboardSnapshotBoundary", () => {
  it.each(["same scope", "different date", "different client", "different partial option", "new generation cache"])(
    "restores cached data after remount only for the same read scope: %s",
    async (scope) => {
      const firstDate = "2026-04-30";
      const nextDate = "2026-05-31";
      const mockSource = createApiClient({ mode: "mock" });
      const snapshot = await mockSource.getHomeSnapshot({ reportDate: firstDate });
      snapshot.result.report_date = firstDate;
      let failRead = false;
      const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>(async (options) => {
        if (failRead || options?.reportDate === nextDate) throw new Error("date unavailable");
        return snapshot;
      });
      const client = buildClientWithSnapshotOverride({ mode: "real", getHomeSnapshot });
      const queryClient = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity, retry: false } } });
      const wrapper = (api: ApiClient, cache: QueryClient) =>
        function Wrapper({ children }: { children: ReactNode }) {
          return (
            <QueryClientProvider client={cache}>
              <ApiClientProvider client={api}>{children}</ApiClientProvider>
            </QueryClientProvider>
          );
        };
      const first = renderHook(
        () => useDashboardSnapshotBoundary({ reportDate: firstDate, allowPartial: false }),
        { wrapper: wrapper(client, queryClient) },
      );
      await waitFor(() => expect(first.result.current.snapshotQuery.isSuccess).toBe(true));
      first.unmount();
      failRead = true;

      const nextClient = scope === "different client"
        ? buildClientWithSnapshotOverride({ mode: "real", getHomeSnapshot })
        : client;
      const nextCache = scope === "new generation cache" ? new QueryClient() : queryClient;
      const next = renderHook(
        () => useDashboardSnapshotBoundary({
          reportDate: scope === "same scope" ? firstDate : nextDate,
          allowPartial: scope === "different partial option",
        }),
        { wrapper: wrapper(nextClient, nextCache) },
      );
      await waitFor(() => expect(next.result.current.snapshotQuery.isError).toBe(true));
      if (scope === "same scope") {
        expect(next.result.current.snapshotResult?.report_date).toBe(firstDate);
        expect(next.result.current.reportDateDataWarning).toBe("当前报告日刷新失败，保留该报告日上一版本数据");
      } else {
        expect(next.result.current.snapshotResult).toBeUndefined();
        expect(next.result.current.adapterOutput.overview.state.kind).toBe("error");
      }
      next.unmount();
      queryClient.clear();
      nextCache.clear();
    },
  );

  it("keeps pure mock mode explicit when the source client is mock", async () => {
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>((options) =>
      createApiClient({ mode: "mock" }).getHomeSnapshot(options),
    );
    const mockClient = buildClientWithSnapshotOverride({
      mode: "mock",
      getHomeSnapshot,
    });

    const { result } = renderHook(
      () =>
        useDashboardSnapshotBoundary({
          reportDate: "",
          allowPartial: false,
        }),
      {
        wrapper: createWrapper(mockClient),
      },
    );

    await waitFor(() => {
      expect(result.current.snapshotQuery.isSuccess).toBe(true);
    });

    expect(result.current.displayMode).toBe("mock");
    expect(result.current.dataClient.mode).toBe("mock");
    expect(result.current.isLiveDataFallback).toBe(false);
    expect(getHomeSnapshot).toHaveBeenCalledWith({
      reportDate: undefined,
      allowPartial: false,
    });
  });

  it("keeps the real client active after a successful real snapshot fetch", async () => {
    const liveSnapshotReportDate = "2026-04-30";
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>(async (options) => {
      const base = await createApiClient({ mode: "mock" }).getHomeSnapshot(options);
      return {
        ...base,
        result: {
          ...base.result,
          report_date: liveSnapshotReportDate,
        },
      };
    });
    const realClient = buildClientWithSnapshotOverride({
      mode: "real",
      getHomeSnapshot,
    });

    const { result } = renderHook(
      () =>
        useDashboardSnapshotBoundary({
          reportDate: "",
          allowPartial: false,
        }),
      {
        wrapper: createWrapper(realClient),
      },
    );

    await waitFor(() => {
      expect(result.current.snapshotQuery.isSuccess).toBe(true);
    });

    expect(result.current.displayMode).toBe("real");
    expect(result.current.dataClient.mode).toBe("real");
    expect(result.current.isLiveDataFallback).toBe(false);
    expect(result.current.initialEffectiveReportDate).toBe(liveSnapshotReportDate);
    expect(getHomeSnapshot).toHaveBeenCalledTimes(1);
  });

  it("keeps the real client active after a snapshot network failure instead of showing mock data", async () => {
    const realClient = buildClientWithSnapshotOverride({
      mode: "real",
      getHomeSnapshot: vi
        .fn<ApiClient["getHomeSnapshot"]>()
        .mockRejectedValue(new TypeError("Failed to fetch")),
    });

    const { result } = renderHook(
      () =>
        useDashboardSnapshotBoundary({
          reportDate: "",
          allowPartial: false,
        }),
      {
        wrapper: createWrapper(realClient),
      },
    );

    await waitFor(() => {
      expect(result.current.snapshotQuery.isError).toBe(true);
    });

    expect(result.current.displayMode).toBe("real");
    expect(result.current.dataClient.mode).toBe("real");
    expect(result.current.isLiveDataFallback).toBe(false);
    expect(result.current.adapterOutput.overview.state.kind).toBe("error");
  });

  it("falls back to trimmed reportDate when snapshot report_date is missing", async () => {
    const client = buildClientWithSnapshotOverride({
      mode: "mock",
      getHomeSnapshot: vi.fn(async (options) => {
        const base = await createApiClient({ mode: "mock" }).getHomeSnapshot(options);
        return {
          ...base,
          result: {
            ...base.result,
            report_date: "",
          },
        };
      }),
    });

    const { result } = renderHook(
      () =>
        useDashboardSnapshotBoundary({
          reportDate: " 2026-04-18 ",
          allowPartial: false,
        }),
      {
        wrapper: createWrapper(client),
      },
    );

    await waitFor(() => {
      expect(result.current.snapshotQuery.isSuccess).toBe(true);
    });

    expect(result.current.initialEffectiveReportDate).toBe("2026-04-18");
    expect(result.current.supplementalReportDate).toBe("2026-04-18");
  });

  it("refreshSnapshot refetches the real client after a network failure", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const liveSnapshotReportDate = "2026-05-06";
    const liveSnapshotEnvelopePromise = mockSource.getHomeSnapshot({
      reportDate: liveSnapshotReportDate,
      allowPartial: false,
    });
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockImplementationOnce(async () => {
        const base = await liveSnapshotEnvelopePromise;
        return {
          ...base,
          result: {
            ...base.result,
            report_date: liveSnapshotReportDate,
          },
        };
      });
    const realClient = buildClientWithSnapshotOverride({
      mode: "real",
      getHomeSnapshot,
    });

    const { result } = renderHook(
      () =>
        useDashboardSnapshotBoundary({
          reportDate: "",
          allowPartial: false,
        }),
      {
        wrapper: createWrapper(realClient),
      },
    );

    await waitFor(() => {
      expect(result.current.snapshotQuery.isError).toBe(true);
    });

    expect(result.current.dataClient.mode).toBe("real");
    expect(result.current.isLiveDataFallback).toBe(false);

    await act(async () => {
      await result.current.refreshSnapshot();
    });

    await waitFor(() => {
      expect(getHomeSnapshot).toHaveBeenCalledTimes(2);
      expect(result.current.dataClient.mode).toBe("real");
      expect(result.current.isLiveDataFallback).toBe(false);
      expect(result.current.snapshotQuery.isSuccess).toBe(true);
      expect(result.current.initialEffectiveReportDate).toBe(liveSnapshotReportDate);
    });
  });

  it("clears the previous date snapshot when a new report date fails", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const firstReportDate = "2026-04-30";
    const failedReportDate = "2026-05-31";
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>(async (options) => {
      if (options?.reportDate === failedReportDate) {
        throw new TypeError("Failed to fetch");
      }
      const base = await mockSource.getHomeSnapshot(options);
      return {
        ...base,
        result: {
          ...base.result,
          report_date: options?.reportDate ?? firstReportDate,
        },
      };
    });
    const realClient = buildClientWithSnapshotOverride({
      mode: "real",
      getHomeSnapshot,
    });

    const { result, rerender } = renderHook(
      ({ reportDate }) =>
        useDashboardSnapshotBoundary({
          reportDate,
          allowPartial: false,
        }),
      {
        initialProps: { reportDate: firstReportDate },
        wrapper: createWrapper(realClient),
      },
    );

    await waitFor(() => {
      expect(result.current.snapshotQuery.isSuccess).toBe(true);
    });
    expect(result.current.initialEffectiveReportDate).toBe(firstReportDate);

    rerender({ reportDate: failedReportDate });

    await waitFor(() => {
      expect(result.current.snapshotQuery.isError).toBe(true);
    });

    expect(result.current.dataClient.mode).toBe("real");
    expect(result.current.isLiveDataFallback).toBe(false);
    expect(result.current.initialEffectiveReportDate).toBe("");
    expect(result.current.supplementalReportDate).toBeUndefined();
    expect(result.current.snapshotResult).toBeUndefined();
    expect(result.current.reportDateDataWarning).toBe(
      "实时数据源当前不可用，未展示本地模拟数据",
    );
    expect(result.current.adapterOutput.overview.state.kind).toBe("error");
  });
});
