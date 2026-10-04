"""Build a non-authoritative ADB monthly golden recapture candidate.

The tool deliberately cannot write the committed golden-sample tree.  It replays
the deterministic test fixture in a temporary directory, validates the complete
response against the current API envelope, and writes review-only artifacts to a
new caller-selected directory.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import stat
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.schemas.adb_analysis import AdbAnalysisEnvelope  # noqa: E402

SAMPLE_ID = "GS-AVERAGE-BALANCE-MONTHLY-A"
SAMPLE_YEAR = 2025
CAPTURE_TIMESTAMP = "2026-08-31T00:00:00Z"
AUTHORITATIVE_GOLDEN_ROOT = ROOT / "tests" / "golden_samples"
CURRENT_RESPONSE_PATH = AUTHORITATIVE_GOLDEN_ROOT / SAMPLE_ID / "response.json"
FIXTURE_MODULE_PATH = ROOT / "tests" / "test_golden_samples_capture_ready.py"
FIXTURE_MODULE_NAME = "tests._adb_monthly_golden_candidate_fixture"
OUTPUT_FILENAMES = (
    "candidate-response.json",
    "diff.json",
    "README.md",
)
BOUNDARY_FLAGS = {
    "authoritative": False,
    "captures_approval": False,
    "writes_golden_sample": False,
    "production_writes": False,
}

_MISSING = object()


class CaptureCandidateError(RuntimeError):
    """A fail-closed candidate capture boundary violation."""


class _FixtureEnvironment:
    """Minimal ``MonkeyPatch.setenv`` adapter used by the shared fixture helper."""

    def __init__(self) -> None:
        self._original: dict[str, str | object] = {}

    def setenv(self, name: str, value: str) -> None:
        if name not in self._original:
            self._original[name] = os.environ.get(name, _MISSING)
        os.environ[name] = str(value)

    def undo(self) -> None:
        for name, value in self._original.items():
            if value is _MISSING:
                os.environ.pop(name, None)
            else:
                os.environ[name] = str(value)
        self._original.clear()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _assert_no_symlink_junction_or_reparse(path: Path, *, field_name: str) -> None:
    current = Path(path.anchor) if path.is_absolute() else Path(".")
    parts = path.parts[1:] if path.is_absolute() else path.parts
    reparse_mask = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    for part in parts:
        current /= part
        if not os.path.lexists(current):
            continue
        try:
            metadata = current.stat(follow_symlinks=False)
            junction_probe = getattr(current, "is_junction", None)
            is_junction = bool(junction_probe()) if callable(junction_probe) else False
            is_symlink = current.is_symlink()
        except OSError as exc:
            raise CaptureCandidateError(f"{field_name}_identity_unavailable") from exc
        file_attributes = int(getattr(metadata, "st_file_attributes", 0))
        if is_symlink or is_junction or bool(file_attributes & reparse_mask):
            raise CaptureCandidateError(
                f"{field_name}_contains_symlink_junction_or_reparse"
            )


def _path_identity(path: Path, *, field_name: str) -> tuple[int, int]:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise CaptureCandidateError(f"{field_name}_identity_unavailable") from exc
    return int(metadata.st_dev), int(metadata.st_ino)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _normalize_new_output_dir(output_dir: str | os.PathLike[str]) -> Path:
    raw = os.fspath(output_dir)
    if not raw or not raw.strip():
        raise CaptureCandidateError("output_dir_required")

    requested = Path(raw).expanduser()
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    requested = Path(os.path.abspath(requested))
    if requested.name in {"", ".", ".."}:
        raise CaptureCandidateError("output_dir_invalid")

    parent = requested.parent
    _assert_no_symlink_junction_or_reparse(parent, field_name="output_dir_parent")
    if not parent.is_dir():
        raise CaptureCandidateError("output_dir_parent_must_exist")
    resolved_parent = parent.resolve(strict=True)
    normalized = resolved_parent / requested.name

    authoritative_root = AUTHORITATIVE_GOLDEN_ROOT.resolve(strict=True)
    if _is_within(normalized, authoritative_root):
        raise CaptureCandidateError("output_dir_is_authoritative_golden_tree")
    if os.path.lexists(normalized):
        raise CaptureCandidateError("output_dir_must_not_exist")
    return normalized


def _create_output_dir(path: Path) -> tuple[int, int]:
    _assert_no_symlink_junction_or_reparse(path.parent, field_name="output_dir_parent")
    parent_identity = _path_identity(path.parent, field_name="output_dir_parent")
    if os.path.lexists(path):
        raise CaptureCandidateError("output_dir_must_not_exist")
    try:
        path.mkdir()
    except FileExistsError as exc:
        raise CaptureCandidateError("output_dir_must_not_exist") from exc
    if _path_identity(path.parent, field_name="output_dir_parent") != parent_identity:
        raise CaptureCandidateError("output_dir_parent_identity_changed")
    _assert_no_symlink_junction_or_reparse(path, field_name="output_dir")
    if not path.is_dir():
        raise CaptureCandidateError("output_dir_identity_invalid")
    return _path_identity(path, field_name="output_dir")


def _assert_output_identity(path: Path, expected: tuple[int, int]) -> None:
    _assert_no_symlink_junction_or_reparse(path, field_name="output_dir")
    if _path_identity(path, field_name="output_dir") != expected:
        raise CaptureCandidateError("output_dir_identity_changed")


def _write_new_file(
    output_dir: Path,
    output_identity: tuple[int, int],
    filename: str,
    payload: bytes,
) -> None:
    _assert_output_identity(output_dir, output_identity)
    path = output_dir / filename
    if os.path.lexists(path):
        raise CaptureCandidateError(f"output_file_already_exists:{filename}")
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise CaptureCandidateError(f"output_file_already_exists:{filename}") from exc
    _assert_no_symlink_junction_or_reparse(path, field_name="output_file")
    _assert_output_identity(output_dir, output_identity)


@contextmanager
def _preserve_modules(module_names: Sequence[str]) -> Iterator[None]:
    previous = {name: sys.modules.get(name, _MISSING) for name in module_names}
    try:
        yield
    finally:
        for name, module in previous.items():
            if module is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module  # type: ignore[assignment]


def _load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        FIXTURE_MODULE_NAME, FIXTURE_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise CaptureCandidateError("fixture_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[FIXTURE_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise CaptureCandidateError("fixture_module_load_failed") from exc
    return module


def _produce_fixture_response() -> dict[str, Any]:
    preserved_modules = (
        FIXTURE_MODULE_NAME,
        "backend.app.repositories.balance_analysis_repo",
        "backend.app.services.adb_analysis_service",
    )
    with TemporaryDirectory(prefix="moss-adb-monthly-golden-candidate-") as temp_dir:
        fixture_root = Path(temp_dir)
        fixture_db = fixture_root / "average-balance.duckdb"
        fixture_environment = _FixtureEnvironment()
        with _preserve_modules(preserved_modules):
            try:
                fixture_module = _load_fixture_module()
                setup = getattr(fixture_module, "_setup_average_balance", None)
                if not callable(setup):
                    raise CaptureCandidateError("fixture_setup_unavailable")
                setup(fixture_root, fixture_environment)
                if not fixture_db.is_file():
                    raise CaptureCandidateError("fixture_duckdb_not_created")

                service_module = importlib.import_module(
                    "backend.app.services.adb_analysis_service"
                )
                original_get_settings = service_module.get_settings
                service_module.get_settings = lambda: SimpleNamespace(
                    duckdb_path=fixture_db
                )
                try:
                    raw = service_module.adb_monthly_envelope(SAMPLE_YEAR)
                finally:
                    service_module.get_settings = original_get_settings
            finally:
                fixture_environment.undo()
                from backend.app.governance.settings import get_settings

                get_settings.cache_clear()

    if not isinstance(raw, dict):
        raise CaptureCandidateError("fixture_response_invalid")
    return raw


def _validated_candidate_response() -> dict[str, Any]:
    candidate = deepcopy(_produce_fixture_response())
    result_meta = candidate.get("result_meta")
    if not isinstance(result_meta, dict) or not result_meta.get("generated_at"):
        raise CaptureCandidateError("fixture_generated_at_missing")
    result_meta["generated_at"] = CAPTURE_TIMESTAMP
    try:
        validated = AdbAnalysisEnvelope.model_validate(candidate)
    except Exception as exc:
        raise CaptureCandidateError("candidate_response_model_invalid") from exc
    dumped = validated.model_dump(mode="json")
    if dumped["result_meta"]["generated_at"] != CAPTURE_TIMESTAMP:
        raise CaptureCandidateError("capture_timestamp_not_canonical")
    return dumped


def _join_path(parent: str, segment: str | int) -> str:
    if isinstance(segment, int):
        return f"{parent}[{segment}]" if parent else f"[{segment}]"
    return f"{parent}.{segment}" if parent else segment


def _json_diff(
    current: Any,
    candidate: Any,
    *,
    path: str = "",
) -> tuple[list[str], list[str], list[str]]:
    added: list[str] = []
    removed: list[str] = []
    changed: list[str] = []
    if isinstance(current, dict) and isinstance(candidate, dict):
        current_keys = set(current)
        candidate_keys = set(candidate)
        added.extend(
            _join_path(path, key) for key in sorted(candidate_keys - current_keys)
        )
        removed.extend(
            _join_path(path, key) for key in sorted(current_keys - candidate_keys)
        )
        for key in sorted(current_keys & candidate_keys):
            child_added, child_removed, child_changed = _json_diff(
                current[key],
                candidate[key],
                path=_join_path(path, key),
            )
            added.extend(child_added)
            removed.extend(child_removed)
            changed.extend(child_changed)
        return added, removed, changed
    if isinstance(current, list) and isinstance(candidate, list):
        common_length = min(len(current), len(candidate))
        for index in range(common_length):
            child_added, child_removed, child_changed = _json_diff(
                current[index],
                candidate[index],
                path=_join_path(path, index),
            )
            added.extend(child_added)
            removed.extend(child_removed)
            changed.extend(child_changed)
        added.extend(
            _join_path(path, index) for index in range(common_length, len(candidate))
        )
        removed.extend(
            _join_path(path, index) for index in range(common_length, len(current))
        )
        return added, removed, changed
    if current != candidate:
        changed.append(path or "$")
    return added, removed, changed


def _build_diff(
    *,
    current: Mapping[str, Any],
    candidate: Mapping[str, Any],
    current_sha256: str,
    candidate_sha256: str,
) -> dict[str, Any]:
    added, removed, changed = _json_diff(dict(current), dict(candidate))
    return {
        "artifact_kind": "average_balance_monthly_golden_recapture_candidate_diff",
        "sample_id": SAMPLE_ID,
        "capture_timestamp": CAPTURE_TIMESTAMP,
        "current_response": CURRENT_RESPONSE_PATH.relative_to(ROOT).as_posix(),
        "candidate_response": "candidate-response.json",
        "current_sha256": current_sha256,
        "candidate_sha256": candidate_sha256,
        "added_paths": added,
        "removed_paths": removed,
        "changed_paths": changed,
        **BOUNDARY_FLAGS,
    }


def _markdown_path_list(paths: Sequence[str]) -> str:
    if not paths:
        return "- None"
    return "\n".join(f"- `{path}`" for path in paths)


def _render_readme(diff: Mapping[str, Any]) -> str:
    return f"""# ADB Monthly Golden Recapture Candidate

This directory contains review-only output from the deterministic fixture-backed
producer for `{SAMPLE_ID}`. It is not a golden-sample update and conveys no
approval or promotion status.

## Boundary

- `authoritative=false`
- `captures_approval=false`
- `writes_golden_sample=false`
- `production_writes=false`

## Capture

- Sample year: `{SAMPLE_YEAR}`
- Fixed `result_meta.generated_at`: `{CAPTURE_TIMESTAMP}`
- Current response: `{diff["current_response"]}`
- Current SHA-256: `{diff["current_sha256"]}`
- Candidate SHA-256: `{diff["candidate_sha256"]}`
- Model validation: `backend.app.schemas.adb_analysis.AdbAnalysisEnvelope`

Only `result_meta.generated_at` is normalized. The fixture DuckDB exists solely
inside a Python `TemporaryDirectory` and is removed before these artifacts are
written. The tool does not read a configured DuckDB path and cannot write under
`tests/golden_samples`.

## Added paths

{_markdown_path_list(diff["added_paths"])}

## Removed paths

{_markdown_path_list(diff["removed_paths"])}

## Changed paths

{_markdown_path_list(diff["changed_paths"])}
"""


def capture_candidate(output_dir: str | os.PathLike[str]) -> dict[str, Any]:
    normalized_output = _normalize_new_output_dir(output_dir)
    _assert_no_symlink_junction_or_reparse(
        CURRENT_RESPONSE_PATH,
        field_name="current_golden_response",
    )
    if not CURRENT_RESPONSE_PATH.is_file():
        raise CaptureCandidateError("current_golden_response_missing")

    current_bytes = CURRENT_RESPONSE_PATH.read_bytes()
    try:
        current = json.loads(current_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CaptureCandidateError("current_golden_response_invalid") from exc
    if not isinstance(current, dict):
        raise CaptureCandidateError("current_golden_response_invalid")

    candidate = _validated_candidate_response()
    candidate_bytes = _json_bytes(candidate)
    current_sha256 = _sha256_bytes(current_bytes)
    candidate_sha256 = _sha256_bytes(candidate_bytes)
    diff = _build_diff(
        current=current,
        candidate=candidate,
        current_sha256=current_sha256,
        candidate_sha256=candidate_sha256,
    )
    # These fields are the migration boundary this tool is intended to review.
    # A current golden response may already carry them after a prior recapture,
    # so require them in the validated candidate and accept an existing current
    # path as well as an added path from an old sample.
    for required_path in ("calibration", "result_meta.trace_id"):
        current_value: Any = current
        candidate_value: Any = candidate
        for segment in required_path.split("."):
            current_value = (
                current_value.get(segment, _MISSING)
                if isinstance(current_value, dict)
                else _MISSING
            )
            candidate_value = (
                candidate_value.get(segment, _MISSING)
                if isinstance(candidate_value, dict)
                else _MISSING
            )
        if candidate_value is _MISSING:
            raise CaptureCandidateError(
                f"candidate_missing_{required_path.replace('.', '_')}"
            )
        if current_value is _MISSING and required_path not in diff["added_paths"]:
            raise CaptureCandidateError(
                f"candidate_diff_missing_{required_path.replace('.', '_')}"
            )
    if CURRENT_RESPONSE_PATH.read_bytes() != current_bytes:
        raise CaptureCandidateError("current_golden_response_changed_during_capture")

    output_identity = _create_output_dir(normalized_output)
    _write_new_file(
        normalized_output,
        output_identity,
        "candidate-response.json",
        candidate_bytes,
    )
    _write_new_file(
        normalized_output,
        output_identity,
        "diff.json",
        _json_bytes(diff),
    )
    _write_new_file(
        normalized_output,
        output_identity,
        "README.md",
        _render_readme(diff).encode("utf-8"),
    )
    if CURRENT_RESPONSE_PATH.read_bytes() != current_bytes:
        raise CaptureCandidateError("current_golden_response_changed_during_write")
    _assert_output_identity(normalized_output, output_identity)

    return {
        "status": "candidate_written",
        "output_dir": str(normalized_output),
        "files": list(OUTPUT_FILENAMES),
        "current_sha256": current_sha256,
        "candidate_sha256": candidate_sha256,
        **BOUNDARY_FLAGS,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a non-authoritative ADB monthly golden recapture candidate."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="New directory for candidate artifacts; it must not already exist.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        receipt = capture_candidate(args.output_dir)
    except CaptureCandidateError as exc:
        print(
            json.dumps(
                {"status": "blocked", "reason": str(exc), **BOUNDARY_FLAGS},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
