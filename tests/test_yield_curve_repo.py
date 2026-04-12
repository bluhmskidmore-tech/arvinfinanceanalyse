from __future__ import annotations

from decimal import Decimal

import duckdb

from backend.app.repositories.yield_curve_repo import (
    FORMAL_FACT_TABLE,
    YieldCurveRepository,
    ensure_yield_curve_tables,
)
from backend.app.schemas.yield_curve import YieldCurvePoint, YieldCurveSnapshot


def test_fetch_curve_returns_tenor_rate_dict(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    repo = YieldCurveRepository(str(duckdb_path))
    repo.replace_curve_snapshots(
        trade_date="2026-04-10",
        snapshots=[
            YieldCurveSnapshot(
                curve_type="treasury",
                trade_date="2026-04-10",
                points=[
                    YieldCurvePoint("1Y", Decimal("1.10")),
                    YieldCurvePoint("3Y", Decimal("1.30")),
                ],
                vendor_name="akshare",
                vendor_version="vv_curve_1",
                source_version="sv_curve_1",
            )
        ],
        rule_version="rv_curve_repo_test",
    )

    curve = repo.fetch_curve("2026-04-10", "treasury")

    assert curve == {
        "1Y": Decimal("1.10"),
        "3Y": Decimal("1.30"),
    }


def test_fetch_latest_trade_date(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    repo = YieldCurveRepository(str(duckdb_path))
    repo.replace_curve_snapshots(
        trade_date="2026-04-09",
        snapshots=[
            YieldCurveSnapshot(
                curve_type="treasury",
                trade_date="2026-04-09",
                points=[YieldCurvePoint("1Y", Decimal("1.00"))],
                vendor_name="akshare",
                vendor_version="vv_curve_old",
                source_version="sv_curve_old",
            )
        ],
        rule_version="rv_curve_repo_test",
    )
    repo.replace_curve_snapshots(
        trade_date="2026-04-10",
        snapshots=[
            YieldCurveSnapshot(
                curve_type="treasury",
                trade_date="2026-04-10",
                points=[YieldCurvePoint("1Y", Decimal("1.10"))],
                vendor_name="choice",
                vendor_version="vv_curve_new",
                source_version="sv_curve_new",
            )
        ],
        rule_version="rv_curve_repo_test",
    )

    assert repo.fetch_latest_trade_date("treasury") == "2026-04-10"
    assert repo.fetch_latest_trade_date_on_or_before("treasury", "2026-04-08") is None
    assert repo.fetch_latest_trade_date_on_or_before("treasury", "2026-04-09") == "2026-04-09"
    assert repo.fetch_latest_trade_date_on_or_before("treasury", "2026-04-11") == "2026-04-10"
    assert repo.list_trade_dates("treasury") == ["2026-04-10", "2026-04-09"]


def test_empty_table_returns_none(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_yield_curve_tables(conn)
    finally:
        conn.close()
    repo = YieldCurveRepository(str(duckdb_path))

    assert repo.fetch_curve("2026-04-10", "treasury") == {}
    assert repo.fetch_latest_trade_date("treasury") is None
    assert repo.list_trade_dates("treasury") == []


def test_fetch_curve_snapshot_exposes_lineage(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_yield_curve_tables(conn)
        conn.execute(
            f"""
            insert into {FORMAL_FACT_TABLE} (
              trade_date, curve_type, tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ["2026-04-10", "cdb", "5Y", Decimal("1.88"), "choice", "vv_cdb", "sv_cdb", "rv_curve"],
        )
    finally:
        conn.close()

    repo = YieldCurveRepository(str(duckdb_path))
    snapshot = repo.fetch_curve_snapshot("2026-04-10", "cdb")

    assert snapshot is not None
    assert snapshot["curve"] == {"5Y": Decimal("1.88")}
    assert snapshot["vendor_name"] == "choice"
    assert snapshot["vendor_version"] == "vv_cdb"
    assert snapshot["source_version"] == "sv_cdb"
    assert snapshot["rule_version"] == "rv_curve"


def test_fetch_curve_snapshot_rejects_mismatched_lineage_across_tenors(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_yield_curve_tables(conn)
        conn.executemany(
            f"""
            insert into {FORMAL_FACT_TABLE} (
              trade_date, curve_type, tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ["2026-04-10", "treasury", "1Y", Decimal("1.00"), "a", "vv1", "sv1", "rv1"],
                ["2026-04-10", "treasury", "2Y", Decimal("2.00"), "b", "vv1", "sv1", "rv1"],
            ],
        )
    finally:
        conn.close()

    repo = YieldCurveRepository(str(duckdb_path))
    assert repo.fetch_curve_snapshot("2026-04-10", "treasury") is None
