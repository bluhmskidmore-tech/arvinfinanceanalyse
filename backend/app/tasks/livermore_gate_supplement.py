from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection

LIVERMORE_GATE_SUPPLEMENT_LOCK = LockDefinition(
    key="lock:duckdb:livermore-gate-supplement",
    ttl_seconds=600,
)
RULE_VERSION = "rv_livermore_gate_supplement_v1"


def materialize_livermore_gate_supplement_daily(
    *,
    duckdb_path: str | None = None,
    rows: list[dict[str, Any]],
    run_id: str | None = None,
) -> dict[str, object]:
    """Write analytical Livermore gate supplement rows (breadth / limit-up flags). API-safe callers must not use."""
    from backend.app.governance.settings import get_settings

    settings = get_settings()
    path = Path(duckdb_path or settings.duckdb_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    effective_run = run_id or f"livermore_gate_supplement:{uuid.uuid4().hex[:12]}"

    with acquire_lock(LIVERMORE_GATE_SUPPLEMENT_LOCK, base_dir=path.parent):
        conn = duckdb.connect(str(path), read_only=False)
        try:
            apply_pending_migrations_on_connection(conn)
            conn.execute("begin transaction")
            dates: list[str] = []
            for raw in rows:
                td = raw.get("trade_date")
                if hasattr(td, "isoformat"):
                    dates.append(td.isoformat())  # type: ignore[union-attr]
                else:
                    dates.append(str(td))
            for d in sorted(set(dates)):
                conn.execute(
                    "delete from fact_livermore_gate_supplement_daily where trade_date = ?",
                    [d],
                )
            for raw in rows:
                td = raw["trade_date"]
                trade_date = td.isoformat() if hasattr(td, "isoformat") else str(td)
                b = raw.get("breadth_5d")
                breadth = float(b) if b is not None else None
                lim = raw.get("limit_up_quality_ok")
                lim_ok: bool | None
                if lim is None:
                    lim_ok = None
                else:
                    lim_ok = bool(lim)
                conn.execute(
                    """
                    insert into fact_livermore_gate_supplement_daily (
                      trade_date, breadth_5d, limit_up_quality_ok,
                      source_version, vendor_version, rule_version, run_id
                    ) values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        trade_date,
                        breadth,
                        lim_ok,
                        str(raw.get("source_version") or "sv_livermore_gate_supplement"),
                        str(raw.get("vendor_version") or "vv_livermore_gate_supplement"),
                        RULE_VERSION,
                        effective_run,
                    ],
                )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
        finally:
            conn.close()

    return {
        "status": "completed",
        "run_id": effective_run,
        "row_count": len(rows),
        "rule_version": RULE_VERSION,
    }


materialize_livermore_gate_supplement_daily.fn = materialize_livermore_gate_supplement_daily
