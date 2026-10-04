-- Controlled migration-ledger v46 schema for dedicated current-rule certified cohort storage.
-- This slice is intentionally excluded from register_all/startup migration and
-- may only be applied through the explicit v46 controlled entry point after
-- the ordinary schema ledger is proven complete through v45.
-- These tables are additive and keep current-rule replay isolated from the
-- mixed-history as_produced objects. The approved minimum natural keys are
-- enforced here with NOT NULL columns and unique indexes. Exactly-one-active
-- promotion remains a transaction-level invariant owned by the task layer.
-- MOSS:STMT
create table if not exists stock_analysis_current_rule_cohort_manifest (
  cohort_id varchar not null,
  page_id varchar not null,
  cohort_mode varchar not null,
  cohort_status varchar not null,
  is_active boolean,

  requested_start_date varchar,
  requested_end_date varchar,
  observed_start_date varchar,
  observed_end_date varchar,
  certified_start_date varchar,
  certified_end_date varchar,
  evaluation_as_of_date varchar,
  governed_era_start varchar,
  governed_era_end varchar,

  stock_candidate_selection_policy varchar,
  decision_metric_basis varchar,
  coverage_authority_mode varchar,
  strict_coverage boolean,
  fallback_covered boolean,

  candidate_rule_version varchar,
  stock_candidate_selection_formula_version varchar,
  candidate_outcome_formula_version varchar,
  execution_formula_version varchar,
  matched_baseline_formula_version varchar,
  market_gate_rule_version varchar,
  signal_confluence_rule_version varchar,
  macro_formula_version varchar,

  candidate_source_version varchar,
  execution_source_version varchar,
  matched_baseline_source_version varchar,
  macro_source_version varchar,
  calendar_source_id varchar,
  calendar_source_version varchar,
  theme_overlay_fingerprint varchar,
  choice_catalog_fingerprint varchar,
  source_lineage_json varchar,

  plan_digest_sha256 varchar,
  receipt_path varchar,
  receipt_sha256 varchar,
  calendar_receipt_path varchar,
  calendar_receipt_sha256 varchar,
  backup_path varchar,
  backup_sha256 varchar,

  run_id varchar not null,
  idempotency_key varchar not null,
  promoted_from_cohort_id varchar,
  promoted_by_run_id varchar,

  completed_dates integer,
  completed_with_signals_dates integer,
  completed_no_signal_dates integer,
  pending_tail_dates integer,
  blocking_pending_dates integer,
  unsupported_dates integer,
  proxy_only_dates integer,
  matched_entry_count integer,
  t5_usable_count integer,
  t20_usable_count integer,
  stale_execution_row_count integer,
  stale_matched_baseline_row_count integer,
  audit_counts_json varchar,

  failure_reason_code varchar,
  primary_blocker_code varchar,
  blocker_summary_json varchar,
  notes_json varchar,

  created_at varchar,
  certified_at varchar,
  promoted_at varchar,
  superseded_at varchar,
  failed_at varchar
)
-- MOSS:STMT
create index if not exists idx_sa_cr_manifest_page_mode_status
on stock_analysis_current_rule_cohort_manifest(page_id, cohort_mode, cohort_status, is_active)
-- MOSS:STMT
create index if not exists idx_sa_cr_manifest_run
on stock_analysis_current_rule_cohort_manifest(run_id)
-- MOSS:STMT
create index if not exists idx_sa_cr_manifest_plan_digest
on stock_analysis_current_rule_cohort_manifest(plan_digest_sha256)
-- MOSS:STMT
create unique index if not exists uq_sa_cr_manifest_cohort_id
on stock_analysis_current_rule_cohort_manifest(cohort_id)
-- MOSS:STMT
create unique index if not exists uq_sa_cr_manifest_page_mode_idempotency
on stock_analysis_current_rule_cohort_manifest(page_id, cohort_mode, idempotency_key)
-- MOSS:STMT
create table if not exists stock_analysis_current_rule_replay_fact (
  cohort_id varchar not null,
  signal_date varchar not null,
  stock_code varchar not null,
  stock_name varchar,
  signal_kind varchar not null,

  candidate_rank integer,
  market_state varchar,
  signal_close double,
  selection_close double,
  breakout_level double,
  ema10 double,

  entry_date varchar,
  entry_price double,
  entry_price_kind varchar,
  entry_executable boolean,
  entry_block_reason varchar,
  entry_ex_div boolean,

  exit_date_5d varchar,
  exit_price_5d double,
  return_5d_gross_adj double,
  return_5d_net_adj double,
  exit_date_20d varchar,
  exit_price_20d double,
  return_20d_gross_adj double,
  return_20d_net_adj double,

  price_adjustment_mode varchar,
  buy_cost_bps double,
  sell_cost_bps double,
  slippage_bps double,

  candidate_data_status varchar,
  execution_data_status varchar,
  matched_baseline_status varchar,
  matched_baseline_control_count integer,
  matched_alpha_5d double,
  matched_alpha_20d double,
  control_entry_date varchar,
  control_exit_date_5d varchar,
  control_exit_date_20d varchar,
  control_eval_basis varchar,
  control_pit_proof_json varchar,

  candidate_rule_version varchar,
  stock_candidate_selection_formula_version varchar,
  candidate_outcome_formula_version varchar,
  execution_formula_version varchar,
  matched_baseline_formula_version varchar,
  stock_candidate_selection_policy varchar,
  decision_metric_basis varchar,
  coverage_authority_mode varchar,
  strict_coverage boolean,
  fallback_covered boolean,
  candidate_source_version varchar,
  execution_source_version varchar,
  matched_baseline_source_version varchar,
  run_id varchar,

  evidence_json varchar,
  created_at varchar
)
-- MOSS:STMT
create index if not exists idx_sa_cr_fact_cohort_date
on stock_analysis_current_rule_replay_fact(cohort_id, signal_date)
-- MOSS:STMT
create unique index if not exists uq_sa_cr_fact_logical_key
on stock_analysis_current_rule_replay_fact(cohort_id, signal_date, stock_code, signal_kind)
-- MOSS:STMT
create table if not exists stock_analysis_current_rule_date_certificate (
  cohort_id varchar not null,
  trade_date varchar not null,
  certificate_status varchar not null,
  reason_code varchar,

  affects_completed_stats boolean,
  candidate_count integer,
  executable_candidate_count integer,
  t5_usable_count integer,
  t20_usable_count integer,
  matched_entry_count integer,

  stale_execution_row_count integer,
  stale_matched_baseline_row_count integer,
  unsupported_source_count integer,
  proxy_only_evidence_count integer,
  blocking_gap_count integer,

  candidate_rule_version varchar,
  stock_candidate_selection_formula_version varchar,
  candidate_outcome_formula_version varchar,
  execution_formula_version varchar,
  matched_baseline_formula_version varchar,
  stock_candidate_selection_policy varchar,
  decision_metric_basis varchar,
  coverage_authority_mode varchar,
  strict_coverage boolean,
  fallback_covered boolean,
  candidate_source_version varchar,
  execution_source_version varchar,
  matched_baseline_source_version varchar,
  calendar_source_id varchar,
  calendar_source_version varchar,
  control_entry_proven_count integer,
  control_exit_proven_5d_count integer,
  control_exit_proven_20d_count integer,
  control_eval_proof_json varchar,
  zero_signal_certificate_path varchar,
  zero_signal_certificate_sha256 varchar,
  calendar_receipt_path varchar,
  calendar_receipt_sha256 varchar,
  source_coverage_json varchar,
  blocker_detail_json varchar,
  receipt_path varchar,
  receipt_sha256 varchar,
  run_id varchar,
  created_at varchar
)
-- MOSS:STMT
create unique index if not exists uq_sa_cr_cert_logical_key
on stock_analysis_current_rule_date_certificate(cohort_id, trade_date)
-- MOSS:STMT
create index if not exists idx_sa_cr_cert_status
on stock_analysis_current_rule_date_certificate(cohort_id, certificate_status, trade_date)
