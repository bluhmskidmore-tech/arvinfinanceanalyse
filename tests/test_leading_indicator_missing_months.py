"""宏观 M-1：领先指标缺失月不得以 0 污染历史均值（commit 89b45263c honesty）。

锁定行为：
- 稀疏月度序列中缺失字段保留为 None（不 zero-fill）
- `_history_mean` / 分项得分只对可用月求均值
- `history_samples` 披露 used/total
- 缺失月触发 `*_HISTORY_MISSING_MONTHS` 警告
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.macro.leading_indicator import (
    _history_mean,
    _monthly_series,
    compute_leading_indicator,
)


def _row(
    trade_date: date,
    *,
    pmi: float | None = 50.0,
    m2_yoy: float | None = 8.0,
    social_financing_yoy: float | None = 8.0,
    term_spread_10y_1y: float | None = 60.0,
    credit_spread_aaa_3y: float | None = 40.0,
    brent_oil: float | None = 80.0,
) -> dict[str, object]:
    return {
        "trade_date": trade_date,
        "pmi": pmi,
        "m2_yoy": m2_yoy,
        "social_financing_yoy": social_financing_yoy,
        "term_spread_10y_1y": term_spread_10y_1y,
        "credit_spread_aaa_3y": credit_spread_aaa_3y,
        "brent_oil": brent_oil,
    }


def test_history_mean_skips_none_months() -> None:
    mean, used, total = _history_mean([Decimal("10"), None, Decimal("20"), None])
    assert mean == Decimal("15")
    assert used == 2
    assert total == 4

    # 对照：若把 None 当成 0 再求均值，会被拉向 0。
    zero_filled = (Decimal("10") + Decimal("0") + Decimal("20") + Decimal("0")) / Decimal("4")
    assert mean != zero_filled
    assert mean > zero_filled


def test_monthly_series_keeps_missing_as_none() -> None:
    rows = [
        _row(date(2026, 3, 31), pmi=50.0, m2_yoy=None, social_financing_yoy=8.0, brent_oil=80.0),
        _row(date(2026, 2, 28), pmi=None, m2_yoy=9.0, social_financing_yoy=None, brent_oil=None),
    ]
    series = _monthly_series(rows)

    assert series["m2"][0] is None
    assert series["m2"][1] == Decimal("9")
    assert series["sf"][1] is None
    assert series["pmi"][1] is None
    assert series["oil"][1] is None


def test_compute_leading_indicator_missing_months_do_not_zero_fill_mean() -> None:
    """稀疏历史月：均值只用可用月；得分不得被缺失月的假 0 拉偏。"""
    # newest-first，与 `_monthly_series` / `compute_leading_indicator` 约定一致
    rows = [
        # current
        _row(
            date(2026, 3, 31),
            pmi=51.0,
            m2_yoy=12.0,
            social_financing_yoy=10.0,
            brent_oil=84.0,
        ),
        # history: missing m2 / sf / oil / pmi
        _row(
            date(2026, 2, 28),
            pmi=None,
            m2_yoy=None,
            social_financing_yoy=None,
            brent_oil=None,
        ),
        # history: available
        _row(
            date(2026, 1, 31),
            pmi=50.0,
            m2_yoy=8.0,
            social_financing_yoy=6.0,
            brent_oil=80.0,
        ),
        # history: missing again
        _row(
            date(2025, 12, 31),
            pmi=49.0,
            m2_yoy=None,
            social_financing_yoy=None,
            brent_oil=None,
        ),
    ]

    result = compute_leading_indicator(rows, date(2026, 3, 31))

    # history window = months after current → 3 months; only 1 available for m2/sf/oil
    assert result["history_samples"] == {
        "m2_yoy": {"used": 1, "total": 3},
        "social_financing_yoy": {"used": 1, "total": 3},
        "commodity": {"used": 1, "total": 3},
    }
    assert "M2_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert "SOCIAL_FINANCING_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert "COMMODITY_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert result["data_status"] == "degraded"

    # Honest means use only the available history month (8 / 6 / 80).
    honest_m2_score = Decimal("50") + (Decimal("12") - Decimal("8")) * Decimal("5")  # 70
    honest_sf_score = Decimal("50") + (Decimal("10") - Decimal("6")) * Decimal("5")  # 70
    honest_commodity = Decimal("50") + (Decimal("84") - Decimal("80")) / Decimal("80") * Decimal(
        "500"
    )  # 75
    honest_commodity = max(Decimal("0"), min(Decimal("100"), honest_commodity))

    assert Decimal(str(result["m2_score"])) == honest_m2_score
    assert Decimal(str(result["social_financing_score"])) == honest_sf_score
    assert Decimal(str(result["commodity_score"])) == honest_commodity

    # Zero-fill counterfactual: treat missing history months as 0 → mean pulled toward 0 → scores inflate.
    zero_fill_m2_avg = (Decimal("0") + Decimal("8") + Decimal("0")) / Decimal("3")
    zero_fill_m2_score = Decimal("50") + (Decimal("12") - zero_fill_m2_avg) * Decimal("5")
    zero_fill_m2_score = max(Decimal("0"), min(Decimal("100"), zero_fill_m2_score))
    assert Decimal(str(result["m2_score"])) != zero_fill_m2_score
    assert Decimal(str(result["m2_score"])) < zero_fill_m2_score

    zero_fill_sf_avg = (Decimal("0") + Decimal("6") + Decimal("0")) / Decimal("3")
    zero_fill_sf_score = Decimal("50") + (Decimal("10") - zero_fill_sf_avg) * Decimal("5")
    zero_fill_sf_score = max(Decimal("0"), min(Decimal("100"), zero_fill_sf_score))
    assert Decimal(str(result["social_financing_score"])) != zero_fill_sf_score

    zero_fill_oil_avg = (Decimal("0") + Decimal("80") + Decimal("0")) / Decimal("3")
    zero_fill_commodity = Decimal("50") + (Decimal("84") - zero_fill_oil_avg) / zero_fill_oil_avg * Decimal(
        "500"
    )
    zero_fill_commodity = max(Decimal("0"), min(Decimal("100"), zero_fill_commodity))
    assert Decimal(str(result["commodity_score"])) != zero_fill_commodity


def test_compute_leading_indicator_discloses_history_sample_counts_when_all_history_missing() -> None:
    rows = [
        _row(date(2026, 3, 31), m2_yoy=10.0, social_financing_yoy=8.0, brent_oil=80.0),
        _row(
            date(2026, 2, 28),
            m2_yoy=None,
            social_financing_yoy=7.0,
            brent_oil=70.0,
        ),
    ]
    result = compute_leading_indicator(rows, date(2026, 3, 31))

    assert result["history_samples"]["m2_yoy"] == {"used": 0, "total": 1}
    assert result["history_samples"]["social_financing_yoy"] == {"used": 1, "total": 1}
    assert result["history_samples"]["commodity"] == {"used": 1, "total": 1}
    assert "M2_HISTORY_MISSING_MONTHS" in result["warnings"]
    assert "SOCIAL_FINANCING_HISTORY_MISSING_MONTHS" not in result["warnings"]
    assert "COMMODITY_HISTORY_MISSING_MONTHS" not in result["warnings"]
    # 无可用历史均值时回落中性 50，而不是用 0 当均值算出极端分。
    assert Decimal(str(result["m2_score"])) == Decimal("50")
