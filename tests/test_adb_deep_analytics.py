"""Unit tests for ADB deep-insight pure calculations (core_finance/adb_deep_analytics.py).

Contract: docs/plans/2026-08-13-average-balance-deep-analysis-prd.md §4（口径）/ §5（结构）。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta

import pandas as pd
import pytest

from backend.app.core_finance.adb_deep_analytics import (
    AdbSideInput,
    AdbWindowInput,
    build_adb_insights_payload,
    build_nim_attribution,
    build_scale_attribution,
    build_side_input,
    build_volatility_block,
    compute_comparison_windows,
    shift_date_by_years,
)

CAT_GOV = "\u56fd\u503a"
CAT_FIN = "\u91d1\u878d\u503a"
CAT_NEW = "\u65b0\u589e\u7c7b"
CAT_EXIT = "\u9000\u51fa\u7c7b"
CAT_REPO = "\u5356\u51fa\u56de\u8d2d\u8bc1\u5238"


def _weighted_rate(
    rate_balances: Mapping[str, float],
    rates: Mapping[str, float | None],
) -> float | None:
    denominator = sum(rate_balances.values())
    if denominator <= 0:
        return None
    numerator = sum(balance * float(rates[category]) for category, balance in rate_balances.items())
    return round(numerator / denominator, 4)


def _side(
    *,
    balances: Mapping[str, float] | None = None,
    rates: Mapping[str, float | None] | None = None,
    coverage: float | None = None,
    daily: Mapping[str, Mapping[str, float]] | None = None,
) -> AdbSideInput:
    balance_by_category = dict(balances or {})
    rate_by_category = dict(rates or {})
    rate_balance_by_category = {
        category: value
        for category, value in balance_by_category.items()
        if rate_by_category.get(category) is not None
    }
    daily_category_balances = {day: dict(values) for day, values in (daily or {}).items()}
    return AdbSideInput(
        balance_by_category=balance_by_category,
        rate_balance_by_category=rate_balance_by_category,
        rate_by_category=rate_by_category,
        total_rate=_weighted_rate(rate_balance_by_category, rate_by_category),
        rate_coverage=coverage,
        daily_totals={
            day: float(sum(values.values())) for day, values in daily_category_balances.items()
        },
        daily_category_balances=daily_category_balances,
    )


def _single_category_daily(
    category: str,
    start: date,
    values: list[float],
) -> dict[str, dict[str, float]]:
    return {
        (start + timedelta(days=index)).strftime("%Y-%m-%d"): {category: value}
        for index, value in enumerate(values)
    }


def _window(
    *,
    start: str,
    end: str,
    calendar_days: int,
    assets: AdbSideInput | None = None,
    liabilities: AdbSideInput | None = None,
    has_data: bool = True,
    coverage_days: int = 0,
) -> AdbWindowInput:
    return AdbWindowInput(
        start_date=start,
        end_date=end,
        calendar_days=calendar_days,
        coverage_days=coverage_days,
        has_data=has_data,
        assets=assets or AdbSideInput(),
        liabilities=liabilities or AdbSideInput(),
    )


def _rows_by_category(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["category"]): row for row in rows}


# ---------------------------------------------------------------------------
# 4.1 窗口
# ---------------------------------------------------------------------------


def test_comparison_windows_use_adjacent_equal_span_and_minus_one_year() -> None:
    windows = compute_comparison_windows(date(2026, 3, 1), date(2026, 3, 10))

    assert windows["current"] == (date(2026, 3, 1), date(2026, 3, 10))
    assert windows["qoq"] == (date(2026, 2, 19), date(2026, 2, 28))
    assert windows["yoy"] == (date(2025, 3, 1), date(2025, 3, 10))


def test_leap_day_shifts_back_to_february_28() -> None:
    assert shift_date_by_years(date(2024, 2, 29), -1) == date(2023, 2, 28)
    assert shift_date_by_years(date(2026, 7, 31), -1) == date(2025, 7, 31)


# ---------------------------------------------------------------------------
# Frame aggregation（与 comparison 同源的 enriched frames）
# ---------------------------------------------------------------------------


def test_build_side_input_aggregates_categories_days_and_rate_balance() -> None:
    frame = pd.DataFrame(
        {
            "report_date": pd.to_datetime(["2026-03-01", "2026-03-01", "2026-03-02"]),
            "category": [CAT_GOV, CAT_FIN, CAT_GOV],
            "balance": [100.0, 50.0, 120.0],
            "rate_decimal": [0.025, None, 0.026],
        }
    )

    side = build_side_input([frame], rate_by_category={CAT_GOV: 2.55}, total_rate=2.55, rate_coverage=0.8)

    assert side.balance_by_category == {CAT_GOV: 220.0, CAT_FIN: 50.0}
    assert side.rate_balance_by_category == {CAT_GOV: 220.0, CAT_FIN: 0.0}
    assert side.daily_totals == {"2026-03-01": 150.0, "2026-03-02": 120.0}
    assert side.daily_category_balances["2026-03-01"] == {CAT_GOV: 100.0, CAT_FIN: 50.0}
    assert side.total_rate == 2.55
    assert side.rate_coverage == 0.8


def test_build_side_input_skips_frames_without_enriched_columns() -> None:
    side = build_side_input([pd.DataFrame(), pd.DataFrame({"report_date": ["2026-03-01"]})])

    assert side.balance_by_category == {}
    assert side.daily_totals == {}


def test_build_side_input_excludes_invalid_balances_instead_of_zero_filling() -> None:
    frame = pd.DataFrame(
        {
            "report_date": pd.to_datetime(["2026-03-01", "2026-03-02", "2026-03-03"]),
            "category": ["坏值", "缺失", CAT_GOV],
            "balance": ["not-a-number", None, 120.0],
            "rate_decimal": [0.02, 0.02, 0.026],
        }
    )

    side = build_side_input([frame])

    assert side.balance_by_category == {CAT_GOV: 120.0}
    assert side.daily_totals == {"2026-03-03": 120.0}
    assert side.daily_category_balances == {"2026-03-03": {CAT_GOV: 120.0}}


# ---------------------------------------------------------------------------
# 4.2 规模变动归因
# ---------------------------------------------------------------------------


def _scale_pair() -> tuple[AdbWindowInput, AdbWindowInput]:
    current = _window(
        start="2026-03-01",
        end="2026-03-10",
        calendar_days=10,
        assets=_side(balances={CAT_GOV: 1000.0, CAT_FIN: 500.0, CAT_NEW: 300.0}),
        liabilities=_side(balances={CAT_REPO: 2000.0}),
    )
    prior = _window(
        start="2026-02-19",
        end="2026-02-28",
        calendar_days=10,
        assets=_side(balances={CAT_GOV: 800.0, CAT_FIN: 600.0, CAT_EXIT: 200.0}),
        liabilities=_side(balances={CAT_REPO: 2500.0}),
    )
    return current, prior


def test_scale_attribution_category_deltas_close_on_total_delta() -> None:
    current, prior = _scale_pair()

    attribution = build_scale_attribution(current, prior)

    for side_key, rows_key in (("assets", "asset_contributions"), ("liabilities", "liability_contributions")):
        totals = attribution["side_totals"][side_key]
        rows = attribution[rows_key]
        assert sum(row["delta"] for row in rows) == pytest.approx(totals["delta"], rel=1e-9, abs=1e-9)
        assert totals["current_avg"] - totals["prior_avg"] == pytest.approx(totals["delta"])

    asset_totals = attribution["side_totals"]["assets"]
    assert asset_totals["current_avg"] == pytest.approx(180.0)
    assert asset_totals["prior_avg"] == pytest.approx(160.0)
    assert asset_totals["delta"] == pytest.approx(20.0)
    assert asset_totals["delta_pct"] == pytest.approx(12.5)

    liability_totals = attribution["side_totals"]["liabilities"]
    assert liability_totals["delta"] == pytest.approx(-50.0)
    assert liability_totals["delta_pct"] == pytest.approx(-20.0)


def test_scale_attribution_discloses_entering_and_exiting_categories_as_null() -> None:
    current, prior = _scale_pair()

    attribution = build_scale_attribution(current, prior)
    rows = _rows_by_category(attribution["asset_contributions"])

    assert rows[CAT_NEW]["prior_avg"] is None
    assert rows[CAT_NEW]["current_avg"] == pytest.approx(30.0)
    assert rows[CAT_NEW]["delta"] == pytest.approx(30.0)
    assert rows[CAT_EXIT]["current_avg"] is None
    assert rows[CAT_EXIT]["prior_avg"] == pytest.approx(20.0)
    assert rows[CAT_EXIT]["delta"] == pytest.approx(-20.0)
    assert rows[CAT_GOV]["contribution_pct"] == pytest.approx(100.0)
    assert rows[CAT_NEW]["contribution_pct"] == pytest.approx(150.0)
    assert all(row["side"] == "asset" for row in attribution["asset_contributions"])
    assert all(row["side"] == "liability" for row in attribution["liability_contributions"])


def test_scale_attribution_uses_each_window_own_calendar_denominator() -> None:
    current = _window(
        start="2026-03-01",
        end="2026-03-10",
        calendar_days=10,
        assets=_side(balances={CAT_GOV: 1000.0}),
    )
    prior = _window(
        start="2026-02-01",
        end="2026-02-20",
        calendar_days=20,
        assets=_side(balances={CAT_GOV: 1000.0}),
    )

    totals = build_scale_attribution(current, prior)["side_totals"]["assets"]

    assert totals["current_avg"] == pytest.approx(100.0)
    assert totals["prior_avg"] == pytest.approx(50.0)


def test_scale_attribution_reports_null_pct_when_total_delta_is_zero() -> None:
    flat = _side(balances={CAT_GOV: 1000.0})
    current = _window(start="2026-03-01", end="2026-03-10", calendar_days=10, assets=flat)
    prior = _window(start="2026-02-19", end="2026-02-28", calendar_days=10, assets=flat)

    attribution = build_scale_attribution(current, prior)

    assert attribution["side_totals"]["assets"]["delta"] == pytest.approx(0.0)
    assert attribution["asset_contributions"][0]["contribution_pct"] is None


# ---------------------------------------------------------------------------
# 4.3 NIM 量价归因
# ---------------------------------------------------------------------------


def _nim_pair() -> tuple[AdbWindowInput, AdbWindowInput]:
    current = _window(
        start="2026-03-01",
        end="2026-03-10",
        calendar_days=10,
        assets=_side(balances={"A": 600.0, "B": 400.0}, rates={"A": 3.0, "B": 2.0}, coverage=1.0),
        liabilities=_side(balances={"L1": 800.0, "L2": 200.0}, rates={"L1": 1.7, "L2": 1.0}, coverage=1.0),
    )
    prior = _window(
        start="2026-02-19",
        end="2026-02-28",
        calendar_days=10,
        assets=_side(balances={"A": 500.0, "B": 500.0}, rates={"A": 2.8, "B": 2.2}, coverage=1.0),
        liabilities=_side(balances={"L1": 700.0, "L2": 300.0}, rates={"L1": 1.2, "L2": 0.9}, coverage=1.0),
    )
    return current, prior


def test_nim_attribution_rate_mix_and_residual_close_on_side_total() -> None:
    current, prior = _nim_pair()

    attribution, reason = build_nim_attribution(current, prior)

    assert reason is None
    assert attribution is not None
    for side_key in ("asset_side", "liability_side"):
        side = attribution[side_key]
        assert side["rate_effect_bp"] + side["mix_effect_bp"] + side["residual_bp"] == pytest.approx(
            side["total_effect_bp"], abs=1e-9
        )
        assert sum(row["rate_effect_bp"] for row in side["by_category"]) == pytest.approx(
            side["rate_effect_bp"], abs=1e-9
        )
        assert sum(row["mix_effect_bp"] for row in side["by_category"]) == pytest.approx(
            side["mix_effect_bp"], abs=1e-9
        )

    asset_side = attribution["asset_side"]
    assert asset_side["total_effect_bp"] == pytest.approx(10.0)
    assert asset_side["rate_effect_bp"] == pytest.approx(0.0)
    assert asset_side["mix_effect_bp"] == pytest.approx(6.0)
    assert asset_side["residual_bp"] == pytest.approx(4.0)
    rows = _rows_by_category(asset_side["by_category"])
    assert rows["A"]["share_current"] == pytest.approx(0.6)
    assert rows["A"]["share_prior"] == pytest.approx(0.5)
    assert rows["A"]["rate_effect_bp"] == pytest.approx(10.0)
    assert rows["B"]["rate_effect_bp"] == pytest.approx(-10.0)


def test_nim_identity_holds_between_sides() -> None:
    current, prior = _nim_pair()

    attribution, _reason = build_nim_attribution(current, prior)

    assert attribution is not None
    assert attribution["basis"] == "qoq"
    assert attribution["nim_current"] == pytest.approx(2.6 - 1.56)
    assert attribution["nim_prior"] == pytest.approx(2.5 - 1.11)
    assert attribution["nim_delta_bp"] == pytest.approx(
        attribution["asset_side"]["total_effect_bp"] - attribution["liability_side"]["total_effect_bp"],
        abs=1e-9,
    )
    assert attribution["nim_delta_bp"] == pytest.approx(-35.0)


def test_nim_attribution_handles_entering_and_exiting_categories() -> None:
    current = _window(
        start="2026-03-01",
        end="2026-03-10",
        calendar_days=10,
        assets=_side(balances={"A": 600.0, CAT_NEW: 400.0}, rates={"A": 3.0, CAT_NEW: 4.0}),
        liabilities=_side(balances={"L1": 1000.0}, rates={"L1": 1.5}),
    )
    prior = _window(
        start="2026-02-19",
        end="2026-02-28",
        calendar_days=10,
        assets=_side(balances={"A": 600.0, CAT_EXIT: 400.0}, rates={"A": 3.0, CAT_EXIT: 1.0}),
        liabilities=_side(balances={"L1": 1000.0}, rates={"L1": 1.5}),
    )

    attribution, reason = build_nim_attribution(current, prior)

    assert reason is None
    assert attribution is not None
    asset_side = attribution["asset_side"]
    rows = _rows_by_category(asset_side["by_category"])
    assert rows[CAT_NEW]["share_prior"] is None
    assert rows[CAT_NEW]["rate_prior"] is None
    assert rows[CAT_NEW]["rate_effect_bp"] == pytest.approx(0.0)
    assert rows[CAT_EXIT]["share_current"] is None
    assert rows[CAT_EXIT]["rate_current"] is None
    assert rows[CAT_EXIT]["rate_effect_bp"] == pytest.approx(0.0)
    assert asset_side["rate_effect_bp"] + asset_side["mix_effect_bp"] + asset_side["residual_bp"] == pytest.approx(
        asset_side["total_effect_bp"], abs=1e-9
    )
    assert attribution["nim_delta_bp"] == pytest.approx(
        asset_side["total_effect_bp"] - attribution["liability_side"]["total_effect_bp"], abs=1e-9
    )


def test_nim_attribution_null_when_any_side_rate_missing() -> None:
    current = _window(
        start="2026-03-01",
        end="2026-03-10",
        calendar_days=10,
        assets=_side(balances={"A": 600.0}, rates={"A": 3.0}),
        liabilities=_side(balances={"L1": 500.0}),
    )
    prior = _window(
        start="2026-02-19",
        end="2026-02-28",
        calendar_days=10,
        assets=_side(balances={"A": 600.0}, rates={"A": 2.8}),
        liabilities=_side(balances={"L1": 500.0}, rates={"L1": 1.2}),
    )

    attribution, reason = build_nim_attribution(current, prior)

    assert attribution is None
    assert reason == "rate_unavailable"


# ---------------------------------------------------------------------------
# 4.4 波动与异常
# ---------------------------------------------------------------------------


def _anomaly_series() -> list[float]:
    values = [100.0 + index for index in range(11)]
    values.append(200.0)
    values.extend(201.0 + index for index in range(9))
    return values


def test_volatility_flags_single_day_jump_as_anomaly() -> None:
    window = _window(
        start="2026-03-01",
        end="2026-03-21",
        calendar_days=21,
        assets=_side(daily=_single_category_daily(CAT_GOV, date(2026, 3, 1), _anomaly_series())),
    )

    volatility = build_volatility_block(window)

    assert volatility is not None
    assert volatility["anomaly_detection_available"] is True
    assert [item["date"] for item in volatility["anomalies"]] == ["2026-03-12"]
    anomaly = volatility["anomalies"][0]
    assert anomaly["side"] == "asset"
    assert anomaly["direction"] == "up"
    assert anomaly["delta"] == pytest.approx(90.0)
    assert anomaly["zscore"] == pytest.approx(4.2485, abs=1e-3)
    assert volatility["assets"]["max_daily_change"]["date"] == "2026-03-12"
    assert volatility["assets"]["min"] == {"date": "2026-03-01", "value": 100.0}
    assert volatility["assets"]["max"] == {"date": "2026-03-21", "value": 209.0}
    assert volatility["liabilities"] is None


def test_volatility_reports_unavailable_detection_for_flat_short_series() -> None:
    window = _window(
        start="2026-03-01",
        end="2026-03-03",
        calendar_days=3,
        assets=_side(daily=_single_category_daily(CAT_GOV, date(2026, 3, 1), [100.0, 100.0, 100.0])),
    )

    volatility = build_volatility_block(window)

    assert volatility is not None
    assert volatility["anomaly_detection_available"] is False
    assert volatility["anomalies"] == []
    assert volatility["assets"]["std"] == pytest.approx(0.0)
    assert volatility["assets"]["cv"] == pytest.approx(0.0)


def _month_end_daily() -> dict[str, dict[str, float]]:
    daily = _single_category_daily(CAT_GOV, date(2026, 3, 1), [100.0, 100.0, 100.0, 100.0, 100.0, 130.0])
    daily.update(_single_category_daily(CAT_GOV, date(2026, 4, 1), [100.0, 100.0, 100.0, 100.0, 100.0, 120.0]))
    return daily


def test_volatility_month_end_effect_averages_across_months_and_flags() -> None:
    window = _window(
        start="2026-03-01",
        end="2026-04-06",
        calendar_days=37,
        assets=_side(daily=_month_end_daily()),
        liabilities=_side(
            daily=_single_category_daily(CAT_REPO, date(2026, 3, 1), [200.0] * 6),
        ),
    )

    month_end = build_volatility_block(window)["month_end_effect"]

    assert month_end["assets"]["months_observed"] == 2
    assert month_end["assets"]["uplift_pct"] == pytest.approx(25.0)
    assert month_end["assets"]["flagged"] is True
    assert month_end["liabilities"]["uplift_pct"] == pytest.approx(0.0)
    assert month_end["liabilities"]["flagged"] is False


def test_volatility_month_end_skips_months_with_too_few_observations() -> None:
    window = _window(
        start="2026-03-01",
        end="2026-03-04",
        calendar_days=4,
        assets=_side(daily=_single_category_daily(CAT_GOV, date(2026, 3, 1), [100.0, 100.0, 100.0, 400.0])),
    )

    month_end = build_volatility_block(window)["month_end_effect"]

    assert month_end["assets"] == {"uplift_pct": None, "months_observed": 0, "flagged": False}


# ---------------------------------------------------------------------------
# 4.5 结构集中度
# ---------------------------------------------------------------------------


def test_concentration_reports_hhi_topn_and_movers_between_first_and_last_observation() -> None:
    daily = {
        "2026-03-01": {CAT_GOV: 600.0, CAT_FIN: 300.0, CAT_NEW: 100.0},
        "2026-03-05": {CAT_GOV: 500.0, CAT_FIN: 400.0, CAT_NEW: 100.0},
        "2026-03-10": {CAT_GOV: 800.0, CAT_FIN: 100.0, CAT_NEW: 100.0},
    }
    window = _window(
        start="2026-03-01",
        end="2026-03-10",
        calendar_days=10,
        assets=_side(balances={CAT_GOV: 1900.0}, daily=daily),
    )

    payload = build_adb_insights_payload(
        current=window,
        qoq=_window(start="2026-02-19", end="2026-02-28", calendar_days=10, has_data=False),
        yoy=_window(start="2025-03-01", end="2025-03-10", calendar_days=10, has_data=False),
    )
    assets = payload["concentration"]["assets"]

    assert payload["concentration"]["reason"] is None
    assert assets["start_observation_date"] == "2026-03-01"
    assert assets["end_observation_date"] == "2026-03-10"
    assert assets["hhi_start"] == pytest.approx(0.46)
    assert assets["hhi_end"] == pytest.approx(0.66)
    assert assets["top3_share_start"] == pytest.approx(1.0)
    assert payload["concentration"]["liabilities"] is None
    movers = _rows_by_category(assets["movers"])
    assert movers[CAT_GOV]["delta_pp"] == pytest.approx(20.0)
    assert movers[CAT_FIN]["delta_pp"] == pytest.approx(-20.0)
    assert movers[CAT_NEW]["delta_pp"] == pytest.approx(0.0)
    assert any(item["id"] == "concentration_up" for item in payload["insights"])


def test_concentration_null_with_reason_when_only_one_observation_day() -> None:
    window = _window(
        start="2026-03-01",
        end="2026-03-10",
        calendar_days=10,
        assets=_side(daily={"2026-03-01": {CAT_GOV: 600.0, CAT_FIN: 400.0}}),
    )

    payload = build_adb_insights_payload(
        current=window,
        qoq=_window(start="2026-02-19", end="2026-02-28", calendar_days=10, has_data=False),
        yoy=_window(start="2025-03-01", end="2025-03-10", calendar_days=10, has_data=False),
    )

    assert payload["concentration"] == {"assets": None, "liabilities": None, "reason": "single_observation"}


# ---------------------------------------------------------------------------
# 5 payload 形态与缺数语义
# ---------------------------------------------------------------------------


def test_empty_window_returns_null_blocks_and_no_data_reasons() -> None:
    payload = build_adb_insights_payload(
        current=_window(start="2024-01-01", end="2024-01-10", calendar_days=10, has_data=False),
        qoq=_window(start="2023-12-22", end="2023-12-31", calendar_days=10, has_data=False),
        yoy=_window(start="2023-01-01", end="2023-01-10", calendar_days=10, has_data=False),
    )

    assert payload["insufficient_window"] is False
    assert payload["windows"]["current"] == {
        "start_date": "2024-01-01",
        "end_date": "2024-01-10",
        "calendar_days_inclusive": 10,
        "coverage_days": 0,
        "available": False,
        "reason": "no_data",
    }
    assert payload["scale_attribution"] == {"qoq": None, "yoy": None}
    assert payload["nim_attribution"] is None
    assert payload["nim_attribution_unavailable_reason"] == "current_unavailable"
    assert payload["volatility"] is None
    assert payload["concentration"] is None
    assert [item["id"] for item in payload["insights"]] == [
        "current_unavailable",
        "comparison_unavailable",
    ]


def test_single_day_window_nulls_every_analysis_block() -> None:
    current = _window(
        start="2026-03-05",
        end="2026-03-05",
        calendar_days=1,
        coverage_days=1,
        assets=_side(balances={CAT_GOV: 1000.0}, rates={CAT_GOV: 2.5}, daily={"2026-03-05": {CAT_GOV: 1000.0}}),
        liabilities=_side(balances={CAT_REPO: 500.0}, rates={CAT_REPO: 1.5}),
    )

    payload = build_adb_insights_payload(
        current=current,
        qoq=_window(start="2026-03-04", end="2026-03-04", calendar_days=1, has_data=True),
        yoy=_window(start="2025-03-05", end="2025-03-05", calendar_days=1, has_data=True),
    )

    assert payload["insufficient_window"] is True
    assert payload["scale_attribution"] == {"qoq": None, "yoy": None}
    assert payload["nim_attribution"] is None
    assert payload["nim_attribution_unavailable_reason"] == "insufficient_window"
    assert payload["volatility"] is None
    assert payload["concentration"] is None
    assert payload["insights"] == []
    assert payload["windows"]["current"]["available"] is True


# ---------------------------------------------------------------------------
# 4.6 结论规则
# ---------------------------------------------------------------------------


def test_insights_fire_for_nim_compression_month_end_and_missing_comparison() -> None:
    current = _window(
        start="2026-03-01",
        end="2026-04-06",
        calendar_days=37,
        coverage_days=12,
        assets=_side(
            balances={CAT_GOV: 1000.0},
            rates={CAT_GOV: 2.5},
            coverage=1.0,
            daily=_month_end_daily(),
        ),
        liabilities=_side(
            balances={CAT_REPO: 1000.0},
            rates={CAT_REPO: 1.5},
            coverage=1.0,
            daily=_single_category_daily(CAT_REPO, date(2026, 3, 1), [200.0] * 6),
        ),
    )
    qoq = _window(
        start="2026-01-23",
        end="2026-02-28",
        calendar_days=37,
        coverage_days=12,
        assets=_side(balances={CAT_GOV: 1000.0}, rates={CAT_GOV: 2.5}, coverage=1.0),
        liabilities=_side(balances={CAT_REPO: 1000.0}, rates={CAT_REPO: 1.0}, coverage=1.0),
    )
    yoy = _window(start="2025-03-01", end="2025-04-06", calendar_days=37, has_data=False)

    payload = build_adb_insights_payload(current=current, qoq=qoq, yoy=yoy)
    insights = {item["id"]: item for item in payload["insights"]}

    assert {"nim_compression", "month_end_effect", "comparison_unavailable"} <= set(insights)
    assert payload["nim_attribution"]["nim_delta_bp"] == pytest.approx(-50.0)

    compression = insights["nim_compression"]
    assert compression["severity"] == "warning"
    assert compression["dimension"] == "nim"
    assert "\u51c0\u606f\u5dee\u73af\u6bd4\u6536\u7a84" in compression["title"]
    assert "50.0bp" in compression["detail"]
    assert compression["evidence"]["dominant_driver"] == "\u8d1f\u503a\u5229\u7387"

    month_end = insights["month_end_effect"]
    assert month_end["severity"] == "warning"
    assert month_end["dimension"] == "volatility"
    assert "25.00%" in month_end["detail"]

    unavailable = insights["comparison_unavailable"]
    assert unavailable["severity"] == "info"
    assert unavailable["dimension"] == "quality"
    assert "2025-03-01" in unavailable["detail"]
    assert unavailable["evidence"]["missing_windows"][0]["basis"] == "yoy"


def test_scale_move_and_rate_coverage_insights_use_frozen_thresholds() -> None:
    current = _window(
        start="2026-03-01",
        end="2026-03-10",
        calendar_days=10,
        coverage_days=10,
        assets=_side(
            balances={CAT_GOV: 12_000_000_000.0, CAT_FIN: 2_000_000_000.0},
            rates={CAT_GOV: 2.5},
            coverage=0.85,
            daily=_single_category_daily(CAT_GOV, date(2026, 3, 1), [1_400_000_000.0] * 10),
        ),
        liabilities=_side(balances={CAT_REPO: 6_000_000_000.0}, rates={CAT_REPO: 1.5}, coverage=1.0),
    )
    qoq = _window(
        start="2026-02-19",
        end="2026-02-28",
        calendar_days=10,
        coverage_days=10,
        assets=_side(balances={CAT_GOV: 10_000_000_000.0, CAT_FIN: 2_000_000_000.0}, rates={CAT_GOV: 2.5}),
        liabilities=_side(balances={CAT_REPO: 6_000_000_000.0}, rates={CAT_REPO: 1.5}),
    )
    yoy = _window(
        start="2025-03-01",
        end="2025-03-10",
        calendar_days=10,
        coverage_days=10,
        assets=_side(balances={CAT_GOV: 9_000_000_000.0}, rates={CAT_GOV: 2.4}),
        liabilities=_side(balances={CAT_REPO: 6_000_000_000.0}, rates={CAT_REPO: 1.4}),
    )

    payload = build_adb_insights_payload(current=current, qoq=qoq, yoy=yoy)
    insights = {item["id"]: item for item in payload["insights"]}

    assert insights["scale_qoq_move"]["severity"] == "notice"
    assert insights["scale_qoq_move"]["dimension"] == "scale"
    assert "2.00\u4ebf\u5143" in insights["scale_qoq_move"]["detail"]
    assert "16.67%" in insights["scale_qoq_move"]["detail"]
    assert insights["rate_coverage_low"]["severity"] == "info"
    assert "85.00%" in insights["rate_coverage_low"]["detail"]
    assert "comparison_unavailable" not in insights
    assert payload["scale_attribution"]["yoy"] is not None
