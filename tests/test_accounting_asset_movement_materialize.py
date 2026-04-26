from __future__ import annotations

from decimal import Decimal

import duckdb

from backend.app.tasks.accounting_asset_movement import (
    materialize_accounting_asset_movement_on_connection,
)


def test_accounting_asset_movement_materialize_writes_monthly_reconciliation_rows():
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              market_value_amount decimal(24, 8),
              amortized_cost_amount decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            create table product_category_pnl_canonical_fact (
              report_date varchar,
              account_code varchar,
              currency varchar,
              account_name varchar,
              beginning_balance decimal(24, 8),
              ending_balance decimal(24, 8),
              monthly_pnl decimal(24, 8),
              daily_avg_balance decimal(24, 8),
              annual_avg_balance decimal(24, 8),
              days_in_period integer,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_zqtz_balance_daily values (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-02-28", "FVTPL", "asset", "CNY", "110", "100", "sv-zqtz", "rv-balance"),
                ("2026-02-28", "AC", "asset", "CNY", "260", "265", "sv-zqtz", "rv-balance"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "80", "75", "sv-zqtz", "rv-balance"),
            ],
        )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-02-28", "14101010001", "CNY", "TPL", "100", "110", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14201010001", "CNY", "AC bond", "200", "220", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14301040001", "CNY", "AC other", "50", "45", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14401010001", "CNY", "OCI", "70", "80", "0", "0", "0", 28, "sv-gl", "rv-gl"),
            ],
        )

        written = materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-02-28",
            currency_basis="CNY",
        )
        rows = conn.execute(
            """
            select basis_bucket, previous_balance, current_balance, balance_change,
                   zqtz_amount, reconciliation_status
            from fact_accounting_asset_movement_monthly
            where report_date = '2026-02-28'
            order by sort_order
            """
        ).fetchall()
    finally:
        conn.close()

    assert len(written) == 3
    by_bucket = {
        row[0]: {
            "previous_balance": row[1],
            "current_balance": row[2],
            "balance_change": row[3],
            "zqtz_amount": row[4],
            "reconciliation_status": row[5],
        }
        for row in rows
    }

    assert by_bucket["AC"]["previous_balance"] == Decimal("250.00000000")
    assert by_bucket["AC"]["current_balance"] == Decimal("265.00000000")
    assert by_bucket["AC"]["balance_change"] == Decimal("15.00000000")
    assert by_bucket["AC"]["zqtz_amount"] == Decimal("265.00000000")
    assert by_bucket["AC"]["reconciliation_status"] == "matched"
    assert by_bucket["TPL"]["reconciliation_status"] == "matched"
    assert by_bucket["OCI"]["reconciliation_status"] == "matched"
