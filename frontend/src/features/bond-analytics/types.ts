export type PeriodType = "MoM" | "YTD" | "TTM";

export interface AssetClassBreakdown {
  asset_class: string;
  carry: string;
  roll_down: string;
  rate_effect: string;
  spread_effect: string;
  fx_effect?: string;
  convexity_effect?: string;
  trading: string;
  total: string;
  bond_count: number;
  market_value: string;
}

export interface BondLevelDecomposition {
  bond_code: string;
  bond_name: string;
  asset_class: string;
  accounting_class: string;
  market_value: string;
  carry: string;
  roll_down: string;
  rate_effect: string;
  spread_effect: string;
  trading: string;
  total: string;
  explained_for_recon: string;
  economic_only_effects: string;
}

export interface ReturnDecompositionResponse {
  report_date: string;
  period_type: string;
  period_start: string;
  period_end: string;
  carry: string;
  roll_down: string;
  rate_effect: string;
  spread_effect: string;
  trading: string;
  fx_effect: string;
  convexity_effect: string;
  explained_pnl: string;
  explained_pnl_accounting: string;
  explained_pnl_economic: string;
  oci_reserve_impact: string;
  actual_pnl: string;
  recon_error: string;
  recon_error_pct: string;
  by_asset_class: AssetClassBreakdown[];
  by_accounting_class: AssetClassBreakdown[];
  bond_details: BondLevelDecomposition[];
  bond_count: number;
  total_market_value: string;
  warnings: string[];
  computed_at: string;
}

// ExcessSourceBreakdown
export interface ExcessSourceBreakdown {
  source: string;
  contribution: string;
  description: string;
}

export interface BenchmarkExcessResponse {
  report_date: string;
  period_type: string;
  period_start: string;
  period_end: string;
  portfolio_return: string;
  benchmark_return: string;
  excess_return: string;
  tracking_error?: string;
  information_ratio?: string;
  duration_effect: string;
  curve_effect: string;
  spread_effect: string;
  selection_effect: string;
  allocation_effect: string;
  explained_excess: string;
  recon_error: string;
  portfolio_duration: string;
  benchmark_duration: string;
  duration_diff: string;
  excess_sources: ExcessSourceBreakdown[];
  benchmark_id: string;
  benchmark_name: string;
  warnings: string[];
  computed_at: string;
}

// KRD types
export interface KRDBucket {
  tenor: string;
  krd: string;
  dv01: string;
  market_value_weight: string;
}

export interface ScenarioResult {
  scenario_name: string;
  scenario_description: string;
  shocks: Record<string, number>;
  pnl_economic: string;
  pnl_oci: string;
  pnl_tpl: string;
  rate_contribution: string;
  convexity_contribution: string;
  by_asset_class: Record<string, Record<string, string>>;
}

export interface AssetClassRiskSummary {
  asset_class: string;
  market_value: string;
  duration: string;
  dv01: string;
  weight: string;
}

export interface KRDCurveRiskResponse {
  report_date: string;
  portfolio_duration: string;
  portfolio_modified_duration: string;
  portfolio_dv01: string;
  portfolio_convexity: string;
  krd_buckets: KRDBucket[];
  scenarios: ScenarioResult[];
  by_asset_class: AssetClassRiskSummary[];
  warnings: string[];
  computed_at: string;
}

// Credit spread types
export interface SpreadScenarioResult {
  scenario_name: string;
  spread_change_bp: number;
  pnl_impact: string;
  oci_impact: string;
  tpl_impact: string;
}

export interface MigrationScenarioResult {
  scenario_name: string;
  from_rating: string;
  to_rating: string;
  affected_bonds: number;
  affected_market_value: string;
  pnl_impact: string;
  oci_impact?: string;
}

export interface ConcentrationItem {
  name: string;
  weight: string;
  market_value: string;
}

export interface ConcentrationMetrics {
  dimension: string;
  hhi: string;
  top5_concentration: string;
  top_items: ConcentrationItem[];
}

/** Optional per-bond rows for rating×tenor heatmap; server may omit. */
export interface CreditSpreadBondDetailRow {
  market_value: string;
  rating?: string;
  tenor_bucket?: string;
}

export interface CreditSpreadMigrationResponse {
  report_date: string;
  credit_bond_count: number;
  credit_market_value: string;
  credit_weight: string;
  spread_dv01: string;
  weighted_avg_spread: string;
  weighted_avg_spread_duration: string;
  spread_scenarios: SpreadScenarioResult[];
  migration_scenarios: MigrationScenarioResult[];
  concentration_by_issuer?: ConcentrationMetrics;
  concentration_by_industry?: ConcentrationMetrics;
  concentration_by_rating?: ConcentrationMetrics;
  concentration_by_tenor?: ConcentrationMetrics;
  /** When present with rating + tenor_bucket, UI can build rating×tenor heatmap. */
  bond_details?: CreditSpreadBondDetailRow[];
  oci_credit_exposure: string;
  oci_spread_dv01: string;
  oci_sensitivity_25bp: string;
  warnings: string[];
  computed_at: string;
}

// Action attribution types
export interface ActionTypeSummary {
  action_type: string;
  action_type_name: string;
  action_count: number;
  total_pnl_economic: string;
  total_pnl_accounting: string;
  avg_pnl_per_action: string;
}

export interface ActionDetail {
  action_id: string;
  action_type: string;
  action_date: string;
  bonds_involved: string[];
  description: string;
  pnl_economic: string;
  pnl_accounting: string;
  delta_duration: string;
  delta_dv01: string;
  delta_spread_dv01: string;
  opportunity_cost?: string;
  opportunity_cost_method?: string;
}

export interface ActionAttributionResponse {
  report_date: string;
  period_type: string;
  period_start: string;
  period_end: string;
  total_actions: number;
  total_pnl_from_actions: string;
  by_action_type: ActionTypeSummary[];
  action_details: ActionDetail[];
  period_start_duration: string;
  period_end_duration: string;
  duration_change_from_actions: string;
  period_start_dv01: string;
  period_end_dv01: string;
  warnings: string[];
  computed_at: string;
}

// Accounting audit types
export interface AccountingClassAuditItem {
  asset_class: string;
  position_count: number;
  market_value: string;
  market_value_weight: string;
  infer_accounting_class: string;
  map_accounting_class: string;
  infer_rule_id: string;
  infer_match: string | null;
  map_rule_id: string;
  map_match: string | null;
  is_divergent: boolean;
  is_map_unclassified: boolean;
}

export interface AccountingClassAuditResponse {
  report_date: string;
  total_positions: number;
  total_market_value: string;
  distinct_asset_classes: number;
  divergent_asset_classes: number;
  divergent_position_count: number;
  divergent_market_value: string;
  map_unclassified_asset_classes: number;
  map_unclassified_position_count: number;
  map_unclassified_market_value: string;
  rows: AccountingClassAuditItem[];
  warnings: string[];
  computed_at: string;
}

export const ACTION_TYPE_NAMES: Record<string, string> = {
  ADD_DURATION: "加久期",
  REDUCE_DURATION: "减久期",
  SWITCH: "换券",
  CREDIT_DOWN: "信用下沉",
  CREDIT_UP: "信用上收",
  TIMING_BUY: "择时买入",
  TIMING_SELL: "择时卖出",
  HEDGE: "对冲操作",
};
