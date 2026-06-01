-- MOSS:STMT
create table if not exists ledger_import_batch (
  batch_id bigint,
  file_name varchar,
  file_hash varchar,
  as_of_date varchar,
  status varchar,
  row_count integer,
  error_count integer,
  source_version varchar,
  rule_version varchar,
  duplicate_of_batch_id bigint,
  created_at varchar
)
-- MOSS:STMT
create table if not exists ledger_raw_row (
  batch_id bigint,
  row_no integer,
  raw_json varchar,
  source_version varchar,
  rule_version varchar
)
-- MOSS:STMT
create table if not exists position_snapshot (
  batch_id bigint,
  row_no integer,
  as_of_date varchar,
  position_key varchar,
  direction varchar,
  bond_code varchar,
  bond_name varchar,
  counterparty_cif_no varchar,
  portfolio varchar,
  business_type varchar,
  credit_customer_attribute varchar,
  business_type_1 varchar,
  account_category_std varchar,
  cost_center varchar,
  asset_class_std varchar,
  risk_mitigation varchar,
  face_amount decimal(24, 8),
  fair_value decimal(24, 8),
  amortized_cost decimal(24, 8),
  accrued_interest decimal(24, 8),
  interest_method varchar,
  coupon_rate decimal(24, 12),
  interest_start_date varchar,
  maturity_date varchar,
  interest_rate_benchmark_code varchar,
  interest_rate_reset_frequency varchar,
  counterparty_industry varchar,
  counterparty_name_cn varchar,
  credit_customer_id varchar,
  credit_customer_no varchar,
  credit_customer_rating varchar,
  credit_customer_industry varchar,
  interest_receivable_payable decimal(24, 8),
  currency varchar,
  credit_customer_name varchar,
  manual_impairment_adjustment varchar,
  channel varchar,
  legal_customer_name varchar,
  legal_customer_id varchar,
  group_customer_name varchar,
  group_customer_id varchar,
  principal_overdue_flag varchar,
  interest_overdue_flag varchar,
  quantity decimal(24, 8),
  latest_face_value decimal(24, 8),
  principal_overdue_days integer,
  interest_overdue_days integer,
  yield_to_maturity decimal(24, 12),
  option_or_special_maturity_date varchar,
  source_version varchar,
  rule_version varchar
)
-- MOSS:STMT
create unique index if not exists ux_ledger_import_batch_batch_id
on ledger_import_batch(batch_id)
-- MOSS:STMT
create unique index if not exists ux_ledger_import_batch_file_hash
on ledger_import_batch(file_hash)
-- MOSS:STMT
create unique index if not exists ux_ledger_raw_row_batch_row
on ledger_raw_row(batch_id, row_no)
-- MOSS:STMT
create unique index if not exists ux_position_snapshot_batch_row
on position_snapshot(batch_id, row_no)
