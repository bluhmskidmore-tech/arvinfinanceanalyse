/** Bond dashboard business summary/headline and cashflow forecast contracts. */
import type { ApiEnvelope, Numeric } from "./core";
import type { BondAnalyticsDatesPayload, BondPortfolioHeadlinesPayload, BondTopHoldingsPayload, DV01RiskPayload, YieldCurveTermStructurePayload } from "./bondAnalytics";

// --- 现金流预测 / 久期缺口 (`/api/cashflow-projection`) ---
export type CashflowMonthlyBucket = {
  year_month: string;
  asset_inflow: Numeric;
  liability_outflow: Numeric;
  net_cashflow: Numeric;
  cumulative_net: Numeric;
};

export type CashflowMaturingAsset = {
  instrument_code: string;
  instrument_name: string;
  maturity_date: string;
  face_value: Numeric;
  market_value: Numeric;
  currency_code: string;
};

export type CashflowProjectionPayload = {
  report_date: string;
  duration_gap: Numeric;
  asset_duration: Numeric;
  liability_duration: Numeric;
  equity_duration: Numeric;
  rate_sensitivity_1bp: Numeric;
  reinvestment_risk_12m: Numeric;
  monthly_buckets: CashflowMonthlyBucket[];
  top_maturing_assets_12m: CashflowMaturingAsset[];
  /**
   * 质量披露字段：后端 `CashflowProjectionResponse` 始终返回（缺省 0），此处标注为可选以兼容
   * 现存未提交改动的字面量（`riskHomeAdapter.test.ts` 的 `cashflowFixture`）；缺失时按 0 / 空处理。
   */
  floating_rate_proxy_count?: number;
  floating_rate_proxy_market_value?: Numeric;
  payment_frequency_fallback_count?: number;
  payment_frequency_fallback_market_value?: Numeric;
  bullet_value_date_fallback_count?: number;
  bullet_value_date_fallback_market_value?: Numeric;
  warnings: string[];
  computed_at: string;
};

export type CashflowForecastFormalOperatingIncome = {
  basis: "formal";
  amount: Numeric;
  source: string;
};

export type CashflowForecastManagementNetProfit = {
  basis: "analytical";
  amount: Numeric;
  assumption: string;
};

export type CashflowForecastMonthlyPressure = {
  year_month: string;
  maturity_principal: Numeric;
  liability_maturity: Numeric;
  net_pressure: Numeric;
};

export type CashflowProfitForecastPayload = {
  report_date: string;
  forecast_year_end: string;
  actual_ytd_operating_net_income: CashflowForecastFormalOperatingIncome;
  projected_remaining_operating_net_income: Record<string, Numeric>;
  projected_full_year_operating_net_income: Record<string, Numeric>;
  coupon_income_remaining: Numeric;
  ftp_cost_remaining: Numeric;
  net_coupon_income_remaining: Numeric;
  maturity_principal_by_month: Record<string, Numeric>;
  reinvestment_income_by_scenario: Record<string, Numeric>;
  reinvestment_ftp_cost_by_scenario: Record<string, Numeric>;
  net_reinvestment_income_by_scenario: Record<string, Numeric>;
  liability_rollover_cost_by_scenario: Record<string, Numeric>;
  net_cashflow_pressure_by_month: CashflowForecastMonthlyPressure[];
  management_net_profit_estimate_by_scenario: Record<string, CashflowForecastManagementNetProfit>;
  warnings: string[];
  source_versions: Record<string, string>;
  computed_at: string;
};

// --- 债券分析驾驶舱 (`/api/bond-dashboard`) ---
export type BondDashboardKpiItem = {
  label: string;
  value: string;
  unit: string;
  change_value: string | null;
  change_label: string | null;
};

export type BondDashboardHeadlinePayload = {
  report_date: string;
  prev_report_date: string | null;
  kpis: {
    total_market_value: Numeric;
    unrealized_pnl: Numeric;
    weighted_ytm: Numeric;
    weighted_duration: Numeric;
    weighted_coupon: Numeric;
    credit_spread_median: Numeric;
    total_dv01: Numeric;
    bond_count: number;
  };
  prev_kpis: {
    total_market_value: Numeric;
    unrealized_pnl: Numeric;
    weighted_ytm: Numeric;
    weighted_duration: Numeric;
    weighted_coupon: Numeric;
    credit_spread_median: Numeric;
    total_dv01: Numeric;
    bond_count: number;
  } | null;
};

export type AssetStructureItem = {
  category: string;
  total_market_value: Numeric;
  bond_count: number;
  percentage: Numeric | null;
};

export type AssetStructurePayload = {
  report_date: string;
  group_by: string;
  items: AssetStructureItem[];
  total_market_value: Numeric;
};

export type YieldDistributionItem = {
  yield_bucket: string;
  total_market_value: Numeric;
  bond_count: number;
};

export type YieldDistributionPayload = {
  report_date: string;
  items: YieldDistributionItem[];
  weighted_ytm: Numeric;
};

export type PortfolioComparisonItem = {
  portfolio_name: string;
  total_market_value: Numeric;
  weighted_ytm: Numeric;
  weighted_duration: Numeric;
  total_dv01: Numeric;
  bond_count: number;
};

export type PortfolioComparisonPayload = {
  report_date: string;
  items: PortfolioComparisonItem[];
};

export type SpreadAnalysisItem = {
  bond_type: string;
  median_yield: Numeric | null;
  bond_count: number;
  total_market_value: Numeric;
};

export type SpreadAnalysisPayload = {
  report_date: string;
  items: SpreadAnalysisItem[];
};

export type MaturityStructureItem = {
  maturity_bucket: string;
  total_market_value: Numeric;
  bond_count: number;
  percentage: Numeric | null;
};

export type MaturityStructurePayload = {
  report_date: string;
  items: MaturityStructureItem[];
  total_market_value: Numeric;
};

export type IndustryDistItem = {
  industry_name: string;
  total_market_value: Numeric;
  bond_count: number;
  percentage: Numeric | null;
};

export type IndustryDistPayload = {
  report_date: string;
  items: IndustryDistItem[];
};

export type RiskIndicatorsPayload = {
  report_date: string;
  total_market_value: Numeric;
  total_dv01: Numeric;
  weighted_duration: Numeric;
  credit_ratio: Numeric;
  weighted_convexity: Numeric;
  total_spread_dv01: Numeric;
  reinvestment_ratio_1y: Numeric;
};

export type BondDashboardHomeSummaryPayload = {
  report_date: string;
  headline: BondDashboardHeadlinePayload;
  risk: RiskIndicatorsPayload;
  asset_type: AssetStructurePayload;
  asset_rating: AssetStructurePayload;
  maturity: MaturityStructurePayload;
  industry: IndustryDistPayload;
  yield_distribution: YieldDistributionPayload;
  portfolio_comparison: PortfolioComparisonPayload;
  spread: SpreadAnalysisPayload;
  business_type: BondBusinessTypeMetricsResult;
};

export type BondDashboardBundleSectionId =
  | "dates"
  | "headline-kpis"
  | "home-summary"
  | "asset-structure"
  | "asset-structure-rating"
  | "asset-structure-portfolio-name"
  | "asset-structure-tenor-bucket"
  | "yield-distribution"
  | "portfolio-comparison"
  | "spread-analysis"
  | "maturity-structure"
  | "industry-distribution"
  | "risk-indicators"
  | "business-type-metrics"
  | "top-holdings"
  | "portfolio-headlines"
  | "dv01-risk"
  | "dv01-risk-ac"
  | "dv01-risk-oci"
  | "dv01-risk-tpl"
  | "dv01-risk-all"
  | "yield-curve-term-structure";

export type BondDashboardBundleSectionEnvelopeMap = {
  dates: ApiEnvelope<BondAnalyticsDatesPayload>;
  "headline-kpis": ApiEnvelope<BondDashboardHeadlinePayload>;
  "home-summary": ApiEnvelope<BondDashboardHomeSummaryPayload>;
  "asset-structure": ApiEnvelope<AssetStructurePayload>;
  "asset-structure-rating": ApiEnvelope<AssetStructurePayload>;
  "asset-structure-portfolio-name": ApiEnvelope<AssetStructurePayload>;
  "asset-structure-tenor-bucket": ApiEnvelope<AssetStructurePayload>;
  "yield-distribution": ApiEnvelope<YieldDistributionPayload>;
  "portfolio-comparison": ApiEnvelope<PortfolioComparisonPayload>;
  "spread-analysis": ApiEnvelope<SpreadAnalysisPayload>;
  "maturity-structure": ApiEnvelope<MaturityStructurePayload>;
  "industry-distribution": ApiEnvelope<IndustryDistPayload>;
  "risk-indicators": ApiEnvelope<RiskIndicatorsPayload>;
  "business-type-metrics": ApiEnvelope<BondBusinessTypeMetricsResult>;
  "top-holdings": ApiEnvelope<BondTopHoldingsPayload>;
  "portfolio-headlines": ApiEnvelope<BondPortfolioHeadlinesPayload>;
  "dv01-risk": ApiEnvelope<DV01RiskPayload>;
  "dv01-risk-ac": ApiEnvelope<DV01RiskPayload>;
  "dv01-risk-oci": ApiEnvelope<DV01RiskPayload>;
  "dv01-risk-tpl": ApiEnvelope<DV01RiskPayload>;
  "dv01-risk-all": ApiEnvelope<DV01RiskPayload>;
  "yield-curve-term-structure": ApiEnvelope<YieldCurveTermStructurePayload>;
};

export type BondDashboardBundleSectionStatus = {
  status: "ok" | "error";
  message: string | null;
  duration_ms: number;
};

export type BondDashboardBundlePayload = {
  report_date: string | null;
  requested_sections: BondDashboardBundleSectionId[];
  sections: Partial<BondDashboardBundleSectionEnvelopeMap>;
  section_statuses?: Partial<Record<BondDashboardBundleSectionId, BondDashboardBundleSectionStatus>>;
  failed_sections?: BondDashboardBundleSectionId[];
};

/** @deprecated 使用 AdbMonthlyItem — 保留别名供旧代码类型引用 */

/** @deprecated 使用 AdbMonthlyPayload */

// ── Dashboard core metrics ──────────────────────────────────────────────────

export type CoreMetricsCardData = {
  total_amount: Numeric;
  weighted_avg_rate: Numeric;
  change_amount: Numeric;
  change_pct: Numeric;
  top_3_details: Array<{ name: string; amount: string; rate: string }>;
};

export type CoreMetricsResult = {
  report_date: string;
  bond_investments: CoreMetricsCardData;
  interbank_assets: CoreMetricsCardData;
  interbank_liabilities: CoreMetricsCardData;
};

export type CoreMetricsPayload = ApiEnvelope<CoreMetricsResult>;

// ── Dashboard daily changes ─────────────────────────────────────────────────

export type DailyChangePeriod = {
  period: "day" | "week" | "month";
  bond_investments_change: Numeric;
  interbank_assets_change: Numeric;
  interbank_liabilities_change: Numeric;
  net_change: Numeric;
};

export type DailyChangesResult = {
  report_date: string;
  periods: DailyChangePeriod[];
};

export type DailyChangesPayload = ApiEnvelope<DailyChangesResult>;

// ── Bond dashboard business type metrics ────────────────────────────────────

export type BondBusinessTypeMetricItem = {
  name: string;
  market_value: string;
  weighted_avg_ytm_pct: string;
  weighted_avg_duration: string;
  duration_source: string;
};

export type BondBusinessTypeMetricsResult = {
  report_date: string;
  items: BondBusinessTypeMetricItem[];
};

export type BondBusinessTypeMetricsPayload = ApiEnvelope<BondBusinessTypeMetricsResult>;
