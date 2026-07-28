import { readHttpJsonDetail } from "./httpResponseError";
import type { ApiEnvelope } from "./contracts";

type FetchLike = typeof fetch;

type MacroToolkitClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

const MACRO_TOOLKIT_READ_TIMEOUT_MS = 90_000;

export type MacroToolkitScriptRecord = {
  name: string;
  filename: string;
  group: string;
  default_data_sources: string[];
  optional_dependencies: string[];
  notes: string;
  path: string;
  available: boolean;
};

export type MacroToolkitOutputFile = {
  name: string;
  path: string;
  size_bytes: number;
  modified_at: string;
};

export type MacroToolkitSourceCheck = {
  alias: string;
  row_count: number;
  latest: null | {
    date: string;
    series_id: string;
    vendor_name: string;
    value: number;
  };
};

export type MacroToolkitCapability = {
  key: string;
  legacy_module: string;
  label: string;
  group: string;
  implementation_status: string;
  route_status: string;
  frontend_status: string;
  data_status: string;
  data_hit_count: number;
  data_required_count: number;
  evidence: Array<{
    alias: string;
    row_count: number;
    latest_date: string | null;
    series_id: string | null;
  }>;
  next_step: string;
};

export type MacroToolkitCffexMemberRankStatus = {
  materialized: boolean;
  status: string;
  row_count: number;
  latest_trade_date: string | null;
  contracts: string[];
  source_vendors: string[];
  freshness_status?: string;
  reference_date?: string | null;
  stale_days?: number | null;
};

export type MacroToolkitChoiceStockRefreshPermission = {
  mode: "identity_only" | string;
  allowed?: boolean;
  user_id?: string | null;
  role?: string | null;
  identity_source?: string | null;
  resource?: string;
  actions?: string[];
};

export type MacroToolkitChoiceStockRefreshRun = {
  status: string;
  run_id?: string;
  job_name?: string;
  cache_key?: string;
  trigger_mode?: "idle" | "async" | "terminal" | string;
  report_date?: string;
  error_message?: string | null;
  failure_category?: string | null;
  failure_reason?: string | null;
  history_row_count?: number | null;
  factor_row_count?: number | null;
  source_version?: string;
  vendor_version?: string | null;
  rule_version?: string | null;
  cache_version?: string | null;
  refresh_history?: boolean;
  refresh_factors?: boolean;
  factor_max_stock_count?: number | null;
  permission?: MacroToolkitChoiceStockRefreshPermission;
};

export type MacroToolkitChoiceStockTableStatus = {
  materialized: boolean;
  status: string;
  row_count: number;
  stock_count: number;
  trade_date_count?: number;
  latest_trade_date?: string | null;
  as_of_date?: string | null;
  freshness_status?: string;
  reference_date?: string | null;
  stale_days?: number | null;
  fallback_mode?: string | null;
  fallback_date?: string | null;
};

export type MacroToolkitChoiceStockRefreshStatus = {
  permission: MacroToolkitChoiceStockRefreshPermission;
  refresh?: MacroToolkitChoiceStockRefreshRun;
  daily_observation?: MacroToolkitChoiceStockTableStatus;
  factor_snapshot?: MacroToolkitChoiceStockTableStatus;
  default_factor_max_stock_count?: number | null;
};

export type MacroToolkitChoiceStockRefreshResponse = ApiEnvelope<{
  refresh: MacroToolkitChoiceStockRefreshRun;
  choice_stock_refresh: MacroToolkitChoiceStockRefreshStatus;
}>;

export type MacroToolkitCommodityFuturesRefreshPermission = MacroToolkitChoiceStockRefreshPermission;

export type MacroToolkitCommodityFuturesHealthStatus = {
  materialized: boolean;
  status: string;
  table: string;
  row_count: number | null;
  latest_trade_date: string | null;
  source_vendors: string[];
  target_products?: string[];
  coverage: {
    target_product_count: number;
    available_product_count: number;
    available_products: string[];
    missing_products: string[];
    products?: Array<Record<string, unknown>>;
  };
  nanhua_input: {
    status: string;
    product_code: string;
    series_id: string;
    system_series_id?: string | null;
    latest_trade_date: string | null;
    latest_value: number | null;
    row_count: number;
    source_version?: string | null;
    vendor_version?: string | null;
    rule_version?: string | null;
  };
};

export type MacroToolkitCommodityFuturesRefreshStatus = {
  permission: MacroToolkitCommodityFuturesRefreshPermission;
  refresh?: MacroToolkitCommodityFuturesRefreshRun;
  status?: MacroToolkitCommodityFuturesHealthStatus;
};

export type MacroToolkitCommodityFuturesRefreshSummary = {
  table: string;
  row_count_before: number | null;
  row_count_after: number | null;
  row_count_delta: number | null;
  latest_trade_date_before: string | null;
  latest_trade_date_after: string | null;
  available_product_count_before: number | null;
  available_product_count_after: number | null;
  target_product_count: number | null;
  newly_available_products: string[];
  missing_products_after: string[];
  nanhua_status_before: string | null;
  nanhua_status_after: string | null;
  nanhua_latest_date_before: string | null;
  nanhua_latest_date_after: string | null;
  nanhua_latest_value_after: number | null;
  source_vendors_after: string[];
  dry_run: boolean;
};

export type MacroToolkitPayload = {
  default_data_sources: string[];
  toolkit_root: string;
  output_dir: string;
  scripts: MacroToolkitScriptRecord[];
  groups: string[];
  omitted_scripts: Record<string, string>;
  output_files: MacroToolkitOutputFile[];
  source_checks: MacroToolkitSourceCheck[];
  capabilities: MacroToolkitCapability[];
  cffex_member_rank?: MacroToolkitCffexMemberRankStatus;
  choice_stock_refresh?: MacroToolkitChoiceStockRefreshStatus;
  commodity_futures_refresh?: MacroToolkitCommodityFuturesRefreshStatus;
  model_readiness?: MacroToolkitModelReadiness[];
  readiness_summary?: MacroToolkitReadinessSummary;
  warnings: string[];
};

export type MacroToolkitIndicator = {
  key: string;
  alias: string;
  label: string;
  group: string;
  unit: string;
  row_count: number;
  latest_date: string | null;
  latest_value: number | null;
  previous_value: number | null;
  change: number | null;
  change_pct: number | null;
  source: string | null;
  series_id: string | null;
  quality: "ok" | "missing";
};

export type MacroToolkitSignalCard = {
  key: string;
  title: string;
  stance: string;
  tone: "positive" | "neutral" | "negative" | "missing";
  score: number | null;
  evidence: string[];
};

export type MacroToolkitInputEvidence = {
  inputs?: Array<{
    field: string;
    label: string;
    aliases?: string[];
    warning?: string;
    required?: boolean;
    available?: boolean;
    stale?: boolean;
    stale_days?: number | null;
    freshness_tier?: string;
    cadence?: string;
    row_count?: number;
    latest_date?: string | null;
    series_id?: string | null;
    source?: string | null;
    value?: number | null;
  }>;
  missing_inputs?: string[];
  stale_inputs?: string[];
  sources?: string[];
  latest_dates?: string[];
};

export type MacroToolkitCapabilityResult = {
  key: string;
  legacy_module: string;
  label: string;
  group: string;
  status: "complete" | "degraded" | "unavailable";
  tone: MacroToolkitSignalCard["tone"];
  score: number | null;
  headline: string;
  primary_metric: {
    label: string;
    value: string | number;
    unit: string;
  } | null;
  input_evidence?: MacroToolkitInputEvidence | null;
  evidence: string[];
  warnings: string[];
  result: Record<string, unknown> & {
    input_evidence?: MacroToolkitInputEvidence | null;
  };
};

export type MacroToolkitStrategySummary = {
  key: string;
  label: string;
  group: string;
  status: "sample_only" | "complete" | "degraded" | "unavailable";
  tone: MacroToolkitSignalCard["tone"];
  primary_metric: {
    label: string;
    value: string | number;
    unit: string;
  } | null;
  evidence: string[];
  warnings: string[];
  result: Record<string, unknown>;
};

export type MacroToolkitShadowPortfolioHolding = {
  rank: number;
  stock_code: string;
  industry: string;
  score: number;
  pe: number;
  pb: number;
  three_month_return: number;
};

export type MacroToolkitShadowPortfolioCostResult = {
  cost_bps: number;
  total_return: number;
  excess_return: number;
  max_drawdown: number;
  win_rate?: number;
};

export type MacroToolkitShadowPortfolioAdmissionCriterion = {
  key: string;
  label: string;
  passed: boolean;
  actual: unknown;
  threshold: unknown;
};

export type MacroToolkitShadowPortfolioAdmission = {
  status: "passed" | "needs_review" | "failed" | string;
  label: string;
  summary: string;
  criteria: MacroToolkitShadowPortfolioAdmissionCriterion[];
};

export type MacroToolkitShadowPortfolioPeriodCostResult = {
  cost_bps: number;
  net_return: number;
  cost: number;
};

export type MacroToolkitShadowPortfolioPeriodReturn = {
  portfolio_key: string;
  start_date: string;
  end_date: string;
  gross_return: number;
  benchmark_return: number;
  excess_return: number;
  selected_count: number;
  name_turnover: number | null;
  traded_notional: number | null;
  cost_results: MacroToolkitShadowPortfolioPeriodCostResult[];
};

export type MacroToolkitShadowPortfolio = {
  key: string;
  label: string;
  role: "production_reference" | "shadow_candidate" | string;
  total_return: number;
  excess_return: number;
  max_drawdown: number;
  win_rate: number;
  average_turnover: number | null;
  average_traded_notional?: number | null;
  average_count: number;
  average_pe: number | null;
  average_pb: number | null;
  weights: Record<string, number>;
  constraints: {
    pe_max?: number | null;
    pb_max?: number | null;
    turnover_cap?: number | null;
    top_pct?: number;
    max_candidates?: number;
    max_per_industry?: number;
  };
  cost_results: MacroToolkitShadowPortfolioCostResult[];
  latest_holdings: MacroToolkitShadowPortfolioHolding[];
  admission?: MacroToolkitShadowPortfolioAdmission;
};

export type MacroToolkitShadowPortfolioReport = {
  status: "complete" | "insufficient_history" | "unavailable" | string;
  basis: "read_only_shadow" | string;
  label: string;
  as_of_date: string | null;
  completed_periods: number;
  factor_dates: string[];
  rule_version: string;
  tables_used: string[];
  warnings: string[];
  cost_model: {
    cost_bps: number[];
    initial_build_included: boolean;
    final_liquidation_included: boolean;
    method?: string;
  };
  benchmark: {
    key: string;
    label: string;
    total_return: number;
    max_drawdown: number;
  } | null;
  portfolios: MacroToolkitShadowPortfolio[];
  period_returns: MacroToolkitShadowPortfolioPeriodReturn[];
};

export type MacroToolkitAShareRiskPayload = {
  trade_date: string | null;
  status: "complete" | "degraded" | "unavailable";
  risk_score: number | null;
  risk_level: "green" | "yellow" | "orange" | "red" | "unknown";
  risk_name: string;
  summary: string;
  position_rule: string;
  metrics: Record<string, number | null>;
  triggered_rules: string[];
  watch_next: string[];
  warnings: string[];
  tables_used: string[];
};

export type MacroToolkitRuntimeStatusPayload = {
  analysis_scope: "core" | "full" | string;
  deferred_sections: Array<{
    key: string;
    label: string;
    status: "deferred" | "loading" | "complete" | "failed" | string;
  }>;
};

export type MacroToolkitDataHealth = {
  analysis_scope?: string | null;
  indicator_coverage: {
    hit_count: number;
    total_count: number;
    hit_rate: number | null;
    missing_count: number;
    missing: Array<{
      key?: string | null;
      alias?: string | null;
      label?: string | null;
    }>;
  };
  source_coverage: {
    hit_count: number;
    total_count: number;
    hit_rate: number | null;
    latest_date: string | null;
    deferred: boolean;
    missing_aliases: string[];
  };
  capability_results: {
    complete: number;
    degraded: number;
    unavailable: number;
    total_count: number;
    deferred: boolean;
  };
  capability_plan: {
    ready_count: number;
    wired_count: number;
    total_count: number;
    deferred: boolean;
  };
  deferred_sections: string[];
  warnings: string[];
  repair_items?: Array<{
    type?: string | null;
    scope?: string | null;
    priority?: string | null;
    key?: string | null;
    alias?: string | null;
    label?: string | null;
    source_table?: string | null;
    latest_date?: string | null;
    reference_date?: string | null;
    stale_days?: number | null;
    suggested_action?: string | null;
    action?: {
      kind?: string | null;
      label?: string | null;
      enabled?: boolean | null;
      reason?: string | null;
      analysis_detail?: string | null;
    } | null;
    tags?: string[];
  }>;
};

export type MacroToolkitHasonStrategyModule = {
  key: string;
  label: string;
  status: string;
  scripts: string[];
  available_scripts: string[];
  missing_scripts: string[];
  evidence: string[];
};

export type MacroToolkitArtifactReceipt = {
  status: string;
  model_id: string;
  script_name: string;
  artifact_paths: string[];
  missing_artifacts: string[];
  degraded_reason: string | null;
  data_asof: string | null;
  generated_at: string;
  runtime_endpoint: string;
  page_surface: string;
  formal_use_allowed: boolean;
  observation_only: boolean;
};

export type MacroToolkitModelReadiness = {
  id: string;
  label: string;
  script_name: string;
  script_available?: boolean;
  expected_outputs: string[];
  outputs?: Array<{
    name: string;
    freshness_status: string;
    freshness_basis: string;
    modified_at: string | null;
    modified_date: string | null;
    content_date: string | null;
    content_date_min: string | null;
    content_date_max: string | null;
    content_date_invalid_count: number;
    reference_date: string | null;
  }>;
  readiness: "artifact_backed" | "missing_output" | "stale" | "registered_only" | "degraded" | "unknown";
  degraded_reason?: string | null;
  evidence_level?: string;
  date_basis?: string;
  artifact_receipt?: MacroToolkitArtifactReceipt;
  observation_only: boolean;
  formal_use_allowed: boolean;
  latest_modified_at?: string | null;
  latest_content_date?: string | null;
  missing_outputs: string[];
  stale_outputs: string[];
  degraded_outputs?: string[];
  notes: string[];
};

export type MacroToolkitReadinessSummary = {
  total_count: number;
  artifact_backed_count: number;
  degraded_count: number;
  status_counts: Record<string, number>;
  observation_only: boolean;
  formal_use_allowed: boolean;
};

export type MacroToolkitHasonStrategy = {
  key: "hason_macro_strategy" | string;
  framework_name: string;
  basis: "analytical" | string;
  observation_only: boolean;
  formal_use_allowed: boolean;
  formal_metric_id: string | null;
  status: string;
  display_status: string;
  readiness: {
    ready_modules: number;
    partial_modules: number;
    missing_modules: number;
    missing_script_count: number;
    total_modules: number;
    ratio: number;
  };
  modules: MacroToolkitHasonStrategyModule[];
  runtime_output_status: string;
  runtime_outputs: Array<{
    name: string;
    freshness_status: string;
    freshness_basis: string;
    modified_at: string | null;
    modified_date: string | null;
    content_date: string | null;
    content_date_min: string | null;
    content_date_max: string | null;
    content_date_invalid_count: number;
    reference_date: string | null;
  }>;
  required_runtime_outputs: string[];
  runtime_output_gaps: string[];
  missing_runtime_outputs: string[];
  stale_runtime_outputs: string[];
  boundary: string;
  source_trace: Array<{
    script: string;
    filename: string | null;
    group: string | null;
    available: boolean;
    modules?: string[];
  }>;
};

export type MacroToolkitReportBundleArtifact = {
  id: string;
  filename: string;
  label: string;
  kind: string;
  media_type: "application/pdf" | "image/png" | "text/markdown";
  size_bytes: number;
  sha256: string;
};

export type MacroToolkitReportBundle = {
  status: "ready" | "missing" | "invalid";
  reason: string | null;
  schema_version?: string;
  bundle_id?: string;
  title?: string;
  basis: "analytical";
  as_of_date?: string;
  curve_date?: string;
  account_report_date?: string;
  observation_only: true;
  formal_use_allowed: false;
  validation?: {
    passed: number;
    failed: number;
    scope: string;
  };
  warnings: string[];
  artifacts: MacroToolkitReportBundleArtifact[];
};

export type MacroToolkitAnalysisPayload = {
  default_data_sources: string[];
  as_of_date: string | null;
  conclusion: {
    stance: string;
    tone: "positive" | "neutral" | "negative" | "missing";
    summary: string;
    recommended_action: string;
  };
  coverage: {
    indicator_count: number;
    hit_count: number;
    hit_rate: number;
    script_count: number;
    output_file_count: number;
  };
  indicators: MacroToolkitIndicator[];
  signal_cards: MacroToolkitSignalCard[];
  model_readiness?: MacroToolkitModelReadiness[];
  readiness_summary?: MacroToolkitReadinessSummary;
  hason_strategy?: MacroToolkitHasonStrategy;
  a_share_risk?: MacroToolkitAShareRiskPayload;
  capability_results: MacroToolkitCapabilityResult[];
  strategy_summaries: MacroToolkitStrategySummary[];
  shadow_portfolio_report?: MacroToolkitShadowPortfolioReport;
  output_files: MacroToolkitOutputFile[];
  report_bundle?: MacroToolkitReportBundle;
  source_checks: MacroToolkitSourceCheck[];
  capabilities: MacroToolkitCapability[];
  cffex_member_rank?: MacroToolkitPayload["cffex_member_rank"];
  choice_stock_refresh?: MacroToolkitChoiceStockRefreshStatus;
  runtime_status?: MacroToolkitRuntimeStatusPayload;
  data_health?: MacroToolkitDataHealth;
  warnings: string[];
};

export type MacroToolkitDualFrequencyHistorySource = {
  status?: string;
  quality?: string;
  table?: string;
  series_id?: string;
  field?: string;
  unit?: string;
  aggregation?: string;
  source_versions?: string[];
  vendor_versions?: string[];
  rule_versions?: string[];
  quality_flags?: string[];
  run_ids?: string[];
  date_count?: number;
  canonical_row_count?: number;
  amount_value_row_count?: number;
  null_amount_row_count?: number;
  valid_amount_observation_count?: number;
  null_amount_observation_count?: number;
  missing_trade_date_count?: number;
};

export type MacroToolkitDualFrequencyHistoryEvidence = {
  status?: string;
  quality?: string;
  series_id?: string;
  date_basis?: string;
  requested_as_of_date?: string | null;
  effective_as_of_date?: string | null;
  earliest_trade_date?: string | null;
  latest_trade_date?: string | null;
  lookback_rows?: number;
  row_count?: number;
  tables_used?: string[];
  sources?: Record<string, MacroToolkitDualFrequencyHistorySource>;
  warnings?: string[];
};

export type MacroToolkitDualFrequencyCandidate = {
  status?: string;
  strategy_name?: string;
  boundary?: string;
  execution_enabled?: boolean;
  formula_version?: string;
  rule_version?: string;
  as_of_date?: string | null;
  slow?: {
    status?: string;
    source?: string;
    reason?: string | null;
    cap?: number | null;
  } | null;
  fast?: {
    status?: string;
    state?: string | null;
    multiplier?: number | null;
    signal_date?: string | null;
    minimum_required_rows?: number | null;
    available_rows?: number | null;
    last_transition?: {
      layer?: string;
      date?: string;
      event?: string;
      state?: string;
      reason?: string;
      close?: number;
      amount_ratio_20?: number;
      return_5?: number;
    } | null;
    latest_metrics?: {
      close?: number | null;
      high_20?: number | null;
      amount_ratio_20?: number | null;
      return_5?: number | null;
      atr_proxy_20?: number | null;
      ma_60?: number | null;
      highest_close_since_attack?: number | null;
      consecutive_closes_below_ma60?: number | null;
    } | null;
  } | null;
  survival?: {
    status?: string;
    source?: string;
    state?: string | null;
    multiplier?: number | null;
    signal_date?: string | null;
    current_drawdown?: number | null;
    five_day_drawdown?: number | null;
    halved?: boolean | null;
    killed?: boolean | null;
    cooldown_remaining?: number | null;
    ramp_remaining?: number | null;
    reason?: string | null;
  } | null;
  pre_survival_target_total_weight?: number | null;
  final_target_total_weight?: number | null;
  events?: Array<Record<string, unknown>>;
  data_status?: {
    status?: string;
    market_history_status?: string;
    slow_cap_status?: string;
    fast_status?: string;
    survival_status?: string;
    input_row_count?: number | null;
    usable_row_count?: number | null;
    invalid_row_count?: number | null;
    duplicate_date_count?: number | null;
    latest_trade_date?: string | null;
    as_of_alignment?: string;
    history?: MacroToolkitDualFrequencyHistoryEvidence;
  };
  methodology?: {
    slow_layer?: string;
    fast_entry?: string;
    fast_exit?: string;
    atr_proxy?: string;
    amount_ratio?: string;
    survival_layer?: string;
    execution_timing?: string;
  };
  provenance?: {
    calculation_module?: string;
    source_strategy?: string;
    integration_mode?: string;
    slow_cap_source?: string;
    fast_input_fields?: string[];
    survival_input_source?: string;
    nav_history_authoritative_complete?: boolean;
    signal_date?: string | null;
    latest_trade_date?: string | null;
    history?: MacroToolkitDualFrequencyHistoryEvidence;
    amount_methodology?: {
      source_table?: string;
      field?: string;
      aggregation?: string;
      scope?: string;
      is_csi300_constituent_turnover?: boolean;
      unit?: string;
    };
  };
  warnings?: string[];
};

export type MacroToolkitMacroEtfStrategySnapshot = {
  strategy_name?: string;
  boundary?: string;
  execution_enabled?: boolean;
  as_of_date?: string | null;
  dual_frequency?: MacroToolkitDualFrequencyCandidate | null;
  data_status?: {
    status?: string;
    dual_frequency_status?: string;
  };
  provenance?: {
    source_script?: string;
    integration_mode?: string;
    tables_used?: string[];
    deferred_controls?: string[];
  };
  warnings?: string[];
};

export type MacroToolkitStrategySummariesPayload = {
  strategy_summaries: MacroToolkitStrategySummary[];
  shadow_portfolio_report?: MacroToolkitShadowPortfolioReport;
  choice_stock_refresh?: MacroToolkitChoiceStockRefreshStatus;
  macro_etf_strategy?: MacroToolkitMacroEtfStrategySnapshot;
};

export type MacroToolkitRunResponse = {
  status: "completed" | "failed" | "timeout";
  script: MacroToolkitScriptRecord;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  output_files: MacroToolkitOutputFile[];
  message?: string;
};

export type MacroToolkitScriptChainRun = {
  chain_id?: string;
  status: "completed" | "failed" | "timeout" | "dry_run" | string;
  dry_run: boolean;
  started_at: string;
  finished_at: string;
  timeout_seconds: number;
  manifest: Array<{
    order: number;
    script_name: string;
    label: string;
    expected_outputs: string[];
    available: boolean;
  }>;
  receipts: Array<{
    order: number;
    chain_id?: string;
    script_name: string;
    status: string;
    exit_code: number | null;
    expected_outputs: string[];
    produced_outputs: string[];
    missing_outputs_after: string[];
    degraded_reason?: string | null;
    data_asof?: string | null;
    generated_at?: string;
    runtime_endpoint?: string;
    page_surface?: string;
    formal_use_allowed?: boolean;
    observation_only?: boolean;
    started_at?: string | null;
    finished_at?: string | null;
    stdout: string;
    stderr: string;
  }>;
  readiness_before: MacroToolkitReadinessSummary;
  readiness_after: MacroToolkitReadinessSummary;
  model_readiness: MacroToolkitModelReadiness[];
  observation_only: boolean;
  formal_use_allowed: boolean;
};

export type MacroToolkitScriptChainRunResponse = ApiEnvelope<{
  run: MacroToolkitScriptChainRun;
  model_readiness: MacroToolkitModelReadiness[];
}>;

export type MacroToolkitCffexRefreshResponse = ApiEnvelope<{
  refresh: Record<string, unknown>;
  cffex_member_rank: MacroToolkitCffexMemberRankStatus;
}>;

export type MacroToolkitSourceBackfillRefreshResponse = ApiEnvelope<{
  refresh: {
    status: string;
    alias: string;
    series_ids: string[];
    series_names?: string[];
    start_date?: string | null;
    end_date?: string | null;
    total_added: number;
    processed_count?: number;
    results?: Record<string, number>;
    errors?: Record<string, string>;
  };
}>;

export type MacroToolkitCommodityFuturesRefreshRun = {
  status: string;
  dry_run?: boolean;
  start_date?: string | null;
  end_date?: string | null;
  product_count?: number;
  row_count?: number;
  estimated_total_rows?: number;
  estimated_trading_days?: number;
  products?: Array<Record<string, unknown> | string>;
  table?: string;
  rule_version?: string;
  permission?: MacroToolkitCommodityFuturesRefreshPermission;
  before_status?: MacroToolkitCommodityFuturesHealthStatus;
  after_status?: MacroToolkitCommodityFuturesHealthStatus;
  summary?: MacroToolkitCommodityFuturesRefreshSummary;
};

export type MacroToolkitCommodityFuturesRefreshResponse = ApiEnvelope<{
  refresh: MacroToolkitCommodityFuturesRefreshRun;
  commodity_futures_refresh?: MacroToolkitCommodityFuturesRefreshStatus;
}>;

export type MacroToolkitAnalysisRequest = {
  detail?: "core" | "full";
  historyLimit?: number;
};

export type MacroToolkitRequestOptions = {
  signal?: AbortSignal;
};

export type MacroToolkitClientMethods = {
  getMacroToolkitAnalysis: (
    options?: MacroToolkitAnalysisRequest,
  ) => Promise<ApiEnvelope<MacroToolkitAnalysisPayload>>;
  getMacroToolkitStrategySummaries: (
    options?: MacroToolkitRequestOptions,
  ) => Promise<ApiEnvelope<MacroToolkitStrategySummariesPayload>>;
  getMacroToolkitScripts: () => Promise<ApiEnvelope<MacroToolkitPayload>>;
  runMacroToolkitScript: (
    name: string,
    options?: { timeoutSeconds?: number; argv?: string[] },
  ) => Promise<MacroToolkitRunResponse>;
  runMacroToolkitScriptChain: (options?: {
    dryRun?: boolean;
    timeoutSeconds?: number;
  }) => Promise<MacroToolkitScriptChainRunResponse>;
  refreshCffexMemberRank: (options?: {
    tradeDate?: string;
    contracts?: string[];
    sources?: string[];
  }) => Promise<MacroToolkitCffexRefreshResponse>;
  refreshMacroSourceBackfill: (options: {
    alias: string;
    startDate?: string | null;
    endDate?: string | null;
    sources?: string[];
  }) => Promise<MacroToolkitSourceBackfillRefreshResponse>;
  refreshCommodityFutures: (options?: {
    startDate?: string | null;
    endDate?: string | null;
    products?: string[];
    dryRun?: boolean;
  }) => Promise<MacroToolkitCommodityFuturesRefreshResponse>;
  refreshChoiceStock: (options?: {
    asOfDate?: string;
    refreshHistory?: boolean;
    refreshFactors?: boolean;
    factorMaxStockCount?: number | null;
  }) => Promise<MacroToolkitChoiceStockRefreshResponse>;
  getChoiceStockRefreshStatus: (runId: string) => Promise<MacroToolkitChoiceStockRefreshResponse>;
};

export function createRealMacroToolkitClient({
  fetchImpl,
  baseUrl,
}: MacroToolkitClientFactoryOptions): MacroToolkitClientMethods {
  return {
    getMacroToolkitAnalysis: (options?: MacroToolkitAnalysisRequest) => {
      const detail = options?.detail ?? "core";
      const params = new URLSearchParams({ detail });
      if (options?.historyLimit != null) {
        params.set("history_limit", String(options.historyLimit));
      }
      return requestJson<MacroToolkitAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/ui/macro/toolkit/analysis?${params.toString()}`,
      );
    },
    getMacroToolkitStrategySummaries: (options) =>
      requestJson<MacroToolkitStrategySummariesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/macro/toolkit/analysis/strategy-summaries",
        { signal: options?.signal },
      ),
    getMacroToolkitScripts: () =>
      requestJson<MacroToolkitPayload>(fetchImpl, baseUrl, "/ui/macro/toolkit/scripts"),
    runMacroToolkitScript: (name, options) =>
      requestActionJson<MacroToolkitRunResponse>(
        fetchImpl,
        baseUrl,
        `/ui/macro/toolkit/scripts/${encodeURIComponent(name)}/run`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            argv: options?.argv ?? [],
            timeout_seconds: options?.timeoutSeconds ?? 120,
          }),
        },
      ),
    runMacroToolkitScriptChain: (options) =>
      requestActionJson<MacroToolkitScriptChainRunResponse>(
        fetchImpl,
        baseUrl,
        "/ui/macro/toolkit/scripts/run-chain",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            dry_run: options?.dryRun ?? true,
            timeout_seconds: options?.timeoutSeconds ?? 120,
          }),
        },
      ),
    refreshCffexMemberRank: (options) =>
      requestActionJson<MacroToolkitCffexRefreshResponse>(
        fetchImpl,
        baseUrl,
        "/ui/macro/toolkit/cffex-member-rank/refresh",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            trade_date: options?.tradeDate ?? null,
            contracts: options?.contracts ?? ["TS.CFE", "TF.CFE", "T.CFE", "TL.CFE"],
            sources: options?.sources ?? ["choice", "tushare"],
          }),
        },
      ),
    refreshMacroSourceBackfill: (options) =>
      requestActionJson<MacroToolkitSourceBackfillRefreshResponse>(
        fetchImpl,
        baseUrl,
        "/ui/macro/toolkit/source-backfill/refresh",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            alias: options.alias,
            start_date: options.startDate ?? null,
            end_date: options.endDate ?? null,
            sources: options.sources ?? null,
          }),
        },
      ),
    refreshCommodityFutures: (options) =>
      requestActionJson<MacroToolkitCommodityFuturesRefreshResponse>(
        fetchImpl,
        baseUrl,
        "/ui/macro/toolkit/commodity-futures/refresh",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            start_date: options?.startDate ?? null,
            end_date: options?.endDate ?? null,
            products: options?.products ?? null,
            dry_run: options?.dryRun ?? false,
          }),
        },
      ),
    refreshChoiceStock: (options) =>
      requestActionJson<MacroToolkitChoiceStockRefreshResponse>(
        fetchImpl,
        baseUrl,
        "/ui/macro/toolkit/choice-stock/refresh",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            as_of_date: options?.asOfDate ?? null,
            refresh_history: options?.refreshHistory ?? true,
            refresh_factors: options?.refreshFactors ?? true,
            factor_max_stock_count: options?.factorMaxStockCount ?? null,
          }),
        },
      ),
    getChoiceStockRefreshStatus: (runId) =>
      requestJson<MacroToolkitChoiceStockRefreshResponse["result"]>(
        fetchImpl,
        baseUrl,
        `/ui/macro/toolkit/choice-stock/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
  };
}

async function requestJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  options: MacroToolkitRequestOptions = {},
): Promise<ApiEnvelope<TData>> {
  const controller = new AbortController();
  const abortFromSignal = () => controller.abort();
  if (options.signal?.aborted) {
    controller.abort();
  } else {
    options.signal?.addEventListener("abort", abortFromSignal, { once: true });
  }
  const timeoutId = setTimeout(() => controller.abort(), MACRO_TOOLKIT_READ_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetchImpl(`${baseUrl}${path}`, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
  } catch (error) {
    const errorName =
      typeof error === "object" && error !== null && "name" in error
        ? (error as { name?: unknown }).name
        : undefined;
    if (errorName === "AbortError") {
      if (options.signal?.aborted) {
        throw error;
      }
      throw new Error(`Macro toolkit request timed out: ${path}`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", abortFromSignal);
  }

  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<TData>;
}

async function requestActionJson<TResponse>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<TResponse> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as TResponse;
}
