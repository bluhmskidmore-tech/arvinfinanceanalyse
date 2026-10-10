from __future__ import annotations

from dataclasses import replace

import pytest

from backend.app.schemas.market_overview import MarketOverviewGate
from backend.app.services import market_overview_service as service
from backend.app.services.macro_toolkit_refresh_receipt_service import MacroToolkitRefreshReceiptHealth

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]


def _health():
    return MacroToolkitRefreshReceiptHealth(
        status="ready", ready=True, cache_fingerprint="ready:test", generated_at=None,
        run_status="success", source_version="test", missing_fields=(), warnings=(),
        latest_observation_dates={},
    )


def _component(result, quality="ok"):
    return service._component_from_envelope(
        "macro_analysis_core", cache_key=None,
        envelope={"result": result, "result_meta": {"quality_flag": quality, "vendor_status": "ok"}},
    )


def test_missing_direction_has_actionable_reason_even_when_aggregate_meta_is_ok():
    gate = service._build_gate(_health(), _component({"conclusion": {
        "stance": "暂不判断", "tone": "missing", "basis": {"directional_coverage": {
            "expected_count": 3, "valid_count": 1, "missing_keys": ["risk_appetite", "credit"],
            "status": "insufficient",
        }},
    }}))
    MarketOverviewGate.model_validate(gate)
    assert gate["level"] == "review"
    assert gate["reason_code"] == "directional_inputs_missing"
    assert "风险偏好、信用" in gate["human_reason"]
    actions = service._build_actions(gate=gate, dates=None, tape=None, crisis=None, news=None)
    action = actions["items"][0]
    assert action["key"] == "gate_review_directional_coverage"
    assert action["route"] == "/macro-toolkit"
    assert "暂不形成" in action["evidence"]["impact"]


def test_stale_stock_and_model_materials_are_distinct_from_directional_inputs():
    result = {
        "choice_stock_refresh": {
            "daily_observation": {"freshness_status": "stale", "latest_trade_date": "2026-08-24"},
            "factor_snapshot": {"freshness_status": "stale", "as_of_date": "2026-08-23"},
        },
        "model_readiness": [{"readiness": "stale"}, {"readiness": "artifact_backed"}],
        "report_bundle": {"warnings": ["Exception: 192.0.2.1 secret path"]},
    }
    gate = service._build_gate(_health(), _component(result, "warning"))
    MarketOverviewGate.model_validate(gate)
    issues = {item["key"]: item for item in gate["issues"]}
    assert "2026-08-24" in issues["stock_daily_observation"]["reason"]
    assert "2026-08-23" in issues["stock_factor_snapshot"]["reason"]
    assert "1 项" in issues["model_artifacts"]["reason"]
    assert "directional_coverage" not in issues
    assert "研究" in issues["research_boundary"]["impact"]
    assert "192.0.2.1" not in str(gate)


def test_recovered_snapshot_clears_issues_and_review_actions():
    gate = service._build_gate(_health(), _component({
        "conclusion": {"basis": {"directional_coverage": {"status": "complete"}}},
        "choice_stock_refresh": {"daily_observation": {"freshness_status": "current"}},
        "model_readiness": [{"readiness": "artifact_backed"}],
    }))
    assert gate["level"] == "ok"
    assert gate["issues"] == []
    assert service._build_actions(gate=gate, dates=None, tape=None, crisis=None, news=None)["items"] == []


@pytest.mark.parametrize("readiness", ["stale", "degraded", "missing_output", "unknown", "registered_only"])
def test_all_production_model_failure_states_have_a_review_item(readiness):
    gate = service._build_gate(_health(), _component({
        "model_readiness": [{"readiness": readiness}],
        "report_bundle": {"warnings": ["研究材料"]},
    }, "warning"))
    assert "model_artifacts" in {item["key"] for item in gate["issues"]}


def test_lagging_stock_inputs_remain_actionable():
    gate = service._build_gate(_health(), _component({
        "choice_stock_refresh": {"daily_observation": {
            "freshness_status": "lagging", "latest_trade_date": "2026-09-03",
        }},
    }))
    assert gate["issues"][0]["key"] == "stock_daily_observation"
    assert "2026-09-03" in gate["human_reason"]


def test_deferred_capabilities_are_not_reported_as_missing():
    gate = service._build_gate(_health(), _component({
        "data_health": {"repair_items": [{"type": "deferred", "key": "capabilities"}]},
        "runtime_status": {"deferred_sections": [{"key": "capabilities"}]},
    }))
    assert gate["level"] == "ok" and gate["issues"] == []


def test_unexplained_warning_remains_visible():
    gate = service._build_gate(_health(), _component({}, "warning"))
    assert gate["level"] == "review"
    assert gate["issues"][0]["key"] == "core_quality"
    assert "未提供更细的原因" in gate["human_reason"]


def test_abandoned_refresh_cannot_retain_a_cached_positive_conclusion():
    health = replace(_health(), status="abandoned", ready=False)
    gate = service._build_gate(health, _component({"conclusion": {"tone": "positive", "summary": "旧结论"}}))
    assert gate["reason_code"] == "refresh_receipt_abandoned"
    assert gate["conclusion"]["tone"] == "missing"
    assert "旧结论" not in str(gate)


def test_source_unavailable_action_does_not_claim_collection_failed():
    gate = service._build_gate(_health(), None)
    actions = service._build_actions(gate=gate, dates=None, tape=None, crisis=None, news=None)
    assert gate["conclusion"]["tone"] == "missing"
    assert actions["items"][0]["label"] == "恢复核心宏观分析"
