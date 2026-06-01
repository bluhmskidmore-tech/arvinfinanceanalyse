from __future__ import annotations

from backend.app.core_finance.cycle_macro_score import (
    build_cycle_macro_snapshot,
    compute_credit_impulse_signal,
    compute_macro_score,
    compute_pmi_signal,
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
