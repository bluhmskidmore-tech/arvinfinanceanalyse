"""Unit tests for bond analytics shared helpers and read models."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.bond_analytics import common
from backend.app.core_finance.bond_analytics.read_models import (
    summarize_return_decomposition,
)
from tests.helpers import load_module


def _read_models_module():
    return load_module(
        "backend.app.core_finance.bond_analytics.read_models",
        "backend/app/core_finance/bond_analytics/read_models.py",
    )


def test_safe_decimal_coerces_and_handles_bad_input() -> None:
    assert common.safe_decimal(None) == Decimal("0")
    assert common.safe_decimal("") == Decimal("0")
    assert common.safe_decimal("12.5") == Decimal("12.5")
    assert common.safe_decimal(3.25) == Decimal(str(3.25))
    d = Decimal("7.77")
    assert common.safe_decimal(d) is d
    assert common.safe_decimal("not-a-number") == Decimal("0")


def test_rating_aa_and_below_portfolio_weight_excludes_aaa_and_aa_plus() -> None:
    rm = _read_models_module()
    total = Decimal("100")
    credit_rows = [
        {"rating": "AAA", "market_value": Decimal("40")},
        {"rating": "AA+", "market_value": Decimal("30")},
        {"rating": "AA", "market_value": Decimal("20")},
        {"rating": "A", "market_value": Decimal("10")},
    ]
    w = rm.rating_aa_and_below_portfolio_weight(credit_rows, total_portfolio_market_value=total)
    assert w == Decimal("0.3")


def test_rating_aa_and_below_portfolio_weight_ignores_unknown_rating() -> None:
    rm = _read_models_module()
    total = Decimal("100")
    credit_rows = [
        {"rating": "AA", "market_value": Decimal("50")},
        {"rating": "MOODY", "market_value": Decimal("50")},
    ]
    w = rm.rating_aa_and_below_portfolio_weight(credit_rows, total_portfolio_market_value=total)
    assert w == Decimal("0.5")


def test_summarize_credit_weighted_avg_spread_published_in_bp() -> None:
    """AAA 4.00% − 国债 3.00% = 1 个百分点，契约单位为 bp，应发布 100（审计 FI-01）。"""
    rm = _read_models_module()
    rows = [
        {
            "accounting_class": "OCI",
            "market_value": Decimal("100"),
            "years_to_maturity": Decimal("5"),
            "spread_dv01": Decimal("0.04"),
            "modified_duration": Decimal("4"),
        }
    ]
    summary = rm.summarize_credit(
        rows,
        total_rows=rows,
        aaa_credit_curve_current={"5Y": Decimal("4.00")},
        treasury_curve_current={"5Y": Decimal("3.00")},
    )
    assert summary["weighted_avg_spread"] == Decimal("100")


def test_build_curve_points_skips_unknown_tenor_instead_of_faking_5y() -> None:
    """未知期限标签不得静默映射为假 5Y 节点（审计 FI-05）：跳过并告警，插值不崩溃。"""
    points = common.build_curve_points(
        {
            "1Y": Decimal("2.00"),
            "5Y": Decimal("3.00"),
            "8Y": Decimal("3.20"),  # 词表外标签：旧行为会映射为 5.0 年与真实 5Y 重复
            "10Y": Decimal("3.50"),
        }
    )

    assert [years for years, _ in points] == [1.0, 5.0, 10.0]
    # 旧行为在此处触发三次样条 h=0 除零；现在应正常插值。
    rate = common.interpolate_rate(points, 8.0)
    assert Decimal("2") < rate < Decimal("4")


def test_tenor_to_years_fails_loud_on_unknown_label() -> None:
    """tenor_to_years 对词表外标签 fail-loud，而不是发明 5.0 年（审计 FI-05）。"""
    with pytest.raises(ValueError, match="Unknown curve tenor label"):
        common.tenor_to_years("8Y")


def test_classify_asset_class_rate_credit_other() -> None:
    assert common.classify_asset_class("国债") == "rate"
    assert common.classify_asset_class("企业债") == "credit"
    assert common.classify_asset_class("xxx") == "other"
    assert common.classify_asset_class("") == "other"


def test_classify_asset_class_recognizes_real_world_credit_bond_labels() -> None:
    assert common.classify_asset_class("信用债券-企业") == "credit"
    assert common.classify_asset_class("信用债券-公用事业") == "credit"
    assert common.classify_asset_class("商业银行债") == "credit"
    assert common.classify_asset_class("资产支持证券") == "credit"


def test_map_accounting_class_patterns() -> None:
    assert common.map_accounting_class("持有至到期") == "AC"
    assert common.map_accounting_class("交易性") == "TPL"
    assert common.map_accounting_class("FVOCI") == "OCI"


def test_estimate_duration_macaulay_vs_fallback() -> None:
    rd = date(2026, 3, 31)
    mat = date(2031, 3, 31)
    coupon = Decimal("0.03")
    ytm = Decimal("0.035")
    d_mac = common.estimate_duration(mat, rd, coupon_rate=coupon, ytm=ytm)
    assert d_mac > Decimal("0")
    # Fallback: no coupon/ytm path uses years to maturity
    d_years = common.estimate_duration(mat, rd)
    years_approx = Decimal("1826") / Decimal("365")  # ~5y
    assert abs(d_years - years_approx) < Decimal("0.02")
    # 缺到期日 -> 不可用标记（W-fi-2026-08 P2：不再硬编码 3.0 年占位）
    assert common.estimate_duration(None, rd) == common.DURATION_UNAVAILABLE
    assert common.estimate_duration(None, rd) != Decimal("3")


def test_estimate_duration_missing_maturity_signals_unavailable() -> None:
    """缺到期日：``estimate_duration_with_status`` 返回 ``(None, maturity_unavailable)``。

    W-fi-2026-08 P2：此前 ``return Decimal("3")`` 给一批**根本不是债券**的持仓
    （2026-07-31 实测 127 笔 / 434.00 亿，全是公募基金与 ETF）凭空编了 3 年久期，
    折合组合加权久期虚增 0.3804 年。现在返回明确的「不可用」信号，兼容外壳
    ``estimate_duration`` 折成 ``DURATION_UNAVAILABLE``（0）以保住 Decimal 契约。
    """
    rd = date(2026, 7, 31)

    assert common.estimate_duration_with_status(None, rd) == (
        None,
        common.DURATION_TERM_MATURITY_UNAVAILABLE,
    )
    assert common.estimate_duration_with_status(date(2031, 7, 31), None) == (
        None,
        common.DURATION_TERM_MATURITY_UNAVAILABLE,
    )
    # 已到期与缺到期日数值同为 0，但状态必须可区分。
    assert common.estimate_duration_with_status(date(2026, 1, 31), rd) == (
        Decimal("0"),
        common.DURATION_TERM_NO_REMAINING_TERM,
    )


def test_missing_maturity_duration_constant_is_defined_once() -> None:
    """占位常数只此一处：``resolve_missing_maturity_duration`` 是唯一出处。"""
    assert common.DURATION_UNAVAILABLE == Decimal("0")
    assert (
        common.resolve_missing_maturity_duration(
            bond_code="SA0106070101",
            maturity_date_missing=True,
            report_date_missing=False,
        )
        == common.DURATION_UNAVAILABLE
    )


# --- W-fi-2026-08 P1: 有票息缺 ytm 的 par 假设回退（黄金手算样本） ---
#
# 用例基准：报告日 2026-01-01、到期日 2035-12-30，相差恰 3650 天 →
# years_to_maturity = 3650/365 = 10（整），年付（coupon_frequency=1）。
#
# par 假设（ytm = coupon = 3%）的闭式手算（独立推导，未经被测函数）：
#   平价债 Macaulay D = (1+y)/y * (1 - (1+y)^-n)
#     = (1.03/0.03) * (1 - 1.03^-10) = 8.786108921879104...
#   修正久期 = D / (1 + y/f) = 8.786108921879104 / 1.03 = 8.530202836775829...
# 逐笔现金流求和（D = Σ t·cf·v^t / Σ cf·v^t, v=1/1.03, cf=0.03×9期+1.03末期）
# 交叉验证与闭式一致。
_PAR_10Y_3PCT_MACAULAY = Decimal("8.786108921879104")
_PAR_10Y_3PCT_MODIFIED = Decimal("8.530202836775829")
_GOLDEN_TOL = Decimal("0.000001")
_PAR_CASE_REPORT_DATE = date(2026, 1, 1)
_PAR_CASE_MATURITY_DATE = date(2035, 12, 30)


def test_estimate_duration_coupon_bond_missing_ytm_uses_par_assumption() -> None:
    """有票息但 ytm 缺失/非正：按 par 假设（ytm=coupon）走 Macaulay，不再返回剩余年限。"""
    assert (_PAR_CASE_MATURITY_DATE - _PAR_CASE_REPORT_DATE).days == 3650

    for missing_ytm in (Decimal("0"), Decimal("-0.01")):
        dur = common.estimate_duration(
            _PAR_CASE_MATURITY_DATE,
            _PAR_CASE_REPORT_DATE,
            coupon_rate=Decimal("0.03"),
            ytm=missing_ytm,
            coupon_frequency=1,
        )
        assert abs(dur - _PAR_10Y_3PCT_MACAULAY) < _GOLDEN_TOL
        # 旧缺陷（零息假设）返回 10 年整；par 口径 ≈8.79 年。
        assert dur < Decimal("10")

    # par 回退结果 ≡ 显式传 ytm=coupon 的正常路径结果（口径自洽）。
    explicit = common.estimate_duration(
        _PAR_CASE_MATURITY_DATE,
        _PAR_CASE_REPORT_DATE,
        coupon_rate=Decimal("0.03"),
        ytm=Decimal("0.03"),
        coupon_frequency=1,
    )
    fallback = common.estimate_duration(
        _PAR_CASE_MATURITY_DATE,
        _PAR_CASE_REPORT_DATE,
        coupon_rate=Decimal("0.03"),
        coupon_frequency=1,
    )
    assert fallback == explicit


def test_estimate_duration_zero_coupon_missing_ytm_keeps_years_fallback() -> None:
    """零票息 + ytm 缺失：维持剩余年限（零息债 Macaulay=剩余年限本就正确）。"""
    assert (
        common.estimate_duration(_PAR_CASE_MATURITY_DATE, _PAR_CASE_REPORT_DATE)
        == Decimal("10")
    )
    assert (
        common.estimate_duration(
            _PAR_CASE_MATURITY_DATE,
            _PAR_CASE_REPORT_DATE,
            coupon_rate=Decimal("0"),
            ytm=Decimal("0"),
        )
        == Decimal("10")
    )


def test_estimate_duration_positive_ytm_path_regression_pin() -> None:
    """ytm>0 正常路径行为不变：10Y/3% 票息、ytm=3.5%、年付的手算 pin。

    期望值由逐笔现金流独立求和（未经被测函数）：
      D = Σ t·cf·v^t / Σ cf·v^t，v = 1/1.035，cf = 0.03×9期 + 1.03末期
        = 8.754809652828168...
    """
    dur = common.estimate_duration(
        _PAR_CASE_MATURITY_DATE,
        _PAR_CASE_REPORT_DATE,
        coupon_rate=Decimal("0.03"),
        ytm=Decimal("0.035"),
        coupon_frequency=1,
    )
    assert abs(dur - Decimal("8.754809652828168")) < _GOLDEN_TOL


def test_resolve_ytm_with_par_fallback_paths() -> None:
    # ytm>0 正常路径：原样返回，不标记回退。
    assert common.resolve_ytm_with_par_fallback(Decimal("0.03"), Decimal("0.035")) == (
        Decimal("0.035"),
        False,
    )
    # 有票息缺/非正 ytm：par 假设，标记回退。
    assert common.resolve_ytm_with_par_fallback(Decimal("0.03"), Decimal("0")) == (
        Decimal("0.03"),
        True,
    )
    assert common.resolve_ytm_with_par_fallback(Decimal("0.03"), Decimal("-0.01")) == (
        Decimal("0.03"),
        True,
    )
    # 零票息：不适用 par 假设。
    assert common.resolve_ytm_with_par_fallback(Decimal("0"), Decimal("0")) == (
        Decimal("0"),
        False,
    )
    assert common.resolve_ytm_with_par_fallback(Decimal("0"), Decimal("0.02")) == (
        Decimal("0.02"),
        False,
    )


def test_estimate_modified_duration_par_assumption_and_legacy_semantics() -> None:
    """par 假设行的修正久期以生效 ytm(=coupon) 折算；ytm<=0 直传保持原语义。"""
    effective_ytm, used = common.resolve_ytm_with_par_fallback(
        Decimal("0.03"), Decimal("0")
    )
    assert used is True
    modified = common.estimate_modified_duration(
        _PAR_10Y_3PCT_MACAULAY, effective_ytm, coupon_frequency=1
    )
    assert abs(modified - _PAR_10Y_3PCT_MODIFIED) < _GOLDEN_TOL
    # 未走 par 解析、直接传 ytm<=0 的旧调用方（如 pnl_bridge 回退路径）：
    # 不折算、原样返回 Macaulay（行为不变）。
    assert common.estimate_modified_duration(Decimal("5"), Decimal("0")) == Decimal("5")


@pytest.mark.parametrize(
    ("period_type", "start_expect", "end_expect"),
    [
        ("MoM", date(2026, 3, 1), date(2026, 3, 31)),
        ("YTD", date(2026, 1, 1), date(2026, 3, 31)),
        ("TTM", date(2025, 3, 31), date(2026, 3, 31)),
    ],
)
def test_resolve_period_mom_ytd_ttm(
    period_type: str,
    start_expect: date,
    end_expect: date,
) -> None:
    rd = date(2026, 3, 31)
    start, end = common.resolve_period(rd, period_type)
    assert start == start_expect
    assert end == end_expect


@pytest.mark.parametrize(
    ("period_type", "start_expect"),
    [
        # 闰日报告日：上一年 2/29 不存在，回退到目标月最后一天（2/28），
        # 不得抛 ValueError（修复前当天全部 TTM 视图 500）。
        ("TTM", date(2027, 2, 28)),
        ("YTD", date(2028, 1, 1)),
        ("MoM", date(2028, 2, 1)),
    ],
)
def test_resolve_period_on_leap_day_does_not_raise(
    period_type: str,
    start_expect: date,
) -> None:
    leap_day = date(2028, 2, 29)
    start, end = common.resolve_period(leap_day, period_type)
    assert start == start_expect
    assert end == leap_day


@pytest.mark.parametrize(
    ("years", "bucket"),
    [
        (0.25, "6M"),
        (1.0, "1Y"),
        (2.0, "2Y"),
        (3.5, "3Y"),
        (5.5, "5Y"),
        (8.0, "7Y"),
        (10.0, "10Y"),
        (15.0, "20Y"),
        (30.0, "30Y"),
    ],
)
def test_get_tenor_bucket(years: float, bucket: str) -> None:
    assert common.get_tenor_bucket(years) == bucket


def test_portfolio_risk_duration_excludes_no_maturity_rows_from_denominator() -> None:
    summary = _read_models_module().summarize_portfolio_risk(
        [
            {
                "market_value": Decimal("100"),
                "maturity_date": date(2030, 1, 1),
                "macaulay_duration": Decimal("4.2"),
                "modified_duration": Decimal("4"),
                "convexity": Decimal("20"),
                "dv01": Decimal("4"),
            },
            {
                "market_value": Decimal("300"),
                "maturity_date": None,
                "macaulay_duration": Decimal("0"),
                "modified_duration": Decimal("0"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
        ]
    )

    assert summary["total_market_value"] == Decimal("400")
    assert summary["portfolio_dv01"] == Decimal("4")
    assert summary["portfolio_duration"] == Decimal("4.2")
    assert summary["portfolio_modified_duration"] == Decimal("4")


def test_convexity_effect_with_curve_data() -> None:
    summary = summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 5Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        treasury_curve_current={"5Y": Decimal("3.00")},
        treasury_curve_prior={"5Y": Decimal("1.00")},
    )

    expected = Decimal("0.5") * Decimal("2") * Decimal("0.02") * Decimal("0.02") * Decimal("100")

    assert summary["convexity_effect_total"] == expected
    assert summary["bond_details"][0]["convexity_effect"] == expected


def test_carry_uses_exclusive_elapsed_days_aligned_with_campisi() -> None:
    """Carry 天数与 campisi/attribution_daily 一致：exclusive (end-start).days，同日下限 1。"""
    summary = summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Coupon Bond",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0.03"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("0"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
    )
    # exclusive 30 days: 0.03 * 100 * 30 / 365
    expected = Decimal("0.03") * Decimal("100") * Decimal("30") / Decimal("365")
    assert summary["carry_total"] == expected
    assert summary["bond_details"][0]["carry"] == expected


def test_roll_down_uses_exclusive_elapsed_days_for_current_anchor() -> None:
    rm = _read_models_module()
    current_curve = {"1Y": Decimal("1.00"), "2Y": Decimal("2.00")}

    summary = rm.summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 2Y",
                "asset_class_raw": "rate",
                "asset_class_std": "rate",
                "bond_type": "treasury",
                "accounting_class": "FVTPL",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("2"),
                "tenor_bucket": "2Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("0"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        treasury_curve_current=current_curve,
    )

    expected = rm._curve_roll_down(
        current_curve=current_curve,
        years_to_maturity=Decimal("2"),
        period_days=30,
        modified_duration=Decimal("4"),
        market_value=Decimal("100"),
    )
    assert summary["roll_down_total"] == expected
    assert summary["bond_details"][0]["roll_down"] == expected


def test_convexity_effect_without_curve_data_is_zero() -> None:
    summary = summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 5Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
    )

    assert summary["convexity_effect_total"] == Decimal("0")
    assert summary["bond_details"][0]["convexity_effect"] == Decimal("0")


def test_convexity_effect_uses_same_delta_y_as_rate_effect() -> None:
    """一阶（rate_effect）与二阶（convexity_effect）必须用同一套 Δy。

    行的实际剩余年限 2 年，tenor_bucket 故意标成 "10Y"：曲线在 2Y 处
    下移 50bp、10Y 处不变。修复前 convexity_effect 按 tenor_bucket 标签取
    Δy=0 而 rate_effect 按 years_to_maturity 插值取 Δy=50bp——同一只债的
    一阶/二阶项吃两套 Δy。修复后两者同源（years_to_maturity 插值）。
    """
    rm = _read_models_module()
    current_curve = {"1Y": Decimal("3.0"), "2Y": Decimal("3.0"), "10Y": Decimal("3.0")}
    prior_curve = {"1Y": Decimal("2.5"), "2Y": Decimal("2.5"), "10Y": Decimal("3.0")}
    summary = rm.summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 2Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "face_value": Decimal("100"),
                "market_value": Decimal("1000"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("2"),
                "tenor_bucket": "10Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("8"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        treasury_curve_current=current_curve,
        treasury_curve_prior=prior_curve,
    )

    delta_y = (
        rm._curve_rate(current_curve, Decimal("2")) - rm._curve_rate(prior_curve, Decimal("2"))
    ) / Decimal("100")
    detail = summary["bond_details"][0]
    # 同一 Δy 同时驱动一阶与二阶项。
    assert detail["rate_effect"] == -(delta_y * Decimal("4") * Decimal("1000"))
    assert detail["convexity_effect"] == Decimal("0.5") * Decimal("8") * delta_y * delta_y * Decimal("1000")
    # 旧实现按 "10Y" 标签取 Δy=0，凸性项恒为 0；修复后必须非零。
    assert detail["convexity_effect"] > Decimal("0")


def test_fx_effect_zero_for_cny_bonds() -> None:
    summary = _read_models_module().summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 5Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    assert summary["fx_effect_total"] == Decimal("0")
    assert summary["bond_details"][0]["fx_effect"] == Decimal("0")


def test_fx_effect_positive_when_usd_appreciates() -> None:
    summary = _read_models_module().summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "USD Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "USD",
                "face_value": Decimal("1000"),
                "market_value_native": Decimal("1000"),
                "market_value": Decimal("7082.70000000"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    assert summary["fx_effect_total"] == Decimal("41.35000000")
    assert summary["bond_details"][0]["fx_effect"] == Decimal("41.35000000")


def test_fx_effect_base_includes_native_accrued_interest() -> None:
    """FX 折算基数是原币脏价（market_value_native + accrued_interest_native）。

    与 ``pnl_bridge._fx_exposure_native`` 及 ``docs/calc_rules.md`` 的
    「FX translation base」对齐：应计票息与净价承担同样的汇率敞口。
    修复前 read_models 只用净市值，同一持仓在桥接与收益分解两条路径上
    拿到两个不同的 fx_effect。
    """
    summary = _read_models_module().summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "USD Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "USD",
                "face_value": Decimal("1000"),
                "market_value_native": Decimal("1000"),
                "accrued_interest_native": Decimal("100"),
                "market_value": Decimal("7082.70000000"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    # (1000 + 100) × (7.0827 − 7.04135) = 1100 × 0.04135
    assert summary["fx_effect_total"] == Decimal("45.4850")
    assert summary["bond_details"][0]["fx_effect"] == Decimal("45.4850")


def test_fx_effect_missing_rate_emits_fx_rate_missing_warning() -> None:
    summary = _read_models_module().summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "USD Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "USD",
                "face_value": Decimal("1000"),
                "market_value_native": Decimal("1000"),
                "market_value": Decimal("7082.70000000"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        fx_rates_current={"EUR": Decimal("7.9")},
        fx_rates_prior={"EUR": Decimal("7.8")},
    )

    # Value still defaults to zero, but the missing FX input must be observable.
    assert summary["fx_effect_total"] == Decimal("0")
    assert summary["fx_rate_missing_currencies"] == ["USD"]
    assert any("FX_RATE_MISSING" in warning for warning in summary["warnings"])


def test_fx_effect_cny_bonds_do_not_emit_fx_rate_missing_warning() -> None:
    summary = _read_models_module().summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 5Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
    )

    # CNY exposure has no FX effect and must not raise a missing-input warning.
    assert summary["fx_effect_total"] == Decimal("0")
    assert summary["fx_rate_missing_currencies"] == []
    assert all("FX_RATE_MISSING" not in warning for warning in summary["warnings"])


def test_fx_effect_zero_without_native_market_value() -> None:
    summary = _read_models_module().summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "USD Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "USD",
                "face_value": Decimal("1000"),
                "market_value": Decimal("7082.70000000"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        fx_rates_current={"USD": Decimal("7.0827")},
        fx_rates_prior={"USD": Decimal("7.04135")},
    )

    assert summary["fx_effect_total"] == Decimal("0")
    assert summary["bond_details"][0]["fx_effect"] == Decimal("0")


def test_spread_effect_moves_excess_return_without_selection_residual() -> None:
    summary = _read_models_module().compute_benchmark_excess(
        [
            {
                "instrument_code": "C1",
                "instrument_name": "Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "macaulay_duration": Decimal("5"),
                "modified_duration": Decimal("5"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            }
        ],
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current={"5Y": Decimal("2.00")},
        benchmark_curve_prior={"5Y": Decimal("2.00")},
        treasury_curve_current={"5Y": Decimal("2.00")},
        treasury_curve_prior={"5Y": Decimal("2.00")},
        aaa_credit_curve_current={"5Y": Decimal("6.00")},
        aaa_credit_curve_prior={"5Y": Decimal("5.00")},
    )

    assert summary["excess_return"] == Decimal("-500.00000000")
    assert summary["spread_effect"] == Decimal("-500.00000000")
    assert summary["selection_effect"] == Decimal("0")
    assert summary["allocation_effect"] == Decimal("0")


def test_allocation_sector_return_includes_fx_but_excludes_spread() -> None:
    """配置效应含 FX（无独立 fx 项）；故意不含 spread（已有独立 spread_effect，避免双重计数）。"""
    read_models = _read_models_module()
    sector_summary = {
        "carry": Decimal("1"),
        "roll_down": Decimal("2"),
        "rate_effect": Decimal("3"),
        "spread_effect": Decimal("4"),
        "convexity_effect": Decimal("5"),
        "fx_effect": Decimal("6"),
        "market_value": Decimal("100"),
    }
    sector_return = read_models._allocation_sector_return(
        sector_summary=sector_summary,
        sector_market_value=Decimal("100"),
    )
    # (1+2+3+5+6) / 100 * 100 = 17；spread 4 不计入
    assert sector_return == Decimal("17")


def test_allocation_effect_uses_non_carry_sector_returns() -> None:
    summary = _read_models_module().compute_benchmark_excess(
        [
            {
                "instrument_code": "R1",
                "instrument_name": "Treasury 1Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("1"),
                "tenor_bucket": "1Y",
                "macaulay_duration": Decimal("1"),
                "modified_duration": Decimal("1"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
            {
                "instrument_code": "C1",
                "instrument_name": "Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "macaulay_duration": Decimal("5"),
                "modified_duration": Decimal("5"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
        ],
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current={"1Y": Decimal("3.00"), "5Y": Decimal("3.00")},
        benchmark_curve_prior={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
        treasury_curve_current={"1Y": Decimal("3.00"), "5Y": Decimal("3.00")},
        treasury_curve_prior={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
        aaa_credit_curve_current={"5Y": Decimal("3.00")},
        aaa_credit_curve_prior={"5Y": Decimal("3.00")},
    )

    assert summary["allocation_effect"] == Decimal("-200.0000000")
    assert summary["selection_effect"] == Decimal("200.00000000")
    # recon_error is the unexplained residual: excess minus the independently
    # computed effects (excluding the selection plug). It can be non-zero.
    assert summary["recon_error"] == (
        summary["excess_return"]
        - summary["duration_effect"]
        - summary["curve_effect"]
        - summary["spread_effect"]
        - summary["allocation_effect"]
    )
    assert summary["recon_error"] == summary["selection_effect"]
    assert summary["recon_error"] != Decimal("0")
    assert summary["explained_excess"] == summary["excess_return"]


def test_benchmark_excess_reuses_return_decomposition_for_allocation(monkeypatch: pytest.MonkeyPatch) -> None:
    read_models = _read_models_module()
    calls = 0
    original = read_models.summarize_return_decomposition

    def counting_summary(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(read_models, "summarize_return_decomposition", counting_summary)

    summary = read_models.compute_benchmark_excess(
        [
            {
                "instrument_code": "R1",
                "instrument_name": "Treasury 1Y",
                "asset_class_raw": "rate",
                "asset_class_std": "rate",
                "bond_type": "treasury",
                "accounting_class": "AC",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("1"),
                "tenor_bucket": "1Y",
                "macaulay_duration": Decimal("1"),
                "modified_duration": Decimal("1"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
            {
                "instrument_code": "C1",
                "instrument_name": "Credit 5Y",
                "asset_class_raw": "credit",
                "asset_class_std": "credit",
                "bond_type": "credit",
                "accounting_class": "OCI",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "macaulay_duration": Decimal("5"),
                "modified_duration": Decimal("5"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
        ],
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current={"1Y": Decimal("3.00"), "5Y": Decimal("3.00")},
        benchmark_curve_prior={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
        treasury_curve_current={"1Y": Decimal("3.00"), "5Y": Decimal("3.00")},
        treasury_curve_prior={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
        aaa_credit_curve_current={"5Y": Decimal("3.00")},
        aaa_credit_curve_prior={"5Y": Decimal("3.00")},
    )

    assert calls == 1
    assert summary["allocation_effect"] == Decimal("-200.0000000")


def test_benchmark_excess_reuses_prepared_curve_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    read_models = _read_models_module()
    calls = 0
    original = read_models.build_full_curve

    def counting_build_full_curve(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(read_models, "build_full_curve", counting_build_full_curve)
    rows = [
        {
            "instrument_code": f"R{i}",
            "instrument_name": f"Treasury {i}Y",
            "asset_class_raw": "rate",
            "asset_class_std": "rate",
            "bond_type": "treasury",
            "accounting_class": "AC",
            "currency_code": "CNY",
            "face_value": Decimal("100"),
            "market_value": Decimal("100"),
            "coupon_rate": Decimal("0"),
            "years_to_maturity": Decimal(str(i)),
            "tenor_bucket": "5Y",
            "macaulay_duration": Decimal(str(i)),
            "modified_duration": Decimal(str(i)),
            "convexity": Decimal("1"),
            "dv01": Decimal("0"),
        }
        for i in range(1, 7)
    ]

    summary = read_models.compute_benchmark_excess(
        rows,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current={"1Y": Decimal("3.00"), "3Y": Decimal("3.20"), "5Y": Decimal("3.40")},
        benchmark_curve_prior={"1Y": Decimal("2.00"), "3Y": Decimal("2.20"), "5Y": Decimal("2.40")},
        treasury_curve_current={"1Y": Decimal("3.00"), "3Y": Decimal("3.20"), "5Y": Decimal("3.40")},
        treasury_curve_prior={"1Y": Decimal("2.00"), "3Y": Decimal("2.20"), "5Y": Decimal("2.40")},
    )

    assert summary["benchmark_return"] != Decimal("0")
    assert calls <= 4


def test_portfolio_return_is_invariant_across_benchmark_choice() -> None:
    read_models = _read_models_module()
    rows = [
        {
            "instrument_code": "R1",
            "instrument_name": "Treasury 1Y",
            "asset_class_raw": "rate",
            "asset_class_std": "rate",
            "bond_type": "treasury",
            "accounting_class": "AC",
            "currency_code": "CNY",
            "face_value": Decimal("100"),
            "market_value": Decimal("100"),
            "coupon_rate": Decimal("0.10"),
            "years_to_maturity": Decimal("1"),
            "tenor_bucket": "1Y",
            "macaulay_duration": Decimal("1"),
            "modified_duration": Decimal("1"),
            "convexity": Decimal("0"),
            "dv01": Decimal("0"),
        },
        {
            "instrument_code": "C1",
            "instrument_name": "Credit 5Y",
            "asset_class_raw": "credit",
            "asset_class_std": "credit",
            "bond_type": "credit",
            "accounting_class": "OCI",
            "currency_code": "CNY",
            "face_value": Decimal("100"),
            "market_value": Decimal("100"),
            "coupon_rate": Decimal("0.20"),
            "years_to_maturity": Decimal("5"),
            "tenor_bucket": "5Y",
            "macaulay_duration": Decimal("4"),
            "modified_duration": Decimal("4"),
            "convexity": Decimal("0"),
            "dv01": Decimal("0"),
        },
    ]
    treasury_current = {"1Y": Decimal("2.00"), "5Y": Decimal("2.00")}
    treasury_prior = {"1Y": Decimal("1.00"), "5Y": Decimal("1.00")}
    cdb_current = {"1Y": Decimal("2.50"), "5Y": Decimal("2.50")}
    cdb_prior = {"1Y": Decimal("1.50"), "5Y": Decimal("1.50")}
    aaa_current = {"1Y": Decimal("4.00"), "5Y": Decimal("4.00")}
    aaa_prior = {"1Y": Decimal("2.00"), "5Y": Decimal("2.00")}

    treasury_summary = read_models.compute_benchmark_excess(
        rows,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current=treasury_current,
        benchmark_curve_prior=treasury_prior,
        treasury_curve_current=treasury_current,
        treasury_curve_prior=treasury_prior,
        cdb_curve_current=cdb_current,
        cdb_curve_prior=cdb_prior,
        aaa_credit_curve_current=aaa_current,
        aaa_credit_curve_prior=aaa_prior,
    )
    cdb_summary = read_models.compute_benchmark_excess(
        rows,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="CDB_INDEX",
        benchmark_curve_current=cdb_current,
        benchmark_curve_prior=cdb_prior,
        treasury_curve_current=treasury_current,
        treasury_curve_prior=treasury_prior,
        cdb_curve_current=cdb_current,
        cdb_curve_prior=cdb_prior,
        aaa_credit_curve_current=aaa_current,
        aaa_credit_curve_prior=aaa_prior,
    )
    aaa_summary = read_models.compute_benchmark_excess(
        rows,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="AAA_CREDIT_INDEX",
        benchmark_curve_current=aaa_current,
        benchmark_curve_prior=aaa_prior,
        treasury_curve_current=treasury_current,
        treasury_curve_prior=treasury_prior,
        cdb_curve_current=cdb_current,
        cdb_curve_prior=cdb_prior,
        aaa_credit_curve_current=aaa_current,
        aaa_credit_curve_prior=aaa_prior,
    )

    assert treasury_summary["portfolio_return"] == cdb_summary["portfolio_return"] == aaa_summary["portfolio_return"]


def test_allocation_effect_sums_correctly() -> None:
    summary = _read_models_module().compute_benchmark_excess(
        [
            {
                "instrument_code": "R1",
                "instrument_name": "Treasury 1Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0.10"),
                "years_to_maturity": Decimal("1"),
                "tenor_bucket": "1Y",
                "macaulay_duration": Decimal("0"),
                "modified_duration": Decimal("0"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
            {
                "instrument_code": "C1",
                "instrument_name": "Credit 5Y",
                "asset_class_raw": "信用债",
                "asset_class_std": "credit",
                "bond_type": "企业债",
                "accounting_class": "OCI",
                "currency_code": "CNY",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0.20"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "macaulay_duration": Decimal("0"),
                "modified_duration": Decimal("0"),
                "convexity": Decimal("0"),
                "dv01": Decimal("0"),
            },
        ],
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        benchmark_id="TREASURY_INDEX",
        benchmark_curve_current={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
        benchmark_curve_prior={"1Y": Decimal("2.00"), "5Y": Decimal("2.00")},
    )

    # Carry uses exclusive day-count (2026 non-leap: 364 days), so effects scale by 364/365
    # vs the legacy inclusive-365 golden values (500 / 1000).
    scale = Decimal("364") / Decimal("365")
    assert summary["allocation_effect"] == pytest.approx(Decimal("500") * scale)
    assert summary["selection_effect"] == pytest.approx(Decimal("1000") * scale)
    # recon_error equals the unexplained residual (== the selection plug), non-zero here.
    assert summary["recon_error"] == pytest.approx(Decimal("1000") * scale)
    assert summary["explained_excess"] == summary["excess_return"]


def test_summarize_return_decomposition_trading_defaults_to_zero() -> None:
    summary = summarize_return_decomposition(
        [
            {
                "instrument_code": "B1",
                "instrument_name": "Treasury 5Y",
                "asset_class_raw": "利率债",
                "asset_class_std": "rate",
                "bond_type": "国债",
                "accounting_class": "AC",
                "face_value": Decimal("100"),
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "years_to_maturity": Decimal("5"),
                "tenor_bucket": "5Y",
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
            }
        ],
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
    )
    assert summary["trading_total"] == Decimal("0")
    assert summary["bond_details"][0]["trading"] == Decimal("0")


def test_rebucket_return_decomposition_aggregates_trading() -> None:
    from backend.app.core_finance.bond_analytics.read_models import rebucket_return_decomposition

    z = Decimal("0")
    d1: dict = {
        "instrument_code": "A1",
        "asset_class_std": "rate",
        "accounting_class": "AC",
        "carry": z,
        "roll_down": z,
        "rate_effect": z,
        "spread_effect": z,
        "convexity_effect": z,
        "fx_effect": z,
        "trading": Decimal("3"),
        "market_value": Decimal("100"),
        "total": Decimal("3"),
    }
    d2: dict = {
        "instrument_code": "A2",
        "asset_class_std": "credit",
        "accounting_class": "AC",
        "carry": z,
        "roll_down": z,
        "rate_effect": z,
        "spread_effect": z,
        "convexity_effect": z,
        "fx_effect": z,
        "trading": Decimal("7"),
        "market_value": Decimal("200"),
        "total": Decimal("7"),
    }
    by_ac, by_acc = rebucket_return_decomposition([d1, d2])
    rate = next(b for b in by_ac if b["key"] == "rate")
    credit = next(b for b in by_ac if b["key"] == "credit")
    assert rate["trading"] == Decimal("3")
    assert credit["trading"] == Decimal("7")
    assert sum((b["trading"] for b in by_acc), Decimal("0")) == Decimal("10")


# --- Standard curve scenarios: full tenor-bucket coverage ---

# Buckets produced by common.get_tenor_bucket (the active bond-analytics path).
_ALL_TENOR_BUCKETS = ("6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y")


def _scenario(name: str) -> dict:
    return next(s for s in common.STANDARD_SCENARIOS if s["name"] == name)


def _risk_row(tenor_bucket: str) -> dict:
    return {
        "tenor_bucket": tenor_bucket,
        "market_value": Decimal("1000000"),
        "modified_duration": Decimal("4"),
        "convexity": Decimal("20"),
        "asset_class_std": "rate",
        "accounting_class": "OCI",
    }


def test_steepening_flattening_scenarios_cover_all_tenor_buckets() -> None:
    for name in ("steepening_50bp", "flattening_50bp"):
        shocks = _scenario(name)["shocks"]
        missing = [t for t in _ALL_TENOR_BUCKETS if not shocks.get(t)]
        assert not missing, f"{name} has zero/missing shocks for buckets: {missing}"


def test_steepening_flattening_anchor_shocks_unchanged() -> None:
    steepening = _scenario("steepening_50bp")["shocks"]
    flattening = _scenario("flattening_50bp")["shocks"]
    assert (steepening["1Y"], steepening["10Y"], steepening["30Y"]) == (-25, 25, 50)
    assert (flattening["1Y"], flattening["10Y"], flattening["30Y"]) == (25, -25, -50)


def test_steepening_shocks_monotonic_and_flattening_is_mirror() -> None:
    steepening = _scenario("steepening_50bp")["shocks"]
    flattening = _scenario("flattening_50bp")["shocks"]
    values = [steepening[t] for t in _ALL_TENOR_BUCKETS]
    assert values == sorted(values), "steepening shocks should be non-decreasing along the curve"
    assert steepening["2Y"] < 0 and steepening["7Y"] > 0
    for tenor in _ALL_TENOR_BUCKETS:
        assert flattening[tenor] == -steepening[tenor]


def test_build_curve_scenarios_shocks_middle_buckets() -> None:
    rm = _read_models_module()
    rows = [_risk_row(t) for t in ("2Y", "5Y", "7Y")]
    scenarios = {s["scenario_name"]: s for s in rm.build_curve_scenarios(rows)}
    for name in ("steepening_50bp", "flattening_50bp"):
        assert scenarios[name]["pnl_economic"] != Decimal("0"), (
            f"{name} must shock middle tenor buckets (2Y/5Y/7Y)"
        )
    # Steepening on this short/mid book (negative shocks) should be a gain; flattening a loss.
    assert scenarios["steepening_50bp"]["pnl_economic"] > Decimal("0")
    assert scenarios["flattening_50bp"]["pnl_economic"] < Decimal("0")


def test_parallel_scenarios_shock_every_bucket_equally() -> None:
    rm = _read_models_module()
    single = {
        s["scenario_name"]: s["pnl_economic"]
        for s in rm.build_curve_scenarios([_risk_row("6M")])
    }
    for tenor in _ALL_TENOR_BUCKETS[1:]:
        other = {
            s["scenario_name"]: s["pnl_economic"]
            for s in rm.build_curve_scenarios([_risk_row(tenor)])
        }
        for name in ("parallel_up_25bp", "parallel_up_100bp", "parallel_down_50bp"):
            assert other[name] == single[name], f"{name} shock differs for bucket {tenor}"
