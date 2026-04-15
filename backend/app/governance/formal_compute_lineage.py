from __future__ import annotations

from collections.abc import Callable

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
    backend_mode: str = "",
) -> dict[str, object]:
    repo = _governance_repo(
        governance_dir=governance_dir,
        sql_dsn=sql_dsn,
        backend_mode=backend_mode,
    )
    latest = repo.read_latest_manifest(cache_key)
    if latest is None:
        raise RuntimeError(f"Canonical formal lineage unavailable for cache_key={cache_key}.")
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
    backend_mode: str = "",
) -> dict[str, object] | None:
    repo = _governance_repo(
        governance_dir=governance_dir,
        sql_dsn=sql_dsn,
        backend_mode=backend_mode,
    )
    cache_key_text = str(cache_key or "").strip()
    job_name_text = str(job_name or "").strip()
    report_date_text = str(report_date or "").strip()
    rows = repo.read_all(CACHE_BUILD_RUN_STREAM)
    for row in reversed(rows):
        if str(row.get("cache_key") or "").strip() != cache_key_text:
            continue
        if str(row.get("status") or "").strip() != "completed":
            continue
        if job_name_text and str(row.get("job_name") or "").strip() != job_name_text:
            continue
        if report_date_text and str(row.get("report_date") or "").strip() != report_date_text:
            continue
        if not str(row.get("source_version") or "").strip():
            continue
        return row
    return None


def resolve_formal_facts_lineage(
    *,
    governance_dir: str,
    cache_key: str,
    job_name: str,
    report_date: str,
    has_rows: bool,
    row_source_versions: list[str] | tuple[str, ...],
    default_source_version: str,
    default_rule_version: str,
    default_cache_version: str,
    default_vendor_version: str = "vv_none",
    sql_dsn: str = "",
    backend_mode: str = "",
) -> dict[str, str]:
    repo = _governance_repo(
        governance_dir=governance_dir,
        sql_dsn=sql_dsn,
        backend_mode=backend_mode,
    )
    latest_build = repo.read_latest_completed_run(
        cache_key,
        job_name=job_name,
        report_date=report_date,
    ) or {}
    normalized_row_sources = sorted(
        {
            str(value or "").strip()
            for value in row_source_versions
            if str(value or "").strip()
        }
    )
    if not has_rows and not latest_build:
        return {
            "source_version": default_source_version,
            "rule_version": default_rule_version,
            "cache_version": default_cache_version,
            "vendor_version": default_vendor_version,
        }
    latest_manifest = repo.read_latest_manifest(cache_key) or {}
    return {
        "source_version": _first_non_empty(
            str(latest_build.get("source_version") or "").strip(),
            "__".join(normalized_row_sources),
            default_source_version,
        ),
        "rule_version": _first_non_empty(
            str(latest_build.get("rule_version") or "").strip(),
            str(latest_manifest.get("rule_version") or "").strip(),
            default_rule_version,
        ),
        "cache_version": _first_non_empty(
            str(latest_build.get("cache_version") or "").strip(),
            str(latest_manifest.get("cache_version") or "").strip(),
            default_cache_version,
        ),
        "vendor_version": _first_non_empty(
            str(latest_build.get("vendor_version") or "").strip(),
            str(latest_manifest.get("vendor_version") or "").strip(),
            default_vendor_version,
        ),
    }


def resolve_formal_dates_lineage(
    *,
    governance_dir: str,
    cache_key: str,
    report_dates: list[str] | tuple[str, ...],
    default_source_version: str,
    default_rule_version: str,
    default_cache_version: str,
    default_vendor_version: str = "vv_none",
    fallback_lineage_loader: Callable[[str], dict[str, str]] | None = None,
) -> dict[str, str]:
    if report_dates:
        try:
            manifest = resolve_formal_manifest_lineage(
                governance_dir=governance_dir,
                cache_key=cache_key,
            )
            return {
                "source_version": str(manifest["source_version"]),
                "rule_version": str(manifest["rule_version"]),
                "cache_version": str(manifest.get("cache_version") or "").strip()
                or default_cache_version,
                "vendor_version": str(manifest.get("vendor_version") or "").strip()
                or default_vendor_version,
            }
        except RuntimeError:
            if fallback_lineage_loader is not None:
                return fallback_lineage_loader(report_dates[0])
    return {
        "source_version": default_source_version,
        "rule_version": default_rule_version,
        "cache_version": default_cache_version,
        "vendor_version": default_vendor_version,
    }


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


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""
