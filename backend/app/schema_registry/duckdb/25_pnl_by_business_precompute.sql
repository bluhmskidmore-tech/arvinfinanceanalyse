-- MOSS:STMT
create table if not exists fact_pnl_by_business_precompute (
  year integer,
  as_of_date varchar,
  result_kind varchar,
  dimension varchar,
  business_key varchar,
  payload_json varchar,
  source_version varchar,
  rule_version varchar,
  generated_at varchar
)
