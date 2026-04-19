import { useState, type ReactNode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";

vi.mock("../features/executive-dashboard/components/PnlAttributionSection", () => ({
  default: () => null,
}));
import { routerFuture } from "../router/routerFuture";
import { createWorkbenchMemoryRouter, renderWorkbenchApp } from "./renderWorkbenchApp";

function renderDashboard(client?: ApiClient) {
  if (!client) {
    return renderWorkbenchApp(["/"]);
  }

  const router = createWorkbenchMemoryRouter(["/"]);

  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <RouterProvider router={router} future={routerFuture} />
    </Wrapper>,
  );
}

describe("DashboardPage", () => {
  it("renders the governed dashboard shell while snapshot query is unresolved", async () => {
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

    renderDashboard(slowClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-overview-hero-strip")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    expect(await screen.findByTestId("dashboard-governed-meta")).toBeInTheDocument();
  });

  it("does not request excluded executive surfaces from the dashboard page", async () => {
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

    renderDashboard(guardedClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-governed-meta")).toBeInTheDocument();
    expect(riskCalls).toBe(0);
    expect(contributionCalls).toBe(0);
    expect(alertsCalls).toBe(0);
  });

  it("renders the dashboard overview cockpit sections", async () => {
    renderDashboard();

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    const statusStrip = await screen.findByTestId("dashboard-data-status-strip");
    expect(statusStrip).toBeInTheDocument();
    expect(within(statusStrip).getByText("Overview")).toBeInTheDocument();
    expect(within(statusStrip).getByText("Attribution")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-global-judgment")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-module-snapshot")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-alert-center")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-tasks-calendar")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-module-entry-grid")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-bond-headline-lead")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-macro-spot-grid")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-news-digest-list")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-bond-counterparty-section")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-liability-counterparty-section")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-governed-meta")).toBeInTheDocument();
  });

  it("surfaces a strong mock-data warning when the app is not using real APIs", async () => {
    renderDashboard();

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-data-warning")).toHaveTextContent(/mock/i);
  });

  it("uses one selected report date for the home snapshot query", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const snapshotOpts: Array<{ reportDate?: string; allowPartial?: boolean } | undefined> = [];
    const datedClient: ApiClient = {
      ...base,
      getHomeSnapshot: async (options) => {
        snapshotOpts.push(options);
        return mockSnapshotSource.getHomeSnapshot(options);
      },
    };

    renderDashboard(datedClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();

    const reportDateInput = screen.getByLabelText("报告日");
    fireEvent.change(reportDateInput, { target: { value: "2026-03-31" } });

    await waitFor(() => {
      expect(snapshotOpts.some((o) => o?.reportDate === "2026-03-31")).toBe(true);
    });

    const statusStrip = await screen.findByTestId("dashboard-data-status-strip");
    await waitFor(() => {
      expect(within(statusStrip).getAllByText(/as_of_date: 2026-04-18/i)).toHaveLength(2);
    });
  });

  it("prefers backend-returned snapshot report_date over the local requested date label", async () => {
    const base = createApiClient({ mode: "mock" });
    const governedClient: ApiClient = {
      ...base,
      mode: "real",
      getHomeSnapshot: async (options) => {
        const envelope = await base.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-02-28",
          },
          result_meta: {
            ...envelope.result_meta,
            filters_applied: {
              requested_report_date: "2026-02-28",
              effective_report_dates: {
                balance: "2026-02-28",
                pnl: "2026-02-28",
                liability: "2026-02-28",
                risk: "2026-02-28",
              },
            },
          },
        };
      },
    };

    renderDashboard(governedClient);

    const statusStrip = await screen.findByTestId("dashboard-data-status-strip");
    await waitFor(() => {
      expect(within(statusStrip).getAllByText(/as_of_date: 2026-02-28/i)).toHaveLength(2);
    });
  });
});
