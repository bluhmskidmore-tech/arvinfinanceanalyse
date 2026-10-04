"""V1 PnL envelope cache helpers, separate from service orchestration."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelectionError,
    resolve_effective_read_path,
)
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    SOURCE_MANIFEST_STREAM,
    GovernanceRepository,
    _jsonl_file_cache_key,
)
from backend.app.repositories.object_store_repo import resolve_local_archive_path
from backend.app.services.pnl_source_service import (
    MANIFEST_ELIGIBLE_STATUSES,
    SUPPORTED_PNL_SOURCE_FAMILIES,
)
from backend.app.services.pnl_task_dispatch import PNL_RESULT_CACHE_VERSION

_PNL_V1_DATA_INPUT_FAMILIES: tuple[tuple[str, str], ...] = (
    ("", "*.xls"),
    ("", "*.xlsx"),
    ("pnl", "*.xls"),
    ("pnl/processed", "*.xls"),
    ("pnl_514", "*.xlsx"),
    ("pnl_514/processed", "*.xlsx"),
    ("pnl_516", "*.xlsx"),
    ("pnl_516/processed", "*.xlsx"),
    ("pnl_517", "*.xlsx"),
    ("pnl_517/processed", "*.xlsx"),
)


def _pnl_v1_data_envelope_with_fresh_trace(envelope: dict[str, object]) -> dict[str, object]:
    """Shallow-copy the cached envelope and refresh trace_id in place.

    The result payload can be sizeable; deep-copying on every hit would reintroduce
    the GIL contention this cache is designed to remove. Downstream callers must
    not mutate nested cached structures.
    """
    response = dict(envelope)
    meta = envelope.get("result_meta")
    if isinstance(meta, dict):
        response["result_meta"] = {**meta, "trace_id": f"tr_pnl_v1_data_{uuid4().hex[:12]}"}
    return response


def _pnl_v1_data_duckdb_identity(duckdb_path: str) -> tuple[str, int, int] | None:
    """Fingerprint the DuckDB file that `PnlRepository` will actually read.

    `PnlRepository` connects through `resolve_effective_read_path(self.path)`
    (see `backend/app/repositories/pnl_repo.py:824,892`), so an active read
    context can swap the physical file (e.g. a snapshot) underneath the
    requested path. Stat the resolved path so the cache identity moves with
    the storage the repository actually opens.
    """
    active_path = str(duckdb_path)
    try:
        effective_path = resolve_effective_read_path(active_path)
    except (DuckDBReadSelectionError, OSError):
        return None
    path = Path(effective_path)
    if not path.exists():
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    return (str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def _pnl_v1_data_governance_streams_identity(
    governance_dir: str,
) -> tuple[tuple[object, ...], ...]:
    """Fingerprint the governance JSONL streams gating this envelope.

    `_pnl_v1_data_envelope_compute` funnels through
    `_build_pnl_formal_result_envelope_from_lineage`, which reads
    `cache_build_run.jsonl` / `cache_manifest.jsonl` via
    `backend/app/governance/formal_compute_lineage.py`. The compute path also
    reads `source_manifest.jsonl` through `load_latest_pnl_refresh_input`.
    Reuse the existing `_jsonl_file_cache_key` helper (same pattern as
    `bond_analytics_service._bond_analytics_result_cache_key`) so any edit to
    those streams bumps the cache key.
    """
    governance_path = Path(governance_dir)
    identities: list[tuple[object, ...]] = []
    for stream in (CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM, SOURCE_MANIFEST_STREAM):
        stream_path = governance_path / f"{stream}.jsonl"
        identity: tuple[object, ...] | None
        try:
            identity = _jsonl_file_cache_key(stream_path)
        except OSError:
            identity = None
        if identity is None:
            identity = (str(stream_path.resolve()), "missing", 0)
        identities.append(identity)
    return tuple(identities)


def _pnl_v1_data_input_fingerprint(data_root: Path) -> tuple[tuple[str, int, int], ...] | None:
    if not data_root.exists():
        return None
    hits: dict[str, tuple[int, int]] = {}
    for subdir, pattern in _PNL_V1_DATA_INPUT_FAMILIES:
        base = data_root / subdir if subdir else data_root
        if not base.exists():
            continue
        for path in base.glob(pattern):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                return None
            hits[str(path.resolve())] = (stat.st_mtime_ns, stat.st_size)
    return tuple(
        (resolved, mtime, size)
        for resolved, (mtime, size) in sorted(hits.items())
    )


def _pnl_v1_data_manifest_archived_paths_fingerprint(
    governance_dir: str,
    archive_root: str | Path | None = None,
) -> tuple[tuple[str, int, int], ...] | None:
    """Stat every eligible `archived_path` referenced by `source_manifest.jsonl`.

    Mirrors `pnl_source_service._manifest_candidates` filtering (supported
    source family, eligible status, non-empty archived_path, not a `processed/`
    path) so we fingerprint the actual files the read path materialises. Only
    stat is performed for current-root files; relocated identities also verify
    the full receipt SHA256 before returning a physical path. No xlsx parsing
    is performed. If any eligible archived_path cannot
    be stat'd, return None so the envelope falls back to the uncached path
    instead of serving stale bytes from an inconsistent manifest.
    """
    manifest_path = Path(governance_dir) / f"{SOURCE_MANIFEST_STREAM}.jsonl"
    if not manifest_path.exists():
        return ()
    try:
        rows = GovernanceRepository(base_dir=governance_dir).read_all(SOURCE_MANIFEST_STREAM)
    except OSError:
        return None

    hits: dict[str, tuple[int, int]] = {}
    for row in rows:
        source_family = str(row.get("source_family", ""))
        if source_family not in SUPPORTED_PNL_SOURCE_FAMILIES:
            continue
        if str(row.get("status", "")) not in MANIFEST_ELIGIBLE_STATUSES:
            continue
        archived_path = row.get("archived_path")
        if archived_path in (None, ""):
            continue
        historical_path = Path(str(archived_path))
        if any(part.lower() == "processed" for part in historical_path.parts):
            continue
        path = resolve_local_archive_path(historical_path, archive_root) if archive_root is not None else historical_path
        try:
            stat = path.stat()
        except OSError:
            return None
        hits[str(path.resolve())] = (stat.st_mtime_ns, stat.st_size)
    return tuple(
        (resolved, mtime, size)
        for resolved, (mtime, size) in sorted(hits.items())
    )


def _pnl_v1_data_cache_key(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    data_root: Path,
    archive_root: str | Path | None = None,
) -> tuple[object, ...] | None:
    duckdb_identity = _pnl_v1_data_duckdb_identity(duckdb_path)
    if duckdb_identity is None:
        return None
    input_fingerprint = _pnl_v1_data_input_fingerprint(data_root)
    if input_fingerprint is None:
        return None
    archived_fingerprint = _pnl_v1_data_manifest_archived_paths_fingerprint(governance_dir, archive_root)
    if archived_fingerprint is None:
        return None
    governance_identities = _pnl_v1_data_governance_streams_identity(governance_dir)
    return (
        "pnl_service.v1_data_envelope",
        PNL_RESULT_CACHE_VERSION,
        report_date,
        duckdb_identity,
        governance_identities,
        archived_fingerprint,
        input_fingerprint,
    )
