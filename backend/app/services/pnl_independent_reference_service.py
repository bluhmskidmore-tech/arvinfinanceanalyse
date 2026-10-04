from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from backend.app.core_finance.pnl_independent_reconciliation import (
    FACT_MATERIALIZED_ADJUSTMENT_STAGE,
    PNL_COMPONENTS,
    IndependentPnlComponentReference,
    IndependentPnlReference,
    reconcile_pnl_overview_to_independent_reference,
)
from backend.app.repositories.pnl_independent_reference_repo import (
    PnlFormalFactDependencyBinding,
    PnlIndependentReferenceRepository,
)
from backend.app.services.product_category_source_service import (
    SourcePair,
    build_ledger_only_facts,
)
from backend.app.services.source_file_hash import sha256_file

LEDGER_REFERENCE_RULE_VERSION = "rv_pnl_independent_ledger_reference_v1"
LEDGER_COMPONENTS = PNL_COMPONENTS[:3]


@dataclass(frozen=True, slots=True)
class LedgerPnlComponentScope:
    status: Literal["ready", "pending"]
    account_prefixes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    zero_observation_evidence_refs: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if self.status == "ready":
            if not self.account_prefixes:
                raise ValueError("A ready ledger component scope requires account_prefixes")
            if not self.evidence_refs:
                raise ValueError("A ready ledger component scope requires evidence_refs")
        elif self.status == "pending":
            if not self.reason.strip():
                raise ValueError("A pending ledger component scope requires a reason")
        else:
            raise ValueError(f"Unsupported ledger component scope status={self.status!r}")


def pending_component_reference(reason: str) -> IndependentPnlComponentReference:
    return IndependentPnlComponentReference(status="pending", reason=reason)


def ready_adjustment_reference(
    amount_yuan: Decimal,
    *,
    evidence_refs: tuple[str, ...],
) -> IndependentPnlComponentReference:
    """Create the post-approval adjustment side of an independent reference.

    Supplying zero is allowed only when ``evidence_refs`` proves that the
    approved adjustment population for the report date was checked and empty.
    """

    return IndependentPnlComponentReference(
        status="ready",
        value_yuan=amount_yuan,
        evidence_refs=evidence_refs,
    )


def build_independent_ledger_pnl_reference(
    pair: SourcePair,
    *,
    component_scopes: Mapping[str, LedgerPnlComponentScope],
    manual_adjustment: IndependentPnlComponentReference,
    formal_dependency_binding: PnlFormalFactDependencyBinding,
) -> IndependentPnlReference:
    """Prepare a typed independent reference in a background/write workflow.

    ``build_ledger_only_facts`` performs source workbook parsing here. API GET
    callers should only deserialize the resulting ``IndependentPnlReference``
    record and call the pure core reconciliation function.

    CNX is selected because it is the workbook's consolidated CNY-equivalent
    population. CNY rows are a subset and must not be added to CNX again.
    H/A/T, 517 event eligibility, formal FX, and source-population completeness
    are deliberately represented by ``component_scopes``. The builder cannot
    infer those semantics from account codes alone.
    """

    if formal_dependency_binding.report_date != pair.report_date.isoformat():
        raise ValueError("Formal fact dependency binding report_date does not match source pair")
    unknown = set(component_scopes) - set(LEDGER_COMPONENTS)
    if unknown:
        raise ValueError(f"Unknown ledger PnL component scopes: {sorted(unknown)}")
    facts = build_ledger_only_facts(pair)
    components: dict[str, IndependentPnlComponentReference] = {}
    matched_account_by_component: dict[str, set[str]] = {}
    for component in LEDGER_COMPONENTS:
        scope = component_scopes.get(component)
        if scope is None:
            components[component] = pending_component_reference(
                "component scope contract is missing"
            )
            continue
        if scope.status == "pending":
            components[component] = pending_component_reference(scope.reason)
            continue
        matched_rows = [
            row
            for row in facts
            if row.currency == "CNX"
            and any(str(row.account_code).startswith(prefix) for prefix in scope.account_prefixes)
        ]
        matched_account_by_component[component] = {
            str(row.account_code) for row in matched_rows
        }
        if not matched_rows and not scope.zero_observation_evidence_refs:
            components[component] = pending_component_reference(
                "no matching CNX ledger rows and no explicit zero-observation evidence"
            )
            continue
        components[component] = IndependentPnlComponentReference(
            status="ready",
            value_yuan=sum((row.monthly_pnl for row in matched_rows), Decimal("0")),
            evidence_refs=tuple(
                dict.fromkeys((*scope.evidence_refs, *scope.zero_observation_evidence_refs))
            ),
        )

    overlap: dict[str, list[str]] = {}
    for account_code in sorted(set().union(*matched_account_by_component.values())):
        matched_components = [
            component
            for component, account_codes in matched_account_by_component.items()
            if account_code in account_codes
        ]
        if len(matched_components) > 1:
            overlap[account_code] = matched_components
    if overlap:
        raise ValueError(f"Independent ledger component scopes overlap: {overlap}")

    components["manual_adjustment"] = manual_adjustment
    return IndependentPnlReference(
        report_date=pair.report_date.isoformat(),
        currency_basis="CNY",
        ledger_currency_code="CNX",
        source_version=f"sv_pnl_independent_ledger_{sha256_file(pair.ledger_path)[:16]}",
        rule_version=LEDGER_REFERENCE_RULE_VERSION,
        formal_source_version=formal_dependency_binding.formal_source_version,
        formal_rule_version=formal_dependency_binding.formal_rule_version,
        approved_adjustment_version=formal_dependency_binding.approved_adjustment_version,
        formal_dependency_revision=formal_dependency_binding.formal_dependency_revision,
        formal_dependency_protocol_version=(
            formal_dependency_binding.formal_dependency_protocol_version
        ),
        adjustment_stage=formal_dependency_binding.adjustment_stage,
        components=components,
    )


def prepare_and_store_independent_ledger_pnl_reference(
    pair: SourcePair,
    *,
    governance_dir: str | Path,
    component_scopes: Mapping[str, LedgerPnlComponentScope],
    manual_adjustment: IndependentPnlComponentReference,
    formal_dependency_binding: PnlFormalFactDependencyBinding,
) -> IndependentPnlReference:
    """Background entry point: parse the source, bind dependencies, persist the result."""

    reference = build_independent_ledger_pnl_reference(
        pair,
        component_scopes=component_scopes,
        manual_adjustment=manual_adjustment,
        formal_dependency_binding=formal_dependency_binding,
    )
    PnlIndependentReferenceRepository(Path(governance_dir)).store_prepared(reference)
    return reference


def load_prepared_independent_pnl_reference(
    *,
    governance_dir: str | Path,
    report_date: str,
    formal_dependency_revision: int,
    formal_dependency_protocol_version: str,
) -> IndependentPnlReference | None:
    """GET-safe read: load an exact dependency-bound record without parsing Excel."""

    return PnlIndependentReferenceRepository(Path(governance_dir)).load_prepared(
        report_date=report_date,
        formal_dependency_revision=formal_dependency_revision,
        formal_dependency_protocol_version=formal_dependency_protocol_version,
    )


def load_and_reconcile_prepared_independent_pnl_reference(
    formal_totals: Mapping[str, object],
    *,
    governance_dir: str | Path,
    report_date: str,
    formal_dependency_revision: int,
    formal_dependency_protocol_version: str,
) -> dict[str, object]:
    """GET-safe entry point: lightweight record read followed by pure comparison."""

    reference = load_prepared_independent_pnl_reference(
        governance_dir=governance_dir,
        report_date=report_date,
        formal_dependency_revision=formal_dependency_revision,
        formal_dependency_protocol_version=formal_dependency_protocol_version,
    )
    return reconcile_pnl_overview_to_independent_reference(
        formal_totals,
        reference,
        report_date=report_date,
        formal_dependency_revision=formal_dependency_revision,
        formal_dependency_protocol_version=formal_dependency_protocol_version,
        adjustment_stage=FACT_MATERIALIZED_ADJUSTMENT_STAGE,
    )


__all__ = [
    "LEDGER_REFERENCE_RULE_VERSION",
    "LedgerPnlComponentScope",
    "build_independent_ledger_pnl_reference",
    "load_and_reconcile_prepared_independent_pnl_reference",
    "load_prepared_independent_pnl_reference",
    "pending_component_reference",
    "prepare_and_store_independent_ledger_pnl_reference",
    "ready_adjustment_reference",
]
