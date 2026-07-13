from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from backend.app.api.routes import macro_toolkit as macro_toolkit_route
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.services import macro_toolkit_service
from fastapi import BackgroundTasks, HTTPException


def _permission() -> dict[str, object]:
    return {
        "mode": "scoped_refresh",
        "allowed": True,
        "user_id": "fixture-user",
        "role": "viewer",
        "identity_source": "test",
        "resource": "macro_toolkit.choice_stock",
        "actions": ["history", "factor_snapshot", "theme_overlay"],
    }


def _history_result() -> dict[str, object]:
    return {
        "status": "completed",
        "run_id": "choice_stock_materialize:2026-04-30:fixture",
        "as_of_date": "2026-04-30",
        "row_count": 111,
        "stock_code_count": 5,
        "source_version": "sv_history",
        "vendor_version": "vv_history",
    }


def test_choice_stock_refresh_request_defaults_overlay_off() -> None:
    payload = macro_toolkit_route.ChoiceStockRefreshRequest().model_dump()

    assert payload["theme_overlay_mode"] == "off"


def test_choice_stock_refresh_route_allows_overlay_only_and_passes_archive_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        choice_stock_catalog_file=tmp_path / "choice_stock_catalog.json",
        governance_path=tmp_path / "governance",
        local_archive_path=tmp_path / "archive",
    )
    monkeypatch.setattr(macro_toolkit_route, "get_settings", lambda: settings)
    monkeypatch.setattr(
        macro_toolkit_route, "_ensure_choice_stock_refresh_allowed", lambda *_args: None
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "_choice_stock_refresh_overview",
        lambda *_args, **_kwargs: {"status": "queued"},
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "queue_choice_stock_refresh",
        lambda **kwargs: (
            calls.append(dict(kwargs))
            or macro_toolkit_service.MacroToolkitActionResult(
                payload={"status": "queued", "run_id": "choice-stock-refresh-fixture"},
                quality_flag="ok",
                fallback_mode="none",
                as_of_date="2026-04-30",
            )
        ),
    )
    auth = SimpleNamespace(
        user_id="fixture-user", role="viewer", identity_source="test"
    )

    result = macro_toolkit_route.macro_toolkit_refresh_choice_stock(
        background_tasks=BackgroundTasks(),
        auth=auth,
        idempotency_key="overlay-only",
        request=macro_toolkit_route.ChoiceStockRefreshRequest(
            as_of_date="2026-04-30",
            refresh_history=False,
            refresh_factors=False,
            theme_overlay_mode="archive",
        ),
    )

    assert result["result"]["refresh"]["status"] == "queued"
    assert calls[0]["refresh_history"] is False
    assert calls[0]["refresh_factors"] is False
    assert calls[0]["theme_overlay_mode"] == "archive"
    assert calls[0]["archive_root"] == str(settings.local_archive_path)


def test_choice_stock_refresh_route_rejects_when_every_action_is_off() -> None:
    with pytest.raises(HTTPException) as exc_info:
        macro_toolkit_route.macro_toolkit_refresh_choice_stock(
            background_tasks=BackgroundTasks(),
            auth=SimpleNamespace(
                user_id="fixture-user", role="viewer", identity_source="test"
            ),
            request=macro_toolkit_route.ChoiceStockRefreshRequest(
                refresh_history=False,
                refresh_factors=False,
                theme_overlay_mode="off",
            ),
        )

    assert exc_info.value.status_code == 400


def test_queue_choice_stock_refresh_records_mode_in_queue_status_and_task(
    tmp_path: Path,
) -> None:
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    background_tasks = BackgroundTasks()

    queued = macro_toolkit_service.queue_choice_stock_refresh(
        background_tasks=background_tasks,
        duckdb_path=str(tmp_path / "moss.duckdb"),
        catalog_path=str(tmp_path / "choice_stock_catalog.json"),
        governance_path=str(governance_path),
        archive_root=str(archive_root),
        as_of_date="2026-04-30",
        refresh_history=True,
        refresh_factors=False,
        factor_max_stock_count=None,
        theme_overlay_mode="archive",
        permission=_permission(),
        idempotency_key="fixture-key",
    )

    assert queued.payload["theme_overlay_mode"] == "archive"
    assert queued.payload["theme_overlay_status"] == "pending"
    assert background_tasks.tasks[0].kwargs["theme_overlay_mode"] == "archive"
    assert background_tasks.tasks[0].kwargs["archive_root"] == str(archive_root)
    status = macro_toolkit_service.choice_stock_refresh_status(
        governance_path,
        run_id=str(queued.payload["run_id"]),
    )
    assert status["theme_overlay_mode"] == "archive"
    assert status["theme_overlay_status"] == "pending"


def test_choice_stock_refresh_idempotency_matching_includes_overlay_mode(
    tmp_path: Path,
) -> None:
    governance_path = tmp_path / "governance"
    for mode in ("off", "dry_run"):
        macro_toolkit_service.append_choice_stock_refresh_run(
            governance_path,
            macro_toolkit_service.build_choice_stock_refresh_run_payload(
                run_id=f"choice_stock_refresh:2026-04-30:{mode}",
                status="completed",
                as_of_date="2026-04-30",
                refresh_history=True,
                refresh_factors=False,
                theme_overlay_mode=mode,
                idempotency_key="same-key",
            ),
        )

    selected = macro_toolkit_service.latest_choice_stock_refresh_for_idempotency_key(
        governance_path,
        as_of_date="2026-04-30",
        refresh_history=True,
        refresh_factors=False,
        factor_max_stock_count=None,
        theme_overlay_mode="off",
        idempotency_key="same-key",
    )

    assert selected is not None
    assert selected["run_id"] == "choice_stock_refresh:2026-04-30:off"


def test_choice_stock_refresh_worker_publishes_completion_before_overlay_and_then_terminal_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    governance_path = tmp_path / "governance"
    run_id = "choice_stock_refresh:2026-04-30:fixture"
    overlay_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: _history_result(),
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "verify_choice_stock_daily_observation_landing",
        lambda **_kwargs: 5,
    )

    def fake_overlay(**kwargs: object) -> dict[str, object]:
        repo = GovernanceRepository(base_dir=governance_path)
        completed = [
            row
            for row in repo.read_all(CACHE_BUILD_RUN_STREAM)
            if row.get("run_id") == run_id and row.get("status") == "completed"
        ]
        assert len(completed) == 1
        manifest = repo.read_latest_manifest(
            macro_toolkit_service.CHOICE_STOCK_REFRESH_CACHE_KEY
        )
        assert manifest is not None
        assert manifest["run_id"] == run_id
        visible_status = macro_toolkit_service.choice_stock_refresh_status(
            governance_path,
            run_id=run_id,
        )
        assert visible_status["status"] == "running"
        assert visible_status["trigger_mode"] == "async"
        assert visible_status["choice_completion_status"] == "completed"
        in_flight = macro_toolkit_service.latest_choice_stock_inflight_refresh(
            governance_path,
            as_of_date="2026-04-30",
        )
        assert in_flight is not None
        assert in_flight["run_id"] == run_id
        with pytest.raises(macro_toolkit_service.MacroToolkitConflictError):
            macro_toolkit_service.queue_choice_stock_refresh(
                background_tasks=BackgroundTasks(),
                duckdb_path=str(tmp_path / "moss.duckdb"),
                catalog_path=str(tmp_path / "choice_stock_catalog.json"),
                governance_path=str(governance_path),
                archive_root=str(tmp_path / "archive"),
                as_of_date="2026-04-30",
                refresh_history=True,
                refresh_factors=False,
                factor_max_stock_count=None,
                theme_overlay_mode="off",
                permission=_permission(),
            )
        overlay_calls.append(dict(kwargs))
        return {
            "mode": "archive",
            "status": "completed",
            "overlay_status": "completed",
            "message": None,
            "member_count": 12,
            "run_id": kwargs["run_id"],
        }

    monkeypatch.setattr(
        macro_toolkit_service,
        "refresh_choice_stock_theme_overlay",
        fake_overlay,
        raising=False,
    )

    macro_toolkit_service._run_choice_stock_refresh_job(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        catalog_path=str(tmp_path / "choice_stock_catalog.json"),
        governance_path=str(governance_path),
        archive_root=str(tmp_path / "archive"),
        run_id=run_id,
        as_of_date="2026-04-30",
        queued_at="2026-07-12T12:00:00+00:00",
        refresh_history=True,
        refresh_factors=False,
        factor_max_stock_count=None,
        theme_overlay_mode="archive",
        permission=_permission(),
    )

    digest = hashlib.sha256(f"{run_id}|2026-04-30".encode()).hexdigest()[:16]
    assert overlay_calls == [
        {
            "mode": "archive",
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "governance_dir": str(governance_path),
            "archive_root": str(tmp_path / "archive"),
            "expected_report_date": "2026-04-30",
            "run_id": f"{run_id}:theme-overlay",
            "source_version": f"sv_choice_stock_theme_overlay_{digest}",
            "vendor_version": "vv_tushare_ths_current_overlay_v1",
        }
    ]
    status = macro_toolkit_service.choice_stock_refresh_status(
        governance_path, run_id=run_id
    )
    assert status["status"] == "completed"
    assert status["trigger_mode"] == "terminal"
    assert status["theme_overlay_mode"] == "archive"
    assert status["theme_overlay_status"] == "completed"
    assert status["theme_overlay_message"] is None
    assert status["theme_overlay_member_count"] == 12
    assert status["theme_overlay_run_id"] == f"{run_id}:theme-overlay"
    assert (
        macro_toolkit_service.latest_choice_stock_inflight_refresh(
            governance_path,
            as_of_date="2026-04-30",
        )
        is None
    )


def test_choice_stock_refresh_overlay_only_reuses_existing_observation_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    governance_path = tmp_path / "governance"
    repo = GovernanceRepository(base_dir=governance_path)
    previous_run_id = "choice_stock_refresh:2026-04-30:previous"
    previous_payload = macro_toolkit_service.build_choice_stock_refresh_run_payload(
        run_id=previous_run_id,
        status="completed",
        as_of_date="2026-04-30",
        refresh_history=True,
        refresh_factors=False,
        history_row_count=111,
        source_version="sv_history",
        vendor_version="vv_history",
        permission=_permission(),
    )
    previous_manifest = macro_toolkit_service.build_choice_stock_observation_manifest(
        history_result=_history_result(),
        refresh_run_id=previous_run_id,
        report_date="2026-04-30",
        daily_observation_row_count=5,
        created_at="2026-07-12T12:00:00+00:00",
    )
    macro_toolkit_service.append_choice_stock_refresh_completion(
        governance_repo=repo,
        completed_run_payload=previous_payload,
        observation_manifest=previous_manifest,
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("history must not run")),
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_factor_snapshot",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("factors must not run")),
    )

    def fake_overlay(**kwargs: object) -> dict[str, object]:
        assert repo.read_latest_manifest(
            macro_toolkit_service.CHOICE_STOCK_REFRESH_CACHE_KEY
        ) == previous_manifest
        return {
            "mode": "dry_run",
            "status": "dry_run",
            "overlay_status": "dry_run",
            "message": None,
            "member_count": 8,
            "run_id": kwargs["run_id"],
        }

    monkeypatch.setattr(
        macro_toolkit_service,
        "refresh_choice_stock_theme_overlay",
        fake_overlay,
    )
    run_id = "choice_stock_refresh:2026-04-30:overlay-only"

    macro_toolkit_service._run_choice_stock_refresh_job(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        catalog_path=str(tmp_path / "choice_stock_catalog.json"),
        governance_path=str(governance_path),
        archive_root=str(tmp_path / "archive"),
        run_id=run_id,
        as_of_date="2026-04-30",
        queued_at="2026-07-12T12:01:00+00:00",
        refresh_history=False,
        refresh_factors=False,
        factor_max_stock_count=None,
        theme_overlay_mode="dry_run",
        permission=_permission(),
    )

    assert repo.read_latest_manifest(
        macro_toolkit_service.CHOICE_STOCK_REFRESH_CACHE_KEY
    ) == previous_manifest
    status = macro_toolkit_service.choice_stock_refresh_status(
        governance_path,
        run_id=run_id,
    )
    assert status["status"] == "completed"
    assert status["theme_overlay_status"] == "dry_run"
    assert status["theme_overlay_member_count"] == 8


@pytest.mark.parametrize(
    ("failure_kind", "expected_overlay_status"),
    (("raises", "archive_failed"), ("source_status", "source_failed")),
)
def test_choice_stock_refresh_worker_keeps_choice_completed_when_overlay_fails(
    tmp_path: Path,
    monkeypatch,
    failure_kind: str,
    expected_overlay_status: str,
) -> None:
    governance_path = tmp_path / "governance"
    run_id = "choice_stock_refresh:2026-04-30:overlay-failure"
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: _history_result(),
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "verify_choice_stock_daily_observation_landing",
        lambda **_kwargs: 5,
    )
    def fail_overlay(**kwargs: object) -> dict[str, object]:
        if failure_kind == "raises":
            raise RuntimeError(r"THS timeout token=secret C:\private\overlay.json")
        return {
            "status": "source_failed",
            "overlay_status": "source_failed",
            "message": r"token=secret C:\private\overlay.json",
            "member_count": 0,
            "run_id": kwargs["run_id"],
        }

    monkeypatch.setattr(
        macro_toolkit_service,
        "refresh_choice_stock_theme_overlay",
        fail_overlay,
        raising=False,
    )

    macro_toolkit_service._run_choice_stock_refresh_job(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        catalog_path=str(tmp_path / "choice_stock_catalog.json"),
        governance_path=str(governance_path),
        archive_root=str(tmp_path / "archive"),
        run_id=run_id,
        as_of_date="2026-04-30",
        queued_at="2026-07-12T12:00:00+00:00",
        refresh_history=True,
        refresh_factors=False,
        factor_max_stock_count=None,
        theme_overlay_mode="archive",
        permission=_permission(),
    )

    records = [
        row
        for row in GovernanceRepository(base_dir=governance_path).read_all(
            CACHE_BUILD_RUN_STREAM
        )
        if row.get("run_id") == run_id
    ]
    assert not [row for row in records if row.get("status") == "failed"]
    assert records[-1]["status"] == "completed"
    assert records[-1]["theme_overlay_status"] == expected_overlay_status
    assert records[-1]["theme_overlay_message"] == (
        "Theme overlay refresh failed; see server logs."
    )
    assert "secret" not in str(
        macro_toolkit_service.choice_stock_refresh_status(
            governance_path, run_id=run_id
        )
    )
    assert "private" not in str(
        macro_toolkit_service.choice_stock_refresh_status(
            governance_path, run_id=run_id
        )
    )
    assert records[-1]["theme_overlay_member_count"] == 0
    assert records[-1]["theme_overlay_run_id"] == f"{run_id}:theme-overlay"
