/**
 * Bond analytics / bond dashboard demo-mock client slices.
 * Loaded only from mock composition paths (mockApiClient.ts /
 * homeSupplementalClient loadMockClient); keeps demo fixtures and mock
 * payloads out of the real-mode bundle that imports bondAnalyticsClient.ts.
 */
import type {
  ApiEnvelope,
  BondBusinessTypeMetricsPayload,
  BondDashboardBundlePayload,
  BondDashboardBundleSectionEnvelopeMap,
  BondDashboardBundleSectionId,
  DV01ActionPlanPayload,
  DV01LimitConfigStatusPayload,
  DV01MovementPayload,
  DV01ReconciliationPayload,
  DV01RiskPayload,
  ResultMeta,
} from "./contracts";
import { formatRawAsNumeric } from "../utils/format";
import {
  buildMockBondTradingDeskTopHoldings,
  sumMockTopHoldingsMarketValue,
} from "../mocks/bondTradingDeskDrillFixtures";
import { mockBondAnalyticsYieldCurveTermStructure } from "./bondAnalyticsYieldCurveTermStructureMock";
import { buildMockBondDashboardBundleEnvelope } from "./bondDashboardBundleMock";
import type {
  BondAnalyticsClientMethods,
  BondAnalyticsCoreClientMethods,
  BondAnalyticsReturnDecompositionOptions,
  BondDashboardBundleOptions,
  BondDashboardClientMethods,
} from "./bondAnalyticsClient";

type Delay = () => Promise<void>;

type DashboardWorkbenchSamples = typeof import("../fixtures/dashboardCoreWorkbenchSamples");

const MOCK_BOND_DASHBOARD_REPORT_DATES = ["2026-03-31", "2026-02-28", "2025-12-31"];
const MOCK_BOND_DASHBOARD_EVIDENCE_ROWS = 428;
const BOND_DASHBOARD_FACT_TABLE = "fact_formal_bond_analytics_daily";
const YIELD_CURVE_FACT_TABLE = "fact_formal_yield_curve_daily";
const BOND_DASHBOARD_NULL_CURRENCY_META = {
  amount_currency_basis: null,
  amount_currency_basis_note: null,
} as const;
// The live dates envelope emits an explicit not-applicable null. The shared
// frontend ResultMeta contract still models evidence_rows as number-only.
const BOND_DASHBOARD_DATES_NULL_EVIDENCE_META: object = { evidence_rows: null };

function buildMockBondDashboardAnalyticalMeta(
  reportDate: string,
  evidenceRows = MOCK_BOND_DASHBOARD_EVIDENCE_ROWS,
): Partial<ResultMeta> {
  return {
    ...BOND_DASHBOARD_NULL_CURRENCY_META,
    basis: "analytical",
    formal_use_allowed: false,
    cache_key: null,
    quality_flag: evidenceRows > 0 ? "ok" : "warning",
    requested_report_date: reportDate,
    resolved_report_date: reportDate,
    as_of_date: reportDate,
    date_basis: "bond_dashboard_report_date",
    fallback_date: null,
    filters_applied: { report_date: reportDate },
    tables_used: [BOND_DASHBOARD_FACT_TABLE],
    evidence_rows: evidenceRows,
    next_drill: [],
  };
}

function buildMockBondDashboardDatesMeta(): Partial<ResultMeta> {
  return {
    ...BOND_DASHBOARD_NULL_CURRENCY_META,
    basis: "formal",
    formal_use_allowed: true,
    cache_key: null,
    quality_flag: "ok",
    requested_report_date: null,
    resolved_report_date: null,
    as_of_date: null,
    date_basis: null,
    fallback_date: null,
    filters_applied: {},
    tables_used: [],
    ...BOND_DASHBOARD_DATES_NULL_EVIDENCE_META,
    next_drill: [],
  };
}

function mockPreviousBondDashboardReportDate(reportDate: string): string | null {
  const index = MOCK_BOND_DASHBOARD_REPORT_DATES.indexOf(reportDate);
  return index >= 0 ? (MOCK_BOND_DASHBOARD_REPORT_DATES[index + 1] ?? null) : null;
}

// Demo-only fixtures load lazily so sample data stays out of the production bundle.
let dashboardWorkbenchSamplesPromise: Promise<DashboardWorkbenchSamples> | null = null;

function ensureDashboardWorkbenchSamples(): Promise<DashboardWorkbenchSamples> {
  dashboardWorkbenchSamplesPromise ??= import("../fixtures/dashboardCoreWorkbenchSamples");
  return dashboardWorkbenchSamplesPromise;
}

type BondDashboardMockBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

type EnsureBondDashboardMockBundle = () => Promise<BondDashboardMockBundle>;

type DemoBondDashboardBundleClient = BondDashboardClientMethods & {
  getBondBusinessTypeMetrics?: (params: { reportDate: string }) => Promise<BondBusinessTypeMetricsPayload>;
} & Pick<
  BondAnalyticsClientMethods,
  | "getBondAnalyticsPortfolioHeadlines"
  | "getBondAnalyticsTopHoldings"
  | "getBondAnalyticsDv01Risk"
  | "getBondAnalyticsYieldCurveTermStructure"
>;

function requireBondDashboardBundleReportDate(
  section: BondDashboardBundleSectionId,
  reportDate: string | null | undefined,
): string {
  const normalized = reportDate?.trim() ?? "";
  if (section !== "dates" && !normalized) {
    throw new Error("report_date is required for the requested bundle sections");
  }
  return normalized;
}

async function fetchDemoBondDashboardBundleSection(
  client: DemoBondDashboardBundleClient,
  section: BondDashboardBundleSectionId,
  reportDate: string | null | undefined,
  ensureMockClientBundle: EnsureBondDashboardMockBundle,
  opts?: BondDashboardBundleOptions,
): Promise<[
  BondDashboardBundleSectionId,
  BondDashboardBundleSectionEnvelopeMap[BondDashboardBundleSectionId],
]> {
  if (section === "dates") {
    return [section, await client.getBondDashboardDates()];
  }

  const rd = requireBondDashboardBundleReportDate(section, reportDate);
  if (section === "headline-kpis") {
    return [section, await client.getBondDashboardHeadlineKpis(rd)];
  }
  if (section === "home-summary") {
    return [section, await client.getBondDashboardHomeSummary(rd)];
  }
  if (section === "asset-structure") {
    return [section, await client.getBondDashboardAssetStructure(rd, "bond_type")];
  }
  if (section === "asset-structure-rating") {
    return [section, await client.getBondDashboardAssetStructure(rd, "rating")];
  }
  if (section === "asset-structure-portfolio-name") {
    return [section, await client.getBondDashboardAssetStructure(rd, "portfolio_name")];
  }
  if (section === "asset-structure-tenor-bucket") {
    return [section, await client.getBondDashboardAssetStructure(rd, "tenor_bucket")];
  }
  if (section === "yield-distribution") {
    return [section, await client.getBondDashboardYieldDistribution(rd)];
  }
  if (section === "portfolio-comparison") {
    return [section, await client.getBondDashboardPortfolioComparison(rd)];
  }
  if (section === "spread-analysis") {
    return [section, await client.getBondDashboardSpreadAnalysis(rd)];
  }
  if (section === "maturity-structure") {
    return [section, await client.getBondDashboardMaturityStructure(rd)];
  }
  if (section === "industry-distribution") {
    const envelope = await client.getBondDashboardIndustryDistribution(rd);
    const topN = opts?.industryTopN ?? 10;
    if (topN >= envelope.result.items.length) {
      return [section, envelope];
    }
    const items = envelope.result.items.slice(0, topN);
    const totalMarketValue = items.reduce(
      (sum, item) => sum + (item.total_market_value.raw ?? 0),
      0,
    );
    return [
      section,
      {
        ...envelope,
        result: {
          ...envelope.result,
          items: items.map((item) => ({
            ...item,
            percentage: formatRawAsNumeric({
              raw: totalMarketValue > 0
                ? (item.total_market_value.raw ?? 0) / totalMarketValue
                : 0,
              unit: "pct",
              sign_aware: false,
            }),
          })),
        },
      },
    ];
  }
  if (section === "risk-indicators") {
    return [section, await client.getBondDashboardRiskIndicators(rd)];
  }
  if (section === "top-holdings") {
    return [section, await client.getBondAnalyticsTopHoldings(rd, opts?.analyticsTopN ?? 10)];
  }
  if (section === "portfolio-headlines") {
    return [section, await client.getBondAnalyticsPortfolioHeadlines(rd)];
  }
  if (section === "dv01-risk") {
    return [
      section,
      await client.getBondAnalyticsDv01Risk(rd, {
        accountingClass: opts?.dv01AccountingClass ?? "all",
        topN: opts?.dv01TopN ?? 1,
        shockBps: opts?.dv01ShockBps ?? "1",
      }),
    ];
  }
  if (
    section === "dv01-risk-ac" ||
    section === "dv01-risk-oci" ||
    section === "dv01-risk-tpl" ||
    section === "dv01-risk-all"
  ) {
    const accountingClass = section.replace("dv01-risk-", "").toUpperCase();
    return [
      section,
      await client.getBondAnalyticsDv01Risk(rd, {
        accountingClass: accountingClass === "ALL" ? "all" : accountingClass,
        topN: opts?.dv01TopN ?? 1,
        shockBps: opts?.dv01ShockBps ?? "1",
      }),
    ];
  }
  if (section === "yield-curve-term-structure") {
    return [
      section,
      await client.getBondAnalyticsYieldCurveTermStructure(rd, {
        curveTypes: opts?.curveTypes ?? "treasury,cdb",
      }),
    ];
  }

  if (client.getBondBusinessTypeMetrics) {
    return [section, await client.getBondBusinessTypeMetrics({ reportDate: rd })];
  }

  const { sampleBondBusinessTypeMetricRows } = await ensureDashboardWorkbenchSamples();
  return [
    section,
    {
      ...(await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_dashboard.business_type_metrics",
        {
          report_date: rd,
          items: sampleBondBusinessTypeMetricRows,
        },
        buildMockBondDashboardAnalyticalMeta(rd),
      ),
      data_source: "bond_analytics_facts",
    },
  ];
}

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
      _options?: BondAnalyticsReturnDecompositionOptions,
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
    async getBondAnalyticsDv01Risk(
      reportDate: string,
      options?: { accountingClass?: string; topN?: number; shockBps?: string },
    ) {
      await delay();
      const accountingClass = options?.accountingClass ?? "OCI";
      const zeroYuan = formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false });
      const zeroRatio = formatRawAsNumeric({ raw: 0, unit: "ratio", sign_aware: false });
      const zeroDv01 = formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: false });
      return (await ensureMockClientBundle()).buildMockApiEnvelope<DV01RiskPayload>(
        "bond_analytics.dv01_risk",
        {
          report_date: reportDate,
          accounting_class: accountingClass,
          dv01_basis: "face_value_modified_duration",
          scenario_pnl_basis: "face_value_dv01_linear",
          total_face_value: zeroYuan,
          total_market_value: zeroYuan,
          face_weighted_modified_duration: zeroRatio,
          total_dv01: zeroDv01,
          position_count: 0,
          shock_scenarios: [],
          tenor_buckets: [],
          top_bonds: [],
          top_issuers: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsDv01Reconciliation(
      reportDate: string,
      options?: { accountingClass?: string },
    ) {
      await delay();
      const accountingClass = options?.accountingClass ?? "OCI";
      const zeroYuan = formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false });
      const zeroRatio = formatRawAsNumeric({ raw: 0, unit: "ratio", sign_aware: false });
      const zeroDv01 = formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: false });
      return (await ensureMockClientBundle()).buildMockApiEnvelope<DV01ReconciliationPayload>(
        "bond_analytics.dv01_reconciliation",
        {
          report_date: reportDate,
          accounting_class: accountingClass,
          total_face_value: zeroYuan,
          total_market_value: zeroYuan,
          face_weighted_modified_duration: zeroRatio,
          total_dv01: zeroDv01,
          position_count: 0,
          rows: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsDv01Movement(
      reportDate: string,
      options?: { accountingClass?: string; topN?: number },
    ) {
      await delay();
      void options?.topN;
      const accountingClass = options?.accountingClass ?? "OCI";
      const zeroYuan = formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false });
      const zeroRatio = formatRawAsNumeric({ raw: 0, unit: "ratio", sign_aware: false });
      const zeroDv01 = formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: false });
      const signedZeroDv01 = formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: true });
      return (await ensureMockClientBundle()).buildMockApiEnvelope<DV01MovementPayload>(
        "bond_analytics.dv01_movement",
        {
          report_date: reportDate,
          previous_report_date: null,
          accounting_class: accountingClass,
          source_status: "empty",
          current_total_face_value: zeroYuan,
          previous_total_face_value: zeroYuan,
          current_total_market_value: zeroYuan,
          previous_total_market_value: zeroYuan,
          current_face_weighted_modified_duration: zeroRatio,
          previous_face_weighted_modified_duration: zeroRatio,
          current_total_dv01: zeroDv01,
          previous_total_dv01: zeroDv01,
          delta_dv01: signedZeroDv01,
          current_position_count: 0,
          previous_position_count: 0,
          attribution: [],
          anomaly_bonds: [],
          methodology_checks: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsDv01ActionPlan(
      reportDate: string,
      options?: { accountingClass?: string; topN?: number },
    ) {
      await delay();
      void options?.topN;
      const accountingClass = options?.accountingClass ?? "OCI";
      const zeroRatio = formatRawAsNumeric({ raw: 0, unit: "ratio", sign_aware: true });
      const zeroDv01 = formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: false });
      const signedZeroDv01 = formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: true });
      return (await ensureMockClientBundle()).buildMockApiEnvelope<DV01ActionPlanPayload>(
        "bond_analytics.dv01_action_plan",
        {
          report_date: reportDate,
          accounting_class: accountingClass,
          risk_level: "no_data",
          policy_basis: "page_threshold_fallback",
          threshold_note: "页面预警阈值，不代表正式限额；未接入正式限额源时仅作参考。",
          limit_source: "page_threshold",
          limit_source_version: "unconfigured",
          limit_rule_version: "rv_dv01_page_threshold_v3",
          limit_effective_date: null,
          total_dv01: zeroDv01,
          limit_dv01: zeroDv01,
          warning_dv01: zeroDv01,
          limit_usage: zeroRatio,
          remaining_limit_dv01: signedZeroDv01,
          dv01_to_reduce: signedZeroDv01,
          hedge_instrument_label: "DV01 hedge unit",
          hedge_instrument_dv01: zeroDv01,
          suggested_hedge_units: zeroRatio,
          position_count: 0,
          breach_count: 0,
          scenario_breaches: [],
          tenor_actions: [],
          issuer_actions: [],
          bond_actions: [],
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "bond_analytics_report_date",
          filters_applied: {
            report_date: reportDate,
            accounting_class: accountingClass,
            policy_basis: "page_threshold_fallback",
          },
          tables_used: ["fact_formal_bond_analytics_daily"],
          evidence_rows: 0,
        },
      );
    },
    async getBondAnalyticsDv01LimitConfigStatus(reportDate: string) {
      await delay();
      const zeroDv01 = formatRawAsNumeric({ raw: 0, unit: "dv01", sign_aware: false });
      return (await ensureMockClientBundle()).buildMockApiEnvelope<DV01LimitConfigStatusPayload>(
        "bond_analytics.dv01_limit_config_status",
        {
          report_date: reportDate,
          overall_status: "incomplete",
          acceptance_status: "blocked",
          acceptance_message:
            "正式 DV01 限额配置验收未通过；待补分类：AC, OCI, TPL, all。",
          next_action:
            "请在 bond_dv01_limit_config 治理流补齐 AC, OCI, TPL, all 的 accounting_class、limit_dv01、warning_dv01、hedge_target_dv01、limit_source、limit_source_version、limit_rule_version、limit_effective_date。",
          config_stream: "bond_dv01_limit_config",
          required_accounting_classes: ["AC", "OCI", "TPL", "all"],
          required_fields: [
            "accounting_class",
            "limit_dv01",
            "warning_dv01",
            "hedge_target_dv01",
            "limit_source",
            "limit_source_version",
            "limit_rule_version",
            "limit_effective_date",
          ],
          configured_accounting_classes: [],
          missing_accounting_classes: ["AC", "OCI", "TPL", "all"],
          invalid_accounting_classes: [],
          missing_business_fields_by_class: {
            AC: [
              "limit_dv01",
              "warning_dv01",
              "hedge_target_dv01",
              "limit_source",
              "limit_source_version",
              "limit_rule_version",
              "limit_effective_date",
            ],
            OCI: [
              "limit_dv01",
              "warning_dv01",
              "hedge_target_dv01",
              "limit_source",
              "limit_source_version",
              "limit_rule_version",
              "limit_effective_date",
            ],
            TPL: [
              "limit_dv01",
              "warning_dv01",
              "hedge_target_dv01",
              "limit_source",
              "limit_source_version",
              "limit_rule_version",
              "limit_effective_date",
            ],
            all: [
              "limit_dv01",
              "warning_dv01",
              "hedge_target_dv01",
              "limit_source",
              "limit_source_version",
              "limit_rule_version",
              "limit_effective_date",
            ],
          },
          review_package_command:
            "python -m backend.app.tasks.bond_dv01_limit_config_import --review-package-dir .tmp\\bond_dv01_limit_config_review_package --report-date 2026-03-31",
          dry_run_command:
            "python -m backend.app.tasks.bond_dv01_limit_config_import --config-path .tmp\\bond_dv01_limit_config_review_package\\bond_dv01_limit_config_review_2026-03-31.csv --report-date 2026-03-31 --dry-run",
          configured_count: 0,
          missing_count: 4,
          invalid_count: 0,
          rows: ["AC", "OCI", "TPL", "all"].map((accountingClass) => ({
            accounting_class: accountingClass,
            status: "missing" as const,
            limit_dv01: zeroDv01,
            warning_dv01: zeroDv01,
            hedge_target_dv01: zeroDv01,
            limit_source: "unconfigured",
            limit_source_version: "unconfigured",
            limit_rule_version: "unconfigured",
            limit_effective_date: null,
            message: "未找到正式 DV01 限额配置。",
          })),
          warnings: ["未接入正式 DV01 限额配置；页面仅展示配置状态，不生成业务限额。"],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true, quality_flag: "warning" },
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
          warnings: ["formal_pending: bond-analysis action attribution must not be used as a formal metric."],
          computed_at: "2026-04-13T00:00:00Z",
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          source_surface: "bond_analytics",
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "bond_analytics_report_date",
          filters_applied: {
            report_date: reportDate,
            period_type: periodType,
          },
          tables_used: ["fact_formal_bond_analytics_daily"],
          evidence_rows: 0,
        },
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
      options?: { spreadScenarios?: string },
    ) {
      await delay();
      const spreadScenarios = options?.spreadScenarios ?? "10,25,50";
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.credit_spread_migration",
        {
          report_date: reportDate,
          credit_bond_count: 12,
          credit_market_value: formatRawAsNumeric({ raw: 1_500_000_000, unit: "yuan", sign_aware: false }),
          credit_weight: formatRawAsNumeric({ raw: 0.25, unit: "ratio", sign_aware: false }),
          rating_aa_and_below_weight: formatRawAsNumeric({ raw: 0.08, unit: "ratio", sign_aware: false }),
          spread_dv01: formatRawAsNumeric({ raw: 25_000, unit: "dv01", sign_aware: false }),
          weighted_avg_spread: formatRawAsNumeric({ raw: 80, unit: "bp", sign_aware: false }),
          weighted_avg_spread_duration: formatRawAsNumeric({ raw: 4.2, unit: "ratio", sign_aware: false }),
          spread_scenarios: [],
          migration_scenarios: [],
          concentration_by_issuer: {
            dimension: "issuer",
            hhi: formatRawAsNumeric({ raw: 0.12, unit: "ratio", sign_aware: false }),
            top5_concentration: formatRawAsNumeric({ raw: 0.3, unit: "ratio", sign_aware: false }),
            top_items: [
              {
                name: "Issuer A",
                weight: formatRawAsNumeric({ raw: 0.08, unit: "ratio", sign_aware: false }),
                market_value: formatRawAsNumeric({ raw: 480_000_000, unit: "yuan", sign_aware: false }),
              },
            ],
          },
          concentration_by_industry: {
            dimension: "industry",
            hhi: formatRawAsNumeric({ raw: 0.1, unit: "ratio", sign_aware: false }),
            top5_concentration: formatRawAsNumeric({ raw: 0.25, unit: "ratio", sign_aware: false }),
            top_items: [],
          },
          concentration_by_rating: {
            dimension: "rating",
            hhi: formatRawAsNumeric({ raw: 0.2, unit: "ratio", sign_aware: false }),
            top5_concentration: formatRawAsNumeric({ raw: 0.4, unit: "ratio", sign_aware: false }),
            top_items: [],
          },
          concentration_by_tenor: {
            dimension: "tenor",
            hhi: formatRawAsNumeric({ raw: 0.11, unit: "ratio", sign_aware: false }),
            top5_concentration: formatRawAsNumeric({ raw: 0.28, unit: "ratio", sign_aware: false }),
            top_items: [],
          },
          // 展示限额（后端下发，非风控正式限额）；与后端 CONCENTRATION_DISPLAY_LIMITS 过渡口径一致。
          display_limits: {
            issuer_single_max: 0.1,
            issuer_top5_max: 0.4,
            hhi_warning: 0.15,
            below_aa_max: 0.2,
            credit_weight_max: 0.85,
          },
          oci_credit_exposure: formatRawAsNumeric({ raw: 800_000_000, unit: "yuan", sign_aware: false }),
          oci_spread_dv01: formatRawAsNumeric({ raw: 12_000, unit: "dv01", sign_aware: false }),
          oci_sensitivity_25bp: formatRawAsNumeric({ raw: -300_000, unit: "yuan", sign_aware: true }),
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "bond_analytics_report_date",
          filters_applied: {
            report_date: reportDate,
            spread_scenarios: spreadScenarios,
          },
          tables_used: ["fact_formal_bond_analytics_daily"],
          evidence_rows: 0,
        },
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
      const items = buildMockBondTradingDeskTopHoldings(topN);
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.top_holdings",
        {
          report_date: reportDate,
          top_n: topN,
          items,
          total_market_value: sumMockTopHoldingsMarketValue(items),
          warnings: [],
          computed_at: "2026-04-13T00:00:00Z",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getBondAnalyticsPositionChanges(reportDate: string, topN = 5) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "bond_analytics.position_changes",
        {
          report_date: reportDate,
          prev_report_date: null,
          top_n: topN,
          source_status: "empty",
          items: [],
          total_market_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
          prev_total_market_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
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
  const methods: BondDashboardClientMethods = {
    async getBondDashboardDates() {
      await delay();
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.dates",
          { report_dates: [...MOCK_BOND_DASHBOARD_REPORT_DATES] },
          buildMockBondDashboardDatesMeta(),
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
      const prevReportDate = mockPreviousBondDashboardReportDate(reportDate);
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.headline_kpis",
          {
            report_date: reportDate,
            prev_report_date: prevReportDate,
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
            prev_kpis: prevReportDate
              ? {
                  total_market_value: zy(320_000_000_000),
                  unrealized_pnl: zy(1_600_000_000, true),
                  weighted_ytm: zp(0.0281),
                  weighted_duration: zr(3.52),
                  weighted_coupon: zp(0.0308),
                  credit_spread_median: zp(0.0089),
                  total_dv01: zd(-128_900),
                  bond_count: 415,
                }
              : null,
          },
          buildMockBondDashboardAnalyticalMeta(reportDate),
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardHomeSummary(reportDate: string) {
      await delay();
      const { sampleBondBusinessTypeMetricRows } = await ensureDashboardWorkbenchSamples();
      const [
        headline,
        risk,
        assetType,
        assetRating,
        maturity,
        industry,
        yieldDistribution,
        portfolioComparison,
        spread,
      ] = await Promise.all([
        methods.getBondDashboardHeadlineKpis(reportDate),
        methods.getBondDashboardRiskIndicators(reportDate),
        methods.getBondDashboardAssetStructure(reportDate, "bond_type"),
        methods.getBondDashboardAssetStructure(reportDate, "rating"),
        methods.getBondDashboardMaturityStructure(reportDate),
        methods.getBondDashboardIndustryDistribution(reportDate),
        methods.getBondDashboardYieldDistribution(reportDate),
        methods.getBondDashboardPortfolioComparison(reportDate),
        methods.getBondDashboardSpreadAnalysis(reportDate),
      ]);
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.home_summary",
          {
            report_date: reportDate,
            headline: headline.result,
            risk: risk.result,
            asset_type: assetType.result,
            asset_rating: assetRating.result,
            maturity: maturity.result,
            industry: industry.result,
            yield_distribution: yieldDistribution.result,
            portfolio_comparison: portfolioComparison.result,
            spread: spread.result,
            business_type: {
              report_date: reportDate,
              items: sampleBondBusinessTypeMetricRows,
            },
          },
          buildMockBondDashboardAnalyticalMeta(reportDate),
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardAssetStructure(reportDate: string, groupBy: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
      const totalMarketValue = 328_709_000_000;
      const rows = groupBy === "rating"
        ? [
            { category: "利率债默认 AAA", marketValue: 128_500_000_000, bondCount: 118 },
            { category: "AAA", marketValue: 92_000_000_000, bondCount: 106 },
            { category: "AA+", marketValue: 51_000_000_000, bondCount: 92 },
            { category: "AA", marketValue: 36_209_000_000, bondCount: 68 },
            { category: "未评级", marketValue: 21_000_000_000, bondCount: 44 },
          ]
        : groupBy === "portfolio_name"
          ? [
              { category: "银行账户", marketValue: 185_000_000_000, bondCount: 220 },
              { category: "交易账户", marketValue: 98_000_000_000, bondCount: 128 },
              { category: "OCI 账户", marketValue: 45_709_000_000, bondCount: 80 },
            ]
          : groupBy === "tenor_bucket"
            ? [
                { category: "1年以内", marketValue: 91_500_000_000, bondCount: 155 },
                { category: "1-3年", marketValue: 128_000_000_000, bondCount: 145 },
                { category: "3-5年", marketValue: 72_000_000_000, bondCount: 78 },
                { category: "5年以上", marketValue: 37_209_000_000, bondCount: 50 },
              ]
            : [
                { category: "政策性金融债", marketValue: 98_500_000_000, bondCount: 42 },
                { category: "地方政府债", marketValue: 82_000_000_000, bondCount: 56 },
                { category: "同业存单", marketValue: 71_000_000_000, bondCount: 120 },
                { category: "信用债-企业", marketValue: 49_209_000_000, bondCount: 150 },
                { category: "其他", marketValue: 28_000_000_000, bondCount: 60 },
              ];
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.asset_structure",
          {
            report_date: reportDate,
            group_by: groupBy,
            total_market_value: zy(totalMarketValue),
            items: rows.map((row) => ({
              category: row.category,
              total_market_value: zy(row.marketValue),
              bond_count: row.bondCount,
              percentage: zp(row.marketValue / totalMarketValue),
            })),
          },
          buildMockBondDashboardAnalyticalMeta(reportDate),
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
          buildMockBondDashboardAnalyticalMeta(reportDate),
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
          buildMockBondDashboardAnalyticalMeta(reportDate),
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
              {
                bond_type: "无收益率覆盖样例",
                median_yield: null,
                bond_count: 3,
                total_market_value: zy(0),
              },
            ],
          },
          buildMockBondDashboardAnalyticalMeta(reportDate),
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardMaturityStructure(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
      const totalMarketValue = 328_709_000_000;
      const rows = [
        { maturity_bucket: "7天内", total_market_value: 2_100_000_000, bond_count: 8 },
        { maturity_bucket: "8-30天", total_market_value: 8_900_000_000, bond_count: 22 },
        { maturity_bucket: "31-90天", total_market_value: 18_500_000_000, bond_count: 35 },
        { maturity_bucket: "91天-1年", total_market_value: 62_000_000_000, bond_count: 90 },
        { maturity_bucket: "1-3年", total_market_value: 128_000_000_000, bond_count: 145 },
        { maturity_bucket: "3-5年", total_market_value: 72_000_000_000, bond_count: 78 },
        { maturity_bucket: "5年以上", total_market_value: 37_209_000_000, bond_count: 50 },
      ];
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.maturity_structure",
          {
            report_date: reportDate,
            total_market_value: zy(totalMarketValue),
            items: rows.map((row) => ({
              maturity_bucket: row.maturity_bucket,
              total_market_value: zy(row.total_market_value),
              bond_count: row.bond_count,
              percentage: zp(row.total_market_value / totalMarketValue),
            })),
          },
          buildMockBondDashboardAnalyticalMeta(reportDate),
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async getBondDashboardIndustryDistribution(reportDate: string) {
      await delay();
      const zy = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
      const zp = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
      const totalMarketValue = 328_709_000_000;
      const rows = [
        { industry_name: "银行", total_market_value: 82_000_000_000, bond_count: 95 },
        { industry_name: "城投", total_market_value: 61_000_000_000, bond_count: 72 },
        { industry_name: "交通运输", total_market_value: 48_000_000_000, bond_count: 48 },
        { industry_name: "电力", total_market_value: 39_000_000_000, bond_count: 40 },
        { industry_name: "房地产", total_market_value: 28_000_000_000, bond_count: 35 },
        { industry_name: "其他", total_market_value: 70_709_000_000, bond_count: 138 },
      ];
      return {
        ...(await ensureMockClientBundle()).buildMockApiEnvelope(
          "bond_dashboard.industry_distribution",
          {
            report_date: reportDate,
            items: rows.map((row) => ({
              industry_name: row.industry_name,
              total_market_value: zy(row.total_market_value),
              bond_count: row.bond_count,
              percentage: zp(row.total_market_value / totalMarketValue),
            })),
          },
          buildMockBondDashboardAnalyticalMeta(reportDate),
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
            weighted_convexity_coverage_ratio: zr(0.91),
          },
          buildMockBondDashboardAnalyticalMeta(reportDate),
        ),
        data_source: "bond_analytics_facts",
      };
    },
    async fetchBondDashboardBundle(this: DemoBondDashboardBundleClient | undefined, reportDate, sections, opts) {
      await delay();
      const requestedSections = [...new Set(sections)];
      if (requestedSections.length === 0) {
        throw new Error("sections must include at least one supported section id");
      }
      const normalizedReportDate = reportDate?.trim() || null;
      if (requestedSections.some((section) => section !== "dates") && !normalizedReportDate) {
        throw new Error("report_date is required for the requested bundle sections");
      }
      const bundleClient =
        this && typeof this.getBondDashboardHeadlineKpis === "function"
          ? this
          : (methods as DemoBondDashboardBundleClient);
      const sectionEnvelopes: Partial<BondDashboardBundleSectionEnvelopeMap> = {};
      const sectionStatuses: BondDashboardBundlePayload["section_statuses"] = {};
      const failedSections: BondDashboardBundleSectionId[] = [];
      const entries = await Promise.all(
        requestedSections.map(async (section) => {
          try {
            const [, envelope] = await fetchDemoBondDashboardBundleSection(
              bundleClient,
              section,
              normalizedReportDate,
              ensureMockClientBundle,
              opts,
            );
            return { ok: true as const, section, envelope };
          } catch (error) {
            return { ok: false as const, section, error };
          }
        }),
      );
      for (const entry of entries) {
        if (!entry.ok) {
          failedSections.push(entry.section);
          sectionStatuses[entry.section] = {
            status: "error",
            message: entry.error instanceof Error ? entry.error.message : String(entry.error),
            duration_ms: 0,
          };
          continue;
        }
        (sectionEnvelopes as Record<BondDashboardBundleSectionId, ApiEnvelope<unknown>>)[entry.section] =
          entry.envelope as ApiEnvelope<unknown>;
        sectionStatuses[entry.section] = { status: "ok", message: null, duration_ms: 0 };
      }
      const bundle = buildMockBondDashboardBundleEnvelope({
        buildMockApiEnvelope: (await ensureMockClientBundle()).buildMockApiEnvelope,
        reportDate: normalizedReportDate,
        requestedSections,
        sections: sectionEnvelopes,
        industryTopN: opts?.industryTopN ?? 10,
        analyticsTopN: opts?.analyticsTopN ?? 10,
        dv01TopN: opts?.dv01TopN ?? 1,
        dv01ShockBps: opts?.dv01ShockBps ?? "1",
        dv01AccountingClass: opts?.dv01AccountingClass ?? "all",
        curveTypes: opts?.curveTypes ?? "treasury,cdb",
        sectionStatuses,
        failedSections,
      });
      const tablesUsed = normalizedReportDate
        ? [
            BOND_DASHBOARD_FACT_TABLE,
            ...(requestedSections.includes("yield-curve-term-structure")
              ? [YIELD_CURVE_FACT_TABLE]
              : []),
          ]
        : [];
      return {
        ...bundle,
        result_meta: {
          ...bundle.result_meta,
          ...BOND_DASHBOARD_NULL_CURRENCY_META,
          cache_key: null,
          formal_use_allowed: normalizedReportDate ? false : true,
          fallback_date: null,
          tables_used: tablesUsed,
          evidence_rows: normalizedReportDate ? MOCK_BOND_DASHBOARD_EVIDENCE_ROWS : 0,
          next_drill: [],
        },
      };
    },
  };
  return methods;
}
