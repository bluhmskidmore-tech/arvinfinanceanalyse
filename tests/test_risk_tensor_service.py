from __future__ import annotations

from decimal import Decimal
from pathlib import Path

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


def _configure_and_materialize_risk_tensor_with_tyw_liability(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fact_formal_tyw_balance_daily (
              report_date varchar,
              position_id varchar,
              product_type varchar,
              position_side varchar,
              counterparty_name varchar,
              account_type varchar,
              special_account_type varchar,
              core_customer_type varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              currency_code varchar,
              principal_amount decimal(24, 8),
              accrued_interest_amount decimal(24, 8),
              funding_cost_rate decimal(18, 8),
              maturity_date varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily (
              report_date, position_id, product_type, position_side, counterparty_name,
              account_type, special_account_type, core_customer_type, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code, principal_amount,
              accrued_interest_amount, funding_cost_rate, maturity_date, source_version,
              rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                REPORT_DATE,
                "TYW-L-1",
                "Interbank",
                "liability",
                "Bank L",
                "",
                "",
                "",
                "H",
                "AC",
                "liability",
                "CNY",
                "CNY",
                "4",
                "0",
                "0",
                "2026-04-10",
                "sv_tyw_liab_1",
                "rv_balance_analysis_formal_materialize_v1",
                "ib-liab-1",
                "trace-liab-1",
            ],
        )
    finally:
        conn.close()

    risk_task_mod = _materialize_risk_tensor(duckdb_path, governance_dir)
    return duckdb_path, governance_dir, risk_task_mod


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
    assert result["asset_cashflow_30d"] == "14.00000000"
    assert result["asset_cashflow_90d"] == "14.00000000"
    assert result["liability_cashflow_30d"] == "0.00000000"
    assert result["liability_cashflow_90d"] == "0.00000000"
    assert result["liquidity_gap_30d"] == "14.00000000"
    assert result["liquidity_gap_90d"] == "14.00000000"
    assert (
        Decimal(result["liquidity_gap_30d"])
        == Decimal(result["asset_cashflow_30d"]) - Decimal(result["liability_cashflow_30d"])
    )
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


def test_risk_tensor_dates_envelope_uses_risk_tensor_manifest_lineage(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    lineage_mod = load_module(
        "backend.app.governance.formal_compute_lineage",
        "backend/app/governance/formal_compute_lineage.py",
    )
    calls: list[dict[str, str]] = []

    def _capture(**kwargs):
        calls.append(kwargs)
        return lineage_mod.resolve_formal_manifest_lineage(**kwargs)

    monkeypatch.setattr(service_mod, "resolve_formal_manifest_lineage", _capture)

    payload = service_mod.risk_tensor_dates_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert len(calls) == 1
    assert calls[0]["cache_key"] == service_mod.CACHE_KEY
    assert Path(str(calls[0]["governance_dir"])).resolve() == Path(str(governance_dir)).resolve()
    assert payload["result_meta"]["result_kind"] == "risk.tensor.dates"
    assert payload["result_meta"]["source_version"]
    assert payload["result"]["report_dates"] == [REPORT_DATE]
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


def test_risk_tensor_service_fails_when_downstream_fact_is_stale_against_newer_tyw_liability_lineage(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor_with_tyw_liability(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_tyw_balance_daily
            set source_version = ?
            where report_date = ?
              and position_id = 'TYW-L-1'
            """,
            ["sv_tyw_liab_2", REPORT_DATE],
        )
    finally:
        conn.close()

    try:
        service_mod.risk_tensor_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date=REPORT_DATE,
        )
    except RuntimeError as exc:
        assert "Risk tensor stale against TYW liability lineage" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for stale TYW liability lineage")

    get_settings.cache_clear()


def test_risk_tensor_service_fails_when_downstream_fact_is_stale_against_newer_tyw_liability_rule_version(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor_with_tyw_liability(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_tyw_balance_daily
            set rule_version = ?
            where report_date = ?
              and position_id = 'TYW-L-1'
            """,
            ["rv_balance_analysis_formal_materialize_v2", REPORT_DATE],
        )
    finally:
        conn.close()

    try:
        service_mod.risk_tensor_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date=REPORT_DATE,
        )
    except RuntimeError as exc:
        assert "Risk tensor stale against TYW liability lineage" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for stale TYW liability rule_version")

    get_settings.cache_clear()
