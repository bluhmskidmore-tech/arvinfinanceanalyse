"""DuckDB DDL and replace-safe writers for standardized zqtz / tyw snapshot tables."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import duckdb

from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection

ZQTZ_TABLE = "zqtz_bond_daily_snapshot"
TYW_TABLE = "tyw_interbank_daily_snapshot"


def ensure_snapshot_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)


def delete_zqtz_snapshots_for_batches(
    conn: duckdb.DuckDBPyConnection,
    ingest_batch_ids: list[str],
    *,
    report_dates: list[object] | None = None,
) -> None:
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
    if not report_dates:
        return
    placeholders = ",".join(["?::date"] * len(report_dates))
    conn.execute(f"delete from {TYW_TABLE} where report_date in ({placeholders})", list(report_dates))


def _sql_value(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    return value


def replace_zqtz_snapshot_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[dict[str, Any]],
    *,
    ingest_batch_ids: list[str],
    report_dates: list[object] | None = None,
    replace_all_for_report_dates: bool = False,
) -> int:
    if replace_all_for_report_dates and report_dates:
        delete_zqtz_snapshots_for_report_dates(conn, list(report_dates))
    else:
        delete_zqtz_snapshots_for_batches(conn, ingest_batch_ids, report_dates=report_dates)
    if not rows:
        return 0
    conn.executemany(
        f"""
        insert into {ZQTZ_TABLE} values (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
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
            )
            for r in rows
        ],
    )
    return len(rows)


def replace_tyw_snapshot_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[dict[str, Any]],
    *,
    ingest_batch_ids: list[str],
    report_dates: list[object] | None = None,
    replace_all_for_report_dates: bool = False,
) -> int:
    if replace_all_for_report_dates and report_dates:
        delete_tyw_snapshots_for_report_dates(conn, list(report_dates))
    else:
        delete_tyw_snapshots_for_batches(conn, ingest_batch_ids, report_dates=report_dates)
    if not rows:
        return 0
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
        row["portfolio_name"],
        row["cost_center"],
        row["currency_code"],
    )


def tyw_grain_key(row: dict[str, Any]) -> tuple[object, ...]:
    return (row["report_date"], row["position_id"])


def merge_tyw_rows_by_grain(rows_in_order: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[object, ...], dict[str, Any]] = {}
    weighted_rate_num: dict[tuple[object, ...], Decimal] = {}

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
            principal = Decimal(str(row.get("principal_native") or 0))
            rate = row.get("funding_cost_rate")
            weighted_rate_num[key] = principal * Decimal(str(rate or 0)) if rate not in (None, "") else Decimal("0")
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

        principal = Decimal(str(row.get("principal_native") or 0))
        rate = row.get("funding_cost_rate")
        if rate not in (None, ""):
            weighted_rate_num[key] += principal * Decimal(str(rate))

    for key, row in merged.items():
        principal = Decimal(str(row.get("principal_native") or 0))
        if principal > 0:
            row["funding_cost_rate"] = weighted_rate_num[key] / principal if weighted_rate_num[key] != Decimal("0") else row.get("funding_cost_rate")

    return list(merged.values())


def merge_rows_by_grain(
    rows_in_order: list[dict[str, Any]],
    grain_fn,
) -> list[dict[str, Any]]:
    merged: dict[tuple[object, ...], dict[str, Any]] = {}
    for row in rows_in_order:
        merged[grain_fn(row)] = row
    return list(merged.values())
