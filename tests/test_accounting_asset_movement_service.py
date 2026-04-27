from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import duckdb

from backend.app.services.accounting_asset_movement_service import (
    accounting_asset_movement_envelope,
)
from backend.app.tasks.accounting_asset_movement import (
    materialize_accounting_asset_movement_on_connection,
)


def test_balance_movement_analysis_service_exposes_gl_control_rows():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    refresh_rows = _seed_source_tables_and_materialize(duckdb_path)
    assert len(refresh_rows) == 3

    envelope = accounting_asset_movement_envelope(
        str(duckdb_path),
        report_date="2026-02-28",
        currency_basis="CNX",
    )
    result = envelope["result"]

    assert result["accounting_controls"] == ["141%", "142%", "143%", "1440101%"]
    assert result["excluded_controls"] == ["144020%"]
    assert Decimal(result["summary"]["current_balance_total"]) == Decimal("415.00000000")
    by_bucket = {row["basis_bucket"]: row for row in result["rows"]}
    assert Decimal(by_bucket["AC"]["current_balance"]) == Decimal("225.00000000")
    assert Decimal(by_bucket["AC"]["current_balance_pct"]).quantize(
        Decimal("0.000001")
    ) == Decimal("54.216867")
    assert Decimal(by_bucket["OCI"]["current_balance"]) == Decimal("80.00000000")
    assert Decimal(by_bucket["TPL"]["current_balance"]) == Decimal("110.00000000")
    assert result["summary"]["matched_bucket_count"] == 3
    assert [month["report_date"] for month in result["trend_months"]] == [
        "2026-02-28",
        "2026-01-31",
    ]
    assert Decimal(result["trend_months"][0]["current_balance_total"]) == Decimal(
        "415.00000000"
    )
    trend_ac = next(
        row for row in result["trend_months"][0]["rows"] if row["basis_bucket"] == "AC"
    )
    assert Decimal(trend_ac["current_balance_pct"]).quantize(
        Decimal("0.000001")
    ) == Decimal("54.216867")
    assert envelope["result_meta"]["quality_flag"] == "ok"
    assert envelope["result_meta"]["result_kind"] == "balance-analysis.movement.detail"
    assert set(envelope["result_meta"]["source_version"].split("__")) == {
        "sv-gl",
        "sv-gl-prior",
        "sv-zqtz",
        "sv-zqtz-prior",
    }
    assert set(envelope["result_meta"]["rule_version"].split("__")) == {
        "rv-balance",
        "rv-balance-prior",
        "rv-gl",
        "rv-gl-prior",
    }
    assert envelope["result_meta"]["evidence_rows"] == 6


def test_balance_movement_analysis_service_keeps_zqtz_gap_out_of_formal_quality():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    _seed_source_tables_and_materialize(
        duckdb_path,
        zqtz_tpl_market_value=Decimal("111"),
    )

    envelope = accounting_asset_movement_envelope(
        str(duckdb_path),
        report_date="2026-02-28",
        currency_basis="CNX",
    )

    result = envelope["result"]
    by_bucket = {row["basis_bucket"]: row for row in result["rows"]}
    assert Decimal(by_bucket["TPL"]["current_balance"]) == Decimal("110.00000000")
    assert Decimal(by_bucket["TPL"]["zqtz_amount"]) == Decimal("111.00000000")
    assert Decimal(by_bucket["TPL"]["reconciliation_diff"]) == Decimal("1.00000000")
    assert by_bucket["TPL"]["reconciliation_status"] == "mismatch"
    assert envelope["result_meta"]["quality_flag"] == "ok"


def _seed_source_tables_and_materialize(
    duckdb_path: Path,
    *,
    zqtz_tpl_market_value: Decimal = Decimal("110"),
) -> list[object]:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
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
                ("2026-01-31", "FVTPL", "asset", "CNY", "100", "100", "sv-zqtz-prior", "rv-balance-prior"),
                ("2026-01-31", "AC", "asset", "CNY", "205", "205", "sv-zqtz-prior", "rv-balance-prior"),
                ("2026-01-31", "FVOCI", "asset", "CNY", "70", "70", "sv-zqtz-prior", "rv-balance-prior"),
                (
                    "2026-02-28",
                    "FVTPL",
                    "asset",
                    "CNY",
                    str(zqtz_tpl_market_value),
                    "100",
                    "sv-zqtz",
                    "rv-balance",
                ),
                ("2026-02-28", "AC", "asset", "CNY", "260", "225", "sv-zqtz", "rv-balance"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "80", "75", "sv-zqtz", "rv-balance"),
            ],
        )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-01-31", "14101010001", "CNX", "TPL", "90", "100", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14201010001", "CNX", "AC bond", "190", "200", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14301010001", "CNX", "Voucher bond", "4", "4", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14301010002", "CNX", "Voucher accrued", "1", "1", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14401010001", "CNX", "OCI debt", "65", "70", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14402010001", "CNX", "OCI equity", "90", "99", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-02-28", "14101010001", "CNX", "TPL", "100", "110", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14201010001", "CNX", "AC bond", "200", "220", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14301010001", "CNX", "Voucher bond", "4", "4", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14301010002", "CNX", "Voucher accrued", "1", "1", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14401010001", "CNX", "OCI debt", "70", "80", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14402010001", "CNX", "OCI equity", "90", "99", "0", "0", "0", 28, "sv-gl", "rv-gl"),
            ],
        )
        materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-01-31",
            currency_basis="CNX",
        )
        return materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-02-28",
            currency_basis="CNX",
        )
    finally:
        conn.close()
