from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.action_attribution import (
    bond_analytics_action_line_payload,
    build_action_attribution_placeholder_payload,
    build_action_attribution_success_payload,
    compute_action_attribution_bonds,
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


def test_compute_action_attribution_bonds_closes_totals_for_no_significant_change_position() -> None:
    """存续持仓久期/市值变动均低于阈值时不生成 detail 行，但需在
    ``by_action_type`` 中以 UNALLOCATED 汇总行披露，使合计与
    ``total_pnl_from_actions`` 闭合（回归 by_action_type 与 total 不闭合的缺陷）。
    """
    positions_start = [
        {
            "bond_code": "BOND-HOLD",
            "book_id": "PF::Desk",
            "market_value": Decimal("100000000"),
            "modified_duration": Decimal("3.00"),
            "asset_class": "rate",
        }
    ]
    positions_end = [
        {
            "bond_code": "BOND-HOLD",
            "book_id": "PF::Desk",
            "market_value": Decimal("100500000"),  # +0.5%，低于 mv_ratio_epsilon(2%)
            "modified_duration": Decimal("3.05"),  # +0.05，低于 duration_epsilon(0.15)
            "asset_class": "rate",
        }
    ]
    pnl_by_key = {"BOND-HOLD::PF::Desk": Decimal("42000")}

    raw = compute_action_attribution_bonds(
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        positions_start=positions_start,
        positions_end=positions_end,
        pnl_by_key=pnl_by_key,
    )

    assert raw["total_actions"] == 0
    assert raw["action_details"] == []
    assert raw["total_pnl_from_actions"] == pytest.approx(42000.0)

    by_type = {row["action_type"]: row for row in raw["by_action_type"]}
    assert "UNALLOCATED" in by_type
    assert by_type["UNALLOCATED"]["action_count"] == 1
    assert by_type["UNALLOCATED"]["total_pnl_economic"] == pytest.approx(42000.0)

    detail_sum = sum(row["total_pnl_economic"] for row in raw["by_action_type"])
    assert detail_sum == pytest.approx(raw["total_pnl_from_actions"])
    assert "ACTION_ATTRIBUTION_PNL_NOT_FULLY_IN_DETAILS" not in raw["warnings"]


def test_compute_action_attribution_bonds_closes_totals_with_mixed_buy_sell_and_hold() -> None:
    """买入/卖出正常生成 detail 行，同时存在的存续无显著变化持仓通过
    UNALLOCATED 行闭合，既有分类行为保持回归。
    """
    positions_start = [
        {
            "bond_code": "BOND-SELL",
            "book_id": "PF::Desk",
            "market_value": Decimal("50000000"),
            "modified_duration": Decimal("2.5"),
            "asset_class": "credit",
        },
        {
            "bond_code": "BOND-HOLD",
            "book_id": "PF::Desk",
            "market_value": Decimal("100000000"),
            "modified_duration": Decimal("3.00"),
            "asset_class": "rate",
        },
    ]
    positions_end = [
        {
            "bond_code": "BOND-HOLD",
            "book_id": "PF::Desk",
            "market_value": Decimal("100500000"),
            "modified_duration": Decimal("3.05"),
            "asset_class": "rate",
        },
        {
            "bond_code": "BOND-BUY",
            "book_id": "PF::Desk",
            "market_value": Decimal("30000000"),
            "modified_duration": Decimal("4.00"),
            "asset_class": "rate",
        },
    ]
    pnl_by_key = {
        "BOND-SELL::PF::Desk": Decimal("-15000"),
        "BOND-HOLD::PF::Desk": Decimal("42000"),
        "BOND-BUY::PF::Desk": Decimal("8000"),
    }

    raw = compute_action_attribution_bonds(
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        positions_start=positions_start,
        positions_end=positions_end,
        pnl_by_key=pnl_by_key,
    )

    assert raw["total_actions"] == 2
    action_types_in_details = {d["action_type"] for d in raw["action_details"]}
    assert action_types_in_details == {"TIMING_BUY", "TIMING_SELL"}
    # 会计口径当前仍是经济口径的占位复制值（详见函数 docstring）。
    for detail in raw["action_details"]:
        assert detail["pnl_accounting"] == pytest.approx(detail["pnl_economic"])

    by_type = {row["action_type"]: row for row in raw["by_action_type"]}
    assert "UNALLOCATED" in by_type
    assert by_type["UNALLOCATED"]["action_count"] == 1
    assert by_type["UNALLOCATED"]["total_pnl_economic"] == pytest.approx(42000.0)

    assert raw["total_pnl_from_actions"] == pytest.approx(35000.0)
    detail_sum = sum(row["total_pnl_economic"] for row in raw["by_action_type"])
    assert detail_sum == pytest.approx(raw["total_pnl_from_actions"])
    assert "ACTION_ATTRIBUTION_PNL_NOT_FULLY_IN_DETAILS" not in raw["warnings"]


def test_compute_action_attribution_bonds_omits_unallocated_row_when_fully_covered() -> None:
    """既有场景（全部持仓变动均生成 detail 行）不应出现多余的 UNALLOCATED 行。"""
    positions_end = [
        {
            "bond_code": "BOND-NEW",
            "book_id": "PF::Desk",
            "market_value": Decimal("10000000"),
            "modified_duration": Decimal("5.0"),
            "asset_class": "rate",
        }
    ]
    pnl_by_key = {"BOND-NEW::PF::Desk": Decimal("1000")}

    raw = compute_action_attribution_bonds(
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        positions_start=[],
        positions_end=positions_end,
        pnl_by_key=pnl_by_key,
    )

    action_types = {row["action_type"] for row in raw["by_action_type"]}
    assert "UNALLOCATED" not in action_types
    assert raw["total_pnl_from_actions"] == pytest.approx(1000.0)
