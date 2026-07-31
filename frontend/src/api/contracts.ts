/** Shared API surface: envelope, health, and cross-cutting enums. */
/**
 * Shared governed numeric primitive.
 * Mirrors backend ``backend/app/schemas/common_numeric.py::Numeric``.
 * See ``docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md`` § 3.
 */
export type NumericUnit = "yuan" | "pct" | "bp" | "ratio" | "years" | "count" | "dv01" | "yi";

export type Numeric = {
  raw: number | null;
  unit: NumericUnit;
  display: string;
  precision: number;
  sign_aware: boolean;
};

export type ApiBasis = "formal" | "scenario" | "analytical" | "ledger" | "mock";
export type PnlBasis = "formal" | "analytical";
export type ApiQuality = "ok" | "warning" | "error" | "stale" | "missing";

export type ResultNextDrill = string | Record<string, unknown>;

export type HealthCheckStatus = {
  ok: boolean;
  detail: string;
};

export type HealthResponse = {
  status: "ok" | "degraded" | "down";
  checks?: Record<string, HealthCheckStatus>;
};

/** GET /health/live 与 GET /health — 后端返回的最简 `{ status: string }` 载荷。 */
export type HealthStatusResponse = {
  status: string;
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
  cache_key?: string | null;
  quality_flag: ApiQuality;
  vendor_status: "ok" | "vendor_stale" | "vendor_unavailable";
  fallback_mode: "none" | "latest_snapshot";
  source_surface?: string | null;
  scenario_flag: boolean;
  requested_report_date?: string | null;
  resolved_report_date?: string | null;
  as_of_date?: string | null;
  date_basis?: string | null;
  fallback_date?: string | null;
  generated_at: string;
  tables_used?: string[];
  filters_applied?: Record<string, unknown>;
  evidence_rows?: number;
  next_drill?: ResultNextDrill[];
};

export type ApiEnvelope<T> = {
  result_meta: ResultMeta;
  result: T;
  /** 可选：标识本响应依赖的正式事实表族（如 bond_analytics vs balance_analysis）。 */
  data_source?: string;
};

/** `/ui/home/*`, `/ui/pnl/attribution`, `/ui/risk/overview`, `/ui/home/alerts` payloads. */
export type ExecutiveMetric = {
  id: string;
  label: string;
  caliber_label?: string | null;
  value: Numeric;
  delta: Numeric;
  tone: "positive" | "neutral" | "warning" | "negative";
  detail: string;
  /** 后端契约字段；旧 mock 可能缺省，由 adapter 归一为 null */
  history?: number[] | null;
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
  amount: Numeric;
  tone: "positive" | "neutral" | "negative";
};

export type PnlAttributionPayload = {
  title: string;
  total: Numeric;
  segments: AttributionSegment[];
};

export type VerdictReason = {
  label: string;
  value: string;
  detail: string;
  tone: "positive" | "neutral" | "warning" | "negative";
};

export type VerdictSuggestion = { text: string; link: string | null };

export type VerdictPayload = {
  conclusion: string;
  tone: "positive" | "neutral" | "warning" | "negative";
  reasons: VerdictReason[];
  suggestions: VerdictSuggestion[];
};

/** 与 /product-category-pnl「汇总视图」（ytd）页脚口径一致的首屏摘要（后端算、前端只展示）。 */
export type ProductCategoryYtdHeadlinePayload = {
  view: "ytd";
  summary_pnl: Numeric;
  summary_pnl_detail: string;
  operating_income: Numeric;
  operating_income_detail: string;
  intermediate_business_income: Numeric;
  intermediate_business_income_detail: string;
};

/** 与 /product-category-pnl「月度视图」（monthly）页脚口径一致的首屏摘要（后端算、前端只展示）。 */
export type ProductCategoryMonthlyHeadlinePayload = {
  view: "monthly";
  monthly_income: Numeric;
  monthly_income_detail: string;
};

export type HomeSnapshotPayload = {
  report_date: string;
  mode: "strict" | "partial";
  source_surface: "executive_analytical";
  overview: OverviewPayload;
  attribution: PnlAttributionPayload;
  domains_missing: string[];
  domains_effective_date: Record<string, string>;
  verdict?: VerdictPayload | null;
  product_category_ytd?: ProductCategoryYtdHeadlinePayload | null;
  product_category_monthly?: ProductCategoryMonthlyHeadlinePayload | null;
};

export type HomeResearchReportItem = {
  id: string;
  title: string;
  category: string;
  published_at: string;
  link: string | null;
  source: string;
  institution?: string | null;
  source_status: "ready" | "empty" | "stale";
  summary?: string | null;
};

export type HomeResearchReportsPayload = {
  report_date: string;
  source_status: "ready" | "empty" | "stale";
  items: HomeResearchReportItem[];
  warnings: string[];
};

export type HomeIncomeTrendPointSourceStatus = "ready" | "partial";
export type HomeIncomeTrendSourceStatus = HomeIncomeTrendPointSourceStatus | "empty";

export type HomeIncomeTrendPoint = {
  date: string;
  portfolio_pnl: Numeric;
  benchmark_pnl: Numeric;
  excess_pnl: Numeric;
  basis: "product_category_pnl_monthly";
  source_status: HomeIncomeTrendPointSourceStatus;
};

export type HomeIncomeTrendPayload = {
  report_date: string;
  window: number;
  source_status: HomeIncomeTrendSourceStatus;
  points: HomeIncomeTrendPoint[];
  missing_components: string[];
  warnings: string[];
};

export type HomeMacroSourceStatus = "ready" | "partial" | "stale" | "fallback" | "source_pending" | "error";
export type HomeMacroDisplayUnit = "index" | "pct" | "persons";
export type HomeMacroChangeUnit = "index_point" | "pct_point" | "persons" | "bp";
export type HomeMacroDirection = "up" | "down" | "flat" | "unavailable";

export type HomeMacroReleaseContextMetric = {
  metric_key: string;
  label: string;
  actual_value: number | null;
  previous_value: number | null;
  change_value: number | null;
  display_unit: HomeMacroDisplayUnit;
  change_unit: HomeMacroChangeUnit;
  precision: number;
  direction: HomeMacroDirection;
};

export type HomeMacroReleaseContextHistoryItem = {
  indicator_key: string;
  title: string;
  region: "CN" | "US";
  category: "activity" | "inflation" | "growth" | "employment" | "monetary_policy";
  importance: "high" | "medium" | "low";
  observation_date: string | null;
  previous_observation_date: string | null;
  reference_period: string | null;
  previous_reference_period: string | null;
  release_date: string | null;
  source_status: HomeMacroSourceStatus;
  source_name: string | null;
  metrics: HomeMacroReleaseContextMetric[];
  notes: string[];
};

export type HomeMacroReleaseContextCoverage = {
  configured_count: number;
  ready_count: number;
  partial_count: number;
  stale_count: number;
  fallback_count: number;
  source_pending_count: number;
  error_count: number;
};

export type HomeMacroReleaseContextPayload = {
  window_start_date: string;
  window_end_date: string;
  history_items: HomeMacroReleaseContextHistoryItem[];
  coverage: HomeMacroReleaseContextCoverage;
  warnings: string[];
};

export type GetHomeMacroReleaseContextOptions = {
  startDate: string;
  endDate: string;
  historyLimit?: number;
};

export type GetHomeSnapshotOptions = {
  reportDate?: string;
  allowPartial?: boolean;
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
  row_count?: number;
  vendor_version?: string;
  source_version?: string;
  cache_key?: string;
  warnings?: string[];
  warning_code?: string;
  quality_flag?: string;
  choice_macro?: ChoiceMacroRefreshPayload;
  public_cross_asset?: ChoiceMacroRefreshPayload;
  tushare_ncd_shibor?: ChoiceMacroRefreshPayload;
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
  theme?: string | null;
  tags?: string[];
  refresh_tier?: "stable" | "fallback" | "isolated" | null;
  fetch_mode?: "date_slice" | "latest" | null;
  fetch_granularity?: "batch" | "single" | null;
  policy_note?: string | null;
};

export type MacroVendorPayload = {
  read_target: "duckdb";
  series: MacroVendorSeries[];
};

export type MarketDataCatalogPayload = MacroVendorPayload;

export type ChoiceMacroLatestPoint = {
  series_id: string;
  series_name: string;
  trade_date: string;
  value_numeric: number;
  frequency?: string;
  unit: string;
  source_version: string;
  vendor_version: string;
  vendor_name?: string | null;
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
  derived_spreads?: Partial<Record<string, number | null>>;
};

export type MarketDataBondFuturesRankingRow = {
  trade_date: string;
  contract: string;
  product_code: string;
  exchange: string;
  member_name: string;
  source_vendor: string;
  source_row_no: number | null;
  volume: number | null;
  volume_change: number | null;
  long_holding: number | null;
  long_change: number | null;
  short_holding: number | null;
  short_change: number | null;
  source_version: string | null;
  vendor_version: string | null;
  rule_version: string | null;
};

export type MarketDataBondFuturesRankingsPayload = {
  read_target: "duckdb";
  as_of_date: string | null;
  requested_trade_date: string | null;
  contract: string;
  rows: MarketDataBondFuturesRankingRow[];
  warnings: string[];
};

export type MarketDataCoverageStatus =
  | "ready"
  | "empty"
  | "warning"
  | "stale"
  | "error"
  | "source_pending"
  | "proxy_only"
  | "deferred";

export type MarketDataCoverageSection = {
  key: string;
  label: string;
  status: MarketDataCoverageStatus;
  basis: "formal" | "analytical";
  formal_use_allowed: boolean;
  quality_flag: ApiQuality;
  fallback_mode: "none" | "latest_snapshot";
  vendor_status: "ok" | "vendor_stale" | "vendor_unavailable";
  row_count?: number | null;
  series_count?: number | null;
  group_count?: number | null;
  latest_trade_date?: string | null;
  as_of_date?: string | null;
  source_pending: boolean;
  proxy_only: boolean;
  message: string;
};

export type MarketDataCoverageHeadline = {
  readiness_label: string;
  formal_fragment_ready: boolean;
  formal_use_allowed: boolean;
  analytical_warning_count: number;
  source_pending_count: number;
  proxy_only_count: number;
};

export type MarketDataCoverageAction = {
  key: string;
  label: string;
  severity: "info" | "warning" | "error";
  target_anchor: string | null;
};

export type MarketDataCoverageSummaryPayload = {
  read_target: "duckdb";
  as_of_date: string | null;
  generated_at: string;
  headline: MarketDataCoverageHeadline;
  sections: MarketDataCoverageSection[];
  actions: MarketDataCoverageAction[];
};

export type MacroBondLinkageEnvironmentFactor = Record<string, unknown>;

export type MacroBondLinkageCompositeContribution = {
  component: string;
  raw_score: number;
  weight: number;
  signed_contribution: number;
};

export type MacroBondLinkageEnvironmentScore = {
  report_date: string;
  rate_direction: string;
  rate_direction_score: number;
  liquidity_score: number;
  growth_score: number;
  inflation_score: number;
  composite_score: number;
  composite_contributions?: MacroBondLinkageCompositeContribution[];
  composite_formula_version?: string;
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
  alignment_mode?: "conservative" | "market_timing" | null;
  sample_size?: number | null;
  winsorized?: boolean;
  zscore_applied?: boolean;
  lead_lag_confidence?: number | null;
  effective_observation_span_days?: number | null;
};

export type MacroBondLinkageMethodVariant = {
  method_meta: {
    variant: "conservative" | "market_timing";
    description?: string | null;
    warnings?: string[];
  };
  top_correlations: MacroBondLinkageTopCorrelation[];
};

export type MacroBondLinkageMethodVariants = {
  conservative: MacroBondLinkageMethodVariant;
  market_timing: MacroBondLinkageMethodVariant;
};

export type MacroBondResearchView = {
  key: string;
  stance: string;
  confidence: string;
  summary: string;
  affected_targets?: string[];
  evidence?: string[];
  status: "ready" | "pending_signal";
};

export type MacroBondTransmissionAxis = {
  axis_key: string;
  status: "ready" | "pending_signal";
  stance: string;
  summary: string;
  impacted_views?: string[];
  required_series_ids?: string[];
  warnings?: string[];
};

export type MacroBondLinkagePayload = {
  report_date: string;
  environment_score: Partial<MacroBondLinkageEnvironmentScore>;
  portfolio_impact: Partial<MacroBondLinkagePortfolioImpact>;
  top_correlations: MacroBondLinkageTopCorrelation[];
  method_variants?: MacroBondLinkageMethodVariants;
  spread_tenor_correlations?: MacroBondLinkageTopCorrelation[];
  research_views?: MacroBondResearchView[];
  transmission_axes?: MacroBondTransmissionAxis[];
  warnings: string[];
  computed_at: string;
};

export type FxAnalyticalGroupKey = "middle_rate" | "fx_index" | "fx_swap_curve" | "fx_event_calendar";

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

export type FxAnalyticalEventRow = {
  group_key: "fx_event_calendar";
  event_id: string;
  event_date: string;
  event_time: string | null;
  currency: string | null;
  country: string | null;
  event: string;
  value: string | null;
  pre_value: string | null;
  fore_value: string | null;
  source_version: string;
  vendor_version: string;
  quality_flag?: ApiQuality;
};

export type FxAnalyticalGroup = {
  group_key: FxAnalyticalGroupKey;
  title: string;
  description: string;
  series: FxAnalyticalSeriesPoint[];
  events?: FxAnalyticalEventRow[];
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
  display_text?: string | null;
  payload_json: string | null;
};

export type ChoiceNewsCompareRow = {
  event_family?: string;
  factor_tags?: string[];
  event_count?: number;
  source_event_ids?: string[];
  summary?: string;
  review_reason?: string;
  conflict_type?: string;
  families?: Array<{ event_family: string; source_event_ids: string[] }>;
};

export type ChoiceNewsCandidateScenario = {
  event_family: string;
  match_rule: string;
  factor_tags: string[];
  scenario_template_id: string;
  default_shocks: string[];
  rule_version: string;
  human_review_required: boolean;
  mapping_rule_id: string;
  source_event_ids: string[];
};

export type ChoiceNewsComparePayload = {
  basis: "analytical";
  rule_version: string;
  same_direction: ChoiceNewsCompareRow[];
  conflicting: ChoiceNewsCompareRow[];
  review_needed: ChoiceNewsCompareRow[];
  candidate_scenarios: ChoiceNewsCandidateScenario[];
};

export type ChoiceNewsEventsPayload = {
  total_rows: number;
  limit: number;
  offset: number;
  as_of_date: string | null;
  excluded_future_rows: number;
  stock_code?: string | null;
  stock_filter_mode?: string | null;
  stock_filter_tokens?: string[];
  compare?: ChoiceNewsComparePayload;
  payload_json_included?: boolean;
  events: ChoiceNewsEvent[];
};

/** 与 `GET /ui/news/choice-events/latest` 返回的 `result.events[]` 单行一致（后端 payload_rows）。 */
export type ChoiceNewsLatestEvent = ChoiceNewsEvent;

/** 与 `GET /ui/news/choice-events/latest` 的 `result` 对象一致。 */
export type ChoiceNewsLatestPayload = ChoiceNewsEventsPayload;

export type NcdFundingProxyRow = {
  row_key: string;
  label: string;
  "1M": number | null;
  "3M": number | null;
  "6M": number | null;
  "9M": number | null;
  "1Y": number | null;
  quote_count: number | null;
};

export type FormalNcdMatrixStatus = {
  status: string;
  required_shape: string;
  current_proxy_basis: string;
  choice_status: string;
  tushare_status: string;
  missing_requirements: string[];
};

export type NcdFundingProxyPayload = {
  as_of_date: string | null;
  proxy_label: string;
  is_actual_ncd_matrix: boolean;
  formal_ncd_matrix_status?: FormalNcdMatrixStatus | null;
  rows: NcdFundingProxyRow[];
  warnings: string[];
};

export type TushareMoneySupplyRow = {
  month: string;
  m0: number | null;
  m0_yoy: number | null;
  m0_mom: number | null;
  m1: number | null;
  m1_yoy: number | null;
  m1_mom: number | null;
  m2: number | null;
  m2_yoy: number | null;
  m2_mom: number | null;
};

export type TushareEcoCalEventRow = {
  event_id: string;
  event_date: string;
  event_time: string | null;
  currency: string | null;
  country: string | null;
  event: string;
  value: string | null;
  pre_value: string | null;
  fore_value: string | null;
};

export type TushareSupplementPayload = {
  money_supply_rows: TushareMoneySupplyRow[];
  eco_cal_rows: TushareEcoCalEventRow[];
  money_supply_total_count?: number;
  money_supply_truncated?: boolean;
  eco_cal_total_count?: number;
  eco_cal_truncated?: boolean;
  warnings: string[];
};

export type LivermoreMarketGateState =
  | "OFF"
  | "WARM"
  | "HOT"
  | "OVERHEAT"
  | "PENDING_DATA"
  | "NO_DATA"
  | "STALE";

export type LivermoreConditionStatus = "pass" | "fail" | "missing" | "stale";
export type LivermoreRuleReadinessKey =
  | "market_gate"
  | "sector_rank"
  | "stock_pivot"
  | "risk_exit";
export type LivermoreRuleReadinessStatus =
  | "ready"
  | "partial"
  | "missing"
  | "blocked"
  | "stale";
export type LivermoreDiagnosticSeverity = "info" | "warning" | "error";
export type ExternalDataFreshnessTier = "fresh" | "stale" | "expired" | "unknown";
export type LivermoreDataGapStatus = "missing" | "partial" | "stale" | "ready" | "look_ahead";
export type LivermoreOutputKey =
  | "market_gate"
  | "sector_rank"
  | "stock_candidates"
  | "uptrend_momentum_candidates"
  | "fresh_trend_watchlist"
  | "mean_reversion_candidates"
  | "factor_screen_candidates"
  | "theme_breakout"
  | "hybrid_fusion"
  | "risk_exit";

export type LivermoreMarketCondition = {
  key: string;
  label: string;
  status: LivermoreConditionStatus;
  evidence: string;
  source_series_id?: string | null;
};

export type LivermoreMarketGateMacroContextStatus =
  | "ready"
  | "missing"
  | "expired"
  | "look_ahead";

export type LivermoreMarketGateCycleState =
  | "recession"
  | "contraction"
  | "neutral"
  | "expansion";

export type LivermoreMarketGateMacroComponent = {
  input_family: string;
  input: string;
  cadence: string;
  business_date: string;
  age_days?: number | null;
  tier?: ExternalDataFreshnessTier | string | null;
};

/** Market-gate macro cycle disclosure (rv_market_gate_macro_overlay_v1). Not signal confluence macro_context. */
export type LivermoreMarketGateMacroContext = {
  status: LivermoreMarketGateMacroContextStatus | string;
  cycle_state?: LivermoreMarketGateCycleState | string | null;
  macro_score?: number | null;
  gate_as_of_date?: string | null;
  data_date?: string | null;
  lag_days?: number | null;
  max_component_lag_days?: number | null;
  components?: LivermoreMarketGateMacroComponent[];
  evidence?: string | null;
  formula_version?: string | null;
};

export type LivermoreMarketGateMacroOverlay = {
  applied: boolean;
  exposure_cap?: number | null;
  exposure_raw: number;
  exposure_adjusted: number;
  rule?: string | null;
  formula_version?: string | null;
};

export type LivermoreMarketGate = {
  state: LivermoreMarketGateState;
  exposure: number;
  passed_conditions: number;
  available_conditions: number;
  required_conditions: number;
  conditions: LivermoreMarketCondition[];
  /** Pre-overlay exposure; equals exposure when macro inputs are missing. */
  exposure_raw?: number;
  formula_version?: string | null;
  /** Gate-level macro cycle disclosure; distinct from signal confluence macro_context. */
  macro_context?: LivermoreMarketGateMacroContext | null;
  macro_overlay?: LivermoreMarketGateMacroOverlay | null;
};

export type LivermoreRuleReadiness = {
  key: LivermoreRuleReadinessKey;
  title: string;
  status: LivermoreRuleReadinessStatus;
  summary: string;
  required_inputs: string[];
  missing_inputs: string[];
};

export type LivermoreDiagnostic = {
  severity: LivermoreDiagnosticSeverity;
  code: string;
  message: string;
  input_family?: string | null;
};

export type LivermoreDataGap = {
  input_family: string;
  status: LivermoreDataGapStatus;
  evidence: string;
  input?: string | null;
  business_date?: string | null;
  age_days?: number | null;
  tier?: ExternalDataFreshnessTier | null;
};

export type StockAnalysisWorkbenchDataGap = LivermoreDataGap & {
  blocks_review: boolean;
};

export type ExternalDataWatermarkEntry = {
  series_id: string;
  series_name: string;
  vendor_name: string;
  source_family: string;
  domain: "macro" | "news" | "yield_curve" | "fx" | "other";
  frequency?: string | null;
  unit?: string | null;
  refresh_tier?: string | null;
  fetch_mode?: string | null;
  relation_name?: string | null;
  date_column?: string | null;
  row_count: number;
  latest_business_date?: string | null;
  latest_loaded_at?: string | null;
  age_days?: number | null;
  freshness_tier?: ExternalDataFreshnessTier | null;
  data_status: "available" | "no_data" | "unavailable";
  error_message?: string | null;
};

export type ExternalDataWatermarkSummary = {
  catalog_count: number;
  available_count: number;
  no_data_count: number;
  unavailable_count: number;
  oldest_available_business_date?: string | null;
  newest_available_business_date?: string | null;
  last_successful_ingest?: string | null;
};

export type ExternalDataWatermarkLedger = {
  summary: ExternalDataWatermarkSummary;
  entries: ExternalDataWatermarkEntry[];
};

export type LivermoreUnsupportedOutput = {
  key: LivermoreOutputKey;
  reason: string;
};

export type LivermoreModuleState = {
  key: LivermoreOutputKey;
  state: "ready" | "degraded" | "partial" | "blocked" | "unsupported";
  render_mode: "primary" | "evidence_only" | "hidden";
  source_date: string | null;
  lag_days: number | null;
  threshold_days: number | null;
  coverage_count?: number | null;
  coverage_denominator?: number | null;
  coverage_ratio?: number | null;
  coverage_threshold?: number | null;
  reasons: string[];
  evidence_scope: "primary" | "detail" | "detail_only" | "none";
  excludes_from_primary: boolean;
};

export type LivermoreSectorRankLeaderConstituent = {
  rank: number;
  stock_code: string;
  stock_name: string;
  pctchange: number;
  turn: number;
  amplitude: number;
};

export type LivermoreSectorRankItem = {
  rank: number;
  sector_code: string;
  sector_name: string;
  score: number;
  avg_pctchange: number;
  avg_turn: number;
  avg_amplitude: number;
  constituent_count: number;
  leader_constituents?: LivermoreSectorRankLeaderConstituent[];
};

export type LivermoreSectorRankPayload = {
  as_of_date: string;
  formula_version: string;
  is_provisional: boolean;
  formula_status?: "review_pending" | "signed_off" | string;
  formula_note?: string | null;
  formula_component_weights?: Record<string, number>;
  sector_count: number;
  excluded_constituent_count: number;
  excluded_sector_count: number;
  leader_constituent_limit?: number;
  leader_constituent_method?: string;
  items: LivermoreSectorRankItem[];
};

export type LivermoreStockCandidateItem = {
  rank: number;
  stock_code: string;
  stock_name: string;
  sector_code: string;
  sector_name: string;
  sector_rank: number;
  close: number;
  breakout_level: number;
  ema10?: number | null;
  ma20: number;
  ma60: number;
  ma120: number;
  close_strength: number;
  gap_norm: number;
  breakout_extension_norm?: number | null;
  abnormal_turnover: number;
  selection_policy?: string | null;
  pe?: number | null;
  pb?: number | null;
  ps?: number | null;
  roe?: number | null;
  gross_margin?: number | null;
  three_month_return?: number | null;
  twelve_month_return?: number | null;
  volatility?: number | null;
  dividend_yield?: number | null;
  factor_score?: number | null;
  factor_overlay_rank?: number | null;
};

export type LivermoreStockCandidatesPayload = {
  as_of_date: string;
  formula_version: string;
  market_state: LivermoreMarketGateState;
  input_stock_count: number;
  candidate_count: number;
  excluded_stock_count: number;
  insufficient_history_count: number;
  selection_policy?: string | null;
  fundamental_overlay?: {
    status?: string | null;
    input_candidate_count?: number | null;
    valid_factor_count?: number | null;
    selected_factor_count?: number | null;
    top_fraction?: number | null;
    factor_missing_count?: number | null;
  };
  items: LivermoreStockCandidateItem[];
};

export type LivermoreThemeBreakoutStockItem = {
  stock_code: string;
  stock_name: string;
  sector_code: string;
  sector_name: string;
  sector_rank: number;
  open: number;
  high: number;
  low: number;
  close: number;
  pctchange: number;
  turn: number;
  amplitude: number;
  close_strength: number;
  closed_up_limit: boolean;
  strong: boolean;
  concept_source_kind?: "real_concept" | "tushare_current_overlay" | "proxy" | string;
};

export type LivermoreThemeBreakoutItem = {
  rank: number;
  as_of_date: string;
  theme_key: string;
  theme_name: string;
  source_kind?: "real_concept" | "proxy" | string;
  parent_sector_code: string;
  parent_sector_name: string;
  parent_sector_rank: number;
  member_count: number;
  advance_count: number;
  advance_ratio: number;
  strong_stock_count: number;
  limit_stock_count: number;
  avg_pctchange: number;
  avg_turn: number;
  avg_amplitude: number;
  movement_event_count?: number;
  latest_event_title?: string;
  latest_event_time?: string;
  observation_only: boolean;
  reason: string;
  items: LivermoreThemeBreakoutStockItem[];
};

export type LivermoreThemeEvidenceStatus =
  | "catalog_unconfirmed"
  | "table_missing"
  | "landed_no_rows"
  | "matched_rows"
  | string;

export type LivermoreThemeEvidenceInputState = {
  input_family?: string;
  status?: LivermoreThemeEvidenceStatus;
  state?: LivermoreThemeEvidenceStatus;
  table?: string;
  table_name?: string;
  row_count?: number;
  date_row_count?: number;
  matched_row_count?: number;
  member_count?: number;
  concept_source_kind?: "real_concept" | "tushare_current_overlay" | "proxy" | string | null;
  overlay_status?: string | null;
  overlay_reason?: string | null;
  source_kind?: "tushare_ths_current_overlay" | string | null;
  source_version?: string | null;
  vendor_version?: string | null;
  run_id?: string | null;
  point_in_time?: boolean | null;
  historical_use_allowed?: boolean | null;
  message?: string;
};

export type LivermoreThemeEvidenceState = {
  concept_membership?: LivermoreThemeEvidenceInputState;
  intraday_movement?: LivermoreThemeEvidenceInputState;
  inputs?: LivermoreThemeEvidenceInputState[];
  summary?: string;
};

export type LivermoreThemeBreakoutReviewItem = Omit<LivermoreThemeBreakoutItem, "rank"> & {
  rank?: number;
  failed_gates?: string[];
  failed_gate_codes?: string[];
};

export type LivermoreThemeBreakoutPayload = {
  as_of_date: string;
  formula_version: string;
  is_proxy: boolean;
  theme_count: number;
  evidence_state?: LivermoreThemeEvidenceState;
  items: LivermoreThemeBreakoutItem[];
  review_items?: LivermoreThemeBreakoutReviewItem[];
};

export type LivermoreRiskExitItem = {
  stock_code: string;
  stock_name: string;
  reason: string;
  entry_cost: number | null;
  entry_cost_available?: boolean;
  bars_since_entry: number;
  latest_close: number;
  latest_ema10: number;
  prior_close: number;
  prior_ema10: number;
};

export type LivermoreRiskExitWatchItem = {
  stock_code: string;
  stock_name: string;
  entry_cost: number | null;
  entry_cost_available?: boolean;
  bars_since_entry: number;
  latest_close: number;
  latest_ema10: number;
  prior_close: number;
  prior_ema10: number;
  exit_watch_price: number;
  triggered: boolean;
};

export type LivermoreRiskExitPayload = {
  as_of_date: string;
  formula_version: string;
  position_count: number;
  signal_count: number;
  excluded_position_count: number;
  insufficient_history_count: number;
  items: LivermoreRiskExitItem[];
  watch_items?: LivermoreRiskExitWatchItem[];
};

export type MeanReversionCandidateItem = {
  rank: number;
  stock_code: string;
  stock_name: string;
  sector_code: string;
  sector_name: string;
  close: number;
  drawdown_20d: number;
  drawdown_60d: number;
  ma5: number;
  ma10: number;
  close_strength: number;
  vol_ratio: number;
  score: number;
};

export type MeanReversionCandidatesPayload = {
  as_of_date: string;
  formula_version: string;
  market_state: LivermoreMarketGateState;
  input_stock_count: number;
  candidate_count: number;
  excluded_stock_count: number;
  insufficient_history_count: number;
  items: MeanReversionCandidateItem[];
};

export type UptrendMomentumCandidateItem = {
  rank: number;
  stock_code: string;
  stock_name: string;
  sector_code: string;
  sector_name: string;
  close: number;
  ma20: number;
  ma60: number;
  ma120: number;
  return_20d: number;
  return_60d: number;
  return_120d: number;
  close_to_ma20: number;
  amount_ratio: number;
  pctchange: number | null;
  turn: number | null;
  amplitude: number | null;
  score: number;
};

export type UptrendMomentumCandidatesPayload = {
  as_of_date: string;
  formula_version: string;
  market_state: LivermoreMarketGateState;
  observation_only?: boolean;
  input_stock_count: number;
  candidate_count: number;
  excluded_stock_count: number;
  insufficient_history_count: number;
  items: UptrendMomentumCandidateItem[];
};

export type FreshTrendWatchlistCandidateItem = {
  rank: number;
  stock_code: string;
  stock_name: string;
  sector_code: string;
  sector_name: string;
  concepts: string[];
  close: number;
  ma20: number;
  ma60: number;
  ma120: number;
  return_20d: number;
  return_60d: number;
  return_120d: number;
  close_to_ma20: number;
  amount_ratio: number;
  pctchange: number | null;
  turn: number | null;
  amplitude: number | null;
  hlimitedays: number | null;
  score: number;
};

export type FreshTrendWatchlistPayload = {
  as_of_date: string;
  formula_version: string;
  market_state: LivermoreMarketGateState;
  observation_only?: boolean;
  input_stock_count: number;
  candidate_count: number;
  excluded_stock_count: number;
  insufficient_history_count: number;
  items: FreshTrendWatchlistCandidateItem[];
};

export type FactorScreenCandidateItem = {
  rank: number;
  stock_code: string;
  stock_name: string;
  sector_code: string;
  sector_name: string;
  industry: string;
  score: number;
  pe: number | null;
  pb: number | null;
  roe: number | null;
  gross_margin: number | null;
  three_month_return: number | null;
  twelve_month_return: number | null;
  dividend_yield: number | null;
};

export type FactorScreenCandidatesPayload = {
  as_of_date: string;
  factor_snapshot_as_of_date?: string;
  formula_version: string;
  market_state: LivermoreMarketGateState;
  observation_only?: boolean;
  input_stock_count: number;
  coverage_count?: number | null;
  coverage_denominator?: number | null;
  coverage_denominator_as_of_date?: string | null;
  coverage_ratio?: number | null;
  coverage_threshold?: number | null;
  candidate_count: number;
  coverage_note: string;
  items: FactorScreenCandidateItem[];
};

export type HybridFusionCandidateItem = {
  rank: number;
  stock_code: string;
  stock_name: string;
  sector_code: string;
  sector_name: string;
  fusion_score: number;
  cycle_score: number;
  lifecourt_proxy_score: number;
  attention_score: number;
  price_confirm_score: number;
  crowding_penalty: number;
  crowding_score?: number;
  vcov_score?: number;
  consensus_score?: number;
  burst_score?: number;
  hygiene_score?: number;
  regime_score?: number;
  life_long_pass?: boolean;
  fusion_action?: string;
  factor_rank_available?: boolean;
  confidence: "high" | "medium" | "low" | string;
  reason: string;
  evidence: Record<string, unknown>;
};

export type HybridFusionCandidatesPayload = {
  as_of_date: string;
  formula_version: string;
  market_state: LivermoreMarketGateState;
  observation_only: boolean;
  macro_score?: number | null;
  candidate_count: number;
  coverage_note?: string;
  items: HybridFusionCandidateItem[];
};

export type LivermoreCycleRotationLayer = {
  key: "macro_direction" | "industry_cycle" | "market_flow" | "valuation_support" | "execution_constraints";
  title: string;
  weight: number | null;
  status: string;
  evidence: string;
  available_inputs: string[];
  missing_inputs: string[];
};

export type LivermoreCycleRotationFramework = {
  strategy_name: string;
  display_name: string;
  observation_only: boolean;
  implementation_stage: string;
  score_formula: string;
  macro_formula?: string;
  lifecourt_formula?: string;
  fusion_formula?: string;
  rebalance_cadence: string;
  lifecourt_overlay?: {
    display_name: string;
    observation_only: boolean;
    implementation_stage: string;
    rebalance_cadence: string;
    boundary: string;
    available_inputs: string[];
    missing_inputs: string[];
    life_long_gates: string[];
  };
  fusion_policy?: {
    cycle_weight: number;
    life_weight: number;
    conflict_policy: string;
    matrix: Array<{ cycle: string; life: string; action: string }>;
  };
  macro_layer?: {
    macro_score: number | null;
    ready: boolean;
    evidence: string;
    available_inputs: string[];
    missing_inputs: string[];
    lineage: Record<string, unknown>;
  };
  layers: LivermoreCycleRotationLayer[];
  constraints: string[];
  boundary: string;
};
export type LivermoreCycleProxyBacktestInterval = {
  return: number;
  start_date?: string;
  end_date?: string;
  peak_date?: string;
  trough_date?: string;
};
export type LivermoreProxyCostBasis = {
  source: string;
  buy_cost_rate: number;
  sell_cost_rate: number;
  slippage_rate: number;
  round_trip_cost_rate: number;
};
export type LivermoreCycleProxyBacktestSummary = {
  sample_days: number;
  candidate_rows: number;
  return_field_used?: string;
  return_field_fallback?: string;
  return_field_second_fallback?: string;
  execution_return_costs_already_applied?: boolean;
  return_rows_execution_net_adjusted?: number;
  return_rows_adjusted?: number;
  return_rows_adjusted_fallback?: number;
  return_rows_gross_fallback?: number;
  cost_basis?: LivermoreProxyCostBasis;
  cumulative_return: number;
  annualized_return: number | null;
  max_gain: LivermoreCycleProxyBacktestInterval;
  max_drawdown: LivermoreCycleProxyBacktestInterval;
};
export type LivermoreCycleProxyBacktestNavPoint = {
  date: string;
  exit_date?: string;
  period_return: number;
  period_return_gross?: number;
  nav: number;
  candidate_count: number;
};
export type LivermoreCycleProxyBacktestPayload = {
  status: "proxy" | "unsupported" | string;
  full_strategy_status: "blocked_missing_inputs" | string;
  formula_version?: string;
  proxy_signal_kind: string;
  proxy_rule: string;
  execution_blocked_rows_in_window?: number;
  snapshot_from: string | null;
  snapshot_to: string | null;
  missing_full_strategy_inputs: string[];
  warnings: string[];
  summary: LivermoreCycleProxyBacktestSummary | null;
  nav_series: LivermoreCycleProxyBacktestNavPoint[];
  workbench_summary?: Record<string, unknown>;
};
export type LivermoreCandidateHistoryPortfolioBacktestNavPoint = {
  date: string;
  nav: number;
  cash_weight: number;
  holding_count: number;
};

export type LivermoreCandidateHistoryPortfolioBacktestRebalance = {
  date: string;
  market_state: string;
  target_count: number;
  buy_turnover: number;
  sell_turnover: number;
  transaction_cost: number;
};

export type LivermoreCandidateHistoryPortfolioBacktestSummary = {
  sample_days: number;
  candidate_rows: number;
  rebalance_count: number;
  invested_rebalance_count: number;
  cash_rebalance_count: number;
  gross_turnover: number;
  cost_basis?: LivermoreProxyCostBasis;
  cost_drag: number;
  cumulative_return: number;
  annualized_return: number | null;
  max_gain: LivermoreCycleProxyBacktestInterval;
  max_drawdown: LivermoreCycleProxyBacktestInterval;
};

export type LivermoreCandidateHistoryPortfolioBacktestPayload = {
  status: "portfolio_proxy" | "unsupported" | string;
  full_strategy_status: "blocked_missing_inputs" | string;
  signal_kind: string;
  rebalance_rule: string;
  weighting_rule: string;
  snapshot_from: string | null;
  snapshot_to: string | null;
  missing_full_strategy_inputs: string[];
  warnings: string[];
  summary: LivermoreCandidateHistoryPortfolioBacktestSummary | null;
  nav_series: LivermoreCandidateHistoryPortfolioBacktestNavPoint[];
  rebalance_log: LivermoreCandidateHistoryPortfolioBacktestRebalance[];
  workbench_summary?: Record<string, unknown>;
};

export type LivermoreStrategyPayload = {
  as_of_date: string | null;
  requested_as_of_date: string | null;
  strategy_name: string;
  basis: "analytical";
  market_gate: LivermoreMarketGate;
  rule_readiness: LivermoreRuleReadiness[];
  diagnostics: LivermoreDiagnostic[];
  data_gaps: LivermoreDataGap[];
  supported_outputs: LivermoreOutputKey[];
  unsupported_outputs: LivermoreUnsupportedOutput[];
  module_states: LivermoreModuleState[];
  cycle_rotation_framework?: LivermoreCycleRotationFramework;
  sector_rank?: LivermoreSectorRankPayload;
  stock_candidates?: LivermoreStockCandidatesPayload;
  uptrend_momentum_candidates?: UptrendMomentumCandidatesPayload;
  fresh_trend_watchlist?: FreshTrendWatchlistPayload;
  mean_reversion_candidates?: MeanReversionCandidatesPayload;
  factor_screen_candidates?: FactorScreenCandidatesPayload;
  theme_breakout?: LivermoreThemeBreakoutPayload;
  hybrid_fusion_candidates?: HybridFusionCandidatesPayload;
  risk_exit?: LivermoreRiskExitPayload;
  workbench_summary?: Record<string, unknown>;
};

export type StockAnalysisWorkbenchAnswerState =
  | "review_ready"
  | "limited_review"
  | "blocked"
  | "no_data"
  | string;

export type StockAnalysisWorkbenchModuleStatus =
  | "ready"
  | "deferred"
  | "missing"
  | "error"
  | "unsupported"
  | "stale"
  | string;

export type StockAnalysisWorkbenchIssue = {
  severity: "info" | "warning" | "blocking" | string;
  code: string;
  message: string;
  source_module: string | null;
};

export type StockAnalysisWorkbenchModule<T = unknown> = {
  key: string;
  label: string;
  endpoint: string;
  status: StockAnalysisWorkbenchModuleStatus;
  result: T | null;
  summary: Record<string, unknown>;
  meta: Record<string, unknown>;
  issues: StockAnalysisWorkbenchIssue[];
};

export type StockAnalysisWorkbenchEndpointEvidence = {
  key: string;
  label: string;
  endpoint: string;
  status: StockAnalysisWorkbenchModuleStatus;
  as_of_date: string | null;
  rows: number | null;
  warning: string | null;
};

export type StockAnalysisWorkbenchPayload = {
  page_id: "GAP-STOCK-ANALYSIS-PAGE";
  route: "/stock-analysis";
  basis: "analytical";
  contract_status: "observational_only";
  formal_use_allowed: false;
  requested_as_of_date: string | null;
  as_of_date: string | null;
  fallback_date: string | null;
  stale: boolean;
  page_question: {
    question: string;
    answer_state: StockAnalysisWorkbenchAnswerState;
    answer_label: string;
    reason: string;
  };
  decision_summary: {
    gate_state: string | null;
    gate_label: string;
    can_review_candidates: boolean;
    top_review_stock_code: string | null;
    top_review_stock_name: string | null;
    review_queue_count: number;
    evidence_closure_label: string;
    primary_blocker: string | null;
    quality_flag?: string | null;
  };
  data_status: {
    quality_flag: string | null;
    vendor_status: string | null;
    fallback_mode: string | null;
    source_version: string | null;
    rule_version: string | null;
    cache_version: string | null;
    tables_used: string[];
    evidence_rows: number | null;
  };
  first_screen: {
    market_gate: LivermoreMarketGate | Record<string, unknown> | null;
    review_queue: Record<string, unknown>[];
    sector_snapshot: Record<string, unknown>[];
    risk_exit_snapshot: Record<string, unknown>[];
    data_gaps: StockAnalysisWorkbenchDataGap[];
    diagnostics: LivermoreDiagnostic[] | Record<string, unknown>[];
    supported_outputs: string[];
    unsupported_outputs: LivermoreUnsupportedOutput[] | Record<string, unknown>[];
  };
  modules: Record<string, StockAnalysisWorkbenchModule>;
  endpoint_evidence: StockAnalysisWorkbenchEndpointEvidence[];
  issues: StockAnalysisWorkbenchIssue[];
  links: {
    stock_detail: string;
    kline_analysis: string;
    candidate_history: string;
    sector_rank_series: string;
    strategy_score: string;
    strategy_optimization: string;
    cycle_proxy_backtest: string;
    portfolio_backtest: string;
  };
  include: {
    requested: string[];
    unknown: string[];
    sector_window_days: number;
    top_k: number;
  };
};

export type LivermoreStockDetailCandle = {
  trade_date: string;
  open_value: number | null;
  high_value: number | null;
  low_value: number | null;
  close_value: number | null;
  volume: number | null;
  amount: number | null;
};

export type LivermoreStockDetailFactor = {
  as_of_date: string | null;
  pe: number | null;
  pb: number | null;
  roe: number | null;
  dividend_yield: number | null;
};

export type LivermoreStockDetailState = "ok" | "missing";

export type LivermoreStockDetailPayload = {
  basis: "analytical";
  state: LivermoreStockDetailState;
  stock_code: string;
  requested_as_of_date: string | null;
  as_of_date: string | null;
  lookback: number;
  candles: LivermoreStockDetailCandle[];
  factor: LivermoreStockDetailFactor;
};

export type StockKlineAnalysisState = "ok" | "missing" | "insufficient" | string;

export type StockKlineAnalysisPattern = {
  key: string;
  label: string;
  tone: "positive" | "negative" | "neutral" | string;
  evidence: string;
};

export type StockKlineAnalysisPayload = {
  basis: "analytical";
  state: StockKlineAnalysisState;
  contract_status: "observational_only";
  formal_use_allowed: false;
  trading_instruction_allowed: false;
  stock_code: string;
  requested_as_of_date: string | null;
  as_of_date: string | null;
  lookback: number;
  engine: {
    name: string;
    source: string;
    rule_version: string;
    coverage: string[];
  };
  latest_candle: (LivermoreStockDetailCandle & {
    pctchange?: number | null;
    turn?: number | null;
    amplitude?: number | null;
  }) | null;
  indicators: {
    latest_close?: number | null;
    ma5?: number | null;
    ma20?: number | null;
    ma60?: number | null;
    return_5d?: number | null;
    return_20d?: number | null;
    volume_ratio_20d?: number | null;
    latest_turnover?: number | null;
    latest_amplitude?: number | null;
  };
  patterns: StockKlineAnalysisPattern[];
  validity: {
    state: string;
    usable: boolean;
    bar_count: number;
    required_bar_count: number;
    recommended_bar_count: number;
    data_health: Record<string, unknown>;
    liquidity: Record<string, unknown>;
    warnings: string[];
  };
  observation_signal: {
    level: string;
    label: string;
    score: number | null;
    confidence: "low" | "medium" | "high" | string;
    reasons: string[];
    risks: string[];
  };
  diagnostics: Array<Record<string, unknown>>;
};

export type LivermoreSectorRankSeriesPoint = {
  trade_date: string;
  sector_code: string;
  sector_name: string;
  score: number | null;
  rank: number | null;
  avg_pctchange: number | null;
  avg_turn: number | null;
  avg_amplitude: number | null;
  constituent_count: number | null;
  cum_pctchange_window: number | null;
};

export type LivermoreSectorRankSeriesPayload = {
  basis: "analytical";
  state: "ok" | "missing";
  as_of_date: string | null;
  window_days: number;
  top_k: number;
  sector_code_filter: string | null;
  formula_version: string;
  series: LivermoreSectorRankSeriesPoint[];
  unsupported_notes: string[];
  workbench_summary?: Record<string, unknown>;
};

export type LivermoreCandidateForwardMaturityStatus =
  | "natural_pending"
  | "complete"
  | "matured_missing_bar"
  | "raw_matured_adjustment_missing"
  | "partial_halt"
  | string;

export type LivermoreCandidateForwardMaturityHorizonKey = "1d" | "5d" | "10d" | "20d";

export type LivermoreCandidateForwardMaturityHorizon = {
  status: LivermoreCandidateForwardMaturityStatus;
  reason?: string | null;
  horizon_bars: number;
  target_trade_date?: string | null;
  stock_valid_bar_count?: number;
  market_trade_date_count?: number;
  target_observation_verified?: boolean;
};

export type LivermoreCandidateForwardMaturity = {
  evaluation_as_of_date: string;
  horizons: Partial<
    Record<LivermoreCandidateForwardMaturityHorizonKey, LivermoreCandidateForwardMaturityHorizon>
  >;
  maturity_clock?: string;
  diagnostic_clock?: string;
  source_status?: "available" | "unavailable" | string;
  source_issue?: string | null;
  classification_available?: boolean;
};

export type LivermoreCandidateHistoryRow = {
  snapshot_as_of_date: string;
  stock_code: string;
  stock_name?: string | null;
  signal_kind?: string | null;
  candidate_rank: number;
  sector_code?: string | null;
  sector_name?: string | null;
  selection_close: number | null;
  forward_trade_date_1d: string | null;
  forward_trade_date_5d: string | null;
  forward_trade_date_20d: string | null;
  return_1d: number | null;
  return_5d: number | null;
  return_20d: number | null;
  data_status: "complete" | "partial_halt" | "pending" | string;
  forward_coverage?: "complete" | "pending" | "missing_bar" | "partial_halt" | string;
  forward_maturity?: LivermoreCandidateForwardMaturity | null;
};

export type BacktestWindowSummaryStatus = "valid" | "partial" | "unsupported";

export type ReplayDateStatus = "completed" | "pending" | "unsupported" | "proxy_only";

export type ReplayReasonCode =
  | "missing_daily_limit_flags"
  | "missing_required_source_table"
  | "forward_returns_pending"
  | "no_strategy_signals"
  | "real_theme_inputs_unconfirmed"
  | "proxy_theme_only";

export type ReplayDateReason = {
  trade_date: string;
  status: ReplayDateStatus;
  reason_code: ReplayReasonCode;
  message: string;
  affects_completed_stats: boolean;
  signal_kinds: string[];
};

export type BacktestWindowSummary = {
  status: BacktestWindowSummaryStatus;
  snapshot_from: string | null;
  snapshot_to: string | null;
  replay_dates_total: number;
  replay_dates_completed: number;
  replay_dates_pending: number;
  replay_dates_unsupported: number;
  replay_dates_proxy_only: number;
  completed_rows: number;
  pending_rows: number;
  unsupported_rows: number;
  proxy_only_rows: number;
  included_completed_stats_dates: string[];
  excluded_from_completed_stats_dates: string[];
  date_reasons: ReplayDateReason[];
};

export type LivermoreCandidateHistoryLegacySummary = {
  row_count: number;
  complete_count?: number;
  pending_count?: number;
  partial_halt_count?: number;
  missing_forward_return_count?: number;
  avg_return_1d?: number | null;
  avg_return_5d?: number | null;
  avg_return_10d?: number | null;
  avg_return_20d?: number | null;
  horizon_stats?: LivermoreCandidateHistoryHorizonStatsByKey;
  horizon_usable_stats?: LivermoreCandidateHistoryHorizonStatsByKey;
  by_signal_kind?: Record<string, number>;
  by_signal_kind_horizon_stats?: LivermoreCandidateHistorySignalKindHorizonStats;
  by_signal_kind_horizon_usable_stats?: LivermoreCandidateHistorySignalKindHorizonStats;
  by_market_state_signal_kind_horizon_stats?: LivermoreCandidateHistoryMarketStateSignalKindHorizonStats;
  by_market_state_signal_kind_execution_stats?: LivermoreCandidateHistoryMarketStateSignalKindHorizonStats;
  decision_usable_stats?: LivermoreCandidateHistoryDecisionUsableStats | null;
  execution_usable_stats?: LivermoreCandidateHistoryExecutionUsableStats | null;
  entry_blocked_stats?: LivermoreCandidateHistoryEntryBlockedStats | null;
  matched_baseline_stats?: LivermoreCandidateHistoryMatchedBaselineStats | null;
};

export type LivermoreCandidateHistoryHorizonKey = "return_1d" | "return_5d" | "return_10d" | "return_20d";

export type LivermoreCandidateHistoryHorizonStats = {
  available_count: number;
  missing_count: number;
  positive_count: number;
  non_positive_count: number;
  avg_return: number | null;
  median_return?: number | null;
  win_rate: number | null;
  n?: number;
  adj_missing_n?: number;
  win?: number | null;
  avg?: number | null;
  median?: number | null;
  p10?: number | null;
  p90?: number | null;
};

export type LivermoreCandidateHistoryHorizonStatsByKey = Record<
  LivermoreCandidateHistoryHorizonKey,
  LivermoreCandidateHistoryHorizonStats
>;

export type LivermoreCandidateHistorySignalKindHorizonStats = Record<
  string,
  LivermoreCandidateHistoryHorizonStatsByKey
>;

export type LivermoreCandidateHistoryMarketStateSignalKindHorizonStats = Record<
  string,
  LivermoreCandidateHistorySignalKindHorizonStats
>;

export type LivermoreCandidateHistoryExecutionUsableStats = {
  metric_basis: string;
  basis_label?: string | null;
  row_count: number;
  execution_row_count?: number;
  entry_executable_count?: number;
  horizon_usable_stats?: LivermoreCandidateHistoryHorizonStatsByKey;
  by_signal_kind?: Record<string, number>;
  by_signal_kind_horizon_stats?: LivermoreCandidateHistorySignalKindHorizonStats;
  by_signal_kind_horizon_usable_stats?: LivermoreCandidateHistorySignalKindHorizonStats;
  included_signal_dates?: string[];
};

export type LivermoreCandidateHistoryEntryBlockedStats = {
  metric_basis?: string;
  total_row_count: number;
  entry_executable_count: number;
  blocked_row_count: number;
  blocked_ratio: number | null;
  by_reason: Record<string, { count: number; share: number | null }>;
};

export type LivermoreCandidateHistoryMatchedBaselineHorizonStats = {
  n: number;
  paired_alpha_avg: number | null;
  paired_alpha_median: number | null;
  avg_control_count?: number | null;
  bootstrap_ci_95?: {
    low: number | null;
    high: number | null;
    confidence: number;
    iterations: number;
  };
};

export type LivermoreCandidateHistoryMatchedBaselineStats = Record<
  string,
  Record<string, LivermoreCandidateHistoryMatchedBaselineHorizonStats>
>;

export type LivermoreCandidateHistoryDecisionUsableStats = {
  metric_basis?: string;
  adj_coverage_count?: number;
  adj_coverage_total?: number;
  adj_coverage_ratio?: number | null;
  row_count: number;
  complete_row_count: number;
  pending_row_count: number;
  partial_halt_row_count: number;
  missing_forward_return_count: number;
  avg_return_1d: number | null;
  avg_return_5d: number | null;
  avg_return_10d?: number | null;
  avg_return_20d: number | null;
  win_rate_1d: number | null;
  win_rate_5d: number | null;
  win_rate_10d?: number | null;
  win_rate_20d: number | null;
  horizon_usable_stats?: LivermoreCandidateHistoryHorizonStatsByKey;
  by_signal_kind: Record<string, number>;
  by_signal_kind_horizon_stats?: LivermoreCandidateHistorySignalKindHorizonStats;
  by_signal_kind_horizon_usable_stats?: LivermoreCandidateHistorySignalKindHorizonStats;
  by_market_state_signal_kind_horizon_stats?: LivermoreCandidateHistoryMarketStateSignalKindHorizonStats;
  included_snapshot_dates: string[];
  excluded_snapshot_dates: string[];
};

export type LivermoreCandidateHistoryPayload = {
  stock_code: string | null;
  snapshot_from: string | null;
  snapshot_to: string | null;
  effective_snapshot_to?: string | null;
  evaluation_as_of_date?: string | null;
  limit: number;
  summary?: LivermoreCandidateHistoryLegacySummary | null;
  backtest_window_summary?: BacktestWindowSummary | null;
  items: LivermoreCandidateHistoryRow[];
  workbench_summary?: Record<string, unknown>;
};

export type LivermoreStrategyScoreSampleStatus = "sufficient" | "insufficient" | string;

export type LivermoreStrategyScorePriorityLabel = "优先复核" | "降权观察" | "样本不足" | string;

export type LivermoreStrategyScoreRankBucket = {
  label: string;
  rank_from: number;
  rank_to: number | null;
  sample_status: LivermoreStrategyScoreSampleStatus;
  priority_label: LivermoreStrategyScorePriorityLabel;
  included_in_priority: boolean;
  reason: string;
  stats: LivermoreCandidateHistoryHorizonStatsByKey;
};

export type LivermoreStrategyScoreRiskFlag = {
  kind: string;
  label: string;
  horizon?: LivermoreCandidateHistoryHorizonKey | string;
  reason: string;
  stats?: LivermoreCandidateHistoryHorizonStats;
};

export type LivermoreStrategyScoreSnapshotStat = {
  snapshot_as_of_date: string;
  available_count: number;
  positive_count: number;
  non_positive_count: number;
  avg_return: number | null;
  median_return?: number | null;
  win_rate: number | null;
};

export type LivermoreStrategyScoreHorizonMaturity = LivermoreCandidateHistoryHorizonStats & {
  status: "complete" | "partial" | "pending" | string;
};

export type LivermoreStrategyScoreTrackedSnapshot = {
  snapshot_as_of_date: string;
  candidate_count: number;
  horizons: Record<LivermoreCandidateHistoryHorizonKey, LivermoreStrategyScoreHorizonMaturity>;
};

export type LivermoreStrategyScoreMaturity = {
  status: "sufficient" | "narrow" | string;
  label: string;
  reason: string;
  min_mature_snapshot_count: number;
  mature_snapshot_count: number;
  snapshot_stats: LivermoreStrategyScoreSnapshotStat[];
  tracked_snapshots: LivermoreStrategyScoreTrackedSnapshot[];
  worst_snapshot: LivermoreStrategyScoreSnapshotStat | null;
};

export type LivermoreStrategyScoreDiagnostics = {
  priority_scope: string | null;
  priority_scope_label: string | null;
  priority_scope_stats?: LivermoreCandidateHistoryHorizonStatsByKey | null;
  maturity?: LivermoreStrategyScoreMaturity | null;
  rank_buckets: LivermoreStrategyScoreRankBucket[];
  risk_flags: LivermoreStrategyScoreRiskFlag[];
};

export type LivermoreStrategyFamilyMetadata = {
  family_key?: string | null;
  family_label?: string | null;
  family_contract_version?: string | null;
  primary_sample_size?: number | null;
  family_readiness?: LivermoreStrategyFamilyReadiness | null;
};

export type LivermoreMacroContextV1 = {
  macro_context_id: string;
  macro_contract_version: string;
  asof_date: string;
  report_date?: string | null;
  data_state: "ready" | "degraded" | "stale" | "no_data" | string;
  coverage_ratio: number;
  freshness_score: number;
  confidence_score: number;
  fallback_mode: string;
  dimension_scores: Record<string, number | null>;
  readiness_reasons: string[];
  quality_flag?: string | null;
  vendor_status?: string | null;
  source_version?: string | null;
  vendor_version?: string | null;
  rule_version?: string | null;
  cache_version?: string | null;
  evidence_rows?: number | null;
  warning_count?: number | null;
};

export type LivermoreStrategyFamilyReadiness = {
  readiness_contract_version: string;
  readiness_state: "observation_ready" | "degraded_observation" | string;
  macro_context_id?: string | null;
  market_gate_context_id?: string | null;
  macro_compatibility: "compatible" | "degraded" | "unknown" | string;
  market_gate_compatibility: "compatible" | "degraded" | "unknown" | string;
  data_readiness: "ready" | "degraded" | "missing" | string;
  sample_maturity: "sufficient" | "insufficient" | "unknown" | string;
  readiness_reasons: string[];
  observational_only: boolean;
  formal_use_allowed: boolean;
};

export type LivermoreStrategyScoreRow = LivermoreStrategyFamilyMetadata & {
  market_state: string;
  signal_kind: string;
  strategy_label: string;
  sample_status: LivermoreStrategyScoreSampleStatus;
  priority_score: number | null;
  priority_rank: number | null;
  priority_label: LivermoreStrategyScorePriorityLabel;
  reason: string;
  stats: LivermoreCandidateHistoryHorizonStatsByKey;
  diagnostics?: LivermoreStrategyScoreDiagnostics;
};

export type LivermoreStrategyScorePayload = {
  as_of_date: string | null;
  snapshot_from: string | null;
  snapshot_to: string | null;
  primary_horizon: LivermoreCandidateHistoryHorizonKey;
  min_sample: number;
  review_thresholds?: Record<string, unknown>;
  current_market_state: string | null;
  macro_context?: LivermoreMacroContextV1 | null;
  backtest_window_summary?: BacktestWindowSummary | null;
  rows: LivermoreStrategyScoreRow[];
  current_market_state_rows: LivermoreStrategyScoreRow[];
  stock_candidate_state_scopes?: Record<string, unknown> | unknown[];
  workbench_summary?: Record<string, unknown>;
};

export type LivermoreStrategyOptimizationHorizonKey =
  | LivermoreCandidateHistoryHorizonKey
  | "return_10d";

export type LivermoreStrategyOptimizationAction =
  | "promote"
  | "downgrade"
  | "observe"
  | "pending_more_history"
  | string;

export type LivermoreStrategyOptimizationRecommendation = {
  action: LivermoreStrategyOptimizationAction;
  priority_label: "优先复核" | "降权观察" | "继续观察" | "样本不足" | string;
  reason: string;
  primary_horizon: LivermoreStrategyOptimizationHorizonKey;
  review_horizon?: LivermoreStrategyOptimizationHorizonKey;
  available_count: number;
  min_sample: number;
  avg_return: number | null;
  median_return?: number | null;
  t20_median_return?: number | null;
  win_rate: number | null;
  score: number | null;
};

export type LivermoreStrategyOptimizationDateWeightedStats = {
  available_day_count: number;
  candidate_row_count: number;
  avg_return: number | null;
  positive_day_rate: number | null;
  worst_day_return: number | null;
  best_day_return: number | null;
};

export type LivermoreStrategyOptimizationHorizonStatsByKey = Record<
  string,
  LivermoreCandidateHistoryHorizonStats
>;

export type LivermoreStrategyOptimizationDateWeightedStatsByKey = Record<
  string,
  LivermoreStrategyOptimizationDateWeightedStats
>;

export type LivermoreStrategyOptimizationSummary = LivermoreStrategyFamilyMetadata & {
  summary_key: string;
  signal_kind: string;
  strategy_label: string;
  sample_status: LivermoreStrategyScoreSampleStatus;
  stats: LivermoreStrategyOptimizationHorizonStatsByKey;
  date_weighted_stats: LivermoreStrategyOptimizationDateWeightedStatsByKey;
  recommendation: LivermoreStrategyOptimizationRecommendation;
};

export type LivermoreStrategyOptimizationSlice = LivermoreStrategyFamilyMetadata & {
  slice_key: string;
  signal_kind: string;
  strategy_label: string;
  dimension: string;
  bucket: string;
  label: string;
  sample_status: LivermoreStrategyScoreSampleStatus;
  stats: LivermoreStrategyOptimizationHorizonStatsByKey;
  date_weighted_stats: LivermoreStrategyOptimizationDateWeightedStatsByKey;
  recommendation: LivermoreStrategyOptimizationRecommendation;
};

export type LivermoreStrategyOptimizationPendingSummary = {
  primary_horizon: LivermoreStrategyOptimizationHorizonKey;
  pending_rows: number;
  pending_dates: string[];
  latest_pending_date: string | null;
  message: string;
};

export type LivermoreStrategyOptimizationSampleMaturity = {
  status: "sufficient" | "insufficient" | string;
  primary_horizon: LivermoreStrategyOptimizationHorizonKey;
  min_sample: number;
  sufficient_count: number;
  insufficient_count: number;
};

export type LivermoreStrategyOptimizationPayload = {
  as_of_date: string | null;
  snapshot_from: string | null;
  snapshot_to: string | null;
  primary_horizon: LivermoreStrategyOptimizationHorizonKey;
  min_sample: number;
  review_thresholds?: Record<string, unknown>;
  current_market_state: string | null;
  macro_context?: LivermoreMacroContextV1 | null;
  backtest_window_summary?: BacktestWindowSummary | null;
  strategy_summaries: LivermoreStrategyOptimizationSummary[];
  slices: LivermoreStrategyOptimizationSlice[];
  recommendations: Array<
    LivermoreStrategyOptimizationRecommendation & {
      target_type: "strategy" | "slice" | string;
      target_key: string;
      signal_kind: string;
      label: string;
    } & LivermoreStrategyFamilyMetadata
  >;
  pending_summary: LivermoreStrategyOptimizationPendingSummary;
  sample_maturity?: LivermoreStrategyOptimizationSampleMaturity | null;
  workbench_summary?: Record<string, unknown>;
};

export type ConfluenceReplayBlockedDate = {
  trade_date: string;
  status: "pending" | "unsupported" | "proxy_only";
  reason_code:
    | "missing_daily_limit_flags"
    | "missing_required_source_table"
    | "forward_returns_pending"
    | "real_theme_inputs_unconfirmed"
    | "proxy_theme_only";
  signal_kinds: string[];
};

export type ConfluenceReplayStatus = {
  window_status: BacktestWindowSummaryStatus;
  maturity_status?: "ready" | "partial" | "insufficient" | "pending" | "unsupported" | "proxy_only" | "missing" | string;
  has_decision_usable_completed_stats: boolean;
  completed_dates: number;
  pending_dates: number;
  unsupported_dates: number;
  proxy_only_dates: number;
  completed_candidate_rows: number;
  pending_candidate_rows: number;
  unsupported_candidate_rows: number;
  proxy_only_candidate_rows: number;
  matched_entry_count?: number;
  has_required_horizon_stats?: boolean;
  included_completed_stats_dates: string[];
  blocked_dates: ConfluenceReplayBlockedDate[];
  completed_zero_signal_dates: string[];
};

export type LivermoreSignalConfluenceMacroStatus =
  | "supportive"
  | "neutral"
  | "restrictive"
  | "unknown";

export type LivermoreSignalConfluenceMacroContext = {
  status: LivermoreSignalConfluenceMacroStatus;
  composite_score: number | null;
  multiplier: number;
  description?: string | null;
};

export type LivermoreSignalConfluenceStrategyContext = {
  market_gate_state: string;
  market_gate_exposure: number;
  allows_new_entry_observations: boolean;
  new_entry_observation_allowed?: boolean | null;
  position_size_hint?: number | null;
};

export type LivermoreSignalConfluenceEntryObservationAction =
  | "observe_entry_setup"
  | "observe_only";

export type LivermoreSignalConfluenceEntryObservation = {
  stock_code: string | null;
  stock_name: string | null;
  action: LivermoreSignalConfluenceEntryObservationAction;
  trigger_price: number | null;
  buy_trigger_price?: number | null;
  current_price: number | null;
  invalidation_reference_price: number | null;
  position_size_hint?: number | null;
  evidence?: string[] | string | null;
};

export type LivermoreSignalConfluenceExitObservationAction =
  | "observe_exit_watch"
  | "exit_triggered";

export type LivermoreSignalConfluenceExitObservation = {
  stock_code: string | null;
  stock_name: string | null;
  action: LivermoreSignalConfluenceExitObservationAction;
  current_price: number | null;
  exit_watch_price: number | null;
  triggered?: boolean | null;
  evidence?: string[] | string | null;
};

export type LivermoreSignalConfluenceDiagnostic =
  | string
  | {
      severity?: string | null;
      code?: string | null;
      message?: string | null;
    };

export type LivermoreSignalConfluenceAdversarialContext = {
  status: "complete" | "degraded" | "missing" | string;
  mode: string;
  risk_gate: "pass" | "block" | "degrade" | "degraded" | "missing" | string;
  position_scale: number | null;
  strongest_block_reason?: string | null;
};

export type LivermoreSignalConfluenceClosedLoopState = {
  entry_gate: "open" | "observe_only" | "blocked" | "missing" | string;
  exit_gate: "watch" | "triggered" | "missing" | string;
  replay_status: ConfluenceReplayStatus | "available" | "missing" | "degraded" | string;
  lineage_status: "complete" | "degraded" | "missing" | string;
};

export type LivermoreSignalConfluenceReplayEvidenceItem = {
  stock_code: string | null;
  stock_name?: string | null;
  candidate_rank?: number | null;
  signal_kind?: string | null;
  data_status?: string | null;
};

export type LivermoreSignalConfluenceReplayEvidence = {
  status: "available" | "missing" | "degraded" | string;
  snapshot_as_of_date: string | null;
  row_count: number;
  matched_entry_count: number;
  sample_items: LivermoreSignalConfluenceReplayEvidenceItem[];
};

export type LivermoreSignalConfluencePayload = {
  as_of_date: string;
  macro_context: LivermoreSignalConfluenceMacroContext;
  strategy_context: LivermoreSignalConfluenceStrategyContext;
  position_size_hint: number;
  entry_observations: LivermoreSignalConfluenceEntryObservation[];
  exit_observations: LivermoreSignalConfluenceExitObservation[];
  adversarial_context?: LivermoreSignalConfluenceAdversarialContext | null;
  closed_loop_state?: LivermoreSignalConfluenceClosedLoopState | null;
  replay_evidence?: LivermoreSignalConfluenceReplayEvidence | null;
  diagnostics: LivermoreSignalConfluenceDiagnostic[];
  disclaimer: string;
  workbench_summary?: Record<string, unknown>;
};

export type LivermorePositionSnapshotPayload = {
  status: string;
  fact_source: string;
  input_mode?: "csv" | "manual";
  as_of_date: string;
  row_count: number;
  run_id: string;
  source_file_hash: string;
  source_systems: string[];
  source_version: string;
  vendor_version: string;
  csv_path: string | null;
  risk_exit_input_status: "ready" | "blocked";
  risk_exit_input_block_reason: string;
};

export type LivermoreManualPositionInput = {
  stockCode: string;
  stockName?: string;
  entryCost: number;
  barsSinceEntry?: number;
  entryDate?: string;
  positionQuantity?: number;
  positionStatus?: "ACTIVE" | "CLOSED" | "EXITED";
};

export type ResearchCalendarEventKind = "macro" | "supply" | "auction" | "internal";

export type ResearchCalendarEvent = {
  id: string;
  date: string;
  title: string;
  kind: ResearchCalendarEventKind;
  severity: "high" | "medium" | "low";
  amount_label?: string | null;
  /** 发行人/主体；与主标题分开展示。 */
  issuer?: string | null;
  /** 短句元信息，不含整段 URL、不含 `issuer` 重复；原文见 `source_url`。 */
  note?: string | null;
  /** 公告/披露原文链接 */
  source_url?: string | null;
  /** 链接展示名，如「中国债券信息网」 */
  source_label?: string | null;
};

/** Raw supply/auction row from `GET /ui/calendar/supply-auctions` (`ResearchCalendarEvent` in backend). */
export type ResearchCalendarApiEventRow = {
  event_id: string;
  series_id: string;
  event_date: string;
  event_kind: "auction" | "supply";
  title: string;
  source_family: string;
  severity: "high" | "medium" | "low";
  issuer?: string | null;
  market?: string | null;
  instrument_type?: string | null;
  term_label?: string | null;
  amount?: number | null;
  amount_unit?: string | null;
  currency?: string | null;
  status?: "scheduled" | "completed" | "cancelled" | "unknown";
  headline_text?: string | null;
  headline_url?: string | null;
  headline_published_at?: string | null;
};

export type ResearchCalendarResultPayload = {
  series_id: string;
  total_rows: number;
  limit: number;
  offset: number;
  events: ResearchCalendarApiEventRow[];
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
  summary: import("./pnlByBusinessContracts").PnlByBusinessSummary;
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

export type BalanceMovementBucket = "AC" | "OCI" | "TPL";
export type BalanceMovementReconciliationStatus =
  | "matched"
  | "mismatch"
  | "gl_only"
  | "zqtz_only";

export type BalanceMovementRow = {
  report_date: string;
  report_month: string;
  currency_basis: string;
  sort_order: number;
  basis_bucket: BalanceMovementBucket;
  previous_balance: DecimalLike;
  current_balance: DecimalLike;
  previous_balance_pct: DecimalLike | null;
  current_balance_pct: DecimalLike | null;
  balance_change: DecimalLike;
  change_pct: DecimalLike | null;
  contribution_pct: DecimalLike | null;
  zqtz_amount: DecimalLike;
  gl_amount: DecimalLike;
  reconciliation_diff: DecimalLike;
  reconciliation_status: BalanceMovementReconciliationStatus;
  source_version: string;
  rule_version: string;
};

export type BalanceMovementSummary = {
  previous_balance_total: DecimalLike;
  current_balance_total: DecimalLike;
  balance_change_total: DecimalLike;
  zqtz_amount_total: DecimalLike;
  reconciliation_diff_total: DecimalLike;
  matched_bucket_count: number;
  bucket_count: number;
};

export type BalanceMovementTrendMonth = {
  report_date: string;
  report_month: string;
  current_balance_total: DecimalLike;
  balance_change_total: DecimalLike;
  rows: BalanceMovementRow[];
};

export type BalanceBusinessMovementRow = {
  report_date: string;
  report_month: string;
  currency_basis: string;
  side: "asset" | "liability";
  sort_order: number;
  row_key: string;
  row_label: string;
  current_balance: DecimalLike;
  source_kind: "ledger" | "zqtz";
  source_note: string;
  source_version: string;
  rule_version: string;
};

export type BalanceBusinessMovementTrendMonth = {
  report_date: string;
  report_month: string;
  asset_balance_total: DecimalLike;
  liability_balance_total: DecimalLike;
  net_balance_total: DecimalLike;
  rows: BalanceBusinessMovementRow[];
};

export type BalanceZqtzCalibrationItem = {
  row_key: string;
  row_label: string;
  system_amount: DecimalLike;
  reference_amount: DecimalLike;
  diff_amount: DecimalLike;
  status: "matched" | "watch";
  note: string;
};

export type BalanceZqtzCalibrationAnalysis = {
  source_file: string;
  conclusion: string;
  root_cause: string;
  remediation: string;
  items: BalanceZqtzCalibrationItem[];
  residual_risks: string[];
};

export type BalanceStructureMigrationBucket = {
  basis_bucket: BalanceMovementBucket;
  previous_balance: DecimalLike;
  current_balance: DecimalLike;
  balance_delta: DecimalLike;
  previous_share_pct: DecimalLike | null;
  current_share_pct: DecimalLike | null;
  share_delta_pp: DecimalLike | null;
};

export type BalanceStructureMigrationPair = {
  previous_report_date: string;
  current_report_date: string;
  previous_report_month: string;
  current_report_month: string;
  total_balance_delta: DecimalLike;
  dominant_share_increase_bucket: BalanceMovementBucket | null;
  fvtpl_volatility_signal: string;
  oci_valuation_signal: string;
  buckets: BalanceStructureMigrationBucket[];
};

export type BalanceStructureMigrationAnalysis = {
  summary: string;
  caveat: string;
  pairs: BalanceStructureMigrationPair[];
};

export type BalanceDifferenceAttributionComponent = {
  component_key: string;
  component_label: string;
  amount: DecimalLike;
  source_kind: "ledger" | "zqtz" | "derived" | "residual";
  evidence_note: string;
  is_residual: boolean;
  is_supported: boolean;
};

export type BalanceDifferenceAttributionWaterfall = {
  reference_label: string;
  reference_total: DecimalLike;
  target_label: string;
  target_total: DecimalLike;
  net_difference: DecimalLike;
  components: BalanceDifferenceAttributionComponent[];
  closing_check: DecimalLike;
  caveat: string;
};

export type BalanceMovementDrilldownStatus =
  | "supported"
  | "unsupported_missing_columns"
  | "unsupported_low_coverage"
  | "no_data";

export type BalanceMovementDrilldownMeta = {
  source_tables: string[];
  source_scope: string;
  report_date: string;
  prior_report_date: string | null;
  currency_basis: string;
  zqtz_currency_basis?: string | null;
  unit: "yuan";
  eligible_total: DecimalLike;
  covered_total: DecimalLike | null;
  unknown_total: DecimalLike | null;
  coverage_pct: DecimalLike | null;
  status: BalanceMovementDrilldownStatus;
  caveat: string;
};

export type BalanceBasisMovementComponent = {
  component_key: string;
  component_label: string;
  account_code_pattern: string;
  previous_balance: DecimalLike;
  current_balance: DecimalLike;
  balance_change: DecimalLike;
  contribution_pct: DecimalLike | null;
  source_note: string;
  is_supported: boolean;
};

export type BalanceBasisMovementBucket = {
  basis_bucket: BalanceMovementBucket;
  previous_balance: DecimalLike;
  current_balance: DecimalLike;
  balance_change: DecimalLike;
  rows: BalanceBasisMovementComponent[];
  residual_amount: DecimalLike;
  closing_check: DecimalLike;
};

export type BalanceBasisMovementDecomposition = {
  meta: BalanceMovementDrilldownMeta;
  buckets: BalanceBasisMovementBucket[];
};

export type BalanceZqtzMaturityBucketKey =
  | "overdue_or_matured"
  | "<=30d"
  | "31-90d"
  | "91d-1y"
  | "1-3y"
  | "3-5y"
  | ">5y"
  | "unknown";

export type BalanceZqtzMaturityBucket = {
  maturity_bucket: BalanceZqtzMaturityBucketKey;
  bucket_label: string;
  current_amount: DecimalLike;
  prior_amount: DecimalLike;
  delta_amount: DecimalLike;
  item_count: number;
  share_pct: DecimalLike | null;
};

export type BalanceZqtzMaturityStructure = {
  meta: BalanceMovementDrilldownMeta;
  buckets: BalanceZqtzMaturityBucket[];
};

export type BalanceZqtzConcentrationDimensionKey =
  | "issuer_name"
  | "rating"
  | "industry_name";

export type BalanceZqtzConcentrationItem = {
  rank: number;
  dimension_value: string;
  current_amount: DecimalLike;
  prior_amount: DecimalLike | null;
  delta_amount: DecimalLike | null;
  share_pct: DecimalLike | null;
  item_count: number;
  item_kind: "top" | "other" | "unknown";
};

export type BalanceZqtzConcentrationDimension = {
  dimension: BalanceZqtzConcentrationDimensionKey;
  status: BalanceMovementDrilldownStatus;
  eligible_total: DecimalLike;
  covered_total: DecimalLike;
  unknown_total: DecimalLike;
  coverage_pct: DecimalLike | null;
  prior_coverage_pct: DecimalLike | null;
  top_n: number;
  hhi: DecimalLike | null;
  top5_share_pct: DecimalLike | null;
  items: BalanceZqtzConcentrationItem[];
  caveat: string;
};

export type BalanceZqtzConcentrationAnalysis = {
  meta: BalanceMovementDrilldownMeta;
  dimensions: BalanceZqtzConcentrationDimension[];
};

/** 余额类页面可选返回的口径说明快照（后端未部署时字段可缺失）。 */
export type BalancePageCalibration = {
  position_scope: string;
  currency_basis: string;
  source_families: string[];
  tyw_amount_semantics?: string;
  data_basis: string;
  calibration_note: string;
};

export type BalanceMovementPayload = {
  report_date: string;
  currency_basis: string;
  rows: BalanceMovementRow[];
  summary: BalanceMovementSummary;
  trend_months: BalanceMovementTrendMonth[];
  business_trend_months: BalanceBusinessMovementTrendMonth[];
  zqtz_calibration_analysis: BalanceZqtzCalibrationAnalysis | null;
  structure_migration_analysis: BalanceStructureMigrationAnalysis | null;
  difference_attribution_waterfall: BalanceDifferenceAttributionWaterfall | null;
  basis_movement_decomposition?: BalanceBasisMovementDecomposition | null;
  zqtz_maturity_structure?: BalanceZqtzMaturityStructure | null;
  zqtz_concentration_analysis?: BalanceZqtzConcentrationAnalysis | null;
  accounting_controls: string[];
  excluded_controls: string[];
  calibration?: BalancePageCalibration | null;
};

export type BalanceMovementDatesPayload = {
  report_dates: string[];
  currency_basis: string;
  latest_read_model_report_date?: string | null;
  latest_upstream_control_report_date?: string | null;
  freshness_status?:
    | "fresh"
    | "read_model_lagging"
    | "read_model_empty"
    | "upstream_empty";
};

export type BalanceMovementRefreshPayload = {
  status: string;
  cache_key: string;
  report_date: string;
  currency_basis: string;
  run_id?: string | null;
  job_name?: string | null;
  trigger_mode?: string | null;
  row_count?: number | null;
  source_version?: string | null;
  rule_version: string;
  product_category_refreshed_dates?: string[];
  formal_balance_refreshed_dates?: string[];
  movement_refreshed_dates?: string[];
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

export type BalanceAnalysisMetricDefinition = {
  key: string;
  label: string;
  source_field: string;
  raw_unit: "yuan";
  display_unit: "yi_yuan";
  basis: "formal";
  source_surface: "formal_balance";
  applies_to: Array<"overview" | "summary" | "detail">;
  description: string;
};

export type BalanceAnalysisOverviewPayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  detail_row_count: number;
  summary_row_count: number;
  /** 当前 filters 下 ZQTZ+TYW 合计；`position_scope === "all"` 时为资产+负债加总。 */
  total_market_value_amount: DecimalLike;
  total_amortized_cost_amount: DecimalLike;
  total_accrued_interest_amount: DecimalLike;
  /** 正式事实表 `position_scope = asset` 侧加总（元）。`position_scope` 为单端时非零的一端为有效值。 */
  asset_total_market_value_amount: DecimalLike;
  liability_total_market_value_amount: DecimalLike;
  asset_total_amortized_cost_amount: DecimalLike;
  liability_total_amortized_cost_amount: DecimalLike;
  asset_total_accrued_interest_amount: DecimalLike;
  liability_total_accrued_interest_amount: DecimalLike;
  metric_definitions?: BalanceAnalysisMetricDefinition[];
  calibration?: BalancePageCalibration | null;
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
  status: "not_ready" | "partial";
  summary?: Record<string, string>;
  available_components?: string[];
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
  can_write_decision_status: boolean | null;
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
export type AgentPageContext = {
  page_id: string;
  current_filters: Record<string, unknown>;
  selected_rows: Array<Record<string, unknown>>;
  context_note?: string | null;
};

export type AgentConversationContextTurn = {
  question: string;
  answer: string;
  run_id?: string | null;
  trace_id?: string | null;
  result_kind?: string | null;
};

export type AgentConversationContext = {
  recent_turns: AgentConversationContextTurn[];
};

export type AgentRequestContext = {
  user_id?: string;
  user_role?: string;
  identity_source?: string;
  workflow_mode?: "execute" | string;
  intent?: string;
  conversation?: AgentConversationContext;
  [key: string]: unknown;
};

/** POST /api/agent/query — 字段缺省时由后端填入默认值（见 backend AgentQueryRequest）。 */
export type AgentQueryRequest = {
  question: string;
  basis?: "formal" | "scenario" | "analytical";
  filters?: Record<string, unknown>;
  position_scope?: string;
  currency_basis?: string;
  /** @deprecated Prefer `page_context`. Frontend AgentPanel no longer sends this field. */
  context?: AgentRequestContext;
  page_context?: AgentPageContext | null;
};

export type AgentDrill = {
  dimension: string;
  label: string;
};

export type AgentSuggestedAction = {
  type: string;
  label: string;
  payload: Record<string, unknown>;
  requires_confirmation: boolean;
  confirmation_token?: string | null;
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
  evidence_strength?: string;
};

export type AgentResultMeta = ResultMeta & {
  tables_used: string[];
  filters_applied: Record<string, unknown>;
  sql_executed: string[];
  evidence_rows: number;
  evidence_strength?: string;
  next_drill: AgentDrill[];
};

export type AgentEnvelope = {
  answer: string;
  cards: AgentCard[];
  evidence: AgentEvidence;
  result_meta: AgentResultMeta;
  next_drill: AgentDrill[];
  suggested_actions: AgentSuggestedAction[];
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

export type LedgerMoneyValue = {
  yuan: string;
  yi: string;
  wan?: string;
};

export type LedgerPnlDatesPayload = {
  dates: string[];
};

export type LedgerPnlDataItem = {
  account_code: string;
  account_name: string;
  currency: string;
  beginning_balance: LedgerMoneyValue;
  ending_balance: LedgerMoneyValue;
  monthly_pnl: LedgerMoneyValue;
  daily_avg_balance: LedgerMoneyValue;
  days_in_period: number;
};

export type LedgerPnlDataPayload = {
  data_status?: "ready" | "no_data";
  report_date: string;
  items: LedgerPnlDataItem[];
  summary: {
    total_pnl_cnx: LedgerMoneyValue;
    total_pnl_cny: LedgerMoneyValue;
    total_pnl: LedgerMoneyValue;
    count: number;
  };
};

export type LedgerPnlSummaryByCurrency = {
  currency: string;
  total_pnl: LedgerMoneyValue;
};

export type LedgerPnlSummaryByAccount = {
  account_code: string;
  account_name: string;
  total_pnl: LedgerMoneyValue;
  count: number;
};

export type LedgerPnlSummaryPayload = {
  data_status?: "ready" | "no_data";
  report_date: string;
  source_version: string;
  ledger_total_assets: LedgerMoneyValue;
  ledger_total_liabilities: LedgerMoneyValue;
  ledger_net_assets: LedgerMoneyValue;
  ledger_monthly_pnl_core: LedgerMoneyValue;
  ledger_monthly_pnl_all: LedgerMoneyValue;
  by_currency: LedgerPnlSummaryByCurrency[];
  by_account: LedgerPnlSummaryByAccount[];
};

export type LedgerPnlAnalysisDirection = "positive" | "negative" | "flat" | "unavailable";
export type LedgerPnlAnalysisOtherEffect = "support" | "drag" | "neutral" | "unavailable";
export type LedgerPnlAnalysisAvailability = "ready" | "no_data";

export type LedgerPnlAnalysisBridgeComponent = {
  metric_key: "core_pnl" | "other_5_pnl";
  metric_name: string;
  amount: LedgerMoneyValue | null;
};

export type LedgerPnlAnalysisBasisMetricKey =
  | "assets"
  | "liabilities"
  | "net_assets"
  | "core_pnl"
  | "all_pnl"
  | "other_5_pnl";

export type LedgerPnlAnalysisBasisComparisonRow = {
  metric_key: LedgerPnlAnalysisBasisMetricKey;
  metric_name: string;
  cnx: LedgerMoneyValue | null;
  cny: LedgerMoneyValue | null;
  cnx_minus_cny: LedgerMoneyValue | null;
  availability: {
    CNX: LedgerPnlAnalysisAvailability;
    CNY: LedgerPnlAnalysisAvailability;
  };
  evidence_rows: {
    CNX: number;
    CNY: number;
  };
};

export type LedgerPnlAnalysisContributor = {
  rank: number;
  account_code: string;
  account_name: string;
  amount: LedgerMoneyValue;
  count: number;
};

export type LedgerPnlAnalysisPeriodStatus =
  | "available"
  | "no_previous_period"
  | "current_basis_no_data"
  | "previous_basis_no_data";

export type LedgerPnlAnalysisPeriodRow = {
  metric_key: "core_pnl" | "other_5_pnl" | "all_pnl";
  metric_name: string;
  current: LedgerMoneyValue;
  previous: LedgerMoneyValue;
  change: LedgerMoneyValue;
};

export type LedgerPnlAnalysisPayload = {
  report_date: string;
  source_version: string;
  currency_basis: "CNX" | "CNY";
  basis_availability: {
    CNX: LedgerPnlAnalysisAvailability;
    CNY: LedgerPnlAnalysisAvailability;
  };
  analysis_status: "ready" | "no_data";
  metric_status: "candidate";
  conclusion: {
    direction: LedgerPnlAnalysisDirection;
    other_effect: LedgerPnlAnalysisOtherEffect;
    core_pnl: LedgerMoneyValue | null;
    other_5_pnl: LedgerMoneyValue | null;
    all_pnl: LedgerMoneyValue | null;
  };
  pnl_bridge: {
    components: LedgerPnlAnalysisBridgeComponent[];
    total: LedgerMoneyValue | null;
    residual: LedgerMoneyValue | null;
  };
  basis_comparison: LedgerPnlAnalysisBasisComparisonRow[];
  contributors: {
    positive_total: LedgerMoneyValue | null;
    negative_total: LedgerMoneyValue | null;
    net_total: LedgerMoneyValue | null;
    top_positive: LedgerPnlAnalysisContributor[];
    top_negative: LedgerPnlAnalysisContributor[];
  };
  period_comparison: {
    status: LedgerPnlAnalysisPeriodStatus;
    previous_report_date: string | null;
    previous_source_version: string | null;
    rows: LedgerPnlAnalysisPeriodRow[];
  };
  calculation_basis: {
    core_pnl_prefixes: string[];
    all_pnl_prefixes: string[];
    other_5_pnl_formula: string;
    other_5_pnl_boundary: string;
    basis_difference_formula: string;
    basis_boundary: string;
    basis_availability_boundary: string;
    metric_boundary: string;
    previous_period_rule: string;
    [key: string]: string | string[] | undefined;
  };
};

export type LedgerPnlAccountDetailPeriodStatus =
  | "available"
  | "current_account_no_data"
  | "no_previous_period"
  | "previous_account_no_data";

export type LedgerPnlAccountDetailBasisSnapshot = {
  report_date: string;
  source_version: string;
  cnx: LedgerMoneyValue | null;
  cny: LedgerMoneyValue | null;
  cnx_minus_cny: LedgerMoneyValue | null;
  availability: {
    CNX: LedgerPnlAnalysisAvailability;
    CNY: LedgerPnlAnalysisAvailability;
  };
  evidence_rows: {
    CNX: number;
    CNY: number;
  };
};

export type LedgerPnlAccountDetailCanonicalEvidenceRow = {
  period: "current" | "previous";
  report_date: string;
  source_version: string;
  account_code: string;
  account_name: string;
  currency: "CNX" | "CNY";
  beginning_balance: LedgerMoneyValue;
  ending_balance: LedgerMoneyValue;
  monthly_pnl: LedgerMoneyValue;
  days_in_period: number;
};

export type LedgerPnlAccountDetailPayload = {
  report_date: string;
  source_version: string;
  currency_basis: "CNX" | "CNY";
  analysis_status: "ready" | "no_data";
  metric_status: "candidate";
  account: {
    account_code: string;
    account_name: string | null;
  };
  period_comparison: {
    status: LedgerPnlAccountDetailPeriodStatus;
    previous_report_date: string | null;
    previous_source_version: string | null;
    current_monthly_pnl: LedgerMoneyValue | null;
    previous_monthly_pnl: LedgerMoneyValue | null;
    change: LedgerMoneyValue | null;
    current_evidence_rows: number;
    previous_evidence_rows: number;
  };
  basis_comparison: {
    current: LedgerPnlAccountDetailBasisSnapshot;
    previous: LedgerPnlAccountDetailBasisSnapshot | null;
  };
  canonical_evidence_rows: LedgerPnlAccountDetailCanonicalEvidenceRow[];
  calculation_basis: {
    account_match: "exact";
    amount_field: "monthly_pnl";
    change_formula: "current_monthly_pnl - previous_monthly_pnl";
    basis_difference_formula: "CNX - CNY";
    basis_boundary: string;
    previous_period_rule: string;
    evidence_boundary: string;
    metric_boundary: string;
  };
};

export type LedgerPnlFormalIndicatorSourceStatus =
  | "formal_pending"
  | "candidate_qdb_aligned"
  | "needs_reconciliation";

export type LedgerPnlCandidateFinancialIndicatorCalculationStatus =
  | "ready"
  | "warning"
  | "error"
  | "no_data";

export type LedgerPnlCandidateFinancialIndicatorMetricStatus =
  | "ok"
  | "warning"
  | "manual_default"
  | "error";

export type LedgerPnlCandidateFinancialIndicatorSource = {
  source_kind: "ledger" | "daily";
  file_name: string;
  exists: boolean;
  sha256: string | null;
  locked_sha256: string | null;
  locked_hash_match: boolean | null;
  sheets: string[];
  periods: LedgerPnlCandidateFinancialIndicatorPeriod[];
};

export type LedgerPnlCandidateFinancialIndicatorPeriod = {
  evidence_id:
    | "ledger"
    | "daily_ytd"
    | "daily_month"
    | "microloan_ytd"
    | "microloan_month"
    | "microloan_ledger";
  start: string;
  end: string;
  source_cell: string;
};

export type LedgerPnlCandidateFinancialIndicatorAccountLineage = {
  lineage_type: "account";
  source: "main" | "microloan" | "ledger" | "microloan_ledger";
  basis: "point" | "ytd_average" | "month_average" | "cumulative" | null;
  level: "l1" | "l2" | "l3" | "full";
  code: string;
  weight: string;
  observed: boolean;
  raw_yuan: string;
  contribution_yi: string;
  evidence_refs: string[];
};

export type LedgerPnlCandidateFinancialIndicatorMetricLineage = {
  lineage_type: "metric";
  metric_id: string;
  weight: string;
  metric_value_yi: string | null;
  contribution_yi: string | null;
  dependency_status: LedgerPnlCandidateFinancialIndicatorMetricStatus;
};

export type LedgerPnlCandidateFinancialIndicatorManualLineage = {
  lineage_type: "manual";
  supplied: boolean;
  value_yi: string;
};

export type LedgerPnlCandidateFinancialIndicatorLineage =
  | LedgerPnlCandidateFinancialIndicatorAccountLineage
  | LedgerPnlCandidateFinancialIndicatorMetricLineage
  | LedgerPnlCandidateFinancialIndicatorManualLineage;

export type LedgerPnlCandidateFinancialIndicatorMetric = {
  metric_id: string;
  name: string;
  category: string;
  basis: "point" | "ytd_average" | "month_average" | "cumulative";
  unit: "亿元";
  value: string | null;
  status: LedgerPnlCandidateFinancialIndicatorMetricStatus;
  reasons: string[];
  lineage: LedgerPnlCandidateFinancialIndicatorLineage[];
};

export type LedgerPnlCandidateFinancialIndicatorValidation = {
  validation_id: string;
  severity: "warning" | "error";
  passed: boolean;
  message: string;
  delta_yi: string | null;
  sample: string[];
};

export type LedgerPnlCandidateFinancialIndicatorGap = {
  gap_id: string;
  severity: "info" | "warning" | "error";
  kind:
    | "source_missing"
    | "source_hash"
    | "source_parse"
    | "validation"
    | "missing_account"
    | "manual_input"
    | "calculation";
  title: string;
  detail: string;
  metric_ids: string[];
};

export type LedgerPnlCandidateFinancialIndicatorPromotionCheck = {
  check_id:
    | "rule_asset"
    | "source_evidence"
    | "validation_controls"
    | "manual_inputs"
    | "account_coverage"
    | "formal_contract";
  label: string;
  status: "passed" | "blocked" | "not_evaluated";
  blocking: boolean;
  summary: string;
  evidence_refs: string[];
  action: string;
};

export type LedgerPnlCandidatePromotionOwnerRequirement = {
  requirement_id: string;
  category:
    | "source_evidence"
    | "validation_control"
    | "manual_input"
    | "account_coverage"
    | "formal_contract"
    | "business_owner_approval";
  status: "awaiting_owner_input";
  submitted_value: null;
  evidence_refs: string[];
  required_evidence: string[];
  action: string;
};

export type LedgerPnlCandidatePromotionEvidencePack = {
  contract_version: "candidate-promotion-evidence-v1";
  evidence_pack_key: string;
  report_month: string;
  report_date: string;
  rule_version: "qdb-finance-2026-v1.0.0" | "qdb-finance-2026-v1.0.1";
  rule_hash: string;
  source_version: string;
  source_alignment: "matched" | "mismatch" | "not_applicable" | "incomplete";
  candidate_idempotency_key: string;
  readiness_contract_version: "promotion-readiness-v1";
  readiness_evidence_key: string;
  metric_status: "candidate";
  formal_use_allowed: false;
  owner_approval_required: true;
  contains_metric_values: false;
  contains_formal_values: false;
  certification_effect: "none";
  blocking_count: number;
  check_total: 6;
  formal_contract_status: "missing_contract" | "contract_fixture" | "unavailable";
  formal_sample_id: string;
  formal_source_version: string;
  formal_release_gate_status: string | null;
  formal_metric_count: number;
  checks: LedgerPnlCandidateFinancialIndicatorPromotionCheck[];
  owner_requirement_count: number;
  owner_requirements: LedgerPnlCandidatePromotionOwnerRequirement[];
  outcome_status: "blocked" | "awaiting_owner_approval";
};

export type LedgerPnlCandidateFinancialIndicatorPromotionReadiness = {
  readiness_contract_version: "promotion-readiness-v1";
  readiness_evidence_key: string;
  status: "blocked" | "review_required";
  blocking_count: number;
  check_total: 6;
  candidate_idempotency_key: string;
  formal_contract_status: "missing_contract" | "contract_fixture" | "unavailable";
  formal_use_allowed: false;
  owner_approval_required: true;
  next_action: string;
  checks: LedgerPnlCandidateFinancialIndicatorPromotionCheck[];
  evidence_pack: LedgerPnlCandidatePromotionEvidencePack;
};

export type LedgerPnlCandidateSourceVersionImpact = {
  contract_version: "candidate-source-version-impact-v1";
  impact_asset_sha256: string;
  status: "numerically_unchanged" | "numeric_digest_mismatch" | "comparison_incomplete";
  comparison_basis: "canonical_decimal_value";
  report_month: string;
  reference_rule_version: "qdb-finance-2026-v1.0.0";
  current_rule_version: "qdb-finance-2026-v1.0.1";
  reference_result_sha256: string;
  reference_ledger_sha256: string;
  current_ledger_sha256: string;
  daily_sha256: string;
  metric_total: 186;
  compared_metric_count: number;
  reference_numeric_digest: string;
  current_numeric_digest: string;
  numeric_changed_count: number | null;
  serialization_only_count: number;
  serialization_only_metric_ids: string[];
  formal_use_allowed: false;
  certification_effect: "none";
};

export type LedgerPnlCandidateFinancialIndicatorsPayload = {
  report_month: string;
  report_date: string;
  currency: "CNX";
  basis: "ledger";
  metric_status: "candidate";
  formal_use_allowed: false;
  calculation_status: LedgerPnlCandidateFinancialIndicatorCalculationStatus;
  source_alignment: "matched" | "mismatch" | "not_applicable" | "incomplete";
  source_version: string;
  rule_version: "qdb-finance-2026-v1.0.0" | "qdb-finance-2026-v1.0.1";
  rule_hash: string;
  idempotency_key: string;
  requested_metric_id: string | null;
  include_lineage: boolean;
  source_version_impact?: LedgerPnlCandidateSourceVersionImpact | null;
  promotion_readiness: LedgerPnlCandidateFinancialIndicatorPromotionReadiness;
  sources: LedgerPnlCandidateFinancialIndicatorSource[];
  summary: {
    metric_total: 186;
    metric_evaluated: number;
    metric_returned: number;
    ok_count: number;
    warning_count: number;
    manual_default_count: number;
    error_count: number;
    validation_total: 12;
    validation_evaluated: number;
    validation_passed: number;
    validation_warning_failed: number;
    validation_error_failed: number;
  };
  metrics: LedgerPnlCandidateFinancialIndicatorMetric[];
  validations: LedgerPnlCandidateFinancialIndicatorValidation[];
  gaps: LedgerPnlCandidateFinancialIndicatorGap[];
};

export type LedgerPnlCandidateFinancialIndicatorsFilters = {
  report_month: string;
  include_lineage: boolean;
  metric_id: string | null;
};

export type LedgerPnlCandidateFinancialIndicatorsResultMeta = Omit<
  ResultMeta,
  | "basis"
  | "result_kind"
  | "formal_use_allowed"
  | "cache_key"
  | "quality_flag"
  | "vendor_status"
  | "fallback_mode"
  | "requested_report_date"
  | "resolved_report_date"
  | "scenario_flag"
  | "as_of_date"
  | "date_basis"
  | "fallback_date"
  | "filters_applied"
  | "tables_used"
  | "evidence_rows"
  | "next_drill"
  | "source_surface"
> & {
  basis: "ledger";
  result_kind: "ledger_pnl.candidate_financial_indicators";
  formal_use_allowed: false;
  amount_currency_basis: "CNX";
  amount_currency_basis_note: string;
  cache_key: string;
  quality_flag: "ok" | "warning" | "error";
  vendor_status: "ok";
  fallback_mode: "none";
  requested_report_date: string;
  resolved_report_date: string;
  scenario_flag: false;
  as_of_date: string;
  date_basis: "report_month_end";
  fallback_date: null;
  filters_applied: LedgerPnlCandidateFinancialIndicatorsFilters;
  tables_used: string[];
  evidence_rows: number;
  next_drill: ResultNextDrill[];
  source_surface: null;
};

export type LedgerPnlCandidateFinancialIndicatorsEnvelope = {
  result_meta: LedgerPnlCandidateFinancialIndicatorsResultMeta;
  result: LedgerPnlCandidateFinancialIndicatorsPayload;
};

export type LedgerPnlCandidateFinancialIndicatorManualOverride = {
  value_yi: string;
  submitted_evidence_refs: string[];
};

export type LedgerPnlCandidateFinancialIndicatorRevalidationRequest = {
  base_candidate_idempotency_key: string;
  base_evidence_pack_key: string;
  manual_overrides: Record<string, LedgerPnlCandidateFinancialIndicatorManualOverride>;
};

export type LedgerPnlCandidateRequirementResolutionStatus =
  | "awaiting_owner_input"
  | "evidence_received"
  | "validation_failed"
  | "verified";

export type LedgerPnlCandidateRequirementResolutionItem = {
  requirement_id: string;
  status: LedgerPnlCandidateRequirementResolutionStatus;
  status_detail: string;
  submitted_evidence_refs: string[];
  validation_evidence_refs: string[];
};

export type LedgerPnlCandidateRequirementResolution = {
  contract_version: "candidate-promotion-resolution-v1";
  resolution_key: string;
  base_evidence_pack_key: string;
  result_evidence_pack_key: string;
  base_requirement_ids: string[];
  requirements: LedgerPnlCandidateRequirementResolutionItem[];
};

export type LedgerPnlCandidateFinancialIndicatorRevalidationReceipt = {
  contract_version: "candidate-financial-indicator-revalidation-v1";
  revalidation_effect: "none";
  persisted: false;
  formal_use_allowed: false;
  base_candidate_idempotency_key: string;
  base_evidence_pack_key: string;
  manual_override_count: number;
  requirement_resolution: LedgerPnlCandidateRequirementResolution;
  result: LedgerPnlCandidateFinancialIndicatorsEnvelope;
};

export type LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus =
  | "ok"
  | "warning"
  | "manual_default"
  | "error"
  | "missing";

export type LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod = {
  month: string;
  report_date: string;
  ledger_file_name: string;
  ledger_sha256: string;
  locked_sha256: string | null;
  lock_status: "locked_match" | "locked_mismatch" | "unlocked";
};

export type LedgerPnlCandidateFinancialIndicatorPeriodComparisonMetric = {
  metric_id: string;
  metric_name: string;
  basis: "calendar_month_from_cumulative" | "month_end_point";
  method: "finance_metric_cumulative_mom" | "finance_metric_point_to_point";
  unit: "亿元";
  comparison_status: "comparable" | "not_comparable";
  current_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus;
  previous_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus;
  two_month_prior_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus | null;
  current_value_yi: string | null;
  previous_value_yi: string | null;
  current_source_value_yi: string | null;
  previous_source_value_yi: string | null;
  two_month_prior_source_value_yi: string | null;
  delta_yi: string | null;
  change_rate: string | null;
  rate_reason: "zero_denominator" | "missing_reference" | "metric_status_not_ok" | null;
  reasons: string[];
  driver_status: "unclear";
  quality_status: "standard_candidate" | "degraded_candidate" | "not_comparable";
};

export type LedgerPnlCandidateFinancialIndicatorNetInterestComponent = {
  metric_id: string;
  metric_name: string;
  formula_weight: -1 | 1;
  current_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus;
  previous_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus;
  two_month_prior_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus;
  current_value_yi: string | null;
  previous_value_yi: string | null;
  current_source_value_yi: string | null;
  previous_source_value_yi: string | null;
  two_month_prior_source_value_yi: string | null;
  component_delta_yi: string | null;
  contribution_to_net_delta_yi: string | null;
  reasons: string[];
};

export type LedgerPnlCandidateFinancialIndicatorNetInterestComponentBridge = {
  analysis_kind: "accounting_component_bridge";
  status: "available" | "not_evaluable";
  metric_id: "income.interest.net";
  basis: "calendar_month_from_cumulative";
  method: "finance_metric_component_contribution";
  unit: "亿元";
  quality_status: "standard_candidate" | "degraded_candidate" | "not_evaluable";
  foot_status: "passed" | "failed" | "not_evaluable";
  net_delta_yi: string | null;
  component_contribution_total_yi: string | null;
  reconciliation_delta_yi: string | null;
  reasons: string[];
  components: LedgerPnlCandidateFinancialIndicatorNetInterestComponent[];
};

export type LedgerPnlCandidateFinancialIndicatorFullScopeGap = {
  reason_code:
    | "missing_source_file"
    | "missing_required_sheet"
    | "source_parse_error"
    | "full_replay_incomplete"
    | "source_evaluation_error";
  source_kind: "ledger" | "daily";
  month: string;
  required_sheet: string | null;
};

export type LedgerPnlCandidateFinancialIndicatorPeriodComparison = {
  contract_version: "candidate-financial-indicator-period-comparison-v2";
  report_month: string;
  report_date: string;
  comparison_month: string;
  two_month_prior: string;
  comparison_scope: "ledger_only_key_metrics";
  full_scope_status: "available" | "unavailable";
  full_scope_reason_code:
    | "available"
    | "missing_source_file"
    | "missing_required_sheet"
    | "source_parse_error"
    | "full_replay_incomplete"
    | "source_evaluation_error";
  full_scope_detail: string;
  full_scope_gaps: LedgerPnlCandidateFinancialIndicatorFullScopeGap[];
  overall_status: "available" | "partial" | "unavailable";
  metric_status: "candidate";
  formal_use_allowed: false;
  certification_effect: "none";
  driver_status: "unclear";
  rule_version: "qdb-finance-2026-v1.0.1";
  rule_hash: string;
  idempotency_key: string;
  source_periods: LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod[];
  net_interest_component_bridge: LedgerPnlCandidateFinancialIndicatorNetInterestComponentBridge;
  metrics: LedgerPnlCandidateFinancialIndicatorPeriodComparisonMetric[];
};

export type LedgerPnlCandidateFinancialIndicatorComponentMetricId =
  | "income.interest.loan.total"
  | "expense.interest.deposit.total"
  | "income.interest.investment"
  | "income.interest.interbank_net";

export type LedgerPnlCandidateFinancialIndicatorComponentMatchedTerm = {
  source: "ledger";
  level: "l1" | "l2" | "l3" | "full";
  code: string;
  weight: string;
};

export type LedgerPnlCandidateFinancialIndicatorComponentSourceEvidence = {
  month: string;
  report_date: string;
  ledger_file_name: string;
  ledger_sha256: string;
  locked_sha256: string | null;
  lock_status: "locked_match" | "unlocked";
  sheet: "综本";
  row: number;
  account_code_cell: string;
  ending_cell: string;
  ending_yuan: string;
};

export type LedgerPnlCandidateFinancialIndicatorComponentDetailRow = {
  row_status: "contributing" | "excluded_offset";
  account_code: string;
  account_name: string;
  currency: "CNX";
  effective_component_weight: string;
  effective_net_weight: string;
  matched_terms: LedgerPnlCandidateFinancialIndicatorComponentMatchedTerm[];
  current_ending_yuan: string;
  previous_ending_yuan: string;
  two_month_prior_ending_yuan: string;
  current_value_yi: string;
  previous_value_yi: string;
  component_delta_yi: string;
  contribution_to_net_delta_yi: string;
  source_evidence: LedgerPnlCandidateFinancialIndicatorComponentSourceEvidence[];
};

export type LedgerPnlCandidateFinancialIndicatorComponentDetail = {
  contract_version: "candidate-financial-indicator-component-detail-v1";
  analysis_kind: "accounting_component_account_detail";
  report_month: string;
  report_date: string;
  comparison_month: string;
  two_month_prior: string;
  metric_id: LedgerPnlCandidateFinancialIndicatorComponentMetricId;
  metric_name: string;
  formula_weight: -1 | 1;
  currency: "CNX";
  basis: "calendar_month_from_cumulative";
  method: "finance_metric_account_contribution";
  unit: "亿元";
  status: "available" | "not_evaluable" | "stale_parent";
  quality_status: "standard_candidate" | "degraded_candidate" | "not_evaluable";
  foot_status: "passed" | "failed" | "not_evaluable";
  formal_use_allowed: false;
  certification_effect: "none";
  driver_status: "unclear";
  rule_version: "qdb-finance-2026-v1.0.1";
  rule_hash: string;
  parent_idempotency_key: string;
  idempotency_key: string;
  source_periods: LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod[];
  parent_current_value_yi: string | null;
  parent_previous_value_yi: string | null;
  parent_component_delta_yi: string | null;
  parent_contribution_to_net_delta_yi: string | null;
  account_current_total_yi: string | null;
  account_previous_total_yi: string | null;
  account_component_delta_total_yi: string | null;
  account_contribution_total_yi: string | null;
  current_reconciliation_yi: string | null;
  previous_reconciliation_yi: string | null;
  component_delta_reconciliation_yi: string | null;
  contribution_reconciliation_yi: string | null;
  reasons: string[];
  rows: LedgerPnlCandidateFinancialIndicatorComponentDetailRow[];
};

export type LedgerPnlFormalFinancialIndicatorMetric = {
  metric_key: string;
  metric_name: string;
  scope: string;
  excel_value: string;
  unit: string;
  excel_ref: string;
  formula: string;
  source_status: LedgerPnlFormalIndicatorSourceStatus;
  system_metric: string | null;
  system_value: string | null;
  reconciliation_gap?: string | null;
  value: string | number | null;
  basis: "formal_financial_indicator_source_contract";
  formal_use_allowed: boolean;
  source_version: string;
  rule_version: string;
  consolidation_scope: string;
  cell_ref: string;
  golden_sample_ref: string;
  missing_reason: string;
};

export type LedgerPnlFormalFinancialIndicatorRemediation = {
  required: boolean;
  action_label: string;
  action_detail: string;
  required_artifact: string;
  artifact_status?: "missing" | "available" | string;
  blocking_reason?: string;
  acceptance_criteria?: string[];
  registration_package?: {
    fixture_target?: string;
    registry_target?: string;
    contract_builder?: string;
    release_gate?: string;
  };
  registration_package_guard?: {
    status?: string;
    required_fields?: string[];
    missing_fields?: string[];
    blocking_rule?: string;
  };
  readback_acceptance?: {
    label?: string;
    readback_query?: string;
    target_state?: string;
    release_state?: string;
    formal_use_guard?: string;
    source_guard?: string;
    verification?: string;
  };
  registration_target: string;
  verification: string;
};

export type LedgerPnlFormalFinancialIndicatorContractPayload = {
  sample_id: string;
  sample_status: string;
  surface: string;
  report_month: string;
  report_date: string;
  source_workbook: string;
  source_sheet: string;
  source_basis: string;
  source_version: string;
  rule_version: string;
  formal_use_allowed: boolean;
  contract_note: string;
  release_gate?: {
    status?: string;
    blocking_reason?: string;
    required_evidence?: string[];
    readback_action?: string;
  };
  status_semantics: Record<LedgerPnlFormalIndicatorSourceStatus, string>;
  remediation?: LedgerPnlFormalFinancialIndicatorRemediation;
  metrics: LedgerPnlFormalFinancialIndicatorMetric[];
};

export type LedgerPnlRatioRecomputationStatus = "matched" | "mismatch" | "insufficient_inputs";

export type LedgerPnlRatioRecomputationCheck = {
  check_key: string;
  metric_name: string;
  contract_metric_key: string;
  contract_value: string;
  unit: string;
  status: LedgerPnlRatioRecomputationStatus;
  formula?: string;
  numerator_metric_key?: string;
  numerator_value?: string;
  denominator_metric_key?: string;
  denominator_value?: string;
  recomputed_value?: string;
  diff?: string;
  tolerance?: string;
  missing_inputs?: string[];
  note?: string;
};

export type LedgerPnlAdditivityCheckStatus = "exact" | "residual_present";

export type LedgerPnlAdditivityComponent = {
  metric_key: string;
  value: string;
};

export type LedgerPnlAdditivityCheck = {
  check_key: string;
  metric_name: string;
  total_metric_key: string;
  total_value: string;
  components: LedgerPnlAdditivityComponent[];
  components_sum: string;
  residual: string;
  unit: string;
  status: LedgerPnlAdditivityCheckStatus;
  note?: string;
};

export type LedgerPnlArrangementRuleStatus =
  | "pass"
  | "fail"
  | "insufficient_inputs"
  | "informational"
  | "summary";

export type LedgerPnlArrangementRule = {
  rule_key: string;
  rule_name: string;
  source_ref: string;
  status: LedgerPnlArrangementRuleStatus;
  missing_inputs?: string[];
  note?: string;
  quarter_end_type?: string;
  actual_value?: string;
  target_value?: string;
  comparator?: string;
  unit?: string;
  assumption_value?: string;
  assumption_unit?: string;
  referenced_additivity_check_keys?: string[];
  exact_count?: number;
  residual_present_count?: number;
};

export type LedgerPnlFormalIndicatorRuleChecksSummary = {
  ratio_recomputation: { matched: number; mismatch: number; insufficient_inputs: number; total: number };
  additivity_checks: { exact: number; residual_present: number; total: number };
  arrangement_rules: {
    pass: number;
    fail: number;
    insufficient_inputs: number;
    informational: number;
    summary: number;
    total: number;
  };
  total_checks: number;
};

export type LedgerPnlFormalIndicatorRuleChecksPayload = {
  report_month: string;
  report_date: string;
  basis: string;
  formal_use_allowed: boolean;
  sample_status: string;
  source_version: string;
  rule_version: string;
  contract_note: string;
  ratio_recomputation: LedgerPnlRatioRecomputationCheck[];
  additivity_checks: LedgerPnlAdditivityCheck[];
  arrangement_rules: LedgerPnlArrangementRule[];
  summary: LedgerPnlFormalIndicatorRuleChecksSummary;
  remediation?: LedgerPnlFormalFinancialIndicatorRemediation;
};

export type CampisiFourEffectsTotals = {
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
  summary: CampisiDecisionGradeSummary;
  formal_pnl_view: {
    total_actual_pnl: number;
    explained_pnl: number;
    residual_noise: number;
    components: CampisiDecisionComponents;
    closure: {
      status: "closed" | "warning";
      difference: number;
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

export type CampisiFourEffectsRow = {
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

export type CampisiEnhancedRow = {
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
};

export type BondDashboardBundlePayload = {
  report_date: string | null;
  requested_sections: BondDashboardBundleSectionId[];
  sections: Partial<BondDashboardBundleSectionEnvelopeMap>;
  section_statuses?: Partial<Record<BondDashboardBundleSectionId, BondDashboardBundleSectionStatus>>;
  failed_sections?: BondDashboardBundleSectionId[];
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
  amount?: Numeric | null;
  amount_yi?: Numeric | null;
};

export type LiabilityNameAmountItem = {
  name: string;
  amount?: Numeric | null;
  amount_yi?: Numeric | null;
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
  asset_yield: Numeric | null;
  liability_cost: Numeric | null;
  market_liability_cost: Numeric | null;
  nim: Numeric | null;
  nim_stress?: LiabilityNimStress | null;
};

export type LiabilityNimStress = {
  nim_stressed: Numeric | null;
  delta_bp: Numeric | null;
};

export type LiabilityYieldHistoryPoint = {
  date: string;
  asset_yield: number | null;
  liability_cost: number | null;
  market_liability_cost: number | null;
  nim: number | null;
};

export type LiabilityYieldScatterPoint = {
  x: number;
  y: number;
  z: number;
  name: string;
};

export type LiabilityYieldMetricsPayload = {
  report_date: string;
  kpi: LiabilityYieldKpi;
  history?: LiabilityYieldHistoryPoint[];
  scatter?: LiabilityYieldScatterPoint[];
};

/** V1-compatible `/api/analysis/yield-by-period` payload (periods empty when the year has no PnL rollups). */
export type YieldByPeriodSummary = {
  period: string;
  period_type: string;
  start_date: string;
  end_date: string;
  num_days: number;
  total_avg_balance: number;
  total_pnl: number;
  overall_yield: number | null;
  overall_annualized_yield: number | null;
  weighted_portfolio_yield: number | null;
  weighted_portfolio_annualized_yield: number | null;
  items: unknown[];
};

export type YieldByPeriodPayload = {
  period_type: string;
  year: number;
  periods: YieldByPeriodSummary[];
};

export type LiabilityCounterpartyItem = {
  name: string;
  value?: Numeric | null;
  type: string;
  weighted_cost?: Numeric | null;
};

export type LiabilityCounterpartyTypeSlice = {
  name: string;
  value?: Numeric | null;
};

export type LiabilityCounterpartyPayload = {
  report_date: string;
  total_value: Numeric;
  top_10: LiabilityCounterpartyItem[];
  by_type: LiabilityCounterpartyTypeSlice[];
};

export type LiabilityKnowledgeNote = {
  id: string;
  title: string;
  summary: string;
  why_it_matters: string;
  key_questions: string[];
  source_path: string;
};

export type LiabilityKnowledgeBriefPayload = {
  page_id: string;
  available: boolean;
  vault_path: string | null;
  status_note: string | null;
  notes: LiabilityKnowledgeNote[];
};

/** 与后端 `LiabilityMonthlyBreakdownRow` 对齐。 */
export type LiabilityMonthlyBreakdownRow = {
  category?: string | null;
  bucket?: string | null;
  type?: string | null;
  name?: string | null;
  avg_balance?: Numeric | null;
  avg_value?: Numeric | null;
  proportion?: Numeric | null;
  amount?: Numeric | null;
  pct?: Numeric | null;
  weighted_cost?: Numeric | null;
};

export type LiabilitiesMonthlyItem = {
  month: string;
  month_label: string;
  avg_total_liabilities: Numeric | null;
  avg_interbank_liabilities: Numeric | null;
  avg_issued_liabilities: Numeric | null;
  avg_liability_cost: Numeric | null;
  mom_change: Numeric | null;
  mom_change_pct: Numeric | null;
  counterparty_top10?: LiabilityMonthlyBreakdownRow[];
  by_institution_type?: LiabilityMonthlyBreakdownRow[];
  structure_overview?: LiabilityMonthlyBreakdownRow[];
  term_buckets?: LiabilityMonthlyBreakdownRow[];
  interbank_by_type?: LiabilityMonthlyBreakdownRow[];
  interbank_term_buckets?: LiabilityMonthlyBreakdownRow[];
  issued_by_type?: LiabilityMonthlyBreakdownRow[];
  issued_term_buckets?: LiabilityMonthlyBreakdownRow[];
  counterparty_details?: LiabilityMonthlyBreakdownRow[];
  num_days: number;
};

export type LiabilitiesMonthlyPayload = {
  year: number;
  months: LiabilitiesMonthlyItem[];
  ytd_avg_total_liabilities: Numeric | null;
  ytd_avg_liability_cost: Numeric | null;
};

export type CockpitWatchItem = {
  id: string;
  label: string;
  level: "watch" | "warning";
  detail: string;
};

export type CockpitAlertEvent = {
  id: string;
  severity: "high" | "medium" | "low";
  title: string;
  occurred_at: string;
  detail: string;
};

export type CockpitWarningsPayload = {
  report_date: string;
  watch_items: CockpitWatchItem[];
  alert_events: CockpitAlertEvent[];
};

export type ContributionSplitRow = {
  category: string;
  side: "asset" | "liability";
  amount_yi: number | null;
  yield_or_cost: number | null;
  contribution_yi: number | null;
};

export type ContributionSplitPayload = {
  report_date: string;
  contributions: ContributionSplitRow[];
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

export type AdbCategoryItem = {
  category: string;
  spot_balance: number;
  avg_balance: number | null;
  proportion: number;
  weighted_rate?: number | null;
  rate_coverage_ratio?: number | null;
};

export type AdbAccountingBasisDailyAvgItem = {
  basis_bucket: "AC" | "OCI" | "TPL" | string;
  daily_avg_balance: number | null;
  daily_avg_pct: number | null;
  source_account_patterns: string[];
};

export type AdbAccountingBasisDailyAvg = {
  report_date: string;
  report_month?: string;
  currency_basis: string;
  daily_avg_total: number | null;
  rows: AdbAccountingBasisDailyAvgItem[];
  accounting_controls: string[];
  excluded_controls: string[];
};

export type AdbAccountingBasisDailyAvgTrendItem = AdbAccountingBasisDailyAvg & {
  report_month: string;
};

export type AdbComparisonResponse = {
  result_meta?: ResultMeta;
  report_date: string;
  start_date: string;
  end_date: string;
  /** 用户选择的起止日期对应的日历天数（含首尾），不因 ledger 加权而改变 */
  calendar_days_inclusive: number;
  /**
   * formal_calendar：数据来自 fact_formal_*（CNY 物化）；日均对比分母仍为查询区间日历天数。
   * snapshot_calendar：无 formal 表时回退快照；与页面“7日/30日/年初至今”观察窗口一致。
   * snapshot_distinct_days / ledger_weighted：历史兼容值。
   */
  adb_denominator_basis:
    | "formal_calendar"
    | "snapshot_distinct_days"
    | "snapshot_calendar"
    | "ledger_weighted";
  /** 与区间日均口径一致的分母：有快照时为上述不重复日期数；无数据时为 0 */
  num_days: number;
  /** 正式表中实际覆盖的不重复日期数（可能 < num_days）；未覆盖日由 sample_fill 补全 */
  coverage_days?: number;
  /** 是否触发了 sample_fill（coverage < calendar 时自动放大） */
  sample_filled?: boolean;
  /** sample_fill 补全方法标识 */
  sample_fill_method?: string;
  simulated: boolean;
  total_spot_assets: number;
  total_avg_assets: number;
  total_spot_liabilities: number;
  total_avg_liabilities: number;
  /** 同业（TYW）区间日均资产（元）；分母与 num_days（快照 distinct 日数）一致 */
  total_avg_interbank_assets: number;
  /** 同业（TYW）区间日均负债（元） */
  total_avg_interbank_liabilities: number;
  asset_yield: number | null;
  liability_cost: number | null;
  net_interest_margin: number | null;
  asset_rate_coverage_ratio?: number | null;
  liability_rate_coverage_ratio?: number | null;
  assets_breakdown: AdbCategoryItem[];
  liabilities_breakdown: AdbCategoryItem[];
  accounting_basis_daily_avg?: AdbAccountingBasisDailyAvg;
  /** 区间内每个 report_date 的 AC/OCI/TPL 日均结构（与月度接口中 trend 项结构一致） */
  accounting_basis_daily_avg_trend?: AdbAccountingBasisDailyAvgTrendItem[];
  detail?: string;
  calibration?: BalancePageCalibration | null;
};

export type AdbMonthlyBreakdownItem = {
  category: string;
  avg_balance: number | null;
  proportion?: number | null;
  weighted_rate?: number | null;
  rate_coverage_ratio?: number | null;
};

export type AdbMonthlyDataItem = {
  month: string;
  month_label: string;
  num_days: number;
  avg_assets: number | null;
  avg_liabilities: number | null;
  asset_yield: number | null;
  liability_cost: number | null;
  net_interest_margin: number | null;
  asset_rate_coverage_ratio?: number | null;
  liability_rate_coverage_ratio?: number | null;
  mom_change_assets: number | null;
  mom_change_pct_assets: number | null;
  mom_change_liabilities: number | null;
  mom_change_pct_liabilities: number | null;
  breakdown_assets: AdbMonthlyBreakdownItem[];
  breakdown_liabilities: AdbMonthlyBreakdownItem[];
};

export type AdbMonthlyResponse = {
  result_meta?: ResultMeta;
  year: number;
  months: AdbMonthlyDataItem[];
  accounting_basis_daily_avg_trend?: AdbAccountingBasisDailyAvgTrendItem[];
  ytd_avg_assets: number | null;
  ytd_avg_liabilities: number | null;
  ytd_asset_yield: number | null;
  ytd_liability_cost: number | null;
  ytd_nim: number | null;
  ytd_asset_rate_coverage_ratio?: number | null;
  ytd_liability_rate_coverage_ratio?: number | null;
  unit?: string;
};

/** `GET /api/analysis/adb/coverage` 只读诊断（快照 vs formal 日期覆盖） */
export type AdbCoverageTableBlock = {
  dates_count: number;
  dates: string[];
  error?: string;
};

export type AdbCoveragePayload = {
  start_date: string;
  end_date: string;
  calendar_days: number;
  snapshot_tables: Record<string, AdbCoverageTableBlock>;
  formal_tables: Record<string, AdbCoverageTableBlock>;
  snapshot_date_count: number;
  formal_date_count: number;
  missing_dates: string[];
  missing_count: number;
  coverage_pct: number;
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
