-- MOSS:STMT
-- Daily all-market breadth + limit-up seal/break counts aggregated from
-- choice_stock_daily_observation. Feeds fact_livermore_gate_supplement_daily.
-- Writes go through backend/app/tasks/market_breadth_materialize.py (not API paths).
create table if not exists fact_market_breadth_daily (
  trade_date varchar not null,
  total_count integer,
  advancing_count integer,
  declining_count integer,
  unchanged_count integer,
  limit_up_sealed_count integer,
  limit_up_broken_count integer,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar,
  primary key (trade_date)
)
