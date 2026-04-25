/**
 * Market Data domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroRefreshPayload,
  ChoiceNewsEventsPayload,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  MacroBondLinkagePayload,
  MacroVendorPayload,
  NcdFundingProxyPayload,
  SourcePreviewHistoryPayload,
  SourcePreviewPayload,
  SourcePreviewRefreshPayload,
  SourcePreviewRowsPayload,
  SourcePreviewTracesPayload,
} from "./contracts";

export type MarketDataClientMethods = {
  getSourceFoundation: () => Promise<ApiEnvelope<SourcePreviewPayload>>;
  refreshSourcePreview: () => Promise<SourcePreviewRefreshPayload>;
  getSourcePreviewRefreshStatus: (runId: string) => Promise<SourcePreviewRefreshPayload>;
  getSourceFoundationHistory: (options: {
    sourceFamily?: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewHistoryPayload>>;
  getSourceFoundationRows: (options: {
    sourceFamily: string;
    ingestBatchId: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewRowsPayload>>;
  getSourceFoundationTraces: (options: {
    sourceFamily: string;
    ingestBatchId: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewTracesPayload>>;
  getMacroFoundation: () => Promise<ApiEnvelope<MacroVendorPayload>>;
  getChoiceMacroLatest: () => Promise<ApiEnvelope<ChoiceMacroLatestPayload>>;
  getMacroBondLinkageAnalysis: (options: {
    reportDate: string;
  }) => Promise<ApiEnvelope<MacroBondLinkagePayload>>;
  getNcdFundingProxy: () => Promise<ApiEnvelope<NcdFundingProxyPayload>>;
  getFxFormalStatus: () => Promise<ApiEnvelope<FxFormalStatusPayload>>;
  getFxAnalytical: () => Promise<ApiEnvelope<FxAnalyticalPayload>>;
  refreshChoiceMacro: (backfillDays?: number) => Promise<ChoiceMacroRefreshPayload>;
  getChoiceMacroRefreshStatus: (runId: string) => Promise<ChoiceMacroRefreshPayload>;
  getChoiceNewsEvents: (options: {
    limit: number;
    offset: number;
    groupId?: string;
    topicCode?: string;
    errorOnly?: boolean;
    receivedFrom?: string;
    receivedTo?: string;
  }) => Promise<ApiEnvelope<ChoiceNewsEventsPayload>>;
  ingestTushareNprNews: (options?: { limit?: number }) => Promise<{
    status: string;
    inserted: number;
    skipped_duplicates: number;
    fetched: number;
    npr: { inserted: number; skipped_duplicates: number; fetched: number };
    news: { inserted: number; skipped_duplicates: number; fetched: number; src: string; error?: string };
  }>;
};
