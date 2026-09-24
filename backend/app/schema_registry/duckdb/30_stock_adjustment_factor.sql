-- MOSS:STMT
create table if not exists stock_adjustment_factor (
  stock_code varchar,
  trade_date varchar,
  adj_factor double,
  source_version varchar,
  run_id varchar
)
