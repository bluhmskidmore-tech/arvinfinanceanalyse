import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiClientProvider, createApiClient } from "../../../api/client";
import { useBalanceMovementAnalysis } from "./useBalanceMovementAnalysis";

function setup(entry: string) {
  const client = createApiClient({ mode: "mock" });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(client, "getBalanceMovementDates").mockResolvedValue({ result: { report_dates: ["2026-06-30", "2026-05-31"], currency_basis: "CNX" }, result_meta: {} } as Awaited<ReturnType<typeof client.getBalanceMovementDates>>);
  const refresh = vi.spyOn(client, "refreshBalanceMovementAnalysis");
  function wrapper({ children }: PropsWithChildren) {
    return <MemoryRouter initialEntries={["/sentinel", entry]}><QueryClientProvider client={queryClient}><ApiClientProvider client={client}>{children}</ApiClientProvider></QueryClientProvider></MemoryRouter>;
  }
  const hook = renderHook(() => ({ ...useBalanceMovementAnalysis(), location: useLocation(), navigate: useNavigate() }), { wrapper });
  return { ...hook, refresh, client, queryClient };
}

describe("CNX monthly read selection", () => {
  it("canonicalizes a default month by replacing the entry without adding history", async () => {
    const { result } = setup("/balance-movement-analysis");
    await waitFor(() => expect(result.current.selectedDate).toBe("2026-06-30"));
    await waitFor(() => expect(new URLSearchParams(result.current.location.search).get("report_date")).toBe("2026-06-30"));
    act(() => result.current.navigate(-1));
    await waitFor(() => expect(result.current.location.pathname).toBe("/sentinel"));
  });

  it("keeps deliberate month changes in history for Back and Forward", async () => {
    const { result, refresh } = setup("/balance-movement-analysis?report_date=2026-06-30&currency_basis=CNX");
    await waitFor(() => expect(result.current.selectedDate).toBe("2026-06-30"));
    act(() => result.current.updateReportDateSelection("2026-05-31"));
    await waitFor(() => expect(result.current.selectedDate).toBe("2026-05-31"));
    act(() => result.current.navigate(-1));
    await waitFor(() => expect(result.current.selectedDate).toBe("2026-06-30"));
    act(() => result.current.navigate(1));
    await waitFor(() => expect(result.current.selectedDate).toBe("2026-05-31"));
    expect(refresh).not.toHaveBeenCalled();
  });

  it("discloses the invalid requested date while preserving the existing latest-date fallback", async () => {
    const { result } = setup("/balance-movement-analysis?report_date=2020-01-31&currency_basis=CNY");
    await waitFor(() => expect(result.current.selectedDate).toBe("2026-06-30"));
    await waitFor(() => expect(new URLSearchParams(result.current.location.search).get("report_date")).toBe("2026-06-30"));
    expect(result.current.requestedReportDate).toBe("2020-01-31");
    expect(result.current.currencyBasis).toBe("CNX");
  });

  it("keeps the month and bucket when opening evidence, returning and navigating history", async () => {
    const { result, refresh } = setup("/balance-movement-analysis?report_date=2026-05-31&currency_basis=CNX&basis_bucket=OCI");
    await waitFor(() => expect(result.current.selectedDate).toBe("2026-05-31"));
    expect(result.current.selectedBucket).toBe("OCI");
    act(() => result.current.updateEvidenceSelection(true));
    await waitFor(() => expect(result.current.isEvidenceOpen).toBe(true));
    act(() => result.current.updateEvidenceSelection(false));
    await waitFor(() => expect(result.current.isEvidenceOpen).toBe(false));
    expect(result.current.selectedBucket).toBe("OCI");
    expect(result.current.selectedDate).toBe("2026-05-31");
    act(() => result.current.navigate(-1));
    await waitFor(() => expect(result.current.isEvidenceOpen).toBe(true));
    expect(refresh).not.toHaveBeenCalled();
  });
});

it.each(["date", "bucket"] as const)("does not let an old refresh overwrite a newer %s selection", async (change) => {
  const { result, refresh, client } = setup("/balance-movement-analysis?report_date=2026-05-31&currency_basis=CNX&basis_bucket=OCI");
  await waitFor(() => expect(result.current.datesQuery.isSuccess).toBe(true));
  const dates = { report_dates: ["2026-06-30", "2026-05-31"], currency_basis: "CNX", freshness_status: "read_model_lagging" as const, latest_upstream_control_report_date: "2026-07-31" };
  vi.mocked(client.getBalanceMovementDates).mockResolvedValue({ result: dates, result_meta: {} } as Awaited<ReturnType<typeof client.getBalanceMovementDates>>);
  await act(async () => { await result.current.datesQuery.refetch(); });
  await waitFor(() => expect(result.current.datesQuery.data?.result.latest_upstream_control_report_date).toBe("2026-07-31"));
  let release!: (value: Awaited<ReturnType<typeof client.refreshBalanceMovementAnalysis>>) => void;
  refresh.mockReturnValue(new Promise((resolve) => { release = resolve; }));
  let work!: Promise<void>;
  act(() => { work = result.current.handleRefresh(); });
  await waitFor(() => expect(refresh).toHaveBeenCalledWith({ reportDate: "2026-07-31", currencyBasis: "CNX" }));
  act(() => {
    if (change === "date") result.current.updateReportDateSelection("2026-06-30");
    else result.current.updateBucketSelection("AC");
  });
  const currentSearch = result.current.location.search;
  vi.mocked(client.getBalanceMovementDates).mockResolvedValue({ result: { ...dates, report_dates: ["2026-07-31", ...dates.report_dates] }, result_meta: {} } as Awaited<ReturnType<typeof client.getBalanceMovementDates>>);
  await act(async () => { release({ status: "completed", report_date: "2026-07-31", currency_basis: "CNX", cache_key: "test", rule_version: "test" }); await work; });
  expect(result.current.location.search).toBe(currentSearch);
});

it("releases a pending refresh when leaving the page without another date read", async () => {
  const { result, refresh, client, unmount } = setup("/balance-movement-analysis?report_date=2026-05-31&currency_basis=CNX");
  await waitFor(() => expect(result.current.selectedDate).toBe("2026-05-31"));
  let release!: (value: Awaited<ReturnType<typeof client.refreshBalanceMovementAnalysis>>) => void;
  refresh.mockReturnValue(new Promise((resolve) => { release = resolve; }));
  let settled = false;
  let work!: Promise<void>;
  act(() => { work = result.current.handleRefresh().then(() => { settled = true; }); });
  const calls = vi.mocked(client.getBalanceMovementDates).mock.calls.length;
  unmount();
  try { await waitFor(() => expect(settled).toBe(true), { timeout: 150 }); }
  finally { await act(async () => { release({ status: "completed", report_date: "2026-05-31", currency_basis: "CNX", cache_key: "test", rule_version: "test" }); await work; }); }
  expect(client.getBalanceMovementDates).toHaveBeenCalledTimes(calls);
});

it("releases an old mode refresh when the next mode already has the same cached month", async () => {
  const mockClient = createApiClient({ mode: "mock" });
  const realClient = createApiClient({
    mode: "real",
    fetchImpl: vi.fn(async () => { throw new Error("Unexpected transport in synthetic mode test"); }),
  });
  const detail = await mockClient.getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
  const dates: Awaited<ReturnType<typeof mockClient.getBalanceMovementDates>> = {
    result: { report_dates: ["2026-06-30"], currency_basis: "CNX" },
    result_meta: detail.result_meta,
  };
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  for (const client of [mockClient, realClient]) {
    vi.spyOn(client, "getBalanceMovementDates").mockResolvedValue(dates);
    vi.spyOn(client, "getBalanceMovementAnalysis").mockResolvedValue(detail);
    queryClient.setQueryData(["balance-movement-analysis", "dates", client.mode, "CNX"], dates);
    queryClient.setQueryData(["balance-movement-analysis", "detail", client.mode, "2026-06-30", "CNX"], detail);
  }
  let activeClient = mockClient;
  function wrapper({ children }: PropsWithChildren) {
    return <MemoryRouter initialEntries={["/balance-movement-analysis?report_date=2026-06-30&currency_basis=CNX"]}><QueryClientProvider client={queryClient}><ApiClientProvider client={activeClient}>{children}</ApiClientProvider></QueryClientProvider></MemoryRouter>;
  }
  let release!: (value: Awaited<ReturnType<typeof mockClient.refreshBalanceMovementAnalysis>>) => void;
  const refresh = vi.spyOn(mockClient, "refreshBalanceMovementAnalysis").mockReturnValue(new Promise((resolve) => { release = resolve; }));
  const { result, rerender, unmount } = renderHook(useBalanceMovementAnalysis, { wrapper });
  let settled = false;
  let work!: Promise<void>;
  act(() => { work = result.current.handleRefresh().then(() => { settled = true; }); });
  await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
  activeClient = realClient;
  rerender();
  try {
    await waitFor(() => expect(settled).toBe(true), { timeout: 150 });
  } finally {
    await act(async () => { release({ status: "completed", report_date: "2026-06-30", currency_basis: "CNX", cache_key: "synthetic", rule_version: "synthetic" }); await work; });
  }
  expect(result.current.selectedDate).toBe("2026-06-30");
  expect(result.current.refreshMessage).toBeNull();
  expect(mockClient.getBalanceMovementDates).not.toHaveBeenCalled();
  expect(realClient.getBalanceMovementDates).not.toHaveBeenCalled();
  unmount();
  queryClient.clear();
});
