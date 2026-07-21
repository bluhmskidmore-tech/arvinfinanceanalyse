/**
 * Formal, Ledger, and Bridge P&L client slice.
 * Imported by client.ts for ApiClient composition.
 */
import type {
  ApiEnvelope,
  FormalPnlRefreshPayload,
  LedgerPnlAccountDetailPayload,
  LedgerPnlDataPayload,
  LedgerPnlDatesPayload,
  LedgerPnlAnalysisPayload,
  LedgerPnlCandidateFinancialIndicatorsPayload,
  LedgerPnlCandidateFinancialIndicatorsEnvelope,
  LedgerPnlCandidateFinancialIndicatorComponentDetail,
  LedgerPnlCandidateFinancialIndicatorComponentMetricId,
  LedgerPnlCandidateFinancialIndicatorPeriodComparison,
  LedgerPnlCandidateFinancialIndicatorRevalidationReceipt,
  LedgerPnlCandidateFinancialIndicatorRevalidationRequest,
  LedgerPnlFormalFinancialIndicatorContractPayload,
  LedgerPnlFormalIndicatorRuleChecksPayload,
  LedgerPnlSummaryPayload,
  PnlBasis,
  PnlBridgePayload,
  PnlDataPayload,
  PnlDatesPayload,
  PnlOverviewPayload,
  QdbGlMonthlyAnalysisDatesPayload,
  QdbGlMonthlyAnalysisWorkbookPayload,
} from "./contracts";

export type PnlCoreClientMethods = {
  getFormalPnlDates: (basis?: PnlBasis) => Promise<ApiEnvelope<PnlDatesPayload>>;
  getFormalPnlData: (date: string, basis?: PnlBasis) => Promise<ApiEnvelope<PnlDataPayload>>;
  getFormalPnlOverview: (
    reportDate: string,
    basis?: PnlBasis,
  ) => Promise<ApiEnvelope<PnlOverviewPayload>>;
  getLedgerPnlDates: () => Promise<ApiEnvelope<LedgerPnlDatesPayload>>;
  getLedgerPnlData: (
    reportDate: string,
    currency?: string,
  ) => Promise<ApiEnvelope<LedgerPnlDataPayload>>;
  getLedgerPnlSummary: (
    reportDate: string,
    currency?: string,
  ) => Promise<ApiEnvelope<LedgerPnlSummaryPayload>>;
  getLedgerPnlAnalysis: (
    reportDate: string,
    currency?: string,
  ) => Promise<ApiEnvelope<LedgerPnlAnalysisPayload>>;
  getLedgerPnlAccountDetail: (
    reportDate: string,
    accountCode: string,
    currency?: string,
  ) => Promise<ApiEnvelope<LedgerPnlAccountDetailPayload>>;
  getLedgerPnlFormalFinancialIndicators: (
    reportMonth: string,
  ) => Promise<ApiEnvelope<LedgerPnlFormalFinancialIndicatorContractPayload>>;
  getLedgerPnlCandidateFinancialIndicators: (
    reportMonth: string,
    options?: { includeLineage?: boolean; metricId?: string },
  ) => Promise<LedgerPnlCandidateFinancialIndicatorsEnvelope>;
  getLedgerPnlCandidateFinancialIndicatorPeriodComparison: (
    reportMonth: string,
    options?: { signal?: AbortSignal },
  ) => Promise<LedgerPnlCandidateFinancialIndicatorPeriodComparison>;
  getLedgerPnlCandidateFinancialIndicatorComponentDetail: (
    reportMonth: string,
    metricId: LedgerPnlCandidateFinancialIndicatorComponentMetricId,
    parentIdempotencyKey: string,
    options?: { signal?: AbortSignal },
  ) => Promise<LedgerPnlCandidateFinancialIndicatorComponentDetail>;
  revalidateLedgerPnlCandidateFinancialIndicators: (
    reportMonth: string,
    request: LedgerPnlCandidateFinancialIndicatorRevalidationRequest,
  ) => Promise<LedgerPnlCandidateFinancialIndicatorRevalidationReceipt>;
  getLedgerPnlFormalIndicatorRuleChecks: (
    reportMonth: string,
  ) => Promise<ApiEnvelope<LedgerPnlFormalIndicatorRuleChecksPayload>>;
  getLedgerPnlMonthlyAnalysisDates: () => Promise<ApiEnvelope<QdbGlMonthlyAnalysisDatesPayload>>;
  getLedgerPnlMonthlyAnalysisWorkbook: (options: {
    reportMonth: string;
  }) => Promise<ApiEnvelope<QdbGlMonthlyAnalysisWorkbookPayload>>;
  getPnlBridge: (reportDate: string) => Promise<ApiEnvelope<PnlBridgePayload>>;
  refreshFormalPnl: (reportDate?: string) => Promise<FormalPnlRefreshPayload>;
  getFormalPnlImportStatus: (runId?: string) => Promise<FormalPnlRefreshPayload>;
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

export type PnlCoreClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
  requestActionJson: RequestActionJson;
};

function buildPnlBasisQuerySegment(basis?: PnlBasis) {
  return basis && basis !== "formal" ? `&basis=${encodeURIComponent(basis)}` : "";
}

export function createRealPnlCoreClient(
  options: PnlCoreClientFactoryOptions,
): PnlCoreClientMethods {
  const { fetchImpl, baseUrl, requestJson, requestActionJson } = options;

  return {
    getFormalPnlDates: (basis = "formal") =>
      requestJson<PnlDatesPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/dates${basis !== "formal" ? `?basis=${encodeURIComponent(basis)}` : ""}`,
      ),
    getFormalPnlData: (date: string, basis = "formal") =>
      requestJson<PnlDataPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/data?date=${encodeURIComponent(date)}${buildPnlBasisQuerySegment(basis)}`,
      ),
    getFormalPnlOverview: (reportDate: string, basis = "formal") =>
      requestJson<PnlOverviewPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/overview?report_date=${encodeURIComponent(reportDate)}${buildPnlBasisQuerySegment(basis)}`,
      ),
    getLedgerPnlDates: () =>
      requestJson<LedgerPnlDatesPayload>(fetchImpl, baseUrl, "/api/ledger-pnl/dates"),
    getLedgerPnlData: (reportDate: string, currency?: string) => {
      const params = new URLSearchParams({
        date: reportDate,
      });
      if (currency?.trim()) {
        params.set("currency", currency.trim());
      }
      return requestJson<LedgerPnlDataPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/data?${params.toString()}`,
      );
    },
    getLedgerPnlSummary: (reportDate: string, currency?: string) => {
      const params = new URLSearchParams({
        date: reportDate,
      });
      if (currency?.trim()) {
        params.set("currency", currency.trim());
      }
      return requestJson<LedgerPnlSummaryPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/summary?${params.toString()}`,
      );
    },
    getLedgerPnlAnalysis: (reportDate: string, currency?: string) => {
      const params = new URLSearchParams({
        date: reportDate,
      });
      if (currency?.trim()) {
        params.set("currency", currency.trim());
      }
      return requestJson<LedgerPnlAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/analysis?${params.toString()}`,
      );
    },
    getLedgerPnlAccountDetail: (
      reportDate: string,
      accountCode: string,
      currency?: string,
    ) => {
      const params = new URLSearchParams({
        date: reportDate,
        account_code: accountCode,
      });
      if (currency?.trim()) {
        params.set("currency", currency.trim());
      }
      return requestJson<LedgerPnlAccountDetailPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/account-detail?${params.toString()}`,
      );
    },
    getLedgerPnlFormalFinancialIndicators: (reportMonth: string) => {
      const params = new URLSearchParams({
        report_month: reportMonth.trim(),
      });
      return requestJson<LedgerPnlFormalFinancialIndicatorContractPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/formal-financial-indicators?${params.toString()}`,
      );
    },
    getLedgerPnlCandidateFinancialIndicators: (reportMonth, options = {}) => {
      const params = new URLSearchParams({
        report_month: reportMonth.trim(),
      });
      if (options.includeLineage) {
        params.set("include_lineage", "true");
      }
      if (options.metricId?.trim()) {
        params.set("metric_id", options.metricId.trim());
      }
      return requestJson<LedgerPnlCandidateFinancialIndicatorsPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/candidate-financial-indicators?${params.toString()}`,
      ) as Promise<LedgerPnlCandidateFinancialIndicatorsEnvelope>;
    },
    getLedgerPnlCandidateFinancialIndicatorPeriodComparison: (reportMonth, options = {}) =>
      requestActionJson<LedgerPnlCandidateFinancialIndicatorPeriodComparison>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/candidate-financial-indicators/period-comparison?report_month=${encodeURIComponent(reportMonth.trim())}`,
        { signal: options.signal },
      ),
    getLedgerPnlCandidateFinancialIndicatorComponentDetail: (
      reportMonth,
      metricId,
      parentIdempotencyKey,
      options = {},
    ) => {
      const params = new URLSearchParams({
        report_month: reportMonth.trim(),
        metric_id: metricId.trim(),
        parent_idempotency_key: parentIdempotencyKey.trim(),
      });
      return requestActionJson<LedgerPnlCandidateFinancialIndicatorComponentDetail>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/candidate-financial-indicators/period-comparison/component-detail?${params.toString()}`,
        { signal: options.signal },
      );
    },
    revalidateLedgerPnlCandidateFinancialIndicators: (reportMonth, request) =>
      requestActionJson<LedgerPnlCandidateFinancialIndicatorRevalidationReceipt>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/candidate-financial-indicators/revalidate?report_month=${encodeURIComponent(reportMonth.trim())}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request),
        },
      ),
    getLedgerPnlFormalIndicatorRuleChecks: (reportMonth: string) => {
      const params = new URLSearchParams({
        report_month: reportMonth.trim(),
      });
      return requestJson<LedgerPnlFormalIndicatorRuleChecksPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/formal-indicator-rule-checks?${params.toString()}`,
      );
    },
    getLedgerPnlMonthlyAnalysisDates: () =>
      requestJson<QdbGlMonthlyAnalysisDatesPayload>(
        fetchImpl,
        baseUrl,
        "/api/ledger-pnl/monthly-analysis/dates",
      ),
    getLedgerPnlMonthlyAnalysisWorkbook: ({ reportMonth }) =>
      requestJson<QdbGlMonthlyAnalysisWorkbookPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/monthly-analysis/workbook?report_month=${encodeURIComponent(reportMonth.trim())}`,
      ),
    getPnlBridge: (reportDate: string) =>
      requestJson<PnlBridgePayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/bridge?report_date=${encodeURIComponent(reportDate)}`,
      ),
    refreshFormalPnl: (reportDate?: string) =>
      requestActionJson<FormalPnlRefreshPayload>(
        fetchImpl,
        baseUrl,
        reportDate
          ? `/api/data/refresh_pnl?report_date=${encodeURIComponent(reportDate)}`
          : "/api/data/refresh_pnl",
        {
          method: "POST",
        },
      ),
    getFormalPnlImportStatus: (runId?: string) =>
      requestActionJson<FormalPnlRefreshPayload>(
        fetchImpl,
        baseUrl,
        runId
          ? `/api/data/import_status/pnl?run_id=${encodeURIComponent(runId)}`
          : "/api/data/import_status/pnl",
      ),
  };
}
