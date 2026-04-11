import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { createWorkbenchMemoryRouter } from "./renderWorkbenchApp";
import { routerFuture } from "../router/routerFuture";

function renderBalanceAnalysisWithClient(client: ReturnType<typeof createApiClient>) {
  const router = createWorkbenchMemoryRouter(["/balance-analysis"]);
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: 0,
        refetchOnWindowFocus: false,
      },
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

function buildMeta(resultKind: string, traceId: string) {
  return {
    trace_id: traceId,
    basis: "formal" as const,
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_balance",
    vendor_version: "vv_none",
    rule_version: "rv_balance",
    cache_version: "cv_balance",
    quality_flag: "ok" as const,
    scenario_flag: false,
    generated_at: "2026-04-11T04:00:00Z",
  };
}

function buildSummaryResponse(offset: number) {
  const rows =
    offset === 0
      ? [
          {
            row_key: "zqtz:240001.IB:portfolio-a:cc-1:CNY:asset:A:FVOCI",
            source_family: "zqtz" as const,
            display_name: "240001.IB",
            owner_name: "利率债组合",
            category_name: "交易账户",
            position_scope: "asset" as const,
            currency_basis: "CNY" as const,
            invest_type_std: "A",
            accounting_basis: "FVOCI",
            detail_row_count: 3,
            market_value_amount: "720.00",
            amortized_cost_amount: "648.00",
            accrued_interest_amount: "36.00",
          },
          {
            row_key: "tyw:repo-1:CNY:liability:H:AC",
            source_family: "tyw" as const,
            display_name: "repo-1",
            owner_name: "同业负债池",
            category_name: "卖出回购",
            position_scope: "liability" as const,
            currency_basis: "CNY" as const,
            invest_type_std: "H",
            accounting_basis: "AC",
            detail_row_count: 1,
            market_value_amount: "72.00",
            amortized_cost_amount: "72.00",
            accrued_interest_amount: "14.40",
          },
        ]
      : [
          {
            row_key: "zqtz:240002.IB:portfolio-b:cc-2:CNY:asset:H:AC",
            source_family: "zqtz" as const,
            display_name: "240002.IB",
            owner_name: "高等级组合",
            category_name: "摊余成本",
            position_scope: "asset" as const,
            currency_basis: "CNY" as const,
            invest_type_std: "H",
            accounting_basis: "AC",
            detail_row_count: 2,
            market_value_amount: "410.00",
            amortized_cost_amount: "403.00",
            accrued_interest_amount: "20.00",
          },
        ];

  return {
    result_meta: buildMeta("balance-analysis.summary", `tr_balance_summary_${offset}`),
    result: {
      report_date: "2025-12-31",
      position_scope: "all" as const,
      currency_basis: "CNY" as const,
      limit: 2,
      offset,
      total_rows: 3,
      rows,
    },
  };
}

describe("BalanceAnalysisPage", () => {
  it("renders cockpit cards and a paginated summary table from the dedicated summary query", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getDatesSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.dates", "tr_balance_dates"),
      result: {
        report_dates: ["2025-12-31"],
      },
    }));
    const getOverviewSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.overview", "tr_balance_overview"),
      result: {
        report_date: "2025-12-31",
        position_scope: "all" as const,
        currency_basis: "CNY" as const,
        detail_row_count: 7,
        summary_row_count: 3,
        total_market_value_amount: "999.99",
        total_amortized_cost_amount: "888.88",
        total_accrued_interest_amount: "77.77",
      },
    }));
    const getDetailSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.detail", "tr_balance_detail"),
      result: {
        report_date: "2025-12-31",
        position_scope: "all" as const,
        currency_basis: "CNY" as const,
        details: [
          {
            source_family: "zqtz",
            report_date: "2025-12-31",
            row_key: "zqtz:detail-1",
            display_name: "240001.IB",
            position_scope: "asset",
            currency_basis: "CNY",
            invest_type_std: "A",
            accounting_basis: "FVOCI",
            market_value_amount: "720.00",
            amortized_cost_amount: "648.00",
            accrued_interest_amount: "36.00",
            is_issuance_like: false,
          },
        ],
        summary: [],
      },
    }));
    const getSummarySpy = vi.fn(async ({ offset }: { offset: number }) => buildSummaryResponse(offset));

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisDates: getDatesSpy,
      getBalanceAnalysisOverview: getOverviewSpy,
      getBalanceAnalysisDetail: getDetailSpy,
      getBalanceAnalysisSummary: getSummarySpy,
    });

    expect(await screen.findByRole("heading", { name: "资产负债分析" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("999.99");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("888.88");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("77.77");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("7");
      expect(screen.getByTestId("balance-analysis-overview-cards")).toHaveTextContent("3");
    });

    expect(screen.getByTestId("balance-analysis-summary-table")).toHaveTextContent("利率债组合");
    expect(screen.getByTestId("balance-analysis-summary-table")).toHaveTextContent("同业负债池");
    await waitFor(() => {
      expect(screen.getByTestId("balance-analysis-workbook-cards")).toHaveTextContent(
        "债券资产(剔除发行类)",
      );
      expect(screen.getByTestId("balance-analysis-workbook-table-bond_business_types")).toHaveTextContent(
        "政策性金融债",
      );
    });
    expect(screen.getByText("第 1 / 2 页")).toBeInTheDocument();

    await waitFor(() => {
      expect(getSummarySpy).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        positionScope: "all",
        currencyBasis: "CNY",
        limit: 2,
        offset: 0,
      });
    });

    await userEvent.click(screen.getByRole("button", { name: "下一页" }));

    await waitFor(() => {
      expect(getSummarySpy).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        positionScope: "all",
        currencyBasis: "CNY",
        limit: 2,
        offset: 2,
      });
      expect(screen.getByTestId("balance-analysis-summary-table")).toHaveTextContent("高等级组合");
      expect(screen.getByText("第 2 / 2 页")).toBeInTheDocument();
    });

    expect(screen.getByTestId("balance-analysis-result-meta-overview")).toHaveTextContent("formal");
    expect(screen.getByTestId("balance-analysis-result-meta-overview")).toHaveTextContent(
      "balance-analysis.overview",
    );
    expect(screen.getByTestId("balance-analysis-result-meta-workbook")).toHaveTextContent(
      "balance-analysis.workbook",
    );
    expect(screen.getByTestId("balance-analysis-result-meta-summary")).toHaveTextContent(
      "balance-analysis.summary",
    );
    expect(screen.getByTestId("balance-analysis-result-meta-summary")).toHaveTextContent(
      "tr_balance_summary_2",
    );
    expect(screen.getByTestId("balance-analysis-result-meta-detail")).toHaveTextContent(
      "balance-analysis.detail",
    );
  });

  it("downloads the filtered summary export as csv", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const exportSpy = vi.fn(async () => ({
      filename: "balance-analysis-summary-2025-12-31-asset-CNY.csv",
      content: "row_key,display_name\nrow-1,240001.IB\n",
    }));
    const createObjectUrl = vi.fn(() => "blob:balance-analysis");
    const revokeObjectUrl = vi.fn();
    const clickSpy = vi.fn();
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    const originalRevokeObjectURL = globalThis.URL.revokeObjectURL;
    const originalCreateElement = document.createElement.bind(document);

    globalThis.URL.createObjectURL = createObjectUrl;
    globalThis.URL.revokeObjectURL = revokeObjectUrl;
    vi.spyOn(document, "createElement").mockImplementation(((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", {
          configurable: true,
          value: clickSpy,
        });
      }
      return element;
    }) as typeof document.createElement);

    try {
      renderBalanceAnalysisWithClient({
        ...baseClient,
        exportBalanceAnalysisSummaryCsv: exportSpy,
      });

      await screen.findByRole("heading", { name: "资产负债分析" });
      await user.selectOptions(screen.getByLabelText("balance-position-scope"), "asset");
      await user.click(screen.getByTestId("balance-analysis-export-button"));

      await waitFor(() => {
        expect(exportSpy).toHaveBeenCalledWith({
          reportDate: "2025-12-31",
          positionScope: "asset",
          currencyBasis: "CNY",
        });
        expect(createObjectUrl).toHaveBeenCalledTimes(1);
        expect(clickSpy).toHaveBeenCalledTimes(1);
        expect(revokeObjectUrl).toHaveBeenCalledWith("blob:balance-analysis");
      });
    } finally {
      globalThis.URL.createObjectURL = originalCreateObjectURL;
      globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
      vi.restoreAllMocks();
    }
  });

  it("polls refresh status and refetches overview detail and summary after rebuild", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => ({
      status: "queued",
      run_id: "balance_analysis_materialize:test-run",
      job_name: "balance_analysis_materialize",
      trigger_mode: "async",
      cache_key: "balance_analysis:materialize:formal",
      report_date: "2025-12-31",
    }));
    const statusSpy = vi
      .fn()
      .mockResolvedValueOnce({
        status: "running",
        run_id: "balance_analysis_materialize:test-run",
        job_name: "balance_analysis_materialize",
        trigger_mode: "async",
        cache_key: "balance_analysis:materialize:formal",
      })
      .mockResolvedValueOnce({
        status: "completed",
        run_id: "balance_analysis_materialize:test-run",
        job_name: "balance_analysis_materialize",
        trigger_mode: "terminal",
        cache_key: "balance_analysis:materialize:formal",
        report_date: "2025-12-31",
        source_version: "sv_balance",
      });
    const getDatesSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.dates", "tr_balance_dates"),
      result: {
        report_dates: ["2025-12-31"],
      },
    }));
    const getOverviewSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.overview", "tr_balance_overview"),
      result: {
        report_date: "2025-12-31",
        position_scope: "all" as const,
        currency_basis: "CNY" as const,
        detail_row_count: 0,
        summary_row_count: 0,
        total_market_value_amount: "0.00",
        total_amortized_cost_amount: "0.00",
        total_accrued_interest_amount: "0.00",
      },
    }));
    const getDetailSpy = vi.fn(async () => ({
      result_meta: buildMeta("balance-analysis.detail", "tr_balance_detail"),
      result: {
        report_date: "2025-12-31",
        position_scope: "all" as const,
        currency_basis: "CNY" as const,
        details: [],
        summary: [],
      },
    }));
    const getSummarySpy = vi.fn(async ({ offset }: { offset: number }) => buildSummaryResponse(offset));

    renderBalanceAnalysisWithClient({
      ...baseClient,
      getBalanceAnalysisDates: getDatesSpy,
      getBalanceAnalysisOverview: getOverviewSpy,
      getBalanceAnalysisDetail: getDetailSpy,
      getBalanceAnalysisSummary: getSummarySpy,
      refreshBalanceAnalysis: refreshSpy,
      getBalanceAnalysisRefreshStatus: statusSpy,
    });

    await screen.findByRole("heading", { name: "资产负债分析" });
    await user.click(screen.getByTestId("balance-analysis-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledWith("2025-12-31");
      expect(statusSpy).toHaveBeenCalledWith("balance_analysis_materialize:test-run");
      expect(screen.getByText(/balance_analysis_materialize:test-run/)).toBeInTheDocument();
      expect(getDatesSpy.mock.calls.length).toBeGreaterThan(1);
      expect(getOverviewSpy.mock.calls.length).toBeGreaterThan(1);
      expect(getDetailSpy.mock.calls.length).toBeGreaterThan(1);
      expect(getSummarySpy.mock.calls.length).toBeGreaterThan(1);
    });
  });
});
