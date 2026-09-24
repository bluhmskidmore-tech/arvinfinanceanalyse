from __future__ import annotations

from datetime import date
from typing import Final

# Shared formal PnL contract constants. Keep this module leaf-only so
# repositories and core_finance implementations can share one source of truth
# without importing the full `core_finance.pnl` surface.
PNL_514_VAT_EFFECTIVE_START_DATE: Final = date(2026, 1, 1)
PNL_514_VAT_EFFECTIVE_END_DATE: Final = date(2026, 6, 30)
PNL_FORMAL_FACT_RULE_VERSION: Final = "rv_pnl_phase2_materialize_v3"
