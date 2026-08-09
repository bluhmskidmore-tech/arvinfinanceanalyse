import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
import {
  DASHBOARD_BOND_NEWS_TOPICS,
  DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS,
} from "../dashboard/dashboardMacroNewsTopics";
import { todayIsoDate } from "../pages/dashboardPageHelpers";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";
import { useDashboardHomeViewModel } from "./useDashboardHomeViewModel";

const BOND_NEWS_PROBE_GROUP_ID = DASHBOARD_BOND_NEWS_TOPICS[0]?.groupId;

// Gate release must stay well under these budgets. They intentionally sit far
// below the previous implementation's worst case (2s for the body-detail /
// body-structure chain, 3s+ for the event-feed / secondary / bond-news
// chain), so a regression back to long per-tier delays fails this test.
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

describe("useDashboardHomeViewModel release timing", () => {
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

  it("releases the body-detail/body-structure chain well under the previous 2-second budget", async () => {
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

  it("releases the event-feed/secondary/bond-news chain well under the previous 3-second budget", async () => {
    const reportDate = "2026-05-31";
    const getChoiceNewsEvents = vi.fn(createApiClient({ mode: "mock" }).getChoiceNewsEvents);
    const dataClient = createHomeViewModelClient({
      getChoiceNewsEvents,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderHook(() => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, reportDate)), {
      wrapper: createWrapper(),
    });

    await waitFor(
      () => {
        expect(getChoiceNewsEvents).toHaveBeenCalled();
      },
      { timeout: GATED_QUERY_TIMEOUT_MS },
    );
  });

  it("fires the bond news probe after the event-feed tier, no longer chained behind the macro fallback tier", async () => {
    expect(BOND_NEWS_PROBE_GROUP_ID).toBeTruthy();
    const reportDate = "2026-05-31";
    const getChoiceNewsEvents = vi.fn(createApiClient({ mode: "mock" }).getChoiceNewsEvents);
    const dataClient = createHomeViewModelClient({
      getChoiceNewsEvents,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderHook(() => useDashboardHomeViewModel(buildSnapshotBoundary(dataClient, reportDate)), {
      wrapper: createWrapper(),
    });

    // Each idle gate resolves in ~350ms in this jsdom environment (no
    // requestIdleCallback, so it falls through to the timeout fallback).
    // The bond news probe now depends only on the event-feed tier (one gate,
    // ~350ms), not on the event-feed -> secondary-event-feed chain (two
    // gates, ~700ms) that used to sit in front of it. Asserting it resolves
    // well inside a single extra tier's budget catches any regression back
    // to the three-tier chain (which would need ~1050ms).
    await waitFor(
      () => {
        expect(
          getChoiceNewsEvents.mock.calls.some(
            ([params]) => params.groupId === BOND_NEWS_PROBE_GROUP_ID,
          ),
        ).toBe(true);
      },
      { timeout: 850 },
    );
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
    expect(query?.observers[0]?.options.refetchOnWindowFocus).toBe(true);
  });
});
