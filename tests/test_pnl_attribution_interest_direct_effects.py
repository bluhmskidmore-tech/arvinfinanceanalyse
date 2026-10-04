"""Account-backed non-interest changes must not masquerade as interest-rate effects."""
from decimal import Decimal

import pytest

from backend.app.core_finance.pnl_attribution.workbench import (
    build_pnl_attribution_analysis_summary,
    build_volume_rate_attribution_from_grouped_rows,
)
from backend.app.schemas.pnl_attribution import VolumeRateAttributionPayload
from backend.app.services.pnl_attribution_service import _promote_payload_numerics


def row(category, scale, interest, fair_value="0", gain="0", manual="0", total=None):
    components = [Decimal(str(value)) for value in (interest, fair_value, gain, manual)]
    return {
        "business_type_primary": category,
        "scale_amount": str(scale),
        "interest_income_514": str(interest),
        "fair_value_change_516": str(fair_value),
        "capital_gain_517": str(gain),
        "manual_adjustment": str(manual),
        "total_pnl": str(total if total is not None else sum(components)),
    }


def attribute(current, previous):
    return build_volume_rate_attribution_from_grouped_rows(
        current_rows=current,
        prior_rows=previous,
        current_period="2026-08",
        previous_period="2026-07",
        compare_type="mom",
        interest_field="interest_income_514",
    )


def test_unchanged_interest_yield_does_not_turn_fair_value_into_rate_effect():
    result = attribute([row("Bond", 1200, 12, 80, 9, 3)], [row("Bond", 1000, 10, 50, 4, 1)])
    item = result["items"][0]
    assert item["current_yield_pct"] == pytest.approx(1)
    assert item["volume_effect"] == 2
    assert item["rate_effect"] == item["interaction_effect"] == 0
    assert item["fair_value_effect"] == 30
    assert item["capital_gain_effect"] == 5
    assert item["manual_adjustment_effect"] == 2
    assert item["attrib_sum"] == result["total_pnl_change"] == 39
    assert item["recon_error"] == result["total_recon_error"] == 0


def test_exited_position_direct_accounts_are_explained_without_invented_scale():
    result = attribute([row("Unmatched", 0, 0, 500, 7)], [row("Unmatched", 0, 0, -4, 2)])
    item = result["items"][0]
    assert item["current_yield_pct"] is None
    assert item["volume_effect"] is item["rate_effect"] is item["interaction_effect"] is None
    assert result["total_fair_value_effect"] == 504
    assert result["total_capital_gain_effect"] == 5
    assert item["attrib_sum"] == result["total_pnl_change"] == 509
    assert result["total_recon_error"] == 0


def test_unmatched_interest_remains_unexplained_alongside_known_direct_effects():
    result = attribute([row("Unmatched-A", 0, 33, 100)], [row("Unmatched-A", 0, 82, 90)])
    item = result["items"][0]
    assert item["fair_value_effect"] == 10
    assert item["attrib_sum"] == 10
    assert item["recon_error"] == result["total_recon_error"] == -49


def test_missing_category_is_not_evidence_of_observed_zero_scale():
    result = attribute([row("Bond", 1000, 10)], [row("Bond", 1000, 10), row("Bill", 500, 6)])
    item = next(item for item in result["items"] if item["category"] == "Bill")
    assert item["current_yield_pct"] is None
    assert item["volume_effect"] is None
    assert item["recon_error"] == result["total_recon_error"] == -6


def test_missing_account_component_stays_unknown_and_reconciliation_exposes_gap():
    current = row("Bond", 1000, 10, 50)
    del current["fair_value_change_516"]
    result = attribute([current], [row("Bond", 1000, 10, 20)])
    assert result["items"][0]["fair_value_effect"] is None
    assert result["total_fair_value_effect"] is None
    assert result["has_complete_inputs"] is False
    assert result["total_recon_error"] == 30


def test_missing_interest_is_not_healthy_even_if_other_accounts_numerically_close():
    current = row("Bond", 1000, 10, 50)
    current["interest_income_514"] = None
    result = attribute([current], [row("Bond", 1000, 10, 20)])
    assert result["total_recon_error"] == 0
    assert result["total_volume_effect"] is result["total_rate_effect"] is None
    assert result["has_complete_inputs"] is False


@pytest.mark.parametrize("invalid_total", [None, "NaN", "Infinity"])
def test_missing_or_nonfinite_total_is_rejected_instead_of_inventing_a_loss(invalid_total):
    current = row("Bond", 1000, 10, 50)
    current["total_pnl"] = invalid_total
    with pytest.raises(ValueError, match="requires finite total_pnl"):
        attribute([current], [row("Bond", 1000, 10, 20)])


def test_independently_rounded_total_is_not_overwritten_to_force_closure():
    result = attribute([row("Bond", 1000, 10, "0.03", total="10.02")], [row("Bond", 1000, 10)])
    assert result["total_recon_error"] == pytest.approx(-0.01)


def test_no_prior_keeps_every_delta_missing_and_numeric_contract_preserves_units():
    result = attribute([row("Bond", 1000, 10, 50)], None)
    assert result["total_fair_value_effect"] is result["total_recon_error"] is None
    assert result["items"][0]["capital_gain_effect"] is None
    paired = attribute([row("Bond", 1000, 10, 50)], [row("Bond", 1000, 10, 20)])
    payload = VolumeRateAttributionPayload.model_validate(_promote_payload_numerics(paired, VolumeRateAttributionPayload))
    assert payload.attribution_basis == "interest_income_and_direct_pnl"
    assert payload.total_fair_value_effect.raw == 30
    assert payload.total_fair_value_effect.unit == "yuan"
    assert payload.items[0].current_yield_pct.raw == pytest.approx(0.01)


def test_summary_includes_non_interest_effects_instead_of_claiming_volume_dominates():
    summary = build_pnl_attribution_analysis_summary(
        report_date="2026-08-31", volume_effect=2, rate_effect=0, interaction_effect=0,
        fair_value_effect=90, capital_gain_effect=-5, manual_adjustment_effect=0,
        unexplained_effect=-3, attribution_basis="interest_income_and_direct_pnl",
        correlation_tpl_treasury=None,
    )
    assert summary["primary_driver"] == "fair_value"
    assert summary["primary_driver_pct"] == 90
    assert "公允价值变动" in " ".join(summary["key_findings"])


def test_summary_missing_effect_does_not_claim_a_known_primary_driver():
    summary = build_pnl_attribution_analysis_summary(
        report_date="2026-08-31", volume_effect=None, rate_effect=0, interaction_effect=0,
        fair_value_effect=90, capital_gain_effect=-5, manual_adjustment_effect=0,
        unexplained_effect=-3, attribution_basis="interest_income_and_direct_pnl",
        correlation_tpl_treasury=None,
    )
    assert summary["primary_driver"] == "unknown"
    assert summary["primary_driver_pct"] is None
