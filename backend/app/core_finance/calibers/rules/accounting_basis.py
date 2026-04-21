"""
Caliber rule: accounting basis (AC / FVOCI / FVTPL) from investment type (H / A / T).

Background
----------
Accounting basis tags how fair-value and amortised-cost mechanics flow through
the books:

- **AC** — amortised cost (摊余成本), aligned with held-to-maturity-style
  carry for qualifying instruments.
- **FVOCI** — fair value through other comprehensive income (FVOCI / OCI
  bucket), aligned with available-for-sale-style classification.
- **FVTPL** — fair value through profit or loss (FVTPL / trading), aligned
  with mark-to-market P&L.

In this codebase, AC/FVOCI/FVTPL is a **strict downstream function** of the
normalized H/A/T investment-type tag from :mod:`hat_mapping`: ``H→AC``,
``A→FVOCI``, ``T→FVTPL``. Re-encoding those three literals without going
through the canonical mapper invites the same bond to show as FVTPL on one
page and AC on another for the same date.

Resolution matrix
-----------------

           accounting              management          external_exposure
formal     COMPUTE_VIA_CANONICAL   INHERIT_FROM_FORMAL INHERIT_FROM_FORMAL
scenario   INHERIT_FROM_FORMAL     INHERIT_FROM_FORMAL INHERIT_FROM_FORMAL
analytical INHERIT_FROM_FORMAL     INHERIT_FROM_FORMAL INHERIT_FROM_FORMAL

The single ``COMPUTE_VIA_CANONICAL`` cell delegates to
``derive_accounting_basis_value``; every other cell is
``INHERIT_FROM_FORMAL`` (use the formal/accounting answer verbatim).

Canonical callable
------------------
``backend.app.core_finance.field_normalization.derive_accounting_basis_value``
implements the 1-to-1 mapping from ``NormalizedInvestTypeStd`` to
``NormalizedAccountingBasis``.

Justified residuals
-------------------
Some lines may remain flagged until consumer code migrates off inline
comparisons (e.g. ``basis == "AC"``) to the canonical helper, or until the
audit regex gains Literal/annotation carve-outs comparable to other rules.
Document intentional exceptions with ``# Human: caliber-accounting_basis-justified``.

CI gate status
--------------
Currently **informational**: the inline audit reports violations, but
``_GATE_ENFORCED_RULES`` excludes ``accounting_basis`` until consumer
migration completes. The rule will be moved into the enforced set in the
planned **W-accounting-basis-migration** batch (see also W-rule-coverage-2026-04-21).
"""

from __future__ import annotations

from backend.app.core_finance.calibers.descriptor import CaliberRuleDescriptor
from backend.app.core_finance.calibers.enums import Basis, Resolution, View
from backend.app.core_finance.calibers.registry import ensure_caliber_rule

DESCRIPTOR: CaliberRuleDescriptor = CaliberRuleDescriptor(
    rule_id="accounting_basis",
    rule_version="v1.0",
    canonical_module="backend.app.core_finance.field_normalization",
    canonical_callable="derive_accounting_basis_value",
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
        "fact_formal_pnl_fi_daily",
        "fact_formal_zqtz_balance_daily",
        "fact_formal_bond_analytics_daily",
    ),
    rationale=(
        "AC, FVOCI and FVTPL must follow the same H/A/T classification as "
        "hat_mapping: the formal accounting view computes the basis via "
        "derive_accounting_basis_value, and every other (basis, view) cell "
        "inherits so accounting-basis labels never diverge across pages or "
        "scenarios for the same position date."
    ),
    source_doc=".omx/specs/deep-interview-global-caliber-unification.md",
)


ensure_caliber_rule(DESCRIPTOR)
