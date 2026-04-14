-- MOSS:STMT
create table if not exists fact_formal_yield_curve_daily (
    trade_date varchar,
    curve_type varchar,
    tenor varchar,
    rate_pct decimal(18, 8),
    vendor_name varchar,
    vendor_version varchar,
    source_version varchar,
    rule_version varchar
)
-- MOSS:STMT
create or replace view yield_curve_daily as
select
  trade_date,
  curve_type,
  tenor,
  rate_pct,
  vendor_name,
  vendor_version,
  source_version
from fact_formal_yield_curve_daily
