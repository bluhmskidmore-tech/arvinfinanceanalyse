from __future__ import annotations

from datetime import date
from decimal import Decimal

from tests.helpers import load_module


def test_bond_action_attribution_service_returns_explicit_unavailable_contract():
    service_module = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_module.get_action_attribution(date(2026, 3, 31), "MoM")

    assert payload["result_meta"]["result_kind"] == "bond_analytics.action_attribution"
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["scenario_flag"] is False
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result"]["status"] == "unavailable"
    assert payload["result"]["total_actions"] == 0
    tp = payload["result"]["total_pnl_from_actions"]
    if isinstance(tp, str):
        assert Decimal(tp) == 0
    else:
        assert tp["raw"] == 0.0
        assert tp["unit"] == "yuan"
    assert payload["result"]["available_components"] == []
    assert payload["result"]["missing_inputs"] == [
        "trade_level_action_facts",
        "trade_execution_metadata",
    ]
    assert payload["result"]["blocked_components"] == [
        "realized_trading",
        "action_attribution",
    ]
    assert any("unavailable" in warning.lower() for warning in payload["result"]["warnings"])
    assert payload["result"]["warnings_detail"] == [
        {
            "code": "bond_action_placeholder",
            "level": "warning",
            "message": (
                "Governed trade-action facts unavailable; returning unavailable action-attribution contract "
                "until trade records are integrated."
            ),
        }
    ]
    assert not any("ready" in warning.lower() for warning in payload["result"]["warnings"])
    assert not any("placeholder" in warning.lower() for warning in payload["result"]["warnings"])
    assert not any("fabricated" in warning.lower() for warning in payload["result"]["warnings"])
