"""Account-level evidence for one governed net-interest bridge component."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from backend.app.core_finance.finance_metric_period_comparison import (
    _cumulative_mom_for_report_month,
)
from backend.app.core_finance.finance_metric_xlsx import (
    LEDGER_HEADERS,
    FinanceMetricLedgerOnlySourceData,
    LedgerObservation,
)

YI_DIVISOR = Decimal("100000000")
AccountRowStatus = Literal["contributing", "excluded_offset"]
ComponentDetailStatus = Literal["available", "not_evaluable"]
ComponentDetailQuality = Literal[
    "standard_candidate",
    "degraded_candidate",
    "not_evaluable",
]
ComponentDetailFootStatus = Literal["passed", "failed", "not_evaluable"]


@dataclass(frozen=True, slots=True)
class FinanceMetricComponentDetailDefinition:
    metric_id: str
    metric_name: str
    formula_weight: Literal[-1, 1]


@dataclass(frozen=True, slots=True)
class FinanceMetricComponentParentSummary:
    current_value_yi: Decimal
    previous_value_yi: Decimal
    component_delta_yi: Decimal
    contribution_to_net_delta_yi: Decimal


@dataclass(frozen=True, slots=True)
class FinanceMetricComponentMatchedTerm:
    source: Literal["ledger"]
    level: Literal["l1", "l2", "l3", "full"]
    code: str
    weight: Decimal


@dataclass(frozen=True, slots=True)
class FinanceMetricComponentSourceEvidence:
    month: str
    report_date: date
    ledger_file_name: str
    ledger_sha256: str
    locked_sha256: str | None
    lock_status: Literal["locked_match", "unlocked"]
    sheet: Literal["综本"]
    row: int
    account_code_cell: str
    ending_cell: str
    ending_yuan: Decimal


@dataclass(frozen=True, slots=True)
class FinanceMetricComponentDetailRow:
    row_status: AccountRowStatus
    account_code: str
    account_name: str
    currency: Literal["CNX"]
    effective_component_weight: Decimal
    effective_net_weight: Decimal
    matched_terms: tuple[FinanceMetricComponentMatchedTerm, ...]
    current_ending_yuan: Decimal
    previous_ending_yuan: Decimal
    two_month_prior_ending_yuan: Decimal
    current_value_yi: Decimal
    previous_value_yi: Decimal
    component_delta_yi: Decimal
    contribution_to_net_delta_yi: Decimal
    source_evidence: tuple[FinanceMetricComponentSourceEvidence, ...]


@dataclass(frozen=True, slots=True)
class FinanceMetricComponentDetail:
    metric_id: str
    metric_name: str
    formula_weight: Literal[-1, 1]
    status: ComponentDetailStatus
    quality_status: ComponentDetailQuality
    foot_status: ComponentDetailFootStatus
    parent: FinanceMetricComponentParentSummary
    account_current_total_yi: Decimal | None
    account_previous_total_yi: Decimal | None
    account_component_delta_total_yi: Decimal | None
    account_contribution_total_yi: Decimal | None
    current_reconciliation_yi: Decimal | None
    previous_reconciliation_yi: Decimal | None
    component_delta_reconciliation_yi: Decimal | None
    contribution_reconciliation_yi: Decimal | None
    reasons: tuple[str, ...]
    rows: tuple[FinanceMetricComponentDetailRow, ...]


def build_finance_metric_component_detail(
    *,
    report_month: str,
    definition: FinanceMetricComponentDetailDefinition,
    direct_rule: Mapping[str, Any],
    source_periods: tuple[
        FinanceMetricLedgerOnlySourceData,
        FinanceMetricLedgerOnlySourceData,
        FinanceMetricLedgerOnlySourceData,
    ],
    source_contracts: Sequence[Mapping[str, Any]],
    parent: FinanceMetricComponentParentSummary,
) -> FinanceMetricComponentDetail:
    """Expand one fixed component to exact CNX ledger rows and reconcile it."""

    _validate_inputs(
        report_month=report_month,
        definition=definition,
        direct_rule=direct_rule,
        source_periods=source_periods,
        source_contracts=source_contracts,
        parent=parent,
    )
    terms = _direct_terms(direct_rule)
    rows_by_period = tuple(_matched_rows(source, terms) for source in source_periods)
    account_sets = tuple(set(rows) for rows in rows_by_period)
    if account_sets[0] != account_sets[1] or account_sets[0] != account_sets[2]:
        return _not_evaluable(definition, parent, "account_set_mismatch")

    detail_rows = tuple(
        _build_detail_row(
            report_month=report_month,
            definition=definition,
            terms=terms,
            account_code=account_code,
            observations=tuple(rows[account_code] for rows in rows_by_period),
            source_contracts=source_contracts,
        )
        for account_code in sorted(account_sets[0])
    )
    detail_rows = tuple(
        sorted(
            detail_rows,
            key=lambda item: (
                0 if item.row_status == "contributing" else 1,
                -abs(item.contribution_to_net_delta_yi),
                item.account_code,
            ),
        )
    )
    contributing = tuple(
        item for item in detail_rows if item.row_status == "contributing"
    )
    current_total = sum((item.current_value_yi for item in contributing), Decimal(0))
    previous_total = sum((item.previous_value_yi for item in contributing), Decimal(0))
    delta_total = sum((item.component_delta_yi for item in contributing), Decimal(0))
    contribution_total = sum(
        (item.contribution_to_net_delta_yi for item in contributing),
        Decimal(0),
    )
    current_reconciliation = parent.current_value_yi - current_total
    previous_reconciliation = parent.previous_value_yi - previous_total
    delta_reconciliation = parent.component_delta_yi - delta_total
    contribution_reconciliation = (
        parent.contribution_to_net_delta_yi - contribution_total
    )
    passed = all(
        value == 0
        for value in (
            current_reconciliation,
            previous_reconciliation,
            delta_reconciliation,
            contribution_reconciliation,
        )
    )
    base_quality: ComponentDetailQuality = (
        "standard_candidate"
        if all(item["lock_status"] == "locked_match" for item in source_contracts)
        else "degraded_candidate"
    )
    return FinanceMetricComponentDetail(
        metric_id=definition.metric_id,
        metric_name=definition.metric_name,
        formula_weight=definition.formula_weight,
        status="available" if passed else "not_evaluable",
        quality_status=base_quality if passed else "not_evaluable",
        foot_status="passed" if passed else "failed",
        parent=parent,
        account_current_total_yi=current_total if passed else None,
        account_previous_total_yi=previous_total if passed else None,
        account_component_delta_total_yi=delta_total if passed else None,
        account_contribution_total_yi=contribution_total if passed else None,
        current_reconciliation_yi=current_reconciliation,
        previous_reconciliation_yi=previous_reconciliation,
        component_delta_reconciliation_yi=delta_reconciliation,
        contribution_reconciliation_yi=contribution_reconciliation,
        reasons=() if passed else ("component_account_reconciliation_failed",),
        rows=detail_rows if passed else (),
    )


def _validate_inputs(
    *,
    report_month: str,
    definition: FinanceMetricComponentDetailDefinition,
    direct_rule: Mapping[str, Any],
    source_periods: Sequence[FinanceMetricLedgerOnlySourceData],
    source_contracts: Sequence[Mapping[str, Any]],
    parent: FinanceMetricComponentParentSummary,
) -> None:
    if direct_rule.get("id") != definition.metric_id:
        raise ValueError("direct rule must match the component definition")
    if len(source_periods) != 3 or len(source_contracts) != 3:
        raise ValueError("component detail requires exactly three source periods")
    if tuple(item.report_month for item in source_periods)[0] != report_month:
        raise ValueError("current source period must match report_month")
    if any(
        not value.is_finite()
        for value in (
            parent.current_value_yi,
            parent.previous_value_yi,
            parent.component_delta_yi,
            parent.contribution_to_net_delta_yi,
        )
    ):
        raise ValueError("parent component values must be finite Decimals")
    for source, contract in zip(source_periods, source_contracts, strict=True):
        if (
            contract.get("month") != source.report_month
            or str(contract.get("report_date")) != source.report_date.isoformat()
            or contract.get("ledger_sha256") != source.ledger_sha256
        ):
            raise ValueError("source contracts must match parsed ledger periods")
        if contract.get("lock_status") == "locked_mismatch":
            raise ValueError("locked source mismatches are forbidden")


def _direct_terms(
    direct_rule: Mapping[str, Any],
) -> tuple[FinanceMetricComponentMatchedTerm, ...]:
    terms: list[FinanceMetricComponentMatchedTerm] = []
    for raw in direct_rule.get("terms", ()):
        source = str(raw.get("source") or "")
        level = str(raw.get("level") or "")
        code = str(raw.get("code") or "")
        weight = Decimal(str(raw.get("weight")))
        if source != "ledger" or level not in {"l1", "l2", "l3", "full"}:
            raise ValueError("component detail supports fixed ledger direct terms only")
        if not code.isdigit() or not weight.is_finite():
            raise ValueError("component direct term is invalid")
        terms.append(
            FinanceMetricComponentMatchedTerm(
                source="ledger",
                level=level,  # type: ignore[arg-type]
                code=code,
                weight=weight,
            )
        )
    if not terms:
        raise ValueError("component direct rule must contain ledger terms")
    return tuple(terms)


def _matched_rows(
    source: FinanceMetricLedgerOnlySourceData,
    terms: tuple[FinanceMetricComponentMatchedTerm, ...],
) -> dict[str, LedgerObservation]:
    matched: dict[str, LedgerObservation] = {}
    for row in source.ledger:
        if row.currency != "CNX":
            continue
        if not _matching_terms(row.account_code, terms):
            continue
        if row.account_code in matched:
            raise ValueError("duplicate CNX account source identity")
        matched[row.account_code] = row
    return matched


def _matching_terms(
    account_code: str,
    terms: tuple[FinanceMetricComponentMatchedTerm, ...],
) -> tuple[FinanceMetricComponentMatchedTerm, ...]:
    lengths = {"l1": 3, "l2": 5, "l3": 7}
    return tuple(
        term
        for term in terms
        if (
            account_code == term.code
            if term.level == "full"
            else account_code[: lengths[term.level]] == term.code
        )
    )


def _build_detail_row(
    *,
    report_month: str,
    definition: FinanceMetricComponentDetailDefinition,
    terms: tuple[FinanceMetricComponentMatchedTerm, ...],
    account_code: str,
    observations: tuple[LedgerObservation, LedgerObservation, LedgerObservation],
    source_contracts: Sequence[Mapping[str, Any]],
) -> FinanceMetricComponentDetailRow:
    matched_terms = _matching_terms(account_code, terms)
    component_weight = sum((item.weight for item in matched_terms), Decimal(0))
    net_weight = component_weight * Decimal(definition.formula_weight)
    comparison = _cumulative_mom_for_report_month(
        report_month=report_month,
        current_cumulative=observations[0].ending,
        prior_cumulative=observations[1].ending,
        two_month_prior_cumulative=observations[2].ending,
    )
    assert comparison.current_month is not None
    assert comparison.previous_month is not None
    current_value = comparison.current_month * component_weight / YI_DIVISOR
    previous_value = comparison.previous_month * component_weight / YI_DIVISOR
    delta = current_value - previous_value
    contribution = delta * Decimal(definition.formula_weight)
    evidence = tuple(
        _source_evidence(observation, contract)
        for observation, contract in zip(
            observations,
            source_contracts,
            strict=True,
        )
    )
    return FinanceMetricComponentDetailRow(
        row_status=("contributing" if component_weight != 0 else "excluded_offset"),
        account_code=account_code,
        account_name=observations[0].account_name,
        currency="CNX",
        effective_component_weight=component_weight,
        effective_net_weight=net_weight,
        matched_terms=matched_terms,
        current_ending_yuan=observations[0].ending,
        previous_ending_yuan=observations[1].ending,
        two_month_prior_ending_yuan=observations[2].ending,
        current_value_yi=current_value,
        previous_value_yi=previous_value,
        component_delta_yi=delta,
        contribution_to_net_delta_yi=contribution,
        source_evidence=evidence,
    )


def _source_evidence(
    observation: LedgerObservation,
    contract: Mapping[str, Any],
) -> FinanceMetricComponentSourceEvidence:
    refs = dict(observation.cell_refs)
    account_code_cell = refs.get(LEDGER_HEADERS[0], "")
    ending_cell = refs.get(LEDGER_HEADERS[-1], "")
    if not account_code_cell or not ending_cell:
        raise ValueError("component source row requires account and ending cell locators")
    return FinanceMetricComponentSourceEvidence(
        month=str(contract["month"]),
        report_date=observation_report_date(contract),
        ledger_file_name=str(contract["ledger_file_name"]),
        ledger_sha256=str(contract["ledger_sha256"]),
        locked_sha256=(
            str(contract["locked_sha256"])
            if contract.get("locked_sha256") is not None
            else None
        ),
        lock_status=str(contract["lock_status"]),  # type: ignore[arg-type]
        sheet="综本",
        row=observation.row,
        account_code_cell=account_code_cell,
        ending_cell=ending_cell,
        ending_yuan=observation.ending,
    )


def observation_report_date(contract: Mapping[str, Any]) -> date:
    value = contract["report_date"]
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _not_evaluable(
    definition: FinanceMetricComponentDetailDefinition,
    parent: FinanceMetricComponentParentSummary,
    reason: str,
) -> FinanceMetricComponentDetail:
    return FinanceMetricComponentDetail(
        metric_id=definition.metric_id,
        metric_name=definition.metric_name,
        formula_weight=definition.formula_weight,
        status="not_evaluable",
        quality_status="not_evaluable",
        foot_status="not_evaluable",
        parent=parent,
        account_current_total_yi=None,
        account_previous_total_yi=None,
        account_component_delta_total_yi=None,
        account_contribution_total_yi=None,
        current_reconciliation_yi=None,
        previous_reconciliation_yi=None,
        component_delta_reconciliation_yi=None,
        contribution_reconciliation_yi=None,
        reasons=(reason,),
        rows=(),
    )
