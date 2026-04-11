"""Canonical Dramatiq worker bootstrap surface for active task modules."""

from importlib import import_module


CANONICAL_TASK_MODULES: tuple[str, ...] = (
    "backend.app.tasks.ingest",
    "backend.app.tasks.materialize",
    "backend.app.tasks.source_preview_refresh",
    "backend.app.tasks.pnl_materialize",
    "backend.app.tasks.balance_analysis_materialize",
    "backend.app.tasks.product_category_pnl",
    "backend.app.tasks.snapshot_materialize",
    "backend.app.tasks.choice_macro",
    "backend.app.tasks.choice_news",
)


# Ensure the Redis broker is configured before loading actor modules that use
# direct @dramatiq.actor decoration.
import_module("backend.app.tasks.broker")
LOADED_TASK_MODULES = tuple(import_module(module_path) for module_path in CANONICAL_TASK_MODULES)
