from __future__ import annotations

from copy import deepcopy

import pytest

from backend.app.services.macro_toolkit_analysis_service import (
    _crisis_risk_severity,
    _crisis_score_card,
    _gate_capability_results_on_refresh_receipt,
)
from backend.app.services.macro_toolkit_refresh_receipt_service import (
    EXPECTED_SOURCE_VERSION,
    MacroToolkitRefreshReceiptHealth,
)
from backend.app.services.macro_toolkit_route_support import (
    _gate_analysis_conclusion_on_refresh_receipt,
    _gate_primary_signal_on_refresh_receipt,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


def _health(
    *,
    status: str = "blocked",
    ready: bool = False,
    choice_status: str | None = "failed",
    choice_row_count: object = 0,
    choice_latest_date: str | None = "2026-08-24",
    missing_fields: tuple[str, ...] = (),
) -> MacroToolkitRefreshReceiptHealth:
    step_statuses: dict[str, dict[str, object]] = {
        "commodity_daily_ingest": {"status": "success", "row_count": 15},
        "public_cross_asset_headlines": {"status": "success", "row_count": 4},
        "tushare_ncd_shibor": {"status": "success", "row_count": 10},
    }
    if choice_status is not None:
        step_statuses["choice_policy_rate_7d"] = {
            "status": choice_status,
            "row_count": choice_row_count,
        }
    latest_observation_dates = (
        {"EMM00088132": choice_latest_date} if choice_latest_date is not None else {}
    )
    return MacroToolkitRefreshReceiptHealth(
        status=status,
        ready=ready,
        cache_fingerprint=f"test:{status}:{choice_status}:{choice_row_count}",
        generated_at="2026-08-25T01:00:00+00:00",
        run_status="success" if ready else "failed",
        source_version=EXPECTED_SOURCE_VERSION,
        missing_fields=missing_fields,
        warnings=tuple(),
        latest_observation_dates=latest_observation_dates,
        step_statuses=step_statuses,
    )


def _cards() -> list[dict[str, object]]:
    return [
        {
            "key": "monetary_policy_stance",
            "legacy_module": "M7",
            "status": "complete",
            "tone": "negative",
            "score": 72.5,
            "headline": "货币政策偏紧",
            "primary_metric": {"label": "立场得分", "value": 72.5, "unit": ""},
            "evidence": ["DR007 2.10%"],
            "warnings": [],
            "result": {"stance_score": 72.5, "headline": "货币政策偏紧"},
        },
        {
            "key": "yield_curve_shape",
            "legacy_module": "M2",
            "status": "complete",
            "tone": "neutral",
            "score": 35.0,
            "headline": "曲线正常",
            "primary_metric": {"label": "10Y-1Y", "value": 35.0, "unit": "bp"},
            "evidence": ["10Y-1Y 35bp"],
            "warnings": [],
            "result": {"shape": "Normal", "spreads": {"10Y-1Y": 35.0}},
        },
        {
            "key": "crisis_score_cn",
            "legacy_module": "M10",
            "status": "degraded",
            "tone": "negative",
            "score": 3.2,
            "headline": "危机状态",
            "primary_metric": {"label": "Crisis Score", "value": 3.2, "unit": ""},
            "evidence": ["crisis_score=3.2"],
            "warnings": ["一项辅助输入降级"],
            "result": {"crisis_score": 3.2, "regime": "CRISIS"},
        },
        {
            "key": "decision_summary",
            "legacy_module": "Decision",
            "status": "degraded",
            "tone": "negative",
            "score": 34.0,
            "headline": "宏观信号偏谨慎",
            "primary_metric": {"label": "可用模块", "value": 3, "unit": "/3"},
            "evidence": ["M7 货币政策偏紧", "M10 危机状态"],
            "warnings": ["部分模块数据降级或不可用"],
            "result": {"positive_count": 0, "negative_count": 2},
        },
    ]


def _by_key(cards: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(card["key"]): card for card in cards}


def test_choice_failure_blocks_direct_capabilities_and_transitive_decision_only() -> None:
    original = _cards()
    original_snapshot = deepcopy(original)

    gated = _gate_capability_results_on_refresh_receipt(
        original,
        _health(choice_status="failed", choice_row_count=0),
    )

    cards = _by_key(gated)
    for key in ("monetary_policy_stance", "crisis_score_cn"):
        card = cards[key]
        before = _by_key(original_snapshot)[key]
        assert card["status"] == before["status"]
        assert card["result"] == before["result"]
        assert card["evidence"] == before["evidence"]
        assert card["tone"] == "missing"
        assert card["score"] is None
        assert card["primary_metric"] is None
        assert card["headline"] == "依赖未通过，原始计算仅作审阅证据"
        assert card["dependency_gate"] == {
            "status": "blocked",
            "blocked_by": ["choice_policy_rate_7d"],
            "reason_code": "required_refresh_step_not_ready",
        }
        assert any(
            "依赖未通过，原始计算仅作审阅证据" in warning
            for warning in card["warnings"]
        )

    decision = cards["decision_summary"]
    assert decision["status"] == _by_key(original_snapshot)["decision_summary"]["status"]
    assert decision["result"] == _by_key(original_snapshot)["decision_summary"]["result"]
    assert decision["tone"] == "missing"
    assert decision["score"] is None
    assert decision["primary_metric"] is None
    assert decision["dependency_gate"] == {
        "status": "blocked",
        "blocked_by": ["choice_policy_rate_7d"],
        "reason_code": "transitive_dependency_blocked",
    }

    non_choice = cards["yield_curve_shape"]
    assert non_choice is original[1]
    assert non_choice == original_snapshot[1]
    assert "dependency_gate" not in non_choice


def test_choice_step_can_pass_locally_while_page_receipt_remains_blocked() -> None:
    original = _cards()
    health = _health(choice_status="success", choice_row_count=8)

    gated = _gate_capability_results_on_refresh_receipt(original, health)
    cards = _by_key(gated)

    for key in ("monetary_policy_stance", "crisis_score_cn", "decision_summary"):
        before = _by_key(original)[key]
        card = cards[key]
        for presentation_field in ("status", "tone", "score", "headline", "primary_metric"):
            assert card[presentation_field] == before[presentation_field]
        assert "dependency_gate" not in card

    primary = _gate_primary_signal_on_refresh_receipt(
        {"key": "crisis_score_cn", "selection_status": "selected"},
        health,
    )
    warnings: list[str] = []
    conclusion = _gate_analysis_conclusion_on_refresh_receipt(
        {"stance": "偏谨慎", "tone": "negative", "basis": {}},
        warnings,
        health,
    )
    assert primary["selection_status"] == "blocked"
    assert primary["key"] is None
    assert conclusion["tone"] == "missing"


@pytest.mark.parametrize(
    ("health", "reason_code"),
    [
        (_health(status="missing", choice_status=None), "refresh_receipt_missing"),
        (_health(status="invalid", choice_status=None), "refresh_receipt_invalid"),
        (_health(choice_status=None), "required_refresh_step_not_ready"),
        (
            _health(choice_status="success", choice_row_count=8, choice_latest_date=None),
            "latest_observation_missing",
        ),
        (
            _health(
                choice_status="success",
                choice_row_count=8,
                missing_fields=("receipt.source_version",),
            ),
            "refresh_receipt_invalid",
        ),
    ],
)
def test_choice_dependency_reason_codes_are_structural_not_error_text(
    health: MacroToolkitRefreshReceiptHealth,
    reason_code: str,
) -> None:
    gated = _gate_capability_results_on_refresh_receipt(_cards(), health)

    assert _by_key(gated)["monetary_policy_stance"]["dependency_gate"]["reason_code"] == reason_code


def test_dependency_blocked_crisis_cannot_drive_risk_selection_or_signal_presentation() -> None:
    gated = _gate_capability_results_on_refresh_receipt(
        _cards(),
        _health(choice_status="failed", choice_row_count=0),
    )

    assert _crisis_risk_severity(gated) == 0
    crisis_signal = _crisis_score_card(gated)
    assert crisis_signal["tone"] == "missing"
    assert crisis_signal["score"] is None
    assert crisis_signal["stance"] == "依赖未通过，原始计算仅作审阅证据"


def test_ready_receipt_does_not_add_dependency_gate_or_rewrite_cards() -> None:
    original = _cards()

    gated = _gate_capability_results_on_refresh_receipt(
        original,
        _health(status="ready", ready=True, choice_status="success", choice_row_count=8),
    )

    assert gated is original
    assert all("dependency_gate" not in card for card in gated)
