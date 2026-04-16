-- MOSS:STMT
create table if not exists phase1_materialize_runs (
  run_id varchar,
  cache_key varchar,
  status varchar
)
