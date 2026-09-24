/** Risk overview widgets, risk tensor (`/api/risk/tensor`), and scenario stress payloads. */
import type { Numeric } from "./core";

export type RiskSignal = {
  id: string;
  label: string;
  value: Numeric;
  status: "stable" | "watch" | "warning";
  detail: string;
};

export type RiskOverviewPayload = {
  title: string;
  signals: RiskSignal[];
};

export type ContributionRow = {
  id: string;
  name: string;
  owner: string;
  contribution: Numeric;
  completion: number;
  status: string;
};

export type ContributionPayload = {
  title: string;
  rows: ContributionRow[];
};

export type AlertItem = {
  id: string;
  severity: "high" | "medium" | "low";
  title: string;
  occurred_at: string;
  detail: string;
};

export type AlertsPayload = {
  title: string;
  items: AlertItem[];
};

/**
 * `/api/risk/tensor?report_date=` — 数值字段为 governed `Numeric` JSON 或（mock/历史）纯字符串；展示层用 `bondNumericDisplay` 等归一化。
 * 「风险总览」与「风险张量」页面均通过 `getRiskTensor` 消费同一载荷；不在前端补算指标。
 */
/**
 * @legacy `string` 分支仅供历史/mock 数据兼容：`bondAnalyticsAdapter.bondNumericRaw`/`bondNumericDisplay`
 * 仍显式处理 `typeof value === "string"`。正式后端读surface（`/api/risk/tensor`）已统一返回 `Numeric`，
 * 新增消费方不应依赖该字符串分支。
 */
export type RiskTensorScalar = string | Numeric;

export type RiskTensorPayload = {
  report_date: string;
  portfolio_dv01: RiskTensorScalar;
  regulatory_dv01?: RiskTensorScalar | null;
  krd_1y: RiskTensorScalar;
  krd_3y: RiskTensorScalar;
  krd_5y: RiskTensorScalar;
  krd_7y: RiskTensorScalar;
  krd_10y: RiskTensorScalar;
  krd_30y: RiskTensorScalar;
  cs01: RiskTensorScalar;
  portfolio_convexity: RiskTensorScalar;
  portfolio_modified_duration: RiskTensorScalar;
  issuer_concentration_hhi: RiskTensorScalar;
  issuer_top5_weight: RiskTensorScalar;
  asset_cashflow_30d: RiskTensorScalar;
  asset_cashflow_90d: RiskTensorScalar;
  liability_cashflow_30d: RiskTensorScalar;
  liability_cashflow_90d: RiskTensorScalar;
  liquidity_gap_30d: RiskTensorScalar;
  liquidity_gap_90d: RiskTensorScalar;
  liquidity_gap_30d_ratio: RiskTensorScalar;
  total_market_value: RiskTensorScalar;
  rate_risk_market_value: RiskTensorScalar;
  rate_risk_dv01: RiskTensorScalar;
  rate_risk_modified_duration: RiskTensorScalar;
  duration_excluded_market_value: RiskTensorScalar;
  duration_excluded_count: number;
  missing_maturity_market_value?: RiskTensorScalar | null;
  missing_maturity_count?: number | null;
  floating_rate_proxy_market_value?: RiskTensorScalar | null;
  floating_rate_proxy_count?: number | null;
  payment_frequency_fallback_market_value?: RiskTensorScalar | null;
  payment_frequency_fallback_count?: number | null;
  bullet_value_date_fallback_market_value?: RiskTensorScalar | null;
  bullet_value_date_fallback_count?: number | null;
  projection_quality_status?: string | null;
  bond_count: number;
  quality_flag: string;
  warnings: string[];
};

export type BlockedReportDate = {
  report_date: string;
  reason: string;
};

export type RiskTensorDatesPayload = {
  report_dates: string[];
  blocked_report_dates?: BlockedReportDate[];
};

/**
 * `/api/risk/tensor/history?report_date=&periods=` — 走势图/涨跌胶囊只读窗口序列；
 * 数值为字符串（与张量载荷的历史字符串口径一致），展示层解析归一化，不在前端补算指标。
 */
export type RiskTensorHistoryPoint = {
  report_date: string;
  portfolio_dv01: string | null;
  regulatory_dv01?: string | null;
  portfolio_modified_duration: string | null;
  portfolio_convexity: string | null;
  cs01: string | null;
  issuer_concentration_hhi: string | null;
  issuer_top5_weight: string | null;
  liquidity_gap_30d: string | null;
};

export type RiskTensorHistoryPayload = {
  report_date: string;
  periods: number;
  window: { from: string; to: string };
  points: RiskTensorHistoryPoint[];
};

export type RiskScenarioStressCategory = "rate" | "credit" | "liquidity" | "fx";

export type RiskScenarioStressRow = {
  scenario_key: string;
  category: RiskScenarioStressCategory;
  label: string;
  source_field: string;
  shock: Numeric;
  estimated_impact: Numeric;
  measure: string;
  calculation: string;
  interpretation: string;
  data_status: "available" | "source_missing";
  human_review_required: boolean;
  baseline_value?: Numeric;
  stressed_value?: Numeric;
  baseline_ratio?: Numeric;
  stressed_ratio?: Numeric;
};

export type RiskScenarioStressSummary = {
  scenario_count: number;
  available_count: number;
  review_required_count: number;
  worst_estimated_impact: Numeric;
  worst_scenario_key: string | null;
  message: string;
};

export type RiskScenarioStressPayload = {
  report_date: string;
  basis: "scenario";
  scenario_set_id: string;
  rule_version: string;
  source: {
    result_kind?: string | null;
    trace_id?: string | null;
    source_version?: string | null;
    rule_version?: string | null;
    cache_version?: string | null;
    quality_flag?: string | null;
  };
  summary: RiskScenarioStressSummary;
  scenarios: RiskScenarioStressRow[];
  warnings: string[];
  source_warnings: string[];
};

export type PlaceholderSnapshot = {
  title: string;
  summary: string;
  highlights: string[];
};
