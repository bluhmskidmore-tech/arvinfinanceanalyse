from decimal import Decimal as D

import pytest

from backend.app.core_finance.campisi_decision_grade import compute_decision_grade_row


@pytest.mark.parametrize("coverage", [D("0"), D("0.5")])
def test_partial_tenor_does_not_price_full_position_at_covered_average(coverage):
    row = {
        "actual_pnl": D("200000"),
        "market_value": D("100000000"),
        "modified_duration": D("2"),
        "convexity": D("3"),
        "spread_dv01": D("20000"),
        "years_to_maturity": D("3"),
        "years_to_maturity_coverage_ratio": coverage,
        "rating": "AAA",
        "is_credit": True,
    }
    result = compute_decision_grade_row(
        row,
        treasury_start={"1Y": D("2"), "3Y": D("2")},
        treasury_end={"1Y": D("2"), "3Y": D("1.9")},
        credit_start_by_rating={"AAA": {"1Y": D("3"), "3Y": D("3")}},
        credit_end_by_rating={"AAA": {"1Y": D("3"), "3Y": D("3.1")}},
    )
    parts = result["components"]
    # The parallel shift is -5bp and does not depend on the partial tenor.
    assert parts["rate_level_effect"] == D("100000")
    assert parts["curve_shape_effect"] == 0
    assert parts["credit_spread_effect"] == 0
    assert parts["convexity_effect"] == 0
    assert parts["selection_proxy"] == 0
    assert parts["residual_noise"] == D("100000")
    assert sum(parts.values()) == row["actual_pnl"]
    assert "partial_years_to_maturity_coverage" in result["residual_reasons"]
