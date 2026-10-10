"""M15 must consume one complete, same-date government-curve snapshot."""

from __future__ import annotations

from backend.app.services import macro_toolkit_route_support as macro_toolkit_support

from datetime import date, timedelta

import pytest


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


_REPORT_DATE = date(2026, 8, 21)
_REQUIRED_TENORS = ("1Y", "3Y", "5Y", "7Y", "10Y")


def _gov_row(sample_date: date, tenor: str, rate: float) -> dict[str, object]:
    return {
        "biz_date": sample_date,
        "curve_id": "CN_GOVT",
        "tenor": tenor,
        "rate_value": rate,
    }


def _complete_snapshot(sample_date: date, *, base_rate: float) -> list[dict[str, object]]:
    return [
        _gov_row(sample_date, tenor, base_rate + index / 10)
        for index, tenor in enumerate(_REQUIRED_TENORS)
    ]


def test_m15_falls_back_to_latest_complete_same_date_snapshot() -> None:
    selected_date = _REPORT_DATE - timedelta(days=1)
    rows = [_gov_row(_REPORT_DATE, "10Y", 9.99)]
    rows.extend(_complete_snapshot(selected_date, base_rate=1.0))

    curve, evidence = macro_toolkit_support._current_gov_curve_snapshot(
        rows,
        _REPORT_DATE,
    )

    assert curve == {
        tenor: pytest.approx(1.0 + index / 10)
        for index, tenor in enumerate(_REQUIRED_TENORS)
    }
    assert curve["10Y"] != pytest.approx(9.99)
    assert evidence == {
        "requested_report_date": _REPORT_DATE.isoformat(),
        "curve_date": selected_date.isoformat(),
        "fallback_mode": "latest_complete_snapshot",
        "stale_days": 1,
        "missing_tenors": [],
    }


def test_m15_uses_latest_partial_snapshot_without_cross_date_tenor_mix() -> None:
    older_date = _REPORT_DATE - timedelta(days=1)
    rows = [
        _gov_row(_REPORT_DATE, "10Y", 2.0),
        _gov_row(older_date, "1Y", 1.0),
        _gov_row(older_date, "3Y", 1.2),
        _gov_row(older_date, "5Y", 1.4),
        _gov_row(older_date, "7Y", 1.6),
    ]

    curve, evidence = macro_toolkit_support._current_gov_curve_snapshot(
        rows,
        _REPORT_DATE,
    )

    assert curve == {"10Y": pytest.approx(2.0)}
    assert evidence["curve_date"] == _REPORT_DATE.isoformat()
    assert evidence["fallback_mode"] == "none_available"
    assert evidence["stale_days"] == 0
    assert evidence["missing_tenors"] == ["1Y", "3Y", "5Y", "7Y"]


def test_m15_complete_latest_snapshot_keeps_existing_behavior() -> None:
    rows = _complete_snapshot(_REPORT_DATE, base_rate=1.0)

    curve, evidence = macro_toolkit_support._current_gov_curve_snapshot(
        rows,
        _REPORT_DATE,
    )

    assert set(curve) == set(_REQUIRED_TENORS)
    assert evidence == {
        "requested_report_date": _REPORT_DATE.isoformat(),
        "curve_date": _REPORT_DATE.isoformat(),
        "fallback_mode": "none",
        "stale_days": 0,
        "missing_tenors": [],
    }
    # The compatibility helper continues to expose only the curve mapping.
    assert macro_toolkit_support._current_gov_curve(rows, _REPORT_DATE) == curve


def test_m15_route_result_discloses_curve_snapshot_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    selected_date = _REPORT_DATE - timedelta(days=2)
    curve_rows = [_gov_row(_REPORT_DATE, "10Y", 9.99)]
    curve_rows.extend(_complete_snapshot(selected_date, base_rate=1.0))

    monkeypatch.setattr(
        macro_toolkit_support,
        "_load_macro_capability_context",
        lambda *_args, **_kwargs: (curve_rows, None, []),
    )
    monkeypatch.setattr(
        macro_toolkit_support,
        "load_series_by_aliases",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        macro_toolkit_support,
        "_load_macro_wide_rows",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        macro_toolkit_support,
        "_risk_tensor_to_liquidity_inputs",
        lambda *_args, **_kwargs: ([], [], None),
    )
    monkeypatch.setattr(
        macro_toolkit_support,
        "build_bond_portfolio_profile",
        lambda *_args, **_kwargs: {
            "total_mv": 100.0,
            "weighted_duration": 2.0,
            "bond_count": 1,
            "buckets": {},
        },
    )
    monkeypatch.setattr(
        macro_toolkit_support,
        "_with_capability_input_evidence",
        lambda _key, result, **_kwargs: result,
    )
    monkeypatch.setattr(
        macro_toolkit_support,
        "_source_checks_for_aliases",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        macro_toolkit_support,
        "_run_capability",
        lambda key, compute: (
            compute()
            if key == "macro_portfolio_impact"
            else {"data_status": "unavailable", "warnings": ["skipped"]}
        ),
    )

    cards = macro_toolkit_support._macro_capability_results(
        "unused.duckdb",
        report_date=_REPORT_DATE.isoformat(),
    )
    result = next(
        card["result"]
        for card in cards
        if card["key"] == "macro_portfolio_impact"
    )

    assert result["requested_report_date"] == _REPORT_DATE.isoformat()
    assert result["curve_date"] == selected_date.isoformat()
    assert result["fallback_mode"] == "latest_complete_snapshot"
    assert result["stale_days"] == 2
    assert result["missing_tenors"] == []
    assert result["current_curve"]["10Y"] == pytest.approx(1.4)
    assert result["data_status"] == "degraded"
    assert "CURVE_DATE_FALLBACK" in result["warnings"]
