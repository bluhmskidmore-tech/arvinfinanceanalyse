-- MOSS:STMT
create table if not exists fact_formal_pnl_fi (
  report_date varchar,
  instrument_code varchar,
  portfolio_name varchar,
  cost_center varchar,
  invest_type_std varchar,
  accounting_basis varchar,
  currency_basis varchar,
  interest_income_514 decimal(24, 8),
  fair_value_change_516 decimal(24, 8),
  capital_gain_517 decimal(24, 8),
  manual_adjustment decimal(24, 8),
  total_pnl decimal(24, 8),
  source_version varchar,
  rule_version varchar,
  ingest_batch_id varchar,
  trace_id varchar
)
-- MOSS:STMT
create table if not exists fact_nonstd_pnl_bridge (
  report_date varchar,
  bond_code varchar,
  portfolio_name varchar,
  cost_center varchar,
  interest_income_514 decimal(24, 8),
  fair_value_change_516 decimal(24, 8),
  capital_gain_517 decimal(24, 8),
  manual_adjustment decimal(24, 8),
  total_pnl decimal(24, 8),
  source_version varchar,
  rule_version varchar,
  ingest_batch_id varchar,
  trace_id varchar
)
