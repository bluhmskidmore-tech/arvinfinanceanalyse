-- MOSS:STMT
create table if not exists choice_market_snapshot (
  series_id varchar,
  series_name varchar,
  vendor_series_code varchar,
  vendor_name varchar,
  trade_date varchar,
  value_numeric double,
  frequency varchar,
  unit varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
-- MOSS:STMT
create table if not exists fact_choice_macro_daily (
  series_id varchar,
  series_name varchar,
  trade_date varchar,
  value_numeric double,
  frequency varchar,
  unit varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  quality_flag varchar,
  run_id varchar
)
-- MOSS:STMT
create table if not exists phase1_macro_vendor_catalog (
  series_id varchar,
  series_name varchar,
  vendor_name varchar,
  vendor_version varchar,
  frequency varchar,
  unit varchar,
  vendor_series_code varchar,
  batch_id varchar,
  catalog_version varchar,
  theme varchar,
  is_core boolean,
  tags_json varchar,
  request_options varchar,
  fetch_mode varchar,
  fetch_granularity varchar,
  refresh_tier varchar,
  policy_note varchar
)
-- MOSS:STMT
create table if not exists market_data_series_category (
  series_id varchar,
  category_key varchar,
  category_label varchar,
  source_surface varchar,
  fetch_mode varchar,
  fetch_granularity varchar,
  policy_note varchar,
  catalog_version varchar,
  batch_id varchar,
  updated_at varchar,
  run_id varchar
)
-- MOSS:STMT
alter table phase1_macro_vendor_catalog add column if not exists vendor_series_code varchar
-- MOSS:STMT
alter table phase1_macro_vendor_catalog add column if not exists batch_id varchar
-- MOSS:STMT
alter table phase1_macro_vendor_catalog add column if not exists catalog_version varchar
-- MOSS:STMT
alter table phase1_macro_vendor_catalog add column if not exists theme varchar
-- MOSS:STMT
alter table phase1_macro_vendor_catalog add column if not exists is_core boolean
-- MOSS:STMT
alter table phase1_macro_vendor_catalog add column if not exists tags_json varchar
-- MOSS:STMT
alter table phase1_macro_vendor_catalog add column if not exists request_options varchar
-- MOSS:STMT
alter table phase1_macro_vendor_catalog add column if not exists fetch_mode varchar
-- MOSS:STMT
alter table phase1_macro_vendor_catalog add column if not exists fetch_granularity varchar
-- MOSS:STMT
alter table phase1_macro_vendor_catalog add column if not exists refresh_tier varchar
-- MOSS:STMT
alter table phase1_macro_vendor_catalog add column if not exists policy_note varchar
-- MOSS:STMT
alter table market_data_series_category add column if not exists category_key varchar
-- MOSS:STMT
alter table market_data_series_category add column if not exists category_label varchar
-- MOSS:STMT
alter table market_data_series_category add column if not exists source_surface varchar
-- MOSS:STMT
alter table market_data_series_category add column if not exists fetch_mode varchar
-- MOSS:STMT
alter table market_data_series_category add column if not exists fetch_granularity varchar
-- MOSS:STMT
alter table market_data_series_category add column if not exists policy_note varchar
-- MOSS:STMT
alter table market_data_series_category add column if not exists catalog_version varchar
-- MOSS:STMT
alter table market_data_series_category add column if not exists batch_id varchar
-- MOSS:STMT
alter table market_data_series_category add column if not exists updated_at varchar
-- MOSS:STMT
alter table market_data_series_category add column if not exists run_id varchar
