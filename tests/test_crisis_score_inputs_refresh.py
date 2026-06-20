from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from backend.app.tasks.crisis_score_inputs_refresh import (
    DEFAULT_ROLLING_WINDOW_DAYS,
    run_crisis_score_inputs_refresh,
)


def test_run_crisis_score_inputs_refresh_uses_rolling_window() -> None:
    expected_end = date.today().isoformat()
    expected_start = (date.today() - timedelta(days=DEFAULT_ROLLING_WINDOW_DAYS - 1)).isoformat()
    captured: dict[str, object] = {}

    def fake_backfill(**kwargs):
        captured.update(kwargs)
        return {"dry_run": kwargs.get("dry_run"), "input_count": 7}

    with patch(
        "backend.app.tasks.crisis_score_inputs_refresh.backfill_crisis_score_inputs",
        side_effect=fake_backfill,
    ):
        payload = run_crisis_score_inputs_refresh(dry_run=True)

    assert captured["start_date"] == expected_start
    assert captured["end_date"] == expected_end
    assert captured["dry_run"] is True
    assert payload["status"] == "dry_run"
    assert payload["window_days"] == DEFAULT_ROLLING_WINDOW_DAYS
    assert payload["backfill"] == {"dry_run": True, "input_count": 7}


def test_run_crisis_score_inputs_refresh_task_is_registered() -> None:
    from backend.app.tasks import crisis_score_inputs_refresh as module

    assert module.run_crisis_score_inputs_refresh_task.actor_name == "run_crisis_score_inputs_refresh"
