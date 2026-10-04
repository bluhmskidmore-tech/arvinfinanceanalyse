import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../../../api/client";
import { useResearchDeskQueries } from "./useResearchDeskQueries";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return { queryClient, Wrapper };
}

type Client = ReturnType<typeof createApiClient>;

function stubResearchDeskClient(client: Client, detailAsOfDate: string | null) {
  const detailSpy = vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue({
    result_meta: {},
    result: { as_of_date: detailAsOfDate },
  } as unknown as Awaited<ReturnType<Client["getLivermoreStockDetail"]>>);
  const klineSpy = vi.spyOn(client, "getStockKlineAnalysis").mockResolvedValue({
    result_meta: {},
    result: {},
  } as unknown as Awaited<ReturnType<Client["getStockKlineAnalysis"]>>);
  const newsSpy = vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue({
    result_meta: {},
    result: { items: [] },
  } as unknown as Awaited<ReturnType<Client["getChoiceNewsEvents"]>>);
  return { detailSpy, klineSpy, newsSpy };
}

describe("useResearchDeskQueries", () => {
  const queryClients: QueryClient[] = [];

  afterEach(() => {
    for (const queryClient of queryClients.splice(0)) queryClient.clear();
    vi.restoreAllMocks();
  });

  it("stays idle without a selected candidate", () => {
    const client = createApiClient({ mode: "mock" });
    const { detailSpy, klineSpy, newsSpy } = stubResearchDeskClient(client, "2026-04-29");
    const { queryClient, Wrapper } = createWrapper();
    queryClients.push(queryClient);

    const { result } = renderHook(
      () =>
        useResearchDeskQueries({
          client,
          selectedCandidate: null,
          asOfDate: "2026-04-29",
          analyticsAsOf: "2026-04-29",
        }),
      { wrapper: Wrapper },
    );

    expect(result.current.detailQuery.fetchStatus).toBe("idle");
    expect(result.current.klineQuery.fetchStatus).toBe("idle");
    expect(result.current.newsQuery.fetchStatus).toBe("idle");
    expect(result.current.newsAsOfDate).toBe("2026-04-29");
    expect(detailSpy).not.toHaveBeenCalled();
    expect(klineSpy).not.toHaveBeenCalled();
    expect(newsSpy).not.toHaveBeenCalled();
  });

  it("reads detail, kline, and news for the selected candidate on the strategy as-of date", async () => {
    const client = createApiClient({ mode: "mock" });
    const { detailSpy, klineSpy, newsSpy } = stubResearchDeskClient(client, "2026-04-29");
    const { queryClient, Wrapper } = createWrapper();
    queryClients.push(queryClient);

    const { result } = renderHook(
      () =>
        useResearchDeskQueries({
          client,
          selectedCandidate: { stockCode: "600519.SH" },
          asOfDate: "2026-04-29",
          analyticsAsOf: "2026-04-29",
        }),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.newsQuery.isSuccess).toBe(true);
    });

    expect(detailSpy).toHaveBeenCalledWith({
      stockCode: "600519.SH",
      asOfDate: "2026-04-29",
      lookback: 60,
    });
    expect(klineSpy).toHaveBeenCalledWith({
      stockCode: "600519.SH",
      asOfDate: "2026-04-29",
      lookback: 60,
    });
    expect(newsSpy).toHaveBeenCalledWith({
      limit: 10,
      offset: 0,
      stockCode: "600519.SH",
      receivedTo: "2026-04-29T23:59:59Z",
    });
    expect(result.current.newsAsOfDate).toBe("2026-04-29");
  });

  it("keeps a late response for the previous candidate and date out of the active dossier", async () => {
    const client = createApiClient({ mode: "mock" });
    type DetailResponse = Awaited<ReturnType<Client["getLivermoreStockDetail"]>>;
    let resolvePrevious!: (value: DetailResponse) => void;
    const detailSpy = vi.spyOn(client, "getLivermoreStockDetail").mockImplementation((options) => {
      if (options.stockCode === "000001.SZ") {
        return new Promise<DetailResponse>((resolve) => {
          resolvePrevious = resolve;
        });
      }
      return Promise.resolve({
        result_meta: {},
        result: { stock_code: options.stockCode, as_of_date: options.asOfDate },
      } as unknown as DetailResponse);
    });
    vi.spyOn(client, "getStockKlineAnalysis").mockResolvedValue({
      result_meta: {},
      result: {},
    } as unknown as Awaited<ReturnType<Client["getStockKlineAnalysis"]>>);
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue({
      result_meta: {},
      result: { items: [] },
    } as unknown as Awaited<ReturnType<Client["getChoiceNewsEvents"]>>);
    const { queryClient, Wrapper } = createWrapper();
    queryClients.push(queryClient);

    const { result, rerender } = renderHook(
      ({ stockCode, asOfDate }: { stockCode: string; asOfDate: string }) =>
        useResearchDeskQueries({
          client,
          selectedCandidate: { stockCode },
          asOfDate,
          analyticsAsOf: asOfDate,
        }),
      {
        wrapper: Wrapper,
        initialProps: { stockCode: "000001.SZ", asOfDate: "2026-04-29" },
      },
    );

    await waitFor(() => expect(detailSpy).toHaveBeenCalledTimes(1));
    rerender({ stockCode: "000002.SZ", asOfDate: "2026-04-30" });
    await waitFor(() =>
      expect(result.current.detailQuery.data?.result).toMatchObject({
        stock_code: "000002.SZ",
        as_of_date: "2026-04-30",
      }),
    );

    await act(async () => {
      resolvePrevious({
        result_meta: {},
        result: { stock_code: "000001.SZ", as_of_date: "2026-04-29" },
      } as unknown as DetailResponse);
    });

    expect(result.current.detailQuery.data?.result).toMatchObject({
      stock_code: "000002.SZ",
      as_of_date: "2026-04-30",
    });
    expect(detailSpy).toHaveBeenNthCalledWith(1, {
      stockCode: "000001.SZ",
      asOfDate: "2026-04-29",
      lookback: 60,
    });
    expect(detailSpy).toHaveBeenNthCalledWith(2, {
      stockCode: "000002.SZ",
      asOfDate: "2026-04-30",
      lookback: 60,
    });
  });

  it("falls back to the detail payload's as_of_date for news when the strategy date is missing", async () => {
    const client = createApiClient({ mode: "mock" });
    const { newsSpy } = stubResearchDeskClient(client, "2026-04-28");
    const { queryClient, Wrapper } = createWrapper();
    queryClients.push(queryClient);

    const { result } = renderHook(
      () =>
        useResearchDeskQueries({
          client,
          selectedCandidate: { stockCode: "600519.SH" },
          asOfDate: undefined,
          analyticsAsOf: null,
        }),
      { wrapper: Wrapper },
    );

    expect(result.current.newsAsOfDate).toBeNull();
    expect(result.current.newsQuery.fetchStatus).toBe("idle");

    await waitFor(() => {
      expect(result.current.newsQuery.isSuccess).toBe(true);
    });

    expect(result.current.newsAsOfDate).toBe("2026-04-28");
    expect(newsSpy).toHaveBeenCalledTimes(1);
    expect(newsSpy).toHaveBeenCalledWith({
      limit: 10,
      offset: 0,
      stockCode: "600519.SH",
      receivedTo: "2026-04-28T23:59:59Z",
    });
  });
});
