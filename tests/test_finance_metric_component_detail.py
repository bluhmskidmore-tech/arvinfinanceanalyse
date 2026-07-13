from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.core_finance.finance_metric_component_detail import (
    FinanceMetricComponentDetailDefinition,
    FinanceMetricComponentParentSummary,
    build_finance_metric_component_detail,
)
from backend.app.core_finance.finance_metric_engine import load_finance_metric_rules
from backend.app.core_finance.finance_metric_period_comparison import (
    NET_INTEREST_COMPONENT_DEFINITIONS,
)
from backend.app.services import (
    candidate_financial_indicator_period_comparison_service as period_service,
)


SOURCE_DIR = Path(__file__).resolve().parents[1] / "data_input" / "pnl_总账对账-日均"
REAL_LEDGER_WORKBOOKS = tuple(
    SOURCE_DIR / f"总账对账{month}.xlsx"
    for month in ("202604", "202605", "202606")
)


def _real_inputs(metric_id: str):
    rules = load_finance_metric_rules(rule_version="qdb-finance-2026-v1.0.1")
    direct_rule = next(item for item in rules["direct_rules"] if item["id"] == metric_id)
    definition = next(
        item for item in NET_INTEREST_COMPONENT_DEFINITIONS if item.metric_id == metric_id
    )
    parent = period_service.candidate_financial_indicator_period_comparison_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
    )
    parent_component = next(
        item
        for item in parent["net_interest_component_bridge"]["components"]
        if item["metric_id"] == metric_id
    )
    source_periods = tuple(
        period_service._load_ledger_only_period(root=SOURCE_DIR, report_month=month)
        for month in ("202606", "202605", "202604")
    )
    source_contracts = tuple(parent["source_periods"])
    return (
        FinanceMetricComponentDetailDefinition(
            metric_id=definition.metric_id,
            metric_name=definition.metric_name,
            formula_weight=definition.formula_weight,
        ),
        direct_rule,
        source_periods,
        source_contracts,
        FinanceMetricComponentParentSummary(
            current_value_yi=Decimal(parent_component["current_value_yi"]),
            previous_value_yi=Decimal(parent_component["previous_value_yi"]),
            component_delta_yi=Decimal(parent_component["component_delta_yi"]),
            contribution_to_net_delta_yi=Decimal(
                parent_component["contribution_to_net_delta_yi"]
            ),
        ),
    )


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_LEDGER_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
@pytest.mark.parametrize(
    ("metric_id", "expected_count", "expected_delta", "expected_contribution"),
    [
        ("income.interest.loan.total", 21, "-0.3473924741", "-0.3473924741"),
        ("expense.interest.deposit.total", 14, "-0.0830909629", "0.0830909629"),
        ("income.interest.investment", 18, "-1.7260319538", "-1.7260319538"),
        ("income.interest.interbank_net", 19, "-0.5727880768", "-0.5727880768"),
    ],
)
def test_component_detail_real_accounts_reconcile_exactly(
    metric_id: str,
    expected_count: int,
    expected_delta: str,
    expected_contribution: str,
) -> None:
    definition, rule, sources, contracts, parent = _real_inputs(metric_id)

    result = build_finance_metric_component_detail(
        report_month="202606",
        definition=definition,
        direct_rule=rule,
        source_periods=sources,
        source_contracts=contracts,
        parent=parent,
    )

    contributing = [item for item in result.rows if item.row_status == "contributing"]
    assert result.status == "available"
    assert result.quality_status == "degraded_candidate"
    assert result.foot_status == "passed"
    assert len(contributing) == expected_count
    assert result.account_component_delta_total_yi == Decimal(expected_delta)
    assert result.account_contribution_total_yi == Decimal(expected_contribution)
    assert result.component_delta_reconciliation_yi == 0
    assert result.contribution_reconciliation_yi == 0


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_LEDGER_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
def test_investment_detail_ranks_exact_source_backed_top_account() -> None:
    definition, rule, sources, contracts, parent = _real_inputs(
        "income.interest.investment"
    )

    result = build_finance_metric_component_detail(
        report_month="202606",
        definition=definition,
        direct_rule=rule,
        source_periods=sources,
        source_contracts=contracts,
        parent=parent,
    )

    top = result.rows[0]
    assert top.account_code == "51402010003"
    assert top.contribution_to_net_delta_yi == Decimal("-1.3160266974")
    assert [item.month for item in top.source_evidence] == [
        "202606",
        "202605",
        "202604",
    ]
    current = top.source_evidence[0]
    assert current.sheet == "综本"
    assert current.row == 1041
    assert current.account_code_cell == "A1041"
    assert current.ending_cell == "G1041"
    assert current.ledger_sha256 == contracts[0]["ledger_sha256"]
    assert top.current_ending_yuan == Decimal("-156368.57")


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_LEDGER_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
def test_interbank_offset_term_is_visible_but_excluded_from_foot() -> None:
    definition, rule, sources, contracts, parent = _real_inputs(
        "income.interest.interbank_net"
    )

    result = build_finance_metric_component_detail(
        report_month="202606",
        definition=definition,
        direct_rule=rule,
        source_periods=sources,
        source_contracts=contracts,
        parent=parent,
    )

    offset = next(item for item in result.rows if item.account_code == "50206000001")
    assert offset.row_status == "excluded_offset"
    assert offset.effective_component_weight == 0
    assert offset.effective_net_weight == 0
    assert [(item.level, item.code, item.weight) for item in offset.matched_terms] == [
        ("l1", "502", Decimal("-1")),
        ("l2", "50206", Decimal("1")),
    ]
    assert offset.contribution_to_net_delta_yi == 0
    assert result.rows[-1] == offset


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_LEDGER_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
def test_component_detail_fails_closed_when_exact_account_sets_differ() -> None:
    definition, rule, sources, contracts, parent = _real_inputs(
        "income.interest.investment"
    )
    previous = sources[1]
    changed_previous = replace(
        previous,
        ledger=tuple(
            row for row in previous.ledger if row.account_code != "51402010003"
        ),
    )

    result = build_finance_metric_component_detail(
        report_month="202606",
        definition=definition,
        direct_rule=rule,
        source_periods=(sources[0], changed_previous, sources[2]),
        source_contracts=contracts,
        parent=parent,
    )

    assert result.status == "not_evaluable"
    assert result.quality_status == "not_evaluable"
    assert result.foot_status == "not_evaluable"
    assert result.rows == ()
    assert result.account_current_total_yi is None
    assert "account_set_mismatch" in result.reasons


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_LEDGER_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
def test_component_detail_failed_foot_hides_account_explanation() -> None:
    definition, rule, sources, contracts, parent = _real_inputs(
        "income.interest.investment"
    )
    drifted_parent = FinanceMetricComponentParentSummary(
        current_value_yi=parent.current_value_yi + Decimal("1"),
        previous_value_yi=parent.previous_value_yi,
        component_delta_yi=parent.component_delta_yi + Decimal("1"),
        contribution_to_net_delta_yi=(
            parent.contribution_to_net_delta_yi + Decimal("1")
        ),
    )

    result = build_finance_metric_component_detail(
        report_month="202606",
        definition=definition,
        direct_rule=rule,
        source_periods=sources,
        source_contracts=contracts,
        parent=drifted_parent,
    )

    assert result.status == "not_evaluable"
    assert result.quality_status == "not_evaluable"
    assert result.foot_status == "failed"
    assert result.rows == ()
    assert result.account_current_total_yi is None
    assert result.account_previous_total_yi is None
    assert result.account_component_delta_total_yi is None
    assert result.account_contribution_total_yi is None
    assert result.current_reconciliation_yi == Decimal("1")
    assert result.previous_reconciliation_yi == 0
    assert result.component_delta_reconciliation_yi == Decimal("1")
    assert result.contribution_reconciliation_yi == Decimal("1")
    assert result.reasons == ("component_account_reconciliation_failed",)
