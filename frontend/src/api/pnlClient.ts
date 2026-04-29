/**
 * P&L and Attribution domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  AdvancedAttributionSummary,
  CampisiAttributionPayload,
  CampisiEnhancedPayload,
  CampisiFourEffectsPayload,
  CampisiMaturityBucketsPayload,
  CarryRollDownPayload,
  FormalPnlRefreshPayload,
  KRDAttributionPayload,
  LedgerPnlDataPayload,
  LedgerPnlDatesPayload,
  LedgerPnlSummaryPayload,
  PnlAttributionAnalysisSummary,
  PnlAttributionPayload,
  PnlBasis,
  PnlBridgePayload,
  PnlCompositionPayload,
  PnlDataPayload,
  PnlDatesPayload,
  PnlOverviewPayload,
  ProductCategoryDatesPayload,
  ProductCategoryAttributionPayload,
  ProductCategoryManualAdjustmentExportPayload,
  ProductCategoryManualAdjustmentListPayload,
  ProductCategoryManualAdjustmentPayload,
  ProductCategoryManualAdjustmentQuery,
  ProductCategoryManualAdjustmentRequest,
  ProductCategoryPnlPayload,
  ProductCategoryRefreshPayload,
  QdbGlMonthlyAnalysisDatesPayload,
  QdbGlMonthlyAnalysisManualAdjustmentExportPayload,
  QdbGlMonthlyAnalysisManualAdjustmentListPayload,
  QdbGlMonthlyAnalysisManualAdjustmentPayload,
  QdbGlMonthlyAnalysisManualAdjustmentRequest,
  QdbGlMonthlyAnalysisScenarioPayload,
  QdbGlMonthlyAnalysisWorkbookExportPayload,
  QdbGlMonthlyAnalysisWorkbookPayload,
  SpreadAttributionPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "./contracts";

export type PnlClientMethods = {
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
  getPnlBridge: (reportDate: string) => Promise<ApiEnvelope<PnlBridgePayload>>;
  refreshFormalPnl: (reportDate?: string) => Promise<FormalPnlRefreshPayload>;
  getFormalPnlImportStatus: (runId?: string) => Promise<FormalPnlRefreshPayload>;
  getPnlAttribution: (reportDate?: string) => Promise<ApiEnvelope<PnlAttributionPayload>>;
  getVolumeRateAttribution: (options?: {
    reportDate?: string;
    compareType?: "mom" | "yoy";
  }) => Promise<ApiEnvelope<VolumeRateAttributionPayload>>;
  getTplMarketCorrelation: (options?: {
    months?: number;
  }) => Promise<ApiEnvelope<TPLMarketCorrelationPayload>>;
  getPnlCompositionBreakdown: (options?: {
    reportDate?: string;
    includeTrend?: boolean;
    trendMonths?: number;
  }) => Promise<ApiEnvelope<PnlCompositionPayload>>;
  getPnlAttributionAnalysisSummary: (
    reportDate?: string,
  ) => Promise<ApiEnvelope<PnlAttributionAnalysisSummary>>;
  getPnlCarryRollDown: (reportDate?: string) => Promise<ApiEnvelope<CarryRollDownPayload>>;
  getPnlSpreadAttribution: (options?: {
    reportDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<SpreadAttributionPayload>>;
  getPnlKrdAttribution: (options?: {
    reportDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<KRDAttributionPayload>>;
  getPnlAdvancedAttributionSummary: (
    reportDate?: string,
  ) => Promise<ApiEnvelope<AdvancedAttributionSummary>>;
  getPnlCampisiAttribution: (options?: {
    startDate?: string;
    endDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<CampisiAttributionPayload>>;
  getPnlCampisiFourEffects: (options?: {
    startDate?: string;
    endDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<CampisiFourEffectsPayload>>;
  getPnlCampisiEnhanced: (options?: {
    startDate?: string;
    endDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<CampisiEnhancedPayload>>;
  getPnlCampisiMaturityBuckets: (options?: {
    startDate?: string;
    endDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<CampisiMaturityBucketsPayload>>;
  getProductCategoryDates: () => Promise<ApiEnvelope<ProductCategoryDatesPayload>>;
  refreshProductCategoryPnl: () => Promise<ProductCategoryRefreshPayload>;
  getProductCategoryRefreshStatus: (runId: string) => Promise<ProductCategoryRefreshPayload>;
  createProductCategoryManualAdjustment: (
    payload: ProductCategoryManualAdjustmentRequest,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  getProductCategoryManualAdjustments: (
    reportDate: string,
    options?: ProductCategoryManualAdjustmentQuery,
  ) => Promise<ProductCategoryManualAdjustmentListPayload>;
  exportProductCategoryManualAdjustmentsCsv: (
    reportDate: string,
    options?: ProductCategoryManualAdjustmentQuery,
  ) => Promise<ProductCategoryManualAdjustmentExportPayload>;
  updateProductCategoryManualAdjustment: (
    adjustmentId: string,
    payload: ProductCategoryManualAdjustmentRequest,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  revokeProductCategoryManualAdjustment: (
    adjustmentId: string,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  restoreProductCategoryManualAdjustment: (
    adjustmentId: string,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  getProductCategoryPnl: (options: {
    reportDate: string;
    view: string;
    scenarioRatePct?: string;
  }) => Promise<ApiEnvelope<ProductCategoryPnlPayload>>;
  getProductCategoryAttribution: (options: {
    reportDate: string;
    compare?: "mom" | "yoy";
  }) => Promise<ApiEnvelope<ProductCategoryAttributionPayload>>;
  getQdbGlMonthlyAnalysisDates: () => Promise<ApiEnvelope<QdbGlMonthlyAnalysisDatesPayload>>;
  getQdbGlMonthlyAnalysisWorkbook: (options: {
    reportMonth: string;
  }) => Promise<ApiEnvelope<QdbGlMonthlyAnalysisWorkbookPayload>>;
  exportQdbGlMonthlyAnalysisWorkbookXlsx: (options: {
    reportMonth: string;
  }) => Promise<QdbGlMonthlyAnalysisWorkbookExportPayload>;
  refreshQdbGlMonthlyAnalysis: (options: {
    reportMonth: string;
  }) => Promise<{ status: string; run_id: string; job_name: string; trigger_mode: string; cache_key?: string; report_month?: string }>;
  getQdbGlMonthlyAnalysisRefreshStatus: (runId: string) => Promise<{ status: string; run_id: string; job_name: string; trigger_mode: string; cache_key?: string }>;
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
