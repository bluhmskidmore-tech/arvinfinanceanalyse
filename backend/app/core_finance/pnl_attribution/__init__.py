"""PnL attribution workbench — pure read-model math for formal FI + bond facts."""

from backend.app.core_finance.pnl_attribution.workbench import (
    build_advanced_attribution_summary,
    build_campisi_attribution,
    build_carry_roll_down,
    build_krd_attribution,
    build_pnl_attribution_analysis_summary,
    build_pnl_composition,
    build_spread_attribution,
    build_tpl_market_correlation,
    build_volume_rate_attribution,
)

__all__ = [
    "build_volume_rate_attribution",
    "build_tpl_market_correlation",
    "build_pnl_composition",
    "build_pnl_attribution_analysis_summary",
    "build_carry_roll_down",
    "build_spread_attribution",
    "build_krd_attribution",
    "build_advanced_attribution_summary",
    "build_campisi_attribution",
]
