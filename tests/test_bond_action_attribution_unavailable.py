from __future__ import annotations

from datetime import date
from decimal import Decimal

from tests.helpers import load_module


def test_bond_action_attribution_service_returns_explicit_unavailable_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "empty.duckdb"))

    service_module = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_module.get_action_attribution(date(2026, 3, 31), "MoM")

    assert payload["result_meta"]["result_kind"] == "bond_analytics.action_attribution"
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
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


def test_bond_action_attribution_computation_failure_discloses_computation_failed(
    tmp_path, monkeypatch
):
    """计算异常分支不得伪装成"交易数据未接入"：warning 必须是 computation_failed 语义。"""
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "empty.duckdb"))

    service_module = load_module(
        "backend.app.services.bond_analytics_service_action_attr_failure",
        "backend/app/services/bond_analytics_service.py",
    )

    monkeypatch.setattr(
        service_module,
        "_fetch_action_attribution_snapshots",
        lambda *, repo, period_end: ([{"stub": "end-row"}], [], None),
    )
    monkeypatch.setattr(
        service_module,
        "_build_action_attribution_pnl_by_key",
        lambda *_args, **_kwargs: ({}, []),
    )
    monkeypatch.setattr(
        service_module,
        "bond_analytics_action_line_payload",
        lambda row: row,
    )

    def exploding_compute(**_kwargs):
        raise RuntimeError("attribution math blew up")

    monkeypatch.setattr(
        service_module, "compute_action_attribution_bonds", exploding_compute
    )

    payload = service_module.get_action_attribution(date(2026, 3, 31), "MoM")

    assert payload["result_meta"]["result_kind"] == "bond_analytics.action_attribution"
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result"]["status"] == "unavailable"
    assert payload["result"]["total_actions"] == 0
    assert payload["result"]["warnings_detail"] == [
        {
            "code": "bond_action_attribution_computation_failed",
            "level": "error",
            "message": (
                "Action attribution computation failed (RuntimeError); "
                "no attribution result is available for this request. "
                "This is a computation error, not missing trade-record integration; "
                "see server logs for the stack trace."
            ),
        }
    ]
    warnings = payload["result"]["warnings"]
    assert any("computation failed" in warning.lower() for warning in warnings)
    # 计算失败绝不能沿用"until trade records are integrated"的无数据占位文案。
    assert not any("until trade records are integrated" in warning for warning in warnings)
