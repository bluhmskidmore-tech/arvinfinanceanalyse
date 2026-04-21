"""
Caliber rule: issuance-class bond-liability inclusion / exclusion gate.

Background
----------
"Issuance-class" instruments (发行类债务 / 发行类债券) are bonds **issued by
the bank itself** — i.e. they sit on the *liability* side of the balance
sheet. The accounting view must include them (the ledger truthfully books
issued debt as a liability), but every management or external-exposure
view that ranks "bond holdings" must exclude them — otherwise we would
double-count our own debt as if it were an investment position.

User Round-5 correction (transcript 2026-04-21):

    "发行类债券不是资产，是负债"

This rule encodes that semantic so no caller has to re-implement the
"is this a self-issued liability?" check inline.

Resolution matrix
-----------------

           accounting   management   external_exposure
formal     INCLUDE      EXCLUDE      EXCLUDE
scenario   INHERIT      INHERIT      INHERIT
analytical INCLUDE      EXCLUDE      EXCLUDE

- ``INCLUDE`` means "row passes the filter (it stays in the result set)".
- ``EXCLUDE`` means "row is filtered out before aggregation".
- ``INHERIT_FROM_FORMAL`` means scenario calculations adopt the formal
  cell's resolution for the same view; this preserves scenario-vs-formal
  comparability (a scenario PnL for accounting still includes issuance,
  matching its formal counterpart).

Canonical callable
------------------
``backend.app.core_finance.config.classification_rules.is_bond_liability``
is the existing single source of truth that classifies a row as
issuance-class. **W3 deliberately does not modify the function** — its
fuzzy matching (``"发行" in normalized``) is a known issue tracked in
the PRD §2.3 and will be tightened in a separate, reconciliation-gated
phase (Q-PRD-5 'a': blocking).

This skeleton-only registration makes the policy auditable and binds
all migration call-sites to a stable contract.
"""

from __future__ import annotations

from backend.app.core_finance.calibers.descriptor import CaliberRuleDescriptor
from backend.app.core_finance.calibers.enums import Basis, Resolution, View
from backend.app.core_finance.calibers.registry import ensure_caliber_rule

DESCRIPTOR: CaliberRuleDescriptor = CaliberRuleDescriptor(
    rule_id="issuance_exclusion",
    rule_version="v1.0",
    canonical_module="backend.app.core_finance.config.classification_rules",
    canonical_callable="is_bond_liability",
    matrix={
        (Basis.FORMAL, View.ACCOUNTING): Resolution.INCLUDE,
        (Basis.FORMAL, View.MANAGEMENT): Resolution.EXCLUDE,
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE): Resolution.EXCLUDE,
        (Basis.SCENARIO, View.ACCOUNTING): Resolution.INHERIT_FROM_FORMAL,
        (Basis.SCENARIO, View.MANAGEMENT): Resolution.INHERIT_FROM_FORMAL,
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE): Resolution.INHERIT_FROM_FORMAL,
        (Basis.ANALYTICAL, View.ACCOUNTING): Resolution.INCLUDE,
        (Basis.ANALYTICAL, View.MANAGEMENT): Resolution.EXCLUDE,
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE): Resolution.EXCLUDE,
    },
    applies_to=(
        "fact_formal_zqtz_balance_daily",
        "fact_formal_bond_analytics_daily",
        "fact_formal_pnl_fi_daily",
        "fact_formal_product_category_pnl_daily",
    ),
    rationale=(
        "Issuance-class bonds are self-issued liabilities (user Round-5 "
        "correction). They MUST be included in accounting views (the ledger "
        "books them as liabilities and balance integrity requires it) and "
        "MUST be excluded from every management or external_exposure view "
        "that ranks bond holdings, or the bank would appear to invest in "
        "its own debt. Six call-sites currently re-implement the filter "
        "inline (PRD §2.3 baseline); they will migrate to is_bond_liability "
        "via deprecation warnings once the W3 audit script enumerates them."
    ),
    source_doc=".omx/specs/deep-interview-global-caliber-unification.md",
)


ensure_caliber_rule(DESCRIPTOR)
