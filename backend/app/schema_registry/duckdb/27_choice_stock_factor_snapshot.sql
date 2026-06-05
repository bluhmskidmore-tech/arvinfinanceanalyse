-- MOSS:STMT
create table if not exists choice_stock_factor_snapshot (
  as_of_date varchar,
  stock_code varchar,
  pe double,
  pb double,
  ps double,
  roe double,
  gross_margin double,
  three_month_return double,
  twelve_month_return double,
  volatility double,
  dividend_yield double,
  industry varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
