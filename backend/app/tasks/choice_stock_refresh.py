from __future__ import annotations

from backend.app.tasks.broker import register_actor_once


def run_choice_stock_refresh(
    *,
    duckdb_path: str,
    catalog_path: str,
    governance_path: str,
    archive_root: str,
    run_id: str,
    as_of_date: str,
    queued_at: str,
    refresh_history: bool,
    refresh_factors: bool,
    factor_max_stock_count: int | None,
    theme_overlay_mode: str,
    permission: dict[str, object],
    idempotency_key: str | None = None,
) -> None:
    from backend.app.services.macro_toolkit_service import (
        _run_choice_stock_refresh_job,
    )

    _run_choice_stock_refresh_job(
        duckdb_path=duckdb_path,
        catalog_path=catalog_path,
        governance_path=governance_path,
        archive_root=archive_root,
        run_id=run_id,
        as_of_date=as_of_date,
        queued_at=queued_at,
        refresh_history=refresh_history,
        refresh_factors=refresh_factors,
        factor_max_stock_count=factor_max_stock_count,
        theme_overlay_mode=theme_overlay_mode,
        permission=permission,
        idempotency_key=idempotency_key,
    )


run_choice_stock_refresh_task = register_actor_once(
    "run_choice_stock_refresh",
    run_choice_stock_refresh,
    max_retries=3,
    time_limit_ms=3_600_000,
)
