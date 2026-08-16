"""Campisi 占比字段（*_contribution_pct）契约测试。

契约：占比 Numeric 的 ``raw`` 恒为小数比率（0.4 == 40%），不再随取值大小在
百分点 / 比率之间摇摆；``display`` 保持与旧编码（百分点 → /100）逐字符一致。
覆盖三类样例：40%（旧编码正常归一化）、0.8%（旧 schema-shim 下 abs<=1 会保持
百分点的边界）、0 / 缺失数据。另加 >100% 用例锁定前端 ×100 展示语义。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from backend.app.schemas.pnl_attribution import CampisiAttributionPayload
from backend.app.services import pnl_attribution_service as svc

SHARE_KEYS = (
    "income_contribution_pct",
    "treasury_contribution_pct",
    "spread_contribution_pct",
    "selection_contribution_pct",
)

START_DATE = "2026-01-01"
END_DATE = "2026-01-31"


@dataclass
class _CoreResult:
    num_days: int
    totals: dict[str, float]
    by_asset_class: list[dict[str, Any]]
    by_bond: list[dict[str, Any]]
    diagnostics: list[str]


def _core_result(
    *,
    total_return: float,
    income: float,
    treasury: float,
    spread: float,
    selection: float,
) -> _CoreResult:
    return _CoreResult(
        num_days=30,
        totals={
            "market_value_start": 1_000.0,
            "total_return": total_return,
            "income_return": income,
            "treasury_effect": treasury,
            "spread_effect": spread,
            "selection_effect": selection,
        },
        by_asset_class=[],
        by_bond=[],
        diagnostics=[],
    )


def _validated_payload(result: _CoreResult) -> dict[str, Any]:
    payload = svc._core_campisi_result_to_path_a_payload(
        result,
        report_date=END_DATE,
        period_start=START_DATE,
        period_end=END_DATE,
    )
    promoted = svc._promote_payload_numerics(payload, CampisiAttributionPayload)
    return CampisiAttributionPayload.model_validate(promoted).model_dump(mode="json")


def _assert_share(numeric: dict[str, Any], raw: float, display: str) -> None:
    assert numeric["unit"] == "pct"
    assert numeric["raw"] == pytest.approx(raw, abs=1e-12)
    assert numeric["display"] == display


def test_share_40_pct_raw_is_ratio_display_unchanged() -> None:
    # income 40 / total 100 = 40%：旧编码 raw 40 -> /100 归一化为 0.4，display "+40.00%"。
    payload = _validated_payload(
        _core_result(total_return=100.0, income=40.0, treasury=25.0, spread=20.0, selection=15.0)
    )
    _assert_share(payload["income_contribution_pct"], 0.4, "+40.00%")
    _assert_share(payload["treasury_contribution_pct"], 0.25, "+25.00%")
    _assert_share(payload["spread_contribution_pct"], 0.2, "+20.00%")
    _assert_share(payload["selection_contribution_pct"], 0.15, "+15.00%")


def test_share_below_1_pct_raw_is_ratio_not_percent_points() -> None:
    # spread 0.8 / total 100 = 0.8%：旧 schema-shim 下 abs(0.8)<=1 会把 raw 留在
    # 百分点（0.8），本契约要求 raw 恒为比率 0.008，display 仍是 "+0.80%"。
    payload = _validated_payload(
        _core_result(total_return=100.0, income=99.2, treasury=0.0, spread=0.8, selection=0.0)
    )
    _assert_share(payload["spread_contribution_pct"], 0.008, "+0.80%")
    assert payload["spread_contribution_pct"]["raw"] != pytest.approx(0.8)
    _assert_share(payload["income_contribution_pct"], 0.992, "+99.20%")


def test_share_zero_and_missing_data() -> None:
    # 占比为 0：raw 0.0，display "+0.00%"。
    payload = _validated_payload(
        _core_result(total_return=100.0, income=100.0, treasury=0.0, spread=0.0, selection=0.0)
    )
    _assert_share(payload["treasury_contribution_pct"], 0.0, "+0.00%")

    # total_return 近零（缺口径分母）：全部占比守护为 0，不产生 inf/百分点。
    guarded = _validated_payload(
        _core_result(total_return=0.0, income=12.0, treasury=-8.0, spread=1.0, selection=-5.0)
    )
    for key in SHARE_KEYS:
        _assert_share(guarded[key], 0.0, "+0.00%")

    # 无数据 envelope（dates 为空）：占比字段仍是合法 Numeric，raw 0。
    class _EmptyRepo:
        def list_report_dates(self) -> list[str]:
            return []

        def fetch_bond_analytics_rows(self, **_kwargs: Any) -> list[dict[str, Any]]:
            return []

        def fetch_curve(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {}

    import unittest.mock as mock

    with mock.patch.object(svc, "_bond_repo", lambda: _EmptyRepo()), mock.patch.object(
        svc, "_curve_repo", lambda: _EmptyRepo()
    ):
        result = svc.campisi_attribution_envelope(start_date=None, end_date=None)["result"]
    for key in SHARE_KEYS:
        _assert_share(result[key], 0.0, "+0.00%")


def test_share_above_100_pct_raw_stays_ratio() -> None:
    # 方向相反的效应会让单项占比超过 100%：raw 必须仍是比率（1.5 / -1.9），
    # 前端统一 ×100 展示后与 display 一致。
    payload = _validated_payload(
        _core_result(total_return=50.0, income=75.0, treasury=-95.0, spread=60.0, selection=10.0)
    )
    _assert_share(payload["income_contribution_pct"], 1.5, "+150.00%")
    _assert_share(payload["treasury_contribution_pct"], -1.9, "-190.00%")
