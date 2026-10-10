from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.finance_metric_engine import FinanceMetricResult
from backend.app.core_finance.finance_metric_period_comparison import (
    KEY_METRIC_DEFINITIONS,
    build_finance_metric_period_comparisons,
    build_net_interest_component_bridge,
)


def _metric(
    metric_id: str,
    value: str | None,
    *,
    status: str = "ok",
) -> FinanceMetricResult:
    return FinanceMetricResult(
        id=metric_id,
        name=metric_id,
        category="test",
        basis="point" if metric_id.endswith("::point") else "cumulative",
        unit="亿元",
        value=Decimal(value) if value is not None else None,
        status=status,  # type: ignore[arg-type]
        reasons=() if status == "ok" else (f"{metric_id}:{status}",),
        lineage=None,
    )


def _period(
    values: dict[str, tuple[str | None, str]],
) -> tuple[FinanceMetricResult, ...]:
    return tuple(
        _metric(metric_id, value, status=status)
        for metric_id, (value, status) in values.items()
    )


def test_build_period_comparisons_uses_cumulative_month_conversion_and_point_basis() -> (
    None
):
    interest_id = "income.interest.net"
    point_id = "balance.deposit.corporate.total::point"
    current = _period({interest_id: ("130", "ok"), point_id: ("120", "ok")})
    prior = _period({interest_id: ("100", "ok"), point_id: ("100", "ok")})
    two_prior = _period({interest_id: ("80", "ok"), point_id: ("90", "ok")})

    rows = build_finance_metric_period_comparisons(
        report_month="202606",
        current_metrics=current,
        previous_metrics=prior,
        two_month_prior_metrics=two_prior,
        comparable_quality_status="degraded_candidate",
    )
    by_id = {row.metric_id: row for row in rows}

    interest = by_id[interest_id]
    assert interest.method == "finance_metric_cumulative_mom"
    assert interest.current_value_yi == Decimal("30")
    assert interest.previous_value_yi == Decimal("20")
    assert interest.delta_yi == Decimal("10")
    assert interest.change_rate == Decimal("0.5")
    assert interest.comparison_status == "comparable"
    assert interest.quality_status == "degraded_candidate"
    assert interest.current_source_value_yi == Decimal("130")
    assert interest.previous_source_value_yi == Decimal("100")
    assert interest.two_month_prior_source_value_yi == Decimal("80")

    point = by_id[point_id]
    assert point.method == "finance_metric_point_to_point"
    assert point.current_value_yi == Decimal("120")
    assert point.previous_value_yi == Decimal("100")
    assert point.delta_yi == Decimal("20")
    assert point.change_rate == Decimal("0.2")


def test_build_period_comparisons_blocks_warning_metrics_and_preserves_zero_denominator_reason() -> (
    None
):
    noninterest_id = "income.noninterest.total"
    point_id = "balance.deposit.corporate.total::point"
    current = _period({noninterest_id: ("10", "warning"), point_id: ("5", "ok")})
    prior = _period({noninterest_id: ("8", "warning"), point_id: ("0", "ok")})
    two_prior = _period({noninterest_id: ("7", "warning"), point_id: ("2", "ok")})

    rows = build_finance_metric_period_comparisons(
        report_month="202606",
        current_metrics=current,
        previous_metrics=prior,
        two_month_prior_metrics=two_prior,
        comparable_quality_status="standard_candidate",
    )
    by_id = {row.metric_id: row for row in rows}

    blocked = by_id[noninterest_id]
    assert blocked.comparison_status == "not_comparable"
    assert blocked.current_value_yi is None
    assert blocked.previous_value_yi is None
    assert blocked.delta_yi is None
    assert blocked.change_rate is None
    assert blocked.rate_reason == "metric_status_not_ok"
    assert blocked.quality_status == "not_comparable"
    assert blocked.current_source_value_yi == Decimal("10")

    zero = by_id[point_id]
    assert zero.comparison_status == "comparable"
    assert zero.delta_yi == Decimal("5")
    assert zero.change_rate is None
    assert zero.rate_reason == "zero_denominator"


def test_january_cumulative_comparison_resets_at_year_boundary() -> None:
    metric_id = "income.interest.net"
    rows = build_finance_metric_period_comparisons(
        report_month="202701",
        current_metrics=_period({metric_id: ("12", "ok")}),
        previous_metrics=_period({metric_id: ("120", "ok")}),
        two_month_prior_metrics=_period({metric_id: ("100", "ok")}),
        comparable_quality_status="degraded_candidate",
    )

    row = next(item for item in rows if item.metric_id == metric_id)
    assert row.current_value_yi == Decimal("12")
    assert row.previous_value_yi == Decimal("20")
    assert row.delta_yi == Decimal("-8")
    assert row.change_rate == Decimal("-0.4")


def test_february_cumulative_comparison_uses_january_cumulative_as_january_month() -> (
    None
):
    metric_id = "income.interest.net"
    rows = build_finance_metric_period_comparisons(
        report_month="202702",
        current_metrics=_period({metric_id: ("30", "ok")}),
        previous_metrics=_period({metric_id: ("12", "ok")}),
        two_month_prior_metrics=_period({metric_id: ("120", "ok")}),
        comparable_quality_status="degraded_candidate",
    )

    row = next(item for item in rows if item.metric_id == metric_id)
    assert row.current_value_yi == Decimal("18")
    assert row.previous_value_yi == Decimal("12")
    assert row.delta_yi == Decimal("6")
    assert row.change_rate == Decimal("0.5")


def test_key_metric_definitions_are_fixed_and_ordered() -> None:
    assert [item.metric_id for item in KEY_METRIC_DEFINITIONS] == [
        "income.interest.net",
        "income.noninterest.total",
        "income.operating.mother_bank",
        "balance.deposit.corporate.total::point",
        "balance.deposit.retail.total::point",
        "balance.loan.corporate.total::point",
        "balance.loan.retail.total::point",
    ]
    assert all(item.unit == "亿元" for item in KEY_METRIC_DEFINITIONS)


def _net_interest_row(
    *,
    report_month: str,
    current: str,
    previous: str,
    two_month_prior: str,
):
    return next(
        item
        for item in build_finance_metric_period_comparisons(
            report_month=report_month,
            current_metrics=_period({"income.interest.net": (current, "ok")}),
            previous_metrics=_period({"income.interest.net": (previous, "ok")}),
            two_month_prior_metrics=_period(
                {"income.interest.net": (two_month_prior, "ok")}
            ),
            comparable_quality_status="degraded_candidate",
        )
        if item.metric_id == "income.interest.net"
    )


def _interest_components(
    *,
    loan: tuple[str | None, str],
    deposit: tuple[str | None, str],
    investment: tuple[str | None, str],
    interbank: tuple[str | None, str],
) -> tuple[FinanceMetricResult, ...]:
    return _period(
        {
            "income.interest.loan.total": loan,
            "expense.interest.deposit.total": deposit,
            "income.interest.investment": investment,
            "income.interest.interbank_net": interbank,
        }
    )


def test_net_interest_component_bridge_reconciles_signed_decimal_contributions() -> (
    None
):
    current = _interest_components(
        loan=("130", "ok"),
        deposit=("48", "ok"),
        investment=("37", "ok"),
        interbank=("10", "ok"),
    )
    previous = _interest_components(
        loan=("100", "ok"),
        deposit=("40", "ok"),
        investment=("30", "ok"),
        interbank=("8", "ok"),
    )
    two_month_prior = _interest_components(
        loan=("80", "ok"),
        deposit=("30", "ok"),
        investment=("20", "ok"),
        interbank=("5", "ok"),
    )

    bridge = build_net_interest_component_bridge(
        report_month="202606",
        current_metrics=current,
        previous_metrics=previous,
        two_month_prior_metrics=two_month_prior,
        net_interest_row=_net_interest_row(
            report_month="202606",
            current="129",
            previous="98",
            two_month_prior="75",
        ),
        comparable_quality_status="degraded_candidate",
    )

    assert bridge.analysis_kind == "accounting_component_bridge"
    assert bridge.status == "available"
    assert bridge.metric_id == "income.interest.net"
    assert bridge.basis == "calendar_month_from_cumulative"
    assert bridge.method == "finance_metric_component_contribution"
    assert bridge.unit == "亿元"
    assert bridge.quality_status == "degraded_candidate"
    assert bridge.foot_status == "passed"
    assert bridge.net_delta_yi == Decimal("8")
    assert bridge.component_contribution_total_yi == Decimal("8")
    assert bridge.reconciliation_delta_yi == Decimal("0")
    assert bridge.reasons == ()
    assert [item.metric_id for item in bridge.components] == [
        "income.interest.loan.total",
        "expense.interest.deposit.total",
        "income.interest.investment",
        "income.interest.interbank_net",
    ]
    assert [item.formula_weight for item in bridge.components] == [1, -1, 1, 1]
    assert [item.current_value_yi for item in bridge.components] == [
        Decimal("30"),
        Decimal("8"),
        Decimal("7"),
        Decimal("2"),
    ]
    assert [item.previous_value_yi for item in bridge.components] == [
        Decimal("20"),
        Decimal("10"),
        Decimal("10"),
        Decimal("3"),
    ]
    assert [item.component_delta_yi for item in bridge.components] == [
        Decimal("10"),
        Decimal("-2"),
        Decimal("-3"),
        Decimal("-1"),
    ]
    assert [item.contribution_to_net_delta_yi for item in bridge.components] == [
        Decimal("10"),
        Decimal("2"),
        Decimal("-3"),
        Decimal("-1"),
    ]
    assert bridge.components[1].current_source_value_yi == Decimal("48")
    assert bridge.components[1].previous_source_value_yi == Decimal("40")
    assert bridge.components[1].two_month_prior_source_value_yi == Decimal("30")


@pytest.mark.parametrize(
    (
        "report_month",
        "current",
        "previous",
        "two_month_prior",
        "expected_current",
        "expected_previous",
        "expected_delta",
    ),
    [
        ("202701", "12", "120", "100", "12", "20", "-8"),
        ("202702", "30", "12", "120", "18", "12", "6"),
    ],
)
def test_net_interest_component_bridge_preserves_calendar_year_reset_rules(
    report_month: str,
    current: str,
    previous: str,
    two_month_prior: str,
    expected_current: str,
    expected_previous: str,
    expected_delta: str,
) -> None:
    zero_components = {
        "deposit": ("0", "ok"),
        "investment": ("0", "ok"),
        "interbank": ("0", "ok"),
    }
    bridge = build_net_interest_component_bridge(
        report_month=report_month,
        current_metrics=_interest_components(loan=(current, "ok"), **zero_components),
        previous_metrics=_interest_components(loan=(previous, "ok"), **zero_components),
        two_month_prior_metrics=_interest_components(
            loan=(two_month_prior, "ok"), **zero_components
        ),
        net_interest_row=_net_interest_row(
            report_month=report_month,
            current=current,
            previous=previous,
            two_month_prior=two_month_prior,
        ),
        comparable_quality_status="degraded_candidate",
    )

    loan = bridge.components[0]
    assert bridge.status == "available"
    assert loan.current_value_yi == Decimal(expected_current)
    assert loan.previous_value_yi == Decimal(expected_previous)
    assert loan.component_delta_yi == Decimal(expected_delta)
    assert loan.contribution_to_net_delta_yi == Decimal(expected_delta)
    assert bridge.net_delta_yi == Decimal(expected_delta)
    assert bridge.reconciliation_delta_yi == Decimal("0")


def test_net_interest_component_bridge_fails_closed_when_any_period_is_not_ok() -> None:
    bridge = build_net_interest_component_bridge(
        report_month="202606",
        current_metrics=_interest_components(
            loan=("130", "ok"),
            deposit=("48", "warning"),
            investment=("37", "ok"),
            interbank=("10", "ok"),
        ),
        previous_metrics=_interest_components(
            loan=("100", "ok"),
            deposit=("40", "ok"),
            investment=("30", "ok"),
            interbank=("8", "ok"),
        ),
        two_month_prior_metrics=_interest_components(
            loan=("80", "ok"),
            deposit=("30", "ok"),
            investment=("20", "ok"),
            interbank=("5", "ok"),
        ),
        net_interest_row=_net_interest_row(
            report_month="202606",
            current="129",
            previous="98",
            two_month_prior="75",
        ),
        comparable_quality_status="degraded_candidate",
    )

    assert bridge.status == "not_evaluable"
    assert bridge.quality_status == "not_evaluable"
    assert bridge.foot_status == "not_evaluable"
    assert bridge.net_delta_yi is None
    assert bridge.component_contribution_total_yi is None
    assert bridge.reconciliation_delta_yi is None
    assert bridge.reasons
    assert all(item.current_value_yi is None for item in bridge.components)
    assert all(item.component_delta_yi is None for item in bridge.components)
    assert all(item.contribution_to_net_delta_yi is None for item in bridge.components)


def test_net_interest_component_bridge_marks_failed_foot_as_not_evaluable() -> None:
    bridge = build_net_interest_component_bridge(
        report_month="202606",
        current_metrics=_interest_components(
            loan=("130", "ok"),
            deposit=("48", "ok"),
            investment=("37", "ok"),
            interbank=("10", "ok"),
        ),
        previous_metrics=_interest_components(
            loan=("100", "ok"),
            deposit=("40", "ok"),
            investment=("30", "ok"),
            interbank=("8", "ok"),
        ),
        two_month_prior_metrics=_interest_components(
            loan=("80", "ok"),
            deposit=("30", "ok"),
            investment=("20", "ok"),
            interbank=("5", "ok"),
        ),
        net_interest_row=_net_interest_row(
            report_month="202606",
            current="130",
            previous="98",
            two_month_prior="75",
        ),
        comparable_quality_status="degraded_candidate",
    )

    assert bridge.status == "not_evaluable"
    assert bridge.quality_status == "not_evaluable"
    assert bridge.foot_status == "failed"
    assert bridge.net_delta_yi == Decimal("9")
    assert bridge.component_contribution_total_yi == Decimal("8")
    assert bridge.reconciliation_delta_yi == Decimal("1")
    assert bridge.reasons
