from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import duckdb

from backend.app.services.accounting_asset_movement_service import (
    accounting_asset_movement_dates_envelope,
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
    business_month = result["business_trend_months"][0]
    assert business_month["report_date"] == "2026-02-28"
    business_rows = {row["row_key"]: row for row in business_month["rows"]}
    assert Decimal(business_rows["asset_interbank_lending"]["current_balance"]) == Decimal("80.00000000")
    assert Decimal(business_rows["asset_reverse_repo"]["current_balance"]) == Decimal("90.00000000")
    assert Decimal(business_rows["asset_interbank_current_deposit"]["current_balance"]) == Decimal("35.00000000")
    assert Decimal(business_rows["asset_domestic_interbank_term_deposit"]["current_balance"]) == Decimal("45.00000000")
    assert Decimal(business_rows["asset_overseas_interbank_term_deposit"]["current_balance"]) == Decimal("25.00000000")
    assert Decimal(business_rows["asset_zqtz_interbank_cd"]["current_balance"]) == Decimal("18.00000000")
    assert business_rows["asset_zqtz_interbank_cd"]["source_kind"] == "zqtz"
    assert Decimal(business_rows["liability_interbank_deposits"]["current_balance"]) == Decimal("-90.00000000")
    assert Decimal(business_rows["liability_interbank_borrowings"]["current_balance"]) == Decimal("-35.00000000")
    assert Decimal(business_rows["liability_repo"]["current_balance"]) == Decimal("-95.00000000")
    assert Decimal(business_rows["liability_interbank_cd"]["current_balance"]) == Decimal("-40.00000000")
    assert Decimal(business_month["asset_balance_total"]) == Decimal("293.00000000")
    assert Decimal(business_month["liability_balance_total"]) == Decimal("-260.00000000")
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
        "rv-gl",
        "rv-gl-prior",
        "rv-zqtz",
        "rv-zqtz-prior",
    }
    assert envelope["result_meta"]["evidence_rows"] == 26


def test_balance_movement_analysis_service_uses_cnx_diagnostic_and_ignores_cny_noise():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    _seed_source_tables_and_materialize(duckdb_path)

    envelope = accounting_asset_movement_envelope(
        str(duckdb_path),
        report_date="2026-02-28",
        currency_basis="CNX",
    )

    result = envelope["result"]
    by_bucket = {row["basis_bucket"]: row for row in result["rows"]}
    assert Decimal(by_bucket["TPL"]["current_balance"]) == Decimal("110.00000000")
    assert Decimal(by_bucket["TPL"]["zqtz_amount"]) == Decimal("110.00000000")
    assert Decimal(by_bucket["TPL"]["reconciliation_diff"]) == Decimal("0E-8")
    assert by_bucket["TPL"]["reconciliation_status"] == "matched"
    assert envelope["result_meta"]["quality_flag"] == "ok"


def test_balance_movement_dates_only_advertise_materialized_read_model_dates():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table product_category_pnl_canonical_fact (
              report_date varchar,
              account_code varchar,
              currency varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date varchar,
              report_month varchar,
              currency_basis varchar,
              sort_order integer,
              basis_bucket varchar,
              previous_balance decimal(24, 8),
              current_balance decimal(24, 8),
              balance_change decimal(24, 8),
              change_pct decimal(24, 8),
              contribution_pct decimal(24, 8),
              zqtz_amount decimal(24, 8),
              gl_amount decimal(24, 8),
              reconciliation_diff decimal(24, 8),
              reconciliation_status varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?)",
            ["2026-02-28", "14101010001", "CNX"],
        )
        conn.execute(
            """
            insert into fact_accounting_asset_movement_monthly values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2026-01-31",
                "2026-01",
                "CNX",
                1,
                "AC",
                "90",
                "100",
                "10",
                "11.11111111",
                "100",
                "100",
                "100",
                "0",
                "matched",
                "sv-read-model",
                "rv-read-model",
            ],
        )
    finally:
        conn.close()

    envelope = accounting_asset_movement_dates_envelope(
        str(duckdb_path),
        currency_basis="CNX",
    )

    assert envelope["result"]["report_dates"] == ["2026-01-31"]
    assert envelope["result_meta"]["tables_used"] == [
        "fact_accounting_asset_movement_monthly"
    ]


def test_balance_movement_dates_source_version_is_currency_scoped():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date varchar,
              report_month varchar,
              currency_basis varchar,
              sort_order integer,
              basis_bucket varchar,
              previous_balance decimal(24, 8),
              current_balance decimal(24, 8),
              balance_change decimal(24, 8),
              change_pct decimal(24, 8),
              contribution_pct decimal(24, 8),
              zqtz_amount decimal(24, 8),
              gl_amount decimal(24, 8),
              reconciliation_diff decimal(24, 8),
              reconciliation_status varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_accounting_asset_movement_monthly values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    "2026-02-28",
                    "2026-02",
                    "CNY",
                    1,
                    "AC",
                    "90",
                    "100",
                    "10",
                    "11.11111111",
                    "100",
                    "100",
                    "100",
                    "0",
                    "matched",
                    "sv-cny-latest",
                    "rv-cny",
                ),
                (
                    "2026-01-31",
                    "2026-01",
                    "CNX",
                    1,
                    "AC",
                    "80",
                    "90",
                    "10",
                    "12.50000000",
                    "100",
                    "90",
                    "90",
                    "0",
                    "matched",
                    "sv-cnx-selected",
                    "rv-cnx",
                ),
            ],
        )
    finally:
        conn.close()

    envelope = accounting_asset_movement_dates_envelope(
        str(duckdb_path),
        currency_basis="CNX",
    )

    assert envelope["result"]["report_dates"] == ["2026-01-31"]
    assert envelope["result_meta"]["source_version"] == "sv-cnx-selected"
    assert envelope["result_meta"]["filters_applied"] == {"currency_basis": "CNX"}


def _seed_source_tables_and_materialize(
    duckdb_path: Path,
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
              bond_type varchar,
              business_type_primary varchar,
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
            "insert into fact_formal_zqtz_balance_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-01-31", "FVTPL", "asset", "CNY", "其他债券", "同业存单", "12", "12", "sv-zqtz-prior", "rv-zqtz-prior"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "其他债券", "同业存单", "18", "18", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "国债", "国债", "999", "999", "sv-zqtz-cny", "rv-balance-cny"),
                ("2026-02-28", "AC", "asset", "CNY", "国债", "国债", "999", "999", "sv-zqtz-cny", "rv-balance-cny"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "国债", "国债", "999", "999", "sv-zqtz-cny", "rv-balance-cny"),
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
                ("2026-01-31", "12001000001", "CNX", "拆放同业", "35", "40", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "12101000001", "CNX", "拆放同业", "8", "10", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14001000001", "CNX", "买入返售", "65", "70", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14004000001", "CNX", "排除买入返售", "999", "999", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14005000001", "CNX", "排除买入返售", "999", "999", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "11401000001", "CNX", "同业存放-活期", "25", "30", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "11501000001", "CNX", "存放同业境内-定期", "35", "40", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "11601000001", "CNX", "存放同业境外-定期", "15", "20", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "23401000001", "CNX", "同业存放", "-45", "-50", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "23501000001", "CNX", "同业存放", "-8", "-10", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "24101000001", "CNX", "同业拆入", "-15", "-20", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "24201000001", "CNX", "同业拆入", "-3", "-5", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "25501000001", "CNX", "卖出回购", "-60", "-70", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "27205000001", "CNX", "同业存单", "-10", "-11", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "27206000001", "CNX", "同业存单", "-8", "-9", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-02-28", "14101010001", "CNX", "TPL", "100", "110", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14201010001", "CNX", "AC bond", "200", "220", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14301010001", "CNX", "Voucher bond", "4", "4", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14301010002", "CNX", "Voucher accrued", "1", "1", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14401010001", "CNX", "OCI debt", "70", "80", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14402010001", "CNX", "OCI equity", "90", "99", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "12001000001", "CNX", "拆放同业", "40", "60", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "12101000001", "CNX", "拆放同业", "10", "20", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14001000001", "CNX", "买入返售", "70", "90", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14004000001", "CNX", "排除买入返售", "999", "999", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14005000001", "CNX", "排除买入返售", "999", "999", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "11401000001", "CNX", "同业存放-活期", "30", "35", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "11501000001", "CNX", "存放同业境内-定期", "40", "45", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "11601000001", "CNX", "存放同业境外-定期", "20", "25", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "23401000001", "CNX", "同业存放", "-50", "-70", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "23501000001", "CNX", "同业存放", "-10", "-20", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "24101000001", "CNX", "同业拆入", "-20", "-25", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "24201000001", "CNX", "同业拆入", "-5", "-10", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "25501000001", "CNX", "卖出回购", "-70", "-95", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "27205000001", "CNX", "同业存单", "-11", "-25", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "27206000001", "CNX", "同业存单", "-9", "-15", "0", "0", "0", 28, "sv-gl", "rv-gl"),
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
