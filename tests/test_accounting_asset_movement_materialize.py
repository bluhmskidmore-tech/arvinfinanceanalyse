from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import json

import duckdb
import pytest

from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)

import backend.app.tasks.accounting_asset_movement as movement_task
from backend.app.tasks.accounting_asset_movement import (
    AccountingAssetMovementSourceMissingError,
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
                ("2026-02-28", "FVTPL", "asset", "CNY", "999", "999", "sv-zqtz-cny", "rv-balance-cny"),
                ("2026-02-28", "AC", "asset", "CNY", "999", "999", "sv-zqtz-cny", "rv-balance-cny"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "999", "999", "sv-zqtz-cny", "rv-balance-cny"),
            ],
        )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-02-28", "14101010001", "CNX", "TPL", "100", "110", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14201010001", "CNX", "AC bond", "200", "220", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14301010001", "CNX", "Voucher bond", "4", "4", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14301010002", "CNX", "Voucher accrued", "1", "1", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14401010001", "CNX", "OCI debt", "70", "80", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14402010001", "CNX", "OCI equity", "90", "99", "0", "0", "0", 28, "sv-gl", "rv-gl"),
            ],
        )

        written = materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-02-28",
            currency_basis="CNX",
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

    assert by_bucket["AC"]["previous_balance"] == Decimal("205.00000000")
    assert by_bucket["AC"]["current_balance"] == Decimal("225.00000000")
    assert by_bucket["AC"]["balance_change"] == Decimal("20.00000000")
    assert by_bucket["AC"]["zqtz_amount"] == Decimal("225.00000000")
    assert by_bucket["AC"]["reconciliation_status"] == "matched"
    assert by_bucket["TPL"]["reconciliation_status"] == "matched"
    assert by_bucket["OCI"]["current_balance"] == Decimal("80.00000000")
    assert by_bucket["OCI"]["reconciliation_status"] == "matched"


def test_accounting_asset_movement_materialize_refuses_missing_control_source():
    conn = duckdb.connect(":memory:")
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

        try:
            materialize_accounting_asset_movement_on_connection(
                conn,
                report_date="2026-02-28",
                currency_basis="CNX",
            )
        except AccountingAssetMovementSourceMissingError:
            pass
        else:
            raise AssertionError("expected missing source rows to fail closed")

        row_count = conn.execute(
            "select count(*) from fact_accounting_asset_movement_monthly"
        ).fetchone()[0]
    finally:
        conn.close()

    assert row_count == 0


def test_task_owned_refresh_fails_closed_when_cutover_disabled(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_MOVEMENT_REFRESH_VIA_TASK", "0")

    with pytest.raises(RuntimeError, match="disabled"):
        movement_task.refresh_accounting_asset_movement_window.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_dates=["2026-01-31"],
            anchor_report_date="2026-01-31",
            currency_basis="CNX",
        )


def test_task_owned_refresh_writes_governance_runs_and_manifests_for_each_report_date(
    tmp_path,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    report_dates = ["2026-01-31", "2026-02-28"]
    _seed_refresh_sources(duckdb_path, report_dates)

    payload = movement_task.refresh_accounting_asset_movement_window.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_dates=report_dates,
        anchor_report_date="2026-02-28",
        currency_basis="CNX",
        product_category_refreshed_dates=["2026-01-31"],
        formal_balance_refreshed_dates=["2026-02-28"],
    )

    assert payload["status"] == "completed"
    assert payload["report_date"] == "2026-02-28"
    assert payload["job_name"] == "accounting_asset_movement_refresh"
    assert payload["movement_refreshed_dates"] == report_dates
    assert payload["payloads_by_date"]["2026-02-28"]["row_count"] == 3

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select cast(report_date as varchar), count(*)
            from fact_accounting_asset_movement_monthly
            group by 1
            order by 1
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("2026-01-31", 3), ("2026-02-28", 3)]

    governance_repo = GovernanceRepository(base_dir=governance_dir)
    build_runs = [
        row
        for row in governance_repo.read_all(CACHE_BUILD_RUN_STREAM)
        if row.get("run_id") == payload["run_id"]
    ]
    manifests = [
        row
        for row in governance_repo.read_all(CACHE_MANIFEST_STREAM)
        if row.get("run_id") == payload["run_id"]
    ]

    assert [row["status"] for row in build_runs] == ["queued", "running", "completed"]
    assert [row["job_name"] for row in build_runs] == [
        "accounting_asset_movement_refresh",
        "accounting_asset_movement_refresh",
        "accounting_asset_movement_refresh",
    ]
    assert sorted(row["report_date"] for row in manifests) == report_dates
    assert all(row["cache_key"] == movement_task.CACHE_KEY for row in manifests)
    assert all(row["cache_version"] == movement_task.CACHE_VERSION for row in manifests)
    assert all(row["fact_tables"] == ["fact_accounting_asset_movement_monthly"] for row in manifests)
    assert all(row["rule_version"] == movement_task.RULE_VERSION for row in manifests)
    assert manifests[0]["lineage"]["movement_refreshed_dates"] == report_dates
    assert manifests[0]["lineage"]["product_category_refreshed_dates"] == ["2026-01-31"]
    assert manifests[0]["lineage"]["formal_balance_refreshed_dates"] == ["2026-02-28"]


def test_task_owned_refresh_rolls_back_all_target_dates_and_writes_failed_run_only(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    report_dates = ["2026-01-31", "2026-02-28"]
    _seed_refresh_sources(duckdb_path, report_dates)

    original_materialize = movement_task.materialize_accounting_asset_movement_on_connection

    def fail_on_second_date(conn, *, report_date: str, currency_basis: str = "CNX"):
        if report_date == "2026-02-28":
            raise RuntimeError("movement window exploded")
        return original_materialize(
            conn,
            report_date=report_date,
            currency_basis=currency_basis,
        )

    monkeypatch.setattr(
        movement_task,
        "materialize_accounting_asset_movement_on_connection",
        fail_on_second_date,
    )

    with pytest.raises(RuntimeError, match="movement window exploded"):
        movement_task.refresh_accounting_asset_movement_window.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_dates=report_dates,
            anchor_report_date="2026-02-28",
            currency_basis="CNX",
        )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        table_exists = conn.execute(
            """
            select count(*)
            from information_schema.tables
            where table_name = 'fact_accounting_asset_movement_monthly'
            """
        ).fetchone()[0]
        row_count = (
            conn.execute(
                """
                select count(*)
                from fact_accounting_asset_movement_monthly
                where cast(report_date as varchar) in ('2026-01-31', '2026-02-28')
                """
            ).fetchone()[0]
            if table_exists
            else 0
        )
    finally:
        conn.close()

    assert row_count == 0

    governance_repo = GovernanceRepository(base_dir=governance_dir)
    build_runs = governance_repo.read_all(CACHE_BUILD_RUN_STREAM)
    manifests = governance_repo.read_all(CACHE_MANIFEST_STREAM)
    assert [row["status"] for row in build_runs] == ["queued", "running", "failed"]
    assert build_runs[-1]["error_message"] == "movement window exploded"
    assert manifests == []


def test_task_owned_refresh_marks_lock_failure_without_success_manifest(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_refresh_sources(duckdb_path, ["2026-02-28"])

    def fail_lock(*_args, **_kwargs):
        raise TimeoutError("Timed out acquiring lock lock:duckdb:accounting-asset-movement")

    monkeypatch.setattr(movement_task, "acquire_lock", fail_lock)

    with pytest.raises(TimeoutError, match="Timed out acquiring lock"):
        movement_task.refresh_accounting_asset_movement_window.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_dates=["2026-02-28"],
            anchor_report_date="2026-02-28",
            currency_basis="CNX",
        )

    governance_repo = GovernanceRepository(base_dir=governance_dir)
    build_runs = governance_repo.read_all(CACHE_BUILD_RUN_STREAM)
    manifests = governance_repo.read_all(CACHE_MANIFEST_STREAM)
    assert [row["status"] for row in build_runs] == ["queued", "running", "failed"]
    assert "Timed out acquiring lock" in str(build_runs[-1]["error_message"])
    assert manifests == []


def _seed_refresh_sources(duckdb_path: Path, report_dates: list[str]) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
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
        rows: list[tuple[object, ...]] = []
        for report_date in report_dates:
            rows.extend(
                [
                    (
                        report_date,
                        "14101010001",
                        "CNX",
                        "TPL",
                        "100",
                        "110",
                        "0",
                        "0",
                        "0",
                        28,
                        f"sv-gl-{report_date}",
                        f"rv-gl-{report_date}",
                    ),
                    (
                        report_date,
                        "14201010001",
                        "CNX",
                        "AC bond",
                        "200",
                        "220",
                        "0",
                        "0",
                        "0",
                        28,
                        f"sv-gl-{report_date}",
                        f"rv-gl-{report_date}",
                    ),
                    (
                        report_date,
                        "14301010001",
                        "CNX",
                        "Voucher bond",
                        "4",
                        "4",
                        "0",
                        "0",
                        "0",
                        28,
                        f"sv-gl-{report_date}",
                        f"rv-gl-{report_date}",
                    ),
                    (
                        report_date,
                        "14301010002",
                        "CNX",
                        "Voucher accrued",
                        "1",
                        "1",
                        "0",
                        "0",
                        "0",
                        28,
                        f"sv-gl-{report_date}",
                        f"rv-gl-{report_date}",
                    ),
                    (
                        report_date,
                        "14401010001",
                        "CNX",
                        "OCI debt",
                        "70",
                        "80",
                        "0",
                        "0",
                        "0",
                        28,
                        f"sv-gl-{report_date}",
                        f"rv-gl-{report_date}",
                    ),
                ]
            )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        conn.close()
