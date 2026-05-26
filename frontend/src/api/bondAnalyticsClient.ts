/**
 * Bond Analytics domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  BondAnalyticsDatesPayload,
  BondAnalyticsRefreshPayload,
  BondBusinessTypeMetricsPayload,
  BondPortfolioHeadlinesPayload,
  BondTopHoldingsPayload,
  BenchmarkExcessPayload,
  AssetStructurePayload,
  BondDashboardHeadlinePayload,
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
import { formatRawAsNumeric } from "../utils/format";
import { mockBondAnalyticsYieldCurveTermStructure } from "./bondAnalyticsYieldCurveTermStructureMock";
import type { CashflowClientMethods } from "./cashflowClient";

type BondAnalyticsCoreSurfaceMethods = {
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
  getBondBusinessTypeMetrics: (params: {
    reportDate: string;
  }) => Promise<BondBusinessTypeMetricsPayload>;
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
  getBondAnalyticsYieldCurveTermStructure: (
    reportDate: string,
    options?: { curveTypes?: string },
  ) => Promise<ApiEnvelope<YieldCurveTermStructurePayload>>;
};

export type BondAnalyticsClientMethods = BondAnalyticsCoreSurfaceMethods & CashflowClientMethods;

type FetchLike = typeof fetch;
type Delay = () => Promise<void>;

type BondAnalyticsCoreClientMethods = Pick<
  BondAnalyticsClientMethods,
  | "refreshBondAnalytics"
  | "getBondAnalyticsRefreshStatus"
  | "getBondAnalyticsDates"
  | "getBondAnalyticsReturnDecomposition"
  | "getBondAnalyticsBenchmarkExcess"
  | "getBondAnalyticsKrdCurveRisk"
  | "getBondAnalyticsActionAttribution"
  | "getBondAnalyticsAccountingClassAudit"
  | "getBondAnalyticsCreditSpreadMigration"
  | "getBondAnalyticsPortfolioHeadlines"
  | "getBondAnalyticsTopHoldings"
  | "getBondAnalyticsYieldCurveTermStructure"
  | "getCreditSpreadAnalysisDetail"
>;

type BondDashboardClientMethods = Pick<
  BondAnalyticsClientMethods,
  | "getBondDashboardDates"
  | "getBondDashboardHeadlineKpis"
  | "getBondDashboardAssetStructure"
  | "getBondDashboardYieldDistribution"
  | "getBondDashboardPortfolioComparison"
  | "getBondDashboardSpreadAnalysis"
  | "getBondDashboardMaturityStructure"
  | "getBondDashboardIndustryDistribution"
  | "getBondDashboardRiskIndicators"
>;

type BondDashboardMockBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

type EnsureBondDashboardMockBundle = () => Promise<BondDashboardMockBundle>;

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

export function createDemoBondAnalyticsClient(
  delay: Delay,
  ensureMockClientBundle: EnsureBondDashboardMockBundle,
): BondAnalyticsCoreClientMethods {
  return {
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
    async getBondAnalyticsDates() {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.dates",
        {
          report_dates: ["2026-03-31", "2026-02-28", "2025-12-31"],
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
      const zy = (sign_aware: boolean) => formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware });
      const zp = (sign_aware: boolean) => formatRawAsNumeric({ raw: 0, unit: "pct", sign_aware });
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.return_decomposition",
        {
          report_date: reportDate,
          period_type: periodType,
          period_start: reportDate,
          period_end: reportDate,
          carry: zy(true),
          roll_down: zy(true),
          rate_effect: zy(true),
          spread_effect: zy(true),
          trading: zy(true),
          fx_effect: zy(true),
          convexity_effect: zy(true),
          explained_pnl: zy(true),
          explained_pnl_accounting: zy(true),
          explained_pnl_economic: zy(true),
          oci_reserve_impact: zy(true),
          actual_pnl: zy(true),
          recon_error: zy(true),
          recon_error_pct: zp(true),
          by_asset_class: [],
          by_accounting_class: [],
          bond_details: [],
          bond_count: 0,
          total_market_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
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
      const zPct = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "pct", sign_aware: s });
      const zBp = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "bp", sign_aware: s });
      const zRatio = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "ratio", sign_aware: s });
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.benchmark_excess",
        {
          report_date: reportDate,
          period_type: periodType,
          period_start: reportDate,
          period_end: reportDate,
          portfolio_return: zPct(true),
          benchmark_return: zPct(true),
          excess_return: zBp(true),
          tracking_error: null,
          information_ratio: null,
          duration_effect: zBp(true),
          curve_effect: zBp(true),
          spread_effect: zBp(true),
          selection_effect: zBp(true),
          allocation_effect: zBp(true),
          explained_excess: zBp(true),
          recon_error: zBp(true),
          portfolio_duration: zRatio(false),
          benchmark_duration: zRatio(false),
          duration_diff: zRatio(true),
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
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.krd_curve_risk",
        {
          report_date: reportDate,
          portfolio_duration: formatRawAsNumeric({ raw: 3.8, unit: "ratio", sign_aware: false }),
          portfolio_modified_duration: formatRawAsNumeric({ raw: 3.6, unit: "ratio", sign_aware: false }),
          portfolio_dv01: formatRawAsNumeric({ raw: 120, unit: "dv01", sign_aware: false }),
          portfolio_convexity: formatRawAsNumeric({ raw: 0.8, unit: "ratio", sign_aware: false }),
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
      const zy = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: s });
      const zr = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "ratio", sign_aware: s });
      const zd = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: s });
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.action_attribution",
        {
          report_date: reportDate,
          period_type: periodType,
          period_start: reportDate,
          period_end: reportDate,
          total_actions: 0,
          total_pnl_from_actions: zy(true),
          by_action_type: [],
          action_details: [],
          period_start_duration: zr(false),
          period_end_duration: zr(false),
          duration_change_from_actions: zr(true),
          period_start_dv01: zd(false),
          period_end_dv01: zd(false),
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsAccountingClassAudit(reportDate: string) {
      await delay();
      const zm = () => formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false });
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.accounting_class_audit",
        {
          report_date: reportDate,
          total_positions: 0,
          total_market_value: zm(),
          distinct_asset_classes: 0,
          divergent_asset_classes: 0,
          divergent_position_count: 0,
          divergent_market_value: zm(),
          map_unclassified_asset_classes: 0,
          map_unclassified_position_count: 0,
          map_unclassified_market_value: zm(),
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
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.credit_spread_migration",
        {
          report_date: reportDate,
          credit_bond_count: 12,
          credit_market_value: formatRawAsNumeric({ raw: 1_500_000_000, unit: "yuan", sign_aware: false }),
          credit_weight: formatRawAsNumeric({ raw: 0.25, unit: "ratio", sign_aware: false }),
          spread_dv01: formatRawAsNumeric({ raw: 25_000, unit: "dv01", sign_aware: false }),
          weighted_avg_spread: formatRawAsNumeric({ raw: 80, unit: "bp", sign_aware: false }),
          weighted_avg_spread_duration: formatRawAsNumeric({ raw: 4.2, unit: "ratio", sign_aware: false }),
          spread_scenarios: [],
          migration_scenarios: [],
          oci_credit_exposure: formatRawAsNumeric({ raw: 800_000_000, unit: "yuan", sign_aware: false }),
          oci_spread_dv01: formatRawAsNumeric({ raw: 12_000, unit: "dv01", sign_aware: false }),
          oci_sensitivity_25bp: formatRawAsNumeric({ raw: -300_000, unit: "yuan", sign_aware: true }),
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsPortfolioHeadlines(reportDate: string) {
      await delay();
      const zy = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: s });
      const zPct = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "pct", sign_aware: s });
      const zRatio = (s: boolean) => formatRawAsNumeric({ raw: 0, unit: "ratio", sign_aware: s });
      const zDv = () => formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: false });
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.portfolio_headlines",
        {
          report_date: reportDate,
          total_market_value: zy(false),
          weighted_ytm: zPct(true),
          weighted_duration: zRatio(false),
          weighted_coupon: zPct(true),
          total_dv01: zDv(),
          bond_count: 0,
          credit_weight: zRatio(false),
          issuer_hhi: zRatio(false),
          issuer_top5_weight: zRatio(false),
          by_asset_class: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsTopHoldings(reportDate: string, topN = 20) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.top_holdings",
        {
          report_date: reportDate,
          top_n: topN,
          items: [],
          total_market_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsYieldCurveTermStructure(
      reportDate: string,
      _options?: { curveTypes?: string },
    ) {
      await delay();
      void _options;
      return mockBondAnalyticsYieldCurveTermStructure(reportDate);
    },
    async getCreditSpreadAnalysisDetail(reportDate: string) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
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
  };
}

export function createDemoBondDashboardClient(
  delay: Delay,
  ensureMockClientBundle: EnsureBondDashboardMockBundle,
): BondDashboardClientMethods {
  return {
    async getBondDashboardDates() {
      await delay();
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.dates",
          { report_dates: ["2026-03-31", "2026-02-28", "2025-12-31"] },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardHeadlineKpis(reportDate: string) {
      await delay();
      const zy = (raw: number, sign_aware = false) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware });
      const zp = (raw: number, sign_aware = true) => formatRawAsNumeric({ raw, unit: "pct", sign_aware });
      const zr = (raw: number, sign_aware = false) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware });
      const zd = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.headline_kpis",
          {
            report_date: reportDate,
            prev_report_date: "2026-02-28",
            kpis: {
              total_market_value: zy(328_709_000_000),
              unrealized_pnl: zy(1_850_000_000, true),
              weighted_ytm: zp(0.0285),
              weighted_duration: zr(3.45),
              weighted_coupon: zp(0.0312),
              credit_spread_median: zp(0.0085),
              total_dv01: zd(-125_430.5),
              bond_count: 428,
            },
            prev_kpis: {
              total_market_value: zy(320_000_000_000),
              unrealized_pnl: zy(1_600_000_000, true),
              weighted_ytm: zp(0.0281),
              weighted_duration: zr(3.52),
              weighted_coupon: zp(0.0308),
              credit_spread_median: zp(0.0089),
              total_dv01: zd(-128_900),
              bond_count: 415,
            },
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardAssetStructure(reportDate: string, groupBy: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.asset_structure",
          {
            report_date: reportDate,
            group_by: groupBy,
            total_market_value: zy(328_709_000_000),
            items: [
              {
                category: "政策性金融债",
                total_market_value: zy(98_500_000_000),
                bond_count: 42,
                percentage: zp(29.96428571),
              },
              {
                category: "地方政府债",
                total_market_value: zy(82_000_000_000),
                bond_count: 56,
                percentage: zp(24.94571429),
              },
              {
                category: "同业存单",
                total_market_value: zy(71_000_000_000),
                bond_count: 120,
                percentage: zp(21.6),
              },
              {
                category: "信用债-企业",
                total_market_value: zy(49_209_000_000),
                bond_count: 150,
                percentage: zp(14.97),
              },
              {
                category: "其他",
                total_market_value: zy(26_000_000_000),
                bond_count: 60,
                percentage: zp(7.91),
              },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardYieldDistribution(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: true });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.yield_distribution",
          {
            report_date: reportDate,
            weighted_ytm: zp(0.0285),
            items: [
              { yield_bucket: "<1.5%", total_market_value: zy(12_000_000_000), bond_count: 12 },
              { yield_bucket: "1.5%-2.0%", total_market_value: zy(45_000_000_000), bond_count: 88 },
              { yield_bucket: "2.0%-2.5%", total_market_value: zy(98_000_000_000), bond_count: 142 },
              { yield_bucket: "2.5%-3.0%", total_market_value: zy(110_000_000_000), bond_count: 118 },
              { yield_bucket: "3.0%-3.5%", total_market_value: zy(42_000_000_000), bond_count: 48 },
              { yield_bucket: "3.5%-4.0%", total_market_value: zy(15_000_000_000), bond_count: 15 },
              { yield_bucket: ">4.0%", total_market_value: zy(6_709_000_000), bond_count: 5 },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardPortfolioComparison(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: true });
      const zr = (raw: number) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
      const zd = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.portfolio_comparison",
          {
            report_date: reportDate,
            items: [
              {
                portfolio_name: "银行账户",
                total_market_value: zy(185_000_000_000),
                weighted_ytm: zp(0.0278),
                weighted_duration: zr(3.21),
                total_dv01: zd(-70_200),
                bond_count: 220,
              },
              {
                portfolio_name: "交易账户",
                total_market_value: zy(98_000_000_000),
                weighted_ytm: zp(0.0295),
                weighted_duration: zr(3.88),
                total_dv01: zd(-40_200),
                bond_count: 128,
              },
              {
                portfolio_name: "OCI 账户",
                total_market_value: zy(45_709_000_000),
                weighted_ytm: zp(0.0289),
                weighted_duration: zr(3.55),
                total_dv01: zd(-15_030.5),
                bond_count: 80,
              },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardSpreadAnalysis(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: true });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.spread_analysis",
          {
            report_date: reportDate,
            items: [
              {
                bond_type: "国债",
                median_yield: zp(0.0245),
                bond_count: 45,
                total_market_value: zy(52_000_000_000),
              },
              {
                bond_type: "政金债",
                median_yield: zp(0.0272),
                bond_count: 62,
                total_market_value: zy(78_000_000_000),
              },
              {
                bond_type: "企业债",
                median_yield: zp(0.0341),
                bond_count: 88,
                total_market_value: zy(91_000_000_000),
              },
              {
                bond_type: "NCD",
                median_yield: zp(0.0268),
                bond_count: 130,
                total_market_value: zy(87_000_000_000),
              },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardMaturityStructure(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.maturity_structure",
          {
            report_date: reportDate,
            total_market_value: zy(328_709_000_000),
            items: [
              { maturity_bucket: "7天内", total_market_value: zy(2_100_000_000), bond_count: 8, percentage: zp(0.63871429) },
              { maturity_bucket: "8-30天", total_market_value: zy(8_900_000_000), bond_count: 22, percentage: zp(2.707) },
              { maturity_bucket: "31-90天", total_market_value: zy(18_500_000_000), bond_count: 35, percentage: zp(5.62857143) },
              { maturity_bucket: "91天-1年", total_market_value: zy(62_000_000_000), bond_count: 90, percentage: zp(18.86285714) },
              { maturity_bucket: "1-3年", total_market_value: zy(128_000_000_000), bond_count: 145, percentage: zp(38.94285714) },
              { maturity_bucket: "3-5年", total_market_value: zy(72_000_000_000), bond_count: 78, percentage: zp(21.90428571) },
              { maturity_bucket: "5年以上", total_market_value: zy(55_209_000_000), bond_count: 50, percentage: zp(16.79571429) },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardIndustryDistribution(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.industry_distribution",
          {
            report_date: reportDate,
            items: [
              { industry_name: "银行", total_market_value: zy(82_000_000_000), bond_count: 95, percentage: zp(24.94571429) },
              { industry_name: "城投", total_market_value: zy(61_000_000_000), bond_count: 72, percentage: zp(18.55714286) },
              { industry_name: "交通运输", total_market_value: zy(48_000_000_000), bond_count: 48, percentage: zp(14.60428571) },
              { industry_name: "电力", total_market_value: zy(39_000_000_000), bond_count: 40, percentage: zp(11.86571429) },
              { industry_name: "房地产", total_market_value: zy(28_000_000_000), bond_count: 35, percentage: zp(8.51714286) },
            ],
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardRiskIndicators(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zd = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });
      const zr = (raw: number) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.risk_indicators",
          {
            report_date: reportDate,
            total_market_value: zy(328_709_000_000),
            total_dv01: zd(-125_430.5),
            weighted_duration: zr(3.45),
            credit_ratio: zr(0.42),
            weighted_convexity: zr(0.085),
            total_spread_dv01: zd(-45_200),
            reinvestment_ratio_1y: zr(0.18),
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
  };
}

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
  };
}
