"""`credit_spread_analysis.py` 的直接单元测试（characterization test）。

背景：2026-09-02 系统审计 §2.2 指出该模块此前只经 FastAPI TestClient 间接覆盖。
本文件把模块**当前实现**的行为钉住，所有期望值均按源码公式以 Decimal 手算得出，
不重新定义业务口径。文中"第 N 行"均指 `backend/app/core_finance/credit_spread_analysis.py`。

曲线刻意只给两个节点（1Y=2.0、5Y=3.0）：`bond_analytics.common.interpolate_rate`
在节点数 < 3 时退化为分段线性 + 两端平推，期望值才能手算；节点数 ≥ 3 会走三次样条。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from backend.app.core_finance.credit_spread_analysis import (
    BondSpreadRow,
    SpreadHistoricalContext,
    SpreadTermStructurePoint,
    _median,
    _normalize_ytm_to_pct,
    _percentile,
    _q8,
    _resolve_actual_maturity_benchmark_yield,
    _resolve_benchmark_yield,
    _window_values,
    build_spread_term_structure,
    compute_bond_spreads,
    compute_spread_historical_context,
    curve_has_usable_tenors,
    spread_history_observation_counts,
)

pytestmark = pytest.mark.unit

D = Decimal

# 两节点曲线：线性插值 1Y→5Y 每年 +0.25 个百分点；1Y 以下平推 2.0，5Y 以上平推 3.0。
TWO_POINT_CURVE: dict[str, Decimal] = {"1Y": D("2.0"), "5Y": D("3.0")}


def _bond(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "instrument_code": "BOND-A",
        "instrument_name": "债券A",
        "rating": "AAA",
        "asset_class_std": "credit",
        "tenor_bucket": "3Y",
        "ytm": D("0.0312"),
        "years_to_maturity": None,
        "market_value": D("1000000"),
        "face_value": D("1200000"),
        "modified_duration": D("2.5"),
    }
    row.update(overrides)
    return row


def _spread_row(
    tenor_bucket: str,
    credit_spread: str,
    market_value: str,
    code: str = "X",
) -> BondSpreadRow:
    return BondSpreadRow(
        instrument_code=code,
        instrument_name=code,
        rating="AA+",
        tenor_bucket=tenor_bucket,
        ytm=D("3"),
        benchmark_yield=D("2"),
        credit_spread=D(credit_spread),
        spread_duration=D("2"),
        spread_dv01=D("0"),
        market_value=D(market_value),
        weight=D("0"),
    )


def _assert_q8(value: Decimal) -> None:
    assert isinstance(value, Decimal)
    assert value.as_tuple().exponent == -8


@pytest.mark.parametrize("face", [D("0"), 0, "0"])
def test_spread_dv01_preserves_explicit_zero_face(face):
    from backend.app.core_finance.bond_analytics.dv01 import estimated_dv01_from_face_duration

    source = _bond(face_value=face, modified_duration=D("5"))
    (row,) = compute_bond_spreads([source], TWO_POINT_CURVE)
    assert row.spread_dv01 == estimated_dv01_from_face_duration(source) == D("0")


@pytest.mark.parametrize("missing", [True, False])
def test_spread_dv01_retains_legacy_missing_face_fallback(missing):
    source = _bond(face_value=None, modified_duration=D("5"))
    if missing:
        source.pop("face_value")
    (row,) = compute_bond_spreads([source], TWO_POINT_CURVE)
    assert row.spread_dv01 == D("500")


def test_zero_face_spread_detail_matches_formal_engine_and_cs01():
    from dataclasses import asdict

    from backend.app.core_finance.bond_analytics.engine import compute_bond_analytics_rows
    from backend.app.core_finance.risk_tensor import compute_portfolio_risk_tensor

    report_date = date(2026, 3, 31)
    (formal,) = compute_bond_analytics_rows([{
        "instrument_code": "ZERO-FACE", "asset_class": "credit bond",
        "bond_type": "corporate bond", "currency_code": "CNY", "accounting_basis": "FVOCI",
        "face_value_native": D("0"), "market_value_native": D("1000000"),
        "coupon_rate": D("3"), "ytm_value": D("3"), "interest_mode": "annual",
        "maturity_date": date(2031, 3, 31),
    }], report_date)
    assert formal.is_credit
    (detail,) = compute_bond_spreads([asdict(formal)], TWO_POINT_CURVE)
    risk = compute_portfolio_risk_tensor([asdict(formal)], report_date)
    assert formal.dv01 == formal.spread_dv01 == risk.cs01 == detail.spread_dv01 == D("0")


# ---------------------------------------------------------------------------
# 1. compute_bond_spreads 正常路径
# ---------------------------------------------------------------------------


class TestComputeBondSpreadsHappyPath:
    def test_two_credit_bonds_against_two_point_curve(self):
        """依据第 91/102-113/120-126 行公式手算。

        A：ytm 0.0312 → 3.12%（第 243 行 ×100）；years_to_maturity 缺失 → 第 207 行返回 None，
           回退第 107 行按 tenor_bucket "3Y" 取 full_curve["3Y"]：build_full_curve 对
           1Y=2.0/5Y=3.0 线性插值 → 2.0 + 0.5×1.0 = 2.5；
           credit_spread = (3.12 − 2.5) × 100 = 62 bp；
           spread_dv01 = face 1_200_000 × 2.5 / 10000 = 300（第 124 行）。
        B：ytm 0.045 → 4.5%；years_to_maturity 3 → 第 219-227 行在 (1Y,2.0)-(5Y,3.0) 间线性：
           2.0 + 1.0 × 2.0 / 4.0 = 2.5（**优先于** tenor_bucket "5Y" 的 3.0）；
           credit_spread = (4.5 − 2.5) × 100 = 200 bp；
           face_value 缺失 → 第 110-111 行回退 market_value 3_000_000，dv01 = 3_000_000 × 2.8 / 10000 = 840。
        weight：total_credit_mv = 4_000_000（第 95 行）→ A 0.25、B 0.75。
        """
        rows = [
            _bond(),
            _bond(
                instrument_code="BOND-B",
                instrument_name="债券B",
                rating="AA",
                tenor_bucket="5Y",
                ytm=D("0.045"),
                years_to_maturity=3,
                market_value=D("3000000"),
                face_value=None,
                modified_duration=D("2.8"),
            ),
        ]
        result = compute_bond_spreads(rows, TWO_POINT_CURVE)

        assert len(result) == 2
        a, b = result

        assert a.instrument_code == "BOND-A"
        assert a.rating == "AAA"
        assert a.tenor_bucket == "3Y"
        assert a.ytm == D("3.12")
        assert a.benchmark_yield == D("2.5")
        assert a.credit_spread == D("62")
        assert a.spread_duration == D("2.5")
        assert a.spread_dv01 == D("300")
        assert a.market_value == D("1000000")
        assert a.weight == D("0.25")

        assert b.instrument_code == "BOND-B"
        assert b.tenor_bucket == "5Y"
        assert b.ytm == D("4.5")
        assert b.benchmark_yield == D("2.5")
        assert b.credit_spread == D("200")
        assert b.spread_duration == D("2.8")
        assert b.spread_dv01 == D("840")
        assert b.weight == D("0.75")

        for row in result:
            for field in (
                row.ytm,
                row.benchmark_yield,
                row.credit_spread,
                row.spread_duration,
                row.spread_dv01,
                row.market_value,
                row.weight,
            ):
                _assert_q8(field)

    def test_float_ytm_and_string_curve_values_are_coerced(self):
        """第 77 行对曲线值做 safe_decimal，第 91 行对 ytm 做 safe_decimal（float 经 str 转换）。

        ytm 0.0312(float) → Decimal("0.0312") → 3.12%；曲线 "2.0"/3.0 → 同上 → 3Y 基准 2.5 → 62 bp。
        """
        result = compute_bond_spreads([_bond(ytm=0.0312)], {"1Y": "2.0", "5Y": 3.0})
        assert len(result) == 1
        assert result[0].ytm == D("3.12")
        assert result[0].benchmark_yield == D("2.5")
        assert result[0].credit_spread == D("62")

    def test_actual_maturity_beyond_curve_ends_is_clamped(self):
        """第 214-217 行：目标年限 ≤ 首节点取首节点，≥ 末节点取末节点（平推，不外推）。

        years_to_maturity 0.5 → 2.0 → spread = (3.12 − 2.0)×100 = 112 bp；
        years_to_maturity 8 → 3.0 → spread = (3.12 − 3.0)×100 = 12 bp。
        """
        short, long = compute_bond_spreads(
            [
                _bond(instrument_code="S", years_to_maturity=D("0.5")),
                _bond(instrument_code="L", years_to_maturity=8),
            ],
            TWO_POINT_CURVE,
        )
        assert short.benchmark_yield == D("2.0")
        assert short.credit_spread == D("112")
        assert long.benchmark_yield == D("3.0")
        assert long.credit_spread == D("12")

    def test_missing_optional_fields_default_to_zero_or_empty(self):
        """第 112/116-118 行：modified_duration 缺失 → spread_duration 0、dv01 0；code/name/rating 缺失 → ""。"""
        (row,) = compute_bond_spreads(
            [
                _bond(
                    instrument_code=None,
                    instrument_name=None,
                    rating=None,
                    modified_duration=None,
                )
            ],
            TWO_POINT_CURVE,
        )
        assert row.instrument_code == ""
        assert row.instrument_name == ""
        assert row.rating == ""
        assert row.spread_duration == D("0")
        assert row.spread_dv01 == D("0")


# ---------------------------------------------------------------------------
# 2. _normalize_ytm_to_pct 输入形态
# ---------------------------------------------------------------------------


class TestNormalizeYtmToPct:
    def test_decimal_form_is_multiplied_by_100(self):
        """第 243 行：小数口径 0.0312 → 3.12。"""
        assert _normalize_ytm_to_pct(D("0.0312")) == D("3.12")

    def test_float_and_string_inputs_are_coerced_via_safe_decimal(self):
        """第 238 行 safe_decimal：float 经 str() 转换，字符串直接 Decimal()。"""
        assert _normalize_ytm_to_pct(0.0312) == D("3.12")
        assert _normalize_ytm_to_pct("0.0312") == D("3.12")

    def test_percent_form_is_rejected_as_dirty_data(self):
        """第 241-242 行：|ytm| > 0.2 视为脏数据返回 None（3.12 为百分数误存）。"""
        assert _normalize_ytm_to_pct(D("3.12")) is None
        assert _normalize_ytm_to_pct(3.12) is None
        assert _normalize_ytm_to_pct(D("0.21")) is None

    def test_threshold_0_2_is_inclusive(self):
        """第 241 行用严格大于：恰好 0.2 仍按小数口径 ×100 → 20；0.20000001 → None。"""
        assert _normalize_ytm_to_pct(D("0.2")) == D("20")
        assert _normalize_ytm_to_pct(D("0.20000001")) is None

    def test_negative_values_follow_same_rule(self):
        """第 241 行取绝对值：-0.05 → -5；-0.25 → None。"""
        assert _normalize_ytm_to_pct(D("-0.05")) == D("-5")
        assert _normalize_ytm_to_pct(D("-0.25")) is None

    def test_zero_returns_zero(self):
        """第 239-240 行：0 短路返回 Decimal("0")。"""
        result = _normalize_ytm_to_pct(D("0"))
        assert result == D("0")
        assert result is not None

    def test_missing_ytm_is_unavailable(self):
        assert _normalize_ytm_to_pct(None) is None

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), D("NaN"), D("-Infinity"), "not-a-number", ""])
    def test_invalid_ytm_is_unavailable(self, value):
        assert _normalize_ytm_to_pct(value) is None


# ---------------------------------------------------------------------------
# 3. 基准收益率解析
# ---------------------------------------------------------------------------


class TestResolveBenchmarkYield:
    def test_direct_hit_returns_curve_value(self):
        """第 195-197 行：tenor_bucket 命中直接返回 safe_decimal 后的值。"""
        assert _resolve_benchmark_yield({"1Y": D("2.0"), "5Y": D("3.0")}, "1Y") == D("2.0")
        assert _resolve_benchmark_yield({"1Y": "2.0", "5Y": "3.0"}, "5Y") == D("3.0")

    def test_miss_falls_back_to_interpolation_between_nodes(self):
        """第 198-199 行：未命中 → build_curve_points + interpolate_rate。

        两节点走线性：3Y 在 1Y-5Y 中点 → 2.0 + 0.5 × 1.0 = 2.5。
        """
        assert _resolve_benchmark_yield(TWO_POINT_CURVE, "3Y") == D("2.5")

    def test_miss_outside_nodes_is_clamped_flat(self):
        """第 199 行 interpolate_rate 两端平推：1M → 2.0，10Y → 3.0。"""
        assert _resolve_benchmark_yield(TWO_POINT_CURVE, "1M") == D("2.0")
        assert _resolve_benchmark_yield(TWO_POINT_CURVE, "10Y") == D("3.0")

    def test_unknown_tenor_label_raises_value_error(self):
        """第 199 行 tenor_to_years 对词表外标签抛 ValueError（不静默映射）。"""
        with pytest.raises(ValueError, match="Unknown curve tenor label"):
            _resolve_benchmark_yield(TWO_POINT_CURVE, "8Y")


class TestResolveActualMaturityBenchmarkYield:
    def test_linear_interpolation_between_nodes(self):
        """第 219-227 行：2Y → 2.0 + 1.0 × 1.0 / 4.0 = 2.25；2.5Y → 2.0 + 1.0 × 1.5 / 4.0 = 2.375。"""
        assert _resolve_actual_maturity_benchmark_yield(TWO_POINT_CURVE, 2) == D("2.25")
        assert _resolve_actual_maturity_benchmark_yield(TWO_POINT_CURVE, 2.5) == D("2.375")

    def test_string_years_are_coerced(self):
        """第 206 行 safe_decimal："3" → 3 → 2.5。"""
        assert _resolve_actual_maturity_benchmark_yield(TWO_POINT_CURVE, "3") == D("2.5")

    def test_at_or_beyond_nodes_is_clamped(self):
        """第 214-217 行：≤ 首节点返回首节点值，≥ 末节点返回末节点值（含恰好落在节点上）。"""
        assert _resolve_actual_maturity_benchmark_yield(TWO_POINT_CURVE, 1) == D("2.0")
        assert _resolve_actual_maturity_benchmark_yield(TWO_POINT_CURVE, D("0.25")) == D("2.0")
        assert _resolve_actual_maturity_benchmark_yield(TWO_POINT_CURVE, 5) == D("3.0")
        assert _resolve_actual_maturity_benchmark_yield(TWO_POINT_CURVE, 30) == D("3.0")

    def test_non_positive_or_missing_years_return_none(self):
        """第 206-208 行：None / 0 / 负数 / NaN 经 safe_decimal 后 ≤ 0 → None（交由调用方回退 tenor_bucket）。"""
        assert _resolve_actual_maturity_benchmark_yield(TWO_POINT_CURVE, None) is None
        assert _resolve_actual_maturity_benchmark_yield(TWO_POINT_CURVE, 0) is None
        assert _resolve_actual_maturity_benchmark_yield(TWO_POINT_CURVE, -1) is None
        assert _resolve_actual_maturity_benchmark_yield(TWO_POINT_CURVE, float("nan")) is None

    def test_curve_without_known_tenors_returns_none(self):
        """第 210-212 行：曲线为空或全为词表外标签 → points 为空 → None。"""
        assert _resolve_actual_maturity_benchmark_yield({}, 3) is None
        assert _resolve_actual_maturity_benchmark_yield({"8Y": D("3.0")}, 3) is None


class TestBenchmarkResolutionInsideComputeBondSpreads:
    def test_unknown_tenor_bucket_without_maturity_raises(self):
        """第 107 行回退到 _resolve_benchmark_yield → 第 199 行 tenor_to_years 对 "8Y" 抛 ValueError，
        compute_bond_spreads 不捕获，异常直接向上抛。"""
        with pytest.raises(ValueError, match="Unknown curve tenor label"):
            compute_bond_spreads([_bond(tenor_bucket="8Y", years_to_maturity=None)], TWO_POINT_CURVE)

    def test_curve_with_only_unknown_tenors_is_unavailable(self):
        """曲线没有任何有效期限节点时 fail-closed，不把 0 当作国债收益率继续计算。"""
        assert compute_bond_spreads([_bond(years_to_maturity=None)], {"8Y": D("3.0")}) == []


# ---------------------------------------------------------------------------
# 4. build_spread_term_structure
# ---------------------------------------------------------------------------


class TestBuildSpreadTermStructure:
    def test_market_value_weighted_average_per_bucket_sorted_by_tenor(self):
        """第 137-159 行。3Y 桶：(60×1_000_000 + 90×3_000_000) / 4_000_000 = 82.5；
        1Y 桶单券 → avg = 30。结果按 tenor_to_years 升序排列（1Y 在 3Y 之前，与插入顺序无关）。
        """
        points = build_spread_term_structure(
            [
                _spread_row("3Y", "60", "1000000", code="A"),
                _spread_row("1Y", "30", "500000", code="C"),
                _spread_row("3Y", "90", "3000000", code="B"),
            ]
        )
        assert [p.tenor_bucket for p in points] == ["1Y", "3Y"]

        one_y, three_y = points
        assert one_y == SpreadTermStructurePoint(
            tenor_bucket="1Y",
            avg_spread_bps=D("30.00000000"),
            min_spread_bps=D("30"),
            max_spread_bps=D("30"),
            bond_count=1,
            total_market_value=D("500000.00000000"),
        )
        assert three_y.avg_spread_bps == D("82.5")
        assert three_y.min_spread_bps == D("60")
        assert three_y.max_spread_bps == D("90")
        assert three_y.bond_count == 2
        assert three_y.total_market_value == D("4000000")
        _assert_q8(three_y.avg_spread_bps)
        _assert_q8(three_y.total_market_value)

    def test_sort_uses_tenor_years_not_string_order(self):
        """第 159 行按年限排序："6M"(0.5) < "1Y" < "10Y"，而非字典序 "10Y" < "1Y" < "6M"。"""
        points = build_spread_term_structure(
            [
                _spread_row("10Y", "100", "1"),
                _spread_row("6M", "10", "1"),
                _spread_row("1Y", "20", "1"),
            ]
        )
        assert [p.tenor_bucket for p in points] == ["6M", "1Y", "10Y"]

    def test_empty_input_returns_empty_list(self):
        """第 137-159 行：无行 → 无分组 → []。"""
        assert build_spread_term_structure([]) == []

    def test_zero_total_market_value_bucket_reports_zero_average(self):
        """第 143-145 行：桶内市值合计为 0（+1_000_000 与 −1_000_000 抵消）→ avg 记 0，
        但 min/max/bond_count 仍按行统计。"""
        (point,) = build_spread_term_structure(
            [
                _spread_row("3Y", "100", "1000000"),
                _spread_row("3Y", "50", "-1000000"),
            ]
        )
        assert point.avg_spread_bps == D("0")
        assert point.min_spread_bps == D("50")
        assert point.max_spread_bps == D("100")
        assert point.bond_count == 2
        assert point.total_market_value == D("0")

    def test_unknown_tenor_bucket_raises_on_sort(self):
        """第 159 行排序调用 tenor_to_years，词表外标签抛 ValueError。"""
        with pytest.raises(ValueError, match="Unknown curve tenor label"):
            build_spread_term_structure([_spread_row("8Y", "10", "1")])


# ---------------------------------------------------------------------------
# 5. compute_spread_historical_context 及其辅助函数
# ---------------------------------------------------------------------------

ANCHOR = date(2026, 3, 31)
# 第 252 行：cutoff = anchor − days。365 天 → 2025-03-31；1095 天 → 2023-04-01
# （2023-03-31 至 2024-03-31 含 2024-02-29 共 366 天，故 3 年窗口起点是 4 月 1 日）。
HISTORY: list[tuple[date, Decimal]] = [
    (date(2023, 3, 31), D("500")),  # 3 年窗口外（早于 2023-04-01 一天）
    (date(2023, 4, 1), D("10")),  # 3 年窗口边界（含）
    (date(2024, 9, 30), D("20")),
    (date(2025, 3, 30), D("30")),  # 1 年窗口外一天
    (date(2025, 3, 31), D("40")),  # 1 年窗口边界（含）
    (date(2025, 12, 31), D("60")),
    (ANCHOR, D("50")),
]
# values_1y = [40, 60, 50]；values_3y = [10, 20, 30, 40, 60, 50]


class TestWindowValues:
    def test_cutoff_is_inclusive_and_preserves_input_order(self):
        """第 252-253 行：point_date >= cutoff 保留，顺序沿用输入顺序（不排序）。"""
        assert _window_values(HISTORY, anchor_date=ANCHOR, days=365) == [D("40"), D("60"), D("50")]
        assert _window_values(HISTORY, anchor_date=ANCHOR, days=365 * 3) == [
            D("10"),
            D("20"),
            D("30"),
            D("40"),
            D("60"),
            D("50"),
        ]

    def test_values_are_coerced_and_missing_or_non_finite_values_are_excluded(self):
        history: list[tuple[date, Any]] = [
            (ANCHOR, "55"),
            (ANCHOR, None),
            (ANCHOR, 12.5),
            (ANCHOR, D("NaN")),
            (ANCHOR, D("Infinity")),
        ]
        assert _window_values(history, anchor_date=ANCHOR, days=1) == [D("55"), D("12.5")]

    def test_empty_history(self):
        assert _window_values([], anchor_date=ANCHOR, days=365) == []


class TestPercentile:
    def test_empty_returns_none(self):
        """第 257-258 行。"""
        assert _percentile(D("1"), []) is None

    def test_inclusive_empirical_cdf_in_percent(self):
        """第 259-260 行：count(v <= current) / n × 100，量化 8 位。
        [40, 60, 50] 对 45 → 1/3 → 33.33333333；[10,20,30,40,60,50] 对 45 → 4/6 → 66.66666667。"""
        result_1y = _percentile(D("45"), [D("40"), D("60"), D("50")])
        assert result_1y == D("33.33333333")
        _assert_q8(result_1y)
        assert _percentile(D("45"), [D("10"), D("20"), D("30"), D("40"), D("60"), D("50")]) == D("66.66666667")

    def test_current_equal_to_extremes(self):
        """第 259 行用 <=：等于最大值 → 100；等于最小值 → 1/n（不是 0）；低于全部 → 0。"""
        values = [D("40"), D("60"), D("50")]
        assert _percentile(D("60"), values) == D("100")
        assert _percentile(D("40"), values) == D("33.33333333")
        assert _percentile(D("39.99"), values) == D("0")

    def test_single_element(self):
        assert _percentile(D("50"), [D("50")]) == D("100")
        assert _percentile(D("49"), [D("50")]) == D("0")


class TestMedian:
    def test_empty_returns_none(self):
        """第 264-265 行。"""
        assert _median([]) is None

    def test_single_element(self):
        assert _median([D("7")]) == D("7")

    def test_odd_count_takes_middle(self):
        """第 266 行 statistics.median：[40, 60, 50] 排序后中位 50。"""
        assert _median([D("40"), D("60"), D("50")]) == D("50")

    def test_even_count_averages_two_middles(self):
        """第 266 行：6 个值排序 [10,20,30,40,50,60] → (30+40)/2 = 35。"""
        assert _median([D("10"), D("20"), D("30"), D("40"), D("60"), D("50")]) == D("35")


class TestComputeSpreadHistoricalContext:
    def test_empty_history_returns_all_none_with_quantized_current(self):
        """第 168-177 行。current 45.123456789 → 第 170 行 _q8 → 45.12345679（ROUND_HALF_UP）。"""
        ctx = compute_spread_historical_context(D("45.123456789"), [])
        assert ctx == SpreadHistoricalContext(
            current_spread_bps=D("45.12345679"),
            percentile_1y=None,
            percentile_3y=None,
            median_1y=None,
            median_3y=None,
            min_1y=None,
            max_1y=None,
        )

    def test_history_with_no_valid_observations_returns_none_statistics(self):
        ctx = compute_spread_historical_context(
            D("45"),
            [(ANCHOR, None), (ANCHOR, D("NaN")), (ANCHOR, D("-Infinity"))],
        )
        assert ctx.percentile_1y is None
        assert ctx.percentile_3y is None
        assert ctx.median_1y is None
        assert ctx.median_3y is None
        assert ctx.min_1y is None
        assert ctx.max_1y is None

    def test_windows_anchor_on_latest_history_date(self):
        """第 179-191 行；窗口以历史序列中最大日期为锚（第 179 行），非今日。

        values_1y = [40, 60, 50]：percentile(45) = 33.33333333，median 50，min 40，max 60。
        values_3y = [10, 20, 30, 40, 60, 50]：percentile(45) = 66.66666667，median 35。
        """
        ctx = compute_spread_historical_context(D("45"), HISTORY)
        assert ctx.current_spread_bps == D("45")
        _assert_q8(ctx.current_spread_bps)
        assert ctx.percentile_1y == D("33.33333333")
        assert ctx.percentile_3y == D("66.66666667")
        assert ctx.median_1y == D("50")
        assert ctx.median_3y == D("35")
        assert ctx.min_1y == D("40")
        assert ctx.max_1y == D("60")

    def test_current_equal_to_window_extremes(self):
        """第 185 行 _percentile 的 <= 语义：current = 1 年最大值 60 → 100；current = 1 年最小值 40 → 33.33333333。"""
        assert compute_spread_historical_context(D("60"), HISTORY).percentile_1y == D("100")
        assert compute_spread_historical_context(D("40"), HISTORY).percentile_1y == D("33.33333333")

    def test_single_point_history(self):
        """单点历史：1 年与 3 年窗口相同，percentile 由 <= 决定，median/min/max 均为该点。"""
        ctx = compute_spread_historical_context(D("50"), [(ANCHOR, D("50"))])
        assert ctx.percentile_1y == D("100")
        assert ctx.percentile_3y == D("100")
        assert ctx.median_1y == D("50")
        assert ctx.median_3y == D("50")
        assert ctx.min_1y == D("50")
        assert ctx.max_1y == D("50")

    def test_stale_history_is_still_fully_inside_window(self):
        """第 179 行锚点取历史最大日期：即便整段历史停在 2020 年，1 年窗口仍相对于 2020-12-31 计算，
        两个点都被视为"近 1 年"。"""
        ctx = compute_spread_historical_context(
            D("10"),
            [(date(2020, 6, 30), D("10")), (date(2020, 12, 31), D("20"))],
        )
        assert ctx.median_1y == D("15")
        assert ctx.min_1y == D("10")
        assert ctx.max_1y == D("20")
        assert ctx.percentile_1y == D("50")

    def test_input_order_does_not_matter_for_anchor(self):
        """第 179 行用 max() 取锚，历史序列无需按日期排序。"""
        reversed_history = list(reversed(HISTORY))
        assert compute_spread_historical_context(D("45"), reversed_history) == compute_spread_historical_context(
            D("45"), HISTORY
        )


class TestSpreadHistoryObservationCounts:
    def test_counts_follow_the_same_windows_as_the_context(self):
        """HISTORY 的 1 年窗有 3 个点、3 年窗有 6 个点，与 compute_spread_historical_context 同窗。"""
        assert spread_history_observation_counts(HISTORY) == (3, 6)

    def test_missing_and_non_finite_values_are_not_counted(self):
        history: list[tuple[date, Any]] = [
            (ANCHOR, D("50")),
            (ANCHOR, None),
            (ANCHOR, D("NaN")),
            (ANCHOR, D("Infinity")),
        ]
        assert spread_history_observation_counts(history) == (1, 1)

    def test_empty_history_counts_zero(self):
        assert spread_history_observation_counts([]) == (0, 0)


class TestCurveHasUsableTenors:
    @pytest.mark.parametrize(
        "invalid_rate",
        [None, D("NaN"), D("sNaN"), D("Infinity"), D("-Infinity"), float("nan"), float("inf"), "bad", ""],
    )
    def test_known_tenor_with_invalid_rate_is_unusable(self, invalid_rate):
        curve = {"3Y": invalid_rate}
        assert curve_has_usable_tenors(curve) is False
        assert compute_bond_spreads([_bond(ytm=D("0.03"))], curve) == []

    @pytest.mark.parametrize("maturity", [None, D("3")])
    def test_invalid_node_is_excluded_from_interpolation(self, maturity):
        curve = {**TWO_POINT_CURVE, "3Y": D("NaN")}
        assert curve_has_usable_tenors(curve) is True
        (row,) = compute_bond_spreads([_bond(ytm=D("0.03"), years_to_maturity=maturity)], curve)
        assert row.benchmark_yield == D("2.5")
        assert row.credit_spread == D("50")

    @pytest.mark.parametrize("rate", [D("0"), D("-0.5"), "0", "-0.5"])
    def test_observed_zero_and_negative_rates_are_preserved(self, rate):
        curve = {"3Y": rate}
        assert curve_has_usable_tenors(curve) is True
        (row,) = compute_bond_spreads([_bond(ytm=D("0.03"))], curve)
        assert row.benchmark_yield == D(rate)
        assert row.credit_spread == (D("3") - D(rate)) * D("100")

    def test_known_tenor_curve_is_usable(self):
        assert curve_has_usable_tenors(TWO_POINT_CURVE) is True

    def test_only_unknown_tenor_labels_is_unusable(self):
        """与 compute_bond_spreads 对同一曲线 fail-closed 返回 [] 的判定一致。"""
        assert curve_has_usable_tenors({"8Y": D("3.0")}) is False
        assert compute_bond_spreads([_bond(years_to_maturity=None)], {"8Y": D("3.0")}) == []

    def test_mixed_labels_keep_the_known_node(self):
        assert curve_has_usable_tenors({"8Y": D("3.0"), "1Y": D("2.0")}) is True

    def test_empty_curve_is_unusable(self):
        assert curve_has_usable_tenors({}) is False


# ---------------------------------------------------------------------------
# 6. compute_bond_spreads 的行过滤与异常输入
# ---------------------------------------------------------------------------


class TestComputeBondSpreadsFiltering:
    def test_empty_inputs_return_empty_list(self):
        """第 74-75 行：bond_rows 或 treasury_curve 为空 → []。"""
        assert compute_bond_spreads([], TWO_POINT_CURVE) == []
        assert compute_bond_spreads([_bond()], {}) == []

    def test_non_credit_rows_are_skipped_case_sensitively(self):
        """第 85 行：asset_class_std 需 strip 后**恰好**等于 "credit"；"rate"、"Credit"、None 均跳过，
        " credit " 保留。"""
        result = compute_bond_spreads(
            [
                _bond(instrument_code="RATE", asset_class_std="rate"),
                _bond(instrument_code="CAP", asset_class_std="Credit"),
                _bond(instrument_code="NONE", asset_class_std=None),
                _bond(instrument_code="PADDED", asset_class_std=" credit "),
            ],
            TWO_POINT_CURVE,
        )
        assert [r.instrument_code for r in result] == ["PADDED"]
        assert result[0].weight == D("1")

    def test_blank_tenor_bucket_is_skipped(self):
        """第 86 行：tenor_bucket None / "" / 纯空白 → 跳过。"""
        result = compute_bond_spreads(
            [
                _bond(instrument_code="N", tenor_bucket=None),
                _bond(instrument_code="E", tenor_bucket=""),
                _bond(instrument_code="W", tenor_bucket="   "),
                _bond(instrument_code="OK"),
            ],
            TWO_POINT_CURVE,
        )
        assert [r.instrument_code for r in result] == ["OK"]

    def test_none_ytm_and_percent_form_ytm_are_skipped(self):
        """第 87 行 ytm is None → 跳过；第 91-93 行 3.12（百分数形式）→ _normalize 返回 None → 跳过。"""
        result = compute_bond_spreads(
            [
                _bond(instrument_code="NONE", ytm=None),
                _bond(instrument_code="PCT", ytm=D("3.12")),
                _bond(instrument_code="OK"),
            ],
            TWO_POINT_CURVE,
        )
        assert [r.instrument_code for r in result] == ["OK"]

    def test_zero_ytm_is_kept_and_yields_negative_spread(self):
        """第 87 行只拦 None；ytm 0 经第 239-240 行返回 Decimal("0")（非 None）→ 行保留，
        credit_spread = (0 − 2.5) × 100 = −250 bp。"""
        (row,) = compute_bond_spreads([_bond(ytm=D("0"))], TWO_POINT_CURVE)
        assert row.ytm == D("0")
        assert row.credit_spread == D("-250")

    def test_invalid_ytm_is_excluded_without_diluting_observed_weights(self):
        rows = compute_bond_spreads(
            [_bond(instrument_code="INVALID", ytm=float("nan")), _bond(instrument_code="OBSERVED")],
            TWO_POINT_CURVE,
        )
        assert [row.instrument_code for row in rows] == ["OBSERVED"]
        assert rows[0].weight == D("1")

    def test_zero_or_missing_market_value_is_skipped(self):
        """第 88 行：safe_decimal(market_value) == 0 → 跳过（None 归 0 亦跳过）。"""
        result = compute_bond_spreads(
            [
                _bond(instrument_code="ZERO", market_value=D("0")),
                _bond(instrument_code="NONE", market_value=None),
                _bond(instrument_code="OK"),
            ],
            TWO_POINT_CURVE,
        )
        assert [r.instrument_code for r in result] == ["OK"]

    def test_negative_market_value_is_kept_with_negative_weight(self):
        """第 88 行只拦 == 0，负市值保留。total_credit_mv = 3_000_000 − 1_000_000 = 2_000_000（第 95 行）；
        weight A = 1.5、B = −0.5（第 126 行）；B 无 face_value → 回退负市值 → dv01 = −1_000_000 × 2 / 10000 = −200。"""
        a, b = compute_bond_spreads(
            [
                _bond(instrument_code="A", market_value=D("3000000")),
                _bond(
                    instrument_code="B",
                    market_value=D("-1000000"),
                    face_value=None,
                    modified_duration=D("2"),
                ),
            ],
            TWO_POINT_CURVE,
        )
        assert a.weight == D("1.5")
        assert b.weight == D("-0.5")
        assert b.market_value == D("-1000000")
        assert b.spread_dv01 == D("-200")

    def test_candidates_netting_to_zero_market_value_return_empty(self):
        """第 95-97 行：候选行市值合计为 0（+1_000_000 与 −1_000_000）→ 返回 []（避免除零）。"""
        result = compute_bond_spreads(
            [
                _bond(instrument_code="A", market_value=D("1000000")),
                _bond(instrument_code="B", market_value=D("-1000000")),
            ],
            TWO_POINT_CURVE,
        )
        assert result == []

    def test_skipped_rows_do_not_dilute_weights(self):
        """第 95 行 total_credit_mv 只累计候选行；被跳过的利率债不参与分母，剩余两券权重之和为 1。"""
        rows = compute_bond_spreads(
            [
                _bond(instrument_code="A", market_value=D("1000000")),
                _bond(instrument_code="B", market_value=D("3000000")),
                _bond(instrument_code="RATE", asset_class_std="rate", market_value=D("96000000")),
            ],
            TWO_POINT_CURVE,
        )
        assert [r.instrument_code for r in rows] == ["A", "B"]
        assert sum((r.weight for r in rows), D("0")) == D("1")


class TestQ8:
    def test_rounds_half_up_to_8_places(self):
        """第 269-270 行：ROUND_HALF_UP 量化到 1e-8。"""
        assert _q8(D("1.000000005")) == D("1.00000001")
        assert _q8(D("1.000000004")) == D("1.00000000")
        assert _q8(D("-1.000000005")) == D("-1.00000001")
        _assert_q8(_q8(D("7")))
