from __future__ import annotations

from pathlib import Path

import duckdb
from backend.app.repositories.cffex_member_rank_repo import (
    CffexMemberRankRow,
    replace_member_rank_rows,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope


def persist_cffex_member_rank_rows(
    *,
    duckdb_path: str | Path,
    rows: list[CffexMemberRankRow],
) -> int:
    if not rows:
        return 0

    resolved_path = Path(duckdb_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(resolved_path), read_only=False)
    try:
        with repository_task_write_scope(__name__):
            return replace_member_rank_rows(conn, rows)
    finally:
        conn.close()
