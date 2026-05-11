-- MOSS:STMT
create table if not exists choice_stock_materialize_run (
  run_id varchar,
  as_of_date varchar,
  status varchar,
  catalog_path varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  request_count integer,
  row_count integer,
  started_at varchar,
  completed_at varchar,
  error_message varchar
)
-- MOSS:STMT
create table if not exists choice_stock_request_audit (
  run_id varchar,
  as_of_date varchar,
  input_family varchar,
  field_key varchar,
  call varchar,
  vendor_indicator varchar,
  request_arguments_json varchar,
  request_options_json varchar,
  status varchar,
  row_count integer,
  error_code integer,
  error_msg varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar
)
-- MOSS:STMT
create table if not exists choice_stock_universe (
  as_of_date varchar,
  stock_code varchar,
  stock_name varchar,
  field_key varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
-- MOSS:STMT
create table if not exists choice_stock_sector_membership (
  as_of_date varchar,
  stock_code varchar,
  sw2021 varchar,
  sw2021code varchar,
  field_key varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
-- MOSS:STMT
create table if not exists choice_stock_daily_observation (
  trade_date varchar,
  stock_code varchar,
  open_value double,
  high_value double,
  low_value double,
  close_value double,
  volume double,
  amount double,
  pctchange double,
  turn double,
  amplitude double,
  tradestatus varchar,
  highlimit varchar,
  lowlimit varchar,
  field_keys_json varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
-- MOSS:STMT
create table if not exists choice_stock_limit_quality (
  as_of_date varchar,
  stock_code varchar,
  issurgedlimit varchar,
  isdeclinelimit varchar,
  hlimitedays integer,
  llimitedays integer,
  field_key varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
-- MOSS:STMT
create table if not exists choice_stock_concept_membership (
  as_of_date varchar,
  stock_code varchar,
  concept_code varchar,
  concept_name varchar,
  concept_source varchar,
  field_key varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
-- MOSS:STMT
create table if not exists choice_stock_intraday_movement_event (
  as_of_date varchar,
  event_time varchar,
  stock_code varchar,
  stock_name varchar,
  concept_code varchar,
  concept_name varchar,
  event_type varchar,
  event_title varchar,
  pctchange double,
  turn double,
  source_url varchar,
  field_key varchar,
  raw_json varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
