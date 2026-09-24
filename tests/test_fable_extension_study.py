from __future__ import annotations

import pytest

from scripts.run_fable_extension_study import (
    assign_extension_bin,
    classify_outcome_maturity,
)


def _trading_dates(count: int) -> list[str]:
    dates = [
        "2026-06-02",
        "2026-06-03",
        "2026-06-04",
        "2026-06-05",
        "2026-06-08",
        "2026-06-09",
        "2026-06-10",
        "2026-06-11",
        "2026-06-12",
        "2026-06-15",
        "2026-06-16",
        "2026-06-17",
        "2026-06-18",
        "2026-06-19",
        "2026-06-22",
        "2026-06-23",
        "2026-06-24",
        "2026-06-25",
        "2026-06-26",
        "2026-06-29",
    ]
    return dates[:count]


@pytest.mark.parametrize(
    ("adjusted_return", "raw_return", "expected"),
    [
        (0.03, 0.02, "complete_adjusted"),
        (None, 0.02, "matured_adjustment_missing"),
        (None, None, "matured_missing_bar"),
    ],
)
def test_mature_outcome_statuses_are_explicit(
    adjusted_return: float | None,
    raw_return: float | None,
    expected: str,
) -> None:
    assert (
        classify_outcome_maturity(
            signal_date="2026-06-01",
            trading_dates=_trading_dates(20),
            horizon=20,
            adjusted_return=adjusted_return,
            raw_return=raw_return,
        )
        == expected
    )


def test_incomplete_trading_horizon_is_natural_pending() -> None:
    assert (
        classify_outcome_maturity(
            signal_date="2026-06-01",
            trading_dates=_trading_dates(19),
            horizon=20,
            adjusted_return=None,
            raw_return=None,
        )
        == "natural_pending"
    )


def test_future_outcome_conflict_fails_instead_of_leaking() -> None:
    with pytest.raises(ValueError, match="outcome exists before the horizon matures"):
        classify_outcome_maturity(
            signal_date="2026-06-01",
            trading_dates=_trading_dates(19),
            horizon=20,
            adjusted_return=0.03,
            raw_return=0.02,
        )


@pytest.mark.parametrize(
    ("extension", "expected"),
    [
        (None, "feature_missing"),
        (-0.0001, "lt_0"),
        (0.0, "0_5"),
        (0.05, "0_5"),
        (0.050001, "5_10"),
        (0.10, "5_10"),
        (0.100001, "10_15"),
        (0.15, "10_15"),
        (0.150001, "15_plus"),
    ],
)
def test_extension_bins_are_predeclared_and_boundary_stable(
    extension: float | None,
    expected: str,
) -> None:
    assert assign_extension_bin(extension) == expected
