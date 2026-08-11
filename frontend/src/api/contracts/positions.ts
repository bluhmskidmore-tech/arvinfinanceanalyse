/** Positions module types (positions + KPI scoring contracts). */
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

export type RateCoverage = {
  policy: string;
  covered_amount: string;
  missing_amount: string;
  missing_count: number;
  coverage_ratio: string;
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
  ytm_rate_coverage?: RateCoverage | null;
  coupon_rate_coverage?: RateCoverage | null;
  /** CR10 集中度等指标；后端可按日返回 */
  cr10_ratio?: string | null;
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
  ytm_rate_coverage?: RateCoverage | null;
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
  ytm_rate_coverage?: RateCoverage | null;
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
