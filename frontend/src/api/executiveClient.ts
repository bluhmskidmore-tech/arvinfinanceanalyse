/**
 * Executive Dashboard domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  AlertsPayload,
  ContributionPayload,
  GetHomeSnapshotOptions,
  GetHomeMacroReleaseContextOptions,
  HomeIncomeTrendPayload,
  HomeMacroReleaseContextPayload,
  HomeResearchReportsPayload,
  HomeSnapshotPayload,
  OverviewPayload,
  PlaceholderSnapshot,
  ResultMeta,
  RiskOverviewPayload,
  RiskScenarioStressPayload,
  RiskTensorDatesPayload,
  RiskTensorHistoryPayload,
  RiskTensorPayload,
  SummaryPayload,
} from "./contracts";
import { fetchHomeSnapshotEnvelope } from "./executiveHomeSnapshotFetch";

export type ExecutiveClientMethods = {
  getOverview: (reportDate?: string) => Promise<ApiEnvelope<OverviewPayload>>;
  getHomeSnapshot: (
    options?: GetHomeSnapshotOptions,
  ) => Promise<ApiEnvelope<HomeSnapshotPayload>>;
  getHomeMacroReleaseContext: (
    options: GetHomeMacroReleaseContextOptions,
  ) => Promise<ApiEnvelope<HomeMacroReleaseContextPayload>>;
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
  getRiskTensorHistory: (
    reportDate: string,
    periods?: number,
  ) => Promise<ApiEnvelope<RiskTensorHistoryPayload>>;
  getRiskScenarioStress: (reportDate: string) => Promise<ApiEnvelope<RiskScenarioStressPayload>>;
  getContribution: () => Promise<ApiEnvelope<ContributionPayload>>;
  getAlerts: () => Promise<ApiEnvelope<AlertsPayload>>;
  getPlaceholderSnapshot: (key: string) => Promise<ApiEnvelope<PlaceholderSnapshot>>;
};

type FetchLike = typeof fetch;
type Delay = () => Promise<void>;

const RISK_TENSOR_FORMAL_SOURCE_VERSION = "sv_risk_tensor_fact_mock_v3";
const RISK_TENSOR_FORMAL_RULE_VERSION = "rv_risk_tensor_formal_materialize_v6";
const RISK_TENSOR_FORMAL_CACHE_VERSION =
  "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v6";

type ExecutiveThinClientMethods = Pick<
  ExecutiveClientMethods,
  | "getOverview"
  | "getHomeSnapshot"
  | "getHomeMacroReleaseContext"
  | "getHomeResearchReports"
  | "getHomeIncomeTrend"
  | "getSummary"
  | "getRiskOverview"
  | "getRiskTensorDates"
  | "getRiskTensor"
  | "getRiskTensorHistory"
  | "getRiskScenarioStress"
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
};

function buildReadinessPlaceholderEnvelope(key: string): ApiEnvelope<PlaceholderSnapshot> {
  const normalizedKey = key.trim() || "unknown";
  const meta: ResultMeta = {
    trace_id: `readiness_${normalizedKey}`,
    basis: "analytical",
    result_kind: `workbench.${normalizedKey}.readiness`,
    formal_use_allowed: false,
    source_version: "readiness:placeholder",
    vendor_version: "vv_none",
    rule_version: "rv_readiness_placeholder_v1",
    cache_version: "cv_readiness_placeholder_v1",
    quality_flag: "missing",
    vendor_status: "ok",
    fallback_mode: "none",
    source_surface: "workbench_placeholder",
    scenario_flag: false,
    generated_at: "2026-04-09T10:30:00Z",
  };

  return {
    result_meta: meta,
    result: {
      title: normalizedKey === "source-preview" ? "Source Preview" : normalizedKey,
      summary: "",
      highlights: [],
    },
  };
}

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
    async getHomeMacroReleaseContext(options: GetHomeMacroReleaseContextOptions) {
      await delay();
      const bundle = await ensureBundle();
      return bundle.buildMockApiEnvelope<HomeMacroReleaseContextPayload>(
        "home.macro_release_context",
        {
          window_start_date: options.startDate,
          window_end_date: options.endDate,
          history_items: [],
          coverage: {
            configured_count: 8,
            ready_count: 0,
            partial_count: 0,
            stale_count: 0,
            fallback_count: 0,
            source_pending_count: 8,
            error_count: 0,
          },
          warnings: [],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
        },
      );
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
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: RISK_TENSOR_FORMAL_SOURCE_VERSION,
          rule_version: RISK_TENSOR_FORMAL_RULE_VERSION,
          cache_version: RISK_TENSOR_FORMAL_CACHE_VERSION,
        },
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
          missing_maturity_market_value: zero,
          missing_maturity_count: 0,
          floating_rate_proxy_market_value: zero,
          floating_rate_proxy_count: 0,
          payment_frequency_fallback_market_value: zero,
          payment_frequency_fallback_count: 0,
          bullet_value_date_fallback_market_value: zero,
          bullet_value_date_fallback_count: 0,
          projection_quality_status: "available",
          bond_count: 8,
          quality_flag: "warning",
          warnings: [
            "2 rows carry market_value=100000000.00000000 and are excluded from portfolio duration denominator.",
          ],
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: RISK_TENSOR_FORMAL_SOURCE_VERSION,
          rule_version: RISK_TENSOR_FORMAL_RULE_VERSION,
          cache_version: RISK_TENSOR_FORMAL_CACHE_VERSION,
        },
      );
    },
    async getRiskTensorHistory(reportDate: string, periods = 24) {
      await delay();
      const bundle = await ensureBundle();
      const vary = (base: number, amplitude: number, index: number, offset: number) =>
        (base * (1 + Math.sin(index * 0.55 + offset) * amplitude)).toFixed(8);
      const end = new Date(`${reportDate}T00:00:00Z`).getTime();
      const points = Array.from({ length: periods }, (_, index) => {
        const day = new Date(end - (periods - 1 - index) * 86400000);
        return {
          report_date: day.toISOString().slice(0, 10),
          portfolio_dv01: vary(120000, 0.04, index, 0.0),
          regulatory_dv01: vary(120000, 0.04, index, 0.0),
          portfolio_modified_duration: vary(4.2, 0.03, index, 1.3),
          portfolio_convexity: vary(24.5, 0.03, index, 2.1),
          cs01: vary(18000, 0.05, index, 0.7),
          issuer_concentration_hhi: vary(0.12, 0.06, index, 2.9),
          issuer_top5_weight: vary(0.36, 0.05, index, 3.7),
          liquidity_gap_30d: vary(100000000, 0.35, index, 4.4),
        };
      });
      return bundle.buildMockApiEnvelope(
        "risk.tensor.history",
        {
          report_date: reportDate,
          periods: points.length,
          window: {
            from: points[0]?.report_date ?? reportDate,
            to: points[points.length - 1]?.report_date ?? reportDate,
          },
          points,
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: RISK_TENSOR_FORMAL_SOURCE_VERSION,
          rule_version: RISK_TENSOR_FORMAL_RULE_VERSION,
          cache_version: RISK_TENSOR_FORMAL_CACHE_VERSION,
        },
      );
    },
    async getRiskScenarioStress(reportDate: string) {
      await delay();
      const bundle = await ensureBundle();
      const yuan = (raw: number | null, display?: string) => ({
        raw,
        unit: "yuan" as const,
        display: display ?? (raw === null ? "待接入" : raw.toLocaleString("zh-CN", { maximumFractionDigits: 2 })),
        precision: 2,
        sign_aware: true,
      });
      const bp = (raw: number) => ({
        raw,
        unit: "bp" as const,
        display: `${raw > 0 ? "+" : ""}${raw} bp`,
        precision: 0,
        sign_aware: true,
      });
      const pct = (raw: number | null) => ({
        raw,
        unit: "pct" as const,
        display: raw === null ? "待接入" : `${(raw * 100).toFixed(1)}%`,
        precision: 1,
        sign_aware: true,
      });
      const scenarios = [
        {
          scenario_key: "parallel_rate_up_10bp",
          category: "rate" as const,
          label: "利率平行上行 10bp",
          source_field: "regulatory_dv01",
          shock: bp(10),
          estimated_impact: yuan(-1_200_000),
          measure: "estimated_pnl_impact",
          calculation: "-regulatory_dv01 * shock_bp",
          interpretation: "利率上行时，按监管口径 DV01 估算组合价格影响。",
          data_status: "available" as const,
          human_review_required: true,
        },
        {
          scenario_key: "credit_spread_up_10bp",
          category: "credit" as const,
          label: "信用利差走阔 10bp",
          source_field: "cs01",
          shock: bp(10),
          estimated_impact: yuan(-180_000),
          measure: "estimated_pnl_impact",
          calculation: "-cs01 * shock_bp",
          interpretation: "信用利差走阔时，按 CS01 估算信用敏感性影响。",
          data_status: "available" as const,
          human_review_required: true,
        },
        {
          scenario_key: "liquidity_30d_cashflow_10pct",
          category: "liquidity" as const,
          label: "30天现金流压力 10%",
          source_field: "asset_cashflow_30d/liability_cashflow_30d/liquidity_gap_30d",
          shock: pct(0.1),
          estimated_impact: yuan(-50_000_000),
          measure: "stressed_30d_liquidity_gap_delta",
          calculation:
            "asset_cashflow_30d * (1 - shock_pct) - liability_cashflow_30d * (1 + shock_pct) - liquidity_gap_30d",
          interpretation: "现金流压力下的30天流动性缺口变化；负值表示缓冲收窄。",
          data_status: "available" as const,
          human_review_required: true,
          baseline_value: yuan(100_000_000),
          stressed_value: yuan(50_000_000),
          baseline_ratio: pct(0.05),
          stressed_ratio: pct(0.025),
        },
        {
          scenario_key: "fx_usdcny_move_candidate",
          category: "fx" as const,
          label: "汇率波动情景",
          source_field: "fx_exposure",
          shock: pct(null),
          estimated_impact: yuan(null),
          measure: "estimated_pnl_impact",
          calculation: "fx_exposure * fx_shock",
          interpretation: "当前风险张量未提供汇率敞口，需接入 FX exposure 后再估算。",
          data_status: "source_missing" as const,
          human_review_required: true,
        },
      ];
      return bundle.buildMockApiEnvelope(
        "risk.tensor.scenario_stress",
        {
          report_date: reportDate,
          basis: "scenario",
          scenario_set_id: "standard_risk_tensor_scenario_v1",
          rule_version: "rv_risk_tensor_scenario_stress_v1",
          source: {
            result_kind: "risk.tensor",
            trace_id: `mock_risk.tensor_${reportDate}`,
            source_version: RISK_TENSOR_FORMAL_SOURCE_VERSION,
            rule_version: RISK_TENSOR_FORMAL_RULE_VERSION,
            cache_version: RISK_TENSOR_FORMAL_CACHE_VERSION,
            quality_flag: "warning",
          },
          summary: {
            scenario_count: scenarios.length,
            available_count: 3,
            review_required_count: scenarios.length,
            worst_estimated_impact: yuan(-50_000_000),
            worst_scenario_key: "liquidity_30d_cashflow_10pct",
            message: "已生成标准多情景压力估算；所有结果均为情景口径，需复核后再用于经营判断。",
          },
          scenarios,
          warnings: ["情景压力结果为基于正式风险张量的敏感性覆盖层，不是正式损益、正式限额判定或交易建议。"],
          source_warnings: [],
        },
        { basis: "scenario", formal_use_allowed: false, scenario_flag: true },
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
  const { fetchImpl, baseUrl, requestJson } = options;

  return {
    getOverview: (reportDate?: string) =>
      requestJson<OverviewPayload>(
        fetchImpl,
        baseUrl,
        `/ui/home/overview${reportDate?.trim() ? `?report_date=${encodeURIComponent(reportDate.trim())}` : ""}`,
      ),
    getHomeSnapshot: (options?: GetHomeSnapshotOptions) =>
      fetchHomeSnapshotEnvelope(fetchImpl, baseUrl, options),
    getHomeMacroReleaseContext: (options: GetHomeMacroReleaseContextOptions) => {
      const params = new URLSearchParams({
        start_date: options.startDate,
        end_date: options.endDate,
        history_limit: String(options.historyLimit ?? 8),
      });
      return requestJson<HomeMacroReleaseContextPayload>(
        fetchImpl,
        baseUrl,
        `/ui/home/macro-release-context?${params.toString()}`,
      );
    },
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
    getRiskTensorHistory: (reportDate: string, periods = 24) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        periods: String(periods),
      });
      return requestJson<RiskTensorHistoryPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/tensor/history?${params.toString()}`,
      );
    },
    getRiskScenarioStress: (reportDate: string) =>
      requestJson<RiskScenarioStressPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/scenario-stress?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getContribution: () =>
      requestJson<ContributionPayload>(
        fetchImpl,
        baseUrl,
        "/ui/home/contribution",
      ),
    getAlerts: () =>
      requestJson<AlertsPayload>(fetchImpl, baseUrl, "/ui/home/alerts"),
    async getPlaceholderSnapshot(key: string) {
      return buildReadinessPlaceholderEnvelope(key);
    },
  };
}
