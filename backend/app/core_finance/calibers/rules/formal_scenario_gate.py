"""
Caliber rule: formal / scenario / analytical basis-by-view legitimacy gate.

Background
----------
MOSS-V3 distinguishes three calculation bases (formal, scenario, analytical)
and three reporting views (accounting, management, external_exposure). Not
every (basis, view) combination is governance-legitimate — for example,
publishing scenario numbers under an accounting view would surface
hypothetical figures as if they were ledger-grade truth.

This rule encodes the system-wide policy as a single 9-cell matrix. It is
not tied to any specific calculation; instead, it gates which call sites
may proceed at all. ``services/analysis_adapters.py``, ``tasks/pnl_materialize``,
and several schemas currently re-implement fragments of this gate inline —
they will migrate to ``assert_basis_view_allowed`` over W2-W3.

Resolution matrix
-----------------

           accounting   management   external_exposure
formal     INCLUDE      INCLUDE      INCLUDE
scenario   EXCLUDE      INCLUDE      EXCLUDE
analytical EXCLUDE      INCLUDE      EXCLUDE

- ``INCLUDE`` means "the (basis, view) request is legitimate; calculations
  may proceed". ``EXCLUDE`` means "the request is forbidden; the gate
  raises ``ForbiddenBasisViewCombination``".
- The diagonal-shape is intentional: only the ``management`` view is allowed
  to mix bases (because management dashboards do scenario comparison).
- ``accounting`` and ``external_exposure`` columns reject anything that is
  not a formal-basis result.
"""

from __future__ import annotations

from backend.app.core_finance.calibers.descriptor import CaliberRuleDescriptor
from backend.app.core_finance.calibers.enums import Basis, Resolution, View
from backend.app.core_finance.calibers.registry import (
    ensure_caliber_rule,
    resolve_caliber,
)


class ForbiddenBasisViewCombination(ValueError):
    """
    Raised by :func:`assert_basis_view_allowed` when the requested
    ``(basis, view)`` combination is marked ``EXCLUDE`` by the
    ``formal_scenario_gate`` matrix.

    Catch this where governance allows a softer fallback (e.g. a UI badge
    that just hides the figure); leave it uncaught in service / task code
    so the violation surfaces as an HTTP 422 or task failure.
    """

    def __init__(self, basis: Basis, view: View) -> None:
        super().__init__(
            f"Caliber gate forbids combination "
            f"(basis={basis.value}, view={view.value}). "
            f"Policy is owned by 'formal_scenario_gate' caliber rule "
            f"({DESCRIPTOR.canonical_module})."
        )
        self.basis = basis
        self.view = view


def is_basis_view_allowed(basis: Basis, view: View) -> bool:
    """Return True iff ``(basis, view)`` resolves to ``Resolution.INCLUDE``."""
    return resolve_caliber("formal_scenario_gate", basis, view) is Resolution.INCLUDE


def assert_basis_view_allowed(basis: Basis, view: View) -> None:
    """
    Raise :class:`ForbiddenBasisViewCombination` if the requested
    combination is not legitimate.

    This is the canonical call-site for every formal/scenario gate decision.
    Any other site that re-implements the policy should be flagged via
    ``assert_canonical_callsite('formal_scenario_gate', __name__)`` and
    migrated.
    """
    if not is_basis_view_allowed(basis, view):
        raise ForbiddenBasisViewCombination(basis, view)


DESCRIPTOR: CaliberRuleDescriptor = CaliberRuleDescriptor(
    rule_id="formal_scenario_gate",
    rule_version="v1.0",
    canonical_module="backend.app.core_finance.calibers.rules.formal_scenario_gate",
    canonical_callable="assert_basis_view_allowed",
    matrix={
        (Basis.FORMAL, View.ACCOUNTING): Resolution.INCLUDE,
        (Basis.FORMAL, View.MANAGEMENT): Resolution.INCLUDE,
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE): Resolution.INCLUDE,
        (Basis.SCENARIO, View.ACCOUNTING): Resolution.EXCLUDE,
        (Basis.SCENARIO, View.MANAGEMENT): Resolution.INCLUDE,
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE): Resolution.EXCLUDE,
        (Basis.ANALYTICAL, View.ACCOUNTING): Resolution.EXCLUDE,
        (Basis.ANALYTICAL, View.MANAGEMENT): Resolution.INCLUDE,
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE): Resolution.EXCLUDE,
    },
    applies_to=(
        "fact_formal_pnl_fi_daily",
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "fact_formal_bond_analytics_daily",
        "fact_formal_product_category_pnl_daily",
    ),
    rationale=(
        "Only formal-basis calculations may surface in accounting and "
        "external_exposure views. Scenario and analytical bases are "
        "permitted only in the management view (where comparison is the "
        "stated purpose). Inline re-implementations of this policy in "
        "services/, tasks/, and schemas/ must migrate to "
        "assert_basis_view_allowed; the W2 audit script enumerates them."
    ),
    source_doc=".omx/specs/deep-interview-global-caliber-unification.md",
)


ensure_caliber_rule(DESCRIPTOR)
