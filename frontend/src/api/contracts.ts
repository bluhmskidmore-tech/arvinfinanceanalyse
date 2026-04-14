/** Shared API surface: envelope, health, and cross-cutting enums. */
export type ApiBasis = "formal" | "scenario" | "analytical" | "mock";
export type ApiQuality = "ok" | "warning" | "error" | "stale";

export type HealthCheckStatus = {
  ok: boolean;
  detail: string;
};

export type HealthResponse = {
  status: "ok" | "degraded" | "down";
  checks?: Record<string, HealthCheckStatus>;
};

export type ResultMeta = {
  trace_id: string;
  basis: ApiBasis;
  result_kind: string;
  formal_use_allowed: boolean;
  source_version: string;
  vendor_version: string;
  rule_version: string;
  cache_version: string;
  quality_flag: ApiQuality;
  vendor_status: "ok" | "vendor_stale" | "vendor_unavailable";
  fallback_mode: "none" | "latest_snapshot";
  scenario_flag: boolean;
  generated_at: string;
};

export type ApiEnvelope<T> = {
  result_meta: ResultMeta;
  result: T;
};

/** `/ui/home/*`, `/ui/pnl/attribution`, `/ui/risk/overview`, `/ui/home/alerts` payloads. */
export type ExecutiveMetric = {
  id: string;
  label: string;
  value: string;
  delta: string;
  tone: "positive" | "neutral" | "warning" | "negative";
  detail: string;
};

export type OverviewPayload = {
  title: string;
  metrics: ExecutiveMetric[];
};

export type SummaryPoint = {
  id: string;
  label: string;
  tone: "positive" | "neutral" | "warning";
  text: string;
};

export type SummaryPayload = {
  title: string;
  narrative: string;
  points: SummaryPoint[];
};

export type AttributionSegment = {
  id: string;
  label: string;
  amount: number;
  display_amount: string;
  tone: "positive" | "neutral" | "negative";
};

export type PnlAttributionPayload = {
  title: string;
  total: string;
  segments: AttributionSegment[];
};

export type FormalPnlRefreshPayload = {
  status: string;
  run_id?: string;
  job_name: string;
  trigger_mode: string;
  cache_key?: string;
  report_date?: string;
  source_version?: string;
  vendor_version?: string;
  rule_version?: string;
  lock?: string;
  formal_fi_rows?: number;
  nonstd_bridge_rows?: number;
  detail?: string | null;
  error_message?: string | null;
};

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
};

export type BondLevelDecomposition = {
  bond_code: string;
  bond_name: string | null;
  asset_class: string;
  accounting_class: string;
  market_value: string;
  carry: string;
  roll_down: string;
  rate_effect: string;
  spread_effect: string;
  convexity_effect: string;
  trading: string;
  total: string;
  explained_for_recon: string;
  economic_only_effects: string;
};

export type ReturnDecompositionPayload = {
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
};

export type ExcessSourceBreakdown = {
  source: string;
  contribution: string;
  description: string;
};

export type BenchmarkExcessPayload = {
  report_date: string;
  period_type: string;
  period_start: string;
  period_end: string;
  portfolio_return: string;
  benchmark_return: string;
  excess_return: string;
  tracking_error: string | null;
  information_ratio: string | null;
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
};

export type KRDBucket = {
  tenor: string;
  krd: string;
  dv01: string;
  market_value_weight: string;
};

export type KRDScenarioResult = {
  scenario_name: string;
  scenario_description: string;
  shocks: Record<string, number>;
  pnl_economic: string;
  pnl_oci: string;
  pnl_tpl: string;
  rate_contribution: string;
  convexity_contribution: string;
  by_asset_class: Record<string, Record<string, string>>;
};

export type AssetClassRiskSummary = {
  asset_class: string;
  market_value: string;
  duration: string;
  dv01: string;
  weight: string;
};

export type KRDCurveRiskPayload = {
  report_date: string;
  portfolio_duration: string;
  portfolio_modified_duration: string;
  portfolio_dv01: string;
  portfolio_convexity: string;
  krd_buckets: KRDBucket[];
  scenarios: KRDScenarioResult[];
  by_asset_class: AssetClassRiskSummary[];
  warnings: string[];
  computed_at: string;
};

/** `/api/bond-analytics/portfolio-headlines` */
export type BondPortfolioHeadlinesPayload = {
  report_date: string;
  total_market_value: string;
  weighted_ytm: string;
  weighted_duration: string;
  weighted_coupon: string;
  total_dv01: string;
  bond_count: number;
  credit_weight: string;
  issuer_hhi: string;
  issuer_top5_weight: string;
  by_asset_class: AssetClassRiskSummary[];
  warnings: string[];
  computed_at: string;
};

export type BondTopHoldingItem = {
  instrument_code: string;
  instrument_name: string | null;
  issuer_name: string | null;
  rating: string | null;
  asset_class: string;
  market_value: string;
  face_value: string;
  ytm: string;
  modified_duration: string;
  weight: string;
};

/** `/api/bond-analytics/top-holdings` */
export type BondTopHoldingsPayload = {
  report_date: string;
  top_n: number;
  items: BondTopHoldingItem[];
  total_market_value: string;
  warnings: string[];
  computed_at: string;
};

export type SpreadScenarioResult = {
  scenario_name: string;
  spread_change_bp: number;
  pnl_impact: string;
  oci_impact: string;
  tpl_impact: string;
};

export type MigrationScenarioResult = {
  scenario_name: string;
  from_rating: string;
  to_rating: string;
  affected_bonds: number;
  affected_market_value: string;
  pnl_impact: string;
  oci_impact?: string;
};

export type ConcentrationItem = {
  name: string;
  weight: string;
  market_value: string;
};

export type ConcentrationMetrics = {
  dimension: string;
  hhi: string;
  top5_concentration: string;
  top_items: ConcentrationItem[];
};

export type CreditSpreadBondDetailRow = {
  market_value: string;
  rating?: string;
  tenor_bucket?: string;
};

export type CreditSpreadMigrationPayload = {
  report_date: string;
  credit_bond_count: number;
  credit_market_value: string;
  credit_weight: string;
  rating_aa_and_below_weight?: string;
  spread_dv01: string;
  weighted_avg_spread: string;
  weighted_avg_spread_duration: string;
  spread_scenarios: SpreadScenarioResult[];
  migration_scenarios: MigrationScenarioResult[];
  concentration_by_issuer?: ConcentrationMetrics;
  concentration_by_industry?: ConcentrationMetrics;
  concentration_by_rating?: ConcentrationMetrics;
  concentration_by_tenor?: ConcentrationMetrics;
  bond_details?: CreditSpreadBondDetailRow[];
  oci_credit_exposure: string;
  oci_spread_dv01: string;
  oci_sensitivity_25bp: string;
  warnings: string[];
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

export type ActionTypeSummary = {
  action_type: string;
  action_type_name: string;
  action_count: number;
  total_pnl_economic: string;
  total_pnl_accounting: string;
  avg_pnl_per_action: string;
};

export type ActionDetail = {
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
};

export type ActionAttributionPayload = {
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
};

export type AccountingClassAuditItem = {
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
};

export type AccountingClassAuditPayload = {
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
};

export type RiskSignal = {
  id: string;
  label: string;
  value: string;
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
  contribution: string;
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
 * `/api/risk/tensor?report_date=` — `result` 内为风险张量载荷（小数字段为后端量化后的字符串）。
 * 「风险总览」与「风险张量」页面均通过 `getRiskTensor` 消费同一载荷；不在前端补算指标。
 */
export type RiskTensorPayload = {
  report_date: string;
  portfolio_dv01: string;
  krd_1y: string;
  krd_3y: string;
  krd_5y: string;
  krd_7y: string;
  krd_10y: string;
  krd_30y: string;
  cs01: string;
  portfolio_convexity: string;
  portfolio_modified_duration: string;
  issuer_concentration_hhi: string;
  issuer_top5_weight: string;
  liquidity_gap_30d: string;
  liquidity_gap_90d: string;
  liquidity_gap_30d_ratio: string;
  total_market_value: string;
  bond_count: number;
  quality_flag: string;
  warnings: string[];
};

export type RiskTensorDatesPayload = {
  report_dates: string[];
};

export type PlaceholderSnapshot = {
  title: string;
  summary: string;
  highlights: string[];
};

/**
 * Source preview (`/ui/preview/source-foundation`) and product-category P&L
 * (`/ui/pnl/product-category*`) contract shapes.
 */
export type SourcePreviewSummary = {
  ingest_batch_id?: string | null;
  batch_created_at?: string | null;
  source_family: string;
  report_date: string | null;
  report_start_date?: string | null;
  report_end_date?: string | null;
  report_granularity?: string | null;
  source_file: string;
  total_rows: number;
  manual_review_count: number;
  source_version: string;
  rule_version: string;
  group_counts: Record<string, number>;
  preview_mode?: string;
};

export type SourcePreviewPayload = {
  sources: SourcePreviewSummary[];
};

export type SourcePreviewHistoryPayload = {
  limit: number;
  offset: number;
  total_rows: number;
  rows: SourcePreviewSummary[];
};

/**
 * Backend source-preview rows are family-dependent dynamic dictionaries from DuckDB `select *`.
 * Frontend callers should treat them as records and only read known keys defensively.
 */
export type SourcePreviewRow = Record<string, unknown>;

export type SourcePreviewColumn = {
  key: string;
  label: string;
  type: "string" | "number" | "boolean";
};

export type SourcePreviewRowsPayload = {
  source_family: string;
  ingest_batch_id?: string | null;
  limit: number;
  offset: number;
  total_rows: number;
  columns: SourcePreviewColumn[];
  rows: SourcePreviewRow[];
};

export type SourcePreviewTraceRow = Record<string, unknown>;

export type SourcePreviewTracesPayload = {
  source_family: string;
  ingest_batch_id?: string | null;
  limit: number;
  offset: number;
  total_rows: number;
  columns: SourcePreviewColumn[];
  rows: SourcePreviewTraceRow[];
};

export type SourcePreviewRefreshPayload = {
  status: string;
  run_id?: string;
  job_name: string;
  trigger_mode: string;
  cache_key?: string;
  preview_sources?: string[];
  ingest_batch_id?: string | null;
  report_dates?: string[];
  source_version?: string;
  vendor_version?: string;
  rule_version?: string;
  lock?: string;
  detail?: string | null;
  error_message?: string | null;
};

export type ChoiceMacroRefreshPayload = {
  status: string;
  run_id?: string;
  series_count?: number;
  vendor_version?: string;
  source_version?: string;
  cache_key?: string;
  detail?: string | null;
  error_message?: string | null;
};

export type MacroVendorSeries = {
  series_id: string;
  series_name: string;
  vendor_name: string;
  vendor_version: string;
  frequency: string;
  unit: string;
  refresh_tier?: "stable" | "fallback" | "isolated" | null;
  fetch_mode?: "date_slice" | "latest" | null;
  fetch_granularity?: "batch" | "single" | null;
  policy_note?: string | null;
};

export type MacroVendorPayload = {
  read_target: "duckdb";
  series: MacroVendorSeries[];
};

export type ChoiceMacroLatestPoint = {
  series_id: string;
  series_name: string;
  trade_date: string;
  value_numeric: number;
  frequency?: string;
  unit: string;
  source_version: string;
  vendor_version: string;
  refresh_tier?: "stable" | "fallback" | "isolated" | null;
  fetch_mode?: "date_slice" | "latest" | null;
  fetch_granularity?: "batch" | "single" | null;
  policy_note?: string | null;
  quality_flag?: ApiQuality;
  latest_change?: number | null;
  recent_points?: ChoiceMacroRecentPoint[];
};

export type ChoiceMacroRecentPoint = {
  trade_date: string;
  value_numeric: number;
  source_version: string;
  vendor_version: string;
  quality_flag: ApiQuality;
};

export type ChoiceMacroLatestPayload = {
  read_target: "duckdb";
  series: ChoiceMacroLatestPoint[];
};

export type MacroBondLinkageEnvironmentFactor = Record<string, unknown>;

export type MacroBondLinkageEnvironmentScore = {
  report_date: string;
  rate_direction: string;
  rate_direction_score: number;
  liquidity_score: number;
  growth_score: number;
  inflation_score: number;
  composite_score: number;
  signal_description: string;
  contributing_factors: MacroBondLinkageEnvironmentFactor[];
  warnings: string[];
};

export type MacroBondLinkagePortfolioImpact = {
  estimated_rate_change_bps: DecimalLike;
  estimated_spread_widening_bps: DecimalLike;
  estimated_rate_pnl_impact: DecimalLike;
  estimated_spread_pnl_impact: DecimalLike;
  total_estimated_impact: DecimalLike;
  impact_ratio_to_market_value: DecimalLike;
};

export type MacroBondLinkageTopCorrelation = {
  series_id: string;
  series_name: string;
  target_family: string;
  target_tenor: string | null;
  target_yield?: string | null;
  correlation_3m: number | null;
  correlation_6m: number | null;
  correlation_1y: number | null;
  lead_lag_days: number;
  direction: "positive" | "negative" | "neutral";
};

export type MacroBondLinkagePayload = {
  report_date: string;
  environment_score: Partial<MacroBondLinkageEnvironmentScore>;
  portfolio_impact: Partial<MacroBondLinkagePortfolioImpact>;
  top_correlations: MacroBondLinkageTopCorrelation[];
  warnings: string[];
  computed_at: string;
};

export type FxAnalyticalGroupKey = "middle_rate" | "fx_index" | "fx_swap_curve";

export type FxFormalStatusRow = {
  base_currency: string;
  quote_currency: string;
  pair_label: string;
  series_id: string;
  series_name: string;
  vendor_series_code: string;
  trade_date: string | null;
  observed_trade_date: string | null;
  mid_rate: number | null;
  source_name: string | null;
  vendor_name: string | null;
  vendor_version: string | null;
  source_version: string | null;
  is_business_day: boolean | null;
  is_carry_forward: boolean | null;
  status: "ok" | "missing";
};

export type FxFormalStatusPayload = {
  read_target: "duckdb";
  vendor_priority: string[];
  candidate_count: number;
  materialized_count: number;
  latest_trade_date: string | null;
  carry_forward_count: number;
  rows: FxFormalStatusRow[];
};

export type FxAnalyticalSeriesPoint = {
  group_key: FxAnalyticalGroupKey;
  series_id: string;
  series_name: string;
  trade_date: string;
  value_numeric: number;
  frequency: string;
  unit: string;
  source_version: string;
  vendor_version: string;
  refresh_tier?: "stable" | "fallback" | "isolated" | null;
  fetch_mode?: "date_slice" | "latest" | null;
  fetch_granularity?: "batch" | "single" | null;
  policy_note?: string | null;
  quality_flag?: ApiQuality;
  latest_change?: number | null;
  recent_points?: ChoiceMacroRecentPoint[];
};

export type FxAnalyticalGroup = {
  group_key: FxAnalyticalGroupKey;
  title: string;
  description: string;
  series: FxAnalyticalSeriesPoint[];
};

export type FxAnalyticalPayload = {
  read_target: "duckdb";
  groups: FxAnalyticalGroup[];
};

export type ChoiceNewsEvent = {
  event_key: string;
  received_at: string;
  group_id: string;
  content_type: string;
  serial_id: number;
  request_id: number;
  error_code: number;
  error_msg: string;
  topic_code: string;
  item_index: number;
  payload_text: string | null;
  payload_json: string | null;
};

export type ChoiceNewsEventsPayload = {
  total_rows: number;
  limit: number;
  offset: number;
  events: ChoiceNewsEvent[];
};

export type PnlFormalFiRow = {
  report_date: string;
  instrument_code: string;
  portfolio_name: string;
  cost_center: string;
  invest_type_std: string;
  accounting_basis: string;
  currency_basis: string;
  interest_income_514: string;
  fair_value_change_516: string;
  capital_gain_517: string;
  manual_adjustment: string;
  total_pnl: string;
  source_version: string;
  rule_version: string;
  ingest_batch_id: string;
  trace_id: string;
};

export type PnlNonStdBridgeRow = {
  report_date: string;
  bond_code: string;
  portfolio_name: string;
  cost_center: string;
  interest_income_514: string;
  fair_value_change_516: string;
  capital_gain_517: string;
  manual_adjustment: string;
  total_pnl: string;
  source_version: string;
  rule_version: string;
  ingest_batch_id: string;
  trace_id: string;
};

export type PnlDatesPayload = {
  report_dates: string[];
  formal_fi_report_dates: string[];
  nonstd_bridge_report_dates: string[];
};

export type PnlDataPayload = {
  report_date: string;
  formal_fi_rows: PnlFormalFiRow[];
  nonstd_bridge_rows: PnlNonStdBridgeRow[];
};

export type PnlOverviewPayload = {
  report_date: string;
  formal_fi_row_count: number;
  nonstd_bridge_row_count: number;
  interest_income_514: string;
  fair_value_change_516: string;
  capital_gain_517: string;
  manual_adjustment: string;
  total_pnl: string;
};

export type PnlBridgeQuality = "ok" | "warning" | "error";

export type PnlBridgeRow = {
  report_date?: string;
  instrument_code: string;
  portfolio_name: string;
  cost_center?: string;
  accounting_basis: string;
  beginning_dirty_mv?: string;
  ending_dirty_mv?: string;
  carry: string;
  roll_down: string;
  treasury_curve: string;
  credit_spread: string;
  fx_translation: string;
  realized_trading: string;
  unrealized_fv: string;
  manual_adjustment: string;
  explained_pnl: string;
  actual_pnl: string;
  residual: string;
  residual_ratio: string;
  quality_flag: PnlBridgeQuality;
  current_balance_found?: boolean;
  prior_balance_found?: boolean;
  balance_diagnostics?: string[];
};

export type PnlBridgeSummary = {
  row_count: number;
  ok_count: number;
  warning_count: number;
  error_count: number;
  total_beginning_dirty_mv: string;
  total_ending_dirty_mv: string;
  total_carry: string;
  total_roll_down: string;
  total_treasury_curve: string;
  total_credit_spread: string;
  total_fx_translation: string;
  total_realized_trading: string;
  total_unrealized_fv: string;
  total_manual_adjustment: string;
  total_explained_pnl: string;
  total_actual_pnl: string;
  total_residual: string;
  quality_flag: PnlBridgeQuality;
};

export type PnlBridgePayload = {
  report_date: string;
  rows: PnlBridgeRow[];
  summary: PnlBridgeSummary;
  warnings: string[];
};

export type DecimalLike = string | number;

export type ProductCategoryPnlRow = {
  category_id: string;
  category_name: string;
  side: string;
  level: number;
  view: string;
  report_date: string;
  baseline_ftp_rate_pct: DecimalLike;
  cnx_scale: DecimalLike;
  cny_scale: DecimalLike;
  foreign_scale: DecimalLike;
  cnx_cash: DecimalLike;
  cny_cash: DecimalLike;
  foreign_cash: DecimalLike;
  cny_ftp: DecimalLike;
  foreign_ftp: DecimalLike;
  cny_net: DecimalLike;
  foreign_net: DecimalLike;
  business_net_income: DecimalLike;
  weighted_yield: DecimalLike | null;
  is_total: boolean;
  children: string[];
  scenario_rate_pct?: DecimalLike | null;
};

export type ProductCategoryDatesPayload = {
  report_dates: string[];
};

export type ProductCategoryPnlPayload = {
  report_date: string;
  view: string;
  available_views: string[];
  scenario_rate_pct: DecimalLike | null;
  rows: ProductCategoryPnlRow[];
  asset_total: ProductCategoryPnlRow;
  liability_total: ProductCategoryPnlRow;
  grand_total: ProductCategoryPnlRow;
};

export type ProductCategoryRefreshPayload = {
  status: string;
  run_id: string;
  job_name: string;
  trigger_mode: string;
  cache_key?: string;
  month_count?: number;
  report_dates?: string[];
  rule_version?: string;
  source_version?: string;
  lock?: string;
  detail?: string | null;
};

export type BalanceAnalysisDatesPayload = {
  report_dates: string[];
};

export type BalancePositionScope = "asset" | "liability" | "all";

export type BalanceCurrencyBasis = "native" | "CNY";

export type BalanceAnalysisDetailRow = {
  source_family: "zqtz" | "tyw";
  report_date: string;
  row_key: string;
  display_name: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  invest_type_std: string;
  accounting_basis: string;
  market_value_amount: DecimalLike;
  amortized_cost_amount: DecimalLike;
  accrued_interest_amount: DecimalLike;
  is_issuance_like: boolean | null;
};

export type BalanceAnalysisSummaryRow = {
  source_family: "zqtz" | "tyw" | "combined";
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  row_count: number;
  market_value_amount: DecimalLike;
  amortized_cost_amount: DecimalLike;
  accrued_interest_amount: DecimalLike;
};

export type BalanceAnalysisOverviewPayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  detail_row_count: number;
  summary_row_count: number;
  total_market_value_amount: DecimalLike;
  total_amortized_cost_amount: DecimalLike;
  total_accrued_interest_amount: DecimalLike;
};

export type BalanceAnalysisTableRow = {
  row_key: string;
  source_family: "zqtz" | "tyw";
  display_name: string;
  owner_name: string;
  category_name: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  invest_type_std: string;
  accounting_basis: string;
  detail_row_count: number;
  market_value_amount: DecimalLike;
  amortized_cost_amount: DecimalLike;
  accrued_interest_amount: DecimalLike;
};

export type BalanceAnalysisSummaryTablePayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  limit: number;
  offset: number;
  total_rows: number;
  rows: BalanceAnalysisTableRow[];
};

export type BalanceAnalysisPayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  details: BalanceAnalysisDetailRow[];
  summary: BalanceAnalysisSummaryRow[];
};

export type BalanceAnalysisBasisBreakdownRow = {
  source_family: "zqtz" | "tyw";
  invest_type_std: string;
  accounting_basis: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  detail_row_count: number;
  market_value_amount: DecimalLike;
  amortized_cost_amount: DecimalLike;
  accrued_interest_amount: DecimalLike;
};

export type BalanceAnalysisBasisBreakdownPayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  rows: BalanceAnalysisBasisBreakdownRow[];
};

export type BalanceAnalysisAdvancedAttributionBundlePayload = {
  report_date: string;
  mode: "analytical" | "scenario";
  scenario_name: string | null;
  scenario_inputs: Record<string, number>;
  upstream_summaries: Record<string, Record<string, string | string[]>>;
  status: "not_ready";
  missing_inputs: string[];
  blocked_components: string[];
  warnings: string[];
};

export type BalanceAnalysisWorkbookCard = {
  key: string;
  label: string;
  value: DecimalLike;
  note?: string | null;
};

export type BalanceAnalysisWorkbookColumn = {
  key: string;
  label: string;
};

export type BalanceAnalysisWorkbookSectionKind =
  | "table"
  | "decision_items"
  | "event_calendar"
  | "risk_alerts";

export type BalanceAnalysisSeverity = "low" | "medium" | "high";
export type BalanceAnalysisDecisionStatus = "pending" | "confirmed" | "dismissed";

export type BalanceAnalysisWorkbookTable = {
  key: string;
  title: string;
  section_kind: "table";
  columns: BalanceAnalysisWorkbookColumn[];
  rows: Array<Record<string, unknown>>;
};

export type BalanceAnalysisDecisionItemRow = {
  title: string;
  action_label: string;
  severity: BalanceAnalysisSeverity;
  reason: string;
  source_section: string;
  rule_id: string;
  rule_version: string;
};

export type BalanceAnalysisDecisionStatusRecord = {
  decision_key: string;
  status: BalanceAnalysisDecisionStatus;
  updated_at: string | null;
  updated_by: string | null;
  comment?: string | null;
};

export type BalanceAnalysisCurrentUserPayload = {
  user_id: string;
  role: string;
  identity_source: "header" | "env" | "system" | "fallback";
};

export type BalanceAnalysisDecisionItemStatusRow = {
  decision_key: string;
  title: string;
  action_label: string;
  severity: BalanceAnalysisSeverity;
  reason: string;
  source_section: string;
  rule_id: string;
  rule_version: string;
  latest_status: BalanceAnalysisDecisionStatusRecord;
};

export type BalanceAnalysisDecisionItemsSection = {
  key: "decision_items";
  title: string;
  section_kind: "decision_items";
  columns: BalanceAnalysisWorkbookColumn[];
  rows: BalanceAnalysisDecisionItemRow[];
};

export type BalanceAnalysisEventCalendarRow = {
  event_date: string;
  event_type: string;
  title: string;
  source: string;
  impact_hint: string;
  source_section: string;
};

export type BalanceAnalysisEventCalendarSection = {
  key: "event_calendar";
  title: string;
  section_kind: "event_calendar";
  columns: BalanceAnalysisWorkbookColumn[];
  rows: BalanceAnalysisEventCalendarRow[];
};

export type BalanceAnalysisRiskAlertRow = {
  title: string;
  severity: BalanceAnalysisSeverity;
  reason: string;
  source_section: string;
  rule_id: string;
  rule_version: string;
};

export type BalanceAnalysisRiskAlertsSection = {
  key: "risk_alerts";
  title: string;
  section_kind: "risk_alerts";
  columns: BalanceAnalysisWorkbookColumn[];
  rows: BalanceAnalysisRiskAlertRow[];
};

export type BalanceAnalysisWorkbookOperationalSection =
  | BalanceAnalysisDecisionItemsSection
  | BalanceAnalysisEventCalendarSection
  | BalanceAnalysisRiskAlertsSection;

export type BalanceAnalysisDecisionItemsPayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  columns: BalanceAnalysisWorkbookColumn[];
  rows: BalanceAnalysisDecisionItemStatusRow[];
};

export type BalanceAnalysisWorkbookPayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  cards: BalanceAnalysisWorkbookCard[];
  tables: BalanceAnalysisWorkbookTable[];
  operational_sections: BalanceAnalysisWorkbookOperationalSection[];
};

export type BalanceAnalysisSummaryExportPayload = {
  filename: string;
  content: string;
};

export type BalanceAnalysisWorkbookExportPayload = {
  filename: string;
  content: Blob;
};

export type BalanceAnalysisRefreshPayload = {
  status: string;
  run_id?: string;
  job_name: string;
  trigger_mode: string;
  cache_key?: string;
  report_date?: string;
  source_version?: string;
  vendor_version?: string;
  rule_version?: string;
  lock?: string;
  zqtz_rows?: number;
  tyw_rows?: number;
  detail?: string | null;
  error_message?: string | null;
};

export type ProductCategoryManualAdjustmentRequest = {
  report_date: string;
  operator: "ADD" | "DELTA" | "OVERRIDE";
  approval_status: "approved" | "pending" | "rejected";
  account_code: string;
  currency: "CNX" | "CNY";
  account_name?: string;
  beginning_balance?: string | null;
  ending_balance?: string | null;
  monthly_pnl?: string | null;
  daily_avg_balance?: string | null;
  annual_avg_balance?: string | null;
};

export type ProductCategoryManualAdjustmentPayload = {
  adjustment_id: string;
  event_type: string;
  created_at: string;
  stream: string;
  report_date: string;
  operator: string;
  approval_status: string;
  account_code: string;
  currency: string;
  account_name: string;
  beginning_balance?: string | null;
  ending_balance?: string | null;
  monthly_pnl?: string | null;
  daily_avg_balance?: string | null;
  annual_avg_balance?: string | null;
};

export type ProductCategoryManualAdjustmentListPayload = {
  report_date: string;
  adjustment_count: number;
  adjustment_limit: number;
  adjustment_offset: number;
  event_total: number;
  event_limit: number;
  event_offset: number;
  adjustments: ProductCategoryManualAdjustmentPayload[];
  events: ProductCategoryManualAdjustmentPayload[];
};

export type ProductCategoryCurrentSortField =
  | "created_at"
  | "adjustment_id"
  | "approval_status"
  | "account_code";

export type ProductCategoryEventSortField =
  | "created_at"
  | "adjustment_id"
  | "event_type"
  | "approval_status"
  | "account_code";

export type ProductCategorySortDirection = "asc" | "desc";

export type ProductCategoryManualAdjustmentQuery = {
  adjustmentId?: string;
  adjustmentIdExact?: boolean;
  accountCode?: string;
  approvalStatus?: string;
  eventType?: string;
  currentSortField?: ProductCategoryCurrentSortField;
  currentSortDir?: ProductCategorySortDirection;
  eventSortField?: ProductCategoryEventSortField;
  eventSortDir?: ProductCategorySortDirection;
  createdAtFrom?: string;
  createdAtTo?: string;
  adjustmentLimit?: number;
  adjustmentOffset?: number;
  limit?: number;
  offset?: number;
};

export type ProductCategoryManualAdjustmentExportPayload = {
  filename: string;
  content: string;
};

export type QdbGlMonthlyAnalysisDatesPayload = {
  report_months: string[];
};

export type QdbGlMonthlyAnalysisSheet = {
  key: string;
  title: string;
  columns: string[];
  rows: Array<Record<string, unknown>>;
};

export type QdbGlMonthlyAnalysisWorkbookPayload = {
  report_month: string;
  sheets: QdbGlMonthlyAnalysisSheet[];
};

export type QdbGlMonthlyAnalysisScenarioPayload = QdbGlMonthlyAnalysisWorkbookPayload & {
  scenario_name: string;
  applied_overrides: Record<string, unknown>;
};

export type QdbGlMonthlyAnalysisWorkbookExportPayload = {
  filename: string;
  content: Blob;
};

export type QdbGlMonthlyAnalysisManualAdjustmentRequest = {
  report_month: string;
  adjustment_class: "mapping_adjustment" | "analysis_adjustment";
  target: Record<string, unknown>;
  operator: "ADD" | "DELTA" | "OVERRIDE";
  value: string;
  approval_status: "approved" | "pending" | "rejected";
};

export type QdbGlMonthlyAnalysisManualAdjustmentPayload = {
  adjustment_id: string;
  event_type: string;
  created_at: string;
  stream: string;
  report_month: string;
  adjustment_class: "mapping_adjustment" | "analysis_adjustment";
  target: Record<string, unknown>;
  operator: string;
  value: string;
  approval_status: string;
};

export type QdbGlMonthlyAnalysisManualAdjustmentListPayload = {
  report_month: string;
  adjustment_count: number;
  adjustments: QdbGlMonthlyAnalysisManualAdjustmentPayload[];
  events: QdbGlMonthlyAnalysisManualAdjustmentPayload[];
};

export type QdbGlMonthlyAnalysisManualAdjustmentExportPayload = {
  filename: string;
  content: string;
};

/** Agent / multi-batch tooling contracts (separate from UI envelope-only pages). */
export type AgentQueryRequest = {
  question: string;
  basis: "formal" | "scenario" | "analytical";
  filters: Record<string, unknown>;
  position_scope: string;
  currency_basis: string;
  context: Record<string, unknown>;
};

export type AgentDrill = {
  dimension: string;
  label: string;
};

export type AgentCard = {
  type: string;
  title: string;
  value?: string;
  data?: Record<string, unknown> | Array<Record<string, unknown>>;
  spec?: Record<string, unknown>;
};

export type AgentEvidence = {
  tables_used: string[];
  filters_applied: Record<string, unknown>;
  sql_executed: string[];
  evidence_rows: number;
  quality_flag: ApiQuality;
};

export type AgentResultMeta = ResultMeta & {
  tables_used: string[];
  filters_applied: Record<string, unknown>;
  sql_executed: string[];
  evidence_rows: number;
  next_drill: AgentDrill[];
};

export type AgentEnvelope = {
  answer: string;
  cards: AgentCard[];
  evidence: AgentEvidence;
  result_meta: AgentResultMeta;
  next_drill: AgentDrill[];
};

export type AgentDisabledResponse = {
  enabled: false;
  phase: "phase1";
  detail: string;
};

/** Positions module types */
export type PositionDirection = "Asset" | "Liability";

export type PageResponse<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type BondPositionItem = {
  bond_code: string;
  credit_name: string | null;
  sub_type: string | null;
  asset_class: string | null;
  market_value: string | null;
  face_value: string | null;
  valuation_net_price: string | null;
  yield_rate: string | null;
};

export type InterbankPositionItem = {
  deal_id: string;
  counterparty: string | null;
  product_type: string | null;
  direction: PositionDirection | null;
  amount: string;
  interest_rate: string | null;
  maturity_date: string | null;
};

export type CounterpartyStatItem = {
  customer_name: string;
  total_amount: string;
  avg_daily_balance: string;
  weighted_rate: string | null;
  weighted_coupon_rate?: string | null;
  transaction_count: number;
};

export type CounterpartyStatsResponse = {
  start_date: string;
  end_date: string;
  num_days: number;
  items: CounterpartyStatItem[];
  total_amount: string;
  total_avg_daily: string;
  total_weighted_rate: string | null;
  total_weighted_coupon_rate?: string | null;
  total_customers: number;
};

export type SubTypesResponse = { sub_types: string[] };
export type ProductTypesResponse = { product_types: string[] };

export type RatingStatItem = {
  rating: string;
  total_amount: string;
  avg_daily_balance: string;
  weighted_rate: string | null;
  bond_count: number;
  percentage: string;
};

export type RatingStatsResponse = {
  start_date: string;
  end_date: string;
  num_days: number;
  items: RatingStatItem[];
  total_amount: string;
  total_avg_daily: string;
};

export type IndustryStatItem = {
  industry: string;
  total_amount: string;
  avg_daily_balance: string;
  weighted_rate: string | null;
  bond_count: number;
  percentage: string;
};

export type IndustryStatsResponse = {
  start_date: string;
  end_date: string;
  num_days: number;
  items: IndustryStatItem[];
  total_amount: string;
  total_avg_daily: string;
};

export type CustomerBondDetailItem = {
  bond_code: string;
  sub_type: string | null;
  asset_class: string | null;
  market_value: string;
  yield_rate: string | null;
  maturity_date: string | null;
  rating: string;
  industry: string;
};

export type CustomerBondDetailsResponse = {
  customer_name: string;
  report_date: string;
  total_market_value: string;
  bond_count: number;
  items: CustomerBondDetailItem[];
};

export type PositionBalanceTrendItem = {
  date: string;
  balance: string;
};

export type CustomerBalanceTrendResponse = {
  customer_name: string;
  start_date: string;
  end_date: string;
  days: number;
  items: PositionBalanceTrendItem[];
};

export type InterbankCounterpartySplitResponse = {
  start_date: string;
  end_date: string;
  num_days: number;
  asset_total_amount: string;
  asset_total_avg_daily: string;
  asset_total_weighted_rate: string | null;
  asset_customer_count: number;
  liability_total_amount: string;
  liability_total_avg_daily: string;
  liability_total_weighted_rate: string | null;
  liability_customer_count: number;
  asset_items: CounterpartyStatItem[];
  liability_items: CounterpartyStatItem[];
};

// --- KPI / 绩效考核 (`/api/kpi`) — Decimal 字段保持 string，不在前端做金额计算 ---

export type KpiDecimalString = string | null;

export type KpiScopeType = "portfolio_type" | "asset_class" | "department" | "custom";

export type KpiScoringRuleType =
  | "LINEAR_RATIO"
  | "LINEAR_RATIO_PROGRESS"
  | "THRESHOLD_DEDUCT_BP"
  | "THRESHOLD_DEDUCT_ABS"
  | "LINEAR_COMPOSITE_AVG"
  | "DEPEND_ON_OTHER_OWNER"
  | "MANUAL";

export type KpiDataSourceType = "AUTO" | "MANUAL" | "EXTERNAL";

export type KpiFetchStatus = "SUCCESS" | "FAILED" | "PENDING" | "SKIPPED";

export type KpiFetchTrace = {
  sql_template_id?: string;
  sql_hash?: string;
  fetch_function?: string;
  params: Record<string, unknown>;
  execution_time_ms: number;
  row_count: number;
  error?: string;
  fetched_at: string;
};

export type KpiRoundingConfig = {
  precision: number;
  mode: "HALF_UP" | "HALF_DOWN" | "CEILING" | "FLOOR";
};

export type KpiScoreTrace = {
  rule_type: string;
  score_input_field: "completion_ratio" | "progress_pct" | string;
  inputs: Record<string, string>;
  formula: string;
  intermediate: Record<string, string>;
  final_score: string;
  capped: boolean;
  rounding: string;
  reason?: string;
  scored_at: string;
};

export type KpiOwner = {
  owner_id: number;
  owner_name: string;
  org_unit: string;
  person_name?: string;
  year: number;
  scope_type: KpiScopeType;
  scope_key?: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type KpiOwnerListResponse = {
  owners: KpiOwner[];
  total: number;
};

export type KpiScoringRuleParams = {
  weight: KpiDecimalString;
  cap?: KpiDecimalString;
  score_input_field: "completion_ratio" | "progress_pct";
  rounding?: KpiRoundingConfig;
  threshold?: KpiDecimalString;
  deduct_per_bp?: KpiDecimalString;
  deduct_per_unit?: KpiDecimalString;
};

export type KpiDataSourceParams = {
  fetch_function?: string;
  sql_template_id?: string;
  unit?: string;
  extra_filter?: Record<string, unknown>;
};

export type KpiMetric = {
  metric_id: number;
  metric_code: string;
  owner_id: number;
  year: number;
  major_category: string;
  indicator_category?: string;
  metric_name: string;
  target_value: KpiDecimalString;
  target_text?: string;
  score_weight: KpiDecimalString;
  unit?: string;
  scoring_text?: string;
  scoring_rule_type: KpiScoringRuleType;
  scoring_rule_params?: KpiScoringRuleParams;
  data_source_type: KpiDataSourceType;
  data_source_params?: KpiDataSourceParams;
  progress_plan?: string;
  remarks?: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
};

export type KpiMetricUpsertRequest = {
  metric_code: string;
  metric_name: string;
  major_category: string;
  owner_id: number;
  year: number;
  score_weight: string;
  data_source_type: KpiDataSourceType;
  scoring_rule_type: KpiScoringRuleType;
  indicator_category?: string;
  target_value?: KpiDecimalString;
  target_text?: string;
  unit?: string;
  scoring_text?: string;
  remarks?: string;
};

export type KpiMetricListResponse = {
  metrics: KpiMetric[];
  total: number;
};

export type KpiMetricValue = {
  value_id: number;
  metric_id: number;
  as_of_date: string;
  actual_value: KpiDecimalString;
  actual_text?: string;
  completion_ratio: KpiDecimalString;
  progress_pct: KpiDecimalString;
  score_value: KpiDecimalString;
  fetch_status?: KpiFetchStatus;
  fetch_trace?: KpiFetchTrace;
  fetched_at?: string;
  score_calc_trace?: KpiScoreTrace;
  scored_at?: string;
  source?: string;
  created_at: string;
  updated_at: string;
};

export type KpiMetricWithValue = KpiMetric & {
  value_id?: number;
  as_of_date?: string;
  actual_value?: KpiDecimalString;
  actual_text?: string;
  completion_ratio?: KpiDecimalString;
  progress_pct?: KpiDecimalString;
  score_value?: KpiDecimalString;
  fetch_status?: KpiFetchStatus;
  fetch_trace?: KpiFetchTrace;
  score_calc_trace?: KpiScoreTrace;
  source?: string;
};

export type KpiValuesResponse = {
  owner_id: number;
  owner_name: string;
  as_of_date: string;
  metrics: KpiMetricWithValue[];
  total: number;
};

export type KpiFetchAndRecalcRequest = {
  metric_ids?: number[];
};

export type KpiMetricResultItem = {
  metric_id: number;
  metric_code: string;
  metric_name: string;
  target_value: KpiDecimalString;
  actual_value: KpiDecimalString;
  completion_ratio: KpiDecimalString;
  progress_pct: KpiDecimalString;
  score_value: KpiDecimalString;
  fetch_status: KpiFetchStatus;
  score_status: string;
  error_message?: string;
  fetch_trace?: KpiFetchTrace;
  score_calc_trace?: KpiScoreTrace;
};

export type KpiFetchAndRecalcResponse = {
  owner_id: number;
  owner_name: string;
  as_of_date: string;
  total_metrics: number;
  fetched_count: number;
  scored_count: number;
  failed_count: number;
  skipped_count: number;
  results: KpiMetricResultItem[];
};

export type KpiReportRow = {
  owner_name: string;
  org_unit: string;
  major_category: string;
  indicator_category?: string;
  metric_name: string;
  target_value: KpiDecimalString;
  target_text?: string;
  unit?: string;
  score_weight: KpiDecimalString;
  scoring_text?: string;
  actual_value: KpiDecimalString;
  completion_ratio: KpiDecimalString;
  progress_pct: KpiDecimalString;
  score_value: KpiDecimalString;
  remarks?: string;
};

export type KpiReportResponse = {
  year: number;
  generated_at: string;
  rows: KpiReportRow[];
  total: number;
};

export type KpiPeriodMetricSummary = {
  metric_id: number;
  metric_code: string;
  metric_name: string;
  major_category: string;
  indicator_category?: string;
  target_value?: string;
  unit?: string;
  score_weight: string;
  period_actual_value?: string;
  period_completion_ratio?: string;
  period_progress_pct?: string;
  period_score_value?: string;
  period_start_date: string;
  period_end_date: string;
  data_date?: string;
};

export type KpiPeriodSummaryResponse = {
  owner_id: number;
  owner_name: string;
  year: number;
  period_type: string;
  period_value?: number;
  period_label: string;
  period_start_date: string;
  period_end_date: string;
  metrics: KpiPeriodMetricSummary[];
  total: number;
  total_weight: string;
  total_score: string;
};

export type KpiBatchUpdateResponse = {
  success_count: number;
  failed_count: number;
  errors: string[];
};

// --- PnL attribution workbench (`/api/pnl-attribution/*`, V1-aligned numeric payloads) ---

export type VolumeRateAttributionItem = {
  category: string;
  category_type: string;
  level: number;
  current_scale: number;
  current_pnl: number;
  current_yield: number | null;
  previous_scale: number | null;
  previous_pnl: number | null;
  previous_yield: number | null;
  pnl_change: number | null;
  pnl_change_pct: number | null;
  volume_effect: number | null;
  rate_effect: number | null;
  interaction_effect: number | null;
  attrib_sum: number | null;
  recon_error: number | null;
  volume_contribution_pct: number | null;
  rate_contribution_pct: number | null;
};

export type VolumeRateAttributionPayload = {
  current_period: string;
  previous_period: string;
  compare_type: string;
  total_current_pnl: number;
  total_previous_pnl: number | null;
  total_pnl_change: number | null;
  total_volume_effect: number | null;
  total_rate_effect: number | null;
  total_interaction_effect: number | null;
  items: VolumeRateAttributionItem[];
  has_previous_data: boolean;
};

export type TPLMarketDataPoint = {
  period: string;
  period_label: string;
  tpl_fair_value_change: number;
  tpl_total_pnl: number;
  tpl_scale: number;
  treasury_10y: number | null;
  treasury_10y_change: number | null;
  dr007: number | null;
};

export type TPLMarketCorrelationPayload = {
  start_period: string;
  end_period: string;
  num_periods: number;
  correlation_coefficient: number | null;
  correlation_interpretation: string;
  total_tpl_fv_change: number;
  avg_treasury_10y_change: number | null;
  treasury_10y_total_change: number | null;
  data_points: TPLMarketDataPoint[];
  analysis_summary: string;
};

export type PnlCompositionItem = {
  category: string;
  category_type: string;
  level: number;
  total_pnl: number;
  interest_income: number;
  fair_value_change: number;
  capital_gain: number;
  other_income: number;
  interest_pct: number;
  fair_value_pct: number;
  capital_gain_pct: number;
  other_pct: number;
};

export type PnlCompositionTrendItem = {
  period: string;
  period_label: string;
  interest_income: number;
  fair_value_change: number;
  capital_gain: number;
  total_pnl: number;
};

export type PnlCompositionPayload = {
  report_period: string;
  report_date: string;
  total_pnl: number;
  total_interest_income: number;
  total_fair_value_change: number;
  total_capital_gain: number;
  total_other_income: number;
  interest_pct: number;
  fair_value_pct: number;
  capital_gain_pct: number;
  other_pct: number;
  items: PnlCompositionItem[];
  trend_data: PnlCompositionTrendItem[];
};

export type PnlAttributionAnalysisSummary = {
  report_date: string;
  primary_driver: "volume" | "rate" | "market" | "unknown";
  primary_driver_pct: number;
  key_findings: string[];
  tpl_market_aligned: boolean;
  tpl_market_note: string;
};

export type CarryRollDownItem = {
  category: string;
  category_type: string;
  market_value: number;
  weight: number;
  coupon_rate: number;
  ytm: number | null;
  funding_cost: number;
  carry: number;
  carry_pnl: number;
  duration: number;
  curve_slope: number | null;
  rolldown: number;
  rolldown_pnl: number;
  static_return: number;
  static_pnl: number;
};

export type CarryRollDownPayload = {
  report_date: string;
  total_market_value: number;
  portfolio_carry: number;
  portfolio_rolldown: number;
  portfolio_static_return: number;
  total_carry_pnl: number;
  total_rolldown_pnl: number;
  total_static_pnl: number;
  ftp_rate: number;
  items: CarryRollDownItem[];
};

export type SpreadAttributionItem = {
  category: string;
  category_type: string;
  market_value: number;
  duration: number;
  weight: number;
  yield_change: number | null;
  treasury_change: number | null;
  spread_change: number | null;
  treasury_effect: number;
  spread_effect: number;
  total_price_effect: number;
  treasury_contribution_pct: number;
  spread_contribution_pct: number;
};

export type SpreadAttributionPayload = {
  report_date: string;
  start_date: string;
  end_date: string;
  treasury_10y_start: number | null;
  treasury_10y_end: number | null;
  treasury_10y_change: number | null;
  total_market_value: number;
  portfolio_duration: number;
  total_treasury_effect: number;
  total_spread_effect: number;
  total_price_change: number;
  primary_driver: string;
  interpretation: string;
  items: SpreadAttributionItem[];
};

export type KRDAttributionBucket = {
  tenor: string;
  tenor_years: number;
  market_value: number;
  weight: number;
  bond_count: number;
  bucket_duration: number;
  krd: number;
  yield_change: number | null;
  duration_contribution: number;
  contribution_pct: number;
};

export type KRDAttributionPayload = {
  report_date: string;
  start_date: string;
  end_date: string;
  total_market_value: number;
  portfolio_duration: number;
  portfolio_dv01: number;
  total_duration_effect: number;
  curve_shift_type: string;
  curve_interpretation: string;
  buckets: KRDAttributionBucket[];
  max_contribution_tenor: string;
  max_contribution_value: number;
};

export type AdvancedAttributionSummary = {
  report_date: string;
  portfolio_carry: number;
  portfolio_rolldown: number;
  static_return_annualized: number;
  treasury_effect_total: number;
  spread_effect_total: number;
  spread_driver: string;
  max_krd_tenor: string;
  curve_shape_change: string;
  key_insights: string[];
};

export type CampisiAttributionItem = {
  category: string;
  market_value: number;
  weight: number;
  total_return: number;
  total_return_pct: number;
  income_return: number;
  income_return_pct: number;
  treasury_effect: number;
  treasury_effect_pct: number;
  spread_effect: number;
  spread_effect_pct: number;
  selection_effect: number;
  selection_effect_pct: number;
};

export type CampisiAttributionPayload = {
  report_date: string;
  period_start: string;
  period_end: string;
  num_days: number;
  total_market_value: number;
  total_return: number;
  total_return_pct: number;
  total_income: number;
  total_treasury_effect: number;
  total_spread_effect: number;
  total_selection_effect: number;
  income_contribution_pct: number;
  treasury_contribution_pct: number;
  spread_contribution_pct: number;
  selection_contribution_pct: number;
  primary_driver: string;
  interpretation: string;
  items: CampisiAttributionItem[];
};

// --- 现金流预测 / 久期缺口 (`/api/cashflow-projection`) ---
export type CashflowMonthlyBucket = {
  year_month: string;
  asset_inflow: string;
  liability_outflow: string;
  net_cashflow: string;
  cumulative_net: string;
};

export type CashflowMaturingAsset = {
  instrument_code: string;
  instrument_name: string;
  maturity_date: string;
  face_value: string;
  market_value: string;
  currency_code: string;
};

export type CashflowProjectionPayload = {
  report_date: string;
  duration_gap: string;
  asset_duration: string;
  liability_duration: string;
  equity_duration: string;
  rate_sensitivity_1bp: string;
  reinvestment_risk_12m: string;
  monthly_buckets: CashflowMonthlyBucket[];
  top_maturing_assets_12m: CashflowMaturingAsset[];
  warnings: string[];
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
    total_market_value: string;
    unrealized_pnl: string;
    weighted_ytm: string;
    weighted_duration: string;
    weighted_coupon: string;
    credit_spread_median: string;
    total_dv01: string;
    bond_count: number;
  };
  prev_kpis: {
    total_market_value: string;
    unrealized_pnl: string;
    weighted_ytm: string;
    weighted_duration: string;
    weighted_coupon: string;
    credit_spread_median: string;
    total_dv01: string;
    bond_count: number;
  } | null;
};

export type AssetStructureItem = {
  category: string;
  total_market_value: string;
  bond_count: number;
  percentage: string;
};

export type AssetStructurePayload = {
  report_date: string;
  group_by: string;
  items: AssetStructureItem[];
  total_market_value: string;
};

export type YieldDistributionItem = {
  yield_bucket: string;
  total_market_value: string;
  bond_count: number;
};

export type YieldDistributionPayload = {
  report_date: string;
  items: YieldDistributionItem[];
  weighted_ytm: string;
};

export type PortfolioComparisonItem = {
  portfolio_name: string;
  total_market_value: string;
  weighted_ytm: string;
  weighted_duration: string;
  total_dv01: string;
  bond_count: number;
};

export type PortfolioComparisonPayload = {
  report_date: string;
  items: PortfolioComparisonItem[];
};

export type SpreadAnalysisItem = {
  bond_type: string;
  median_yield: string;
  bond_count: number;
  total_market_value: string;
};

export type SpreadAnalysisPayload = {
  report_date: string;
  items: SpreadAnalysisItem[];
};

export type MaturityStructureItem = {
  maturity_bucket: string;
  total_market_value: string;
  bond_count: number;
  percentage: string;
};

export type MaturityStructurePayload = {
  report_date: string;
  items: MaturityStructureItem[];
  total_market_value: string;
};

export type IndustryDistItem = {
  industry_name: string;
  total_market_value: string;
  bond_count: number;
  percentage: string;
};

export type IndustryDistPayload = {
  report_date: string;
  items: IndustryDistItem[];
};

export type RiskIndicatorsPayload = {
  report_date: string;
  total_market_value: string;
  total_dv01: string;
  weighted_duration: string;
  credit_ratio: string;
  weighted_convexity: string;
  total_spread_dv01: string;
  reinvestment_ratio_1y: string;
};

// --- Cube 多维查询 (`/api/cube`) ---
export type CubeBasis = "formal" | "scenario" | "analytical";

export type CubeQueryRequest = {
  report_date: string;
  fact_table: string;
  measures: string[];
  dimensions?: string[];
  filters?: Record<string, string[]>;
  order_by?: string[];
  limit?: number;
  offset?: number;
  basis?: CubeBasis;
};

export type CubeDrillPath = {
  dimension: string;
  label: string;
  available_values: string[];
  current_filter: string[] | null;
};

export type CubeQueryPayload = {
  report_date: string;
  fact_table: string;
  measures: string[];
  dimensions: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
  drill_paths: CubeDrillPath[];
};

export type CubeDimensionsPayload = {
  fact_table: string;
  dimensions: string[];
  measures: string[];
  measure_fields: string[];
};

/** 后端 `CubeQueryResponse`：业务字段与 `result_meta` 同层，非 `ApiEnvelope`。 */
export type CubeQueryResult = CubeQueryPayload & { result_meta: ResultMeta };

// --- 负债结构分析（V1兼容 `/api/risk/buckets` 等原始 JSON，待后端统一 `ApiEnvelope`） ---

export type LiabilityBucketAmountItem = {
  bucket: string;
  /** 原币金额（元），V1 多为 number；迁移中可为 decimal string */
  amount?: number | string | null;
  amount_yi?: number | string | null;
};

export type LiabilityNameAmountItem = {
  name: string;
  amount?: number | string | null;
  amount_yi?: number | string | null;
};

export type LiabilityRiskBucketsPayload = {
  report_date: string;
  liabilities_structure: LiabilityNameAmountItem[];
  liabilities_term_buckets: LiabilityBucketAmountItem[];
  interbank_liabilities_structure?: LiabilityNameAmountItem[];
  interbank_liabilities_term_buckets?: LiabilityBucketAmountItem[];
  issued_liabilities_structure?: LiabilityNameAmountItem[];
  issued_liabilities_term_buckets?: LiabilityBucketAmountItem[];
};

export type LiabilityYieldKpi = {
  /** 小数口径，如 0.0255 = 2.55% */
  asset_yield: number | null;
  liability_cost: number | null;
  market_liability_cost: number | null;
  nim: number | null;
};

export type LiabilityYieldMetricsPayload = {
  report_date: string;
  kpi: LiabilityYieldKpi;
};

export type LiabilityCounterpartyItem = {
  name: string;
  value: number;
  type?: string;
  weighted_cost?: number | null;
  weighted_rate?: number | null;
};

export type LiabilityCounterpartyTypeSlice = {
  name: string;
  value: number;
};

export type LiabilityCounterpartyPayload = {
  report_date: string;
  total_value: number;
  top_10: LiabilityCounterpartyItem[];
  by_type: LiabilityCounterpartyTypeSlice[];
};

export type LiabMonthlyCounterpartyDetailItem = {
  name: string;
  avg_value: number;
  proportion: number;
  weighted_cost?: number | null;
  type?: string | null;
};

export type LiabMonthlyCategoryBreakdownItem = {
  category: string;
  avg_balance: number;
  proportion: number;
};

export type LiabMonthlyBucketItem = {
  bucket: string;
  avg_balance: number;
};

export type LiabMonthlyInstitutionTypeItem = {
  type: string;
  avg_value: number;
};

export type LiabilitiesMonthlyItem = {
  month: string;
  month_label: string;
  avg_total_liabilities: number;
  avg_interbank_liabilities: number;
  avg_issued_liabilities: number;
  avg_liability_cost: number | null;
  mom_change: number | null;
  mom_change_pct: number | null;
  counterparty_top10?: LiabMonthlyCounterpartyDetailItem[];
  by_institution_type?: LiabMonthlyInstitutionTypeItem[];
  structure_overview?: LiabMonthlyCategoryBreakdownItem[];
  term_buckets?: LiabMonthlyBucketItem[];
  interbank_by_type?: LiabMonthlyCategoryBreakdownItem[];
  interbank_term_buckets?: LiabMonthlyBucketItem[];
  issued_by_type?: LiabMonthlyCategoryBreakdownItem[];
  issued_term_buckets?: LiabMonthlyBucketItem[];
  counterparty_details?: LiabMonthlyCounterpartyDetailItem[];
  num_days: number;
};

export type LiabilitiesMonthlyPayload = {
  year: number;
  months: LiabilitiesMonthlyItem[];
  ytd_avg_total_liabilities: number;
  ytd_avg_liability_cost: number | null;
};

/** ADB 日均分析 — 与 V1 `/api/analysis/adb` 对齐 */
export type AdbSummary = {
  total_avg_assets: number;
  total_avg_liabilities: number;
  end_spot_assets: number;
  end_spot_liabilities: number;
};

export type AdbTrendItem = {
  date: string;
  daily_balance: number;
  moving_average_30d: number;
};

export type AdbBreakdownItem = {
  category: string;
  side: "Asset" | "Liability" | string;
  avg_balance: number;
};

export type AdbPayload = {
  summary: AdbSummary;
  trend: AdbTrendItem[];
  breakdown: AdbBreakdownItem[];
};

export type AdbComparisonRow = {
  category: string;
  spot: number;
  avg: number;
  deviation: number;
};

export type AdbComparisonBreakdownItem = {
  category: string;
  spot_balance: number;
  avg_balance: number;
  deviation?: number;
  proportion?: number | null;
  weighted_rate?: number | null;
};

export type AdbComparisonPayload = {
  report_date?: string;
  start_date: string;
  end_date: string;
  num_days: number;
  simulated: boolean;
  total_spot_assets?: number;
  total_avg_assets?: number;
  total_spot_liabilities?: number;
  total_avg_liabilities?: number;
  asset_yield?: number | null;
  liability_cost?: number | null;
  net_interest_margin?: number | null;
  assets_breakdown?: AdbComparisonBreakdownItem[];
  liabilities_breakdown?: AdbComparisonBreakdownItem[];
  assets: AdbComparisonRow[];
  liabilities: AdbComparisonRow[];
  detail?: string;
};

export type AdbMonthlyBreakdownItem = {
  category: string;
  side: string;
  avg_balance: number;
  proportion: number;
  weighted_rate: number | null;
};

export type AdbMonthlyItem = {
  month: string;
  month_label: string;
  avg_assets: number;
  avg_liabilities: number;
  end_spot_assets: number;
  end_spot_liabilities: number;
  assets_mom_change: number | null;
  liabilities_mom_change: number | null;
  asset_yield: number | null;
  liability_cost: number | null;
  net_interest_margin: number | null;
  breakdown_assets: AdbMonthlyBreakdownItem[];
  breakdown_liabilities: AdbMonthlyBreakdownItem[];
  num_days: number;
};

export type AdbMonthlyPayload = {
  year: number;
  months: AdbMonthlyItem[];
  ytd_avg_assets: number;
  ytd_avg_liabilities: number;
  ytd_asset_yield: number | null;
  ytd_liability_cost: number | null;
  ytd_net_interest_margin: number | null;
  unit?: string;
};

/** @deprecated 使用 AdbMonthlyItem — 保留别名供旧代码类型引用 */
export type LiabilityAdbMonthlyItem = AdbMonthlyItem;

/** @deprecated 使用 AdbMonthlyPayload */
export type LiabilityAdbMonthlyPayload = AdbMonthlyPayload;
