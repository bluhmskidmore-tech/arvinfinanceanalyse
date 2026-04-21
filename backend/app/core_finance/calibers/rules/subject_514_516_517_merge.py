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
