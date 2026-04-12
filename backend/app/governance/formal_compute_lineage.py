from __future__ import annotations

from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)


def resolve_formal_manifest_lineage(
    *,
    governance_dir: str,
    cache_key: str,
    sql_dsn: str = "",
    backend_mode: str = "jsonl",
) -> dict[str, object]:
    rows = _governance_repo(
        governance_dir=governance_dir,
        sql_dsn=sql_dsn,
        backend_mode=backend_mode,
    ).read_all(CACHE_MANIFEST_STREAM)
    matches = [row for row in rows if str(row.get("cache_key")) == cache_key]
    if not matches:
        raise RuntimeError(f"Canonical formal lineage unavailable for cache_key={cache_key}.")

    latest = matches[-1]
    required = ("source_version", "vendor_version", "rule_version")
    missing = [key for key in required if not str(latest.get(key) or "").strip()]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Canonical formal lineage malformed for cache_key={cache_key}: missing {joined}."
        )
    return latest


def resolve_completed_formal_build_lineage(
    *,
    governance_dir: str,
    cache_key: str,
    job_name: str,
    report_date: str,
    sql_dsn: str = "",
    backend_mode: str = "jsonl",
) -> dict[str, object] | None:
    rows = _governance_repo(
        governance_dir=governance_dir,
        sql_dsn=sql_dsn,
        backend_mode=backend_mode,
    ).read_all(CACHE_BUILD_RUN_STREAM)
    matches = [
        row
        for row in rows
        if str(row.get("cache_key")) == cache_key
        and str(row.get("job_name")) == job_name
        and str(row.get("status")) == "completed"
        and str(row.get("report_date")) == report_date
        and str(row.get("source_version") or "").strip()
    ]
    return matches[-1] if matches else None


def _governance_repo(
    *,
    governance_dir: str,
    sql_dsn: str,
    backend_mode: str,
) -> GovernanceRepository:
    return GovernanceRepository(
        base_dir=governance_dir,
        sql_dsn=sql_dsn,
        backend_mode=backend_mode,
    )
