import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { AssetStructurePie } from "../features/bond-dashboard/components/AssetStructurePie";
import { CreditRatingBlocks } from "../features/bond-dashboard/components/CreditRatingBlocks";
import { IndustryTable } from "../features/bond-dashboard/components/IndustryTable";
import { MaturityStructureChart } from "../features/bond-dashboard/components/MaturityStructureChart";
import BondDashboardPage from "../features/bond-dashboard/pages/BondDashboardPage";
import { formatRawAsNumeric } from "../utils/format";
import {
  PORTFOLIO_CROSS_PAGE_EXPECTED,
  PORTFOLIO_CROSS_PAGE_REPORT_DATE,
  portfolioCrossPageBondHomeSummary,
  portfolioCrossPageEnvelope,
} from "./portfolioCrossPageGoldenSample";

vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => (
    <div data-testid="bond-dashboard-echarts-stub" data-option={JSON.stringify(option)} />
  ),
}));

function resultMeta(resultKind: string, overrides: Partial<ResultMeta> = {}): ResultMeta {
  const isBondHeadline = resultKind === "bond_dashboard.headline_kpis";
  return {
    trace_id: `tr_${resultKind}`,
    basis: isBondHeadline ? "analytical" : "formal",
    result_kind: resultKind,
    formal_use_allowed: !isBondHeadline,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: isBondHeadline ? "warning" : "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-19T00:00:00Z",
    ...overrides,
  };
}

const yuan = (raw: number | null) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
const pct = (raw: number | null) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
const ratio = (raw: number | null) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
const dv01 = (raw: number | null) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });

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
    client.getBondBusinessTypeMetrics = async () => ({
      result_meta: resultMeta("bond_dashboard.business_type_metrics"),
      result: {
        report_date: "2026-04-30",
        items: [
          {
            name: "Core book",
            market_value: "343822795478.69",
            weighted_avg_ytm_pct: "2.565621",
            weighted_avg_duration: "4.13678311",
            duration_source: "position_duration",
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
      expect(screen.getByTestId("bond-dashboard-conclusion")).toHaveTextContent("29.3%");
      expect(screen.getByTestId("bond-dashboard-risk-row-credit_ratio")).toHaveTextContent("29.25%");
      expect(screen.getByTestId("bond-dashboard-portfolio-summary-ytm")).toHaveTextContent("2.57");
      expect(screen.getByTestId("bond-dashboard-business-type-metrics")).toHaveTextContent("2.57%");
    });
  });

  it("does not turn missing governed numerics into a zero-exposure business conclusion", async () => {
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
          total_market_value: yuan(null),
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
    });
    client.getBondDashboardRiskIndicators = async () => ({
      result_meta: resultMeta("bond_dashboard.risk_indicators"),
      result: {
        report_date: "2026-04-30",
        total_market_value: yuan(null),
        total_dv01: dv01(100),
        weighted_duration: ratio(4.1),
        credit_ratio: ratio(null),
        weighted_convexity: ratio(0.03),
        total_spread_dv01: dv01(40),
        reinvestment_ratio_1y: ratio(0.12),
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

    const conclusion = await screen.findByTestId("bond-dashboard-conclusion");
    expect(conclusion).toHaveTextContent("暂无数据");
    expect(conclusion).toHaveTextContent("不形成投放状态结论");
    expect(conclusion).not.toHaveTextContent("尚未形成有效持仓");
    expect(conclusion).not.toHaveTextContent("信用占比 0.0%");
  });

  it("surfaces first-screen result_meta degradation for headline and risk envelopes", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardDates = async () => ({
      result_meta: resultMeta("bond_dashboard.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    client.getBondDashboardHeadlineKpis = async () => ({
      result_meta: resultMeta("bond_dashboard.headline_kpis", {
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
        resolved_report_date: "2026-04-29",
        as_of_date: "2026-04-29",
      }),
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
    });
    client.getBondDashboardRiskIndicators = async () => ({
      result_meta: resultMeta("bond_dashboard.risk_indicators", {
        quality_flag: "warning",
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
        resolved_report_date: "2026-04-29",
        as_of_date: "2026-04-29",
      }),
      result: {
        report_date: "2026-04-30",
        total_market_value: yuan(100_000_000),
        total_dv01: dv01(100),
        weighted_duration: ratio(4.1),
        credit_ratio: ratio(0.4),
        weighted_convexity: ratio(0.03),
        total_spread_dv01: dv01(40),
        reinvestment_ratio_1y: ratio(0.12),
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

    const metaPanel = await screen.findByTestId("bond-dashboard-first-screen-result-meta");
    expect(metaPanel).toHaveTextContent("供应商陈旧");
    expect(metaPanel).toHaveTextContent("最新快照降级");
    expect(metaPanel).toHaveTextContent("2026-04-29");
  });

  it("renders the shared portfolio golden sample on the bond dashboard source page", async () => {
    const client = createApiClient({ mode: "mock" });
    const sample = portfolioCrossPageBondHomeSummary();
    client.getBondDashboardDates = async () =>
      portfolioCrossPageEnvelope("bond_dashboard.dates", {
        report_dates: [PORTFOLIO_CROSS_PAGE_REPORT_DATE],
      });
    client.getBondDashboardHeadlineKpis = async () =>
      portfolioCrossPageEnvelope("bond_dashboard.headline_kpis", sample.headline);
    client.getBondDashboardRiskIndicators = async () =>
      portfolioCrossPageEnvelope("bond_dashboard.risk_indicators", sample.risk);
    client.getBondDashboardPortfolioComparison = async () =>
      portfolioCrossPageEnvelope("bond_dashboard.portfolio_comparison", sample.portfolio_comparison);
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

    const headline = await screen.findByTestId("bond-dashboard-headline-kpis");
    expect(within(headline).getByTestId("bond-dashboard-kpi-total_market_value")).toHaveTextContent(
      PORTFOLIO_CROSS_PAGE_EXPECTED.bondMarketValueYi,
    );
    expect(within(headline).getByTestId("bond-dashboard-kpi-weighted_duration")).toHaveTextContent(
      PORTFOLIO_CROSS_PAGE_EXPECTED.bondDuration,
    );
    expect(within(headline).getByTestId("bond-dashboard-kpi-total_dv01")).toHaveTextContent(
      PORTFOLIO_CROSS_PAGE_EXPECTED.bondDv01Wan,
    );
  });

  it("surfaces candidate metric and risk-source boundaries on the governed dashboard", async () => {
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

    const headlineBoundary = await screen.findByTestId("bond-dashboard-headline-candidate-boundary");
    expect(headlineBoundary).toHaveTextContent("MTR-BOND-001");
    expect(headlineBoundary).toHaveTextContent("pending_confirmation=true");
    expect(headlineBoundary).toHaveTextContent("GS-BOND-HEADLINE-A");
    expect(headlineBoundary).toHaveTextContent("非字典级批准");

    const riskBoundary = await screen.findByTestId("bond-dashboard-risk-source-boundary");
    expect(riskBoundary).toHaveTextContent("GAP-BOND-DASH-RISK");
    expect(riskBoundary).toHaveTextContent("不自动继承 GS-RISK-A");
  });

  it("renders credit-rating percentages from ratio Numeric values", () => {
    render(
      <CreditRatingBlocks
        loading={false}
        data={{
          report_date: "2026-04-30",
          group_by: "rating",
          total_market_value: yuan(200),
          items: [
            { category: "AAA", total_market_value: yuan(199), bond_count: 1, percentage: pct(0.995) },
            { category: "AA", total_market_value: yuan(1), bond_count: 1, percentage: pct(0.005) },
          ],
        }}
      />,
    );

    expect(screen.getByText("99.50%")).toBeInTheDocument();
    expect(screen.getByText("0.50%")).toBeInTheDocument();
  });

  it("renders industry percentages from ratio Numeric values", () => {
    render(
      <IndustryTable
        loading={false}
        data={{
          report_date: "2026-04-30",
          items: [
            {
              industry_name: "金融业",
              total_market_value: yuan(1),
              bond_count: 1,
              percentage: pct(0.005),
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("0.50")).toBeInTheDocument();
  });

  it("uses a segmented asset-structure group control without Ant Tabs overflow controls", () => {
    const onGroupByChange = vi.fn();
    const { container } = render(
      <AssetStructurePie
        loading={false}
        groupBy="bond_type"
        onGroupByChange={onGroupByChange}
        data={{
          report_date: "2026-04-30",
          group_by: "bond_type",
          total_market_value: yuan(200),
          items: [{ category: "Rate", total_market_value: yuan(200), bond_count: 1, percentage: pct(1) }],
        }}
      />,
    );

    expect(container.querySelector(".ant-tabs-nav")).toBeNull();
    expect(container.querySelector(".ant-tabs-nav-more")).toBeNull();

    const groupOptions = container.querySelectorAll(".ant-segmented-item");
    expect(groupOptions).toHaveLength(4);
    fireEvent.click(groupOptions[1]);

    expect(onGroupByChange).toHaveBeenCalledWith("rating");
  });

  it("passes percent-point data to the maturity structure line chart", () => {
    render(
      <MaturityStructureChart
        loading={false}
        data={{
          report_date: "2026-04-30",
          total_market_value: yuan(200),
          items: [
            { maturity_bucket: "7天内", total_market_value: yuan(1), bond_count: 1, percentage: pct(0.005) },
          ],
        }}
      />,
    );

    const option = JSON.parse(screen.getByTestId("bond-dashboard-echarts-stub").dataset.option ?? "{}");
    expect(option.series[1].data).toEqual([0.5]);
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
