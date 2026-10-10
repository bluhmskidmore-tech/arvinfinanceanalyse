from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Iterator, Mapping
from concurrent.futures import Future
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

import duckdb
from backend.app.governance.locks import LockDefinition, acquire_lock

PUBLICATION_PROTOCOL_VERSION = "financial-result-publication/v1"
FINANCIAL_PUBLICATION_API_VERSION = "financial-api/v1"
FINANCIAL_PUBLICATION_SCHEMA_VERSION = "financial-results/v1"
_PUBLICATION_LOCK_TTL_SECONDS = 7200
PUBLICATION_POINTER_FILE = "current.json"
PUBLICATION_MANIFEST_TABLE = "_moss_financial_publication_manifest"
_GENERATION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ValidationKey = tuple[str, tuple[int, int, int, int], tuple[int, int, int, int]]
_VALIDATION_CACHE: dict[_ValidationKey, ResolvedFinancialPublication] = {}
_VALIDATION_IN_FLIGHT: dict[_ValidationKey, Future[ResolvedFinancialPublication]] = {}
_VALIDATION_CACHE_LOCK = Lock()
_VALIDATION_CACHE_MAX_ENTRIES = 32


class FinancialPublicationError(RuntimeError):
    """Base error for a rejected or corrupt immutable financial publication."""


class FinancialPublicationUnavailable(FinancialPublicationError):
    pass


class FinancialPublicationInvalid(FinancialPublicationError):
    pass


class FinancialPublicationConflict(FinancialPublicationInvalid):
    pass


class FinancialPublicationIncompatible(FinancialPublicationError):
    pass


@dataclass(frozen=True)
class ResolvedFinancialPublication:
    generation: str
    database_path: Path
    manifest_path: Path
    manifest_sha256: str
    manifest: Mapping[str, object]


def canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def validate_generation(value: str) -> str:
    generation = str(value or "").strip()
    if not _GENERATION_PATTERN.fullmatch(generation):
        raise FinancialPublicationInvalid(
            "Publication generation must contain only letters, digits, dot, underscore, or dash."
        )
    return generation


def generation_database_path(publication_root: Path | str, generation: str) -> Path:
    validated = validate_generation(generation)
    return Path(publication_root).resolve() / "generations" / f"{validated}.duckdb"


def generation_manifest_path(publication_root: Path | str, generation: str) -> Path:
    validated = validate_generation(generation)
    return Path(publication_root).resolve() / "generations" / f"{validated}.manifest.json"


def generation_invalidation_path(publication_root: Path | str, generation: str) -> Path:
    validated = validate_generation(generation)
    return Path(publication_root).resolve() / "invalidations" / f"{validated}.json"


def read_publication_pointer(
    publication_root: Path | str,
    *,
    require_valid: bool = True,
) -> dict[str, object] | None:
    pointer_path = Path(publication_root).resolve() / PUBLICATION_POINTER_FILE
    if not pointer_path.is_file():
        return None
    payload = _read_json_object(pointer_path, label="publication pointer")
    if payload.get("protocol_version") != PUBLICATION_PROTOCOL_VERSION:
        raise FinancialPublicationInvalid("Publication pointer protocol version is unsupported.")
    current_generation = validate_generation(str(payload.get("generation") or ""))
    manifest_sha256 = str(payload.get("manifest_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256):
        raise FinancialPublicationInvalid("Publication pointer manifest digest is invalid.")
    validity = payload.get("validity")
    if not isinstance(validity, Mapping):
        raise FinancialPublicationInvalid("Publication pointer validity declaration is missing.")
    if require_valid and validity.get("state") != "valid":
        raise FinancialPublicationUnavailable("Current financial publication is not valid.")
    retained = payload.get("retained_generations")
    if not isinstance(retained, list) or not retained:
        raise FinancialPublicationInvalid("Publication pointer retained-generation set is missing.")
    retained_names: list[str] = []
    for item in retained:
        if not isinstance(item, Mapping):
            raise FinancialPublicationInvalid("Publication pointer retained-generation entry is invalid.")
        retained_generation = validate_generation(str(item.get("generation") or ""))
        retained_digest = str(item.get("manifest_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", retained_digest):
            raise FinancialPublicationInvalid("Publication pointer retained manifest digest is invalid.")
        retained_names.append(retained_generation)
    if retained_names[0] != current_generation or len(retained_names) != len(set(retained_names)):
        raise FinancialPublicationInvalid("Publication pointer retained generations are inconsistent.")
    if len(retained_names) > 2:
        raise FinancialPublicationInvalid("Publication pointer retains more than the supported window.")
    return payload


def resolve_financial_generation(
    publication_root: Path | str,
    *,
    generation: str | None,
    reader_api_version: str,
    reader_schema_version: str,
) -> ResolvedFinancialPublication:
    root = Path(publication_root).resolve()
    pointer = read_publication_pointer(root, require_valid=generation is None)
    if generation is None:
        if pointer is None:
            raise FinancialPublicationUnavailable("No current financial publication is committed.")
        resolved_generation = validate_generation(str(pointer["generation"]))
        expected_manifest_sha256 = str(pointer["manifest_sha256"])
    else:
        resolved_generation = validate_generation(generation)
        if pointer is None:
            raise FinancialPublicationUnavailable("No committed financial publication exists.")
        expected_manifest_sha256 = _retained_manifest_sha256(pointer, resolved_generation)

    return revalidate_financial_generation(
        root,
        generation=resolved_generation,
        expected_manifest_sha256=expected_manifest_sha256,
        reader_api_version=reader_api_version,
        reader_schema_version=reader_schema_version,
        require_current_validity=generation is None,
    )


def revalidate_financial_generation(
    publication_root: Path | str,
    *,
    generation: str,
    expected_manifest_sha256: str,
    reader_api_version: str,
    reader_schema_version: str,
    require_current_validity: bool,
) -> ResolvedFinancialPublication:
    """Recheck a fixed generation and digest without following the current pointer."""

    root = Path(publication_root).resolve()
    resolved = validate_sealed_financial_generation(
        root,
        generation=generation,
        expected_manifest_sha256=expected_manifest_sha256,
        reader_api_version=reader_api_version,
        reader_schema_version=reader_schema_version,
    )
    # Validation may wait for another reader. Recheck authorization for the fixed
    # selection, without following a newer current generation.
    latest_pointer = read_publication_pointer(root, require_valid=False)
    if latest_pointer is None:
        raise FinancialPublicationUnavailable("No committed financial publication exists.")
    latest_digest = _retained_manifest_sha256(latest_pointer, resolved.generation)
    if latest_digest != expected_manifest_sha256:
        raise FinancialPublicationInvalid("Current pointer does not match the sealed publication manifest.")
    if require_current_validity and latest_pointer["generation"] == resolved.generation:
        validity = latest_pointer["validity"]
        assert isinstance(validity, Mapping)
        if validity.get("state") != "valid":
            raise FinancialPublicationUnavailable("Current financial publication is not valid.")
    return resolved


def _retained_manifest_sha256(pointer: Mapping[str, object], generation: str) -> str:
    retained = pointer["retained_generations"]
    assert isinstance(retained, list)
    entry = next(
        (
            item
            for item in retained
            if isinstance(item, Mapping) and item.get("generation") == generation
        ),
        None,
    )
    if entry is None:
        raise FinancialPublicationUnavailable(
            f"Financial publication {generation} is not in the committed retention window."
        )
    return str(entry["manifest_sha256"])


def validate_sealed_financial_generation(
    publication_root: Path | str,
    *,
    generation: str,
    expected_manifest_sha256: str | None,
    reader_api_version: str,
    reader_schema_version: str,
) -> ResolvedFinancialPublication:
    """Validate sealed artifacts without treating them as reader-authorized.

    Reader entry points must use ``resolve_financial_generation`` so the current
    pointer and retention window are enforced. The publisher uses this function
    for post-close validation immediately before the pointer commit.
    """

    root = Path(publication_root).resolve()
    resolved_generation = validate_generation(generation)
    invalidation_path = generation_invalidation_path(root, resolved_generation)
    manifest_path = generation_manifest_path(root, resolved_generation)
    database_path = generation_database_path(root, resolved_generation)
    while True:
        if invalidation_path.exists():
            invalidation = _read_json_object(invalidation_path, label="publication invalidation")
            raise FinancialPublicationUnavailable(
                f"Financial publication {resolved_generation} was invalidated: "
                f"{str(invalidation.get('reason') or 'reason not recorded')}"
            )
        if not manifest_path.is_file() or not database_path.is_file():
            raise FinancialPublicationUnavailable(
                f"Financial publication {resolved_generation} is incomplete or unavailable."
            )

        manifest_bytes = manifest_path.read_bytes()
        manifest_sha256 = sha256_bytes(manifest_bytes)
        if expected_manifest_sha256 is not None and manifest_sha256 != expected_manifest_sha256:
            raise FinancialPublicationInvalid("Current pointer does not match the sealed publication manifest.")
        manifest_identity = _file_identity(manifest_path)
        database_identity = _file_identity(database_path)
        cache_key = (manifest_sha256, manifest_identity, database_identity)
        with _VALIDATION_CACHE_LOCK:
            cached = _VALIDATION_CACHE.get(cache_key)
        if cached is not None:
            _validate_manifest_header(
                cached.manifest,
                generation=resolved_generation,
                reader_api_version=reader_api_version,
                reader_schema_version=reader_schema_version,
            )
            return cached

        # Reader compatibility is caller-specific; only artifact validation is shared.
        manifest = _parse_json_object(manifest_bytes, label="publication manifest")
        _validate_manifest_header(
            manifest,
            generation=resolved_generation,
            reader_api_version=reader_api_version,
            reader_schema_version=reader_schema_version,
        )
        owns_validation = False
        with _VALIDATION_CACHE_LOCK:
            cached = _VALIDATION_CACHE.get(cache_key)
            if cached is not None:
                return cached
            pending = _VALIDATION_IN_FLIGHT.get(cache_key)
            if pending is None:
                pending = Future()
                _VALIDATION_IN_FLIGHT[cache_key] = pending
                owns_validation = True
        if not owns_validation:
            pending.result()
            # A shared result is not authority to skip fresh revocation, file identity,
            # manifest digest, expiry, or this caller's reader-version checks.
            continue

        try:
            _validate_database_artifact(database_path, manifest)
            # The owner can cross the same expiry/revocation boundary as a waiter.
            # Recheck small artifacts and identities before caching its heavy result.
            try:
                latest_manifest_bytes = manifest_path.read_bytes()
                latest_manifest_identity = _file_identity(manifest_path)
                latest_database_identity = _file_identity(database_path)
            except OSError as exc:
                raise FinancialPublicationUnavailable(
                    f"Financial publication {resolved_generation} became unavailable during validation."
                ) from exc
            if sha256_bytes(latest_manifest_bytes) != manifest_sha256:
                raise FinancialPublicationInvalid("Publication manifest changed during artifact validation.")
            if latest_manifest_identity != manifest_identity or latest_database_identity != database_identity:
                raise FinancialPublicationInvalid("Publication artifact identity changed during validation.")
            if invalidation_path.exists():
                raise FinancialPublicationUnavailable(
                    f"Financial publication {resolved_generation} was invalidated during artifact validation."
                )
            _validate_manifest_header(
                manifest,
                generation=resolved_generation,
                reader_api_version=reader_api_version,
                reader_schema_version=reader_schema_version,
            )
            resolved = ResolvedFinancialPublication(
                generation=resolved_generation,
                database_path=database_path,
                manifest_path=manifest_path,
                manifest_sha256=manifest_sha256,
                manifest=manifest,
            )
            with _VALIDATION_CACHE_LOCK:
                if len(_VALIDATION_CACHE) >= _VALIDATION_CACHE_MAX_ENTRIES:
                    _VALIDATION_CACHE.clear()
                _VALIDATION_CACHE[cache_key] = resolved
            pending.set_result(resolved)
            return resolved
        except BaseException as exc:
            pending.set_exception(exc)
            raise
        finally:
            with _VALIDATION_CACHE_LOCK:
                if _VALIDATION_IN_FLIGHT.get(cache_key) is pending:
                    del _VALIDATION_IN_FLIGHT[cache_key]


@contextmanager
def open_financial_generation(
    publication_root: Path | str,
    *,
    generation: str | None,
    reader_api_version: str,
    reader_schema_version: str,
) -> Iterator[tuple[duckdb.DuckDBPyConnection, ResolvedFinancialPublication]]:
    resolved = resolve_financial_generation(
        publication_root,
        generation=generation,
        reader_api_version=reader_api_version,
        reader_schema_version=reader_schema_version,
    )
    conn = duckdb.connect(str(resolved.database_path), read_only=True)
    try:
        # Recheck the small revocation marker after the connection opens. A pinned
        # generation is never silently replaced by the current generation.
        invalidation_path = generation_invalidation_path(publication_root, resolved.generation)
        if invalidation_path.exists():
            raise FinancialPublicationUnavailable(
                f"Financial publication {resolved.generation} was invalidated before query execution."
            )
        yield conn, resolved
    finally:
        conn.close()


def reset_financial_publication_validation_cache() -> None:
    """Clear completed entries while in-flight owners keep waking their waiters."""

    with _VALIDATION_CACHE_LOCK:
        _VALIDATION_CACHE.clear()


def _validate_manifest_header(
    manifest: Mapping[str, object],
    *,
    generation: str,
    reader_api_version: str,
    reader_schema_version: str,
) -> None:
    if manifest.get("protocol_version") != PUBLICATION_PROTOCOL_VERSION:
        raise FinancialPublicationInvalid("Publication manifest protocol version is unsupported.")
    if manifest.get("generation") != generation:
        raise FinancialPublicationInvalid("Publication manifest generation does not match its file name.")
    validity = manifest.get("validity")
    if not isinstance(validity, Mapping) or validity.get("state") != "valid":
        raise FinancialPublicationUnavailable(f"Financial publication {generation} is not valid.")
    expires_at = validity.get("expires_at")
    if expires_at is not None and _parse_utc_timestamp(str(expires_at)) <= datetime.now(UTC):
        raise FinancialPublicationUnavailable(f"Financial publication {generation} has expired.")
    compatibility = manifest.get("compatibility")
    if not isinstance(compatibility, Mapping):
        raise FinancialPublicationInvalid("Publication compatibility declaration is missing.")
    supported_api_versions = compatibility.get("supported_api_versions")
    supported_schema_versions = compatibility.get("supported_schema_versions")
    if not isinstance(supported_api_versions, list) or reader_api_version not in supported_api_versions:
        raise FinancialPublicationIncompatible(
            f"Reader API version {reader_api_version!r} is incompatible with publication {generation}."
        )
    if not isinstance(supported_schema_versions, list) or reader_schema_version not in supported_schema_versions:
        raise FinancialPublicationIncompatible(
            f"Reader schema version {reader_schema_version!r} is incompatible with publication {generation}."
        )


def _validate_database_artifact(database_path: Path, manifest: Mapping[str, object]) -> None:
    database = manifest.get("database")
    if not isinstance(database, Mapping):
        raise FinancialPublicationInvalid("Publication database declaration is missing.")
    if database.get("file_name") != database_path.name:
        raise FinancialPublicationInvalid("Publication database file name does not match its manifest.")
    expected_size = database.get("size_bytes")
    if not isinstance(expected_size, int) or database_path.stat().st_size != expected_size:
        raise FinancialPublicationInvalid("Publication database size does not match its manifest.")
    expected_sha256 = str(database.get("sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise FinancialPublicationInvalid("Publication database digest is invalid.")
    if sha256_file(database_path) != expected_sha256:
        raise FinancialPublicationInvalid("Publication database digest does not match its manifest.")

    sealed_payload = manifest.get("sealed_payload")
    sealed_payload_sha256 = str(manifest.get("sealed_payload_sha256") or "")
    if sha256_bytes(canonical_json_bytes(sealed_payload)) != sealed_payload_sha256:
        raise FinancialPublicationInvalid("Publication sealed payload digest is invalid.")
    conn = duckdb.connect(str(database_path), read_only=True)
    try:
        row = conn.execute(
            f'SELECT protocol_version, generation, sealed_payload_json, sealed_payload_sha256 '
            f'FROM "{PUBLICATION_MANIFEST_TABLE}"'
        ).fetchone()
    except duckdb.Error as exc:
        raise FinancialPublicationInvalid("Publication database has no readable sealed manifest.") from exc
    finally:
        conn.close()
    if row is None or len(row) != 4:
        raise FinancialPublicationInvalid("Publication database sealed manifest is empty.")
    if row[0] != PUBLICATION_PROTOCOL_VERSION or row[1] != manifest.get("generation"):
        raise FinancialPublicationInvalid("Publication database identity does not match its manifest.")
    if row[2] != canonical_json_bytes(sealed_payload).decode("utf-8") or row[3] != sealed_payload_sha256:
        raise FinancialPublicationInvalid("Publication database sealed payload does not match its manifest.")


def _read_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        return _parse_json_object(path.read_bytes(), label=label)
    except OSError as exc:
        raise FinancialPublicationUnavailable(f"Unable to read {label}.") from exc


def _parse_json_object(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FinancialPublicationInvalid(f"{label.capitalize()} is not valid UTF-8 JSON.") from exc
    if not isinstance(value, dict):
        raise FinancialPublicationInvalid(f"{label.capitalize()} must be a JSON object.")
    return value


def _parse_utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise FinancialPublicationInvalid("Publication expiry timestamp is invalid.") from exc
    if parsed.tzinfo is None:
        raise FinancialPublicationInvalid("Publication expiry timestamp must include a timezone.")
    return parsed.astimezone(UTC)


def _file_identity(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return (int(stat.st_dev), int(stat.st_ino), int(stat.st_size), int(stat.st_mtime_ns))


def invalidate_financial_generation(
    publication_root: Path | str,
    *,
    generation: str,
    reason: str,
) -> Path:
    root = Path(publication_root).resolve()
    validated_generation = validate_generation(generation)
    normalized_reason = " ".join(str(reason or "").split())
    if not normalized_reason:
        raise ValueError("Financial publication invalidation requires a reason.")
    invalidation_path = generation_invalidation_path(root, validated_generation)
    invalidation_path.parent.mkdir(parents=True, exist_ok=True)
    with acquire_lock(_publication_lock(root), base_dir=root):
        if invalidation_path.exists():
            return invalidation_path
        payload = {
            "protocol_version": PUBLICATION_PROTOCOL_VERSION,
            "generation": validated_generation,
            "invalidated_at": _utc_now(),
            "reason": normalized_reason,
        }
        _write_atomic_json(invalidation_path, payload, replace=False)
        pointer = read_publication_pointer(root, require_valid=False)
        if pointer is not None and pointer.get("generation") == validated_generation:
            _write_atomic_json(
                root / PUBLICATION_POINTER_FILE,
                {
                    **pointer,
                    "validity": {
                        "state": "invalid",
                        "invalidated_at": payload["invalidated_at"],
                        "reason": normalized_reason,
                    },
                },
                replace=True,
            )
    return invalidation_path


def _publication_lock(root: Path) -> LockDefinition:
    digest = sha256_bytes(str(root).lower().encode("utf-8"))[:12]
    return LockDefinition(
        key=f"lock:financial-result-publication:{digest}",
        ttl_seconds=_PUBLICATION_LOCK_TTL_SECONDS,
    )


def _write_atomic_json(path: Path, payload: Mapping[str, object], *, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    encoded = canonical_json_bytes(payload)
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if not replace and path.exists():
            raise FinancialPublicationConflict(f"Immutable publication artifact already exists: {path.name}")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
