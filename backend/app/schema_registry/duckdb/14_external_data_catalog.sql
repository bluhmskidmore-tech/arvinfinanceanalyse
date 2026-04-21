-- MOSS:STMT
create table if not exists external_data_catalog (
  series_id varchar primary key,
  series_name varchar not null,
  vendor_name varchar not null,
  source_family varchar not null,
  domain varchar not null,
  frequency varchar,
  unit varchar,
  refresh_tier varchar,
  fetch_mode varchar,
  raw_zone_path varchar,
  standardized_table varchar,
  view_name varchar,
  access_path varchar,
  catalog_version varchar not null,
  created_at timestamp not null
)
-- MOSS:STMT
create index if not exists idx_external_data_catalog_domain on external_data_catalog (domain)
