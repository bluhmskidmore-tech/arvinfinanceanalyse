-- MOSS:STMT
create table if not exists livermore_matched_baseline_history (
  signal_date varchar,
  candidate_stock_code varchar,
  signal_kind varchar,
  control_stock_code varchar,
  control_group varchar,
  control_return_1d_net_adj double,
  control_return_5d_net_adj double,
  control_return_10d_net_adj double,
  control_return_20d_net_adj double,
  control_entry_executable boolean,
  seed varchar,
  formula_version varchar,
  run_id varchar
)
