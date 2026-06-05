/**
 * Executive Dashboard domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  AlertsPayload,
  ContributionPayload,
  GetHomeSnapshotOptions,
  HomeIncomeTrendPayload,
  HomeResearchReportsPayload,
  HomeSnapshotPayload,
  OverviewPayload,
  PlaceholderSnapshot,
  RiskOverviewPayload,
  RiskTensorDatesPayload,
  RiskTensorPayload,
  SummaryPayload,
} from "./contracts";
import { fetchHomeSnapshotEnvelope } from "./executiveHomeSnapshotFetch";

export type ExecutiveClientMethods = {
  getOverview: (reportDate?: string) => Promise<ApiEnvelope<OverviewPayload>>;
  getHomeSnapshot: (
    options?: GetHomeSnapshotOptions,
  ) => Promise<ApiEnvelope<HomeSnapshotPayload>>;
  getHomeResearchReports: (
    reportDate: string,
    limit?: number,
  ) => Promise<ApiEnvelope<HomeResearchReportsPayload>>;
  getHomeIncomeTrend: (
    reportDate: string,
    window?: number,
  ) => Promise<ApiEnvelope<HomeIncomeTrendPayload>>;
  getSummary: () => Promise<ApiEnvelope<SummaryPayload>>;
  getRiskOverview: () => Promise<ApiEnvelope<RiskOverviewPayload>>;
  getRiskTensorDates: () => Promise<ApiEnvelope<RiskTensorDatesPayload>>;
  getRiskTensor: (reportDate: string) => Promise<ApiEnvelope<RiskTensorPayload>>;
  getContribution: () => Promise<ApiEnvelope<ContributionPayload>>;
  getAlerts: () => Promise<ApiEnvelope<AlertsPayload>>;
  getPlaceholderSnapshot: (key: string) => Promise<ApiEnvelope<PlaceholderSnapshot>>;
};

type FetchLike = typeof fetch;
type Delay = () => Promise<void>;

type ExecutiveThinClientMethods = Pick<
  ExecutiveClientMethods,
  | "getOverview"
  | "getHomeSnapshot"
  | "getHomeResearchReports"
  | "getHomeIncomeTrend"
  | "getSummary"
  | "getRiskOverview"
  | "getRiskTensorDates"
  | "getRiskTensor"
  | "getContribution"
  | "getAlerts"
  | "getPlaceholderSnapshot"
>;

type ExecutiveMockBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
> &
  Pick<
    typeof import("../mocks/workbench"),
    | "overviewPayload"
    | "mockHomeSnapshot"
    | "summaryPayload"
    | "riskOverviewPayload"
    | "contributionPayload"
    | "alertsPayload"
    | "placeholderSnapshots"
  >;

type EnsureExecutiveMockBundle = () => Promise<ExecutiveMockBundle>;

type RequestJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
) => Promise<ApiEnvelope<T>>;

export type ExecutiveClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
  getPlaceholderSnapshot: ExecutiveClientMethods["getPlaceholderSnapshot"];
};

export function createDemoExecutiveClient(
  delay: Delay,
  ensureBundle: EnsureExecutiveMockBundle,
): ExecutiveThinClientMethods {
  return {
    async getOverview(_reportDate?: string) {
      await delay();
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope("executive.overview", bundle.overviewPayload);
    },
    async getHomeSnapshot(_options?: GetHomeSnapshotOptions) {
      await delay();
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope("home.snapshot", bundle.mockHomeSnapshot);
    },
    async getHomeResearchReports(reportDate: string, limit = 5) {
      await delay();
      void limit;
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope(
        "home.research_reports",
        {
          report_date: reportDate,
          source_status: "empty",
          items: [],
          warnings: [],
        },
        { basis: "analytical", formal_use_allowed: false },
      );
    },
    async getHomeIncomeTrend(reportDate: string, window = 7) {
      await delay();
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope(
        "home.income_trend",
        {
          report_date: reportDate,
          window,
          source_status: "empty",
          points: [],
          missing_components: [],
          warnings: [],
        },
        { basis: "analytical", formal_use_allowed: false },
      );
    },
    async getSummary() {
      await delay();
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope("executive.summary", bundle.summaryPayload);
    },
    async getRiskOverview() {
      await delay();
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope("executive.risk-overview", bundle.riskOverviewPayload);
    },
    async getRiskTensorDates() {
      await delay();
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope(
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
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope(
        "risk.tensor",
        {
          report_date: reportDate,
          portfolio_dv01: "120000.00000000",
          regulatory_dv01: "120000.00000000",
          krd_1y: "25000.00000000",
          krd_3y: "50000.00000000",
          krd_5y: "30000.00000000",
          krd_7y: "10000.00000000",
          krd_10y: "5000.00000000",
          krd_30y: zero,
          cs01: "18000.00000000",
          portfolio_convexity: "24.50000000",
          portfolio_modified_duration: "4.20000000",
          issuer_concentration_hhi: "0.12000000",
          issuer_top5_weight: "0.36000000",
          asset_cashflow_30d: "300000000.00000000",
          asset_cashflow_90d: "500000000.00000000",
          liability_cashflow_30d: "200000000.00000000",
          liability_cashflow_90d: "250000000.00000000",
          liquidity_gap_30d: "100000000.00000000",
          liquidity_gap_90d: "250000000.00000000",
          liquidity_gap_30d_ratio: "0.05000000",
          total_market_value: "500000000.00000000",
          rate_risk_market_value: "400000000.00000000",
          rate_risk_dv01: "110000.00000000",
          rate_risk_modified_duration: "4.20000000",
          duration_excluded_market_value: "100000000.00000000",
          duration_excluded_count: 2,
          bond_count: 8,
          quality_flag: "warning",
          warnings: [
            "2 rows carry market_value=100000000.00000000 and are excluded from portfolio duration denominator.",
          ],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getContribution() {
      await delay();
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope("executive.contribution", bundle.contributionPayload);
    },
    async getAlerts() {
      await delay();
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope("executive.alerts", bundle.alertsPayload);
    },
    async getPlaceholderSnapshot(key: string) {
      await delay();
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope(
        `workbench.${key}`,
        bundle.placeholderSnapshots[key] ?? bundle.placeholderSnapshots.dashboard,
      );
    },
  };
}

export function createRealExecutiveClient(
  options: ExecutiveClientFactoryOptions,
): ExecutiveThinClientMethods {
  const { fetchImpl, baseUrl, requestJson, getPlaceholderSnapshot } = options;

  return {
    getOverview: (reportDate?: string) =>
      requestJson<OverviewPayload>(
        fetchImpl,
        baseUrl,
        `/ui/home/overview${reportDate?.trim() ? `?report_date=${encodeURIComponent(reportDate.trim())}` : ""}`,
      ),
    getHomeSnapshot: (options?: GetHomeSnapshotOptions) =>
      fetchHomeSnapshotEnvelope(fetchImpl, baseUrl, options),
    getHomeResearchReports: (reportDate: string, limit = 5) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        limit: String(limit),
      });
      return requestJson<HomeResearchReportsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/home/research-reports?${params.toString()}`,
      );
    },
    getHomeIncomeTrend: (reportDate: string, window = 7) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        window: String(window),
      });
      return requestJson<HomeIncomeTrendPayload>(
        fetchImpl,
        baseUrl,
        `/ui/home/income-trend?${params.toString()}`,
      );
    },
    getSummary: () =>
      requestJson<SummaryPayload>(fetchImpl, baseUrl, "/ui/home/summary"),
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
    getContribution: () =>
      requestJson<ContributionPayload>(
        fetchImpl,
        baseUrl,
        "/ui/home/contribution",
      ),
    getAlerts: () =>
      requestJson<AlertsPayload>(fetchImpl, baseUrl, "/ui/home/alerts"),
    getPlaceholderSnapshot,
  };
}
