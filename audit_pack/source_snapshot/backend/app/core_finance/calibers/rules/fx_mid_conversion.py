"""
Caliber rule: FX mid-rate date selection for currency conversion.

Background
----------
Foreign-currency amounts must be converted to CNY using the **mid rate**.
The policy question is *which date's mid rate?*

- For ``formal`` calculations (ledger-grade truth), the rate is the mid
  rate **of the business date the row was booked** — this is what auditors
  expect and what the accounting system already uses.
- For ``scenario`` and ``analytical`` calculations, the rate is the mid
  rate **of the as-of date the user is querying** — this lets analysts
  reprice historical rows under "today's" conditions.

The ``analytical / accounting`` cell is ``NOT_APPLICABLE``: an accounting
view of an analytical basis is governance-illegitimate (the
``formal_scenario_gate`` rule already rejects it). Marking the cell here
makes the redundancy explicit and prevents accidental fall-through.

Resolution matrix
-----------------

           accounting              management              external_exposure
formal     COMPUTE_VIA_CANONICAL   COMPUTE_VIA_CANONICAL  COMPUTE_VIA_CANONICAL
scenario   COMPUTE_VIA_CANONICAL   COMPUTE_VIA_CANONICAL  COMPUTE_VIA_CANONICAL
analytical NOT_APPLICABLE          COMPUTE_VIA_CANONICAL  COMPUTE_VIA_CANONICAL

Date-selection policy (rule-internal)
-------------------------------------
The matrix only encodes "does this cell compute, or is it forbidden?".
The *which date* detail lives in :data:`_FX_DATE_POLICY` immediately
below the descriptor, which maps every COMPUTE cell to either
``"business_date"`` or ``"as_of_date"``. Helper :func:`select_fx_date`
consults both the registry resolution and this policy table; it is the
single canonical entry point for picking the FX lookup date.

Canonical callable
------------------
``backend.app.core_finance.fx_rates.get_usd_cny_rate`` is the existing
USD/CNY mid-rate lookup. The W5 skeleton registers it as canonical for
the rule even though the rule itself is currency-agnostic — extending
``fx_rates`` to handle other currencies is out of scope here and tracked
separately. Until then, callers using non-USD currencies will continue
to fail loudly at the lookup layer, which is the desired behaviour.
"""

from __future__ import annotations

from datetime import date

from backend.app.core_finance.calibers.descriptor import CaliberRuleDescriptor
from backend.app.core_finance.calibers.enums import Basis, Resolution, View
from backend.app.core_finance.calibers.registry import (
    ensure_caliber_rule,
    resolve_caliber,
)


class InapplicableFxConversion(ValueError):
    """
    Raised by :func:`select_fx_date` when the requested ``(basis, view)``
    cell is ``NOT_APPLICABLE`` per the ``fx_mid_conversion`` matrix.

    The only NOT_APPLICABLE cell at v1.0 is
    ``(analytical, accounting)`` — an analytical lens onto the accounting
    view, which the ``formal_scenario_gate`` already rejects.
    """

    def __init__(self, basis: Basis, view: View) -> None:
        super().__init__(
            f"FX mid conversion is not applicable for "
            f"(basis={basis.value}, view={view.value}). "
            f"This combination is owned by the 'fx_mid_conversion' "
            f"caliber rule and is marked NOT_APPLICABLE."
        )
        self.basis = basis
        self.view = view


DESCRIPTOR: CaliberRuleDescriptor = CaliberRuleDescriptor(
    rule_id="fx_mid_conversion",
    rule_version="v1.0",
    canonical_module="backend.app.core_finance.fx_rates",
    canonical_callable="get_usd_cny_rate",
    matrix={
        (Basis.FORMAL, View.ACCOUNTING): Resolution.COMPUTE_VIA_CANONICAL,
        (Basis.FORMAL, View.MANAGEMENT): Resolution.COMPUTE_VIA_CANONICAL,
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE): Resolution.COMPUTE_VIA_CANONICAL,
        (Basis.SCENARIO, View.ACCOUNTING): Resolution.COMPUTE_VIA_CANONICAL,
        (Basis.SCENARIO, View.MANAGEMENT): Resolution.COMPUTE_VIA_CANONICAL,
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE): Resolution.COMPUTE_VIA_CANONICAL,
        (Basis.ANALYTICAL, View.ACCOUNTING): Resolution.NOT_APPLICABLE,
        (Basis.ANALYTICAL, View.MANAGEMENT): Resolution.COMPUTE_VIA_CANONICAL,
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE): Resolution.COMPUTE_VIA_CANONICAL,
    },
    applies_to=(
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "fact_formal_pnl_fi_daily",
        "fact_formal_product_category_pnl_daily",
    ),
    rationale=(
        "FX mid-rate date selection diverges by basis: formal rows must "
        "use the business_date mid rate (auditor expectation, matches the "
        "accounting system), while scenario and analytical rows must use "
        "the as_of_date mid rate so analysts can reprice historical rows "
        "under today's conditions. The (analytical, accounting) cell is "
        "NOT_APPLICABLE because the formal_scenario_gate already forbids "
        "it. Date-selection policy lives in _FX_DATE_POLICY immediately "
        "below the descriptor; select_fx_date is the canonical helper."
    ),
    source_doc=".omx/specs/deep-interview-global-caliber-unification.md",
)


_FX_DATE_POLICY: dict[tuple[Basis, View], str] = {
    (Basis.FORMAL, View.ACCOUNTING): "business_date",
    (Basis.FORMAL, View.MANAGEMENT): "business_date",
    (Basis.FORMAL, View.EXTERNAL_EXPOSURE): "business_date",
    (Basis.SCENARIO, View.ACCOUNTING): "as_of_date",
    (Basis.SCENARIO, View.MANAGEMENT): "as_of_date",
    (Basis.SCENARIO, View.EXTERNAL_EXPOSURE): "as_of_date",
    (Basis.ANALYTICAL, View.MANAGEMENT): "as_of_date",
    (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE): "as_of_date",
}


def select_fx_date(
    basis: Basis,
    view: View,
    *,
    business_date: date,
    as_of_date: date,
) -> date:
    """
    Return the canonical FX-lookup date for the requested ``(basis, view)``.

    Raises :class:`InapplicableFxConversion` if the cell is marked
    ``NOT_APPLICABLE`` by the rule matrix.

    The function consults the registry first (so a future matrix change
    propagates without code edits), then looks up the date-selection
    policy in :data:`_FX_DATE_POLICY`. Any COMPUTE cell that is missing
    from the policy table raises ``KeyError`` loudly — this is
    intentional: silent fallback would re-introduce the inconsistency
    we are eliminating.
    """
    resolution = resolve_caliber("fx_mid_conversion", basis, view)
    if resolution is Resolution.NOT_APPLICABLE:
        raise InapplicableFxConversion(basis, view)
    if resolution is not Resolution.COMPUTE_VIA_CANONICAL:
        raise ValueError(
            f"fx_mid_conversion: unexpected resolution {resolution.value!r} "
            f"for (basis={basis.value}, view={view.value}); "
            f"expected COMPUTE_VIA_CANONICAL or NOT_APPLICABLE."
        )
    target = _FX_DATE_POLICY[(basis, view)]
    if target == "business_date":
        return business_date
    if target == "as_of_date":
        return as_of_date
    raise ValueError(
        f"fx_mid_conversion: unknown date-policy key {target!r} for "
        f"(basis={basis.value}, view={view.value})."
    )


ensure_caliber_rule(DESCRIPTOR)
