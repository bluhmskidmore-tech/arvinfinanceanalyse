import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
import { ApiClientProvider } from "../../../api/clientContext";
import type { BalanceAnalysisPublicationStatusPayload } from "../../../api/contracts";
import { usePortfolioHomeQueries } from "./usePortfolioHomeQueries";
import { buildModuleHomeView } from "./moduleHomeModel";
import PortfolioHomePage from "./PortfolioHomePage";

vi.mock("./PortfolioHomeLayout", () => ({
  default: ({ balanceReportDate }: { balanceReportDate: string }) => <output>{balanceReportDate}</output>,
}));

const published = (generation = "balance-current"): BalanceAnalysisPublicationStatusPayload => ({
  enabled: true,
  available: true,
  generation,
  report_dates: ["2026-08-31"],
  manifest_sha256: "a".repeat(64),
  quality_flag: "ok",
  reason: null,
});

function setup() {
  const client = createApiClient({ mode: "mock" });
  client.getBalanceAnalysisDates = vi.fn(async () => ({
    result: { report_dates: ["2026-08-31"] },
    result_meta: {} as never,
  }));
  client.getBalanceAnalysisPublicationStatus = vi.fn(async () => published());
  client.getBalanceAnalysisOverview = vi.fn(async ({ reportDate, generation }) => ({
    result: { report_date: reportDate, currency_basis: "CNY" },
    result_meta: { filters_applied: { generation, manifest_sha256: "a".repeat(64), serving_mode: "published" } },
  }) as never);
  // Keep unrelated sources idle: these tests exercise only the publication boundary.
  client.getBondDashboardDates = vi.fn(() => new Promise<never>(() => undefined));
  client.getRiskTensorDates = vi.fn(() => new Promise<never>(() => undefined));
  client.getBalanceAnalysisSummaryByBasis = vi.fn(async ({ reportDate, generation }) => ({
    result: { report_date: reportDate, rows: [] },
    result_meta: { filters_applied: { generation, manifest_sha256: "a".repeat(64), serving_mode: "published" } },
  }) as never);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return { client, queryClient };
}

function wrapper(client: ApiClient, queryClient: QueryClient) {
  return function HookWrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  };
}

const publicationKey = ["balance-analysis", "publication-status", "mock"];

describe("portfolio balance publication boundary", () => {
  it("pins both balance requests to the published generation", async () => {
    const { client, queryClient } = setup();
    renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(client.getBalanceAnalysisOverview).toHaveBeenCalledWith({
      reportDate: "2026-08-31",
      positionScope: "all",
      currencyBasis: "CNY",
      generation: "balance-current",
    }));
    expect(client.getBalanceAnalysisSummaryByBasis).toHaveBeenCalledWith({
      reportDate: "2026-08-31", positionScope: "all", currencyBasis: "CNY", generation: "balance-current",
    });
  });

  it("waits for publication status before issuing any overview request", async () => {
    const { client, queryClient } = setup();
    client.getBalanceAnalysisPublicationStatus = vi.fn(() => new Promise<never>(() => undefined));
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.balanceDates?.isSuccess).toBe(true));
    expect(client.getBalanceAnalysisOverview).not.toHaveBeenCalled();
    expect(client.getBalanceAnalysisSummaryByBasis).not.toHaveBeenCalled();
  });

  it("opens the published date when the live dates read fails", async () => {
    const { client, queryClient } = setup();
    client.getBalanceAnalysisDates = vi.fn(async () => { throw new Error("writer lock"); });
    renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(client.getBalanceAnalysisOverview).toHaveBeenCalledWith({
      reportDate: "2026-08-31",
      positionScope: "all",
      currencyBasis: "CNY",
      generation: "balance-current",
    }));
  });

  it("does not fall back to live overview when publication is unavailable", async () => {
    const { client, queryClient } = setup();
    client.getBalanceAnalysisPublicationStatus = vi.fn(async () => ({
      ...published(), available: false, generation: null, report_dates: [],
      quality_flag: "stale" as const, reason: "revoked generation",
    }));
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.balanceDates?.isSuccess).toBe(true));
    expect(client.getBalanceAnalysisOverview).not.toHaveBeenCalled();
    expect(result.current.balanceOverview?.data).toBeUndefined();
    expect(result.current.balanceBasis?.data).toBeUndefined();
    expect(client.getBalanceAnalysisSummaryByBasis).not.toHaveBeenCalled();
  });

  it("uses a new request and cache entry when the publication generation changes", async () => {
    const { client, queryClient } = setup();
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.balanceOverview?.data).toBeDefined());
    await act(async () => { queryClient.setQueryData(publicationKey, published("balance-next")); });
    await waitFor(() => expect(client.getBalanceAnalysisOverview).toHaveBeenLastCalledWith({
      reportDate: "2026-08-31", positionScope: "all", currencyBasis: "CNY", generation: "balance-next",
    }));
    expect(queryClient.getQueryCache().findAll({ queryKey: ["module-home", "balance-overview"] }))
      .toEqual(expect.arrayContaining([
        expect.objectContaining({ queryKey: expect.arrayContaining(["balance-current"]) }),
        expect.objectContaining({ queryKey: expect.arrayContaining(["balance-next"]) }),
      ]));
    await waitFor(() => expect(client.getBalanceAnalysisSummaryByBasis).toHaveBeenCalledTimes(2));
    expect(client.getBalanceAnalysisSummaryByBasis).toHaveBeenLastCalledWith({
      reportDate: "2026-08-31", positionScope: "all", currencyBasis: "CNY", generation: "balance-next",
    });
    expect(queryClient.getQueryCache().findAll({ queryKey: ["module-home", "balance-basis"] }))
      .toEqual(expect.arrayContaining([
        expect.objectContaining({ queryKey: expect.arrayContaining(["balance-current"]) }),
        expect.objectContaining({ queryKey: expect.arrayContaining(["balance-next"]) }),
      ]));
  });

  it("withdraws cached overview after publication status refresh fails", async () => {
    const { client, queryClient } = setup();
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.balanceOverview?.data).toBeDefined());
    vi.mocked(client.getBalanceAnalysisPublicationStatus).mockRejectedValue(new Error("status unavailable"));
    await act(async () => { await queryClient.refetchQueries({ queryKey: publicationKey }); });
    await waitFor(() => expect(result.current.balanceOverview?.data).toBeUndefined());
    expect(result.current.balanceBasis?.data).toBeUndefined();
  });

  it("withdraws cached overview after its pinned generation is rejected", async () => {
    const { client, queryClient } = setup();
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.balanceOverview?.data).toBeDefined());
    vi.mocked(client.getBalanceAnalysisOverview).mockRejectedValue(new Error("generation revoked"));
    await act(async () => { await result.current.balanceOverview?.refetch(); });
    await waitFor(() => expect(result.current.balanceOverview?.isError).toBe(true));
    expect(result.current.balanceOverview?.data).toBeUndefined();
    expect(result.current.balanceBasis?.data).toBeUndefined();
  });

  it("retains the unpinned legacy path for a supported historical date when publication reads are disabled", async () => {
    const { client, queryClient } = setup();
    client.getBalanceAnalysisDates = vi.fn(async () => ({
      result: { report_dates: ["2026-07-31"] }, result_meta: {} as never,
    }));
    client.getBalanceAnalysisPublicationStatus = vi.fn(async () => ({
      ...published(), enabled: false, available: false, generation: null, report_dates: [],
    }));
    renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(client.getBalanceAnalysisOverview).toHaveBeenCalledWith({
      reportDate: "2026-07-31", positionScope: "all", currencyBasis: "CNY",
    }));
  });

  it("blocks the report date that requires a generation even when publication reads are disabled", async () => {
    const { client, queryClient } = setup();
    client.getBalanceAnalysisPublicationStatus = vi.fn(async () => ({
      ...published(), enabled: false, available: false, generation: null, report_dates: [],
    }));
    const { result } = renderHook(() => usePortfolioHomeQueries(), { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.balancePublicationStatusQuery.isSuccess).toBe(true));
    await waitFor(() => expect(result.current.balanceReportDate).toBe("2026-08-31"));
    expect(result.current.balanceOverviewServingMode).toBe("blocked");
    expect(client.getBalanceAnalysisOverview).not.toHaveBeenCalled();
    expect(client.getBalanceAnalysisSummaryByBasis).not.toHaveBeenCalled();
  });

  it("uses the published date in the real model without making a replaced live-date failure a core failure", async () => {
    const { client, queryClient } = setup();
    const base = createApiClient({ mode: "mock" });
    const bondDates = await base.getBondDashboardDates();
    const bondSummary = await base.getBondDashboardHomeSummary(bondDates.result.report_dates[0]);
    client.getBondDashboardDates = vi.fn(async () => bondDates);
    client.getBondDashboardHomeSummary = vi.fn(async () => bondSummary);
    client.getRiskTensorDates = base.getRiskTensorDates;
    client.getBalanceAnalysisDates = vi.fn(async () => { throw new Error("writer lock"); });
    const { result } = renderHook(() => {
      const state = usePortfolioHomeQueries();
      return { ...state, view: buildModuleHomeView("portfolio", { mode: "real" }, state.queries) };
    }, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.queries.balanceOverview?.isSuccess).toBe(true));
    await waitFor(() => expect(result.current.queries.bondHeadline?.isSuccess).toBe(true));
    await waitFor(() => expect(result.current.queries.bondRisk?.isSuccess).toBe(true));
    expect(result.current.queries.balanceDates?.isError).toBe(true);
    expect(result.current.view.stateLabel).toBe("已接入");
    expect(result.current.view.stateDetail).toContain("资产负债 2026-08-31");
    render(<PortfolioHomePage />, { wrapper: wrapper(client, queryClient) });
    expect(await screen.findByTestId("portfolio-balance-live-dates-state")).toHaveTextContent("实时日期列表读取失败");
    expect(screen.getByTestId("portfolio-balance-live-dates-state")).toHaveTextContent("总览日期来自已发布快照");
  });

  it("shows the selected published date and confirms the two verified snapshot reads", async () => {
    const { client, queryClient } = setup();
    client.getBalanceAnalysisDates = vi.fn(async () => ({
      result: { report_dates: ["2026-09-25"] }, result_meta: {} as never,
    }));
    render(<PortfolioHomePage />, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(screen.getByTestId("portfolio-balance-publication-state")).toHaveTextContent(
      "资产负债总览与口径分解均来自 2026-08-31 的同一已发布快照。",
    ));
    expect(screen.getByText("2026-08-31")).toBeInTheDocument();
    expect(client.getBalanceAnalysisSummaryByBasis).toHaveBeenCalledWith({
      reportDate: "2026-08-31", positionScope: "all", currencyBasis: "CNY", generation: "balance-current",
    });
  });

  it("shows the blocked publication state and removes a previously available overview", async () => {
    const { client, queryClient } = setup();
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    render(<PortfolioHomePage />, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.balanceOverview?.data).toBeDefined());
    await act(async () => {
      queryClient.setQueryData(publicationKey, {
        ...published(), available: false, generation: null, report_dates: [], quality_flag: "stale",
      });
    });
    await waitFor(() => expect(screen.getByTestId("portfolio-balance-publication-state")).toHaveTextContent("资产负债发布快照尚未就绪"));
    expect(result.current.balanceOverview?.data).toBeUndefined();
    expect(result.current.balanceBasis?.data).toBeUndefined();
  });

  it("discloses publication lookup failure rather than an unexplained empty metric", async () => {
    const { client, queryClient } = setup();
    vi.mocked(client.getBalanceAnalysisPublicationStatus).mockRejectedValue(new Error("status unavailable"));
    render(<PortfolioHomePage />, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(screen.getByTestId("portfolio-balance-publication-state")).toHaveTextContent("资产负债发布状态读取失败"));
    expect(client.getBalanceAnalysisOverview).not.toHaveBeenCalled();
    expect(client.getBalanceAnalysisSummaryByBasis).not.toHaveBeenCalled();
  });

  it("withdraws both reads when only basis fails after a successful pair", async () => {
    const { client, queryClient } = setup();
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    render(<PortfolioHomePage />, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.balanceBasis?.data).toBeDefined());
    vi.mocked(client.getBalanceAnalysisSummaryByBasis).mockRejectedValue(new Error("generation revoked"));
    await act(async () => { await result.current.balanceBasis?.refetch(); });
    await waitFor(() => expect(result.current.balanceBasis?.isError).toBe(true));
    expect(result.current.balanceOverview?.data).toBeUndefined();
    expect(result.current.balanceBasis?.data).toBeUndefined();
    expect(screen.getByTestId("portfolio-balance-publication-state")).toHaveTextContent("资产负债发布快照读取失败");
  });

  it("blocks an available status without manifest evidence", async () => {
    const { client, queryClient } = setup();
    client.getBalanceAnalysisPublicationStatus = vi.fn(async () => ({ ...published(), manifest_sha256: null }));
    const { result } = renderHook(() => usePortfolioHomeQueries(), { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.balanceOverviewServingMode).toBe("blocked"));
    expect(client.getBalanceAnalysisOverview).not.toHaveBeenCalled();
    expect(client.getBalanceAnalysisSummaryByBasis).not.toHaveBeenCalled();
  });

  it("rejects overview evidence from another manifest even when basis matches", async () => {
    const { client, queryClient } = setup();
    const original = client.getBalanceAnalysisOverview;
    client.getBalanceAnalysisOverview = vi.fn(async (options) => {
      const response = await original(options);
      return { ...response, result_meta: { ...response.result_meta, filters_applied: { ...response.result_meta.filters_applied, manifest_sha256: "b".repeat(64) } } };
    });
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.balanceOverview?.isError).toBe(true));
    expect(result.current.balanceOverview?.data).toBeUndefined();
    expect(result.current.balanceBasis?.data).toBeUndefined();
  });

  it.each([
    ["report_date", "2026-07-31"],
    ["generation", "balance-other"],
    ["manifest_sha256", "b".repeat(64)],
    ["serving_mode", "live"],
  ])("rejects a basis response with mismatched %s", async (field, value) => {
    const { client, queryClient } = setup();
    const original = client.getBalanceAnalysisSummaryByBasis;
    client.getBalanceAnalysisSummaryByBasis = vi.fn(async (options) => {
      const response = await original(options);
      return field === "report_date"
        ? { ...response, result: { ...response.result, report_date: value } }
        : { ...response, result_meta: { ...response.result_meta, filters_applied: { ...response.result_meta.filters_applied, [field]: value } } };
    });
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(result.current.balanceBasis?.isError).toBe(true));
    expect(result.current.balanceOverview?.data).toBeUndefined();
    expect(result.current.balanceBasis?.data).toBeUndefined();
  });

  it.each(["overview", "basis"] as const)("waits for both new-generation responses when %s arrives last", async (last) => {
    const { client, queryClient } = setup();
    const overview = client.getBalanceAnalysisOverview;
    const basis = client.getBalanceAnalysisSummaryByBasis;
    const pendingOverview = new Map<string, () => void>();
    const pendingBasis = new Map<string, () => void>();
    client.getBalanceAnalysisOverview = vi.fn<ApiClient["getBalanceAnalysisOverview"]>((options) => new Promise((resolve) => {
      pendingOverview.set(options.generation ?? "", () => { void overview(options).then(resolve); });
    }));
    client.getBalanceAnalysisSummaryByBasis = vi.fn<ApiClient["getBalanceAnalysisSummaryByBasis"]>((options) => new Promise((resolve) => {
      pendingBasis.set(options.generation ?? "", () => { void basis(options).then(resolve); });
    }));
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(pendingBasis.has("balance-current")).toBe(true));
    await act(async () => { queryClient.setQueryData(publicationKey, published("balance-next")); });
    await waitFor(() => expect(pendingBasis.has("balance-next")).toBe(true));
    // Old requests resolve only after the new generation was selected.
    await act(async () => { pendingOverview.get("balance-current")?.(); pendingBasis.get("balance-current")?.(); });
    expect(result.current.balanceOverview?.data).toBeUndefined();
    expect(result.current.balanceBasis?.data).toBeUndefined();
    const firstResponses = last === "overview" ? pendingBasis : pendingOverview;
    const lastResponses = last === "overview" ? pendingOverview : pendingBasis;
    await act(async () => { firstResponses.get("balance-next")?.(); });
    await waitFor(() => expect(last === "overview" ? result.current.balanceBasis?.isSuccess : result.current.balanceOverview?.isSuccess).toBe(true));
    expect(result.current.balanceOverview?.data).toBeUndefined();
    expect(result.current.balanceBasis?.data).toBeUndefined();
    await act(async () => { lastResponses.get("balance-next")?.(); });
    await waitFor(() => expect(result.current.balanceOverview?.data).toBeDefined());
    expect(result.current.balanceOverview?.data?.result_meta.filters_applied?.generation).toBe("balance-next");
    expect(result.current.balanceBasis?.data?.result_meta.filters_applied?.generation).toBe("balance-next");
  });

  it("discards successful in-flight responses after the publication is revoked", async () => {
    const { client, queryClient } = setup();
    const overview = client.getBalanceAnalysisOverview;
    const basis = client.getBalanceAnalysisSummaryByBasis;
    const pending: Array<() => void> = [];
    client.getBalanceAnalysisOverview = vi.fn<ApiClient["getBalanceAnalysisOverview"]>((options) => new Promise((resolve) => {
      pending.push(() => { void overview(options).then(resolve); });
    }));
    client.getBalanceAnalysisSummaryByBasis = vi.fn<ApiClient["getBalanceAnalysisSummaryByBasis"]>((options) => new Promise((resolve) => {
      pending.push(() => { void basis(options).then(resolve); });
    }));
    const { result } = renderHook(() => usePortfolioHomeQueries().queries, { wrapper: wrapper(client, queryClient) });
    await waitFor(() => expect(pending).toHaveLength(2));
    await act(async () => {
      queryClient.setQueryData(publicationKey, { ...published(), available: false, generation: null, report_dates: [] });
    });
    await act(async () => { pending.forEach((resolve) => resolve()); });
    expect(result.current.balanceOverview?.data).toBeUndefined();
    expect(result.current.balanceBasis?.data).toBeUndefined();
  });
});
