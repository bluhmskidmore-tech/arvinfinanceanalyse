"""Canonical accounting_basis string tokens (AC / FVOCI / FVTPL).

Defined in a leaf module (no imports from ``config``) so
``config.classification_rules`` can use them without circular imports with
``field_normalization``. Re-exported from ``field_normalization`` as the
stable public import path.
"""

from __future__ import annotations

from typing import Final

ACCOUNTING_BASIS_AC: Final = "AC"
ACCOUNTING_BASIS_FVOCI: Final = "FVOCI"
ACCOUNTING_BASIS_FVTPL: Final = "FVTPL"
