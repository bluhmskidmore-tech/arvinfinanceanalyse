"""M8/M13 curve consumers must select atomic same-date CN_GOVT snapshots."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.app.core_finance.macro import (
    compute_rate_turning_point,
    compute_yield_curve_shape,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


_REPORT_DATE = date(2026, 8, 21)


def _gov_row(sample_date: date, tenor: str, rate: float) -> dict[str, object]:
    return {
        "biz_date": sample_date,
        "curve_id": "CN_GOVT",
        "tenor": tenor,
        "rate_value": rate,
    }


def _complete_history(*, start_offset: int, days: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for offset in range(start_offset, start_offset + days):
        sample_date = _REPORT_DATE - timedelta(days=offset)
        rows.extend(
            [
                _gov_row(sample_date, "1Y", 1.00 + offset / 100),
                _gov_row(sample_date, "10Y", 2.00 + offset / 100),
            ]
        )
    return rows


def test_m8_falls_back_to_latest_complete_same_date_snapshot() -> None:
    selected_date = _REPORT_DATE - timedelta(days=1)
    rows = [
        _gov_row(_REPORT_DATE, "10Y", 9.99),
        _gov_row(selected_date, "1Y", 1.50),
        _gov_row(selected_date, "5Y", 1.75),
        _gov_row(selected_date, "10Y", 2.00),
        _gov_row(selected_date, "30Y", 2.25),
    ]

    payload = compute_yield_curve_shape(rows, report_date=_REPORT_DATE)

    assert payload["requested_report_date"] == _REPORT_DATE.isoformat()
    assert payload["report_date"] == _REPORT_DATE.isoformat()
    assert payload["curve_date"] == selected_date.isoformat()
    assert payload["fallback_mode"] == "latest_complete_snapshot"
    assert payload["stale_days"] == 1
    assert payload["missing_tenors"] == []
    assert payload["curve"]["10Y"] == pytest.approx(2.00)
    assert payload["spreads"]["10Y-1Y"] == pytest.approx(50.0)
    assert payload["data_status"] == "degraded"
    assert "CURVE_DATE_FALLBACK" in payload["warnings"]


def test_m8_does_not_combine_required_tenors_across_dates() -> None:
    older_date = _REPORT_DATE - timedelta(days=1)
    rows = [
        _gov_row(_REPORT_DATE, "10Y", 2.00),
        _gov_row(older_date, "1Y", 1.50),
    ]

    payload = compute_yield_curve_shape(rows, report_date=_REPORT_DATE)

    assert payload["data_status"] == "unavailable"
    assert payload["curve_date"] == _REPORT_DATE.isoformat()
    assert payload["fallback_mode"] == "none_available"
    assert payload["stale_days"] == 0
    assert payload["missing_tenors"] == ["1Y"]
    assert payload["curve"] == {"10Y": pytest.approx(2.00)}
    assert payload["spreads"] == {}


def test_m13_uses_one_complete_date_for_current_level_and_slope() -> None:
    selected_date = _REPORT_DATE - timedelta(days=1)
    rows = [_gov_row(_REPORT_DATE, "10Y", 9.99)]
    rows.extend(_complete_history(start_offset=1, days=30))

    payload = compute_rate_turning_point(rows, report_date=_REPORT_DATE)

    assert payload["curve_date"] == selected_date.isoformat()
    assert payload["fallback_mode"] == "latest_complete_snapshot"
    assert payload["stale_days"] == 1
    assert payload["missing_tenors"] == []
    assert payload["current_10y"] == pytest.approx(2.01)
    assert payload["current_slope_10y_1y_bp"] == pytest.approx(100.0)
    assert payload["data_status"] == "degraded"
    assert "CURVE_DATE_FALLBACK" in payload["warnings"]


def test_m13_never_combines_partial_dates_into_a_complete_history() -> None:
    rows: list[dict[str, object]] = []
    for offset in range(12):
        sample_date = _REPORT_DATE - timedelta(days=offset)
        tenor = "10Y" if offset % 2 == 0 else "1Y"
        rows.append(_gov_row(sample_date, tenor, 2.00 if tenor == "10Y" else 1.00))

    payload = compute_rate_turning_point(rows, report_date=_REPORT_DATE)

    assert payload["data_status"] == "unavailable"
    assert payload["current_10y"] is None
    assert payload["current_slope_10y_1y_bp"] is None
    assert payload["curve_date"] == _REPORT_DATE.isoformat()
    assert payload["fallback_mode"] == "none_available"
    assert payload["missing_tenors"] == ["1Y"]
    assert "TURNING_POINT_HISTORY_SHORT" in payload["warnings"]


def test_complete_latest_snapshots_keep_existing_complete_behavior() -> None:
    rows = _complete_history(start_offset=0, days=30)
    rows.extend(
        [
            _gov_row(_REPORT_DATE, "5Y", 1.75),
            _gov_row(_REPORT_DATE, "30Y", 2.25),
        ]
    )

    shape = compute_yield_curve_shape(rows, report_date=_REPORT_DATE)
    turning_point = compute_rate_turning_point(rows, report_date=_REPORT_DATE)

    assert shape["curve_date"] == _REPORT_DATE.isoformat()
    assert shape["fallback_mode"] == "none"
    assert shape["stale_days"] == 0
    assert shape["missing_tenors"] == []
    assert shape["data_status"] == "complete"
    assert shape["warnings"] == []
    assert "CURVE_DATE_FALLBACK" not in shape["warnings"]

    assert turning_point["curve_date"] == _REPORT_DATE.isoformat()
    assert turning_point["fallback_mode"] == "none"
    assert turning_point["stale_days"] == 0
    assert turning_point["missing_tenors"] == []
    assert turning_point["data_status"] == "complete"
    assert turning_point["warnings"] == []
