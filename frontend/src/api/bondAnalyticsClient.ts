/**
 * Bond Analytics domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  BondAnalyticsDatesPayload,
  BondAnalyticsRefreshPayload,
  BondPortfolioHeadlinesPayload,
  BondTopHoldingsPayload,
  BenchmarkExcessPayload,
  AssetStructurePayload,
  BondDashboardHeadlinePayload,
  CreditSpreadAnalysisPayload,
  CreditSpreadMigrationPayload,
  ActionAttributionPayload,
  AccountingClassAuditPayload,
  CashflowProjectionPayload,
  KRDCurveRiskPayload,
  IndustryDistPayload,
  MaturityStructurePayload,
  PortfolioComparisonPayload,
  ReturnDecompositionPayload,
  RiskIndicatorsPayload,
  SpreadAnalysisPayload,
  YieldDistributionPayload,
} from "./contracts";

export type BondAnalyticsClientMethods = {
  refreshBondAnalytics: (reportDate: string) => Promise<BondAnalyticsRefreshPayload>;
  getBondAnalyticsRefreshStatus: (runId: string) => Promise<BondAnalyticsRefreshPayload>;
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
  getCashflowProjection: (reportDate: string) => Promise<ApiEnvelope<CashflowProjectionPayload>>;
};
