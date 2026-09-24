-- Point-in-time SCD interval read model derived from choice_stock_concept_membership
-- snapshots (stock x concept x [valid_from, valid_to)). valid_from is the first
-- snapshot date the membership was observed; valid_to is the first later snapshot
-- date (of the same stock and concept_source) where the membership disappeared
-- (exclusive); NULL valid_to means the membership is still open as of the latest
-- observation. Dates before a stock's first observed snapshot have no rows by
-- construction (fail-closed for historical replay). Writer:
-- backend/app/tasks/concept_membership_intervalize.py (deterministic rebuild).
-- Contract: docs/data_contracts.md §4.11.
-- MOSS:STMT
create table if not exists choice_stock_concept_membership_interval (
  stock_code varchar not null,
  concept_code varchar not null,
  concept_name varchar,
  concept_source varchar not null,
  valid_from varchar not null,
  valid_to varchar,
  last_observed_date varchar not null,
  field_key varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
-- MOSS:STMT
create unique index if not exists uq_concept_membership_interval_natural_key
on choice_stock_concept_membership_interval (stock_code, concept_code, concept_source, valid_from)
