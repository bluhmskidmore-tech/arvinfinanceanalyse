-- MOSS:STMT
create or replace view vw_external_legacy_choice_macro as
select
  series_id,
  series_name,
  trade_date,
  value_numeric,
  frequency,
  unit,
  source_version,
  vendor_version,
  rule_version,
  quality_flag,
  run_id
from fact_choice_macro_daily
-- MOSS:STMT
create or replace view vw_external_legacy_choice_news as
select
  ('legacy.choice.news.' || coalesce(nullif(trim(event_key), ''), cast(serial_id as varchar), 'row')) as series_id,
  case
    when length(trim(received_at)) >= 10 then substr(trim(received_at), 1, 10)
    else coalesce(nullif(trim(received_at), ''), '1970-01-01')
  end as trade_date,
  cast(null as double) as value_numeric,
  event_key,
  received_at,
  group_id,
  content_type,
  serial_id,
  request_id,
  error_code,
  error_msg,
  topic_code,
  item_index,
  payload_text,
  payload_json
from choice_news_event
-- MOSS:STMT
create or replace view vw_external_legacy_yield_curve as
select
  (
    'legacy.yield.' || coalesce(vendor_name, 'akshare') || '.' || coalesce(curve_type, 'curve') || '.' || coalesce(tenor, 'tenor')
  ) as series_id,
  trade_date,
  cast(rate_pct as double) as value_numeric,
  curve_type,
  tenor,
  rate_pct,
  vendor_name,
  vendor_version,
  source_version,
  rule_version
from fact_formal_yield_curve_daily
-- MOSS:STMT
create or replace view vw_external_legacy_fx_mid as
select
  (
    'legacy.fx.' || coalesce(vendor_name, 'src') || '.' || coalesce(base_currency, 'base') || '.' || coalesce(quote_currency, 'quote')
  ) as series_id,
  strftime(trade_date, '%Y-%m-%d') as trade_date,
  cast(mid_rate as double) as value_numeric,
  trade_date as trade_date_raw,
  base_currency,
  quote_currency,
  mid_rate,
  source_name,
  is_business_day,
  is_carry_forward,
  source_version,
  vendor_name,
  vendor_version,
  vendor_series_code,
  observed_trade_date
from fx_daily_mid
