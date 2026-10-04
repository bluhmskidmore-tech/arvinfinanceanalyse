/**
 * Bond Analytics domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  BondAnalyticsDatesPayload,
  BondAnalyticsRefreshPayload,
  BondDashboardBundlePayload,
  BondDashboardBundleSectionId,
  BondBusinessTypeMetricsPayload,
  BondPortfolioHeadlinesPayload,
  BondTopHoldingsPayload,
  DV01ActionPlanPayload,
  DV01LimitConfigStatusPayload,
  DV01MovementPayload,
  DV01ReconciliationPayload,
  DV01RiskPayload,
  BenchmarkExcessPayload,
  AssetStructurePayload,
  BondDashboardHeadlinePayload,
  BondDashboardHomeSummaryPayload,
  BondPositionChangesPayload,
  CreditSpreadAnalysisPayload,
  CreditSpreadMigrationPayload,
  YieldCurveTermStructurePayload,
  ActionAttributionPayload,
  AccountingClassAuditPayload,
  KRDCurveRiskPayload,
  IndustryDistPayload,
  MaturityStructurePayload,
  PortfolioComparisonPayload,
  ReturnDecompositionPayload,
  RiskIndicatorsPayload,
  SpreadAnalysisPayload,
  YieldDistributionPayload,
} from "./contracts";
import { normalizeCreditSpreadMigrationEnvelope, normalizePortfolioHeadlinesEnvelope } from "./bondAnalyticsNormalization";
import type { CashflowClientMethods } from "./cashflowClient";

type BondAnalyticsCoreSurfaceMethods = {
  refreshBondAnalytics: (reportDate: string) => Promise<BondAnalyticsRefreshPayload>;
  getBondAnalyticsRefreshStatus: (runId: string) => Promise<BondAnalyticsRefreshPayload>;
  getBondAnalyticsDates: () => Promise<ApiEnvelope<BondAnalyticsDatesPayload>>;
  getBondDashboardDates: () => Promise<ApiEnvelope<BondAnalyticsDatesPayload>>;
  getBondDashboardHeadlineKpis: (
    reportDate: string,
  ) => Promise<ApiEnvelope<BondDashboardHeadlinePayload>>;
  getBondDashboardHomeSummary: (
    reportDate: string,
  ) => Promise<ApiEnvelope<BondDashboardHomeSummaryPayload>>;
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
  getBondBusinessTypeMetrics: (params: {
    reportDate: string;
  }) => Promise<BondBusinessTypeMetricsPayload>;
  getBondDashboardRiskIndicators: (
    reportDate: string,
  ) => Promise<ApiEnvelope<RiskIndicatorsPayload>>;
  fetchBondDashboardBundle: (
    reportDate: string | null | undefined,
    sections: readonly BondDashboardBundleSectionId[],
    opts?: BondDashboardBundleOptions,
  ) => Promise<ApiEnvelope<BondDashboardBundlePayload>>;
  getBondAnalyticsReturnDecomposition: (
    reportDate: string,
    periodType: string,
    options?: BondAnalyticsReturnDecompositionOptions,
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
  getBondAnalyticsDv01Risk: (
    reportDate: string,
    options?: { accountingClass?: string; topN?: number; shockBps?: string },
  ) => Promise<ApiEnvelope<DV01RiskPayload>>;
  getBondAnalyticsDv01Reconciliation: (
    reportDate: string,
    options?: { accountingClass?: string },
  ) => Promise<ApiEnvelope<DV01ReconciliationPayload>>;
  getBondAnalyticsDv01Movement: (
    reportDate: string,
    options?: { accountingClass?: string; topN?: number },
  ) => Promise<ApiEnvelope<DV01MovementPayload>>;
  getBondAnalyticsDv01ActionPlan: (
    reportDate: string,
    options?: { accountingClass?: string; topN?: number },
  ) => Promise<ApiEnvelope<DV01ActionPlanPayload>>;
  getBondAnalyticsDv01LimitConfigStatus: (
    reportDate: string,
  ) => Promise<ApiEnvelope<DV01LimitConfigStatusPayload>>;
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
  getBondAnalyticsPositionChanges: (
    reportDate: string,
    topN?: number,
  ) => Promise<ApiEnvelope<BondPositionChangesPayload>>;
  getCreditSpreadAnalysisDetail: (
    reportDate: string,
  ) => Promise<ApiEnvelope<CreditSpreadAnalysisPayload>>;
  getBondAnalyticsYieldCurveTermStructure: (
    reportDate: string,
    options?: { curveTypes?: string },
  ) => Promise<ApiEnvelope<YieldCurveTermStructurePayload>>;
};

export type BondAnalyticsClientMethods = BondAnalyticsCoreSurfaceMethods & CashflowClientMethods;

type FetchLike = typeof fetch;

export type BondDashboardBundleOptions = {
  industryTopN?: number;
  analyticsTopN?: number;
  dv01TopN?: number;
  dv01ShockBps?: string;
  dv01AccountingClass?: string;
  curveTypes?: string;
};

export type BondAnalyticsReturnDecompositionOptions = {
  assetClass?: string;
  accountingClass?: string;
  detail?: "full" | "summary";
};

export type BondAnalyticsCoreClientMethods = Pick<
  BondAnalyticsClientMethods,
  | "refreshBondAnalytics"
  | "getBondAnalyticsRefreshStatus"
  | "getBondAnalyticsDates"
  | "getBondAnalyticsReturnDecomposition"
  | "getBondAnalyticsBenchmarkExcess"
  | "getBondAnalyticsKrdCurveRisk"
  | "getBondAnalyticsDv01Risk"
  | "getBondAnalyticsDv01Reconciliation"
  | "getBondAnalyticsDv01Movement"
  | "getBondAnalyticsDv01ActionPlan"
  | "getBondAnalyticsDv01LimitConfigStatus"
  | "getBondAnalyticsActionAttribution"
  | "getBondAnalyticsAccountingClassAudit"
  | "getBondAnalyticsCreditSpreadMigration"
  | "getBondAnalyticsPortfolioHeadlines"
  | "getBondAnalyticsTopHoldings"
  | "getBondAnalyticsPositionChanges"
  | "getBondAnalyticsYieldCurveTermStructure"
  | "getCreditSpreadAnalysisDetail"
>;

export type BondDashboardClientMethods = Pick<
  BondAnalyticsClientMethods,
  | "getBondDashboardDates"
  | "getBondDashboardHeadlineKpis"
  | "getBondDashboardHomeSummary"
  | "getBondDashboardAssetStructure"
  | "getBondDashboardYieldDistribution"
  | "getBondDashboardPortfolioComparison"
  | "getBondDashboardSpreadAnalysis"
  | "getBondDashboardMaturityStructure"
  | "getBondDashboardIndustryDistribution"
  | "getBondDashboardRiskIndicators"
  | "fetchBondDashboardBundle"
>;

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

export type BondDashboardClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
};

export type BondAnalyticsClientFactoryOptions = BondDashboardClientFactoryOptions & {
  requestActionJson: RequestActionJson;
};

export function createRealBondAnalyticsClient(
  options: BondAnalyticsClientFactoryOptions,
): BondAnalyticsCoreClientMethods {
  const { fetchImpl, baseUrl, requestJson, requestActionJson } = options;

  return {
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
    getBondAnalyticsDates: () =>
      requestJson<BondAnalyticsDatesPayload>(
        fetchImpl,
        baseUrl,
        "/api/bond-analytics/dates",
      ),
    getBondAnalyticsReturnDecomposition: (
      reportDate: string,
      periodType: string,
      options?: BondAnalyticsReturnDecompositionOptions,
    ) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        period_type: periodType,
      });
      if (options?.assetClass) params.set("asset_class", options.assetClass);
      if (options?.accountingClass) params.set("accounting_class", options.accountingClass);
      if (options?.detail) params.set("detail", options.detail);
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
    getBondAnalyticsDv01Risk: (
      reportDate: string,
      options?: { accountingClass?: string; topN?: number; shockBps?: string },
    ) => {
      const params = new URLSearchParams({ report_date: reportDate });
      params.set("accounting_class", options?.accountingClass ?? "OCI");
      params.set("top_n", String(options?.topN ?? 20));
      params.set("shock_bps", options?.shockBps ?? "1,10,25,50");
      return requestJson<DV01RiskPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/dv01-risk?${params.toString()}`,
      );
    },
    getBondAnalyticsDv01Reconciliation: (
      reportDate: string,
      options?: { accountingClass?: string },
    ) => {
      const params = new URLSearchParams({ report_date: reportDate });
      params.set("accounting_class", options?.accountingClass ?? "OCI");
      return requestJson<DV01ReconciliationPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/dv01-reconciliation?${params.toString()}`,
      );
    },
    getBondAnalyticsDv01Movement: (
      reportDate: string,
      options?: { accountingClass?: string; topN?: number },
    ) => {
      const params = new URLSearchParams({ report_date: reportDate });
      params.set("accounting_class", options?.accountingClass ?? "OCI");
      params.set("top_n", String(options?.topN ?? 20));
      return requestJson<DV01MovementPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/dv01-movement?${params.toString()}`,
      );
    },
    getBondAnalyticsDv01ActionPlan: (
      reportDate: string,
      options?: { accountingClass?: string; topN?: number },
    ) => {
      const params = new URLSearchParams({ report_date: reportDate });
      params.set("accounting_class", options?.accountingClass ?? "OCI");
      params.set("top_n", String(options?.topN ?? 20));
      return requestJson<DV01ActionPlanPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/dv01-action-plan?${params.toString()}`,
      );
    },
    getBondAnalyticsDv01LimitConfigStatus: (reportDate: string) =>
      requestJson<DV01LimitConfigStatusPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/dv01-limit-config-status?report_date=${encodeURIComponent(reportDate)}`,
      ),
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
      ).then(normalizeCreditSpreadMigrationEnvelope);
    },
    getBondAnalyticsPortfolioHeadlines: (reportDate: string) =>
      requestJson<BondPortfolioHeadlinesPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/portfolio-headlines?report_date=${encodeURIComponent(reportDate)}`,
      ).then(normalizePortfolioHeadlinesEnvelope),
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
    getBondAnalyticsPositionChanges: (reportDate: string, topN = 5) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        top_n: String(topN),
      });
      return requestJson<BondPositionChangesPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/position-changes?${params.toString()}`,
      );
    },
    getBondAnalyticsYieldCurveTermStructure: (
      reportDate: string,
      options?: { curveTypes?: string },
    ) => {
      const params = new URLSearchParams({ report_date: reportDate });
      if (options?.curveTypes?.trim()) {
        params.set("curve_types", options.curveTypes.trim());
      }
      return requestJson<YieldCurveTermStructurePayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/yield-curve-term-structure?${params.toString()}`,
      );
    },
    getCreditSpreadAnalysisDetail: (reportDate: string) =>
      requestJson<CreditSpreadAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/api/credit-spread-analysis/detail?report_date=${encodeURIComponent(reportDate)}`,
      ),
  };
}

export function createRealBondDashboardClient(
  options: BondDashboardClientFactoryOptions,
): BondDashboardClientMethods {
  const { fetchImpl, baseUrl, requestJson } = options;

  return {
    getBondDashboardDates: () =>
      requestJson<BondAnalyticsDatesPayload>(fetchImpl, baseUrl, "/api/bond-dashboard/dates"),
    getBondDashboardHeadlineKpis: (reportDate: string) =>
      requestJson<BondDashboardHeadlinePayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/headline-kpis?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondDashboardHomeSummary: (reportDate: string) =>
      requestJson<BondDashboardHomeSummaryPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/home-summary?report_date=${encodeURIComponent(reportDate)}`,
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
    fetchBondDashboardBundle: (reportDate, sections, opts) => {
      const params = new URLSearchParams({
        sections: sections.join(","),
      });
      const normalizedReportDate = reportDate?.trim();
      if (normalizedReportDate) {
        params.set("report_date", normalizedReportDate);
      }
      if (opts?.industryTopN !== undefined) {
        params.set("industry_top_n", String(opts.industryTopN));
      }
      if (opts?.analyticsTopN !== undefined) {
        params.set("analytics_top_n", String(opts.analyticsTopN));
      }
      if (opts?.dv01TopN !== undefined) {
        params.set("dv01_top_n", String(opts.dv01TopN));
      }
      if (opts?.dv01ShockBps !== undefined) {
        params.set("dv01_shock_bps", opts.dv01ShockBps);
      }
      if (opts?.dv01AccountingClass !== undefined) {
        params.set("dv01_accounting_class", opts.dv01AccountingClass);
      }
      if (opts?.curveTypes !== undefined) {
        params.set("curve_types", opts.curveTypes);
      }
      return requestJson<BondDashboardBundlePayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/bundle?${params.toString()}`,
      );
    },
  };
}
