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

export type QdbGlMonthlyAnalysisComparisonMonthStatus = {
  report_month?: string;
  status?: string;
  [key: string]: unknown;
};

export type QdbGlMonthlyAnalysisRefreshPayload = {
  status: string;
  run_id: string;
  job_name: string;
  trigger_mode: string;
  cache_key?: string;
  report_month?: string;
  report_date?: string;
  resolved_report_date?: string;
  source_version?: string;
  sheet_count?: number;
  tables_used?: string[];
  evidence_rows?: number;
  comparison_months?: Record<string, QdbGlMonthlyAnalysisComparisonMonthStatus>;
  failure_category?: string;
  failure_reason?: string;
  error_message?: string;
  idempotency_key?: string | null;
  idempotency_replay?: boolean;
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
