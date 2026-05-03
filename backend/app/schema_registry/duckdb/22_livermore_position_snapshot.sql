-- MOSS:STMT
create table if not exists livermore_position_snapshot (
  as_of_date varchar,
  stock_code varchar,
  stock_name varchar,
  entry_cost double,
  bars_since_entry integer,
  entry_date varchar,
  position_quantity double,
  position_status varchar,
  source_system varchar,
  source_file_hash varchar,
  source_row_no integer,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
-- MOSS:STMT
alter table livermore_position_snapshot add column if not exists entry_date varchar
-- MOSS:STMT
alter table livermore_position_snapshot add column if not exists position_quantity double
-- MOSS:STMT
alter table livermore_position_snapshot add column if not exists position_status varchar
-- MOSS:STMT
alter table livermore_position_snapshot add column if not exists source_system varchar
-- MOSS:STMT
alter table livermore_position_snapshot add column if not exists source_file_hash varchar
-- MOSS:STMT
alter table livermore_position_snapshot add column if not exists source_row_no integer
