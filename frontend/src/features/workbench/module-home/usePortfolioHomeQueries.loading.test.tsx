import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
import { ApiClientProvider } from "../../../api/clientContext";
import type { ApiEnvelope, BondDashboardHomeSummaryPayload } from "../../../api/contracts";
import { apiQueryKeys } from "../../../api/queryKeys";
import { usePortfolioHomeQueries } from "./usePortfolioHomeQueries";

const REPORT_DATE = "2026-08-31";
const PRIOR_DATE = "2026-07-31";
let summary: ApiEnvelope<BondDashboardHomeSummaryPayload>;

beforeAll(async () => {
  summary = await createApiClient({ mode: "mock" }).getBondDashboardHomeSummary(REPORT_DATE);
});

function dates(reportDates = [REPORT_DATE]) {
  return { result: { report_dates: reportDates }, result_meta: summary.result_meta };
}

function setup(mode: "real" | "mock" = "mock") {
  // Every method reached by this hook is replaced; real mode tests never use the network.
  const client: ApiClient = {
    ...createApiClient({ mode: "mock" }),
    mode,
    getBalanceAnalysisDates: vi.fn(() => new Promise<never>(() => undefined)),
    getBalanceAnalysisPublicationStatus: vi.fn(() => new Promise<never>(() => undefined)),
    getRiskTensorDates: vi.fn(() => new Promise<never>(() => undefined)),
    getBondDashboardDates: vi.fn(async () => dates()),
    getBondDashboardHomeSummary: vi.fn(async () => summary),
    getBondDashboardRiskIndicators: vi.fn(async () => ({ ...summary, result: summary.result.risk })),
    getPnlAttributionAnalysisSummary: vi.fn(() => new Promise<never>(() => undefined)),
    getVolumeRateAttribution: vi.fn(() => new Promise<never>(() => undefined)),
  };
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }
  return { client, queryClient, wrapper };
}

describe("portfolio home request reuse", () => {
  it("starts summary from the bond dashboard's confirmed dates without another dates request", async () => {
    const { client, queryClient, wrapper } = setup();
    queryClient.setQueryData([client.mode, "bond-dashboard", "dates"], dates());
    client.getBondDashboardDates = vi.fn(() => new Promise<never>(() => undefined));

    renderHook(() => usePortfolioHomeQueries(), { wrapper });

    await waitFor(() => expect(client.getBondDashboardHomeSummary).toHaveBeenCalledWith(REPORT_DATE));
    expect(client.getBondDashboardDates).not.toHaveBeenCalled();
  });

  it("reuses the home summary and its embedded risk without requesting either again", async () => {
    const { client, queryClient, wrapper } = setup();
    queryClient.setQueryData(apiQueryKeys.bondDashboardHomeSummary(client.mode, REPORT_DATE), summary);
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper });

    await waitFor(() => expect(result.current.bondRisk?.isSuccess).toBe(true));
    expect(result.current.bondHeadline?.data?.result).toEqual(summary.result.headline);
    expect(result.current.bondRisk?.data).toEqual({ ...summary, result: summary.result.risk });
    expect(client.getBondDashboardHomeSummary).not.toHaveBeenCalled();
    expect(client.getBondDashboardRiskIndicators).not.toHaveBeenCalled();
  });

  it("joins an existing in-flight home summary read", async () => {
    const { client, queryClient, wrapper } = setup();
    let resolveSummary!: (value: typeof summary) => void;
    client.getBondDashboardHomeSummary = vi.fn(() => new Promise<typeof summary>((resolve) => {
      resolveSummary = resolve;
    }));
    const inFlight = queryClient.fetchQuery({
      queryKey: apiQueryKeys.bondDashboardHomeSummary(client.mode, REPORT_DATE),
      queryFn: () => client.getBondDashboardHomeSummary(REPORT_DATE),
      staleTime: 60_000,
    });
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper });
    await waitFor(() => expect(result.current.bondDates?.isSuccess).toBe(true));

    expect(client.getBondDashboardHomeSummary).toHaveBeenCalledTimes(1);
    await act(async () => { resolveSummary(summary); await inFlight; });
    await waitFor(() => expect(result.current.bondRisk?.data?.result).toEqual(summary.result.risk));
    expect(client.getBondDashboardRiskIndicators).not.toHaveBeenCalled();
  });

  it("waits for an available bond date before starting date-dependent reads", async () => {
    const { client, wrapper } = setup();
    client.getBondDashboardDates = vi.fn(async () => dates([]));
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper });
    await waitFor(() => expect(result.current.bondDates?.isSuccess).toBe(true));

    expect(client.getBondDashboardHomeSummary).not.toHaveBeenCalled();
    expect(client.getBondDashboardRiskIndicators).not.toHaveBeenCalled();
    expect(client.getPnlAttributionAnalysisSummary).not.toHaveBeenCalled();
    expect(client.getVolumeRateAttribution).not.toHaveBeenCalled();
    expect(result.current.bondRisk?.data).toBeUndefined();
  });

  it("does not substitute a cached summary from another report date or client mode", async () => {
    const { client, queryClient, wrapper } = setup("real");
    queryClient.setQueryData(apiQueryKeys.bondDashboardHomeSummary("mock", REPORT_DATE), summary);
    queryClient.setQueryData(apiQueryKeys.bondDashboardHomeSummary("real", PRIOR_DATE), summary);
    client.getBondDashboardHomeSummary = vi.fn(() => new Promise<never>(() => undefined));
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper });

    await waitFor(() => expect(client.getBondDashboardHomeSummary).toHaveBeenCalledWith(REPORT_DATE));
    expect(result.current.bondHeadline?.data).toBeUndefined();
    expect(result.current.bondRisk?.data).toBeUndefined();
  });

  it("preserves embedded risk nulls and the summary's date, lineage and quality metadata", async () => {
    const { client, wrapper } = setup();
    const degraded = structuredClone(summary);
    degraded.result.risk.weighted_convexity = { ...degraded.result.risk.weighted_convexity, raw: null };
    degraded.result_meta = {
      ...degraded.result_meta,
      quality_flag: "warning",
      fallback_mode: "latest_snapshot",
      fallback_date: PRIOR_DATE,
      source_version: "portfolio-loading-test-source",
    };
    client.getBondDashboardHomeSummary = vi.fn(async () => degraded);
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper });

    await waitFor(() => expect(result.current.bondRisk?.isSuccess).toBe(true));
    expect(result.current.bondRisk?.data).toEqual({ ...degraded, result: degraded.result.risk });
    expect(result.current.bondRisk?.data?.result.weighted_convexity.raw).toBeNull();
  });

  it("propagates summary failure to its risk projection without a second source fallback", async () => {
    const { client, wrapper } = setup();
    const failure = new Error("published summary unavailable");
    client.getBondDashboardHomeSummary = vi.fn(async () => { throw failure; });
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper });

    await waitFor(() => expect(result.current.bondHeadline?.isError).toBe(true));
    expect(result.current.bondRisk?.isError).toBe(true);
    expect(result.current.bondRisk?.error).toBe(failure);
    expect(result.current.bondRisk?.data).toBeUndefined();
    expect(client.getBondDashboardRiskIndicators).not.toHaveBeenCalled();
  });
});
