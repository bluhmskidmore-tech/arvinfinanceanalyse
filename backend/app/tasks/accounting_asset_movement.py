from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb

from backend.app.core_finance.accounting_asset_movement import (
    AccountingAssetMovementRow,
    GlAccountingAssetBalance,
    ZqtzAccountingAssetBalance,
    build_accounting_asset_movement_rows,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.tasks.broker import register_actor_once


RULE_VERSION = "rv_accounting_asset_movement_v1"
CACHE_KEY = "accounting_asset_movement.monthly"


def _materialize_accounting_asset_movement(
    *,
    report_date: str,
    duckdb_path: str | None = None,
    currency_basis: str = "CNY",
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(duckdb_file), read_only=False)
    try:
        conn.execute("begin transaction")
        rows = materialize_accounting_asset_movement_on_connection(
            conn,
            report_date=report_date,
            currency_basis=currency_basis,
        )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise
    finally:
        conn.close()

    source_versions = sorted(
        {
            token
            for row in rows
            for token in row.source_version.split("__")
            if token
        }
    )
    return {
        "status": "completed",
        "cache_key": CACHE_KEY,
        "report_date": report_date,
        "currency_basis": currency_basis,
        "row_count": len(rows),
        "source_version": "__".join(source_versions),
        "rule_version": RULE_VERSION,
    }


materialize_accounting_asset_movement = register_actor_once(
    "materialize_accounting_asset_movement",
    _materialize_accounting_asset_movement,
)


def _ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    apply_pending_migrations_on_connection(conn)


def materialize_accounting_asset_movement_on_connection(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str = "CNY",
) -> list[AccountingAssetMovementRow]:
    parsed_report_date = date.fromisoformat(report_date)
    _ensure_tables(conn)
    zqtz_rows = _load_zqtz_rows(
        conn,
        report_date=report_date,
        currency_basis=currency_basis,
    )
    gl_rows = _load_gl_rows(
        conn,
        report_date=report_date,
        currency_basis=currency_basis,
    )
    rows = build_accounting_asset_movement_rows(
        report_date=parsed_report_date,
        zqtz_rows=zqtz_rows,
        gl_rows=gl_rows,
    )
    conn.execute(
        """
        delete from fact_accounting_asset_movement_monthly
        where report_date = ?
          and currency_basis = ?
        """,
        [report_date, currency_basis],
    )
    _insert_rows(conn, rows, currency_basis=currency_basis)
    return rows


def _load_zqtz_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str,
) -> list[ZqtzAccountingAssetBalance]:
    rows = conn.execute(
        """
        select
          cast(report_date as varchar),
          accounting_basis,
          position_scope,
          currency_basis,
          market_value_amount,
          amortized_cost_amount,
          source_version,
          rule_version
        from fact_formal_zqtz_balance_daily
        where cast(report_date as varchar) = ?
          and currency_basis = ?
          and position_scope = 'asset'
        """,
        [report_date, currency_basis],
    ).fetchall()
    return [
        ZqtzAccountingAssetBalance(
            report_date=date.fromisoformat(str(row[0])),
            accounting_basis=str(row[1]),
            position_scope=str(row[2]),
            currency_basis=str(row[3]),
            market_value_amount=Decimal(str(row[4] or "0")),
            amortized_cost_amount=Decimal(str(row[5] or "0")),
            source_version=str(row[6] or ""),
            rule_version=str(row[7] or ""),
        )
        for row in rows
    ]


def _load_gl_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str,
) -> list[GlAccountingAssetBalance]:
    rows = conn.execute(
        """
        select
          cast(report_date as varchar),
          account_code,
          currency,
          beginning_balance,
          ending_balance,
          source_version,
          rule_version
        from product_category_pnl_canonical_fact
        where cast(report_date as varchar) = ?
          and currency = ?
          and (
            account_code like '141%'
            or account_code like '142%'
            or account_code like '143%'
            or account_code like '144%'
          )
        """,
        [report_date, currency_basis],
    ).fetchall()
    return [
        GlAccountingAssetBalance(
            report_date=date.fromisoformat(str(row[0])),
            account_code=str(row[1]),
            currency_basis=str(row[2]),
            beginning_balance=Decimal(str(row[3] or "0")),
            ending_balance=Decimal(str(row[4] or "0")),
            source_version=str(row[5] or ""),
            rule_version=str(row[6] or ""),
        )
        for row in rows
    ]


def _insert_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[AccountingAssetMovementRow],
    *,
    currency_basis: str,
) -> None:
    for sort_order, row in enumerate(rows, start=1):
        conn.execute(
            """
            insert into fact_accounting_asset_movement_monthly values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                row.report_date.isoformat(),
                row.report_month,
                currency_basis,
                sort_order,
                row.basis_bucket,
                row.previous_balance,
                row.current_balance,
                row.balance_change,
                row.change_pct,
                row.contribution_pct,
                row.zqtz_amount,
                row.gl_amount,
                row.reconciliation_diff,
                row.reconciliation_status,
                row.source_version,
                row.rule_version or RULE_VERSION,
            ],
        )
