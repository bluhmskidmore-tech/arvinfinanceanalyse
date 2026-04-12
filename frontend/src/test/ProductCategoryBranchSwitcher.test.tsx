import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { routerFuture } from "../router/routerFuture";
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
          sheets: [
            {
              key: "overview",
              title: "Overview",
              columns: ["metric", "value"],
              rows: [{ metric: "loan_total", value: 1000 }],
            },
            {
              key: "alerts",
              title: "Alerts",
              columns: ["account_code", "alert_type"],
              rows: [{ account_code: "14001000001", alert_type: "suspicious" }],
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
      expect(screen.getByRole("heading", { name: "Monthly Operating Analysis" })).toBeInTheDocument();
      expect(screen.getByText("Overview")).toBeInTheDocument();
      expect(screen.getByText("Alerts")).toBeInTheDocument();
      expect(screen.queryByTestId("product-category-table")).not.toBeInTheDocument();
    });
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
      expect(screen.getByText("Scenario Alerts")).toBeInTheDocument();
    });
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
