-- MOSS:STMT
-- Analytical-only inputs for Livermore market gate breadth / limit-up quality (per trade_date).
-- Writes go through backend/app/tasks/livermore_gate_supplement.py (not API paths).
create table if not exists fact_livermore_gate_supplement_daily (
  trade_date varchar not null,
  breadth_5d double,
  limit_up_quality_ok boolean,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar,
  primary key (trade_date)
)
