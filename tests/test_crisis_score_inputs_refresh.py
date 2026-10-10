from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from backend.app.tasks.crisis_score_inputs_refresh import (
    DEFAULT_ROLLING_WINDOW_DAYS,
    run_crisis_score_inputs_refresh,
)


def test_run_crisis_score_inputs_refresh_uses_rolling_window() -> None:
    # 注入固定 as_of，窗口断言与真实时钟解耦（消除跨午夜翻车）。
    as_of = date(2026, 8, 12)
    expected_end = as_of.isoformat()
    expected_start = (as_of - timedelta(days=DEFAULT_ROLLING_WINDOW_DAYS - 1)).isoformat()
    captured: dict[str, object] = {}

    def fake_backfill(**kwargs):
        captured.update(kwargs)
        return {"dry_run": kwargs.get("dry_run"), "input_count": 7}

    with patch(
        "backend.app.tasks.crisis_score_inputs_refresh.backfill_crisis_score_inputs",
        side_effect=fake_backfill,
    ):
        payload = run_crisis_score_inputs_refresh(dry_run=True, as_of=as_of.isoformat())

    assert captured["start_date"] == expected_start
    assert captured["end_date"] == expected_end
    assert captured["dry_run"] is True
    assert payload["status"] == "dry_run"
    assert payload["window_days"] == DEFAULT_ROLLING_WINDOW_DAYS
    assert payload["backfill"] == {"dry_run": True, "input_count": 7}


def test_run_crisis_score_inputs_refresh_reports_partial_input_results() -> None:
    backfill_payload = {
        "dry_run": False,
        "input_count": 2,
        "results": {
            "DR007.IB": {"status": "completed"},
            "M0041653": {"status": "no_rows"},
        },
        "errors": {},
    }

    with patch(
        "backend.app.tasks.crisis_score_inputs_refresh.backfill_crisis_score_inputs",
        return_value=backfill_payload,
    ):
        payload = run_crisis_score_inputs_refresh(dry_run=False)

    assert payload["status"] == "partial"
    assert payload["backfill"] == backfill_payload


def test_run_crisis_score_inputs_refresh_task_is_registered() -> None:
    from backend.app.tasks import crisis_score_inputs_refresh as module

    assert module.run_crisis_score_inputs_refresh_task.actor_name == "run_crisis_score_inputs_refresh"
