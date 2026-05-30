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

  it("keeps the previous successful snapshot when a new report date fails", async () => {
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
    expect(result.current.initialEffectiveReportDate).toBe(firstReportDate);
    expect(result.current.supplementalReportDate).toBe(firstReportDate);
    expect(result.current.snapshotResult?.report_date).toBe(firstReportDate);
    expect(result.current.reportDateDataWarning).toBe(
      "新报告日数据获取失败，当前展示上一版本数据",
    );
    expect(result.current.adapterOutput.overview.state.kind).not.toBe("error");
  });
});
