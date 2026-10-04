"""DuckDB DDL and replace-safe writers for standardized zqtz / tyw snapshot tables."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import duckdb
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.task_write_guard import require_repository_task_write_scope
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

ZQTZ_TABLE = "zqtz_bond_daily_snapshot"
TYW_TABLE = "tyw_interbank_daily_snapshot"

# Mirrors backend.app.repositories.snapshot_repo.zqtz_grain_key / tyw_grain_key --
# the exact grain the in-memory merge groups by -- minus the lineage columns
# `source_version` and `ingest_batch_id`. Those two identify *which upload
# produced* a grain instance, not the grain itself; keeping them in the natural
# key would let a same-day replay under a *new* ingest_batch_id sail past both
# the unique index and the pre-delete below while the prior batch's row for the
# same bond/position stayed in place -- the exact double-count defect these
# exist to prevent. tyw_grain_key already excludes them (report_date + position_id only).
ZQTZ_SNAPSHOT_NATURAL_KEY_COLUMNS = (
    "report_date",
    "instrument_code",
    "instrument_name",
    "portfolio_name",
    "cost_center",
    "currency_code",
    "account_category",
    "asset_class",
    "bond_type",
    "business_type_primary",
    "maturity_date",
    "next_call_date",
    "is_issuance_like",
)
TYW_SNAPSHOT_NATURAL_KEY_COLUMNS = ("report_date", "position_id")


def _dedupe_table_keep_last_written_row(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    key_columns: tuple[str, ...],
) -> None:
    """Delete duplicate rows under a NULL-folded key, keeping the highest `rowid`.

    `rowid` is DuckDB's physical insertion-order proxy, so the surviving row is
    the one a correct rerun would have replaced in place -- the deterministic
    "keep the last-written row" rule.
    """
    key_expression = ", ".join(
        f"coalesce(cast({column} as varchar), '__moss_null__')" for column in key_columns
    )
    conn.execute(
        f"""
        delete from {table_name}
        where rowid not in (
            select rowid from (
                select rowid, row_number() over (
                    partition by {key_expression}
                    order by rowid desc
                ) as rn
                from {table_name}
            ) ranked
            where rn = 1
        )
        """
    )


def _assert_no_natural_key_sentinel_collision(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    key_columns: tuple[str, ...],
) -> None:
    """Refuse to build the NULL-folded index if the sentinel already occurs as real data."""
    for column in key_columns:
        collision_row = conn.execute(
            f"select count(*) from {table_name} where cast({column} as varchar) = '__moss_null__'"
        ).fetchone()
        collision_count = int(collision_row[0]) if collision_row else 0
        if collision_count:
            raise RuntimeError(
                f"{table_name}.{column} contains {collision_count} rows matching the "
                "snapshot natural-key NULL sentinel ('__moss_null__'); pick a value outside the domain"
            )


def ensure_snapshot_natural_key_constraints(conn: duckdb.DuckDBPyConnection) -> None:
    """Constrain zqtz/tyw standardized snapshot grains, modeled on
    43_core_fact_natural_key_constraints.sql.

    Defect: 32_fact_snapshot_indexes.sql only gave these tables a plain
    `report_date` index, so a same-day materialization replay under a *new*
    ingest_batch_id (see backend.app.tasks.snapshot_materialize) could leave the
    prior batch's row for the same bond/position in place, double-counting
    market value downstream. See ZQTZ_SNAPSHOT_NATURAL_KEY_COLUMNS above for why
    the key excludes ingest_batch_id/source_version.

    Deviation from v43: v43 refuses to run when the natural key already has
    duplicate groups ("do NOT deduplicate -- investigate the grain first"),
    because a duplicate there is an unexplained anomaly. Here the duplicate
    groups this migration finds *are* the defect being fixed -- accumulated
    same-day reruns under different batch ids -- so this deduplicates before
    building the index, keeping the last-written row per group.

    Lazy-ensure exempt (see manifest.json): the ordinary migration ledger is
    frozen at v45, so this cannot be registered as a new versioned migration;
    it is applied idempotently every time `ensure_snapshot_tables` runs instead.
    """
    if not _main_table_exists(conn, ZQTZ_TABLE) or not _main_table_exists(conn, TYW_TABLE):
        text = (REGISTRY_DIR / "01_snapshot.sql").read_text(encoding="utf-8")
        for statement in parse_registry_sql_text(text):
            conn.execute(statement)

    for table_name, key_columns in (
        (ZQTZ_TABLE, ZQTZ_SNAPSHOT_NATURAL_KEY_COLUMNS),
        (TYW_TABLE, TYW_SNAPSHOT_NATURAL_KEY_COLUMNS),
    ):
        _assert_no_natural_key_sentinel_collision(conn, table_name, key_columns)
        _dedupe_table_keep_last_written_row(conn, table_name, key_columns)

    text = (REGISTRY_DIR / "45_snapshot_natural_key_constraints.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def _main_table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_schema = 'main' and table_name = ?
        limit 1
        """,
        [table_name],
    ).fetchone()
    return row is not None


def ensure_snapshot_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)
    ensure_snapshot_natural_key_constraints(conn)


def delete_zqtz_snapshots_for_batches(
    conn: duckdb.DuckDBPyConnection,
    ingest_batch_ids: list[str],
    *,
    report_dates: list[object] | None = None,
) -> None:
    require_repository_task_write_scope("delete_zqtz_snapshots_for_batches")
    if not ingest_batch_ids:
        return
    placeholders = ",".join(["?"] * len(ingest_batch_ids))
    params: list[object] = list(ingest_batch_ids)
    where_clause = f"ingest_batch_id in ({placeholders})"
    if report_dates:
        report_placeholders = ",".join(["?"] * len(report_dates))
        where_clause += f" and report_date in ({report_placeholders})"
        params.extend(report_dates)
    conn.execute(f"delete from {ZQTZ_TABLE} where {where_clause}", params)


def delete_zqtz_snapshots_for_report_dates(
    conn: duckdb.DuckDBPyConnection,
    report_dates: list[object],
) -> None:
    require_repository_task_write_scope("delete_zqtz_snapshots_for_report_dates")
    if not report_dates:
        return
    placeholders = ",".join(["?::date"] * len(report_dates))
    conn.execute(f"delete from {ZQTZ_TABLE} where report_date in ({placeholders})", list(report_dates))


def delete_tyw_snapshots_for_batches(
    conn: duckdb.DuckDBPyConnection,
    ingest_batch_ids: list[str],
    *,
    report_dates: list[object] | None = None,
) -> None:
    require_repository_task_write_scope("delete_tyw_snapshots_for_batches")
    if not ingest_batch_ids:
        return
    placeholders = ",".join(["?"] * len(ingest_batch_ids))
    params: list[object] = list(ingest_batch_ids)
    where_clause = f"ingest_batch_id in ({placeholders})"
    if report_dates:
        report_placeholders = ",".join(["?"] * len(report_dates))
        where_clause += f" and report_date in ({report_placeholders})"
        params.extend(report_dates)
    conn.execute(f"delete from {TYW_TABLE} where {where_clause}", params)


def delete_tyw_snapshots_for_report_dates(
    conn: duckdb.DuckDBPyConnection,
    report_dates: list[object],
) -> None:
    require_repository_task_write_scope("delete_tyw_snapshots_for_report_dates")
    if not report_dates:
        return
    placeholders = ",".join(["?::date"] * len(report_dates))
    conn.execute(f"delete from {TYW_TABLE} where report_date in ({placeholders})", list(report_dates))


def _sql_value(value: object) -> object:
    """Keep exact Python values for DuckDB parameter binding.

    DuckDB accepts ``Decimal`` directly. Converting it to ``float`` here loses
    precision before DECIMAL columns can apply their declared scale.
    """
    return value


def replace_zqtz_snapshot_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[dict[str, Any]],
    *,
    ingest_batch_ids: list[str],
    report_dates: list[object] | None = None,
    replace_all_for_report_dates: bool = False,
) -> int:
    require_repository_task_write_scope("replace_zqtz_snapshot_rows")
    if replace_all_for_report_dates and report_dates:
        delete_zqtz_snapshots_for_report_dates(conn, list(report_dates))
    else:
        delete_zqtz_snapshots_for_batches(conn, ingest_batch_ids, report_dates=report_dates)
    if not rows:
        return 0
    # Same-day replay under a *different* ingest_batch_id (e.g. an explicit
    # rematerialize of a corrected batch) is not caught by the batch-scoped
    # delete above. Remove any row already sharing an incoming row's natural
    # grain -- regardless of which batch wrote it -- before inserting, so the
    # new batch's value is the only one left instead of accumulating a
    # duplicate that double-counts market value downstream.
    _delete_rows_matching_natural_key(
        conn,
        ZQTZ_TABLE,
        ZQTZ_SNAPSHOT_NATURAL_KEY_COLUMNS,
        {zqtz_snapshot_natural_key(r) for r in rows},
    )
    conn.executemany(
        f"""
        insert into {ZQTZ_TABLE} (
          report_date,
          instrument_code,
          instrument_name,
          portfolio_name,
          cost_center,
          account_category,
          asset_class,
          bond_type,
          business_type_primary,
          issuer_name,
          industry_name,
          rating,
          currency_code,
          face_value_native,
          market_value_native,
          amortized_cost_native,
          accrued_interest_native,
          coupon_rate,
          ytm_value,
          maturity_date,
          next_call_date,
          overdue_days,
          is_issuance_like,
          interest_mode,
          source_version,
          rule_version,
          ingest_batch_id,
          trace_id,
          value_date,
          customer_attribute,
          sub_type,
          interest_receivable_payable
        ) values (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                _sql_value(r["report_date"]),
                r["instrument_code"],
                r["instrument_name"],
                r["portfolio_name"],
                r["cost_center"],
                r["account_category"],
                r["asset_class"],
                r["bond_type"],
                r.get("business_type_primary") or "",
                r["issuer_name"],
                r["industry_name"],
                r["rating"],
                r["currency_code"],
                _sql_value(r["face_value_native"]),
                _sql_value(r["market_value_native"]),
                _sql_value(r["amortized_cost_native"]),
                _sql_value(r["accrued_interest_native"]),
                _sql_value(r["coupon_rate"]),
                _sql_value(r["ytm_value"]),
                _sql_value(r["maturity_date"]),
                _sql_value(r["next_call_date"]),
                r["overdue_days"],
                r["is_issuance_like"],
                r["interest_mode"],
                r["source_version"],
                r["rule_version"],
                r["ingest_batch_id"],
                r["trace_id"],
                _sql_value(r.get("value_date")),
                r.get("customer_attribute") or "",
                r.get("sub_type") or "",
                _sql_value(r.get("interest_receivable_payable")),
            )
            for r in rows
        ],
    )
    return len(rows)


def repair_zqtz_snapshot_coupon_rates(
    conn: duckdb.DuckDBPyConnection,
    repairs: list[dict[str, Any]],
) -> int:
    """Apply an exact, task-scoped coupon remediation without replacing snapshot rows."""

    require_repository_task_write_scope("repair_zqtz_snapshot_coupon_rates")
    changed_count = 0
    conn.execute("begin transaction")
    try:
        for repair in repairs:
            key_params = [repair["report_date"], repair["instrument_code"]]
            current = conn.execute(
                f"""
                select coupon_rate, source_version, rule_version, trace_id
                from {ZQTZ_TABLE}
                where cast(report_date as varchar) = ?
                  and cast(instrument_code as varchar) = ?
                """,
                key_params,
            ).fetchall()
            if len(current) != 1:
                raise RuntimeError(
                    "Coupon remediation target must resolve to exactly one snapshot row: "
                    f"report_date={repair['report_date']}, "
                    f"instrument_code={repair['instrument_code']}, rows={len(current)}."
                )
            expected_before = (
                repair["before_coupon_rate"],
                repair["source_version_before"],
                repair["rule_version_before"],
                repair["trace_id_before"],
            )
            if tuple(current[0]) != expected_before:
                raise RuntimeError(
                    "Coupon remediation target changed after preview: "
                    f"report_date={repair['report_date']}, "
                    f"instrument_code={repair['instrument_code']}."
                )
            conn.execute(
                f"""
                update {ZQTZ_TABLE}
                set coupon_rate = ?,
                    source_version = ?,
                    rule_version = ?,
                    trace_id = ?
                where cast(report_date as varchar) = ?
                  and cast(instrument_code as varchar) = ?
                """,
                [
                    repair["after_coupon_rate"],
                    repair["source_version_after"],
                    repair["rule_version_after"],
                    repair["trace_id_after"],
                    *key_params,
                ],
            )
            changed_count += 1
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise
    return changed_count


def replace_tyw_snapshot_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[dict[str, Any]],
    *,
    ingest_batch_ids: list[str],
    report_dates: list[object] | None = None,
    replace_all_for_report_dates: bool = False,
) -> int:
    require_repository_task_write_scope("replace_tyw_snapshot_rows")
    if replace_all_for_report_dates and report_dates:
        delete_tyw_snapshots_for_report_dates(conn, list(report_dates))
    else:
        delete_tyw_snapshots_for_batches(conn, ingest_batch_ids, report_dates=report_dates)
    if not rows:
        return 0
    # See the matching comment in replace_zqtz_snapshot_rows: catches a same-day
    # replay under a different ingest_batch_id for the same position.
    _delete_rows_matching_natural_key(
        conn,
        TYW_TABLE,
        TYW_SNAPSHOT_NATURAL_KEY_COLUMNS,
        {tyw_snapshot_natural_key(r) for r in rows},
    )
    conn.executemany(
        f"""
        insert into {TYW_TABLE} values (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                _sql_value(r["report_date"]),
                r["position_id"],
                r["product_type"],
                r["position_side"],
                r["counterparty_name"],
                r["account_type"],
                r["special_account_type"],
                r["core_customer_type"],
                r["currency_code"],
                _sql_value(r["principal_native"]),
                _sql_value(r["accrued_interest_native"]),
                _sql_value(r["funding_cost_rate"]),
                _sql_value(r["maturity_date"]),
                r["pledged_bond_code"],
                r["source_version"],
                r["rule_version"],
                r["ingest_batch_id"],
                r["trace_id"],
            )
            for r in rows
        ],
    )
    return len(rows)


def zqtz_grain_key(row: dict[str, Any]) -> tuple[object, ...]:
    return (
        row["report_date"],
        row["instrument_code"],
        row["instrument_name"],
        row["portfolio_name"],
        row["cost_center"],
        row["currency_code"],
        row["account_category"],
        row["asset_class"],
        row["bond_type"],
        row.get("business_type_primary") or "",
        row["maturity_date"],
        row["next_call_date"],
        row["is_issuance_like"],
        row["source_version"],
        row["ingest_batch_id"],
    )


def tyw_grain_key(row: dict[str, Any]) -> tuple[object, ...]:
    return (row["report_date"], row["position_id"])


def zqtz_snapshot_natural_key(row: dict[str, Any]) -> tuple[object, ...]:
    """zqtz_grain_key minus the lineage columns (source_version, ingest_batch_id).

    See ZQTZ_SNAPSHOT_NATURAL_KEY_COLUMNS for why they are excluded.
    """
    return zqtz_grain_key(row)[: len(ZQTZ_SNAPSHOT_NATURAL_KEY_COLUMNS)]


def tyw_snapshot_natural_key(row: dict[str, Any]) -> tuple[object, ...]:
    """tyw_grain_key already excludes lineage columns; kept as a named alias."""
    return tyw_grain_key(row)


def _delete_rows_matching_natural_key(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    key_columns: tuple[str, ...],
    key_tuples: set[tuple[object, ...]],
) -> None:
    """Delete pre-existing rows (any ingest_batch_id) whose natural key matches an incoming row.

    NULL-safe (coalesce(cast(col as varchar), '__moss_null__')), matching the
    unique index built by ensure_snapshot_natural_key_constraints. This is what
    stops a same-day replay under a *different* ingest_batch_id from leaving the
    prior batch's row for the same grain in place -- the double-count defect.
    """
    if not key_tuples:
        return
    predicate = " and ".join(
        f"coalesce(cast({column} as varchar), '__moss_null__') = coalesce(cast(? as varchar), '__moss_null__')"
        for column in key_columns
    )
    conn.executemany(f"delete from {table_name} where {predicate}", list(key_tuples))


def merge_tyw_rows_by_grain(rows_in_order: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[object, ...], dict[str, Any]] = {}

    additive_fields = ("principal_native", "accrued_interest_native")
    protected_fields = (
        "product_type",
        "position_side",
        "counterparty_name",
        "account_type",
        "special_account_type",
        "core_customer_type",
        "currency_code",
        "maturity_date",
        "source_version",
        "rule_version",
        "ingest_batch_id",
    )

    for row in rows_in_order:
        key = tyw_grain_key(row)
        if key not in merged:
            merged[key] = dict(row)
            continue

        existing = merged[key]
        for field in protected_fields:
            if existing.get(field) != row.get(field):
                raise ValueError(
                    "Fail closed: conflicting TYW snapshot rows share the same canonical grain "
                    f"{key!r} but differ at field {field!r}: {existing.get(field)!r} != {row.get(field)!r}."
                )

        for field in additive_fields:
            existing[field] = Decimal(str(existing.get(field) or 0)) + Decimal(str(row.get(field) or 0))

        pledged_codes = sorted(
            {
                str(value).strip()
                for value in (existing.get("pledged_bond_code"), row.get("pledged_bond_code"))
                if str(value or "").strip()
            }
        )
        existing["pledged_bond_code"] = "|".join(pledged_codes) if pledged_codes else None

    weighted_rate_num: dict[tuple[object, ...], Decimal] = {}
    missing_rate_weight: set[tuple[object, ...]] = set()
    for source in rows_in_order:
        key = tyw_grain_key(source)
        principal = Decimal(str(source.get("principal_native") or 0))
        if not principal.is_finite():
            raise ValueError("TYW snapshot principal_native must be finite for rate weighting")
        weighted_rate_num.setdefault(key, Decimal("0"))
        if principal == 0:
            continue
        rate = source.get("funding_cost_rate")
        if rate in (None, ""):
            missing_rate_weight.add(key)
            continue
        parsed_rate = Decimal(str(rate))
        if parsed_rate.is_finite():
            weighted_rate_num[key] += principal * parsed_rate
        else:
            missing_rate_weight.add(key)

    for key, row in merged.items():
        principal = Decimal(str(row.get("principal_native") or 0))
        row["funding_cost_rate"] = (
            weighted_rate_num[key] / principal
            if principal != 0 and key not in missing_rate_weight
            else None
        )

    return list(merged.values())


def merge_zqtz_rows_by_grain(rows_in_order: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[object, ...], dict[str, Any]] = {}
    weighted_fields = ("coupon_rate", "ytm_value")

    additive_fields = (
        "face_value_native",
        "market_value_native",
        "amortized_cost_native",
        "accrued_interest_native",
    )
    # Summed like the additive fields, but "unknown" must not collapse to 0:
    # a genuine 0 receivable is an observation (coupon just paid), NULL is not.
    nullable_additive_fields = ("interest_receivable_payable",)
    protected_fields = (
        "instrument_name",
        "portfolio_name",
        "cost_center",
        "account_category",
        "asset_class",
        "bond_type",
        "business_type_primary",
        "issuer_name",
        "industry_name",
        "rating",
        "currency_code",
        "maturity_date",
        "next_call_date",
        "overdue_days",
        "is_issuance_like",
        "interest_mode",
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "value_date",
        "customer_attribute",
    )

    for row in rows_in_order:
        key = zqtz_grain_key(row)
        if key not in merged:
            merged[key] = dict(row)
            continue

        existing = merged[key]
        for field in protected_fields:
            if existing.get(field) != row.get(field):
                raise ValueError(
                    "Fail closed: conflicting ZQTZ snapshot rows share the same canonical grain "
                    f"{key!r} but differ at field {field!r}: {existing.get(field)!r} != {row.get(field)!r}."
                )

        for field in additive_fields:
            existing[field] = Decimal(str(existing.get(field) or 0)) + Decimal(str(row.get(field) or 0))

        for field in nullable_additive_fields:
            incoming = row.get(field)
            if incoming is None:
                continue
            current = existing.get(field)
            existing[field] = (
                Decimal(str(incoming))
                if current is None
                else Decimal(str(current)) + Decimal(str(incoming))
            )

        trace_ids = sorted(
            {
                str(value).strip()
                for value in (existing.get("trace_id"), row.get("trace_id"))
                if str(value or "").strip()
            }
        )
        existing["trace_id"] = "|".join(trace_ids) if trace_ids else ""

    weighted_nums: dict[tuple[object, ...], dict[str, Decimal]] = {}
    missing_rate_weight: dict[tuple[object, ...], set[str]] = {}
    for source in rows_in_order:
        key = zqtz_grain_key(source)
        face_value = Decimal(str(source.get("face_value_native") or 0))
        if not face_value.is_finite():
            raise ValueError("ZQTZ snapshot face_value_native must be finite for rate weighting")
        nums = weighted_nums.setdefault(key, {field: Decimal("0") for field in weighted_fields})
        missing = missing_rate_weight.setdefault(key, set())
        if face_value == 0:
            continue
        for field in weighted_fields:
            value = source.get(field)
            if value in (None, ""):
                missing.add(field)
                continue
            parsed_rate = Decimal(str(value))
            if parsed_rate.is_finite():
                nums[field] += face_value * parsed_rate
            else:
                missing.add(field)

    for key, row in merged.items():
        face_value = Decimal(str(row.get("face_value_native") or 0))
        for field in weighted_fields:
            row[field] = (
                weighted_nums[key][field] / face_value
                if face_value != 0 and field not in missing_rate_weight[key]
                else None
            )

    return list(merged.values())


def merge_rows_by_grain(
    rows_in_order: list[dict[str, Any]],
    grain_fn,
) -> list[dict[str, Any]]:
    merged: dict[tuple[object, ...], dict[str, Any]] = {}
    for row in rows_in_order:
        merged[grain_fn(row)] = row
    return list(merged.values())
