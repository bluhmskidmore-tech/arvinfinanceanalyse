-- MOSS:STMT
create table if not exists position_snapshot_agg (
  batch_id bigint,
  as_of_date varchar,
  total_rows integer,
  asset_rows integer,
  liability_rows integer,
  asset_face_amount decimal(38, 8),
  liability_face_amount decimal(38, 8),
  net_face_exposure decimal(38, 8),
  source_version varchar,
  rule_version varchar,
  refreshed_at varchar
)
-- MOSS:STMT
create unique index if not exists ux_position_snapshot_agg_batch_date
on position_snapshot_agg(batch_id, as_of_date)
