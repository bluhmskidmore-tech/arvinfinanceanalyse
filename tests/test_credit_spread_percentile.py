"""M16 信用利差历史分位（compute_credit_spread_percentile）单测。

覆盖：
- hist_3y / hist_1y 分母排除当日观测（回归 bug：当日曾混入自身对比样本）
- 当日值为历史最大/最小时分位分别为 100 / 0
- 无历史数据时的 unavailable 降级行为
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.app.core_finance.macro.credit_spread_percentile import (
    compute_credit_spread_percentile,
)

pytestmark = pytest.mark.unit

REPORT_DATE = date(2024, 6, 30)


def _curve_row(biz_date: date, curve_id: str, tenor: str, rate_value: Decimal) -> dict[str, object]:
    return {
        "biz_date": biz_date,
        "curve_id": curve_id,
        "tenor": tenor,
        "rate_value": rate_value,
    }


def _aaa_spread_rows(biz_date: date, spread_bp: float) -> list[dict[str, object]]:
    """构造单日 CN_GOVT/CN_CREDIT_AAA 3Y 曲线行，使 credit_spread_aaa_3y = spread_bp。

    _spread_snapshot_for_date 中 credit_spread_aaa_3y = (aaa_3y - gov_3y) * 100（bp）。
    固定 gov_3y=0，则 aaa_3y = spread_bp / 100 即可得到目标 bp 值。
    """
    gov = Decimal("0")
    aaa = Decimal(str(spread_bp)) / Decimal("100")
    return [
        _curve_row(biz_date, "CN_GOVT", "3Y", gov),
        _curve_row(biz_date, "CN_CREDIT_AAA", "3Y", aaa),
    ]


def _find_spread(result: dict[str, object], key: str) -> dict[str, object]:
    for item in result["spreads"]:
        if item["key"] == key:
            return item
    raise AssertionError(f"spread {key!r} not found in result: {result['spreads']!r}")


class TestExcludesTodayFromComparisonSample:
    def test_pct_3y_and_pct_1y_denominators_exclude_today(self) -> None:
        rows: list[dict[str, object]] = []
        # 当日观测：aaa_3y 利差 = 30bp。
        rows += _aaa_spread_rows(REPORT_DATE, 30.0)
        # 近 5 个交易日（均在 1y 窗口内）：10/20/30/40/50 bp。
        near_values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for offset, value in enumerate(near_values, start=1):
            rows += _aaa_spread_rows(REPORT_DATE - timedelta(days=offset), value)
        # 一个仅落在 3y 窗口、超出 1y cutoff 的历史观测：90bp（400 天前，超过 365 天）。
        rows += _aaa_spread_rows(REPORT_DATE - timedelta(days=400), 90.0)

        result = compute_credit_spread_percentile(rows, REPORT_DATE)

        aaa = _find_spread(result, "credit_spread_aaa_3y")
        assert aaa["current_bp"] == 30.0

        # hist_3y（排除当日）= [10,20,30,40,50,90]，below(<30)=2，len=6 -> 33.3
        assert aaa["percentile_3y"] == 33.3
        # hist_1y（排除当日，且排除 400 天前样本）= [10,20,30,40,50]，below(<30)=2，len=5 -> 40.0
        assert aaa["percentile_1y"] == 40.0

        assert aaa["stats_3y"] == {"min": 10.0, "max": 90.0, "median": 40.0, "mean": 40.0}
        assert aaa["stats_1y"] == {"min": 10.0, "max": 50.0, "median": 30.0, "mean": 30.0}

        # pct_3y=33.3 不落入 <=25 或 >=75，估值应为中性。
        assert aaa["valuation"] == "中性"

    def test_regression_would_fail_with_buggy_denominator(self) -> None:
        """显式验证：若当日观测（bug）混入分母，percentile_3y 会是 33.3 之外的其他值(约 22.2)。

        本用例用不同数值组合，进一步确认修复后的分子/分母语义正确，
        而非恰好与旧 bug 巧合相同。
        """
        rows: list[dict[str, object]] = []
        rows += _aaa_spread_rows(REPORT_DATE, 50.0)
        # 8 个历史观测，全部小于当日值 50 -> 正确分位应为 100。
        for offset, value in enumerate([5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0], start=1):
            rows += _aaa_spread_rows(REPORT_DATE - timedelta(days=offset), value)

        result = compute_credit_spread_percentile(rows, REPORT_DATE)
        aaa = _find_spread(result, "credit_spread_aaa_3y")

        # 修复后：below=8, len=8 -> 100.0
        # 若当日值(50)错误地混入分母：below=8, len=9 -> 88.9（不等于 100）
        assert aaa["percentile_3y"] == 100.0
        assert aaa["percentile_1y"] == 100.0


class TestPercentileBoundaries:
    def test_today_value_is_history_max_percentile_is_100(self) -> None:
        rows: list[dict[str, object]] = []
        rows += _aaa_spread_rows(REPORT_DATE, 100.0)
        for offset, value in enumerate([10.0, 20.0, 30.0], start=1):
            rows += _aaa_spread_rows(REPORT_DATE - timedelta(days=offset), value)

        result = compute_credit_spread_percentile(rows, REPORT_DATE)
        aaa = _find_spread(result, "credit_spread_aaa_3y")

        assert aaa["percentile_3y"] == 100.0
        assert aaa["percentile_1y"] == 100.0
        assert aaa["valuation"] == "偏贵"

    def test_today_value_is_history_min_percentile_is_0(self) -> None:
        rows: list[dict[str, object]] = []
        rows += _aaa_spread_rows(REPORT_DATE, 0.0)
        for offset, value in enumerate([10.0, 20.0, 30.0], start=1):
            rows += _aaa_spread_rows(REPORT_DATE - timedelta(days=offset), value)

        result = compute_credit_spread_percentile(rows, REPORT_DATE)
        aaa = _find_spread(result, "credit_spread_aaa_3y")

        assert aaa["percentile_3y"] == 0.0
        assert aaa["percentile_1y"] == 0.0
        assert aaa["valuation"] == "偏便宜"


class TestNoHistoryDataUnavailable:
    def test_empty_curve_rows_returns_unavailable(self) -> None:
        result = compute_credit_spread_percentile([], REPORT_DATE)

        assert result["data_status"] == "unavailable"
        assert result["spreads"] == []
        assert result["overall_valuation"] == "未知"
        assert result["warnings"] == ["NO_CURVE_HISTORY"]
        assert result["report_date"] == REPORT_DATE.isoformat()

    def test_only_future_dated_rows_returns_unavailable(self) -> None:
        rows = _aaa_spread_rows(REPORT_DATE + timedelta(days=1), 30.0)

        result = compute_credit_spread_percentile(rows, REPORT_DATE)

        assert result["data_status"] == "unavailable"
        assert result["spreads"] == []
        assert result["warnings"] == ["NO_CURVE_HISTORY"]
