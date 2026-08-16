-- MOSS:STMT
-- Natural-key uniqueness for the core ALM facts. Every key below was verified
-- against the full production table, not a sampled report date; the preflight in
-- _v43_add_core_fact_natural_key_constraints re-verifies before any DDL runs.
--
-- accounting_class is part of the grain because one bond is legitimately carried
-- in two books at once (931 of the 935 four-column collisions are real AC/OCI
-- splits, ~CNY 3bn per month end). maturity_date is part of it because a
-- red-reversal row and its re-booked replacement differ only by maturity.
--
-- Every key column is folded onto a sentinel because DuckDB treats NULL as
-- DISTINCT inside a unique index: an unwrapped nullable column would silently
-- exempt every NULL-bearing row from the constraint, and maturity_date alone is
-- NULL for 57,705 rows (7.5%). The varchar cast keeps one sentinel literal valid
-- for both the DATE and VARCHAR vintages of maturity_date. The migration refuses
-- to build the index if the sentinel already occurs in real data.
create unique index if not exists uq_fact_formal_bond_analytics_daily_natural_key
on fact_formal_bond_analytics_daily (coalesce(cast(report_date as varchar), '__moss_null__'), coalesce(cast(instrument_code as varchar), '__moss_null__'), coalesce(cast(portfolio_name as varchar), '__moss_null__'), coalesce(cast(cost_center as varchar), '__moss_null__'), coalesce(cast(accounting_class as varchar), '__moss_null__'), coalesce(cast(maturity_date as varchar), '__moss_null__'))
-- MOSS:STMT
-- Balance grain additionally carries currency_basis (CNY / native), position_scope
-- (asset / liability) and accounting_basis (AC / FVOCI / FVTPL); dropping any of
-- them collapses legitimately distinct rows. maturity_date is NULL for 129,836 rows.
create unique index if not exists uq_fact_formal_zqtz_balance_daily_natural_key
on fact_formal_zqtz_balance_daily (coalesce(cast(report_date as varchar), '__moss_null__'), coalesce(cast(instrument_code as varchar), '__moss_null__'), coalesce(cast(portfolio_name as varchar), '__moss_null__'), coalesce(cast(cost_center as varchar), '__moss_null__'), coalesce(cast(currency_basis as varchar), '__moss_null__'), coalesce(cast(position_scope as varchar), '__moss_null__'), coalesce(cast(accounting_basis as varchar), '__moss_null__'), coalesce(cast(maturity_date as varchar), '__moss_null__'))
-- MOSS:STMT
-- position_id is unique per report_date within one currency_basis; position_scope
-- is retained because it is a declared grain dimension of this fact.
create unique index if not exists uq_fact_formal_tyw_balance_daily_natural_key
on fact_formal_tyw_balance_daily (coalesce(cast(report_date as varchar), '__moss_null__'), coalesce(cast(position_id as varchar), '__moss_null__'), coalesce(cast(currency_basis as varchar), '__moss_null__'), coalesce(cast(position_scope as varchar), '__moss_null__'))
-- MOSS:STMT
-- One aggregated risk row per report date.
create unique index if not exists uq_fact_formal_risk_tensor_daily_natural_key
on fact_formal_risk_tensor_daily (coalesce(cast(report_date as varchar), '__moss_null__'))
-- MOSS:STMT
-- The non-standard PnL bridge carries one row per bond per portfolio per cost
-- center per report date: 2,733 rows over 19 report dates, 0 duplicate groups,
-- no NULL and no blank in any key column. It is deliberately narrower than the
-- formal FI grain next to it — the bridge has no accounting or currency
-- dimension at all, so adding one here would index a column that does not
-- exist rather than protect anything.
--
-- This index is only safe because it ships together with the loader conversion
-- in backend/app/tasks/pnl_materialize.py. Before that change the loader ran
-- "delete by report_date then insert" inside one transaction, which DuckDB
-- 1.5.1 rejects as a duplicate key against the rows it just deleted. Applying
-- this slice against an unconverted loader breaks every rerun.
create unique index if not exists uq_fact_nonstd_pnl_bridge_natural_key
on fact_nonstd_pnl_bridge (coalesce(cast(report_date as varchar), '__moss_null__'), coalesce(cast(bond_code as varchar), '__moss_null__'), coalesce(cast(portfolio_name as varchar), '__moss_null__'), coalesce(cast(cost_center as varchar), '__moss_null__'))
