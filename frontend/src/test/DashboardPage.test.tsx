import { useState, type ReactNode } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
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
  it("renders dashboard chrome while overview query is unresolved", async () => {
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
    expect(screen.getByTestId("dashboard-module-snapshot")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-structure-teaser")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-tasks-calendar")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseOverview).toBeDefined();
    });
    releaseOverview?.();
    expect(await screen.findAllByText(/MOSS/i)).not.toHaveLength(0);
  });

  it("renders module links and action panels after queries settle", async () => {
    renderDashboard();

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();

    const moduleSnapshot = screen.getByTestId("dashboard-module-snapshot");
    expect(within(moduleSnapshot).getAllByRole("link")).toHaveLength(4);

    const structureTeaser = screen.getByTestId("dashboard-structure-teaser");
    expect(within(structureTeaser).getAllByRole("link")).toHaveLength(2);

    const tasksAndCalendar = screen.getByTestId("dashboard-tasks-calendar");
    expect(within(tasksAndCalendar).getAllByText("演示数据")).toHaveLength(2);

    expect(await screen.findAllByText(/MOSS/i)).not.toHaveLength(0);
  });

  it("hides incomplete executive panels when backend marks them vendor_unavailable", async () => {
    const mockBase = createApiClient({ mode: "mock" });
    const unavailableClient: ApiClient = {
      ...mockBase,
      mode: "real",
      getRiskOverview: async () => ({
        result_meta: {
          ...(await mockBase.getRiskOverview()).result_meta,
          vendor_status: "vendor_unavailable",
        },
        result: {
          title: "风险全景",
          signals: [],
        },
      }),
      getContribution: async () => ({
        result_meta: {
          ...(await mockBase.getContribution()).result_meta,
          vendor_status: "vendor_unavailable",
        },
        result: {
          title: "团队 / 账户 / 策略贡献",
          rows: [],
        },
      }),
      getAlerts: async () => ({
        result_meta: {
          ...(await mockBase.getAlerts()).result_meta,
          vendor_status: "vendor_unavailable",
        },
        result: {
          title: "预警与事件",
          items: [],
        },
      }),
    };

    renderDashboard(unavailableClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("预警中心")).not.toBeInTheDocument();
      expect(screen.queryByText("风险全景")).not.toBeInTheDocument();
      expect(screen.queryByText("团队 / 账户 / 策略贡献")).not.toBeInTheDocument();
    });
    expect(screen.getByText("收益归因与风险分解")).toBeInTheDocument();
  });

  it("shows supplemental executive panels in real mode when governed data is available", async () => {
    const mockBase = createApiClient({ mode: "mock" });
    const realClient: ApiClient = {
      ...mockBase,
      mode: "real",
      getRiskOverview: async () => mockBase.getRiskOverview(),
      getContribution: async () => mockBase.getContribution(),
      getAlerts: async () => mockBase.getAlerts(),
    };

    renderDashboard(realClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    expect(await screen.findByText("预警中心")).toBeInTheDocument();
    expect(await screen.findByText("风险全景")).toBeInTheDocument();
    expect(await screen.findByText("团队 / 账户 / 策略贡献")).toBeInTheDocument();
  });

  it("hides supplemental executive panels in real mode when the backend responds with 503", async () => {
    const mockBase = createApiClient({ mode: "mock" });
    const unavailableClient: ApiClient = {
      ...mockBase,
      mode: "real",
      getRiskOverview: async () => {
        throw new Error("Request failed: /ui/risk/overview (503)");
      },
      getContribution: async () => {
        throw new Error("Request failed: /ui/home/contribution (503)");
      },
      getAlerts: async () => {
        throw new Error("Request failed: /ui/home/alerts (503)");
      },
    };

    renderDashboard(unavailableClient);

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("预警中心")).not.toBeInTheDocument();
      expect(screen.queryByText("风险全景")).not.toBeInTheDocument();
      expect(screen.queryByText("团队 / 账户 / 策略贡献")).not.toBeInTheDocument();
    });
  });
});
