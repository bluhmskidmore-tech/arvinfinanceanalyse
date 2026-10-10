-- MOSS:STMT
create table if not exists fact_stock_official_disclosure (
  disclosure_key varchar not null,
  stock_code varchar not null,
  stock_name varchar not null,
  evidence_type varchar not null check (evidence_type in ('official_announcement', 'financial_report')),
  publish_date date not null,
  report_period date,
  title varchar not null,
  document_url varchar not null,
  source_id varchar not null,
  source_label varchar not null,
  source_version varchar not null,
  vendor_version varchar not null,
  received_at timestamptz,
  ingested_at timestamptz not null,
  run_id varchar not null,
  raw_json varchar not null,
  primary key (disclosure_key)
)

-- MOSS:STMT
create index if not exists idx_fact_stock_official_disclosure_code_publish_date
on fact_stock_official_disclosure (stock_code, publish_date)

-- MOSS:STMT
create index if not exists idx_fact_stock_official_disclosure_code_type_publish_date
on fact_stock_official_disclosure (stock_code, evidence_type, publish_date)

-- MOSS:STMT
create index if not exists idx_fact_stock_official_disclosure_type_period_publish_date
on fact_stock_official_disclosure (evidence_type, report_period, publish_date)

-- MOSS:STMT
create table if not exists stock_official_disclosure_sync_status (
  stock_code varchar not null,
  requested_from_date date not null,
  covered_through_date date,
  last_attempt_at timestamptz not null,
  last_success_at timestamptz,
  status varchar not null,
  fetched_count integer not null,
  upserted_count integer not null,
  error varchar,
  run_id varchar not null,
  source_version varchar not null,
  primary key (stock_code)
)
