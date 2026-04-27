-- MOSS:STMT
create table if not exists zqtz_bond_daily_snapshot (
  report_date date,
  instrument_code varchar,
  instrument_name varchar,
  portfolio_name varchar,
  cost_center varchar,
  account_category varchar,
  asset_class varchar,
  bond_type varchar,
  business_type_primary varchar,
  issuer_name varchar,
  industry_name varchar,
  rating varchar,
  currency_code varchar,
  face_value_native decimal(24, 8),
  market_value_native decimal(24, 8),
  amortized_cost_native decimal(24, 8),
  accrued_interest_native decimal(24, 8),
  coupon_rate decimal(18, 8),
  ytm_value decimal(18, 8),
  maturity_date date,
  next_call_date date,
  overdue_days integer,
  is_issuance_like boolean,
  interest_mode varchar,
  source_version varchar,
  rule_version varchar,
  ingest_batch_id varchar,
  trace_id varchar
)
-- MOSS:STMT
alter table zqtz_bond_daily_snapshot add column if not exists value_date date
-- MOSS:STMT
alter table zqtz_bond_daily_snapshot add column if not exists customer_attribute varchar
-- MOSS:STMT
create table if not exists tyw_interbank_daily_snapshot (
  report_date date,
  position_id varchar,
  product_type varchar,
  position_side varchar,
  counterparty_name varchar,
  account_type varchar,
  special_account_type varchar,
  core_customer_type varchar,
  currency_code varchar,
  principal_native decimal(24, 8),
  accrued_interest_native decimal(24, 8),
  funding_cost_rate decimal(18, 8),
  maturity_date date,
  pledged_bond_code varchar,
  source_version varchar,
  rule_version varchar,
  ingest_batch_id varchar,
  trace_id varchar
)
