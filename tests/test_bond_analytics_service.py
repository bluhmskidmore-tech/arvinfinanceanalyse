from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import REPORT_DATE, _seed_bond_snapshot_rows


def _configure_and_materialize(tmp_path, monkeypatch):
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
    return duckdb_path, governance_dir, task_mod


def test_bond_analytics_service_returns_empty_warning_without_fact_data(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 3, 31), "MoM", "all", "all")

    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result"]["bond_count"] == 0
    assert "not yet populated" in payload["result"]["warnings"][0]
    get_settings.cache_clear()


def test_bond_analytics_return_decomposition_aggregates_carry_and_buckets(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 3, 31), "MoM", "all", "all")
    result = payload["result"]

    expected_days = Decimal("31")
    expected_carry = (
        Decimal("0.02") * Decimal("100") * expected_days / Decimal("365")
        + Decimal("0.03") * Decimal("200") * expected_days / Decimal("365")
        + Decimal("0.04") * Decimal("150") * expected_days / Decimal("365")
    )

    assert payload["result_meta"]["source_version"] == "sv_bond_snap_1"
    assert payload["result_meta"]["rule_version"] == "rv_bond_analytics_formal_materialize_v1"
    assert result["bond_count"] == 3
    assert result["total_market_value"] == "429.00000000"
    assert Decimal(result["carry"]) == expected_carry.quantize(Decimal("0.00000001"))
    assert result["actual_pnl"] == result["carry"]
    assert result["explained_pnl"] == result["carry"]
    assert {row["asset_class"] for row in result["by_asset_class"]} == {"credit", "rate"}
    assert {row["asset_class"] for row in result["by_accounting_class"]} == {"AC", "OCI", "TPL"}
    assert len(result["bond_details"]) == 3
    assert any("Phase 3" in warning for warning in result["warnings"])
    get_settings.cache_clear()


def test_bond_analytics_benchmark_excess_uses_portfolio_risk_and_warns_for_missing_benchmark(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_benchmark_excess(date(2026, 3, 31), "MoM", "CDB_INDEX")
    result = payload["result"]

    assert Decimal(result["portfolio_duration"]) > Decimal("0")
    assert result["benchmark_duration"] == "0.00000000"
    assert any("Benchmark index data not yet available" in warning for warning in result["warnings"])
    get_settings.cache_clear()


def test_bond_analytics_krd_curve_risk_aggregates_dv01_and_scenarios(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_krd_curve_risk(date(2026, 3, 31), "standard")
    result = payload["result"]

    assert Decimal(result["portfolio_duration"]) > Decimal("0")
    assert Decimal(result["portfolio_modified_duration"]) > Decimal("0")
    assert Decimal(result["portfolio_dv01"]) > Decimal("0")
    assert len(result["krd_buckets"]) == 3
    assert {row["tenor"] for row in result["krd_buckets"]} == {"1Y", "5Y", "10Y"}
    assert len(result["scenarios"]) == len(service_mod.STANDARD_SCENARIOS)
    assert {row["asset_class"] for row in result["by_asset_class"]} == {"credit", "rate"}
    get_settings.cache_clear()


def test_bond_analytics_credit_spread_migration_uses_credit_subset_and_concentration(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_credit_spread_migration(date(2026, 3, 31), "10,25")
    result = payload["result"]

    assert result["credit_bond_count"] == 2
    assert result["credit_market_value"] == "330.00000000"
    assert result["credit_weight"] == "0.76923077"
    assert Decimal(result["spread_dv01"]) > Decimal("0")
    assert result["weighted_avg_spread"] == "0.00000000"
    assert len(result["spread_scenarios"]) == 4
    assert result["oci_credit_exposure"] == "190.00000000"
    assert result["concentration_by_issuer"]["dimension"] == "issuer"
    assert any("Spread level input unavailable" in warning for warning in result["warnings"])
    get_settings.cache_clear()


def test_bond_analytics_accounting_audit_uses_fact_rows(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_accounting_class_audit(date(2026, 3, 31))
    result = payload["result"]

    assert result["total_positions"] == 3
    assert result["distinct_asset_classes"] == 2
    assert result["divergent_asset_classes"] == 0
    assert len(result["rows"]) == 2
    assert result["rows"][0]["asset_class"] in {"信用债", "利率债"}
    get_settings.cache_clear()


def test_bond_analytics_empty_date_uses_empty_lineage_not_latest_manifest(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 4, 30), "MoM", "all", "all")

    assert payload["result_meta"]["source_version"] == "sv_bond_analytics_empty"
    assert payload["result"]["bond_count"] == 0
    get_settings.cache_clear()
