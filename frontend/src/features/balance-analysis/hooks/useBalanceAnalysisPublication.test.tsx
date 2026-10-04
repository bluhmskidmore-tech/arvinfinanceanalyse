import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
import { ApiClientProvider } from "../../../api/clientContext";
import { useBalanceAnalysisData } from "./useBalanceAnalysisData";

const hookParams = {
  summaryOffset: 0,
  eventTypeFilter: "all",
  riskSeverityFilter: "all" as const,
  selectedDecisionKey: null,
  selectedEventCalendarKey: null,
  selectedRiskAlertKey: null,
};

function wrapper(client: ApiClient, initialEntry = "/balance-analysis") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function HookWrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[initialEntry]}>
        <QueryClientProvider client={queryClient}>
          <ApiClientProvider client={client}>{children}</ApiClientProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  };
}

describe("balance overview publication selection", () => {
  it("opens the published overview on fresh entry when legacy dates are blocked", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () => {
      throw new Error("active database writer lock");
    });
    client.getBalanceAnalysisPublicationStatus = vi.fn(async () => ({
      enabled: true,
      available: true,
      generation: "balance-current",
      report_dates: ["2025-12-31"],
      manifest_sha256: "a".repeat(64),
      quality_flag: "ok" as const,
      reason: null,
    }));
    const overview = vi.fn(() => new Promise<never>(() => undefined));
    client.getBalanceAnalysisOverview = overview;

    const { result } = renderHook(() => useBalanceAnalysisData(hookParams), {
      wrapper: wrapper(client),
    });

    await waitFor(() =>
      expect(overview).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        positionScope: "all",
        currencyBasis: "CNY",
        generation: "balance-current",
      }),
    );
    expect(result.current.availableReportDates).toEqual(["2025-12-31"]);
  });

  it("keeps legacy dates and panels available when the publication does not cover that date", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () => ({
      result: { report_dates: ["2025-12-31", "2025-11-30"] },
      result_meta: {} as never,
    }));
    client.getBalanceAnalysisPublicationStatus = vi.fn(async () => ({
      enabled: true,
      available: true,
      generation: "balance-current",
      report_dates: ["2025-12-31"],
      manifest_sha256: "a".repeat(64),
      quality_flag: "ok" as const,
      reason: null,
    }));
    const overview = vi.fn(() => new Promise<never>(() => undefined));
    const summary = vi.fn(() => new Promise<never>(() => undefined));
    client.getBalanceAnalysisOverview = overview;
    client.getBalanceAnalysisSummary = summary;

    const { result } = renderHook(() => useBalanceAnalysisData(hookParams), {
      wrapper: wrapper(client, "/balance-analysis?report_date=2025-11-30"),
    });

    await waitFor(() => expect(summary).toHaveBeenCalled());
    expect(overview).not.toHaveBeenCalled();
    expect(result.current.availableReportDates).toEqual(["2025-12-31", "2025-11-30"]);
    expect(result.current.selectedReportDate).toBe("2025-11-30");
  });

  it("hides a cached legacy overview when publication becomes unavailable", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () => ({
      result: { report_dates: ["2025-12-31"] },
      result_meta: {} as never,
    }));
    let publicationEnabled = false;
    client.getBalanceAnalysisPublicationStatus = vi.fn(async () =>
      publicationEnabled
        ? {
            enabled: true,
            available: false,
            generation: null,
            report_dates: [],
            manifest_sha256: null,
            quality_flag: "stale" as const,
            reason: "current generation was revoked",
          }
        : {
            enabled: false,
            available: false,
            generation: null,
            report_dates: [],
            manifest_sha256: null,
            quality_flag: "stale" as const,
            reason: "publication reads are disabled",
          },
    );
    const overview = vi.fn(async () =>
      ({
        result: {
          report_date: "2025-12-31",
          currency_basis: "CNY",
        },
        result_meta: {},
      }) as never,
    );
    client.getBalanceAnalysisOverview = overview;

    const { result } = renderHook(() => useBalanceAnalysisData(hookParams), {
      wrapper: wrapper(client),
    });
    await waitFor(() => expect(result.current.overview).toBeDefined());

    publicationEnabled = true;
    await act(async () => {
      await result.current.publicationStatusQuery.refetch();
    });

    await waitFor(() => expect(result.current.overview).toBeUndefined());
    expect(result.current.overviewServingMode).toBe("blocked");
    expect(overview).toHaveBeenCalledTimes(1);
  });

  it("hides published data when the pinned generation is revoked during refetch", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () => ({
      result: { report_dates: ["2025-12-31"] },
      result_meta: {} as never,
    }));
    client.getBalanceAnalysisPublicationStatus = vi.fn(async () => ({
      enabled: true,
      available: true,
      generation: "balance-current",
      report_dates: ["2025-12-31"],
      manifest_sha256: "a".repeat(64),
      quality_flag: "ok" as const,
      reason: null,
    }));
    let revoked = false;
    client.getBalanceAnalysisOverview = vi.fn(async () => {
      if (revoked) {
        throw new Error("revoked generation");
      }
      return {
        result: {
          report_date: "2025-12-31",
          currency_basis: "CNY",
        },
        result_meta: {},
      } as never;
    });

    const { result } = renderHook(() => useBalanceAnalysisData(hookParams), {
      wrapper: wrapper(client),
    });
    await waitFor(() => expect(result.current.overview).toBeDefined());

    revoked = true;
    await act(async () => {
      await result.current.overviewQuery.refetch();
    });

    await waitFor(() => expect(result.current.overviewQuery.isError).toBe(true));
    expect(result.current.overview).toBeUndefined();
  });
});
