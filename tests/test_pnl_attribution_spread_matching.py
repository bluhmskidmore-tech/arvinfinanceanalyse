from __future__ import annotations

import importlib
from decimal import Decimal
from typing import Any

import pytest

from backend.app.core_finance.pnl_attribution.workbench import (
    build_advanced_attribution_summary,
    build_spread_attribution,
)
from backend.app.schemas.pnl_attribution import SpreadAttributionPayload


def _row(code: str = "A", **overrides: Any) -> dict[str, Any]:
    return {
        "instrument_code": code,
        "portfolio_name": "P1",
        "cost_center": "C1",
        "accounting_class": "FVOCI",
        "currency_code": "CNY",
        "asset_class_std": "credit",
        "market_value": 100_000_000.0,
        "modified_duration": 2.0,
        "macaulay_duration": 2.1,
        "convexity": 0.0,
        "dv01": 20_000.0,
        "years_to_maturity": 5.0,
        "maturity_date": "2031-06-30",
        "ytm": 0.03,
        "ytm_input_status": "observed",
        "duration_quality_flag": "observed",
        **overrides,
    }


def _spread(starts: list[dict[str, Any]], ends: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    return build_spread_attribution(
        **{
            "report_date": "2026-06-30",
            "start_date": "2026-05-31",
            "end_date": "2026-06-30",
            "bond_rows_start": starts,
            "bond_rows_end": ends,
            "treasury_10y_start_pct": 2.0,
            "treasury_10y_end_pct": 2.0,
            "treasury_curve_start": {"1Y": Decimal("2"), "10Y": Decimal("2")},
            "treasury_curve_end": {"1Y": Decimal("2"), "10Y": Decimal("2")},
            **overrides,
        }
    )


def _reasons(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["reason"]: item for item in payload["attribution_coverage"]["exclusions"]}


def test_rebalance_with_unchanged_bond_quotes_has_no_market_effect() -> None:
    payload = _spread(
        [_row("A", market_value=90_000_000, ytm=0.02), _row("B", market_value=10_000_000, ytm=0.04)],
        [_row("A", market_value=10_000_000, ytm=0.02), _row("B", market_value=90_000_000, ytm=0.04)],
    )
    assert payload["total_treasury_effect"] == 0
    assert payload["total_spread_effect"] == 0
    assert payload["total_price_change"] == 0
    assert payload["primary_driver"] == "unchanged"
    assert payload["calculation_status"] == "complete"
    assert payload["items"][0]["yield_change"] == 0


def test_pure_spread_shock_uses_start_exposure_despite_resize_and_end_duration() -> None:
    payload = _spread([_row()], [_row(ytm=0.031, market_value=300_000_000, modified_duration=9)])
    assert payload["total_treasury_effect"] == 0
    assert payload["total_spread_effect"] == pytest.approx(-200_000)
    assert payload["items"][0]["matched_start_market_value"] == 100_000_000
    assert payload["items"][0]["attribution_duration"] == 2
    assert payload["items"][0]["duration"] == 9


def test_pure_treasury_shock_uses_matched_tenor_not_ten_year_rate() -> None:
    payload = _spread(
        [_row()], [_row(ytm=0.031)],
        treasury_curve_start={"5Y": Decimal("2"), "10Y": Decimal("2.5")},
        treasury_curve_end={"5Y": Decimal("2.1"), "10Y": Decimal("2.5")},
    )
    assert payload["total_treasury_effect"] == pytest.approx(-200_000)
    assert payload["total_spread_effect"] == pytest.approx(0)
    assert payload["items"][0]["treasury_change"] == pytest.approx(10)
    assert payload["treasury_10y_change"] == 0


def test_static_sloping_curve_roll_is_not_misclassified_as_credit_spread() -> None:
    curve = {"1Y": Decimal("2"), "2Y": Decimal("3")}
    payload = _spread(
        [_row(ytm=0.04, years_to_maturity=2)], [_row(ytm=0.03, years_to_maturity=1)],
        treasury_curve_start=curve, treasury_curve_end=curve,
    )
    assert payload["total_treasury_effect"] == pytest.approx(2_000_000)
    assert payload["total_spread_effect"] == pytest.approx(0)
    assert "期限滚动" in payload["method_note"]
    assert "不能与" in payload["method_note"]


def test_category_change_bp_are_weighted_by_start_dollar_duration_and_close() -> None:
    payload = _spread(
        [_row("A", market_value=100, modified_duration=1), _row("B", market_value=100, modified_duration=3)],
        [_row("A", market_value=100, ytm=0.031), _row("B", market_value=100, ytm=0.032)],
    )
    item = payload["items"][0]
    assert item["yield_change"] == pytest.approx(17.5)
    assert item["spread_change"] == pytest.approx(17.5)
    assert item["total_price_effect"] == pytest.approx(-0.7)
    assert -item["matched_start_market_value"] * item["attribution_duration"] * item["yield_change"] / 10_000 == pytest.approx(-0.7)


@pytest.mark.parametrize("dimension,value", [
    ("portfolio_name", "P2"), ("cost_center", "C2"),
    ("accounting_class", "FVTPL"), ("currency_code", "USD"),
])
def test_same_code_in_different_business_keys_does_not_match(dimension: str, value: str) -> None:
    payload = _spread([_row()], [_row(**{dimension: value})])
    assert payload["attribution_coverage"]["matched_position_count"] == 0
    assert set(_reasons(payload)) == {"added_position", "exited_position"}
    assert payload["total_spread_effect"] is None


def test_empty_portfolio_and_cost_center_remain_valid_exact_key_dimensions() -> None:
    row = _row(portfolio_name="", cost_center=None)
    payload = _spread([row], [{**row, "ytm": 0.031}])
    assert payload["calculation_status"] == "complete"
    assert payload["total_spread_effect"] == pytest.approx(-200_000)


@pytest.mark.parametrize("dimension", ["instrument_code", "accounting_class", "currency_code"])
def test_missing_required_key_is_not_matched_by_anonymous_row_order(dimension: str) -> None:
    row = _row(**{dimension: None})
    payload = _spread([row], [row])
    assert "missing_position_key" in _reasons(payload)
    assert payload["attribution_coverage"]["attributed_position_count"] == 0


def test_added_exited_and_duplicate_positions_do_not_create_estimated_market_pnl() -> None:
    payload = _spread(
        [_row("A"), _row("EXIT"), _row("DUP"), _row("DUP")],
        [_row("A", ytm=0.031), _row("NEW", ytm=0.15), _row("DUP", ytm=0.2)],
    )
    reasons = _reasons(payload)
    assert payload["total_spread_effect"] == pytest.approx(-200_000)
    assert payload["calculation_status"] == "partial"
    assert reasons["duplicate_position_key"]["start_row_count"] == 2
    assert reasons["added_position"]["end_market_value"] == 100_000_000
    assert reasons["exited_position"]["start_market_value"] == 100_000_000
    assert payload["attribution_coverage"]["covered_start_market_value"] == 100_000_000


@pytest.mark.parametrize("value,status", [(None, "missing"), (0, "dirty"), (float("nan"), "observed"), (float("inf"), "observed")])
@pytest.mark.parametrize("side", ["start", "end"])
def test_missing_or_dirty_ytm_is_excluded_without_other_position_fallback(value: Any, status: str, side: str) -> None:
    starts = [_row("A", market_value=100), _row("B", market_value=900)]
    ends = [_row("A", market_value=100, ytm=0.031), _row("B", market_value=900, ytm=0.032)]
    (starts if side == "start" else ends)[1].update(ytm=value, ytm_input_status=status)
    payload = _spread(starts, ends)
    assert payload["total_spread_effect"] == pytest.approx(-0.2)
    assert payload["attribution_coverage"]["matched_position_count"] == 2
    assert payload["attribution_coverage"]["attributed_position_count"] == 1
    assert f"missing_{side}_ytm" in _reasons(payload)


@pytest.mark.parametrize("ytm", [0, -0.005])
def test_observed_zero_and_negative_ytm_are_not_missing(ytm: float) -> None:
    payload = _spread([_row(ytm=ytm)], [_row(ytm=ytm + 0.001)])
    assert payload["total_spread_effect"] == pytest.approx(-200_000)
    assert payload["calculation_status"] == "complete"


@pytest.mark.parametrize("flag", ["ytm_par_fallback", "ytm_unavailable", "coupon_unavailable"])
def test_unobserved_start_duration_is_excluded_but_unused_end_duration_is_not(flag: str) -> None:
    invalid = _spread([_row(duration_quality_flag=flag)], [_row(ytm=0.031)])
    assert invalid["total_price_change"] is None
    assert "estimated_start_duration" in _reasons(invalid)
    valid = _spread([_row()], [_row(ytm=0.031, duration_quality_flag=flag)])
    assert valid["total_spread_effect"] == pytest.approx(-200_000)


@pytest.mark.parametrize("curve,reason", [
    ({}, "missing_start_curve"),
    ({"5Y": Decimal("NaN")}, "missing_start_curve"),
    ({"10Y": Decimal("2")}, "benchmark_start_tenor_uncovered"),
])
def test_missing_or_uncovered_curve_never_becomes_flat_zero_or_ten_year_fallback(curve: dict[str, Decimal], reason: str) -> None:
    payload = _spread([_row()], [_row(ytm=0.031)], treasury_curve_start=curve)
    assert payload["total_treasury_effect"] is None
    assert reason in _reasons(payload)


def test_non_cny_position_is_not_priced_using_cny_treasury_curve() -> None:
    payload = _spread([_row(currency_code="USD")], [_row(currency_code="USD", ytm=0.031)])
    assert payload["total_price_change"] is None
    assert "unsupported_currency" in _reasons(payload)


def test_invalid_ten_year_reference_does_not_poison_valid_matched_tenor() -> None:
    payload = _spread(
        [_row()], [_row(ytm=0.031)], treasury_10y_start_pct=float("nan"),
        treasury_curve_start={"5Y": Decimal("2"), "10Y": Decimal("NaN")},
    )
    assert payload["treasury_10y_start"] is None
    assert payload["treasury_10y_change"] is None
    assert payload["total_spread_effect"] == pytest.approx(-200_000)


def test_offsetting_nonzero_effects_have_unavailable_contribution_percentages() -> None:
    service = importlib.import_module("backend.app.services.pnl_attribution_service")
    payload = _spread(
        [_row()], [_row()],
        treasury_curve_end={"1Y": Decimal("2.1"), "10Y": Decimal("2.1")},
    )
    item = payload["items"][0]
    assert item["treasury_effect"] == pytest.approx(-200_000)
    assert item["spread_effect"] == pytest.approx(200_000)
    assert item["total_price_effect"] == 0
    assert item["treasury_contribution_pct"] is None
    assert item["spread_contribution_pct"] is None
    result = SpreadAttributionPayload.model_validate(service._promote_spread_payload(payload)).model_dump(mode="json")
    assert result["items"][0]["treasury_contribution_pct"]["raw"] is None
    assert result["items"][0]["spread_contribution_pct"]["raw"] is None


def test_no_valid_pairs_preserve_null_through_service_schema_and_advanced_summary() -> None:
    service = importlib.import_module("backend.app.services.pnl_attribution_service")
    payload = _spread([_row()], [_row(ytm=None)])
    result = SpreadAttributionPayload.model_validate(service._promote_spread_payload(payload)).model_dump(mode="json")
    assert result["total_spread_effect"]["raw"] is None
    assert result["items"][0]["spread_effect"]["raw"] is None
    assert result["calculation_status"] == "unavailable"
    summary = build_advanced_attribution_summary(
        report_date="2026-06-30", carry_payload={}, spread_payload=payload, krd_payload={},
    )
    assert summary["treasury_effect_total"] is None
    assert summary["spread_effect_total"] is None


def test_sub_percent_coverage_preserves_ratio_units_through_schema() -> None:
    service = importlib.import_module("backend.app.services.pnl_attribution_service")
    starts = [_row("A", market_value=100), _row("B", market_value=99_900, ytm=None)]
    payload = _spread(starts, starts)
    result = SpreadAttributionPayload.model_validate(service._promote_spread_payload(payload)).model_dump(mode="json")
    assert result["attribution_coverage"]["start_coverage_pct"]["raw"] == pytest.approx(0.001)
    assert result["attribution_coverage"]["exclusions"][0]["start_market_value"]["unit"] == "yuan"


def test_service_reads_full_curve_and_discloses_resolved_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    service = importlib.import_module("backend.app.services.pnl_attribution_service")

    class Repo:
        def list_report_dates(self) -> list[str]:
            return ["2026-06-30", "2026-05-31"]

        def fetch_bond_analytics_rows(self, *, report_date: str) -> list[dict[str, Any]]:
            return [_row(ytm=0.031 if report_date == "2026-06-30" else 0.03)]

        def fetch_curve(self, trade_date: str, curve_type: str) -> dict[str, Decimal]:
            return {
                "2026-05-29": {"5Y": Decimal("2")},
                "2026-06-30": {"5Y": Decimal("2.1")},
            }.get(trade_date, {})

        def fetch_latest_trade_date_on_or_before(self, curve_type: str, trade_date: str) -> str | None:
            return "2026-05-29" if trade_date == "2026-05-31" else None

    repo = Repo()
    monkeypatch.setattr(service, "_bond_repo", lambda: repo)
    monkeypatch.setattr(service, "_curve_repo", lambda: repo)
    envelope = service._spread_attribution_envelope_uncached(report_date="2026-06-30", lookback_days=30)
    result = envelope["result"]
    assert result["total_treasury_effect"]["raw"] == pytest.approx(-200_000)
    assert result["total_spread_effect"]["raw"] == pytest.approx(0)
    assert result["treasury_10y_start"] is None
    assert result["attribution_coverage"]["attributed_position_count"] == 1
    assert envelope["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert envelope["result_meta"]["rule_version"] == "rv_pnl_attribution_spread_matched_v2"
    assert envelope["result_meta"]["fallback_date"] == "2026-05-29"
    assert envelope["result_meta"]["filters_applied"]["treasury_curve_start_date"] == "2026-05-29"
