-- MOSS:STMT
-- Analytical CFFEX futures member-rank data used by the macro toolkit crowding module.
-- Live fills go through backend/app/services/cffex_member_rank_service.py.
create table if not exists fact_cffex_member_rank_daily (
  trade_date varchar not null,
  contract varchar not null,
  product_code varchar not null,
  exchange varchar not null,
  member_name varchar not null,
  source_vendor varchar not null,
  source_row_no integer,
  volume double,
  volume_change double,
  long_holding double,
  long_change double,
  short_holding double,
  short_change double,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  ingest_batch_id varchar,
  raw_payload_json varchar,
  created_at timestamp not null default current_timestamp
)

-- MOSS:STMT
create unique index if not exists idx_cffex_member_rank_daily_unique
on fact_cffex_member_rank_daily (trade_date, contract, member_name, source_vendor)

-- MOSS:STMT
create or replace view vw_cffex_member_rank_daily as
select
  trade_date,
  contract,
  product_code,
  exchange,
  member_name,
  source_vendor,
  source_row_no,
  volume,
  volume_change,
  long_holding,
  long_change,
  short_holding,
  short_change,
  source_version,
  vendor_version,
  rule_version,
  ingest_batch_id,
  raw_payload_json,
  created_at
from (
  select
    *,
    row_number() over (
      partition by trade_date, contract, member_name
      order by
        case lower(source_vendor)
          when 'choice' then 0
          when 'tushare' then 1
          else 9
        end,
        created_at desc
    ) as source_rank
  from fact_cffex_member_rank_daily
) ranked
where source_rank = 1
