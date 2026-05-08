-- MOSS:STMT
create table if not exists livermore_candidate_history (
  snapshot_as_of_date varchar,
  stock_code varchar,
  stock_name varchar,
  candidate_rank integer,
  sector_code varchar,
  sector_name varchar,
  selection_close double,
  forward_trade_date_1d varchar,
  forward_trade_date_5d varchar,
  forward_trade_date_20d varchar,
  return_1d double,
  return_5d double,
  return_20d double,
  data_status varchar,
  formula_version varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
