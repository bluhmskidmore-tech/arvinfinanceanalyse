from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.action_attribution import (
    bond_analytics_action_line_payload,
    build_action_attribution_placeholder_payload,
    build_action_attribution_success_payload,
    select_action_attribution_pnl_report_dates,
)


def test_bond_analytics_action_line_payload_maps_service_row_to_core_input() -> None:
    payload = bond_analytics_action_line_payload(
        {
            "instrument_code": "BOND-001",
            "portfolio_name": "Portfolio A",
            "cost_center": "Desk 7",
            "market_value": Decimal("100.50"),
            "modified_duration": Decimal("3.25"),
            "asset_class_std": "OCI",
            "accounting_class": "TPL",
        }
    )

    assert payload == {
        "bond_code": "BOND-001",
        "book_id": "Portfolio A::Desk 7",
        "market_value": Decimal("100.50"),
        "modified_duration": Decimal("3.25"),
        "asset_class": "OCI",
    }


def test_bond_analytics_action_line_payload_does_not_treat_accrued_interest_as_action_input() -> None:
    payload = bond_analytics_action_line_payload(
        {
            "instrument_code": "BOND-AI-001",
            "portfolio_name": "Portfolio A",
            "cost_center": "Desk 7",
            "market_value": Decimal("100.50"),
            "modified_duration": Decimal("3.25"),
            "asset_class_std": "credit",
            "accrued_interest": Decimal("9.99"),
            "accrued_interest_cny": Decimal("69.93"),
        }
    )

    assert "accrued_interest" not in payload
    assert "accrued_interest_cny" not in payload
    assert payload["market_value"] == Decimal("100.50")


def test_bond_analytics_action_line_payload_falls_back_to_accounting_class() -> None:
    payload = bond_analytics_action_line_payload(
        {
            "instrument_code": "BOND-002",
            "market_value": Decimal("80"),
            "modified_duration": Decimal("2"),
            "accounting_class": "AC",
        }
    )

    assert payload["book_id"] == "::"
    assert payload["asset_class"] == "AC"


def test_build_action_attribution_success_payload_marks_missing_pnl_and_dedupes_warnings() -> None:
    payload = build_action_attribution_success_payload(
        report_date=date(2026, 3, 31),
        period_type="MoM",
        raw={
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "total_actions": 1,
            "total_pnl_from_actions": 0.0,
            "by_action_type": [
                {
                    "action_type": "TIMING_BUY",
                    "action_type_name": "Buy",
                    "action_count": 1,
                    "total_pnl_economic": 0.0,
                    "total_pnl_accounting": 0.0,
                    "avg_pnl_per_action": 0.0,
                }
            ],
            "action_details": [
                {
                    "action_id": "1",
                    "action_type": "TIMING_BUY",
                    "action_date": "2026-03-31",
                    "bonds_involved": ["BOND-001"],
                    "description": "new position",
                    "pnl_economic": 0.0,
                    "pnl_accounting": 0.0,
                    "delta_duration": 3.2,
                    "delta_dv01": 0.0,
                    "delta_spread_dv01": 0.0,
                }
            ],
            "period_start_duration": 0.0,
            "period_end_duration": 3.2,
            "duration_change_from_actions": 3.2,
            "period_start_dv01": 0.0,
            "period_end_dv01": 0.0,
            "warnings": ["ACTION_ATTRIBUTION_HEURISTIC_NO_WIND", "ACTION_ATTRIBUTION_HEURISTIC_NO_WIND"],
        },
        prior_snapshot_date=None,
        pnl_by_key={},
        pnl_warning_codes=["ACTION_ATTRIBUTION_PNL517_NO_FACT_DATES"],
        computed_at="2026-03-31T10:00:00+00:00",
    )

    assert payload["status"] == "ready"
    assert payload["available_components"] == ["snapshot_diff", "capital_gain_517_allocation"]
    assert payload["missing_inputs"] == ["fact_formal_pnl_fi_capital_gain_517"]
    assert payload["blocked_components"] == []
    assert payload["computed_at"] == "2026-03-31T10:00:00+00:00"
    assert payload["warnings"] == [
        "ACTION_ATTRIBUTION_HEURISTIC_NO_WIND",
        "ACTION_ATTRIBUTION_NO_PRIOR_SNAPSHOT",
        "ACTION_ATTRIBUTION_PNL517_NO_FACT_DATES",
    ]
    assert payload["warnings_detail"] == [
        {"code": code, "level": "warning", "message": code}
        for code in payload["warnings"]
    ]


def test_build_action_attribution_placeholder_payload_uses_summary_defaults_and_warning_details() -> None:
    payload = build_action_attribution_placeholder_payload(
        report_date=date(2026, 3, 31),
        summary={
            "period_type": "MoM",
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "total_actions": 0,
            "total_pnl_from_actions": "0",
            "period_start_duration": "0",
            "period_end_duration": "0",
            "duration_change_from_actions": "0",
            "period_start_dv01": "0",
            "period_end_dv01": "0",
            "missing_inputs": ["trade_level_action_facts"],
            "blocked_components": ["action_attribution"],
        },
        facets={
            "by_action_type": [],
            "action_details": [],
        },
        warnings=[
            {"code": "empty", "level": "warning", "message": "no attribution rows"},
            {"code": "empty", "level": "warning", "message": "no attribution rows"},
        ],
        generated_at="2026-03-31T10:00:00+00:00",
        default_status="ready",
    )

    assert payload["report_date"] == date(2026, 3, 31)
    assert payload["period_type"] == "MoM"
    assert payload["period_start"] == date(2026, 3, 1)
    assert payload["period_end"] == date(2026, 3, 31)
    assert payload["status"] == "ready"
    assert payload["missing_inputs"] == ["trade_level_action_facts"]
    assert payload["blocked_components"] == ["action_attribution"]
    assert payload["computed_at"] == "2026-03-31T10:00:00+00:00"
    assert payload["warnings"] == ["no attribution rows"]
    assert payload["warnings_detail"] == [
        {"code": "empty", "level": "warning", "message": "no attribution rows"}
    ]


def test_select_action_attribution_pnl_report_dates_filters_period_and_warns_on_multi_month() -> None:
    selected, warnings = select_action_attribution_pnl_report_dates(
        available_report_dates=[
            "2026-01-31",
            "2026-02-28",
            "2026-03-31",
            "2026-03-31",
            "not-a-date",
            "2026-04-30",
        ],
        period_type="YTD",
        period_start=date(2026, 2, 1),
        period_end=date(2026, 3, 31),
    )

    assert selected == ["2026-02-28", "2026-03-31"]
    assert warnings == ["ACTION_ATTRIBUTION_PNL517_MULTI_MONTH_SUM"]


def test_select_action_attribution_pnl_report_dates_uses_period_end_for_mom() -> None:
    selected, warnings = select_action_attribution_pnl_report_dates(
        available_report_dates=["2026-01-31", "not-a-date"],
        period_type="MoM",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
    )

    assert selected == ["2026-03-31"]
    assert warnings == []
