import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { beforeAll, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="product-category-branch-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient } from "../api/client";
import { routerFuture } from "../router/routerFuture";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { createWorkbenchMemoryRouter } from "./renderWorkbenchApp";

function renderBranchPageWithClient(client: ReturnType<typeof createApiClient>) {
  const router = createWorkbenchMemoryRouter(["/product-category-pnl"]);
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

describe("ProductCategoryPnlPage branch switching", () => {
  beforeAll(async () => {
    await preloadWorkbenchRouteModules("product-category-pnl");
  }, 20_000);

  it("defaults to the legacy product-category branch", async () => {
    renderBranchPageWithClient(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("product-category-table")).toBeInTheDocument();
    expect(screen.getByTestId("product-category-branch-product-category-pnl")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("product-category-branch-monthly-operating-analysis")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("switches to monthly operating analysis and renders its workbook sections", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_months: ["202602"],
        },
      }),
      getQdbGlMonthlyAnalysisWorkbook: async () => ({
        result_meta: {
          trace_id: "tr_qdb_workbook",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.workbook",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_choice_202602",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "stale" as const,
          vendor_status: "vendor_stale" as const,
          fallback_mode: "latest_snapshot" as const,
          scenario_flag: false,
          requested_report_date: "2026-02-28",
          resolved_report_date: "2026-01-31",
          as_of_date: "2026-02-28",
          date_basis: "month_end",
          fallback_date: "2026-01-31",
          generated_at: "2026-04-12T00:00:00Z",
          evidence_rows: 2,
          filters_applied: {
            report_month: "202602",
            comparison_months: {
              prior_month: { report_month: "202601", status: "missing" },
              two_months_ago: { report_month: "202512", status: "invalid" },
              prior_year: { report_month: "202502", status: "loaded" },
            },
          },
        },
        result: {
          report_month: "202602",
          sheets: [
            {
              key: "overview",
              title: "Overview",
              columns: ["metric", "value", "delta", "note", "active"],
              rows: [
                { metric: "loan_total", value: 0, delta: null, note: undefined, active: false },
                { metric: "fee_income", value: 1200.5, delta: 35, note: "ok", active: true },
              ],
            },
            {
              key: "alerts",
              title: "Alerts",
              columns: ["account_code", "alert_type"],
              rows: [{ account_code: "14001000001", alert_type: "suspicious" }],
            },
            {
              key: "empty",
              title: "Empty Sheet",
              columns: ["metric"],
              rows: [],
            },
          ],
        },
      }),
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));

    await waitFor(() => {
      expect(screen.getByTestId("product-category-branch-monthly-operating-analysis")).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      expect(screen.getByTestId("monthly-operating-analysis-page-title")).toHaveTextContent("月度经营分析");
      expect(screen.getByTestId("monthly-operating-analysis-boundary-copy")).toHaveTextContent(
        "月度经营分析工作簿",
      );
      expect(screen.getByText(/仅用于分析口径工作簿/)).toBeInTheDocument();
      expect(screen.getByTestId("monthly-operating-analysis-controls-lead")).toHaveTextContent(
        "月度工作簿控制",
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-lead")).toHaveTextContent(
        "月度经营分析工作表",
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /quality_flag=stale/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /vendor_status=vendor_stale/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /formal_use_allowed=false/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /fallback_mode=latest_snapshot/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /fallback_date=2026-01-31/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /as_of_date=2026-02-28/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /requested_report_date=2026-02-28/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /resolved_report_date=2026-01-31/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /date_basis=month_end/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /source_version=sv_qdb_test/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /vendor_version=vv_choice_202602/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /evidence_rows=2/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-comparison-status")).toHaveTextContent(
        /prior_month 202601 missing/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-comparison-status")).toHaveTextContent(
        /two_months_ago 202512 invalid/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-comparison-status")).toHaveTextContent(
        /prior_year 202502 loaded/,
      );
      expect(screen.getByText("Overview")).toBeInTheDocument();
      expect(screen.getByText("Alerts")).toBeInTheDocument();
      expect(screen.getByText("Empty Sheet")).toBeInTheDocument();
      const overviewSection = screen.getByTestId("monthly-operating-analysis-section-overview");
      expect(within(overviewSection).getByRole("table")).toBeInTheDocument();
      expect(within(overviewSection).getByText("loan_total")).toBeInTheDocument();
      expect(within(overviewSection).getByText("0")).toBeInTheDocument();
      expect(within(overviewSection).getAllByText("--")).toHaveLength(2);
      expect(within(overviewSection).getByText("false")).toBeInTheDocument();
      expect(within(overviewSection).getByText("fee_income")).toBeInTheDocument();
      expect(within(overviewSection).getByText("1200.5")).toBeInTheDocument();
      expect(within(overviewSection).getByText("true")).toBeInTheDocument();
      expect(
        within(screen.getByTestId("monthly-operating-analysis-section-empty")).getByTestId(
          "monthly-operating-analysis-empty-state-empty",
        ),
      ).toHaveTextContent(/没有可展示数据/);
      expect(screen.queryByTestId("product-category-table")).not.toBeInTheDocument();
    });
  });

  it("defaults monthly operating analysis to the latest available report month", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const workbookSpy = vi.fn(async ({ reportMonth }: { reportMonth: string }) => ({
      result_meta: {
        trace_id: `tr_qdb_workbook_${reportMonth}`,
        basis: "analytical" as const,
        result_kind: "qdb-gl-monthly-analysis.workbook",
        formal_use_allowed: false,
        source_version: "sv_qdb_test",
        vendor_version: "vv_none",
        rule_version: "rv_qdb_gl_monthly_analysis_v1",
        cache_version: "cv_qdb_gl_monthly_analysis_v1",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-12T00:00:00Z",
      },
      result: {
        report_month: reportMonth,
        sheets: [
          {
            key: "overview",
            title: "Overview",
            columns: ["metric"],
            rows: [{ metric: `selected-${reportMonth}` }],
          },
        ],
      },
    }));
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202401", "202603", "202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: workbookSpy,
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));

    await waitFor(() => {
      expect(screen.getByTestId("monthly-operating-analysis-month-select")).toHaveValue("202603");
      expect(workbookSpy).toHaveBeenCalledWith({ reportMonth: "202603" });
      expect(screen.getByText("selected-202603")).toBeInTheDocument();
    });
    expect(screen.getByTestId("monthly-operating-analysis-audit-link")).toHaveAttribute(
      "href",
      "/product-category-pnl/audit?branch=monthly_operating_analysis&report_month=202603",
    );
    expect(screen.queryByText("selected-202401")).not.toBeInTheDocument();
  });

  it("surfaces missing report months before loading a monthly operating analysis workbook", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const workbookSpy = vi.fn(async () => {
      throw new Error("workbook should not load without a report month");
    });
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates_empty",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "missing" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: [] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: workbookSpy,
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));

    await waitFor(() => {
      expect(screen.getByTestId("monthly-operating-analysis-dates-empty")).toHaveTextContent(
        /当前没有可用报告月份/,
      );
    });
    expect(screen.getByTestId("monthly-operating-analysis-refresh-button")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-export-workbook")).toBeDisabled();
    expect(screen.getByTestId("monthly-operating-analysis-apply-scenario")).toBeDisabled();
    expect(workbookSpy).not.toHaveBeenCalled();
  });

  it("surfaces an empty monthly operating analysis workbook state", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: async () => ({
        result_meta: {
          trace_id: "tr_qdb_workbook_empty",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.workbook",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "missing" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_month: "202602", sheets: [] },
      }),
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));

    await waitFor(() => {
      expect(screen.getByTestId("monthly-operating-analysis-empty-workbook")).toHaveTextContent(
        /当前报告月份没有工作表数据/,
      );
    });
  });

  it("surfaces monthly operating analysis workbook loading failures", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: async () => {
        throw new Error("workbook unavailable");
      },
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));

    await waitFor(() => {
      expect(screen.getByTestId("monthly-operating-analysis-workbook-error")).toHaveTextContent(
        /workbook unavailable/,
      );
    });
  });

  it("clears stale monthly operating analysis workbook data while a newly selected month is loading", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const workbookSpy = vi.fn(async ({ reportMonth }: { reportMonth: string }) => {
      if (reportMonth === "202601") {
        return new Promise<Awaited<ReturnType<typeof baseClient.getQdbGlMonthlyAnalysisWorkbook>>>(() => undefined);
      }

      return {
        result_meta: {
          trace_id: "tr_qdb_workbook_202602",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.workbook",
          formal_use_allowed: false,
          source_version: "sv_qdb_202602",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
          filters_applied: { report_month: "202602" },
        },
        result: {
          report_month: "202602",
          sheets: [
            {
              key: "overview",
              title: "February Overview",
              columns: ["metric"],
              rows: [{ metric: "old-month-marker" }],
            },
          ],
        },
      };
    });
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202601", "202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: workbookSpy,
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));
    await screen.findByText("old-month-marker");
    expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
      /trace_id=tr_qdb_workbook_202602/,
    );

    await user.selectOptions(screen.getByTestId("monthly-operating-analysis-month-select"), "202601");

    await waitFor(() => {
      expect(workbookSpy).toHaveBeenCalledWith({ reportMonth: "202601" });
    });
    expect(screen.queryByText("old-month-marker")).not.toBeInTheDocument();
    expect(screen.queryByTestId("monthly-operating-analysis-workbook-meta")).not.toBeInTheDocument();
    expect(screen.getByTestId("monthly-operating-analysis-workbook-loading")).toHaveTextContent(/202601/);
  });

  it("downloads the monthly operating analysis workbook export as xlsx", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const workbookBlob = new Blob(["qdb-xlsx"], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const exportSpy = vi.fn(async () => ({
      filename: "qdb-monthly-analysis-202602.xlsx",
      content: workbookBlob,
    }));
    const createObjectUrl = vi.fn(() => "blob:qdb-monthly-analysis");
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
      const client = {
        ...baseClient,
        getQdbGlMonthlyAnalysisDates: async () => ({
          result_meta: {
            trace_id: "tr_qdb_dates",
            basis: "analytical" as const,
            result_kind: "qdb-gl-monthly-analysis.dates",
            formal_use_allowed: false,
            source_version: "sv_qdb_test",
            vendor_version: "vv_none",
            rule_version: "rv_qdb_gl_monthly_analysis_v1",
            cache_version: "cv_qdb_gl_monthly_analysis_v1",
            quality_flag: "ok" as const,
            vendor_status: "ok" as const,
            fallback_mode: "none" as const,
            scenario_flag: false,
            generated_at: "2026-04-12T00:00:00Z",
          },
          result: { report_months: ["202602"] },
        }),
        getQdbGlMonthlyAnalysisWorkbook: async () => ({
          result_meta: {
            trace_id: "tr_qdb_workbook",
            basis: "analytical" as const,
            result_kind: "qdb-gl-monthly-analysis.workbook",
            formal_use_allowed: false,
            source_version: "sv_qdb_test",
            vendor_version: "vv_none",
            rule_version: "rv_qdb_gl_monthly_analysis_v1",
            cache_version: "cv_qdb_gl_monthly_analysis_v1",
            quality_flag: "ok" as const,
            vendor_status: "ok" as const,
            fallback_mode: "none" as const,
            scenario_flag: false,
            generated_at: "2026-04-12T00:00:00Z",
          },
          result: {
            report_month: "202602",
            sheets: [{ key: "overview", title: "Overview", columns: ["metric"], rows: [{ metric: "loan_total" }] }],
          },
        }),
        exportQdbGlMonthlyAnalysisWorkbookXlsx: exportSpy,
      };

      renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

      await screen.findByTestId("product-category-table");
      await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));
      await screen.findByText("Overview");
      await user.click(screen.getByTestId("monthly-operating-analysis-export-workbook"));

      await waitFor(() => {
        expect(exportSpy).toHaveBeenCalledWith({ reportMonth: "202602" });
        expect(createObjectUrl).toHaveBeenCalledWith(workbookBlob);
        expect(clickSpy).toHaveBeenCalledTimes(1);
        expect(revokeObjectUrl).toHaveBeenCalledWith("blob:qdb-monthly-analysis");
      });
    } finally {
      globalThis.URL.createObjectURL = originalCreateObjectURL;
      globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
      vi.restoreAllMocks();
    }
  });

  it("surfaces monthly operating analysis workbook export failures without leaking endpoints", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    let rejectExport!: (error: Error) => void;
    const exportSpy = vi.fn(
      () =>
        new Promise<{ filename: string; content: Blob }>((_resolve, reject) => {
          rejectExport = reject;
        }),
    );
    const createObjectUrl = vi.fn(() => "blob:qdb-monthly-analysis");
    const originalCreateObjectURL = globalThis.URL.createObjectURL;

    globalThis.URL.createObjectURL = createObjectUrl;

    try {
      const client = {
        ...baseClient,
        getQdbGlMonthlyAnalysisDates: async () => ({
          result_meta: {
            trace_id: "tr_qdb_dates",
            basis: "analytical" as const,
            result_kind: "qdb-gl-monthly-analysis.dates",
            formal_use_allowed: false,
            source_version: "sv_qdb_test",
            vendor_version: "vv_none",
            rule_version: "rv_qdb_gl_monthly_analysis_v1",
            cache_version: "cv_qdb_gl_monthly_analysis_v1",
            quality_flag: "ok" as const,
            vendor_status: "ok" as const,
            fallback_mode: "none" as const,
            scenario_flag: false,
            generated_at: "2026-04-12T00:00:00Z",
          },
          result: { report_months: ["202602"] },
        }),
        getQdbGlMonthlyAnalysisWorkbook: async () => ({
          result_meta: {
            trace_id: "tr_qdb_workbook",
            basis: "analytical" as const,
            result_kind: "qdb-gl-monthly-analysis.workbook",
            formal_use_allowed: false,
            source_version: "sv_qdb_test",
            vendor_version: "vv_none",
            rule_version: "rv_qdb_gl_monthly_analysis_v1",
            cache_version: "cv_qdb_gl_monthly_analysis_v1",
            quality_flag: "ok" as const,
            vendor_status: "ok" as const,
            fallback_mode: "none" as const,
            scenario_flag: false,
            generated_at: "2026-04-12T00:00:00Z",
          },
          result: {
            report_month: "202602",
            sheets: [{ key: "overview", title: "Overview", columns: ["metric"], rows: [{ metric: "loan_total" }] }],
          },
        }),
        exportQdbGlMonthlyAnalysisWorkbookXlsx: exportSpy,
      };

      renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

      await screen.findByTestId("product-category-table");
      await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));
      await screen.findByText("Overview");

      const exportButton = screen.getByTestId("monthly-operating-analysis-export-workbook");
      await user.click(exportButton);

      await waitFor(() => {
        expect(exportButton).toBeDisabled();
      });

      rejectExport(
        new Error(
          "Request failed: /ui/qdb-gl-monthly-analysis/workbook/export?report_month=202602 (500)",
        ),
      );

      await waitFor(() => {
        const errorPanel = screen.getByTestId("monthly-operating-analysis-workbook-export-error");
        expect(errorPanel).toHaveTextContent(/500/);
        expect(errorPanel).not.toHaveTextContent(/\/ui\/qdb-gl-monthly-analysis/);
        expect(exportButton).not.toBeDisabled();
      });
      expect(exportSpy).toHaveBeenCalledWith({ reportMonth: "202602" });
      expect(createObjectUrl).not.toHaveBeenCalled();
    } finally {
      globalThis.URL.createObjectURL = originalCreateObjectURL;
    }
  });

  it("disables monthly operating analysis refresh and scenario actions while requests are running", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    let resolveRefresh!: (payload: Awaited<ReturnType<typeof baseClient.refreshQdbGlMonthlyAnalysis>>) => void;
    let resolveScenario!: (
      payload: Awaited<ReturnType<typeof baseClient.getQdbGlMonthlyAnalysisScenario>>,
    ) => void;
    const refreshSpy = vi.fn(
      () =>
        new Promise<Awaited<ReturnType<typeof baseClient.refreshQdbGlMonthlyAnalysis>>>((resolve) => {
          resolveRefresh = resolve;
        }),
    );
    const scenarioSpy = vi.fn(
      () =>
        new Promise<Awaited<ReturnType<typeof baseClient.getQdbGlMonthlyAnalysisScenario>>>((resolve) => {
          resolveScenario = resolve;
        }),
    );
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: async () => ({
        result_meta: {
          trace_id: "tr_qdb_workbook",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.workbook",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_month: "202602",
          sheets: [{ key: "overview", title: "Overview", columns: ["metric"], rows: [{ metric: "loan_total" }] }],
        },
      }),
      refreshQdbGlMonthlyAnalysis: refreshSpy,
      getQdbGlMonthlyAnalysisRefreshStatus: vi.fn(),
      getQdbGlMonthlyAnalysisScenario: scenarioSpy,
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));
    await screen.findByText("Overview");

    const refreshButton = screen.getByTestId("monthly-operating-analysis-refresh-button");
    await user.click(refreshButton);

    await waitFor(() => {
      expect(refreshButton).toBeDisabled();
      expect(refreshButton).toHaveTextContent("正在刷新月度经营分析");
    });

    resolveRefresh({
      status: "completed",
      run_id: "qdb_gl_monthly_analysis:202602",
      job_name: "qdb_gl_monthly_analysis",
      trigger_mode: "sync",
      report_month: "202602",
    });

    await waitFor(() => {
      expect(refreshButton).not.toBeDisabled();
      expect(refreshButton).toHaveTextContent("刷新月度经营分析");
    });
    expect(refreshSpy).toHaveBeenCalledTimes(1);

    const scenarioButton = screen.getByTestId("monthly-operating-analysis-apply-scenario");
    await user.click(scenarioButton);

    await waitFor(() => {
      expect(scenarioButton).toBeDisabled();
      expect(scenarioButton).toHaveTextContent("正在应用情景");
    });

    resolveScenario({
      result_meta: {
        trace_id: "tr_qdb_scenario",
        basis: "scenario" as const,
        result_kind: "qdb-gl-monthly-analysis.scenario",
        formal_use_allowed: false,
        source_version: "sv_qdb_scenario",
        vendor_version: "vv_none",
        rule_version: "rv_qdb_gl_monthly_analysis_v1",
        cache_version: "cv_qdb_gl_monthly_analysis_v1",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: true,
        generated_at: "2026-04-12T00:00:00Z",
      },
      result: {
        report_month: "202602",
        scenario_name: "threshold-stress",
        applied_overrides: { DEVIATION_WARN: 6, DEVIATION_ALERT: 12, DEVIATION_CRITICAL: 18 },
        sheets: [{ key: "overview", title: "Scenario Overview", columns: ["metric"], rows: [{ metric: "stress" }] }],
      },
    });

    await waitFor(() => {
      expect(scenarioButton).not.toBeDisabled();
      expect(scenarioButton).toHaveTextContent("应用情景");
    });
    expect(scenarioSpy).toHaveBeenCalledTimes(1);
  });

  it("runs monthly operating analysis refresh and applies a scenario override", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "qdb_gl_monthly_analysis:202602",
      job_name: "qdb_gl_monthly_analysis",
      trigger_mode: "sync",
      cache_key: "qdb_gl_monthly_analysis.analytical",
      report_month: "202602",
      report_date: "202602",
      source_version: "sv_qdb_gl_202602",
      sheet_count: 2,
      tables_used: ["qdb_gl_average_balance_workbook", "qdb_gl_ledger_reconciliation_workbook"],
      evidence_rows: 2,
      comparison_months: {
        prior_month: { report_month: "202601", status: "missing" },
      },
    }));
    const statusSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "qdb_gl_monthly_analysis:202602",
      job_name: "qdb_gl_monthly_analysis",
      trigger_mode: "terminal",
      cache_key: "qdb_gl_monthly_analysis.analytical",
    }));
    const scenarioSpy = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_qdb_scenario",
        basis: "scenario" as const,
        result_kind: "qdb-gl-monthly-analysis.scenario",
        formal_use_allowed: false,
        source_version: "sv_qdb_scenario",
        vendor_version: "vv_none",
        rule_version: "rv_qdb_gl_monthly_analysis_v1",
        cache_version: "cv_qdb_gl_monthly_analysis_v1",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: true,
        generated_at: "2026-04-12T00:00:00Z",
      },
      result: {
        report_month: "202602",
        scenario_name: "threshold-stress",
        applied_overrides: {
          DEVIATION_WARN: 6,
          DEVIATION_ALERT: 12,
          DEVIATION_CRITICAL: 18,
        },
        sheets: [
          {
            key: "overview",
            title: "Scenario Overview",
            columns: ["metric"],
            rows: [{ metric: "stress" }],
          },
          {
            key: "alerts",
            title: "Scenario Alerts",
            columns: ["account_code", "alert_level"],
            rows: [{ account_code: "14001000001", alert_level: "manual_override" }],
          },
        ],
      },
    }));
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: async () => ({
        result_meta: {
          trace_id: "tr_qdb_workbook",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.workbook",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_month: "202602",
          sheets: [{ key: "overview", title: "Overview", columns: ["metric"], rows: [{ metric: "loan_total" }] }],
        },
      }),
      refreshQdbGlMonthlyAnalysis: refreshSpy,
      getQdbGlMonthlyAnalysisRefreshStatus: statusSpy,
      getQdbGlMonthlyAnalysisScenario: scenarioSpy,
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));

    await screen.findByTestId("monthly-operating-analysis-refresh-button");
    await user.click(screen.getByTestId("monthly-operating-analysis-refresh-button"));
    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledWith({ reportMonth: "202602" });
      expect(screen.getByText(/qdb_gl_monthly_analysis:202602/)).toBeInTheDocument();
      expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).toHaveTextContent(/completed/);
      expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).toHaveTextContent(/sheet_count=2/);
      expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).toHaveTextContent(/evidence_rows=2/);
      expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).toHaveTextContent(
        /prior_month 202601 missing/,
      );
    });

    await user.clear(screen.getByTestId("monthly-operating-analysis-scenario-warn"));
    await user.type(screen.getByTestId("monthly-operating-analysis-scenario-warn"), "6");
    await user.clear(screen.getByTestId("monthly-operating-analysis-scenario-alert"));
    await user.type(screen.getByTestId("monthly-operating-analysis-scenario-alert"), "12");
    await user.clear(screen.getByTestId("monthly-operating-analysis-scenario-critical"));
    await user.type(screen.getByTestId("monthly-operating-analysis-scenario-critical"), "18");
    await user.click(screen.getByTestId("monthly-operating-analysis-apply-scenario"));

    await waitFor(() => {
      expect(scenarioSpy).toHaveBeenCalledWith({
        reportMonth: "202602",
        scenarioName: "threshold-stress",
        deviationWarn: 6,
        deviationAlert: 12,
        deviationCritical: 18,
      });
      expect(screen.getByTestId("monthly-operating-analysis-scenario-summary")).toHaveTextContent(
        /threshold-stress/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /basis=scenario/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /scenario_flag=true/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /source_version=sv_qdb_scenario/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-workbook-meta")).toHaveTextContent(
        /trace_id=tr_qdb_scenario/,
      );
      expect(screen.getByText("Scenario Alerts")).toBeInTheDocument();
    });
  });

  it("surfaces monthly operating analysis scenario failures", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const scenarioSpy = vi.fn(async () => {
      throw new Error(
        "Request failed: /ui/qdb-gl-monthly-analysis/scenario?report_month=202602&scenario_name=threshold-stress (500)",
      );
    });
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: async () => ({
        result_meta: {
          trace_id: "tr_qdb_workbook",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.workbook",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_month: "202602",
          sheets: [{ key: "overview", title: "Overview", columns: ["metric"], rows: [{ metric: "loan_total" }] }],
        },
      }),
      getQdbGlMonthlyAnalysisScenario: scenarioSpy,
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));
    await screen.findByText("Overview");

    await user.click(screen.getByTestId("monthly-operating-analysis-apply-scenario"));

    await waitFor(() => {
      expect(screen.getByTestId("monthly-operating-analysis-scenario-error")).toHaveTextContent(
        /请求失败（500）/,
      );
    });
    expect(screen.getByTestId("monthly-operating-analysis-scenario-error")).not.toHaveTextContent(
      /\/ui\/qdb-gl-monthly-analysis/,
    );
    expect(scenarioSpy).toHaveBeenCalledWith({
      reportMonth: "202602",
      scenarioName: "threshold-stress",
      deviationWarn: 6,
      deviationAlert: 12,
      deviationCritical: 18,
    });
  });

  it("shows monthly operating analysis refresh failure details without refetching workbook", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const workbookSpy = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_qdb_workbook",
        basis: "analytical" as const,
        result_kind: "qdb-gl-monthly-analysis.workbook",
        formal_use_allowed: false,
        source_version: "sv_qdb_test",
        vendor_version: "vv_none",
        rule_version: "rv_qdb_gl_monthly_analysis_v1",
        cache_version: "cv_qdb_gl_monthly_analysis_v1",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-12T00:00:00Z",
      },
      result: {
        report_month: "202602",
        sheets: [{ key: "overview", title: "Overview", columns: ["metric"], rows: [{ metric: "loan_total" }] }],
      },
    }));
    const refreshSpy = vi.fn(async () => ({
      status: "failed",
      run_id: "qdb_gl_monthly_analysis:202602",
      job_name: "qdb_gl_monthly_analysis",
      trigger_mode: "sync",
      cache_key: "qdb_gl_monthly_analysis.analytical",
      report_month: "202602",
      failure_category: "qdb_gl_monthly_analysis_build",
      failure_reason: "ValueError",
      error_message: "invalid-header in workbook",
    }));
    const statusSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "qdb_gl_monthly_analysis:202602",
      job_name: "qdb_gl_monthly_analysis",
      trigger_mode: "terminal",
    }));
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: workbookSpy,
      refreshQdbGlMonthlyAnalysis: refreshSpy,
      getQdbGlMonthlyAnalysisRefreshStatus: statusSpy,
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));
    await screen.findByText("Overview");
    expect(workbookSpy).toHaveBeenCalledTimes(1);

    await user.click(screen.getByTestId("monthly-operating-analysis-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledWith({ reportMonth: "202602" });
      expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).toHaveTextContent(/failed/);
      expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).toHaveTextContent(
        /qdb_gl_monthly_analysis_build/,
      );
      expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).toHaveTextContent(/invalid-header/);
    });
    expect(statusSpy).not.toHaveBeenCalled();
    expect(workbookSpy).toHaveBeenCalledTimes(1);
  });

  it("surfaces monthly operating analysis refresh request errors without refetching workbook", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const workbookSpy = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_qdb_workbook",
        basis: "analytical" as const,
        result_kind: "qdb-gl-monthly-analysis.workbook",
        formal_use_allowed: false,
        source_version: "sv_qdb_test",
        vendor_version: "vv_none",
        rule_version: "rv_qdb_gl_monthly_analysis_v1",
        cache_version: "cv_qdb_gl_monthly_analysis_v1",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-12T00:00:00Z",
      },
      result: {
        report_month: "202602",
        sheets: [{ key: "overview", title: "Overview", columns: ["metric"], rows: [{ metric: "loan_total" }] }],
      },
    }));
    const refreshSpy = vi.fn(async () => {
      throw new Error("Request failed: /ui/qdb-gl-monthly-analysis/refresh?report_month=202602 (500)");
    });
    const statusSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "qdb_gl_monthly_analysis:202602",
      job_name: "qdb_gl_monthly_analysis",
      trigger_mode: "terminal",
    }));
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: workbookSpy,
      refreshQdbGlMonthlyAnalysis: refreshSpy,
      getQdbGlMonthlyAnalysisRefreshStatus: statusSpy,
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));
    await screen.findByText("Overview");
    expect(workbookSpy).toHaveBeenCalledTimes(1);

    await user.click(screen.getByTestId("monthly-operating-analysis-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledWith({ reportMonth: "202602" });
      expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).toHaveTextContent(/failed/);
      expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).toHaveTextContent(/500/);
    });
    expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).not.toHaveTextContent(
      /\/ui\/qdb-gl-monthly-analysis/,
    );
    expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).not.toHaveTextContent(
      /refresh\?report_month/,
    );
    expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).not.toHaveTextContent(
      /Request failed:/,
    );
    expect(statusSpy).not.toHaveBeenCalled();
    expect(workbookSpy).toHaveBeenCalledTimes(1);
  });

  it("surfaces monthly operating analysis refresh permission errors without refetching workbook", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const workbookSpy = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_qdb_workbook",
        basis: "analytical" as const,
        result_kind: "qdb-gl-monthly-analysis.workbook",
        formal_use_allowed: false,
        source_version: "sv_qdb_test",
        vendor_version: "vv_none",
        rule_version: "rv_qdb_gl_monthly_analysis_v1",
        cache_version: "cv_qdb_gl_monthly_analysis_v1",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-12T00:00:00Z",
      },
      result: {
        report_month: "202602",
        sheets: [{ key: "overview", title: "Overview", columns: ["metric"], rows: [{ metric: "loan_total" }] }],
      },
    }));
    const refreshSpy = vi.fn(async () => {
      throw new Error("User is not allowed to refresh qdb_gl_monthly_analysis.");
    });
    const statusSpy = vi.fn(async () => ({
      status: "completed",
      run_id: "qdb_gl_monthly_analysis:202602",
      job_name: "qdb_gl_monthly_analysis",
      trigger_mode: "terminal",
    }));
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: workbookSpy,
      refreshQdbGlMonthlyAnalysis: refreshSpy,
      getQdbGlMonthlyAnalysisRefreshStatus: statusSpy,
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));
    await screen.findByText("Overview");
    expect(workbookSpy).toHaveBeenCalledTimes(1);

    await user.click(screen.getByTestId("monthly-operating-analysis-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledWith({ reportMonth: "202602" });
      expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).toHaveTextContent(/failed/);
      expect(screen.getByTestId("monthly-operating-analysis-refresh-status")).toHaveTextContent(
        /User is not allowed to refresh qdb_gl_monthly_analysis/,
      );
    });
    expect(statusSpy).not.toHaveBeenCalled();
    expect(workbookSpy).toHaveBeenCalledTimes(1);
  });

  it("exposes the full scenario threshold control set for monthly operating analysis", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const scenarioSpy = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_qdb_scenario_full",
        basis: "scenario" as const,
        result_kind: "qdb-gl-monthly-analysis.scenario",
        formal_use_allowed: false,
        source_version: "sv_qdb_test",
        vendor_version: "vv_none",
        rule_version: "rv_qdb_gl_monthly_analysis_v1",
        cache_version: "cv_qdb_gl_monthly_analysis_v1",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: true,
        generated_at: "2026-04-12T00:00:00Z",
      },
      result: {
        report_month: "202602",
        scenario_name: "threshold-stress",
        applied_overrides: {
          DEVIATION_WARN: 7,
          DEVIATION_ALERT: 13,
          DEVIATION_CRITICAL: 21,
        },
        sheets: [],
      },
    }));
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: async () => ({
        result_meta: {
          trace_id: "tr_qdb_workbook",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.workbook",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_month: "202602",
          sheets: [],
        },
      }),
      getQdbGlMonthlyAnalysisScenario: scenarioSpy,
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));

    await user.clear(screen.getByTestId("monthly-operating-analysis-scenario-warn"));
    await user.type(screen.getByTestId("monthly-operating-analysis-scenario-warn"), "7");
    await user.clear(screen.getByTestId("monthly-operating-analysis-scenario-alert"));
    await user.type(screen.getByTestId("monthly-operating-analysis-scenario-alert"), "13");
    await user.clear(screen.getByTestId("monthly-operating-analysis-scenario-critical"));
    await user.type(screen.getByTestId("monthly-operating-analysis-scenario-critical"), "21");
    await user.click(screen.getByTestId("monthly-operating-analysis-apply-scenario"));

    await waitFor(() => {
      expect(scenarioSpy).toHaveBeenCalledWith({
        reportMonth: "202602",
        scenarioName: "threshold-stress",
        deviationWarn: 7,
        deviationAlert: 13,
        deviationCritical: 21,
      });
    });
  });

  it("omits empty or invalid threshold inputs from the scenario request", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const scenarioSpy = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_qdb_scenario_optional",
        basis: "scenario" as const,
        result_kind: "qdb-gl-monthly-analysis.scenario",
        formal_use_allowed: false,
        source_version: "sv_qdb_test",
        vendor_version: "vv_none",
        rule_version: "rv_qdb_gl_monthly_analysis_v1",
        cache_version: "cv_qdb_gl_monthly_analysis_v1",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: true,
        generated_at: "2026-04-12T00:00:00Z",
      },
      result: {
        report_month: "202602",
        scenario_name: "threshold-stress",
        applied_overrides: {},
        sheets: [],
      },
    }));
    const client = {
      ...baseClient,
      getQdbGlMonthlyAnalysisDates: async () => ({
        result_meta: {
          trace_id: "tr_qdb_dates",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.dates",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: { report_months: ["202602"] },
      }),
      getQdbGlMonthlyAnalysisWorkbook: async () => ({
        result_meta: {
          trace_id: "tr_qdb_workbook",
          basis: "analytical" as const,
          result_kind: "qdb-gl-monthly-analysis.workbook",
          formal_use_allowed: false,
          source_version: "sv_qdb_test",
          vendor_version: "vv_none",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_month: "202602",
          sheets: [],
        },
      }),
      getQdbGlMonthlyAnalysisScenario: scenarioSpy,
    };

    renderBranchPageWithClient(client as ReturnType<typeof createApiClient>);

    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-branch-monthly-operating-analysis"));

    await user.clear(screen.getByTestId("monthly-operating-analysis-scenario-warn"));
    await user.clear(screen.getByTestId("monthly-operating-analysis-scenario-alert"));
    await user.type(screen.getByTestId("monthly-operating-analysis-scenario-alert"), "abc");
    await user.clear(screen.getByTestId("monthly-operating-analysis-scenario-critical"));
    await user.click(screen.getByTestId("monthly-operating-analysis-apply-scenario"));

    await waitFor(() => {
      expect(scenarioSpy).toHaveBeenCalledWith({
        reportMonth: "202602",
        scenarioName: "threshold-stress",
        deviationWarn: undefined,
        deviationAlert: undefined,
        deviationCritical: undefined,
      });
    });
  });
});
