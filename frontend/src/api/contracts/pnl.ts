/** PnL by-business, PnL bridge, and product-category PnL contracts. */
import type { ApiQuality, Numeric } from "./core";

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

export type PnlV1DetailRow = {
  report_date: string;
  source: "FI" | "NonStd" | string;
  asset_code: string;
  bond_name: string;
  portfolio: string;
  asset_type: string;
  asset_class: string;
  market_value: string;
  interest_income: string;
  fair_value_change: string;
  capital_gain: string;
  total_pnl: string;
  source_version: string;
  trace_id: string;
};

export type PnlV1DataPayload = {
  report_date: string;
  source_tables: string[];
  rows: PnlV1DetailRow[];
};

export type PnlByBusinessRow = {
  report_date: string;
  business_type_primary: string;
  business_type: string;
  currency_basis: string;
  interest_income_514: string;
  fair_value_change_516: string;
  capital_gain_517: string;
  manual_adjustment: string;
  total_pnl: string;
  scale_amount: string;
  yield_pct: string | null;
  pnl_row_count: number;
  balance_row_count: number;
};

export type PnlByBusinessUntracedReason =
  | "position_absent_before_maturity"
  | "matured_before_or_on_report_date"
  | "never_seen_in_zqtz_asset_balance"
  | "same_day_balance_without_primary_type"
  | "same_day_balance_multiple_primary_types"
  | "unexpected_untraced";

export type PnlByBusinessUntracedBreakdownRow = {
  reason_code: PnlByBusinessUntracedReason;
  invest_type_std: string;
  pnl_row_count: number;
  total_pnl: string;
  abs_pnl: string;
  interest_income_514: string;
  fair_value_change_516: string;
  capital_gain_517: string;
  manual_adjustment: string;
};

export type PnlByBusinessPayload = {
  report_date: string;
  source_tables: string[];
  summary: import("../pnlByBusinessContracts").PnlByBusinessSummary;
  rows: PnlByBusinessRow[];
};

export type PnlByBusinessYtdItem = {
  row_key: string;
  sort_order: number;
  business_type: string;
  interest_income: string;
  fair_value_change: string;
  capital_gain: string;
  manual_adjustment: string;
  total_pnl: string;
  avg_balance: string;
  current_balance: string;
  balance_yield_pct: string | null;
  annualized_yield_pct: string | null;
  ftp_rate_pct: string;
  ftp_cost: string | null;
  ftp_net_pnl: string | null;
  ftp_net_annualized_yield_pct: string | null;
  source_kind?: string | null;
  source_note?: string | null;
  proportion: string | null;
  assets_count: number;
};

export type PnlByBusinessYtdUnallocatedReason =
  | "no_business_rule_match"
  | "detail_only_business_rule_match";

export type PnlByBusinessYtdUnallocatedBreakdownRow = {
  reason_code: PnlByBusinessYtdUnallocatedReason;
  source_kind: string;
  invest_type_std: string;
  accounting_basis: string;
  portfolio_name: string;
  cost_center: string;
  pnl_row_count: number;
  total_pnl: string;
  abs_pnl: string;
  sample_instrument_codes: string[];
};

export type PnlByBusinessYtdUnallocatedItem = {
  report_date: string;
  reason_code: PnlByBusinessYtdUnallocatedReason;
  source_kind: string;
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
  abs_pnl: string;
};

export type PnlByBusinessYtdSummary = {
  interest_income: string;
  fair_value_change: string;
  capital_gain: string;
  manual_adjustment: string;
  total_pnl: string;
  avg_balance: string;
  current_balance: string;
  annualized_yield_pct: string | null;
  ftp_rate_pct: string;
  ftp_cost: string | null;
  ftp_net_pnl: string | null;
  ftp_net_annualized_yield_pct: string | null;
  proportion: string | null;
  assets_count: number;
};

export type PnlByBusinessYtdPayload = {
  year: number;
  period_type: "yearly";
  period_label: string;
  period_start_date: string;
  period_end_date: string;
  total_pnl: string;
  coverage_days?: number;
  expected_days?: number;
  sample_filled?: boolean;
  sample_fill_method?: string | null;
  classified_parent_total_pnl?: string;
  summary?: PnlByBusinessYtdSummary;
  unallocated_pnl?: string;
  unallocated_abs_pnl?: string;
  unallocated_row_count?: number;
  reconciliation_delta?: string;
  unallocated_breakdown?: PnlByBusinessYtdUnallocatedBreakdownRow[];
  unallocated_items?: PnlByBusinessYtdUnallocatedItem[];
  source_tables: string[];
  items: PnlByBusinessYtdItem[];
};

export type PnlByBusinessManualAdjustmentRequest = {
  report_date: string;
  row_key: string;
  business_type?: string;
  operator: "ADD" | "DELTA" | "OVERRIDE";
  approval_status: "approved" | "pending" | "rejected";
  manual_adjustment: string;
  reason?: string;
};

export type PnlByBusinessManualAdjustmentPayload = {
  adjustment_id: string;
  event_type: string;
  created_at: string;
  stream: string;
  report_date: string;
  row_key: string;
  business_type: string;
  operator: string;
  approval_status: string;
  manual_adjustment: string;
  reason: string;
};

export type PnlByBusinessManualAdjustmentListPayload = {
  report_date: string;
  adjustment_count: number;
  event_total: number;
  adjustments: PnlByBusinessManualAdjustmentPayload[];
  events: PnlByBusinessManualAdjustmentPayload[];
};

export type PnlByBusinessPrecomputeStatus = {
  year: number;
  status: "idle" | "queued" | "running" | "completed" | "failed";
  serving_mode: "precomputed" | "live_fallback";
  is_current: boolean;
  run_id: string | null;
  report_date: string | null;
  latest_available_as_of_date?: string | null;
  source_version: string | null;
  rule_version: string | null;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  generated_at: string | null;
  record_count: number | null;
  error_message: string | null;
  failure_category: string | null;
  trigger_reason: string | null;
  retry_attempt: number;
  retry_policy: {
    max_retries: number;
    min_backoff_seconds: number;
  };
};

export type PnlByBusinessMonthlyItem = {
  row_key: string;
  sort_order: number;
  business_type: string;
  interest_income: string;
  fair_value_change: string;
  capital_gain: string;
  manual_adjustment: string;
  total_pnl: string;
  avg_balance: string;
  current_balance: string;
  annualized_yield_pct: string | null;
  ftp_rate_pct: string;
  ftp_cost: string | null;
  ftp_net_pnl: string | null;
  ftp_net_annualized_yield_pct: string | null;
  proportion: string | null;
  asset_count: number;
  source_note?: string | null;
};

export type PnlByBusinessMonthlySummary = {
  interest_income: string;
  fair_value_change: string;
  capital_gain: string;
  manual_adjustment: string;
  total_pnl: string;
  avg_balance: string;
  current_balance: string;
  annualized_yield_pct: string | null;
  ftp_rate_pct: string;
  ftp_cost: string | null;
  ftp_net_pnl: string | null;
  ftp_net_annualized_yield_pct: string | null;
  asset_count: number;
};

export type PnlByBusinessMonthlyBucket = {
  month_key: string;
  period_start_date: string;
  period_end_date: string;
  calendar_days: number;
  coverage_days?: number;
  expected_days?: number;
  sample_filled?: boolean;
  sample_fill_method?: string | null;
  source_total_pnl?: string;
  classified_parent_total_pnl?: string;
  unallocated_pnl?: string;
  unallocated_abs_pnl?: string;
  unallocated_row_count?: number;
  reconciliation_delta?: string;
  unallocated_breakdown?: PnlByBusinessYtdUnallocatedBreakdownRow[];
  unallocated_items?: PnlByBusinessYtdUnallocatedItem[];
  unallocated_evidence_complete?: boolean;
  summary: PnlByBusinessMonthlySummary;
  items: PnlByBusinessMonthlyItem[];
};

export type PnlByBusinessMonthlyChangeMetrics = {
  interest_income_delta: string | null;
  fair_value_change_delta: string | null;
  capital_gain_delta: string | null;
  manual_adjustment_delta: string | null;
  total_pnl_delta: string | null;
  avg_balance_delta: string | null;
  current_balance_delta: string | null;
  annualized_yield_delta_bp: string | null;
  ftp_cost_delta: string | null;
  ftp_net_pnl_delta: string | null;
  ftp_net_annualized_yield_delta_bp: string | null;
};

export type PnlByBusinessMonthlyChangeRow = PnlByBusinessMonthlyChangeMetrics & {
  row_key: string;
  sort_order: number;
  business_type: string;
  comparison_available: boolean;
  comparison_reason: "available" | "current_row_missing" | "previous_row_missing";
};

export type PnlByBusinessMonthlyManagementChange = {
  comparison_basis: "latest_month_vs_previous_calendar_month";
  comparison_scope: "requested_year";
  comparison_status:
    | "available"
    | "data_quality_warning"
    | "current_month_missing"
    | "previous_month_missing"
    | "previous_month_outside_request_scope"
    | "period_incomplete";
  comparison_available: boolean;
  current_month_key: string;
  previous_month_key: string;
  coverage_warning_months: string[];
  reconciliation_warning_months: string[];
  incomplete_months: string[];
  summary: PnlByBusinessMonthlyChangeMetrics | null;
  rows: PnlByBusinessMonthlyChangeRow[];
};

export type PnlByBusinessMonthlyPayload = {
  year: number;
  as_of_date: string;
  source_tables: string[];
  months: PnlByBusinessMonthlyBucket[];
  management_change: PnlByBusinessMonthlyManagementChange | null;
};

export type PnlByBusinessAnalysisDimension =
  | "monthly"
  | "portfolio"
  | "accounting"
  | "currency"
  | "cost_center"
  | "instrument"
  | "bond_bucket"
  | "bond_bucket_monthly";

export type PnlByBusinessAnalysisRow = {
  dimension_key: string;
  dimension_label: string;
  interest_income: string;
  fair_value_change: string;
  capital_gain: string;
  manual_adjustment: string;
  total_pnl: string;
  avg_balance: string;
  current_balance: string;
  annualized_yield_pct: string | null;
  ftp_rate_pct: string;
  ftp_cost: string | null;
  ftp_net_pnl: string | null;
  ftp_net_annualized_yield_pct: string | null;
  asset_count: number;
};

export type PnlByBusinessAnalysisPayload = {
  year: number;
  as_of_date: string;
  business_key: string | null;
  dimension: PnlByBusinessAnalysisDimension;
  period_start_date: string;
  period_end_date: string;
  coverage_days?: number;
  expected_days?: number;
  sample_filled?: boolean;
  sample_fill_method?: string | null;
  source_tables: string[];
  rows: PnlByBusinessAnalysisRow[];
  /** bond_bucket 专用：后端合并展示桶（金融债+其它债券 -> "other_merged" 其他）；加权年化收益为后端正式口径，前端直读不得复算。 */
  merged_bucket_rows?: PnlByBusinessAnalysisRow[];
};

/**
 * Candidate (non-formal) business-type insights — `status=candidate` per
 * `docs/metric_dictionary.md` (MTR-PNLBIZ-001~005). Mirrors backend
 * `backend/app/schemas/pnl.py::PnlByBusinessCandidateInsightsPayload` and siblings.
 * Analytical-only re-aggregation of `pnl.by_business_ytd` / `pnl.by_business_monthly`;
 * must not be treated as formal PnL truth.
 */
export type PnlByBusinessConcentrationRow = {
  row_key: string;
  business_type: string;
  avg_balance: string;
  share_pct: string;
};

export type PnlByBusinessConcentrationSummary = {
  year: number;
  as_of_date: string | null;
  currency_basis: "CNY_EQUIVALENT";
  population_basis: "YTD_AVG_BALANCE_PARENT_ROWS";
  total_avg_balance: string | null;
  hhi_pct: string | null;
  top_n: number;
  top_n_share_pct: string | null;
  rows: PnlByBusinessConcentrationRow[];
};

export type PnlByBusinessNegativeFtpPersistenceRow = {
  row_key: string;
  business_type: string;
  months_observed: number;
  negative_ftp_month_share_pct: string | null;
  negative_ftp_longest_streak_months: number | null;
  warning_triggered: boolean;
  eligible: boolean;
  status: "eligible" | "insufficient_observations";
};

export type PnlByBusinessNegativeFtpPersistenceSummary = {
  as_of_date: string;
  lookback_months: number;
  window_start_month: string | null;
  window_end_month: string | null;
  months_observed: number;
  negative_ftp_month_share_pct: string | null;
  negative_ftp_longest_streak_months: number | null;
  warning_threshold_pct: string;
  minimum_observed_months: number;
  warning_row_count: number;
  eligible: boolean;
  status: "eligible" | "insufficient_observations";
  rows: PnlByBusinessNegativeFtpPersistenceRow[];
};

export type PnlByBusinessShareDriftRow = {
  row_key: string;
  business_type: string;
  current_share_pct: string | null;
  baseline_share_pct: string | null;
  drift_pp: string | null;
  lifecycle_status: "continued" | "new" | "exited" | "unavailable";
};

export type PnlByBusinessShareDriftSummary = {
  year: number;
  as_of_date: string;
  baseline_year: number;
  baseline_as_of_date: string | null;
  baseline_available: boolean;
  available: boolean;
  availability_reason:
    | "baseline_missing"
    | "current_total_non_positive"
    | "baseline_total_non_positive"
    | null;
  comparison_basis: "PRIOR_YEAR_SAME_PERIOD_YTD_AVG_BALANCE_SHARE";
  rows: PnlByBusinessShareDriftRow[];
};

export type PnlByBusinessInsightsComponentEvidence = {
  component: string;
  requested_report_date: string | null;
  resolved_report_date: string | null;
  fallback_mode: "none" | "latest_snapshot";
  quality_flag: Exclude<ApiQuality, "missing">;
  vendor_status: "ok" | "vendor_stale" | "vendor_unavailable";
  basis: "formal" | "scenario" | "analytical" | "ledger" | null;
  formal_use_allowed: boolean | null;
  result_kind: string | null;
  trace_id: string | null;
  source_surface: string | null;
  source_version: string | null;
  rule_version: string | null;
  cache_version: string | null;
  tables_used: string[];
  formal_source_admitted: boolean;
  admission_reason:
    | "component_unavailable"
    | "unexpected_basis"
    | "unexpected_formal_use_allowed"
    | "unexpected_result_kind"
    | "missing_trace_id"
    | "unexpected_source_surface"
    | "missing_source_version"
    | "missing_rule_version"
    | "missing_cache_version"
    | "date_mismatch"
    | "fallback_used"
    | "unusable_quality"
    | "unusable_vendor"
    | "nonformal_source_tables"
    | "missing_required_source_tables"
    | null;
};

export type PnlByBusinessScaleYieldQuadrantKey =
  | "LARGE_HIGH"
  | "LARGE_LOW"
  | "SMALL_HIGH"
  | "SMALL_LOW";

export type PnlByBusinessScaleYieldQuadrantRow = {
  row_key: string;
  business_type: string;
  avg_balance: string;
  scale_share_pct: string;
  ftp_net_annualized_yield_pct: string;
  quadrant_key: PnlByBusinessScaleYieldQuadrantKey;
};

export type PnlByBusinessScaleYieldQuadrantSummary = {
  year: number;
  as_of_date: string;
  currency_basis: "CNY_EQUIVALENT";
  scale_basis: "YTD_AVG_BALANCE_SHARE";
  yield_basis: "FTP_NET_ANNUALIZED_YIELD_PCT";
  minimum_eligible_rows: number;
  eligible_row_count: number;
  total_avg_balance: string | null;
  available: boolean;
  scale_share_median_pct: string | null;
  ftp_net_annualized_yield_median_pct: string | null;
  rows: PnlByBusinessScaleYieldQuadrantRow[];
};

/**
 * `MTR-PNLBIZ-006`: formal reconciliation/data-quality diagnostic trend
 * (`backend/app/schemas/pnl.py::PnlByBusinessUntracedTrendRow`/`Summary`).
 * This is a DIFFERENT kind of candidate metric from the business-type rows
 * above: it reflects formal reconciliation-pipeline completeness, not
 * business contribution/drag. Do not present it alongside the business
 * analysis blocks without explicit visual/semantic separation.
 */
export type PnlByBusinessUntracedTrendRow = {
  report_date: string;
  untraced_row_count: number;
  total_row_count: number;
  untraced_share_pct: string | null;
};

export type PnlByBusinessUntracedTrendSummary = {
  as_of_date: string;
  lookback_months: number;
  available: boolean;
  availability_reason: "source_unavailable" | "no_observations" | null;
  rows: PnlByBusinessUntracedTrendRow[];
};

export type PnlByBusinessCandidateInsightsPayload = {
  result_version: "v2";
  year: number;
  as_of_date: string;
  baseline_requested_report_date: string;
  baseline_resolved_report_date: string | null;
  baseline_fallback_mode: "none" | "latest_snapshot" | "unavailable";
  component_evidence: PnlByBusinessInsightsComponentEvidence[];
  concentration: PnlByBusinessConcentrationSummary;
  negative_ftp_persistence: PnlByBusinessNegativeFtpPersistenceSummary;
  share_drift: PnlByBusinessShareDriftSummary;
  scale_yield_quadrant: PnlByBusinessScaleYieldQuadrantSummary;
  reconciliation_diagnostics: PnlByBusinessUntracedTrendSummary;
};

export type PnlByBusinessInsightsPayload = PnlByBusinessCandidateInsightsPayload;

export type PnlYearlyBusinessSummaryRow = {
  year: number;
  report_month: string;
  report_date: string;
  business_type_primary: string;
  business_type: string;
  currency_basis: string;
  total_pnl: string;
  scale_amount: string;
  yield_pct: string | null;
  pnl_row_count: number;
};

export type PnlYearlyBusinessSummaryPayload = {
  year: number;
  source_tables: string[];
  rows: PnlYearlyBusinessSummaryRow[];
};

export type PnlBridgeQuality = "ok" | "warning" | "error";

export type PnlBridgeRow = {
  report_date?: string;
  instrument_code: string;
  portfolio_name: string;
  cost_center?: string;
  accounting_basis: string;
  beginning_dirty_mv?: Numeric;
  ending_dirty_mv?: Numeric;
  carry: Numeric;
  roll_down: Numeric;
  treasury_curve: Numeric;
  credit_spread: Numeric;
  fx_translation: Numeric;
  realized_trading: Numeric;
  unrealized_fv: Numeric;
  manual_adjustment: Numeric;
  explained_pnl: Numeric;
  actual_pnl: Numeric;
  residual: Numeric;
  residual_ratio: Numeric | null;
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
  total_beginning_dirty_mv: Numeric;
  total_ending_dirty_mv: Numeric;
  total_carry: Numeric;
  total_roll_down: Numeric;
  total_treasury_curve: Numeric;
  total_credit_spread: Numeric;
  total_fx_translation: Numeric;
  total_realized_trading: Numeric;
  total_unrealized_fv: Numeric;
  total_manual_adjustment: Numeric;
  total_explained_pnl: Numeric;
  total_actual_pnl: Numeric;
  total_residual: Numeric;
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

export type ProductCategoryMetricValue = {
  raw: DecimalLike;
  display: string;
  unit: "percent";
};

export type ProductCategoryInterestSpreadPayload = {
  all_currency_asset_yield_pct: ProductCategoryMetricValue | null;
  all_currency_liability_yield_pct: ProductCategoryMetricValue | null;
  all_currency_spread_pct: ProductCategoryMetricValue | null;
  cny_asset_yield_pct: ProductCategoryMetricValue | null;
  cny_liability_yield_pct: ProductCategoryMetricValue | null;
  cny_spread_pct: ProductCategoryMetricValue | null;
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
  interest_spread: ProductCategoryInterestSpreadPayload | null;
  interest_earning_spread?: ProductCategoryInterestSpreadPayload | null;
};

export type ProductCategoryAttributionPoint = {
  report_date: string;
  days: number;
  scale: DecimalLike;
  yield_pct: DecimalLike | null;
  cash: DecimalLike;
  ftp: DecimalLike;
  business_net_income: DecimalLike;
};

export type ProductCategoryAttributionEffects = {
  day_effect: DecimalLike;
  scale_effect: DecimalLike;
  rate_effect: DecimalLike;
  ftp_effect: DecimalLike;
  direct_effect: DecimalLike;
  unexplained_effect: DecimalLike;
  explained_effect: DecimalLike;
  delta_business_net_income: DecimalLike;
  closure_error: DecimalLike;
};

export type ProductCategoryAttributionRow = {
  category_id: string;
  category_name: string;
  side: string;
  level: number;
  state: "complete" | "partial";
  current: ProductCategoryAttributionPoint | null;
  prior: ProductCategoryAttributionPoint | null;
  effects: ProductCategoryAttributionEffects;
};

export type ProductCategoryAttributionPayload = {
  report_date: string;
  compare: "mom" | "yoy";
  current_report_date: string;
  prior_report_date: string;
  state: "complete" | "incomplete";
  reason: string | null;
  rows: ProductCategoryAttributionRow[];
  totals: {
    asset_total: ProductCategoryAttributionRow;
    liability_total: ProductCategoryAttributionRow;
    grand_total: ProductCategoryAttributionRow;
  } | null;
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
