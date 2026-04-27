-- MOSS:STMT
create table if not exists fact_formal_zqtz_balance_daily (
  report_date varchar,
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
  invest_type_std varchar,
  accounting_basis varchar,
  position_scope varchar,
  currency_basis varchar,
  currency_code varchar,
  face_value_amount decimal(24, 8),
  market_value_amount decimal(24, 8),
  amortized_cost_amount decimal(24, 8),
  accrued_interest_amount decimal(24, 8),
  coupon_rate decimal(18, 8),
  ytm_value decimal(18, 8),
  maturity_date varchar,
  interest_mode varchar,
  is_issuance_like boolean,
  source_version varchar,
  rule_version varchar,
  ingest_batch_id varchar,
  trace_id varchar
)
-- MOSS:STMT
alter table fact_formal_zqtz_balance_daily add column if not exists overdue_principal_days integer
-- MOSS:STMT
alter table fact_formal_zqtz_balance_daily add column if not exists overdue_interest_days integer
-- MOSS:STMT
alter table fact_formal_zqtz_balance_daily add column if not exists value_date varchar
-- MOSS:STMT
alter table fact_formal_zqtz_balance_daily add column if not exists customer_attribute varchar
-- MOSS:STMT
create table if not exists fact_formal_tyw_balance_daily (
  report_date varchar,
  position_id varchar,
  product_type varchar,
  position_side varchar,
  counterparty_name varchar,
  account_type varchar,
  special_account_type varchar,
  core_customer_type varchar,
  invest_type_std varchar,
  accounting_basis varchar,
  position_scope varchar,
  currency_basis varchar,
  currency_code varchar,
  principal_amount decimal(24, 8),
  accrued_interest_amount decimal(24, 8),
  funding_cost_rate decimal(18, 8),
  maturity_date varchar,
  source_version varchar,
  rule_version varchar,
  ingest_batch_id varchar,
  trace_id varchar
)
