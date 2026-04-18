import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import CashflowProjectionPage from "../features/cashflow-projection/pages/CashflowProjectionPage";
import { formatRawAsNumeric } from "../utils/format";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="cashflow-echarts-stub" />,
}));

describe("CashflowProjectionPage", () => {
  it("mounts KPI cards when projection loads", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("cashflow-projection-page")).toBeInTheDocument();
    expect(screen.getByTestId("cashflow-page-title")).toHaveTextContent("现金流预测");
    expect(await screen.findByTestId("cashflow-kpi-duration-gap")).toBeInTheDocument();
    expect(await screen.findByTestId("cashflow-kpi-asset-dur")).toBeInTheDocument();
    expect(await screen.findByTestId("cashflow-kpi-liability-dur")).toBeInTheDocument();
    expect(await screen.findByTestId("cashflow-kpi-dv01")).toBeInTheDocument();
    expect(await screen.findByTestId("cashflow-kpi-equity-dur")).toBeInTheDocument();
    expect(await screen.findByTestId("cashflow-kpi-reinvest")).toBeInTheDocument();
    expect(screen.getByText("现金流概览")).toBeInTheDocument();
    expect(screen.getByText("月度投影")).toBeInTheDocument();
    expect(screen.getByText("到期资产与提示")).toBeInTheDocument();
  });

  it("renders chart region when monthly buckets are present", async () => {
    const client = createApiClient({ mode: "mock" });
    const orig = client.getBalanceAnalysisDates.bind(client);
    client.getBalanceAnalysisDates = async () => {
      const r = await orig();
      return {
        ...r,
        result: { ...r.result, report_dates: ["2026-04-01"] },
      };
    };
    client.getCashflowProjection = async (reportDate: string) => {
      const r = await createApiClient({ mode: "mock" }).getCashflowProjection(reportDate);
      return {
        ...r,
        result: {
          ...r.result,
          monthly_buckets: [
            {
              year_month: "2026-04",
              asset_inflow: formatRawAsNumeric({ raw: 100, unit: "yuan", sign_aware: false }),
              liability_outflow: formatRawAsNumeric({ raw: 40, unit: "yuan", sign_aware: false }),
              net_cashflow: formatRawAsNumeric({ raw: 60, unit: "yuan", sign_aware: true }),
              cumulative_net: formatRawAsNumeric({ raw: 60, unit: "yuan", sign_aware: true }),
            },
          ],
        },
      };
    };

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("cashflow-echarts-stub")).toBeInTheDocument();
  });

  it("requests projection for the first available balance-analysis report date", async () => {
    const client = createApiClient({ mode: "mock" });
    const origDates = client.getBalanceAnalysisDates.bind(client);
    client.getBalanceAnalysisDates = async () => {
      const r = await origDates();
      return {
        ...r,
        result: { ...r.result, report_dates: ["2026-04-01", "2026-03-01"] },
      };
    };
    const spy = vi.spyOn(client, "getCashflowProjection");

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CashflowProjectionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(spy).toHaveBeenCalledWith("2026-04-01"));
  });
});
