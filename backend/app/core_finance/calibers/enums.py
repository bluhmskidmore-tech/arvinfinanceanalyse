"""
Caliber rule context dimensions and policy resolutions.

Per spec `.omx/specs/deep-interview-global-caliber-unification.md` §6 (C1 + C2):
- Basis: formal / scenario / analytical
- View: accounting / management / external_exposure

Resolution values represent the *policy decision* for a (basis, view) cell.
The actual data-dependent computation is delegated to each rule's
`canonical_callable` declared on its `CaliberRuleDescriptor`.
"""

from __future__ import annotations

from enum import StrEnum


class Basis(StrEnum):
    """Calculation basis (C1 dimension)."""

    FORMAL = "formal"
    SCENARIO = "scenario"
    ANALYTICAL = "analytical"


class View(StrEnum):
    """Reporting view perspective (C2 dimension)."""

    ACCOUNTING = "accounting"
    MANAGEMENT = "management"
    EXTERNAL_EXPOSURE = "external_exposure"


class Resolution(StrEnum):
    """
    Policy outcome for a single (basis, view) cell of a caliber rule matrix.

    Semantic intent only; the canonical_callable interprets each value in its
    rule-specific way. Examples:

    - `INCLUDE` / `EXCLUDE` for filter-style rules (e.g. issuance_exclusion)
    - `MERGE` / `SPLIT` for grouping rules (e.g. 514/516/517 subject merge)
    - `INHERIT_FROM_FORMAL` to delegate explicitly to the formal cell rather
      than silently falling back (silent fallback is a known finance footgun)
    - `NOT_APPLICABLE` to declare the cell intentionally has no policy
    - `COMPUTE_VIA_CANONICAL` for rules whose answer depends on the data row
      itself (e.g. hat_mapping returns H/A/T per asset, not a static policy)
    """

    INCLUDE = "include"
    EXCLUDE = "exclude"
    MERGE = "merge"
    SPLIT = "split"
    INHERIT_FROM_FORMAL = "inherit_from_formal"
    NOT_APPLICABLE = "not_applicable"
    COMPUTE_VIA_CANONICAL = "compute_via_canonical"


ALL_BASIS: tuple[Basis, ...] = tuple(Basis)
ALL_VIEW: tuple[View, ...] = tuple(View)
ALL_CELLS: frozenset[tuple[Basis, View]] = frozenset(
    (basis, view) for basis in Basis for view in View
)
