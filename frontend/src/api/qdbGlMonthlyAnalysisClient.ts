/**
 * QDB GL Monthly Analysis client slice.
 * Imported by client.ts for ApiClient composition.
 */
import type {
  ApiEnvelope,
  QdbGlMonthlyAnalysisDatesPayload,
  QdbGlMonthlyAnalysisManualAdjustmentExportPayload,
  QdbGlMonthlyAnalysisManualAdjustmentListPayload,
  QdbGlMonthlyAnalysisManualAdjustmentPayload,
  QdbGlMonthlyAnalysisManualAdjustmentRequest,
  QdbGlMonthlyAnalysisScenarioPayload,
  QdbGlMonthlyAnalysisWorkbookExportPayload,
  QdbGlMonthlyAnalysisWorkbookPayload,
} from "./contracts";

export type QdbGlMonthlyAnalysisRefreshPayload = {
  status: string;
  run_id: string;
  job_name: string;
  trigger_mode: string;
  cache_key?: string;
  report_month?: string;
};

export type QdbGlMonthlyAnalysisClientMethods = {
  getQdbGlMonthlyAnalysisDates: () => Promise<ApiEnvelope<QdbGlMonthlyAnalysisDatesPayload>>;
  getQdbGlMonthlyAnalysisWorkbook: (options: {
    reportMonth: string;
  }) => Promise<ApiEnvelope<QdbGlMonthlyAnalysisWorkbookPayload>>;
  exportQdbGlMonthlyAnalysisWorkbookXlsx: (options: {
    reportMonth: string;
  }) => Promise<QdbGlMonthlyAnalysisWorkbookExportPayload>;
  refreshQdbGlMonthlyAnalysis: (options: {
    reportMonth: string;
  }) => Promise<QdbGlMonthlyAnalysisRefreshPayload>;
  getQdbGlMonthlyAnalysisRefreshStatus: (
    runId: string,
  ) => Promise<QdbGlMonthlyAnalysisRefreshPayload>;
  getQdbGlMonthlyAnalysisScenario: (options: {
    reportMonth: string;
    scenarioName: string;
    deviationWarn?: number;
    deviationAlert?: number;
    deviationCritical?: number;
  }) => Promise<ApiEnvelope<QdbGlMonthlyAnalysisScenarioPayload>>;
  createQdbGlMonthlyAnalysisManualAdjustment: (
    payload: QdbGlMonthlyAnalysisManualAdjustmentRequest,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentPayload>;
  updateQdbGlMonthlyAnalysisManualAdjustment: (
    adjustmentId: string,
    payload: QdbGlMonthlyAnalysisManualAdjustmentRequest,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentPayload>;
  revokeQdbGlMonthlyAnalysisManualAdjustment: (
    adjustmentId: string,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentPayload>;
  restoreQdbGlMonthlyAnalysisManualAdjustment: (
    adjustmentId: string,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentPayload>;
  getQdbGlMonthlyAnalysisManualAdjustments: (
    reportMonth: string,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentListPayload>;
  exportQdbGlMonthlyAnalysisManualAdjustmentsCsv: (
    reportMonth: string,
  ) => Promise<QdbGlMonthlyAnalysisManualAdjustmentExportPayload>;
};

type FetchLike = typeof fetch;
type Delay = () => Promise<void>;

type QdbGlMonthlyAnalysisMockBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

type EnsureQdbGlMonthlyAnalysisMockBundle = () => Promise<QdbGlMonthlyAnalysisMockBundle>;

type RequestJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
) => Promise<ApiEnvelope<T>>;

type RequestActionJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
) => Promise<T>;

type RequestText = (
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  fallbackFilename?: string,
) => Promise<{ content: string; filename: string }>;

type RequestBlob = (
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  fallbackFilename?: string,
) => Promise<{ content: Blob; filename: string }>;

type RequestActionWithBody = <TResponse, TBody>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  body: TBody,
) => Promise<TResponse>;

export type QdbGlMonthlyAnalysisClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
  requestActionJson: RequestActionJson;
  requestText: RequestText;
  requestBlob: RequestBlob;
  requestActionWithBody: RequestActionWithBody;
};

function isFiniteNumber(value: number | undefined): value is number {
  return value !== undefined && Number.isFinite(value);
}

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

export function createRealQdbGlMonthlyAnalysisClient(
  options: QdbGlMonthlyAnalysisClientFactoryOptions,
): QdbGlMonthlyAnalysisClientMethods {
  const {
    fetchImpl,
    baseUrl,
    requestJson,
    requestActionJson,
    requestText,
    requestBlob,
    requestActionWithBody,
  } = options;

  return {
    getQdbGlMonthlyAnalysisDates: () =>
      requestJson<QdbGlMonthlyAnalysisDatesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/qdb-gl-monthly-analysis/dates",
      ),
    getQdbGlMonthlyAnalysisWorkbook: ({ reportMonth }) =>
      requestJson<QdbGlMonthlyAnalysisWorkbookPayload>(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/workbook?report_month=${encodeURIComponent(reportMonth)}`,
      ),
    exportQdbGlMonthlyAnalysisWorkbookXlsx: ({ reportMonth }) =>
      requestBlob(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/workbook/export?report_month=${encodeURIComponent(reportMonth)}`,
        "qdb-gl-monthly-analysis.xlsx",
      ),
    refreshQdbGlMonthlyAnalysis: ({ reportMonth }) =>
      requestActionJson<QdbGlMonthlyAnalysisRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/refresh?report_month=${encodeURIComponent(reportMonth)}`,
        { method: "POST" },
      ),
    getQdbGlMonthlyAnalysisRefreshStatus: (runId) =>
      requestActionJson<QdbGlMonthlyAnalysisRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    getQdbGlMonthlyAnalysisScenario: ({
      reportMonth,
      scenarioName,
      deviationWarn,
      deviationAlert,
      deviationCritical,
    }) => {
      const params = new URLSearchParams({
        report_month: reportMonth,
        scenario_name: scenarioName,
      });
      if (isFiniteNumber(deviationWarn)) {
        params.set("deviation_warn", String(deviationWarn));
      }
      if (isFiniteNumber(deviationAlert)) {
        params.set("deviation_alert", String(deviationAlert));
      }
      if (isFiniteNumber(deviationCritical)) {
        params.set("deviation_critical", String(deviationCritical));
      }
      return requestJson<QdbGlMonthlyAnalysisScenarioPayload>(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/scenario?${params.toString()}`,
      );
    },
    createQdbGlMonthlyAnalysisManualAdjustment: (payload) =>
      requestActionWithBody<
        QdbGlMonthlyAnalysisManualAdjustmentPayload,
        QdbGlMonthlyAnalysisManualAdjustmentRequest
      >(
        fetchImpl,
        baseUrl,
        "/ui/qdb-gl-monthly-analysis/manual-adjustments",
        payload,
      ),
    updateQdbGlMonthlyAnalysisManualAdjustment: (adjustmentId, payload) =>
      requestActionWithBody<
        QdbGlMonthlyAnalysisManualAdjustmentPayload,
        QdbGlMonthlyAnalysisManualAdjustmentRequest
      >(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments/${encodeURIComponent(adjustmentId)}/edit`,
        payload,
      ),
    revokeQdbGlMonthlyAnalysisManualAdjustment: (adjustmentId) =>
      requestActionJson<QdbGlMonthlyAnalysisManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments/${encodeURIComponent(adjustmentId)}/revoke`,
        { method: "POST" },
      ),
    restoreQdbGlMonthlyAnalysisManualAdjustment: (adjustmentId) =>
      requestActionJson<QdbGlMonthlyAnalysisManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments/${encodeURIComponent(adjustmentId)}/restore`,
        { method: "POST" },
      ),
    getQdbGlMonthlyAnalysisManualAdjustments: (reportMonth) =>
      requestActionJson<QdbGlMonthlyAnalysisManualAdjustmentListPayload>(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments?report_month=${encodeURIComponent(reportMonth)}`,
      ),
    exportQdbGlMonthlyAnalysisManualAdjustmentsCsv: (reportMonth) =>
      requestText(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments/export?report_month=${encodeURIComponent(reportMonth)}`,
        "monthly-operating-analysis-audit.csv",
      ),
  };
}
