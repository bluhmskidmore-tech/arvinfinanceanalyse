-- MOSS:STMT
-- Proposed point-in-time stock status sidecar for market-breadth classification.
--
-- This proposal is intentionally outside the active root migration ledger:
-- registering a new version also requires changes to
-- backend/app/repositories/duckdb_migrations.py, which is outside this task's
-- allowed file set. Move it into the active ledger only with that integration.
--
-- A sidecar is intentional: choice_stock_daily_observation is currently
-- written with a positional 19-value INSERT. Adding columns to that table
-- before the occupied Choice writer is changed would break every refresh.
--
-- TODO(choice-stock-materialize): after a live Choice probe confirms the
-- daily ST indicator and listing-date entitlement, normalize those fields in
-- backend/app/tasks/choice_stock_materialize.py::_merge_daily_rows and add a
-- dedicated _insert_daily_security_status beside _insert_daily_observations.
-- Keep NULL is_st for genuinely unavailable vendor data so market breadth can
-- distinguish it from an explicit false value and fall back to the name.
create table if not exists choice_stock_daily_security_status (
  trade_date varchar not null,
  stock_code varchar not null,
  is_st boolean,
  listing_date varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar,
  primary key (trade_date, stock_code)
)
