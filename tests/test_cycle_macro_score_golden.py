from __future__ import annotations

from backend.app.core_finance.cycle_macro_score import (
    build_cycle_macro_snapshot,
    compute_credit_impulse_signal,
    compute_macro_score,
    compute_pmi_signal,
    compute_price_spread_signal,
)

# Golden inputs aligned with tests/fixtures/cycle_rotation_macro_monthly.json
_GOLDEN_PMI = 51.0
_GOLDEN_SF_PRIOR = 8.5
_GOLDEN_SF_CURRENT = 9.2
_GOLDEN_PE = 14.0
_GOLDEN_CN10Y = 2.1


def test_credit_impulse_golden_components() -> None:
    signal, impulse_ppt = compute_credit_impulse_signal(
        current_yoy=_GOLDEN_SF_CURRENT,
        prior_yoy=_GOLDEN_SF_PRIOR,
    )
    assert round(impulse_ppt, 6) == 0.7
    assert round(signal, 6) == 0.675


def test_macro_score_golden_snapshot() -> None:
    pmi_signal = compute_pmi_signal(_GOLDEN_PMI)
    credit_signal, impulse_ppt = compute_credit_impulse_signal(
        current_yoy=_GOLDEN_SF_CURRENT,
        prior_yoy=_GOLDEN_SF_PRIOR,
    )
    price_signal, spread_ppt = compute_price_spread_signal(pe=_GOLDEN_PE, cn10y=_GOLDEN_CN10Y)

    assert round(pmi_signal, 6) == 0.666667
    assert round(impulse_ppt, 6) == 0.7
    assert round(credit_signal, 6) == 0.675
    assert round(spread_ppt, 6) == 5.042857
    assert round(price_signal, 6) == 1.0

    macro_score = compute_macro_score(
        pmi_signal=pmi_signal,
        credit_impulse_signal=credit_signal,
        price_spread_signal=price_signal,
    )
    assert macro_score is not None
    assert round(macro_score, 6) == 0.752917

    snapshot = build_cycle_macro_snapshot(
        pmi_points=[("2026-04-01", _GOLDEN_PMI)],
        social_financing_yoy_points=[
            ("2026-03-01", _GOLDEN_SF_PRIOR),
            ("2026-04-01", _GOLDEN_SF_CURRENT),
        ],
        pe=_GOLDEN_PE,
        cn10y=_GOLDEN_CN10Y,
        as_of_date="2026-05-08",
    )
    assert snapshot.macro_score is not None
    assert round(snapshot.macro_score, 6) == 0.752917
    assert round(snapshot.credit_impulse_value, 6) == 0.7
    assert snapshot.pmi_value == _GOLDEN_PMI
