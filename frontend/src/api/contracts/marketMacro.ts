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
  display_name?: string | null;
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
  display_name?: string | null;
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

export type MarketOverviewPartitionStatus = "ok" | "degraded" | "unavailable";

export type MarketOverviewDirectionalCoverage = {
  expected_count: number;
  valid_count: number;
  missing_keys: string[];
  status: "complete" | "insufficient" | string;
};

export type MarketOverviewConclusion = {
  stance?: string | null;
  tone?: string | null;
  summary?: string | null;
  recommended_action?: string | null;
  basis?: {
    source?: string | null;
    signal_cards?: Array<Pick<MarketOverviewSignalCard, "key" | "tone">>;
    directional_coverage?: MarketOverviewDirectionalCoverage;
  } | null;
};

export type MarketOverviewGateIssue = {
  key: string;
  label: string;
  reason: string;
  impact: string;
  route: string;
};

export type MarketOverviewComponent = {
  status: MarketOverviewPartitionStatus;
  reason: string | null;
  quality_flag: string | null;
  vendor_status: string | null;
  basis: string | null;
  cache_key: string | null;
  fallback_mode: "none" | "latest_snapshot" | null;
  fallback_date: string | null;
  formal_use_allowed: boolean | null;
};

export type MarketOverviewGate = {
  level: "ok" | "review" | "blocked";
  reason_code: string;
  human_reason: string;
  recovery_action: string;
  conclusion: MarketOverviewConclusion;
  issues?: MarketOverviewGateIssue[];
  evidence: {
    receipt_status?: string | null;
    receipt_generated_at?: string | null;
    receipt_age_hours?: number | null;
    missing_field_count?: number | null;
  };
};

export type MarketOverviewDateSurface = {
  key: "rates_formal" | "choice_latest" | "macro_analysis" | "news" | "strategy" | string;
  source: string;
  status: MarketOverviewPartitionStatus;
  reason: string | null;
  latest: string | null;
  age_days: number | null;
  basis: "trade_date" | "received_at" | string;
};

export type MarketOverviewDates = {
  status: MarketOverviewPartitionStatus;
  surfaces: MarketOverviewDateSurface[];
  tape_span: { earliest: string | null; latest: string | null };
  computed_on: string;
  date_basis: "calendar_day";
};

export type MarketOverviewTapeSlot = {
  key: string;
  label: string;
  kind: "rate" | "equity" | "commodity" | "fx" | string;
  status: MarketOverviewPartitionStatus | "unresolved";
  reason: string | null;
  value: number | null;
  unit: string | null;
  change: number | null;
  change_unit: string | null;
  trade_date: string | null;
  series_id: string | null;
  series_name: string | null;
  vendor: string | null;
  basis: string | null;
  fallback_mode: "none" | "latest_snapshot" | null;
  fallback_date: string | null;
  formal_use_allowed: boolean | null;
  quality_flag: string;
  tone_hint: "up" | "down" | "flat" | "unavailable" | string;
};

export type MarketOverviewTape = {
  status: MarketOverviewPartitionStatus;
  reason: string | null;
  slots: MarketOverviewTapeSlot[];
};

export type MarketOverviewPulseItem = {
  key: string;
  label: string;
  status: MarketOverviewPartitionStatus;
  reason: string | null;
  previous_value: number | null;
  latest_value: number | null;
  change: number | null;
  change_kind: "absolute" | string;
  unit: string | null;
  change_unit: string | null;
  latest_date: string | null;
  source: string | null;
};

export type MarketOverviewPulse = {
  status: MarketOverviewPartitionStatus;
  reason: string | null;
  items: MarketOverviewPulseItem[];
};

export type MarketOverviewCrisisTrend = {
  requested_window_points: number;
  window_points: number;
  start_date: string | null;
  end_date: string | null;
  start_score: number | null;
  end_score: number | null;
  score_change: number | null;
  start_percentile: number | null;
  end_percentile: number | null;
  percentile_change: number | null;
  direction: "rising" | "falling" | "flat" | "insufficient";
};

export type MarketOverviewCrisisHistoryPoint = {
  date: string;
  crisis_score: number;
  percentile: number | null;
  available_component_count: number | null;
  component_count: number | null;
  available_weight: number | null;
  data_status: string | null;
};

export type MarketOverviewCrisisInputEvidenceItem = {
  field: string;
  label: string;
  aliases: string[];
  warning: string | null;
  required: boolean;
  available: boolean;
  row_count: number;
  latest_date: string | null;
  series_id: string | null;
  source: string | null;
  stale: boolean | null;
  stale_days: number | null;
};

export type MarketOverviewCrisisInputEvidence = {
  inputs: MarketOverviewCrisisInputEvidenceItem[];
  missing_inputs: string[];
  stale_inputs: string[];
  sources: string[];
  latest_dates: string[];
};

export type MarketOverviewCrisisDependencyGate = {
  status: string;
  blocked_by: string[];
  reason_code: string;
};

export type MarketOverviewCrisis = {
  status: MarketOverviewPartitionStatus;
  reason: string | null;
  report_date: string | null;
  requested_report_date: string | null;
  rule_version: string | null;
  score: number | null;
  current_available: boolean;
  history_only: boolean;
  regime: string | null;
  percentile: number | null;
  data_status: "complete" | "degraded" | "unavailable";
  delta: {
    window_points: number;
    score_delta: number | null;
    percentile_delta: number | null;
  };
  score_trend: MarketOverviewCrisisTrend;
  score_trends: MarketOverviewCrisisTrend[];
  score_history: MarketOverviewCrisisHistoryPoint[];
  warnings: string[];
  available_component_count: number | null;
  component_count: number | null;
  input_evidence: MarketOverviewCrisisInputEvidence;
  dependency_gate: MarketOverviewCrisisDependencyGate | null;
  risk_gate: MarketOverviewCrisisRiskGate;
};

export type MarketOverviewCrisisRiskGate = {
  eligible: boolean;
  triggered: boolean;
  threshold: number;
  reason_code: string;
};

export type MarketOverviewSignalCard = {
  key: string;
  title?: string | null;
  stance?: string | null;
  tone?: "positive" | "neutral" | "negative" | "missing" | string;
  score?: number | null;
  evidence?: string[];
  kind: "ops_status" | "market_signal";
};

export type MarketOverviewSignals = {
  status: MarketOverviewPartitionStatus;
  reason: string | null;
  cards: MarketOverviewSignalCard[];
};

export type MarketOverviewNewsLatestItem = {
  event_key: string | null;
  received_at: string;
  topic_code: string | null;
  group_id: string | null;
  summary: string | null;
};

export type MarketOverviewNews = {
  status: MarketOverviewPartitionStatus;
  reason: string | null;
  sample: {
    requested: number;
    returned: number;
    total_rows: number;
    excluded_future_rows: number;
    latest_received_at: string | null;
    stale_days: number | null;
  };
  granularity: { datetime_rows: number; date_only_rows: number };
  density: {
    tz: string;
    bucket_hours: number;
    topics: Array<{ key: string; label: string; cells: number[] }>;
    max_count: number;
  };
  latest: MarketOverviewNewsLatestItem[];
  compare: {
    same_direction: number;
    conflicting: number;
    review_needed: number;
    candidate_scenarios: number;
    review_items: Array<Record<string, unknown>>;
  };
};

export type MarketOverviewAction = {
  priority: "P0" | "P1" | "P2";
  key: string;
  label: string;
  route: string;
  basis: "analytical" | string;
  evidence: Record<string, unknown>;
};

export type MarketOverviewActions = {
  status: MarketOverviewPartitionStatus;
  items: MarketOverviewAction[];
};

export type MarketOverviewCharts = {
  status: MarketOverviewPartitionStatus;
  reason: string | null;
  choice_latest: ChoiceMacroLatestPayload | null;
  market_rates: ChoiceMacroLatestPayload | null;
};

export type MarketOverviewSnapshotPayload = {
  funding_observation?: MarketFundingObservation;
  rates_observation?: MarketRatesObservation;
  components: Partial<
    Record<
      | "choice_latest"
      | "market_rates"
      | "macro_analysis_core"
      | "macro_analysis_full"
      | "macro_pulse"
      | "macro_strategy_summaries"
      | "choice_news",
      MarketOverviewComponent
    >
  >;
  gate?: MarketOverviewGate;
  dates?: MarketOverviewDates;
  tape?: MarketOverviewTape;
  pulse?: MarketOverviewPulse;
  crisis?: MarketOverviewCrisis;
  signals?: MarketOverviewSignals;
  news?: MarketOverviewNews;
  actions?: MarketOverviewActions;
  charts?: MarketOverviewCharts;
};

export type MarketObservationEvidence = {
  key: string;
  label: string;
  series_id: string;
  value: number | null;
  unit: string;
  observation_date: string | null;
  source: string | null;
  quality_flag: string;
  fallback_mode: string;
  is_proxy: boolean;
  previous_value: number | null;
  previous_date: string | null;
  change_bp: number | null;
  status: MarketOverviewPartitionStatus;
  reason: string | null;
  tenor_years?: number;
  recent_points: { trade_date: string; value_numeric: number | null }[];
};
export type MarketObservationBase = {
  status: MarketOverviewPartitionStatus;
  judgment_allowed: boolean;
  observation_date: string | null;
  comparison_date: string | null;
  summary: string;
  interpretation: string;
  limitations: string[];
  reason: string | null;
  rule_version: string;
  evidence: MarketObservationEvidence[];
  rows: MarketObservationEvidence[];
  verification_route: string;
  window_label: string;
};
export type MarketFundingObservation = MarketObservationBase & {
  policy_reference: {
    value: number | null;
    unit: string;
    effective_from: string | null;
    effective_to: string | null;
    validity_status: "verified" | "unverified";
    source: string | null;
    reason: string | null;
  };
  policy_deviation_bp: number | null;
};
export type MarketRatesObservation = MarketObservationBase & {
  curve_family: string;
  full_curve_comparison_allowed: boolean;
  spreads: {
    key: string;
    label: string;
    value_bp: number | null;
    previous_value_bp: number | null;
    change_bp: number | null;
    observation_date: string | null;
    comparison_date: string | null;
    status: MarketOverviewPartitionStatus;
    reason: string | null;
    input_keys: string[];
  }[];
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
  /** 后端 `build_choice_news_compare_payload` 目前不下发 basis / rule_version，只有 mock 带；按实际契约标为可选。 */
  basis?: "analytical";
  rule_version?: string;
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
  value_numeric?: number | null;
  unit?: string | null;
  value_kind?: "index" | "ppt" | string | null;
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

export type LivermoreBreakoutPatternCode = "breakout" | "pullback" | "consolidation";

export type LivermoreStockCandidateItem = {
  rank: number;
  stock_code: string;
  stock_name: string;
  sector_code: string;
  sector_name: string;
  sector_rank: number;
  close: number;
  breakout_level: number;
  /** 后端统一观察位几何距离，单位为百分数；3.0 表示 +3.00%。 */
  distance_to_breakout_pct?: number | null;
  /** 后端统一观察位稳定机器分类；前端归类只匹配该字段。 */
  pattern_code?: LivermoreBreakoutPatternCode | null;
  /** 后端统一观察位展示文案；前端仅透传，不以文案做分类。 */
  pattern?: string | null;
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
  /** 当日成交额（人民币元，已按数据代际归一化）；接口未提供时为 null。 */
  daily_amount?: number | null;
  /** 是否满足 2 亿元日成交门槛；null 表示数据缺失，不构成"未通过"判断。 */
  liquidity_floor_pass?: boolean | null;
};

/**
 * 建议仓位单票条目：equal_weight 为等权主参考（门控敞口/候选数，0-1 小数，
 * 老响应或门控敞口缺失时缺失/为 null）；raw_weight 为 risk_budget 实验参考
 * （截断前单票权重上限，0-1 小数），保留不删。
 */
export type LivermorePositionSizeHintItem = {
  stock_code: string;
  raw_weight: number;
  stop_distance_pct: number;
  stop_basis: "ema10_stop_ref" | "fallback" | string;
  capped: boolean;
  /** 等权主参考仓位（门控敞口/候选数）；老响应缺失，门控敞口缺失时为 null。 */
  equal_weight?: number | null;
};

/** walk-forward 样本外验证披露：status/note/evidence_ref 由后端原文透传，前端必须如实展示、不得弱化。 */
export type LivermorePositionSizeHintOosValidation = {
  status?: string | null;
  note?: string | null;
  evidence_ref?: string | null;
};

/**
 * stock_candidate 建议仓位块：sizing_eqw_v2 起以等权为主参考（primary_basis），
 * risk_budget 输出降为实验参考（risk_budget_status）；串联 gate 敞口语义见
 * gate_exposure_note，等权 shadow 对照说明见 equal_weight_shadow_note。
 */
export type LivermorePositionSizeHint = {
  policy_version: string;
  sizing_mode: string;
  /** 主参考口径声明（"equal_weight"）；老响应缺失时回退 raw_weight 主显。 */
  primary_basis?: string | null;
  /** risk_budget 披露语义（"experimental_reference"）；老响应缺失。 */
  risk_budget_status?: string | null;
  signal_kind: string;
  risk_per_trade: number;
  single_name_cap: number;
  fallback_stop_distance_pct: number;
  stop_basis: string;
  items: LivermorePositionSizeHintItem[];
  stop_ref_fallback_count: number;
  stop_ref_missing_ratio: number;
  coverage_degraded: boolean;
  coverage_warning: string | null;
  /** 等权口径使用的当日门控敞口（[0,1]）；老响应缺失，敞口缺失时为 null。 */
  equal_weight_gate_exposure?: number | null;
  /** 等权口径的候选数分母；老响应缺失。 */
  equal_weight_candidate_count?: number | null;
  /** 等权口径说明原文；老响应缺失。 */
  equal_weight_note?: string | null;
  gate_exposure_note: string;
  equal_weight_shadow_note: string;
  /** 老响应（oos 披露上线前）缺失该块；缺失时不渲染样本外验证注记。 */
  oos_validation?: LivermorePositionSizeHintOosValidation | null;
};

/** walk-forward 样本外判定（报告锚定的静态披露）；老响应缺失时前端必须容错不渲染。 */
export type LivermoreWalkForwardVerdict = {
  contract_version: string;
  signal_kind: string;
  verdict: "supported" | "weakened" | "not_assessable" | string;
  verdict_label: string;
  oos_windows: number | null;
  positive_excess_windows: number | null;
  chained_excess_return: number | null;
  reason: string;
  split: string;
  report: string;
  judged_at: string;
};

export type LivermoreStockCandidatesPayload = {
  walk_forward?: LivermoreWalkForwardVerdict | null;
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
  /** 老响应或字段未上线时缺失/为 null；前端必须容错，缺失时不渲染建议仓位。 */
  position_size_hint?: LivermorePositionSizeHint | null;
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
  walk_forward?: LivermoreWalkForwardVerdict | null;
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
  walk_forward?: LivermoreWalkForwardVerdict | null;
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
  walk_forward?: LivermoreWalkForwardVerdict | null;
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
  walk_forward?: LivermoreWalkForwardVerdict | null;
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
  walk_forward?: LivermoreWalkForwardVerdict | null;
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
  walk_forward?: LivermoreWalkForwardVerdict | null;
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

/** 回测口径披露：解释代理回测样本的入场价与来源代际构成，纯增量、只读展示。 */
export type LivermoreProxyBacktestCaliberDisclosure = {
  entry_price_warning: string | null;
  return_field_stats: Record<string, unknown> | null;
  sample_generation: { tushare_era_rows: number; native_era_rows: number } | null;
  basis_notes: string[];
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
  /** 老响应或字段未上线时缺失/为 null；前端必须容错，缺失时不渲染披露区块。 */
  caliber_disclosure?: LivermoreProxyBacktestCaliberDisclosure | null;
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
  /** 老响应或字段未上线时缺失/为 null；前端必须容错，缺失时不渲染披露区块。 */
  caliber_disclosure?: LivermoreProxyBacktestCaliberDisclosure | null;
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

export type StockAnalysisReplayClosureVersions = {
  candidate_rule_version: string | null;
  stock_candidate_selection_formula_version: string | null;
  candidate_outcome_formula_version: string | null;
  execution_formula_version: string | null;
  matched_baseline_formula_version: string | null;
  market_gate_rule_version: string | null;
  signal_confluence_rule_version: string | null;
  macro_formula_version: string | null;
};

export type StockAnalysisReplayClosureSources = {
  candidate_source_version: string | null;
  execution_source_version: string | null;
  matched_baseline_source_version: string | null;
  macro_source_version: string | null;
  calendar_source_id: string | null;
  calendar_source_version: string | null;
  theme_overlay_fingerprint: string | null;
  choice_catalog_fingerprint: string | null;
};

export type StockAnalysisReplayClosure = {
  cohort_mode: "current_rule_certified" | string;
  selection_status:
    | "schema_unavailable"
    | "no_active_certified"
    | "unique_active_certified"
    | "governance_conflict"
    | "governance_error"
    | "as_of_mismatch"
    | string;
  data_availability: "fresh" | "stale" | "fallback" | "no_data" | "unsupported" | string;
  status: "ready" | "insufficient" | "blocked";
  active_cohort_count: number;
  cohort_id: string | null;
  requested_start_date: string | null;
  requested_end_date: string | null;
  observed_start_date: string | null;
  observed_end_date: string | null;
  certified_start_date: string | null;
  certified_end_date: string | null;
  evaluation_as_of_date: string | null;
  governed_era_start: string | null;
  governed_era_end: string | null;
  stock_candidate_selection_policy: string | null;
  decision_metric_basis: string | null;
  coverage_authority_mode: string | null;
  strict_coverage: boolean | null;
  fallback_covered: boolean | null;
  versions: StockAnalysisReplayClosureVersions;
  sources: StockAnalysisReplayClosureSources;
  counts: {
    completed_dates: number;
    completed_with_signals_dates: number;
    completed_no_signal_dates: number;
    pending_tail_dates: number;
    blocking_pending_dates: number;
    unsupported_dates: number;
    proxy_only_dates: number;
    matched_entry_count: number;
    t5_usable_count: number;
    t20_usable_count: number;
    stale_execution_row_count: number;
    stale_matched_baseline_row_count: number;
  };
  thresholds: {
    completed_dates: number;
    matched_entry_count: number;
  };
  primary_blocker_code: string | null;
  reason_codes: string[];
  run_id: string | null;
  promotion_run_id: string | null;
  receipt: {
    path: string | null;
    sha256: string | null;
    calendar_path: string | null;
    calendar_sha256: string | null;
  };
  tables_used: string[];
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
  /** Unique page authority for current-rule replay closure. Optional only for legacy fixtures/responses. */
  replay_closure?: StockAnalysisReplayClosure | null;
  pretrade_qualification: {
    schema: "pretrade_qualification/v1";
    status: "ready" | "ready_empty" | "unavailable";
    reason: string | null;
    producer_run_id: string | null;
    target_date: string | null;
    stock_candidate_policy: string | null;
    evidence_sha256: string | null;
    input_snapshot_sha256: string | null;
    attested_strategy_payload_sha256: string | null;
    strategy_payload_sha256: string;
    workbench_projection_sha256: string;
  };
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

export type StockPortfolioConstructionSourceGate = {
  status: "ready" | "blocked" | string;
  ready: boolean;
  source: "replay_closure" | string;
  closure_status: string;
  selection_status?: string | null;
  data_availability?: string | null;
  as_of_date?: string | null;
  cohort_id?: string | null;
  primary_blocker_code?: string | null;
  reason_codes: string[];
  versions: Record<string, unknown>;
  sources: Record<string, unknown>;
};

export type StockPortfolioConstructionTargetItem = {
  status: "reference_preview" | string;
  stock_code: string;
  stock_name?: string | null;
  sector_name?: string | null;
  rank?: number | null;
  signal_kind?: string | null;
  selection_close?: number | null;
  score?: number | null;
  equal_weight?: number | null;
  reference_weight?: number | null;
  target_weight?: number | null;
  target_weight_basis?: string | null;
  position_hint?: LivermorePositionSizeHintItem | Record<string, unknown> | null;
  target_block_reason?: string | null;
};

export type StockPortfolioConstructionTarget = {
  status:
    | "reference_preview"
    | "blocked_source_gate"
    | "blocked_main_module"
    | "blocked_no_candidates"
    | string;
  blocked: boolean;
  items: StockPortfolioConstructionTargetItem[];
  candidate_count: number;
  weight_basis: string;
  block_reason?: string | null;
};

export type StockPortfolioConstructionRebalance = {
  status: "blocked_missing_scoped_positions" | string;
  blocked: boolean;
  current_positions: Array<Record<string, unknown>>;
  scoped_positions_available: boolean;
  legacy_position_snapshot_used: boolean;
  legacy_position_snapshot_status: string;
  reason: string;
};

export type StockPortfolioConstructionRiskLimitGate = {
  status: "blocked_missing_approved_policy" | string;
  reason_code?: string | null;
  approved_policy_present: boolean;
};

export type StockPortfolioConstructionRiskSectorExposure = {
  sector_name: string;
  exposure_ratio: number | string | null;
};

export type StockPortfolioConstructionRiskSnapshot = {
  data_status?: "complete" | "partial" | "unavailable" | string;
  status?: "complete" | "partial" | "unavailable" | "error" | string;
  basis?: string | null;
  measurement_basis?: "reference_preview" | string | null;
  portfolio_id?: string | null;
  as_of_date?: string | null;
  source_gate_status?: "ready" | "blocked" | string | null;
  headline?: string | null;
  input_line_count?: number | null;
  position_count?: number | null;
  observation_only?: boolean;
  formal_use_allowed?: boolean;
  target_weight_sum_ratio?: number | string | null;
  gross_exposure_ratio?: number | string | null;
  net_exposure_ratio?: number | string | null;
  cash_ratio?: number | string | null;
  closure_residual_ratio?: number | string | null;
  top1_weight_ratio?: number | string | null;
  top5_weight_ratio?: number | string | null;
  hhi_ratio?: number | string | null;
  hhi_index?: number | string | null;
  sector_exposures?: StockPortfolioConstructionRiskSectorExposure[] | null;
  limit_gate?: StockPortfolioConstructionRiskLimitGate | null;
  reason_codes?: string[];
  warnings?: string[];
};

export type StockPortfolioConstructionIssue = {
  severity: "info" | "warning" | "blocking" | string;
  code: string;
  message: string;
  source?: string | null;
  blocker?: string | null;
};

export type StockPortfolioConstructionPayload = {
  page_id: "GAP-STOCK-ANALYSIS-PORTFOLIO";
  route: "/stock-analysis/portfolio";
  portfolio_id: string;
  requested_as_of_date: string | null;
  as_of_date: string | null;
  resolved_as_of_date: string | null;
  basis: "analytical";
  contract_status: "proposal_only";
  formal_use_allowed: false;
  trading_instruction_allowed: false;
  execution_approval_allowed: false;
  proposal_status:
    | "reference_preview"
    | "blocked_source_gate"
    | "blocked_main_module"
    | "blocked_no_candidates"
    | string;
  context: {
    requested_as_of_date: string | null;
    resolved_as_of_date: string | null;
    portfolio_id: string;
    source_page_id: "GAP-STOCK-ANALYSIS-PAGE";
    source_route: "/stock-analysis";
    source_module: "main" | string;
    main_module_status: string;
  };
  source_gate: StockPortfolioConstructionSourceGate;
  source_gate_status: "ready" | "blocked" | string;
  target: StockPortfolioConstructionTarget;
  rebalance: StockPortfolioConstructionRebalance;
  risk_snapshot: StockPortfolioConstructionRiskSnapshot;
  legacy_position_snapshot: {
    used: boolean;
    status: string;
    reason: string;
  };
  versions: {
    source_version?: string | null;
    workbench_rule_version?: string | null;
    portfolio_construction_rule_version?: string | null;
    portfolio_version?: string | null;
    proposal_version?: string | null;
    calculation_run_id?: string | null;
    review_run_id?: string | null;
  };
  warnings: string[];
  issues: StockPortfolioConstructionIssue[];
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
  total_mv: number | null;
  circ_mv: number | null;
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

export type StockHeavyweightTrendState = "ok" | "partial" | "insufficient" | "missing" | string;

export type StockHeavyweightTrendStock = {
  rank: number | null;
  stock_code: string;
  stock_name: string;
  /** Single-day pctchange from the sector leader snapshot; used to tie out against the workbench card. */
  pctchange: number | null;
  turn: number | null;
  /** Sessions the stock actually traded inside the window, ascending. */
  trade_dates: string[];
  close_values: number[];
  /** (close / first_close - 1) * 100, index-aligned with trade_dates. */
  cum_pct_changes: number[];
  point_count: number;
  missing_point_count: number;
  trend_state: StockHeavyweightTrendState;
  trend_note: string | null;
  window_return_pct: number | null;
};

export type StockHeavyweightTrendSector = {
  sector_code: string;
  sector_name: string;
  sector_rank: number | null;
  stocks: StockHeavyweightTrendStock[];
};

export type StockHeavyweightTrendsPayload = {
  basis: "analytical";
  state: "ok" | "missing";
  contract_status: "observational_only";
  formal_use_allowed: false;
  requested_as_of_date: string | null;
  as_of_date: string | null;
  window_days: number;
  sector_limit: number;
  stocks_per_sector: number;
  series_basis: string;
  window_trade_dates: string[];
  sectors: StockHeavyweightTrendSector[];
  coverage: {
    sector_count: number;
    stock_count: number;
    stock_with_series_count: number;
    stock_missing_series_count: number;
    window_trade_date_count: number;
  };
  metric_notes: string[];
  warnings: string[];
  reason_code?: string;
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
  requested_as_of_date?: string | null;
  as_of_date: string | null;
  fallback_date?: string | null;
  stale?: boolean;
  lag_days?: number | null;
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
  | "missing_candidate_history_receipt"
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
  /** 独立快照日数：available_count 是逐候选行计数，T+5 窗口在相邻交易日高度重叠，
   * 这里披露这些行实际来自几个 snapshot_as_of_date。仅 strategy-score 行返回。 */
  snapshot_day_count?: number | null;
  /** 按快照日聚合的胜率（每日先取当日候选收益均值再判正负）。仅 strategy-score 行返回。 */
  snapshot_day_win_rate?: number | null;
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
    | "missing_candidate_history_receipt"
    | "missing_required_source_table"
    | "forward_returns_pending"
    | "real_theme_inputs_unconfirmed"
    | "proxy_theme_only";
  signal_kinds: string[];
};

export type ConfluenceReplayStatus = {
  window_status: BacktestWindowSummaryStatus;
  snapshot_from?: string | null;
  snapshot_to?: string | null;
  requested_snapshot_from?: string | null;
  requested_snapshot_to?: string | null;
  observed_snapshot_from?: string | null;
  observed_snapshot_to?: string | null;
  metric_basis?: string | null;
  research_metric_basis?: string | null;
  maturity_status?: "ready" | "partial" | "insufficient" | "pending" | "unsupported" | "proxy_only" | "missing" | string;
  has_decision_usable_completed_stats: boolean;
  completed_dates: number;
  pending_dates: number;
  pending_tail_date_count?: number;
  pending_tail_dates?: string[];
  blocking_pending_date_count?: number;
  blocking_pending_dates?: string[];
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
  source_metric?: string | null;
  authority_status?: string | null;
  authority_reasons?: string[] | null;
  cycle_state?: LivermoreMarketGateCycleState | string | null;
  gate_as_of_date?: string | null;
  data_date?: string | null;
  lag_days?: number | null;
  max_component_lag_days?: number | null;
  components?: LivermoreMarketGateMacroComponent[] | null;
  formula_version?: string | null;
  evidence?: string | null;
  required_inputs?: string[] | null;
  missing_inputs?: string[] | null;
  legacy_bond_context?: {
    authority_status?: string | null;
    status?: LivermoreSignalConfluenceMacroStatus | string | null;
    composite_score?: number | null;
  } | null;
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
