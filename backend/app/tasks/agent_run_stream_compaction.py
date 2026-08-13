"""Explicit compaction for the agent run governance JSONL streams.

The ``agent_run`` stream appends one record per lifecycle transition and never
shrinks, which degrades every read path over time. This task rewrites the
stream so that terminal runs older than the retention window keep only their
last terminal snapshot; every removed record is appended verbatim to a
side-by-side ``<stream>.archive.jsonl`` file so no data is lost.

The task is idempotent and is intentionally not wired to any scheduler: it can
be invoked directly (``compact_agent_run_streams``) or dispatched via the
registered Dramatiq actor.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.app.governance.locks import acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services.agent_run_service import (
    AGENT_RUN_DISPATCH_STREAM,
    AGENT_RUN_STREAM,
    AGENT_RUN_TRANSITION_FILE_LOCK,
)
from backend.app.tasks.broker import register_actor_once

AGENT_RUN_COMPACTION_STREAM = "agent_run_compaction"
AGENT_RUN_COMPACTION_JOB_NAME = "agent_run_stream_compaction"
AGENT_RUN_STREAM_RETENTION_DAYS = 7.0
AGENT_RUN_COMPACTION_TIME_LIMIT_MS = 600_000
_TERMINAL_AGENT_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})
_RUN_RECORD_TIME_FIELDS = ("finished_at", "started_at", "queued_at")
_LOGGER = logging.getLogger(__name__)


def compact_agent_run_streams(*, settings: Any) -> dict[str, object]:
    """Compact the ``agent_run`` and ``agent_run_dispatch`` governance streams.

    Rules:

    - Records are grouped by ``run_id``.
    - A run is compacted only when its latest record is terminal AND the run's
      last write time is older than the retention window (default 7 days,
      overridable via ``settings.agent_run_stream_retention_days``).
    - A compacted run keeps only its last (terminal snapshot) record in
      ``agent_run``; its ``agent_run_dispatch`` acceptance records are removed.
    - Non-terminal runs, in-window runs, and unparseable lines are kept as-is.
    - Every removed line is appended verbatim to ``<stream>.archive.jsonl``.
    """
    repo = GovernanceRepository(base_dir=settings.governance_path)
    base_dir = Path(repo.base_dir)
    retention_days = _retention_days(settings)
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    # Same lock order as agent_run_service state transitions (transition lock,
    # then the repository's JSONL batch lock) so the rewrite can never
    # interleave with a read-then-append state transition or a raw append.
    # Repository methods must not be called inside this block: the file locks
    # are not reentrant, and repo.append/read_all acquire the batch lock again.
    with acquire_lock(
        AGENT_RUN_TRANSITION_FILE_LOCK,
        base_dir=base_dir,
        timeout_seconds=30.0,
    ):
        with acquire_lock(
            repo._batch_lock(),  # noqa: SLF001 - reuse the exact existing stream lock
            base_dir=base_dir,
            timeout_seconds=30.0,
        ):
            run_stats, compacted_run_ids = _compact_run_stream(
                base_dir=base_dir,
                cutoff=cutoff,
            )
            dispatch_stats = _compact_dispatch_stream(
                base_dir=base_dir,
                compacted_run_ids=compacted_run_ids,
            )

    archived_total = int(run_stats["archived"]) + int(dispatch_stats["archived"])
    stats: dict[str, object] = {
        "job_name": AGENT_RUN_COMPACTION_JOB_NAME,
        "retention_days": retention_days,
        "runs_compacted": len(compacted_run_ids),
        "agent_run_total": run_stats["total"],
        "agent_run_kept": run_stats["kept"],
        "agent_run_archived": run_stats["archived"],
        "agent_run_dispatch_total": dispatch_stats["total"],
        "agent_run_dispatch_kept": dispatch_stats["kept"],
        "agent_run_dispatch_archived": dispatch_stats["archived"],
    }
    _LOGGER.info(
        "Agent run stream compaction finished retention_days=%g runs_compacted=%d "
        "agent_run_total=%d agent_run_kept=%d agent_run_archived=%d "
        "agent_run_dispatch_total=%d agent_run_dispatch_kept=%d agent_run_dispatch_archived=%d",
        retention_days,
        len(compacted_run_ids),
        run_stats["total"],
        run_stats["kept"],
        run_stats["archived"],
        dispatch_stats["total"],
        dispatch_stats["kept"],
        dispatch_stats["archived"],
    )
    # A no-op rerun must not grow governance itself, so the traceability event
    # is only written when the pass actually archived something.
    if archived_total > 0:
        repo.append(
            AGENT_RUN_COMPACTION_STREAM,
            {**stats, "compacted_at": datetime.now(UTC).isoformat()},
        )
    return stats


def _compact_run_stream(
    *,
    base_dir: Path,
    cutoff: datetime,
) -> tuple[dict[str, int], set[str]]:
    target = base_dir / f"{AGENT_RUN_STREAM}.jsonl"
    lines = _read_lines(target)
    parsed = [_parse_json(line) for line in lines]

    indices_by_run: dict[str, list[int]] = {}
    for index, record in enumerate(parsed):
        if record is None:
            continue
        run_id = str(record.get("run_id") or "").strip()
        if not run_id:
            continue
        indices_by_run.setdefault(run_id, []).append(index)

    archive_indices: set[int] = set()
    compacted_run_ids: set[str] = set()
    for run_id, indices in indices_by_run.items():
        latest = parsed[indices[-1]]
        assert latest is not None
        if str(latest.get("status") or "") not in _TERMINAL_AGENT_RUN_STATUSES:
            continue
        last_write = _last_write_time(parsed[index] for index in indices)
        if last_write is None or last_write >= cutoff:
            continue
        # Include single-record runs so a rerun still cleans their dispatch
        # rows after a crash between the two stream rewrites.
        compacted_run_ids.add(run_id)
        archive_indices.update(indices[:-1])

    kept_lines = [line for index, line in enumerate(lines) if index not in archive_indices]
    archived_lines = [lines[index] for index in sorted(archive_indices)]
    _archive_and_rewrite(target=target, kept_lines=kept_lines, archived_lines=archived_lines)
    return (
        {"total": len(lines), "kept": len(kept_lines), "archived": len(archived_lines)},
        compacted_run_ids,
    )


def _compact_dispatch_stream(
    *,
    base_dir: Path,
    compacted_run_ids: set[str],
) -> dict[str, int]:
    target = base_dir / f"{AGENT_RUN_DISPATCH_STREAM}.jsonl"
    lines = _read_lines(target)
    kept_lines: list[str] = []
    archived_lines: list[str] = []
    for line in lines:
        record = _parse_json(line)
        run_id = str((record or {}).get("run_id") or "").strip()
        if record is not None and run_id and run_id in compacted_run_ids:
            archived_lines.append(line)
        else:
            kept_lines.append(line)
    _archive_and_rewrite(target=target, kept_lines=kept_lines, archived_lines=archived_lines)
    return {"total": len(lines), "kept": len(kept_lines), "archived": len(archived_lines)}


def _archive_and_rewrite(
    *,
    target: Path,
    kept_lines: list[str],
    archived_lines: list[str],
) -> None:
    if not archived_lines:
        return
    # Archive first: a crash between the two writes leaves duplicates (safe),
    # never data loss. Removed lines are appended verbatim.
    archive_path = target.with_name(f"{target.stem}.archive.jsonl")
    with archive_path.open("a", encoding="utf-8") as handle:
        for line in archived_lines:
            handle.write(line + "\n")
    tmp_path = target.with_name(f"{target.name}.tmp")
    tmp_path.write_text(
        "".join(f"{line}\n" for line in kept_lines),
        encoding="utf-8",
    )
    os.replace(tmp_path, target)


def _read_lines(target: Path) -> list[str]:
    if not target.exists():
        return []
    return [
        line
        for line in target.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _parse_json(line: str) -> dict[str, object] | None:
    try:
        record = json.loads(line)
    except ValueError:
        return None
    return record if isinstance(record, dict) else None


def _last_write_time(records) -> datetime | None:
    latest: datetime | None = None
    for record in records:
        if record is None:
            continue
        for field in _RUN_RECORD_TIME_FIELDS:
            parsed = _parse_utc_datetime(record.get(field))
            if parsed is not None and (latest is None or parsed > latest):
                latest = parsed
    return latest


def _parse_utc_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _retention_days(settings: Any) -> float:
    try:
        days = float(
            getattr(
                settings,
                "agent_run_stream_retention_days",
                AGENT_RUN_STREAM_RETENTION_DAYS,
            )
            or AGENT_RUN_STREAM_RETENTION_DAYS
        )
    except (TypeError, ValueError):
        days = AGENT_RUN_STREAM_RETENTION_DAYS
    return max(days, 0.0)


def _compact_agent_run_streams_task() -> None:
    compact_agent_run_streams(settings=get_settings())
    return None


compact_agent_run_streams_task = register_actor_once(
    "compact_agent_run_streams",
    _compact_agent_run_streams_task,
    max_retries=0,
    time_limit_ms=AGENT_RUN_COMPACTION_TIME_LIMIT_MS,
)
