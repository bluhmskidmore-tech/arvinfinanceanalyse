-- MOSS:STMT
create table if not exists std_external_supply_auction_calendar (
  series_id varchar not null,
  event_id varchar not null,
  vendor_name varchar not null,
  source_family varchar not null,
  domain varchar not null,
  event_date varchar not null,
  event_kind varchar not null,
  title varchar not null,
  issuer varchar,
  market varchar,
  instrument_type varchar,
  term_label varchar,
  amount_numeric double,
  amount_unit varchar,
  currency varchar,
  status varchar,
  severity varchar,
  headline_text varchar,
  headline_url varchar,
  headline_published_at varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  ingest_batch_id varchar not null,
  created_at timestamp not null,
  primary key (event_id, ingest_batch_id)
)
-- MOSS:STMT
create index if not exists idx_std_external_supply_auction_calendar_series_date
on std_external_supply_auction_calendar (series_id, event_date)
-- MOSS:STMT
create or replace view vw_external_supply_auction_calendar as
select
  series_id,
  event_id,
  vendor_name,
  source_family,
  domain,
  event_date,
  event_kind,
  title,
  issuer,
  market,
  instrument_type,
  term_label,
  amount_numeric,
  amount_unit,
  currency,
  status,
  severity,
  headline_text,
  headline_url,
  headline_published_at,
  source_version,
  vendor_version,
  rule_version,
  ingest_batch_id,
  created_at
from std_external_supply_auction_calendar
