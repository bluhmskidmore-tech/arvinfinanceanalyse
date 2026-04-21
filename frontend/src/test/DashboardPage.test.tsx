import { useState, type ReactNode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import { formatRawAsNumeric } from "../utils/format";

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

function numericWithRawYuanDisplay(raw: number) {
  return {
    raw,
    unit: "yuan" as const,
    precision: 2,
    sign_aware: false,
    display: raw.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
  };
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
    expect(screen.queryByTestId("dashboard-governed-meta")).not.toBeInTheDocument();
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
    expect(screen.queryByTestId("dashboard-governed-meta")).not.toBeInTheDocument();
    expect(riskCalls).toBe(0);
    expect(contributionCalls).toBe(0);
    expect(alertsCalls).toBe(0);
  });

  it("renders the dashboard overview cockpit sections", async () => {
    renderDashboard();

    expect(await screen.findByTestId("fixed-income-dashboard-page")).toBeInTheDocument();
    const pills = await screen.findByTestId("dashboard-governance-pills");
    expect(pills).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-report-date")).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-snapshot")).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-attention")).toBeInTheDocument();
    expect(within(pills).getByTestId("governance-pill-source")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-data-status-strip")).not.toBeInTheDocument();
    const judgment = await screen.findByTestId("dashboard-global-judgment");
    expect(judgment).toBeInTheDocument();
    expect(
      await within(judgment).findByText("演示：首屏定调结论占位，用于展示 Pyramid 叙事结构。"),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-module-snapshot")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-alert-center")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-tasks-calendar")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-module-entry-grid")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-bond-headline-lead")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-macro-spot-grid")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-news-digest-list")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-bond-counterparty-section")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-liability-counterparty-section")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-governed-meta")).not.toBeInTheDocument();
  });

  it("surfaces counterparty concentration summaries on the home page", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const governedClient: ApiClient = {
      ...base,
      getHomeSnapshot: async (...args) => {
        const envelope = await mockSnapshotSource.getHomeSnapshot(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-03-31",
          },
        };
      },
      getPositionsCounterpartyBonds: async () => ({
        result_meta: {
          trace_id: "tr_test_dashboard_bond_counterparty",
          basis: "formal",
          result_kind: "positions.counterparty.bonds",
          formal_use_allowed: true,
          source_version: "sv_test",
          vendor_version: "vv_test",
          rule_version: "rv_test",
          cache_version: "cv_test",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-21T08:00:00Z",
        },
        result: {
          start_date: "2026-03-31",
          end_date: "2026-03-31",
          num_days: 1,
          items: [
            {
              customer_name: "青岛银行股份有限公司",
              total_amount: "118857000000",
              avg_daily_balance: "118857000000",
              weighted_rate: "1.9325",
              weighted_coupon_rate: "1.8125",
              transaction_count: 12,
            },
            {
              customer_name: "国家开发银行",
              total_amount: "48968000000",
              avg_daily_balance: "48968000000",
              weighted_rate: "2.0575",
              weighted_coupon_rate: "1.9440",
              transaction_count: 7,
            },
          ],
          total_amount: "167825000000",
          total_avg_daily: "167825000000",
          total_weighted_rate: "1.9691",
          total_weighted_coupon_rate: "1.8523",
          total_customers: 2,
        },
      }),
      getLiabilityCounterparty: async () => ({
        report_date: "2026-03-31",
        total_value: numericWithRawYuanDisplay(64768888887.83),
        top_10: [
          {
            name: "中国农业银行股份有限公司",
            value: numericWithRawYuanDisplay(6000000000),
            type: "Bank",
            weighted_cost: formatRawAsNumeric({ raw: 0.01, unit: "pct", sign_aware: false }),
          },
          {
            name: "浦银理财有限责任公司",
            value: numericWithRawYuanDisplay(5151033152.57),
            type: "NonBank",
            weighted_cost: formatRawAsNumeric({ raw: 0.02, unit: "pct", sign_aware: false }),
          },
        ],
        by_type: [
          {
            name: "Bank",
            value: formatRawAsNumeric({ raw: 38000000000, unit: "yuan", sign_aware: false }),
          },
          {
            name: "NonBank",
            value: formatRawAsNumeric({ raw: 26768888887.83, unit: "yuan", sign_aware: false }),
          },
        ],
      }),
    };

    renderDashboard(governedClient);

    const bondSection = await screen.findByTestId("dashboard-bond-counterparty-section");
    expect(await within(bondSection).findByText("区间累计")).toBeInTheDocument();
    expect(await within(bondSection).findByText("日均合计")).toBeInTheDocument();
    expect(await within(bondSection).findByText("加权付息率")).toBeInTheDocument();
    expect(await within(bondSection).findByText("青岛银行股份有限公司")).toBeInTheDocument();
    expect(await within(bondSection).findByText("1.97%")).toBeInTheDocument();
    expect(await within(bondSection).findByText("1.85%")).toBeInTheDocument();

    const liabilitySection = await screen.findByTestId("dashboard-liability-counterparty-section");
    expect(await within(liabilitySection).findByText("Top1 占比")).toBeInTheDocument();
    expect(await within(liabilitySection).findByText("银行占比")).toBeInTheDocument();
    expect(await within(liabilitySection).findByText("中国农业银行股份有限公司")).toBeInTheDocument();
    expect(within(liabilitySection).getByText("647.69 亿")).toBeInTheDocument();
    expect(within(liabilitySection).getByText(/余额 60\.00 亿/)).toBeInTheDocument();
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

    const reportDatePill = await screen.findByTestId("governance-pill-report-date");
    await waitFor(() => {
      expect(reportDatePill).toHaveTextContent("2026-04-18");
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

    const reportDatePill = await screen.findByTestId("governance-pill-report-date");
    await waitFor(() => {
      expect(reportDatePill).toHaveTextContent("2026-02-28");
    });
  });
});
