import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import type { CampisiFourEffectsPayload } from "../../../api/contracts";
import { mockCampisiFourEffectsModelPath } from "../../../mocks/campisiMocks";
import {
  DASHBOARD_BOND_NEWS_TOPICS,
  DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS,
} from "../dashboard/dashboardMacroNewsTopics";
import { todayIsoDate } from "../pages/dashboardPageHelpers";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";
import { useDashboardHomeViewModel } from "./useDashboardHomeViewModel";

const BOND_NEWS_PROBE_GROUP_ID = DASHBOARD_BOND_NEWS_TOPICS[0]?.groupId;

// Visible content must start without the former stacked idle waits.
const GATED_QUERY_TIMEOUT_MS = 2_000;

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: false },
    },
  });
}

function createWrapper(queryClient = createQueryClient()) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function createHomeViewModelClient(overrides: Partial<ApiClient>): ApiClient {
  const base = createApiClient({ mode: "mock" });
  return {
    ...base,
    mode: "real",
    ...overrides,
  };
}

function buildSnapshotBoundary(
  dataClient: ApiClient,
  reportDate: string,
): DashboardHomeSnapshotBoundary {
  return {
    dataClient,
    snapshotQuery: {},
    isLiveDataFallback: false,
    adapterOutput: { attribution: { vm: null } },
    snapshotResult: { report_date: reportDate },
    overviewMeta: null,
    attributionMeta: null,
    snapshotMeta: null,
    initialEffectiveReportDate: reportDate,
    supplementalReportDate: reportDate,
    reportDateDataWarning: null,
    refreshSnapshot: async () => undefined,
  } as unknown as DashboardHomeSnapshotBoundary;
}

describe("useDashboardHomeViewModel section loading", () => {
  it("keeps unseen sections idle even after the former release timers have elapsed", async () => {
    vi.useFakeTimers();
    const mockClient = createApiClient({ mode: "mock" });
    const getMarketDataRates = vi.fn(mockClient.getMarketDataRates);
    const getBondAnalyticsTopHoldings = vi.fn(mockClient.getBondAnalyticsTopHoldings);
    const getPnlCampisiFourEffects = vi.fn(mockClient.getPnlCampisiFourEffects);
    const getChoiceNewsEventsBatch = vi.fn(mockClient.getChoiceNewsEventsBatch);
    const dataClient = createHomeViewModelClient({
      getMarketDataRates,
      getBondAnalyticsTopHoldings,
      getPnlCampisiFourEffects,
      getChoiceNewsEventsBatch,
      getResearchCalendarEvents: vi.fn(async () => []),
    });
    const { result, unmount } = renderHook(
      () => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, "2026-05-31"), {
        sections: { holdings: false, risk: false, market: false, support: false, evidence: false },
      }),
      { wrapper: createWrapper() },
    );
    try {
      await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
      expect(getMarketDataRates).not.toHaveBeenCalled();
      expect(getBondAnalyticsTopHoldings).not.toHaveBeenCalled();
      expect(getPnlCampisiFourEffects).not.toHaveBeenCalled();
      expect(getChoiceNewsEventsBatch).not.toHaveBeenCalled();
      expect(result.current.view.holdingsState.kind).toBe("loading");
      expect(result.current.view.incomeTrendState.kind).toBe("loading");
      expect(result.current.view.researchReportsState.kind).toBe("loading");
    } finally {
      unmount();
      vi.clearAllTimers();
      vi.useRealTimers();
    }
  });

  it("starts only the visible section and uses the latest report date when it becomes visible", async () => {
    const mockClient = createApiClient({ mode: "mock" });
    const getBondAnalyticsTopHoldings = vi.fn(mockClient.getBondAnalyticsTopHoldings);
    const getHomeResearchReports = vi.fn(mockClient.getHomeResearchReports);
    const getBondAnalyticsKrdCurveRisk = vi.fn(mockClient.getBondAnalyticsKrdCurveRisk);
    const getChoiceNewsEventsBatch = vi.fn(mockClient.getChoiceNewsEventsBatch);
    const dataClient = createHomeViewModelClient({
      getBondAnalyticsTopHoldings,
      getHomeResearchReports,
      getBondAnalyticsKrdCurveRisk,
      getChoiceNewsEventsBatch,
      getResearchCalendarEvents: vi.fn(async () => []),
    });
    const { rerender } = renderHook(
      ({ reportDate, holdings }) => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, reportDate), {
        sections: { holdings, risk: false, market: false, support: false, evidence: false },
      }),
      { initialProps: { reportDate: "2026-05-31", holdings: false }, wrapper: createWrapper() },
    );
    rerender({ reportDate: "2026-06-30", holdings: true });
    await waitFor(() => {
      expect(getBondAnalyticsTopHoldings).toHaveBeenCalledWith("2026-06-30", 14);
    });
    expect(getBondAnalyticsTopHoldings).not.toHaveBeenCalledWith("2026-05-31", 14);
    expect(getHomeResearchReports).not.toHaveBeenCalled();
    expect(getBondAnalyticsKrdCurveRisk).not.toHaveBeenCalled();
    expect(getChoiceNewsEventsBatch).not.toHaveBeenCalled();
  });

  it("releases ungated body requests immediately, without waiting on any idle gate", async () => {
    const reportDate = "2026-05-31";
    const getMarketDataRates = vi.fn(createApiClient({ mode: "mock" }).getMarketDataRates);
    const getBondDashboardHomeSummary = vi.fn(
      createApiClient({ mode: "mock" }).getBondDashboardHomeSummary,
    );
    const dataClient = createHomeViewModelClient({
      getMarketDataRates,
      getBondDashboardHomeSummary,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderHook(() => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, reportDate)), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(getMarketDataRates).toHaveBeenCalled();
      expect(getBondDashboardHomeSummary).toHaveBeenCalled();
    });
  });

  it("starts visible holdings within the existing request budget", async () => {
    const reportDate = "2026-05-31";
    const getBondAnalyticsTopHoldings = vi.fn(
      createApiClient({ mode: "mock" }).getBondAnalyticsTopHoldings,
    );
    const dataClient = createHomeViewModelClient({
      getBondAnalyticsTopHoldings,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderHook(() => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, reportDate)), {
      wrapper: createWrapper(),
    });

    await waitFor(
      () => {
        expect(getBondAnalyticsTopHoldings).toHaveBeenCalled();
      },
      { timeout: GATED_QUERY_TIMEOUT_MS },
    );
  });

  it("starts visible news within the existing request budget", async () => {
    const reportDate = "2026-05-31";
    // News waves now travel through the batch endpoint (one request per wave)
    // instead of per-topic getChoiceNewsEvents calls.
    const getChoiceNewsEventsBatch = vi.fn(
      createApiClient({ mode: "mock" }).getChoiceNewsEventsBatch,
    );
    const dataClient = createHomeViewModelClient({
      getChoiceNewsEventsBatch,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderHook(() => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, reportDate)), {
      wrapper: createWrapper(),
    });

    await waitFor(
      () => {
        expect(getChoiceNewsEventsBatch).toHaveBeenCalled();
      },
      { timeout: GATED_QUERY_TIMEOUT_MS },
    );
  });

  it("starts visible bond news without waiting for an unrelated macro response", async () => {
    const mockClient = createApiClient({ mode: "mock" });
    const getChoiceNewsEventsBatch = vi.fn((options: Parameters<ApiClient["getChoiceNewsEventsBatch"]>[0]) =>
      options.groups?.length ? mockClient.getChoiceNewsEventsBatch(options) : new Promise<never>(() => {}),
    );
    const dataClient = createHomeViewModelClient({
      getChoiceNewsEventsBatch,
      getResearchCalendarEvents: vi.fn(async () => []),
    });
    renderHook(() => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, "2026-05-31"), {
      sections: { holdings: false, risk: false, market: false, support: false, evidence: true },
    }), { wrapper: createWrapper() });
    await waitFor(() => {
      expect(getChoiceNewsEventsBatch.mock.calls.some(([options]) =>
        options.groups?.some((group) => group.groupId === BOND_NEWS_PROBE_GROUP_ID),
      )).toBe(true);
    });
  });

  it("settles empty holdings, request failure and an empty balance-date list out of loading", async () => {
    const mockClient = createApiClient({ mode: "mock" });
    const dataClient = createHomeViewModelClient({
      getBondAnalyticsTopHoldings: async (date, limit) => {
        const envelope = await mockClient.getBondAnalyticsTopHoldings(date, limit);
        return { ...envelope, result: { ...envelope.result, items: [] } };
      },
      getHomeResearchReports: async () => { throw new Error("research unavailable"); },
      getBalanceAnalysisDates: async () => {
        const envelope = await mockClient.getBalanceAnalysisDates();
        return { ...envelope, result: { ...envelope.result, report_dates: [] } };
      },
      getResearchCalendarEvents: vi.fn(async () => []),
    });
    const { result } = renderHook(() =>
      useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, "2026-05-31")),
      { wrapper: createWrapper() },
    );
    await waitFor(() => {
      expect(result.current.view.holdingsState.kind).toBe("empty");
      expect(result.current.view.researchReportsState.kind).toBe("error");
      expect(result.current.view.decisionItemsState.kind).not.toBe("loading");
    });
  });

  it("does not reuse an unresolved old-date response after a visible section changes report date", async () => {
    const mockClient = createApiClient({ mode: "mock" });
    let finishOld!: (value: Awaited<ReturnType<ApiClient["getBondAnalyticsTopHoldings"]>>) => void;
    const oldResponse = new Promise<Awaited<ReturnType<ApiClient["getBondAnalyticsTopHoldings"]>>>((resolve) => { finishOld = resolve; });
    const getBondAnalyticsTopHoldings = vi.fn((date: string, limit?: number) =>
      date === "2026-05-31" ? oldResponse : mockClient.getBondAnalyticsTopHoldings(date, limit),
    );
    const dataClient = createHomeViewModelClient({ getBondAnalyticsTopHoldings });
    const { result, rerender } = renderHook(({ reportDate }) =>
      useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, reportDate), {
        sections: { holdings: true, risk: false, market: false, support: false, evidence: false },
      }), { initialProps: { reportDate: "2026-05-31" }, wrapper: createWrapper() },
    );
    expect(result.current.view.holdingsState.kind).toBe("loading");
    rerender({ reportDate: "2026-06-30" });
    await waitFor(() => expect(result.current.view.holdingsState.kind).toBe("ready"));
    const currentRows = result.current.view.holdingRows;
    await act(async () => { finishOld(await mockClient.getBondAnalyticsTopHoldings("2026-05-31", 14)); });
    expect(result.current.view.reportDate).toBe("2026-06-30");
    expect(result.current.view.holdingRows).toEqual(currentRows);
  });

  it("does not show cached mock holdings when the data source switches to real", async () => {
    const mockClient = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 60_000 } },
    });
    const realClient = createHomeViewModelClient({
      getBondAnalyticsTopHoldings: vi.fn(() => new Promise<never>(() => {})),
    });
    const { result, rerender } = renderHook(({ dataClient }) =>
      useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, "2026-05-31"), {
        sections: { holdings: true, risk: false, market: false, support: false, evidence: false },
      }), { initialProps: { dataClient: mockClient }, wrapper: createWrapper(queryClient) },
    );
    await waitFor(() => expect(queryClient.getQueryState(
      apiQueryKeys.bondAnalyticsTopHoldings("mock", "2026-05-31", 14),
    )?.status).toBe("success"));
    rerender({ dataClient: realClient });
    expect(result.current.view.holdingsState.kind).toBe("loading");
    expect(result.current.view.holdingRows).toEqual([]);
    expect(realClient.getBondAnalyticsTopHoldings).toHaveBeenCalledWith("2026-05-31", 14);
  });

  it("queries current-day research independently from the portfolio report date", async () => {
    const reportDate = "2026-05-31";
    const queryClient = createQueryClient();
    const getHomeResearchReports = vi.fn(
      createApiClient({ mode: "mock" }).getHomeResearchReports,
    );
    const dataClient = createHomeViewModelClient({
      getHomeResearchReports,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderHook(() => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, reportDate)), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(
      () => {
        expect(getHomeResearchReports).toHaveBeenCalledWith(todayIsoDate(), 5);
      },
      { timeout: GATED_QUERY_TIMEOUT_MS },
    );
    expect(getHomeResearchReports).not.toHaveBeenCalledWith(reportDate, 5);

    const query = queryClient.getQueryCache().find({
      queryKey: ["home", "research-reports", "real", todayIsoDate(), 5],
      exact: true,
    });
    expect(query?.observers[0]?.options.refetchInterval).toBe(
      DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS,
    );
    expect(query?.observers[0]?.options.refetchIntervalInBackground).toBe(false);
    expect(query?.observers[0]?.options.refetchOnWindowFocus).toEqual(expect.any(Function));
  });

  it("switches research requests and query keys to the new local date after focus", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 28, 23, 59, 59));
    const reportDate = "2026-08-31";
    const queryClient = createQueryClient();
    const mockClient = createApiClient({ mode: "mock" });
    const getHomeResearchReports = vi.fn(mockClient.getHomeResearchReports);
    const getBondDashboardHomeSummary = vi.fn(mockClient.getBondDashboardHomeSummary);
    const dataClient = createHomeViewModelClient({
      getHomeResearchReports,
      getBondDashboardHomeSummary,
    });
    const { unmount } = renderHook(
      () => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, reportDate), {
        sections: { holdings: false, risk: false, market: true, support: false, evidence: false },
      }),
      { wrapper: createWrapper(queryClient) },
    );
    try {
      await waitFor(() => expect(getHomeResearchReports).toHaveBeenCalledWith("2026-09-28", 5));
      const previousDayRequests = getHomeResearchReports.mock.calls.filter(([date]) => date === "2026-09-28").length;

      vi.setSystemTime(new Date(2026, 8, 29, 0, 0, 1));
      act(() => window.dispatchEvent(new Event("focus")));

      await waitFor(() => expect(getHomeResearchReports).toHaveBeenCalledWith("2026-09-29", 5));
      await waitFor(() => expect(
        queryClient.getQueryState(apiQueryKeys.homeResearchReports("real", "2026-09-29", 5))?.status,
      ).toBe("success"));
      expect(getHomeResearchReports.mock.calls.filter(([date]) => date === "2026-09-28")).toHaveLength(previousDayRequests);
      expect(getBondDashboardHomeSummary).toHaveBeenCalledWith(reportDate);
      expect(getBondDashboardHomeSummary).not.toHaveBeenCalledWith("2026-09-29");
    } finally {
      unmount();
      vi.useRealTimers();
    }
  });

  it("updates research requests at local midnight while the page stays open", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 8, 28, 23, 59, 59));
    const mockClient = createApiClient({ mode: "mock" });
    const getHomeResearchReports = vi.fn(mockClient.getHomeResearchReports);
    const dataClient = createHomeViewModelClient({ getHomeResearchReports });
    const { unmount } = renderHook(
      () => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, "2026-08-31"), {
        sections: { holdings: false, risk: false, market: true, support: false, evidence: false },
      }),
      { wrapper: createWrapper() },
    );
    try {
      await act(async () => { await vi.advanceTimersByTimeAsync(10); });
      expect(getHomeResearchReports).toHaveBeenCalledWith("2026-09-28", 5);

      await act(async () => { await vi.advanceTimersByTimeAsync(1_100); });
      expect(getHomeResearchReports).toHaveBeenCalledWith("2026-09-29", 5);
    } finally {
      unmount();
      vi.clearAllTimers();
      vi.useRealTimers();
    }
  });
  it("preserves the Campisi result quality error even when formal use is allowed", async () => {
    const mockClient = createApiClient({ mode: "mock" });
    const getPnlCampisiFourEffects = vi.fn(async (options: Parameters<ApiClient["getPnlCampisiFourEffects"]>[0]) => {
      const envelope = await mockClient.getPnlCampisiFourEffects(options);
      return {
        ...envelope,
        result: { ...mockCampisiFourEffectsModelPath, report_date: "2026-08-31", period_start: "2026-07-31", period_end: "2026-08-31" },
        result_meta: { ...envelope.result_meta, quality_flag: "error" as const, formal_use_allowed: true },
      };
    });
    const dataClient = createHomeViewModelClient({
      getPnlCampisiFourEffects,
      getResearchCalendarEvents: vi.fn(async () => []),
    });
    const { result } = renderHook(
      () => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, "2026-08-31")),
      { wrapper: createWrapper() },
    );
    await waitFor(() => {
      expect(result.current.view.marketContext.attributionCoverage.state).toBe("error");
    }, { timeout: GATED_QUERY_TIMEOUT_MS });
    expect(result.current.view.marketContext.attributionCoverage.effectNotices.join(" ")).toContain("数据质量错误");
    expect(result.current.view.marketContext.attributionCoverage.basisLabel).toContain("不可正式使用");
  });

  it("passes Campisi formal-use metadata and rejects an old source date after the home date changes", async () => {
    const mockClient = createApiClient({ mode: "mock" });
    const payload: CampisiFourEffectsPayload = {
      ...mockCampisiFourEffectsModelPath,
      report_date: "2026-08-30",
      period_start: "2026-08-01",
      period_end: "2026-08-30",
      effect_availability: {
        bonds: 2,
        position_change: {
          status: "partial", reason: "principal_change_without_cashflows",
          unavailable_bonds: 1, covered_bonds: 1,
          unavailable_market_value_start: 50_000_000, unavailable_market_value_end: 30_000_000,
        },
        treasury_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
        spread_effect: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
        accrued_interest: { status: "ok", reason: null, unavailable_bonds: 0, unavailable_market_value_start: 0 },
      },
    };
    const getPnlCampisiFourEffects = vi.fn(async (options: Parameters<ApiClient["getPnlCampisiFourEffects"]>[0]) => {
      const envelope = await mockClient.getPnlCampisiFourEffects(options);
      return {
        ...envelope,
        result: payload,
        result_meta: { ...envelope.result_meta, formal_use_allowed: false },
      };
    });
    const dataClient = createHomeViewModelClient({
      getPnlCampisiFourEffects,
      getResearchCalendarEvents: vi.fn(async () => []),
    });
    const { result, rerender } = renderHook(
      ({ reportDate }) => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, reportDate)),
      { initialProps: { reportDate: "2026-08-30" }, wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.view.marketContext.attributionCoverage.state).toBe("partial");
    }, { timeout: GATED_QUERY_TIMEOUT_MS });
    expect(result.current.view.marketContext.attributionCoverage.basisLabel).toContain("不可正式使用");
    expect(result.current.view.marketContext.attributionCoverage.detailPath).toContain("campisi_end_date=2026-08-30");

    rerender({ reportDate: "2026-08-31" });
    await waitFor(() => {
      expect(getPnlCampisiFourEffects).toHaveBeenCalledWith({ startDate: "2026-07-31", endDate: "2026-08-31", lookbackDays: 30, detail: "summary" });
      expect(result.current.view.marketContext.attributionCoverage.state).toBe("date-mismatch");
    }, { timeout: GATED_QUERY_TIMEOUT_MS });
    expect(result.current.view.marketContext.attributionCoverage.detailPath).toBeNull();
  });

});
