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
  ResultMeta,
  RiskOverviewPayload,
  RiskScenarioStressPayload,
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
  getRiskScenarioStress: (reportDate: string) => Promise<ApiEnvelope<RiskScenarioStressPayload>>;
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
          ac_dv01: "70000.00000000",
          oci_dv01: "30000.00000000",
          tpl_dv01: "20000.00000000",
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
          prior_period_change: {
            status: "no_prior",
            comparison_report_date: null,
            summary: "暂无可比较的上一报告日；当前仅展示截面风险。",
            dominant_krd_bucket: "3Y",
            previous_dominant_krd_bucket: null,
            dominant_krd_shifted: false,
            metrics: [],
          },
          dv01_controls: {
            basis: "regulatory_dv01",
            limit_status: "pending_configuration",
            approved_limit_dv01: null,
            limit_usage_ratio: null,
            volatility_status: "pending_market_volatility",
            daily_rate_volatility_bp: null,
            dominant_krd_bucket: "3Y",
            dominant_krd: {
              raw: 50000,
              unit: "dv01",
              display: "+50,000.00",
              precision: 2,
              sign_aware: true,
            },
            stress_scenarios: [
              {
                scenario_key: "parallel_up_10bp",
                label: "+10bp",
                shock_bp: {
                  raw: 10,
                  unit: "bp",
                  display: "+10 bp",
                  precision: 0,
                  sign_aware: true,
                },
                estimated_pnl_impact: {
                  raw: -1200000,
                  unit: "yuan",
                  display: "-1,200,000.00",
                  precision: 2,
                  sign_aware: true,
                },
              },
              {
                scenario_key: "parallel_up_25bp",
                label: "+25bp",
                shock_bp: {
                  raw: 25,
                  unit: "bp",
                  display: "+25 bp",
                  precision: 0,
                  sign_aware: true,
                },
                estimated_pnl_impact: {
                  raw: -3000000,
                  unit: "yuan",
                  display: "-3,000,000.00",
                  precision: 2,
                  sign_aware: true,
                },
              },
            ],
            operating_judgement:
              "当前监管口径 DV01 120,000.00；+10bp 平行上行估算影响 -1,200,000.00；主风险桶 3Y。审批限额与利率波动源未接入前，暂不判定超限。",
            control_actions: [
              {
                key: "approved_dv01_limit",
                title: "配置审批限额",
                status: "required",
                evidence: "审批 DV01 限额未接入。",
                action: "接入投委会或风控审批后的总 DV01 限额，再计算使用率与预警带。",
              },
              {
                key: "rate_volatility_input",
                title: "接入利率波动",
                status: "required",
                evidence: "日度利率波动率未接入。",
                action: "接入曲线波动率后，把 DV01 敞口转换成日度波动损益观察。",
              },
              {
                key: "bucket_sub_limits",
                title: "拆分期限桶限额",
                status: "required",
                evidence: "当前主风险桶为 3Y。",
                action: "为 1Y/3Y/5Y/7Y/10Y/30Y 设置桶位限额，避免总 DV01 合规但期限错配。",
              },
              {
                key: "stress_escalation",
                title: "固化冲击升级",
                status: "required",
                evidence: "+10bp 估算影响 -1,200,000.00；+25bp 估算影响 -3,000,000.00。",
                action: "将标准冲击纳入日例会；超过授权阈值时进入减久期、套保或审批升级流程。",
              },
            ],
            control_message: "未接入正式限额源前，只展示当前监管口径敞口和标准平行冲击，不判定是否超限。",
            action_hint: "经营落地需要先配置审批 DV01 限额、利率波动率输入与预警阈值，再计算使用率和波动预警。",
          },
        },
        { basis: "formal", formal_use_allowed: true },
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
          scenario_key: "rate_parallel_up_25bp",
          category: "rate" as const,
          label: "利率平行上行 25bp",
          source_field: "regulatory_dv01",
          shock: bp(25),
          estimated_impact: yuan(-3_000_000),
          measure: "estimated_pnl_impact",
          calculation: "-regulatory_dv01 * shock_bp",
          interpretation: "利率上行时，按监管口径 DV01 估算组合价格影响。",
          data_status: "available" as const,
          human_review_required: true,
        },
        {
          scenario_key: "credit_spread_widen_25bp",
          category: "credit" as const,
          label: "信用利差走阔 25bp",
          source_field: "cs01",
          shock: bp(25),
          estimated_impact: yuan(-450_000),
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
            source_version: "sv_mock_dashboard_v2",
            rule_version: "rv_risk_tensor_formal_materialize_v2",
            cache_version: "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v2",
            quality_flag: "warning",
          },
          summary: {
            scenario_count: scenarios.length,
            available_count: 3,
            review_required_count: scenarios.length,
            worst_estimated_impact: yuan(-3_000_000),
            worst_scenario_key: "rate_parallel_up_25bp",
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
