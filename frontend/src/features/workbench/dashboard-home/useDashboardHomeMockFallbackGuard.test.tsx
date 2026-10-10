/**
 * real 模式 mock UI 不可达守卫（parseEnvMode.test 同风格的边界守卫）。
 *
 * isLiveDataFallback 在 useDashboardSnapshotBoundary 中已钉死为 false，
 * dashboard-home 三个视图模型的 useMockFallback 只允许由数据源模式决定
 * （mode !== "real"）。本文件用"敌意"快照边界（mode="real" 且
 * isLiveDataFallback=true）断言 real 模式下 useMockFallback 恒为 false，
 * 防止未来把运行时回退信号重新 OR 回 mock UI 判定。
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
import type { ResultMeta } from "../../../api/contracts";
import { DASHBOARD_COCKPIT_REPORT_DATE } from "../dashboard/dashboardMockData";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";
import { useDashboardHomeSupplementalHydration } from "./useDashboardHomeSupplementalHydration";
import { useDashboardHomeViewModel } from "./useDashboardHomeViewModel";

const boundaryMock = vi.hoisted(() => ({ current: null as unknown }));

vi.mock("../pages/useDashboardSnapshotBoundary", () => ({
  useDashboardSnapshotBoundary: () => boundaryMock.current,
}));

// 同步版真实行为：真实 hook 在 enabled 时异步动态 import mock 首屏视图；
// 这里同步返回同一份 mock 视图，保证"OR 回归 → mock 视图可达"能被断言捕获。
vi.mock("./useMockHomeFirstScreenView", async () => {
  const { createMockHomeFirstScreenView } = await import("./dashboardHomeFirstScreenMockView");
  return {
    useMockHomeFirstScreenView: (enabled: boolean) =>
      enabled ? createMockHomeFirstScreenView() : null,
  };
});

import { useDashboardHomeFirstScreenViewModel } from "./useDashboardHomeFirstScreenViewModel";

const REPORT_DATE = "2026-05-31";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </MemoryRouter>
    );
  };
}

function createRealModeClient(): ApiClient {
  return {
    ...createApiClient({ mode: "mock" }),
    mode: "real",
    getResearchCalendarEvents: vi.fn(async () => []),
  } as ApiClient;
}

/** mode="real" 但 isLiveDataFallback 被恶意置 true 的快照边界。 */
function buildHostileBoundary(dataClient: ApiClient): DashboardHomeSnapshotBoundary {
  return {
    dataClient,
    snapshotQuery: { isError: false, isFetching: false },
    isLiveDataFallback: true,
    adapterOutput: {
      overview: { vm: null, state: { kind: "empty" }, meta: null },
      attribution: { vm: null, state: { kind: "empty" }, meta: null },
      verdict: null,
      domainsEffectiveDate: {},
      domainsMissing: [],
      productCategoryHeadline: { state: "empty", metrics: [] },
      datesDiverged: false,
    },
    snapshotResult: { report_date: REPORT_DATE, mode: "strict", domains_missing: [] },
    snapshotMeta: null,
    initialEffectiveReportDate: REPORT_DATE,
    supplementalReportDate: REPORT_DATE,
    reportDateDataWarning: null,
    refreshSnapshot: vi.fn(),
  } as unknown as DashboardHomeSnapshotBoundary;
}

describe("dashboard-home · real 模式 useMockFallback 恒 false 守卫", () => {
  beforeEach(() => {
    boundaryMock.current = buildHostileBoundary(createRealModeClient());
  });

  it("first-screen view model ignores isLiveDataFallback in real mode", () => {
    const { result } = renderHook(() => useDashboardHomeFirstScreenViewModel(), {
      wrapper: createWrapper(),
    });

    expect(result.current.view.useMockFallback).toBe(false);
  });

  it("body view model maps live data instead of the mock body view in real mode", () => {
    const { result } = renderHook(
      () => useDashboardHomeViewModel(buildHostileBoundary(createRealModeClient())),
      { wrapper: createWrapper() },
    );

    // mock body view 会把 reportDate 钉成 DASHBOARD_COCKPIT_REPORT_DATE；
    // real 模式必须透传边界报告日。
    expect(result.current.view.reportDate).toBe(REPORT_DATE);
    expect(result.current.view.reportDate).not.toBe(DASHBOARD_COCKPIT_REPORT_DATE);
  });

  it("supplemental hydration keeps first-screen queries on the real path in real mode", () => {
    const { result } = renderHook(
      () => useDashboardHomeSupplementalHydration(buildHostileBoundary(createRealModeClient())),
      { wrapper: createWrapper() },
    );

    // useMockFallback=true 时该状态会是「样例模式未请求」。
    expect(result.current.supplementalState?.label).not.toBe("样例模式未请求");
    expect(result.current.supplementalState?.kind).toBe("loading");
  });

  it("mock mode still routes to the mock fallback view", () => {
    boundaryMock.current = buildHostileBoundary({
      ...createApiClient({ mode: "mock" }),
    } as ApiClient);

    const { result } = renderHook(() => useDashboardHomeFirstScreenViewModel(), {
      wrapper: createWrapper(),
    });

    expect(result.current.view.useMockFallback).toBe(true);
  });

  it("supplemental mock hydration preserves the mock report date and update time", async () => {
    const { createMockHomeFirstScreenView } = await import("./dashboardHomeFirstScreenMockView");
    const mockView = createMockHomeFirstScreenView();
    const { result } = renderHook(
      () => useDashboardHomeSupplementalHydration(buildHostileBoundary(createApiClient({ mode: "mock" }))),
      { wrapper: createWrapper() },
    );

    expect(result.current).toEqual({
      firstScreenHydration: { reportDate: mockView.reportDate, keyRiskStrip: mockView.keyRiskStrip },
      updatedAt: mockView.headerStatus.dataUpdatedAt,
      supplementalState: { kind: "backend-gap", label: "样例模式未请求" },
    });
  });
});

describe("supplemental hydration stays independent of the overview and attribution model", () => {
  afterEach(() => vi.useRealTimers());

  it("discloses stale supplemental sources even when the snapshot is healthy", async () => {
    const mockClient = createApiClient({ mode: "mock" });
    const [summary, portfolio, snapshot] = await Promise.all([
      mockClient.getBondDashboardHomeSummary(REPORT_DATE),
      mockClient.getBondAnalyticsPortfolioHeadlines(REPORT_DATE),
      mockClient.getHomeSnapshot({ reportDate: REPORT_DATE }),
    ]);
    const boundary = buildHostileBoundary({
      ...createRealModeClient(),
      getBondDashboardHomeSummary: vi.fn<ApiClient["getBondDashboardHomeSummary"]>(async () => ({
        ...summary,
        result_meta: { ...summary.result_meta, quality_flag: "stale", fallback_mode: "none" },
      } satisfies typeof summary)),
      getBondAnalyticsPortfolioHeadlines: vi.fn<ApiClient["getBondAnalyticsPortfolioHeadlines"]>(async () => ({
        ...portfolio,
        result_meta: { ...portfolio.result_meta, quality_flag: "stale", fallback_mode: "none" },
      } satisfies typeof portfolio)),
    });
    boundary.snapshotMeta = {
      ...snapshot.result_meta, quality_flag: "ok", fallback_mode: "none", generated_at: "2026-05-31T09:37:00",
    };
    vi.useFakeTimers();
    const { result, unmount } = renderHook(() => useDashboardHomeSupplementalHydration(boundary), {
      wrapper: createWrapper(),
    });
    for (let step = 0; step < 20 && result.current.supplementalState.kind === "loading"; step += 1) {
      await act(async () => { await vi.advanceTimersToNextTimerAsync(); });
    }

    expect(result.current.supplementalState.kind).toBe("stale");
    expect(result.current.supplementalState.label).toContain("数据偏旧");
    expect(result.current.supplementalState.label).toContain(REPORT_DATE);
    expect(result.current.firstScreenHydration.keyRiskStrip).toHaveLength(4);
    for (const ticker of result.current.firstScreenHydration.keyRiskStrip) {
      expect(ticker.delta).toContain("数据偏旧");
      expect(ticker.deltaTone).toBe("warn");
    }
    expect(result.current.updatedAt).toBe("09:37");
    unmount();
  });

  it.each([
    { summaryFails: false, portfolioFails: false, responseDate: REPORT_DATE, state: "ready", riskCount: 4 },
    { summaryFails: false, portfolioFails: false, responseDate: "2026-04-30", state: "partial", riskCount: 0 },
    { summaryFails: true, portfolioFails: false, responseDate: REPORT_DATE, state: "partial", riskCount: 4 },
    { summaryFails: true, portfolioFails: true, responseDate: REPORT_DATE, state: "error", riskCount: 0 },
  ])("preserves query states and date filtering: $state / $responseDate", async (scenario) => {
    const mockClient = createApiClient({ mode: "mock" });
    const [summary, portfolio, snapshot] = await Promise.all([
      mockClient.getBondDashboardHomeSummary(REPORT_DATE),
      mockClient.getBondAnalyticsPortfolioHeadlines(REPORT_DATE),
      mockClient.getHomeSnapshot({ reportDate: REPORT_DATE }),
    ]);
    const getBondDashboardHomeSummary = vi.fn<ApiClient["getBondDashboardHomeSummary"]>(async () => {
      if (scenario.summaryFails) throw new Error("summary unavailable");
      return {
        ...summary,
        result: {
          ...summary.result,
          headline: { ...summary.result.headline!, report_date: scenario.responseDate },
        },
      };
    });
    const getBondAnalyticsPortfolioHeadlines = vi.fn<ApiClient["getBondAnalyticsPortfolioHeadlines"]>(async () => {
      if (scenario.portfolioFails) throw new Error("portfolio unavailable");
      return { ...portfolio, result: { ...portfolio.result, report_date: scenario.responseDate } };
    });
    const boundary = buildHostileBoundary({
      ...createRealModeClient(), getBondDashboardHomeSummary, getBondAnalyticsPortfolioHeadlines,
    });
    boundary.snapshotMeta = { ...snapshot.result_meta, generated_at: "2026-05-31T09:37:00" };
    // A supplementary response must not need KPI copy, verdicts, domain state, or PnL segments.
    Object.defineProperty(boundary, "adapterOutput", {
      get: () => { throw new Error("supplemental hydration read the overview model"); },
    });
    vi.useFakeTimers();
    const { result, rerender, unmount } = renderHook(
      ({ currentBoundary }) => useDashboardHomeSupplementalHydration(currentBoundary),
      { wrapper: createWrapper(), initialProps: { currentBoundary: boundary } },
    );

    expect(result.current.supplementalState.kind).toBe("loading");
    expect(getBondDashboardHomeSummary).toHaveBeenCalledWith(REPORT_DATE);
    expect(getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledWith(REPORT_DATE);
    // Follow scheduled work until the observable query state settles, independently of gate delays.
    for (let step = 0; step < 20 && result.current.supplementalState.kind !== scenario.state; step += 1) {
      await act(async () => { await vi.advanceTimersToNextTimerAsync(); });
    }

    expect(getBondDashboardHomeSummary).toHaveBeenCalledWith(REPORT_DATE);
    expect(getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledWith(REPORT_DATE);
    expect(result.current.supplementalState.kind).toBe(scenario.state);
    expect(result.current.firstScreenHydration.reportDate).toBe(REPORT_DATE);
    expect(result.current.firstScreenHydration.keyRiskStrip).toHaveLength(scenario.riskCount);
    expect(result.current.updatedAt).toBe("09:37");

    const hydration = result.current.firstScreenHydration;
    // A failed request for a newer snapshot retains this cached snapshot and its timestamp.
    boundary.reportDateDataWarning = "新报告日读取失败，沿用旧快照";
    Object.assign(boundary.snapshotQuery, { isError: true });
    rerender({ currentBoundary: boundary });
    expect(result.current.firstScreenHydration).toBe(hydration);
    expect(result.current.updatedAt).toBe("09:37");
    unmount();
  });

  it.each<{
    name: string;
    meta: Partial<ResultMeta> | null;
    responseDate?: string;
    kind: "stale" | "partial";
    riskCount: number;
    message: string;
  }>([
    { name: "same-date stale", meta: { quality_flag: "stale" }, kind: "stale", riskCount: 4, message: "数据偏旧" },
    { name: "same-date warning", meta: { quality_flag: "warning" }, kind: "partial", riskCount: 4, message: "数据需复核" },
    { name: "stale vendor", meta: { vendor_status: "vendor_stale" }, kind: "stale", riskCount: 4, message: "数据偏旧" },
    { name: "same-date fallback", meta: { fallback_mode: "latest_snapshot", fallback_date: REPORT_DATE }, kind: "stale", riskCount: 4, message: "使用回退数据" },
    { name: "fallback date differs", meta: { fallback_mode: "latest_snapshot", fallback_date: "2026-04-30" }, kind: "partial", riskCount: 2, message: "2026-04-30" },
    { name: "resolved date differs", meta: { resolved_report_date: "2026-04-30" }, kind: "partial", riskCount: 2, message: "2026-04-30" },
    { name: "as-of date differs", meta: { as_of_date: "2026-04-30" }, kind: "partial", riskCount: 2, message: "2026-04-30" },
    { name: "payload date differs", meta: {}, responseDate: "2026-04-30", kind: "partial", riskCount: 2, message: "2026-04-30" },
    { name: "error quality", meta: { quality_flag: "error" }, kind: "partial", riskCount: 2, message: "数据不可用" },
    { name: "unavailable vendor", meta: { vendor_status: "vendor_unavailable" }, kind: "partial", riskCount: 2, message: "数据不可用" },
    { name: "missing metadata", meta: null, kind: "partial", riskCount: 2, message: "未返回质量信息" },
  ])("keeps the healthy headline independent of a portfolio source with $name", async (scenario) => {
    const mockClient = createApiClient({ mode: "mock" });
    const [summary, portfolio, snapshot] = await Promise.all([
      mockClient.getBondDashboardHomeSummary(REPORT_DATE),
      mockClient.getBondAnalyticsPortfolioHeadlines(REPORT_DATE),
      mockClient.getHomeSnapshot({ reportDate: REPORT_DATE }),
    ]);
    const portfolioEnvelope = {
      ...portfolio,
      result: { ...portfolio.result, report_date: scenario.responseDate ?? REPORT_DATE },
      result_meta: scenario.meta === null ? undefined : { ...portfolio.result_meta, ...scenario.meta },
    } as Awaited<ReturnType<ApiClient["getBondAnalyticsPortfolioHeadlines"]>>;
    const boundary = buildHostileBoundary({
      ...createRealModeClient(),
      getBondDashboardHomeSummary: vi.fn(async () => summary),
      getBondAnalyticsPortfolioHeadlines: vi.fn(async () => portfolioEnvelope),
    });
    boundary.snapshotMeta = { ...snapshot.result_meta, quality_flag: "ok", fallback_mode: "none" };
    vi.useFakeTimers();
    const { result, unmount } = renderHook(() => useDashboardHomeSupplementalHydration(boundary), {
      wrapper: createWrapper(),
    });
    for (let step = 0; step < 20 && result.current.supplementalState.kind === "loading"; step += 1) {
      await act(async () => { await vi.advanceTimersToNextTimerAsync(); });
    }

    expect(result.current.supplementalState.kind).toBe(scenario.kind);
    expect(result.current.supplementalState.label).toContain("组合风险摘要");
    expect(result.current.supplementalState.label).toContain(scenario.message);
    expect(result.current.firstScreenHydration.keyRiskStrip).toHaveLength(scenario.riskCount);
    const tickerById = new Map(result.current.firstScreenHydration.keyRiskStrip.map((ticker) => [ticker.id, ticker]));
    expect(tickerById.get("risk-dv01")?.delta).toBe("当前值");
    expect(tickerById.get("risk-duration")?.deltaTone).toBe("flat");
    if (scenario.riskCount === 4) {
      expect(tickerById.get("risk-top5")?.delta).toContain(scenario.message);
      expect(tickerById.get("risk-credit")?.deltaTone).toBe("warn");
    } else {
      expect(tickerById.has("risk-top5")).toBe(false);
      expect(tickerById.has("risk-credit")).toBe(false);
      expect(result.current.supplementalState.label).toContain("未展示");
    }
    unmount();
  });

  it("retains verified zero values and suppresses missing numeric fields", async () => {
    const mockClient = createApiClient({ mode: "mock" });
    const [summary, portfolio] = await Promise.all([
      mockClient.getBondDashboardHomeSummary(REPORT_DATE),
      mockClient.getBondAnalyticsPortfolioHeadlines(REPORT_DATE),
    ]);
    summary.result.headline!.kpis.total_dv01 = {
      raw: 0, raw_text: "0", unit: "dv01", display: "0.00", precision: 2, sign_aware: false,
    };
    summary.result.headline!.kpis.weighted_duration = {
      raw: null, raw_text: null, unit: "years", display: "5.99", precision: 2, sign_aware: false,
    };
    portfolio.result.issuer_top5_weight = {
      raw: 0, raw_text: "0", unit: "ratio", display: "0.00", precision: 2, sign_aware: false,
    };
    const boundary = buildHostileBoundary({
      ...createRealModeClient(),
      getBondDashboardHomeSummary: vi.fn(async () => summary),
      getBondAnalyticsPortfolioHeadlines: vi.fn(async () => portfolio),
    });
    vi.useFakeTimers();
    const { result, unmount } = renderHook(() => useDashboardHomeSupplementalHydration(boundary), {
      wrapper: createWrapper(),
    });
    for (let step = 0; step < 20 && result.current.supplementalState.kind === "loading"; step += 1) {
      await act(async () => { await vi.advanceTimersToNextTimerAsync(); });
    }

    expect(result.current.supplementalState).toEqual({ kind: "ready", label: "补充查询已完成" });
    const tickerById = new Map(result.current.firstScreenHydration.keyRiskStrip.map((ticker) => [ticker.id, ticker]));
    expect(tickerById.get("risk-dv01")?.value).toBe("0.00 万");
    expect(tickerById.get("risk-top5")?.value).toBe("0.00%");
    expect(tickerById.has("risk-duration")).toBe(false);
    expect(tickerById.get("risk-dv01")?.delta).toBe("当前值");
    unmount();
  });

  it.each([
    { isError: true, isFetching: false },
    { isError: false, isFetching: true },
  ])("waits for a real snapshot and leaves risk/time empty: %j", (snapshotQuery) => {
    const boundary = buildHostileBoundary(createRealModeClient());
    Object.assign(boundary.snapshotQuery, snapshotQuery);
    boundary.snapshotResult = undefined;
    boundary.supplementalReportDate = undefined;
    const { result } = renderHook(() => useDashboardHomeSupplementalHydration(boundary), {
      wrapper: createWrapper(),
    });

    expect(result.current).toEqual({
      firstScreenHydration: { reportDate: "—", keyRiskStrip: [] },
      updatedAt: "—",
      supplementalState: { kind: "backend-gap", label: "等待主快照报告日" },
    });
  });
});
