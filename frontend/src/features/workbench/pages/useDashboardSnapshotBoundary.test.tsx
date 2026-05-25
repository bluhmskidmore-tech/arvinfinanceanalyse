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

  it("keeps displayMode as real and switches to live fallback after a snapshot network failure", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const realClient = buildClientWithSnapshotOverride({
      mode: "real",
      getHomeSnapshot: vi
        .fn<ApiClient["getHomeSnapshot"]>()
        .mockRejectedValueOnce(new TypeError("Failed to fetch"))
        .mockImplementation((options) => mockSource.getHomeSnapshot(options)),
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
      expect(result.current.isLiveDataFallback).toBe(true);
    });

    expect(result.current.displayMode).toBe("real");
    expect(result.current.dataClient.mode).toBe("mock");
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

  it("refreshSnapshot exits fallback mode before refetching live data", async () => {
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
      expect(result.current.isLiveDataFallback).toBe(true);
    });

    expect(result.current.dataClient.mode).toBe("mock");

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
});
