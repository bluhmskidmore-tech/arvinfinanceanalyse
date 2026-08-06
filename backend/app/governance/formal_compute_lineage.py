from __future__ import annotations

from collections.abc import Callable
from datetime import date

from backend.app.repositories.governance_repo import (
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)


class FormalLineageUnavailableError(RuntimeError):
    """Raised when no canonical formal lineage record exists."""


class FormalLineageMalformedError(RuntimeError):
    """Raised when a canonical formal lineage record is incomplete."""


def resolve_formal_manifest_lineage(
    *,
    governance_dir: str,
    cache_key: str,
    sql_dsn: str = "",
    backend_mode: str = "",
    report_date: str | None = None,
    allow_safe_fallback: bool = False,
) -> dict[str, object]:
    repo = _governance_repo(
        governance_dir=governance_dir,
        sql_dsn=sql_dsn,
        backend_mode=backend_mode,
    )
    requested_report_date = str(report_date or "").strip()
    latest = repo.read_latest_manifest(
        cache_key,
        report_date=requested_report_date or None,
    )
    if latest is None and requested_report_date and allow_safe_fallback:
        requested_date = date.fromisoformat(requested_report_date)
        dated_candidates: list[tuple[date, int, dict[str, object]]] = []
        undated_candidates: list[tuple[int, dict[str, object]]] = []
        for index, row in enumerate(repo.read_all(CACHE_MANIFEST_STREAM)):
            if str(row.get("cache_key") or "").strip() != cache_key:
                continue
            candidate_report_date = str(row.get("report_date") or "").strip()
            if not candidate_report_date:
                undated_candidates.append((index, row))
                continue
            try:
                candidate_date = date.fromisoformat(candidate_report_date)
            except ValueError:
                continue
            if candidate_date <= requested_date:
                dated_candidates.append((candidate_date, index, row))

        fallback_date: str | None = None
        if dated_candidates:
            candidate_date, _, selected = max(
                dated_candidates,
                key=lambda candidate: (candidate[0], candidate[1]),
            )
            latest = dict(selected)
            fallback_date = candidate_date.isoformat()
        elif undated_candidates:
            latest = dict(undated_candidates[-1][1])

        if latest is not None:
            latest["_lineage_fallback_mode"] = "latest_snapshot"
            latest["_lineage_fallback_date"] = fallback_date
    if latest is None:
        date_context = (
            f", report_date={requested_report_date}"
            if requested_report_date
            else ""
        )
        raise FormalLineageUnavailableError(
            f"Canonical formal lineage unavailable for cache_key={cache_key}{date_context}."
        )
    required = ("source_version", "vendor_version", "rule_version")
    missing = [key for key in required if not str(latest.get(key) or "").strip()]
    if missing:
        joined = ", ".join(missing)
        raise FormalLineageMalformedError(
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
    return repo.read_latest_completed_run(
        cache_key,
        job_name=job_name,
        report_date=report_date,
        require_source_version=True,
    )


def resolve_formal_manifest_lineage_with_completed_build(
    *,
    governance_dir: str,
    cache_key: str,
    job_name: str,
    report_date: str | None,
    sql_dsn: str = "",
    backend_mode: str = "",
) -> dict[str, object]:
    if not report_date:
        return resolve_formal_manifest_lineage(
            governance_dir=governance_dir,
            cache_key=cache_key,
            sql_dsn=sql_dsn,
            backend_mode=backend_mode,
        )

    build_lineage = resolve_completed_formal_build_lineage(
        governance_dir=governance_dir,
        cache_key=cache_key,
        job_name=job_name,
        report_date=report_date,
        sql_dsn=sql_dsn,
        backend_mode=backend_mode,
    )
    if build_lineage is not None:
        try:
            manifest_lineage = resolve_formal_manifest_lineage(
                governance_dir=governance_dir,
                cache_key=cache_key,
                sql_dsn=sql_dsn,
                backend_mode=backend_mode,
                report_date=report_date,
            )
        except FormalLineageUnavailableError:
            return build_lineage
        return {
            **manifest_lineage,
            **{
                key: value
                for key, value in build_lineage.items()
                if str(value or "").strip()
            },
        }

    try:
        return resolve_formal_manifest_lineage(
            governance_dir=governance_dir,
            cache_key=cache_key,
            sql_dsn=sql_dsn,
            backend_mode=backend_mode,
            report_date=report_date,
        )
    except FormalLineageUnavailableError:
        return resolve_formal_manifest_lineage(
            governance_dir=governance_dir,
            cache_key=cache_key,
            sql_dsn=sql_dsn,
            backend_mode=backend_mode,
            report_date=report_date,
            allow_safe_fallback=True,
        )


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
        require_source_version=True,
    ) or {}
    normalized_row_sources = _normalized_non_empty_values(row_source_versions)
    if has_rows and not latest_build:
        raise RuntimeError(
            "Canonical completed formal build terminal unavailable "
            f"for cache_key={cache_key}, job_name={job_name}, report_date={report_date}; "
            "refusing to certify orphan formal fact rows."
        )
    if not has_rows and not latest_build:
        return _build_lineage_values(
            source_version=default_source_version,
            rule_version=default_rule_version,
            cache_version=default_cache_version,
            vendor_version=default_vendor_version,
            default_source_version=default_source_version,
            default_rule_version=default_rule_version,
            default_cache_version=default_cache_version,
            default_vendor_version=default_vendor_version,
        )
    latest_manifest = repo.read_latest_manifest(cache_key) or {}
    return _build_lineage_values(
        source_version=_first_non_empty(
            str(latest_build.get("source_version") or "").strip(),
            "__".join(normalized_row_sources),
            default_source_version,
        ),
        rule_version=_first_non_empty(
            str(latest_build.get("rule_version") or "").strip(),
            str(latest_manifest.get("rule_version") or "").strip(),
            default_rule_version,
        ),
        cache_version=_first_non_empty(
            str(latest_build.get("cache_version") or "").strip(),
            str(latest_manifest.get("cache_version") or "").strip(),
            default_cache_version,
        ),
        vendor_version=_first_non_empty(
            str(latest_build.get("vendor_version") or "").strip(),
            str(latest_manifest.get("vendor_version") or "").strip(),
            default_vendor_version,
        ),
        default_source_version=default_source_version,
        default_rule_version=default_rule_version,
        default_cache_version=default_cache_version,
        default_vendor_version=default_vendor_version,
    )


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
            return _build_lineage_values(
                source_version=manifest.get("source_version"),
                rule_version=manifest.get("rule_version"),
                cache_version=manifest.get("cache_version"),
                vendor_version=manifest.get("vendor_version"),
                default_source_version=default_source_version,
                default_rule_version=default_rule_version,
                default_cache_version=default_cache_version,
                default_vendor_version=default_vendor_version,
            )
        except RuntimeError:
            if fallback_lineage_loader is not None:
                return _build_lineage_values(
                    **fallback_lineage_loader(report_dates[0]),
                    default_source_version=default_source_version,
                    default_rule_version=default_rule_version,
                    default_cache_version=default_cache_version,
                    default_vendor_version=default_vendor_version,
                )
    return _build_lineage_values(
        source_version=default_source_version,
        rule_version=default_rule_version,
        cache_version=default_cache_version,
        vendor_version=default_vendor_version,
        default_source_version=default_source_version,
        default_rule_version=default_rule_version,
        default_cache_version=default_cache_version,
        default_vendor_version=default_vendor_version,
    )


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


def _normalized_non_empty_values(values: list[str] | tuple[str, ...]) -> list[str]:
    return sorted(
        {
            str(value or "").strip()
            for value in values
            if str(value or "").strip()
        }
    )


def _build_lineage_values(
    *,
    source_version: object | None = None,
    rule_version: object | None = None,
    cache_version: object | None = None,
    vendor_version: object | None = None,
    default_source_version: str,
    default_rule_version: str,
    default_cache_version: str,
    default_vendor_version: str,
) -> dict[str, str]:
    return {
        "source_version": _first_non_empty(str(source_version or "").strip(), default_source_version),
        "rule_version": _first_non_empty(str(rule_version or "").strip(), default_rule_version),
        "cache_version": _first_non_empty(str(cache_version or "").strip(), default_cache_version),
        "vendor_version": _first_non_empty(str(vendor_version or "").strip(), default_vendor_version),
    }
