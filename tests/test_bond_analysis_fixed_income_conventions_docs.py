from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_doc(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_bond_analysis_fixed_income_conventions_are_documented_for_owner_review() -> None:
    calc_rules = _read_doc("docs/calc_rules.md")
    metric_dictionary = _read_doc("docs/metric_dictionary.md")

    required_calc_rule_phrases = [
        "market_value_basis=clean",
        "dirty_market_value = market_value + accrued_interest",
        "accrued_interest_usage=dirty_price",
        "carry and action attribution do not directly consume accrued_interest",
        "day_count=ACT/365_approximation",
        "yield_compounding=nominal_annual_with_coupon_frequency",
        "duration_convexity_scope=vanilla_fixed_rate_only",
        "DV01 = CNY face_value * modified_duration / 10000",
        "dv01_unit=CNY_per_1bp",
        "dv01_base=CNY_face_value",
        "market_value/dirty_value DV01 is not the current formal DV01 convention",
    ]
    for phrase in required_calc_rule_phrases:
        assert phrase in calc_rules

    required_metric_dictionary_phrases = [
        "MTR-RSK-001",
        "CNY_per_1bp",
        "CNY face_value * modified_duration / 10000",
        "not market_value or dirty_value based",
    ]
    for phrase in required_metric_dictionary_phrases:
        assert phrase in metric_dictionary
