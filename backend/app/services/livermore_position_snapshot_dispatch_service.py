"""Service-owned dispatch for Livermore position snapshot materialization."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path


def queue_livermore_position_snapshot_csv(
    *,
    as_of_date: str,
    csv_path: str | Path,
    duckdb_path: str | Path,
) -> dict[str, object]:
    from backend.app.tasks.livermore_position_snapshot_materialize import (
        materialize_livermore_position_snapshot,
    )

    resolved_csv_path = str(csv_path)
    run_id = _build_position_snapshot_run_id(as_of_date)
    materialize_livermore_position_snapshot.send(
        as_of_date=as_of_date,
        csv_path=resolved_csv_path,
        duckdb_path=str(duckdb_path),
        run_id=run_id,
    )
    return {
        "status": "queued",
        "run_id": run_id,
        "as_of_date": as_of_date,
        "input_mode": "csv",
        "csv_path": resolved_csv_path,
    }


def queue_livermore_position_snapshot_rows(
    *,
    as_of_date: str,
    rows: Sequence[Mapping[str, object]],
    duckdb_path: str | Path,
) -> dict[str, object]:
    from backend.app.tasks.livermore_position_snapshot_materialize import (
        materialize_livermore_position_snapshot_rows,
    )

    run_id = _build_position_snapshot_run_id(as_of_date)
    materialize_livermore_position_snapshot_rows.send(
        as_of_date=as_of_date,
        rows=[dict(row) for row in rows],
        duckdb_path=str(duckdb_path),
        run_id=run_id,
    )
    return {
        "status": "queued",
        "run_id": run_id,
        "as_of_date": as_of_date,
        "input_mode": "manual",
    }


def _build_position_snapshot_run_id(as_of_date: str) -> str:
    return f"livermore_position_snapshot:{as_of_date}:{uuid.uuid4().hex[:12]}"
