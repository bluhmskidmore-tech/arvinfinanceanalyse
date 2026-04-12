from __future__ import annotations

from decimal import Decimal

import duckdb

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import REPORT_DATE, _seed_bond_snapshot_rows
from tests.test_bond_analytics_service import _configure_and_materialize


def _materialize_risk_tensor(duckdb_path, governance_dir):
    task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    task_mod.materialize_risk_tensor_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    return task_mod


def _configure_and_materialize_risk_tensor(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    risk_task_mod = _materialize_risk_tensor(duckdb_path, governance_dir)
    return duckdb_path, governance_dir, risk_task_mod


def _configure_and_materialize_degraded_snapshot(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.degraded.duckdb"
    governance_dir = tmp_path / "governance.degraded"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set maturity_date = ?
            where report_date = ?
              and instrument_code = 'CB-001'
            """,
            ["2048-03-31", REPORT_DATE],
        )
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set maturity_date = null
            where report_date = ?
              and instrument_code = 'TB-001'
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()

    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    bond_task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    _materialize_risk_tensor(duckdb_path, governance_dir)
    return duckdb_path, governance_dir, bond_task_mod


def test_risk_tensor_service_returns_formal_envelope_with_lineage(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    payload = service_mod.risk_tensor_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date=REPORT_DATE,
    )

    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["scenario_flag"] is False
    assert payload["result_meta"]["result_kind"] == "risk.tensor"
    assert payload["result_meta"]["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert payload["result_meta"]["rule_version"] == "rv_risk_tensor_formal_materialize_v1"
    assert payload["result_meta"]["cache_version"] == "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v1"
    assert payload["result_meta"]["quality_flag"] == "ok"

    result = payload["result"]
    assert result["report_date"] == REPORT_DATE
    assert result["bond_count"] == 3
    assert result["quality_flag"] == "ok"
    assert result["warnings"] == []
    assert result["total_market_value"] == "429.00000000"
    assert result["liquidity_gap_30d"] == "0.00000000"
    assert result["liquidity_gap_90d"] == "0.00000000"
    assert result["issuer_top5_weight"] == "1.00000000"
    assert isinstance(result["portfolio_dv01"], str)
    assert isinstance(result["portfolio_convexity"], str)
    assert result["portfolio_dv01"].count(".") == 1
    assert len(result["portfolio_dv01"].split(".")[1]) == 8
    assert (
        Decimal(result["krd_1y"])
        + Decimal(result["krd_3y"])
        + Decimal(result["krd_5y"])
        + Decimal(result["krd_7y"])
        + Decimal(result["krd_10y"])
        + Decimal(result["krd_30y"])
    ) == Decimal(result["portfolio_dv01"])
    assert Decimal(result["cs01"]) > Decimal("0")
    assert Decimal(result["portfolio_convexity"]) > Decimal("0")

    get_settings.cache_clear()


def test_risk_tensor_service_returns_404_when_report_date_has_no_upstream_or_downstream_artifact(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    try:
        service_mod.risk_tensor_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date=REPORT_DATE,
        )
    except ValueError as exc:
        assert str(exc) == f"No risk tensor data found for report_date={REPORT_DATE}."
    else:
        raise AssertionError("Expected ValueError for absent risk tensor artifacts")

    get_settings.cache_clear()


def test_risk_tensor_service_fails_when_upstream_exists_but_downstream_fact_is_missing(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    try:
        service_mod.risk_tensor_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date=REPORT_DATE,
        )
    except RuntimeError as exc:
        assert "Risk tensor fact missing" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing downstream risk tensor fact")

    get_settings.cache_clear()


def test_risk_tensor_service_fails_when_downstream_fact_is_stale_against_newer_upstream_lineage(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set source_version = ?
            where report_date = ?
              and instrument_code = 'CB-001'
            """,
            ["sv_bond_snap_2", REPORT_DATE],
        )
    finally:
        conn.close()

    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    bond_task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    try:
        service_mod.risk_tensor_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date=REPORT_DATE,
        )
    except RuntimeError as exc:
        assert "Risk tensor stale against bond analytics lineage" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for stale downstream risk tensor fact")

    get_settings.cache_clear()


def test_risk_tensor_service_returns_non_empty_degraded_tensor_when_materialized_snapshot_rows_are_partial(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_degraded_snapshot(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    payload = service_mod.risk_tensor_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date=REPORT_DATE,
    )

    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["source_version"] == "sv_risk_tensor__sv_bond_snap_1"

    result = payload["result"]
    assert result["bond_count"] == 3
    assert result["quality_flag"] == "warning"
    assert Decimal(result["portfolio_dv01"]) > Decimal("0")
    assert any("Unsupported tenor buckets" in warning for warning in result["warnings"])
    assert any("without maturity_date" in warning for warning in result["warnings"])

    get_settings.cache_clear()
