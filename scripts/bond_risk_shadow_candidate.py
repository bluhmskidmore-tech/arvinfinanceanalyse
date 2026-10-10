from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import heapq
import json
import math
import os
import re
import struct
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.fixed_income_version_set import (  # noqa: E402
    CONFIGURED_CURRENT_VERSION_STATE,
    FIXED_INCOME_VERSION_SET,
    MaterializeModuleVersion,
    compose_risk_tensor_source_version,
)
from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor  # noqa: E402
from backend.app.duckdb_schema_bootstrap import assert_duckdb_schema_current  # noqa: E402
from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.repositories.duckdb_read_context import active_read_scope  # noqa: E402
from backend.app.repositories.duckdb_repo import read_only_connection  # noqa: E402
from backend.app.schema_registry.duckdb_loader import (  # noqa: E402
    capture_main_catalog,
    catalog_snapshot_sha256,
)
from backend.app.tasks.bond_analytics_materialize import (  # noqa: E402
    BOND_ANALYTICS_MODULE,
    materialize_bond_analytics_facts,
)
from backend.app.tasks.risk_tensor_materialize import (  # noqa: E402
    RISK_TENSOR_MODULE,
    materialize_risk_tensor_facts,
)

BOND_CACHE_KEY = FIXED_INCOME_VERSION_SET.bond_analytics.cache_key
BOND_CACHE_VERSION = FIXED_INCOME_VERSION_SET.bond_analytics.cache_version
BOND_RULE_VERSION = FIXED_INCOME_VERSION_SET.bond_analytics.rule_version
RISK_CACHE_KEY = FIXED_INCOME_VERSION_SET.risk_tensor.cache_key
RISK_CACHE_VERSION = FIXED_INCOME_VERSION_SET.risk_tensor.cache_version
RISK_RULE_VERSION = FIXED_INCOME_VERSION_SET.risk_tensor.rule_version

RECEIPT_FILENAME = "bond_risk_shadow_candidate_receipt.json"
RECEIPT_SCHEMA = "moss.bond-risk-shadow-candidate-receipt/v1"
CANDIDATE_FILENAME = "bond_risk_shadow_candidate.duckdb"
GOVERNANCE_DIRNAME = "candidate_governance"
INCOMPLETE_MARKER = ".INCOMPLETE"
SEALED_MARKER = ".SEALED"
SPOOL_DIRNAME = ".identity_spool"
EVIDENCE_CLASS = "structural-shadow"
_SCHEMA_RECEIPT_SCHEMA = "moss.duckdb-schema-current/v1"
_CACHE_BUILD_RUN_FILENAME = "cache_build_run.jsonl"
_CACHE_MANIFEST_FILENAME = "cache_manifest.jsonl"

_INTERNAL_SCHEMAS = {"information_schema", "pg_catalog"}
_TARGET_TABLES = {
    "main.fact_formal_bond_analytics_daily",
    "main.fact_formal_risk_tensor_daily",
}
_TARGET_TABLE_HINTS = {
    "main.fact_formal_bond_analytics_daily": {
        "index_name": "uq_fact_formal_bond_analytics_daily_natural_key",
        "expressions": (
            "(COALESCE(CAST(report_date AS VARCHAR), '__moss_null__'))",
            "(COALESCE(CAST(instrument_code AS VARCHAR), '__moss_null__'))",
            "(COALESCE(CAST(portfolio_name AS VARCHAR), '__moss_null__'))",
            "(COALESCE(CAST(cost_center AS VARCHAR), '__moss_null__'))",
            "(COALESCE(CAST(accounting_class AS VARCHAR), '__moss_null__'))",
            "(COALESCE(CAST(maturity_date AS VARCHAR), '__moss_null__'))",
        ),
    },
    "main.fact_formal_risk_tensor_daily": {
        "index_name": "uq_fact_formal_risk_tensor_daily_natural_key",
        "expressions": (
            "(COALESCE(CAST(report_date AS VARCHAR), '__moss_null__'))",
        ),
    },
}
_ALLOWED_REPORT_DATE_TYPES = {"DATE", "VARCHAR"}
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_CHUNK_SIZE = 4_096
_MERGE_FAN_IN = 32
_COPY_CHUNK_BYTES = 1024 * 1024
_MAX_RECEIPT_BYTES = 16 * 1024 * 1024
_MAX_MARKER_BYTES = 64 * 1024
_MAX_JSONL_TOTAL_BYTES = 8 * 1024 * 1024
_MAX_JSONL_LINES = 10_000
_MAX_JSONL_LINE_BYTES = 1024 * 1024
_MAX_CATALOG_ROWS_PER_KIND = 50_000
_MAX_CATALOG_ROWS_TOTAL = 100_000
_ENVIRONMENT_BINDINGS = (
    ("environment", "MOSS_ENVIRONMENT"),
    ("governance_backend", "MOSS_GOVERNANCE_BACKEND"),
    ("source_preview_governance_backend", "MOSS_SOURCE_PREVIEW_GOVERNANCE_BACKEND"),
    ("duckdb_path", "MOSS_DUCKDB_PATH"),
)


class ShadowCandidateError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail or code


@dataclass(frozen=True)
class TableColumnSpec:
    name: str
    duckdb_type: str

    def as_receipt(self) -> dict[str, str]:
        return {"name": self.name, "duckdb_type": self.duckdb_type}


@dataclass(frozen=True)
class TableSpec:
    schema: str
    name: str
    columns: tuple[TableColumnSpec, ...]

    @property
    def key(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass(frozen=True)
class DigestSummary:
    row_count: int
    table_sha256: str

    def as_receipt(self) -> dict[str, object]:
        return {"row_count": self.row_count, "table_sha256": self.table_sha256}


@dataclass(frozen=True)
class FileFingerprint:
    path: str
    bytes: int
    mtime_ns: int
    sha256: str
    file_identity: dict[str, int]

    def as_receipt(self) -> dict[str, object]:
        return {
            "path": self.path,
            "bytes": self.bytes,
            "mtime_ns": self.mtime_ns,
            "sha256": self.sha256,
            "file_identity": dict(self.file_identity),
        }


def _frame(tag: bytes, payload: bytes) -> bytes:
    if len(tag) != 1:
        raise ValueError("canonical type tags must be one byte")
    return tag + len(payload).to_bytes(8, byteorder="big", signed=False) + payload


def canonical_serialize(value: Any) -> bytes:
    if value is None:
        return _frame(b"N", b"")
    if isinstance(value, bool):
        return _frame(b"B", b"1" if value else b"0")
    if isinstance(value, Decimal):
        sign, digits, exponent = value.as_tuple()
        payload = json.dumps(
            {
                "sign": sign,
                "digits": list(digits),
                "exponent": exponent,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return _frame(b"D", payload)
    if isinstance(value, int):
        return _frame(b"I", str(value).encode("ascii"))
    if isinstance(value, float):
        if math.isnan(value):
            payload = b"nan"
        elif math.isinf(value):
            payload = b"+inf" if value > 0 else b"-inf"
        else:
            payload = struct.pack(">d", value)
        return _frame(b"F", payload)
    if isinstance(value, dt.datetime):
        return _frame(b"T", value.isoformat(timespec="microseconds").encode("ascii"))
    if isinstance(value, dt.date):
        return _frame(b"A", value.isoformat().encode("ascii"))
    if isinstance(value, dt.time):
        return _frame(b"U", value.isoformat(timespec="microseconds").encode("ascii"))
    if isinstance(value, dt.timedelta):
        payload = json.dumps(
            {
                "days": value.days,
                "seconds": value.seconds,
                "microseconds": value.microseconds,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        return _frame(b"X", payload)
    if isinstance(value, str):
        return _frame(b"S", value.encode("utf-8"))
    if isinstance(value, (bytes, bytearray, memoryview)):
        return _frame(b"Y", bytes(value))
    if isinstance(value, uuid.UUID):
        return _frame(b"G", value.bytes)
    if isinstance(value, list):
        return _frame(b"L", b"".join(canonical_serialize(item) for item in value))
    if isinstance(value, tuple):
        return _frame(b"Q", b"".join(canonical_serialize(item) for item in value))
    if isinstance(value, dict):
        entries = [
            canonical_serialize(key) + canonical_serialize(item)
            for key, item in value.items()
        ]
        return _frame(b"M", b"".join(sorted(entries)))
    raise ShadowCandidateError(
        "unsupported_duckdb_value_type",
        detail=f"unsupported DuckDB value type: {type(value)!r}",
    )


def canonical_row_serialize(values: Sequence[Any]) -> bytes:
    return _frame(b"R", b"".join(canonical_serialize(value) for value in values))


def canonical_row_digest(values: Sequence[Any]) -> bytes:
    return hashlib.sha256(canonical_row_serialize(values)).digest()


def _iter_digest_records(stream: Any):
    digest_size = hashlib.sha256().digest_size
    while True:
        chunk = stream.read(digest_size)
        if not chunk:
            break
        if len(chunk) != digest_size:
            raise ShadowCandidateError("corrupt_digest_spool_chunk")
        yield chunk


class _SpoolSorter:
    def __init__(self, root: Path, label: str) -> None:
        self._root = root
        self._label = label
        self._buffer: list[bytes] = []
        self._chunks: list[Path] = []
        self._count = 0
        self._finished: DigestSummary | None = None
        self._merge_round = 0

    def add(self, digest: bytes) -> None:
        self._buffer.append(digest)
        self._count += 1
        if len(self._buffer) >= _CHUNK_SIZE:
            self._flush()

    def _flush(self) -> None:
        if not self._buffer:
            return
        path = self._root / f"{self._label}-{len(self._chunks):06d}.bin"
        with path.open("wb") as handle:
            for digest in sorted(self._buffer):
                handle.write(digest)
        self._chunks.append(path)
        self._buffer.clear()

    def _merge_chunk_group(self, paths: Sequence[Path]) -> Path:
        merged_path = self._root / f"{self._label}-merge-{self._merge_round:06d}-{len(self._chunks):06d}.bin"
        streams = [path.open("rb") for path in paths]
        try:
            with merged_path.open("wb") as handle:
                for digest in heapq.merge(*(_iter_digest_records(stream) for stream in streams)):
                    handle.write(digest)
        finally:
            for stream in streams:
                stream.close()
        for path in paths:
            try:
                path.unlink()
            except FileNotFoundError:
                continue
        self._merge_round += 1
        return merged_path

    def _collapse_chunks(self) -> None:
        while len(self._chunks) > _MERGE_FAN_IN:
            next_round: list[Path] = []
            for index in range(0, len(self._chunks), _MERGE_FAN_IN):
                group = self._chunks[index : index + _MERGE_FAN_IN]
                if len(group) == 1:
                    next_round.append(group[0])
                    continue
                next_round.append(self._merge_chunk_group(group))
            self._chunks = next_round

    def finish(self) -> DigestSummary:
        if self._finished is not None:
            return self._finished
        self._flush()
        self._collapse_chunks()
        table_hasher = hashlib.sha256()
        try:
            if self._chunks:
                streams = [path.open("rb") for path in self._chunks]
                try:
                    for digest in heapq.merge(
                        *(_iter_digest_records(stream) for stream in streams)
                    ):
                        table_hasher.update(digest)
                finally:
                    for stream in streams:
                        stream.close()
        finally:
            for path in self._chunks:
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue
            self._chunks.clear()
        self._finished = DigestSummary(self._count, table_hasher.hexdigest())
        return self._finished


def _stable_json_dumps(payload: Mapping[str, object]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def _sha256_json(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _receipt_sha256(receipt: Mapping[str, object]) -> str:
    payload = dict(receipt)
    payload.pop("canonical_receipt_sha256", None)
    return _sha256_json(payload)


def _absolute_input_path(path: str | Path | os.PathLike[str], *, field_name: str) -> Path:
    raw = Path(os.fspath(path))
    if not raw.is_absolute():
        raise ShadowCandidateError(f"{field_name}_must_be_absolute")
    return Path(os.path.normpath(os.path.abspath(os.fspath(raw))))


def _assert_no_symlink_or_junction(path: Path, *, field_name: str) -> None:
    current = Path(path.anchor) if path.is_absolute() else Path(".")
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for part in parts:
        current /= part
        if not os.path.lexists(current):
            continue
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ShadowCandidateError(
                f"{field_name}_contains_symlink_or_junction",
                detail=f"{field_name} contains a symlink or junction component",
            )


def _path_identity(path: Path, *, field_name: str) -> tuple[int, int]:
    try:
        stat = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise ShadowCandidateError(
            f"{field_name}_identity_unavailable",
            detail=f"{field_name} identity is unavailable: {type(exc).__name__}",
        ) from exc
    return stat.st_dev, stat.st_ino


def _identity_payload(identity: tuple[int, int]) -> dict[str, int]:
    return {"device": int(identity[0]), "inode": int(identity[1])}


def _payload_identity(payload: Mapping[str, object], *, field_name: str) -> tuple[int, int]:
    try:
        device = int(payload["device"])
        inode = int(payload["inode"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ShadowCandidateError(
            f"{field_name}_identity_payload_invalid",
            detail=f"{field_name} identity payload is invalid",
        ) from exc
    return device, inode


def _existing_file_no_links(path: Path, *, field_name: str) -> Path:
    candidate = _absolute_input_path(path, field_name=field_name)
    _assert_no_symlink_or_junction(candidate, field_name=field_name)
    if not candidate.is_file():
        raise ShadowCandidateError(
            f"{field_name}_must_be_existing_file",
            detail=f"{field_name} must be an existing file",
        )
    parent_identity = _path_identity(candidate.parent, field_name=f"{field_name}_parent")
    leaf_identity = _path_identity(candidate, field_name=field_name)
    resolved = candidate.resolve(strict=True)
    if _path_identity(candidate.parent, field_name=f"{field_name}_parent") != parent_identity:
        raise ShadowCandidateError(f"{field_name}_parent_identity_changed")
    if _path_identity(candidate, field_name=field_name) != leaf_identity:
        raise ShadowCandidateError(f"{field_name}_identity_changed")
    return resolved


def _assert_samefile_rejected(source_path: Path, live_path: Path) -> None:
    live_abs = _absolute_input_path(live_path, field_name="configured_live_duckdb_path")
    _assert_no_symlink_or_junction(live_abs, field_name="configured_live_duckdb_path")
    same_path = source_path == live_abs
    try:
        same_file = os.path.samefile(source_path, live_abs)
    except OSError:
        same_file = False
    same_identity = False
    try:
        same_identity = _path_identity(source_path, field_name="source_duckdb_path") == _path_identity(
            live_abs,
            field_name="configured_live_duckdb_path",
        )
    except ShadowCandidateError:
        same_identity = False
    if same_path or same_file or same_identity:
        raise ShadowCandidateError(
            "source_matches_live_duckdb_path",
            detail="source path matches configured live DuckDB path",
        )


def _assert_path_matches_identity(
    path: Path,
    *,
    expected_identity: tuple[int, int],
    field_name: str,
    code: str,
) -> None:
    _assert_no_symlink_or_junction(path, field_name=field_name)
    observed = _path_identity(path, field_name=field_name)
    if observed != expected_identity:
        raise ShadowCandidateError(code, detail=f"{field_name} identity changed")


def _assert_distinct_file_identities(
    left_path: Path,
    right_path: Path,
    *,
    left_field_name: str,
    right_field_name: str,
    code: str,
) -> None:
    _assert_no_symlink_or_junction(left_path, field_name=left_field_name)
    _assert_no_symlink_or_junction(right_path, field_name=right_field_name)
    same_path = left_path == right_path
    try:
        same_file = os.path.samefile(left_path, right_path)
    except OSError:
        same_file = False
    same_identity = False
    try:
        same_identity = _path_identity(left_path, field_name=left_field_name) == _path_identity(
            right_path,
            field_name=right_field_name,
        )
    except ShadowCandidateError:
        same_identity = False
    if same_path or same_file or same_identity:
        raise ShadowCandidateError(
            code,
            detail=f"{left_field_name} matches {right_field_name}",
        )


def _validate_report_date(value: str) -> str:
    text = str(value).strip()
    try:
        parsed = dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ShadowCandidateError("invalid_report_date") from exc
    if parsed.isoformat() != text:
        raise ShadowCandidateError("invalid_report_date")
    return text


def _validate_run_id(value: str | None) -> str:
    if value is None:
        return f"shadow-{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    text = str(value).strip()
    if not _RUN_ID_RE.fullmatch(text):
        raise ShadowCandidateError("invalid_run_id")
    return text


def _validate_expected_source_sha256(value: str) -> str:
    text = str(value).strip()
    if not _SHA256_RE.fullmatch(text):
        raise ShadowCandidateError("invalid_expected_source_sha256")
    return text.lower()


def _check_settings_env_consistency(settings: object) -> dict[str, str]:
    observed: dict[str, str] = {}
    for attr_name, env_name in _ENVIRONMENT_BINDINGS:
        setting_value = str(getattr(settings, attr_name, "") or "").strip()
        if not setting_value:
            raise ShadowCandidateError(f"settings_{attr_name}_missing")
        env_value = str(os.environ.get(env_name, "") or "").strip()
        observed[attr_name] = setting_value
        if env_value and env_value != setting_value:
            raise ShadowCandidateError(
                f"environment_setting_mismatch_{attr_name}",
                detail=f"{env_name} does not match settings.{attr_name}",
            )
    if observed["environment"].lower() == "production":
        raise ShadowCandidateError("production_environment_forbidden")
    if observed["governance_backend"].lower() != "jsonl":
        raise ShadowCandidateError("governance_backend_must_be_jsonl")
    if observed["source_preview_governance_backend"].lower() != "jsonl":
        raise ShadowCandidateError("source_preview_governance_backend_must_be_jsonl")
    return observed


def _create_new_directory(path: Path, *, field_name: str) -> dict[str, object]:
    _assert_no_symlink_or_junction(path, field_name=field_name)
    parent = path.parent
    if not parent.is_dir():
        raise ShadowCandidateError(f"{field_name}_parent_must_exist")
    parent_identity = _path_identity(parent, field_name=f"{field_name}_parent")
    try:
        path.mkdir()
    except FileExistsError as exc:
        raise ShadowCandidateError(f"{field_name}_must_be_new") from exc
    if _path_identity(parent, field_name=f"{field_name}_parent") != parent_identity:
        raise ShadowCandidateError(f"{field_name}_parent_identity_changed")
    identity = _path_identity(path, field_name=field_name)
    return {
        "path": str(path.resolve(strict=True)),
        "file_identity": _identity_payload(identity),
        "parent_identity": _identity_payload(parent_identity),
    }


def _remove_path_if_identity(path: Path, *, expected_identity: tuple[int, int] | None) -> None:
    if expected_identity is None or not os.path.lexists(path):
        return
    try:
        observed = _path_identity(path, field_name="cleanup_path")
    except ShadowCandidateError:
        return
    if observed != expected_identity:
        return
    try:
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()
    except OSError:
        return


def _exclusive_binary_create(path: Path, payload_iter: Any) -> FileFingerprint:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    identity = _path_identity(path, field_name=path.stem or path.name)
    hasher = hashlib.sha256()
    byte_count = 0
    try:
        while True:
            chunk = payload_iter.read(_COPY_CHUNK_BYTES)
            if not chunk:
                break
            if not isinstance(chunk, (bytes, bytearray)):
                raise ShadowCandidateError("copy_stream_must_yield_bytes")
            view = memoryview(chunk)
            offset = 0
            while offset < len(view):
                written = os.write(descriptor, view[offset:])
                if written <= 0:
                    raise ShadowCandidateError("candidate_copy_short_write")
                offset += written
            hasher.update(view)
            byte_count += len(view)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if _path_identity(path, field_name=path.stem or path.name) != identity:
        raise ShadowCandidateError("created_file_identity_changed")
    stat = path.stat()
    return FileFingerprint(
        path=str(path.resolve(strict=True)),
        bytes=byte_count,
        mtime_ns=stat.st_mtime_ns,
        sha256=hasher.hexdigest(),
        file_identity=_identity_payload(identity),
    )


def _fingerprint_file(path: Path) -> FileFingerprint:
    hasher = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_COPY_CHUNK_BYTES)
            if not chunk:
                break
            hasher.update(chunk)
            byte_count += len(chunk)
    stat = path.stat()
    return FileFingerprint(
        path=str(path.resolve(strict=True)),
        bytes=byte_count,
        mtime_ns=stat.st_mtime_ns,
        sha256=hasher.hexdigest(),
        file_identity=_identity_payload((stat.st_dev, stat.st_ino)),
    )


def _copy_source_to_candidate(source_path: Path, candidate_path: Path) -> FileFingerprint:
    with source_path.open("rb") as source_handle:
        return _exclusive_binary_create(candidate_path, source_handle)


def _assert_output_dir_unchanged(
    output_dir: Path,
    *,
    expected_identity: tuple[int, int],
    stage: str,
) -> None:
    _assert_path_matches_identity(
        output_dir,
        expected_identity=expected_identity,
        field_name="output_dir",
        code=f"output_dir_identity_changed_{stage}",
    )


def _assert_candidate_unchanged(
    candidate_path: Path,
    *,
    expected_identity: tuple[int, int],
    stage: str,
) -> None:
    _assert_path_matches_identity(
        candidate_path,
        expected_identity=expected_identity,
        field_name="candidate_duckdb_path",
        code=f"candidate_identity_changed_{stage}",
    )


def _assert_candidate_isolation(
    candidate_path: Path,
    *,
    source_path: Path,
    configured_live_path: Path,
    stage: str,
) -> None:
    _assert_distinct_file_identities(
        candidate_path,
        source_path,
        left_field_name="candidate_duckdb_path",
        right_field_name="source_duckdb_path",
        code=f"candidate_matches_source_{stage}",
    )
    _assert_distinct_file_identities(
        candidate_path,
        configured_live_path,
        left_field_name="candidate_duckdb_path",
        right_field_name="configured_live_duckdb_path",
        code=f"candidate_matches_live_{stage}",
    )


def _assert_execution_state(
    *,
    stage: str,
    output_dir: Path,
    output_identity: tuple[int, int],
    candidate_path: Path,
    candidate_identity: tuple[int, int],
    source_path: Path,
    configured_live_path: Path,
) -> None:
    _assert_output_dir_unchanged(output_dir, expected_identity=output_identity, stage=stage)
    _assert_candidate_unchanged(
        candidate_path,
        expected_identity=candidate_identity,
        stage=stage,
    )
    _assert_candidate_isolation(
        candidate_path,
        source_path=source_path,
        configured_live_path=configured_live_path,
        stage=stage,
    )


def _write_atomic_json_receipt(
    path: Path,
    payload: dict[str, object],
    *,
    parent_identity: tuple[int, int],
    allow_existing_identity: tuple[int, int] | None = None,
) -> dict[str, object]:
    temp_descriptor = None
    temp_path: Path | None = None
    temp_identity: tuple[int, int] | None = None
    path_identity: tuple[int, int] | None = None
    replaced = False
    persisted = dict(payload)
    try:
        import tempfile

        descriptor, raw_temp_path = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temp_descriptor = descriptor
        temp_path = Path(raw_temp_path)
        temp_identity = _path_identity(temp_path, field_name="receipt_temp_path")
        persisted["receipt_file_identity"] = _identity_payload(temp_identity)
        persisted["canonical_receipt_sha256"] = _receipt_sha256(persisted)
        encoded = _stable_json_dumps(persisted).encode("utf-8")
        if len(encoded) > _MAX_RECEIPT_BYTES:
            raise ShadowCandidateError("receipt_too_large")
        with os.fdopen(descriptor, "wb") as handle:
            temp_descriptor = None
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if _path_identity(path.parent, field_name="receipt_parent") != parent_identity:
            raise ShadowCandidateError("receipt_parent_identity_changed")
        if os.path.lexists(path):
            if allow_existing_identity is None:
                raise ShadowCandidateError("receipt_path_must_be_new")
            if _path_identity(path, field_name="receipt_path") != allow_existing_identity:
                raise ShadowCandidateError("receipt_existing_identity_changed")
        os.replace(temp_path, path)
        replaced = True
        path_identity = _path_identity(path, field_name="receipt_path")
        if path_identity != temp_identity:
            raise ShadowCandidateError("receipt_identity_changed_after_replace")
        if _path_identity(path.parent, field_name="receipt_parent") != parent_identity:
            raise ShadowCandidateError("receipt_parent_identity_changed")
    finally:
        if temp_descriptor is not None:
            try:
                os.close(temp_descriptor)
            except OSError:
                pass
        if temp_path is not None and not replaced:
            _remove_path_if_identity(temp_path, expected_identity=temp_identity)
    if path_identity is None:
        raise ShadowCandidateError("receipt_identity_missing")
    if path_identity != temp_identity:
        raise ShadowCandidateError("receipt_identity_changed_after_replace")
    return persisted


def _create_marker(
    path: Path,
    *,
    parent_identity: tuple[int, int],
    payload: Mapping[str, object],
) -> dict[str, object]:
    stable_payload = dict(payload)
    encoded = _stable_json_dumps(stable_payload).encode("utf-8")
    if len(encoded) > _MAX_MARKER_BYTES:
        raise ShadowCandidateError("marker_too_large")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    identity = _path_identity(path, field_name=path.name)
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise ShadowCandidateError("marker_short_write")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if _path_identity(path.parent, field_name=f"{path.name}_parent") != parent_identity:
        raise ShadowCandidateError("marker_parent_identity_changed")
    if _path_identity(path, field_name=path.name) != identity:
        raise ShadowCandidateError("marker_identity_changed")
    fingerprint = _fingerprint_file(path)
    return {
        "path": str(path.resolve(strict=True)),
        "bytes": fingerprint.bytes,
        "sha256": fingerprint.sha256,
        "file_identity": _identity_payload(identity),
        "payload": stable_payload,
        "payload_sha256": _sha256_json(stable_payload),
    }


def _parse_iso_date(value: object, *, table: str, column: str) -> dt.date:
    if isinstance(value, dt.datetime):
        value = value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = dt.date.fromisoformat(text)
        except ValueError as exc:
            raise ShadowCandidateError(
                "non_canonical_report_date_value",
                detail=f"{table}.{column} is not canonical YYYY-MM-DD",
            ) from exc
        if parsed.isoformat() != text:
            raise ShadowCandidateError("non_canonical_report_date_value")
        return parsed
    raise ShadowCandidateError(
        "unsupported_report_date_value_type",
        detail=f"{table}.{column} has unsupported report_date type {type(value)!r}",
    )


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _normalize_sql_text(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower().replace('"', "")


def _normalized_expression_list(value: object) -> tuple[str, ...]:
    try:
        parsed = ast.literal_eval(str(value))
    except (SyntaxError, ValueError) as exc:
        raise ShadowCandidateError("index_expression_list_invalid") from exc
    if not isinstance(parsed, list):
        raise ShadowCandidateError("index_expression_list_invalid")
    return tuple(_normalize_sql_text(item) for item in parsed)


def _required_text(mapping: Mapping[str, object], field_name: str) -> str:
    text = str(mapping.get(field_name) or "").strip()
    if not text:
        raise ShadowCandidateError(f"missing_{field_name}")
    return text


def _load_json_object(
    path: Path,
    *,
    field_name: str,
    max_bytes: int,
) -> dict[str, object]:
    try:
        with path.open("rb") as handle:
            encoded = handle.read(max_bytes + 1)
        if len(encoded) > max_bytes:
            raise ShadowCandidateError(f"{field_name}_too_large")
        payload = json.loads(encoded.decode("utf-8"))
    except ShadowCandidateError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ShadowCandidateError(
            f"{field_name}_invalid_json",
            detail=f"{field_name} is not valid JSON",
        ) from exc
    if not isinstance(payload, dict):
        raise ShadowCandidateError(f"{field_name}_must_be_object")
    return payload


def _fetch_bounded_catalog_rows(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    *,
    kind: str,
) -> list[tuple[object, ...]]:
    rows = conn.execute(query).fetchmany(_MAX_CATALOG_ROWS_PER_KIND + 1)
    if len(rows) > _MAX_CATALOG_ROWS_PER_KIND:
        raise ShadowCandidateError(f"catalog_{kind}_row_limit_exceeded")
    return rows


def _assert_catalog_total_limit(collections: Mapping[str, Sequence[object]]) -> None:
    total = sum(len(rows) for rows in collections.values())
    if total > _MAX_CATALOG_ROWS_TOTAL:
        raise ShadowCandidateError("catalog_metadata_row_limit_exceeded")


def _table_function_columns(
    conn: duckdb.DuckDBPyConnection,
    function_name: str,
) -> set[str]:
    allowed = {
        "duckdb_views",
    }
    if function_name not in allowed:
        raise ShadowCandidateError("catalog_table_function_not_allowed")
    cursor = conn.execute(f"select * from {function_name}() limit 0")
    return {str(column[0]) for column in cursor.description}


def _remove_path_if_identity_strict(path: Path, *, expected_identity: tuple[int, int] | None) -> None:
    if expected_identity is None:
        return
    if not os.path.lexists(path):
        raise ShadowCandidateError("expected_cleanup_path_missing", detail=str(path))
    observed = _path_identity(path, field_name="cleanup_path")
    if observed != expected_identity:
        raise ShadowCandidateError("cleanup_path_identity_changed", detail=str(path))
    try:
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()
    except OSError as exc:
        raise ShadowCandidateError(
            "cleanup_path_remove_failed",
            detail=f"{path}:{type(exc).__name__}",
        ) from exc


def _collect_table_specs(conn: duckdb.DuckDBPyConnection) -> dict[str, TableSpec]:
    table_rows = _fetch_bounded_catalog_rows(
        conn,
        """
        select schema_name, table_name
        from duckdb_tables()
        where database_name = current_database()
          and not internal
          and not temporary
        order by schema_name, table_name
        """,
        kind="table_inventory",
    )
    column_rows = _fetch_bounded_catalog_rows(
        conn,
        """
        select table_schema, table_name, column_name, data_type
        from information_schema.columns
        where table_catalog = current_database()
          and table_schema not in ('information_schema', 'pg_catalog')
        order by table_schema, table_name, ordinal_position
        """,
        kind="column_inventory",
    )
    _assert_catalog_total_limit({"tables": table_rows, "columns": column_rows})
    columns_by_table: dict[tuple[str, str], list[TableColumnSpec]] = {}
    for schema_name, table_name, column_name, data_type in column_rows:
        key = (str(schema_name), str(table_name))
        columns_by_table.setdefault(key, []).append(
            TableColumnSpec(name=str(column_name), duckdb_type=str(data_type))
        )
    inventory: dict[str, TableSpec] = {}
    for schema_name, table_name in table_rows:
        schema_text = str(schema_name)
        if schema_text in _INTERNAL_SCHEMAS:
            continue
        key = (schema_text, str(table_name))
        columns = tuple(columns_by_table.get(key, []))
        inventory[f"{schema_text}.{table_name}"] = TableSpec(
            schema=schema_text,
            name=str(table_name),
            columns=columns,
        )
    return inventory


def _summarize_table(
    conn: duckdb.DuckDBPyConnection,
    spec: TableSpec,
    *,
    temp_root: Path,
    side: str,
    report_date: dt.date,
) -> dict[str, object]:
    columns = ", ".join(_quote_identifier(column.name) for column in spec.columns)
    table_ref = f"{_quote_identifier(spec.schema)}.{_quote_identifier(spec.name)}"
    cursor = conn.execute(f"select {columns} from {table_ref}")
    full = _SpoolSorter(temp_root, f"{side}-{spec.schema}-{spec.name}-full")
    is_target_table = spec.key in _TARGET_TABLES
    target = (
        _SpoolSorter(temp_root, f"{side}-{spec.schema}-{spec.name}-target")
        if is_target_table
        else None
    )
    non_target = (
        _SpoolSorter(temp_root, f"{side}-{spec.schema}-{spec.name}-non-target")
        if is_target_table
        else None
    )
    report_date_index = None
    if is_target_table:
        report_date_index = next(
            (index for index, column in enumerate(spec.columns) if column.name == "report_date"),
            None,
        )
        if report_date_index is None:
            raise ShadowCandidateError("target_table_missing_report_date", detail=spec.key)
        report_date_type = spec.columns[report_date_index].duckdb_type.upper()
        if report_date_type not in _ALLOWED_REPORT_DATE_TYPES:
            raise ShadowCandidateError(
                "target_table_invalid_report_date_type",
                detail=f"{spec.key}:{report_date_type}",
            )

    while True:
        rows = cursor.fetchmany(2_048)
        if not rows:
            break
        for row in rows:
            digest = canonical_row_digest(row)
            full.add(digest)
            if report_date_index is not None:
                row_date = _parse_iso_date(
                    row[report_date_index],
                    table=spec.key,
                    column="report_date",
                )
                if row_date == report_date:
                    assert target is not None
                    target.add(digest)
                else:
                    assert non_target is not None
                    non_target.add(digest)

    result: dict[str, object] = {
        "table_key": spec.key,
        "schema": spec.schema,
        "table_name": spec.name,
        "columns": [column.as_receipt() for column in spec.columns],
        "full_table": full.finish().as_receipt(),
    }
    if target is not None and non_target is not None:
        result["target_report_date"] = {
            "date": report_date.isoformat(),
            **target.finish().as_receipt(),
        }
        result["non_target_report_date"] = non_target.finish().as_receipt()
    return result


def _capture_persistent_catalog(conn: duckdb.DuckDBPyConnection) -> dict[str, object]:
    views_columns = _table_function_columns(conn, "duckdb_views")
    required_view_columns = {
        "database_name",
        "schema_name",
        "view_name",
        "column_count",
        "sql",
        "internal",
        "temporary",
    }
    missing_view_columns = required_view_columns - views_columns
    if missing_view_columns:
        raise ShadowCandidateError("catalog_views_schema_unsupported")
    view_bound_expression = "is_bound" if "is_bound" in views_columns else "cast(null as boolean)"

    schemas = _fetch_bounded_catalog_rows(
        conn,
        """
        select schema_name, coalesce(sql, '')
        from duckdb_schemas()
        where database_name = current_database()
        order by schema_name
        """,
        kind="schemas",
    )
    tables = _fetch_bounded_catalog_rows(
        conn,
        """
        select schema_name, table_name, has_primary_key, column_count, index_count,
               check_constraint_count, coalesce(sql, '')
        from duckdb_tables()
        where database_name = current_database()
          and not internal
          and not temporary
        order by schema_name, table_name
        """,
        kind="tables",
    )
    views = _fetch_bounded_catalog_rows(
        conn,
        f"""
        select schema_name, view_name, column_count, coalesce(sql, ''),
               {view_bound_expression} as is_bound
        from duckdb_views()
        where database_name = current_database()
          and not internal
          and not temporary
        order by schema_name, view_name
        """,
        kind="views",
    )
    columns = _fetch_bounded_catalog_rows(
        conn,
        """
        select table_schema, table_name, ordinal_position, column_name, data_type,
               coalesce(column_default, ''), is_nullable
        from information_schema.columns
        where table_catalog = current_database()
          and table_schema not in ('information_schema', 'pg_catalog')
        order by table_schema, table_name, ordinal_position
        """,
        kind="columns",
    )
    constraints = _fetch_bounded_catalog_rows(
        conn,
        """
        select schema_name, table_name, constraint_index, constraint_type,
               coalesce(constraint_text, ''), coalesce(expression, ''),
               constraint_column_indexes, constraint_column_names,
               constraint_name, coalesce(referenced_table, ''), referenced_column_names
        from duckdb_constraints()
        where database_name = current_database()
        order by schema_name, table_name, constraint_index, constraint_name
        """,
        kind="constraints",
    )
    indexes = _fetch_bounded_catalog_rows(
        conn,
        """
        select schema_name, index_name, table_name,
               is_unique, is_primary, coalesce(expressions, ''), coalesce(sql, '')
        from duckdb_indexes()
        where database_name = current_database()
        order by schema_name, table_name, index_name
        """,
        kind="indexes",
    )
    sequences = _fetch_bounded_catalog_rows(
        conn,
        """
        select schema_name, sequence_name, start_value, min_value, max_value,
               increment_by, cycle, coalesce(sql, '')
        from duckdb_sequences()
        where database_name = current_database()
          and not temporary
        order by schema_name, sequence_name
        """,
        kind="sequences",
    )
    types = _fetch_bounded_catalog_rows(
        conn,
        """
        select schema_name, type_name, logical_type, coalesce(type_category, ''), coalesce(labels, [])
        from duckdb_types()
        where database_name = current_database()
          and not internal
        order by schema_name, type_name
        """,
        kind="types",
    )
    functions = _fetch_bounded_catalog_rows(
        conn,
        """
        select schema_name, function_name, function_type, coalesce(return_type, ''),
               coalesce(parameters, []), coalesce(parameter_types, []),
               coalesce(varargs, ''), coalesce(macro_definition, ''),
               coalesce(alias_of, ''), coalesce(has_side_effects, false),
               coalesce(stability, '')
        from duckdb_functions()
        where database_name = current_database()
          and not internal
        order by schema_name, function_name, function_type, return_type
        """,
        kind="functions",
    )
    catalog_rows = {
        "schemas": schemas,
        "tables": tables,
        "views": views,
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
        "sequences": sequences,
        "types": types,
        "functions": functions,
    }
    _assert_catalog_total_limit(catalog_rows)
    payload = {
        "capture_capabilities": {
            "duckdb_version": str(duckdb.__version__),
            "views_is_bound_available": "is_bound" in views_columns,
        },
        "schemas": [
            {"schema_name": str(schema_name), "sql": str(sql)}
            for schema_name, sql in schemas
        ],
        "tables": [
            {
                "schema_name": str(schema_name),
                "table_name": str(table_name),
                "has_primary_key": bool(has_primary_key),
                "column_count": int(column_count),
                "index_count": int(index_count),
                "check_constraint_count": int(check_constraint_count),
                "sql": str(sql),
            }
            for schema_name, table_name, has_primary_key, column_count, index_count, check_constraint_count, sql in tables
        ],
        "views": [
            {
                "schema_name": str(schema_name),
                "view_name": str(view_name),
                "column_count": int(column_count) if column_count is not None else None,
                "sql": str(sql),
                "is_bound": bool(is_bound) if is_bound is not None else None,
            }
            for schema_name, view_name, column_count, sql, is_bound in views
        ],
        "columns": [
            {
                "table_schema": str(table_schema),
                "table_name": str(table_name),
                "ordinal_position": int(ordinal_position),
                "column_name": str(column_name),
                "data_type": str(data_type),
                "column_default": str(column_default),
                "is_nullable": str(is_nullable),
            }
            for table_schema, table_name, ordinal_position, column_name, data_type, column_default, is_nullable in columns
        ],
        "constraints": [
            {
                "schema_name": str(schema_name),
                "table_name": str(table_name),
                "constraint_index": int(constraint_index),
                "constraint_type": str(constraint_type),
                "constraint_text": str(constraint_text),
                "expression": str(expression),
                "constraint_column_indexes": [int(item) for item in constraint_column_indexes],
                "constraint_column_names": [str(item) for item in constraint_column_names],
                "constraint_name": str(constraint_name),
                "referenced_table": str(referenced_table),
                "referenced_column_names": [str(item) for item in referenced_column_names],
            }
            for (
                schema_name,
                table_name,
                constraint_index,
                constraint_type,
                constraint_text,
                expression,
                constraint_column_indexes,
                constraint_column_names,
                constraint_name,
                referenced_table,
                referenced_column_names,
            ) in constraints
        ],
        "indexes": [
            {
                "schema_name": str(schema_name),
                "index_name": str(index_name),
                "table_name": str(table_name),
                "is_unique": bool(is_unique),
                "is_primary": bool(is_primary),
                "expressions": str(expressions),
                "sql": str(sql),
            }
            for schema_name, index_name, table_name, is_unique, is_primary, expressions, sql in indexes
        ],
        "sequences": [
            {
                "schema_name": str(schema_name),
                "sequence_name": str(sequence_name),
                "start_value": int(start_value),
                "min_value": int(min_value),
                "max_value": int(max_value),
                "increment_by": int(increment_by),
                "cycle": bool(cycle),
                "sql": str(sql),
            }
            for schema_name, sequence_name, start_value, min_value, max_value, increment_by, cycle, sql in sequences
        ],
        "types": [
            {
                "schema_name": str(schema_name),
                "type_name": str(type_name),
                "logical_type": str(logical_type),
                "type_category": str(type_category),
                "labels": [str(item) for item in labels],
            }
            for schema_name, type_name, logical_type, type_category, labels in types
        ],
        "functions": [
            {
                "schema_name": str(schema_name),
                "function_name": str(function_name),
                "function_type": str(function_type),
                "return_type": str(return_type),
                "parameters": [str(item) for item in parameters],
                "parameter_types": [str(item) for item in parameter_types],
                "varargs": str(varargs),
                "macro_definition": str(macro_definition),
                "alias_of": str(alias_of),
                "has_side_effects": bool(has_side_effects) if has_side_effects is not None else None,
                "stability": str(stability),
            }
            for (
                schema_name,
                function_name,
                function_type,
                return_type,
                parameters,
                parameter_types,
                varargs,
                macro_definition,
                alias_of,
                has_side_effects,
                stability,
            ) in functions
        ],
    }
    counts = {
        section: len(items)
        for section, items in payload.items()
        if isinstance(items, list)
    }
    return {"payload": payload, "sha256": _sha256_json(payload), "counts": counts}


def _snapshot_database(
    path: Path,
    *,
    temp_root: Path,
    side: str,
    report_date: dt.date,
) -> dict[str, object]:
    fingerprint_before = _fingerprint_file(path)
    # The receipt fingerprints this exact file, not an inherited online snapshot.
    with active_read_scope(), read_only_connection(str(path)) as conn:
        table_specs = _collect_table_specs(conn)
        main_catalog = capture_main_catalog(conn)
        persistent_catalog = _capture_persistent_catalog(conn)
        tables = {
            key: _summarize_table(
                conn,
                table_specs[key],
                temp_root=temp_root,
                side=side,
                report_date=report_date,
            )
            for key in sorted(table_specs)
        }
    fingerprint_after = _fingerprint_file(path)
    if fingerprint_before.sha256 != fingerprint_after.sha256:
        raise ShadowCandidateError("readonly_snapshot_changed_source")
    return {
        "fingerprint": fingerprint_after.as_receipt(),
        "main_catalog_sha256": catalog_snapshot_sha256(main_catalog),
        "main_catalog_counts": {
            "objects": len(main_catalog.objects),
            "columns": len(main_catalog.columns),
            "indexes": len(main_catalog.indexes),
        },
        "main_catalog_indexes": [
            {
                "schema": schema_name,
                "index_name": index_name,
                "table_name": table_name,
                "is_unique": is_unique,
                "is_primary": is_primary,
                "expressions": expressions,
            }
            for schema_name, index_name, table_name, is_unique, is_primary, expressions in main_catalog.indexes
        ],
        "persistent_catalog": persistent_catalog,
        "tables": tables,
    }


def _compare_section(source_section: Mapping[str, object], candidate_section: Mapping[str, object]) -> dict[str, object]:
    return {
        "source": dict(source_section),
        "candidate": dict(candidate_section),
        "matched": dict(source_section) == dict(candidate_section),
    }


def _validate_target_table_proof(snapshot: Mapping[str, object]) -> dict[str, object]:
    persistent_catalog = snapshot.get("persistent_catalog")
    if not isinstance(persistent_catalog, Mapping):
        raise ShadowCandidateError("persistent_catalog_missing")
    index_rows = persistent_catalog.get("payload", {}).get("indexes") if isinstance(persistent_catalog.get("payload"), Mapping) else None
    if not isinstance(index_rows, list):
        raise ShadowCandidateError("persistent_catalog_indexes_missing")
    proofs: dict[str, object] = {}
    for table_key, expectation in _TARGET_TABLE_HINTS.items():
        table_name = table_key.split(".", 1)[1]
        matches = []
        for row in index_rows:
            if not isinstance(row, Mapping):
                continue
            if str(row.get("schema_name")) != "main" or str(row.get("table_name")) != table_name:
                continue
            if str(row.get("index_name") or "") != expectation["index_name"]:
                continue
            if not bool(row.get("is_unique")):
                continue
            if _normalized_expression_list(row.get("expressions")) != tuple(
                _normalize_sql_text(item) for item in expectation["expressions"]
            ):
                continue
            matches.append(
                {
                    "index_name": str(row.get("index_name") or ""),
                    "expressions": str(row.get("expressions") or ""),
                    "is_unique": bool(row.get("is_unique")),
                    "is_primary": bool(row.get("is_primary")),
                    "sql": str(row.get("sql") or ""),
                }
            )
        if not matches:
            raise ShadowCandidateError("target_table_natural_key_proof_missing", detail=table_key)
        proofs[table_key] = matches
    return proofs


def _compare_database_snapshots(
    source_snapshot: Mapping[str, object],
    candidate_snapshot: Mapping[str, object],
    *,
    report_date: str,
) -> dict[str, object]:
    source_tables = source_snapshot["tables"]
    candidate_tables = candidate_snapshot["tables"]
    if not isinstance(source_tables, Mapping) or not isinstance(candidate_tables, Mapping):
        raise ShadowCandidateError("table_snapshot_shape_invalid")
    if set(source_tables) != set(candidate_tables):
        raise ShadowCandidateError("table_inventory_changed")
    table_identities: list[dict[str, object]] = []
    unexpected_drift: list[str] = []
    for table_key in sorted(source_tables):
        source_entry = source_tables[table_key]
        candidate_entry = candidate_tables[table_key]
        if not isinstance(source_entry, Mapping) or not isinstance(candidate_entry, Mapping):
            raise ShadowCandidateError("table_snapshot_entry_invalid")
        identity = {
            "table_key": table_key,
            "schema": source_entry["schema"],
            "table_name": source_entry["table_name"],
            "columns": source_entry["columns"],
            "full_table": _compare_section(
                source_entry["full_table"],
                candidate_entry["full_table"],
            ),
        }
        if table_key in _TARGET_TABLES:
            target_identity = _compare_section(
                source_entry["target_report_date"],
                candidate_entry["target_report_date"],
            )
            non_target_identity = _compare_section(
                source_entry["non_target_report_date"],
                candidate_entry["non_target_report_date"],
            )
            identity["target_report_date"] = target_identity
            identity["non_target_report_date"] = non_target_identity
            if int(identity["target_report_date"]["source"]["row_count"]) <= 0:
                unexpected_drift.append(f"source_target_empty:{table_key}")
            if int(identity["target_report_date"]["candidate"]["row_count"]) <= 0:
                unexpected_drift.append(f"candidate_target_empty:{table_key}")
            if not non_target_identity["matched"]:
                unexpected_drift.append(f"non_target:{table_key}")
        elif not identity["full_table"]["matched"]:
            unexpected_drift.append(f"full_table:{table_key}")
        table_identities.append(identity)
    main_catalog_identity = {
        "source_sha256": source_snapshot["main_catalog_sha256"],
        "candidate_sha256": candidate_snapshot["main_catalog_sha256"],
        "matched": source_snapshot["main_catalog_sha256"] == candidate_snapshot["main_catalog_sha256"],
        "source_counts": source_snapshot["main_catalog_counts"],
        "candidate_counts": candidate_snapshot["main_catalog_counts"],
    }
    if not main_catalog_identity["matched"]:
        unexpected_drift.append("main_catalog")
    source_persistent = source_snapshot["persistent_catalog"]
    candidate_persistent = candidate_snapshot["persistent_catalog"]
    persistent_catalog_identity = {
        "source_sha256": source_persistent["sha256"],
        "candidate_sha256": candidate_persistent["sha256"],
        "matched": source_persistent["sha256"] == candidate_persistent["sha256"],
        "source_counts": source_persistent["counts"],
        "candidate_counts": candidate_persistent["counts"],
    }
    if not persistent_catalog_identity["matched"]:
        unexpected_drift.append("persistent_catalog")
    return {
        "report_date": report_date,
        "main_catalog_identity": main_catalog_identity,
        "persistent_catalog_identity": persistent_catalog_identity,
        "table_identities": table_identities,
        "unexpected_drift": sorted(unexpected_drift),
    }


def _safe_schema_receipt(receipt: Mapping[str, object]) -> dict[str, object]:
    registry = receipt.get("registry")
    target = receipt.get("target")
    if not isinstance(registry, Mapping) or not isinstance(target, Mapping):
        raise ShadowCandidateError("schema_assertion_shape_invalid")
    source_digest = registry.get("source_digest")
    schema_fingerprint = registry.get("schema_fingerprint")
    if not isinstance(source_digest, Mapping) or not isinstance(schema_fingerprint, Mapping):
        raise ShadowCandidateError("schema_assertion_shape_invalid")
    return {
        "receipt_schema": str(receipt.get("receipt_schema") or ""),
        "status": str(receipt.get("status") or ""),
        "receipt_sha256": str(receipt.get("receipt_sha256") or ""),
        "target": {
            "database_role": str(target.get("database_role") or ""),
            "read_only": bool(target.get("read_only")),
        },
        "registry": {
            "source_digest": {
                "kind": str(source_digest.get("kind") or ""),
                "algorithm": str(source_digest.get("algorithm") or ""),
                "sha256": str(source_digest.get("sha256") or ""),
            },
            "schema_fingerprint": {
                "kind": str(schema_fingerprint.get("kind") or ""),
                "algorithm": str(schema_fingerprint.get("algorithm") or ""),
                "expected_sha256": str(schema_fingerprint.get("expected_sha256") or ""),
                "observed_sha256": str(schema_fingerprint.get("observed_sha256") or ""),
            },
        },
        "findings": [],
    }


def _validate_schema_receipt(receipt: object) -> dict[str, object]:
    if not isinstance(receipt, Mapping):
        raise ShadowCandidateError("schema_assertion_shape_invalid")
    if str(receipt.get("receipt_schema") or "").strip() != _SCHEMA_RECEIPT_SCHEMA:
        raise ShadowCandidateError("schema_assertion_receipt_schema_invalid")
    status = str(receipt.get("status") or "").strip()
    if status != "passed":
        raise ShadowCandidateError("schema_assertion_failed")
    findings = receipt.get("findings")
    if not isinstance(findings, list):
        raise ShadowCandidateError("schema_assertion_findings_shape_invalid")
    if findings:
        raise ShadowCandidateError("schema_assertion_has_findings")
    target = receipt.get("target")
    if not isinstance(target, Mapping):
        raise ShadowCandidateError("schema_assertion_target_missing")
    if str(target.get("database_role") or "").strip() != "duckdb-main":
        raise ShadowCandidateError("schema_assertion_target_role_invalid")
    if target.get("read_only") is not True:
        raise ShadowCandidateError("schema_assertion_target_read_only_invalid")
    registry = receipt.get("registry")
    if not isinstance(registry, Mapping):
        raise ShadowCandidateError("schema_assertion_registry_missing")
    source_digest = registry.get("source_digest")
    if not isinstance(source_digest, Mapping):
        raise ShadowCandidateError("schema_assertion_source_digest_missing")
    if str(source_digest.get("kind") or "").strip() != "registry_sources":
        raise ShadowCandidateError("schema_assertion_source_digest_kind_invalid")
    if str(source_digest.get("algorithm") or "").strip() != "sha256":
        raise ShadowCandidateError("schema_assertion_source_digest_algorithm_invalid")
    if not _SHA256_RE.fullmatch(str(source_digest.get("sha256") or "").strip()):
        raise ShadowCandidateError("schema_assertion_source_digest_sha_invalid")
    schema_fingerprint = registry.get("schema_fingerprint")
    if not isinstance(schema_fingerprint, Mapping):
        raise ShadowCandidateError("schema_assertion_schema_fingerprint_missing")
    if str(schema_fingerprint.get("kind") or "").strip() != "governed_catalog_subset":
        raise ShadowCandidateError("schema_assertion_schema_fingerprint_kind_invalid")
    if str(schema_fingerprint.get("algorithm") or "").strip() != "sha256":
        raise ShadowCandidateError("schema_assertion_schema_fingerprint_algorithm_invalid")
    expected_sha = str(schema_fingerprint.get("expected_sha256") or "").strip()
    observed_sha = str(schema_fingerprint.get("observed_sha256") or "").strip()
    if not _SHA256_RE.fullmatch(expected_sha) or not _SHA256_RE.fullmatch(observed_sha):
        raise ShadowCandidateError("schema_assertion_schema_fingerprint_sha_invalid")
    if expected_sha != observed_sha:
        raise ShadowCandidateError("schema_assertion_schema_fingerprint_mismatch")
    observed_receipt_sha = str(receipt.get("receipt_sha256") or "").strip()
    if not _SHA256_RE.fullmatch(observed_receipt_sha):
        raise ShadowCandidateError("schema_assertion_receipt_sha_invalid")
    normalized = dict(receipt)
    if observed_receipt_sha != _sha256_json({k: v for k, v in normalized.items() if k != "receipt_sha256"}):
        raise ShadowCandidateError("schema_assertion_receipt_sha_mismatch")
    return _safe_schema_receipt(receipt)


def _result_binding_payload(result: Mapping[str, object]) -> dict[str, object]:
    payload = result.get("payload")
    run_payload = payload.get("run") if isinstance(payload, Mapping) else None
    return {
        "status": str(result.get("status") or ""),
        "run_id": str(result.get("run_id") or ""),
        "report_date": str(result.get("report_date") or ""),
        "job_name": str(run_payload.get("job_name") or "") if isinstance(run_payload, Mapping) else "",
        "cache_key": str(result.get("cache_key") or ""),
        "cache_version": str(result.get("cache_version") or ""),
        "source_version": str(result.get("source_version") or ""),
        "rule_version": str(result.get("rule_version") or ""),
        "vendor_version": str(result.get("vendor_version") or ""),
        "lock": str(result.get("lock") or ""),
    }


def _fixed_income_module_version(
    descriptor: FormalComputeModuleDescriptor,
) -> MaterializeModuleVersion:
    for version in (
        FIXED_INCOME_VERSION_SET.bond_analytics,
        FIXED_INCOME_VERSION_SET.risk_tensor,
    ):
        if descriptor == version.descriptor:
            return version
    raise ShadowCandidateError("fixed_income_descriptor_not_registered")


def _expected_runtime_lineage(
    descriptor: FormalComputeModuleDescriptor,
    *,
    run_id: str,
    report_date: str,
    source_version: str,
    vendor_version: str,
) -> dict[str, object]:
    version = _fixed_income_module_version(descriptor)
    try:
        return version.emit_runtime_lineage(
            run_id=run_id,
            report_date=report_date,
            source_version=source_version,
            vendor_version=vendor_version,
        )
    except ValueError as exc:
        raise ShadowCandidateError(
            "fixed_income_runtime_lineage_invalid",
            detail=str(exc),
        ) from exc


def _expected_manifest_min_lineage(
    descriptor: FormalComputeModuleDescriptor,
    *,
    run_id: str,
    report_date: str,
    source_version: str,
    vendor_version: str,
) -> dict[str, object]:
    version = _fixed_income_module_version(descriptor)
    try:
        return version.emit_manifest_min_lineage(
            run_id=run_id,
            report_date=report_date,
            source_version=source_version,
            vendor_version=vendor_version,
        )
    except ValueError as exc:
        raise ShadowCandidateError(
            "fixed_income_manifest_lineage_invalid",
            detail=str(exc),
        ) from exc


def _composite_source_binding_matches(source_version: str, component_prefix: str) -> bool:
    return source_version == component_prefix or source_version.startswith(f"{component_prefix}__")


def _validate_task_result(
    task_name: str,
    result: object,
    *,
    descriptor: FormalComputeModuleDescriptor,
    expected_job_name: str,
    expected_run_id: str,
    expected_report_date: str,
    required_bond_source_version: str | None = None,
) -> tuple[dict[str, object], str]:
    if not isinstance(result, Mapping):
        raise ShadowCandidateError(f"{task_name}_result_shape_invalid")
    binding = _result_binding_payload(result)
    if binding["status"] != "completed":
        raise ShadowCandidateError(f"{task_name}_result_status_invalid", detail=str(binding["status"]))
    if binding["run_id"] != expected_run_id:
        raise ShadowCandidateError(f"{task_name}_run_id_mismatch")
    if binding["report_date"] != expected_report_date:
        raise ShadowCandidateError(f"{task_name}_report_date_mismatch")
    if binding["job_name"] != expected_job_name:
        raise ShadowCandidateError(f"{task_name}_job_name_mismatch")
    if binding["cache_key"] != descriptor.cache_key:
        raise ShadowCandidateError(f"{task_name}_cache_key_mismatch")
    if binding["cache_version"] != descriptor.stable_output_version:
        raise ShadowCandidateError(f"{task_name}_cache_version_mismatch")
    if binding["rule_version"] != descriptor.rule_version:
        raise ShadowCandidateError(f"{task_name}_rule_version_mismatch")
    if binding["lock"] != descriptor.lock_key:
        raise ShadowCandidateError(f"{task_name}_lock_mismatch")
    if not binding["source_version"]:
        raise ShadowCandidateError(f"{task_name}_source_version_missing")
    if not binding["vendor_version"]:
        raise ShadowCandidateError(f"{task_name}_vendor_version_missing")
    payload = result.get("payload")
    if not isinstance(payload, Mapping):
        raise ShadowCandidateError(f"{task_name}_payload_missing")
    if payload.get("error") not in (None, {}):
        raise ShadowCandidateError(f"{task_name}_payload_error_present")
    run_payload = payload.get("run")
    if not isinstance(run_payload, Mapping):
        raise ShadowCandidateError(f"{task_name}_payload_run_missing")
    lineage_payload = payload.get("lineage")
    if not isinstance(lineage_payload, Mapping):
        raise ShadowCandidateError(f"{task_name}_payload_lineage_missing")
    if str(run_payload.get("status") or "") != "completed":
        raise ShadowCandidateError(f"{task_name}_payload_run_status_invalid")
    if str(run_payload.get("job_name") or "") != expected_job_name:
        raise ShadowCandidateError(f"{task_name}_payload_job_name_mismatch")
    if str(run_payload.get("run_id") or "") != expected_run_id:
        raise ShadowCandidateError(f"{task_name}_payload_run_id_mismatch")
    if str(run_payload.get("report_date") or "") != expected_report_date:
        raise ShadowCandidateError(f"{task_name}_payload_report_date_mismatch")
    if str(run_payload.get("lock") or "") != descriptor.lock_key:
        raise ShadowCandidateError(f"{task_name}_payload_lock_mismatch")
    expected_lineage = _expected_runtime_lineage(
        descriptor,
        run_id=expected_run_id,
        report_date=expected_report_date,
        source_version=str(binding["source_version"]),
        vendor_version=str(binding["vendor_version"]),
    )
    for field_name, expected_value in expected_lineage.items():
        if lineage_payload.get(field_name) != expected_value:
            raise ShadowCandidateError(f"{task_name}_payload_{field_name}_mismatch")
    if required_bond_source_version is not None:
        required_component_prefix = f"sv_risk_tensor__{required_bond_source_version}"
        if not _composite_source_binding_matches(
            str(binding["source_version"]),
            required_component_prefix,
        ):
            raise ShadowCandidateError("risk_tensor_upstream_lineage_mismatch")
    safe_payload = {
        **binding,
        "payload_sha256": _sha256_json(payload),
        "result_sha256": _sha256_json(dict(result)),
    }
    return safe_payload, binding["source_version"]


def _load_jsonl_records(path: Path, *, field_name: str) -> list[dict[str, object]]:
    if not path.is_file():
        raise ShadowCandidateError(f"{field_name}_missing")
    rows: list[dict[str, object]] = []
    total_bytes = 0
    try:
        with path.open("rb") as handle:
            while True:
                encoded_line = handle.readline(_MAX_JSONL_LINE_BYTES + 1)
                if not encoded_line:
                    break
                line_number = len(rows) + 1
                if len(encoded_line) > _MAX_JSONL_LINE_BYTES:
                    raise ShadowCandidateError(
                        f"{field_name}_line_too_large",
                        detail=f"{path.name}:{line_number}",
                    )
                total_bytes += len(encoded_line)
                if total_bytes > _MAX_JSONL_TOTAL_BYTES:
                    raise ShadowCandidateError(f"{field_name}_too_large")
                if line_number > _MAX_JSONL_LINES:
                    raise ShadowCandidateError(f"{field_name}_line_limit_exceeded")
                try:
                    line = encoded_line.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ShadowCandidateError(
                        f"{field_name}_invalid_jsonl",
                        detail=f"{path.name}:{line_number}",
                    ) from exc
                if not line.strip():
                    raise ShadowCandidateError(
                        f"{field_name}_blank_line",
                        detail=f"{path.name}:{line_number}",
                    )
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ShadowCandidateError(
                        f"{field_name}_invalid_jsonl",
                        detail=f"{path.name}:{line_number}",
                    ) from exc
                if not isinstance(payload, dict):
                    raise ShadowCandidateError(
                        f"{field_name}_line_not_object",
                        detail=f"{path.name}:{line_number}",
                    )
                rows.append(payload)
    except ShadowCandidateError:
        raise
    except OSError as exc:
        raise ShadowCandidateError(f"{field_name}_read_failed") from exc
    if not rows:
        raise ShadowCandidateError(f"{field_name}_empty")
    return rows


def _validate_governance_build_run_records(
    records: list[dict[str, object]],
    *,
    job_name: str,
    run_id: str,
    report_date: str,
    cache_key: str,
    cache_version: str,
    source_version: str,
    vendor_version: str,
    rule_version: str,
    descriptor: FormalComputeModuleDescriptor,
) -> dict[str, object]:
    run_records = [
        row
        for row in records
        if str(row.get("job_name") or "") == job_name
        and str(row.get("run_id") or "") == run_id
        and str(row.get("report_date") or "") == report_date
        and str(row.get("cache_key") or "") == cache_key
    ]
    for row in run_records:
        if "phase" in row:
            phase = row["phase"]
            if not isinstance(phase, str) or not phase.strip():
                raise ShadowCandidateError("governance_build_run_phase_invalid")
        elif any(field_name.startswith("phase_") for field_name in row):
            raise ShadowCandidateError("governance_build_run_phase_invalid")
    matching = [row for row in run_records if "phase" not in row]
    if len(matching) != 3:
        raise ShadowCandidateError("governance_build_run_sequence_invalid")
    statuses = [str(row.get("status") or "") for row in matching]
    if statuses != ["queued", "running", "completed"]:
        raise ShadowCandidateError("governance_build_run_sequence_invalid")
    lifecycle_status: str | None = None
    phase_records = []
    for row in run_records:
        if str(row.get("cache_version") or "") != descriptor.stable_output_version:
            raise ShadowCandidateError("governance_build_run_cache_version_mismatch")
        if str(row.get("lock") or "") != descriptor.lock_key:
            raise ShadowCandidateError("governance_build_run_lock_mismatch")
        if "phase" not in row:
            lifecycle_status = str(row.get("status") or "")
            continue
        phase = row["phase"]
        # Bond phase diagnostics share the stream but are not lifecycle transitions.
        if (
            descriptor.module_name != "bond_analytics"
            or lifecycle_status != "running"
            or str(row.get("status") or "") != "running"
            or phase not in (
                "write_access", "curve_prepare", "source_read",
                "curve_validation", "compute", "write",
            )
            or row.get("phase_status") not in ("running", "completed")
            or any(
                not str(row.get(field_name) or "").strip()
                for field_name in ("queued_at", "started_at", "phase_started_at")
            )
            or (
                row.get("phase_status") == "completed"
                and not str(row.get("phase_finished_at") or "").strip()
            )
        ):
            raise ShadowCandidateError("governance_build_run_phase_invalid")
        if str(row.get("rule_version") or "") != descriptor.rule_version:
            raise ShadowCandidateError("governance_build_run_phase_rule_version_mismatch")
        phase_records.append(row)
    for row in [*matching[:2], *phase_records]:
        if str(row.get("source_version") or "") != descriptor.running_source_version:
            raise ShadowCandidateError("governance_build_run_running_source_version_mismatch")
        if str(row.get("vendor_version") or "") != descriptor.vendor_version:
            raise ShadowCandidateError("governance_build_run_running_vendor_version_mismatch")
    completed = matching[-1]
    if str(completed.get("cache_version") or "") != cache_version:
        raise ShadowCandidateError("governance_build_run_completed_cache_version_mismatch")
    if str(completed.get("source_version") or "") != source_version:
        raise ShadowCandidateError("governance_build_run_completed_source_version_mismatch")
    if str(completed.get("vendor_version") or "") != vendor_version:
        raise ShadowCandidateError("governance_build_run_completed_vendor_version_mismatch")
    if str(completed.get("rule_version") or "") != rule_version:
        raise ShadowCandidateError("governance_build_run_completed_rule_version_mismatch")
    if not str(matching[0].get("queued_at") or "").strip():
        raise ShadowCandidateError("governance_build_run_queued_at_missing")
    if not str(matching[1].get("started_at") or "").strip():
        raise ShadowCandidateError("governance_build_run_started_at_missing")
    if not str(completed.get("finished_at") or "").strip():
        raise ShadowCandidateError("governance_build_run_finished_at_missing")
    return {
        "record_count": len(matching),
        "statuses": statuses,
    }


def _validate_governance_manifest_records(
    records: list[dict[str, object]],
    *,
    result_payload: Mapping[str, object],
    result_summary: Mapping[str, object],
    descriptor: FormalComputeModuleDescriptor,
) -> dict[str, object]:
    matching = [
        row
        for row in records
        if str(row.get("run_id") or "") == str(result_summary["run_id"])
        and str(row.get("report_date") or "") == str(result_summary["report_date"])
        and str(row.get("cache_key") or "") == str(result_summary["cache_key"])
    ]
    if len(matching) != 1:
        raise ShadowCandidateError("governance_manifest_cardinality_invalid")
    record = matching[0]
    lineage = result_payload.get("lineage")
    if not isinstance(lineage, Mapping):
        raise ShadowCandidateError("result_lineage_missing_for_governance")
    expected_runtime_lineage = _expected_runtime_lineage(
        descriptor,
        run_id=str(result_summary["run_id"]),
        report_date=str(result_summary["report_date"]),
        source_version=str(result_summary["source_version"]),
        vendor_version=str(result_summary["vendor_version"]),
    )
    if dict(lineage) != expected_runtime_lineage:
        raise ShadowCandidateError("result_lineage_descriptor_mismatch")
    expected_top_level = dict(expected_runtime_lineage)
    for field_name, expected_value in expected_top_level.items():
        if record.get(field_name) != expected_value:
            raise ShadowCandidateError(
                f"governance_manifest_{field_name}_mismatch",
                detail=field_name,
            )
    expected_min_lineage = _expected_manifest_min_lineage(
        descriptor,
        run_id=str(result_summary["run_id"]),
        report_date=str(result_summary["report_date"]),
        source_version=str(result_summary["source_version"]),
        vendor_version=str(result_summary["vendor_version"]),
    )
    if record.get("lineage") != expected_min_lineage:
        raise ShadowCandidateError("governance_manifest_lineage_mismatch")
    return {"record_count": 1}


def _validate_governance_records(
    governance_dir: Path,
    *,
    result_summary: Mapping[str, object],
    result_raw: Mapping[str, object],
    descriptor: FormalComputeModuleDescriptor,
) -> dict[str, object]:
    build_run_path = governance_dir / _CACHE_BUILD_RUN_FILENAME
    manifest_path = governance_dir / _CACHE_MANIFEST_FILENAME
    build_records = _load_jsonl_records(build_run_path, field_name="cache_build_run_stream")
    manifest_records = _load_jsonl_records(manifest_path, field_name="cache_manifest_stream")
    payload = result_raw.get("payload")
    if not isinstance(payload, Mapping):
        raise ShadowCandidateError("result_payload_missing_for_governance")
    build_summary = _validate_governance_build_run_records(
        build_records,
        job_name=str(result_summary["job_name"]),
        run_id=str(result_summary["run_id"]),
        report_date=str(result_summary["report_date"]),
        cache_key=str(result_summary["cache_key"]),
        cache_version=str(result_summary["cache_version"]),
        source_version=str(result_summary["source_version"]),
        vendor_version=str(result_summary["vendor_version"]),
        rule_version=str(result_summary["rule_version"]),
        descriptor=descriptor,
    )
    manifest_summary = _validate_governance_manifest_records(
        manifest_records,
        result_payload=payload,
        result_summary=result_summary,
        descriptor=descriptor,
    )
    return {
        "cache_build_run": {
            "path": str(build_run_path.resolve(strict=True)),
            "sha256": _fingerprint_file(build_run_path).sha256,
            **build_summary,
        },
        "cache_manifest": {
            "path": str(manifest_path.resolve(strict=True)),
            "sha256": _fingerprint_file(manifest_path).sha256,
            **manifest_summary,
        },
    }


def _validate_candidate_risk_upstream_lineage(
    candidate_path: Path,
    *,
    report_date: str,
    bond_result: Mapping[str, object],
    risk_result: Mapping[str, object],
) -> dict[str, object]:
    with active_read_scope(), read_only_connection(str(candidate_path)) as conn:
        column_names = {
            str(row[0])
            for row in conn.execute(
                "select name from pragma_table_info('fact_formal_risk_tensor_daily')"
            ).fetchall()
        }
        liability_columns = {
            "liability_source_version",
            "liability_rule_version",
        }
        present_liability_columns = liability_columns.intersection(column_names)
        if present_liability_columns and present_liability_columns != liability_columns:
            raise ShadowCandidateError(
                "risk_tensor_liability_lineage_columns_incomplete"
            )
        liability_projection = (
            "liability_source_version, liability_rule_version"
            if present_liability_columns
            else "'' as liability_source_version, '' as liability_rule_version"
        )
        rows = conn.execute(
            f"""
            select source_version, rule_version, cache_version,
                   upstream_source_version, upstream_rule_version, upstream_cache_version,
                   {liability_projection}
            from fact_formal_risk_tensor_daily
            where cast(report_date as varchar) = ?
            order by 1, 2, 3, 4, 5, 6, 7, 8
            """,
            [report_date],
        ).fetchmany(2)
    if not rows:
        raise ShadowCandidateError("risk_target_rows_missing")
    if len(rows) != 1:
        raise ShadowCandidateError("risk_target_row_cardinality_invalid")
    bond_source_version = str(bond_result["source_version"])
    bond_rule_version = str(bond_result["rule_version"])
    bond_cache_version = str(bond_result["cache_version"])
    risk_source_version = str(risk_result["source_version"])
    risk_rule_version = str(risk_result["rule_version"])
    risk_cache_version = str(risk_result["cache_version"])
    for (
        source_version,
        rule_version,
        cache_version,
        upstream_source_version,
        upstream_rule_version,
        upstream_cache_version,
        liability_source_version,
        liability_rule_version,
    ) in rows:
        if str(source_version or "") != risk_source_version:
            raise ShadowCandidateError("risk_tensor_source_version_mismatch")
        if str(rule_version or "") != risk_rule_version:
            raise ShadowCandidateError("risk_tensor_rule_version_mismatch")
        if str(cache_version or "") != risk_cache_version:
            raise ShadowCandidateError("risk_tensor_cache_version_mismatch")
        if str(upstream_source_version or "") != bond_source_version:
            raise ShadowCandidateError("risk_tensor_upstream_source_version_mismatch")
        if str(upstream_rule_version or "") != bond_rule_version:
            raise ShadowCandidateError("risk_tensor_upstream_rule_version_mismatch")
        if str(upstream_cache_version or "") != bond_cache_version:
            raise ShadowCandidateError("risk_tensor_upstream_cache_version_mismatch")
        normalized_liability_source_version = str(liability_source_version or "")
        normalized_liability_rule_version = str(liability_rule_version or "")
        if bool(normalized_liability_source_version) != bool(
            normalized_liability_rule_version
        ):
            raise ShadowCandidateError(
                "risk_tensor_liability_lineage_pair_incomplete"
            )
        expected_risk_source_version = compose_risk_tensor_source_version(
            upstream_source_version=bond_source_version,
            liability_source_version=normalized_liability_source_version,
        )
        if risk_source_version != expected_risk_source_version:
            raise ShadowCandidateError(
                "risk_tensor_composite_source_version_mismatch"
            )
    return {
        "row_count": len(rows),
        "source_version": risk_source_version,
        "rule_version": risk_rule_version,
        "cache_version": risk_cache_version,
        "upstream_source_version": bond_source_version,
        "upstream_rule_version": bond_rule_version,
        "upstream_cache_version": bond_cache_version,
        "liability_source_version": normalized_liability_source_version,
        "liability_rule_version": normalized_liability_rule_version,
    }


def _list_governance_artifacts(path: Path) -> list[dict[str, object]]:
    artifacts: list[dict[str, object]] = []
    if not path.is_dir():
        return artifacts
    for artifact in sorted(path.rglob("*.jsonl")):
        fingerprint = _fingerprint_file(artifact)
        artifacts.append(
            {
                "path": str(artifact.resolve(strict=True)),
                "bytes": fingerprint.bytes,
                "sha256": fingerprint.sha256,
                "file_identity": dict(fingerprint.file_identity),
            }
        )
    return artifacts


def _version_mapping(
    container: Mapping[str, object],
    field_name: str,
    *,
    code: str,
) -> Mapping[str, object]:
    value = container.get(field_name)
    if not isinstance(value, Mapping):
        raise ShadowCandidateError(code)
    return value


def _validate_receipt_fixed_income_version_fragment(
    receipt: Mapping[str, object],
) -> None:
    fragment = _version_mapping(
        receipt,
        "fixed_income_version_fragment",
        code="fixed_income_version_fragment_missing",
    )
    expected_descriptors = _version_mapping(
        receipt,
        "expected_descriptors",
        code="fixed_income_expected_descriptors_missing",
    )
    runtime = _version_mapping(
        fragment,
        "runtime",
        code="fixed_income_version_runtime_missing",
    )
    if fragment.get("version_state") != CONFIGURED_CURRENT_VERSION_STATE:
        raise ShadowCandidateError("fixed_income_version_state_invalid")
    engine_rule_version = str(fragment.get("engine_rule_version") or "")
    if not engine_rule_version:
        raise ShadowCandidateError("fixed_income_engine_rule_version_missing")
    if engine_rule_version != expected_descriptors.get("engine_rule_version"):
        raise ShadowCandidateError("fixed_income_version_engine_rule_mismatch")

    observed_results: dict[str, Mapping[str, object]] = {}
    for module_name, result_field in (
        ("bond_analytics", "bond_result"),
        ("risk_tensor", "risk_result"),
    ):
        configured = _version_mapping(
            fragment,
            module_name,
            code=f"fixed_income_version_{module_name}_descriptor_missing",
        )
        expected = _version_mapping(
            expected_descriptors,
            module_name,
            code=f"fixed_income_expected_{module_name}_descriptor_missing",
        )
        observed = _version_mapping(
            receipt,
            result_field,
            code=f"fixed_income_observed_{module_name}_result_missing",
        )
        runtime_lineage = _version_mapping(
            runtime,
            module_name,
            code=f"fixed_income_runtime_{module_name}_lineage_missing",
        )
        observed_results[module_name] = observed
        if dict(configured) != dict(expected):
            raise ShadowCandidateError(
                f"fixed_income_version_{module_name}_descriptor_mismatch"
            )
        if configured.get("module_name") != module_name:
            raise ShadowCandidateError(
                f"fixed_income_version_{module_name}_module_name_mismatch"
            )
        for field_name in ("cache_key", "cache_version", "rule_version"):
            expected_value = expected.get(field_name)
            if not isinstance(expected_value, str) or not expected_value:
                raise ShadowCandidateError(
                    f"fixed_income_expected_{module_name}_{field_name}_missing"
                )
            if (
                configured.get(field_name) != expected_value
                or observed.get(field_name) != expected_value
                or runtime_lineage.get(field_name) != expected_value
            ):
                raise ShadowCandidateError(
                    f"fixed_income_version_{module_name}_{field_name}_mismatch"
                )
        for field_name in ("source_version", "vendor_version"):
            if runtime_lineage.get(field_name) != observed.get(field_name):
                raise ShadowCandidateError(
                    f"fixed_income_version_{module_name}_{field_name}_mismatch"
                )
        if runtime_lineage.get("run_id") != receipt.get("run_id"):
            raise ShadowCandidateError(
                f"fixed_income_version_{module_name}_run_id_mismatch"
            )
        if runtime_lineage.get("report_date") != receipt.get("report_date"):
            raise ShadowCandidateError(
                f"fixed_income_version_{module_name}_report_date_mismatch"
            )

    risk_runtime = _version_mapping(
        runtime,
        "risk_tensor",
        code="fixed_income_runtime_risk_tensor_lineage_missing",
    )
    upstream_lineage = _version_mapping(
        risk_runtime,
        "upstream_lineage",
        code="fixed_income_risk_upstream_lineage_missing",
    )
    liability_lineage = _version_mapping(
        risk_runtime,
        "liability_lineage",
        code="fixed_income_risk_liability_lineage_missing",
    )
    candidate_lineage = _version_mapping(
        receipt,
        "risk_candidate_lineage_validation",
        code="fixed_income_risk_candidate_lineage_missing",
    )
    bond_result = observed_results["bond_analytics"]
    for field_name in ("source_version", "rule_version", "cache_version"):
        if (
            upstream_lineage.get(field_name) != bond_result.get(field_name)
            or upstream_lineage.get(field_name)
            != candidate_lineage.get(f"upstream_{field_name}")
        ):
            raise ShadowCandidateError(
                f"fixed_income_risk_upstream_{field_name}_mismatch"
            )
    for field_name in ("source_version", "rule_version"):
        if liability_lineage.get(field_name) != candidate_lineage.get(
            f"liability_{field_name}"
        ):
            raise ShadowCandidateError(
                f"fixed_income_risk_liability_{field_name}_mismatch"
            )
    expected_risk_source = compose_risk_tensor_source_version(
        upstream_source_version=str(upstream_lineage["source_version"]),
        liability_source_version=str(liability_lineage["source_version"]),
    )
    if risk_runtime.get("source_version") != expected_risk_source:
        raise ShadowCandidateError(
            "fixed_income_risk_composite_source_version_mismatch"
        )


def verify_shadow_candidate_receipt(receipt_path: str | Path) -> dict[str, object]:
    receipt_file = _existing_file_no_links(
        _absolute_input_path(receipt_path, field_name="receipt_path"),
        field_name="receipt_path",
    )
    receipt = _load_json_object(
        receipt_file,
        field_name="receipt",
        max_bytes=_MAX_RECEIPT_BYTES,
    )
    if str(receipt.get("canonical_receipt_sha256") or "") != _receipt_sha256(receipt):
        raise ShadowCandidateError("receipt_sha256_mismatch")
    if receipt.get("receipt_schema") != RECEIPT_SCHEMA:
        raise ShadowCandidateError("receipt_schema_unsupported")
    if receipt.get("status") != "completed" or receipt.get("sealed") is not True:
        raise ShadowCandidateError("receipt_not_sealed_completed")
    _validate_receipt_fixed_income_version_fragment(receipt)
    output_dir = _absolute_input_path(receipt["output_dir"], field_name="output_dir")
    candidate_path = _absolute_input_path(receipt["candidate_duckdb_path"], field_name="candidate_duckdb_path")
    sealed_marker_info = receipt.get("sealed_marker")
    if not isinstance(sealed_marker_info, Mapping):
        raise ShadowCandidateError("sealed_marker_missing_from_receipt")
    sealed_marker_path = _absolute_input_path(sealed_marker_info["path"], field_name="sealed_marker")
    if (output_dir / INCOMPLETE_MARKER).exists():
        raise ShadowCandidateError("incomplete_marker_present_after_seal")
    if not sealed_marker_path.is_file():
        raise ShadowCandidateError("sealed_marker_missing")
    candidate_scan = _fingerprint_file(candidate_path).as_receipt()
    candidate_final = receipt.get("candidate_final_scan")
    candidate_pre_seal = receipt.get("candidate_pre_seal_scan")
    if candidate_scan != candidate_final or candidate_scan != candidate_pre_seal:
        raise ShadowCandidateError("candidate_final_scan_mismatch")
    seal_intent = receipt.get("seal_intent")
    if not isinstance(seal_intent, Mapping):
        raise ShadowCandidateError("seal_intent_missing")
    expected_intent = {
        "run_id": receipt["run_id"],
        "candidate_path": candidate_scan["path"],
        "candidate_bytes": candidate_scan["bytes"],
        "candidate_sha256": candidate_scan["sha256"],
        "candidate_file_identity": candidate_scan["file_identity"],
        "fixed_income_version_fragment_sha256": _sha256_json(
            receipt["fixed_income_version_fragment"]
        ),
        "phase1_receipt_sha256": seal_intent.get("phase1_receipt_sha256"),
    }
    if dict(seal_intent) != expected_intent:
        raise ShadowCandidateError("seal_intent_mismatch")
    marker_payload = _load_json_object(
        sealed_marker_path,
        field_name="sealed_marker",
        max_bytes=_MAX_MARKER_BYTES,
    )
    marker_fingerprint = _fingerprint_file(sealed_marker_path)
    if marker_payload != sealed_marker_info.get("payload"):
        raise ShadowCandidateError("sealed_marker_payload_mismatch")
    if sealed_marker_info.get("payload_sha256") != _sha256_json(marker_payload):
        raise ShadowCandidateError("sealed_marker_payload_sha_mismatch")
    if sealed_marker_info.get("sha256") != marker_fingerprint.sha256:
        raise ShadowCandidateError("sealed_marker_file_sha_mismatch")
    if sealed_marker_info.get("bytes") != marker_fingerprint.bytes:
        raise ShadowCandidateError("sealed_marker_file_bytes_mismatch")
    if _payload_identity(
        sealed_marker_info["file_identity"],
        field_name="sealed_marker",
    ) != _payload_identity(marker_fingerprint.file_identity, field_name="sealed_marker_actual"):
        raise ShadowCandidateError("sealed_marker_identity_mismatch")
    expected_marker_payload = {
        "run_id": receipt["run_id"],
        "candidate_path": candidate_scan["path"],
        "candidate_bytes": candidate_scan["bytes"],
        "candidate_sha256": candidate_scan["sha256"],
        "candidate_file_identity": candidate_scan["file_identity"],
        "seal_intent_sha256": _sha256_json(expected_intent),
        "phase1_receipt_sha256": seal_intent["phase1_receipt_sha256"],
    }
    if marker_payload != expected_marker_payload:
        raise ShadowCandidateError("sealed_marker_payload_mismatch")
    return {
        "status": "verified",
        "receipt_path": str(receipt_file),
        "receipt_sha256": receipt["canonical_receipt_sha256"],
        "candidate_sha256": candidate_scan["sha256"],
        "sealed_marker_sha256": marker_fingerprint.sha256,
    }


def _error_payload(exc: BaseException) -> dict[str, object]:
    if isinstance(exc, ShadowCandidateError):
        detail = exc.detail
        return {
            "type": exc.__class__.__name__,
            "code": exc.code,
            "detail_sha256": hashlib.sha256(str(detail).encode("utf-8")).hexdigest(),
        }
    detail = f"{exc.__class__.__name__}:{exc}"
    return {
        "type": exc.__class__.__name__,
        "code": "shadow_candidate_unhandled_exception",
        "detail_sha256": hashlib.sha256(detail.encode("utf-8")).hexdigest(),
    }


def _git_context() -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return {"commit_sha": commit, "dirty": dirty}
    except Exception:
        return {"commit_sha": None, "dirty": None}


def run_bond_risk_shadow_candidate(
    *,
    report_date: str,
    source_duckdb_path: str | Path,
    expected_source_sha256: str,
    output_dir: str | Path,
    run_id: str | None = None,
    bond_runner: Callable[..., dict[str, object]] | None = None,
    risk_runner: Callable[..., dict[str, object]] | None = None,
    schema_assert: Callable[..., dict[str, object]] | None = None,
) -> dict[str, object]:
    normalized_report_date = _validate_report_date(report_date)
    normalized_run_id = _validate_run_id(run_id)
    normalized_expected_sha = _validate_expected_source_sha256(expected_source_sha256)
    source_path = _existing_file_no_links(
        _absolute_input_path(source_duckdb_path, field_name="source_duckdb_path"),
        field_name="source_duckdb_path",
    )
    output_path = _absolute_input_path(output_dir, field_name="output_dir")
    configured_version_fragment = (
        FIXED_INCOME_VERSION_SET.emit_configured_current_fragment()
    )

    receipt: dict[str, object] = {
        "receipt_schema": RECEIPT_SCHEMA,
        "status": "failed",
        "run_id": normalized_run_id,
        "report_date": normalized_report_date,
        "expected_source_sha256": normalized_expected_sha,
        "shadow_only": True,
        "release_gate_eligible": False,
        "financial_golden_validated": False,
        "wp7_eligible": False,
        "evidence_class": EVIDENCE_CLASS,
        "source_duckdb_path": str(source_path),
        "output_dir": str(output_path),
        "candidate_duckdb_path": str(output_path / CANDIDATE_FILENAME),
        "candidate_governance_dir": str(output_path / GOVERNANCE_DIRNAME),
        "receipt_path": str(output_path / RECEIPT_FILENAME),
        "scope": {
            "mode": "single_report_date_structural_shadow",
            "financial_correctness_validated": False,
            "history_coverage": "single_report_date_only",
        },
        "pending_blockers": [
            "financial_golden_validation_not_performed",
            "wp7_release_gate_not_applicable",
        ],
        "fixed_income_version_fragment": configured_version_fragment,
        "expected_descriptors": {
            "engine_rule_version": FIXED_INCOME_VERSION_SET.engine_rule_version,
            "bond_analytics": FIXED_INCOME_VERSION_SET.bond_analytics.emit_descriptor_fragment(),
            "risk_tensor": FIXED_INCOME_VERSION_SET.risk_tensor.emit_descriptor_fragment(),
        },
        "receipt_persisted": False,
        "source_unchanged": None,
        "sealed": False,
    }
    output_owned = False
    output_dir_identity: tuple[int, int] | None = None
    incomplete_identity: tuple[int, int] | None = None
    receipt_parent_identity: tuple[int, int] | None = None
    candidate_fingerprint_initial: FileFingerprint | None = None
    candidate_initial_identity: tuple[int, int] | None = None
    source_scan_before: FileFingerprint | None = None
    source_scan_after: FileFingerprint | None = None
    configured_live_scan_before: FileFingerprint | None = None
    configured_live_scan_after: FileFingerprint | None = None
    candidate_final_scan: dict[str, object] | None = None
    candidate_pre_seal_scan: FileFingerprint | None = None
    bond_summary: dict[str, object] | None = None
    risk_summary: dict[str, object] | None = None
    bond_result_raw: Mapping[str, object] | None = None
    risk_result_raw: Mapping[str, object] | None = None

    try:
        settings = get_settings()
        receipt["settings_binding"] = _check_settings_env_consistency(settings)
        configured_live_path = _absolute_input_path(
            settings.duckdb_path,
            field_name="configured_live_duckdb_path",
        )
        _assert_samefile_rejected(source_path, configured_live_path)
        _assert_no_symlink_or_junction(output_path, field_name="output_dir")
        if source_path == output_path:
            raise ShadowCandidateError("source_conflicts_with_output_dir")
        try:
            source_path.relative_to(output_path)
        except ValueError:
            pass
        else:
            raise ShadowCandidateError("source_inside_output_dir")
        source_scan_before = _fingerprint_file(source_path)
        receipt["source_scan_before"] = source_scan_before.as_receipt()
        if source_scan_before.sha256 != normalized_expected_sha:
            raise ShadowCandidateError("expected_source_sha256_mismatch")
        configured_live_scan_before = _fingerprint_file(configured_live_path)
        receipt["configured_live_scan_before"] = configured_live_scan_before.as_receipt()
        schema_receipt = (
            schema_assert or assert_duckdb_schema_current
        )(duckdb_path=str(source_path))
        receipt["source_schema_assertion"] = _validate_schema_receipt(schema_receipt)

        output_info = _create_new_directory(output_path, field_name="output_dir")
        output_owned = True
        output_dir_identity = _payload_identity(
            output_info["file_identity"],
            field_name="output_dir",
        )
        receipt_parent_identity = output_dir_identity
        receipt["output_dir_identity"] = output_info["file_identity"]
        incomplete = _create_marker(
            output_path / INCOMPLETE_MARKER,
            parent_identity=receipt_parent_identity,
            payload={"run_id": normalized_run_id, "status": "incomplete"},
        )
        receipt["incomplete_marker"] = incomplete
        incomplete_identity = (
            int(incomplete["file_identity"]["device"]),
            int(incomplete["file_identity"]["inode"]),
        )
        governance_dir = output_path / GOVERNANCE_DIRNAME
        governance_info = _create_new_directory(governance_dir, field_name="candidate_governance_dir")
        receipt["candidate_governance_dir_identity"] = governance_info["file_identity"]
        _assert_output_dir_unchanged(
            output_path,
            expected_identity=output_dir_identity,
            stage="after_governance_dir_create",
        )
        spool_dir = output_path / SPOOL_DIRNAME
        spool_info = _create_new_directory(spool_dir, field_name="identity_spool_dir")
        receipt["identity_spool_dir_identity"] = spool_info["file_identity"]
        _assert_output_dir_unchanged(
            output_path,
            expected_identity=output_dir_identity,
            stage="after_spool_dir_create",
        )

        candidate_path = output_path / CANDIDATE_FILENAME
        _assert_output_dir_unchanged(
            output_path,
            expected_identity=output_dir_identity,
            stage="before_candidate_create",
        )
        candidate_fingerprint_initial = _copy_source_to_candidate(source_path, candidate_path)
        candidate_initial_identity = _payload_identity(
            candidate_fingerprint_initial.file_identity,
            field_name="candidate_duckdb_path",
        )
        receipt["candidate_initial_scan"] = candidate_fingerprint_initial.as_receipt()
        receipt["candidate_copy_binding"] = {
            "expected_source_sha256": normalized_expected_sha,
            "source_sha256_before": source_scan_before.sha256,
            "candidate_initial_sha256": candidate_fingerprint_initial.sha256,
            "matched": source_scan_before.sha256 == candidate_fingerprint_initial.sha256,
        }
        if candidate_fingerprint_initial.sha256 != source_scan_before.sha256:
            raise ShadowCandidateError("candidate_initial_hash_mismatch")
        _assert_output_dir_unchanged(
            output_path,
            expected_identity=output_dir_identity,
            stage="after_candidate_create",
        )
        _assert_execution_state(
            stage="before_bond_runner",
            output_dir=output_path,
            output_identity=output_dir_identity,
            candidate_path=candidate_path,
            candidate_identity=candidate_initial_identity,
            source_path=source_path,
            configured_live_path=configured_live_path,
        )

        source_snapshot = _snapshot_database(
            source_path,
            temp_root=spool_dir,
            side="source",
            report_date=dt.date.fromisoformat(normalized_report_date),
        )
        receipt["target_table_natural_key_proof"] = _validate_target_table_proof(source_snapshot)

        bond_callable = bond_runner or materialize_bond_analytics_facts.fn
        risk_callable = risk_runner or materialize_risk_tensor_facts.fn
        bond_result = bond_callable(
            report_date=normalized_report_date,
            duckdb_path=str(candidate_path),
            governance_dir=str(governance_dir),
            run_id=normalized_run_id,
            use_existing_curves_only=True,
        )
        _assert_execution_state(
            stage="after_bond_runner",
            output_dir=output_path,
            output_identity=output_dir_identity,
            candidate_path=candidate_path,
            candidate_identity=candidate_initial_identity,
            source_path=source_path,
            configured_live_path=configured_live_path,
        )
        bond_summary, bond_source_version = _validate_task_result(
            "bond_analytics",
            bond_result,
            descriptor=BOND_ANALYTICS_MODULE,
            expected_job_name="bond_analytics_materialize",
            expected_run_id=normalized_run_id,
            expected_report_date=normalized_report_date,
        )
        bond_result_raw = dict(bond_result)
        receipt["bond_result"] = bond_summary
        _assert_execution_state(
            stage="before_risk_runner",
            output_dir=output_path,
            output_identity=output_dir_identity,
            candidate_path=candidate_path,
            candidate_identity=candidate_initial_identity,
            source_path=source_path,
            configured_live_path=configured_live_path,
        )

        risk_result = risk_callable(
            report_date=normalized_report_date,
            duckdb_path=str(candidate_path),
            governance_dir=str(governance_dir),
            run_id=normalized_run_id,
        )
        _assert_execution_state(
            stage="after_risk_runner",
            output_dir=output_path,
            output_identity=output_dir_identity,
            candidate_path=candidate_path,
            candidate_identity=candidate_initial_identity,
            source_path=source_path,
            configured_live_path=configured_live_path,
        )
        risk_summary, _ = _validate_task_result(
            "risk_tensor",
            risk_result,
            descriptor=RISK_TENSOR_MODULE,
            expected_job_name="risk_tensor_materialize",
            expected_run_id=normalized_run_id,
            expected_report_date=normalized_report_date,
            required_bond_source_version=bond_source_version,
        )
        risk_result_raw = dict(risk_result)
        receipt["risk_result"] = risk_summary
        receipt["governance_validation"] = {
            "bond_analytics": _validate_governance_records(
                governance_dir,
                result_summary=bond_summary,
                result_raw=bond_result_raw,
                descriptor=BOND_ANALYTICS_MODULE,
            ),
            "risk_tensor": _validate_governance_records(
                governance_dir,
                result_summary=risk_summary,
                result_raw=risk_result_raw,
                descriptor=RISK_TENSOR_MODULE,
            ),
        }
        risk_candidate_lineage = _validate_candidate_risk_upstream_lineage(
            candidate_path,
            report_date=normalized_report_date,
            bond_result=bond_summary,
            risk_result=risk_summary,
        )
        receipt["risk_candidate_lineage_validation"] = risk_candidate_lineage
        try:
            receipt["fixed_income_version_fragment"] = (
                FIXED_INCOME_VERSION_SET.emit_runtime_fragment(
                    run_id=normalized_run_id,
                    report_date=normalized_report_date,
                    bond_source_version=str(bond_summary["source_version"]),
                    bond_vendor_version=str(bond_summary["vendor_version"]),
                    risk_source_version=str(risk_summary["source_version"]),
                    risk_vendor_version=str(risk_summary["vendor_version"]),
                    risk_upstream_source_version=str(
                        risk_candidate_lineage["upstream_source_version"]
                    ),
                    risk_upstream_rule_version=str(
                        risk_candidate_lineage["upstream_rule_version"]
                    ),
                    risk_upstream_cache_version=str(
                        risk_candidate_lineage["upstream_cache_version"]
                    ),
                    liability_source_version=str(
                        risk_candidate_lineage["liability_source_version"]
                    ),
                    liability_rule_version=str(
                        risk_candidate_lineage["liability_rule_version"]
                    ),
                )
            )
        except ValueError as exc:
            raise ShadowCandidateError(
                "fixed_income_version_fragment_invalid",
                detail=str(exc),
            ) from exc
        _validate_receipt_fixed_income_version_fragment(receipt)

        candidate_snapshot = _snapshot_database(
            candidate_path,
            temp_root=spool_dir,
            side="candidate",
            report_date=dt.date.fromisoformat(normalized_report_date),
        )
        comparison = _compare_database_snapshots(
            source_snapshot,
            candidate_snapshot,
            report_date=normalized_report_date,
        )
        receipt.update(comparison)
        if comparison["unexpected_drift"]:
            raise ShadowCandidateError(
                "shadow_candidate_identity_mismatch",
                detail="|".join(comparison["unexpected_drift"]),
        )
        receipt["governance_artifacts"] = _list_governance_artifacts(governance_dir)
        candidate_final_scan = dict(candidate_snapshot["fingerprint"])
        receipt["candidate_final_scan"] = candidate_final_scan
        receipt["status"] = "completed"
    except BaseException as exc:
        receipt["status"] = "failed"
        receipt["error"] = _error_payload(exc)
    finally:
        receipt["bond_result"] = bond_summary or receipt.get("bond_result")
        receipt["risk_result"] = risk_summary or receipt.get("risk_result")
        receipt["git_context"] = _git_context()
        receipt["script_scan"] = _fingerprint_file(Path(__file__)).as_receipt()
        if source_scan_before is not None:
            try:
                source_scan_after = _fingerprint_file(source_path)
                receipt["source_scan_after"] = source_scan_after.as_receipt()
                receipt["source_unchanged"] = (
                    source_scan_before.sha256 == source_scan_after.sha256
                    and source_scan_before.bytes == source_scan_after.bytes
                    and source_scan_before.file_identity == source_scan_after.file_identity
                )
            except Exception as exc:
                receipt["source_unchanged"] = False
                if "error" not in receipt:
                    receipt["error"] = _error_payload(exc)
        if configured_live_scan_before is not None:
            try:
                configured_live_scan_after = _fingerprint_file(configured_live_path)
                receipt["configured_live_scan_after"] = configured_live_scan_after.as_receipt()
                receipt["configured_live_unchanged"] = (
                    configured_live_scan_before.sha256 == configured_live_scan_after.sha256
                    and configured_live_scan_before.bytes == configured_live_scan_after.bytes
                    and configured_live_scan_before.file_identity
                    == configured_live_scan_after.file_identity
                )
            except Exception as exc:
                receipt["configured_live_unchanged"] = False
                if "error" not in receipt:
                    receipt["error"] = _error_payload(exc)
        if receipt["status"] == "completed" and receipt.get("source_unchanged") is False:
            receipt["status"] = "failed"
            receipt["error"] = _error_payload(ShadowCandidateError("source_mutated_during_shadow"))
        if receipt["status"] == "completed" and receipt.get("configured_live_unchanged") is False:
            receipt["status"] = "failed"
            receipt["error"] = _error_payload(ShadowCandidateError("configured_live_mutated_during_shadow"))
        if receipt["status"] == "completed":
            receipt["quarantine_state"] = "sealing"
            receipt["sealed"] = False
            receipt["incomplete_marker_removed"] = False
        else:
            receipt["quarantine_state"] = "quarantine"
            receipt["sealed"] = False
        receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)

        if output_owned and receipt_parent_identity is not None and output_dir_identity is not None:
            receipt_path = output_path / RECEIPT_FILENAME
            sealed_marker_path = output_path / SEALED_MARKER
            output_dir_still_trusted = True
            try:
                _assert_output_dir_unchanged(
                    output_path,
                    expected_identity=output_dir_identity,
                    stage="before_receipt_write",
                )
            except BaseException as exc:
                output_dir_still_trusted = False
                if "error" not in receipt:
                    receipt["status"] = "failed"
                    receipt["error"] = _error_payload(exc)
                receipt["sealed"] = False
                receipt["quarantine_state"] = "quarantine"
                receipt["receipt_persisted"] = False
                receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)
            if output_dir_still_trusted:
                try:
                    if receipt["status"] == "completed":
                        if candidate_path is None or candidate_final_scan is None:
                            raise ShadowCandidateError("candidate_final_scan_missing_before_seal")
                        candidate_pre_seal_scan = _fingerprint_file(candidate_path)
                        receipt["candidate_pre_seal_scan"] = candidate_pre_seal_scan.as_receipt()
                        if candidate_pre_seal_scan.as_receipt() != candidate_final_scan:
                            raise ShadowCandidateError("candidate_pre_seal_scan_mismatch")
                        seal_intent = {
                            "run_id": normalized_run_id,
                            "candidate_path": candidate_pre_seal_scan.path,
                            "candidate_bytes": candidate_pre_seal_scan.bytes,
                            "candidate_sha256": candidate_pre_seal_scan.sha256,
                            "candidate_file_identity": dict(candidate_pre_seal_scan.file_identity),
                            "fixed_income_version_fragment_sha256": _sha256_json(
                                receipt["fixed_income_version_fragment"]
                            ),
                        }
                        receipt["seal_intent"] = seal_intent
                        receipt["sealed_marker"] = None
                        receipt["receipt_persisted"] = True
                        receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)
                        receipt = _write_atomic_json_receipt(
                            receipt_path,
                            dict(receipt),
                            parent_identity=receipt_parent_identity,
                        )
                        phase1_receipt_sha256 = str(receipt["canonical_receipt_sha256"])
                        receipt["seal_intent"] = {
                            **seal_intent,
                            "phase1_receipt_sha256": phase1_receipt_sha256,
                        }
                        previous_identity = receipt.get("receipt_file_identity")
                        if not isinstance(previous_identity, Mapping):
                            raise ShadowCandidateError("receipt_identity_missing_before_seal_finalize")
                        receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)
                        receipt = _write_atomic_json_receipt(
                            receipt_path,
                            dict(receipt),
                            parent_identity=receipt_parent_identity,
                            allow_existing_identity=(
                                int(previous_identity["device"]),
                                int(previous_identity["inode"]),
                            ),
                        )
                        previous_identity = receipt.get("receipt_file_identity")
                        if not isinstance(previous_identity, Mapping):
                            raise ShadowCandidateError("receipt_identity_missing_before_marker_create")
                        sealed_identity: tuple[int, int] | None = None
                        try:
                            marker_payload = {
                                "run_id": normalized_run_id,
                                "candidate_path": candidate_pre_seal_scan.path,
                                "candidate_bytes": candidate_pre_seal_scan.bytes,
                                "candidate_sha256": candidate_pre_seal_scan.sha256,
                                "candidate_file_identity": dict(candidate_pre_seal_scan.file_identity),
                                "seal_intent_sha256": _sha256_json(receipt["seal_intent"]),
                                "phase1_receipt_sha256": phase1_receipt_sha256,
                            }
                            sealed = _create_marker(
                                sealed_marker_path,
                                parent_identity=receipt_parent_identity,
                                payload=marker_payload,
                            )
                            sealed_identity = _payload_identity(
                                sealed["file_identity"],
                                field_name="sealed_marker",
                            )
                            if not sealed_marker_path.exists():
                                raise ShadowCandidateError("sealed_marker_missing_after_create")
                            _remove_path_if_identity_strict(
                                output_path / INCOMPLETE_MARKER,
                                expected_identity=incomplete_identity,
                            )
                            if (output_path / INCOMPLETE_MARKER).exists():
                                raise ShadowCandidateError("incomplete_marker_not_removed")
                            _assert_path_matches_identity(
                                sealed_marker_path,
                                expected_identity=sealed_identity,
                                field_name="sealed_marker",
                                code="sealed_marker_identity_changed",
                            )
                            previous_identity = receipt.get("receipt_file_identity")
                            if not isinstance(previous_identity, Mapping):
                                raise ShadowCandidateError("receipt_identity_missing_before_seal_finalize")
                            receipt["sealed_marker"] = sealed
                            receipt["incomplete_marker_removed"] = True
                            receipt["quarantine_state"] = "sealed"
                            receipt["sealed"] = True
                            receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)
                            receipt = _write_atomic_json_receipt(
                                receipt_path,
                                dict(receipt),
                                parent_identity=receipt_parent_identity,
                                allow_existing_identity=(
                                    int(previous_identity["device"]),
                                    int(previous_identity["inode"]),
                                ),
                            )
                            verify_shadow_candidate_receipt(receipt_path)
                        except BaseException as exc:
                            if os.path.lexists(sealed_marker_path):
                                _assert_output_dir_unchanged(
                                    output_path,
                                    expected_identity=output_dir_identity,
                                    stage="before_sealed_marker_cleanup",
                                )
                                cleanup_identity = sealed_identity
                                if cleanup_identity is None:
                                    cleanup_identity = _path_identity(
                                        sealed_marker_path,
                                        field_name="sealed_marker_cleanup",
                                    )
                                _remove_path_if_identity_strict(
                                    sealed_marker_path,
                                    expected_identity=cleanup_identity,
                                )
                            previous_identity = receipt.get("receipt_file_identity")
                            if not isinstance(previous_identity, Mapping):
                                raise
                            receipt["status"] = "failed"
                            receipt["error"] = _error_payload(exc)
                            receipt["sealed"] = False
                            receipt["quarantine_state"] = "quarantine"
                            receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)
                            receipt = _write_atomic_json_receipt(
                                receipt_path,
                                dict(receipt),
                                parent_identity=receipt_parent_identity,
                                allow_existing_identity=(
                                    int(previous_identity["device"]),
                                    int(previous_identity["inode"]),
                                ),
                            )
                    else:
                        receipt["sealed_marker"] = None
                        receipt["incomplete_marker_removed"] = False
                        receipt["receipt_persisted"] = True
                        receipt = _write_atomic_json_receipt(
                            receipt_path,
                            dict(receipt),
                            parent_identity=receipt_parent_identity,
                        )
                except BaseException as exc:
                    receipt["status"] = "failed"
                    receipt["error"] = _error_payload(exc)
                    receipt["receipt_persisted"] = os.path.lexists(receipt_path)
                    receipt["sealed"] = False
                    receipt["quarantine_state"] = "quarantine"
                    receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)
        else:
            receipt["receipt_persisted"] = False
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run bond/risk structural shadow materialization on an isolated DuckDB copy.",
    )
    parser.add_argument("--report-date", required=True)
    parser.add_argument("--source-duckdb-path", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = run_bond_risk_shadow_candidate(
            report_date=args.report_date,
            source_duckdb_path=args.source_duckdb_path,
            expected_source_sha256=args.expected_source_sha256,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
    except BaseException as exc:
        receipt = {
            "status": "failed",
            "shadow_only": True,
            "release_gate_eligible": False,
            "financial_golden_validated": False,
            "wp7_eligible": False,
            "evidence_class": EVIDENCE_CLASS,
            "receipt_persisted": False,
            "error": _error_payload(exc),
        }
    sys.stdout.write(_stable_json_dumps(receipt))
    return 0 if receipt.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
