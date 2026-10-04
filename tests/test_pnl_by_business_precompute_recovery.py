from types import SimpleNamespace
from unittest.mock import Mock

from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.pnl_precompute_state import (
    PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
)
from backend.app.services.pnl_by_business_precompute_lifecycle import (
    queue_precompute_refresh,
    recover_pending_precompute,
)
from backend.app.services.pnl_task_dispatch import (
    PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
)


TARGET_DATES = ["2026-06-30", "2026-07-31"]


def _settings(tmp_path):
    return SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        governance_path=tmp_path / "governance",
    )


def _pending(*, dependency_revision: int) -> dict[str, object]:
    return {
        "year": 2026,
        "dependency_revision": dependency_revision,
        "dirty_from_date": TARGET_DATES[0],
        "target_dates": list(TARGET_DATES),
        "reason": "resource_recovery_test",
        "invalidated_at": "2026-09-14T00:00:00+00:00",
        "protocol_version": PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
    }


def _append_resource_failure(settings, *, run_id: str, dependency_revision: int):
    record = {
        "run_id": run_id,
        "job_name": PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME,
        "status": "failed",
        "failure_category": "resource_over_budget",
        "target_year": 2026,
        "dependency_revision": dependency_revision,
        "target_as_of_dates": list(TARGET_DATES),
        "resource_limits": {"status": "over_budget"},
    }
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        record,
    )
    return record


def test_auto_dirty_recovery_keeps_same_revision_resource_failure_terminal(tmp_path):
    settings = _settings(tmp_path)
    failure = _append_resource_failure(
        settings,
        run_id="pnl-by-business-resource-failed",
        dependency_revision=0,
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {**failure, "status": "queued", "failure_category": ""},
    )
    queue_refresh = Mock()

    recovered = recover_pending_precompute(
        settings,
        pending=_pending(dependency_revision=0),
        optional_cutoffs=lambda *_args, **_kwargs: list(TARGET_DATES),
        queue_refresh=queue_refresh,
    )

    queue_refresh.assert_not_called()
    assert recovered is not None
    assert recovered["run_id"] == "pnl-by-business-resource-failed"
    assert recovered["status"] == "failed"
    assert recovered["failure_category"] == "resource_over_budget"


def test_auto_dirty_recovery_allows_a_later_dependency_revision(tmp_path):
    settings = _settings(tmp_path)
    _append_resource_failure(
        settings,
        run_id="pnl-by-business-old-revision",
        dependency_revision=0,
    )
    queue_refresh = Mock(return_value={"run_id": "new-revision-run"})

    recovered = recover_pending_precompute(
        settings,
        pending=_pending(dependency_revision=1),
        optional_cutoffs=lambda *_args, **_kwargs: list(TARGET_DATES),
        queue_refresh=queue_refresh,
    )

    assert recovered == {"run_id": "new-revision-run"}
    assert queue_refresh.call_args.kwargs["dependency_revision"] == 1
    assert queue_refresh.call_args.kwargs["as_of_dates"] == TARGET_DATES


def test_explicit_queue_creates_new_run_after_resource_failure(tmp_path):
    settings = _settings(tmp_path)
    _append_resource_failure(
        settings,
        run_id="pnl-by-business-failed-explicit",
        dependency_revision=0,
    )
    task_actor = SimpleNamespace(send=Mock())

    queued = queue_precompute_refresh(
        settings,
        year=2026,
        as_of_date=None,
        trigger_reason="user_requested_retry",
        raise_on_dispatch_failure=True,
        raise_on_duplicate=False,
        as_of_dates=list(TARGET_DATES),
        scope="page_dependencies",
        dependency_revision=0,
        adjustment_handoff_ids=None,
        task_actor=task_actor,
    )

    assert queued is not None
    assert queued["run_id"] != "pnl-by-business-failed-explicit"
    task_actor.send.assert_called_once()
    assert task_actor.send.call_args.kwargs["run_id"] == queued["run_id"]
