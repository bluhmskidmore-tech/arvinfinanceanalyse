/** Market data, Choice/macro/FX/news feeds, and Livermore stock-analysis/candidate-screening contracts. */
import type { ApiQuality } from "./core";
import type { DecimalLike } from "./pnl";

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
  payload_json_included?: boolean;
  stock_code?: string | null;
  stock_filter_mode?: string | null;
  stock_filter_tokens?: string[];
  compare?: ChoiceNewsComparePayload;
  events: ChoiceNewsEvent[];
};

/** 与 `GET /ui/news/choice-events/latest` 返回的 `result.events[]` 单行一致（后端 payload_rows）。 */
export type ChoiceNewsLatestEvent = ChoiceNewsEvent;

/** 与 `GET /ui/news/choice-events/latest` 的 `result` 对象一致。 */
export type ChoiceNewsLatestPayload = ChoiceNewsEventsPayload;

/**
 * 与 `GET /ui/news/choice-events/latest-batch` 的 `result.batches[]` 单项一致。
 * `key` 为 `topic:<code>` 或 `group:<gid>`；events 元素与单查端点完全一致。
 */
export type ChoiceNewsEventsBatchItem = {
  key: string;
  topic_code: string | null;
  group_id: string | null;
  events: ChoiceNewsEvent[];
};

/** 与 `GET /ui/news/choice-events/latest-batch` 的 `result` 对象一致（batches 顺序与请求顺序一致，先 topics 后 groups）。 */
export type ChoiceNewsEventsBatchPayload = {
  batches: ChoiceNewsEventsBatchItem[];
};

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
