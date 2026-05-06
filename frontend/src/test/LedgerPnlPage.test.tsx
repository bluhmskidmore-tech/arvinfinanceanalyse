import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  LedgerMoneyValue,
  LedgerPnlDataPayload,
  LedgerPnlDatesPayload,
  LedgerPnlSummaryPayload,
  QdbGlMonthlyAnalysisDatesPayload,
  QdbGlMonthlyAnalysisWorkbookPayload,
  ResultMeta,
} from "../api/contracts";
import LedgerPnlPage from "../features/ledger-pnl/pages/LedgerPnlPage";

function renderLedgerPnlPage(client: ApiClient, initialEntry = "/ledger-pnl?report_date=2026-03-31") {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <LedgerPnlPage />
    </Wrapper>,
  );
}

function buildMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_ledger_test",
    vendor_version: "vv_none",
    rule_version: "rv_ledger_test",
    cache_version: "cv_ledger_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T08:00:00Z",
  };
}

function buildAnalyticalMeta(resultKind: string): ResultMeta {
  return {
    ...buildMeta(resultKind),
    basis: "analytical",
    formal_use_allowed: false,
    trace_id: `tr_${resultKind}`,
    source_version: "sv_qdb_gl_monthly_analysis_test",
    rule_version: "rv_qdb_gl_monthly_analysis_test",
    cache_version: "cv_qdb_gl_monthly_analysis_test",
  };
}

function money(yuan: string, wan = "999.99"): LedgerMoneyValue {
  return {
    yuan,
    yi: (Number(yuan) / 100_000_000).toFixed(2),
    ...(wan === "" ? {} : { wan }),
  } as LedgerMoneyValue;
}

describe("LedgerPnlPage", () => {
  it("renders all ledger money fields in yi units", async () => {
    const base = createApiClient({ mode: "mock" });
    const datesPayload: LedgerPnlDatesPayload = {
      dates: ["2026-03-31"],
    };
    const summaryPayload: LedgerPnlSummaryPayload = {
      report_date: "2026-03-31",
      source_version: "sv_ledger_test",
      ledger_monthly_pnl_core: money("100000000.00", ""),
      ledger_monthly_pnl_all: money("-200000000.00"),
      ledger_total_assets: money("300000000.00"),
      ledger_total_liabilities: money("-400000000.00"),
      ledger_net_assets: money("500000000.00"),
      by_currency: [
        {
          currency: "CNY",
          total_pnl: money("600000000.00"),
        },
      ],
      by_account: [
        {
          account_code: "514",
          account_name: "interest income",
          total_pnl: money("700000000.00"),
          count: 1,
        },
      ],
    };
    const dataPayload: LedgerPnlDataPayload = {
      report_date: "2026-03-31",
      summary: {
        total_pnl_cnx: money("0.00"),
        total_pnl_cny: money("0.00"),
        total_pnl: money("0.00"),
        count: 1,
      },
      items: [
        {
          account_code: "514",
          account_name: "interest income",
          currency: "CNY",
          beginning_balance: money("800000000.00"),
          ending_balance: money("900000000.00"),
          monthly_pnl: money("1100000000.00"),
          daily_avg_balance: money("1200000000.00"),
          days_in_period: 31,
        },
      ],
    };
    const monthlyAnalysisDatesPayload: QdbGlMonthlyAnalysisDatesPayload = {
      report_months: ["202603"],
    };
    const monthlyAnalysisWorkbookPayload: QdbGlMonthlyAnalysisWorkbookPayload = {
      report_month: "202603",
      sheets: [
        {
          key: "overview",
          title: "经营概览",
          columns: ["指标", "值"],
          rows: [
            { 指标: "总资产(亿)", 值: 1200 },
            { 指标: "存贷比%", 值: 79.69 },
          ],
        },
        {
          key: "top_11d",
          title: "11位偏离TOP",
          columns: ["科目代码", "科目名称", "偏离额"],
          rows: [{ 科目代码: "14001000001", 科目名称: "买入返售", 偏离额: 230 }],
        },
        {
          key: "alerts",
          title: "异动预警",
          columns: ["科目代码", "科目名称", "预警级别"],
          rows: [{ 科目代码: "14001000001", 科目名称: "买入返售", 预警级别: "alert" }],
        },
        {
          key: "segment_base_scale",
          title: "分部基础规模",
          columns: ["指标", "时点余额", "年日均", "月日均", "口径来源"],
          rows: [
            {
              指标: "微贷中心",
              时点余额: null,
              年日均: null,
              月日均: null,
              口径来源: "source_missing: 标准日均源不含80297微贷金融支行专段",
            },
          ],
        },
        {
          key: "segment_scale_compare",
          title: "分部规模同比环比",
          columns: ["指标", "口径", "本期", "对比期", "增减额", "增减幅%", "口径来源"],
          rows: [
            {
              指标: "公司贷款合计",
              口径: "时点环比",
              本期: 3458.61,
              对比期: 3339.26,
              增减额: 119.35,
              "增减幅%": 3.57,
              口径来源: "月度分析-分部情况：总账对账+日均同源历史月重建",
            },
            {
              指标: "微贷中心",
              口径: "月日均环比",
              本期: null,
              对比期: null,
              增减额: null,
              "增减幅%": null,
              口径来源: "source_missing: 标准日均源不含80297微贷金融支行专段",
            },
          ],
        },
        {
          key: "financial_market_scale",
          title: "金融市场规模",
          columns: ["指标", "时点余额", "年日均", "月日均", "口径来源"],
          rows: [
            {
              指标: "生息债券投资",
              时点余额: 2541.38,
              年日均: 2458.66,
              月日均: 2522.26,
              口径来源: "金融市场规模：总账对账+日均同源科目重建",
            },
          ],
        },
        {
          key: "company_scale",
          title: "公司规模",
          columns: ["指标", "时点余额", "年日均", "月日均", "口径来源"],
          rows: [
            {
              指标: "公司存款-活期",
              时点余额: 923.15,
              年日均: 935.21,
              月日均: 920.29,
              口径来源: "公司规模：总账对账+日均同源科目重建",
            },
          ],
        },
        {
          key: "company_scale_compare",
          title: "公司规模同比环比",
          columns: ["指标", "口径", "本期", "对比期", "增减额", "增减幅%", "口径来源"],
          rows: [
            {
              指标: "公司贷款-票据",
              口径: "月日均环比",
              本期: 230.53,
              对比期: 228.03,
              增减额: 2.5,
              "增减幅%": 1.1,
              口径来源: "月度分析-公司板块：总账对账+日均同源历史月重建",
            },
          ],
        },
        {
          key: "retail_scale",
          title: "零售规模",
          columns: ["指标", "时点余额", "年日均", "月日均", "口径来源"],
          rows: [
            {
              指标: "零售存款-活期",
              时点余额: 327.8,
              年日均: 318.83,
              月日均: 315.56,
              口径来源: "零售规模：总账对账+日均同源科目重建",
            },
          ],
        },
        {
          key: "retail_scale_compare",
          title: "零售规模同比环比",
          columns: ["指标", "口径", "本期", "对比期", "增减额", "增减幅%", "口径来源"],
          rows: [
            {
              指标: "零售存款合计",
              口径: "时点环比",
              本期: 2604.03,
              对比期: 2566.14,
              增减额: 37.88,
              "增减幅%": 1.48,
              口径来源: "月度分析-零售板块：总账对账+日均同源历史月重建",
            },
            {
              指标: "零售贷款-分支行个贷",
              口径: "月日均环比",
              本期: null,
              对比期: null,
              增减额: null,
              "增减幅%": null,
              口径来源: "source_missing: 零售分支行个贷依赖80297微贷金融支行专段",
            },
          ],
        },
        {
          key: "financial_market_scale_compare",
          title: "金融市场规模同比环比",
          columns: ["指标", "口径", "本期", "对比期", "增减额", "增减幅%", "口径来源"],
          rows: [
            {
              指标: "同业负债",
              口径: "月日均环比",
              本期: 1756.73,
              对比期: 1710.07,
              增减额: 46.66,
              "增减幅%": 2.73,
              口径来源: "月度分析-金融市场：总账对账+日均同源历史月重建",
            },
          ],
        },
        {
          key: "income_rate_analysis",
          title: "收益率分析（总账可复算）",
          columns: ["指标", "板块", "收益类别", "年日均规模", "总账收益/支出", "年化收益率/付息率%", "口径来源"],
          rows: [
            {
              指标: "公司贷款利息收入",
              板块: "公司板块",
              收益类别: "贷款利息收入",
              年日均规模: 3339.26,
              "总账收益/支出": 32.4,
              "年化收益率/付息率%": 3.93,
              口径来源: "收益率分析：总账收益科目+日均规模重建",
            },
            {
              指标: "个人贷款利息收入",
              板块: "参考：个人贷款总量",
              收益类别: "贷款利息收入",
              年日均规模: null,
              "总账收益/支出": 6.53,
              "年化收益率/付息率%": null,
              口径来源: "source_missing: 个人贷款收益率分母依赖信用卡生息规模/80297微贷拆分，当前总账+日均闭环未确认",
            },
            {
              指标: "金融投资利息收入",
              板块: "金融市场",
              收益类别: "金融投资利息收入",
              年日均规模: null,
              "总账收益/支出": null,
              "年化收益率/付息率%": null,
              口径来源: "source_missing: 财务指标表该项依赖外部营收分项/FTP/收益率来源，当前总账+日均闭环未确认",
            },
          ],
        },
        {
          key: "income_rate_attribution",
          title: "收益量价归因（年累计同比）",
          columns: ["指标", "板块", "本期收益/支出", "对比期收益/支出", "增减额", "规模贡献", "利率贡献", "校验差异", "口径来源"],
          rows: [
            {
              指标: "公司贷款利息收入",
              板块: "公司板块",
              "本期收益/支出": 32.4,
              "对比期收益/支出": 29.15,
              增减额: 3.24,
              规模贡献: 6.12,
              利率贡献: -2.88,
              校验差异: 0,
              口径来源: "收益量价归因：总账收益科目+日均规模按年累计同比拆解",
            },
            {
              指标: "个人贷款利息收入",
              板块: "参考：个人贷款总量",
              "本期收益/支出": 6.53,
              "对比期收益/支出": 7.68,
              增减额: -1.15,
              规模贡献: null,
              利率贡献: null,
              校验差异: null,
              口径来源: "source_missing: 个人贷款收益率分母依赖信用卡生息规模/80297微贷拆分，当前总账+日均闭环未确认",
            },
          ],
        },
        {
          key: "deposit_interest_split",
          title: "存款利息拆分",
          columns: ["指标", "板块", "本期年日均", "年累计利息支出", "年化付息率%", "同比增减额", "本月月日均", "本月利息支出", "本月付息率%", "环比增减额", "口径来源"],
          rows: [
            {
              指标: "公司存款",
              板块: "公司板块",
              本期年日均: 2518.24,
              年累计利息支出: 7.67,
              "年化付息率%": 1.24,
              同比增减额: -0.41,
              本月月日均: 2497.6,
              本月利息支出: 2.67,
              "本月付息率%": 1.26,
              环比增减额: 0.29,
              口径来源: "存款利息拆分：总账521利息支出+日均存款规模重建",
            },
          ],
        },
        {
          key: "parent_company_revenue_components",
          title: "母公司营收分项",
          columns: ["指标", "类别", "同比本期", "同比对比期", "同比增减额", "同比增减幅%", "环比本月", "环比上月", "环比增减额", "环比增减幅%", "口径来源"],
          rows: [
            {
              指标: "贷款利息收入",
              类别: "利息净收入",
              同比本期: 39.01,
              同比对比期: 36.96,
              同比增减额: 2.05,
              "同比增减幅%": 5.55,
              环比本月: 13.68,
              环比上月: 12.76,
              环比增减额: 0.92,
              "环比增减幅%": 7.21,
              口径来源: "母公司营收分项：总账损益科目可复算部分",
            },
            {
              指标: "金融投资利息收入",
              类别: "利息净收入",
              同比本期: null,
              同比对比期: null,
              同比增减额: null,
              "同比增减幅%": null,
              环比本月: null,
              环比上月: null,
              环比增减额: null,
              "环比增减幅%": null,
              口径来源: "source_missing: 母公司营收分项该行依赖外部营收分项/FTP/非息明细来源，当前总账+日均闭环未确认",
            },
          ],
        },
        {
          key: "industry_gap",
          title: "行业存贷差",
          columns: ["行业", "存贷差_时点"],
          rows: [{ 行业: "农林牧渔", 存贷差_时点: -600 }],
        },
      ],
    };

    const getLedgerPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.dates"),
      result: datesPayload,
    }));
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: summaryPayload,
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: dataPayload,
    }));
    const getQdbGlMonthlyAnalysisDates = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
      result: monthlyAnalysisDatesPayload,
    }));
    const getQdbGlMonthlyAnalysisWorkbook = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.workbook"),
      result: monthlyAnalysisWorkbookPayload,
    }));

    renderLedgerPnlPage({
      ...base,
      getLedgerPnlDates,
      getLedgerPnlSummary,
      getLedgerPnlData,
      getQdbGlMonthlyAnalysisDates,
      getQdbGlMonthlyAnalysisWorkbook,
    });

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-03-31", undefined);
      expect(getLedgerPnlData).toHaveBeenCalledWith("2026-03-31", undefined);
      expect(getQdbGlMonthlyAnalysisWorkbook).toHaveBeenCalledWith({ reportMonth: "202603" });
    });

    for (const expected of [
      "1.00 亿元",
      "-2.00 亿元",
      "3.00 亿元",
      "-4.00 亿元",
      "5.00 亿元",
      "6.00 亿元",
      "7.00 亿元",
      "8.00 亿元",
      "9.00 亿元",
      "11.00 亿元",
      "12.00 亿元",
    ]) {
      expect(await screen.findByText(expected)).toBeInTheDocument();
    }

    expect(screen.queryByText("100000000.00")).not.toBeInTheDocument();
    expect(screen.queryByText("999.99 万元")).not.toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-panel")).toHaveTextContent("总账对账 + 日均分析");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-month")).toHaveTextContent("202603");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-overview")).toHaveTextContent("总资产(亿)");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-alerts")).toHaveTextContent("14001000001");
    expect(screen.getByText("分部基础规模")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-segment-base-scale")).toHaveTextContent("微贷中心");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-segment-base-scale")).toHaveTextContent(
      "source_missing",
    );
    expect(screen.getByText("分部规模同比环比")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-segment-scale-compare")).toHaveTextContent(
      "公司贷款合计",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-segment-scale-compare")).toHaveTextContent(
      "source_missing",
    );
    expect(screen.getByText("公司规模")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-company-scale")).toHaveTextContent("公司存款-活期");
    expect(screen.getByText("公司规模同比环比")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-company-scale-compare")).toHaveTextContent(
      "公司贷款-票据",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-company-scale-compare")).toHaveTextContent(
      "月度分析-公司板块",
    );
    expect(screen.getByText("零售规模")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-retail-scale")).toHaveTextContent("零售存款-活期");
    expect(screen.getByText("零售规模同比环比")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-retail-scale-compare")).toHaveTextContent(
      "零售存款合计",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-retail-scale-compare")).toHaveTextContent(
      "source_missing",
    );
    expect(screen.getByText("金融市场规模")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-financial-market-scale")).toHaveTextContent(
      "生息债券投资",
    );
    expect(screen.getByText("金融市场规模同比环比")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-financial-market-scale-compare")).toHaveTextContent(
      "同业负债",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-financial-market-scale-compare")).toHaveTextContent(
      "月度分析-金融市场",
    );
    expect(screen.getByText("收益率分析（总账可复算）")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate")).toHaveTextContent(
      "公司贷款利息收入",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate")).toHaveTextContent(
      "个人贷款利息收入",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate")).toHaveTextContent(
      "信用卡生息规模",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate")).toHaveTextContent("source_missing");
    expect(screen.getByText("收益量价归因（年累计同比）")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate-attribution")).toHaveTextContent(
      "规模贡献",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate-attribution")).toHaveTextContent(
      "公司贷款利息收入",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-income-rate-attribution")).toHaveTextContent(
      "个人贷款利息收入",
    );
    expect(screen.getByText("存款利息拆分")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-deposit-interest-split")).toHaveTextContent(
      "公司存款",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-deposit-interest-split")).toHaveTextContent(
      "7.67",
    );
    expect(screen.getByText("母公司营收分项")).toBeInTheDocument();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-parent-company-revenue")).toHaveTextContent(
      "贷款利息收入",
    );
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-parent-company-revenue")).toHaveTextContent(
      "source_missing",
    );
  });

  it("does not fall back to an unrelated monthly analysis workbook", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLedgerPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.dates"),
      result: { dates: ["2026-04-30"] },
    }));
    const getLedgerPnlSummary = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.summary"),
      result: {
        report_date: "2026-04-30",
        source_version: "sv_ledger_test",
        ledger_monthly_pnl_core: money("0.00"),
        ledger_monthly_pnl_all: money("0.00"),
        ledger_total_assets: money("0.00"),
        ledger_total_liabilities: money("0.00"),
        ledger_net_assets: money("0.00"),
        by_currency: [],
        by_account: [],
      },
    }));
    const getLedgerPnlData = vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.data"),
      result: {
        report_date: "2026-04-30",
        summary: {
          total_pnl_cnx: money("0.00"),
          total_pnl_cny: money("0.00"),
          total_pnl: money("0.00"),
          count: 0,
        },
        items: [],
      },
    }));
    const getQdbGlMonthlyAnalysisDates = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.dates"),
      result: { report_months: ["202401", "202402"] },
    }));
    const getQdbGlMonthlyAnalysisWorkbook = vi.fn(async () => ({
      result_meta: buildAnalyticalMeta("qdb-gl-monthly-analysis.workbook"),
      result: { report_month: "202401", sheets: [] },
    }));

    renderLedgerPnlPage(
      {
        ...base,
        getLedgerPnlDates,
        getLedgerPnlSummary,
        getLedgerPnlData,
        getQdbGlMonthlyAnalysisDates,
        getQdbGlMonthlyAnalysisWorkbook,
      },
      "/ledger-pnl?report_date=2026-04-30",
    );

    await waitFor(() => {
      expect(getLedgerPnlSummary).toHaveBeenCalledWith("2026-04-30", undefined);
      expect(getQdbGlMonthlyAnalysisDates).toHaveBeenCalled();
    });

    expect(getQdbGlMonthlyAnalysisWorkbook).not.toHaveBeenCalled();
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-month")).toHaveTextContent("202604 无匹配");
    expect(screen.getByTestId("ledger-pnl-monthly-analysis-missing-month")).toHaveTextContent(
      "当前报告日没有对应月度分析工作簿",
    );
  });
});
