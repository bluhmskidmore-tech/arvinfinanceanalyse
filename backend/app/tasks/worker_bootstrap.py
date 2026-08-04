"""Canonical Dramatiq worker bootstrap surface for active task modules."""

from importlib import import_module

from backend.app.storage_bootstrap import run_startup_storage_migrations

run_startup_storage_migrations()


CANONICAL_TASK_MODULES: tuple[str, ...] = (
    "backend.app.tasks.dev_health",
    "backend.app.tasks.ingest",
    "backend.app.tasks.materialize",
    "backend.app.tasks.source_preview_refresh",
    "backend.app.tasks.pnl_materialize",
    "backend.app.tasks.balance_analysis_materialize",
    "backend.app.tasks.formal_balance_pipeline",
    "backend.app.tasks.bond_analytics_materialize",
    "backend.app.tasks.product_category_pnl",
    "backend.app.tasks.snapshot_materialize",
    "backend.app.tasks.fx_mid_materialize",
    "backend.app.tasks.commodity_daily_ingest",
    "backend.app.tasks.crisis_score_inputs_refresh",
    "backend.app.tasks.nbs_gdp_release_ingest",
    "backend.app.tasks.choice_macro",
    "backend.app.tasks.tushare_macro_ingest",
    "backend.app.tasks.home_macro_release_refresh",
    "backend.app.tasks.choice_news",
    "backend.app.tasks.stock_factor_refresh",
    "backend.app.tasks.research_calendar_upstream_fetch",
    "backend.app.tasks.choice_stock_refresh",
    "backend.app.tasks.macro_toolkit_refresh",
    "backend.app.tasks.macro_toolkit_freshness_refresh",
    "backend.app.tasks.macro_toolkit_write_refresh",
    "backend.app.tasks.livermore_position_snapshot_materialize",
    "backend.app.tasks.agent_run",
    "backend.app.tasks.livermore_gate_supplement",
    "backend.app.tasks.ledger_import",
)


# Ensure the Redis broker is configured before loading actor modules that use
# direct @dramatiq.actor decoration.
import_module("backend.app.tasks.broker").get_broker()
LOADED_TASK_MODULES = tuple(import_module(module_path) for module_path in CANONICAL_TASK_MODULES)
