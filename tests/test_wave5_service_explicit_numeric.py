from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATHS = [
    ROOT / "backend" / "app" / "services" / "bond_analytics_service.py",
    ROOT / "backend" / "app" / "services" / "cashflow_projection_service.py",
    ROOT / "backend" / "app" / "services" / "liability_analytics_service.py",
    ROOT / "backend" / "app" / "services" / "risk_tensor_service.py",
    ROOT / "backend" / "app" / "services" / "pnl_bridge_service.py",
]


def test_wave5_services_route_numeric_promotion_through_shared_helper() -> None:
    for path in SERVICE_PATHS:
        src = path.read_text(encoding="utf-8")
        assert "backend.app.services.explicit_numeric" in src, f"{path} missing shared Numeric helper import"


def test_cashflow_projection_service_promotes_nested_numeric_dicts(tmp_path, monkeypatch) -> None:
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
    result = payload["result"]

    assert isinstance(result["duration_gap"], dict)
    assert isinstance(result["monthly_buckets"][0]["asset_inflow"], dict)
    assert isinstance(result["monthly_buckets"][0]["net_cashflow"], dict)
    assert isinstance(result["top_maturing_assets_12m"][0]["face_value"], dict)
    assert isinstance(result["top_maturing_assets_12m"][0]["market_value"], dict)
    get_settings.cache_clear()
