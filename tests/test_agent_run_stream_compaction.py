from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services import agent_run_service
from backend.app.tasks import agent_run_stream_compaction as compaction

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]

OLD_AT = (datetime.now(UTC) - timedelta(days=8)).isoformat()
RECENT_AT = datetime.now(UTC).isoformat()


def _settings(tmp_path: Path, **overrides) -> SimpleNamespace:
    return SimpleNamespace(
        agent_provider="hermes",
        agent_hermes_model="gpt-test",
        agent_hermes_transport="bridge",
        agent_hermes_toolsets="file",
        agent_hermes_timeout_seconds=9.0,
        governance_path=str(tmp_path / "governance"),
        **overrides,
    )


def _run_record(
    run_id: str,
    status: str,
    *,
    at: str,
    owner: str = "owner-1",
    provider: str = "hermes",
    question: str = "compact me",
) -> dict[str, object]:
    record: dict[str, object] = {
        "job_name": "agent_run",
        "run_id": run_id,
        "status": status,
        "question": question,
        "request": {"question": question, "context": {"user_id": owner}},
        "provider": provider,
        "model": "gpt-test",
        "transport": "bridge",
        "toolsets": "file",
        "queued_at": at,
    }
    if status != "queued":
        record["started_at"] = at
    if status in {"completed", "failed", "cancelled"}:
        record["finished_at"] = at
    return record


def _seed_streams(settings: SimpleNamespace) -> GovernanceRepository:
    repo = GovernanceRepository(base_dir=settings.governance_path)
    for status in ("queued", "starting", "running", "completed"):
        repo.append(
            compaction.AGENT_RUN_STREAM,
            _run_record("agent_run:old-done", status, at=OLD_AT),
        )
    for status in ("queued", "running"):
        repo.append(
            compaction.AGENT_RUN_STREAM,
            _run_record("agent_run:old-active", status, at=OLD_AT, provider="local"),
        )
    for status in ("queued", "completed"):
        repo.append(
            compaction.AGENT_RUN_STREAM,
            _run_record("agent_run:recent-done", status, at=RECENT_AT),
        )
    for run_id in (
        "agent_run:old-done",
        "agent_run:old-active",
        "agent_run:recent-done",
    ):
        repo.append(
            compaction.AGENT_RUN_DISPATCH_STREAM,
            {"run_id": run_id, "accepted_at": OLD_AT},
        )
    return repo


def _stream_records(settings: SimpleNamespace, filename: str) -> list[dict[str, object]]:
    target = Path(settings.governance_path) / filename
    if not target.exists():
        return []
    return [
        json.loads(line)
        for line in target.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("not-json")
    ]


@pytest.fixture(autouse=True)
def _clear_agent_run_cache() -> None:
    agent_run_service._AGENT_RUN_LATEST_RECORDS.clear()


def test_compacts_old_terminal_runs_and_archives_removed_records(tmp_path):
    settings = _settings(tmp_path)
    repo = _seed_streams(settings)
    run_stream_path = Path(settings.governance_path) / "agent_run.jsonl"
    with run_stream_path.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")

    stats = compaction.compact_agent_run_streams(settings=settings)

    assert stats["runs_compacted"] == 1
    assert stats["agent_run_total"] == 9
    assert stats["agent_run_kept"] == 6
    assert stats["agent_run_archived"] == 3
    assert stats["agent_run_dispatch_total"] == 3
    assert stats["agent_run_dispatch_kept"] == 2
    assert stats["agent_run_dispatch_archived"] == 1

    remaining = _stream_records(settings, "agent_run.jsonl")
    by_run: dict[str, list[str]] = {}
    for record in remaining:
        by_run.setdefault(str(record["run_id"]), []).append(str(record["status"]))
    assert by_run == {
        "agent_run:old-done": ["completed"],
        "agent_run:old-active": ["queued", "running"],
        "agent_run:recent-done": ["queued", "completed"],
    }
    # The compacted run keeps its full terminal snapshot.
    snapshot = [r for r in remaining if r["run_id"] == "agent_run:old-done"][0]
    assert snapshot["question"] == "compact me"
    assert snapshot["finished_at"] == OLD_AT
    # Unparseable lines are preserved in place, never archived.
    assert "not-json" in run_stream_path.read_text(encoding="utf-8")

    archived = _stream_records(settings, "agent_run.archive.jsonl")
    assert [record["status"] for record in archived] == ["queued", "starting", "running"]
    assert all(record["run_id"] == "agent_run:old-done" for record in archived)

    dispatch_remaining = _stream_records(settings, "agent_run_dispatch.jsonl")
    assert {str(record["run_id"]) for record in dispatch_remaining} == {
        "agent_run:old-active",
        "agent_run:recent-done",
    }
    dispatch_archived = _stream_records(settings, "agent_run_dispatch.archive.jsonl")
    assert [str(record["run_id"]) for record in dispatch_archived] == [
        "agent_run:old-done"
    ]

    events = repo.read_all(compaction.AGENT_RUN_COMPACTION_STREAM)
    assert len(events) == 1
    assert events[0]["job_name"] == "agent_run_stream_compaction"
    assert events[0]["runs_compacted"] == 1
    assert events[0]["agent_run_archived"] == 3
    assert events[0]["agent_run_dispatch_archived"] == 1
    assert events[0]["compacted_at"]


def test_compaction_is_idempotent_on_rerun(tmp_path):
    settings = _settings(tmp_path)
    repo = _seed_streams(settings)

    compaction.compact_agent_run_streams(settings=settings)
    run_stream_path = Path(settings.governance_path) / "agent_run.jsonl"
    dispatch_stream_path = Path(settings.governance_path) / "agent_run_dispatch.jsonl"
    archive_path = Path(settings.governance_path) / "agent_run.archive.jsonl"
    first_pass_files = (
        run_stream_path.read_bytes(),
        dispatch_stream_path.read_bytes(),
        archive_path.read_bytes(),
    )

    rerun_stats = compaction.compact_agent_run_streams(settings=settings)

    assert rerun_stats["agent_run_archived"] == 0
    assert rerun_stats["agent_run_dispatch_archived"] == 0
    assert (
        run_stream_path.read_bytes(),
        dispatch_stream_path.read_bytes(),
        archive_path.read_bytes(),
    ) == first_pass_files
    # A no-op rerun does not append another compaction event.
    assert len(repo.read_all(compaction.AGENT_RUN_COMPACTION_STREAM)) == 1


def test_retention_window_override_keeps_old_terminal_runs(tmp_path):
    settings = _settings(tmp_path, agent_run_stream_retention_days=30)
    _seed_streams(settings)
    run_stream_path = Path(settings.governance_path) / "agent_run.jsonl"
    before = run_stream_path.read_bytes()

    stats = compaction.compact_agent_run_streams(settings=settings)

    assert stats["retention_days"] == 30.0
    assert stats["runs_compacted"] == 0
    assert stats["agent_run_archived"] == 0
    assert stats["agent_run_dispatch_archived"] == 0
    assert run_stream_path.read_bytes() == before
    assert not (Path(settings.governance_path) / "agent_run.archive.jsonl").exists()
    assert not (
        Path(settings.governance_path) / "agent_run_dispatch.archive.jsonl"
    ).exists()


def test_service_read_paths_are_intact_after_compaction(tmp_path):
    settings = _settings(tmp_path)
    _seed_streams(settings)

    compaction.compact_agent_run_streams(settings=settings)

    status = agent_run_service.get_agent_run_status(
        run_id="agent_run:old-done",
        settings=settings,
    )
    assert status.status == "completed"
    assert status.question == "compact me"
    assert status.provider == "hermes"
    assert status.finished_at == OLD_AT

    listing = agent_run_service.list_agent_runs(
        settings=settings,
        owner_user_id="owner-1",
        limit=20,
    )
    listed = {item.run_id: item.status for item in listing.items}
    assert listed == {
        "agent_run:old-done": "completed",
        "agent_run:old-active": "running",
        "agent_run:recent-done": "completed",
    }


def test_compaction_handles_missing_streams(tmp_path):
    settings = _settings(tmp_path)

    stats = compaction.compact_agent_run_streams(settings=settings)

    assert stats["runs_compacted"] == 0
    assert stats["agent_run_total"] == 0
    assert stats["agent_run_dispatch_total"] == 0
    governance_dir = Path(settings.governance_path)
    assert not (governance_dir / "agent_run.archive.jsonl").exists()
    assert not (governance_dir / "agent_run_compaction.jsonl").exists()


def test_compaction_actor_is_registered_and_calls_service_entry(monkeypatch):
    actor = compaction.compact_agent_run_streams_task

    assert actor.actor_name == "compact_agent_run_streams"
    assert actor.options["max_retries"] == 0
    assert actor.options["time_limit"] == 600_000

    settings = SimpleNamespace()
    calls: list[object] = []
    monkeypatch.setattr(compaction, "get_settings", lambda: settings)
    monkeypatch.setattr(
        compaction,
        "compact_agent_run_streams",
        lambda *, settings: calls.append(settings),
    )

    assert actor.fn() is None
    assert calls == [settings]
