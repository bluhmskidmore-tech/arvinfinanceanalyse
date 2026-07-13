import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PnlByBusinessMonthlyManagementChange } from "../../api/contracts";
import { PnlByBusinessManagementChangePanel } from "./PnlByBusinessManagementChangePanel";

const availableChange = (): PnlByBusinessMonthlyManagementChange => ({
  comparison_basis: "latest_month_vs_previous_calendar_month",
  comparison_scope: "requested_year",
  comparison_status: "available",
  comparison_available: true,
  current_month_key: "2025-12",
  previous_month_key: "2025-11",
  coverage_warning_months: [],
  reconciliation_warning_months: [],
  incomplete_months: [],
  summary: {
    interest_income_delta: "10.00",
    fair_value_change_delta: "0.00",
    capital_gain_delta: "0.00",
    manual_adjustment_delta: "0.00",
    total_pnl_delta: "10.00",
    avg_balance_delta: "100000000.00",
    current_balance_delta: "200000000.00",
    annualized_yield_delta_bp: "1.0000",
    ftp_cost_delta: null,
    ftp_net_pnl_delta: null,
    ftp_net_annualized_yield_delta_bp: null,
  },
  rows: [],
});

describe("PnlByBusinessManagementChangePanel", () => {
  it("announces the loading state", () => {
    render(
      <PnlByBusinessManagementChangePanel
        managementChange={undefined}
        expectedCurrentMonthKey="2025-12"
        selectedRowKey={null}
        isLoading
        isError={false}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("月度变化加载中");
  });

  it("distinguishes a missing current month from a missing previous month", () => {
    render(
      <PnlByBusinessManagementChangePanel
        managementChange={{
          ...availableChange(),
          comparison_status: "current_month_missing",
          comparison_available: false,
          summary: null,
        }}
        expectedCurrentMonthKey="2025-12"
        selectedRowKey={null}
        isLoading={false}
        isError={false}
      />,
    );

    expect(screen.getByText("当前月数据缺失")).toBeInTheDocument();
    expect(screen.queryByText("暂无可比上月")).not.toBeInTheDocument();
  });

  it("fails closed when the YTD month and comparison month differ", () => {
    render(
      <PnlByBusinessManagementChangePanel
        managementChange={availableChange()}
        expectedCurrentMonthKey="2025-11"
        selectedRowKey={null}
        isLoading={false}
        isError={false}
      />,
    );

    expect(screen.getByText("月度变化日期不一致")).toBeInTheDocument();
    expect(screen.getByText(/当前页面月份为 2025-11/)).toBeInTheDocument();
  });

  it("keeps nullable FTP changes unavailable instead of displaying zero", () => {
    render(
      <PnlByBusinessManagementChangePanel
        managementChange={availableChange()}
        expectedCurrentMonthKey="2025-12"
        selectedRowKey={null}
        isLoading={false}
        isError={false}
      />,
    );

    const ftpCard = screen.getByText("FTP净损益变化").closest("article");
    const ftpYieldCard = screen.getByText("FTP后年化变化").closest("article");
    expect(ftpCard).not.toBeNull();
    expect(ftpYieldCard).not.toBeNull();
    expect(within(ftpCard!).getByText("—")).toBeInTheDocument();
    expect(within(ftpYieldCard!).getByText("—")).toBeInTheDocument();
  });

  it("marks cached comparison data stale when a background refresh fails", () => {
    render(
      <PnlByBusinessManagementChangePanel
        managementChange={availableChange()}
        expectedCurrentMonthKey="2025-12"
        selectedRowKey={null}
        isLoading={false}
        isError
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("刷新失败，当前展示上次成功结果");
    expect(screen.getByRole("status")).toHaveTextContent("可能未包含最新补数或手工调整");
  });

  it("fails closed when a cached unavailable state cannot be refreshed", () => {
    render(
      <PnlByBusinessManagementChangePanel
        managementChange={{
          ...availableChange(),
          comparison_status: "current_month_missing",
          comparison_available: false,
          summary: null,
        }}
        expectedCurrentMonthKey="2025-12"
        selectedRowKey={null}
        isLoading={false}
        isError
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("月度变化刷新失败");
    expect(screen.getByRole("status")).toHaveTextContent("缓存状态可能已过期");
    expect(screen.queryByText("当前月数据缺失")).not.toBeInTheDocument();
  });

  it("does not describe a zero-change row as a business driver", () => {
    render(
      <PnlByBusinessManagementChangePanel
        managementChange={{
          ...availableChange(),
          rows: [
            {
              row_key: "asset_zqtz_central_bank_bill",
              sort_order: 60,
              business_type: "央行票据",
              comparison_available: true,
              comparison_reason: "available",
              interest_income_delta: "0.00",
              fair_value_change_delta: "0.00",
              capital_gain_delta: "0.00",
              manual_adjustment_delta: "0.00",
              total_pnl_delta: "0.00",
              avg_balance_delta: "0.00",
              current_balance_delta: "0.00",
              annualized_yield_delta_bp: null,
              ftp_cost_delta: null,
              ftp_net_pnl_delta: null,
              ftp_net_annualized_yield_delta_bp: null,
            },
          ],
        }}
        expectedCurrentMonthKey="2025-12"
        selectedRowKey={null}
        isLoading={false}
        isError={false}
      />,
    );

    expect(screen.queryByText(/最大波动业务为/)).not.toBeInTheDocument();
    expect(screen.getByText("暂无可展示的业务分项比较。")).toBeInTheDocument();
  });

  it("keeps large PnL movements in the page-contract unit of ten-thousand yuan", () => {
    render(
      <PnlByBusinessManagementChangePanel
        managementChange={{
          ...availableChange(),
          summary: {
            ...availableChange().summary!,
            total_pnl_delta: "150000000.00",
          },
        }}
        expectedCurrentMonthKey="2025-12"
        selectedRowKey={null}
        isLoading={false}
        isError={false}
      />,
    );

    expect(screen.getByRole("note")).toHaveTextContent("增加 15,000.00 万元");
    expect(screen.getByRole("note")).not.toHaveTextContent("1.50 亿元");
  });

  it("leads with a concise movement conclusion and returned PnL components", () => {
    render(
      <PnlByBusinessManagementChangePanel
        managementChange={{
          ...availableChange(),
          summary: {
            ...availableChange().summary!,
            interest_income_delta: "20000.00",
            fair_value_change_delta: "5000.00",
            capital_gain_delta: "7500.00",
            manual_adjustment_delta: "2500.00",
            total_pnl_delta: "35000.00",
            avg_balance_delta: "10000000.00",
            current_balance_delta: "8000000.00",
          },
          rows: [
            {
              row_key: "asset_zqtz_policy_financial_bond",
              sort_order: 66,
              business_type: "政策性金融债",
              comparison_available: true,
              comparison_reason: "available",
              interest_income_delta: "20000.00",
              fair_value_change_delta: "5000.00",
              capital_gain_delta: "7500.00",
              manual_adjustment_delta: "2500.00",
              total_pnl_delta: "35000.00",
              avg_balance_delta: "10000000.00",
              current_balance_delta: "8000000.00",
              annualized_yield_delta_bp: "24.6386",
              ftp_cost_delta: "17534.25",
              ftp_net_pnl_delta: "17465.75",
              ftp_net_annualized_yield_delta_bp: "24.6386",
            },
          ],
        }}
        expectedCurrentMonthKey="2025-12"
        selectedRowKey={null}
        isLoading={false}
        isError={false}
      />,
    );

    expect(screen.getByTestId("pnl-by-business-management-change")).toHaveTextContent(
      "2025-12 已分类父级损益较上月增加 3.50 万元",
    );
    expect(screen.getByTestId("pnl-by-business-management-change")).toHaveTextContent(
      "最大波动业务为政策性金融债（增加 3.50 万元）",
    );
    expect(screen.getByTestId("pnl-by-business-management-change")).toHaveTextContent(
      "日均余额增加 0.10 亿元，期末余额增加 0.08 亿元",
    );
    expect(screen.getByText("损益构成变化")).toBeInTheDocument();
    const headers = within(screen.getByTestId("pnl-by-business-management-change-drivers"))
      .getAllByRole("columnheader")
      .map((header) => header.textContent);
    expect(headers).toEqual([
      "已分类业务",
      "损益变化（万元）",
      "FTP净损益变化（万元）",
      "日均变化（亿元）",
      "FTP后年化变化（bp）",
    ]);
  });
});
