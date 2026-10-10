/**
 * Balance Analysis domain client slice.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import { createRealBalanceAnalysisOverviewClient } from "./balanceAnalysisOverviewClient";
import type {
  ApiEnvelope,
  BalanceAnalysisCurrentUserPayload,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisDecisionStatus,
  BalanceAnalysisDecisionStatusRecord,
  BalanceAnalysisOverviewPayload,
  BalanceAnalysisPublicationStatusPayload,
  BalanceAnalysisDatesPayload,
  BalanceCurrencyBasis,
  BalanceAnalysisAdvancedAttributionBundlePayload,
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisPayload,
  BalanceAnalysisWorkbookPayload,
  BalancePositionScope,
  BalanceAnalysisRefreshPayload,
  BalanceAnalysisSummaryExportPayload,
  BalanceAnalysisWorkbookExportPayload,
  BalanceAnalysisSummaryTablePayload,
} from "./contracts";
import type { TransportRequestOptions } from "./transport";

export type BalanceAnalysisClientMethods = {
  getBalanceAnalysisDates: () => Promise<ApiEnvelope<BalanceAnalysisDatesPayload>>;
  getBalanceAnalysisPublicationStatus: () => Promise<BalanceAnalysisPublicationStatusPayload>;
  getBalanceAnalysisOverview: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
    generation?: string;
  }) => Promise<ApiEnvelope<BalanceAnalysisOverviewPayload>>;
  getBalanceAnalysisSummary: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<BalanceAnalysisSummaryTablePayload>>;
  getBalanceAnalysisWorkbook: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisWorkbookPayload>>;
  getBalanceAnalysisCurrentUser: () => Promise<BalanceAnalysisCurrentUserPayload>;
  getBalanceAnalysisDecisionItems: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisDecisionItemsPayload>>;
  updateBalanceAnalysisDecisionStatus: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
    decisionKey: string;
    status: BalanceAnalysisDecisionStatus;
    comment?: string;
  }) => Promise<BalanceAnalysisDecisionStatusRecord>;
  getBalanceAnalysisDetail: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisPayload>>;
  getBalanceAnalysisSummaryByBasis: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
    generation?: string;
  }) => Promise<ApiEnvelope<BalanceAnalysisBasisBreakdownPayload>>;
  getBalanceAnalysisAdvancedAttribution: (options: {
    reportDate: string;
    scenarioName?: string;
    treasuryShiftBp?: number;
    spreadShiftBp?: number;
  }) => Promise<ApiEnvelope<BalanceAnalysisAdvancedAttributionBundlePayload>>;
  exportBalanceAnalysisSummaryCsv: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<BalanceAnalysisSummaryExportPayload>;
  exportBalanceAnalysisWorkbookXlsx: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<BalanceAnalysisWorkbookExportPayload>;
  refreshBalanceAnalysis: (reportDate: string) => Promise<BalanceAnalysisRefreshPayload>;
  getBalanceAnalysisRefreshStatus: (
    runId: string,
  ) => Promise<BalanceAnalysisRefreshPayload>;
};

type FetchLike = typeof fetch;

type RequestJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  options?: TransportRequestOptions,
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

export type BalanceAnalysisClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
  requestActionJson: RequestActionJson;
  requestText: RequestText;
  requestBlob: RequestBlob;
};

export function createRealBalanceAnalysisClient(
  options: BalanceAnalysisClientFactoryOptions,
): BalanceAnalysisClientMethods {
  const { fetchImpl, baseUrl, requestJson, requestActionJson, requestText, requestBlob } = options;

  return {
    getBalanceAnalysisDates: () =>
      requestJson<BalanceAnalysisDatesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/dates",
        { keyFields: [{ path: "report_dates", type: "array" }] },
      ),
    getBalanceAnalysisPublicationStatus: () =>
      requestActionJson<BalanceAnalysisPublicationStatusPayload>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/publication-status",
      ),
    ...createRealBalanceAnalysisOverviewClient({ fetchImpl, baseUrl, requestJson }),
    getBalanceAnalysisSummary: ({
      reportDate,
      positionScope,
      currencyBasis,
      limit,
      offset,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
        limit: String(limit),
        offset: String(offset),
      });
      return requestJson<BalanceAnalysisSummaryTablePayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/summary?${params.toString()}`,
      );
    },
    getBalanceAnalysisWorkbook: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisWorkbookPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/workbook?${params.toString()}`,
      );
    },
    getBalanceAnalysisCurrentUser: () =>
      requestActionJson<BalanceAnalysisCurrentUserPayload>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/current-user",
      ),
    getBalanceAnalysisDecisionItems: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisDecisionItemsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/decision-items?${params.toString()}`,
      );
    },
    updateBalanceAnalysisDecisionStatus: ({
      reportDate,
      positionScope,
      currencyBasis,
      decisionKey,
      status,
      comment,
    }) =>
      requestActionJson<BalanceAnalysisDecisionStatusRecord>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/decision-items/status",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            report_date: reportDate,
            position_scope: positionScope,
            currency_basis: currencyBasis,
            decision_key: decisionKey,
            status,
            comment,
          }),
        },
      ),
    getBalanceAnalysisDetail: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis?${params.toString()}`,
      );
    },
    getBalanceAnalysisSummaryByBasis: ({ reportDate, positionScope, currencyBasis, generation }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      if (generation) {
        params.set("generation", generation);
      }
      return requestJson<BalanceAnalysisBasisBreakdownPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/summary-by-basis?${params.toString()}`,
      );
    },
    getBalanceAnalysisAdvancedAttribution: ({
      reportDate,
      scenarioName,
      treasuryShiftBp,
      spreadShiftBp,
    }) => {
      const params = new URLSearchParams({ report_date: reportDate });
      if (scenarioName) {
        params.set("scenario_name", scenarioName);
      }
      if (treasuryShiftBp !== undefined) {
        params.set("treasury_shift_bp", String(treasuryShiftBp));
      }
      if (spreadShiftBp !== undefined) {
        params.set("spread_shift_bp", String(spreadShiftBp));
      }
      return requestJson<BalanceAnalysisAdvancedAttributionBundlePayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/advanced-attribution?${params.toString()}`,
      );
    },
    exportBalanceAnalysisSummaryCsv: ({
      reportDate,
      positionScope,
      currencyBasis,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestText(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/summary/export?${params.toString()}`,
        "balance-analysis-summary.csv",
      );
    },
    exportBalanceAnalysisWorkbookXlsx: ({
      reportDate,
      positionScope,
      currencyBasis,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestBlob(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/workbook/export?${params.toString()}`,
        "balance-analysis-workbook.xlsx",
      );
    },
    refreshBalanceAnalysis: (reportDate: string) =>
      requestActionJson<BalanceAnalysisRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/refresh?report_date=${encodeURIComponent(reportDate)}`,
        {
          method: "POST",
        },
      ),
    getBalanceAnalysisRefreshStatus: (runId: string) =>
      requestActionJson<BalanceAnalysisRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),  };
}
