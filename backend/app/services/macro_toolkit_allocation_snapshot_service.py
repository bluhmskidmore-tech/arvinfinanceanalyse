"""Fail-closed reader for macro-toolkit allocation refresh snapshots.

The allocation refresh writer publishes one immutable run manifest and then an
atomic ``latest_manifest.json`` pointer.  This module binds a read request to
that pointer exactly once and resolves only the allocation artifacts declared
by the writer.  Artifacts outside that boundary remain explicit, unverified
live reads because they are produced by other macro-toolkit chains.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

_RUNS_DIR_NAME: Final = "_allocation_refresh_runs"
_LATEST_POINTER_NAME: Final = "latest_manifest.json"
_POINTER_SCHEMA: Final = "macro_toolkit_allocation_refresh_latest_pointer.v1"
_MANIFEST_SCHEMA: Final = "macro_toolkit_allocation_refresh_run_manifest.v1"
_MANIFEST_WRITER_STATUSES: Final[frozenset[str]] = frozenset({"captured", "partial"})

# This is intentionally narrower than the refresh writer's complete output
# inventory.  Only artifacts consumed by the model-chain read surface are
# anchored here; unrelated model families must not be accidentally pulled into
# the allocation snapshot contract.
ALLOCATION_ARTIFACT_RELATIVE_PATHS: Final[dict[str, str]] = {
    "dcc_latest.csv": "dcc_garch_cn/dcc_latest.csv",
    "dcc_results.csv": "dcc_garch_cn/dcc_results.csv",
    "regime_results.csv": "regime_switch_cn/regime_results.csv",
    "cta_results.csv": "cta_trend_cn/cta_results.csv",
    "risk_parity_results.csv": "risk_parity_cn/risk_parity_results.csv",
    "rebalance_results.csv": "rebalance_cn/rebalance_results.csv",
    "performance_results.csv": "performance_metrics_cn/performance_results.csv",
    "backtest_results.csv": "backtest_cn/backtest_results.csv",
    "backtest_run_manifest.json": "backtest_cn/backtest_run_manifest.json",
}


@dataclass(frozen=True, slots=True)
class ResolvedAllocationArtifact:
    """One artifact decision made from the request-bound snapshot."""

    path: Path | None
    provenance: dict[str, object]


@dataclass(frozen=True, slots=True)
class _SnapshotArtifactRecord:
    path: Path | None
    relative_path: str
    status: str
    reason_code: str | None
    size_bytes: int | None
    sha256: str | None


class MacroToolkitAllocationSnapshot:
    """Request-scoped allocation artifact resolver.

    Instances are created only through :func:`load_macro_toolkit_allocation_snapshot`.
    The pointer and manifest are already fixed when this object is returned, so
    later pointer publication cannot mix runs inside one response.
    """

    def __init__(
        self,
        *,
        status: str,
        mode: str,
        run_id: str | None,
        snapshot_status: str | None,
        manifest_sha256: str | None,
        warnings: list[str],
        records: Mapping[str, _SnapshotArtifactRecord],
        covered_reads_blocked: bool,
        blocked_reason_code: str | None = None,
    ) -> None:
        self._status = status
        self._mode = mode
        self._run_id = run_id
        self._snapshot_status = snapshot_status
        self._manifest_sha256 = manifest_sha256
        self._warnings = tuple(warnings)
        self._records = dict(records)
        self._covered_reads_blocked = covered_reads_blocked
        self._blocked_reason_code = blocked_reason_code

    @property
    def run_id(self) -> str | None:
        return self._run_id

    def resolve(self, artifact_name: str, *, live_path: Path) -> ResolvedAllocationArtifact:
        """Resolve an artifact without ever falling back after snapshot admission.

        When no pointer has ever been published, compatibility requires a live
        read, but its provenance is explicitly unverified.  Once a pointer
        exists, any pointer/manifest/artifact defect blocks covered artifacts.
        Uncovered model families always remain live and unverified.
        """

        if artifact_name not in ALLOCATION_ARTIFACT_RELATIVE_PATHS:
            return ResolvedAllocationArtifact(
                path=live_path,
                provenance=_live_provenance(artifact_name, reason_code="outside_allocation_snapshot"),
            )

        if self._mode == "live_unverified":
            return ResolvedAllocationArtifact(
                path=live_path,
                provenance=_live_provenance(artifact_name, reason_code="snapshot_pointer_missing"),
            )

        if self._covered_reads_blocked:
            return ResolvedAllocationArtifact(
                path=None,
                provenance=self._blocked_provenance(
                    artifact_name,
                    reason_code=self._blocked_reason_code or "snapshot_invalid",
                    relative_path=ALLOCATION_ARTIFACT_RELATIVE_PATHS[artifact_name],
                ),
            )

        record = self._records.get(artifact_name)
        if record is None or record.path is None or record.status != "verified":
            reason_code = (
                record.reason_code if record is not None else "snapshot_artifact_missing"
            )
            return ResolvedAllocationArtifact(
                path=None,
                provenance=self._blocked_provenance(
                    artifact_name,
                    reason_code=reason_code or "snapshot_artifact_invalid",
                    relative_path=(
                        record.relative_path
                        if record is not None
                        else ALLOCATION_ARTIFACT_RELATIVE_PATHS[artifact_name]
                    ),
                ),
            )
        return ResolvedAllocationArtifact(
            path=record.path,
            provenance={
                "mode": "snapshot",
                "status": "verified",
                "run_id": self._run_id,
                "artifact": artifact_name,
                "relative_path": record.relative_path,
                "size_bytes": record.size_bytes,
                "sha256": record.sha256,
                "reason_code": None,
            },
        )

    def _blocked_provenance(
        self,
        artifact_name: str,
        *,
        reason_code: str,
        relative_path: str,
    ) -> dict[str, object]:
        return {
            "mode": "snapshot_fail_closed",
            "status": "blocked",
            "run_id": self._run_id,
            "artifact": artifact_name,
            "relative_path": relative_path,
            "size_bytes": None,
            "sha256": None,
            "reason_code": reason_code,
        }

    def as_payload(self) -> dict[str, object]:
        verified_count = sum(
            1 for record in self._records.values() if record.status == "verified"
        )
        return {
            "schema_version": "macro_toolkit_allocation_snapshot_read.v1",
            "status": self._status,
            "read_status": self._status,
            "mode": self._mode,
            "run_id": self._run_id,
            "snapshot_status": self._snapshot_status,
            "writer_status": self._snapshot_status,
            "manifest_sha256": self._manifest_sha256,
            "target_artifact_count": len(ALLOCATION_ARTIFACT_RELATIVE_PATHS),
            "verified_artifact_count": verified_count,
            "warnings": list(self._warnings),
        }


def load_macro_toolkit_allocation_snapshot(output_dir: Path | str) -> MacroToolkitAllocationSnapshot:
    """Load and validate the latest allocation pointer and manifest once."""

    directory = Path(output_dir)
    runs_root = directory / _RUNS_DIR_NAME
    pointer_path = runs_root / _LATEST_POINTER_NAME
    if not pointer_path.exists():
        return MacroToolkitAllocationSnapshot(
            status="missing",
            mode="live_unverified",
            run_id=None,
            snapshot_status=None,
            manifest_sha256=None,
            warnings=["snapshot_pointer_missing"],
            records={},
            covered_reads_blocked=False,
        )
    if not pointer_path.is_file():
        return _invalid_snapshot(reason_code="snapshot_pointer_invalid")

    try:
        pointer_bytes = pointer_path.read_bytes()
        pointer = json.loads(pointer_bytes.decode("utf-8"))
    except (OSError, UnicodeError, ValueError):
        return _invalid_snapshot(reason_code="snapshot_pointer_invalid")
    if not isinstance(pointer, Mapping):
        return _invalid_snapshot(reason_code="snapshot_pointer_invalid")

    run_id = _required_text(pointer.get("run_id"))
    manifest_relative_path = _required_text(pointer.get("manifest_relative_path"))
    manifest_sha256 = _required_sha256(pointer.get("manifest_sha256"))
    if (
        pointer.get("schema_version") != _POINTER_SCHEMA
        or run_id is None
        or manifest_relative_path is None
        or manifest_sha256 is None
    ):
        return _invalid_snapshot(
            reason_code="snapshot_pointer_contract_invalid",
            run_id=run_id,
        )

    manifest_path = _confined_path(runs_root, manifest_relative_path)
    if (
        manifest_path is None
        or manifest_path.name != "run_manifest.json"
        or manifest_path.parent.parent != runs_root.resolve()
    ):
        return _invalid_snapshot(
            reason_code="snapshot_manifest_path_invalid",
            run_id=run_id,
        )

    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError:
        return _invalid_snapshot(
            reason_code="snapshot_manifest_missing",
            run_id=run_id,
        )
    if sha256(manifest_bytes).hexdigest() != manifest_sha256:
        return _invalid_snapshot(
            reason_code="snapshot_manifest_hash_mismatch",
            run_id=run_id,
        )
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeError, ValueError):
        return _invalid_snapshot(
            reason_code="snapshot_manifest_invalid",
            run_id=run_id,
        )
    if not isinstance(manifest, Mapping):
        return _invalid_snapshot(
            reason_code="snapshot_manifest_invalid",
            run_id=run_id,
        )
    if (
        manifest.get("schema_version") != _MANIFEST_SCHEMA
        or manifest.get("run_id") != run_id
        or manifest.get("observation_only") is not True
        or manifest.get("formal_use_allowed") is not False
        or not isinstance(manifest.get("artifacts"), list)
    ):
        return _invalid_snapshot(
            reason_code="snapshot_manifest_contract_invalid",
            run_id=run_id,
        )
    writer_status = _required_text(manifest.get("status"))
    if writer_status not in _MANIFEST_WRITER_STATUSES:
        return _invalid_snapshot(
            reason_code="snapshot_manifest_status_invalid",
            run_id=run_id,
        )

    run_dir = manifest_path.parent
    records = _validate_target_artifacts(manifest["artifacts"], run_dir=run_dir)
    warnings = [
        f"{artifact_name}:{record.reason_code}"
        for artifact_name, record in records.items()
        if record.status != "verified"
    ]
    return MacroToolkitAllocationSnapshot(
        status="ready" if not warnings else "partial",
        mode="snapshot",
        run_id=run_id,
        snapshot_status=writer_status,
        manifest_sha256=manifest_sha256,
        warnings=warnings,
        records=records,
        covered_reads_blocked=False,
    )


def _validate_target_artifacts(
    artifacts: list[object],
    *,
    run_dir: Path,
) -> dict[str, _SnapshotArtifactRecord]:
    entries_by_relative_path: dict[str, list[Mapping[str, object]]] = {}
    for raw_entry in artifacts:
        if not isinstance(raw_entry, Mapping):
            continue
        relative_path = _required_text(raw_entry.get("relative_path"))
        if relative_path is None:
            continue
        entries_by_relative_path.setdefault(relative_path.replace("\\", "/"), []).append(raw_entry)

    records: dict[str, _SnapshotArtifactRecord] = {}
    for artifact_name, expected_relative_path in ALLOCATION_ARTIFACT_RELATIVE_PATHS.items():
        matches = entries_by_relative_path.get(expected_relative_path, [])
        if not matches:
            records[artifact_name] = _blocked_record(
                expected_relative_path,
                "snapshot_artifact_missing",
            )
            continue
        if len(matches) != 1:
            records[artifact_name] = _blocked_record(
                expected_relative_path,
                "snapshot_artifact_duplicate",
            )
            continue
        entry = matches[0]
        artifact_path = _confined_path(run_dir, expected_relative_path)
        declared_size = entry.get("size_bytes")
        declared_hash = _required_sha256(entry.get("sha256"))
        if (
            artifact_path is None
            or not isinstance(declared_size, int)
            or isinstance(declared_size, bool)
            or declared_size < 0
            or declared_hash is None
        ):
            records[artifact_name] = _blocked_record(
                expected_relative_path,
                "snapshot_artifact_contract_invalid",
            )
            continue
        try:
            actual_size = artifact_path.stat().st_size
        except OSError:
            records[artifact_name] = _blocked_record(
                expected_relative_path,
                "snapshot_artifact_missing",
            )
            continue
        if not artifact_path.is_file():
            records[artifact_name] = _blocked_record(
                expected_relative_path,
                "snapshot_artifact_missing",
            )
            continue
        if actual_size != declared_size:
            records[artifact_name] = _blocked_record(
                expected_relative_path,
                "snapshot_artifact_size_mismatch",
            )
            continue
        try:
            actual_hash = _sha256_file(artifact_path)
        except OSError:
            records[artifact_name] = _blocked_record(
                expected_relative_path,
                "snapshot_artifact_unreadable",
            )
            continue
        if actual_hash != declared_hash:
            records[artifact_name] = _blocked_record(
                expected_relative_path,
                "snapshot_artifact_hash_mismatch",
            )
            continue
        records[artifact_name] = _SnapshotArtifactRecord(
            path=artifact_path,
            relative_path=expected_relative_path,
            status="verified",
            reason_code=None,
            size_bytes=declared_size,
            sha256=declared_hash,
        )
    return records


def _invalid_snapshot(
    *,
    reason_code: str,
    run_id: str | None = None,
) -> MacroToolkitAllocationSnapshot:
    return MacroToolkitAllocationSnapshot(
        status="invalid",
        mode="snapshot_fail_closed",
        run_id=run_id,
        snapshot_status=None,
        manifest_sha256=None,
        warnings=[reason_code],
        records={},
        covered_reads_blocked=True,
        blocked_reason_code=reason_code,
    )


def _blocked_record(relative_path: str, reason_code: str) -> _SnapshotArtifactRecord:
    return _SnapshotArtifactRecord(
        path=None,
        relative_path=relative_path,
        status="blocked",
        reason_code=reason_code,
        size_bytes=None,
        sha256=None,
    )


def _live_provenance(artifact_name: str, *, reason_code: str) -> dict[str, object]:
    return {
        "mode": "live_unverified",
        "status": "unverified",
        "run_id": None,
        "artifact": artifact_name,
        "relative_path": artifact_name,
        "size_bytes": None,
        "sha256": None,
        "reason_code": reason_code,
    }


def _confined_path(base: Path, relative_path: str) -> Path | None:
    candidate_relative = Path(relative_path)
    if (
        candidate_relative.is_absolute()
        or candidate_relative.drive
        or any(part in {".", ".."} for part in candidate_relative.parts)
    ):
        return None
    try:
        base_resolved = base.resolve()
        candidate = (base_resolved / candidate_relative).resolve()
        candidate.relative_to(base_resolved)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _required_sha256(value: object) -> str | None:
    text = _required_text(value)
    if text is None or len(text) != 64:
        return None
    lowered = text.lower()
    if any(character not in "0123456789abcdef" for character in lowered):
        return None
    return lowered
