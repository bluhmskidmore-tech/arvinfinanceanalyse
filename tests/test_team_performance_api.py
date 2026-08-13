"""团队绩效考核底稿（2025 静态工作簿）：service 汇总 + 路由契约。

- service 层：底稿数值抽查（与前端迁移前 `ASSESSMENT_CENTERS_2025` 一字不差）、
  汇总分与迁移前前端算法（按底稿行序浮点累加）逐位一致、envelope 口径标注。
- 路由层：注册进 app、403（无读权限）、200（envelope 形状）。
"""
from __future__ import annotations

import uuid

import pytest

from backend.app.services.team_performance_service import (
    ASSESSMENT_INDICATORS_2025,
    CENTER_PNL_MAPPINGS_2025,
    assessment_workbook_envelope,
    build_assessment_workbook_payload,
)
from tests.helpers import load_module


def _legacy_frontend_center_totals() -> dict[str, tuple[float, float]]:
    """迁移前前端算法的独立重算：按底稿行序 reduce，返回 {center_id: (weight, score)}。"""
    totals: dict[str, tuple[float, float]] = {}
    order: list[str] = []
    for item in ASSESSMENT_INDICATORS_2025:
        center_id = str(item["center_id"])
        if center_id not in order:
            order.append(center_id)
        weight, score = totals.get(center_id, (0.0, 0.0))
        raw_score = item["score"]
        totals[center_id] = (
            weight + float(item["weight"]),  # type: ignore[arg-type]
            score + (float(raw_score) if raw_score is not None else 0.0),  # type: ignore[arg-type]
        )
    return {center_id: totals[center_id] for center_id in order}


def test_workbook_indicator_values_match_migrated_source_rows():
    payload = build_assessment_workbook_payload()

    by_center = {center.center_id: center for center in payload.centers}
    assert list(by_center) == [
        "product-market",
        "self-investment",
        "interbank-finance",
        "money-trading",
        "bond-trading",
        "fx-derivatives",
        "customer-business",
        "jinan-branch",
    ]
    assert sum(len(center.indicators) for center in payload.centers) == 34

    product_market_first = by_center["product-market"].indicators[0]
    assert product_market_first.metric == "金融投资营业收入"
    assert product_market_first.score == 11.0314285714
    assert product_market_first.source_row == 3

    underwriting = next(
        item
        for item in by_center["customer-business"].indicators
        if item.metric == "利率债承销手续费收入"
    )
    assert underwriting.score == 18.6562203229
    assert underwriting.block_label == "利率债承分销室"

    interbank_scale = next(
        item
        for item in by_center["interbank-finance"].indicators
        if item.source_row == 21
    )
    assert interbank_scale.score == 6.89125

    assert by_center["jinan-branch"].weight_total == 40.0


def test_workbook_summaries_match_legacy_frontend_reduction():
    payload = build_assessment_workbook_payload()
    legacy = _legacy_frontend_center_totals()

    assert [center.center_id for center in payload.centers] == list(legacy)
    for center in payload.centers:
        legacy_weight, legacy_score = legacy[center.center_id]
        assert center.weight_total == legacy_weight
        assert center.workbook_score == legacy_score
        assert center.has_pending_score is False
        assert center.score_rate == legacy_score / legacy_weight

    legacy_total = 0.0
    for center_id in legacy:
        legacy_total += legacy[center_id][1]
    assert payload.total_workbook_score == legacy_total
    # 页面首屏锚点：迁移前 TeamPerformancePage.test.tsx 断言 toFixed(2) == "409.28"。
    assert f"{payload.total_workbook_score:.2f}" == "409.28"
    assert payload.total_center_count == 8

    interbank = next(c for c in payload.centers if c.center_id == "interbank-finance")
    assert interbank.workbook_score == pytest.approx(53.89125)
    assert interbank.weight_total == 45.0


def test_workbook_mappings_migrated_verbatim():
    payload = build_assessment_workbook_payload()

    assert len(payload.mappings) == len(CENTER_PNL_MAPPINGS_2025) == 31
    jinan = [m for m in payload.mappings if m.center_id == "jinan-branch"]
    assert [m.confidence for m in jinan] == ["linked", "linked"]
    assert jinan[0].row_id == "interbank_lending_assets"
    assert jinan[0].scale_field == "cny_scale"
    fx_derivatives_note = next(
        m for m in payload.mappings if m.center_id == "fx-derivatives" and m.row_id == "derivatives"
    )
    assert fx_derivatives_note.note == "汇兑损益及衍生条目按业务净收入展示。"


def test_workbook_envelope_declares_static_non_formal_caliber():
    envelope = assessment_workbook_envelope()

    meta = envelope["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["result_kind"] == "team_performance.assessment_workbook"
    assert meta["quality_flag"] == "ok"
    assert meta["as_of_date"] == "2025-12-31"
    assert meta["filters_applied"] == {"assessment_year": 2025}
    assert meta["evidence_rows"] == 34

    result = envelope["result"]
    assert result["assessment_year"] == 2025
    assert result["caliber_label"] == "静态底稿·非正式口径（后端下发）"
    assert "不作正式绩效口径" in result["caliber_note"]
    assert result["total_center_count"] == 8
    assert len(result["centers"]) == 8
    assert len(result["mappings"]) == 31


def test_fastapi_application_exposes_team_performance_route():
    module = load_module("backend.app.main", "backend/app/main.py")
    app = getattr(module, "app", None)
    paths = {route.path for route in app.routes}
    assert "/api/team-performance/assessment-workbook" in paths


def _load_team_performance_route_module():
    return load_module(
        f"tests._team_performance_routes.route_{uuid.uuid4().hex}",
        "backend/app/api/routes/team_performance.py",
    )


def test_assessment_workbook_route_returns_envelope(monkeypatch):
    module = _load_team_performance_route_module()
    monkeypatch.setattr(module, "ensure_user_allowed", lambda **_kwargs: None)
    auth = module.AuthContext(user_id="team-perf-test", role="viewer", identity_source="test")

    envelope = module.assessment_workbook(auth=auth)

    assert envelope["result_meta"]["result_kind"] == "team_performance.assessment_workbook"
    assert envelope["result"]["caliber_label"] == "静态底稿·非正式口径（后端下发）"


def test_assessment_workbook_route_rejects_unauthorized_reader(monkeypatch):
    from fastapi import HTTPException

    module = _load_team_performance_route_module()

    def _deny(**_kwargs):
        raise PermissionError("team_performance read denied")

    monkeypatch.setattr(module, "ensure_user_allowed", _deny)
    auth = module.AuthContext(user_id="team-perf-test", role="viewer", identity_source="test")

    with pytest.raises(HTTPException) as exc_info:
        module.assessment_workbook(auth=auth)
    assert exc_info.value.status_code == 403
