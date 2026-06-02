"""
Caliber rule: 514 / 516 / 517 ledger-PnL account-prefix merge.

Background
----------
The Chinese accounting ledger uses three top-level subject codes for
fixed-income P&L:

- ``514`` — interest income
- ``516`` — fair-value-change P&L
- ``517`` — investment income (realised gains / losses)

For every formal calculation, these three families MUST be reported as a
single ``ledger_pnl_total`` group; splitting them produces inconsistent
totals across pages. The canonical source of truth is the constant
``LEDGER_PNL_ACCOUNT_PREFIXES`` in
``backend.app.core_finance.config.classification_rules``.

Resolution matrix
-----------------

           accounting   management   external_exposure
formal     MERGE        MERGE        MERGE
scenario   MERGE        MERGE        INHERIT_FROM_FORMAL
analytical MERGE        SPLIT        INHERIT_FROM_FORMAL

Notes
-----
- ``analytical / management`` is the only context where SPLITTING into the
  three sub-families is permitted (drill-down attribution dashboards).
- ``external_exposure`` views always inherit from the formal cell to avoid
  publishing scenario-tuned subject groupings to regulators / auditors.

W-subject-2026-04-21 — trial migration close-out
------------------------------------------------
Cleanup pass that moved every reducible bare-prefix literal onto the
canonical tuple:

- ``backend/app/core_finance/config/product_category_mapping.py``: the
  bond-investment ``pnl_accounts`` root entry now references
  ``LEDGER_PNL_ACCOUNT_PREFIXES[0]`` instead of inlining ``"514"``.
- ``backend/app/core_finance/pnl.py``:
    * Added a runtime ``assert`` that ``JournalType`` Literal members
      stay in lockstep with ``LEDGER_PNL_ACCOUNT_PREFIXES + {'adjustment'}``
      (PEP 586 forbids variable-source Literal members, so the literal
      itself is irreducible — see *Justified residuals* below).
    * Introduced ``SIGN_FLIP_JOURNAL_TYPES`` derived as
      ``frozenset(LEDGER_PNL_ACCOUNT_PREFIXES) - {LEDGER_PNL_ACCOUNT_PREFIXES[0]}``
      and switched the inline ``{"516", "517"}`` set in
      ``_normalize_nonstd_signed_amount`` to use it.

Audit count on this rule dropped 4 → 2 (the residual two are the same
``JournalType`` line counted by both regex variants).

Justified residuals
-------------------
``pnl.py`` line declaring ``JournalType = Literal["514", "516", "517",
"adjustment"]`` is intrinsically irreducible: PEP 586 requires
``Literal[...]`` members to be literal forms (string / int / Enum /
None / Final str alias). The runtime assert above is the canonical
lockstep guard. Audit hits on this single line are documented FPs.

To clear the audit count to 0, the audit script regex would need an
allowlist parser for ``# Human: caliber-…-justified`` markers (a
W-audit-tooling concern, deliberately out of scope).

W-audit-tooling-2026-04-21 update: the audit script now honours the
``# Human: caliber-<rule_id>-justified`` marker (lookback 10 lines,
case-insensitive). The ``JournalType`` Literal site was annotated and
the audit count for this rule dropped 2 → 0 (suppressed=2).
"""

from __future__ import annotations

from backend.app.core_finance.calibers.descriptor import CaliberRuleDescriptor
from backend.app.core_finance.calibers.enums import Basis, Resolution, View
from backend.app.core_finance.calibers.registry import ensure_caliber_rule

DESCRIPTOR: CaliberRuleDescriptor = CaliberRuleDescriptor(
    rule_id="subject_514_516_517_merge",
    rule_version="v1.0",
    canonical_module="backend.app.core_finance.config.classification_rules",
    canonical_callable="LEDGER_PNL_ACCOUNT_PREFIXES",
    matrix={
        (Basis.FORMAL, View.ACCOUNTING): Resolution.MERGE,
        (Basis.FORMAL, View.MANAGEMENT): Resolution.MERGE,
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE): Resolution.MERGE,
        (Basis.SCENARIO, View.ACCOUNTING): Resolution.MERGE,
        (Basis.SCENARIO, View.MANAGEMENT): Resolution.MERGE,
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE): Resolution.INHERIT_FROM_FORMAL,
        (Basis.ANALYTICAL, View.ACCOUNTING): Resolution.MERGE,
        (Basis.ANALYTICAL, View.MANAGEMENT): Resolution.SPLIT,
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE): Resolution.INHERIT_FROM_FORMAL,
    },
    applies_to=(
        "fact_formal_pnl_fi_daily",
        "fact_formal_product_category_pnl_daily",
    ),
    rationale=(
        "Subject codes 514 (interest income), 516 (FV-change P&L) and 517 "
        "(investment income / realised gains) must be merged into a single "
        "ledger_pnl_total group for every formal and scenario context, with "
        "the sole exception of the analytical/management drill-down view. "
        "Splitting them in any other context produces inconsistent totals "
        "across pages — the canonical prefix tuple "
        "LEDGER_PNL_ACCOUNT_PREFIXES already exists; this descriptor binds "
        "the policy to the registry."
    ),
    source_doc=".omx/specs/deep-interview-global-caliber-unification.md",
)

ensure_caliber_rule(DESCRIPTOR)
