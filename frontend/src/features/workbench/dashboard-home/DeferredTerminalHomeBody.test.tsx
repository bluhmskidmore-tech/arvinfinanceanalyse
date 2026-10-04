import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
import { createMockHomeFirstScreenView } from "./dashboardHomeFirstScreenMockView";
import { DeferredTerminalHomeBody } from "./DeferredTerminalHomeBody";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";

function renderBody() {
  const mock = createApiClient({ mode: "mock" });
  const dataClient = {
    ...mock,
    mode: "real",
    getBondAnalyticsTopHoldings: vi.fn(mock.getBondAnalyticsTopHoldings),
    getHomeResearchReports: vi.fn(mock.getHomeResearchReports),
    getBondAnalyticsKrdCurveRisk: vi.fn(mock.getBondAnalyticsKrdCurveRisk),
    getChoiceNewsEventsBatch: vi.fn(mock.getChoiceNewsEventsBatch),
    getResearchCalendarEvents: vi.fn(async () => []),
  } satisfies ApiClient;
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, refetchOnWindowFocus: false } },
  });
  const snapshotBoundary = {
    dataClient,
    snapshotQuery: {},
    adapterOutput: { attribution: { vm: null } },
    snapshotResult: { report_date: "2026-05-31" },
    initialEffectiveReportDate: "2026-05-31",
    supplementalReportDate: "2026-05-31",
    refreshSnapshot: async () => undefined,
  } as unknown as DashboardHomeSnapshotBoundary;
  const result = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DeferredTerminalHomeBody
          snapshotBoundary={snapshotBoundary}
          firstScreenView={createMockHomeFirstScreenView()}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, dataClient };
}

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("DeferredTerminalHomeBody section requests", () => {
  it("observes real section roots, keeps unseen news pending, and retains seen sections after leaving", async () => {
    vi.useFakeTimers();
    const observers = new Map<Element, { enter: (visible: boolean) => void }>();
    vi.stubGlobal("IntersectionObserver", class {
      private active = true;
      constructor(private callback: IntersectionObserverCallback) {}
      observe(target: Element) {
        observers.set(target, { enter: (visible) => {
          if (this.active) this.callback(
            [{ target, isIntersecting: visible } as IntersectionObserverEntry],
            this as unknown as IntersectionObserver,
          );
        } });
      }
      disconnect() { this.active = false; }
    });
    const { container, dataClient, unmount } = renderBody();
    try {
      expect(observers.size).toBe(5);
      await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
      expect(dataClient.getBondAnalyticsTopHoldings).not.toHaveBeenCalled();
      expect(dataClient.getHomeResearchReports).not.toHaveBeenCalled();
      expect(dataClient.getChoiceNewsEventsBatch).not.toHaveBeenCalled();
      const sources = screen.getByRole("table", { name: "来源核验明细" });
      const macroRow = within(sources).getByText("宏观新闻").closest("tr")!;
      const bondRow = within(sources).getByText("债券新闻").closest("tr")!;
      expect(within(macroRow).getByText("读取中")).toBeInTheDocument();
      expect(within(bondRow).getByText("读取中")).toBeInTheDocument();
      expect(within(macroRow).queryByText("暂无数据")).not.toBeInTheDocument();

      const holdings = container.querySelector('section[aria-labelledby="option-two-holdings-title"]')!;
      await act(async () => {
        observers.get(holdings)!.enter(true);
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(dataClient.getBondAnalyticsTopHoldings).toHaveBeenCalledTimes(1);
      expect(dataClient.getHomeResearchReports).not.toHaveBeenCalled();
      expect(dataClient.getChoiceNewsEventsBatch).not.toHaveBeenCalled();
      await act(async () => {
        observers.get(holdings)!.enter(false);
        observers.get(holdings)!.enter(true);
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(dataClient.getBondAnalyticsTopHoldings).toHaveBeenCalledTimes(1);

      await act(async () => {
        observers.get(screen.getByTestId("dashboard-home-deferred-matrix"))!.enter(true);
        observers.get(screen.getByTestId("dashboard-home-option-two-support-band"))!.enter(true);
        const evidence = container.querySelector('section[aria-labelledby="dashboard-home-research-evidence-title"]')!;
        observers.get(evidence)!.enter(true);
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(dataClient.getHomeResearchReports).toHaveBeenCalledTimes(1);
      expect(dataClient.getBondAnalyticsKrdCurveRisk).toHaveBeenCalledTimes(1);
      expect(dataClient.getChoiceNewsEventsBatch).toHaveBeenCalled();
    } finally {
      unmount();
    }
  });

  it("loads via the existing fallback if IntersectionObserver is unavailable", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("IntersectionObserver", undefined);
    const { dataClient, unmount } = renderBody();
    try {
      expect(dataClient.getBondAnalyticsTopHoldings).not.toHaveBeenCalled();
      await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
      expect(dataClient.getBondAnalyticsTopHoldings).toHaveBeenCalledTimes(1);
      expect(dataClient.getHomeResearchReports).toHaveBeenCalledTimes(1);
    } finally {
      unmount();
    }
  });

  it("cancels fallback work when the page unmounts before a section is requested", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("IntersectionObserver", undefined);
    const { dataClient, unmount } = renderBody();
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(dataClient.getBondAnalyticsTopHoldings).not.toHaveBeenCalled();
    expect(dataClient.getHomeResearchReports).not.toHaveBeenCalled();
  });
});
