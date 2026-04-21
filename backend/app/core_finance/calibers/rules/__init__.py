"""
Caliber rules package — side-effect imports register every bundled
:class:`CaliberRuleDescriptor` into the global registry at package
import time.

Add new rules by importing them in this module; the registry's
``ensure_caliber_rule`` call inside each rule module is idempotent.
"""

from backend.app.core_finance.calibers.rules import (  # noqa: F401
    formal_scenario_gate,
    fx_mid_conversion,
    hat_mapping,
    issuance_exclusion,
    subject_514_516_517_merge,
)

__all__ = [
    "formal_scenario_gate",
    "fx_mid_conversion",
    "hat_mapping",
    "issuance_exclusion",
    "subject_514_516_517_merge",
]
