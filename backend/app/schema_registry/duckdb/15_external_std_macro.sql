-- MOSS:STMT
create table if not exists std_external_macro_daily (
  series_id varchar not null,
  vendor_name varchar not null,
  domain varchar not null,
  trade_date varchar not null,
  value_numeric double,
  frequency varchar,
  unit varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  ingest_batch_id varchar not null,
  raw_zone_path varchar,
  created_at timestamp not null,
  primary key (series_id, trade_date, ingest_batch_id)
)
-- MOSS:STMT
create index if not exists idx_std_external_macro_series on std_external_macro_daily (series_id)
-- MOSS:STMT
create or replace view vw_external_macro_daily as
select
  series_id,
  vendor_name,
  domain,
  trade_date,
  value_numeric,
  frequency,
  unit,
  source_version,
  vendor_version,
  rule_version,
  ingest_batch_id,
  raw_zone_path,
  created_at
from std_external_macro_daily
