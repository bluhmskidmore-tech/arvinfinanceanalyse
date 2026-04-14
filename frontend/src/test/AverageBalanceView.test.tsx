import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import AverageBalanceView from "../features/average-balance/components/AverageBalanceView";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="average-balance-echarts-stub" />,
}));

describe("AverageBalanceView", () => {
  it("renders the ADB shell, tabs, and daily KPI cards", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      async getAdbComparison() {
        return {
          report_date: "2025-12-31",
          start_date: "2025-12-02",
          end_date: "2025-12-31",
          num_days: 30,
          simulated: false,
          total_spot_assets: 250000000,
          total_avg_assets: 200000000,
          total_spot_liabilities: 100000000,
          total_avg_liabilities: 90000000,
          asset_yield: 2.55,
          liability_cost: 1.75,
          net_interest_margin: 0.8,
          assets_breakdown: [
            {
              category: "国债",
              spot_balance: 150000000,
              avg_balance: 120000000,
              proportion: 60,
              weighted_rate: 2.4,
            },
          ],
          liabilities_breakdown: [
            {
              category: "同业存单",
              spot_balance: 100000000,
              avg_balance: 90000000,
              proportion: 100,
              weighted_rate: 1.75,
            },
          ],
          assets: [],
          liabilities: [],
        };
      },
    };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <AverageBalanceView />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "日均资产负债（ADB）" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "日均分析" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "月度统计" })).toBeInTheDocument();
    expect(await screen.findByText("资产偏离度")).toBeInTheDocument();
    expect(screen.getByText("负债偏离度")).toBeInTheDocument();
    expect(screen.getByText("资产收益率")).toBeInTheDocument();
    expect(screen.getByText("负债付息率")).toBeInTheDocument();
    expect(screen.getAllByText("时点(亿元)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("加权利率").length).toBeGreaterThan(0);
  });
});
