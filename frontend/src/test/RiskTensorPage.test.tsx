import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="risk-tensor-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ResultMeta, RiskTensorPayload } from "../api/contracts";
import { routerFuture } from "../router/routerFuture";
import { createWorkbenchMemoryRouter } from "./renderWorkbenchApp";

function buildMeta(resultKind: string, traceId: string): ResultMeta {
  return {
    trace_id: traceId,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_tensor_test",
    vendor_version: "vv_none",
    rule_version: "rv_tensor_test",
    cache_version: "cv_tensor_test",
    quality_flag: "warning",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T08:00:00Z",
  };
}

function tensorResult(reportDate: string): RiskTensorPayload {
  return {
    report_date: reportDate,
    portfolio_dv01: "12.34",
    krd_1y: "1",
    krd_3y: "2",
    krd_5y: "3",
    krd_7y: "2.5",
    krd_10y: "1.5",
    krd_30y: "0.5",
    cs01: "8.88",
    portfolio_convexity: "0.42",
    portfolio_modified_duration: "4.2",
    issuer_concentration_hhi: "0.18",
    issuer_top5_weight: "0.35",
    liquidity_gap_30d: "100.1",
    liquidity_gap_90d: "200.2",
    liquidity_gap_30d_ratio: "0.05",
    total_market_value: "999.99",
    bond_count: 12,
    quality_flag: "warning",
    warnings: ["Issuer concentration above desk threshold"],
  };
}

function renderRiskTensorRoute(
  initialEntry: string,
  client: ReturnType<typeof createApiClient>,
) {
  const router = createWorkbenchMemoryRouter([initialEntry]);
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });

  return render(
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} future={routerFuture} />
      </QueryClientProvider>
    </ApiClientProvider>,
  );
}

describe("RiskTensorPage", () => {
  it("uses latest available report date when querystring is absent", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates"),
      result: { report_dates: ["2026-02-28", "2026-01-31"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    expect(await screen.findByRole("heading", { name: "风险张量" })).toBeInTheDocument();
    const kpi = await screen.findByTestId("risk-tensor-kpi-grid");
    expect(kpi).toHaveTextContent("12.34");
    expect(kpi).toHaveTextContent("8.88");
    expect(screen.getByText("集中度")).toBeInTheDocument();
    expect(screen.getByText("流动性缺口（市值）")).toBeInTheDocument();
    expect(screen.getByText("Issuer concentration above desk threshold")).toBeInTheDocument();
    expect(screen.getByTestId("risk-tensor-tenor-drill")).toHaveTextContent("5Y");
    expect(screen.getByTestId("risk-tensor-tenor-drill")).toHaveTextContent("3");
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("tr_tensor_2026-02-28");
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("sv_tensor_test");

    await waitFor(() => {
      expect(getRiskTensorDates).toHaveBeenCalled();
      expect(getRiskTensor).toHaveBeenCalledWith("2026-02-28");
    });
  });

  it("renders governed Numeric tensor values using backend display and raw ratio", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_numeric_dates"),
      result: { report_dates: ["2026-02-28"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_numeric_${reportDate}`),
      result: {
        ...tensorResult(reportDate),
        portfolio_dv01: {
          raw: 1234.56,
          unit: "dv01" as const,
          display: "1,235 governed",
          precision: 0,
          sign_aware: false,
        },
        issuer_top5_weight: {
          raw: 0.42,
          unit: "ratio" as const,
          display: "0.42",
          precision: 2,
          sign_aware: false,
        },
      },
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const kpi = await screen.findByTestId("risk-tensor-kpi-grid");
    expect(kpi).toHaveTextContent("1,235 governed");
    expect(screen.getByText("42.0%")).toBeInTheDocument();
  });

  it("surfaces backend-blocked stale dates without using them as the default", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_with_blocked"),
      result: {
        report_dates: ["2026-02-28"],
        blocked_report_dates: [
          {
            report_date: "2026-02-26",
            reason: "older stale tensor",
          },
          {
            report_date: "2026-02-27",
            reason: "risk tensor source lineage is stale",
          },
        ],
      },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    const blockedDates = await screen.findByTestId("risk-tensor-blocked-dates");
    expect(blockedDates).toHaveTextContent("2026-02-27");
    expect(blockedDates).toHaveTextContent("risk tensor source lineage is stale");
    expect(blockedDates).not.toHaveTextContent("older stale tensor");

    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledWith("2026-02-28");
      expect(getRiskTensor).not.toHaveBeenCalledWith("2026-02-27");
    });
  });

  it("honors report_date in the URL querystring", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates"),
      result: { report_dates: ["2026-02-28", "2026-01-31"] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor?report_date=2026-03-15", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    expect(await screen.findByRole("heading", { name: "风险张量" })).toBeInTheDocument();
    await waitFor(() => {
      expect(getRiskTensor).toHaveBeenCalledWith("2026-03-15");
    });
  });

  it("does not fall back to a hardcoded report date when backend dates are empty", async () => {
    const base = createApiClient({ mode: "mock" });
    const getRiskTensorDates = vi.fn(async () => ({
      result_meta: buildMeta("risk.tensor.dates", "tr_tensor_dates_empty"),
      result: { report_dates: [] },
    }));
    const getRiskTensor = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("risk.tensor", `tr_tensor_${reportDate}`),
      result: tensorResult(reportDate),
    }));

    renderRiskTensorRoute("/risk-tensor", {
      ...base,
      getRiskTensorDates,
      getRiskTensor,
    });

    expect(await screen.findByText("后端未返回可用风险报告日。")).toBeInTheDocument();
    expect(getRiskTensor).not.toHaveBeenCalled();
    expect(screen.getByTestId("risk-tensor-result-meta-panel")).toHaveTextContent("tr_tensor_dates_empty");
  });
});
