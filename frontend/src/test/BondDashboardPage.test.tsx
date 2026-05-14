import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import BondDashboardPage from "../features/bond-dashboard/pages/BondDashboardPage";
import { formatRawAsNumeric } from "../utils/format";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="bond-dashboard-echarts-stub" />,
}));

function resultMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-19T00:00:00Z",
  };
}

const yuan = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
const pct = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
const ratio = (raw: number) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
const dv01 = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });

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

    const reportDateInput = await screen.findByRole("combobox", { name: "bond-dashboard-report-date" });
    await waitFor(() => {
      expect(reportDateInput).not.toBeDisabled();
    });
    const initial = spy.mock.calls.length;
    const reportDateSelect = reportDateInput.closest(".ant-select");
    expect(reportDateSelect).not.toBeNull();
    fireEvent.mouseDown(reportDateSelect!.querySelector(".ant-select-selector")!);
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

  it("uses backend headline numerics for weighted yield and duration in the portfolio table footer", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: resultMeta("bond_dashboard.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    client.getBondDashboardHeadlineKpis = async () => ({
      result_meta: resultMeta("bond_dashboard.headline_kpis"),
      result: {
        report_date: "2026-04-30",
        prev_report_date: null,
        kpis: {
          total_market_value: yuan(100_000_000_000),
          unrealized_pnl: yuan(0),
          weighted_ytm: pct(0.025656206199),
          weighted_duration: ratio(4.1367831054),
          weighted_coupon: pct(0.02),
          credit_spread_median: pct(0.01),
          total_dv01: dv01(1000),
          bond_count: 3,
        },
        prev_kpis: null,
      },
    });
    client.getBondDashboardPortfolioComparison = async () => ({
      result_meta: resultMeta("bond_dashboard.portfolio_comparison"),
      result: {
        report_date: "2026-04-30",
        items: [
          {
            portfolio_name: "Rate + credit",
            total_market_value: yuan(40_000_000_000),
            weighted_ytm: pct(0.035),
            weighted_duration: ratio(5),
            total_dv01: dv01(500),
            bond_count: 2,
          },
          {
            portfolio_name: "Other heavy",
            total_market_value: yuan(60_000_000_000),
            weighted_ytm: pct(0),
            weighted_duration: ratio(0),
            total_dv01: dv01(0),
            bond_count: 1,
          },
        ],
      },
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

    await screen.findByRole("heading", { name: "债券总览" });
    await waitFor(() => {
      expect(screen.getByTestId("bond-dashboard-portfolio-summary-ytm")).toHaveTextContent("2.57");
      expect(screen.getByTestId("bond-dashboard-portfolio-summary-duration")).toHaveTextContent("4.14");
    });
  });

  it("renders non-zero dashboard values from Numeric API payloads", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: resultMeta("bond_dashboard.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    client.getBondDashboardHeadlineKpis = async () => ({
      result_meta: resultMeta("bond_dashboard.headline_kpis"),
      result: {
        report_date: "2026-04-30",
        prev_report_date: null,
        kpis: {
          total_market_value: yuan(343_822_795_478.69),
          unrealized_pnl: yuan(0),
          weighted_ytm: pct(0.02565621),
          weighted_duration: ratio(4.13678311),
          weighted_coupon: pct(0.02),
          credit_spread_median: pct(0.01),
          total_dv01: dv01(106_155_944.31),
          bond_count: 251,
        },
        prev_kpis: null,
      },
    });
    client.getBondDashboardRiskIndicators = async () => ({
      result_meta: resultMeta("bond_dashboard.risk_indicators"),
      result: {
        report_date: "2026-04-30",
        total_market_value: yuan(343_822_795_478.69),
        total_dv01: dv01(106_155_944.31),
        weighted_duration: ratio(4.13678311),
        credit_ratio: ratio(0.29250449),
        weighted_convexity: ratio(0.03),
        total_spread_dv01: dv01(31_000_000),
        reinvestment_ratio_1y: ratio(0.12),
      },
    });
    client.getBondDashboardPortfolioComparison = async () => ({
      result_meta: resultMeta("bond_dashboard.portfolio_comparison"),
      result: {
        report_date: "2026-04-30",
        items: [
          {
            portfolio_name: "Core book",
            total_market_value: yuan(343_822_795_478.69),
            weighted_ytm: pct(0.02565621),
            weighted_duration: ratio(4.13678311),
            total_dv01: dv01(106_155_944.31),
            bond_count: 251,
          },
        ],
      },
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

    const scaleCard = await screen.findByTestId("bond-dashboard-kpi-total_market_value");
    expect(scaleCard.textContent?.replace(/,/g, "")).toContain("3438.23");

    await waitFor(() => {
      expect(screen.getByTestId("bond-dashboard-risk-row-credit_ratio")).toHaveTextContent("29.25%");
      expect(screen.getByTestId("bond-dashboard-portfolio-summary-ytm")).toHaveTextContent("2.57");
    });
  });

  it("loads the first-screen decision data before lower dashboard panels", async () => {
    const client = createApiClient({ mode: "mock" });
    const calls: string[] = [];
    client.getBondDashboardDates = async () => {
      calls.push("dates");
      return {
        result_meta: resultMeta("bond_dashboard.dates"),
        result: { report_dates: ["2026-04-30"] },
      };
    };
    client.getBondDashboardHeadlineKpis = async () => {
      calls.push("headline");
      return {
        result_meta: resultMeta("bond_dashboard.headline_kpis"),
        result: {
          report_date: "2026-04-30",
          prev_report_date: null,
          kpis: {
            total_market_value: yuan(100_000_000),
            unrealized_pnl: yuan(0),
            weighted_ytm: pct(0.025),
            weighted_duration: ratio(4.1),
            weighted_coupon: pct(0.02),
            credit_spread_median: pct(0.01),
            total_dv01: dv01(100),
            bond_count: 1,
          },
          prev_kpis: null,
        },
      };
    };
    client.getBondDashboardRiskIndicators = async () => {
      calls.push("risk");
      return {
        result_meta: resultMeta("bond_dashboard.risk_indicators"),
        result: {
          report_date: "2026-04-30",
          total_market_value: yuan(100_000_000),
          credit_ratio: pct(0.4),
          weighted_duration: ratio(4.1),
          weighted_convexity: ratio(0.03),
          total_dv01: dv01(100),
          total_spread_dv01: dv01(40),
          reinvestment_ratio_1y: pct(0.12),
        },
      };
    };
    const lowerPanelMethods = [
      "getBondDashboardAssetStructure",
      "getBondDashboardYieldDistribution",
      "getBondDashboardPortfolioComparison",
      "getBondDashboardSpreadAnalysis",
      "getBondDashboardMaturityStructure",
      "getBondDashboardIndustryDistribution",
      "getBondBusinessTypeMetrics",
    ] as const;
    for (const method of lowerPanelMethods) {
      vi.spyOn(client, method).mockImplementation(async () => {
        calls.push(method);
        throw new Error(`${method} should wait for first-screen queries`);
      });
    }
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
      expect(calls).toEqual(["dates", "headline", "risk"]);
    });
    expect(await screen.findByTestId("bond-dashboard-conclusion")).toHaveTextContent("当前结论");
  });
});
