/**
 * Demo/mock QdbGlMonthlyAnalysis client.
 * Loaded only by mock composition paths and tests.
 */
import type { QdbGlMonthlyAnalysisClientMethods } from "../api/qdbGlMonthlyAnalysisClient";
type Delay = () => Promise<void>;

type QdbGlMonthlyAnalysisMockBundle = Pick<
  typeof import("./mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

type EnsureQdbGlMonthlyAnalysisMockBundle = () => Promise<QdbGlMonthlyAnalysisMockBundle>;

export function createDemoQdbGlMonthlyAnalysisClient(
  delay: Delay,
  ensureMockClientBundle: EnsureQdbGlMonthlyAnalysisMockBundle,
): QdbGlMonthlyAnalysisClientMethods {
  return {
    async getQdbGlMonthlyAnalysisDates() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "qdb-gl-monthly-analysis.dates",
        { report_months: [] },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_qdb_gl_mock",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
        },
      );
    },
    async getQdbGlMonthlyAnalysisWorkbook({ reportMonth }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "qdb-gl-monthly-analysis.workbook",
        { report_month: reportMonth, sheets: [] },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_qdb_gl_mock",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
        },
      );
    },
    async exportQdbGlMonthlyAnalysisWorkbookXlsx({ reportMonth }) {
      await delay();
      return {
        filename: `analysis_report_${reportMonth}.xlsx`,
        content: new Blob(["mock-qdb-workbook"], {
          type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }),
      };
    },
    async refreshQdbGlMonthlyAnalysis({ reportMonth }) {
      await delay();
      return {
        status: "completed",
        run_id: `qdb_gl_monthly_analysis:${reportMonth}`,
        job_name: "qdb_gl_monthly_analysis",
        trigger_mode: "sync",
        cache_key: "qdb_gl_monthly_analysis.analytical",
        report_month: reportMonth,
      };
    },
    async getQdbGlMonthlyAnalysisRefreshStatus(runId) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "qdb_gl_monthly_analysis",
        trigger_mode: "terminal",
        cache_key: "qdb_gl_monthly_analysis.analytical",
      };
    },
    async getQdbGlMonthlyAnalysisScenario({
      reportMonth,
      scenarioName,
      deviationWarn,
      deviationAlert,
      deviationCritical,
    }) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "qdb-gl-monthly-analysis.scenario",
        {
          report_month: reportMonth,
          scenario_name: scenarioName,
          applied_overrides: {
            ...(deviationWarn === undefined ? {} : { DEVIATION_WARN: deviationWarn }),
            ...(deviationAlert === undefined ? {} : { DEVIATION_ALERT: deviationAlert }),
            ...(deviationCritical === undefined ? {} : { DEVIATION_CRITICAL: deviationCritical }),
          },
          sheets: [],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_qdb_gl_mock",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
        },
      );
    },
    async createQdbGlMonthlyAnalysisManualAdjustment(payload) {
      await delay();
      return {
        adjustment_id: "moa-mock-1",
        event_type: "created",
        created_at: "2026-04-12T00:00:00Z",
        stream: "monthly_operating_analysis_adjustments",
        ...payload,
      };
    },
    async updateQdbGlMonthlyAnalysisManualAdjustment(adjustmentId, payload) {
      await delay();
      return {
        adjustment_id: adjustmentId,
        event_type: "edited",
        created_at: "2026-04-12T00:10:00Z",
        stream: "monthly_operating_analysis_adjustments",
        ...payload,
      };
    },
    async revokeQdbGlMonthlyAnalysisManualAdjustment(adjustmentId) {
      await delay();
      return {
        adjustment_id: adjustmentId,
        event_type: "revoked",
        created_at: "2026-04-12T00:20:00Z",
        stream: "monthly_operating_analysis_adjustments",
        report_month: "202602",
        adjustment_class: "analysis_adjustment",
        target: {},
        operator: "OVERRIDE",
        value: "",
        approval_status: "rejected",
      };
    },
    async restoreQdbGlMonthlyAnalysisManualAdjustment(adjustmentId) {
      await delay();
      return {
        adjustment_id: adjustmentId,
        event_type: "restored",
        created_at: "2026-04-12T00:30:00Z",
        stream: "monthly_operating_analysis_adjustments",
        report_month: "202602",
        adjustment_class: "analysis_adjustment",
        target: {},
        operator: "OVERRIDE",
        value: "",
        approval_status: "approved",
      };
    },
    async getQdbGlMonthlyAnalysisManualAdjustments(reportMonth) {
      await delay();
      return {
        report_month: reportMonth,
        adjustment_count: 0,
        adjustments: [],
        events: [],
      };
    },
    async exportQdbGlMonthlyAnalysisManualAdjustmentsCsv(reportMonth) {
      await delay();
      return {
        filename: `monthly-operating-analysis-audit-${reportMonth}.csv`,
        content: "adjustment_id,event_type\n",
      };
    },
  };
}
