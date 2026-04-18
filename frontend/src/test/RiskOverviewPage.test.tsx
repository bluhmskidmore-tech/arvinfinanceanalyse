import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="risk-overview-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ApiEnvelope, RiskTensorPayload, ResultMeta } from "../api/contracts";
import RiskOverviewPage from "../features/risk-overview/RiskOverviewPage";
import { formatRawAsNumeric } from "../utils/format";
import { routerFuture } from "../router/routerFuture";

const meta: ResultMeta = {
  trace_id: "test_trace",
  basis: "formal",
  result_kind: "risk.tensor",
  formal_use_allowed: true,
  source_version: "sv_test",
  vendor_version: "vv_test",
  rule_version: "rv_test",
  cache_version: "cv_test",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-04-12T10:00:00Z",
};

function tensorEnvelope(overrides: Partial<RiskTensorPayload> = {}): ApiEnvelope<RiskTensorPayload> {
  return {
    result_meta: meta,
    result: {
      report_date: "2025-12-31",
      portfolio_dv01: "120.5",
      krd_1y: "10",
      krd_3y: "20",
      krd_5y: "15",
      krd_7y: "8",
      krd_10y: "12",
      krd_30y: "5",
      cs01: "30.2",
      portfolio_convexity: "1.1",
      portfolio_modified_duration: "4.2",
      issuer_concentration_hhi: "0.12",
      issuer_top5_weight: "0.25",
      liquidity_gap_30d: "100",
      liquidity_gap_90d: "200",
      liquidity_gap_30d_ratio: "0.05",
      total_market_value: "1000000",
      bond_count: 42,
      quality_flag: "ok",
      warnings: [],
      ...overrides,
    },
  };
}

function renderRiskOverview(client: ApiClient, initialEntry = "/risk-overview?report_date=2025-12-31") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  const router = createMemoryRouter(
    [{ path: "/risk-overview", element: <RiskOverviewPage /> }],
    { initialEntries: [initialEntry], future: routerFuture },
  );
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <RouterProvider router={router} future={routerFuture} />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("RiskOverviewPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders risk tensor KPIs from getRiskTensor (主链)", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getRiskTensor: vi.fn(async () => tensorEnvelope()),
    };

    renderRiskOverview(client);

    expect(await screen.findByRole("heading", { name: "风险总览" })).toBeInTheDocument();
    expect(screen.getByText(/\/api\/risk\/tensor/)).toBeInTheDocument();
    expect(await screen.findByTestId("risk-overview-kpi-grid")).toBeInTheDocument();
    expect(await screen.findByText("120.5")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("正式风险张量（主数据）")).toBeInTheDocument();
    expect(screen.getByTestId("risk-overview-result-meta-panel")).toHaveTextContent("test_trace");
    expect(screen.getByTestId("risk-overview-result-meta-panel")).toHaveTextContent("sv_test");
  });

  it("uses backend risk tensor dates for the default report date", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getRiskTensorDates: vi.fn(async () => ({
        result_meta: { ...meta, result_kind: "risk.tensor.dates" },
        result: { report_dates: ["2026-02-28", "2025-12-31"] },
      })),
      getRiskTensor: vi.fn(async (reportDate: string) => tensorEnvelope({ report_date: reportDate })),
      getBondAnalyticsKrdCurveRisk: vi.fn(async (reportDate: string) => ({
        result_meta: { ...meta, result_kind: "bond_analytics.krd_curve_risk" },
        result: {
          report_date: reportDate,
          portfolio_duration: "3",
          portfolio_modified_duration: "3.1",
          portfolio_dv01: "100",
          portfolio_convexity: "0.5",
          krd_buckets: [],
          scenarios: [],
          by_asset_class: [],
          warnings: [],
          computed_at: "2026-04-12T00:00:00Z",
        },
      })),
      getBondAnalyticsCreditSpreadMigration: vi.fn(async (reportDate: string) => ({
        result_meta: { ...meta, result_kind: "bond_analytics.credit_spread_migration" },
        result: {
          report_date: reportDate,
          credit_bond_count: 10,
          credit_market_value: "1",
          credit_weight: "0.1",
          spread_dv01: "2",
          weighted_avg_spread: "100",
          weighted_avg_spread_duration: "4",
          spread_scenarios: [],
          migration_scenarios: [],
          oci_credit_exposure: "0",
          oci_spread_dv01: "0",
          oci_sensitivity_25bp: "0",
          warnings: [],
          computed_at: "2026-04-12T00:00:00Z",
        },
      })),
    };

    renderRiskOverview(client, "/risk-overview");

    expect(await screen.findByText("报告日：")).toBeInTheDocument();
    expect(await screen.findByText("2026-02-28")).toBeInTheDocument();
    expect(client.getRiskTensorDates).toHaveBeenCalledTimes(1);
    expect(client.getRiskTensor).toHaveBeenCalledWith("2026-02-28");
    expect(client.getBondAnalyticsKrdCurveRisk).toHaveBeenCalledWith("2026-02-28");
    expect(client.getBondAnalyticsCreditSpreadMigration).toHaveBeenCalledWith("2026-02-28");
  });

  it("does not fall back to a hardcoded report date when backend dates are empty", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getRiskTensorDates: vi.fn(async () => ({
        result_meta: { ...meta, result_kind: "risk.tensor.dates" },
        result: { report_dates: [] },
      })),
      getRiskTensor: vi.fn(async () => tensorEnvelope()),
    };

    renderRiskOverview(client, "/risk-overview");

    expect(await screen.findByText("后端未返回可用风险报告日。")).toBeInTheDocument();
    expect(client.getRiskTensor).not.toHaveBeenCalled();
  });

  it("keeps rendering explicit report_date data even if dates lookup fails", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getRiskTensorDates: vi.fn(async () => {
        throw new Error("dates backend unavailable");
      }),
      getRiskTensor: vi.fn(async (reportDate: string) => tensorEnvelope({ report_date: reportDate })),
      getBondAnalyticsKrdCurveRisk: vi.fn(async (reportDate: string) => ({
        result_meta: { ...meta, result_kind: "bond_analytics.krd_curve_risk" },
        result: {
          report_date: reportDate,
          portfolio_duration: "3",
          portfolio_modified_duration: "3.1",
          portfolio_dv01: "100",
          portfolio_convexity: "0.5",
          krd_buckets: [],
          scenarios: [],
          by_asset_class: [],
          warnings: [],
          computed_at: "2026-04-12T00:00:00Z",
        },
      })),
      getBondAnalyticsCreditSpreadMigration: vi.fn(async (reportDate: string) => ({
        result_meta: { ...meta, result_kind: "bond_analytics.credit_spread_migration" },
        result: {
          report_date: reportDate,
          credit_bond_count: 10,
          credit_market_value: "1",
          credit_weight: "0.1",
          spread_dv01: "2",
          weighted_avg_spread: "100",
          weighted_avg_spread_duration: "4",
          spread_scenarios: [],
          migration_scenarios: [],
          oci_credit_exposure: "0",
          oci_spread_dv01: "0",
          oci_sensitivity_25bp: "0",
          warnings: [],
          computed_at: "2026-04-12T00:00:00Z",
        },
      })),
    };

    renderRiskOverview(client, "/risk-overview?report_date=2025-12-31");

    expect(await screen.findByTestId("risk-overview-kpi-grid")).toBeInTheDocument();
    expect(screen.queryByText("数据载入失败。")).not.toBeInTheDocument();
    expect(client.getRiskTensor).toHaveBeenCalledWith("2025-12-31");
  });

  it("shows Bond Analytics drill-down sections when fetch succeeds", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getRiskTensor: vi.fn(async () => tensorEnvelope()),
      getBondAnalyticsKrdCurveRisk: vi.fn(async () => ({
        result_meta: { ...meta, result_kind: "bond_analytics.krd_curve_risk" },
        result: {
          report_date: "2025-12-31",
          portfolio_duration: formatRawAsNumeric({ raw: 3, unit: "ratio", sign_aware: false }),
          portfolio_modified_duration: formatRawAsNumeric({ raw: 3.1, unit: "ratio", sign_aware: false }),
          portfolio_dv01: formatRawAsNumeric({ raw: 100, unit: "dv01", sign_aware: false }),
          portfolio_convexity: formatRawAsNumeric({ raw: 0.5, unit: "ratio", sign_aware: false }),
          krd_buckets: [
            {
              tenor: "1Y",
              krd: formatRawAsNumeric({ raw: 10, unit: "ratio", sign_aware: true }),
              dv01: formatRawAsNumeric({ raw: 1.1, unit: "dv01", sign_aware: false }),
              market_value_weight: formatRawAsNumeric({ raw: 0.12, unit: "ratio", sign_aware: false }),
            },
            {
              tenor: "5Y",
              krd: formatRawAsNumeric({ raw: 25, unit: "ratio", sign_aware: true }),
              dv01: formatRawAsNumeric({ raw: 2.5, unit: "dv01", sign_aware: false }),
              market_value_weight: formatRawAsNumeric({ raw: 0.28, unit: "ratio", sign_aware: false }),
            },
          ],
          scenarios: [],
          by_asset_class: [],
          warnings: [],
          computed_at: "2026-04-12T00:00:00Z",
        },
      })),
      getBondAnalyticsCreditSpreadMigration: vi.fn(async () => ({
        result_meta: { ...meta, result_kind: "bond_analytics.credit_spread_migration" },
        result: {
          report_date: "2025-12-31",
          credit_bond_count: 10,
          credit_market_value: formatRawAsNumeric({ raw: 1, unit: "yuan", sign_aware: false }),
          credit_weight: formatRawAsNumeric({ raw: 0.1, unit: "ratio", sign_aware: false }),
          spread_dv01: formatRawAsNumeric({ raw: 2, unit: "dv01", sign_aware: false }),
          weighted_avg_spread: formatRawAsNumeric({ raw: 100, unit: "bp", sign_aware: false }),
          weighted_avg_spread_duration: formatRawAsNumeric({ raw: 4, unit: "ratio", sign_aware: false }),
          spread_scenarios: [],
          migration_scenarios: [],
          concentration_by_issuer: {
            dimension: "issuer",
            hhi: formatRawAsNumeric({ raw: 0.22, unit: "ratio", sign_aware: false }),
            top5_concentration: formatRawAsNumeric({ raw: 0.51, unit: "ratio", sign_aware: false }),
            top_items: [
              {
                name: "城投集团A",
                weight: { raw: 0.18, unit: "ratio", display: "0.18", precision: 2, sign_aware: false },
                market_value: formatRawAsNumeric({ raw: 320_000_000, unit: "yuan", sign_aware: false }),
              },
              {
                name: "产业集团B",
                weight: formatRawAsNumeric({ raw: 0.12, unit: "ratio", sign_aware: false }),
                market_value: formatRawAsNumeric({ raw: 210_000_000, unit: "yuan", sign_aware: false }),
              },
            ],
          },
          oci_credit_exposure: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
          oci_spread_dv01: formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: false }),
          oci_sensitivity_25bp: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: true }),
          warnings: [],
          computed_at: "2026-04-12T00:00:00Z",
        },
      })),
    };

    renderRiskOverview(client);

    expect(await screen.findByText(/Bond Analytics 下钻与补充/)).toBeInTheDocument();
    expect(await screen.findByText("利率曲线与 KRD 风险（物化下钻）")).toBeInTheDocument();
    expect(await screen.findByText("信用利差迁移（物化下钻）")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("risk-overview-bond-krd-kpi-grid")).toBeInTheDocument();
    });
    expect(screen.getByTestId("risk-overview-tenor-drill")).toHaveTextContent("5Y");
    expect(screen.getByTestId("risk-overview-issuer-drill")).toHaveTextContent("城投集团A");
    expect(screen.getByTestId("risk-overview-issuer-drill")).toHaveTextContent("0.18");
    expect(screen.getByTestId("risk-overview-result-meta-panel")).toHaveTextContent(
      "bond_analytics.krd_curve_risk",
    );
    expect(screen.getByTestId("risk-overview-result-meta-panel")).toHaveTextContent(
      "bond_analytics.credit_spread_migration",
    );
  });
});
