from __future__ import annotations

import builtins
from types import ModuleType

import pytest
from backend.app.core_finance import (
    fresh_trend_watchlist_candidates,
    livermore_stock_candidates,
    mean_reversion_candidates,
    uptrend_momentum_candidates,
)

NUMERIC_MODULES = (
    livermore_stock_candidates,
    uptrend_momentum_candidates,
    fresh_trend_watchlist_candidates,
    mean_reversion_candidates,
)


@pytest.mark.parametrize(
    "module",
    NUMERIC_MODULES,
    ids=lambda module: module.__name__.rsplit(".", 1)[-1],
)
def test_native_numbers_skip_text_round_trip(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text_round_trips: list[float] = []

    def tracking_str(value: object) -> str:
        if type(value) in {float, int}:
            text_round_trips.append(float(value))
        return builtins.str(value)

    monkeypatch.setattr(module, "str", tracking_str, raising=False)
    valid_float = getattr(module, "_valid_float")

    assert valid_float(1.25) == 1.25
    assert valid_float(2) == 2.0
    assert valid_float("3.5") == 3.5
    assert valid_float(True) is None
    assert valid_float(float("nan")) is None
    assert text_round_trips == []


@pytest.mark.parametrize(
    "module",
    NUMERIC_MODULES,
    ids=lambda module: module.__name__.rsplit(".", 1)[-1],
)
def test_huge_integer_matches_old_semantics(
    module: ModuleType,
) -> None:
    valid_float = getattr(module, "_valid_float")
    assert valid_float(10**1000) is None
