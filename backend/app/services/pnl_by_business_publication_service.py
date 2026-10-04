from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import date

import duckdb
from backend.app.config.product_category_mapping import resolve_product_category_ftp_rate_pct
from backend.app.governance.settings import Settings
from backend.app.repositories.financial_result_publication_repo import (
    FINANCIAL_PUBLICATION_API_VERSION,
    FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    FinancialPublicationIncompatible,
    FinancialPublicationInvalid,
    FinancialPublicationUnavailable,
    ResolvedFinancialPublication,
    canonical_json_bytes,
    open_financial_generation,
    read_publication_pointer,
    resolve_financial_generation,
    sha256_bytes,
)
from backend.app.repositories.pnl_precompute_state import (
    PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
)
from backend.app.repositories.pnl_repo import PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION
from backend.app.repositories.system_read_publication_repo import (
    current_system_pnl_publication,
    current_system_read_context,
    open_system_pnl_generation,
)
from backend.app.schemas.pnl import PnlByBusinessInsightsPayload
from backend.app.schemas.result_meta import ResultEnvelope
from backend.app.services.pnl_by_business_adjustment_handoff import (
    pnl_by_business_adjustment_handoff_status,
)
from backend.app.services.pnl_by_business_adjustments import (
    active_pnl_by_business_manual_adjustments_for_period,
    pnl_by_business_manual_adjustment_source_version,
)
from backend.app.services.pnl_by_business_candidate_insights import FORMAL_RULE_VERSION
from pydantic import ValidationError

PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE = "fact_pnl_by_business_page_envelope"
PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION = "pnl_by_business_page_envelope/v1"


class PnlPublishedGenerationConflictError(RuntimeError):
    """A caller-pinned generation cannot serve the requested page snapshot."""


def read_published_pnl_by_business_insights(
    settings: Settings,
    *,
    year: int,
    as_of_date: str,
    generation: str | None,
) -> dict[str, object]:
    normalized_date = _normalize_report_date(year=year, as_of_date=as_of_date)
    try:
        with _open_pnl_generation(
            settings,
            generation=generation,
        ) as (conn, resolved):
            row = conn.execute(
                f"""
                select payload_json, payload_sha256, dependency_versions_json,
                       source_version, rule_version, adjustment_version,
                       protocol_version
                from {PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE}
                where report_date = ?
                """,
                [normalized_date],
            ).fetchone()
            if row is None:
                _raise_uncovered_generation(
                    generation=generation,
                    resolved_generation=resolved.generation,
                    report_date=normalized_date,
                )
            assert row is not None
            if str(row[6] or "") != PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION:
                message = "Published pnl-by-business page protocol is incompatible."
                if generation is not None:
                    raise PnlPublishedGenerationConflictError(message)
                raise RuntimeError(message)
            dependency_versions = _json_object(row[2], label="published dependency versions")
            _require_manifest_dependencies(resolved.manifest, dependency_versions)
            try:
                _require_current_governance(settings, dependency_versions)
            except PnlPublishedGenerationConflictError:
                if generation is not None:
                    raise
                raise RuntimeError("Current pnl-by-business publication is stale.") from None
            envelope = _validated_envelope(
                payload_json=str(row[0]),
                payload_sha256=str(row[1]),
                year=int(year),
                report_date=normalized_date,
            )
            result = envelope["result"]
            assert isinstance(result, dict)
            result["generation"] = resolved.generation
            return envelope
    except (FinancialPublicationUnavailable, FinancialPublicationIncompatible) as exc:
        if generation is not None:
            raise PnlPublishedGenerationConflictError(str(exc)) from exc
        raise RuntimeError(str(exc)) from exc
    except FinancialPublicationInvalid as exc:
        raise RuntimeError(str(exc)) from exc


def inspect_current_pnl_by_business_publication(
    settings: Settings,
    *,
    year: int,
    as_of_date: str,
) -> dict[str, object] | None:
    """Read only the current generation's small page-row identity for readiness."""
    return inspect_pnl_by_business_publication(
        settings,
        year=year,
        as_of_date=as_of_date,
        generation=None,
    )


def inspect_pnl_by_business_publication(
    settings: Settings,
    *,
    year: int,
    as_of_date: str,
    generation: str | None,
) -> dict[str, object] | None:
    """Read one retained generation's declared page identity for readiness."""
    normalized_date = _normalize_report_date(year=year, as_of_date=as_of_date)
    try:
        with _open_pnl_generation(
            settings,
            generation=generation,
        ) as (conn, resolved):
            publications = _inspect_open_pnl_by_business_publications(
                settings,
                conn=conn,
                resolved=resolved,
                report_dates=(normalized_date,),
            )
            return publications[0] if publications else None
    except (
        FinancialPublicationUnavailable,
        FinancialPublicationIncompatible,
        FinancialPublicationInvalid,
        PnlPublishedGenerationConflictError,
        duckdb.Error,
        RuntimeError,
    ):
        if current_system_read_context() is not None:
            raise
        return None


def list_retained_pnl_by_business_publications(
    settings: Settings,
    *,
    year: int | None = None,
    as_of_date: str | None = None,
) -> tuple[dict[str, object], ...]:
    """List valid page identities declared by committed retained generations."""
    publication_root = _publication_root(settings)
    target_date: str | None = None
    if as_of_date is not None:
        try:
            target_date = date.fromisoformat(str(as_of_date)).isoformat()
        except ValueError:
            return ()
        if year is not None and date.fromisoformat(target_date).year != int(year):
            return ()
    pinned = current_system_pnl_publication()
    if pinned is not None:
        report_dates = _manifest_page_dates(pinned.manifest, year=year)
        if target_date is not None:
            report_dates = (target_date,) if target_date in report_dates else ()
        with open_system_pnl_generation(
            settings,
            generation=pinned.generation,
        ) as (conn, resolved):
            return _inspect_open_pnl_by_business_publications(
                settings,
                conn=conn,
                resolved=resolved,
                report_dates=report_dates,
            )
    try:
        pointer = read_publication_pointer(publication_root, require_valid=False)
    except (FinancialPublicationUnavailable, FinancialPublicationInvalid, RuntimeError):
        return ()
    if pointer is None:
        return ()
    retained = pointer.get("retained_generations")
    if not isinstance(retained, list):
        return ()

    publications: list[dict[str, object]] = []
    seen_dates: set[str] = set()
    for item in retained:
        if not isinstance(item, Mapping):
            return ()
        generation = str(item.get("generation") or "")
        try:
            with _open_pnl_generation(
                settings,
                generation=generation,
            ) as (conn, resolved):
                report_dates = _manifest_page_dates(resolved.manifest, year=year)
                if target_date is not None:
                    report_dates = (target_date,) if target_date in report_dates else ()
                report_dates = tuple(value for value in report_dates if value not in seen_dates)
                inspected = _inspect_open_pnl_by_business_publications(
                    settings,
                    conn=conn,
                    resolved=resolved,
                    report_dates=report_dates,
                )
        except (
            FinancialPublicationUnavailable,
            FinancialPublicationIncompatible,
            FinancialPublicationInvalid,
            RuntimeError,
        ):
            continue
        for publication in inspected:
            report_date = str(publication["report_date"])
            publications.append(publication)
            seen_dates.add(report_date)
        if target_date is not None and target_date in seen_dates:
            break
    return tuple(publications)


def list_retained_pnl_by_business_publication_coverage(
    settings: Settings,
    *,
    year: int | None = None,
) -> tuple[dict[str, str], ...]:
    """List committed manifest-declared page dates without opening result databases."""
    publication_root = _publication_root(settings)
    pinned = current_system_pnl_publication()
    if pinned is not None:
        return tuple(
            {
                "generation": pinned.generation,
                "manifest_sha256": pinned.manifest_sha256,
                "report_date": report_date,
            }
            for report_date in _manifest_page_dates(pinned.manifest, year=year)
        )
    try:
        pointer = read_publication_pointer(publication_root, require_valid=False)
    except (FinancialPublicationUnavailable, FinancialPublicationInvalid, RuntimeError):
        return ()
    if pointer is None:
        return ()
    retained = pointer.get("retained_generations")
    if not isinstance(retained, list):
        return ()

    coverage: list[dict[str, str]] = []
    seen_dates: set[str] = set()
    for item in retained:
        if not isinstance(item, Mapping):
            return ()
        generation = str(item.get("generation") or "")
        try:
            resolved = resolve_financial_generation(
                publication_root,
                generation=generation,
                reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
                reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
            )
        except (
            FinancialPublicationUnavailable,
            FinancialPublicationIncompatible,
            FinancialPublicationInvalid,
            RuntimeError,
        ):
            continue
        for report_date in _manifest_page_dates(resolved.manifest, year=year):
            if report_date in seen_dates:
                continue
            coverage.append(
                {
                    "generation": resolved.generation,
                    "manifest_sha256": resolved.manifest_sha256,
                    "report_date": report_date,
                }
            )
            seen_dates.add(report_date)
    return tuple(coverage)


def _inspect_open_pnl_by_business_publications(
    settings: Settings,
    *,
    conn: duckdb.DuckDBPyConnection,
    resolved: ResolvedFinancialPublication,
    report_dates: tuple[str, ...],
) -> tuple[dict[str, object], ...]:
    declared_dates = set(_manifest_page_dates(resolved.manifest, year=None))
    publications: list[dict[str, object]] = []
    for report_date in report_dates:
        if report_date not in declared_dates:
            continue
        rows = conn.execute(
            f"""
            select dependency_revision, dependency_versions_json, source_version,
                   rule_version, adjustment_version, prepared_at, protocol_version
            from {PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE}
            where report_date = ?
            """,
            [report_date],
        ).fetchall()
        if len(rows) != 1:
            continue
        row = rows[0]
        if str(row[6] or "") != PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION:
            continue
        try:
            dependency_versions = _json_object(row[1], label="published dependency versions")
            _require_manifest_dependencies(resolved.manifest, dependency_versions)
            _require_current_governance(settings, dependency_versions)
        except (PnlPublishedGenerationConflictError, RuntimeError):
            continue
        publications.append(
            {
                "generation": resolved.generation,
                "manifest_sha256": resolved.manifest_sha256,
                "report_date": report_date,
                "dependency_revision": int(row[0] or 0),
                "dependency_versions": dependency_versions,
                "source_version": str(row[2] or ""),
                "rule_version": str(row[3] or ""),
                "adjustment_version": str(row[4] or ""),
                "prepared_at": str(row[5] or "") or None,
            }
        )
    return tuple(publications)


def list_current_pnl_by_business_publication_dates(
    settings: Settings,
    *,
    year: int,
) -> tuple[str, ...]:
    """List small sealed page coverage without opening the active write database."""
    try:
        resolved = current_system_pnl_publication() or resolve_financial_generation(
            _publication_root(settings),
            generation=None,
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )
        return tuple(
            report_date
            for report_date in _manifest_page_dates(resolved.manifest, year=int(year))
            if inspect_pnl_by_business_publication(
                settings,
                year=int(year),
                as_of_date=report_date,
                generation=resolved.generation,
            )
            is not None
        )
    except (
        FinancialPublicationUnavailable,
        FinancialPublicationIncompatible,
        FinancialPublicationInvalid,
    ):
        return ()


def _manifest_page_dates(
    manifest: Mapping[str, object],
    *,
    year: int | None,
) -> tuple[str, ...]:
    sealed = manifest.get("sealed_payload")
    coverage = sealed.get("coverage_dates") if isinstance(sealed, Mapping) else None
    raw_dates = coverage.get("pnl_by_business_page") if isinstance(coverage, Mapping) else None
    raw_tables = sealed.get("tables") if isinstance(sealed, Mapping) else None
    if not isinstance(raw_dates, list) or not isinstance(raw_tables, list):
        return ()
    page_table = next(
        (
            item
            for item in raw_tables
            if isinstance(item, Mapping)
            and item.get("name") == PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE
            and item.get("date_column") == "report_date"
        ),
        None,
    )
    if not isinstance(page_table, Mapping):
        return ()
    required_dates = page_table.get("required_dates")
    coverage_counts = page_table.get("coverage_row_counts")
    if not isinstance(required_dates, list) or not isinstance(coverage_counts, Mapping):
        return ()
    required = {str(value) for value in required_dates}
    normalized: list[str] = []
    for value in raw_dates:
        try:
            report_date = date.fromisoformat(str(value)).isoformat()
        except ValueError:
            return ()
        row_count = coverage_counts.get(report_date)
        if (
            (year is not None and date.fromisoformat(report_date).year != int(year))
            or report_date not in required
            or isinstance(row_count, bool)
            or not isinstance(row_count, int)
            or row_count < 1
        ):
            continue
        normalized.append(report_date)
    return tuple(sorted(set(normalized)))


def require_current_pnl_by_business_governance(
    settings: Settings,
    dependency_versions: Mapping[str, object],
) -> None:
    """Reject a sealed page whose code, FTP, or approved adjustments have changed."""
    _require_current_governance(settings, dependency_versions)


def _validated_envelope(
    *,
    payload_json: str,
    payload_sha256: str,
    year: int,
    report_date: str,
) -> dict[str, object]:
    payload_bytes = payload_json.encode("utf-8")
    if sha256_bytes(payload_bytes) != payload_sha256:
        raise RuntimeError("Published pnl-by-business page payload digest does not match.")
    envelope = _json_object(payload_json, label="published pnl-by-business envelope")
    if canonical_json_bytes(envelope) != payload_bytes:
        raise RuntimeError("Published pnl-by-business page payload is not canonical JSON.")
    try:
        validated = ResultEnvelope.model_validate(envelope).model_dump(mode="json")
    except ValidationError as exc:
        raise RuntimeError("Published pnl-by-business page envelope is invalid.") from exc
    result = validated.get("result")
    meta = validated.get("result_meta")
    if not isinstance(result, dict) or not isinstance(meta, dict):
        raise RuntimeError("Published pnl-by-business page envelope shape is invalid.")
    if (
        int(result.get("year") or 0) != year
        or str(result.get("as_of_date") or "") != report_date
        or str(meta.get("resolved_report_date") or "") != report_date
        or str(meta.get("result_kind") or "") != "pnl.by_business_insights"
        or str(meta.get("basis") or "") != "formal"
        or meta.get("formal_use_allowed") is not True
    ):
        raise RuntimeError("Published pnl-by-business page identity or formal admission is invalid.")
    try:
        PnlByBusinessInsightsPayload.model_validate(result)
    except ValidationError as exc:
        raise RuntimeError("Published pnl-by-business insights payload is invalid.") from exc
    return validated


def _require_manifest_dependencies(
    manifest: Mapping[str, object],
    expected: Mapping[str, object],
) -> None:
    sealed = manifest.get("sealed_payload")
    dependencies = sealed.get("dependency_versions") if isinstance(sealed, Mapping) else None
    if not isinstance(dependencies, Mapping):
        raise RuntimeError("Published financial manifest has no dependency versions.")
    for key, value in expected.items():
        if str(dependencies.get(key) or "") != str(value or ""):
            raise RuntimeError(f"Published dependency version mismatch for {key}.")


def _require_current_governance(
    settings: Settings,
    dependency_versions: Mapping[str, object],
) -> None:
    expected_constants = {
        "pnl_by_business_page.protocol": PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION,
        "pnl_by_business_page.rules": FORMAL_RULE_VERSION,
    }
    for key, expected in expected_constants.items():
        if str(dependency_versions.get(key) or "") != expected:
            raise PnlPublishedGenerationConflictError(
                f"Published pnl-by-business dependency {key} is no longer compatible."
            )
    prefixes = sorted(
        {
            key.rsplit(".", 1)[0]
            for key in dependency_versions
            if key.startswith("pnl_by_business.") and key.endswith(".requested_report_date")
        }
    )
    if not prefixes:
        raise RuntimeError("Published pnl-by-business dependency dates are missing.")
    dependency_dates = tuple(
        str(dependency_versions.get(f"{prefix}.requested_report_date") or "")
        for prefix in prefixes
    )
    handoff = pnl_by_business_adjustment_handoff_status(
        settings.governance_path,
        dependency_dates=dependency_dates,
    )
    if handoff["pending"]:
        raise PnlPublishedGenerationConflictError(
            "Published pnl-by-business adjustments have a pending precompute handoff."
        )
    for prefix in prefixes:
        requested_date = str(dependency_versions.get(f"{prefix}.requested_report_date") or "")
        dependency_year = date.fromisoformat(requested_date).year
        if str(dependency_versions.get(f"{prefix}.rule_version") or "") != PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION:
            raise PnlPublishedGenerationConflictError(
                f"Published pnl-by-business rule version is stale for {prefix}."
            )
        if (
            str(dependency_versions.get(f"{prefix}.protocol_version") or "")
            != PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION
        ):
            raise PnlPublishedGenerationConflictError(
                f"Published pnl-by-business precompute protocol is stale for {prefix}."
            )
        current_ftp = resolve_product_category_ftp_rate_pct(
            date(dependency_year, 12, 31),
            settings.ftp_rate_pct,
        )
        if str(dependency_versions.get(f"{prefix}.ftp_rate_pct") or "") != str(current_ftp):
            raise PnlPublishedGenerationConflictError(
                f"Published pnl-by-business FTP version is stale for {prefix}."
            )
        adjustments = active_pnl_by_business_manual_adjustments_for_period(
            settings.governance_path,
            year=dependency_year,
            period_end=requested_date,
        )
        current_adjustment_version = pnl_by_business_manual_adjustment_source_version(adjustments)
        if (
            str(dependency_versions.get(f"{prefix}.adjustment_version") or "")
            != current_adjustment_version
        ):
            raise PnlPublishedGenerationConflictError(
                f"Published pnl-by-business adjustments are stale for {prefix}."
            )


def _raise_uncovered_generation(
    *, generation: str | None, resolved_generation: str, report_date: str
) -> None:
    message = (
        f"Financial publication {resolved_generation} does not cover pnl-by-business "
        f"report_date={report_date}."
    )
    if generation is not None:
        raise PnlPublishedGenerationConflictError(message)
    raise RuntimeError(message)


def _normalize_report_date(*, year: int, as_of_date: str) -> str:
    try:
        parsed = date.fromisoformat(str(as_of_date))
    except ValueError as exc:
        raise ValueError("as_of_date must use YYYY-MM-DD format.") from exc
    if parsed.year != int(year):
        raise ValueError(f"as_of_date={parsed.isoformat()} is outside requested year={int(year)}.")
    return parsed.isoformat()


def _publication_root(settings: Settings) -> str:
    root = str(getattr(settings, "financial_publication_root", "") or "").strip()
    if not root:
        raise RuntimeError("Financial publication root is not configured.")
    return root


@contextmanager
def _open_pnl_generation(
    settings: Settings,
    *,
    generation: str | None,
):
    if current_system_read_context() is not None:
        with open_system_pnl_generation(settings, generation=generation) as opened:
            yield opened
        return
    with open_financial_generation(
        _publication_root(settings),
        generation=generation,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    ) as opened:
        yield opened


def _json_object(value: object, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(str(value))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} is invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} must be a JSON object.")
    return payload
