import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import BondDashboardPage from "../features/bond-dashboard/pages/BondDashboardPage";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="bond-dashboard-echarts-stub" />,
}));

describe("BondDashboardPage", () => {
  it("shows title and KPI cards when mock data loads", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <BondDashboardPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "债券总览" })).toBeInTheDocument();
    await waitFor(() => {
      const conclusion = screen.getByTestId("bond-dashboard-conclusion");
      expect(conclusion).toHaveTextContent("当前结论");
      expect(conclusion).toHaveTextContent("当前信用占比");
      expect(conclusion).toHaveTextContent("总市值");
    });
    expect(await screen.findByText("债券持仓规模")).toBeInTheDocument();
    const headline = screen.getByTestId("bond-dashboard-headline-kpis");
    const scaleCard = within(headline).getByTestId("bond-dashboard-kpi-total_market_value");
    expect(scaleCard.textContent?.replace(/,/g, "")).toContain("3287.09");
  });

  it("refetches blocks when report date changes", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const spy = vi.spyOn(client, "getBondDashboardHeadlineKpis");
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <BondDashboardPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await screen.findByRole("combobox", { name: "bond-dashboard-report-date" });
    const initial = spy.mock.calls.length;
    await user.click(screen.getByRole("combobox", { name: "bond-dashboard-report-date" }));
    const listbox = await screen.findByRole("listbox");
    await user.click(within(listbox).getByText("2026-02-28"));

    await waitFor(() => {
      expect(spy.mock.calls.length).toBeGreaterThan(initial);
    });
  });

  it("surfaces an explicit empty-state note when no report dates are available", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: {
        trace_id: "tr_bond_dashboard_dates_empty",
        basis: "formal",
        result_kind: "bond_dashboard.dates",
        formal_use_allowed: true,
        source_version: "sv_empty",
        vendor_version: "vv_none",
        rule_version: "rv_empty",
        cache_version: "cv_empty",
        quality_flag: "warning",
        vendor_status: "ok",
        fallback_mode: "none",
        scenario_flag: false,
        generated_at: "2026-04-19T00:00:00Z",
      },
      result: { report_dates: [] },
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <BondDashboardPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("bond-dashboard-page-state")).toHaveTextContent("暂无可用报告日");
    });
    expect(screen.getByRole("combobox", { name: "bond-dashboard-report-date" })).toBeDisabled();
  });
});
