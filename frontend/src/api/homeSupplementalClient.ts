import type { ApiClient } from "./client";
import type { BalanceMovementClientMethods } from "./balanceMovementClient";
import type {
  ApiEnvelope,
  AssetStructurePayload,
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisDatesPayload,
  BalanceAnalysisOverviewPayload,
  BalanceAnalysisPayload,
  BalanceAnalysisSummaryTablePayload,
  BalanceAnalysisWorkbookPayload,
  BalanceAnalysisAdvancedAttributionBundlePayload,
  BalanceAnalysisCurrentUserPayload,
  BondDashboardHeadlinePayload,
  BondDashboardHomeSummaryPayload,
  BondPositionChangesPayload,
  BondPortfolioHeadlinesPayload,
  BondTopHoldingsPayload,
  CampisiFourEffectsPayload,
  CockpitWarningsPayload,
  CoreMetricsResult,
  CreditSpreadMigrationPayload,
  DailyChangesResult,
  IndustryDistPayload,
  MaturityStructurePayload,
  Numeric,
  NumericUnit,
  PortfolioComparisonPayload,
  ReturnDecompositionPayload,
  RiskIndicatorsPayload,
  YieldCurveTermStructurePayload,
} from "./contracts";
import type { LiabilityAdbClientMethods } from "./liabilityAdbClient";
import { readHttpJsonDetail } from "./httpResponseError";
import { parseNumericOrNull } from "./numeric";
import { formatRawAsNumeric } from "../utils/format";

type FetchLike = typeof fetch;

export type HomeSupplementalClientMethods = Pick<
  ApiClient,
  | "getCoreMetrics"
  | "getDailyChanges"
  | "getBondDashboardHeadlineKpis"
  | "getBondDashboardHomeSummary"
  | "getBondAnalyticsPortfolioHeadlines"
  | "getBondDashboardPortfolioComparison"
  | "getBondAnalyticsCreditSpreadMigration"
  | "getBondAnalyticsReturnDecomposition"
  | "getPnlCampisiFourEffects"
  | "getBondAnalyticsYieldCurveTermStructure"
  | "getBalanceAnalysisDates"
  | "getBalanceAnalysisOverview"
  | "getBalanceAnalysisSummaryByBasis"
  | "getBalanceAnalysisSummary"
  | "getBalanceAnalysisWorkbook"
  | "getBalanceAnalysisCurrentUser"
  | "getBalanceAnalysisDetail"
  | "getBalanceAnalysisAdvancedAttribution"
  | "getBalanceAnalysisDecisionItems"
  | "getBalanceMovementDates"
  | "getBalanceMovementAnalysis"
  | "getAdbComparison"
  | "getBondDashboardAssetStructure"
  | "getBondDashboardMaturityStructure"
  | "getBondDashboardIndustryDistribution"
  | "getBondDashboardRiskIndicators"
  | "getBondAnalyticsTopHoldings"
  | "getBondAnalyticsPositionChanges"
  | "getCockpitWarnings"
>;

type HomeSupplementalClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

type HomeSupplementalMockBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

let mockBundlePromise: Promise<HomeSupplementalMockBundle> | null = null;
let mockClientPromise: Promise<HomeSupplementalClientMethods> | null = null;

const delay = async () => new Promise<void>((resolve) => setTimeout(resolve, 40));

async function ensureMockBundle(): Promise<HomeSupplementalMockBundle> {
  if (!mockBundlePromise) {
    mockBundlePromise = import("../mocks/mockApiEnvelope").then((module) => ({
      buildMockApiEnvelope: module.buildMockApiEnvelope,
    }));
  }
  return mockBundlePromise;
}

async function requestJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<TData>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<TData>;
}

async function requestActionJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<TData> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as TData;
}

function reportDateSuffix(reportDate?: string) {
  const trimmed = reportDate?.trim();
  return trimmed ? `?report_date=${encodeURIComponent(trimmed)}` : "";
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

function decimalRaw(value: unknown): number | null {
  const parsed = parseNumericOrNull(value);
  if (parsed) {
    return parsed.raw;
  }
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const raw = typeof value === "number" ? value : Number.parseFloat(String(value));
  return Number.isFinite(raw) ? raw : null;
}

function normalizeNumeric(
  value: unknown,
  unit: NumericUnit,
  signAware: boolean,
  precision?: number,
): Numeric {
  const parsed = parseNumericOrNull(value);
  if (parsed) {
    return parsed;
  }
  return formatRawAsNumeric({
    raw: decimalRaw(value),
    unit,
    sign_aware: signAware,
    precision,
  });
}

function normalizeConcentration(
  value: unknown,
): CreditSpreadMigrationPayload["concentration_by_rating"] {
  if (!value || typeof value !== "object") {
    return undefined;
  }
  const source = value as Record<string, unknown>;
  const topItems = Array.isArray(source.top_items) ? source.top_items : [];
  return {
    ...source,
    dimension: String(source.dimension ?? ""),
    hhi: normalizeNumeric(source.hhi, "ratio", false),
    top5_concentration: normalizeNumeric(source.top5_concentration, "ratio", false),
    top_items: topItems.map((item) => {
      const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
      return {
        ...row,
        name: String(row.name ?? ""),
        weight: normalizeNumeric(row.weight, "ratio", false),
        market_value: normalizeNumeric(row.market_value, "yuan", false),
      };
    }),
  };
}

function normalizeCreditSpreadMigrationEnvelope(
  envelope: ApiEnvelope<CreditSpreadMigrationPayload>,
): ApiEnvelope<CreditSpreadMigrationPayload> {
  const source = envelope.result as unknown as Record<string, unknown>;
  const spreadScenarios = Array.isArray(source.spread_scenarios) ? source.spread_scenarios : [];
  const migrationScenarios = Array.isArray(source.migration_scenarios) ? source.migration_scenarios : [];
  const bondDetails = Array.isArray(source.bond_details) ? source.bond_details : undefined;
  return {
    ...envelope,
    result: {
      ...envelope.result,
      credit_market_value: normalizeNumeric(source.credit_market_value, "yuan", false),
      credit_weight: normalizeNumeric(source.credit_weight, "ratio", false),
      rating_aa_and_below_weight: normalizeNumeric(source.rating_aa_and_below_weight, "ratio", false),
      spread_dv01: normalizeNumeric(source.spread_dv01, "dv01", false),
      weighted_avg_spread: normalizeNumeric(source.weighted_avg_spread, "bp", false, 2),
      weighted_avg_spread_duration: normalizeNumeric(source.weighted_avg_spread_duration, "ratio", false),
      spread_scenarios: spreadScenarios.map((item) => {
        const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
        return {
          ...row,
          scenario_name: String(row.scenario_name ?? ""),
          spread_change_bp: normalizeNumeric(row.spread_change_bp, "bp", true),
          pnl_impact: normalizeNumeric(row.pnl_impact, "yuan", true),
          oci_impact: normalizeNumeric(row.oci_impact, "yuan", true),
          tpl_impact: normalizeNumeric(row.tpl_impact, "yuan", true),
        };
      }),
      migration_scenarios: migrationScenarios.map((item) => {
        const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
        return {
          ...row,
          scenario_name: String(row.scenario_name ?? ""),
          from_rating: String(row.from_rating ?? ""),
          to_rating: String(row.to_rating ?? ""),
          affected_bonds: Number(row.affected_bonds ?? 0),
          affected_market_value: normalizeNumeric(row.affected_market_value, "yuan", false),
          pnl_impact: normalizeNumeric(row.pnl_impact, "yuan", true),
          oci_impact: normalizeNumeric(row.oci_impact, "yuan", true),
        };
      }),
      concentration_by_issuer: normalizeConcentration(source.concentration_by_issuer),
      concentration_by_industry: normalizeConcentration(source.concentration_by_industry),
      concentration_by_rating: normalizeConcentration(source.concentration_by_rating),
      concentration_by_tenor: normalizeConcentration(source.concentration_by_tenor),
      bond_details: bondDetails?.map((item) => {
        const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
        return {
          ...row,
          market_value: normalizeNumeric(row.market_value, "yuan", false),
        };
      }),
      oci_credit_exposure: normalizeNumeric(source.oci_credit_exposure, "yuan", false),
      oci_spread_dv01: normalizeNumeric(source.oci_spread_dv01, "dv01", false),
      oci_sensitivity_25bp: normalizeNumeric(source.oci_sensitivity_25bp, "yuan", true),
    },
  };
}

function normalizePortfolioHeadlinesEnvelope(
  envelope: ApiEnvelope<BondPortfolioHeadlinesPayload>,
): ApiEnvelope<BondPortfolioHeadlinesPayload> {
  const source = envelope.result as unknown as Record<string, unknown>;
  const byAssetClass = Array.isArray(source.by_asset_class) ? source.by_asset_class : [];
  return {
    ...envelope,
    result: {
      ...envelope.result,
      total_market_value: normalizeNumeric(source.total_market_value, "yuan", false),
      weighted_ytm: normalizeNumeric(source.weighted_ytm, "pct", true),
      weighted_duration: normalizeNumeric(source.weighted_duration, "ratio", false),
      weighted_coupon: normalizeNumeric(source.weighted_coupon, "pct", true),
      total_dv01: normalizeNumeric(source.total_dv01, "dv01", false),
      credit_weight: normalizeNumeric(source.credit_weight, "ratio", false),
      issuer_hhi: normalizeNumeric(source.issuer_hhi, "ratio", false),
      issuer_top5_weight: normalizeNumeric(source.issuer_top5_weight, "ratio", false),
      by_asset_class: byAssetClass.map((item) => {
        const row = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
        return {
          ...row,
          asset_class: String(row.asset_class ?? ""),
          market_value: normalizeNumeric(row.market_value, "yuan", false),
          duration: normalizeNumeric(row.duration, "ratio", false),
          dv01: normalizeNumeric(row.dv01, "dv01", false),
          weight: normalizeNumeric(row.weight, "ratio", false),
        };
      }),
    },
  };
}

async function loadMockClient(): Promise<HomeSupplementalClientMethods> {
  if (!mockClientPromise) {
    mockClientPromise = Promise.all([
      import("./workbenchDashboardApi"),
      import("./bondAnalyticsClient"),
      import("./balanceAnalysisClient"),
      import("./balanceMovementClient"),
      import("./pnlAttributionMockClient"),
      import("./liabilityAdbClient"),
    ]).then(
      ([
        dashboardModule,
        bondModule,
        balanceModule,
        balanceMovementModule,
        pnlAttributionModule,
        liabilityModule,
      ]) =>
        ({
          ...dashboardModule.dashboardWorkbenchDemoEndpoints(delay, ensureMockBundle),
          ...bondModule.createDemoBondDashboardClient(delay, ensureMockBundle),
          ...bondModule.createDemoBondAnalyticsClient(delay, ensureMockBundle),
          ...balanceModule.createDemoBalanceAnalysisClient(delay, ensureMockBundle),
          ...balanceMovementModule.createMockBalanceMovementClient(),
          ...pnlAttributionModule.createDemoPnlAttributionClient(delay),
          ...liabilityModule.createDemoLiabilityAdbClient(delay, ensureMockBundle),
        }) as HomeSupplementalClientMethods,
    );
  }
  return mockClientPromise;
}

export function createRealHomeSupplementalClient({
  fetchImpl,
  baseUrl,
}: HomeSupplementalClientFactoryOptions): HomeSupplementalClientMethods {
  let balanceMovementClientPromise: Promise<BalanceMovementClientMethods> | null = null;
  let liabilityAdbClientPromise: Promise<LiabilityAdbClientMethods> | null = null;

  const loadBalanceMovementClient = () => {
    if (!balanceMovementClientPromise) {
      balanceMovementClientPromise = import("./balanceMovementClient").then(
        ({ createRealBalanceMovementClient }) =>
          createRealBalanceMovementClient({ fetchImpl, baseUrl }),
      );
    }
    return balanceMovementClientPromise;
  };

  const loadLiabilityAdbClient = () => {
    if (!liabilityAdbClientPromise) {
      liabilityAdbClientPromise = import("./liabilityAdbClient").then(
        ({ createRealLiabilityAdbClient }) =>
          createRealLiabilityAdbClient({ fetchImpl, baseUrl, requestJson }),
      );
    }
    return liabilityAdbClientPromise;
  };

  return {
    getCoreMetrics: ({ reportDate } = {}) =>
      requestJson<CoreMetricsResult>(
        fetchImpl,
        baseUrl,
        `/api/dashboard/core_metrics${reportDateSuffix(reportDate)}`,
      ),
    getDailyChanges: ({ reportDate } = {}) =>
      requestJson<DailyChangesResult>(
        fetchImpl,
        baseUrl,
        `/api/dashboard/daily-changes${reportDateSuffix(reportDate)}`,
      ),
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
    getBondAnalyticsPortfolioHeadlines: (reportDate: string) =>
      requestJson<BondPortfolioHeadlinesPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/portfolio-headlines?report_date=${encodeURIComponent(reportDate)}`,
      ).then(normalizePortfolioHeadlinesEnvelope),
    getBondDashboardPortfolioComparison: (reportDate: string) =>
      requestJson<PortfolioComparisonPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/portfolio-comparison?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getBondAnalyticsCreditSpreadMigration: (
      reportDate: string,
      options?: { spreadScenarios?: string },
    ) => {
      const params = new URLSearchParams({ report_date: reportDate });
      if (options?.spreadScenarios) {
        params.set("spread_scenarios", options.spreadScenarios);
      }
      return requestJson<CreditSpreadMigrationPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/credit-spread-migration?${params.toString()}`,
      ).then(normalizeCreditSpreadMigrationEnvelope);
    },
    getBondAnalyticsReturnDecomposition: (
      reportDate: string,
      periodType: string,
      options?: { assetClass?: string; accountingClass?: string; detail?: "full" | "summary" },
    ) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        period_type: periodType,
      });
      if (options?.assetClass) {
        params.set("asset_class", options.assetClass);
      }
      if (options?.accountingClass) {
        params.set("accounting_class", options.accountingClass);
      }
      if (options?.detail) {
        params.set("detail", options.detail);
      }
      return requestJson<ReturnDecompositionPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/return-decomposition?${params.toString()}`,
      );
    },
    getPnlCampisiFourEffects: (options) =>
      requestJson<CampisiFourEffectsPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/campisi/four-effects${buildCampisiQuery(options)}`,
      ),
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
    getBalanceAnalysisSummary: ({ reportDate, positionScope, currencyBasis, limit, offset }) => {
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
    getBalanceMovementDates: (currencyBasis) =>
      loadBalanceMovementClient().then((client) =>
        client.getBalanceMovementDates(currencyBasis),
      ),
    getBalanceMovementAnalysis: (options) =>
      loadBalanceMovementClient().then((client) =>
        client.getBalanceMovementAnalysis(options),
      ),
    getAdbComparison: (startDate, endDate, options) =>
      loadLiabilityAdbClient().then((client) =>
        client.getAdbComparison(startDate, endDate, options),
      ),
    getBondDashboardAssetStructure: (reportDate: string, groupBy: string) =>
      requestJson<AssetStructurePayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/asset-structure?report_date=${encodeURIComponent(reportDate)}&group_by=${encodeURIComponent(groupBy)}`,
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
    getCockpitWarnings: (reportDate?: string | null) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const query = params.toString();
      return requestJson<CockpitWarningsPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/liabilities/cockpit-warnings${query ? `?${query}` : ""}`,
      );
    },
  };
}

export function createMockHomeSupplementalClient(): HomeSupplementalClientMethods {
  return new Proxy({} as HomeSupplementalClientMethods, {
    get(target, property, receiver) {
      if (property === "then") {
        return undefined;
      }
      if (typeof property === "symbol") {
        return Reflect.get(target, property, receiver);
      }
      return async (...args: unknown[]) => {
        const client = await loadMockClient();
        const method = client[property as keyof HomeSupplementalClientMethods] as (
          ...methodArgs: unknown[]
        ) => unknown;
        return method(...args);
      };
    },
  });
}
