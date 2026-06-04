from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.action_attribution import bond_analytics_action_line_payload


def test_bond_analytics_action_line_payload_maps_service_row_to_core_input() -> None:
    payload = bond_analytics_action_line_payload(
        {
            "instrument_code": "BOND-001",
            "portfolio_name": "Portfolio A",
            "cost_center": "Desk 7",
            "market_value": Decimal("100.50"),
            "modified_duration": Decimal("3.25"),
            "asset_class_std": "OCI",
            "accounting_class": "TPL",
        }
    )

    assert payload == {
        "bond_code": "BOND-001",
        "book_id": "Portfolio A::Desk 7",
        "market_value": Decimal("100.50"),
        "modified_duration": Decimal("3.25"),
        "asset_class": "OCI",
    }


def test_bond_analytics_action_line_payload_falls_back_to_accounting_class() -> None:
    payload = bond_analytics_action_line_payload(
        {
            "instrument_code": "BOND-002",
            "market_value": Decimal("80"),
            "modified_duration": Decimal("2"),
            "accounting_class": "AC",
        }
    )

    assert payload["book_id"] == "::"
    assert payload["asset_class"] == "AC"
