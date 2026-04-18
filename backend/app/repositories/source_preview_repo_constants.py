from __future__ import annotations

MANIFEST_ELIGIBLE_STATUSES = {"completed", "rerun"}
PREVIEW_TABLES = (
    "phase1_source_preview_summary",
    "phase1_source_preview_groups",
    "phase1_zqtz_preview_rows",
    "phase1_tyw_preview_rows",
    "phase1_pnl_preview_rows",
    "phase1_nonstd_pnl_preview_rows",
    "phase1_zqtz_rule_traces",
    "phase1_tyw_rule_traces",
    "phase1_pnl_rule_traces",
    "phase1_nonstd_pnl_rule_traces",
)
SUPPORTED_PREVIEW_SOURCE_FAMILIES = frozenset(
    {"zqtz", "tyw", "pnl", "pnl_514", "pnl_516", "pnl_517"}
)
