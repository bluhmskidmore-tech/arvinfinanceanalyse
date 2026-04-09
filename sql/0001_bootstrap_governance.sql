create table if not exists source_version_registry (
  source_name text not null,
  source_version text not null,
  created_at timestamptz default now()
);

create table if not exists rule_version_registry (
  rule_name text not null,
  rule_version text not null,
  created_at timestamptz default now()
);

create table if not exists cache_manifest (
  cache_key text not null,
  source_version text not null,
  rule_version text not null,
  created_at timestamptz default now()
);
