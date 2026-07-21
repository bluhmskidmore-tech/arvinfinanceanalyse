from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

BUNDLE_DIRNAME = "bond_macro_report_bundle"
MANIFEST_FILENAME = "manifest.json"
SCHEMA_VERSION = "macro-report-bundle-v1"
MAX_MANIFEST_BYTES = 1_000_000
MAX_ARTIFACT_BYTES = 50_000_000

_ARTIFACT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_ALLOWED_MEDIA_TYPES = {
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".png": "image/png",
}


class ReportBundleError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ReportBundleNotFoundError(ReportBundleError):
    pass


class ReportBundleInvalidError(ReportBundleError):
    pass


class ReportArtifactNotFoundError(ReportBundleError):
    pass


@dataclass(frozen=True)
class VerifiedReportArtifact:
    artifact_id: str
    filename: str
    label: str
    kind: str
    media_type: str
    size_bytes: int
    sha256: str
    content: bytes

    def metadata(self) -> dict[str, object]:
        return {
            "id": self.artifact_id,
            "filename": self.filename,
            "label": self.label,
            "kind": self.kind,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class _VerifiedReportBundle:
    manifest: dict[str, Any]
    artifacts: tuple[VerifiedReportArtifact, ...]


def load_report_bundle(bundle_dir: str | Path) -> dict[str, object]:
    try:
        bundle = _load_verified_bundle(Path(bundle_dir))
    except ReportBundleNotFoundError:
        return _unavailable_payload(
            status="missing",
            reason="manifest_missing",
            warning="宏观报告资产包尚未发布。",
        )
    except ReportBundleInvalidError as exc:
        return _unavailable_payload(
            status="invalid",
            reason=exc.reason,
            warning="宏观报告资产包校验失败，已禁止下载。",
        )

    manifest = bundle.manifest
    return {
        "status": "ready",
        "reason": None,
        "schema_version": SCHEMA_VERSION,
        "bundle_id": manifest["bundle_id"],
        "title": manifest["title"],
        "basis": "analytical",
        "as_of_date": manifest["as_of_date"],
        "curve_date": manifest["curve_date"],
        "account_report_date": manifest["account_report_date"],
        "observation_only": True,
        "formal_use_allowed": False,
        "validation": manifest["validation"],
        "warnings": manifest["warnings"],
        "artifacts": [artifact.metadata() for artifact in bundle.artifacts],
    }


def read_report_artifact(bundle_dir: str | Path, artifact_id: str) -> VerifiedReportArtifact:
    bundle = _load_verified_bundle(Path(bundle_dir))
    for artifact in bundle.artifacts:
        if artifact.artifact_id == artifact_id:
            return artifact
    raise ReportArtifactNotFoundError("artifact_not_found")


def _unavailable_payload(*, status: str, reason: str, warning: str) -> dict[str, object]:
    return {
        "status": status,
        "reason": reason,
        "basis": "analytical",
        "observation_only": True,
        "formal_use_allowed": False,
        "artifacts": [],
        "warnings": [warning],
    }


def _load_verified_bundle(bundle_dir: Path) -> _VerifiedReportBundle:
    manifest = _read_manifest(bundle_dir)
    _validate_policy(manifest)
    _validate_text_field(manifest, "bundle_id")
    _validate_text_field(manifest, "title")
    for field in ("as_of_date", "curve_date", "account_report_date"):
        _validate_iso_date(manifest, field)
    validation = _validate_validation(manifest.get("validation"))
    warnings = _validate_warnings(manifest.get("warnings"))
    manifest["validation"] = validation
    manifest["warnings"] = warnings

    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise ReportBundleInvalidError("artifacts_required")

    artifacts: list[VerifiedReportArtifact] = []
    ids: set[str] = set()
    filenames: set[str] = set()
    for raw_artifact in raw_artifacts:
        artifact = _verify_artifact(bundle_dir, raw_artifact)
        if artifact.artifact_id in ids:
            raise ReportBundleInvalidError("duplicate_artifact_id")
        if artifact.filename in filenames:
            raise ReportBundleInvalidError("duplicate_artifact_filename")
        ids.add(artifact.artifact_id)
        filenames.add(artifact.filename)
        artifacts.append(artifact)
    return _VerifiedReportBundle(manifest=manifest, artifacts=tuple(artifacts))


def _read_manifest(bundle_dir: Path) -> dict[str, Any]:
    if not bundle_dir.exists():
        raise ReportBundleNotFoundError("manifest_missing")
    if bundle_dir.is_symlink():
        raise ReportBundleInvalidError("bundle_symlink_not_allowed")
    try:
        resolved_bundle_dir = bundle_dir.resolve(strict=True)
    except OSError as exc:
        raise ReportBundleNotFoundError("manifest_missing") from exc
    if not resolved_bundle_dir.is_dir():
        raise ReportBundleInvalidError("bundle_directory_required")

    manifest_path = bundle_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise ReportBundleNotFoundError("manifest_missing")
    if manifest_path.is_symlink():
        raise ReportBundleInvalidError("manifest_symlink_not_allowed")
    try:
        resolved_manifest = manifest_path.resolve(strict=True)
    except OSError as exc:
        raise ReportBundleInvalidError("manifest_unreadable") from exc
    if resolved_manifest.parent != resolved_bundle_dir or not resolved_manifest.is_file():
        raise ReportBundleInvalidError("manifest_path_invalid")
    try:
        if resolved_manifest.stat().st_size > MAX_MANIFEST_BYTES:
            raise ReportBundleInvalidError("manifest_too_large")
        raw = resolved_manifest.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except ReportBundleInvalidError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReportBundleInvalidError("manifest_unreadable") from exc
    if not isinstance(payload, dict):
        raise ReportBundleInvalidError("manifest_object_required")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ReportBundleInvalidError("unsupported_schema_version")
    return payload


def _validate_policy(manifest: dict[str, Any]) -> None:
    if manifest.get("formal_use_allowed") is not False:
        raise ReportBundleInvalidError("formal_use_not_allowed")
    if manifest.get("observation_only") is not True:
        raise ReportBundleInvalidError("observation_only_required")
    if manifest.get("basis") != "analytical":
        raise ReportBundleInvalidError("analytical_basis_required")


def _validate_text_field(manifest: dict[str, Any], field: str) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ReportBundleInvalidError(f"invalid_{field}")
    return value.strip()


def _validate_iso_date(manifest: dict[str, Any], field: str) -> str:
    value = _validate_text_field(manifest, field)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ReportBundleInvalidError(f"invalid_{field}") from exc
    return value


def _validate_validation(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ReportBundleInvalidError("invalid_validation")
    passed = raw.get("passed")
    failed = raw.get("failed")
    scope = raw.get("scope")
    if (
        isinstance(passed, bool)
        or not isinstance(passed, int)
        or passed < 0
        or isinstance(failed, bool)
        or not isinstance(failed, int)
        or failed < 0
        or not isinstance(scope, str)
        or not scope.strip()
    ):
        raise ReportBundleInvalidError("invalid_validation")
    return {"passed": passed, "failed": failed, "scope": scope.strip()}


def _validate_warnings(raw: object) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(item, str) and item.strip() for item in raw):
        raise ReportBundleInvalidError("invalid_warnings")
    return [item.strip() for item in raw]


def _verify_artifact(bundle_dir: Path, raw: object) -> VerifiedReportArtifact:
    if not isinstance(raw, dict):
        raise ReportBundleInvalidError("invalid_artifact")
    artifact_id = raw.get("id")
    filename = raw.get("filename")
    label = raw.get("label")
    kind = raw.get("kind")
    media_type = raw.get("media_type")
    size_bytes = raw.get("size_bytes")
    sha256 = raw.get("sha256")

    if not isinstance(artifact_id, str) or _ARTIFACT_ID_PATTERN.fullmatch(artifact_id) is None:
        raise ReportBundleInvalidError("invalid_artifact_id")
    if not isinstance(filename, str) or not _is_safe_filename(filename):
        raise ReportBundleInvalidError("invalid_artifact_filename")
    if not isinstance(label, str) or not label.strip():
        raise ReportBundleInvalidError("invalid_artifact_label")
    if not isinstance(kind, str) or not kind.strip():
        raise ReportBundleInvalidError("invalid_artifact_kind")
    expected_media_type = _ALLOWED_MEDIA_TYPES.get(Path(filename).suffix.lower())
    if expected_media_type is None or media_type != expected_media_type:
        raise ReportBundleInvalidError("artifact_media_type_not_allowed")
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or not 0 <= size_bytes <= MAX_ARTIFACT_BYTES:
        raise ReportBundleInvalidError("invalid_artifact_size")
    if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
        raise ReportBundleInvalidError("invalid_artifact_sha256")

    content = _read_verified_artifact_bytes(
        bundle_dir,
        filename=filename,
        size_bytes=size_bytes,
        sha256=sha256,
    )
    return VerifiedReportArtifact(
        artifact_id=artifact_id,
        filename=filename,
        label=label.strip(),
        kind=kind.strip(),
        media_type=media_type,
        size_bytes=size_bytes,
        sha256=sha256,
        content=content,
    )


def _is_safe_filename(filename: str) -> bool:
    return (
        filename not in {".", ".."}
        and filename == Path(filename).name
        and "/" not in filename
        and "\\" not in filename
        and not any(ord(character) < 32 for character in filename)
    )


def _read_verified_artifact_bytes(
    bundle_dir: Path,
    *,
    filename: str,
    size_bytes: int,
    sha256: str,
) -> bytes:
    if bundle_dir.is_symlink():
        raise ReportBundleInvalidError("bundle_symlink_not_allowed")
    resolved_bundle_dir = bundle_dir.resolve(strict=True)
    artifact_path = bundle_dir / filename
    if artifact_path.is_symlink():
        raise ReportBundleInvalidError("artifact_symlink_not_allowed")
    try:
        resolved_artifact = artifact_path.resolve(strict=True)
    except OSError as exc:
        raise ReportBundleInvalidError("artifact_missing") from exc
    if resolved_artifact.parent != resolved_bundle_dir or not resolved_artifact.is_file():
        raise ReportBundleInvalidError("artifact_path_invalid")

    try:
        before = resolved_artifact.stat()
        content = resolved_artifact.read_bytes()
        after = resolved_artifact.stat()
    except OSError as exc:
        raise ReportBundleInvalidError("artifact_unreadable") from exc
    before_signature = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_signature = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_signature != after_signature:
        raise ReportBundleInvalidError("artifact_changed_during_read")
    if len(content) != size_bytes:
        raise ReportBundleInvalidError("artifact_size_mismatch")
    if hashlib.sha256(content).hexdigest() != sha256:
        raise ReportBundleInvalidError("artifact_hash_mismatch")
    return content
