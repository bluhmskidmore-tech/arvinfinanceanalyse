from __future__ import annotations

from backend.app.core_finance.cycle_macro_score import (
    M2_YOY_SERIES_ID,
    SOCIAL_FINANCING_YOY_SERIES_ID,
    build_cycle_macro_snapshot,
    compute_credit_impulse_signal,
    compute_macro_score,
    compute_pmi_signal,
    compute_price_spread_signal,
)


def test_compute_pmi_signal_maps_50_to_midpoint() -> None:
    assert compute_pmi_signal(50.0) == 0.5


def test_compute_credit_impulse_signal_uses_yoy_delta() -> None:
    signal, impulse = compute_credit_impulse_signal(current_yoy=10.0, prior_yoy=8.0)
    assert impulse == 2.0
    assert signal == 1.0


def test_compute_macro_score_reweights_available_components() -> None:
    score = compute_macro_score(
        pmi_signal=0.6,
        credit_impulse_signal=None,
        price_spread_signal=0.4,
    )
    assert score is not None
    assert 0.4 < score < 0.6


def test_build_cycle_macro_snapshot_marks_missing_inputs_without_fabrication() -> None:
    snapshot = build_cycle_macro_snapshot(
        pmi_points=None,
        social_financing_yoy_points=None,
        pe=None,
        cn10y=None,
        as_of_date="2026-05-08",
    )
    assert snapshot.macro_score is None
    assert snapshot.missing_inputs == ("PMI", "credit_impulse", "price_spread")
    assert snapshot.available_inputs == ()


def test_build_cycle_macro_snapshot_computes_macro_score_when_inputs_land() -> None:
    snapshot = build_cycle_macro_snapshot(
        pmi_points=[("2026-04-01", 51.0)],
        social_financing_yoy_points=[("2026-03-01", 8.5), ("2026-04-01", 9.2)],
        pe=14.0,
        cn10y=2.1,
        as_of_date="2026-05-08",
    )
    assert snapshot.pmi_ready is True
    assert snapshot.credit_impulse_ready is True
    assert snapshot.price_spread_ready is True
    assert snapshot.macro_score is not None
    assert "MacroScore" in snapshot.evidence


def test_build_cycle_macro_snapshot_rejects_credit_when_any_point_is_after_as_of_date() -> None:
    """PMI can use its prior point, but credit impulse fails closed on any future input."""
    snapshot = build_cycle_macro_snapshot(
        pmi_points=[("2026-04-01", 51.0), ("2026-06-01", 99.0)],
        social_financing_yoy_points=[
            ("2026-03-01", 8.5),
            ("2026-04-01", 9.2),
            ("2026-06-01", 50.0),
        ],
        pe=14.0,
        cn10y=2.1,
        as_of_date="2026-05-08",
    )
    assert snapshot.pmi_value == 51.0
    assert snapshot.credit_impulse_ready is False
    assert snapshot.credit_impulse_value is None


def test_build_cycle_macro_snapshot_reweights_when_all_points_are_future() -> None:
    """If every landed point for an input is after as_of_date, treat it as missing and reweight."""
    snapshot = build_cycle_macro_snapshot(
        pmi_points=[("2026-06-01", 99.0)],
        social_financing_yoy_points=None,
        pe=None,
        cn10y=None,
        as_of_date="2026-05-08",
    )
    assert snapshot.pmi_ready is False
    assert "PMI" in snapshot.missing_inputs
    assert snapshot.macro_score is None


def test_compute_price_spread_signal_returns_tuple_when_pe_non_positive() -> None:
    """The non-positive PE branch must keep the same (signal, spread_ppt) contract as the normal path."""
    result = compute_price_spread_signal(pe=0.0, cn10y=2.1)
    assert isinstance(result, tuple)
    signal, spread_ppt = result
    assert signal == 0.0
    assert spread_ppt is None


def test_build_cycle_macro_snapshot_reports_actual_credit_impulse_source() -> None:
    snapshot = build_cycle_macro_snapshot(
        pmi_points=None,
        social_financing_yoy_points=[("2026-03-01", 8.5), ("2026-04-01", 9.2)],
        credit_impulse_series_id=M2_YOY_SERIES_ID,
        pe=None,
        cn10y=None,
        as_of_date="2026-05-08",
    )

    assert snapshot.credit_impulse_ready is True
    assert snapshot.lineage["credit_impulse"]["series_id"] == M2_YOY_SERIES_ID
    assert M2_YOY_SERIES_ID in snapshot.evidence
    assert SOCIAL_FINANCING_YOY_SERIES_ID not in snapshot.evidence


def test_build_cycle_macro_snapshot_rejects_non_adjacent_credit_months() -> None:
    snapshot = build_cycle_macro_snapshot(
        pmi_points=None,
        social_financing_yoy_points=[("2026-02-01", 8.5), ("2026-04-01", 9.2)],
        credit_impulse_series_id=SOCIAL_FINANCING_YOY_SERIES_ID,
        pe=None,
        cn10y=None,
        as_of_date="2026-05-08",
    )

    assert snapshot.credit_impulse_ready is False
    assert snapshot.lineage["credit_impulse"] == {}


def test_build_cycle_macro_snapshot_rejects_duplicate_credit_months() -> None:
    snapshot = build_cycle_macro_snapshot(
        pmi_points=None,
        social_financing_yoy_points=[
            ("2026-03-01", 8.4),
            ("2026-03-31", 8.5),
            ("2026-04-01", 9.2),
        ],
        credit_impulse_series_id=SOCIAL_FINANCING_YOY_SERIES_ID,
        pe=None,
        cn10y=None,
        as_of_date="2026-05-08",
    )

    assert snapshot.credit_impulse_ready is False


def test_build_cycle_macro_snapshot_rejects_any_future_credit_point() -> None:
    snapshot = build_cycle_macro_snapshot(
        pmi_points=None,
        social_financing_yoy_points=[
            ("2026-03-01", 8.5),
            ("2026-04-01", 9.2),
            ("2026-06-01", 9.8),
        ],
        credit_impulse_series_id=SOCIAL_FINANCING_YOY_SERIES_ID,
        pe=None,
        cn10y=None,
        as_of_date="2026-05-08",
    )

    assert snapshot.credit_impulse_ready is False


def test_build_cycle_macro_snapshot_rejects_mixed_credit_source_id() -> None:
    snapshot = build_cycle_macro_snapshot(
        pmi_points=None,
        social_financing_yoy_points=[("2026-03-01", 8.5), ("2026-04-01", 9.2)],
        credit_impulse_series_id=f"{SOCIAL_FINANCING_YOY_SERIES_ID}+{M2_YOY_SERIES_ID}",
        pe=None,
        cn10y=None,
        as_of_date="2026-05-08",
    )

    assert snapshot.credit_impulse_ready is False
