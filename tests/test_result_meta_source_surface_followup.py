from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import get_args

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_bond_analytics_service import _configure_and_materialize
from tests.test_pnl_api_contract import (
    _append_balance_build_run,
    _append_manifest_override,
    _materialize_three_pnl_dates,
    _seed_pnl_bridge_balance_rows,
)
from tests.test_risk_tensor_service import _configure_and_materialize_risk_tensor


def test_wave5_followup_literals_are_allowed() -> None:
    schema_mod = load_module(
        "backend.app.schemas.result_meta",
        "backend/app/schemas/result_meta.py",
    )

    assert "cashflow" in get_args(schema_mod.SourceSurface)
    assert "pnl_bridge" in get_args(schema_mod.SourceSurface)


def test_balance_analysis_dates_envelope_carries_formal_balance_surface(monkeypatch) -> None:
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    class FakeRepo:
        def __init__(self, duckdb_path: str) -> None:
            self.duckdb_path = duckdb_path

        def list_report_dates(self):
            return ["2025-12-31"]

    monkeypatch.setattr(service_mod, "BalanceAnalysisRepository", FakeRepo)
    monkeypatch.setattr(
        service_mod,
        "resolve_formal_manifest_lineage",
        lambda **_kwargs: {
            "cache_key": service_mod.CACHE_KEY,
            "cache_version": "cv_balance_analysis_test",
            "source_version": "sv_balance_analysis_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_balance_analysis_test",
        },
    )

    payload = service_mod.balance_analysis_dates_envelope(
        duckdb_path="ignored.duckdb",
        governance_dir="ignored-governance",
    )

    assert payload["result_meta"]["source_surface"] == "formal_balance"


def test_liability_yield_payload_carries_formal_liability_surface(monkeypatch) -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service",
        "backend/app/services/liability_analytics_service.py",
    )

    class FakeRepo:
        def __init__(self, duckdb_path: str) -> None:
            self.duckdb_path = duckdb_path

        def resolve_latest_report_date(self):
            return ""

    monkeypatch.setattr(service_mod, "LiabilityAnalyticsRepository", FakeRepo)

    payload = service_mod.liability_yield_metrics_payload(
        duckdb_path="ignored.duckdb",
        report_date=None,
    )

    assert payload["result_meta"]["source_surface"] == "formal_liability"


def test_bond_analytics_dates_envelope_carries_bond_analytics_surface(tmp_path, monkeypatch) -> None:
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.bond_analytics_dates_envelope()

    assert payload["result_meta"]["source_surface"] == "bond_analytics"
    get_settings.cache_clear()


def test_bond_dashboard_dates_envelope_carries_bond_analytics_surface(tmp_path, monkeypatch) -> None:
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_dashboard_service",
        "backend/app/services/bond_dashboard_service.py",
    )

    payload = service_mod.get_bond_dashboard_dates()

    assert payload["result_meta"]["source_surface"] == "bond_analytics"
    get_settings.cache_clear()


def test_risk_tensor_dates_envelope_carries_risk_tensor_surface(tmp_path, monkeypatch) -> None:
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    payload = service_mod.risk_tensor_dates_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["result_meta"]["source_surface"] == "risk_tensor"
    get_settings.cache_clear()


def test_cashflow_projection_envelope_carries_cashflow_surface(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )

    def fake_fetch_bond_rows(self, *, report_date, asset_class="all", accounting_class="all"):
        assert report_date == "2026-01-01"
        return [
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "maturity_date": date(2026, 7, 1),
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0.05"),
                "modified_duration": Decimal("1.5"),
                "years_to_maturity": Decimal("0.5"),
                "interest_mode": "年付",
                "currency_code": "CNY",
                "source_version": "sv_bond_1",
                "rule_version": "rv_bond_1",
            }
        ]

    def fake_fetch_tyw_rows(self, *, report_date, currency_basis="CNY"):
        assert report_date == "2026-01-01"
        return [
            {
                "position_id": "TYW-001",
                "counterparty_name": "Bank A",
                "position_side": "liability",
                "maturity_date": date(2026, 3, 1),
                "principal_amount": Decimal("80"),
                "funding_cost_rate": Decimal("0.03"),
                "currency_code": "CNY",
                "source_version": "sv_tyw_1",
                "rule_version": "rv_tyw_1",
            }
        ]

    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        fake_fetch_bond_rows,
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_tyw_liability_rows",
        fake_fetch_tyw_rows,
    )

    payload = service_mod.get_cashflow_projection(date(2026, 1, 1))

    assert payload["result_meta"]["source_surface"] == "cashflow"
    get_settings.cache_clear()


def test_pnl_bridge_envelope_carries_pnl_bridge_surface(tmp_path, monkeypatch) -> None:
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-current",
        report_date="2025-12-31",
        source_version="sv_balance_current",
        vendor_version="vv_balance",
        rule_version="rv_balance_current",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-prior",
        report_date="2025-10-31",
        source_version="sv_balance_prior",
        vendor_version="vv_balance",
        rule_version="rv_balance_prior",
    )
    service_mod = load_module(
        "backend.app.services.pnl_bridge_service",
        "backend/app/services/pnl_bridge_service.py",
    )

    payload = service_mod.pnl_bridge_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
    )

    assert payload["result_meta"]["source_surface"] == "pnl_bridge"
    get_settings.cache_clear()
