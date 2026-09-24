import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import AverageBalanceView from "../features/average-balance/components/AverageBalanceView";
import { shiftIsoDateByYears } from "../features/average-balance/components/averageBalanceDateUtils";

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
    async getAdbComparison(startDate: string, endDate: string, _opts?: { topN?: number }) {
      if (startDate.startsWith("2025")) {
        return {
          report_date: "2025-04-14",
          start_date: startDate,
          end_date: endDate,
          calendar_days_inclusive: 104,
          adb_denominator_basis: "formal_calendar" as const,
          num_days: 104,
          coverage_days: 104,
          simulated: true,
          total_spot_assets: 520000000,
          total_avg_assets: 450000000,
          total_spot_liabilities: 220000000,
          total_avg_liabilities: 180000000,
          total_avg_interbank_assets: 200000000,
          total_avg_interbank_liabilities: 88000000,
          asset_yield: 2.4,
          liability_cost: 1.68,
          net_interest_margin: 0.72,
          assets_breakdown: [
            {
              category: "债券投资",
              spot_balance: 280000000,
              avg_balance: 250000000,
              proportion: 50,
              weighted_rate: 2.7,
            },
            {
              category: "同业资产",
              spot_balance: 240000000,
              avg_balance: 230000000,
              proportion: 50,
              weighted_rate: 2.2,
            },
          ],
          liabilities_breakdown: [
            {
              category: "同业负债",
              spot_balance: 130000000,
              avg_balance: 100000000,
              proportion: 55,
              weighted_rate: 1.9,
            },
            {
              category: "发行债券",
              spot_balance: 90000000,
              avg_balance: 88000000,
              proportion: 45,
              weighted_rate: 1.55,
            },
          ],
        };
      }
      return {
        report_date: "2026-04-14",
        start_date: "2026-01-01",
        end_date: "2026-04-14",
        calendar_days_inclusive: 104,
        adb_denominator_basis: "formal_calendar" as const,
        num_days: 104,
        coverage_days: 104,
        simulated: true,
        total_spot_assets: 550000000,
        total_avg_assets: 500000000,
        total_spot_liabilities: 230000000,
        total_avg_liabilities: 200000000,
        total_avg_interbank_assets: 240000000,
        total_avg_interbank_liabilities: 110000000,
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
        accounting_basis_daily_avg: {
          report_date: "2026-04-14",
          currency_basis: "CNY",
          daily_avg_total: 500000000,
          rows: [
            {
              basis_bucket: "AC",
              daily_avg_balance: 200000000,
              daily_avg_pct: 40,
              source_account_patterns: [],
            },
            {
              basis_bucket: "FVOCI",
              daily_avg_balance: 200000000,
              daily_avg_pct: 40,
              source_account_patterns: [],
            },
            {
              basis_bucket: "FVTPL",
              daily_avg_balance: 100000000,
              daily_avg_pct: 20,
              source_account_patterns: [],
            },
          ],
          accounting_controls: ["142%", "143%", "1440101%", "141%"],
          excluded_controls: [],
        },
        accounting_basis_daily_avg_trend: [
          {
            report_date: "2026-03-31",
            report_month: "2026-03",
            currency_basis: "CNY",
            daily_avg_total: 480000000,
            rows: [
              { basis_bucket: "AC", daily_avg_balance: 190000000, daily_avg_pct: 39.6, source_account_patterns: [] },
              { basis_bucket: "FVOCI", daily_avg_balance: 190000000, daily_avg_pct: 39.6, source_account_patterns: [] },
              { basis_bucket: "FVTPL", daily_avg_balance: 100000000, daily_avg_pct: 20.8, source_account_patterns: [] },
            ],
            accounting_controls: [],
            excluded_controls: [],
          },
          {
            report_date: "2026-04-14",
            report_month: "2026-04",
            currency_basis: "CNY",
            daily_avg_total: 500000000,
            rows: [
              { basis_bucket: "AC", daily_avg_balance: 200000000, daily_avg_pct: 40, source_account_patterns: [] },
              { basis_bucket: "FVOCI", daily_avg_balance: 200000000, daily_avg_pct: 40, source_account_patterns: [] },
              { basis_bucket: "FVTPL", daily_avg_balance: 100000000, daily_avg_pct: 20, source_account_patterns: [] },
            ],
            accounting_controls: [],
            excluded_controls: [],
          },
        ],
      };
    },
    async getAdbCoverage() {
      return {
        start_date: "2026-01-01",
        end_date: "2026-04-14",
        calendar_days: 104,
        snapshot_tables: {},
        formal_tables: {},
        snapshot_date_count: 0,
        formal_date_count: 0,
        missing_dates: [],
        missing_count: 0,
        coverage_pct: 0,
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
            mom_change_assets: 18_000_000,
            mom_change_pct_assets: 3.78,
            mom_change_liabilities: -7_500_000,
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
  it("defers trend and prior-year requests until the current comparison is ready", async () => {
    let resolveCurrentComparison: (value: unknown) => void = () => {};
    const currentComparisonPromise = new Promise((resolve) => {
      resolveCurrentComparison = resolve;
    });
    const comparisonPayload = {
      report_date: "2026-04-14",
      start_date: "2026-01-01",
      end_date: "2026-04-14",
      calendar_days_inclusive: 104,
      adb_denominator_basis: "formal_calendar" as const,
      num_days: 104,
      coverage_days: 104,
      simulated: false,
      total_spot_assets: 550000000,
      total_avg_assets: 500000000,
      total_spot_liabilities: 230000000,
      total_avg_liabilities: 200000000,
      total_avg_interbank_assets: 240000000,
      total_avg_interbank_liabilities: 110000000,
      asset_yield: 2.55,
      liability_cost: 1.75,
      net_interest_margin: 0.8,
      assets_breakdown: [],
      liabilities_breakdown: [],
    };
    const getAdbComparison = vi.fn((startDate: string, endDate: string) => {
      if (startDate.startsWith("2025")) {
        return Promise.resolve({
          ...comparisonPayload,
          report_date: "2025-04-14",
          start_date: startDate,
          end_date: endDate,
        });
      }
      return currentComparisonPromise;
    });
    const getAdb = vi.fn(async () => ({
      summary: {
        total_avg_assets: 500000000,
        total_avg_liabilities: 200000000,
        end_spot_assets: 550000000,
        end_spot_liabilities: 230000000,
      },
      trend: [],
      breakdown: [],
    }));

    renderView({ getAdbComparison, getAdb });

    await waitFor(() => expect(getAdbComparison).toHaveBeenCalledTimes(1));
    expect(getAdbComparison.mock.calls[0][0]).toBe("2026-01-01");
    expect(getAdb).not.toHaveBeenCalled();

    resolveCurrentComparison(comparisonPayload);

    await waitFor(() => expect(getAdb).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getAdbComparison).toHaveBeenCalledTimes(2));
    expect(getAdbComparison.mock.calls[1][0]).toBe("2025-01-01");
  });

  it("renders the daily analysis tab with preset ranges, KPI cards, warning copy, and breakdown tables", async () => {
    renderView();

    expect(await screen.findByRole("heading", { name: "日均分析" })).toBeInTheDocument();
    expect(screen.getByTestId("average-balance-page-title")).toHaveTextContent("日均分析");
    expect(screen.getByTestId("average-balance-page-subtitle")).toHaveTextContent(
      "期末是否偏离日均",
    );
    // 页头 brief 行不再与副题逐字重复，改为差异化口径边界句（testid 保留）。
    const analysisBrief = screen.getByTestId("average-balance-analysis-brief");
    expect(analysisBrief).toHaveTextContent("口径边界");
    expect(analysisBrief).toHaveTextContent("债券投资（ZQTZ）与同业（TYW）读模型");
    expect(analysisBrief).not.toHaveTextContent("日均分析回答什么");
    expect(screen.getByRole("heading", { name: "区间日均分析" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "日均分析" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "月度统计" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "7日" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "30日" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "年初至今" })).toBeInTheDocument();
    expect(screen.getByLabelText("adb-start-date")).toBeInTheDocument();
    expect(screen.getByLabelText("adb-end-date")).toBeInTheDocument();
    expect(await screen.findByText("区间天数：104 天")).toBeInTheDocument();
    expect(screen.getByTestId("adb-denominator-summary")).toHaveTextContent("分母=");
    expect(screen.getByTestId("adb-accounting-basis-section")).toHaveTextContent("FVOCI");
    // SQL LIKE 前缀模式（"142%" 等）在显示层读作科目前缀，尾部 % 通配符不再直出。
    expect(screen.getByTestId("adb-accounting-basis-section")).toHaveTextContent(
      "控制项：科目前缀 142 / 143 / 1440101 / 141",
    );
    expect(screen.getByTestId("adb-accounting-basis-section")).not.toHaveTextContent("142%");
    expect(screen.getByTestId("adb-accounting-basis-trend-chart")).toBeInTheDocument();
    expect(
      screen.getByText("当前区间仅 1 天时，日均为稳态模拟，便于演示图表逻辑"),
    ).toBeInTheDocument();

    expect(screen.getByText("期末时点总资产")).toBeInTheDocument();
    expect(screen.getByText("日均总资产")).toBeInTheDocument();
    expect(screen.getByText("偏离度（资产）")).toBeInTheDocument();
    expect(screen.getByText("期末时点总负债")).toBeInTheDocument();
    expect(screen.getByText("日均总负债")).toBeInTheDocument();
    expect(screen.getByText("偏离度（负债）")).toBeInTheDocument();
    expect(screen.getByText("同业日均资产")).toBeInTheDocument();
    expect(screen.getByText("同业日均负债")).toBeInTheDocument();
    expect(screen.getAllByText("TYW 正式余额（区间日均）").length).toBe(2);
    expect(screen.getByText("资产加权平均YTM")).toBeInTheDocument();
    expect(screen.getByText("负债加权平均票息")).toBeInTheDocument();
    expect(screen.getByText("利差（YTM−票息）")).toBeInTheDocument();
    const yoyCard = await screen.findByTestId("adb-daily-yoy-summary");
    expect(yoyCard).toHaveTextContent("去年同期对齐");
    expect(yoyCard).toHaveTextContent("不可加总");
    expect(yoyCard).toHaveTextContent("债券与同业");
    expect(yoyCard).toHaveTextContent("2025-01-01");
    expect(yoyCard).toHaveTextContent("2025-04-14");
    expect(yoyCard).toHaveTextContent("区间日均总资产");
    expect(yoyCard).toHaveTextContent("+11.11%");
    expect(screen.getByTestId("adb-daily-yoy-category")).toHaveTextContent("资产端分类");
    expect(screen.getByTestId("adb-daily-yoy-category")).toHaveTextContent("负债端分类");
    expect(screen.getByTestId("adb-top-n-select")).toBeInTheDocument();
    expect(screen.getAllByTestId("average-balance-echarts-stub")).toHaveLength(3);

    expect(screen.getByText(/期末时点与日均偏离对比 · 资产/)).toBeInTheDocument();
    expect(screen.getByText(/期末时点与日均偏离对比 · 负债/)).toBeInTheDocument();
    expect(screen.getByText("资产端分类明细")).toBeInTheDocument();
    expect(screen.getByText("负债端分类明细")).toBeInTheDocument();
    expect(screen.getAllByText("期末时点（亿元）").length).toBeGreaterThan(0);
    expect(screen.getAllByText("日均(亿元)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("收益率(%)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("付息率(%)").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "打开正式资产负债分析" })).toHaveAttribute(
      "href",
      "/balance-analysis?report_date=2026-04-14&position_scope=all&currency_basis=CNY",
    );
  });

  it("marks unmatched prior-year categories as missing instead of real zero", async () => {
    renderView({
      async getAdbComparison(startDate: string, endDate: string, _opts?: { topN?: number }) {
        const current = await createApiClient({ mode: "mock" }).getAdbComparison(startDate, endDate, _opts);
        if (startDate.startsWith("2025")) {
          return {
            ...current,
            report_date: "2025-04-14",
            start_date: startDate,
            end_date: endDate,
            assets_breakdown: [],
            liabilities_breakdown: [],
          };
        }
        return {
          ...current,
          assets_breakdown: [
            {
              category: "new-asset-book",
              spot_balance: 120_000_000,
              avg_balance: 100_000_000,
              proportion: 100,
              weighted_rate: 2.1,
            },
          ],
          liabilities_breakdown: [],
        };
      },
    });

    const yoyCategory = await screen.findByTestId("adb-daily-yoy-category");
    await waitFor(() => expect(yoyCategory).toHaveTextContent("new-asset-book"));
    // 缺去年同期在行内是安静的 EM_DASH，不再逐行重复原因文案。
    expect(yoyCategory).toHaveTextContent("—");
    expect(yoyCategory).not.toHaveTextContent("缺去年同期");
    expect(yoyCategory).not.toHaveTextContent("Infinity");
    // 总规模行仍有去年值（非整列缺失）：区块头不出现整列缺失说明。
    expect(screen.queryByTestId("adb-yoy-prior-missing-notice")).not.toBeInTheDocument();
  });

  it("shows a single block-head notice when the prior-year read model has no coverage at all", async () => {
    renderView({
      async getAdbComparison(startDate: string, endDate: string, _opts?: { topN?: number }) {
        const current = await createApiClient({ mode: "mock" }).getAdbComparison(startDate, endDate, _opts);
        if (startDate.startsWith("2025")) {
          return {
            ...current,
            report_date: "2025-04-14",
            start_date: startDate,
            end_date: endDate,
            total_spot_assets: null,
            total_avg_assets: null,
            total_spot_liabilities: null,
            total_avg_liabilities: null,
            avg_unavailable_reason: "no_data" as const,
            spot_unavailable_reason: "no_data" as const,
            assets_breakdown: [],
            liabilities_breakdown: [],
          };
        }
        return {
          ...current,
          assets_breakdown: [
            {
              category: "债券投资",
              spot_balance: 300_000_000,
              avg_balance: 260_000_000,
              proportion: 52,
              weighted_rate: 2.8,
            },
          ],
          liabilities_breakdown: [],
        };
      },
    });

    const notice = await screen.findByTestId("adb-yoy-prior-missing-notice");
    expect(notice).toHaveTextContent("2025 年同期读模型未覆盖");
    expect(notice).toHaveTextContent("整列缺失");
    // 行内保持安静 EM_DASH，原因只在区块头出现一次。
    expect(screen.getByTestId("adb-daily-yoy-category")).not.toHaveTextContent("缺去年同期");
  });

  it("flags negative deviation beyond the absolute threshold with the same warning chain", async () => {
    renderView({
      async getAdbComparison(startDate: string, endDate: string, _opts?: { topN?: number }) {
        const current = await createApiClient({ mode: "mock" }).getAdbComparison(startDate, endDate, _opts);
        if (startDate.startsWith("2025")) {
          return { ...current, report_date: "2025-04-14", start_date: startDate, end_date: endDate };
        }
        // 期末显著低于日均（-9.45%）：绝对值判据下与正偏离同样预警。
        // 负债侧压回 +2%（阈值内），确保全局警示只能由资产负偏离触发。
        return {
          ...current,
          total_spot_assets: 452_750_000,
          total_avg_assets: 500_000_000,
          total_spot_liabilities: 204_000_000,
          total_avg_liabilities: 200_000_000,
        };
      },
    });

    const deviationCard = (await screen.findByText("偏离度（资产）")).closest(".adb-kpi");
    expect(deviationCard).toHaveTextContent("-9.45%");
    expect(deviationCard?.querySelector(".adb-kpi-warn-icon")).toBeInTheDocument();
    expect(await screen.findByText(/偏离度绝对值 > 5%/)).toBeInTheDocument();
  });

  it("preserves missing comparison average balance as unavailable instead of zero", async () => {
    renderView({
      async getAdbComparison(startDate: string, endDate: string, _opts?: { topN?: number }) {
        const current = await createApiClient({ mode: "mock" }).getAdbComparison(startDate, endDate, _opts);
        if (startDate.startsWith("2025")) {
          return {
            ...current,
            report_date: "2025-04-14",
            start_date: startDate,
            end_date: endDate,
            assets_breakdown: [
              {
                category: "missing-adb",
                spot_balance: 100_000_000,
                avg_balance: 50_000_000,
                proportion: 50,
                weighted_rate: null,
              },
            ],
            liabilities_breakdown: [],
          };
        }
        return {
          ...current,
          assets_breakdown: [
            {
              category: "missing-adb",
              spot_balance: 100_000_000,
              avg_balance: null,
              proportion: 50,
              weighted_rate: null,
            },
            {
              category: "true-zero-adb",
              spot_balance: 0,
              avg_balance: 0,
              proportion: 0,
              weighted_rate: null,
            },
          ],
          liabilities_breakdown: [],
        };
      },
    });

    await waitFor(() => expect(screen.getAllByText("missing-adb").length).toBeGreaterThan(0));
    const missingDetailRow = screen
      .getAllByText("missing-adb")
      .map((node) => node.closest("tr"))
      .find((row): row is HTMLTableRowElement => Boolean(row?.textContent?.includes("50.00")));
    expect(missingDetailRow?.querySelectorAll("td")[2]).toHaveTextContent("—");
    expect(screen.getByTestId("adb-daily-yoy-category")).toHaveTextContent("missing-adb");
    expect(screen.getByTestId("adb-daily-yoy-category")).toHaveTextContent("—");
    expect(screen.getByTestId("adb-daily-yoy-category")).not.toHaveTextContent("-0.50");
    expect(screen.getByText("true-zero-adb").closest("tr")).toHaveTextContent("0.00");
  });

  it("renders deviation KPIs as unavailable and skips the dressing warning when the average denominator is zero", async () => {
    renderView({
      async getAdbComparison(startDate: string, endDate: string, _opts?: { topN?: number }) {
        const current = await createApiClient({ mode: "mock" }).getAdbComparison(startDate, endDate, _opts);
        if (startDate.startsWith("2025")) {
          return { ...current, report_date: "2025-04-14", start_date: startDate, end_date: endDate };
        }
        // 分母（日均总额）为 0：偏离度无法计算，不得显示 "+0.00%"、也不得触发“窗口粉饰”预警。
        return { ...current, total_avg_assets: 0, total_avg_liabilities: 0 };
      },
    });

    const assetDeviationLabel = await screen.findByText("偏离度（资产）");
    expect(assetDeviationLabel.closest(".adb-kpi")).toHaveTextContent("—");
    expect(assetDeviationLabel.closest(".adb-kpi")).not.toHaveTextContent("%");
    const liabilityDeviationLabel = screen.getByText("偏离度（负债）");
    expect(liabilityDeviationLabel.closest(".adb-kpi")).toHaveTextContent("—");
    expect(screen.queryByText(/窗口粉饰/)).not.toBeInTheDocument();
  });

  it("keeps the deviation KPI null-safe and shows an explicit unavailable hint when the interval average total is missing", async () => {
    renderView({
      async getAdbComparison(startDate: string, endDate: string, _opts?: { topN?: number }) {
        if (startDate.startsWith("2025")) {
          return {
            report_date: "2025-04-14",
            start_date: startDate,
            end_date: endDate,
            calendar_days_inclusive: 1,
            adb_denominator_basis: "formal_calendar" as const,
            num_days: 1,
            coverage_days: 1,
            simulated: false,
            total_spot_assets: 500000000,
            total_avg_assets: 480000000,
            total_spot_liabilities: 210000000,
            total_avg_liabilities: 205000000,
            total_avg_interbank_assets: 0,
            total_avg_interbank_liabilities: 0,
            asset_yield: 2.4,
            liability_cost: 1.6,
            net_interest_margin: 0.8,
            assets_breakdown: [],
            liabilities_breakdown: [],
          };
        }
        return {
          report_date: "2026-04-14",
          start_date: startDate,
          end_date: endDate,
          calendar_days_inclusive: 1,
          adb_denominator_basis: "formal_calendar" as const,
          num_days: 1,
          coverage_days: 1,
          simulated: false,
          // 单日观测窗口不足：区间日均按后端约定为 null，不能被伪零覆盖。
          total_spot_assets: 550000000,
          total_avg_assets: null,
          avg_unavailable_reason: "insufficient_window" as const,
          total_spot_liabilities: 230000000,
          total_avg_liabilities: 225000000,
          total_avg_interbank_assets: 0,
          total_avg_interbank_liabilities: 0,
          asset_yield: 2.5,
          liability_cost: 1.7,
          net_interest_margin: 0.8,
          assets_breakdown: [],
          liabilities_breakdown: [],
        };
      },
    });

    const avgAssetsCard = (await screen.findByText("日均总资产")).closest(".adb-kpi");
    expect(avgAssetsCard).toHaveTextContent("—");
    expect(avgAssetsCard).toHaveTextContent("观测窗口不足，日均不可用");

    const deviationCard = screen.getByText("偏离度（资产）").closest(".adb-kpi");
    expect(deviationCard).toHaveTextContent("—");
    expect(deviationCard?.querySelector(".adb-kpi-warn-icon")).not.toBeInTheDocument();

    // 负债侧偏离 ~2.2%（低于 5% 阈值）且资产侧因缺数不参与比较：不应出现全局偏离警示。
    expect(screen.queryByText(/偏离度 > 5%/)).not.toBeInTheDocument();
  });

  it("renders missing accounting-basis daily average balances as unavailable instead of zero", async () => {
    renderView({
      async getAdbComparison(startDate: string, endDate: string, _opts?: { topN?: number }) {
        const current = await createApiClient({ mode: "mock" }).getAdbComparison(startDate, endDate, _opts);
        if (startDate.startsWith("2025")) {
          return {
            ...current,
            report_date: "2025-04-14",
            start_date: startDate,
            end_date: endDate,
          };
        }
        return {
          ...current,
          accounting_basis_daily_avg: {
            report_date: "2026-04-14",
            currency_basis: "CNY",
            daily_avg_total: null,
            rows: [
              {
                basis_bucket: "missing-basis-adb",
                daily_avg_balance: null,
                daily_avg_pct: null,
                source_account_patterns: [],
              },
              {
                basis_bucket: "true-zero-basis-adb",
                daily_avg_balance: 0,
                daily_avg_pct: 0,
                source_account_patterns: [],
              },
            ],
            accounting_controls: [],
            excluded_controls: [],
          },
          accounting_basis_daily_avg_trend: [
            {
              report_date: "2026-03-31",
              report_month: "2026-03",
              currency_basis: "CNY",
              daily_avg_total: null,
              rows: [
                {
                  basis_bucket: "missing-basis-adb",
                  daily_avg_balance: null,
                  daily_avg_pct: null,
                  source_account_patterns: [],
                },
              ],
              accounting_controls: [],
              excluded_controls: [],
            },
            {
              report_date: "2026-04-14",
              report_month: "2026-04",
              currency_basis: "CNY",
              daily_avg_total: 0,
              rows: [
                {
                  basis_bucket: "missing-basis-adb",
                  daily_avg_balance: null,
                  daily_avg_pct: null,
                  source_account_patterns: [],
                },
              ],
              accounting_controls: [],
              excluded_controls: [],
            },
          ],
        };
      },
    });

    const section = await screen.findByTestId("adb-accounting-basis-section");
    await waitFor(() => expect(section).toHaveTextContent("missing-basis-adb"));
    const missingRow = screen.getByText("missing-basis-adb").closest("tr");
    const zeroRow = screen.getByText("true-zero-basis-adb").closest("tr");
    expect(missingRow).toHaveTextContent("—");
    expect(missingRow).not.toHaveTextContent("0.00");
    expect(zeroRow).toHaveTextContent("0.00");
  });

  it("renders the monthly statistics tab with YTD summary, expandable table, and deep analysis panels", async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(await screen.findByRole("tab", { name: "月度统计" }));

    expect(await screen.findByRole("heading", { name: "月度日均统计" })).toBeInTheDocument();
    expect(await screen.findByText("年初至今日均资产")).toBeInTheDocument();
    expect(screen.getByText("年初至今日均负债")).toBeInTheDocument();
    expect(screen.getByText("年初至今加权YTM")).toBeInTheDocument();
    expect(screen.getByText("年初至今加权票息")).toBeInTheDocument();
    expect(screen.getByText("年初至今利差")).toBeInTheDocument();

    expect(screen.getByText("月度汇总表")).toBeInTheDocument();
    expect(screen.getAllByText("2026年3月").length).toBeGreaterThan(0);
    expect(screen.getByText("按月度日均分析 - 深度分析")).toBeInTheDocument();
    expect(screen.getByText("资产端分类明细")).toBeInTheDocument();
    expect(screen.getByText("负债端分类明细")).toBeInTheDocument();
    expect(screen.getByText("月份")).toBeInTheDocument();
    expect(screen.getByText("天数")).toBeInTheDocument();
    expect(screen.getByText(/额\s*\+\s*0\.18\s*亿元/)).toBeInTheDocument();
    const matrix = screen.getByTestId("adb-monthly-analysis-matrix");
    expect(matrix).toHaveTextContent("分类");
    expect(matrix).toHaveTextContent("项目");
    expect(matrix).toHaveTextContent("2026年2月");
    expect(matrix).toHaveTextContent("2026年3月");
    expect(matrix).toHaveTextContent("比上月");
    expect(matrix).toHaveTextContent("比年初");
    expect(matrix).toHaveTextContent("资产：债券投资");
    expect(matrix).toHaveTextContent("负债：同业负债");
    expect(matrix).toHaveTextContent("日均资产");
    expect(matrix).toHaveTextContent("日均负债");
    expect(matrix).toHaveTextContent("加权YTM");
    expect(matrix).toHaveTextContent("利差");
    expect(screen.getAllByTestId("adb-monthly-breakdown-table")).toHaveLength(2);
    expect(screen.getAllByTestId("average-balance-echarts-stub")).toHaveLength(3);
  });

  it("renders missing monthly average balances as unavailable instead of zero", async () => {
    const user = userEvent.setup();
    renderView({
      async getAdbMonthly() {
        return {
          year: 2026,
          ytd_avg_assets: null,
          ytd_avg_liabilities: null,
          ytd_asset_yield: null,
          ytd_liability_cost: null,
          ytd_nim: null,
          months: [
            {
              month: "2026-03",
              month_label: "Null Month",
              num_days: 31,
              avg_assets: null,
              avg_liabilities: null,
              asset_yield: null,
              liability_cost: null,
              net_interest_margin: null,
              mom_change_assets: null,
              mom_change_pct_assets: null,
              mom_change_liabilities: null,
              mom_change_pct_liabilities: null,
              breakdown_assets: [
                {
                  category: "missing-monthly-adb",
                  avg_balance: null,
                  proportion: null,
                  weighted_rate: null,
                },
                {
                  category: "true-zero-monthly-adb",
                  avg_balance: 0,
                  proportion: 0,
                  weighted_rate: null,
                },
              ],
              breakdown_liabilities: [],
            },
          ],
        };
      },
    });

    await user.click(await screen.findByRole("tab", { name: "月度统计" }));

    const ytdAssetCard = (await screen.findByText("年初至今日均资产")).closest(".adb-kpi");
    const ytdLiabilityCard = screen.getByText("年初至今日均负债").closest(".adb-kpi");
    expect(ytdAssetCard).toHaveTextContent("—");
    expect(ytdLiabilityCard).toHaveTextContent("—");

    await waitFor(() => expect(screen.getAllByText("Null Month").length).toBeGreaterThan(0));
    const monthlyRow = screen
      .getAllByText("Null Month")
      .map((node) => node.closest("tr"))
      .find((row): row is HTMLTableRowElement => Boolean(row?.textContent?.includes("31")));
    expect(monthlyRow).toHaveTextContent("—");
    expect(monthlyRow).not.toHaveTextContent("0.00");

    const missingBreakdownRow = screen.getByText("missing-monthly-adb").closest("tr");
    const zeroBreakdownRow = screen.getByText("true-zero-monthly-adb").closest("tr");
    expect(missingBreakdownRow).toHaveTextContent("—");
    expect(zeroBreakdownRow).toHaveTextContent("0.00");
  });

  it("shows an explicit error state when report dates fail and no daily query can start", async () => {
    renderView({
      async getBalanceAnalysisDates() {
        throw new Error("dates unavailable");
      },
    });

    expect(await screen.findByText("可用报告日加载失败，请先恢复报告日列表后再查看日均分析。")).toBeInTheDocument();
    expect(screen.queryByText("期末时点总资产")).not.toBeInTheDocument();
  });

  it("shows an explicit daily error state when comparison loading fails", async () => {
    renderView({
      async getAdbComparison() {
        throw new Error("comparison unavailable");
      },
    });

    expect(await screen.findByText("日均分析加载失败")).toBeInTheDocument();
    expect(screen.queryByText("期末时点总资产")).not.toBeInTheDocument();
  });

  it("loads coverage diagnostics when formal coverage is materially below the calendar window", async () => {
    const user = userEvent.setup();
    renderView({
      async getAdbComparison(startDate: string, endDate: string, _opts?: { topN?: number }) {
        if (startDate.startsWith("2025")) {
          return {
            report_date: "2025-04-14",
            start_date: startDate,
            end_date: endDate,
            calendar_days_inclusive: 104,
            adb_denominator_basis: "formal_calendar" as const,
            num_days: 104,
            coverage_days: 104,
            simulated: true,
            total_spot_assets: 520000000,
            total_avg_assets: 450000000,
            total_spot_liabilities: 220000000,
            total_avg_liabilities: 180000000,
            total_avg_interbank_assets: 200000000,
            total_avg_interbank_liabilities: 88000000,
            asset_yield: 2.4,
            liability_cost: 1.68,
            net_interest_margin: 0.72,
            assets_breakdown: [],
            liabilities_breakdown: [],
          };
        }
        return {
          report_date: "2026-04-14",
          start_date: "2026-01-01",
          end_date: "2026-04-14",
          calendar_days_inclusive: 100,
          adb_denominator_basis: "formal_calendar" as const,
          num_days: 100,
          coverage_days: 30,
          sample_filled: true,
          sample_fill_method: "observed_days_scaled_to_calendar",
          simulated: false,
          total_spot_assets: 550000000,
          total_avg_assets: 500000000,
          total_spot_liabilities: 230000000,
          total_avg_liabilities: 200000000,
          total_avg_interbank_assets: 240000000,
          total_avg_interbank_liabilities: 110000000,
          asset_yield: 2.55,
          liability_cost: 1.75,
          net_interest_margin: 0.8,
          asset_rate_coverage_ratio: 0.5,
          liability_rate_coverage_ratio: 1,
          assets_breakdown: [],
          liabilities_breakdown: [],
        };
      },
      async getAdbCoverage() {
        return {
          start_date: "2026-01-01",
          end_date: "2026-04-14",
          calendar_days: 100,
          snapshot_tables: {},
          formal_tables: {},
          snapshot_date_count: 80,
          formal_date_count: 30,
          missing_dates: ["2026-02-01", "2026-02-02"],
          missing_count: 50,
          coverage_pct: 37.5,
        };
      },
    });

    expect(await screen.findByTestId("adb-coverage-diagnostics")).toBeInTheDocument();
    expect(await screen.findByTestId("adb-rate-coverage-warning")).toHaveTextContent("50.0%");
    await user.click(screen.getByText("快照 vs formal 覆盖诊断（只读）"));
    expect(await screen.findByTestId("adb-rate-coverage-diagnostics")).toHaveTextContent("50.0%");
    expect(await screen.findByTestId("adb-coverage-missing-list")).toHaveTextContent("2026-02-01");
  });

  it("surfaces backend result metadata for daily ADB reads", async () => {
    renderView({
      async getAdbComparison() {
        return {
          report_date: "2026-04-14",
          start_date: "2026-01-01",
          end_date: "2026-04-14",
          calendar_days_inclusive: 104,
          adb_denominator_basis: "formal+snapshot_calendar" as const,
          num_days: 104,
          coverage_days: 104,
          simulated: false,
          total_spot_assets: 550000000,
          total_avg_assets: 500000000,
          total_spot_liabilities: 230000000,
          total_avg_liabilities: 200000000,
          total_avg_interbank_assets: 0,
          total_avg_interbank_liabilities: 0,
          asset_yield: 2.55,
          liability_cost: 1.75,
          net_interest_margin: 0.8,
          assets_breakdown: [],
          liabilities_breakdown: [],
          result_meta: {
            trace_id: "tr_adb_comparison_live",
            basis: "analytical" as const,
            result_kind: "adb.comparison",
            formal_use_allowed: false,
            source_version: "sv_live_adb",
            vendor_version: "vv_none",
            rule_version: "rv_adb_analysis_v1",
            cache_version: "cv_adb_analysis_v1",
            quality_flag: "warning" as const,
            vendor_status: "ok" as const,
            fallback_mode: "latest_snapshot" as const,
            scenario_flag: false,
            requested_report_date: "2026-01-01",
            resolved_report_date: "2026-04-14",
            as_of_date: "2026-04-14",
            date_basis: "adb_comparison_report_date",
            tables_used: [
              "fact_formal_zqtz_balance_daily",
              "fact_formal_tyw_balance_daily",
              "tyw_interbank_daily_snapshot",
            ],
            filters_applied: {
              start_date: "2026-01-01",
              end_date: "2026-04-14",
              top_n: 20,
            },
            evidence_rows: 104,
            generated_at: "2026-04-14T08:00:00+08:00",
          },
        };
      },
    });

    const meta = await screen.findByTestId("adb-daily-result-meta");
    expect(meta).toHaveTextContent("adb.comparison");
    expect(meta).toHaveTextContent("来源=sv_live_adb");
    expect(meta).toHaveTextContent("降级=最新快照降级");
    expect(meta).toHaveTextContent("候选指标");
    expect(meta).toHaveTextContent("PAGE-CONTRACT-PENDING:/average-balance");
    expect(meta).toHaveTextContent("正式可用: 否");
    expect(meta).toHaveTextContent("口径 analytical");
    expect(meta).toHaveTextContent("质量=预警");
    expect(meta).toHaveTextContent("日期基准 adb_comparison_report_date");
    expect(meta).toHaveTextContent("fact_formal_zqtz_balance_daily");
    expect(meta).toHaveTextContent("fact_formal_tyw_balance_daily");
    expect(meta).toHaveTextContent("tyw_interbank_daily_snapshot");
    expect(meta).toHaveTextContent("证据行 104");

    const snapshotWarning = await screen.findByTestId("adb-snapshot-fallback-warning");
    expect(snapshotWarning).toHaveTextContent("快照补数降级");
    expect(snapshotWarning).toHaveTextContent("部分日期由快照补数");
    expect(snapshotWarning).toHaveTextContent("非正式口径");
  });
});

describe("shiftIsoDateByYears", () => {
  it("shifts calendar years and clamps invalid leap dates", () => {
    expect(shiftIsoDateByYears("2025-04-14", -1)).toBe("2024-04-14");
    expect(shiftIsoDateByYears("2024-02-29", -1)).toBe("2023-02-28");
    expect(shiftIsoDateByYears("2023-04-12", 1)).toBe("2024-04-12");
  });
});
