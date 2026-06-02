/**
 * Balance Analysis domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  BalanceAnalysisCurrentUserPayload,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisDecisionStatus,
  BalanceAnalysisDecisionStatusRecord,
  BalanceAnalysisOverviewPayload,
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

export type BalanceAnalysisClientMethods = {
  getBalanceAnalysisDates: () => Promise<ApiEnvelope<BalanceAnalysisDatesPayload>>;
  getBalanceAnalysisOverview: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
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
