from __future__ import annotations

from datetime import date
from decimal import Decimal

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from backend.app.repositories.yield_curve_repo import FORMAL_FACT_TABLE, ensure_yield_curve_tables
from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import REPORT_DATE, _seed_bond_snapshot_rows


def _seed_curve_rows(duckdb_path: str) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        ensure_yield_curve_tables(conn)
        conn.executemany(
            f"""
            insert into {FORMAL_FACT_TABLE} (
              trade_date, curve_type, tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2026-03-31", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_curve_current", "sv_curve_current", "rv_curve"),
                ("2026-03-31", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_curve_current", "sv_curve_current", "rv_curve"),
                ("2026-03-31", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_curve_current", "sv_curve_current", "rv_curve"),
                ("2026-03-31", "aaa_credit", "1Y", Decimal("4.00"), "choice", "vv_aaa_current", "sv_aaa_current", "rv_curve"),
                ("2026-03-31", "aaa_credit", "2Y", Decimal("5.00"), "choice", "vv_aaa_current", "sv_aaa_current", "rv_curve"),
                ("2026-03-31", "aaa_credit", "3Y", Decimal("6.00"), "choice", "vv_aaa_current", "sv_aaa_current", "rv_curve"),
                ("2026-03-01", "treasury", "1Y", Decimal("1.00"), "choice", "vv_curve_prior", "sv_curve_prior", "rv_curve"),
                ("2026-03-01", "treasury", "2Y", Decimal("2.00"), "choice", "vv_curve_prior", "sv_curve_prior", "rv_curve"),
                ("2026-03-01", "treasury", "3Y", Decimal("3.00"), "choice", "vv_curve_prior", "sv_curve_prior", "rv_curve"),
                ("2026-03-01", "aaa_credit", "1Y", Decimal("2.00"), "choice", "vv_aaa_prior", "sv_aaa_prior", "rv_curve"),
                ("2026-03-01", "aaa_credit", "2Y", Decimal("3.00"), "choice", "vv_aaa_prior", "sv_aaa_prior", "rv_curve"),
                ("2026-03-01", "aaa_credit", "3Y", Decimal("4.00"), "choice", "vv_aaa_prior", "sv_aaa_prior", "rv_curve"),
            ],
        )
    finally:
        conn.close()


def test_return_decomposition_uses_curve_effects_and_merges_lineage(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    _seed_bond_snapshot_rows(str(duckdb_path))
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set maturity_date = ?, ytm_value = ?
            where instrument_code = ?
            """,
            ["2028-03-30", Decimal("0"), "TB-001"],
        )
    finally:
        conn.close()
    _seed_curve_rows(str(duckdb_path))

    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 3, 31), "MoM", "rate", "all")
    result = payload["result"]

    assert Decimal(result["roll_down"]) > Decimal("0")
    assert Decimal(result["rate_effect"]) < Decimal("0")
    assert abs(
        Decimal(result["explained_pnl"])
        - (Decimal(result["carry"]) + Decimal(result["roll_down"]) + Decimal(result["rate_effect"]))
    ) <= Decimal("0.00000001")
    assert "sv_curve_current" in payload["result_meta"]["source_version"]
    assert "sv_curve_prior" in payload["result_meta"]["source_version"]
    assert "akshare" in payload["result_meta"]["source_version"]
    assert "choice" in payload["result_meta"]["source_version"]
    assert "vv_curve_current" in payload["result_meta"]["vendor_version"]
    assert payload["result_meta"].get("fallback_mode", "none") == "none"
    assert payload["result_meta"].get("vendor_status", "ok") == "ok"
    assert any("Phase 3 partial delivery" in warning for warning in result["warnings"])
    get_settings.cache_clear()


def test_return_decomposition_uses_spread_effect_for_credit_rows(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    _seed_bond_snapshot_rows(str(duckdb_path))
    _seed_curve_rows(str(duckdb_path))

    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 3, 31), "MoM", "credit", "all")

    assert Decimal(payload["result"]["spread_effect"]) < Decimal("0")
    assert any(Decimal(row["spread_effect"]) != Decimal("0") for row in payload["result"]["bond_details"])
    get_settings.cache_clear()


def test_credit_spread_migration_uses_curve_spread_when_available(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    _seed_bond_snapshot_rows(str(duckdb_path))
    _seed_curve_rows(str(duckdb_path))

    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_credit_spread_migration(date(2026, 3, 31), "10,25")

    assert Decimal(payload["result"]["weighted_avg_spread"]) > Decimal("0")
    assert payload["result"]["warnings"] == []
    assert "sv_aaa_current" in payload["result_meta"]["source_version"]
    get_settings.cache_clear()


def test_return_decomposition_marks_result_meta_stale_when_aaa_curve_uses_latest_fallback(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    _seed_bond_snapshot_rows(str(duckdb_path))
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
                ("2026-03-31", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
                ("2026-03-31", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
                ("2026-03-31", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
                ("2026-03-01", "treasury", "1Y", Decimal("1.00"), "choice", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
                ("2026-03-01", "treasury", "2Y", Decimal("2.00"), "choice", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
                ("2026-03-01", "treasury", "3Y", Decimal("3.00"), "choice", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
                ("2026-03-30", "aaa_credit", "1Y", Decimal("4.00"), "choice", "vv_aaa_latest", "sv_aaa_latest", "rv_curve"),
                ("2026-03-30", "aaa_credit", "2Y", Decimal("5.00"), "choice", "vv_aaa_latest", "sv_aaa_latest", "rv_curve"),
                ("2026-03-30", "aaa_credit", "3Y", Decimal("6.00"), "choice", "vv_aaa_latest", "sv_aaa_latest", "rv_curve"),
                ("2026-03-01", "aaa_credit", "1Y", Decimal("2.00"), "choice", "vv_aaa_prior", "sv_aaa_prior", "rv_curve"),
                ("2026-03-01", "aaa_credit", "2Y", Decimal("3.00"), "choice", "vv_aaa_prior", "sv_aaa_prior", "rv_curve"),
                ("2026-03-01", "aaa_credit", "3Y", Decimal("4.00"), "choice", "vv_aaa_prior", "sv_aaa_prior", "rv_curve"),
            ],
        )
    finally:
        conn.close()

    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 3, 31), "MoM", "credit", "all")

    assert payload["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert payload["result_meta"]["vendor_status"] == "vendor_stale"
    assert any("latest available aaa_credit curve" in warning for warning in payload["result"]["warnings"])
    get_settings.cache_clear()


def test_credit_spread_migration_marks_result_meta_stale_when_curve_fallback_used(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    _seed_bond_snapshot_rows(str(duckdb_path))
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
                ("2026-03-30", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_treasury_latest", "sv_treasury_latest", "rv_curve"),
                ("2026-03-30", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_treasury_latest", "sv_treasury_latest", "rv_curve"),
                ("2026-03-30", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_treasury_latest", "sv_treasury_latest", "rv_curve"),
                ("2026-03-30", "aaa_credit", "1Y", Decimal("4.00"), "choice", "vv_aaa_latest", "sv_aaa_latest", "rv_curve"),
                ("2026-03-30", "aaa_credit", "2Y", Decimal("5.00"), "choice", "vv_aaa_latest", "sv_aaa_latest", "rv_curve"),
                ("2026-03-30", "aaa_credit", "3Y", Decimal("6.00"), "choice", "vv_aaa_latest", "sv_aaa_latest", "rv_curve"),
            ],
        )
    finally:
        conn.close()

    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_credit_spread_migration(date(2026, 3, 31), "10,25")

    assert payload["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert payload["result_meta"]["vendor_status"] == "vendor_stale"
    get_settings.cache_clear()


def test_return_decomposition_marks_result_meta_unavailable_when_credit_curve_missing(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    _seed_bond_snapshot_rows(str(duckdb_path))
    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 3, 31), "MoM", "credit", "all")

    assert payload["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert payload["result_meta"]["fallback_mode"] == "none"
    get_settings.cache_clear()


def test_credit_spread_migration_marks_result_meta_unavailable_when_curves_missing(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    _seed_bond_snapshot_rows(str(duckdb_path))
    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_credit_spread_migration(date(2026, 3, 31), "10,25")

    assert payload["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert payload["result_meta"]["fallback_mode"] == "none"
    get_settings.cache_clear()


def test_return_decomposition_warns_when_latest_curve_fallback_is_used(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    _seed_bond_snapshot_rows(str(duckdb_path))
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set maturity_date = ?, ytm_value = ?
            where instrument_code = ?
            """,
            ["2028-03-30", Decimal("0"), "TB-001"],
        )
    finally:
        conn.close()
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
                ("2026-03-30", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_latest", "sv_latest", "rv_curve"),
                ("2026-03-30", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_latest", "sv_latest", "rv_curve"),
                ("2026-03-30", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_latest", "sv_latest", "rv_curve"),
                ("2026-03-01", "treasury", "1Y", Decimal("1.00"), "choice", "vv_prior", "sv_prior", "rv_curve"),
                ("2026-03-01", "treasury", "2Y", Decimal("2.00"), "choice", "vv_prior", "sv_prior", "rv_curve"),
                ("2026-03-01", "treasury", "3Y", Decimal("3.00"), "choice", "vv_prior", "sv_prior", "rv_curve"),
            ],
        )
    finally:
        conn.close()

    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 3, 31), "MoM", "rate", "all")

    assert any("latest available treasury curve" in warning for warning in payload["result"]["warnings"])
    assert payload["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert payload["result_meta"]["vendor_status"] == "vendor_stale"
    get_settings.cache_clear()


def test_return_decomposition_does_not_use_future_curve_fallback(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    _seed_bond_snapshot_rows(str(duckdb_path))
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set maturity_date = ?, ytm_value = ?
            where instrument_code = ?
            """,
            ["2028-03-30", Decimal("0"), "TB-001"],
        )
        ensure_yield_curve_tables(conn)
        conn.executemany(
            f"""
            insert into {FORMAL_FACT_TABLE} (
              trade_date, curve_type, tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2026-04-01", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_future", "sv_future", "rv_curve"),
                ("2026-04-01", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_future", "sv_future", "rv_curve"),
                ("2026-04-01", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_future", "sv_future", "rv_curve"),
            ],
        )
    finally:
        conn.close()

    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 3, 31), "MoM", "rate", "all")

    assert Decimal(payload["result"]["roll_down"]) == Decimal("0")
    assert Decimal(payload["result"]["rate_effect"]) == Decimal("0")
    assert any("No treasury curve available" in warning for warning in payload["result"]["warnings"])
    assert "sv_future" not in payload["result_meta"]["source_version"]
    get_settings.cache_clear()


def test_return_decomposition_fails_closed_when_same_day_curve_snapshot_lineage_is_corrupt(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    _seed_bond_snapshot_rows(str(duckdb_path))
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set maturity_date = ?, ytm_value = ?
            where instrument_code = ?
            """,
            ["2028-03-30", Decimal("0"), "TB-001"],
        )
        ensure_yield_curve_tables(conn)
        conn.executemany(
            f"""
            insert into {FORMAL_FACT_TABLE} (
              trade_date, curve_type, tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2026-03-31", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_curve", "sv_curve", "rv_curve"),
                ("2026-03-31", "treasury", "2Y", Decimal("3.00"), "choice", "vv_curve", "sv_curve", "rv_curve"),
                ("2026-03-01", "treasury", "1Y", Decimal("1.00"), "akshare", "vv_prior", "sv_prior", "rv_curve"),
                ("2026-03-01", "treasury", "2Y", Decimal("2.00"), "akshare", "vv_prior", "sv_prior", "rv_curve"),
            ],
        )
    finally:
        conn.close()

    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    with pytest.raises(RuntimeError, match="corrupt|inconsistent|lineage"):
        service_mod.get_return_decomposition(date(2026, 3, 31), "MoM", "rate", "all")
    get_settings.cache_clear()
