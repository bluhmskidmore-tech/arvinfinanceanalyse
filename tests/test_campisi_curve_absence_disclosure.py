"""服务层必须把"利率效应为 0"的三种成因分开说（2026-08 金融审计整改）。

`campisi_attribution_service` 用 `curve_repo.fetch_curve(anchor, "treasury")` 取曲线，
没有 latest 回退；报告日 2026-07-31 一行都没有时它返回 `{}`，下游 Campisi 的基准
求值器退化为恒 0，页面拿到的只是一个普通的 0。

三种成因的处置完全不同 —— 补数 / 修单位 / 放宽期限口径 —— 所以它们必须在
`input_quality.market_curve_coverage.treasury_effect.reason` 上可分支，而不是塌成
同一句话：

- ``curve_absent``：仓储对该交易日没有任何行
- ``curve_unusable``：有行，但 6 个关键期限一个可用的都没有
- ``insufficient_shared_tenors``：两端各自可用，但共同正期限 < 2
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.campisi import availability_diagnostics
from backend.app.services.campisi_attribution_service import (
    BRIDGE_CURVE_UNAVAILABLE_REASON,
    TREASURY_CURVE_ABSENT_REASON,
    TREASURY_CURVE_INSUFFICIENT_SHARED_TENORS_REASON,
    TREASURY_CURVE_UNUSABLE_REASON,
    _add_market_curve_quality,
    _build_input_quality,
    _formal_bridge_effect_availability,
    _merge_positions,
    fetch_treasury_market_dict,
)

_FULL_CURVE = {
    "treasury_1y": 2.00,
    "treasury_3y": 2.30,
    "treasury_5y": 2.60,
    "treasury_7y": 2.80,
    "treasury_10y": 3.00,
    "treasury_30y": 3.50,
}


class _CurveRepoStub:
    path = "curve-absence-disclosure.duckdb"

    def __init__(self, curves: dict[tuple[str, str], dict[str, object]]) -> None:
        self._curves = curves

    def fetch_curve(self, trade_date: str, curve_type: str) -> dict[str, object]:
        return dict(self._curves.get((trade_date, curve_type), {}))


def _bond_row(code: str = "BOND_AAA") -> dict[str, object]:
    return {
        "instrument_code": code,
        "portfolio_name": "FIOA",
        "cost_center": "5010",
        "accounting_class": "FVOCI",
        "currency_code": "CNY",
        "market_value": Decimal("100"),
        "face_value": Decimal("100"),
        "accrued_interest": Decimal("0"),
        "coupon_rate": Decimal("0.0300"),
        "ytm": Decimal("0.0320"),
        "maturity_date": "2030-12-31",
        "asset_class_std": "credit",
        "rating": "AAA",
    }


def _quality_for(
    market_start: dict[str, object],
    market_end: dict[str, object],
    **presence: bool | None,
) -> dict[str, object]:
    rows_start = [_bond_row()]
    rows_end = [_bond_row()]
    positions = _merge_positions(rows_start, rows_end)
    quality = _build_input_quality(rows_start=rows_start, rows_end=rows_end, positions=positions)
    _add_market_curve_quality(
        quality,
        positions=positions,
        market_start=market_start,
        market_end=market_end,
        **presence,
    )
    return quality


def test_fetch_treasury_market_dict_reports_absence_separately_from_content():
    repo = _CurveRepoStub(
        {
            ("2026-06-30", "treasury"): {"1Y": Decimal("2.00"), "3Y": Decimal("2.30")},
            # 2026-07-31 故意缺席，复刻报告日的真实情形。
        }
    )

    present_market, present = fetch_treasury_market_dict(repo, "2026-06-30")
    absent_market, absent = fetch_treasury_market_dict(repo, "2026-07-31")

    assert present is True
    assert present_market == {"treasury_1y": 2.00, "treasury_3y": 2.30}
    assert absent is False
    assert absent_market == {}


def test_absent_curve_rows_are_reported_as_curve_absent_not_as_a_thin_curve():
    quality = _quality_for(
        _FULL_CURVE,
        {},
        start_curve_rows_present=True,
        end_curve_rows_present=False,
    )

    treasury = quality["market_curve_coverage"]["treasury_effect"]
    assert treasury["status"] == "unavailable"
    assert treasury["reason"] == TREASURY_CURVE_ABSENT_REASON
    assert treasury["start_curve_rows_present"] is True
    assert treasury["end_curve_rows_present"] is False
    assert treasury["shared_positive_tenors"] == 0

    warning = next(w for w in quality["warnings"] if "treasury curve is absent" in w)
    assert "end date(s)" in warning
    assert 'not "rates did not move"' in warning
    # 保留既有匹配器用的短语，避免下游文本判定悄悄失效。
    assert "degrade to 0" in warning


def test_rows_present_but_no_usable_tenor_is_reported_as_curve_unusable():
    """有行却一个可用期限都没有：这是单位/符号/解析问题，不是"没有数据"。"""
    quality = _quality_for(
        _FULL_CURVE,
        {"treasury_1y": 0.0, "treasury_3y": -1.0},
        start_curve_rows_present=True,
        end_curve_rows_present=True,
    )

    treasury = quality["market_curve_coverage"]["treasury_effect"]
    assert treasury["status"] == "unavailable"
    assert treasury["reason"] == TREASURY_CURVE_UNUSABLE_REASON
    assert treasury["start_usable_tenors"] == 6
    assert treasury["end_usable_tenors"] == 0
    assert any("no key tenor is usable" in w for w in quality["warnings"])


def test_thin_but_present_curves_are_reported_as_insufficient_shared_tenors():
    quality = _quality_for(
        {"treasury_1y": 2.0},
        {"treasury_30y": 3.5},
        start_curve_rows_present=True,
        end_curve_rows_present=True,
    )

    treasury = quality["market_curve_coverage"]["treasury_effect"]
    assert treasury["status"] == "unavailable"
    assert treasury["reason"] == TREASURY_CURVE_INSUFFICIENT_SHARED_TENORS_REASON
    assert treasury["start_usable_tenors"] == 1
    assert treasury["end_usable_tenors"] == 1
    assert treasury["shared_positive_tenors"] == 0
    assert any("fewer than 2 shared positive tenors" in w for w in quality["warnings"])


def test_absence_outranks_thinness_so_the_root_cause_is_the_one_reported():
    """两个问题同时成立时报最上游的那个，否则运维会去修错的东西。"""
    quality = _quality_for(
        {"treasury_1y": 2.0},
        {},
        start_curve_rows_present=True,
        end_curve_rows_present=False,
    )

    assert (
        quality["market_curve_coverage"]["treasury_effect"]["reason"]
        == TREASURY_CURVE_ABSENT_REASON
    )


def test_healthy_curve_pair_reports_ok_and_adds_no_treasury_warning():
    quality = _quality_for(
        _FULL_CURVE,
        {key: value + 0.10 for key, value in _FULL_CURVE.items()},
        start_curve_rows_present=True,
        end_curve_rows_present=True,
    )

    treasury = quality["market_curve_coverage"]["treasury_effect"]
    assert treasury["status"] == "ok"
    assert treasury["reason"] is None
    assert treasury["shared_positive_tenors"] == 6
    assert not [w for w in quality["warnings"] if "treasury curve" in w]


def test_presence_flags_are_optional_so_direct_callers_keep_working():
    """不传 rows_present 时退回按内容判定，既有调用方与用例不受影响。"""
    quality = _quality_for(_FULL_CURVE, {})

    treasury = quality["market_curve_coverage"]["treasury_effect"]
    assert treasury["status"] == "unavailable"
    assert treasury["reason"] == TREASURY_CURVE_UNUSABLE_REASON
    assert treasury["start_curve_rows_present"] is None


def _formal_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "market_value_start": 1_000_000.0,
        "treasury_effect_available": True,
        "spread_effect_available": True,
        "has_accrued_interest": True,
    }
    row.update(overrides)
    return row


def test_formal_bridge_path_relays_the_bridge_row_diagnostics_instead_of_going_silent():
    """formal-bridge 路径不能因为"不是 Campisi 直算"就交出一个空的可用性块。

    桥已经在行级标出"缺曲线 / 两端同源"，这里原样折叠成同一个状态块；否则页面
    看到"没有 unavailable 标记"，会把 1715 行的 0 当成观测值。
    """
    availability = _formal_bridge_effect_availability(
        [
            _formal_row(treasury_effect_available=False, spread_effect_available=False),
            _formal_row(market_value_start=3_000_000.0, has_accrued_interest=False),
        ]
    )

    assert availability["bonds"] == 2
    assert availability["treasury_effect"]["status"] == "partial"
    assert availability["treasury_effect"]["reason"] == BRIDGE_CURVE_UNAVAILABLE_REASON
    assert availability["treasury_effect"]["unavailable_bonds"] == 1
    assert availability["treasury_effect"]["unavailable_market_value_start"] == 1_000_000.0
    assert availability["spread_effect"]["status"] == "partial"
    assert availability["accrued_interest"]["status"] == "partial"
    assert availability["accrued_interest"]["unavailable_market_value_start"] == 3_000_000.0
    assert availability["accrued_interest"]["basis"] == "mixed"

    diagnostics = availability_diagnostics(availability)
    assert any(d.startswith("treasury_effect_unavailable") for d in diagnostics)
    assert any(d.startswith("accrued_interest_clean_price_fallback") for d in diagnostics)


def test_formal_bridge_availability_shape_matches_the_direct_campisi_path():
    availability = _formal_bridge_effect_availability([_formal_row()])

    common_keys = {"status", "reason", "unavailable_bonds", "unavailable_market_value_start"}
    for name in ("treasury_effect", "spread_effect", "accrued_interest"):
        entry = availability[name]
        assert common_keys <= set(entry), name
        assert entry["status"] == "ok"
        assert entry["reason"] is None
    assert availability_diagnostics(availability) == []


def test_partial_tenor_gap_keeps_the_existing_interpolation_warning():
    """回归保险：只是缺长端时仍走原来的"退化到共同期限子集"披露，不被新分支吞掉。"""
    end_missing_30y = {k: v for k, v in _FULL_CURVE.items() if k != "treasury_30y"}

    quality = _quality_for(
        _FULL_CURVE,
        end_missing_30y,
        start_curve_rows_present=True,
        end_curve_rows_present=True,
    )

    assert quality["market_curve_coverage"]["treasury_effect"]["status"] == "ok"
    assert any("shared-tenor subset" in w for w in quality["warnings"])
