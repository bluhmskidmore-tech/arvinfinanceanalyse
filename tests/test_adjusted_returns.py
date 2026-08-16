from __future__ import annotations

import pytest

from backend.app.core_finance.adjusted_returns import net_return_after_costs


def test_net_return_after_costs_uses_multiplicative_cost_basis() -> None:
    # Costs are charged on traded notional, so the net return must be
    # (1 + r) * (1 - c) - 1 with c = buy + sell + 2 * slippage, not the
    # additive approximation r - c (second-order error ~= r * c).
    gross = 0.10
    round_trip_cost = 0.0008 + 0.0013 + 2 * 0.0010
    expected = (1.0 + gross) * (1.0 - round_trip_cost) - 1.0

    result = net_return_after_costs(
        gross,
        buy_cost_rate=0.0008,
        sell_cost_rate=0.0013,
        slippage_rate=0.0010,
    )

    assert result == pytest.approx(expected, abs=1e-12)
    # The additive approximation differs by exactly r * c.
    assert result == pytest.approx(gross - round_trip_cost - gross * round_trip_cost, abs=1e-12)


def test_net_return_after_costs_zero_costs_is_identity() -> None:
    assert net_return_after_costs(
        0.05,
        buy_cost_rate=0.0,
        sell_cost_rate=0.0,
        slippage_rate=0.0,
    ) == pytest.approx(0.05)


def test_net_return_after_costs_none_passthrough() -> None:
    assert (
        net_return_after_costs(
            None,
            buy_cost_rate=0.0008,
            sell_cost_rate=0.0013,
            slippage_rate=0.0010,
        )
        is None
    )
