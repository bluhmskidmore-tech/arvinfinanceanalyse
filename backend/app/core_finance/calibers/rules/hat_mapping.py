"""
Caliber rule: H / A / T investment-type mapping (per FVTPL classification).

Background
----------
Every fixed-income position must be classified into one of three
accounting categories:

- ``H`` — held-to-maturity (HTM)
- ``A`` — available-for-sale (AFS)
- ``T`` — trading

The mapping flows from the *formal accounting* cell only. Management
and external-exposure views, as well as scenario / analytical bases, all
inherit the same H/A/T tag — diverging would let the same bond appear
as ``H`` in one report and ``T`` in another on the same date, which is
exactly the inconsistency that triggered the global-caliber-unification
work (transcript 2026-04-21, user Round 3).

Resolution matrix
-----------------

           accounting              management   external_exposure
formal     COMPUTE_VIA_CANONICAL   INHERIT      INHERIT
scenario   INHERIT                 INHERIT      INHERIT
analytical INHERIT                 INHERIT      INHERIT

- The single ``COMPUTE_VIA_CANONICAL`` cell delegates to
  ``infer_invest_type``; every other cell is ``INHERIT_FROM_FORMAL``,
  which formally means "look up the formal/accounting answer and use
  it verbatim".
- This shape is intentionally narrow: H/A/T is an *accounting*
  classification. Re-deriving it from a scenario or management lens
  would invent classifications that the ledger never made.

Canonical callable selection (PRD Q-PRD-2)
------------------------------------------
Two implementations currently coexist in the codebase:

- A: ``field_normalization.derive_invest_type_std_value``
- B: ``classification_rules.infer_invest_type``

PRD Q-PRD-2 default = **B** (selected). Reasons:

1. B handles the ``is_nonstd`` branch (non-standard assets are mapped to
   H or T based on whether interest income is positive).
2. B does not misclassify liabilities as ``H`` (A had this defect, which
   would compound the issuance-exclusion bug).
3. B is colocated with the other classification rules in
   ``classification_rules.py``, keeping the canonical surface compact.

Function A was deleted in W-cleanup-2026-04-21 once it had zero
production callers (after W-balance and W-pnl migrated their consumers
onto B). ``field_normalization`` retains only the pure normalization
helpers (``is_approved_status``, ``derive_accounting_basis_value``,
``normalize_currency_basis_value``, ``resolve_pnl_source_currency``)
and no longer claims any H/A/T classifier surface; ``_HAT_H_LABEL_SUBSTRINGS``
in ``classification_rules`` is now the single source of truth for the
H-label substring set.

W-cleanup-2026-04-21 — derive_invest_type_std_value deletion
------------------------------------------------------------
``field_normalization.derive_invest_type_std_value`` and its
``_H_LABELS`` constant were removed. Two equivalence tests that
referenced ``_H_LABELS`` were repointed at canonical
``_HAT_H_LABEL_SUBSTRINGS``. Audit count on this rule dropped 14 → 10
(4 more cleared from field_normalization).

W-pnl-2026-04-21 — pnl trial migration
--------------------------------------
``pnl._normalize_fi_invest_type`` was refactored from a thin wrapper over
``field_normalization.derive_invest_type_std_value`` into a thin wrapper
over the canonical ``infer_invest_type``. The dead
``_legacy_normalize_fi_invest_type`` backup was removed, and the legacy
import was dropped from ``pnl.py``. ``derive_invest_type_std_value`` now
has no production callers and can be deleted in the next phase. Audit
count on this rule dropped 17 → 14 (3H cleared from pnl).

W-balance-2026-04-21 — balance_analysis trial migration
-------------------------------------------------------
``balance_analysis.derive_invest_type_std`` was refactored from a
self-contained accounting-label classifier (with its own ``_H_LABELS``
set including the ``发行类债劵`` 劵-variant) into a thin wrapper that
delegates to ``infer_invest_type``. To preserve byte-for-byte output
the canonical ``_HAT_H_LABEL_SUBSTRINGS`` was enriched in the same
commit with all H-label substrings previously owned by
``balance_analysis._H_LABELS`` *and* by
``field_normalization._H_LABELS``, including the 劵 variant. Audit count
on this rule dropped 21 → 17 (3H + 1M cleared from balance_analysis).

This skeleton-only registration binds the policy to the registry; no
behaviour changes ship with W4.
"""

from __future__ import annotations

from backend.app.core_finance.calibers.descriptor import CaliberRuleDescriptor
from backend.app.core_finance.calibers.enums import Basis, Resolution, View
from backend.app.core_finance.calibers.registry import ensure_caliber_rule

DESCRIPTOR: CaliberRuleDescriptor = CaliberRuleDescriptor(
    rule_id="hat_mapping",
    rule_version="v1.0",
    canonical_module="backend.app.core_finance.config.classification_rules",
    canonical_callable="infer_invest_type",
    matrix={
        (Basis.FORMAL, View.ACCOUNTING): Resolution.COMPUTE_VIA_CANONICAL,
        (Basis.FORMAL, View.MANAGEMENT): Resolution.INHERIT_FROM_FORMAL,
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE): Resolution.INHERIT_FROM_FORMAL,
        (Basis.SCENARIO, View.ACCOUNTING): Resolution.INHERIT_FROM_FORMAL,
        (Basis.SCENARIO, View.MANAGEMENT): Resolution.INHERIT_FROM_FORMAL,
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE): Resolution.INHERIT_FROM_FORMAL,
        (Basis.ANALYTICAL, View.ACCOUNTING): Resolution.INHERIT_FROM_FORMAL,
        (Basis.ANALYTICAL, View.MANAGEMENT): Resolution.INHERIT_FROM_FORMAL,
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE): Resolution.INHERIT_FROM_FORMAL,
    },
    applies_to=(
        "fact_formal_zqtz_balance_daily",
        "fact_formal_bond_analytics_daily",
        "fact_formal_pnl_fi_daily",
    ),
    rationale=(
        "H/A/T is an accounting-side classification owned by the formal "
        "basis under the accounting view. All other (basis, view) cells "
        "must INHERIT_FROM_FORMAL so the same bond never appears as 'H' "
        "in one page and 'T' in another on the same date. Q-PRD-2 selected "
        "classification_rules.infer_invest_type as canonical (it has the "
        "is_nonstd branch and does not misclassify liabilities as H, "
        "unlike field_normalization.derive_invest_type_std_value, which "
        "will be thinned to a pure normalization helper in a follow-up "
        "phase)."
    ),
    source_doc=".omx/specs/deep-interview-global-caliber-unification.md",
)


ensure_caliber_rule(DESCRIPTOR)
