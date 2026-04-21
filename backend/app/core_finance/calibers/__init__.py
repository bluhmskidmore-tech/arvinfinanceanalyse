"""
Caliber rule registry — single source of truth for cross-page calculation
semantics in MOSS-V3.

See:
- ``.omx/specs/deep-interview-global-caliber-unification.md`` for the
  intent and acceptance criteria.
- ``.omx/plans/prd-global-caliber-unification.md`` for the architectural
  contract this package implements.

Public API:

- ``Basis``, ``View``, ``Resolution`` enums (context dimensions + policy values)
- ``CaliberRuleDescriptor`` (immutable rule contract)
- ``register_caliber_rule`` / ``ensure_caliber_rule`` (registration)
- ``get_caliber_rule`` / ``list_caliber_rules`` / ``resolve_caliber`` (lookup)
- ``assert_canonical_callsite`` (migration warning helper)
- ``CaliberRuleRegistryError`` / ``CaliberCalibrationViolation`` (errors)

Importing this package side-effect-registers the bundled rule descriptors.
"""

from __future__ import annotations

# Side-effect import: trigger built-in rule registration on first package
# import. Each rule module calls ``ensure_caliber_rule(...)`` at module top.
from backend.app.core_finance.calibers import rules as _rules  # noqa: F401
from backend.app.core_finance.calibers.descriptor import CaliberRuleDescriptor
from backend.app.core_finance.calibers.enums import (
    ALL_BASIS,
    ALL_CELLS,
    ALL_VIEW,
    Basis,
    Resolution,
    View,
)
from backend.app.core_finance.calibers.registry import (
    CaliberCalibrationViolation,
    CaliberRuleRegistryError,
    assert_canonical_callsite,
    clear_caliber_rules,
    ensure_caliber_rule,
    get_caliber_rule,
    list_caliber_rules,
    list_canonical_modules,
    register_caliber_rule,
    replay_caliber_rules,
    resolve_caliber,
)

__all__ = [
    "ALL_BASIS",
    "ALL_CELLS",
    "ALL_VIEW",
    "Basis",
    "CaliberCalibrationViolation",
    "CaliberRuleDescriptor",
    "CaliberRuleRegistryError",
    "Resolution",
    "View",
    "assert_canonical_callsite",
    "clear_caliber_rules",
    "ensure_caliber_rule",
    "get_caliber_rule",
    "list_caliber_rules",
    "list_canonical_modules",
    "register_caliber_rule",
    "replay_caliber_rules",
    "resolve_caliber",
]
