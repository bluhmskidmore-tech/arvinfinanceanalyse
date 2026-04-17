import {
  createContext,
  createElement,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

import type {
  AlertsPayload,
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
  BondPositionItem,
  BondAnalyticsDatesPayload,
  BondAnalyticsRefreshPayload,
  BondPortfolioHeadlinesPayload,
  BondTopHoldingsPayload,
  BenchmarkExcessPayload,
  BalanceAnalysisSummaryExportPayload,
  BalanceAnalysisWorkbookExportPayload,
  BalanceAnalysisSummaryTablePayload,
  AssetStructurePayload,
  BalanceAnalysisTableRow,
  BondDashboardHeadlinePayload,
  CreditSpreadAnalysisPayload,
  CreditSpreadMigrationPayload,
  ActionAttributionPayload,
  AccountingClassAuditPayload,
  AdvancedAttributionSummary,
  CampisiAttributionPayload,
  CampisiEnhancedPayload,
  CampisiFourEffectsPayload,
  CampisiMaturityBucketsPayload,
  CashflowProjectionPayload,
  CarryRollDownPayload,
  KRDCurveRiskPayload,
  KRDAttributionPayload,
  ChoiceMacroLatestPayload,
  ChoiceMacroRecentPoint,
  ChoiceNewsEventsPayload,
  ContributionPayload,
  CounterpartyStatsResponse,
  CubeDimensionsPayload,
  CubeQueryRequest,
  CubeQueryResult,
  CustomerBalanceTrendResponse,
  AdbComparisonResponse,
  AdbMonthlyResponse,
  AdbPayload,
  LiabilitiesMonthlyPayload,
  LiabilityCounterpartyPayload,
  LiabilityRiskBucketsPayload,
  LiabilityYieldMetricsPayload,
  CustomerBondDetailsResponse,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  FormalPnlRefreshPayload,
  HealthResponse,
  IndustryDistPayload,
  IndustryStatsResponse,
  InterbankCounterpartySplitResponse,
  InterbankPositionItem,
  KpiBatchUpdateResponse,
  KpiFetchAndRecalcRequest,
  KpiFetchAndRecalcResponse,
  KpiMetric,
  KpiMetricListResponse,
  KpiMetricUpsertRequest,
  KpiMetricValue,
  KpiOwnerListResponse,
  KpiPeriodSummaryResponse,
  KpiReportResponse,
  KpiValuesResponse,
  LedgerPnlDataPayload,
  LedgerPnlDatesPayload,
  LedgerPnlSummaryPayload,
  MacroBondLinkagePayload,
  MacroVendorPayload,
  MaturityStructurePayload,
  PageResponse,
  OverviewPayload,
  PnlBridgePayload,
  PnlBasis,
  PnlDataPayload,
  PnlDatesPayload,
  PnlOverviewPayload,
  PlaceholderSnapshot,
  PositionDirection,
  ProductCategoryDatesPayload,
  QdbGlMonthlyAnalysisDatesPayload,
  QdbGlMonthlyAnalysisManualAdjustmentExportPayload,
  QdbGlMonthlyAnalysisManualAdjustmentListPayload,
  QdbGlMonthlyAnalysisManualAdjustmentPayload,
  QdbGlMonthlyAnalysisManualAdjustmentRequest,
  QdbGlMonthlyAnalysisScenarioPayload,
  QdbGlMonthlyAnalysisWorkbookExportPayload,
  QdbGlMonthlyAnalysisWorkbookPayload,
  ProductCategoryManualAdjustmentListPayload,
  ProductCategoryManualAdjustmentExportPayload,
  ProductCategoryManualAdjustmentPayload,
  ProductCategoryManualAdjustmentQuery,
  ProductCategoryManualAdjustmentRequest,
  ProductCategoryRefreshPayload,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  ProductTypesResponse,
  PnlAttributionPayload,
  PnlAttributionAnalysisSummary,
  PortfolioComparisonPayload,
  PnlCompositionPayload,
  ReturnDecompositionPayload,
  ResultMeta,
  RiskIndicatorsPayload,
  RatingStatsResponse,
  RiskOverviewPayload,
  RiskTensorDatesPayload,
  RiskTensorPayload,
  SourcePreviewHistoryPayload,
  SourcePreviewRefreshPayload,
  ChoiceMacroRefreshPayload,
  SourcePreviewRowsPayload,
  SourcePreviewTracesPayload,
  SourcePreviewColumn,
  SourcePreviewSummary,
  SourcePreviewPayload,
  SpreadAnalysisPayload,
  SpreadAttributionPayload,
  SubTypesResponse,
  SummaryPayload,
  TPLMarketCorrelationPayload,
  YieldDistributionPayload,
  VolumeRateAttributionPayload,
} from "./contracts";
import {
  mockAdvancedAttributionSummary,
  mockCampisiAttribution,
  mockCarryRollDown,
  mockKrdAttribution,
  mockPnlAttributionAnalysisSummary,
  mockPnlComposition,
  mockSpreadAttribution,
  mockTplMarketCorrelation,
  mockVolumeRateAttribution,
} from "../mocks/pnlAttributionWorkbench";
import {
  alertsPayload,
  contributionPayload,
  overviewPayload,
  placeholderSnapshots,
  pnlAttributionPayload,
  riskOverviewPayload,
  summaryPayload,
} from "../mocks/workbench";
export type DataSourceMode = "mock" | "real";

export type ApiClient = {
  mode: DataSourceMode;
  getHealth: () => Promise<HealthResponse>;
  getOverview: () => Promise<ApiEnvelope<OverviewPayload>>;
  getSummary: () => Promise<ApiEnvelope<SummaryPayload>>;
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
  getPnlAttribution: () => Promise<ApiEnvelope<PnlAttributionPayload>>;
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
  getRiskOverview: () => Promise<ApiEnvelope<RiskOverviewPayload>>;
  getRiskTensorDates: () => Promise<ApiEnvelope<RiskTensorDatesPayload>>;
  getRiskTensor: (reportDate: string) => Promise<ApiEnvelope<RiskTensorPayload>>;
  getContribution: () => Promise<ApiEnvelope<ContributionPayload>>;
  getAlerts: () => Promise<ApiEnvelope<AlertsPayload>>;
  getPlaceholderSnapshot: (key: string) => Promise<ApiEnvelope<PlaceholderSnapshot>>;
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
  getBondAnalyticsDates: () => Promise<ApiEnvelope<BondAnalyticsDatesPayload>>;
  getBondDashboardDates: () => Promise<ApiEnvelope<BondAnalyticsDatesPayload>>;
  getBondDashboardHeadlineKpis: (
    reportDate: string,
  ) => Promise<ApiEnvelope<BondDashboardHeadlinePayload>>;
  getBondDashboardAssetStructure: (
    reportDate: string,
    groupBy: string,
  ) => Promise<ApiEnvelope<AssetStructurePayload>>;
  getBondDashboardYieldDistribution: (
    reportDate: string,
  ) => Promise<ApiEnvelope<YieldDistributionPayload>>;
  getBondDashboardPortfolioComparison: (
    reportDate: string,
  ) => Promise<ApiEnvelope<PortfolioComparisonPayload>>;
  getBondDashboardSpreadAnalysis: (
    reportDate: string,
  ) => Promise<ApiEnvelope<SpreadAnalysisPayload>>;
  getBondDashboardMaturityStructure: (
    reportDate: string,
  ) => Promise<ApiEnvelope<MaturityStructurePayload>>;
  getBondDashboardIndustryDistribution: (
    reportDate: string,
  ) => Promise<ApiEnvelope<IndustryDistPayload>>;
  getBondDashboardRiskIndicators: (
    reportDate: string,
  ) => Promise<ApiEnvelope<RiskIndicatorsPayload>>;
  getBondAnalyticsReturnDecomposition: (
    reportDate: string,
    periodType: string,
    options?: { assetClass?: string; accountingClass?: string },
  ) => Promise<ApiEnvelope<ReturnDecompositionPayload>>;
  getBondAnalyticsBenchmarkExcess: (
    reportDate: string,
    periodType: string,
    benchmarkId: string,
  ) => Promise<ApiEnvelope<BenchmarkExcessPayload>>;
  getBondAnalyticsKrdCurveRisk: (
    reportDate: string,
    options?: { scenarioSet?: string },
  ) => Promise<ApiEnvelope<KRDCurveRiskPayload>>;
  getBondAnalyticsActionAttribution: (
    reportDate: string,
    periodType: string,
  ) => Promise<ApiEnvelope<ActionAttributionPayload>>;
  getBondAnalyticsAccountingClassAudit: (
    reportDate: string,
  ) => Promise<ApiEnvelope<AccountingClassAuditPayload>>;
  getBondAnalyticsCreditSpreadMigration: (
    reportDate: string,
    options?: { spreadScenarios?: string },
  ) => Promise<ApiEnvelope<CreditSpreadMigrationPayload>>;
  getBondAnalyticsPortfolioHeadlines: (
    reportDate: string,
  ) => Promise<ApiEnvelope<BondPortfolioHeadlinesPayload>>;
  getBondAnalyticsTopHoldings: (
    reportDate: string,
    topN?: number,
  ) => Promise<ApiEnvelope<BondTopHoldingsPayload>>;
  getCreditSpreadAnalysisDetail: (
    reportDate: string,
  ) => Promise<ApiEnvelope<CreditSpreadAnalysisPayload>>;
  getPositionsBondSubTypes: (
    reportDate?: string | null,
  ) => Promise<ApiEnvelope<SubTypesResponse>>;
  getPositionsBondsList: (options: {
    reportDate?: string | null;
    subType?: string | null;
    page: number;
    pageSize: number;
    includeIssued?: boolean;
  }) => Promise<ApiEnvelope<PageResponse<BondPositionItem>>>;
  getPositionsCounterpartyBonds: (options: {
    startDate: string;
    endDate: string;
    subType?: string | null;
    topN?: number;
    page?: number;
    pageSize?: number;
  }) => Promise<ApiEnvelope<CounterpartyStatsResponse>>;
  getPositionsInterbankProductTypes: (
    reportDate?: string | null,
  ) => Promise<ApiEnvelope<ProductTypesResponse>>;
  getPositionsInterbankList: (options: {
    reportDate?: string | null;
    productType?: string | null;
    direction?: PositionDirection | "ALL" | null;
    page: number;
    pageSize: number;
  }) => Promise<ApiEnvelope<PageResponse<InterbankPositionItem>>>;
  getPositionsCounterpartyInterbankSplit: (options: {
    startDate: string;
    endDate: string;
    productType?: string | null;
    topN?: number;
  }) => Promise<ApiEnvelope<InterbankCounterpartySplitResponse>>;
  getPositionsStatsRating: (options: {
    startDate: string;
    endDate: string;
    subType?: string | null;
  }) => Promise<ApiEnvelope<RatingStatsResponse>>;
  getPositionsStatsIndustry: (options: {
    startDate: string;
    endDate: string;
    subType?: string | null;
    topN?: number;
  }) => Promise<ApiEnvelope<IndustryStatsResponse>>;
  getPositionsCustomerDetails: (options: {
    customerName: string;
    reportDate?: string | null;
  }) => Promise<ApiEnvelope<CustomerBondDetailsResponse>>;
  getPositionsCustomerTrend: (options: {
    customerName: string;
    endDate?: string | null;
    days?: number;
  }) => Promise<ApiEnvelope<CustomerBalanceTrendResponse>>;
  getCashflowProjection: (reportDate: string) => Promise<ApiEnvelope<CashflowProjectionPayload>>;
  /**
   * 负债结构分析（V1 兼容 JSON）。
   * TODO: 后端待实现/收敛 — 当前路径与 V1 对齐：`/api/risk/buckets`、`/api/analysis/yield_metrics` 等。
   */
  getLiabilityRiskBuckets: (reportDate?: string | null) => Promise<LiabilityRiskBucketsPayload>;
  getLiabilityYieldMetrics: (reportDate?: string | null) => Promise<LiabilityYieldMetricsPayload>;
  getLiabilityCounterparty: (options: {
    reportDate?: string | null;
    topN?: number;
  }) => Promise<LiabilityCounterpartyPayload>;
  getLiabilitiesMonthly: (year: number) => Promise<LiabilitiesMonthlyPayload>;
  getLiabilityAdbMonthly: (year: number) => Promise<AdbMonthlyResponse>;
  getAdb: (params: { startDate: string; endDate: string }) => Promise<AdbPayload>;
  getAdbComparison: (
    startDate: string,
    endDate: string,
    options?: {
      topN?: number;
    },
  ) => Promise<AdbComparisonResponse>;
  getAdbMonthly: (year: number) => Promise<AdbMonthlyResponse>;
  refreshBondAnalytics: (reportDate: string) => Promise<BondAnalyticsRefreshPayload>;
  getBondAnalyticsRefreshStatus: (
    runId: string,
  ) => Promise<BondAnalyticsRefreshPayload>;

  // --- KPI 绩效考核 ---
  getKpiOwners: (params?: {
    year?: number;
    is_active?: boolean;
  }) => Promise<KpiOwnerListResponse>;
  getKpiMetrics: (params?: {
    owner_id?: number;
    year?: number;
    is_active?: boolean;
  }) => Promise<KpiMetricListResponse>;
  getKpiMetricById: (metricId: number) => Promise<KpiMetric>;
  createKpiMetric: (data: KpiMetricUpsertRequest) => Promise<KpiMetric>;
  updateKpiMetric: (metricId: number, data: KpiMetricUpsertRequest) => Promise<KpiMetric>;
  deleteKpiMetric: (metricId: number) => Promise<void>;
  getKpiValues: (params: {
    owner_id: number;
    as_of_date: string;
    include_trace?: boolean;
  }) => Promise<KpiValuesResponse>;
  getKpiValuesSummary: (params: {
    owner_id: number;
    year: number;
    period_type: "MONTH" | "QUARTER" | "YEAR";
    period_value?: number;
  }) => Promise<KpiPeriodSummaryResponse>;
  createKpiValue: (data: {
    metric_id: number;
    as_of_date: string;
    actual_value?: string;
    actual_text?: string;
    progress_pct?: string;
    source?: string;
  }) => Promise<KpiMetricValue>;
  updateKpiValue: (
    valueId: number,
    metricId: number,
    asOfDate: string,
    data: {
      target_value?: string;
      actual_value?: string;
      actual_text?: string;
      progress_pct?: string;
      score_value?: string;
      source?: string;
    },
  ) => Promise<KpiMetricValue>;
  batchUpdateKpiValues: (
    asOfDate: string,
    items: Array<{
      metric_id: number;
      actual_value?: string;
      progress_pct?: string;
    }>,
  ) => Promise<KpiBatchUpdateResponse>;
  fetchAndRecalcKpi: (
    ownerId: number,
    asOfDate: string,
    request?: KpiFetchAndRecalcRequest,
  ) => Promise<KpiFetchAndRecalcResponse>;
  getKpiReport: (params: {
    year: number;
    owner_id?: number;
    as_of_date?: string;
    format?: "json" | "csv";
  }) => Promise<KpiReportResponse>;
  downloadKpiReportCSV: (params: {
    year: number;
    owner_id?: number;
    as_of_date?: string;
  }) => Promise<void>;
  getCubeDimensions: (factTable: string) => Promise<CubeDimensionsPayload>;
  executeCubeQuery: (request: CubeQueryRequest) => Promise<CubeQueryResult>;
};

type ApiClientOptions = {
  mode?: DataSourceMode;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
};

type ApiClientProviderProps = {
  children: ReactNode;
  client?: ApiClient;
};

const defaultFetch = (...args: Parameters<typeof fetch>) => fetch(...args);

const delay = async () => new Promise((resolve) => setTimeout(resolve, 40));

function isFiniteNumber(value: number | undefined): value is number {
  return value !== undefined && Number.isFinite(value);
}

const buildMockMeta = (resultKind: string): ResultMeta => ({
  trace_id: `mock_${resultKind}`,
  basis: "mock",
  result_kind: resultKind,
  formal_use_allowed: false,
  source_version: "sv_mock_dashboard_v2",
  vendor_version: "vv_none",
  rule_version: "rv_dashboard_mock_v2",
  cache_version: "cv_dashboard_mock_v2",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-04-09T10:30:00Z",
});

const buildMockApiEnvelope = <T>(
  resultKind: string,
  result: T,
  metaOverrides?: Partial<ResultMeta>,
): ApiEnvelope<T> => ({
  result_meta: { ...buildMockMeta(resultKind), ...metaOverrides },
  result,
});

function buildPnlBasisQuerySegment(basis?: PnlBasis) {
  return basis && basis !== "formal" ? `&basis=${encodeURIComponent(basis)}` : "";
}

function buildCampisiQuery(options?: {
  startDate?: string;
  endDate?: string;
  lookbackDays?: number;
}) {
  const params = new URLSearchParams();
  if (options?.startDate?.trim()) {
    params.set("start_date", options.startDate.trim());
  }
  if (options?.endDate?.trim()) {
    params.set("end_date", options.endDate.trim());
  }
  if (Number.isFinite(options?.lookbackDays)) {
    params.set("lookback_days", String(options?.lookbackDays));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

const mockLedgerMoney = (yuan: string) => ({
  yuan,
  yi: (Number(yuan) / 100_000_000).toFixed(2),
  wan: (Number(yuan) / 10_000).toFixed(2),
});

const mockLedgerPnlDates: LedgerPnlDatesPayload = {
  dates: ["2025-12-31", "2025-11-30"],
};

const mockLedgerPnlSummary: LedgerPnlSummaryPayload = {
  report_date: "2025-12-31",
  source_version: "sv_mock_ledger",
  ledger_total_assets: mockLedgerMoney("1250000000"),
  ledger_total_liabilities: mockLedgerMoney("980000000"),
  ledger_net_assets: mockLedgerMoney("270000000"),
  ledger_monthly_pnl_core: mockLedgerMoney("3520000"),
  ledger_monthly_pnl_all: mockLedgerMoney("4180000"),
  by_currency: [
    { currency: "CNX", total_pnl: mockLedgerMoney("3010000") },
    { currency: "CNY", total_pnl: mockLedgerMoney("510000") },
  ],
  by_account: [
    {
      account_code: "514100",
      account_name: "利息收入",
      total_pnl: mockLedgerMoney("2120000"),
      count: 18,
    },
    {
      account_code: "516100",
      account_name: "公允价值变动损益",
      total_pnl: mockLedgerMoney("880000"),
      count: 9,
    },
  ],
};

const mockLedgerPnlData: LedgerPnlDataPayload = {
  report_date: "2025-12-31",
  items: [
    {
      account_code: "514100",
      account_name: "利息收入",
      currency: "CNX",
      beginning_balance: mockLedgerMoney("101200000"),
      ending_balance: mockLedgerMoney("106500000"),
      monthly_pnl: mockLedgerMoney("880000"),
      daily_avg_balance: mockLedgerMoney("104100000"),
      days_in_period: 31,
    },
    {
      account_code: "516100",
      account_name: "公允价值变动损益",
      currency: "CNX",
      beginning_balance: mockLedgerMoney("10000000"),
      ending_balance: mockLedgerMoney("11200000"),
      monthly_pnl: mockLedgerMoney("420000"),
      daily_avg_balance: mockLedgerMoney("10600000"),
      days_in_period: 31,
    },
  ],
  summary: {
    total_pnl_cnx: mockLedgerMoney("1300000"),
    total_pnl_cny: mockLedgerMoney("0"),
    total_pnl: mockLedgerMoney("1300000"),
    count: 2,
  },
};

const mockCampisiFourEffects: CampisiFourEffectsPayload = {
  report_date: "2026-03-31",
  period_start: "2026-03-01",
  period_end: "2026-03-31",
  num_days: 30,
  totals: {
    income_return: 820000,
    treasury_effect: -210000,
    spread_effect: 160000,
    selection_effect: 95000,
    total_return: 865000,
    market_value_start: 128000000,
  },
  by_asset_class: [
    {
      asset_class: "政策性金融债",
      market_value_start: 78000000,
      income_return: 520000,
      treasury_effect: -180000,
      spread_effect: 120000,
      selection_effect: 50000,
      total_return: 510000,
      weight_pct: 60.94,
    },
  ],
  by_bond: [
    {
      bond_code: "240001.IB",
      asset_class: "政策性金融债",
      maturity_bucket: "1-3Y",
      market_value_start: 32000000,
      income_return: 210000,
      treasury_effect: -70000,
      spread_effect: 42000,
      selection_effect: 20000,
      total_return: 202000,
      mod_duration: 2.7,
    },
  ],
};

const mockCampisiEnhanced: CampisiEnhancedPayload = {
  report_date: "2026-03-31",
  period_start: "2026-03-01",
  period_end: "2026-03-31",
  num_days: 30,
  totals: {
    income_return: 820000,
    treasury_effect: -210000,
    spread_effect: 160000,
    convexity_effect: 18000,
    cross_effect: 6000,
    reinvestment_effect: 0,
    selection_effect: 81000,
    total_return: 875000,
    market_value_start: 128000000,
  },
  by_asset_class: [
    {
      asset_class: "政策性金融债",
      market_value_start: 78000000,
      income_return: 520000,
      treasury_effect: -180000,
      spread_effect: 120000,
      convexity_effect: 12000,
      cross_effect: 3000,
      reinvestment_effect: 0,
      selection_effect: 45000,
      total_return: 520000,
      weight_pct: 60.94,
    },
  ],
  by_bond: [
    {
      bond_code: "240001.IB",
      asset_class: "政策性金融债",
      maturity_bucket: "1-3Y",
      market_value_start: 32000000,
      income_return: 210000,
      treasury_effect: -70000,
      spread_effect: 42000,
      convexity_effect: 5000,
      cross_effect: 1000,
      reinvestment_effect: 0,
      selection_effect: 17000,
      total_return: 205000,
      mod_duration: 2.7,
    },
  ],
};

const mockCampisiMaturityBuckets: CampisiMaturityBucketsPayload = {
  period_start: "2026-03-01",
  period_end: "2026-03-31",
  buckets: {
    "0-1Y": {
      market_value_start: 18000000,
      income_return: 90000,
      treasury_effect: -20000,
      spread_effect: 15000,
      selection_effect: 6000,
      total_return: 91000,
    },
    "1-3Y": {
      market_value_start: 52000000,
      income_return: 330000,
      treasury_effect: -82000,
      spread_effect: 61000,
      selection_effect: 26000,
      total_return: 335000,
    },
  },
};

/** Inline mock for `getSourceFoundation` in mock mode only (mirrors backend preview shape). */
const MOCK_SOURCE_FOUNDATION_SUMMARIES: SourcePreviewSummary[] = [
  {
    source_family: "tyw",
    report_date: "2025-12-31",
    source_file: "TYWLSHOW-20251231.xls",
    total_rows: 2395,
    manual_review_count: 18,
    source_version: "sv_mock_tyw_preview",
    rule_version: "rv_phase1_source_preview_v1",
    group_counts: {
      "回购类": 1060,
      "拆借类": 97,
      "存放类": 1238,
    },
  },
  {
    source_family: "zqtz",
    report_date: "2025-12-31",
    source_file: "ZQTZSHOW-20251231.xls",
    total_rows: 1724,
    manual_review_count: 0,
    source_version: "sv_mock_zqtz_preview",
    rule_version: "rv_phase1_source_preview_v1",
    group_counts: {
      "债券类": 1571,
      "基金类": 127,
      "特定目的载体及其他非标类": 26,
    },
  },
];

const MOCK_CHOICE_NEWS_EVENTS: ChoiceNewsEventsPayload["events"] = [
  {
    event_key: "ce_mock_001",
    received_at: "2026-04-10T09:01:00Z",
    group_id: "news_cmd1",
    content_type: "sectornews",
    serial_id: 1001,
    request_id: 501,
    error_code: 0,
    error_msg: "",
    topic_code: "S888010007API",
    item_index: 0,
    payload_text: "Macro data release calendar updated for CPI and industrial production.",
    payload_json: null,
  },
  {
    event_key: "ce_mock_002",
    received_at: "2026-04-10T08:58:00Z",
    group_id: "news_cmd1",
    content_type: "sectornews",
    serial_id: 1001,
    request_id: 501,
    error_code: 0,
    error_msg: "",
    topic_code: "C000003006",
    item_index: 0,
    payload_text: null,
    payload_json:
      "{\"headline\":\"Policy follow-up\",\"summary\":\"PBOC open-market operation commentary stream.\"}",
  },
  {
    event_key: "ce_mock_003",
    received_at: "2026-04-10T08:50:00Z",
    group_id: "news_cmd1",
    content_type: "sectornews",
    serial_id: 1002,
    request_id: 502,
    error_code: 101,
    error_msg: "vendor callback timeout",
    topic_code: "__callback__",
    item_index: -1,
    payload_text: null,
    payload_json: null,
  },
];

const MOCK_MACRO_FOUNDATION_PAYLOAD: MacroVendorPayload = {
  read_target: "duckdb",
  series: [
    {
      series_id: "M001",
      series_name: "公开市场7天逆回购利率",
      vendor_name: "choice",
      vendor_version: "vv_choice_catalog_v1",
      frequency: "daily",
      unit: "%",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
    },
    {
      series_id: "M002",
      series_name: "DR007",
      vendor_name: "choice",
      vendor_version: "vv_choice_catalog_v1",
      frequency: "daily",
      unit: "%",
      refresh_tier: "fallback",
      fetch_mode: "latest",
      fetch_granularity: "single",
      policy_note: "low-frequency latest-only lane",
    },
    {
      series_id: "M003",
      series_name: "1年期国债到期收益率",
      vendor_name: "choice",
      vendor_version: "vv_choice_catalog_v1",
      frequency: "daily",
      unit: "%",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
    },
  ],
};

function buildMockChoiceMacroRecentPoints(
  endDate: string,
  count: number,
  finalValue: number,
  amplitude: number,
): ChoiceMacroRecentPoint[] {
  const out: ChoiceMacroRecentPoint[] = [];
  for (let i = 0; i < count; i++) {
    const dayOffset = -(count - 1 - i);
    const d = new Date(`${endDate}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + dayOffset);
    const trade_date = d.toISOString().slice(0, 10);
    const t = count > 1 ? i / (count - 1) : 1;
    const wobble = Math.sin(i * 0.8 + amplitude) * amplitude * 0.15;
    const value_numeric = Number((finalValue + (t - 1) * amplitude * 0.35 + wobble).toFixed(4));
    out.push({
      trade_date,
      value_numeric,
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      quality_flag: "ok",
    });
  }
  out[out.length - 1] = {
    ...out[out.length - 1],
    value_numeric: finalValue,
  };
  return out;
}

const MOCK_CHOICE_MACRO_LATEST_PAYLOAD: ChoiceMacroLatestPayload = {
  read_target: "duckdb",
  series: [
    {
      series_id: "M001",
      series_name: "公开市场7天逆回购利率",
      trade_date: "2026-04-10",
      value_numeric: 1.75,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
      latest_change: 0.2,
      recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 1.75, 0.06),
    },
    {
      series_id: "M002",
      series_name: "DR007",
      trade_date: "2026-04-10",
      value_numeric: 1.83,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
      refresh_tier: "fallback",
      fetch_mode: "latest",
      fetch_granularity: "single",
      policy_note: "low-frequency latest-only lane",
      latest_change: -0.05,
      recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 1.83, 0.05),
    },
    {
      series_id: "M003",
      series_name: "1年期国债到期收益率",
      trade_date: "2026-04-10",
      value_numeric: 1.56,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
      latest_change: 0.03,
      recent_points: buildMockChoiceMacroRecentPoints("2026-04-10", 20, 1.56, 0.04),
    },
    {
      series_id: "E1000180",
      series_name: "中债国债到期收益率:10年",
      trade_date: "2026-03-01",
      value_numeric: 1.94,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "edb chinabond cross-asset",
      latest_change: -0.011,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 1.94, 0.04),
    },
    {
      series_id: "E1003238",
      series_name: "美国国债收益率曲线:10年",
      trade_date: "2026-03-01",
      value_numeric: 4.1,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "edb fed cross-asset",
      latest_change: 0.05,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 4.1, 0.12),
    },
    {
      series_id: "EM1",
      series_name: "10Y中国国债-10Y美国国债",
      trade_date: "2026-03-01",
      value_numeric: -210,
      unit: "bp",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "edb chinabond spread",
      latest_change: -3,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, -210, 8),
    },
    {
      series_id: "EMM00166466",
      series_name: "中债国债到期收益率:10年",
      trade_date: "2026-03-01",
      value_numeric: 1.94,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "catalog-aligned cross-asset",
      latest_change: -0.011,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 1.94, 0.04),
    },
    {
      series_id: "EMM00166502",
      series_name: "中债政策性金融债到期收益率(国开行)10年",
      trade_date: "2026-03-01",
      value_numeric: 2.09,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "catalog-aligned cross-asset",
      latest_change: 0.015,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 2.09, 0.05),
    },
    {
      series_id: "EMM00167613",
      series_name: "银行间同业拆借加权利率:7天",
      trade_date: "2026-03-01",
      value_numeric: 1.82,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "catalog-aligned cross-asset",
      latest_change: 0.021,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 1.82, 0.06),
    },
    {
      series_id: "EMM01843735",
      series_name: "第一财经研究院中国金融条件指数(日)",
      trade_date: "2026-03-01",
      value_numeric: 98.6,
      unit: "index",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "catalog-aligned cross-asset",
      latest_change: 0.35,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 98.6, 0.8),
    },
    {
      series_id: "EMM00058124",
      series_name: "中间价:美元兑人民币",
      trade_date: "2026-03-01",
      value_numeric: 7.14,
      unit: "CNY/USD",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "catalog-aligned cross-asset",
      latest_change: 0.0064,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 7.14, 0.02),
    },
    {
      series_id: "CA.CN_GOV_10Y",
      series_name: "中债国债到期收益率:10年",
      trade_date: "2026-03-01",
      value_numeric: 1.94,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: -0.011,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 1.94, 0.04),
    },
    {
      series_id: "EMG00001310",
      series_name: "美国:国债收益率:10年",
      trade_date: "2026-03-01",
      value_numeric: 4.1,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "edb us treasury — catalog-aligned",
      latest_change: 0.05,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 4.1, 0.12),
    },
    {
      series_id: "CA.US_GOV_10Y",
      series_name: "美国10年期国债收益率",
      trade_date: "2026-03-01",
      value_numeric: 4.1,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: 0.05,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 4.1, 0.12),
    },
    {
      series_id: "CA.CN_US_SPREAD",
      series_name: "中美国债利差(10Y)",
      trade_date: "2026-03-01",
      value_numeric: -210,
      unit: "bp",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: -3,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, -210, 8),
    },
    {
      series_id: "CA.DR007",
      series_name: "存款类机构质押式回购加权利率:DR007",
      trade_date: "2026-03-01",
      value_numeric: 1.82,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: 0.021,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 1.82, 0.06),
    },
    {
      series_id: "CA.CSI300",
      series_name: "沪深300指数",
      trade_date: "2026-03-01",
      value_numeric: 3924.5,
      unit: "index",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: 1.89,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 3924.5, 45),
    },
    {
      series_id: "CA.BRENT",
      series_name: "ICE布伦特原油期货收盘价",
      trade_date: "2026-03-01",
      value_numeric: 82.3,
      unit: "USD/bbl",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: 4.8,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 82.3, 2.2),
    },
    {
      series_id: "CA.STEEL",
      series_name: "螺纹钢主力合约结算价",
      trade_date: "2026-03-01",
      value_numeric: 8500,
      unit: "CNY/t",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: 3.2,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 8500, 120),
    },
    {
      series_id: "CA.USDCNY",
      series_name: "即期汇率:美元兑人民币",
      trade_date: "2026-03-01",
      value_numeric: 7.14,
      unit: "CNY/USD",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_mock_v1",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "cross-asset headline lane",
      latest_change: 0.0064,
      recent_points: buildMockChoiceMacroRecentPoints("2026-03-01", 20, 7.14, 0.02),
    },
  ],
};

const MOCK_MACRO_BOND_LINKAGE_PAYLOAD: MacroBondLinkagePayload = {
  report_date: "2026-04-10",
  environment_score: {
    report_date: "2026-04-10",
    rate_direction: "falling",
    rate_direction_score: -0.42,
    liquidity_score: 0.31,
    growth_score: -0.14,
    inflation_score: 0.08,
    composite_score: -0.11,
    signal_description:
      "资金面维持宽松，长端对海外利率与风险偏好更敏感：国内短端利率稳定，权益与商品反弹带来增长预期修复，但美债高位约束利差压缩空间。建议以流动性为锚、用海外约束做上限、用增长预期做节奏。",
    contributing_factors: [
      {
        category: "rate",
        series_id: "EMM00166466",
        series_name: "10Y treasury yield",
        latest_value: 1.56,
        delta: -0.18,
        score: -1,
      },
    ],
    warnings: [],
  },
  portfolio_impact: {
    estimated_rate_change_bps: "-12.6",
    estimated_spread_widening_bps: "-6.2",
    estimated_rate_pnl_impact: "1820000.50",
    estimated_spread_pnl_impact: "410000.25",
    total_estimated_impact: "2230000.75",
    impact_ratio_to_market_value: "0.0041",
  },
  top_correlations: [
    {
      series_id: "EMM00166466",
      series_name: "10Y treasury yield",
      target_family: "credit_spread",
      target_tenor: "5Y",
      target_yield: "credit_spread_5Y",
      correlation_3m: -0.41,
      correlation_6m: -0.58,
      correlation_1y: -0.63,
      lead_lag_days: -4,
      direction: "negative",
    },
    {
      series_id: "EMM00166253",
      series_name: "DR007",
      target_family: "treasury",
      target_tenor: "10Y",
      target_yield: "treasury_10Y",
      correlation_3m: 0.32,
      correlation_6m: 0.47,
      correlation_1y: 0.51,
      lead_lag_days: 2,
      direction: "positive",
    },
    {
      series_id: "EMM00072301",
      series_name: "CPI YoY",
      target_family: "aaa_credit",
      target_tenor: "3Y",
      target_yield: "aaa_credit_3Y",
      correlation_3m: 0.11,
      correlation_6m: 0.26,
      correlation_1y: 0.29,
      lead_lag_days: 7,
      direction: "positive",
    },
  ],
  warnings: [
    "Analytical signal only. Do not treat estimated impact as formal attribution.",
  ],
  computed_at: "2026-04-13T00:00:00Z",
};

const MOCK_FX_FORMAL_STATUS_PAYLOAD: FxFormalStatusPayload = {
  read_target: "duckdb",
  vendor_priority: ["choice", "akshare", "fail_closed"],
  candidate_count: 3,
  materialized_count: 2,
  latest_trade_date: "2026-04-10",
  carry_forward_count: 1,
  rows: [
    {
      base_currency: "USD",
      quote_currency: "CNY",
      pair_label: "USD/CNY",
      series_id: "FX.USD.CNY",
      series_name: "USD/CNY middle rate",
      vendor_series_code: "USD/CNY",
      trade_date: "2026-04-10",
      observed_trade_date: "2026-04-09",
      mid_rate: 7.2,
      source_name: "fx_daily_mid",
      vendor_name: "choice",
      vendor_version: "vv_fx_formal_mock",
      source_version: "sv_fx_formal_mock",
      is_business_day: false,
      is_carry_forward: true,
      status: "ok",
    },
    {
      base_currency: "EUR",
      quote_currency: "CNY",
      pair_label: "EUR/CNY",
      series_id: "FX.EUR.CNY",
      series_name: "EUR/CNY middle rate",
      vendor_series_code: "EUR/CNY",
      trade_date: "2026-04-10",
      observed_trade_date: "2026-04-10",
      mid_rate: 7.88,
      source_name: "fx_daily_mid",
      vendor_name: "akshare",
      vendor_version: "vv_fx_formal_mock",
      source_version: "sv_fx_formal_mock",
      is_business_day: true,
      is_carry_forward: false,
      status: "ok",
    },
    {
      base_currency: "JPY",
      quote_currency: "CNY",
      pair_label: "JPY/CNY",
      series_id: "FX.JPY.CNY",
      series_name: "JPY/CNY middle rate",
      vendor_series_code: "JPY/CNY",
      trade_date: null,
      observed_trade_date: null,
      mid_rate: null,
      source_name: null,
      vendor_name: null,
      vendor_version: null,
      source_version: null,
      is_business_day: null,
      is_carry_forward: null,
      status: "missing",
    },
  ],
};

const MOCK_FX_ANALYTICAL_PAYLOAD: FxAnalyticalPayload = {
  read_target: "duckdb",
  groups: [
    {
      group_key: "middle_rate",
      title: "Analytical FX: middle-rates",
      description:
        "Catalog-observed middle-rate series remain analytical views and do not redefine the formal seam.",
      series: [
        {
          group_key: "middle_rate",
          series_id: "FX.USD.CNY.OBS",
          series_name: "USD/CNY middle-rate observation",
          trade_date: "2026-04-10",
          value_numeric: 7.2,
          frequency: "daily",
          unit: "CNY",
          source_version: "sv_fx_analytical_mock",
          vendor_version: "vv_fx_analytical_mock",
          refresh_tier: "stable",
          fetch_mode: "date_slice",
          fetch_granularity: "batch",
          policy_note: "analytical middle-rate observation only",
          quality_flag: "ok",
          latest_change: 0.02,
          recent_points: [
            {
              trade_date: "2026-04-10",
              value_numeric: 7.2,
              source_version: "sv_fx_analytical_mock",
              vendor_version: "vv_fx_analytical_mock",
              quality_flag: "ok",
            },
            {
              trade_date: "2026-04-09",
              value_numeric: 7.18,
              source_version: "sv_fx_analytical_prev",
              vendor_version: "vv_fx_analytical_prev",
              quality_flag: "ok",
            },
          ],
        },
      ],
    },
    {
      group_key: "fx_index",
      title: "Analytical FX: indices",
      description:
        "RMB index / estimate index series stay analytical-only and never flow into formal FX.",
      series: [
        {
          group_key: "fx_index",
          series_id: "FX.CFETS.RMB",
          series_name: "CFETS RMB basket index",
          trade_date: "2026-04-10",
          value_numeric: 101.3,
          frequency: "daily",
          unit: "index",
          source_version: "sv_fx_analytical_mock",
          vendor_version: "vv_fx_analytical_mock",
          refresh_tier: "fallback",
          fetch_mode: "latest",
          fetch_granularity: "single",
          policy_note: "analytical index observation only",
          quality_flag: "warning",
          latest_change: null,
          recent_points: [],
        },
      ],
    },
    {
      group_key: "fx_swap_curve",
      title: "Analytical FX: swap curves",
      description:
        "FX swap / C-Swap series stay analytical-only and never write into formal FX.",
      series: [
        {
          group_key: "fx_swap_curve",
          series_id: "FX.SWAP.1Y",
          series_name: "USD/CNY 1Y FX swap",
          trade_date: "2026-04-10",
          value_numeric: 125.0,
          frequency: "daily",
          unit: "bp",
          source_version: "sv_fx_analytical_mock",
          vendor_version: "vv_fx_analytical_mock",
          refresh_tier: "stable",
          fetch_mode: "date_slice",
          fetch_granularity: "batch",
          policy_note: "analytical swap observation only",
          quality_flag: "ok",
          latest_change: -3,
          recent_points: [
            {
              trade_date: "2026-04-10",
              value_numeric: 125.0,
              source_version: "sv_fx_analytical_mock",
              vendor_version: "vv_fx_analytical_mock",
              quality_flag: "ok",
            },
          ],
        },
      ],
    },
  ],
};

function buildMockSourcePreviewColumns(rows: Array<Record<string, unknown>>): SourcePreviewColumn[] {
  const firstRow = rows[0];
  if (!firstRow) {
    return [];
  }
  return Object.keys(firstRow).map((key) => ({
    key,
    label: buildMockSourcePreviewLabel(key),
    type: key === "row_locator" || key === "trace_step"
      ? "number"
      : key === "manual_review_needed"
        ? "boolean"
        : "string",
  }));
}

function buildMockSourcePreviewLabel(key: string) {
  const labels: Record<string, string> = {
    ingest_batch_id: "批次ID",
    row_locator: "行号",
    report_date: "报告日期",
    business_type_primary: "业务种类1",
    business_type_final: "业务种类2归类",
    asset_group: "资产分组",
    instrument_code: "债券代码",
    instrument_name: "债券名称",
    account_category: "账户类别",
    product_group: "产品分组",
    institution_category: "机构类型",
    special_nature: "特殊性质",
    counterparty_name: "对手方名称",
    investment_portfolio: "投资组合",
    manual_review_needed: "需人工复核",
    trace_step: "轨迹步骤",
    field_name: "字段名",
    field_value: "字段值",
    derived_label: "归类标签",
  };
  return labels[key] ?? key;
}

type ProductCategoryPnlMockOptions = {
  reportDate: string;
  view: string;
  scenarioRatePct?: string;
};

function reduceLatestManualAdjustments<
  T extends { adjustment_id: string; created_at: string }
>(records: T[]): T[] {
  const latestById = new Map<string, T>();
  for (const record of records) {
    const existing = latestById.get(record.adjustment_id);
    if (!existing || record.created_at >= existing.created_at) {
      latestById.set(record.adjustment_id, record);
    }
  }
  return Array.from(latestById.values());
}

function filterManualAdjustments<
  T extends {
    adjustment_id: string;
    created_at: string;
    account_code: string;
    approval_status: string;
    event_type: string;
  }
>(
  records: T[],
  options: ProductCategoryManualAdjustmentQuery = {},
  applyEventType = true,
): T[] {
  const adjustmentId = options.adjustmentId?.trim() ?? "";
  const adjustmentIdExact = options.adjustmentIdExact ?? false;
  const accountCode = options.accountCode?.trim() ?? "";
  const approvalStatus = options.approvalStatus?.trim() ?? "";
  const eventType = options.eventType?.trim() ?? "";
  const createdAtFrom = options.createdAtFrom?.trim() ?? "";
  const createdAtTo = options.createdAtTo?.trim() ?? "";

  return records.filter((record) => {
    if (adjustmentId) {
      if (adjustmentIdExact) {
        if (record.adjustment_id !== adjustmentId) {
          return false;
        }
      } else if (!record.adjustment_id.includes(adjustmentId)) {
        return false;
      }
    }
    if (accountCode && !record.account_code.includes(accountCode)) {
      return false;
    }
    if (approvalStatus && record.approval_status !== approvalStatus) {
      return false;
    }
    if (applyEventType && eventType && record.event_type !== eventType) {
      return false;
    }
    if (createdAtFrom && record.created_at < createdAtFrom) {
      return false;
    }
    if (createdAtTo && record.created_at > createdAtTo) {
      return false;
    }
    return true;
  });
}

function sortManualAdjustments<
  T extends {
    adjustment_id: string;
    created_at: string;
    account_code: string;
    approval_status: string;
    event_type: string;
  }
>(
  records: T[],
  field:
    | "created_at"
    | "adjustment_id"
    | "event_type"
    | "approval_status"
    | "account_code",
  direction: "asc" | "desc",
) {
  const sorted = [...records].sort((left, right) => {
    const leftValue = String(left[field] ?? "").toLowerCase();
    const rightValue = String(right[field] ?? "").toLowerCase();
    return leftValue.localeCompare(rightValue);
  });
  return direction === "desc" ? sorted.reverse() : sorted;
}

function buildManualAdjustmentSearchParams(
  reportDate: string,
  options: ProductCategoryManualAdjustmentQuery = {},
) {
  const params = new URLSearchParams({
    report_date: reportDate,
  });
  if (options.adjustmentId?.trim()) {
    params.set("adjustment_id", options.adjustmentId.trim());
  }
  if (options.adjustmentIdExact) {
    params.set("adjustment_id_exact", "true");
  }
  if (options.accountCode?.trim()) {
    params.set("account_code", options.accountCode.trim());
  }
  if (options.approvalStatus?.trim()) {
    params.set("approval_status", options.approvalStatus.trim());
  }
  if (options.eventType?.trim()) {
    params.set("event_type", options.eventType.trim());
  }
  if (options.currentSortField) {
    params.set("current_sort_field", options.currentSortField);
  }
  if (options.currentSortDir) {
    params.set("current_sort_dir", options.currentSortDir);
  }
  if (options.eventSortField) {
    params.set("event_sort_field", options.eventSortField);
  }
  if (options.eventSortDir) {
    params.set("event_sort_dir", options.eventSortDir);
  }
  if (options.createdAtFrom?.trim()) {
    params.set("created_at_from", options.createdAtFrom.trim());
  }
  if (options.createdAtTo?.trim()) {
    params.set("created_at_to", options.createdAtTo.trim());
  }
  if (options.adjustmentLimit !== undefined) {
    params.set("adjustment_limit", String(options.adjustmentLimit));
  }
  if (options.adjustmentOffset !== undefined) {
    params.set("adjustment_offset", String(options.adjustmentOffset));
  }
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (options.offset !== undefined) {
    params.set("offset", String(options.offset));
  }
  return params;
}

function buildMockProductCategoryPnlEnvelope(
  options: ProductCategoryPnlMockOptions,
): ApiEnvelope<ProductCategoryPnlPayload> {
  const scenarioRate = options.scenarioRatePct ?? null;
  const rows: ProductCategoryPnlRow[] = [
    {
      category_id: "interbank_lending_assets",
      category_name: "拆放同业",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "171.60",
      cny_scale: "156.91",
      foreign_scale: "14.69",
      cnx_cash: "0.33",
      cny_cash: "0.27",
      foreign_cash: "0.06",
      cny_ftp: scenarioRate ? "0.27" : "0.21",
      foreign_ftp: scenarioRate ? "0.03" : "0.02",
      cny_net: scenarioRate ? "0.00" : "0.05",
      foreign_net: scenarioRate ? "0.03" : "0.05",
      business_net_income: scenarioRate ? "0.03" : "0.10",
      weighted_yield: "2.50",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "repo_assets",
      category_name: "买入返售",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "230.11",
      cny_scale: "230.11",
      foreign_scale: "0.00",
      cnx_cash: "0.26",
      cny_cash: "0.26",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.39" : "0.31",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "-0.13" : "-0.05",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "-0.13" : "-0.05",
      weighted_yield: "1.47",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_investment",
      category_name: "债券投资",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "3361.78",
      cny_scale: "3305.70",
      foreign_scale: "56.08",
      cnx_cash: "6.79",
      cny_cash: "6.62",
      foreign_cash: "0.17",
      cny_ftp: scenarioRate ? "5.66" : "4.44",
      foreign_ftp: scenarioRate ? "0.10" : "0.08",
      cny_net: scenarioRate ? "0.96" : "2.18",
      foreign_net: scenarioRate ? "0.07" : "0.10",
      business_net_income: scenarioRate ? "1.03" : "2.27",
      weighted_yield: "2.63",
      is_total: false,
      children: ["bond_tpl", "bond_ac", "bond_ac_other", "bond_fvoci", "bond_valuation_spread"],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_tpl",
      category_name: "TPL",
      side: "asset",
      level: 1,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "864.98",
      cny_scale: "865.79",
      foreign_scale: "-0.80",
      cnx_cash: "1.53",
      cny_cash: "1.51",
      foreign_cash: "0.02",
      cny_ftp: scenarioRate ? "1.48" : "1.16",
      foreign_ftp: scenarioRate ? "0.01" : "0.00",
      cny_net: scenarioRate ? "0.03" : "0.35",
      foreign_net: scenarioRate ? "0.01" : "0.02",
      business_net_income: scenarioRate ? "0.04" : "0.37",
      weighted_yield: "2.31",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_ac",
      category_name: "AC债券投资",
      side: "asset",
      level: 1,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "1373.13",
      cny_scale: "1371.70",
      foreign_scale: "1.43",
      cnx_cash: "2.61",
      cny_cash: "2.60",
      foreign_cash: "0.01",
      cny_ftp: scenarioRate ? "2.35" : "1.84",
      foreign_ftp: scenarioRate ? "0.01" : "0.00",
      cny_net: scenarioRate ? "0.25" : "0.76",
      foreign_net: scenarioRate ? "0.00" : "0.01",
      business_net_income: scenarioRate ? "0.25" : "0.76",
      weighted_yield: "2.47",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_ac_other",
      category_name: "AC其他投资",
      side: "asset",
      level: 1,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "58.04",
      cny_scale: "29.64",
      foreign_scale: "28.40",
      cnx_cash: "0.05",
      cny_cash: "0.05",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.05" : "0.04",
      foreign_ftp: scenarioRate ? "0.05" : "0.04",
      cny_net: scenarioRate ? "0.00" : "0.01",
      foreign_net: scenarioRate ? "-0.05" : "-0.04",
      business_net_income: scenarioRate ? "-0.05" : "-0.03",
      weighted_yield: "1.09",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_fvoci",
      category_name: "FVOCI",
      side: "asset",
      level: 1,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "1065.63",
      cny_scale: "1038.57",
      foreign_scale: "27.05",
      cnx_cash: "2.10",
      cny_cash: "1.96",
      foreign_cash: "0.14",
      cny_ftp: scenarioRate ? "1.77" : "1.39",
      foreign_ftp: scenarioRate ? "0.05" : "0.04",
      cny_net: scenarioRate ? "0.19" : "0.56",
      foreign_net: scenarioRate ? "0.09" : "0.11",
      business_net_income: scenarioRate ? "0.28" : "0.67",
      weighted_yield: "2.57",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_valuation_spread",
      category_name: "估值及买卖价差等",
      side: "asset",
      level: 1,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "0",
      cny_scale: "0",
      foreign_scale: "0",
      cnx_cash: "0.50",
      cny_cash: "0.50",
      foreign_cash: "0.00",
      cny_ftp: "0",
      foreign_ftp: "0",
      cny_net: "0.50",
      foreign_net: "0.00",
      business_net_income: "0.50",
      weighted_yield: null,
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "interest_earning_assets",
      category_name: "生息资产",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "2898.50",
      cny_scale: "2826.94",
      foreign_scale: "71.57",
      cnx_cash: "5.34",
      cny_cash: "5.13",
      foreign_cash: "0.22",
      cny_ftp: scenarioRate ? "4.85" : "3.80",
      foreign_ftp: scenarioRate ? "0.13" : "0.10",
      cny_net: scenarioRate ? "0.28" : "1.33",
      foreign_net: scenarioRate ? "0.09" : "0.12",
      business_net_income: scenarioRate ? "0.37" : "1.45",
      weighted_yield: "2.40",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "derivatives",
      category_name: "衍生品",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "0",
      cny_scale: "0",
      foreign_scale: "0",
      cnx_cash: "-0.01",
      cny_cash: "-0.01",
      foreign_cash: "0.00",
      cny_ftp: "0",
      foreign_ftp: "0",
      cny_net: "-0.01",
      foreign_net: "0.00",
      business_net_income: "-0.01",
      weighted_yield: null,
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "intermediate_business_income",
      category_name: "中间业务收入",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "0",
      cny_scale: "0",
      foreign_scale: "0",
      cnx_cash: "0.38",
      cny_cash: "0.38",
      foreign_cash: "0.00",
      cny_ftp: "0",
      foreign_ftp: "0",
      cny_net: "0.38",
      foreign_net: "0.00",
      business_net_income: "0.38",
      weighted_yield: null,
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "interbank_deposits",
      category_name: "同业存放",
      side: "liability",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "75.24",
      cny_scale: "75.73",
      foreign_scale: "0.49",
      cnx_cash: "0.07",
      cny_cash: "0.06",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.13" : "0.10",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "-0.07" : "0.04",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "-0.07" : "0.03",
      weighted_yield: "1.18",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "interbank_borrowings",
      category_name: "同业拆入",
      side: "liability",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "424.48",
      cny_scale: "425.10",
      foreign_scale: "0.63",
      cnx_cash: "0.51",
      cny_cash: "0.51",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.72" : "0.57",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "-0.21" : "0.06",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "-0.21" : "0.06",
      weighted_yield: "1.58",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "repo_liabilities",
      category_name: "卖出回购",
      side: "liability",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "197.03",
      cny_scale: "196.89",
      foreign_scale: "0.14",
      cnx_cash: "0.21",
      cny_cash: "0.21",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.33" : "0.26",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "-0.12" : "0.05",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "-0.12" : "0.05",
      weighted_yield: "1.41",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "interbank_cds",
      category_name: "同业存单",
      side: "liability",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "1013.32",
      cny_scale: "1013.32",
      foreign_scale: "0.01",
      cnx_cash: "1.32",
      cny_cash: "1.32",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "1.74" : "1.36",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "-0.42" : "0.04",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "-0.42" : "0.04",
      weighted_yield: "1.70",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "credit_linked_notes",
      category_name: "信用联结票据",
      side: "liability",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "18.51",
      cny_scale: "18.51",
      foreign_scale: "0.00",
      cnx_cash: "0.04",
      cny_cash: "0.04",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.03" : "0.02",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "0.01" : "0.02",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "0.01" : "0.02",
      weighted_yield: "3.13",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
  ];
  const assetTotal: ProductCategoryPnlRow = {
    category_id: "asset_total",
    category_name: "资产端合计",
    side: "asset",
    level: 0,
    view: options.view,
    report_date: options.reportDate,
    baseline_ftp_rate_pct: "1.75",
    cnx_scale: "3763.49",
    cny_scale: "3692.72",
    foreign_scale: "70.76",
    cnx_cash: "7.75",
    cny_cash: "7.51",
    foreign_cash: "0.24",
    cny_ftp: scenarioRate ? "6.32" : "4.96",
    foreign_ftp: scenarioRate ? "0.11" : "0.09",
    cny_net: scenarioRate ? "1.19" : "2.56",
    foreign_net: scenarioRate ? "0.13" : "0.14",
    business_net_income: scenarioRate ? "1.32" : "2.70",
    weighted_yield: "2.68",
    is_total: true,
    children: [],
    scenario_rate_pct: scenarioRate,
  };
  const liabilityTotal: ProductCategoryPnlRow = {
    category_id: "liability_total",
    category_name: "负债端合计",
    side: "liability",
    level: 0,
    view: options.view,
    report_date: options.reportDate,
    baseline_ftp_rate_pct: "1.75",
    cnx_scale: "1728.58",
    cny_scale: "1729.55",
    foreign_scale: "0.97",
    cnx_cash: "2.16",
    cny_cash: "2.16",
    foreign_cash: "0.00",
    cny_ftp: scenarioRate ? "2.96" : "2.32",
    foreign_ftp: "0.00",
    cny_net: scenarioRate ? "-0.80" : "0.16",
    foreign_net: "0.00",
    business_net_income: scenarioRate ? "-0.80" : "0.16",
    weighted_yield: "1.63",
    is_total: true,
    children: [],
    scenario_rate_pct: scenarioRate,
  };
  const grandTotal: ProductCategoryPnlRow = {
    category_id: "grand_total",
    category_name: "grand_total",
    side: "all",
    level: 0,
    view: options.view,
    report_date: options.reportDate,
    baseline_ftp_rate_pct: "1.75",
    cnx_scale: "0",
    cny_scale: "0",
    foreign_scale: "0",
    cnx_cash: "0",
    cny_cash: "0",
    foreign_cash: "0",
    cny_ftp: "0",
    foreign_ftp: "0",
    cny_net: "0",
    foreign_net: "0",
    business_net_income: scenarioRate ? "0.52" : "2.85",
    weighted_yield: null,
    is_total: true,
    children: [],
    scenario_rate_pct: scenarioRate,
  };
  const assetRows = rows.filter((row) => row.side === "asset");
  const liabilityRows = rows.filter((row) => row.side === "liability");

  return buildMockApiEnvelope(
    "product_category_pnl.detail",
    {
      report_date: options.reportDate,
      view: options.view,
      available_views: ["monthly", "qtd", "ytd", "year_to_report_month_end"],
      scenario_rate_pct: scenarioRate,
      rows: [...assetRows, assetTotal, ...liabilityRows, liabilityTotal, grandTotal],
      asset_total: assetTotal,
      liability_total: liabilityTotal,
      grand_total: grandTotal,
    },
    {
      basis: scenarioRate ? "scenario" : "formal",
      formal_use_allowed: !scenarioRate,
      scenario_flag: Boolean(scenarioRate),
    },
  );
}

function buildMockChoiceNewsEnvelope(options: {
  limit: number;
  offset: number;
  groupId?: string;
  topicCode?: string;
  errorOnly?: boolean;
  receivedFrom?: string;
  receivedTo?: string;
}): ApiEnvelope<ChoiceNewsEventsPayload> {
  const filtered = MOCK_CHOICE_NEWS_EVENTS.filter((event) => {
    if (options.groupId?.trim() && event.group_id !== options.groupId.trim()) {
      return false;
    }
    if (options.topicCode?.trim() && event.topic_code !== options.topicCode.trim()) {
      return false;
    }
    if (options.errorOnly && event.error_code === 0) {
      return false;
    }
    if (options.receivedFrom?.trim() && event.received_at < options.receivedFrom.trim()) {
      return false;
    }
    if (options.receivedTo?.trim() && event.received_at > options.receivedTo.trim()) {
      return false;
    }
    return true;
  });

  return buildMockApiEnvelope("news.choice.latest", {
    total_rows: filtered.length,
    limit: options.limit,
    offset: options.offset,
    events: filtered.slice(options.offset, options.offset + options.limit),
  });
}

const normalizeBaseUrl = (value?: string) =>
  value ? value.replace(/\/$/, "") : "";

const parseEnvMode = (): DataSourceMode => {
  const raw = import.meta.env.VITE_DATA_SOURCE;
  const envValue = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  return envValue === "real" ? "real" : "mock";
};

const parseBaseUrl = () => {
  const raw = import.meta.env.VITE_API_BASE_URL;
  return normalizeBaseUrl(typeof raw === "string" ? raw.trim() : undefined);
};

function buildMockBalanceAnalysisTableRows(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): BalanceAnalysisTableRow[] {
  const rows: BalanceAnalysisTableRow[] = [
    {
      row_key: "zqtz:240001.IB:portfolio-a:cc-1:CNY:asset:A:FVOCI",
      source_family: "zqtz",
      display_name: "240001.IB",
      owner_name: "利率债组合",
      category_name: "交易账户",
      position_scope: "asset",
      currency_basis: "CNY",
      invest_type_std: "A",
      accounting_basis: "FVOCI",
      detail_row_count: 3,
      market_value_amount: "720.00",
      amortized_cost_amount: "648.00",
      accrued_interest_amount: "36.00",
    },
    {
      row_key: "tyw:repo-1:CNY:liability:H:AC",
      source_family: "tyw",
      display_name: "repo-1",
      owner_name: "同业负债池",
      category_name: "卖出回购",
      position_scope: "liability",
      currency_basis: "CNY",
      invest_type_std: "H",
      accounting_basis: "AC",
      detail_row_count: 1,
      market_value_amount: "72.00",
      amortized_cost_amount: "72.00",
      accrued_interest_amount: "14.40",
    },
    {
      row_key: "zqtz:240002.IB:portfolio-b:cc-2:CNY:asset:H:AC",
      source_family: "zqtz",
      display_name: "240002.IB",
      owner_name: "高等级组合",
      category_name: "摊余成本",
      position_scope: "asset",
      currency_basis: "CNY",
      invest_type_std: "H",
      accounting_basis: "AC",
      detail_row_count: 2,
      market_value_amount: "410.00",
      amortized_cost_amount: "403.00",
      accrued_interest_amount: "20.00",
    },
  ];
  return rows.filter((row) => {
    const matchesScope = positionScope === "all" || row.position_scope === positionScope;
    const matchesBasis = row.currency_basis === currencyBasis;
    return matchesScope && matchesBasis;
  });
}

function buildMockBalanceAnalysisSummaryTable(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
  limit: number,
  offset: number,
): ApiEnvelope<BalanceAnalysisSummaryTablePayload> {
  const rows = buildMockBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
  return buildMockApiEnvelope(
    "balance-analysis.summary",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      limit,
      offset,
      total_rows: rows.length,
      rows: rows.slice(offset, offset + limit),
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

function buildMockBalanceAnalysisSummaryCsv(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): BalanceAnalysisSummaryExportPayload {
  const rows = buildMockBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
  const headers = [
    "row_key",
    "source_family",
    "display_name",
    "owner_name",
    "category_name",
    "position_scope",
    "currency_basis",
    "invest_type_std",
    "accounting_basis",
    "detail_row_count",
    "market_value_amount",
    "amortized_cost_amount",
    "accrued_interest_amount",
    "report_date",
    "source_version",
    "rule_version",
  ];
  const lines = rows.map((row) =>
    [
      row.row_key,
      row.source_family,
      row.display_name,
      row.owner_name,
      row.category_name,
      row.position_scope,
      row.currency_basis,
      row.invest_type_std,
      row.accounting_basis,
      String(row.detail_row_count),
      String(row.market_value_amount),
      String(row.amortized_cost_amount),
      String(row.accrued_interest_amount),
      reportDate,
      "sv_balance_mock",
      "rv_balance_analysis_formal_materialize_v1",
    ].join(","),
  );
  return {
    filename: `balance-analysis-summary-${reportDate}-${positionScope}-${currencyBasis}.csv`,
    content: [headers.join(","), ...lines].join("\n"),
  };
}

function buildMockBalanceAnalysisWorkbook(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): ApiEnvelope<BalanceAnalysisWorkbookPayload> {
  return buildMockApiEnvelope(
    "balance-analysis.workbook",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      cards: [
        {
          key: "bond_assets_excluding_issue",
          label: "债券资产(剔除发行类)",
          value: "720.00",
          note: "ZQTZ 资产端剔除发行类后的余额。",
        },
        {
          key: "interbank_assets",
          label: "同业资产",
          value: "36.00",
          note: "TYW 资产端余额。",
        },
        {
          key: "interbank_liabilities",
          label: "同业负债",
          value: "72.00",
          note: "TYW 负债端余额。",
        },
        {
          key: "issuance_liabilities",
          label: "发行类负债",
          value: "18.00",
          note: "ZQTZ 发行类单列余额。",
        },
        {
          key: "net_position",
          label: "净头寸",
          value: "648.00",
          note: "资产端合计 - 同业负债。",
        },
      ],
      tables: [
        {
          key: "bond_business_types",
          title: "债券业务种类",
          section_kind: "table",
          columns: [
            { key: "bond_type", label: "业务种类" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              bond_type: "政策性金融债",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "maturity_gap",
          title: "期限缺口分析",
          section_kind: "table",
          columns: [
            { key: "bucket", label: "期限分类" },
            { key: "gap_amount", label: "缺口" },
          ],
          rows: [
            {
              bucket: "1-2年",
              gap_amount: "648.00",
            },
          ],
        },
        {
          key: "rating_analysis",
          title: "信用评级分析",
          section_kind: "table",
          columns: [
            { key: "rating", label: "评级" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              rating: "AAA",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "issuance_business_types",
          title: "发行类分析",
          section_kind: "table",
          columns: [
            { key: "bond_type", label: "业务种类" },
            { key: "balance_amount", label: "金额" },
          ],
          rows: [
            {
              bond_type: "同业存单",
              balance_amount: "180.00",
            },
          ],
        },
        {
          key: "industry_distribution",
          title: "行业分布",
          section_kind: "table",
          columns: [
            { key: "industry_name", label: "行业" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              industry_name: "金融业",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "rate_distribution",
          title: "利率分布分析",
          section_kind: "table",
          columns: [
            { key: "bucket", label: "利率区间" },
            { key: "bond_amount", label: "债券面值" },
            { key: "interbank_asset_amount", label: "同业资产" },
            { key: "interbank_liability_amount", label: "同业负债" },
          ],
          rows: [
            {
              bucket: "1.5%-2.0%",
              bond_amount: "9900.75",
              interbank_asset_amount: "958.00",
              interbank_liability_amount: "2206.08",
            },
          ],
        },
        {
          key: "counterparty_types",
          title: "对手方类型",
          section_kind: "table",
          columns: [
            { key: "counterparty_type", label: "对手方类型" },
            { key: "asset_amount", label: "资产金额" },
            { key: "liability_amount", label: "负债金额" },
            { key: "net_position_amount", label: "净头寸" },
          ],
          rows: [
            {
              counterparty_type: "股份制银行",
              asset_amount: "120.00",
              liability_amount: "86.08",
              net_position_amount: "33.92",
            },
          ],
        },
        {
          key: "interest_modes",
          title: "计息方式",
          section_kind: "table",
          columns: [
            { key: "interest_mode", label: "计息方式" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              interest_mode: "固定",
              balance_amount: "32874.42",
            },
          ],
        },
      ],
      operational_sections: [
        {
          key: "decision_items",
          title: "决策事项",
          section_kind: "decision_items",
          columns: [
            { key: "title", label: "Title" },
            { key: "action_label", label: "Action" },
            { key: "severity", label: "Severity" },
            { key: "reason", label: "Reason" },
          ],
          rows: [
            {
              title: "Review 1-2 year gap positioning",
              action_label: "Review gap",
              severity: "high",
              reason: "Bucket gap is 648.00 wan yuan.",
              source_section: "maturity_gap",
              rule_id: "bal_wb_decision_gap_001",
              rule_version: "v1",
            },
          ],
        },
        {
          key: "event_calendar",
          title: "事件日历",
          section_kind: "event_calendar",
          columns: [
            { key: "event_date", label: "Event Date" },
            { key: "event_type", label: "Event Type" },
            { key: "title", label: "Title" },
            { key: "impact_hint", label: "Impact Hint" },
          ],
          rows: [
            {
              event_date: "2026-01-31",
              event_type: "asset_maturity",
              title: "asset-1 maturity",
              source: "internal_governed_schedule",
              impact_hint: "asset book / 拆放同业",
              source_section: "maturity_gap",
            },
            {
              event_date: "2026-02-05",
              event_type: "funding_rollover",
              title: "repo-1 maturity",
              source: "internal_governed_schedule",
              impact_hint: "liability book / 卖出回购",
              source_section: "maturity_gap",
            },
          ],
        },
        {
          key: "risk_alerts",
          title: "风险预警",
          section_kind: "risk_alerts",
          columns: [
            { key: "title", label: "Title" },
            { key: "severity", label: "Severity" },
            { key: "reason", label: "Reason" },
          ],
          rows: [
            {
              title: "Issuance liabilities outstanding",
              severity: "medium",
              reason: "Issuance book totals 18.00 wan yuan.",
              source_section: "issuance_business_types",
              rule_id: "bal_wb_risk_issuance_001",
              rule_version: "v1",
            },
            {
              title: "Negative gap in 1-2 year bucket",
              severity: "high",
              reason: "Gap dropped to -128.00 wan yuan.",
              source_section: "maturity_gap",
              rule_id: "bal_wb_risk_gap_001",
              rule_version: "v1",
            },
          ],
        },
      ],
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

function buildMockBalanceAnalysisDecisionItems(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): ApiEnvelope<BalanceAnalysisDecisionItemsPayload> {
  return buildMockApiEnvelope(
    "balance-analysis.decision-items",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      columns: [
        { key: "title", label: "Title" },
        { key: "action_label", label: "Action" },
        { key: "severity", label: "Severity" },
        { key: "reason", label: "Reason" },
        { key: "source_section", label: "Source Section" },
        { key: "rule_id", label: "Rule Id" },
        { key: "rule_version", label: "Rule Version" },
      ],
      rows: [
        {
          decision_key: "bal_wb_decision_gap_001::maturity_gap::Review 1-2 year gap positioning",
          title: "Review 1-2 year gap positioning",
          action_label: "Review gap",
          severity: "high",
          reason: "Bucket gap is 648.00 wan yuan.",
          source_section: "maturity_gap",
          rule_id: "bal_wb_decision_gap_001",
          rule_version: "v1",
          latest_status: {
            decision_key:
              "bal_wb_decision_gap_001::maturity_gap::Review 1-2 year gap positioning",
            status: "pending",
            updated_at: null,
            updated_by: null,
            comment: null,
          },
        },
      ],
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

export class ActionRequestError extends Error {
  readonly status: number;
  readonly runId?: string;
  /** Top-level `error_message` from the JSON body when present. */
  readonly errorMessage?: string;
  /** Raw `detail` field from the JSON body (string, object, or array). */
  readonly detail?: unknown;

  constructor(
    message: string,
    opts: {
      status: number;
      runId?: string;
      errorMessage?: string;
      detail?: unknown;
    },
  ) {
    super(message);
    this.name = "ActionRequestError";
    this.status = opts.status;
    this.runId = opts.runId;
    this.errorMessage = opts.errorMessage;
    this.detail = opts.detail;
  }
}

function extractApiRunId(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const top = body.run_id;
  if (typeof top === "string" && top.trim()) {
    return top;
  }
  const detail = body.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const nested = (detail as Record<string, unknown>).run_id;
    if (typeof nested === "string" && nested.trim()) {
      return nested;
    }
  }
  return undefined;
}

function extractTopLevelErrorMessage(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const errMsg = (payload as Record<string, unknown>).error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  return undefined;
}

function extractApiErrorDetail(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const errMsg = body.error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  const detail = body.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as Record<string, unknown>;
    const nestedMsg = d.error_message;
    if (typeof nestedMsg === "string" && nestedMsg.trim()) {
      return nestedMsg;
    }
    const nestedDetail = d.detail;
    if (typeof nestedDetail === "string" && nestedDetail.trim()) {
      return nestedDetail;
    }
  }
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (typeof item === "string") {
        return item;
      }
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg: unknown }).msg);
      }
      try {
        return JSON.stringify(item);
      } catch {
        return String(item);
      }
    });
    const joined = parts.filter((p) => p.trim()).join("; ");
    return joined || undefined;
  }
  return undefined;
}

function extractRawDetail(payload: unknown): unknown {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  if (!("detail" in (payload as Record<string, unknown>))) {
    return undefined;
  }
  return (payload as Record<string, unknown>).detail;
}

const requestJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<T>> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as ApiEnvelope<T>;
};

/** V1 风格：响应体即为业务 JSON，无 `ApiEnvelope` 包裹（负债结构等接口待迁移）。 */
const requestPlainJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
): Promise<T> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as T;
};

const requestEnvelopeOrPlainJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
): Promise<T> => {
  const payload = await requestPlainJson<Record<string, unknown>>(fetchImpl, baseUrl, path);
  if (
    payload &&
    typeof payload === "object" &&
    "result_meta" in payload &&
    "result" in payload
  ) {
    return payload.result as T;
  }
  return payload as T;
};

function normalizeAdbComparisonResponse(raw: Record<string, unknown>): AdbComparisonResponse {
  const mapBreakdown = (items: unknown[]) =>
    items.map((item) => {
      const row = item as Record<string, unknown>;
      return {
        category: String(row.category ?? ""),
        spot_balance: Number(row.spot_balance ?? 0),
        avg_balance: Number(row.avg_balance ?? 0),
        proportion: Number(row.proportion ?? 0),
        weighted_rate:
          row.weighted_rate === null || row.weighted_rate === undefined
            ? null
            : Number(row.weighted_rate),
      };
    });

  const assetsBreakdown = mapBreakdown(
    Array.isArray(raw.assets_breakdown) ? raw.assets_breakdown : [],
  );
  const liabilitiesBreakdown = mapBreakdown(
    Array.isArray(raw.liabilities_breakdown) ? raw.liabilities_breakdown : [],
  );

  return {
    report_date: String(raw.report_date ?? raw.end_date ?? ""),
    start_date: String(raw.start_date ?? ""),
    end_date: String(raw.end_date ?? ""),
    num_days: Number(raw.num_days ?? 0),
    simulated: Boolean(raw.simulated),
    total_spot_assets: Number(raw.total_spot_assets ?? 0),
    total_avg_assets: Number(raw.total_avg_assets ?? 0),
    total_spot_liabilities: Number(raw.total_spot_liabilities ?? 0),
    total_avg_liabilities: Number(raw.total_avg_liabilities ?? 0),
    asset_yield:
      raw.asset_yield === null || raw.asset_yield === undefined ? null : Number(raw.asset_yield),
    liability_cost:
      raw.liability_cost === null || raw.liability_cost === undefined
        ? null
        : Number(raw.liability_cost),
    net_interest_margin:
      raw.net_interest_margin === null || raw.net_interest_margin === undefined
        ? null
        : Number(raw.net_interest_margin),
    assets_breakdown: assetsBreakdown,
    liabilities_breakdown: liabilitiesBreakdown,
    detail: raw.detail ? String(raw.detail) : undefined,
  };
}

function normalizeAdbMonthlyResponse(raw: Record<string, unknown>): AdbMonthlyResponse {
  const months = Array.isArray(raw.months) ? raw.months : [];
  return {
    year: Number(raw.year ?? 0),
    months: months.map((item) => {
      const row = item as Record<string, unknown>;
      const breakdownAssets = Array.isArray(row.breakdown_assets) ? row.breakdown_assets : [];
      const breakdownLiabilities = Array.isArray(row.breakdown_liabilities)
        ? row.breakdown_liabilities
        : [];
      const mapBreakdown = (entries: unknown[]) =>
        entries.map((entry) => {
          const breakdown = entry as Record<string, unknown>;
          return {
            category: String(breakdown.category ?? ""),
            avg_balance: Number(breakdown.avg_balance ?? 0),
            proportion:
              breakdown.proportion === null || breakdown.proportion === undefined
                ? null
                : Number(breakdown.proportion),
            weighted_rate:
              breakdown.weighted_rate === null || breakdown.weighted_rate === undefined
                ? null
                : Number(breakdown.weighted_rate),
          };
        });

      return {
        month: String(row.month ?? ""),
        month_label: String(row.month_label ?? row.month ?? ""),
        num_days: Number(row.num_days ?? 0),
        avg_assets: Number(row.avg_assets ?? 0),
        avg_liabilities: Number(row.avg_liabilities ?? 0),
        asset_yield:
          row.asset_yield === null || row.asset_yield === undefined
            ? null
            : Number(row.asset_yield),
        liability_cost:
          row.liability_cost === null || row.liability_cost === undefined
            ? null
            : Number(row.liability_cost),
        net_interest_margin:
          row.net_interest_margin === null || row.net_interest_margin === undefined
            ? null
            : Number(row.net_interest_margin),
        mom_change_assets:
          row.mom_change_assets === null || row.mom_change_assets === undefined
            ? null
            : Number(row.mom_change_assets),
        mom_change_pct_assets:
          row.mom_change_pct_assets === null || row.mom_change_pct_assets === undefined
            ? null
            : Number(row.mom_change_pct_assets),
        mom_change_liabilities:
          row.mom_change_liabilities === null || row.mom_change_liabilities === undefined
            ? null
            : Number(row.mom_change_liabilities),
        mom_change_pct_liabilities:
          row.mom_change_pct_liabilities === null || row.mom_change_pct_liabilities === undefined
            ? null
            : Number(row.mom_change_pct_liabilities),
        breakdown_assets: mapBreakdown(breakdownAssets),
        breakdown_liabilities: mapBreakdown(breakdownLiabilities),
      };
    }),
    ytd_avg_assets: Number(raw.ytd_avg_assets ?? 0),
    ytd_avg_liabilities: Number(raw.ytd_avg_liabilities ?? 0),
    ytd_asset_yield:
      raw.ytd_asset_yield === null || raw.ytd_asset_yield === undefined
        ? null
        : Number(raw.ytd_asset_yield),
    ytd_liability_cost:
      raw.ytd_liability_cost === null || raw.ytd_liability_cost === undefined
        ? null
        : Number(raw.ytd_liability_cost),
    ytd_nim:
      raw.ytd_nim === null || raw.ytd_nim === undefined ? null : Number(raw.ytd_nim),
    unit: raw.unit ? String(raw.unit) : undefined,
  };
}

const requestActionJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    const detailText =
      extractApiErrorDetail(body) ?? `Request failed: ${path} (${response.status})`;
    const runId = extractApiRunId(body);
    const rawDetail = extractRawDetail(body);
    const topErrorMessage = extractTopLevelErrorMessage(body);
    const nestedDetail =
      rawDetail && typeof rawDetail === "object" && !Array.isArray(rawDetail)
        ? (rawDetail as Record<string, unknown>).error_message
        : undefined;
    const errorMessageField =
      topErrorMessage ??
      (typeof nestedDetail === "string" && nestedDetail.trim() ? nestedDetail : undefined);
    throw new ActionRequestError(detailText, {
      status: response.status,
      runId,
      errorMessage: errorMessageField,
      detail: rawDetail,
    });
  }

  return (await response.json()) as T;
};

function kpiQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === "") continue;
    q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

async function requestKpiJson<T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetchImpl(`${baseUrl}/api/kpi${path}`, {
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init?.headers as Record<string, string> | undefined),
    },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `KPI API ${response.status}`);
  }
  return response.json() as Promise<T>;
}

const requestText = async (
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  fallbackFilename = "download.csv",
): Promise<{ content: string; filename: string }> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "text/csv, text/plain;q=0.9, */*;q=0.8",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  const contentDisposition = response.headers.get("Content-Disposition") ?? "";
  return {
    content: await response.text(),
    filename: parseDownloadFilename(contentDisposition, fallbackFilename),
  };
};

function parseDownloadFilename(contentDisposition: string, fallbackFilename: string) {
  const utf8Match = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(contentDisposition);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const filenameMatch = /filename=\"?([^\";]+)\"?/i.exec(contentDisposition);
  return filenameMatch?.[1] ?? fallbackFilename;
}

const requestBlob = async (
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  fallbackFilename = "download.bin",
): Promise<{ content: Blob; filename: string }> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/octet-stream;q=0.9, */*;q=0.8",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  const contentDisposition = response.headers.get("Content-Disposition") ?? "";
  return {
    content: await response.blob(),
    filename: parseDownloadFilename(contentDisposition, fallbackFilename),
  };
};

const requestActionWithBody = async <TResponse, TBody>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  body: TBody,
): Promise<TResponse> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as TResponse;
};

export function createApiClient(options: ApiClientOptions = {}): ApiClient {
  const mode = options.mode ?? parseEnvMode();
  const baseUrl = normalizeBaseUrl(options.baseUrl ?? parseBaseUrl());
  const fetchImpl = options.fetchImpl ?? defaultFetch;
  const mockManualAdjustments: ProductCategoryManualAdjustmentPayload[] = [];
  let mockManualAdjustmentSeq = 0;

  const mockClient: ApiClient = {
    mode: "mock",
    async getHealth() {
      await delay();
      return { status: "ok" };
    },
    async getOverview() {
      await delay();
      return buildMockApiEnvelope("executive.overview", overviewPayload);
    },
    async getSummary() {
      await delay();
      return buildMockApiEnvelope("executive.summary", summaryPayload);
    },
    async getFormalPnlDates(basis = "formal") {
      await delay();
      return buildMockApiEnvelope(
        "pnl.dates",
        {
          report_dates: [],
          formal_fi_report_dates: [],
          nonstd_bridge_report_dates: [],
        },
        { basis, formal_use_allowed: basis === "formal" },
      );
    },
    async getFormalPnlData(date: string, basis = "formal") {
      await delay();
      return buildMockApiEnvelope(
        "pnl.data",
        {
          report_date: date,
          formal_fi_rows: [],
          nonstd_bridge_rows: [],
        },
        { basis, formal_use_allowed: basis === "formal" },
      );
    },
    async getFormalPnlOverview(reportDate: string, basis = "formal") {
      await delay();
      return buildMockApiEnvelope(
        "pnl.overview",
        {
          report_date: reportDate,
          formal_fi_row_count: 0,
          nonstd_bridge_row_count: 0,
          interest_income_514: "0.00",
          fair_value_change_516: "0.00",
          capital_gain_517: "0.00",
          manual_adjustment: "0.00",
          total_pnl: "0.00",
        },
        { basis, formal_use_allowed: basis === "formal" },
      );
    },
    async getLedgerPnlDates() {
      await delay();
      return buildMockApiEnvelope("ledger_pnl.dates", mockLedgerPnlDates, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
    async getLedgerPnlData(reportDate: string, currency) {
      await delay();
      return buildMockApiEnvelope(
        "ledger_pnl.data",
        {
          ...mockLedgerPnlData,
          report_date: reportDate,
          items: currency
            ? mockLedgerPnlData.items.filter((item) => item.currency === currency)
            : mockLedgerPnlData.items,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getLedgerPnlSummary(reportDate: string, currency) {
      await delay();
      return buildMockApiEnvelope(
        "ledger_pnl.summary",
        {
          ...mockLedgerPnlSummary,
          report_date: reportDate,
          by_currency: currency
            ? mockLedgerPnlSummary.by_currency.filter((item) => item.currency === currency)
            : mockLedgerPnlSummary.by_currency,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPnlBridge(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.bridge",
        {
          report_date: reportDate,
          rows: [],
          summary: {
            row_count: 0,
            ok_count: 0,
            warning_count: 0,
            error_count: 0,
            total_beginning_dirty_mv: "0",
            total_ending_dirty_mv: "0",
            total_carry: "0",
            total_roll_down: "0",
            total_treasury_curve: "0",
            total_credit_spread: "0",
            total_fx_translation: "0",
            total_realized_trading: "0",
            total_unrealized_fv: "0",
            total_manual_adjustment: "0",
            total_explained_pnl: "0",
            total_actual_pnl: "0",
            total_residual: "0",
            quality_flag: "ok",
          },
          warnings: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async refreshFormalPnl(reportDate?: string) {
      await delay();
      return {
        status: "queued",
        run_id: "pnl_materialize:mock-run",
        job_name: "pnl_materialize",
        trigger_mode: "async",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: reportDate ?? "2026-02-28",
      };
    },
    async getFormalPnlImportStatus(runId?: string) {
      await delay();
      return {
        status: runId ? "completed" : "idle",
        run_id: runId ?? "pnl_materialize:mock-run",
        job_name: "pnl_materialize",
        trigger_mode: runId ? "terminal" : "idle",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: "2026-02-28",
        source_version: "sv_mock_dashboard_v2",
      };
    },
    async getPnlAttribution() {
      await delay();
      return buildMockApiEnvelope("executive.pnl-attribution", pnlAttributionPayload);
    },
    async getVolumeRateAttribution(options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.volume_rate", {
        ...mockVolumeRateAttribution,
        compare_type: options?.compareType ?? mockVolumeRateAttribution.compare_type,
      });
    },
    async getTplMarketCorrelation(_options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.tpl_market", mockTplMarketCorrelation);
    },
    async getPnlCompositionBreakdown(_options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.composition", mockPnlComposition);
    },
    async getPnlAttributionAnalysisSummary(_reportDate) {
      await delay();
      return buildMockApiEnvelope(
        "pnl_attribution.summary",
        mockPnlAttributionAnalysisSummary,
      );
    },
    async getPnlCarryRollDown(_reportDate) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.carry_rolldown", mockCarryRollDown);
    },
    async getPnlSpreadAttribution(_options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.spread", mockSpreadAttribution);
    },
    async getPnlKrdAttribution(_options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.krd", mockKrdAttribution);
    },
    async getPnlAdvancedAttributionSummary(_reportDate) {
      await delay();
      return buildMockApiEnvelope(
        "pnl_attribution.advanced_summary",
        mockAdvancedAttributionSummary,
      );
    },
    async getPnlCampisiAttribution(_options) {
      await delay();
      return buildMockApiEnvelope("pnl_attribution.campisi", mockCampisiAttribution);
    },
    async getPnlCampisiFourEffects(_options) {
      await delay();
      return buildMockApiEnvelope("campisi.four_effects", mockCampisiFourEffects, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
    async getPnlCampisiEnhanced(_options) {
      await delay();
      return buildMockApiEnvelope("campisi.enhanced", mockCampisiEnhanced, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
    async getPnlCampisiMaturityBuckets(_options) {
      await delay();
      return buildMockApiEnvelope("campisi.maturity_buckets", mockCampisiMaturityBuckets, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
    async getRiskOverview() {
      await delay();
      return buildMockApiEnvelope("executive.risk-overview", riskOverviewPayload);
    },
    async getRiskTensorDates() {
      await delay();
      return buildMockApiEnvelope(
        "risk.tensor.dates",
        {
          report_dates: ["2026-02-28", "2026-01-31", "2025-12-31"],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getRiskTensor(reportDate: string) {
      await delay();
      const zero = "0.00000000";
      return buildMockApiEnvelope(
        "risk.tensor",
        {
          report_date: reportDate,
          portfolio_dv01: zero,
          krd_1y: zero,
          krd_3y: zero,
          krd_5y: zero,
          krd_7y: zero,
          krd_10y: zero,
          krd_30y: zero,
          cs01: zero,
          portfolio_convexity: zero,
          portfolio_modified_duration: zero,
          issuer_concentration_hhi: zero,
          issuer_top5_weight: zero,
          liquidity_gap_30d: zero,
          liquidity_gap_90d: zero,
          liquidity_gap_30d_ratio: zero,
          total_market_value: zero,
          bond_count: 0,
          quality_flag: "ok",
          warnings: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getContribution() {
      await delay();
      return buildMockApiEnvelope("executive.contribution", contributionPayload);
    },
    async getAlerts() {
      await delay();
      return buildMockApiEnvelope("executive.alerts", alertsPayload);
    },
    async getPlaceholderSnapshot(key: string) {
      await delay();
      return buildMockApiEnvelope(
        `workbench.${key}`,
        placeholderSnapshots[key] ?? placeholderSnapshots.dashboard,
      );
    },
    async getSourceFoundation() {
      await delay();
      return buildMockApiEnvelope("preview.source-foundation", {
        sources: MOCK_SOURCE_FOUNDATION_SUMMARIES,
      });
    },
    async refreshSourcePreview() {
      await delay();
      return {
        status: "queued",
        run_id: "source_preview_refresh:mock-run",
        job_name: "source_preview_refresh",
        trigger_mode: "async",
        cache_key: "source_preview.foundation",
        preview_sources: ["zqtz", "tyw"],
      };
    },
    async getSourcePreviewRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "source_preview_refresh",
        trigger_mode: "terminal",
        cache_key: "source_preview.foundation",
        preview_sources: ["zqtz", "tyw"],
        ingest_batch_id: "ib_mock_preview",
        source_version: "sv_mock_preview_refresh",
      };
    },
    async getSourceFoundationHistory({ sourceFamily, limit, offset }) {
      await delay();
      const rows = sourceFamily
        ? MOCK_SOURCE_FOUNDATION_SUMMARIES.filter(
            (summary) => summary.source_family === sourceFamily,
          )
        : MOCK_SOURCE_FOUNDATION_SUMMARIES;
      return buildMockApiEnvelope("preview.source-foundation.history", {
        limit,
        offset,
        total_rows: rows.length,
        rows: rows.slice(offset, offset + limit),
      });
    },
    async getSourceFoundationRows({ sourceFamily, ingestBatchId, limit, offset }) {
      await delay();
      const rows =
        sourceFamily === "zqtz"
          ? [
              {
                ingest_batch_id: ingestBatchId,
                row_locator: 1,
                report_date: "2025-12-31",
                business_type_primary: "其他债券",
                business_type_final: "公募基金",
                asset_group: "基金类",
                instrument_code: "SA0001",
                instrument_name: "MOCK-ZQTZ",
                account_category: "银行账户",
                manual_review_needed: false,
              },
            ]
          : [
              {
                ingest_batch_id: ingestBatchId,
                row_locator: 1,
                report_date: "2025-12-31",
                business_type_primary: "同业拆入",
                product_group: "拆借类",
                institution_category: "bank",
                special_nature: "普通",
                counterparty_name: "MOCK-TYW",
                investment_portfolio: "拆借自营",
                manual_review_needed: false,
              },
            ];
      return buildMockApiEnvelope(`preview.${sourceFamily}.rows`, {
        source_family: sourceFamily,
        ingest_batch_id: ingestBatchId,
        limit,
        offset,
        total_rows: rows.length,
        columns: buildMockSourcePreviewColumns(rows),
        rows,
      });
    },
    async getSourceFoundationTraces({ sourceFamily, ingestBatchId, limit, offset }) {
      await delay();
      const rows = [
        {
          ingest_batch_id: ingestBatchId,
          row_locator: 1,
          trace_step: 1,
          field_name: sourceFamily === "zqtz" ? "业务种类1" : "产品类型",
          field_value: sourceFamily === "zqtz" ? "其他债券" : "同业拆入",
          derived_label: sourceFamily === "zqtz" ? "公募基金" : "拆借类",
          manual_review_needed: false,
        },
      ];
      return buildMockApiEnvelope(`preview.${sourceFamily}.traces`, {
        source_family: sourceFamily,
        ingest_batch_id: ingestBatchId,
        limit,
        offset,
        total_rows: rows.length,
        columns: buildMockSourcePreviewColumns(rows),
        rows,
      });
    },
    async getMacroFoundation() {
      await delay();
      return buildMockApiEnvelope(
        "preview.macro-foundation",
        MOCK_MACRO_FOUNDATION_PAYLOAD,
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_macro_vendor_mock",
          vendor_version: "vv_choice_catalog_v1",
          rule_version: "rv_phase1_macro_vendor_v1",
          cache_version: "cv_phase1_macro_vendor_v1",
        },
      );
    },
    async getChoiceMacroLatest() {
      await delay();
      return buildMockApiEnvelope(
        "macro.choice.latest",
        MOCK_CHOICE_MACRO_LATEST_PAYLOAD,
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_choice_macro_mock",
          vendor_version: "vv_choice_macro_20260410",
          rule_version: "rv_choice_macro_thin_slice_v1",
          cache_version: "cv_choice_macro_thin_slice_v1",
        },
      );
    },
    async refreshChoiceMacro(_backfillDays?: number) {
      await delay();
      return {
        status: "completed",
        run_id: "choice_macro_refresh:mock-run",
      } as ChoiceMacroRefreshPayload;
    },
    async getChoiceMacroRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
      } as ChoiceMacroRefreshPayload;
    },
    async getMacroBondLinkageAnalysis({ reportDate }) {
      await delay();
      return buildMockApiEnvelope(
        "macro_bond_linkage.analysis",
        {
          ...MOCK_MACRO_BOND_LINKAGE_PAYLOAD,
          report_date: reportDate,
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_macro_bond_linkage_mock",
          vendor_version: "vv_choice_macro_mock",
          rule_version: "rv_macro_bond_linkage_v1",
          cache_version: "cv_macro_bond_linkage_v1",
          quality_flag: "warning",
        },
      );
    },
    async getFxFormalStatus() {
      await delay();
      return buildMockApiEnvelope(
        "fx.formal.status",
        MOCK_FX_FORMAL_STATUS_PAYLOAD,
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_fx_formal_mock",
          vendor_version: "vv_fx_formal_mock",
          rule_version: "rv_fx_formal_mid_v1",
          cache_version: "cv_fx_formal_mid_v1",
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "latest_snapshot",
        },
      );
    },
    async getFxAnalytical() {
      await delay();
      return buildMockApiEnvelope(
        "fx.analytical.groups",
        MOCK_FX_ANALYTICAL_PAYLOAD,
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_fx_analytical_mock",
          vendor_version: "vv_fx_analytical_mock",
          rule_version: "rv_fx_analytical_v1",
          cache_version: "cv_fx_analytical_v1",
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "latest_snapshot",
        },
      );
    },
    async getChoiceNewsEvents(options) {
      await delay();
      return buildMockChoiceNewsEnvelope(options);
    },
    async getProductCategoryDates() {
      await delay();
      return buildMockApiEnvelope(
        "product_category_pnl.dates",
        {
          report_dates: ["2026-02-28", "2026-01-31"],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async refreshProductCategoryPnl() {
      await delay();
      return {
        status: "queued",
        run_id: "product_category_pnl:mock-run",
        job_name: "product_category_pnl",
        trigger_mode: "async",
        cache_key: "product_category_pnl.formal",
      };
    },
    async getProductCategoryRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "product_category_pnl",
        trigger_mode: "async",
        cache_key: "product_category_pnl.formal",
        month_count: 2,
        report_dates: ["2026-01-31", "2026-02-28"],
        rule_version: "rv_product_category_pnl_v1",
        source_version: "sv_mock_dashboard_v2",
      };
    },
    async createProductCategoryManualAdjustment(payload) {
      await delay();
      mockManualAdjustmentSeq += 1;
      const record = {
        adjustment_id: `pca-mock-${mockManualAdjustmentSeq}`,
        event_type: "created",
        created_at: "2026-04-10T09:30:00Z",
        stream: "product_category_pnl_adjustments",
        report_date: payload.report_date,
        operator: payload.operator,
        approval_status: payload.approval_status,
        account_code: payload.account_code,
        currency: payload.currency,
        account_name: payload.account_name ?? "",
        beginning_balance: payload.beginning_balance ?? null,
        ending_balance: payload.ending_balance ?? null,
        monthly_pnl: payload.monthly_pnl ?? null,
        daily_avg_balance: payload.daily_avg_balance ?? null,
        annual_avg_balance: payload.annual_avg_balance ?? null,
      };
      mockManualAdjustments.unshift(record);
      return record;
    },
    async getProductCategoryManualAdjustments(reportDate, options = {}) {
      await delay();
      const allEvents = mockManualAdjustments.filter(
        (item) => item.report_date === reportDate,
      );
      const events = sortManualAdjustments(
        filterManualAdjustments(allEvents, options, true),
        options.eventSortField ?? "created_at",
        options.eventSortDir ?? "desc",
      );
      const limit = options.limit ?? 20;
      const offset = options.offset ?? 0;
      const adjustmentLimit = options.adjustmentLimit ?? 20;
      const adjustmentOffset = options.adjustmentOffset ?? 0;
      const pagedEvents = events.slice(offset, offset + limit);
      const adjustments = sortManualAdjustments(
        filterManualAdjustments(reduceLatestManualAdjustments(allEvents), options, false),
        options.currentSortField ?? "created_at",
        options.currentSortDir ?? "desc",
      );
      return {
        report_date: reportDate,
        adjustment_count: adjustments.length,
        adjustment_limit: adjustmentLimit,
        adjustment_offset: adjustmentOffset,
        event_total: events.length,
        event_limit: limit,
        event_offset: offset,
        adjustments: adjustments.slice(
          adjustmentOffset,
          adjustmentOffset + adjustmentLimit,
        ),
        events: pagedEvents,
      };
    },
    async exportProductCategoryManualAdjustmentsCsv(reportDate, options = {}) {
      await delay();
      const allEvents = mockManualAdjustments.filter(
        (item) => item.report_date === reportDate,
      );
      const filteredEvents = sortManualAdjustments(
        filterManualAdjustments(allEvents, options, true),
        options.eventSortField ?? "created_at",
        options.eventSortDir ?? "desc",
      );
      const filteredAdjustments = sortManualAdjustments(
        filterManualAdjustments(reduceLatestManualAdjustments(allEvents), options, false),
        options.currentSortField ?? "created_at",
        options.currentSortDir ?? "desc",
      );
      const headers = [
        "adjustment_id",
        "event_type",
        "created_at",
        "report_date",
        "operator",
        "approval_status",
        "account_code",
        "currency",
        "account_name",
      ];
      const toCsv = (rows: ProductCategoryManualAdjustmentPayload[]) =>
        rows
          .map((row) =>
            headers
              .map((header) => {
                const value = String(
                  (row as Record<string, string | number | null | undefined>)[header] ?? "",
                ).replace(/"/g, '""');
                return `"${value}"`;
              })
              .join(","),
          )
          .join("\n");
      return {
        filename: `product-category-audit-${reportDate}.csv`,
        content: [
          "Current State",
          headers.join(","),
          toCsv(filteredAdjustments),
          "",
          "Event Timeline",
          headers.join(","),
          toCsv(filteredEvents),
        ].join("\n"),
      };
    },
    async updateProductCategoryManualAdjustment(adjustmentId, payload) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const updated = {
        ...mockManualAdjustments[index],
        ...payload,
        event_type: "edited",
        created_at: "2026-04-10T09:40:00Z",
      };
      mockManualAdjustments.unshift(updated);
      return updated;
    },
    async revokeProductCategoryManualAdjustment(adjustmentId) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const revoked = {
        ...mockManualAdjustments[index],
        event_type: "revoked",
        approval_status: "rejected",
        created_at: "2026-04-10T09:45:00Z",
      };
      mockManualAdjustments.unshift(revoked);
      return revoked;
    },
    async restoreProductCategoryManualAdjustment(adjustmentId) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const restored = {
        ...mockManualAdjustments[index],
        event_type: "restored",
        approval_status: "approved",
        created_at: "2026-04-10T09:50:00Z",
      };
      mockManualAdjustments.unshift(restored);
      return restored;
    },
    async getProductCategoryPnl(options) {
      await delay();
      return buildMockProductCategoryPnlEnvelope(options);
    },
    async getQdbGlMonthlyAnalysisDates() {
      await delay();
      return buildMockApiEnvelope(
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
      return buildMockApiEnvelope(
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
      return buildMockApiEnvelope(
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
    async getBalanceAnalysisDates() {
      await delay();
      return buildMockApiEnvelope(
        "balance-analysis.dates",
        {
          report_dates: ["2025-12-31"],
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisOverview({ reportDate, positionScope, currencyBasis }) {
      await delay();
      const detailRows = [
        {
          source_family: "zqtz" as const,
          position_scope: "asset" as const,
          currency_basis: "CNY" as const,
          market_value_amount: "720.00",
          amortized_cost_amount: "648.00",
          accrued_interest_amount: "36.00",
        },
        {
          source_family: "tyw" as const,
          position_scope: "liability" as const,
          currency_basis: "CNY" as const,
          market_value_amount: "72.00",
          amortized_cost_amount: "72.00",
          accrued_interest_amount: "14.40",
        },
      ].filter((row) => {
        const matchesScope = positionScope === "all" || row.position_scope === positionScope;
        const matchesBasis = row.currency_basis === currencyBasis;
        return matchesScope && matchesBasis;
      });
      const totals = detailRows.reduce(
        (acc, row) => ({
          detailRowCount: acc.detailRowCount + 1,
          summaryRowCount: acc.summaryRowCount + 1,
          marketValue: acc.marketValue + Number.parseFloat(row.market_value_amount),
          amortizedCost: acc.amortizedCost + Number.parseFloat(row.amortized_cost_amount),
          accruedInterest: acc.accruedInterest + Number.parseFloat(row.accrued_interest_amount),
        }),
        {
          detailRowCount: 0,
          summaryRowCount: 0,
          marketValue: 0,
          amortizedCost: 0,
          accruedInterest: 0,
        },
      );
      return buildMockApiEnvelope(
        "balance-analysis.overview",
        {
          report_date: reportDate,
          position_scope: positionScope,
          currency_basis: currencyBasis,
          detail_row_count: totals.detailRowCount,
          summary_row_count: totals.summaryRowCount,
          total_market_value_amount: totals.marketValue.toFixed(2),
          total_amortized_cost_amount: totals.amortizedCost.toFixed(2),
          total_accrued_interest_amount: totals.accruedInterest.toFixed(2),
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisDetail({ reportDate, positionScope, currencyBasis }) {
      await delay();
      const baseDetails = [
        {
          source_family: "zqtz" as const,
          report_date: reportDate,
          row_key: "zqtz:mock",
          display_name: "240001.IB",
          position_scope: "asset" as const,
          currency_basis: "CNY" as const,
          invest_type_std: "A",
          accounting_basis: "FVOCI",
          market_value_amount: "720.00",
          amortized_cost_amount: "648.00",
          accrued_interest_amount: "36.00",
          is_issuance_like: false,
        },
        {
          source_family: "tyw" as const,
          report_date: reportDate,
          row_key: "tyw:mock",
          display_name: "pos-1",
          position_scope: "liability" as const,
          currency_basis: "CNY" as const,
          invest_type_std: "H",
          accounting_basis: "AC",
          market_value_amount: "72.00",
          amortized_cost_amount: "72.00",
          accrued_interest_amount: "14.40",
          is_issuance_like: null,
        },
      ].filter((row) => {
        const matchesScope = positionScope === "all" || row.position_scope === positionScope;
        const matchesBasis = row.currency_basis === currencyBasis;
        return matchesScope && matchesBasis;
      });
      const summary = baseDetails.map((row) => ({
        source_family: row.source_family,
        position_scope: row.position_scope,
        currency_basis: row.currency_basis,
        row_count: 1,
        market_value_amount: row.market_value_amount,
        amortized_cost_amount: row.amortized_cost_amount,
        accrued_interest_amount: row.accrued_interest_amount,
      }));
      return buildMockApiEnvelope(
        "balance-analysis.detail",
        {
          report_date: reportDate,
          position_scope: positionScope,
          currency_basis: currencyBasis,
          details: baseDetails,
          summary,
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisSummaryByBasis({ reportDate, positionScope, currencyBasis }) {
      await delay();
      const rows: BalanceAnalysisBasisBreakdownPayload["rows"] = [
        {
          source_family: "zqtz" as const,
          invest_type_std: "A",
          accounting_basis: "FVOCI",
          position_scope: "asset" as const,
          currency_basis: "CNY" as const,
          detail_row_count: 3,
          market_value_amount: "720.00",
          amortized_cost_amount: "648.00",
          accrued_interest_amount: "36.00",
        },
        {
          source_family: "tyw" as const,
          invest_type_std: "H",
          accounting_basis: "AC",
          position_scope: "liability" as const,
          currency_basis: "CNY" as const,
          detail_row_count: 1,
          market_value_amount: "72.00",
          amortized_cost_amount: "72.00",
          accrued_interest_amount: "14.40",
        },
      ].filter((row) => {
        const matchesScope = positionScope === "all" || row.position_scope === positionScope;
        const matchesBasis = row.currency_basis === currencyBasis;
        return matchesScope && matchesBasis;
      });
      return buildMockApiEnvelope(
        "balance-analysis.basis_breakdown",
        {
          report_date: reportDate,
          position_scope: positionScope,
          currency_basis: currencyBasis,
          rows,
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisAdvancedAttribution({ reportDate }) {
      await delay();
      return buildMockApiEnvelope(
        "balance-analysis.advanced_attribution_bundle",
        {
          report_date: reportDate,
          mode: "analytical",
          scenario_name: null,
          scenario_inputs: {},
          upstream_summaries: {},
          status: "not_ready",
          missing_inputs: ["phase3_yield_curves_aligned_to_instruments"],
          blocked_components: ["roll_down", "rate_effect"],
          warnings: [
            "bond_analytics.phase3: roll_down / rate_effect require Phase 3 curve and trade data",
            "balance-analysis.advanced_attribution_bundle: status=not_ready; no attribution figures are returned",
          ],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          source_version: "sv_advanced_attribution_not_ready",
          rule_version: "rv_advanced_attribution_bundle_v0",
          cache_version: "cv_advanced_attribution_v0",
        },
      );
    },
    async getBalanceAnalysisSummary({ reportDate, positionScope, currencyBasis, limit, offset }) {
      await delay();
      return buildMockBalanceAnalysisSummaryTable(
        reportDate,
        positionScope,
        currencyBasis,
        limit,
        offset,
      );
    },
    async getBalanceAnalysisWorkbook({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return buildMockBalanceAnalysisWorkbook(reportDate, positionScope, currencyBasis);
    },
    async getBalanceAnalysisCurrentUser() {
      await delay();
      return {
        user_id: "phase1-dev-user",
        role: "admin",
        identity_source: "fallback",
      };
    },
    async getBalanceAnalysisDecisionItems({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return buildMockBalanceAnalysisDecisionItems(reportDate, positionScope, currencyBasis);
    },
    async updateBalanceAnalysisDecisionStatus({
      decisionKey,
      status,
      comment,
    }) {
      await delay();
      return {
        decision_key: decisionKey,
        status,
        updated_at: "2026-04-12T08:00:00Z",
        updated_by: "phase1-dev-user",
        comment: comment ?? null,
      };
    },
    async exportBalanceAnalysisSummaryCsv({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return buildMockBalanceAnalysisSummaryCsv(reportDate, positionScope, currencyBasis);
    },
    async exportBalanceAnalysisWorkbookXlsx({ reportDate }) {
      await delay();
      return {
        filename: `资产负债分析_${reportDate}.xlsx`,
        content: new Blob(["mock-workbook"], {
          type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }),
      };
    },
    async refreshBalanceAnalysis(reportDate: string) {
      await delay();
      return {
        status: "queued",
        run_id: "balance_analysis_materialize:mock-run",
        job_name: "balance_analysis_materialize",
        trigger_mode: "async",
        cache_key: "balance_analysis:materialize:formal",
        report_date: reportDate,
      };
    },
    async getBalanceAnalysisRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "balance_analysis_materialize",
        trigger_mode: "terminal",
        cache_key: "balance_analysis:materialize:formal",
        report_date: "2025-12-31",
        source_version: "sv_balance_mock",
        rule_version: "rv_balance_analysis_formal_materialize_v1",
      };
    },
    async refreshBondAnalytics(reportDate: string) {
      await delay();
      return {
        status: "queued",
        run_id: "bond_analytics_refresh:mock-run",
        job_name: "bond_analytics_refresh",
        cache_key: "bond_analytics:materialize",
        report_date: reportDate,
      };
    },
    async getBondAnalyticsDates() {
      await delay();
      return buildMockApiEnvelope(
        "bond_analytics.dates",
        {
          report_dates: ["2026-03-31", "2026-02-28", "2025-12-31"],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondDashboardDates() {
      await delay();
      return buildMockApiEnvelope(
        "bond_dashboard.dates",
        { report_dates: ["2026-03-31", "2026-02-28", "2025-12-31"] },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondDashboardHeadlineKpis(reportDate: string) {
      await delay();
      const mv = "328709000000.00000000";
      const prevMv = "320000000000.00000000";
      return buildMockApiEnvelope(
        "bond_dashboard.headline_kpis",
        {
          report_date: reportDate,
          prev_report_date: "2026-02-28",
          kpis: {
            total_market_value: mv,
            unrealized_pnl: "1850000000.00000000",
            weighted_ytm: "0.02850000",
            weighted_duration: "3.45000000",
            weighted_coupon: "0.03120000",
            credit_spread_median: "0.00850000",
            total_dv01: "-125430.50000000",
            bond_count: 428,
          },
          prev_kpis: {
            total_market_value: prevMv,
            unrealized_pnl: "1600000000.00000000",
            weighted_ytm: "0.02810000",
            weighted_duration: "3.52000000",
            weighted_coupon: "0.03080000",
            credit_spread_median: "0.00890000",
            total_dv01: "-128900.00000000",
            bond_count: 415,
          },
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondDashboardAssetStructure(reportDate: string, groupBy: string) {
      await delay();
      const total = "328709000000.00000000";
      return buildMockApiEnvelope(
        "bond_dashboard.asset_structure",
        {
          report_date: reportDate,
          group_by: groupBy,
          total_market_value: total,
          items: [
            {
              category: "政策性金融债",
              total_market_value: "98500000000.00000000",
              bond_count: 42,
              percentage: "29.96428571",
            },
            {
              category: "地方政府债",
              total_market_value: "82000000000.00000000",
              bond_count: 56,
              percentage: "24.94571429",
            },
            {
              category: "同业存单",
              total_market_value: "71000000000.00000000",
              bond_count: 120,
              percentage: "21.60000000",
            },
            {
              category: "信用债-企业",
              total_market_value: "49209000000.00000000",
              bond_count: 150,
              percentage: "14.97000000",
            },
            {
              category: "其他",
              total_market_value: "26000000000.00000000",
              bond_count: 60,
              percentage: "7.91000000",
            },
          ],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondDashboardYieldDistribution(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "bond_dashboard.yield_distribution",
        {
          report_date: reportDate,
          weighted_ytm: "0.02850000",
          items: [
            { yield_bucket: "<1.5%", total_market_value: "12000000000.00000000", bond_count: 12 },
            { yield_bucket: "1.5%-2.0%", total_market_value: "45000000000.00000000", bond_count: 88 },
            { yield_bucket: "2.0%-2.5%", total_market_value: "98000000000.00000000", bond_count: 142 },
            { yield_bucket: "2.5%-3.0%", total_market_value: "110000000000.00000000", bond_count: 118 },
            { yield_bucket: "3.0%-3.5%", total_market_value: "42000000000.00000000", bond_count: 48 },
            { yield_bucket: "3.5%-4.0%", total_market_value: "15000000000.00000000", bond_count: 15 },
            { yield_bucket: ">4.0%", total_market_value: "6709000000.00000000", bond_count: 5 },
          ],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondDashboardPortfolioComparison(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "bond_dashboard.portfolio_comparison",
        {
          report_date: reportDate,
          items: [
            {
              portfolio_name: "银行账户",
              total_market_value: "185000000000.00000000",
              weighted_ytm: "0.02780000",
              weighted_duration: "3.21000000",
              total_dv01: "-70200.00000000",
              bond_count: 220,
            },
            {
              portfolio_name: "交易账户",
              total_market_value: "98000000000.00000000",
              weighted_ytm: "0.02950000",
              weighted_duration: "3.88000000",
              total_dv01: "-40200.00000000",
              bond_count: 128,
            },
            {
              portfolio_name: "OCI 账户",
              total_market_value: "45709000000.00000000",
              weighted_ytm: "0.02890000",
              weighted_duration: "3.55000000",
              total_dv01: "-15030.50000000",
              bond_count: 80,
            },
          ],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondDashboardSpreadAnalysis(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "bond_dashboard.spread_analysis",
        {
          report_date: reportDate,
          items: [
            {
              bond_type: "国债",
              median_yield: "0.02450000",
              bond_count: 45,
              total_market_value: "52000000000.00000000",
            },
            {
              bond_type: "政金债",
              median_yield: "0.02720000",
              bond_count: 62,
              total_market_value: "78000000000.00000000",
            },
            {
              bond_type: "企业债",
              median_yield: "0.03410000",
              bond_count: 88,
              total_market_value: "91000000000.00000000",
            },
            {
              bond_type: "NCD",
              median_yield: "0.02680000",
              bond_count: 130,
              total_market_value: "87000000000.00000000",
            },
          ],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondDashboardMaturityStructure(reportDate: string) {
      await delay();
      const total = "328709000000.00000000";
      return buildMockApiEnvelope(
        "bond_dashboard.maturity_structure",
        {
          report_date: reportDate,
          total_market_value: total,
          items: [
            { maturity_bucket: "7天内", total_market_value: "2100000000.00000000", bond_count: 8, percentage: "0.63871429" },
            { maturity_bucket: "8-30天", total_market_value: "8900000000.00000000", bond_count: 22, percentage: "2.70700000" },
            { maturity_bucket: "31-90天", total_market_value: "18500000000.00000000", bond_count: 35, percentage: "5.62857143" },
            { maturity_bucket: "91天-1年", total_market_value: "62000000000.00000000", bond_count: 90, percentage: "18.86285714" },
            { maturity_bucket: "1-3年", total_market_value: "128000000000.00000000", bond_count: 145, percentage: "38.94285714" },
            { maturity_bucket: "3-5年", total_market_value: "72000000000.00000000", bond_count: 78, percentage: "21.90428571" },
            { maturity_bucket: "5年以上", total_market_value: "55209000000.00000000", bond_count: 50, percentage: "16.79571429" },
          ],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondDashboardIndustryDistribution(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "bond_dashboard.industry_distribution",
        {
          report_date: reportDate,
          items: [
            { industry_name: "银行", total_market_value: "82000000000.00000000", bond_count: 95, percentage: "24.94571429" },
            { industry_name: "城投", total_market_value: "61000000000.00000000", bond_count: 72, percentage: "18.55714286" },
            { industry_name: "交通运输", total_market_value: "48000000000.00000000", bond_count: 48, percentage: "14.60428571" },
            { industry_name: "电力", total_market_value: "39000000000.00000000", bond_count: 40, percentage: "11.86571429" },
            { industry_name: "房地产", total_market_value: "28000000000.00000000", bond_count: 35, percentage: "8.51714286" },
          ],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondDashboardRiskIndicators(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "bond_dashboard.risk_indicators",
        {
          report_date: reportDate,
          total_market_value: "328709000000.00000000",
          total_dv01: "-125430.50000000",
          weighted_duration: "3.45000000",
          credit_ratio: "0.42000000",
          weighted_convexity: "0.08500000",
          total_spread_dv01: "-45200.00000000",
          reinvestment_ratio_1y: "0.18000000",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsReturnDecomposition(
      reportDate: string,
      periodType: string,
      _options?: { assetClass?: string; accountingClass?: string },
    ) {
      await delay();
      void _options;
      return buildMockApiEnvelope(
        "bond_analytics.return_decomposition",
        {
          report_date: reportDate,
          period_type: periodType,
          period_start: reportDate,
          period_end: reportDate,
          carry: "0",
          roll_down: "0",
          rate_effect: "0",
          spread_effect: "0",
          trading: "0",
          fx_effect: "0",
          convexity_effect: "0",
          explained_pnl: "0",
          explained_pnl_accounting: "0",
          explained_pnl_economic: "0",
          oci_reserve_impact: "0",
          actual_pnl: "0",
          recon_error: "0",
          recon_error_pct: "0",
          by_asset_class: [],
          by_accounting_class: [],
          bond_details: [],
          bond_count: 0,
          total_market_value: "0",
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsBenchmarkExcess(
      reportDate: string,
      periodType: string,
      benchmarkId: string,
    ) {
      await delay();
      return buildMockApiEnvelope(
        "bond_analytics.benchmark_excess",
        {
          report_date: reportDate,
          period_type: periodType,
          period_start: reportDate,
          period_end: reportDate,
          portfolio_return: "0",
          benchmark_return: "0",
          excess_return: "0",
          tracking_error: null,
          information_ratio: null,
          duration_effect: "0",
          curve_effect: "0",
          spread_effect: "0",
          selection_effect: "0",
          allocation_effect: "0",
          explained_excess: "0",
          recon_error: "0",
          portfolio_duration: "0",
          benchmark_duration: "0",
          duration_diff: "0",
          excess_sources: [],
          benchmark_id: benchmarkId,
          benchmark_name: benchmarkId,
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsKrdCurveRisk(
      reportDate: string,
      _options?: { scenarioSet?: string },
    ) {
      await delay();
      void _options;
      return buildMockApiEnvelope(
        "bond_analytics.krd_curve_risk",
        {
          report_date: reportDate,
          portfolio_duration: "3.8",
          portfolio_modified_duration: "3.6",
          portfolio_dv01: "120",
          portfolio_convexity: "0.8",
          krd_buckets: [],
          scenarios: [],
          by_asset_class: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsActionAttribution(reportDate: string, periodType: string) {
      await delay();
      return buildMockApiEnvelope(
        "bond_analytics.action_attribution",
        {
          report_date: reportDate,
          period_type: periodType,
          period_start: reportDate,
          period_end: reportDate,
          total_actions: 0,
          total_pnl_from_actions: "0",
          by_action_type: [],
          action_details: [],
          period_start_duration: "0",
          period_end_duration: "0",
          duration_change_from_actions: "0",
          period_start_dv01: "0",
          period_end_dv01: "0",
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsAccountingClassAudit(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "bond_analytics.accounting_class_audit",
        {
          report_date: reportDate,
          total_positions: 0,
          total_market_value: "0",
          distinct_asset_classes: 0,
          divergent_asset_classes: 0,
          divergent_position_count: 0,
          divergent_market_value: "0",
          map_unclassified_asset_classes: 0,
          map_unclassified_position_count: 0,
          map_unclassified_market_value: "0",
          rows: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsCreditSpreadMigration(
      reportDate: string,
      _options?: { spreadScenarios?: string },
    ) {
      await delay();
      void _options;
      return buildMockApiEnvelope(
        "bond_analytics.credit_spread_migration",
        {
          report_date: reportDate,
          credit_bond_count: 12,
          credit_market_value: "1500000000",
          credit_weight: "0.25",
          spread_dv01: "25000",
          weighted_avg_spread: "80",
          weighted_avg_spread_duration: "4.2",
          spread_scenarios: [],
          migration_scenarios: [],
          oci_credit_exposure: "800000000",
          oci_spread_dv01: "12000",
          oci_sensitivity_25bp: "-300000",
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsPortfolioHeadlines(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "bond_analytics.portfolio_headlines",
        {
          report_date: reportDate,
          total_market_value: "0",
          weighted_ytm: "0",
          weighted_duration: "0",
          weighted_coupon: "0",
          total_dv01: "0",
          bond_count: 0,
          credit_weight: "0",
          issuer_hhi: "0",
          issuer_top5_weight: "0",
          by_asset_class: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsTopHoldings(reportDate: string, topN = 20) {
      await delay();
      return buildMockApiEnvelope(
        "bond_analytics.top_holdings",
        {
          report_date: reportDate,
          top_n: topN,
          items: [],
          total_market_value: "0",
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getCreditSpreadAnalysisDetail(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "credit_spread_analysis.detail",
        {
          report_date: reportDate,
          credit_bond_count: 12,
          total_credit_market_value: "1500000000",
          weighted_avg_spread_bps: "80.00000000",
          spread_term_structure: [],
          top_spread_bonds: [],
          bottom_spread_bonds: [],
          historical_context: null,
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsBondSubTypes(_reportDate?: string | null) {
      await delay();
      return buildMockApiEnvelope(
        "positions.bonds.sub_types",
        { sub_types: ["利率债", "信用债"] },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsBondsList(options: {
      reportDate?: string | null;
      subType?: string | null;
      page: number;
      pageSize: number;
      includeIssued?: boolean;
    }) {
      await delay();
      return buildMockApiEnvelope(
        "positions.bonds.list",
        {
          items: [],
          total: 0,
          page: options.page,
          page_size: options.pageSize,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCounterpartyBonds(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
      topN?: number;
      page?: number;
      pageSize?: number;
    }) {
      await delay();
      return buildMockApiEnvelope(
        "positions.counterparty.bonds",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
          total_weighted_rate: null,
          total_weighted_coupon_rate: null,
          total_customers: 0,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsInterbankProductTypes(_reportDate?: string | null) {
      await delay();
      return buildMockApiEnvelope(
        "positions.interbank.product_types",
        { product_types: ["拆借", "存放"] },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsInterbankList(options: {
      reportDate?: string | null;
      productType?: string | null;
      direction?: PositionDirection | "ALL" | null;
      page: number;
      pageSize: number;
    }) {
      await delay();
      return buildMockApiEnvelope(
        "positions.interbank.list",
        {
          items: [],
          total: 0,
          page: options.page,
          page_size: options.pageSize,
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCounterpartyInterbankSplit(options: {
      startDate: string;
      endDate: string;
      productType?: string | null;
      topN?: number;
    }) {
      await delay();
      return buildMockApiEnvelope(
        "positions.counterparty.interbank.split",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          asset_total_amount: "0",
          asset_total_avg_daily: "0",
          asset_total_weighted_rate: null,
          asset_customer_count: 0,
          liability_total_amount: "0",
          liability_total_avg_daily: "0",
          liability_total_weighted_rate: null,
          liability_customer_count: 0,
          asset_items: [],
          liability_items: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsStatsRating(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
    }) {
      await delay();
      return buildMockApiEnvelope(
        "positions.stats.rating",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsStatsIndustry(options: {
      startDate: string;
      endDate: string;
      subType?: string | null;
      topN?: number;
    }) {
      await delay();
      return buildMockApiEnvelope(
        "positions.stats.industry",
        {
          start_date: options.startDate,
          end_date: options.endDate,
          num_days: 0,
          items: [],
          total_amount: "0",
          total_avg_daily: "0",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCustomerDetails(options: {
      customerName: string;
      reportDate?: string | null;
    }) {
      await delay();
      return buildMockApiEnvelope(
        "positions.customer.details",
        {
          customer_name: options.customerName,
          report_date: options.reportDate ?? "",
          total_market_value: "0",
          bond_count: 0,
          items: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPositionsCustomerTrend(options: {
      customerName: string;
      endDate?: string | null;
      days?: number;
    }) {
      await delay();
      return buildMockApiEnvelope(
        "positions.customer.trend",
        {
          customer_name: options.customerName,
          start_date: options.endDate ?? "",
          end_date: options.endDate ?? "",
          days: options.days ?? 30,
          items: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getCashflowProjection(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "cashflow_projection.overview",
        {
          report_date: reportDate,
          duration_gap: "1.25000000",
          asset_duration: "3.80000000",
          liability_duration: "2.55000000",
          equity_duration: "5.20000000",
          rate_sensitivity_1bp: "125000.00000000",
          reinvestment_risk_12m: "0.18500000",
          monthly_buckets: [],
          top_maturing_assets_12m: [],
          warnings: [],
          computed_at: new Date().toISOString(),
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getLiabilityRiskBuckets(reportDate?: string | null) {
      await delay();
      return {
        report_date: reportDate?.trim() || "",
        liabilities_structure: [],
        liabilities_term_buckets: [],
        interbank_liabilities_structure: [],
        interbank_liabilities_term_buckets: [],
        issued_liabilities_structure: [],
        issued_liabilities_term_buckets: [],
      };
    },
    async getLiabilityYieldMetrics(reportDate?: string | null) {
      await delay();
      return {
        report_date: reportDate?.trim() || "",
        kpi: {
          asset_yield: null,
          liability_cost: null,
          market_liability_cost: null,
          nim: null,
        },
      };
    },
    async getLiabilityCounterparty(options: { reportDate?: string | null; topN?: number }) {
      await delay();
      return {
        report_date: options.reportDate?.trim() || "",
        total_value: 0,
        top_10: [],
        by_type: [],
      };
    },
    async getLiabilitiesMonthly(year: number) {
      await delay();
      return {
        year,
        months: [],
        ytd_avg_total_liabilities: 0,
        ytd_avg_liability_cost: null,
      };
    },
    async getLiabilityAdbMonthly(year: number) {
      await delay();
      return {
        year,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      };
    },
    async getAdb(_params: { startDate: string; endDate: string }) {
      await delay();
      return {
        summary: {
          total_avg_assets: 0,
          total_avg_liabilities: 0,
          end_spot_assets: 0,
          end_spot_liabilities: 0,
        },
        trend: [],
        breakdown: [],
      };
    },
    async getAdbComparison(_startDate: string, _endDate: string, _options?: { topN?: number }) {
      await delay();
      return {
        report_date: "",
        start_date: "",
        end_date: "",
        num_days: 0,
        simulated: false,
        total_spot_assets: 0,
        total_avg_assets: 0,
        total_spot_liabilities: 0,
        total_avg_liabilities: 0,
        asset_yield: null,
        liability_cost: null,
        net_interest_margin: null,
        assets_breakdown: [],
        liabilities_breakdown: [],
      };
    },
    async getAdbMonthly(year: number) {
      await delay();
      return {
        year,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      };
    },
    async getBondAnalyticsRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "bond_analytics_refresh",
        cache_key: "bond_analytics:materialize",
        report_date: "2025-12-31",
      };
    },

    // --- KPI mock ---
    async getKpiOwners(params) {
      await delay();
      return {
        owners: [
          {
            owner_id: 1,
            owner_name: "固定收益部",
            org_unit: "金融市场部",
            year: params?.year ?? new Date().getFullYear(),
            scope_type: "department" as const,
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          {
            owner_id: 2,
            owner_name: "同业业务部",
            org_unit: "金融市场部",
            year: params?.year ?? new Date().getFullYear(),
            scope_type: "department" as const,
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ],
        total: 2,
      };
    },
    async getKpiMetrics() {
      await delay();
      return { metrics: [], total: 0 };
    },
    async getKpiMetricById() {
      await delay();
      return {
        metric_id: 1,
        metric_code: "MOCK_001",
        owner_id: 1,
        year: new Date().getFullYear(),
        major_category: "收益类",
        metric_name: "债券投资收益率",
        target_value: "4.50",
        score_weight: "15.00",
        scoring_rule_type: "LINEAR_RATIO" as const,
        data_source_type: "AUTO" as const,
        is_active: true,
      };
    },
    async createKpiMetric(_data) {
      await delay();
      return {
        metric_id: Date.now(),
        metric_code: _data.metric_code,
        owner_id: _data.owner_id,
        year: _data.year,
        major_category: _data.major_category,
        metric_name: _data.metric_name,
        target_value: _data.target_value ?? null,
        score_weight: _data.score_weight,
        scoring_rule_type: _data.scoring_rule_type,
        data_source_type: _data.data_source_type,
        is_active: true,
      };
    },
    async updateKpiMetric(metricId, data) {
      await delay();
      return {
        metric_id: metricId,
        metric_code: data.metric_code,
        owner_id: data.owner_id,
        year: data.year,
        major_category: data.major_category,
        metric_name: data.metric_name,
        target_value: data.target_value ?? null,
        score_weight: data.score_weight,
        scoring_rule_type: data.scoring_rule_type,
        data_source_type: data.data_source_type,
        is_active: true,
      };
    },
    async deleteKpiMetric() {
      await delay();
    },
    async getKpiValues(params) {
      await delay();
      return {
        owner_id: params.owner_id,
        owner_name: "固定收益部",
        as_of_date: params.as_of_date,
        metrics: [],
        total: 0,
      };
    },
    async getKpiValuesSummary(params) {
      await delay();
      return {
        owner_id: params.owner_id,
        owner_name: "固定收益部",
        year: params.year,
        period_type: params.period_type,
        period_value: params.period_value,
        period_label: `${params.year}年${params.period_value ?? ""}${params.period_type === "MONTH" ? "月" : params.period_type === "QUARTER" ? "季度" : "年度"}`,
        period_start_date: `${params.year}-01-01`,
        period_end_date: `${params.year}-12-31`,
        metrics: [],
        total: 0,
        total_weight: "100.00",
        total_score: "0.00",
      };
    },
    async createKpiValue(data) {
      await delay();
      return {
        value_id: Date.now(),
        metric_id: data.metric_id,
        as_of_date: data.as_of_date,
        actual_value: data.actual_value ?? null,
        completion_ratio: null,
        progress_pct: data.progress_pct ?? null,
        score_value: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    },
    async updateKpiValue(valueId, metricId, asOfDate, data) {
      await delay();
      return {
        value_id: valueId || Date.now(),
        metric_id: metricId,
        as_of_date: asOfDate,
        actual_value: data.actual_value ?? null,
        completion_ratio: null,
        progress_pct: data.progress_pct ?? null,
        score_value: data.score_value ?? null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    },
    async batchUpdateKpiValues() {
      await delay();
      return { success_count: 0, failed_count: 0, errors: [] };
    },
    async fetchAndRecalcKpi(ownerId, asOfDate) {
      await delay();
      return {
        owner_id: ownerId,
        owner_name: "固定收益部",
        as_of_date: asOfDate,
        total_metrics: 0,
        fetched_count: 0,
        scored_count: 0,
        failed_count: 0,
        skipped_count: 0,
        results: [],
      };
    },
    async getKpiReport(params) {
      await delay();
      return {
        year: params.year,
        generated_at: new Date().toISOString(),
        rows: [],
        total: 0,
      };
    },
    async downloadKpiReportCSV() {
      await delay();
    },
    async getCubeDimensions(factTable: string) {
      await delay();
      const dimensionMap: Record<string, string[]> = {
        bond_analytics: [
          "asset_class_std",
          "accounting_class",
          "tenor_bucket",
          "rating",
          "bond_type",
          "issuer_name",
          "industry_name",
          "portfolio_name",
          "cost_center",
        ],
        pnl: ["invest_type_std", "accounting_basis", "portfolio_name", "cost_center"],
        balance: [
          "asset_class",
          "invest_type_std",
          "accounting_basis",
          "position_scope",
          "bond_type",
          "rating",
        ],
        product_category: ["category_id", "category_name", "side", "view"],
      };
      const fieldMap: Record<string, string[]> = {
        bond_analytics: ["market_value", "duration"],
        pnl: ["total_pnl"],
        balance: ["market_value", "amortized_cost", "accrued_interest"],
        product_category: ["business_net_income"],
      };
      return {
        fact_table: factTable,
        dimensions: dimensionMap[factTable] ?? [],
        measures: ["sum", "avg", "count", "min", "max"],
        measure_fields: fieldMap[factTable] ?? [],
      };
    },
    async executeCubeQuery(request: CubeQueryRequest) {
      await delay();
      return {
        report_date: request.report_date,
        fact_table: request.fact_table,
        measures: request.measures,
        dimensions: request.dimensions ?? [],
        rows: [],
        total_rows: 0,
        drill_paths: [],
        result_meta: {
          ...buildMockMeta("cube.query"),
          basis: "formal",
          formal_use_allowed: true,
        },
      };
    },
  };

  if (mode === "mock") {
    return mockClient;
  }

  return {
    mode,
    async getHealth() {
      const response = await fetchImpl(`${baseUrl}/health/ready`, {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(`Request failed: /health/ready (${response.status})`);
      }

      return (await response.json()) as HealthResponse;
    },
    getOverview: () =>
      requestJson<OverviewPayload>(fetchImpl, baseUrl, "/ui/home/overview"),
    getSummary: () =>
      requestJson<SummaryPayload>(fetchImpl, baseUrl, "/ui/home/summary"),
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
    getPnlAttribution: () =>
      requestJson<PnlAttributionPayload>(
        fetchImpl,
        baseUrl,
        "/ui/pnl/attribution",
      ),
    getVolumeRateAttribution: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.compareType) {
        params.set("compare_type", options.compareType);
      }
      const q = params.toString();
      return requestJson<VolumeRateAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/volume-rate${q ? `?${q}` : ""}`,
      );
    },
    getTplMarketCorrelation: (options) => {
      const params = new URLSearchParams();
      if (options?.months !== undefined) {
        params.set("months", String(options.months));
      }
      const q = params.toString();
      return requestJson<TPLMarketCorrelationPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/tpl-market${q ? `?${q}` : ""}`,
      );
    },
    getPnlCompositionBreakdown: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.includeTrend === false) {
        params.set("include_trend", "false");
      }
      if (options?.trendMonths !== undefined) {
        params.set("trend_months", String(options.trendMonths));
      }
      const q = params.toString();
      return requestJson<PnlCompositionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/composition${q ? `?${q}` : ""}`,
      );
    },
    getPnlAttributionAnalysisSummary: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<PnlAttributionAnalysisSummary>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/summary${q ? `?${q}` : ""}`,
      );
    },
    getPnlCarryRollDown: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<CarryRollDownPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/carry-rolldown${q ? `?${q}` : ""}`,
      );
    },
    getPnlSpreadAttribution: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.lookbackDays !== undefined) {
        params.set("lookback_days", String(options.lookbackDays));
      }
      const q = params.toString();
      return requestJson<SpreadAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/spread${q ? `?${q}` : ""}`,
      );
    },
    getPnlKrdAttribution: (options) => {
      const params = new URLSearchParams();
      if (options?.reportDate?.trim()) {
        params.set("report_date", options.reportDate.trim());
      }
      if (options?.lookbackDays !== undefined) {
        params.set("lookback_days", String(options.lookbackDays));
      }
      const q = params.toString();
      return requestJson<KRDAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/krd${q ? `?${q}` : ""}`,
      );
    },
    getPnlAdvancedAttributionSummary: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<AdvancedAttributionSummary>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/summary${q ? `?${q}` : ""}`,
      );
    },
    getPnlCampisiAttribution: (options) => {
      const q = buildCampisiQuery(options);
      return requestJson<CampisiAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/advanced/campisi${q}`,
      );
    },
    getPnlCampisiFourEffects: (options) =>
      requestJson<CampisiFourEffectsPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/campisi/four-effects${buildCampisiQuery(options)}`,
      ),
    getPnlCampisiEnhanced: (options) =>
      requestJson<CampisiEnhancedPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/campisi/enhanced${buildCampisiQuery(options)}`,
      ),
    getPnlCampisiMaturityBuckets: (options) =>
      requestJson<CampisiMaturityBucketsPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/campisi/maturity-buckets${buildCampisiQuery(options)}`,
      ),
    getRiskOverview: () =>
      requestJson<RiskOverviewPayload>(
        fetchImpl,
        baseUrl,
        "/ui/risk/overview",
      ),
    getRiskTensorDates: () =>
      requestJson<RiskTensorDatesPayload>(
        fetchImpl,
        baseUrl,
        "/api/risk/tensor/dates",
      ),
    getRiskTensor: (reportDate: string) =>
      requestJson<RiskTensorPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/tensor?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondAnalyticsDates: () =>
      requestJson<BondAnalyticsDatesPayload>(
        fetchImpl,
        baseUrl,
        "/api/bond-analytics/dates",
      ),
    getBondDashboardDates: () =>
      requestJson<BondAnalyticsDatesPayload>(fetchImpl, baseUrl, "/api/bond-dashboard/dates"),
    getBondDashboardHeadlineKpis: (reportDate: string) =>
      requestJson<BondDashboardHeadlinePayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/headline-kpis?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondDashboardAssetStructure: (reportDate: string, groupBy: string) =>
      requestJson<AssetStructurePayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/asset-structure?report_date=${encodeURIComponent(reportDate)}&group_by=${encodeURIComponent(groupBy)}`,
      ),
    getBondDashboardYieldDistribution: (reportDate: string) =>
      requestJson<YieldDistributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/yield-distribution?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondDashboardPortfolioComparison: (reportDate: string) =>
      requestJson<PortfolioComparisonPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/portfolio-comparison?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondDashboardSpreadAnalysis: (reportDate: string) =>
      requestJson<SpreadAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/spread-analysis?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondDashboardMaturityStructure: (reportDate: string) =>
      requestJson<MaturityStructurePayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/maturity-structure?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondDashboardIndustryDistribution: (reportDate: string) =>
      requestJson<IndustryDistPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/industry-distribution?report_date=${encodeURIComponent(reportDate)}&top_n=10`,
      ),
    getBondDashboardRiskIndicators: (reportDate: string) =>
      requestJson<RiskIndicatorsPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/risk-indicators?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondAnalyticsReturnDecomposition: (
      reportDate: string,
      periodType: string,
      options?: { assetClass?: string; accountingClass?: string },
    ) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        period_type: periodType,
      });
      if (options?.assetClass) params.set("asset_class", options.assetClass);
      if (options?.accountingClass) params.set("accounting_class", options.accountingClass);
      return requestJson<ReturnDecompositionPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/return-decomposition?${params.toString()}`,
      );
    },
    getBondAnalyticsBenchmarkExcess: (
      reportDate: string,
      periodType: string,
      benchmarkId: string,
    ) =>
      requestJson<BenchmarkExcessPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/benchmark-excess?report_date=${encodeURIComponent(reportDate)}&period_type=${encodeURIComponent(periodType)}&benchmark_id=${encodeURIComponent(benchmarkId)}`,
      ),
    getBondAnalyticsKrdCurveRisk: (reportDate: string, options?: { scenarioSet?: string }) => {
      const params = new URLSearchParams({ report_date: reportDate });
      if (options?.scenarioSet) params.set("scenario_set", options.scenarioSet);
      return requestJson<KRDCurveRiskPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/krd-curve-risk?${params.toString()}`,
      );
    },
    getBondAnalyticsActionAttribution: (reportDate: string, periodType: string) =>
      requestJson<ActionAttributionPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/action-attribution?report_date=${encodeURIComponent(reportDate)}&period_type=${encodeURIComponent(periodType)}`,
      ),
    getBondAnalyticsAccountingClassAudit: (reportDate: string) =>
      requestJson<AccountingClassAuditPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/accounting-class-audit?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondAnalyticsCreditSpreadMigration: (
      reportDate: string,
      options?: { spreadScenarios?: string },
    ) => {
      const params = new URLSearchParams({ report_date: reportDate });
      if (options?.spreadScenarios) params.set("spread_scenarios", options.spreadScenarios);
      return requestJson<CreditSpreadMigrationPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/credit-spread-migration?${params.toString()}`,
      );
    },
    getBondAnalyticsPortfolioHeadlines: (reportDate: string) =>
      requestJson<BondPortfolioHeadlinesPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/portfolio-headlines?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondAnalyticsTopHoldings: (reportDate: string, topN = 20) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        top_n: String(topN),
      });
      return requestJson<BondTopHoldingsPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/top-holdings?${params.toString()}`,
      );
    },
    getCreditSpreadAnalysisDetail: (reportDate: string) =>
      requestJson<CreditSpreadAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/api/credit-spread-analysis/detail?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getPositionsBondSubTypes: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<SubTypesResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/bonds/sub_types${q ? `?${q}` : ""}`,
      );
    },
    getPositionsBondsList: ({
      reportDate,
      subType,
      page,
      pageSize,
      includeIssued,
    }) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      if (includeIssued) {
        params.set("include_issued", "true");
      }
      return requestJson<PageResponse<BondPositionItem>>(
        fetchImpl,
        baseUrl,
        `/api/positions/bonds?${params.toString()}`,
      );
    },
    getPositionsCounterpartyBonds: ({
      startDate,
      endDate,
      subType,
      topN,
      page,
      pageSize,
    }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      params.set("page", String(page ?? 1));
      params.set("page_size", String(pageSize ?? 50));
      return requestJson<CounterpartyStatsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/counterparty/bonds?${params.toString()}`,
      );
    },
    getPositionsInterbankProductTypes: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<ProductTypesResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/interbank/product_types${q ? `?${q}` : ""}`,
      );
    },
    getPositionsInterbankList: ({
      reportDate,
      productType,
      direction,
      page,
      pageSize,
    }) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      if (productType?.trim()) {
        params.set("product_type", productType.trim());
      }
      if (direction && direction !== "ALL") {
        params.set("direction", direction);
      }
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      return requestJson<PageResponse<InterbankPositionItem>>(
        fetchImpl,
        baseUrl,
        `/api/positions/interbank?${params.toString()}`,
      );
    },
    getPositionsCounterpartyInterbankSplit: ({
      startDate,
      endDate,
      productType,
      topN,
    }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (productType?.trim()) {
        params.set("product_type", productType.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      return requestJson<InterbankCounterpartySplitResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/counterparty/interbank/split?${params.toString()}`,
      );
    },
    getPositionsStatsRating: ({ startDate, endDate, subType }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      return requestJson<RatingStatsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/stats/rating?${params.toString()}`,
      );
    },
    getPositionsStatsIndustry: ({ startDate, endDate, subType, topN }) => {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (subType?.trim()) {
        params.set("sub_type", subType.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      return requestJson<IndustryStatsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/stats/industry?${params.toString()}`,
      );
    },
    getPositionsCustomerDetails: ({ customerName, reportDate }) => {
      const params = new URLSearchParams({
        customer_name: customerName,
      });
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      return requestJson<CustomerBondDetailsResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/customer/details?${params.toString()}`,
      );
    },
    getPositionsCustomerTrend: ({ customerName, endDate, days }) => {
      const params = new URLSearchParams({
        customer_name: customerName,
      });
      if (endDate?.trim()) {
        params.set("end_date", endDate.trim());
      }
      if (days !== undefined) {
        params.set("days", String(days));
      }
      return requestJson<CustomerBalanceTrendResponse>(
        fetchImpl,
        baseUrl,
        `/api/positions/customer/trend?${params.toString()}`,
      );
    },
    getCashflowProjection: (reportDate: string) =>
      requestJson<CashflowProjectionPayload>(
        fetchImpl,
        baseUrl,
        `/api/cashflow-projection?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getLiabilityRiskBuckets: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestEnvelopeOrPlainJson<LiabilityRiskBucketsPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/buckets${q ? `?${q}` : ""}`,
      );
    },
    getLiabilityYieldMetrics: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestEnvelopeOrPlainJson<LiabilityYieldMetricsPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/yield_metrics${q ? `?${q}` : ""}`,
      );
    },
    getLiabilityCounterparty: ({ reportDate, topN }) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      const q = params.toString();
      return requestEnvelopeOrPlainJson<LiabilityCounterpartyPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/liabilities/counterparty${q ? `?${q}` : ""}`,
      );
    },
    getLiabilitiesMonthly: (year) =>
      requestEnvelopeOrPlainJson<LiabilitiesMonthlyPayload>(
        fetchImpl,
        baseUrl,
        `/api/liabilities/monthly?year=${encodeURIComponent(String(year))}`,
      ),
    getLiabilityAdbMonthly: (year) =>
      requestEnvelopeOrPlainJson<AdbMonthlyResponse>(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/monthly?year=${encodeURIComponent(String(year))}`,
      ),
    getAdb: ({ startDate, endDate }) => {
      const params = new URLSearchParams();
      params.set("start_date", startDate.trim());
      params.set("end_date", endDate.trim());
      return requestEnvelopeOrPlainJson<AdbPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb?${params.toString()}`,
      );
    },
    getAdbComparison: async (startDate, endDate, options) => {
      const params = new URLSearchParams();
      params.set("start_date", startDate.trim());
      params.set("end_date", endDate.trim());
      const topN = options?.topN;
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      const raw = await requestEnvelopeOrPlainJson<Record<string, unknown>>(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/comparison?${params.toString()}`,
      );
      return normalizeAdbComparisonResponse(raw);
    },
    getAdbMonthly: async (year) =>
      normalizeAdbMonthlyResponse(
        await requestEnvelopeOrPlainJson<Record<string, unknown>>(
          fetchImpl,
          baseUrl,
          `/api/analysis/adb/monthly?year=${encodeURIComponent(String(year))}`,
        ),
      ),
    getContribution: () =>
      requestJson<ContributionPayload>(
        fetchImpl,
        baseUrl,
        "/ui/home/contribution",
      ),
    getAlerts: () =>
      requestJson<AlertsPayload>(fetchImpl, baseUrl, "/ui/home/alerts"),
    getPlaceholderSnapshot: mockClient.getPlaceholderSnapshot,
    getSourceFoundation: () =>
      requestJson<SourcePreviewPayload>(
        fetchImpl,
        baseUrl,
        "/ui/preview/source-foundation",
      ),
    refreshSourcePreview: () =>
      requestActionJson<SourcePreviewRefreshPayload>(
        fetchImpl,
        baseUrl,
        "/ui/preview/source-foundation/refresh",
        {
          method: "POST",
        },
      ),
    getSourcePreviewRefreshStatus: (runId: string) =>
      requestActionJson<SourcePreviewRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    getSourceFoundationHistory: ({ sourceFamily, limit, offset }) => {
      const params = new URLSearchParams();
      if (sourceFamily?.trim()) {
        params.set("source_family", sourceFamily);
      }
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      return requestJson<SourcePreviewHistoryPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/history?${params.toString()}`,
      );
    },
    getSourceFoundationRows: ({ sourceFamily, ingestBatchId, limit, offset }) =>
      requestJson<SourcePreviewRowsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/${encodeURIComponent(sourceFamily)}/rows?ingest_batch_id=${encodeURIComponent(ingestBatchId)}&limit=${limit}&offset=${offset}`,
      ),
    getSourceFoundationTraces: ({ sourceFamily, ingestBatchId, limit, offset }) =>
      requestJson<SourcePreviewTracesPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/${encodeURIComponent(sourceFamily)}/traces?ingest_batch_id=${encodeURIComponent(ingestBatchId)}&limit=${limit}&offset=${offset}`,
      ),
    getMacroFoundation: () =>
      requestJson<MacroVendorPayload>(
        fetchImpl,
        baseUrl,
        "/ui/preview/macro-foundation",
      ),
    getChoiceMacroLatest: () =>
      requestJson<ChoiceMacroLatestPayload>(
        fetchImpl,
        baseUrl,
        "/ui/macro/choice-series/latest",
      ),
    getMacroBondLinkageAnalysis: ({ reportDate }) =>
      requestJson<MacroBondLinkagePayload>(
        fetchImpl,
        baseUrl,
        `/api/macro-bond-linkage/analysis?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getFxFormalStatus: () =>
      requestJson<FxFormalStatusPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/fx/formal-status",
      ),
    getFxAnalytical: () =>
      requestJson<FxAnalyticalPayload>(
        fetchImpl,
        baseUrl,
        "/ui/market-data/fx/analytical",
      ),
    refreshChoiceMacro: (backfillDays?: number) => {
      const params = backfillDays ? `?backfill_days=${backfillDays}` : "";
      return requestActionJson<ChoiceMacroRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/macro/choice-series/refresh${params}`,
        { method: "POST" },
      );
    },
    getChoiceMacroRefreshStatus: (runId: string) =>
      requestActionJson<ChoiceMacroRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/macro/choice-series/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    getChoiceNewsEvents: ({
      limit,
      offset,
      groupId,
      topicCode,
      errorOnly,
      receivedFrom,
      receivedTo,
    }) => {
      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      if (groupId?.trim()) {
        params.set("group_id", groupId.trim());
      }
      if (topicCode?.trim()) {
        params.set("topic_code", topicCode.trim());
      }
      if (errorOnly) {
        params.set("error_only", "true");
      }
      if (receivedFrom?.trim()) {
        params.set("received_from", receivedFrom.trim());
      }
      if (receivedTo?.trim()) {
        params.set("received_to", receivedTo.trim());
      }
      return requestJson<ChoiceNewsEventsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/news/choice-events/latest?${params.toString()}`,
      );
    },
    getProductCategoryDates: () =>
      requestJson<ProductCategoryDatesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/dates",
      ),
    refreshProductCategoryPnl: () =>
      requestActionJson<ProductCategoryRefreshPayload>(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/refresh",
        {
          method: "POST",
        },
      ),
    getProductCategoryRefreshStatus: (runId: string) =>
      requestActionJson<ProductCategoryRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    createProductCategoryManualAdjustment: (payload) =>
      requestActionWithBody<
        ProductCategoryManualAdjustmentPayload,
        ProductCategoryManualAdjustmentRequest
      >(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/manual-adjustments",
        payload,
      ),
    getProductCategoryManualAdjustments: (reportDate, options = {}) => {
      const params = buildManualAdjustmentSearchParams(reportDate, options);
      return requestActionJson<ProductCategoryManualAdjustmentListPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments?${params.toString()}`,
      );
    },
    exportProductCategoryManualAdjustmentsCsv: (reportDate, options = {}) => {
      const params = buildManualAdjustmentSearchParams(reportDate, options);
      return requestText(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/export?${params.toString()}`,
        "product-category-audit.csv",
      );
    },
    updateProductCategoryManualAdjustment: (adjustmentId, payload) =>
      requestActionWithBody<
        ProductCategoryManualAdjustmentPayload,
        ProductCategoryManualAdjustmentRequest
      >(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/edit`,
        payload,
      ),
    revokeProductCategoryManualAdjustment: (adjustmentId) =>
      requestActionJson<ProductCategoryManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/revoke`,
        {
          method: "POST",
        },
      ),
    restoreProductCategoryManualAdjustment: (adjustmentId) =>
      requestActionJson<ProductCategoryManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/restore`,
        {
          method: "POST",
        },
      ),
    getProductCategoryPnl: ({ reportDate, view, scenarioRatePct }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        view,
      });
      if (scenarioRatePct?.trim()) {
        params.set("scenario_rate_pct", scenarioRatePct);
      }
      return requestJson<ProductCategoryPnlPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category?${params.toString()}`,
      );
    },
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
      requestActionJson(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/refresh?report_month=${encodeURIComponent(reportMonth)}`,
        { method: "POST" },
      ),
    getQdbGlMonthlyAnalysisRefreshStatus: (runId) =>
      requestActionJson(
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
      return requestJson(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/scenario?${params.toString()}`,
      );
    },
    createQdbGlMonthlyAnalysisManualAdjustment: (payload) =>
      requestActionWithBody(
        fetchImpl,
        baseUrl,
        "/ui/qdb-gl-monthly-analysis/manual-adjustments",
        payload,
      ),
    updateQdbGlMonthlyAnalysisManualAdjustment: (adjustmentId, payload) =>
      requestActionWithBody(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments/${encodeURIComponent(adjustmentId)}/edit`,
        payload,
      ),
    revokeQdbGlMonthlyAnalysisManualAdjustment: (adjustmentId) =>
      requestActionJson(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments/${encodeURIComponent(adjustmentId)}/revoke`,
        { method: "POST" },
      ),
    restoreQdbGlMonthlyAnalysisManualAdjustment: (adjustmentId) =>
      requestActionJson(
        fetchImpl,
        baseUrl,
        `/ui/qdb-gl-monthly-analysis/manual-adjustments/${encodeURIComponent(adjustmentId)}/restore`,
        { method: "POST" },
      ),
    getQdbGlMonthlyAnalysisManualAdjustments: (reportMonth) =>
      requestActionJson(
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
    getBalanceAnalysisDates: () =>
      requestJson<BalanceAnalysisDatesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/dates",
      ),
    getBalanceAnalysisOverview: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisOverviewPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/overview?${params.toString()}`,
      );
    },
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
    getBalanceAnalysisSummaryByBasis: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
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
      ),
    refreshBondAnalytics: (reportDate: string) =>
      requestActionJson<BondAnalyticsRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/refresh?report_date=${encodeURIComponent(reportDate)}`,
        {
          method: "POST",
        },
      ),
    getBondAnalyticsRefreshStatus: (runId: string) =>
      requestActionJson<BondAnalyticsRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),

    // --- KPI real ---
    getKpiOwners: (params) =>
      requestKpiJson<KpiOwnerListResponse>(
        fetchImpl,
        baseUrl,
        `/owners${kpiQueryString(params ?? {})}`,
      ),
    getKpiMetrics: (params) =>
      requestKpiJson<KpiMetricListResponse>(
        fetchImpl,
        baseUrl,
        `/metrics${kpiQueryString(params ?? {})}`,
      ),
    getKpiMetricById: (metricId) =>
      requestKpiJson<KpiMetric>(fetchImpl, baseUrl, `/metrics/${metricId}`),
    createKpiMetric: (data) =>
      requestKpiJson<KpiMetric>(
        fetchImpl,
        baseUrl,
        "/metrics",
        { method: "POST", body: JSON.stringify(data) },
      ),
    updateKpiMetric: (metricId, data) =>
      requestKpiJson<KpiMetric>(
        fetchImpl,
        baseUrl,
        `/metrics/${metricId}`,
        { method: "PUT", body: JSON.stringify(data) },
      ),
    deleteKpiMetric: async (metricId) => {
      const response = await fetchImpl(`${baseUrl}/api/kpi/metrics/${metricId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `KPI API ${response.status}`);
      }
    },
    getKpiValues: (params) =>
      requestKpiJson<KpiValuesResponse>(
        fetchImpl,
        baseUrl,
        `/values${kpiQueryString(params)}`,
      ),
    getKpiValuesSummary: (params) =>
      requestKpiJson<KpiPeriodSummaryResponse>(
        fetchImpl,
        baseUrl,
        `/values/summary${kpiQueryString(params)}`,
      ),
    createKpiValue: (data) =>
      requestKpiJson<KpiMetricValue>(
        fetchImpl,
        baseUrl,
        "/values",
        { method: "POST", body: JSON.stringify(data) },
      ),
    updateKpiValue: async (valueId, metricId, asOfDate, data) => {
      if (valueId && valueId > 0) {
        return requestKpiJson<KpiMetricValue>(
          fetchImpl,
          baseUrl,
          `/values/${valueId}`,
          { method: "PUT", body: JSON.stringify(data) },
        );
      }
      return requestKpiJson<KpiMetricValue>(
        fetchImpl,
        baseUrl,
        "/values",
        {
          method: "POST",
          body: JSON.stringify({ metric_id: metricId, as_of_date: asOfDate, ...data }),
        },
      );
    },
    batchUpdateKpiValues: (asOfDate, items) =>
      requestKpiJson<KpiBatchUpdateResponse>(
        fetchImpl,
        baseUrl,
        "/values/batch",
        { method: "POST", body: JSON.stringify({ as_of_date: asOfDate, items }) },
      ),
    fetchAndRecalcKpi: (ownerId, asOfDate, request) =>
      requestKpiJson<KpiFetchAndRecalcResponse>(
        fetchImpl,
        baseUrl,
        `/fetch_and_recalc${kpiQueryString({ owner_id: ownerId, as_of_date: asOfDate })}`,
        { method: "POST", body: JSON.stringify(request ?? {}) },
      ),
    getKpiReport: (params) =>
      requestKpiJson<KpiReportResponse>(
        fetchImpl,
        baseUrl,
        `/report${kpiQueryString(params)}`,
      ),
    downloadKpiReportCSV: async (params) => {
      const response = await fetchImpl(
        `${baseUrl}/api/kpi/report${kpiQueryString({ ...params, format: "csv" })}`,
      );
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `KPI API ${response.status}`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `kpi_report_${params.year}_${params.as_of_date || "latest"}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    },
    getCubeDimensions: async (factTable: string) => {
      const response = await fetchImpl(
        `${baseUrl}/api/cube/dimensions/${encodeURIComponent(factTable)}`,
        {
          headers: { Accept: "application/json" },
        },
      );
      if (!response.ok) {
        throw new Error(`Request failed: /api/cube/dimensions/${factTable} (${response.status})`);
      }
      return response.json() as Promise<CubeDimensionsPayload>;
    },
    executeCubeQuery: async (request: CubeQueryRequest) => {
      const response = await fetchImpl(`${baseUrl}/api/cube/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `Cube query failed (${response.status})`);
      }
      return response.json() as Promise<CubeQueryResult>;
    },
  };
}

const ApiClientContext = createContext<ApiClient | null>(null);

export function ApiClientProvider({
  children,
  client,
}: ApiClientProviderProps) {
  const resolvedClient = useMemo(
    () => client ?? createApiClient(),
    [client],
  );

  return createElement(
    ApiClientContext.Provider,
    { value: resolvedClient },
    children,
  );
}

export function useApiClient(): ApiClient {
  const client = useContext(ApiClientContext);

  if (!client) {
    throw new Error("ApiClientProvider is missing");
  }

  return client;
}
