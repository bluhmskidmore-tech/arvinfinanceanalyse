import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import AverageBalanceView from "../features/average-balance/components/AverageBalanceView";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="average-balance-echarts-stub" />,
}));

function renderView(clientOverrides?: Record<string, unknown>) {
  const baseClient = createApiClient({ mode: "mock" });
  const client = {
    ...baseClient,
    async getBalanceAnalysisDates() {
      return {
        result_meta: {
          trace_id: "tr_adb_dates",
          basis: "formal" as const,
          result_kind: "analysis.adb.dates",
          formal_use_allowed: true,
          source_version: "sv_adb",
          vendor_version: "vv_none",
          rule_version: "rv_adb",
          cache_version: "cv_adb",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-14T08:00:00+08:00",
        },
        result: {
          report_dates: ["2026-04-14", "2026-03-31"],
        },
      };
    },
    async getAdbComparison() {
      return {
        report_date: "2026-04-14",
        start_date: "2026-01-01",
        end_date: "2026-04-14",
        num_days: 104,
        simulated: true,
        total_spot_assets: 550000000,
        total_avg_assets: 500000000,
        total_spot_liabilities: 230000000,
        total_avg_liabilities: 200000000,
        asset_yield: 2.55,
        liability_cost: 1.75,
        net_interest_margin: 0.8,
        assets_breakdown: [
          {
            category: "债券投资",
            spot_balance: 300000000,
            avg_balance: 260000000,
            proportion: 52,
            weighted_rate: 2.8,
          },
          {
            category: "同业资产",
            spot_balance: 250000000,
            avg_balance: 240000000,
            proportion: 48,
            weighted_rate: 2.29,
          },
        ],
        liabilities_breakdown: [
          {
            category: "同业负债",
            spot_balance: 140000000,
            avg_balance: 110000000,
            proportion: 55,
            weighted_rate: 1.86,
          },
          {
            category: "发行债券",
            spot_balance: 90000000,
            avg_balance: 90000000,
            proportion: 45,
            weighted_rate: 1.61,
          },
        ],
      };
    },
    async getAdbMonthly() {
      return {
        year: 2026,
        ytd_avg_assets: 480000000,
        ytd_avg_liabilities: 190000000,
        ytd_asset_yield: 2.41,
        ytd_liability_cost: 1.62,
        ytd_nim: 0.79,
        months: [
          {
            month: "2026-03",
            month_label: "2026年3月",
            num_days: 31,
            avg_assets: 500000000,
            avg_liabilities: 210000000,
            asset_yield: 2.45,
            liability_cost: 1.66,
            net_interest_margin: 0.79,
            mom_change_assets: 18.2,
            mom_change_pct_assets: 3.78,
            mom_change_liabilities: -7.5,
            mom_change_pct_liabilities: -3.45,
            breakdown_assets: [
              {
                category: "债券投资",
                avg_balance: 280000000,
                proportion: 56,
                weighted_rate: 2.61,
              },
              {
                category: "同业资产",
                avg_balance: 220000000,
                proportion: 44,
                weighted_rate: 2.25,
              },
            ],
            breakdown_liabilities: [
              {
                category: "同业负债",
                avg_balance: 130000000,
                proportion: 61.9,
                weighted_rate: 1.74,
              },
              {
                category: "发行债券",
                avg_balance: 80000000,
                proportion: 38.1,
                weighted_rate: 1.53,
              },
            ],
          },
          {
            month: "2026-02",
            month_label: "2026年2月",
            num_days: 28,
            avg_assets: 481800000,
            avg_liabilities: 217500000,
            asset_yield: 2.38,
            liability_cost: 1.71,
            net_interest_margin: 0.67,
            mom_change_assets: null,
            mom_change_pct_assets: null,
            mom_change_liabilities: null,
            mom_change_pct_liabilities: null,
            breakdown_assets: [
              {
                category: "债券投资",
                avg_balance: 270000000,
                proportion: 56,
                weighted_rate: 2.55,
              },
            ],
            breakdown_liabilities: [
              {
                category: "同业负债",
                avg_balance: 217500000,
                proportion: 100,
                weighted_rate: 1.71,
              },
            ],
          },
        ],
      };
    },
    ...clientOverrides,
  };

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <MemoryRouter>
          <AverageBalanceView />
        </MemoryRouter>
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("AverageBalanceView", () => {
  it("renders the daily analysis tab with preset ranges, KPI cards, warning copy, and breakdown tables", async () => {
    renderView();

    expect(await screen.findByRole("heading", { name: "日均管理" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "日均分析" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "月度统计" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "7D" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "30D" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "YTD" })).toBeInTheDocument();
    expect(screen.getByLabelText("adb-start-date")).toBeInTheDocument();
    expect(screen.getByLabelText("adb-end-date")).toBeInTheDocument();
    expect(await screen.findByText("有效天数：104 天")).toBeInTheDocument();
    expect(
      screen.getByText("当前区间仅 1 天时，日均为稳态模拟，便于演示图表逻辑"),
    ).toBeInTheDocument();

    expect(screen.getByText("Spot 总资产")).toBeInTheDocument();
    expect(screen.getByText("ADB 总资产")).toBeInTheDocument();
    expect(screen.getByText("偏离度（资产）")).toBeInTheDocument();
    expect(screen.getByText("Spot 总负债")).toBeInTheDocument();
    expect(screen.getByText("ADB 总负债")).toBeInTheDocument();
    expect(screen.getByText("偏离度（负债）")).toBeInTheDocument();
    expect(screen.getByText("资产收益率（年化）")).toBeInTheDocument();
    expect(screen.getByText("负债付息率（年化）")).toBeInTheDocument();
    expect(screen.getByText("NIM（年化）")).toBeInTheDocument();

    expect(screen.getByText("Spot vs ADB 偏离对比")).toBeInTheDocument();
    expect(screen.getByText("资产端分类明细")).toBeInTheDocument();
    expect(screen.getByText("负债端分类明细")).toBeInTheDocument();
    expect(screen.getAllByText("Spot(亿元)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("日均(亿元)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("收益率(%)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("付息率(%)").length).toBeGreaterThan(0);
    expect(screen.getAllByTestId("average-balance-echarts-stub")).toHaveLength(1);
  });

  it("renders the monthly statistics tab with YTD summary, expandable table, and deep analysis panels", async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(await screen.findByRole("tab", { name: "月度统计" }));

    expect(await screen.findByText("YTD 日均资产")).toBeInTheDocument();
    expect(screen.getByText("YTD 日均负债")).toBeInTheDocument();
    expect(screen.getByText("YTD 资产收益率")).toBeInTheDocument();
    expect(screen.getByText("YTD 负债付息率")).toBeInTheDocument();
    expect(screen.getByText("YTD NIM")).toBeInTheDocument();

    expect(screen.getByText("月度汇总表")).toBeInTheDocument();
    expect(screen.getAllByText("2026年3月").length).toBeGreaterThan(0);
    expect(screen.getByText("按月度日均分析 - 深度分析")).toBeInTheDocument();
    expect(screen.getByText("资产端分类明细")).toBeInTheDocument();
    expect(screen.getByText("负债端分类明细")).toBeInTheDocument();
    expect(screen.getByText("月份")).toBeInTheDocument();
    expect(screen.getByText("天数")).toBeInTheDocument();
    expect(screen.getAllByTestId("average-balance-echarts-stub")).toHaveLength(2);
  });

  it("shows an explicit error state when report dates fail and no daily query can start", async () => {
    renderView({
      async getBalanceAnalysisDates() {
        throw new Error("dates unavailable");
      },
    });

    expect(await screen.findByText("可用报告日加载失败，请先恢复报告日列表后再查看日均分析。")).toBeInTheDocument();
    expect(screen.queryByText("Spot 总资产")).not.toBeInTheDocument();
  });
});
