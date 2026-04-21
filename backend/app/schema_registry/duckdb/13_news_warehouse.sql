-- MOSS:STMT
create table if not exists fact_news_event (
  news_key varchar primary key,
  source varchar not null,
  source_kind varchar not null,
  title varchar,
  url varchar,
  content varchar,
  summary varchar,
  pub_time timestamp,
  ingested_at timestamp not null,
  retention_until timestamp not null,
  extra_json varchar
)
-- MOSS:STMT
create index if not exists idx_fact_news_event_source_pub_time on fact_news_event (source, pub_time desc)
-- MOSS:STMT
create index if not exists idx_fact_news_event_retention_until on fact_news_event (retention_until)
