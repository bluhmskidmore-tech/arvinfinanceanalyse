/** Bond analytics: return decomposition, DV01/KRD risk, credit spread, yield curve, action attribution, and Campisi return attribution. */
import type { Numeric } from "./core";

export type BondAnalyticsRefreshPayload = {
  status: string;
  run_id: string;
  job_name?: string;
  cache_key?: string;
  report_date?: string;
  error_message?: string;
  [key: string]: unknown;
};

export type BondAnalyticsDatesPayload = {
  report_dates: string[];
};

export type AssetClassBreakdown = {
  asset_class: string;
  carry: Numeric;
  roll_down: Numeric;
  rate_effect: Numeric;
  spread_effect: Numeric;
  convexity_effect?: Numeric;
  trading: Numeric;
  total: Numeric;
  bond_count: number;
  market_value: Numeric;
};

export type BondLevelDecomposition = {
  bond_code: string;
  bond_name: string | null;
  asset_class: string;
  accounting_class: string;
  market_value: Numeric;
  carry: Numeric;
  roll_down: Numeric;
  rate_effect: Numeric;
  spread_effect: Numeric;
  convexity_effect: Numeric;
  trading: Numeric;
  total: Numeric;
  explained_for_recon: Numeric;
  economic_only_effects: Numeric;
};

export type ReturnDecompositionPayload = {
  report_date: string;
  period_type: string;
  period_start: string;
  period_end: string;
  carry: Numeric;
  roll_down: Numeric;
  rate_effect: Numeric;
  spread_effect: Numeric;
  trading: Numeric;
  fx_effect: Numeric;
  convexity_effect: Numeric;
  explained_pnl: Numeric;
  explained_pnl_accounting: Numeric;
  explained_pnl_economic: Numeric;
  oci_reserve_impact: Numeric;
  actual_pnl: Numeric;
  recon_error: Numeric;
  recon_error_pct: Numeric;
  by_asset_class: AssetClassBreakdown[];
  by_accounting_class: AssetClassBreakdown[];
  bond_details: BondLevelDecomposition[];
  bond_count: number;
  total_market_value: Numeric;
  warnings: string[];
  computed_at: string;
};

export type ExcessSourceBreakdown = {
  source: string;
  contribution: Numeric;
  description: string;
};

export type BenchmarkExcessPayload = {
  report_date: string;
  period_type: string;
  period_start: string;
  period_end: string;
  portfolio_return: Numeric;
  benchmark_return: Numeric;
  excess_return: Numeric;
  tracking_error: Numeric | null;
  information_ratio: Numeric | null;
  duration_effect: Numeric;
  curve_effect: Numeric;
  spread_effect: Numeric;
  selection_effect: Numeric;
  allocation_effect: Numeric;
  explained_excess: Numeric;
  recon_error: Numeric;
  portfolio_duration: Numeric;
  benchmark_duration: Numeric;
  duration_diff: Numeric;
  excess_sources: ExcessSourceBreakdown[];
  benchmark_id: string;
  benchmark_name: string;
  warnings: string[];
  computed_at: string;
};

export type KRDBucket = {
  tenor: string;
  /** MV-weighted average modified duration in the tenor bucket (not true KRD). */
  avg_modified_duration: Numeric;
  dv01: Numeric;
  market_value_weight: Numeric;
  /** @deprecated Alias of avg_modified_duration; remove after consumers migrate. */
  krd?: Numeric;
};

export type KRDScenarioResult = {
  scenario_name: string;
  scenario_description: string;
  shocks: Record<string, number>;
  pnl_economic: Numeric;
  pnl_oci: Numeric;
  pnl_tpl: Numeric;
  rate_contribution: Numeric;
  convexity_contribution: Numeric;
  by_asset_class: Record<string, Record<string, Numeric>>;
};

export type AssetClassRiskSummary = {
  asset_class: string;
  market_value: Numeric;
  duration: Numeric;
  dv01: Numeric;
  weight: Numeric;
};

export type KRDCurveRiskPayload = {
  report_date: string;
  portfolio_duration: Numeric;
  portfolio_modified_duration: Numeric;
  portfolio_dv01: Numeric;
  portfolio_convexity: Numeric;
  krd_buckets: KRDBucket[];
  scenarios: KRDScenarioResult[];
  by_asset_class: AssetClassRiskSummary[];
  warnings: string[];
  computed_at: string;
};

/** `/api/bond-analytics/portfolio-headlines` */
export type BondPortfolioHeadlinesPayload = {
  report_date: string;
  total_market_value: Numeric;
  weighted_ytm: Numeric;
  weighted_duration: Numeric;
  weighted_coupon: Numeric;
  total_dv01: Numeric;
  bond_count: number;
  credit_weight: Numeric;
  issuer_hhi: Numeric;
  issuer_top5_weight: Numeric;
  by_asset_class: AssetClassRiskSummary[];
  warnings: string[];
  warning_codes?: string[];
  computed_at: string;
};

export type BondTopHoldingItem = {
  instrument_code: string;
  instrument_name: string | null;
  issuer_name: string | null;
  rating: string | null;
  asset_class: string;
  market_value: Numeric;
  face_value: Numeric;
  ytm: Numeric;
  modified_duration: Numeric;
  weight: Numeric;
};

/** `/api/bond-analytics/top-holdings` */
export type BondTopHoldingsPayload = {
  report_date: string;
  top_n: number;
  items: BondTopHoldingItem[];
  total_market_value: Numeric;
  warnings: string[];
  computed_at: string;
};

export type BondPositionChangeItem = {
  instrument_code: string;
  instrument_name: string | null;
  issuer_name: string | null;
  rating: string | null;
  asset_class: string;
  previous_market_value: Numeric;
  current_market_value: Numeric;
  change_market_value: Numeric;
  previous_weight: Numeric;
  current_weight: Numeric;
  change_weight: Numeric;
  direction: "increase" | "decrease" | "flat";
  reason_label: string;
  source_status: "ready" | "empty" | "stale";
};

export type BondPositionChangesPayload = {
  report_date: string;
  prev_report_date: string | null;
  top_n: number;
  source_status: "ready" | "empty" | "stale";
  items: BondPositionChangeItem[];
  total_market_value: Numeric;
  prev_total_market_value: Numeric;
  warnings: string[];
  computed_at: string;
};

export type DV01ShockScenario = {
  scenario_name: string;
  shock_bp: Numeric;
  estimated_pnl: Numeric;
};

export type DV01TenorBucket = {
  tenor_bucket: string;
  face_value: Numeric;
  market_value: Numeric;
  face_weighted_modified_duration: Numeric;
  dv01: Numeric;
  dv01_share: Numeric;
  position_count: number;
};

export type DV01TopBondItem = {
  instrument_code: string;
  instrument_name: string | null;
  issuer_name: string | null;
  rating: string | null;
  tenor_bucket: string;
  accounting_class: string;
  face_value: Numeric;
  market_value: Numeric;
  modified_duration: Numeric;
  dv01: Numeric;
  dv01_share: Numeric;
};

export type DV01TopIssuerItem = {
  issuer_name: string;
  face_value: Numeric;
  market_value: Numeric;
  face_weighted_modified_duration: Numeric;
  dv01: Numeric;
  dv01_share: Numeric;
  position_count: number;
};

export type DV01RiskPayload = {
  report_date: string;
  accounting_class: string;
  dv01_basis: "face_value_modified_duration";
  scenario_pnl_basis: "face_value_dv01_linear";
  total_face_value: Numeric;
  total_market_value: Numeric;
  face_weighted_modified_duration: Numeric;
  total_dv01: Numeric;
  position_count: number;
  shock_scenarios: DV01ShockScenario[];
  tenor_buckets: DV01TenorBucket[];
  top_bonds: DV01TopBondItem[];
  top_issuers: DV01TopIssuerItem[];
  warnings: string[];
  computed_at: string;
};

export type DV01ReconciliationRow = {
  report_date: string;
  instrument_code: string;
  instrument_name: string | null;
  accounting_class: string;
  issuer_name: string | null;
  rating: string | null;
  tenor_bucket: string;
  face_value: Numeric;
  market_value: Numeric;
  modified_duration: Numeric;
  dv01: Numeric;
  dv01_share: Numeric;
  source_version: string;
  rule_version: string;
  trace_id: string;
};

export type DV01ReconciliationPayload = {
  report_date: string;
  accounting_class: string;
  total_face_value: Numeric;
  total_market_value: Numeric;
  face_weighted_modified_duration: Numeric;
  total_dv01: Numeric;
  position_count: number;
  rows: DV01ReconciliationRow[];
  warnings: string[];
  computed_at: string;
};

export type DV01MovementAttributionItem = {
  driver_key: string;
  driver_label: string;
  dv01_delta: Numeric;
  dv01_delta_share: Numeric;
  position_count: number;
};

export type DV01MovementBondItem = {
  instrument_code: string;
  instrument_name: string | null;
  issuer_name: string | null;
  rating: string | null;
  tenor_bucket: string;
  previous_accounting_class: string | null;
  current_accounting_class: string | null;
  previous_face_value: Numeric;
  current_face_value: Numeric;
  previous_modified_duration: Numeric;
  current_modified_duration: Numeric;
  previous_dv01: Numeric;
  current_dv01: Numeric;
  dv01_delta: Numeric;
  estimated_dv01_from_face_duration: Numeric;
  dv01_estimate_gap: Numeric;
  reason_label: string;
};

export type DV01MovementPayload = {
  report_date: string;
  previous_report_date: string | null;
  accounting_class: string;
  source_status: "ready" | "empty";
  current_total_face_value: Numeric;
  previous_total_face_value: Numeric;
  current_total_market_value: Numeric;
  previous_total_market_value: Numeric;
  current_face_weighted_modified_duration: Numeric;
  previous_face_weighted_modified_duration: Numeric;
  current_total_dv01: Numeric;
  previous_total_dv01: Numeric;
  delta_dv01: Numeric;
  current_position_count: number;
  previous_position_count: number;
  attribution: DV01MovementAttributionItem[];
  anomaly_bonds: DV01MovementBondItem[];
  methodology_checks: DV01MovementBondItem[];
  warnings: string[];
  computed_at: string;
};

export type DV01ActionScenarioBreach = {
  scenario_name: string;
  shock_bp: Numeric;
  estimated_loss: Numeric;
  loss_threshold: Numeric;
  risk_level: string;
};

export type DV01ActionTenorItem = {
  tenor_bucket: string;
  dv01: Numeric;
  dv01_share: Numeric;
  suggested_reduction_dv01: Numeric;
  position_count: number;
};

export type DV01ActionIssuerItem = {
  issuer_name: string;
  dv01: Numeric;
  dv01_share: Numeric;
  suggested_reduction_dv01: Numeric;
  position_count: number;
};

export type DV01ActionBondItem = {
  instrument_code: string;
  instrument_name: string | null;
  issuer_name: string | null;
  rating: string | null;
  tenor_bucket: string;
  accounting_class: string;
  face_value: Numeric;
  market_value: Numeric;
  modified_duration: Numeric;
  dv01: Numeric;
  dv01_share: Numeric;
  suggested_reduction_dv01: Numeric;
};

export type DV01ActionPlanPayload = {
  report_date: string;
  accounting_class: string;
  risk_level: "ok" | "watch" | "breach" | "no_data";
  policy_basis: string;
  threshold_note: string;
  limit_source: string;
  limit_source_version: string;
  limit_rule_version: string;
  limit_effective_date: string | null;
  total_dv01: Numeric;
  limit_dv01: Numeric;
  warning_dv01: Numeric;
  limit_usage: Numeric;
  remaining_limit_dv01: Numeric;
  dv01_to_reduce: Numeric;
  hedge_instrument_label: string;
  hedge_instrument_dv01: Numeric;
  suggested_hedge_units: Numeric;
  position_count: number;
  breach_count: number;
  scenario_breaches: DV01ActionScenarioBreach[];
  tenor_actions: DV01ActionTenorItem[];
  issuer_actions: DV01ActionIssuerItem[];
  bond_actions: DV01ActionBondItem[];
  warnings: string[];
  computed_at: string;
};

export type DV01LimitConfigStatusRow = {
  accounting_class: string;
  status: "ready" | "missing" | "invalid";
  limit_dv01: Numeric;
  warning_dv01: Numeric;
  hedge_target_dv01: Numeric;
  limit_source: string;
  limit_source_version: string;
  limit_rule_version: string;
  limit_effective_date: string | null;
  message: string;
};

export type DV01LimitConfigStatusPayload = {
  report_date: string;
  overall_status: "ready" | "incomplete";
  acceptance_status: "ready" | "blocked";
  acceptance_message: string;
  next_action: string;
  config_stream: string;
  required_accounting_classes: string[];
  required_fields: string[];
  configured_accounting_classes: string[];
  missing_accounting_classes: string[];
  invalid_accounting_classes: string[];
  missing_business_fields_by_class: Record<string, string[]>;
  review_package_command: string;
  dry_run_command: string;
  configured_count: number;
  missing_count: number;
  invalid_count: number;
  rows: DV01LimitConfigStatusRow[];
  computed_at: string;
  warnings: string[];
};

export type SpreadScenarioResult = {
  scenario_name: string;
  spread_change_bp: Numeric;
  pnl_impact: Numeric;
  oci_impact: Numeric;
  tpl_impact: Numeric;
};

export type MigrationScenarioResult = {
  scenario_name: string;
  from_rating: string;
  to_rating: string;
  affected_bonds: number;
  affected_market_value: Numeric;
  pnl_impact: Numeric;
  oci_impact?: Numeric;
};

export type ConcentrationItem = {
  name: string;
  weight: Numeric;
  market_value: Numeric;
};

export type ConcentrationMetrics = {
  dimension: string;
  hhi: Numeric;
  top5_concentration: Numeric;
  top_items: ConcentrationItem[];
};

export type CreditSpreadBondDetailRow = {
  market_value: Numeric;
  rating?: string;
  tenor_bucket?: string;
};

export type CreditSpreadMigrationPayload = {
  report_date: string;
  credit_bond_count: number;
  credit_market_value: Numeric;
  credit_weight: Numeric;
  rating_aa_and_below_weight?: Numeric;
  spread_dv01: Numeric;
  weighted_avg_spread: Numeric;
  weighted_avg_spread_duration: Numeric;
  spread_scenarios: SpreadScenarioResult[];
  migration_scenarios: MigrationScenarioResult[];
  concentration_by_issuer?: ConcentrationMetrics;
  concentration_by_industry?: ConcentrationMetrics;
  concentration_by_rating?: ConcentrationMetrics;
  concentration_by_tenor?: ConcentrationMetrics;
  bond_details?: CreditSpreadBondDetailRow[];
  oci_credit_exposure: Numeric;
  oci_spread_dv01: Numeric;
  oci_sensitivity_25bp: Numeric;
  warnings: string[];
  warning_codes?: string[];
  computed_at: string;
};

export type CreditSpreadTermStructurePoint = {
  tenor_bucket: string;
  avg_spread_bps: string;
  min_spread_bps: string;
  max_spread_bps: string;
  bond_count: number;
  total_market_value: string;
};

export type CreditSpreadDetailBondRow = {
  instrument_code: string;
  instrument_name: string;
  rating: string;
  tenor_bucket: string;
  ytm: string;
  benchmark_yield: string;
  credit_spread: string;
  spread_duration: string;
  spread_dv01: string;
  market_value: string;
  weight: string;
};

export type SpreadHistoricalContextPayload = {
  current_spread_bps: string;
  percentile_1y: string | null;
  percentile_3y: string | null;
  median_1y: string | null;
  median_3y: string | null;
  min_1y: string | null;
  max_1y: string | null;
};

export type CreditSpreadAnalysisPayload = {
  report_date: string;
  credit_bond_count: number;
  total_credit_market_value: string;
  weighted_avg_spread_bps: string;
  spread_term_structure: CreditSpreadTermStructurePoint[];
  top_spread_bonds: CreditSpreadDetailBondRow[];
  bottom_spread_bonds: CreditSpreadDetailBondRow[];
  historical_context: SpreadHistoricalContextPayload | null;
  warnings: string[];
  computed_at: string;
};

export type YieldCurveTermPointPayload = {
  tenor: string;
  yield_pct: Numeric | null;
  delta_bp_prev: Numeric | null;
};

export type YieldCurveTermStructureCurvePayload = {
  curve_type: string;
  trade_date_requested: string;
  trade_date_resolved: string | null;
  points: YieldCurveTermPointPayload[];
  source_version: string;
  rule_version: string;
  vendor_name: string;
  vendor_version: string;
};

export type YieldCurveTermStructurePayload = {
  report_date: string;
  curves: YieldCurveTermStructureCurvePayload[];
  warnings: string[];
  computed_at: string;
};

export type ActionTypeSummary = {
  action_type: string;
  action_type_name: string;
  action_count: number;
  total_pnl_economic: Numeric;
  total_pnl_accounting: Numeric;
  avg_pnl_per_action: Numeric;
};

export type ActionDetail = {
  action_id: string;
  action_type: string;
  action_date: string;
  bonds_involved: string[];
  description: string;
  pnl_economic: Numeric;
  pnl_accounting: Numeric;
  delta_duration: Numeric;
  delta_dv01: Numeric;
  delta_spread_dv01: Numeric;
  opportunity_cost?: Numeric;
  opportunity_cost_method?: string;
};

export type ActionAttributionPayload = {
  report_date: string;
  period_type: string;
  period_start: string;
  period_end: string;
  total_actions: number;
  total_pnl_from_actions: Numeric;
  by_action_type: ActionTypeSummary[];
  action_details: ActionDetail[];
  period_start_duration: Numeric;
  period_end_duration: Numeric;
  duration_change_from_actions: Numeric;
  period_start_dv01: Numeric;
  period_end_dv01: Numeric;
  status?: string;
  available_components?: string[];
  missing_inputs?: string[];
  blocked_components?: string[];
  warnings: string[];
  warning_codes?: string[];
  computed_at: string;
};

export type AccountingClassAuditItem = {
  asset_class: string;
  position_count: number;
  market_value: Numeric;
  market_value_weight: Numeric;
  infer_accounting_class: string;
  map_accounting_class: string;
  infer_rule_id: string;
  infer_match: string | null;
  map_rule_id: string;
  map_match: string | null;
  is_divergent: boolean;
  is_map_unclassified: boolean;
};

export type AccountingClassAuditPayload = {
  report_date: string;
  total_positions: number;
  total_market_value: Numeric;
  distinct_asset_classes: number;
  divergent_asset_classes: number;
  divergent_position_count: number;
  divergent_market_value: Numeric;
  map_unclassified_asset_classes: number;
  map_unclassified_position_count: number;
  map_unclassified_market_value: Numeric;
  rows: AccountingClassAuditItem[];
  warnings: string[];
  computed_at: string;
};

// --- PnL attribution workbench (`/api/pnl-attribution/*`, V1-aligned numeric payloads) ---

export type VolumeRateAttributionItem = {
  category: string;
  category_type: string;
  level: number;
  current_scale: Numeric;
  current_pnl: Numeric;
  current_yield_pct: Numeric | null;
  previous_scale: Numeric | null;
  previous_pnl: Numeric | null;
  previous_yield_pct: Numeric | null;
  pnl_change: Numeric | null;
  pnl_change_pct: Numeric | null;
  volume_effect: Numeric | null;
  rate_effect: Numeric | null;
  interaction_effect: Numeric | null;
  attrib_sum: Numeric | null;
  recon_error: Numeric | null;
  volume_contribution_pct: Numeric | null;
  rate_contribution_pct: Numeric | null;
};

export type VolumeRateAttributionPayload = {
  current_period: string;
  previous_period: string;
  compare_type: string;
  total_current_pnl: Numeric;
  total_previous_pnl: Numeric | null;
  total_pnl_change: Numeric | null;
  total_volume_effect: Numeric | null;
  total_rate_effect: Numeric | null;
  total_interaction_effect: Numeric | null;
  total_recon_error: Numeric | null;
  items: VolumeRateAttributionItem[];
  has_previous_data: boolean;
};

export type TPLMarketDataPoint = {
  period: string;
  period_label: string;
  tpl_fair_value_change: Numeric;
  tpl_total_pnl: Numeric;
  tpl_scale: Numeric;
  treasury_10y: Numeric | null;
  treasury_10y_change: Numeric | null;
  dr007: Numeric | null;
};

export type TPLMarketCorrelationPayload = {
  start_period: string;
  end_period: string;
  num_periods: number;
  correlation_coefficient: Numeric | null;
  correlation_interpretation: string;
  total_tpl_fv_change: Numeric;
  avg_treasury_10y_change: Numeric | null;
  treasury_10y_total_change_bp: Numeric | null;
  data_points: TPLMarketDataPoint[];
  analysis_summary: string;
};

export type PnlCompositionItem = {
  category: string;
  category_type: string;
  level: number;
  total_pnl: Numeric;
  interest_income: Numeric;
  fair_value_change: Numeric;
  capital_gain: Numeric;
  other_income: Numeric;
  interest_pct: Numeric;
  fair_value_pct: Numeric;
  capital_gain_pct: Numeric;
  other_pct: Numeric;
  unexplained_residual: Numeric | null;
};

export type PnlCompositionTrendItem = {
  period: string;
  period_label: string;
  interest_income: Numeric;
  fair_value_change: Numeric;
  capital_gain: Numeric;
  other_income: Numeric;
  total_pnl: Numeric;
};

export type PnlCompositionPayload = {
  report_period: string;
  report_date: string;
  total_pnl: Numeric;
  total_interest_income: Numeric;
  total_fair_value_change: Numeric;
  total_capital_gain: Numeric;
  total_other_income: Numeric;
  interest_pct: Numeric;
  fair_value_pct: Numeric;
  capital_gain_pct: Numeric;
  other_pct: Numeric;
  unexplained_residual: Numeric | null;
  items: PnlCompositionItem[];
  trend_data: PnlCompositionTrendItem[];
};

export type PnlAttributionAnalysisSummary = {
  report_date: string;
  primary_driver: "volume" | "rate" | "market" | "unknown";
  primary_driver_pct: Numeric;
  key_findings: string[];
  tpl_market_aligned: boolean;
  tpl_market_note: string;
};

export type CarryRollDownItem = {
  category: string;
  category_type: string;
  market_value: Numeric;
  weight: Numeric;
  coupon_rate: Numeric;
  ytm: Numeric | null;
  funding_cost: Numeric;
  carry: Numeric;
  carry_pnl: Numeric;
  duration: Numeric;
  curve_slope: Numeric | null;
  rolldown: Numeric;
  rolldown_pnl: Numeric;
  static_return: Numeric;
  static_pnl: Numeric;
};

export type CarryRollDownPayload = {
  report_date: string;
  total_market_value: Numeric;
  portfolio_carry: Numeric;
  portfolio_rolldown: Numeric;
  portfolio_static_return: Numeric;
  total_carry_pnl: Numeric;
  total_rolldown_pnl: Numeric;
  total_static_pnl: Numeric;
  ftp_rate: Numeric;
  items: CarryRollDownItem[];
};

export type AttributionRiskCoverageExclusionReason =
  | "no_maturity"
  | "missing_maturity"
  | "matured_or_expired"
  | "nonpositive_duration";

export type AttributionRiskCoverageExclusion = {
  reason: AttributionRiskCoverageExclusionReason;
  row_count: number;
  market_value: Numeric;
};

/** 归因口径覆盖率披露：分母/剔除行说明，见 `AttributionRiskCoverage`（后端 pnl_attribution schema）。 */
export type AttributionRiskCoverage = {
  total_row_count: number;
  covered_row_count: number;
  excluded_row_count: number;
  total_market_value: Numeric;
  covered_market_value: Numeric;
  excluded_market_value: Numeric;
  coverage_pct: Numeric;
  excluded_pct: Numeric;
  exclusions: AttributionRiskCoverageExclusion[];
};

export type SpreadAttributionItem = {
  category: string;
  category_type: string;
  market_value: Numeric;
  duration: Numeric;
  weight: Numeric;
  yield_change: Numeric | null;
  treasury_change: Numeric | null;
  spread_change: Numeric | null;
  treasury_effect: Numeric;
  spread_effect: Numeric;
  total_price_effect: Numeric;
  treasury_contribution_pct: Numeric;
  spread_contribution_pct: Numeric;
};

export type SpreadAttributionPayload = {
  report_date: string;
  start_date: string;
  end_date: string;
  treasury_10y_start: Numeric | null;
  treasury_10y_end: Numeric | null;
  treasury_10y_change: Numeric | null;
  total_market_value: Numeric;
  risk_coverage: AttributionRiskCoverage;
  portfolio_duration: Numeric;
  total_treasury_effect: Numeric;
  total_spread_effect: Numeric;
  total_price_change: Numeric;
  primary_driver: string;
  interpretation: string;
  items: SpreadAttributionItem[];
};

export type KRDAttributionBucket = {
  tenor: string;
  tenor_years: Numeric;
  market_value: Numeric;
  weight: Numeric;
  bond_count: number;
  bucket_duration: Numeric;
  /** Same semantics as bucket_duration / avg_modified_duration. */
  avg_modified_duration?: Numeric;
  /** @deprecated Alias of avg_modified_duration. */
  krd: Numeric;
  yield_change: Numeric | null;
  duration_contribution: Numeric;
  contribution_pct: Numeric;
};

export type KRDAttributionPayload = {
  report_date: string;
  start_date: string;
  end_date: string;
  total_market_value: Numeric;
  risk_coverage: AttributionRiskCoverage;
  portfolio_duration: Numeric;
  portfolio_dv01: Numeric;
  total_duration_effect: Numeric;
  curve_shift_type: string;
  curve_interpretation: string;
  buckets: KRDAttributionBucket[];
  max_contribution_tenor: string;
  max_contribution_value: Numeric;
};

export type AdvancedAttributionSummary = {
  report_date: string;
  portfolio_carry: Numeric;
  portfolio_rolldown: Numeric;
  static_return_annualized: Numeric;
  treasury_effect_total: Numeric;
  spread_effect_total: Numeric;
  spread_driver: string;
  max_krd_tenor: string;
  curve_shape_change: string;
  key_insights: string[];
};

export type CampisiAttributionItem = {
  category: string;
  market_value: Numeric;
  weight: Numeric;
  total_return: Numeric;
  total_return_pct: Numeric;
  income_return: Numeric;
  income_return_pct: Numeric;
  treasury_effect: Numeric;
  treasury_effect_pct: Numeric;
  spread_effect: Numeric;
  spread_effect_pct: Numeric;
  selection_effect: Numeric;
  selection_effect_pct: Numeric;
};

export type CampisiAttributionPayload = {
  report_date: string;
  period_start: string;
  period_end: string;
  num_days: number;
  total_market_value: Numeric;
  total_return: Numeric;
  total_return_pct: Numeric;
  total_income: Numeric;
  total_treasury_effect: Numeric;
  total_spread_effect: Numeric;
  total_selection_effect: Numeric;
  income_contribution_pct: Numeric;
  treasury_contribution_pct: Numeric;
  spread_contribution_pct: Numeric;
  selection_contribution_pct: Numeric;
  primary_driver: string;
  interpretation: string;
  items: CampisiAttributionItem[];
};

export type CampisiDecisionWindowDeclaration = {
  start: string;
  end: string;
  kind: string;
};

export type CampisiBridgeDetailFields = {
  realized_trading?: number;
  manual_adjustment?: number;
  fx_translation?: number;
};

export type CampisiFourEffectsTotals = CampisiBridgeDetailFields & {
  income_return: number;
  treasury_effect: number;
  spread_effect: number;
  selection_effect: number;
  total_return: number;
  market_value_start: number;
};

export type CampisiEnhancedTotals = CampisiFourEffectsTotals & {
  convexity_effect: number;
  cross_effect: number;
  reinvestment_effect: number;
};

export type CampisiFormalClosure = {
  basis: "pnl.bridge.total_actual_pnl";
  report_date: string;
  status: "closed" | "warning" | "unavailable";
  campisi_total_return: number | null;
  formal_actual_pnl: number | null;
  residual_to_formal_pnl: number | null;
  residual_ratio: number | null;
  bridge_quality_flag?: string | null;
  bridge_vendor_status?: string | null;
  bridge_fallback_mode?: string | null;
  message: string;
};

export type CampisiDecisionEffectKey =
  | "carry"
  | "rate_level_effect"
  | "curve_shape_effect"
  | "credit_spread_effect"
  | "convexity_effect"
  | "realized_trading"
  | "manual_adjustment"
  | "selection_proxy"
  | "residual_noise";

export type CampisiDecisionComponents = Record<CampisiDecisionEffectKey, number>;

export type CampisiDecisionGradeSummary = {
  formal_actual_pnl: number;
  explained_pnl: number;
  residual_noise: number;
  residual_ratio: number | null;
  valuation_change_516: number;
  fvoci_valuation_change_516: number;
  fvtpl_valuation_change_516: number;
  main_driver: string;
  quality_flag: string;
  bond_scope_row_count: number;
  out_of_scope_pnl_row_count: number;
};

export type CampisiDecisionEffect = {
  key: CampisiDecisionEffectKey;
  label: string;
  amount: number;
  ability_treatment: string;
};

export type CampisiDecisionAccountingRow = {
  accounting_basis: string;
  formal_pnl: number;
  valuation_or_oci_516: number;
  interpretation: string;
};

export type CampisiDecisionAbilityRow = {
  portfolio_name: string;
  cost_center: string;
  carry: number;
  market_beta: number;
  strategy_proxy: number;
  credit_proxy: number;
  selection_proxy: number;
  residual_noise: number;
  total_actual_pnl: number;
  confidence: "low" | "medium" | "high" | string;
  notes: string;
};

export type CampisiDecisionGradePayload = {
  basis: "campisi_decision_grade_v1";
  report_date: string;
  period_start: string;
  period_end: string;
  num_days: number;
  pnl_window?: CampisiDecisionWindowDeclaration;
  curve_window?: CampisiDecisionWindowDeclaration;
  summary: CampisiDecisionGradeSummary;
  formal_pnl_view: {
    total_actual_pnl: number;
    explained_pnl: number;
    residual_noise: number;
    components: CampisiDecisionComponents;
    closure: {
      status: "closed" | "warning" | "error";
      difference: number;
      difference_ratio?: number | null;
      basis: string;
    };
  };
  valuation_oci_view: {
    total_valuation_change_516: number;
    fvoci_valuation_change_516: number;
    fvtpl_valuation_change_516: number;
    rows_by_accounting_basis: CampisiDecisionAccountingRow[];
    reinvestment: {
      implemented: boolean;
      message: string;
    };
  };
  effects: CampisiDecisionEffect[];
  accounting_matrix: Record<string, CampisiDecisionAccountingRow>;
  ability_matrix: CampisiDecisionAbilityRow[];
  risk_tensor_check: Record<string, unknown>;
  residual_diagnostics: {
    missing_curve_count: number;
    missing_spread_count: number;
    duplicate_position_keys: number;
    aggregated_position_groups?: number;
    unmatched_pnl_rows: number;
    stale_curve_fallback_count: number;
    warnings: string[];
  };
  warnings: string[];
  method_notes: string[];
};

export type CampisiFourEffectsRow = CampisiBridgeDetailFields & {
  asset_class: string;
  market_value_start: number;
  income_return: number;
  treasury_effect: number;
  spread_effect: number;
  selection_effect: number;
  total_return: number;
  weight_pct?: number;
};

export type CampisiFourEffectsBondRow = CampisiFourEffectsRow & {
  bond_code: string;
  maturity_bucket: string;
  mod_duration: number;
};

export type CampisiEnhancedRow = CampisiBridgeDetailFields & {
  asset_class: string;
  market_value_start: number;
  income_return: number;
  treasury_effect: number;
  spread_effect: number;
  convexity_effect: number;
  cross_effect: number;
  reinvestment_effect: number;
  selection_effect: number;
  total_return: number;
  weight_pct?: number;
};

export type CampisiEnhancedBondRow = CampisiEnhancedRow & {
  bond_code: string;
  maturity_bucket: string;
  mod_duration: number;
};

export type CampisiFourEffectsPayload = {
  report_date: string;
  period_start: string;
  period_end: string;
  num_days: number;
  totals: CampisiFourEffectsTotals;
  by_asset_class: CampisiFourEffectsRow[];
  by_bond: CampisiFourEffectsBondRow[];
  formal_closure?: CampisiFormalClosure;
  basis?: string;
  decomposition_basis?: string;
  warnings?: string[];
};

export type CampisiEnhancedPayload = {
  report_date: string;
  period_start: string;
  period_end: string;
  num_days: number;
  totals: CampisiEnhancedTotals;
  by_asset_class: CampisiEnhancedRow[];
  by_bond: CampisiEnhancedBondRow[];
  basis?: string;
  decomposition_basis?: string;
};

export type CampisiMaturityBucketBreakdown = {
  market_value_start: number;
  income_return: number;
  treasury_effect: number;
  spread_effect: number;
  selection_effect: number;
  total_return: number;
};

export type CampisiMaturityBucketsPayload = {
  period_start: string;
  period_end: string;
  buckets: Record<string, CampisiMaturityBucketBreakdown>;
};
