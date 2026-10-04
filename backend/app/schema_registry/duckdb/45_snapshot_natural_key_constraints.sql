-- MOSS:STMT
-- Natural-key uniqueness for the standardized zqtz/tyw snapshot tables, modeled on
-- 43_core_fact_natural_key_constraints.sql. The key columns are exactly the
-- business grain that backend.app.repositories.snapshot_repo.merge_zqtz_rows_by_grain
-- groups by (zqtz_grain_key minus the lineage columns source_version and
-- ingest_batch_id, which are provenance of a grain instance, not part of the
-- grain identity). Excluding those two is deliberate: including them would let a
-- same-day replay under a *new* ingest_batch_id sail past this constraint while
-- still leaving the prior batch's row for the same bond/position in place, which
-- is the exact double-count defect this index exists to catch.
--
-- Every key column is folded onto a sentinel because DuckDB treats NULL as
-- DISTINCT inside a unique index: an unwrapped nullable column would silently
-- exempt every NULL-bearing row (e.g. next_call_date, which is legitimately NULL
-- for non-callable bonds) from the constraint.
create unique index if not exists uq_zqtz_bond_daily_snapshot_natural_key
on zqtz_bond_daily_snapshot (coalesce(cast(report_date as varchar), '__moss_null__'), coalesce(cast(instrument_code as varchar), '__moss_null__'), coalesce(cast(instrument_name as varchar), '__moss_null__'), coalesce(cast(portfolio_name as varchar), '__moss_null__'), coalesce(cast(cost_center as varchar), '__moss_null__'), coalesce(cast(currency_code as varchar), '__moss_null__'), coalesce(cast(account_category as varchar), '__moss_null__'), coalesce(cast(asset_class as varchar), '__moss_null__'), coalesce(cast(bond_type as varchar), '__moss_null__'), coalesce(cast(business_type_primary as varchar), '__moss_null__'), coalesce(cast(maturity_date as varchar), '__moss_null__'), coalesce(cast(next_call_date as varchar), '__moss_null__'), coalesce(cast(is_issuance_like as varchar), '__moss_null__'))
-- MOSS:STMT
-- tyw_grain_key is already (report_date, position_id) with no lineage columns.
create unique index if not exists uq_tyw_interbank_daily_snapshot_natural_key
on tyw_interbank_daily_snapshot (coalesce(cast(report_date as varchar), '__moss_null__'), coalesce(cast(position_id as varchar), '__moss_null__'))
