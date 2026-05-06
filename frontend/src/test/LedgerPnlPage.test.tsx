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
