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
import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
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
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
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
    expect(result.current.supplementalState?.label).toBe("等待补充查询");
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
});
