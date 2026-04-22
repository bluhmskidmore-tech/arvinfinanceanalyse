-- MOSS:STMT
create table if not exists fx_daily_mid (
  trade_date date,
  base_currency varchar,
  quote_currency varchar,
  mid_rate decimal(24, 8),
  source_name varchar,
  is_business_day boolean,
  is_carry_forward boolean,
  source_version varchar,
  vendor_name varchar,
  vendor_version varchar,
  vendor_series_code varchar,
  observed_trade_date date
)
-- MOSS:STMT
alter table fx_daily_mid add column if not exists source_name varchar
-- MOSS:STMT
alter table fx_daily_mid add column if not exists is_business_day boolean
-- MOSS:STMT
alter table fx_daily_mid add column if not exists is_carry_forward boolean
-- MOSS:STMT
alter table fx_daily_mid add column if not exists vendor_name varchar
-- MOSS:STMT
alter table fx_daily_mid add column if not exists vendor_version varchar
-- MOSS:STMT
alter table fx_daily_mid add column if not exists vendor_series_code varchar
-- MOSS:STMT
alter table fx_daily_mid add column if not exists observed_trade_date date
