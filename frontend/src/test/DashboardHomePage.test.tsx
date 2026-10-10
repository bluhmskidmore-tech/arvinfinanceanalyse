import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, getConfig, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="dashboard-echarts-stub" />,
}));

vi.mock("../app/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../app/navigation")>()),
  isAgentFrontendEnabled: () => true,
}));

vi.mock("../features/agent/AgentPanel", () => ({
  AgentPanel: function MockAgentPanel({
    pageId,
    reportDate = null,
    currentFilters = {},
    defaultFilters = {},
    selectedRows = [],
    contextNote = null,
  }: {
    pageId: string;
    reportDate?: string | null;
    currentFilters?: Record<string, unknown>;
    defaultFilters?: Record<string, unknown>;
    selectedRows?: Array<Record<string, unknown>>;
    contextNote?: string | null;
  }) {
    const pageContext = {
      page_id: pageId,
      current_filters:
        reportDate != null
          ? { ...defaultFilters, ...currentFilters, report_date: reportDate }
          : { ...defaultFilters, ...currentFilters },
      selected_rows: selectedRows,
      context_note: contextNote,
    };
    return (
      <div data-testid="agent-panel">
        <code data-testid="agent-panel-page-context">{JSON.stringify(pageContext)}</code>
      </div>
    );
  },
}));

import { createApiClient, type ApiClient } from "../api/client";
import { ApiClientProvider } from "../api/clientContext";
import { getApiClientFactoryRecord, registerApiClientFactory } from "../api/clientFactoryOptions";
import type {
  ApiEnvelope,
  ChoiceNewsEvent,
  ChoiceNewsEventsBatchPayload,
  Numeric,
} from "../api/contracts";
import { apiQueryKeys } from "../api/queryKeys";
import { SYSTEM_READ_GENERATION_HEADER } from "../api/systemReadGeneration";
import {
  DASHBOARD_BOND_NEWS_TOPICS,
  DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS,
  DASHBOARD_MACRO_NEWS_TOPICS,
} from "../features/workbench/dashboard/dashboardMacroNewsTopics";
import DashboardHomePage from "../features/workbench/dashboard-home/DashboardHomePage";
import { todayIsoDate as resolveTodayIsoDate } from "../features/workbench/pages/dashboardPageHelpers";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

type MockIntersectionObserver = {
  observe: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
  options: IntersectionObserverInit[];
  triggerAll: (entry?: Partial<IntersectionObserverEntry>) => void;
};

afterEach(() => {
  if (restoreHomeGateTimers) {
    restoreHomeGateTimers();
    restoreHomeGateTimers = null;
  }
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  vi.stubGlobal("IntersectionObserver", undefined);
});

beforeAll(async () => {
  await preloadWorkbenchRouteModules("dashboard-home");
}, 60_000);

function stubIntersectionObserver(): MockIntersectionObserver {
  const callbacks: IntersectionObserverCallback[] = [];
  const options: IntersectionObserverInit[] = [];
  const observer: MockIntersectionObserver = {
    observe: vi.fn(),
    disconnect: vi.fn(),
    options,
    triggerAll: (entry = {}) => {
      const target = (entry.target ?? document.createElement("div")) as Element;
      for (const callback of callbacks) {
        callback(
          [
            {
              isIntersecting: false,
              intersectionRatio: 0,
              target,
              ...entry,
            } as IntersectionObserverEntry,
          ],
          {} as IntersectionObserver,
        );
      }
    },
  };
  const MockObserver = vi.fn(function MockIntersectionObserver(
    callback: IntersectionObserverCallback,
    init?: IntersectionObserverInit,
  ) {
    callbacks.push(callback);
    options.push(init ?? {});
    return observer;
  });

  vi.stubGlobal("IntersectionObserver", MockObserver);
  return observer;
}


function createRealModeHomeClient(overrides: Partial<ApiClient> = {}): ApiClient {
  const base = createApiClient({ mode: "real" });
  const mockSnapshotSource = createApiClient({ mode: "mock" });
  return {
    ...base,
    getHomeSnapshot: (...args) => mockSnapshotSource.getHomeSnapshot(...args),
    // 分层门控打开后首页会请求的跨域补充接口：统一走 mock 本地实现，
    // 避免 jsdom 里发真实 fetch 产生网络错误噪音。
    getBondAnalyticsKrdCurveRisk: (...args) =>
      mockSnapshotSource.getBondAnalyticsKrdCurveRisk(...args),
    getBalanceAnalysisDates: (...args) => mockSnapshotSource.getBalanceAnalysisDates(...args),
    getBalanceAnalysisDecisionItems: (...args) =>
      mockSnapshotSource.getBalanceAnalysisDecisionItems(...args),
    ...overrides,
  };
}

function renderDashboardHome(client?: ApiClient) {
  const resolvedClient = client ?? createApiClient({ mode: "mock" });
  if (resolvedClient.mode === "real" && !getApiClientFactoryRecord(resolvedClient)) {
    registerApiClientFactory(
      resolvedClient,
      {
        mode: "real",
        baseUrl: "",
        fetchImpl: async (input) => {
          const path = new URL(String(input), "http://moss.local").pathname;
          if (path === "/api/system-read-publication") {
            return jsonResponse({ enabled: false, generation: null, coverage_dates: {} });
          }
          throw new Error(`Unexpected factory fetch in homepage test: ${path}`);
        },
      },
      () => resolvedClient,
    );
  }
  return renderWorkbenchApp(["/"], {
    client: resolvedClient,
  });
}

type HomeSnapshotEnvelope = Awaited<ReturnType<ApiClient["getHomeSnapshot"]>>;

function homeSnapshotWithAumDisplay(
  envelope: HomeSnapshotEnvelope,
  raw: number,
  display: string,
): HomeSnapshotEnvelope {
  return {
    ...envelope,
    result: {
      ...envelope.result,
      overview: {
        ...envelope.result.overview,
        metrics: envelope.result.overview.metrics.map((metric) =>
          metric.id === "aum"
            ? { ...metric, value: { ...metric.value, raw, display } }
            : metric,
        ),
      },
    },
  };
}

function jsonResponse(payload: unknown, generation?: string) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      ...(generation ? { [SYSTEM_READ_GENERATION_HEADER]: generation } : {}),
    },
  });
}

function renderPolicyFundingDeepLink(client?: ApiClient) {
  return renderWorkbenchApp(["/政策与资金面"], {
    client: client ?? createApiClient({ mode: "mock" }),
  });
}

let restoreHomeGateTimers: (() => void) | null = null;
const pendingHomeDelays = new Map<Parameters<typeof window.clearTimeout>[0], number>();

function enableHomeGateTimerCompression() {
  if (restoreHomeGateTimers) {
    return;
  }

  const originalSetTimeout = window.setTimeout;
  const originalClearTimeout = window.clearTimeout;

  // Only short window timers within RTL's existing wait budget are accelerated.
  // Keep query TTLs, RTL deadlines and refetch intervals on their original clocks.
  // Preserve relative delays without copying production gate constants here.
  window.setTimeout = ((...args: Parameters<typeof window.setTimeout>) => {
    const [handler, timeout, ...rest] = args;
    if (
      typeof handler !== "function" || !timeout || timeout <= 0 ||
      timeout >= getConfig().asyncUtilTimeout
    ) {
      return originalSetTimeout.call(window, handler, timeout, ...rest);
    }
    const handle = originalSetTimeout.call(
      window,
      () => {
        pendingHomeDelays.delete(handle);
        handler(...rest);
      },
      Math.max(1, Math.ceil(timeout / 50)),
    );
    pendingHomeDelays.set(handle, timeout);
    return handle;
  }) as unknown as typeof window.setTimeout;
  window.clearTimeout = (handle) => {
    if (handle != null) pendingHomeDelays.delete(handle);
    originalClearTimeout.call(window, handle);
  };

  restoreHomeGateTimers = () => {
    for (const handle of pendingHomeDelays.keys()) {
      originalClearTimeout.call(window, handle);
    }
    pendingHomeDelays.clear();
    window.setTimeout = originalSetTimeout;
    window.clearTimeout = originalClearTimeout;
  };
}

async function flushHomeQueryNotifications() {
  await act(async () => {
    await new Promise((resolve) => globalThis.setTimeout(resolve, 0));
  });
}

async function settleHomeTimersWithoutIdle() {
  // Let pending timeouts and query notifications finish, but keep idle work
  // blocked so negative assertions observe a fully scheduled, unopened gate.
  await waitFor(
    async () => {
      await flushHomeQueryNotifications();
      expect([...pendingHomeDelays.values()], "pending home window delays").toEqual([]);
    },
    { interval: 1 },
  );
}

function stubIdleCallbacks() {
  enableHomeGateTimerCompression();
  const callbacks = new Map<number, () => void>();
  let nextHandle = 1;

  vi.stubGlobal(
    "requestIdleCallback",
    vi.fn((callback: () => void) => {
      const handle = nextHandle;
      nextHandle += 1;
      callbacks.set(handle, callback);
      return handle;
    }),
  );
  vi.stubGlobal(
    "cancelIdleCallback",
    vi.fn((handle: number) => {
      callbacks.delete(handle);
    }),
  );

  return {
    pendingCount: () => callbacks.size,
    runPending: () => {
      const pending = Array.from(callbacks.values());
      callbacks.clear();
      for (const callback of pending) {
        callback();
      }
    },
  };
}

type StubbedIdleCallbacks = ReturnType<typeof stubIdleCallbacks>;

async function runNextIdle(idle: StubbedIdleCallbacks) {
  await waitFor(
    () => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    },
    { interval: 1 },
  );
  await act(async () => {
    idle.runPending();
  });
}

async function settleHomeIdleWork(idle: StubbedIdleCallbacks) {
  // Finish remaining work for final request/content assertions. Tests of a
  // boundary use runNextIdle and assert before releasing the following wave.
  // The normal RTL deadline bounds the drain and reports any remaining delays.
  // Flush query observers outside the gate act, so their dependent effects can
  // enqueue the next wave before deciding that this page's queue is empty.
  await waitFor(
    async () => {
      await act(async () => { idle.runPending(); });
      await flushHomeQueryNotifications();
      expect(screen.getByTestId("dashboard-home-work-grid")).toBeInTheDocument();
      expect([...pendingHomeDelays.values()], "pending home window delays").toEqual([]);
      expect(idle.pendingCount(), "pending home idle callbacks").toBe(0);
    },
    { interval: 1 },
  );
}

type ChoiceNewsBatchOptions = Parameters<ApiClient["getChoiceNewsEventsBatch"]>[0];
type ChoiceNewsBatchSpy = {
  mock: { calls: Array<[ChoiceNewsBatchOptions]> };
};

// 批量化后请求形态从“每 topic 一次调用”变为“每波一次批量调用”，
// 这些 helper 把批量调用摊平回 topic/group 维度，让原有场景断言语义保持不变。
function requestedNewsTopicCodes(spy: ChoiceNewsBatchSpy): string[] {
  return spy.mock.calls.flatMap(([options]) =>
    (options.topics ?? []).map(({ topicCode }) => topicCode),
  );
}

function requestedNewsTopicCount(spy: ChoiceNewsBatchSpy, topicCode: string): number {
  return requestedNewsTopicCodes(spy).filter((requestedTopicCode) => requestedTopicCode === topicCode).length;
}

function requestedNewsGroupIds(spy: ChoiceNewsBatchSpy): string[] {
  return spy.mock.calls.flatMap(([options]) =>
    (options.groups ?? []).map(({ groupId }) => groupId),
  );
}

function bondNewsGroupIds(): string[] {
  return DASHBOARD_BOND_NEWS_TOPICS.map((topic) => topic.groupId);
}

function choiceNewsEvent(overrides: Partial<ChoiceNewsEvent>): ChoiceNewsEvent {
  return {
    event_key: overrides.event_key ?? "home-choice-news-ok",
    received_at: overrides.received_at ?? "2026-06-04T09:30:00Z",
    group_id: overrides.group_id ?? "home",
    content_type: overrides.content_type ?? "sectornews",
    serial_id: overrides.serial_id ?? 1,
    request_id: overrides.request_id ?? 1,
    error_code: overrides.error_code ?? 0,
    error_msg: overrides.error_msg ?? "",
    topic_code: overrides.topic_code ?? DASHBOARD_MACRO_NEWS_TOPICS[0].code,
    item_index: overrides.item_index ?? 0,
    payload_text: overrides.payload_text ?? "资金面维持平稳，DR007 小幅回落。",
    payload_json: overrides.payload_json ?? null,
  };
}

/** 按契约回放批量响应：batches 顺序与请求顺序一致（先 topics 后 groups）。 */
function choiceNewsBatchEnvelope(
  options: ChoiceNewsBatchOptions,
  eventsForTopic: (topicCode: string) => ChoiceNewsEvent[] = () => [],
  eventsForGroup: (groupId: string) => ChoiceNewsEvent[] = () => [],
): ApiEnvelope<ChoiceNewsEventsBatchPayload> {
  return {
    result_meta: {
      basis: "formal",
      trace_id: "tr_home_choice_news_test",
      result_kind: "news.choice.latest_batch",
      formal_use_allowed: true,
      source_version: "sv_test",
      vendor_version: "vv_test",
      rule_version: "rv_test",
      cache_version: "cv_test",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-06-04T00:00:00Z",
    },
    result: {
      batches: [
        ...(options.topics ?? []).map(({ topicCode }) => ({
          key: `topic:${topicCode}`,
          topic_code: topicCode,
          group_id: null,
          events: eventsForTopic(topicCode),
        })),
        ...(options.groups ?? []).map(({ groupId }) => ({
          key: `group:${groupId}`,
          topic_code: null,
          group_id: groupId,
          events: eventsForGroup(groupId),
        })),
      ],
    },
  };
}

function createSupplementalHomeSpies(mockSnapshotSource: ApiClient) {
  return {
    getMarketDataRates: vi.fn(mockSnapshotSource.getMarketDataRates),
    getCoreMetrics: vi.fn(mockSnapshotSource.getCoreMetrics),
    getDailyChanges: vi.fn(mockSnapshotSource.getDailyChanges),
    getBondDashboardHeadlineKpis: vi.fn(mockSnapshotSource.getBondDashboardHeadlineKpis),
    getBondDashboardHomeSummary: vi.fn(mockSnapshotSource.getBondDashboardHomeSummary),
    getBondAnalyticsPortfolioHeadlines: vi.fn(mockSnapshotSource.getBondAnalyticsPortfolioHeadlines),
    getBondDashboardPortfolioComparison: vi.fn(mockSnapshotSource.getBondDashboardPortfolioComparison),
    getBondAnalyticsCreditSpreadMigration: vi.fn(mockSnapshotSource.getBondAnalyticsCreditSpreadMigration),
    getBondAnalyticsReturnDecomposition: vi.fn(mockSnapshotSource.getBondAnalyticsReturnDecomposition),
    getPnlCampisiFourEffects: vi.fn(mockSnapshotSource.getPnlCampisiFourEffects),
    getBondAnalyticsYieldCurveTermStructure: vi.fn(mockSnapshotSource.getBondAnalyticsYieldCurveTermStructure),
    getBondAnalyticsKrdCurveRisk: vi.fn(mockSnapshotSource.getBondAnalyticsKrdCurveRisk),
    getBalanceAnalysisDates: vi.fn(mockSnapshotSource.getBalanceAnalysisDates),
    getBalanceAnalysisDecisionItems: vi.fn(mockSnapshotSource.getBalanceAnalysisDecisionItems),
    getResearchCalendarEvents: vi.fn(async () => []),
    getChoiceNewsEvents: vi.fn(mockSnapshotSource.getChoiceNewsEvents),
    getChoiceNewsEventsBatch: vi.fn(mockSnapshotSource.getChoiceNewsEventsBatch),
    getBondDashboardAssetStructure: vi.fn(mockSnapshotSource.getBondDashboardAssetStructure),
    getBondDashboardMaturityStructure: vi.fn(mockSnapshotSource.getBondDashboardMaturityStructure),
    getBondDashboardIndustryDistribution: vi.fn(mockSnapshotSource.getBondDashboardIndustryDistribution),
    getBondDashboardRiskIndicators: vi.fn(mockSnapshotSource.getBondDashboardRiskIndicators),
    getBondAnalyticsTopHoldings: vi.fn(mockSnapshotSource.getBondAnalyticsTopHoldings),
    getBondAnalyticsPositionChanges: vi.fn(mockSnapshotSource.getBondAnalyticsPositionChanges),
    getHomeResearchReports: vi.fn(mockSnapshotSource.getHomeResearchReports),
    getHomeIncomeTrend: vi.fn(mockSnapshotSource.getHomeIncomeTrend),
    getCockpitWarnings: vi.fn(mockSnapshotSource.getCockpitWarnings),
  };
}

describe("DashboardHomePage", () => {
  it("opens a new fixed-generation interaction from the real home refresh button", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const baseSnapshot = await mockSource.getHomeSnapshot();
    const snapshots = {
      "full-gen-r0": homeSnapshotWithAumDisplay(baseSnapshot, 10_000_000_000, "100.00 亿"),
      "full-gen-r1": homeSnapshotWithAumDisplay(baseSnapshot, 20_000_000_000, "200.00 亿"),
    };
    let publishedGeneration: keyof typeof snapshots = "full-gen-r0";
    let handshakeCount = 0;
    const snapshotRequestGenerations: Array<string | null> = [];
    const fetchImpl = vi.fn<typeof fetch>(async (input, init) => {
      const path = new URL(String(input), "http://moss.local").pathname;
      if (path === "/api/system-read-publication") {
        handshakeCount += 1;
        return jsonResponse(
          { enabled: true, generation: publishedGeneration, coverage_dates: {} },
          publishedGeneration,
        );
      }
      if (path === "/ui/home/snapshot") {
        const requestGeneration = new Headers(init?.headers).get(SYSTEM_READ_GENERATION_HEADER);
        snapshotRequestGenerations.push(requestGeneration);
        if (requestGeneration !== publishedGeneration) {
          throw new Error(`Unexpected home generation ${String(requestGeneration)}`);
        }
        return jsonResponse(snapshots[publishedGeneration], publishedGeneration);
      }
      throw new Error(`Unexpected homepage request ${path}`);
    });

    renderDashboardHome(createApiClient({ mode: "real", fetchImpl }));

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("100.00");
    });
    publishedGeneration = "full-gen-r1";
    fireEvent.click(screen.getByRole("button", { name: "刷新首页数据" }));

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("200.00");
    });
    expect(handshakeCount).toBe(2);
    expect(snapshotRequestGenerations).toEqual(["full-gen-r0", "full-gen-r1"]);
  });

  it("keeps the selected report date across a fixed-generation refresh", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const baseSnapshot = await mockSource.getHomeSnapshot();
    const snapshots = {
      "full-gen-r0": homeSnapshotWithAumDisplay(baseSnapshot, 10_000_000_000, "100.00 亿"),
      "full-gen-r1": homeSnapshotWithAumDisplay(baseSnapshot, 20_000_000_000, "200.00 亿"),
    };
    let publishedGeneration: keyof typeof snapshots = "full-gen-r0";
    let handshakeCount = 0;
    const requestedDates: Array<string | null> = [];
    const snapshotRequestGenerations: Array<string | null> = [];
    const fetchImpl = vi.fn<typeof fetch>(async (input, init) => {
      const url = new URL(String(input), "http://moss.local");
      if (url.pathname === "/api/system-read-publication") {
        handshakeCount += 1;
        return jsonResponse(
          { enabled: true, generation: publishedGeneration, coverage_dates: {} },
          publishedGeneration,
        );
      }
      if (url.pathname === "/ui/home/snapshot") {
        requestedDates.push(url.searchParams.get("report_date"));
        const requestGeneration = new Headers(init?.headers).get(SYSTEM_READ_GENERATION_HEADER);
        snapshotRequestGenerations.push(requestGeneration);
        if (requestGeneration !== publishedGeneration) {
          throw new Error(`Unexpected home generation ${String(requestGeneration)}`);
        }
        return jsonResponse(snapshots[publishedGeneration], publishedGeneration);
      }
      throw new Error(`Unexpected homepage request ${url.pathname}`);
    });

    renderDashboardHome(createApiClient({ mode: "real", fetchImpl }));

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("100.00");
    });
    fireEvent.change(screen.getByLabelText("报告日"), {
      target: { value: "2026-07-31" },
    });
    await waitFor(() => {
      expect(requestedDates).toContain("2026-07-31");
      expect(screen.getByLabelText("报告日")).toHaveValue("2026-07-31");
    });

    publishedGeneration = "full-gen-r1";
    fireEvent.click(screen.getByRole("button", { name: "刷新首页数据" }));

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("200.00");
    });
    // Date selection keeps the confirmed generation; explicit refresh acquires a new one.
    expect(handshakeCount).toBe(2);
    expect(snapshotRequestGenerations).toEqual([
      "full-gen-r0",
      "full-gen-r0",
      "full-gen-r1",
    ]);
    expect(requestedDates).toEqual([null, "2026-07-31", "2026-07-31"]);
    expect(screen.getByLabelText("报告日")).toHaveValue("2026-07-31");
  });

  it("keeps the existing home query refetch when fixed-generation reads are disabled", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const snapshot = await mockSource.getHomeSnapshot();
    let handshakeCount = 0;
    const snapshotRequestGenerations: Array<string | null> = [];
    const fetchImpl = vi.fn<typeof fetch>(async (input, init) => {
      const path = new URL(String(input), "http://moss.local").pathname;
      if (path === "/api/system-read-publication") {
        handshakeCount += 1;
        return jsonResponse({ enabled: false, generation: null, coverage_dates: {} });
      }
      if (path === "/ui/home/snapshot") {
        snapshotRequestGenerations.push(
          new Headers(init?.headers).get(SYSTEM_READ_GENERATION_HEADER),
        );
        return jsonResponse(snapshot);
      }
      throw new Error(`Unexpected homepage request ${path}`);
    });

    renderDashboardHome(createApiClient({ mode: "real", fetchImpl }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "刷新首页数据" })).not.toHaveAttribute(
        "aria-busy",
        "true",
      );
    });
    expect(snapshotRequestGenerations).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "刷新首页数据" }));
    await waitFor(() => expect(snapshotRequestGenerations).toHaveLength(2));
    expect(handshakeCount).toBe(1);
    expect(snapshotRequestGenerations).toEqual([null, null]);
  });

  it("keeps the existing home query refetch without a generation boundary", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>((...args) =>
      mockSource.getHomeSnapshot(...args),
    );
    const client: ApiClient = { ...mockSource, getHomeSnapshot };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <MemoryRouter>
        <ApiClientProvider client={client}>
          <QueryClientProvider client={queryClient}>
            <DashboardHomePage />
          </QueryClientProvider>
        </ApiClientProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "刷新首页数据" })).not.toHaveAttribute(
        "aria-busy",
        "true",
      );
    });
    expect(getHomeSnapshot).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "刷新首页数据" }));
    await waitFor(() => expect(getHomeSnapshot).toHaveBeenCalledTimes(2));
  });

  it("observes the deferred boundary as soon as the shell commits while the snapshot is pending", () => {
    const observer = stubIntersectionObserver();
    const client = createRealModeHomeClient({
      getHomeSnapshot: vi.fn(() => new Promise<HomeSnapshotEnvelope>(() => {})),
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { unmount } = render(
      <MemoryRouter>
        <ApiClientProvider client={client}>
          <QueryClientProvider client={queryClient}>
            <DashboardHomePage />
          </QueryClientProvider>
        </ApiClientProvider>
      </MemoryRouter>,
    );

    expect(observer.observe).toHaveBeenCalledWith(
      screen.getByTestId("dashboard-home-deferred-sentinel"),
    );
    expect(screen.queryByTestId("dashboard-home-work-grid")).not.toBeInTheDocument();
    unmount();
    queryClient.clear();
  });

  it("reveals requested below-fold content from a cached snapshot while its same-date background refresh is pending", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const snapshot = await mockSource.getHomeSnapshot();
    const observer = stubIntersectionObserver();
    stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSource);
    let releaseRefresh!: () => void;
    const refresh = new Promise<HomeSnapshotEnvelope>((resolve) => {
      releaseRefresh = () => resolve(snapshot);
    });
    const getHomeSnapshot = vi.fn(() => refresh);
    const client = createRealModeHomeClient({
      ...supplementalCalls,
      getHomeSnapshot,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(mockSource.getLedgerPnlCandidateFinancialIndicators),
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["home-snapshot", "real", "latest", false], snapshot);
    const { unmount } = render(
      <MemoryRouter>
        <ApiClientProvider client={client}>
          <QueryClientProvider client={queryClient}>
            <DashboardHomePage />
          </QueryClientProvider>
        </ApiClientProvider>
      </MemoryRouter>,
    );

    try {
      await waitFor(() => expect(getHomeSnapshot).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(observer.observe).toHaveBeenCalledWith(
        screen.getByTestId("dashboard-home-deferred-sentinel"),
      ));
      await act(async () => {
        fireEvent.scroll(window);
        observer.triggerAll({ isIntersecting: true, intersectionRatio: 1 });
      });

      expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
      expect(queryClient.isFetching({ queryKey: ["home-snapshot"] })).toBe(1);
      await waitFor(() => expect(supplementalCalls.getBondDashboardHomeSummary)
        .toHaveBeenCalledWith(snapshot.result.report_date));
    } finally {
      await act(async () => { releaseRefresh(); });
      unmount();
      queryClient.clear();
    }
  });

  it("retains new-date cached risk hydration when the loaded body switches report dates", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const reportDates = ["2026-04-30", "2026-03-31"];
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 60_000, refetchOnWindowFocus: false } },
    });
    for (const [index, reportDate] of reportDates.entries()) {
      const [snapshot, summary, portfolio] = await Promise.all([
        mockSource.getHomeSnapshot({ reportDate, allowPartial: true }),
        mockSource.getBondDashboardHomeSummary(reportDate),
        mockSource.getBondAnalyticsPortfolioHeadlines(reportDate),
      ]);
      const sourceMeta = {
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        resolved_report_date: reportDate,
        as_of_date: reportDate,
        fallback_date: undefined,
      };
      queryClient.setQueryData(["home-snapshot", "real", reportDate, true], {
        ...snapshot,
        result: { ...snapshot.result, report_date: reportDate },
        result_meta: { ...snapshot.result_meta, ...sourceMeta },
      });
      queryClient.setQueryData(apiQueryKeys.bondDashboardHomeSummary("real", reportDate), {
        ...summary,
        result: { ...summary.result, headline: { ...summary.result.headline!, report_date: reportDate } },
        result_meta: { ...summary.result_meta, ...sourceMeta },
      });
      queryClient.setQueryData(apiQueryKeys.bondAnalyticsPortfolioHeadlines("real", reportDate), {
        ...portfolio,
        result: {
          ...portfolio.result,
          report_date: reportDate,
          issuer_top5_weight: {
            ...portfolio.result.issuer_top5_weight,
            raw: index === 0 ? 0.4567 : 0.8765,
            display: index === 0 ? "0.4567" : "0.8765",
            unit: "ratio",
          },
        },
        result_meta: { ...portfolio.result_meta, ...sourceMeta },
      });
    }
    const observer = stubIntersectionObserver();
    stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSource);
    const getHomeSnapshot = vi.fn(mockSource.getHomeSnapshot);
    const client = createRealModeHomeClient({
      ...supplementalCalls,
      getHomeSnapshot,
      getLedgerPnlCandidateFinancialIndicators: vi.fn(mockSource.getLedgerPnlCandidateFinancialIndicators),
    });
    const { unmount } = render(
      <MemoryRouter initialEntries={["/?report_date=" + reportDates[0]]}>
        <ApiClientProvider client={client}>
          <QueryClientProvider client={queryClient}>
            <DashboardHomePage />
          </QueryClientProvider>
        </ApiClientProvider>
      </MemoryRouter>,
    );
    try {
      await act(async () => {
        fireEvent.scroll(window);
        observer.triggerAll({ isIntersecting: true, intersectionRatio: 1 });
      });
      expect(await screen.findByTestId("dashboard-home-risk-exposure")).toHaveTextContent("45.67%");
      const dateInput = screen.getByDisplayValue(reportDates[0]);
      await act(async () => {
        fireEvent.change(dateInput, { target: { value: reportDates[1] } });
      });
      await waitFor(() => expect(screen.getByTestId("dashboard-home-risk-exposure"))
        .toHaveTextContent("87.65%"));
      expect(screen.getByTestId("dashboard-home-risk-exposure")).not.toHaveTextContent("45.67%");
      expect(getHomeSnapshot).not.toHaveBeenCalled();
      expect(supplementalCalls.getBondDashboardHomeSummary).not.toHaveBeenCalled();
      expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).not.toHaveBeenCalled();
    } finally {
      unmount();
      queryClient.clear();
    }
  });

  it("renders the home shell while snapshot query is unresolved", async () => {
    const base = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const slowClient: ApiClient = {
      ...base,
      getHomeSnapshot: async () => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return base.getHomeSnapshot();
      },
    };

    renderDashboardHome(slowClient);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    expect(await screen.findByTestId("workbench-group-nav")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
  });

  it("opens the review copilot drawer with the dashboard page context", { timeout: 45_000 }, async () => {
    renderDashboardHome();

    const hero = await screen.findByTestId("dashboard-home-hero");
    expect(within(hero).getByTestId("dashboard-home-kpi-aum")).toBeInTheDocument();

    fireEvent.click(await screen.findByTestId("dashboard-home-agent-open"));

    // 抽屉整体懒加载（antd chunk 冷启动较慢），放宽等待时间避免抖动。
    expect(
      await screen.findByTestId("dashboard-home-agent-drawer", undefined, { timeout: 30_000 }),
    ).toBeInTheDocument();
    const contextCode = await screen.findByTestId("agent-panel-page-context", undefined, {
      timeout: 10_000,
    });
    const pageContext = JSON.parse(contextCode.textContent ?? "{}") as {
      page_id: string;
      current_filters: Record<string, unknown>;
      selected_rows: unknown[];
      context_note: string | null;
    };
    expect(pageContext.page_id).toBe("dashboard");
    expect(pageContext.current_filters.report_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(pageContext.current_filters.allow_partial).toBe(false);
    expect(typeof pageContext.current_filters.data_status).toBe("string");
    expect(pageContext.selected_rows).toEqual([]);
    expect(pageContext.context_note).toContain("组合经营日报");
  });

  it("starts event feeds and income trend when their sections enter the viewport after snapshot", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const observer = stubIntersectionObserver();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEventsBatch = vi.fn(async (options: ChoiceNewsBatchOptions) =>
      mockSnapshotSource.getChoiceNewsEventsBatch(options),
    );
    const getHomeIncomeTrend = vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
      mockSnapshotSource.getHomeIncomeTrend(...args),
    );
    const getBondAnalyticsTopHoldings = vi.fn(
      async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
      mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
    );
    const getBondAnalyticsPositionChanges = vi.fn(
      async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
      mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEventsBatch,
      getHomeIncomeTrend,
      getBondAnalyticsTopHoldings,
      getBondAnalyticsPositionChanges,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    expect(getResearchCalendarEvents).not.toHaveBeenCalled();
    expect(getChoiceNewsEventsBatch).not.toHaveBeenCalled();
    expect(getHomeIncomeTrend).not.toHaveBeenCalled();

    releaseSnapshot?.();
    await waitFor(() => expect(observer.observe).toHaveBeenCalledWith(
      screen.getByTestId("dashboard-home-deferred-sentinel"),
    ));
    await act(async () => {
      fireEvent.scroll(window);
      observer.triggerAll({ isIntersecting: true, intersectionRatio: 1 });
    });
    await screen.findByTestId("dashboard-home-work-grid");
    expect(getResearchCalendarEvents).not.toHaveBeenCalled();
    expect(getChoiceNewsEventsBatch).not.toHaveBeenCalled();
    expect(getHomeIncomeTrend).not.toHaveBeenCalled();

    await act(async () => {
      observer.triggerAll({ isIntersecting: true, intersectionRatio: 1 });
    });
    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
      expect(getChoiceNewsEventsBatch).toHaveBeenCalled();
      expect(getHomeIncomeTrend).toHaveBeenCalled();
      expect(getBondAnalyticsTopHoldings).toHaveBeenCalled();
    });
    // Batch collapses all macro topics into one request. Secondary/bond gates
    // share the same post-event-feed delay window as structure, so by this
    // point they may already be in-flight; only assert the primary macro batch.
    expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).toEqual(
      expect.arrayContaining(DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => topic.code)),
    );

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code)),
      );
    });

    await waitFor(() => {
      expect(requestedNewsGroupIds(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(bondNewsGroupIds()),
      );
    });

    expect(getHomeIncomeTrend).toHaveBeenCalled();
  });

  it("keeps stored-news reread available while source updates remain backend-controlled", async () => {
    const idle = stubIdleCallbacks();
    renderDashboardHome();

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await settleHomeIdleWork(idle);

    const bondNews = await screen.findByTestId("dashboard-home-bond-news");
    expect(
      within(bondNews).getByRole("button", {
        name: "重新读取已落库新闻与研报",
      }),
    ).toBeEnabled();
    expect(
      within(bondNews).getByRole("button", {
        name: "来源更新由后台受控任务维护",
      }),
    ).toBeDisabled();
  });

  // 路由层已将 /政策与资金面 重定向到 canonical "/"（见 routes.tsx），
  // 深链不再原地渲染，也不再触发政策资金面聚焦与即时事件订阅。
  it("redirects the policy funding Chinese deep link to the canonical home without focus mode", async () => {
    const idle = stubIdleCallbacks();
    renderPolicyFundingDeepLink();

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await runNextIdle(idle);

    const policyFundingPane = await screen.findByTestId("dashboard-home-policy-funding-pane");
    expect(policyFundingPane).not.toHaveAttribute("data-focused");
  });

  it("skips macro fallback news when Choice macro news is fresh and usable", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEventsBatch = vi.fn(async (options: ChoiceNewsBatchOptions) =>
      choiceNewsBatchEnvelope(options, (topicCode) =>
        DASHBOARD_MACRO_NEWS_TOPICS.some((topic) => topic.code === topicCode)
          ? [
              choiceNewsEvent({
                received_at: `${resolveTodayIsoDate()}T09:30:00Z`,
                topic_code: topicCode,
                payload_text: "资金面维持平稳，DR007 小幅回落。",
              }),
            ]
          : [],
      ),
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEventsBatch,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await settleHomeIdleWork(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => topic.code)),
      );
    });
    expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).not.toEqual(
      expect.arrayContaining(DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code)),
    );

    await waitFor(() => {
      expect(requestedNewsGroupIds(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(bondNewsGroupIds()),
      );
    });
    // 债券 group 批量请求不携带 topics，宏观 topic 批量请求不携带 groups。
    expect(
      getChoiceNewsEventsBatch.mock.calls
        .filter(([options]) => (options.groups?.length ?? 0) > 0)
        .every(([options]) => (options.topics?.length ?? 0) === 0),
    ).toBe(true);
    expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).not.toEqual(
      expect.arrayContaining(DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code)),
    );
    expect(getResearchCalendarEvents).toHaveBeenCalled();
  });

  // 原“probe 权限错误时跳过剩余 topic”改为批量语义：一个批量请求覆盖全部宏观
  // topic（无级联可跳过），权限错误按 topic 落在各自 events 中，兜底触发语义不变。
  it("keeps macro topics in one batch and still triggers fallback when the probe topic reports missing permission", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEventsBatch = vi.fn(async (options: ChoiceNewsBatchOptions) =>
      choiceNewsBatchEnvelope(options, (topicCode) =>
        topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code
          ? [
              choiceNewsEvent({
                event_key: "choice-permission-error",
                topic_code: topicCode,
                error_code: 10001012,
                error_msg: "insufficient user access",
                payload_text: null,
              }),
            ]
          : [],
      ),
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEventsBatch,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await settleHomeIdleWork(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining([
          DASHBOARD_MACRO_NEWS_TOPICS[0].code,
          ...DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code),
        ]),
      );
    });
    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code)),
      );
      expect(requestedNewsGroupIds(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(bondNewsGroupIds()),
      );
    });
    // 宏观主批只发一次（全部 topic 合并进同一个批量请求，不存在 probe→remaining 级联）。
    const macroBatchCalls = getChoiceNewsEventsBatch.mock.calls.filter(([options]) =>
      (options.topics ?? []).some(
        ({ topicCode }) => topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code,
      ),
    );
    expect(macroBatchCalls).toHaveLength(1);
    expect((macroBatchCalls[0]?.[0].topics ?? []).map(({ topicCode }) => topicCode)).toEqual(
      DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => topic.code),
    );
    expect(getResearchCalendarEvents).toHaveBeenCalled();
  });

  it("loads macro fallback news when the Choice macro batch request fails", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEventsBatch = vi.fn(async (options: ChoiceNewsBatchOptions) => {
      const isMacroBatch = (options.topics ?? []).some(
        ({ topicCode }) => topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code,
      );
      if (isMacroBatch) {
        throw new Error("choice macro batch unavailable");
      }
      return choiceNewsBatchEnvelope(options);
    });
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEventsBatch,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await settleHomeIdleWork(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining([
          DASHBOARD_MACRO_NEWS_TOPICS[0].code,
          ...DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code),
        ]),
      );
    });
    expect(getResearchCalendarEvents).toHaveBeenCalled();
  });

  it("loads macro fallback news as soon as Choice macro news has no usable policy funding rows", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEventsBatch = vi.fn(async (options: ChoiceNewsBatchOptions) =>
      choiceNewsBatchEnvelope(options, (topicCode) =>
        topicCode === "tushare.news.sina"
          ? [
              choiceNewsEvent({
                event_key: "tushare-policy-funding",
                received_at: "2026-06-04T10:17:00Z",
                topic_code: "tushare.news.sina",
                payload_text: "10年期美国国债收益率最新上涨2.8个基点，报4.483%。",
              }),
            ]
          : [],
      ),
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEventsBatch,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await settleHomeIdleWork(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(["tushare.news.sina"]),
      );
    });
    await waitFor(() => {
      expect(screen.getAllByText("10年期美国国债收益率最新上涨2.8个基点，报4.483%。").length).toBeGreaterThan(0);
    });
  });

  it("does not request the shared fallback news topic twice for bond news", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEventsBatch = vi.fn(async (options: ChoiceNewsBatchOptions) =>
      choiceNewsBatchEnvelope(options, (topicCode) =>
        topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code
          ? [
              choiceNewsEvent({
                event_key: "choice-permission-error",
                topic_code: topicCode,
                error_code: 10001012,
                error_msg: "insufficient user access",
                payload_text: null,
              }),
            ]
          : [],
      ),
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEventsBatch,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await settleHomeIdleWork(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCount(getChoiceNewsEventsBatch, "tushare.npr")).toBe(1);
    });
    expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).toEqual(
      expect.arrayContaining([
        DASHBOARD_MACRO_NEWS_TOPICS[0].code,
        ...DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code),
      ]),
    );
    await waitFor(() => {
      expect(requestedNewsGroupIds(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(bondNewsGroupIds()),
      );
    });
    // 兜底 topic 只以 topic 形式请求一次；债券侧继续走 group 维度，不重复拉同一 topic。
    expect(requestedNewsTopicCount(getChoiceNewsEventsBatch, "tushare.npr")).toBe(1);
    expect(requestedNewsGroupIds(getChoiceNewsEventsBatch)).toEqual(
      expect.arrayContaining(bondNewsGroupIds()),
    );
  });

  it("continues bond news topic loading when the bond probe has no usable rows", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEventsBatch = vi.fn(async (options: ChoiceNewsBatchOptions) =>
      choiceNewsBatchEnvelope(
        options,
        (topicCode) =>
          topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code
            ? [
                choiceNewsEvent({
                  event_key: "choice-permission-error",
                  topic_code: topicCode,
                  error_code: 10001012,
                  error_msg: "insufficient user access",
                  payload_text: null,
                }),
              ]
            : [],
        (groupId) =>
          groupId === DASHBOARD_BOND_NEWS_TOPICS[0].groupId
            ? [
                choiceNewsEvent({
                  event_key: "bond-probe-error",
                  group_id: groupId,
                  topic_code: DASHBOARD_BOND_NEWS_TOPICS[0].code,
                  error_code: 10001012,
                  error_msg: "insufficient user access",
                  payload_text: null,
                }),
              ]
            : [],
      ),
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEventsBatch,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await settleHomeIdleWork(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => topic.code)),
      );
    });

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code)),
      );
    });

    await waitFor(() => {
      expect(requestedNewsGroupIds(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(bondNewsGroupIds()),
      );
    });
  });

  it("loads remaining bond news topics when the bond probe has rows", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEventsBatch = vi.fn(async (options: ChoiceNewsBatchOptions) =>
      choiceNewsBatchEnvelope(
        options,
        (topicCode) =>
          topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code
            ? [
                choiceNewsEvent({
                  event_key: "choice-permission-error",
                  topic_code: topicCode,
                  error_code: 10001012,
                  error_msg: "insufficient user access",
                  payload_text: null,
                }),
              ]
            : [],
        (groupId) =>
          groupId === DASHBOARD_BOND_NEWS_TOPICS[0].groupId
            ? [
                choiceNewsEvent({
                  event_key: "bond-probe-hit",
                  group_id: groupId,
                  topic_code: DASHBOARD_BOND_NEWS_TOPICS[0].code,
                  payload_text: "债券市场收益率曲线下行，资金面保持宽松。",
                }),
              ]
            : [],
      ),
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEventsBatch,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await settleHomeIdleWork(idle);

    await waitFor(() => {
      expect(requestedNewsGroupIds(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(bondNewsGroupIds()),
      );
    });
  });

  it("starts shared risk hydration with the body after the first-screen idle gate opens", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();

    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...base,
      ...supplementalCalls,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    for (const spy of Object.values(supplementalCalls)) {
      expect(spy).not.toHaveBeenCalled();
    }

    await act(async () => {
      releaseSnapshot?.();
    });
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });
    for (const spy of Object.values(supplementalCalls)) {
      expect(spy).not.toHaveBeenCalled();
    }

    await runNextIdle(idle);
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(supplementalCalls.getMarketDataRates).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getBondDashboardHomeSummary).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
  });

  it("preloads home-summary with the body and waits for visible sections before depth reads", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const observer = stubIntersectionObserver();
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...supplementalCalls,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => expect(observer.observe).toHaveBeenCalledWith(
      screen.getByTestId("dashboard-home-deferred-sentinel"),
    ));
    await act(async () => {
      fireEvent.scroll(window);
      observer.triggerAll({ isIntersecting: true, intersectionRatio: 1 });
    });
    await screen.findByTestId("dashboard-home-work-grid");
    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHomeSummary).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getMarketDataRates).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondAnalyticsTopHoldings).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondAnalyticsPositionChanges).not.toHaveBeenCalled();
    expect(supplementalCalls.getHomeResearchReports).not.toHaveBeenCalled();

    await act(async () => {
      observer.triggerAll({ isIntersecting: true, intersectionRatio: 1 });
    });
    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHomeSummary).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getMarketDataRates).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getBondAnalyticsTopHoldings).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getBondAnalyticsPositionChanges).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getHomeResearchReports).toHaveBeenCalledTimes(1);
    });
  });

  it("starts shared risk hydration on explicit reveal while unseen sections stay gated", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const observer = stubIntersectionObserver();
    stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...supplementalCalls,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).not.toHaveBeenCalled();
    expect(supplementalCalls.getMarketDataRates).not.toHaveBeenCalled();

    await waitFor(() => expect(observer.observe).toHaveBeenCalledWith(
      screen.getByTestId("dashboard-home-deferred-sentinel"),
    ));
    await act(async () => {
      fireEvent.scroll(window);
      observer.triggerAll({ isIntersecting: true, intersectionRatio: 1 });
    });
    await screen.findByTestId("dashboard-home-work-grid");

    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
    expect(supplementalCalls.getMarketDataRates).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHomeSummary).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
  });

  it("reveals initially visible below-fold content after the first-screen idle gate", async () => {
    const observer = stubIntersectionObserver();
    const idle = stubIdleCallbacks();

    renderDashboardHome();

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-deferred-index")).toBeInTheDocument();

    await waitFor(() => expect(observer.observe).toHaveBeenCalled());
    expect(observer.options[0]?.root).toBeNull();
    expect(observer.observe).toHaveBeenCalledWith(
      screen.getByTestId("dashboard-home-deferred-sentinel"),
    );
    expect(
      screen.getByTestId("dashboard-home-deferred-sentinel").getAttribute("class"),
    ).toMatch(/deferredSentinel/);
    expect(screen.queryByTestId("dashboard-home-work-grid")).not.toBeInTheDocument();

    await act(async () => {
      observer.triggerAll({ isIntersecting: true, intersectionRatio: 1 });
    });

    expect(screen.queryByTestId("dashboard-home-work-grid")).not.toBeInTheDocument();
    await runNextIdle(idle);
    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
  });

  it("starts requested body and risk hydration immediately while unseen section queries stay gated", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...supplementalCalls,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => expect(idle.pendingCount()).toBeGreaterThan(0));
    await settleHomeTimersWithoutIdle();
    expect(idle.pendingCount()).toBeGreaterThan(0);
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();

    const sectionObserver: { current: MockIntersectionObserver | null } = { current: null };
    await act(async () => {
      fireEvent.scroll(window);
      // The outer no-IO fallback has already recorded the user's reach. Give
      // the newly mounted sections an observer so their visibility gate stays closed.
      sectionObserver.current = stubIntersectionObserver();
    });

    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
    expect(sectionObserver.current?.observe).toHaveBeenCalledWith(
      screen.getByTestId("dashboard-home-deferred-matrix"),
    );
    expect(supplementalCalls.getMarketDataRates).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHomeSummary).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
  });

  it.each([false, true])("remembers below-fold reach while the snapshot is pending (observer available: %s)", async (observerAvailable) => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const observer = observerAvailable ? stubIntersectionObserver() : null;
    const idle = stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...base,
      ...supplementalCalls,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    if (observer) {
      await waitFor(() => expect(observer.observe).toHaveBeenCalled());
    }
    await act(async () => {
      if (observer) {
        fireEvent.scroll(window);
        observer.triggerAll({ isIntersecting: true, intersectionRatio: 1 });
      } else {
        fireEvent.scroll(window);
      }
    });

    await settleHomeTimersWithoutIdle();
    expect(screen.queryByTestId("dashboard-home-work-grid")).not.toBeInTheDocument();
    for (const spy of Object.values(supplementalCalls)) {
      expect(spy).not.toHaveBeenCalled();
    }

    await act(async () => {
      releaseSnapshot?.();
    });
    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();

    await settleHomeIdleWork(idle);
    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHomeSummary).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
  });

  it("keeps below-fold content deferred through unrelated input until the internal scroll boundary intersects", async () => {
    const observer = stubIntersectionObserver();
    stubIdleCallbacks();
    const getComputedStyle = window.getComputedStyle.bind(window);
    vi.spyOn(window, "getComputedStyle").mockImplementation((element, pseudoElement) => {
      const style = getComputedStyle(element, pseudoElement);
      if ((element as HTMLElement).dataset.testid !== "dashboard-home-scroll-root") {
        return style;
      }
      return new Proxy(style, {
        get(target, property, receiver) {
          if (property === "overflowY") {
            return "auto";
          }
          return Reflect.get(target, property, receiver);
        },
      });
    });

    renderDashboardHome();

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => expect(observer.observe).toHaveBeenCalled());
    expect(screen.queryByTestId("dashboard-home-work-grid")).not.toBeInTheDocument();
    const scrollRoot = screen.getByTestId("dashboard-home-scroll-root");
    expect(observer.options[0]?.root).toBe(scrollRoot);

    await act(async () => {
      fireEvent.scroll(scrollRoot);
      fireEvent.wheel(scrollRoot);
      fireEvent.touchMove(scrollRoot);
      fireEvent.keyDown(window, { key: "PageDown" });
      observer.triggerAll({ isIntersecting: false, intersectionRatio: 0 });
    });

    await settleHomeTimersWithoutIdle();
    expect(screen.queryByTestId("dashboard-home-work-grid")).not.toBeInTheDocument();

    await act(async () => {
      observer.triggerAll({ isIntersecting: true, intersectionRatio: 1 });
    });

    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
    expect(observer.disconnect).toHaveBeenCalled();
  });

  it("does not reuse an old idle gate for supplemental queries while a new report-date snapshot is pending", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();

    let releaseLatestSnapshot: (() => void) | undefined;
    let releaseNewSnapshot: (() => void) | undefined;
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...base,
      ...supplementalCalls,
      getHomeSnapshot: async (options) => {
        if (options?.reportDate === "2026-03-31") {
          await new Promise<void>((resolve) => {
            releaseNewSnapshot = resolve;
          });
          const envelope = await mockSnapshotSource.getHomeSnapshot(options);
          return {
            ...envelope,
            result: {
              ...envelope.result,
              report_date: options.reportDate,
            },
          };
        }
        await new Promise<void>((resolve) => {
          releaseLatestSnapshot = resolve;
        });
        const envelope = await mockSnapshotSource.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: options?.reportDate ?? envelope.result.report_date,
          },
        };
      },
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseLatestSnapshot).toBeDefined();
    });

    await act(async () => {
      releaseLatestSnapshot?.();
    });
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    const reportDateInput = await screen.findByLabelText("报告日");
    await act(async () => {
      fireEvent.change(reportDateInput, { target: { value: "2026-03-31" } });
    });
    await waitFor(() => {
      expect(releaseNewSnapshot).toBeDefined();
    });

    await act(async () => {
      idle.runPending();
    });
    for (const spy of Object.values(supplementalCalls)) {
      expect(spy).not.toHaveBeenCalled();
    }

    await act(async () => {
      releaseNewSnapshot?.();
    });
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-page")).toBeInTheDocument();
    });
    for (const spy of Object.values(supplementalCalls)) {
      expect(spy).not.toHaveBeenCalled();
    }
  });

  it("does not keep formal supplemental queries enabled while a new report-date snapshot is pending", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();

    let releaseNewSnapshot: (() => void) | undefined;
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...base,
      ...supplementalCalls,
      getHomeSnapshot: async (options) => {
        if (options?.reportDate === "2026-03-31") {
          await new Promise<void>((resolve) => {
            releaseNewSnapshot = resolve;
          });
        }
        const envelope = await mockSnapshotSource.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: options?.reportDate ?? envelope.result.report_date,
          },
        };
      },
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await settleHomeIdleWork(idle);
    await waitFor(() => {
      expect(supplementalCalls.getHomeIncomeTrend).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getCockpitWarnings).not.toHaveBeenCalled();

    const incomeTrendCallsBeforeSwitch = supplementalCalls.getHomeIncomeTrend.mock.calls.length;
    const cockpitWarningCallsBeforeSwitch = supplementalCalls.getCockpitWarnings.mock.calls.length;
    const reportDateInput = await screen.findByLabelText("报告日");
    await act(async () => {
      fireEvent.change(reportDateInput, { target: { value: "2026-03-31" } });
    });
    await waitFor(() => {
      expect(releaseNewSnapshot).toBeDefined();
    });
    await settleHomeTimersWithoutIdle();

    expect(supplementalCalls.getHomeIncomeTrend).toHaveBeenCalledTimes(incomeTrendCallsBeforeSwitch);
    expect(supplementalCalls.getCockpitWarnings).toHaveBeenCalledTimes(cockpitWarningCallsBeforeSwitch);

    await act(async () => {
      releaseNewSnapshot?.();
    });
  });

  it("does not start supplemental queries when a requested report-date snapshot fails without prior data", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();

    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...base,
      ...supplementalCalls,
      getHomeSnapshot: async () => {
        throw new Error("snapshot unavailable");
      },
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    const reportDateInput = await screen.findByLabelText("报告日");
    await act(async () => {
      fireEvent.change(reportDateInput, { target: { value: "2026-03-31" } });
    });
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-hero")).toBeInTheDocument();
    });
    await act(async () => {
      idle.runPending();
    });
    await settleHomeTimersWithoutIdle();

    for (const spy of Object.values(supplementalCalls)) {
      expect(spy).not.toHaveBeenCalled();
    }
  });

  it("starts formal context while heavy bond lists are still settling", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    let releaseSnapshot: (() => void) | undefined;
    let releaseTopHoldings: (() => void) | undefined;
    let releaseIncomeTrend: (() => void) | undefined;
    const getBondAnalyticsTopHoldings = vi.fn(async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) => {
      await new Promise<void>((resolve) => {
        releaseTopHoldings = resolve;
      });
      return mockSnapshotSource.getBondAnalyticsTopHoldings(...args);
    });
    const getBondAnalyticsPositionChanges = vi.fn(
      async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
      mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
    );
    const getHomeIncomeTrend = vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) => {
      await new Promise<void>((resolve) => {
        releaseIncomeTrend = resolve;
      });
      return mockSnapshotSource.getHomeIncomeTrend(...args);
    });
    const getBondAnalyticsCreditSpreadMigration = vi.fn(
      mockSnapshotSource.getBondAnalyticsCreditSpreadMigration,
    );
    const getBondAnalyticsReturnDecomposition = vi.fn(mockSnapshotSource.getBondAnalyticsReturnDecomposition);
    const getPnlCampisiFourEffects = vi.fn(mockSnapshotSource.getPnlCampisiFourEffects);
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(
      mockSnapshotSource.getBondAnalyticsYieldCurveTermStructure,
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getBondAnalyticsTopHoldings,
      getBondAnalyticsPositionChanges,
      getHomeIncomeTrend,
      getBondAnalyticsCreditSpreadMigration,
      getBondAnalyticsReturnDecomposition,
      getPnlCampisiFourEffects,
      getBondAnalyticsYieldCurveTermStructure,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    expect(idle.pendingCount()).toBe(0);
    await act(async () => {
      releaseSnapshot?.();
    });
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });
    expect(getBondAnalyticsTopHoldings).not.toHaveBeenCalled();
    expect(getHomeIncomeTrend).not.toHaveBeenCalled();

    await act(async () => {
      idle.runPending();
    });

    await screen.findByTestId("dashboard-home-work-grid");

    await settleHomeIdleWork(idle);
    await waitFor(() => {
      expect(getHomeIncomeTrend).toHaveBeenCalled();
      expect(releaseIncomeTrend).toBeDefined();
      expect(getBondAnalyticsCreditSpreadMigration).toHaveBeenCalled();
      expect(getBondAnalyticsReturnDecomposition).toHaveBeenCalled();
      expect(getPnlCampisiFourEffects).toHaveBeenCalled();
      expect(getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalled();
    });
    expect(getBondAnalyticsTopHoldings).toHaveBeenCalled();
    expect(releaseTopHoldings).toBeDefined();

    await act(async () => {
      releaseTopHoldings?.();
    });

    releaseIncomeTrend?.();
  });

  it("starts formal queries while slow position changes are still settling", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    let releaseSnapshot: (() => void) | undefined;
    let releasePositionChanges: (() => void) | undefined;
    let releaseIncomeTrend: (() => void) | undefined;
    const getBondAnalyticsTopHoldings = vi.fn(mockSnapshotSource.getBondAnalyticsTopHoldings);
    const getBondAnalyticsPositionChanges = vi.fn(
      async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) => {
        await new Promise<void>((resolve) => {
          releasePositionChanges = resolve;
        });
        return mockSnapshotSource.getBondAnalyticsPositionChanges(...args);
      },
    );
    const getHomeIncomeTrend = vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) => {
      await new Promise<void>((resolve) => {
        releaseIncomeTrend = resolve;
      });
      return mockSnapshotSource.getHomeIncomeTrend(...args);
    });
    const getBondAnalyticsCreditSpreadMigration = vi.fn(
      mockSnapshotSource.getBondAnalyticsCreditSpreadMigration,
    );
    const getBondAnalyticsReturnDecomposition = vi.fn(mockSnapshotSource.getBondAnalyticsReturnDecomposition);
    const getPnlCampisiFourEffects = vi.fn(mockSnapshotSource.getPnlCampisiFourEffects);
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(
      mockSnapshotSource.getBondAnalyticsYieldCurveTermStructure,
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getBondAnalyticsTopHoldings,
      getBondAnalyticsPositionChanges,
      getHomeIncomeTrend,
      getBondAnalyticsCreditSpreadMigration,
      getBondAnalyticsReturnDecomposition,
      getPnlCampisiFourEffects,
      getBondAnalyticsYieldCurveTermStructure,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    await act(async () => {
      releaseSnapshot?.();
    });
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    await runNextIdle(idle);
    await screen.findByTestId("dashboard-home-work-grid");
    await settleHomeIdleWork(idle);
    await waitFor(() => {
      expect(getHomeIncomeTrend).toHaveBeenCalled();
      expect(releaseIncomeTrend).toBeDefined();
      expect(getBondAnalyticsCreditSpreadMigration).toHaveBeenCalled();
      expect(getBondAnalyticsReturnDecomposition).toHaveBeenCalled();
      expect(getPnlCampisiFourEffects).toHaveBeenCalled();
      expect(getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalled();
    });
    expect(getBondAnalyticsTopHoldings).toHaveBeenCalled();
    expect(getBondAnalyticsPositionChanges).toHaveBeenCalled();
    expect(releasePositionChanges).toBeDefined();

    await act(async () => {
      releasePositionChanges?.();
    });
    await waitFor(() => {
      expect(getHomeIncomeTrend).toHaveBeenCalled();
      expect(releaseIncomeTrend).toBeDefined();
      expect(getBondAnalyticsReturnDecomposition).toHaveBeenCalled();
      expect(getPnlCampisiFourEffects).toHaveBeenCalled();
      expect(getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalled();
    });

    releaseIncomeTrend?.();
  });

  it("keeps formal queries independent from failed position changes", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    let releaseSnapshot: (() => void) | undefined;
    let rejectPositionChanges: (() => void) | undefined;
    let releaseIncomeTrend: (() => void) | undefined;
    const getBondAnalyticsTopHoldings = vi.fn(mockSnapshotSource.getBondAnalyticsTopHoldings);
    const getBondAnalyticsPositionChanges = vi.fn(
      async () => {
        await new Promise<void>((resolve) => {
          rejectPositionChanges = resolve;
        });
        throw new Error("position changes unavailable");
      },
    );
    const getHomeIncomeTrend = vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) => {
      await new Promise<void>((resolve) => {
        releaseIncomeTrend = resolve;
      });
      return mockSnapshotSource.getHomeIncomeTrend(...args);
    });
    const getBondAnalyticsCreditSpreadMigration = vi.fn(
      mockSnapshotSource.getBondAnalyticsCreditSpreadMigration,
    );
    const getBondAnalyticsReturnDecomposition = vi.fn(mockSnapshotSource.getBondAnalyticsReturnDecomposition);
    const getPnlCampisiFourEffects = vi.fn(mockSnapshotSource.getPnlCampisiFourEffects);
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(
      mockSnapshotSource.getBondAnalyticsYieldCurveTermStructure,
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getBondAnalyticsTopHoldings,
      getBondAnalyticsPositionChanges,
      getHomeIncomeTrend,
      getBondAnalyticsCreditSpreadMigration,
      getBondAnalyticsReturnDecomposition,
      getPnlCampisiFourEffects,
      getBondAnalyticsYieldCurveTermStructure,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    await act(async () => {
      releaseSnapshot?.();
    });
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    await runNextIdle(idle);
    await screen.findByTestId("dashboard-home-work-grid");
    await settleHomeIdleWork(idle);
    await waitFor(() => {
      expect(getHomeIncomeTrend).toHaveBeenCalled();
      expect(releaseIncomeTrend).toBeDefined();
      expect(getBondAnalyticsCreditSpreadMigration).toHaveBeenCalled();
      expect(getBondAnalyticsReturnDecomposition).toHaveBeenCalled();
      expect(getPnlCampisiFourEffects).toHaveBeenCalled();
      expect(getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalled();
    });
    expect(getBondAnalyticsTopHoldings).toHaveBeenCalled();
    expect(getBondAnalyticsPositionChanges).toHaveBeenCalled();
    expect(rejectPositionChanges).toBeDefined();

    await act(async () => {
      rejectPositionChanges?.();
    });
    await waitFor(() => {
      expect(getHomeIncomeTrend).toHaveBeenCalled();
      expect(releaseIncomeTrend).toBeDefined();
      expect(getBondAnalyticsReturnDecomposition).toHaveBeenCalled();
      expect(getPnlCampisiFourEffects).toHaveBeenCalled();
      expect(getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalled();
    });

    releaseIncomeTrend?.();
  });

  it("does not issue stale formal requests after switching report date", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    let releaseNewSnapshot: (() => void) | undefined;
    let newSnapshotReturned = false;
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...base,
      ...supplementalCalls,
      getHomeSnapshot: async (options) => {
        if (options?.reportDate === "2026-03-31") {
          await new Promise<void>((resolve) => {
            releaseNewSnapshot = resolve;
          });
        }
        const envelope = await mockSnapshotSource.getHomeSnapshot(options);
        if (options?.reportDate === "2026-03-31") {
          newSnapshotReturned = true;
        }
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: options?.reportDate ?? envelope.result.report_date,
          },
        };
      },
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await settleHomeIdleWork(idle);
    await waitFor(() => {
      expect(supplementalCalls.getBondAnalyticsCreditSpreadMigration).toHaveBeenCalled();
      expect(supplementalCalls.getBondAnalyticsReturnDecomposition).toHaveBeenCalled();
      expect(supplementalCalls.getPnlCampisiFourEffects).toHaveBeenCalled();
      expect(supplementalCalls.getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalled();
    });

    const formalCallsBeforeSwitch = {
      creditSpread: supplementalCalls.getBondAnalyticsCreditSpreadMigration.mock.calls.length,
      returnDecomposition: supplementalCalls.getBondAnalyticsReturnDecomposition.mock.calls.length,
      campisi: supplementalCalls.getPnlCampisiFourEffects.mock.calls.length,
      yieldCurve: supplementalCalls.getBondAnalyticsYieldCurveTermStructure.mock.calls.length,
    };
    const reportDateInput = await screen.findByLabelText("报告日");
    await act(async () => {
      fireEvent.change(reportDateInput, { target: { value: "2026-03-31" } });
    });
    await waitFor(() => {
      expect(releaseNewSnapshot).toBeDefined();
    });
    // URL-backed date changes remount the generation boundary. The new home
    // shell stays unloaded while its requested snapshot is still pending.
    await act(async () => {
      idle.runPending();
    });

    expect(supplementalCalls.getBondAnalyticsCreditSpreadMigration).toHaveBeenCalledTimes(
      formalCallsBeforeSwitch.creditSpread,
    );
    expect(supplementalCalls.getBondAnalyticsReturnDecomposition).toHaveBeenCalledTimes(
      formalCallsBeforeSwitch.returnDecomposition,
    );
    expect(supplementalCalls.getPnlCampisiFourEffects).toHaveBeenCalledTimes(
      formalCallsBeforeSwitch.campisi,
    );
    expect(supplementalCalls.getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalledTimes(
      formalCallsBeforeSwitch.yieldCurve,
    );

    await act(async () => {
      releaseNewSnapshot?.();
    });
    await waitFor(() => {
      expect(newSnapshotReturned).toBe(true);
    });
    await settleHomeIdleWork(idle);
    await waitFor(() => {
      expect(supplementalCalls.getBondAnalyticsCreditSpreadMigration).toHaveBeenCalledWith("2026-03-31");
      expect(supplementalCalls.getBondAnalyticsReturnDecomposition).toHaveBeenCalledWith(
        "2026-03-31",
        "MoM",
        {
          accountingClass: "all",
          assetClass: "all",
          detail: "summary",
        },
      );
      expect(supplementalCalls.getPnlCampisiFourEffects).toHaveBeenCalledWith({
        startDate: "2026-02-28",
        endDate: "2026-03-31",
        lookbackDays: 30,
        detail: "summary",
      });
      expect(supplementalCalls.getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalledWith(
        "2026-03-31",
        { curveTypes: "treasury,cdb,aaa_credit" },
      );
    });
  });

  it("does not refetch market tape when only the snapshot report date resolves", async () => {
    const idle = stubIdleCallbacks();
    const base = createApiClient({ mode: "mock" });
    const getMarketDataRates = vi.fn(base.getMarketDataRates);
    const client: ApiClient = {
      ...base,
      getMarketDataRates,
    };

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await runNextIdle(idle);
    await waitFor(() => {
      expect(getMarketDataRates).toHaveBeenCalledTimes(1);
    });
    await settleHomeIdleWork(idle);
    expect(getMarketDataRates).toHaveBeenCalledTimes(1);
  });

  it("uses mock-shaped first-screen content when the app is not using real APIs", async () => {
    renderDashboardHome();

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    const hero = await screen.findByTestId("dashboard-home-hero");
    expect(within(hero).getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("3,708.10");
  });

  it("does not request excluded executive surfaces from the home page", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let riskCalls = 0;
    let contributionCalls = 0;
    let alertsCalls = 0;

    const guardedClient: ApiClient = {
      ...base,
      getHomeSnapshot: (...args) => mockSnapshotSource.getHomeSnapshot(...args),
      getRiskOverview: async () => {
        riskCalls += 1;
        throw new Error("risk-overview should not be requested");
      },
      getContribution: async () => {
        contributionCalls += 1;
        throw new Error("contribution should not be requested");
      },
      getAlerts: async () => {
        alertsCalls += 1;
        throw new Error("alerts should not be requested");
      },
    };

    renderDashboardHome(guardedClient);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(riskCalls).toBe(0);
      expect(contributionCalls).toBe(0);
      expect(alertsCalls).toBe(0);
    });
  });

  it("updates same-date assets with missing PnL and clears them when the whole date is unavailable", async () => {
    const source = createApiClient({ mode: "mock" });
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>(async (options) => {
      const date = options?.reportDate || "2026-08-31";
      if (date === "2026-07-29") {
        throw new Error("报告日 2026-07-29 缺少余额及损益数据 [code=home_report_date_unavailable]");
      }
      const partial = date === "2026-07-30";
      if (partial) expect(options?.allowPartial).toBe(true);
      const effectiveDates: Record<string, string> = { balance_sheet: date };
      if (!partial) effectiveDates.pnl = date;
      const envelope = await source.getHomeSnapshot(options);
      return {
        ...envelope,
        result_meta: {
          ...envelope.result_meta,
          quality_flag: partial ? "warning" as const : "ok" as const,
          vendor_status: partial ? "vendor_unavailable" as const : "ok" as const,
        },
        result: {
          ...envelope.result,
          report_date: date,
          mode: partial ? "partial" as const : "strict" as const,
          domains_missing: partial ? ["pnl"] : [],
          domains_effective_date: effectiveDates,
          product_category_monthly: partial ? null : envelope.result.product_category_monthly,
          overview: {
            ...envelope.result.overview,
            metrics: [{
              ...envelope.result.overview.metrics[0],
              id: "aum",
              label: "总资产规模",
              value: {
                raw: partial ? 385_000_000_000 : date === "2026-08-31" ? 380_000_000_000 : 370_000_000_000,
                unit: "yuan" as const,
                display: partial ? "3,850.00 亿" : date === "2026-08-31" ? "3,800.00 亿" : "3,700.00 亿",
                precision: 2,
                sign_aware: false,
              },
            }],
          },
        },
      };
    });
    renderDashboardHome(createRealModeHomeClient({
      ...createApiClient({ mode: "real" }), getHomeSnapshot,
    }));
    await waitFor(() => expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("3,800.00"));
    fireEvent.change(screen.getByLabelText("报告日"), { target: { value: "2026-07-31" } });
    await waitFor(() => expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("3,700.00"));
    fireEvent.change(screen.getByLabelText("报告日"), { target: { value: "2026-07-30" } });
    await waitFor(() => expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("3,850.00"));
    expect(screen.getAllByText("部分可用").length).toBeGreaterThan(0);
    expect(screen.getByTestId("dashboard-home-kpi-aum")).not.toHaveTextContent("3,700.00");
    fireEvent.change(screen.getByLabelText("报告日"), { target: { value: "2026-07-29" } });
    await waitFor(() => expect(screen.getByTestId("dashboard-home-report-date-context")).toHaveAttribute("data-report-date-mode", "error"));
    expect(screen.getAllByText("报告日暂不可用").length).toBeGreaterThan(0);
    expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("—");
    expect(screen.getByTestId("dashboard-home-kpi-aum")).not.toHaveTextContent("3,700.00");
    fireEvent.change(screen.getByLabelText("报告日"), { target: { value: "2026-08-31" } });
    await waitFor(() => expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("3,800.00"));
  });

  it("prefers real first-screen values over local fallback", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const getHomeSnapshot = vi.fn(async (options) => {
      const envelope = await mockSnapshotSource.getHomeSnapshot(options);
      return {
        ...envelope,
        result_meta: {
          ...envelope.result_meta,
          trace_id: "trace-real-home-overview",
          basis: "analytical" as const,
          formal_use_allowed: false,
          source_version: "sv_home_overview_test",
          vendor_version: "vv_home_overview_test",
          rule_version: "rv_home_overview_test",
          cache_version: "cv_home_overview_test",
          source_surface: "executive_analytical",
          generated_at: "2026-04-30T10:45:00+08:00",
        },
        result: {
          ...envelope.result,
          report_date: "2026-04-30",
          overview: {
            ...envelope.result.overview,
            metrics: [
              {
                id: "aum",
                label: "债券资产规模",
                caliber_label: "真实接口口径",
                value: {
                  raw: 4_567_890_000_000,
                  unit: "yuan" as const,
                  display: "4,567.89 亿",
                  precision: 2,
                  sign_aware: false,
                },
                delta: {
                  raw: 12_300_000_000,
                  unit: "yuan" as const,
                  display: "+12.30 亿",
                  precision: 2,
                  sign_aware: true,
                },
                tone: "positive" as const,
                detail: "测试真实接口返回值。",
              },
              {
                id: "yield",
                label: "年度损益（不扣FTP）",
                caliber_label: "FI + 非标桥接",
                value: {
                  raw: 3_639_159_930.63,
                  unit: "yuan" as const,
                  display: "+36.39 亿",
                  precision: 2,
                  sign_aware: true,
                },
                delta: {
                  raw: 0.2251,
                  unit: "pct" as const,
                  display: "+22.51%",
                  precision: 2,
                  sign_aware: true,
                },
                tone: "positive" as const,
                detail: "测试真实接口返回值。",
                history: [2_970_577_023.0, 3_639_159_930.63],
              },
              {
                id: "nim",
                label: "净息差",
                caliber_label: null,
                value: {
                  raw: 0.01046,
                  unit: "pct" as const,
                  display: "+1.05%",
                  precision: 2,
                  sign_aware: true,
                },
                delta: {
                  raw: 10.44,
                  unit: "bp" as const,
                  display: "+0.10pp",
                  precision: 2,
                  sign_aware: true,
                },
                tone: "positive" as const,
                detail: "测试真实接口返回值。",
                history: [0.0094, 0.01046],
              },
              {
                id: "dv01",
                label: "组合DV01",
                caliber_label: null,
                value: {
                  raw: 106_223_757,
                  unit: "dv01" as const,
                  display: "106,223,757",
                  precision: 0,
                  sign_aware: false,
                },
                delta: {
                  raw: -0.0185,
                  unit: "pct" as const,
                  display: "-1.85%",
                  precision: 2,
                  sign_aware: true,
                },
                tone: "warning" as const,
                detail: "测试真实接口返回值。",
                history: [108_230_899, 106_223_757],
              },
            ],
          },
        },
      };
    });
    const client = createRealModeHomeClient({
      getHomeSnapshot,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderDashboardHome(client);

    const hero = await screen.findByTestId("dashboard-home-hero");
    await waitFor(() => {
      expect(getHomeSnapshot).toHaveBeenCalled();
      expect(within(hero).getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("4,567.89");
      expect(within(hero).getByTestId("dashboard-home-kpi-yield")).toHaveTextContent("+36.39");
      expect(within(hero).getByTestId("dashboard-home-kpi-nim")).toHaveTextContent("+1.05");
      expect(within(hero).getByTestId("dashboard-home-kpi-dv01-wan")).toBeInTheDocument();
      expect(within(hero).queryByTestId("dashboard-home-kpi-spread-bp")).not.toBeInTheDocument();
      expect(
        within(hero).queryByTestId("dashboard-home-kpi-holding-occupancy"),
      ).not.toBeInTheDocument();
    });
  });

  it("never lets supplemental bond metrics replace an empty governed overview", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    const yuan = (raw: number, display: string, signAware = false) => ({
      raw,
      unit: "yuan" as const,
      display,
      precision: 2,
      sign_aware: signAware,
    });
    const ratio = (raw: number, display: string) => ({
      raw,
      unit: "ratio" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const pct = (raw: number, display: string) => ({
      raw,
      unit: "pct" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const getBondDashboardHomeSummary = vi.fn<ApiClient["getBondDashboardHomeSummary"]>(
      async (reportDate) => {
        const envelope = await mockSnapshotSource.getBondDashboardHomeSummary(reportDate);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-04-30",
            headline: {
              report_date: "2026-04-30",
              prev_report_date: "2026-04-29",
              kpis: {
                total_market_value: yuan(328_709_000_000, "3,287.09 亿"),
                unrealized_pnl: yuan(1_842_000_000, "+18.42 亿", true),
                weighted_ytm: pct(0.0285, "2.85%"),
                weighted_duration: ratio(4.23, "4.23"),
                weighted_coupon: pct(0.031, "3.10%"),
                credit_spread_median: {
                  raw: 72,
                  unit: "bp" as const,
                  display: "72bp",
                  precision: 2,
                  sign_aware: false,
                },
                total_dv01: {
                  raw: 120_000,
                  unit: "dv01" as const,
                  display: "120,000.00",
                  precision: 2,
                  sign_aware: false,
                },
                bond_count: 128,
              },
              prev_kpis: {
                total_market_value: yuan(320_000_000_000, "3,200.00 亿"),
                unrealized_pnl: yuan(1_700_000_000, "+17.00 亿", true),
                weighted_ytm: pct(0.0281, "2.81%"),
                weighted_duration: ratio(4.18, "4.18"),
                weighted_coupon: pct(0.0308, "3.08%"),
                credit_spread_median: {
                  raw: 75,
                  unit: "bp" as const,
                  display: "75bp",
                  precision: 2,
                  sign_aware: false,
                },
                total_dv01: {
                  raw: 118_000,
                  unit: "dv01" as const,
                  display: "118,000.00",
                  precision: 2,
                  sign_aware: false,
                },
                bond_count: 128,
              },
            },
          },
        };
      },
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        const envelope = await mockSnapshotSource.getHomeSnapshot(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-04-30",
            overview: {
              ...envelope.result.overview,
              metrics: [],
            },
          },
        };
      },
      getBondDashboardHomeSummary,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderDashboardHome(client);

    const hero = await screen.findByTestId("dashboard-home-hero");
    const kpiStrip = within(hero).getByTestId("dashboard-home-hero-kpi-strip");
    const primaryCards = within(kpiStrip).getAllByRole("article");
    expect(primaryCards.map((card) => card.getAttribute("data-testid"))).toEqual([
      "dashboard-home-kpi-aum",
      "dashboard-home-kpi-yield",
      "dashboard-home-kpi-nim",
      "dashboard-home-kpi-dv01-wan",
    ]);
    primaryCards.forEach((card) => expect(card).toHaveTextContent("—"));
    expect(within(hero).queryByTestId("dashboard-home-kpi-bond-market-value")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    await act(async () => {
      idle.runPending();
    });
    await settleHomeIdleWork(idle);
    expect(getBondDashboardHomeSummary).toHaveBeenCalledWith("2026-04-30");
    expect(getBondDashboardHomeSummary).toHaveBeenCalledTimes(1);
    await act(async () => {
      await getBondDashboardHomeSummary.mock.results[0].value;
    });
    await flushHomeQueryNotifications();
    primaryCards.forEach((card) => expect(card).toHaveTextContent("—"));
    expect(within(hero).queryByTestId("dashboard-home-kpi-bond-market-value")).not.toBeInTheDocument();
    expect(within(hero).queryByTestId("dashboard-home-kpi-duration")).not.toBeInTheDocument();
    expect(within(hero).queryByTestId("dashboard-home-kpi-ytm")).not.toBeInTheDocument();
  });

  it.each(["late", "failed", "previous date"] as const)(
    "keeps four snapshot KPIs intact when supplemental results are %s",
    async (scenario) => {
      const mockSnapshotSource = createApiClient({ mode: "mock" });
      const idle = stubIdleCallbacks();
      const initialDate = "2026-04-30";
      const nextDate = "2026-03-31";
      let releaseSupplemental!: () => void;
      const supplementalReady = new Promise<void>((resolve) => {
        releaseSupplemental = resolve;
      });
      const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
      const getBondDashboardHomeSummary = vi.fn<ApiClient["getBondDashboardHomeSummary"]>(
        async (reportDate) => {
          if (reportDate === initialDate) await supplementalReady;
          if (scenario === "failed") throw new Error("supplemental summary unavailable");
          const envelope = await mockSnapshotSource.getBondDashboardHomeSummary(reportDate);
          return {
            ...envelope,
            result: {
              ...envelope.result,
              report_date: reportDate,
              headline: {
                ...envelope.result.headline,
                report_date: reportDate,
                kpis: {
                  ...envelope.result.headline.kpis,
                  total_market_value: {
                    raw: 999_000_000_000,
                    unit: "yuan",
                    display: "9,990.00 亿",
                    precision: 2,
                    sign_aware: false,
                  },
                },
              },
            },
          };
        },
      );
      const getBondAnalyticsPortfolioHeadlines = vi.fn<ApiClient["getBondAnalyticsPortfolioHeadlines"]>(
        async (reportDate) => {
          if (reportDate === initialDate) await supplementalReady;
          if (scenario === "failed") throw new Error("supplemental portfolio unavailable");
          const envelope = await mockSnapshotSource.getBondAnalyticsPortfolioHeadlines(reportDate);
          const weight = reportDate === initialDate ? 0.77 : 0.22;
          return {
            ...envelope,
            result: {
              ...envelope.result,
              report_date: reportDate,
              issuer_top5_weight: {
                raw: weight,
                unit: "ratio",
                display: String(weight),
                precision: 2,
                sign_aware: false,
              },
            },
          };
        },
      );
      const client = createRealModeHomeClient({
        ...supplementalCalls,
        getBondDashboardHomeSummary,
        getBondAnalyticsPortfolioHeadlines,
        getHomeSnapshot: async (options) => {
          const envelope = await mockSnapshotSource.getHomeSnapshot(options);
          const reportDate = options?.reportDate ?? initialDate;
          const isNextDate = reportDate === nextDate;
          const values: Array<{ id: string; raw: number; display: string; unit: Numeric["unit"] }> = [
            { id: "aum", raw: isNextDate ? 20_000_000_000 : 10_000_000_000, display: isNextDate ? "200.00 亿" : "100.00 亿", unit: "yuan" },
            { id: "yield", raw: 200_000_000, display: "+2.00 亿", unit: "yuan" },
            { id: "nim", raw: 0.0123, display: "+1.23%", unit: "pct" },
            { id: "dv01", raw: 1_230_000, display: "1,230,000", unit: "dv01" },
          ];
          return {
            ...envelope,
            result: {
              ...envelope.result,
              report_date: reportDate,
              domains_effective_date: { balance_sheet: reportDate, pnl: reportDate },
              overview: {
                ...envelope.result.overview,
                metrics: values.map(({ id, raw, display, unit }) => ({
                  id,
                  label: id,
                  value: { raw, display, unit, precision: 2, sign_aware: false },
                  delta: { raw: null, display: "—", unit, precision: 2, sign_aware: false },
                  tone: "neutral" as const,
                  detail: "Synthetic snapshot metric for hydration boundary regression.",
                })),
              },
            },
          };
        },
      });

      renderDashboardHome(client);
      const kpiStrip = await screen.findByTestId("dashboard-home-hero-kpi-strip");
      await waitFor(() => {
        expect(within(kpiStrip).getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("100.00");
      });
      const originalKpis = within(kpiStrip).getAllByRole("article").map((card) => card.textContent);
      expect(originalKpis).toHaveLength(4);
      expect(within(kpiStrip).getByTestId("dashboard-home-kpi-yield")).toHaveTextContent("+2.00");
      expect(within(kpiStrip).getByTestId("dashboard-home-kpi-nim")).toHaveTextContent("+1.23");
      expect(within(kpiStrip).getByTestId("dashboard-home-kpi-dv01-wan")).toHaveTextContent("123.00");
      await settleHomeIdleWork(idle);
      await waitFor(() => {
        expect(getBondDashboardHomeSummary).toHaveBeenCalledWith(initialDate);
        expect(getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledWith(initialDate);
      });
      expect(within(kpiStrip).getAllByRole("article").map((card) => card.textContent)).toEqual(originalKpis);

      if (scenario === "previous date") {
        fireEvent.change(screen.getByLabelText("报告日"), { target: { value: nextDate } });
        await waitFor(() => {
          expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("200.00");
        });
        await settleHomeIdleWork(idle);
        await waitFor(() => {
          expect(screen.getByTestId("dashboard-home-risk-metric-strip")).toHaveTextContent("22.00%");
        });
      }
      const currentKpiStrip = screen.getByTestId("dashboard-home-hero-kpi-strip");
      const currentKpis = within(currentKpiStrip).getAllByRole("article").map((card) => card.textContent);
      await act(async () => {
        releaseSupplemental();
        await Promise.allSettled([
          getBondDashboardHomeSummary.mock.results[0].value,
          getBondAnalyticsPortfolioHeadlines.mock.results[0].value,
        ]);
      });
      // Let query observers deliver the completed responses before checking retention.
      await flushHomeQueryNotifications();

      if (scenario === "failed") {
        expect(await screen.findByText("辅助来源 · 补充查询失败")).toBeInTheDocument();
      } else {
        await waitFor(() => {
          const riskStrip = screen.getByTestId("dashboard-home-risk-metric-strip");
          expect(riskStrip).toHaveTextContent(scenario === "previous date" ? "22.00%" : "77.00%");
          if (scenario === "previous date") expect(riskStrip).not.toHaveTextContent("77.00%");
        });
      }
      expect(within(currentKpiStrip).getAllByRole("article").map((card) => card.textContent)).toEqual(currentKpis);
      expect(currentKpiStrip).not.toHaveTextContent("9,990.00");
    },
  );

  it("starts shared risk hydration with the idle body mount while unseen section queries remain disabled", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...supplementalCalls,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    const sectionObserver: { current: MockIntersectionObserver | null } = { current: null };
    await act(async () => {
      idle.runPending();
      // The body mounts on this idle turn; observe its sections before React
      // commits them, rather than letting the no-IO section fallback timer fire.
      sectionObserver.current = stubIntersectionObserver();
    });

    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
    expect(supplementalCalls.getMarketDataRates).not.toHaveBeenCalled();
    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
    expect(sectionObserver.current?.observe).toHaveBeenCalledWith(
      screen.getByTestId("dashboard-home-deferred-matrix"),
    );
    expect(supplementalCalls.getMarketDataRates).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHomeSummary).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
  });

  it("keeps the legacy headline request excluded when the idle body and shared risk hydration load", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...supplementalCalls,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    await act(async () => {
      idle.runPending();
    });

    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
  });

  it("renders terminal holdings and newly landed home backend blocks", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>(async (options) => {
      const envelope = await mockSource.getHomeSnapshot(options);
      return {
        ...envelope,
        result: {
          ...envelope.result,
          report_date: "2026-04-30",
        },
      };
    });
    const yuan = (raw: number, display: string) => ({
      raw,
      unit: "yuan" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const ratio = (raw: number, display: string) => ({
      raw,
      unit: "ratio" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const pct = (raw: number, display: string) => ({
      raw,
      unit: "pct" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const signedYuan = (raw: number, display: string) => ({
      raw,
      unit: "yuan" as const,
      display,
      precision: 2,
      sign_aware: true,
    });
    const missingYuan = {
      raw: null,
      unit: "yuan" as const,
      display: "-",
      precision: 2,
      sign_aware: true,
    };
    const getBondAnalyticsTopHoldings = vi.fn<ApiClient["getBondAnalyticsTopHoldings"]>(
      async (...args) => {
        const envelope = await mockSource.getBondAnalyticsTopHoldings(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            items: [
              {
                instrument_code: "240001.IB",
                instrument_name: "测试国债01",
                issuer_name: "财政部",
                rating: "AAA",
                asset_class: "利率债",
                market_value: yuan(12_350_000_000, "123.50 亿"),
                face_value: yuan(12_000_000_000, "120.00 亿"),
                ytm: pct(0.0236, "2.36%"),
                modified_duration: ratio(4.21, "4.21"),
                weight: pct(0.0961, "9.61%"),
              },
            ],
          },
        };
      },
    );
    const getBondAnalyticsPositionChanges = vi.fn<ApiClient["getBondAnalyticsPositionChanges"]>(
      async (...args) => {
        const envelope = await mockSource.getBondAnalyticsPositionChanges(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-04-30",
            prev_report_date: "2026-04-29",
            source_status: "ready",
            items: [
              {
                instrument_code: "240002.IB",
                instrument_name: "测试增持债",
                issuer_name: "财政部",
                rating: "AAA",
                asset_class: "rate",
                previous_market_value: yuan(10_000_000_000, "100.00 亿"),
                current_market_value: yuan(13_000_000_000, "130.00 亿"),
                change_market_value: signedYuan(3_000_000_000, "+30.00 亿"),
                previous_weight: ratio(0.08, "8.00%"),
                current_weight: ratio(0.1, "10.00%"),
                change_weight: ratio(0.02, "+2.00pp"),
                direction: "increase" as const,
                reason_label: "增持",
                source_status: "ready" as const,
              },
            ],
          },
        };
      },
    );
    const getHomeResearchReports = vi.fn<ApiClient["getHomeResearchReports"]>(
      async (...args) => {
        const envelope = await mockSource.getHomeResearchReports(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-04-30",
            source_status: "ready",
            items: [
              {
                id: "research-1",
                title: "利率债周报",
                category: "fixed_income",
                published_at: "2026-04-29T09:00:00",
                link: "https://example.com/report.pdf",
                source: "tushare_research",
                source_status: "ready" as const,
                summary: "关注久期和曲线",
              },
            ],
          },
        };
      },
    );
    const getHomeIncomeTrend = vi.fn<ApiClient["getHomeIncomeTrend"]>(
      async (reportDate, window = 7) => {
        const envelope = await mockSource.getHomeSnapshot({ reportDate });
        return {
          ...envelope,
          result_meta: {
            ...envelope.result_meta,
            result_kind: "home.income_trend",
          },
          result: {
            report_date: "2026-04-30",
            window,
            source_status: "partial",
            missing_components: ["benchmark_pnl", "excess_pnl"],
            warnings: ["Benchmark and excess PnL are not available."],
            points: [
              {
                date: "2026-03-31",
                portfolio_pnl: signedYuan(120_000_000, "+1.20 yi"),
                benchmark_pnl: missingYuan,
                excess_pnl: missingYuan,
                basis: "product_category_pnl_monthly" as const,
                source_status: "partial" as const,
              },
              {
                date: "2026-04-30",
                portfolio_pnl: signedYuan(90_000_000, "+0.90 yi"),
                benchmark_pnl: missingYuan,
                excess_pnl: missingYuan,
                basis: "product_category_pnl_monthly" as const,
                source_status: "partial" as const,
              },
            ],
          },
        };
      },
    );
    const client = createRealModeHomeClient({
      getHomeSnapshot,
      getBondAnalyticsTopHoldings,
      getBondAnalyticsPositionChanges,
      getHomeResearchReports,
      getHomeIncomeTrend,
      getResearchCalendarEvents: vi.fn(async () => []),
    });
    const idle = stubIdleCallbacks();

    renderDashboardHome(client);
    await settleHomeIdleWork(idle);

    await waitFor(() => {
      expect(getBondAnalyticsTopHoldings).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        14,
      );
      expect(getBondAnalyticsPositionChanges).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        5,
      );
      expect(getHomeResearchReports).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        5,
      );
      expect(getHomeIncomeTrend).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        7,
      );
    });
    await waitFor(() => {
      const holdingsTable = screen.getByTestId("dashboard-home-holdings-table");
      expect(within(holdingsTable).getAllByTestId("dashboard-home-holding-row").length).toBeGreaterThan(0);
    });
    const positionChanges = await screen.findByTestId("dashboard-home-position-changes");
    expect(positionChanges).toHaveTextContent("240002.IB");
    expect(positionChanges).toHaveTextContent("+30.00 亿");
    expect(positionChanges).not.toHaveTextContent("+2.00pp");
    expect(positionChanges).not.toHaveTextContent("现值");
    expect(
      within(positionChanges).getByTestId("dashboard-home-position-comparison"),
    ).toHaveAttribute("data-state", "unavailable");
    expect(
      within(positionChanges).getByRole("link", {
        name: /查看 .+（240002\.IB）明细/,
      }),
    ).toHaveAttribute(
      "href",
      "/bond-trading-desk?bond_code=240002.IB&report_date=2026-04-30",
    );
    const incomeTrend = await screen.findByTestId("dashboard-home-income-trend");
    await waitFor(() => {
      expect(incomeTrend).toHaveTextContent("组合");
      expect(incomeTrend).toHaveTextContent("基准");
      expect(incomeTrend).toHaveTextContent("超额");
      expect(incomeTrend).toHaveTextContent("+1.20");
    });
    expect(await screen.findByTestId("dashboard-home-research-reports")).toHaveTextContent("利率债周报");
    expect(screen.queryByTestId("dashboard-home-backend-gap-research-reports")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-home-backend-gap-position-changes")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-home-backend-gap-income-trend")).not.toBeInTheDocument();
  });

    /*
    expect(screen.getByTestId("dashboard-home-backend-gap-research-reports")).toHaveTextContent(
      "后端待接入",
    );
    expect(screen.getByTestId("dashboard-home-backend-gap-position-changes")).toHaveTextContent(
      "后端待接入",
    );
  });

    */
  it("renders supply and auction calendar items from the research calendar feed", async () => {
    const researchCalendarCalls: Array<{
      reportDate?: string;
      startDate?: string;
      endDate?: string;
    }> = [];
    const client = createRealModeHomeClient({
      getResearchCalendarEvents: async (options) => {
        researchCalendarCalls.push(options ?? {});
        return [
          {
            id: "cal_supply_001",
            date: "2026-04-18",
            title: "国债净融资节奏",
            kind: "supply" as const,
            severity: "medium" as const,
            amount_label: "净融资 180 亿元",
            note: "供给节奏",
          },
          {
            id: "cal_auction_002",
            date: "2026-04-19",
            title: "政策性金融债招标",
            kind: "auction" as const,
            severity: "high" as const,
            amount_label: "420 亿元",
            note: "国开行",
          },
        ];
      },
    });

    const idle = stubIdleCallbacks();

    renderDashboardHome(client);
    await settleHomeIdleWork(idle);

    const calendar = await screen.findByTestId("dashboard-home-research-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("国债净融资节奏");
      expect(calendar).toHaveTextContent("政策性金融债招标");
    });
    expect(calendar).toHaveTextContent("供给/招标：");
    expect(researchCalendarCalls.some((call) => call.startDate && call.endDate)).toBe(true);
  });

  it("keeps an explicit no-data state when the external event feed is empty", async () => {
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const mockNewsClient = createApiClient({ mode: "mock" });
    const getChoiceNewsEventsBatch = vi.fn((options: ChoiceNewsBatchOptions) =>
      mockNewsClient.getChoiceNewsEventsBatch(options),
    );
    const client = createRealModeHomeClient({
      getResearchCalendarEvents,
      getChoiceNewsEventsBatch,
    });

    renderDashboardHome(client);
    await settleHomeIdleWork(idle);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
      expect(getChoiceNewsEventsBatch).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-home-research-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("重大信息发布日期前瞻");
      expect(calendar).toHaveTextContent("政策与资金面");
      // b41cd303 视觉降噪后：信任条可见处收短文案，完整来源/状态/截至/刷新说明进 title。
      const trustStrip = within(calendar).getByLabelText("政策与资金面数据状态");
      expect(trustStrip).toHaveTextContent("来源 Choice 宏观新闻");
      const trustTooltip = trustStrip.getAttribute("title") ?? "";
      expect(trustTooltip).toContain("来源：Choice 宏观新闻");
      expect(trustTooltip).toContain("来源状态");
      expect(trustTooltip).toContain("数据截至");
      expect(trustTooltip).toContain("刷新：");
      expect(calendar).toHaveTextContent("供给/招标：已查询当前窗口，暂无事件");
      expect(calendar).not.toHaveTextContent("当前窗口暂无供给/招标事件。");
    });
    expect(requestedNewsTopicCodes(getChoiceNewsEventsBatch)).toEqual(
      expect.arrayContaining([
        "S888010007API",
        "S888010003API",
        "S888010005API",
        "S888005004API",
        "C000003006",
        "C000003002",
      ]),
    );
    await waitFor(() => {
      expect(requestedNewsGroupIds(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(bondNewsGroupIds()),
      );
    });
  });

  it("keeps an explicit error state when the external event feed fails", async () => {
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => {
      throw new Error("calendar backend unavailable");
    });
    const client = createRealModeHomeClient({ getResearchCalendarEvents });

    renderDashboardHome(client);
    await settleHomeIdleWork(idle);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-home-research-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("供给/招标：加载失败");
    });
  });
});
