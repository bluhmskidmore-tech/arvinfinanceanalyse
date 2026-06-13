"""Daily rolling refresh for Crisis Score input series."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from backend.app.tasks.broker import register_actor_once
from backend.scripts.backfill_crisis_score_inputs import backfill_crisis_score_inputs

logger = logging.getLogger(__name__)

DEFAULT_ROLLING_WINDOW_DAYS = 30
RULE_VERSION = "rv_crisis_score_inputs_daily_refresh_v1"


def run_crisis_score_inputs_refresh(
    *,
    duckdb_path: str | None = None,
    window_days: int = DEFAULT_ROLLING_WINDOW_DAYS,
    dry_run: bool = False,
) -> dict[str, object]:
    end_date = date.today().isoformat()
    start_date = (date.today() - timedelta(days=max(window_days - 1, 0))).isoformat()
    payload = backfill_crisis_score_inputs(
        duckdb_path=duckdb_path,
        start_date=start_date,
        end_date=end_date,
        dry_run=dry_run,
    )
    return {
        "status": "completed" if not dry_run else "dry_run",
        "rule_version": RULE_VERSION,
        "window_days": window_days,
        "start_date": start_date,
        "end_date": end_date,
        "backfill": payload,
    }


run_crisis_score_inputs_refresh_task = register_actor_once(
    "run_crisis_score_inputs_refresh",
    run_crisis_score_inputs_refresh,
    time_limit_ms=3_600_000,
)
