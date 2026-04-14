-- MOSS:STMT
create table if not exists phase1_source_preview_summary (
  ingest_batch_id varchar,
  batch_created_at varchar,
  source_family varchar,
  report_date varchar,
  report_start_date varchar,
  report_end_date varchar,
  report_granularity varchar,
  source_file varchar,
  total_rows bigint,
  manual_review_count bigint,
  source_version varchar,
  rule_version varchar,
  preview_mode varchar
)
-- MOSS:STMT
create table if not exists phase1_source_preview_groups (
  ingest_batch_id varchar,
  source_family varchar,
  group_label varchar,
  row_count bigint,
  source_version varchar
)
-- MOSS:STMT
create table if not exists phase1_zqtz_preview_rows (
  ingest_batch_id varchar,
  row_locator bigint,
  report_date varchar,
  business_type_primary varchar,
  business_type_final varchar,
  asset_group varchar,
  instrument_code varchar,
  instrument_name varchar,
  account_category varchar,
  manual_review_needed boolean,
  source_version varchar,
  rule_version varchar
)
-- MOSS:STMT
create table if not exists phase1_tyw_preview_rows (
  ingest_batch_id varchar,
  row_locator bigint,
  report_date varchar,
  business_type_primary varchar,
  product_group varchar,
  institution_category varchar,
  special_nature varchar,
  counterparty_name varchar,
  investment_portfolio varchar,
  manual_review_needed boolean,
  source_version varchar,
  rule_version varchar
)
-- MOSS:STMT
create table if not exists phase1_pnl_preview_rows (
  source_family varchar,
  ingest_batch_id varchar,
  row_locator bigint,
  report_date varchar,
  instrument_code varchar,
  invest_type_raw varchar,
  portfolio_name varchar,
  cost_center varchar,
  currency varchar,
  manual_review_needed boolean,
  source_version varchar,
  rule_version varchar
)
-- MOSS:STMT
create table if not exists phase1_nonstd_pnl_preview_rows (
  source_family varchar,
  ingest_batch_id varchar,
  row_locator bigint,
  report_date varchar,
  journal_type varchar,
  product_type varchar,
  asset_code varchar,
  account_code varchar,
  dc_flag_raw varchar,
  raw_amount varchar,
  manual_review_needed boolean,
  source_version varchar,
  rule_version varchar
)
-- MOSS:STMT
create table if not exists phase1_zqtz_rule_traces (
  ingest_batch_id varchar,
  row_locator bigint,
  trace_step bigint,
  field_name varchar,
  field_value varchar,
  derived_label varchar,
  manual_review_needed boolean
)
-- MOSS:STMT
create table if not exists phase1_tyw_rule_traces (
  ingest_batch_id varchar,
  row_locator bigint,
  trace_step bigint,
  field_name varchar,
  field_value varchar,
  derived_label varchar,
  manual_review_needed boolean
)
-- MOSS:STMT
create table if not exists phase1_pnl_rule_traces (
  source_family varchar,
  ingest_batch_id varchar,
  row_locator bigint,
  trace_step bigint,
  field_name varchar,
  field_value varchar,
  derived_label varchar,
  manual_review_needed boolean
)
-- MOSS:STMT
create table if not exists phase1_nonstd_pnl_rule_traces (
  source_family varchar,
  ingest_batch_id varchar,
  row_locator bigint,
  trace_step bigint,
  field_name varchar,
  field_value varchar,
  derived_label varchar,
  manual_review_needed boolean
)
