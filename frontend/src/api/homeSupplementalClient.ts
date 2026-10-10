import type { ApiClient } from "./client";
import type { BalanceMovementClientMethods } from "./balanceMovementClient";
import { createRealBalanceAnalysisOverviewClient } from "./balanceAnalysisOverviewClient";
import type {
  ApiEnvelope,
  AssetStructurePayload,
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisDatesPayload,
  BalanceAnalysisPublicationStatusPayload,
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
  PortfolioComparisonPayload,
  KRDCurveRiskPayload,
  ReturnDecompositionPayload,
  RiskIndicatorsPayload,
  YieldCurveTermStructurePayload,
} from "./contracts";
import type { LiabilityAdbClientMethods } from "./liabilityAdbClient";
import { readHttpJsonDetail } from "./httpResponseError";
import { normalizeCreditSpreadMigrationEnvelope, normalizePortfolioHeadlinesEnvelope } from "./bondAnalyticsNormalization";
import { assertApiEnvelopeShape, requestJson as requestTransportJson } from "./transport";

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
  | "getBondAnalyticsKrdCurveRisk"
  | "getBalanceAnalysisDates"
  | "getBalanceAnalysisPublicationStatus"
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

function requestJson<TData>(fetchImpl: FetchLike, baseUrl: string, path: string): Promise<ApiEnvelope<TData>> {
  return requestTransportJson<TData>(fetchImpl, baseUrl, path, { errorDetail: "json-detail" });
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
  detail?: "full" | "summary";
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
  if (options?.detail) {
    params.set("detail", options.detail);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function loadMockClient(): Promise<HomeSupplementalClientMethods> {
  if (!mockClientPromise) {
    mockClientPromise = Promise.all([
      import("../mocks/workbenchDashboardMockApi"),
      import("../mocks/bondAnalyticsMockClient"),
      import("../mocks/balanceAnalysisMockClient"),
      import("../mocks/balanceMovementMockClient"),
      import("../mocks/pnlAttributionMockClient"),
      import("../mocks/liabilityAdbMockClient"),
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
    getBondAnalyticsKrdCurveRisk: (
      reportDate: string,
      options?: { scenarioSet?: string },
    ) => {
      const params = new URLSearchParams({ report_date: reportDate });
      if (options?.scenarioSet) {
        params.set("scenario_set", options.scenarioSet);
      }
      return requestJson<KRDCurveRiskPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/krd-curve-risk?${params.toString()}`,
      );
    },
    getBalanceAnalysisDates: async () => {
      const path = "/ui/balance-analysis/dates";
      const envelope = await requestJson<BalanceAnalysisDatesPayload>(
        fetchImpl,
        baseUrl,
        path,
      );
      assertApiEnvelopeShape(envelope, `${baseUrl}${path}`, [
        { path: "report_dates", type: "array" },
      ]);
      return envelope;
    },
    getBalanceAnalysisPublicationStatus: () =>
      requestActionJson<BalanceAnalysisPublicationStatusPayload>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/publication-status",
      ),
    ...createRealBalanceAnalysisOverviewClient({
      fetchImpl,
      baseUrl,
      requestJson: (fetchImpl, baseUrl, path) =>
        requestTransportJson(fetchImpl, baseUrl, path, { errorDetail: "json-detail" }),
    }),
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
    getBalanceMovementDates: (currencyBasis, options) =>
      loadBalanceMovementClient().then((client) =>
        client.getBalanceMovementDates(currencyBasis, options),
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
