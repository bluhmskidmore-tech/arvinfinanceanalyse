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
  it("renders the governed dashboard shell while overview query is unresolved", async () => {
    const base = createApiClient({ mode: "mock" });
    let releaseOverview: (() => void) | undefined;
    const slowClient: ApiClient = {
      ...base,
      getOverview: async () => {
        await new Promise<void>((resolve) => {
          releaseOverview = resolve;
        });
        return base.getOverview();
      },
    };

    renderDashboard(slowClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-module-snapshot")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-structure-teaser")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-tasks-calendar")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(releaseOverview).toBeDefined();
    });
    releaseOverview?.();
    expect(await screen.findByTestId("dashboard-governed-meta")).toBeInTheDocument();
  });

  it("does not request excluded executive surfaces from the dashboard page", async () => {
    const base = createApiClient({ mode: "real" });
    let riskCalls = 0;
    let contributionCalls = 0;
    let alertsCalls = 0;

    const guardedClient: ApiClient = {
      ...base,
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

  it("shows governed result metadata instead of supplemental demo panels", async () => {
    renderDashboard();

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    const statusStrip = await screen.findByTestId("dashboard-data-status-strip");
    expect(statusStrip).toBeInTheDocument();
    expect(within(statusStrip).getByText("Overview")).toBeInTheDocument();
    expect(within(statusStrip).getByText("Attribution")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-governed-meta")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-module-snapshot")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-structure-teaser")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-tasks-calendar")).not.toBeInTheDocument();
  });

  it("surfaces a strong mock-data warning when the app is not using real APIs", async () => {
    renderDashboard();

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-data-warning")).toHaveTextContent(/mock/i);
  });

  it("uses one selected report date for both governed dashboard queries", async () => {
    const base = createApiClient({ mode: "real" });
    const overviewDates: Array<string | undefined> = [];
    const attributionDates: Array<string | undefined> = [];
    const datedClient: ApiClient = {
      ...base,
      getOverview: async (reportDate?: string) => {
        overviewDates.push(reportDate);
        return base.getOverview(reportDate);
      },
      getPnlAttribution: async (reportDate?: string) => {
        attributionDates.push(reportDate);
        return base.getPnlAttribution(reportDate);
      },
    };

    renderDashboard(datedClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();

    const reportDateInput = screen.getByLabelText("报告日");
    fireEvent.change(reportDateInput, { target: { value: "2026-03-31" } });

    await waitFor(() => {
      expect(overviewDates).toContain("2026-03-31");
      expect(attributionDates).toContain("2026-03-31");
    });

    const statusStrip = await screen.findByTestId("dashboard-data-status-strip");
    expect(within(statusStrip).getAllByText(/requested_date: 2026-03-31/i)).toHaveLength(2);
  });

  it("prefers backend-returned report dates over the local requested date label", async () => {
    const base = createApiClient({ mode: "mock" });
    const governedClient: ApiClient = {
      ...base,
      mode: "real",
      getOverview: async (reportDate?: string) => {
        const payload = await base.getOverview(reportDate);
        return {
          ...payload,
          result_meta: {
            ...payload.result_meta,
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
      getPnlAttribution: async (reportDate?: string) => {
        const payload = await base.getPnlAttribution(reportDate);
        return {
          ...payload,
          result_meta: {
            ...payload.result_meta,
            filters_applied: {
              report_date: "2026-02-28",
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
