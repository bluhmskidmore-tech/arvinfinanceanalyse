from __future__ import annotations

import os
import re
import threading
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import Protocol, overload

import duckdb
from anyio import to_thread
from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    active_read_scope,
    duckdb_read_scope,
)
from backend.app.repositories.financial_result_publication_repo import (
    FINANCIAL_PUBLICATION_API_VERSION,
    FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    FinancialPublicationError,
    FinancialPublicationInvalid,
    FinancialPublicationUnavailable,
    ResolvedFinancialPublication,
    generation_invalidation_path,
    open_financial_generation,
    resolve_financial_generation,
    revalidate_financial_generation,
    validate_sealed_financial_generation,
)
from backend.app.services.pretrade_qualification import (
    normalize_pretrade_qualification,
    unavailable_pretrade_qualification,
)

SYSTEM_READ_BUNDLE_KEY = "system_read_bundle"
SYSTEM_READ_BUNDLE_PROTOCOL_VERSION = 2
SYSTEM_READ_API_VERSION = "system-read-api/v1"
SYSTEM_READ_SCHEMA_VERSION = "system-read-schema/v1"
SYSTEM_READ_GENERATION_HEADER = "X-MOSS-Read-Generation"
SYSTEM_READ_PUBLICATION_DIRECTORY = "system_read_publications"
SYSTEM_READ_GOVERNANCE_STREAMS = frozenset({"cache_build_run", "cache_manifest"})
SYSTEM_READ_BUNDLE_FIELDS = frozenset(
    {
        "protocol_version",
        "full_database",
        "active_database_identity",
        "governance_base_identity",
        "governance_streams",
        "pnl_generation",
        "pnl_manifest_sha256",
        "data_update_run_id",
        "global_run_id",
        "workflow",
        "report_date",
    }
)
SYSTEM_READ_EXTENDED_BUNDLE_FIELDS = SYSTEM_READ_BUNDLE_FIELDS | frozenset(
    {
        "writer_run_id",
        "writer_receipt_sha256",
        "terminal_references",
        "required_table_coverage",
    }
)
SYSTEM_READ_V2_BUNDLE_FIELDS = SYSTEM_READ_EXTENDED_BUNDLE_FIELDS | frozenset(
    {"pretrade_availability"}
)
_SYSTEM_READ_GENERATION_PATTERN = re.compile(r"^system-read-(\d{4}-\d{2}-\d{2})-[0-9a-f]{20}$")


class SystemReadSettings(Protocol):
    system_read_publication_enabled: bool
    governance_path: Path
    financial_publication_root: str
    duckdb_path: str


@dataclass(frozen=True)
class SystemReadContext:
    publication: ResolvedFinancialPublication
    pnl_publication: ResolvedFinancialPublication
    active_database_identity: str
    governance_base_identity: str
    governance_streams: Mapping[str, tuple[Mapping[str, object], ...]]
    coverage_dates: Mapping[str, tuple[str, ...]]
    data_update_run_id: str | None
    global_run_id: str | None
    writer_run_id: str
    writer_receipt_sha256: str | None
    workflow: str
    report_date: str
    pretrade_availability: Mapping[str, object]

    @property
    def generation(self) -> str:
        return self.publication.generation


_SYSTEM_READ_CONTEXT: ContextVar[SystemReadContext | None] = ContextVar(
    "system_read_publication_context",
    default=None,
)
_SYSTEM_CONTEXT_CACHE: dict[tuple[object, ...], SystemReadContext] = {}
_SYSTEM_CONTEXT_CACHE_LOCK = threading.Lock()
_SYSTEM_CONTEXT_CACHE_MAX_ENTRIES = 16
_SYSTEM_READ_CACHE_NAMESPACE = "moss-system-read-cache"


def system_read_publication_root(settings: SystemReadSettings) -> Path:
    return Path(settings.governance_path).resolve() / SYSTEM_READ_PUBLICATION_DIRECTORY


def current_system_read_context() -> SystemReadContext | None:
    return _SYSTEM_READ_CONTEXT.get()


def current_system_read_publication() -> ResolvedFinancialPublication | None:
    context = current_system_read_context()
    return context.publication if context is not None else None


def current_system_pnl_publication() -> ResolvedFinancialPublication | None:
    context = current_system_read_context()
    return context.pnl_publication if context is not None else None


def raise_if_system_read_failure(exc: BaseException) -> None:
    """Keep required online-read failures from degrading into empty business data."""

    if isinstance(exc, DuckDBReadSelectionError) or (
        current_system_read_context() is not None
        and isinstance(exc, FinancialPublicationError)
    ):
        raise exc


def system_read_cache_key(key: str) -> str:
    context = current_system_read_context()
    if context is None:
        return key
    return "::".join(
        (
            _SYSTEM_READ_CACHE_NAMESPACE,
            context.generation,
            context.publication.manifest_sha256,
            _path_identity(context.publication.database_path),
            key,
        )
    )


def system_read_cache_identity(key: object) -> object:
    """Namespace a process-local cache key by the pinned full-system generation."""

    context = current_system_read_context()
    if context is None:
        return key
    return (
        _SYSTEM_READ_CACHE_NAMESPACE,
        context.generation,
        context.publication.manifest_sha256,
        _path_identity(context.publication.database_path),
        key,
    )


def system_read_original_cache_key(key: object) -> object:
    """Restore the caller-visible key before evaluating cache predicates."""

    if (
        isinstance(key, tuple)
        and len(key) == 5
        and key[0] == _SYSTEM_READ_CACHE_NAMESPACE
    ):
        return key[4]
    return key


@contextmanager
def open_system_pnl_generation(
    settings: SystemReadSettings,
    *,
    generation: str | None,
) -> Iterator[tuple[duckdb.DuckDBPyConnection, ResolvedFinancialPublication]]:
    """Open the PnL generation referenced by the current full-system pin."""

    context = current_system_read_context()
    if context is None:
        with open_financial_generation(
            settings.financial_publication_root,
            generation=generation,
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        ) as opened:
            yield opened
        return

    resolved = context.pnl_publication
    requested_generation = str(generation or "").strip()
    if requested_generation and requested_generation != resolved.generation:
        raise FinancialPublicationUnavailable(
            "Requested PnL generation does not match the pinned system publication."
        )
    conn = duckdb.connect(str(resolved.database_path), read_only=True)
    try:
        invalidation_path = generation_invalidation_path(
            settings.financial_publication_root,
            resolved.generation,
        )
        if invalidation_path.exists():
            raise FinancialPublicationUnavailable(
                f"Pinned PnL publication {resolved.generation} was invalidated before query execution."
            )
        yield conn, resolved
    finally:
        conn.close()


def frozen_system_governance_rows(
    governance_base_path: str | os.PathLike[str],
    stream_name: str,
) -> list[dict[str, object]] | None:
    """Return an isolated frozen-stream copy, or ``None`` for a live stream."""

    context = current_system_read_context()
    if (
        context is None
        or _path_identity(governance_base_path) != _path_identity(context.governance_base_identity)
        or stream_name not in SYSTEM_READ_GOVERNANCE_STREAMS
    ):
        return None
    rows = context.governance_streams.get(stream_name)
    if rows is None:
        raise FinancialPublicationInvalid("Pinned system read governance stream is unavailable.")
    return [_deep_thaw(row) for row in rows]


def resolve_system_read_publication(
    settings: SystemReadSettings,
    generation: str | None = None,
) -> ResolvedFinancialPublication:
    return _resolve_system_read_context(settings, generation=generation).publication


@contextmanager
def system_read_scope(
    settings: SystemReadSettings,
    generation: str | None = None,
) -> Iterator[ResolvedFinancialPublication | None]:
    """Pin one validated system generation for the whole request/task scope."""

    if not bool(getattr(settings, "system_read_publication_enabled", False)):
        yield None
        return

    context = _resolve_system_read_context(settings, generation=generation)
    with _system_read_context_scope(settings, context) as publication:
        yield publication


@asynccontextmanager
async def async_system_read_scope(
    settings: SystemReadSettings,
    generation: str | None = None,
) -> AsyncIterator[ResolvedFinancialPublication | None]:
    """Resolve artifacts off the event loop, then pin in the caller's task."""

    if not bool(getattr(settings, "system_read_publication_enabled", False)):
        yield None
        return

    context = await to_thread.run_sync(
        partial(_resolve_system_read_context, settings, generation=generation)
    )
    # ContextVar changes in a worker do not propagate back to the request task.
    with _system_read_context_scope(settings, context) as publication:
        yield publication


@contextmanager
def _system_read_context_scope(
    settings: SystemReadSettings,
    context: SystemReadContext,
) -> Iterator[ResolvedFinancialPublication]:
    selection = DuckDBReadSelection(
        active_path=str(settings.duckdb_path),
        snapshot_path=context.publication.database_path,
        generation=context.publication.generation,
    )
    token = _SYSTEM_READ_CONTEXT.set(context)
    try:
        with duckdb_read_scope(selection, required_online=True):
            yield context.publication
    finally:
        _SYSTEM_READ_CONTEXT.reset(token)


@contextmanager
def active_system_read_scope() -> Iterator[None]:
    """Clear both system and DuckDB read pins for an active task/CLI block."""

    token = _SYSTEM_READ_CONTEXT.set(None)
    try:
        with active_read_scope():
            yield None
    finally:
        _SYSTEM_READ_CONTEXT.reset(token)


def _resolve_system_read_context(
    settings: SystemReadSettings,
    *,
    generation: str | None,
) -> SystemReadContext:
    if not settings.system_read_publication_enabled:
        raise FinancialPublicationUnavailable("System read publication is disabled.")
    requested_generation = None if generation is None else str(generation).strip()
    if generation is not None and not requested_generation:
        raise FinancialPublicationInvalid("System read generation header must not be empty.")

    publication = resolve_financial_generation(
        system_read_publication_root(settings),
        generation=requested_generation,
        reader_api_version=SYSTEM_READ_API_VERSION,
        reader_schema_version=SYSTEM_READ_SCHEMA_VERSION,
    )
    generation_match = _SYSTEM_READ_GENERATION_PATTERN.fullmatch(publication.generation)
    if generation_match is None:
        raise FinancialPublicationInvalid("System read generation format is invalid.")
    sealed_payload = publication.manifest.get("sealed_payload")
    if not isinstance(sealed_payload, Mapping):
        raise FinancialPublicationInvalid("System read sealed payload is missing.")
    bundle = sealed_payload.get(SYSTEM_READ_BUNDLE_KEY)
    if not isinstance(bundle, Mapping):
        raise FinancialPublicationInvalid("System read bundle profile is missing.")
    bundle_fields = set(bundle)
    if bundle_fields not in {
        SYSTEM_READ_BUNDLE_FIELDS,
        SYSTEM_READ_EXTENDED_BUNDLE_FIELDS,
        SYSTEM_READ_V2_BUNDLE_FIELDS,
    }:
        raise FinancialPublicationInvalid("System read bundle fields are invalid.")
    bundle_protocol_version = bundle.get("protocol_version")
    v1_bundle = bundle_fields in {
        SYSTEM_READ_BUNDLE_FIELDS,
        SYSTEM_READ_EXTENDED_BUNDLE_FIELDS,
    }
    if (v1_bundle and bundle_protocol_version != 1) or (
        not v1_bundle and bundle_protocol_version != SYSTEM_READ_BUNDLE_PROTOCOL_VERSION
    ):
        raise FinancialPublicationInvalid("System read bundle protocol version is unsupported.")
    extended_bundle = bundle_fields != SYSTEM_READ_BUNDLE_FIELDS
    if bundle.get("full_database") is not True:
        raise FinancialPublicationInvalid("System read bundle is not a full-database snapshot.")

    active_database_identity = _required_string(bundle, "active_database_identity")
    expected_active_database_identity = str(Path(settings.duckdb_path).resolve())
    if (
        active_database_identity != str(Path(active_database_identity).resolve())
        or _path_identity(active_database_identity) != _path_identity(expected_active_database_identity)
    ):
        raise FinancialPublicationInvalid("System read active database identity does not match settings.")

    governance_base_identity = _required_string(bundle, "governance_base_identity")
    expected_governance_identity = str(Path(settings.governance_path).resolve())
    if (
        governance_base_identity != str(Path(governance_base_identity).resolve())
        or _path_identity(governance_base_identity) != _path_identity(expected_governance_identity)
    ):
        raise FinancialPublicationInvalid("System read governance identity does not match settings.")

    pnl_generation = _required_string(bundle, "pnl_generation")
    pnl_manifest_sha256 = _required_string(bundle, "pnl_manifest_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", pnl_manifest_sha256):
        raise FinancialPublicationInvalid("System read PnL manifest digest is invalid.")
    financial_publication_root = str(settings.financial_publication_root or "").strip()
    if not financial_publication_root:
        raise FinancialPublicationUnavailable("Financial publication root is not configured.")
    pnl_publication = validate_sealed_financial_generation(
        financial_publication_root,
        generation=pnl_generation,
        expected_manifest_sha256=pnl_manifest_sha256,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    # PnL validation may wait after the system selection was authorized. Keep the
    # original generation/digest, but require it to remain valid and retained.
    publication = revalidate_financial_generation(
        system_read_publication_root(settings),
        generation=publication.generation,
        expected_manifest_sha256=publication.manifest_sha256,
        reader_api_version=SYSTEM_READ_API_VERSION,
        reader_schema_version=SYSTEM_READ_SCHEMA_VERSION,
        require_current_validity=requested_generation is None,
    )

    cache_key = (
        publication.manifest_sha256,
        _file_identity(publication.database_path),
        pnl_publication.manifest_sha256,
        _file_identity(pnl_publication.database_path),
        _path_identity(settings.duckdb_path),
        _path_identity(settings.governance_path),
        _path_identity(settings.financial_publication_root),
    )
    with _SYSTEM_CONTEXT_CACHE_LOCK:
        cached = _SYSTEM_CONTEXT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    governance_streams_value = bundle.get("governance_streams")
    if not isinstance(governance_streams_value, Mapping) or not governance_streams_value:
        raise FinancialPublicationInvalid("System read governance streams are empty or invalid.")
    if set(governance_streams_value) != SYSTEM_READ_GOVERNANCE_STREAMS:
        raise FinancialPublicationInvalid("System read governance stream allowlist is invalid.")
    governance_streams: dict[str, tuple[Mapping[str, object], ...]] = {}
    for raw_name, raw_rows in governance_streams_value.items():
        stream_name = str(raw_name or "").strip()
        if not stream_name or not isinstance(raw_rows, list) or not raw_rows:
            raise FinancialPublicationInvalid("System read governance stream is empty or invalid.")
        frozen_rows: list[Mapping[str, object]] = []
        for row in raw_rows:
            if not isinstance(row, Mapping) or not row:
                raise FinancialPublicationInvalid("System read governance row is empty or invalid.")
            frozen_rows.append(_deep_freeze(row))
        governance_streams[stream_name] = tuple(frozen_rows)

    coverage_dates_value = sealed_payload.get("coverage_dates")
    if not isinstance(coverage_dates_value, Mapping):
        raise FinancialPublicationInvalid("System read coverage dates are missing or invalid.")
    coverage_dates: dict[str, tuple[str, ...]] = {}
    for raw_name, raw_dates in coverage_dates_value.items():
        coverage_name = str(raw_name or "").strip()
        if (
            not coverage_name
            or not isinstance(raw_dates, Sequence)
            or isinstance(raw_dates, (str, bytes))
        ):
            raise FinancialPublicationInvalid("System read coverage date entry is invalid.")
        normalized_dates = tuple(str(value or "").strip() for value in raw_dates)
        if any(not value for value in normalized_dates):
            raise FinancialPublicationInvalid("System read coverage date is empty or invalid.")
        coverage_dates[coverage_name] = normalized_dates

    report_date = _required_string(bundle, "report_date")
    if report_date != generation_match.group(1):
        raise FinancialPublicationInvalid("System read generation does not match its report date.")

    workflow = _required_string(bundle, "workflow")
    if extended_bundle:
        writer_run_id = _required_string(bundle, "writer_run_id")
        writer_receipt_sha256 = _required_string(bundle, "writer_receipt_sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", writer_receipt_sha256):
            raise FinancialPublicationInvalid("System read writer receipt digest is invalid.")
        data_update_run_id = _optional_string(bundle, "data_update_run_id")
        global_run_id = _optional_string(bundle, "global_run_id")
        if workflow == "core_financial":
            if data_update_run_id is None or global_run_id is None:
                raise FinancialPublicationInvalid(
                    "Core financial system read bundle requires both parent run identities."
                )
        elif workflow == "balance_daily":
            if data_update_run_id != writer_run_id or global_run_id is not None:
                raise FinancialPublicationInvalid(
                    "Balance daily system read bundle has invalid writer identity."
                )
        elif workflow == "market_daily":
            if data_update_run_id is not None or global_run_id is not None:
                raise FinancialPublicationInvalid(
                    "Market daily system read bundle must use standalone writer identity."
                )
        else:
            raise FinancialPublicationInvalid("System read preserved workflow is unsupported.")
        _validate_extended_bundle_evidence(bundle)
    else:
        data_update_run_id = _required_string(bundle, "data_update_run_id")
        global_run_id = _required_string(bundle, "global_run_id")
        writer_run_id = data_update_run_id
        writer_receipt_sha256 = None

    if bundle_fields == SYSTEM_READ_V2_BUNDLE_FIELDS:
        pretrade_availability = _validate_pretrade_availability(
            bundle.get("pretrade_availability")
        )
    else:
        pretrade_availability = unavailable_pretrade_qualification(
            "legacy_system_read_bundle_has_no_pretrade_qualification"
        )

    context = SystemReadContext(
        publication=publication,
        pnl_publication=pnl_publication,
        active_database_identity=active_database_identity,
        governance_base_identity=governance_base_identity,
        governance_streams=MappingProxyType(governance_streams),
        coverage_dates=MappingProxyType(coverage_dates),
        data_update_run_id=data_update_run_id,
        global_run_id=global_run_id,
        writer_run_id=writer_run_id,
        writer_receipt_sha256=writer_receipt_sha256,
        workflow=workflow,
        report_date=report_date,
        pretrade_availability=_deep_freeze(pretrade_availability),
    )
    with _SYSTEM_CONTEXT_CACHE_LOCK:
        if len(_SYSTEM_CONTEXT_CACHE) >= _SYSTEM_CONTEXT_CACHE_MAX_ENTRIES:
            _SYSTEM_CONTEXT_CACHE.clear()
        _SYSTEM_CONTEXT_CACHE[cache_key] = context
    return context


def _required_string(bundle: Mapping[str, object], field_name: str) -> str:
    value = bundle.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise FinancialPublicationInvalid(
            f"System read bundle field {field_name!r} must be a non-empty string."
        )
    return value.strip()


def _optional_string(bundle: Mapping[str, object], field_name: str) -> str | None:
    value = bundle.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise FinancialPublicationInvalid(
            f"System read bundle field {field_name!r} must be null or a non-empty string."
        )
    return value.strip()


def _validate_extended_bundle_evidence(bundle: Mapping[str, object]) -> None:
    terminal_references = bundle.get("terminal_references")
    table_coverage = bundle.get("required_table_coverage")
    if (
        not isinstance(terminal_references, list)
        or not terminal_references
        or not isinstance(table_coverage, list)
        or not table_coverage
    ):
        raise FinancialPublicationInvalid(
            "System read extended bundle has no explicit terminal or table coverage evidence."
        )
    terminal_fields = {"run_id", "cache_key", "report_date"}
    table_fields = {"table_name", "date_column", "coverage_date", "minimum_rows"}
    terminal_keys: set[str] = set()
    for item in terminal_references:
        if not isinstance(item, Mapping) or set(item) != terminal_fields:
            raise FinancialPublicationInvalid("System read terminal reference is invalid.")
        _required_string(item, "run_id")
        cache_key = _required_string(item, "cache_key")
        _required_string(item, "report_date")
        if cache_key in terminal_keys:
            raise FinancialPublicationInvalid("System read terminal reference is duplicated.")
        terminal_keys.add(cache_key)
    table_names: set[str] = set()
    for item in table_coverage:
        if not isinstance(item, Mapping) or set(item) != table_fields:
            raise FinancialPublicationInvalid("System read table coverage entry is invalid.")
        table_name = _required_string(item, "table_name")
        _required_string(item, "date_column")
        _required_string(item, "coverage_date")
        minimum_rows = item.get("minimum_rows")
        if (
            not isinstance(minimum_rows, int)
            or isinstance(minimum_rows, bool)
            or minimum_rows < 1
            or table_name in table_names
        ):
            raise FinancialPublicationInvalid("System read table coverage entry is invalid.")
        table_names.add(table_name)


def _validate_pretrade_availability(value: object) -> dict[str, object]:
    normalized = normalize_pretrade_qualification(value)
    if not isinstance(value, Mapping) or normalized != dict(value):
        raise FinancialPublicationInvalid(
            "System read pretrade availability is invalid or non-normalized."
        )
    return normalized


def _path_identity(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def _file_identity(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return (int(stat.st_dev), int(stat.st_ino), int(stat.st_size), int(stat.st_mtime_ns))


@overload
def _deep_freeze(value: Mapping[str, object]) -> Mapping[str, object]: ...


@overload
def _deep_freeze(value: object) -> object: ...


def _deep_freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_deep_freeze(item) for item in value)
    return value


@overload
def _deep_thaw(value: Mapping[str, object]) -> dict[str, object]: ...


@overload
def _deep_thaw(value: object) -> object: ...


def _deep_thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _deep_thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_deep_thaw(item) for item in value]
    return value
