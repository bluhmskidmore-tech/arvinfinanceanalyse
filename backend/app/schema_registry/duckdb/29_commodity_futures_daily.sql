-- MOSS:STMT
-- Main-contract commodity futures + Nanhua index daily bars for cross-asset dashboards.
-- Live fills go through backend/app/tasks/commodity_daily_ingest.py.
create table if not exists fact_commodity_futures_daily (
  trade_date varchar not null,
  product_code varchar not null,
  contract_code varchar,
  exchange varchar,
  open_value double,
  high_value double,
  low_value double,
  close_value double,
  settle_value double,
  volume double,
  open_interest double,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar default 'rv_commodity_daily_v1',
  created_at timestamp default current_timestamp,
  primary key (trade_date, product_code)
)
