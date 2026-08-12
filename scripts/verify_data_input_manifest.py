#!/usr/bin/env python3
"""Verify docs/data/data_input_manifest.json against the on-disk data_input/ tree.

Directory-level governance check (C2-MANIFEST):

- every directory registered in the manifest exists on disk;
- no unregistered top-level directory appears under data_input/;
- top-level files conform to the registered file-family naming patterns
  (or are explicitly registered exceptions);
- files inside each registered directory conform to that directory's
  naming patterns (or are registered exceptions); nested subdirectories
  must be listed in ``allowed_subdirectories``.

File-level registration is intentionally out of scope (~1300 files);
content authenticity is governed by source_file_hash records instead.
File-count drift versus the manifest snapshot is reported as
informational only, because daily deliveries grow the tree by design.

Exit codes:
    0  verification passed, or data_input/ does not exist (CI checkout skip)
    1  verification failed (details printed with [FAIL] prefix)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_RELPATH = Path("docs") / "data" / "data_input_manifest.json"
MAX_SAMPLES = 10


def _resolve_data_root() -> Path:
    override = str(os.environ.get("MOSS_DATA_INPUT_ROOT", "") or "").strip()
    if override:
        candidate = Path(override).expanduser()
        return candidate if candidate.is_absolute() else (REPO_ROOT / candidate)
    return REPO_ROOT / "data_input"


def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def _matches_any(name: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(regex.match(name) for regex in patterns)


def _sample(names: list[str]) -> str:
    shown = ", ".join(names[:MAX_SAMPLES])
    extra = len(names) - MAX_SAMPLES
    return shown + (f" ... (+{extra} more)" if extra > 0 else "")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    data_root = _resolve_data_root()
    if not data_root.is_dir():
        print(
            f"[skip] data_input directory not found at {data_root}; "
            "nothing to verify (expected for CI checkouts, the directory is gitignored). Exit 0."
        )
        return 0

    manifest_path = REPO_ROOT / MANIFEST_RELPATH
    if not manifest_path.is_file():
        print(f"[FAIL] manifest not found: {manifest_path}")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))

    errors: list[str] = []
    infos: list[str] = []

    # -- 1. Top-level directory registration -------------------------------
    directories = {entry["path"]: entry for entry in manifest.get("directories", [])}
    actual_dirs = {path.name for path in data_root.iterdir() if path.is_dir()}

    for missing in sorted(set(directories) - actual_dirs):
        errors.append(f"registered directory missing on disk: {missing}/")
    for unregistered in sorted(actual_dirs - set(directories)):
        errors.append(
            f"unregistered top-level directory: {unregistered}/ "
            f"(register it in {MANIFEST_RELPATH.as_posix()} or remove it)"
        )

    # -- 2. Top-level loose files against family patterns ------------------
    family_patterns = _compile(
        [
            pattern
            for family in manifest.get("top_level_file_families", [])
            for pattern in family.get("filename_patterns", [])
        ]
    )
    top_exceptions = {
        entry["file"] for entry in manifest.get("top_level_registered_exceptions", [])
    }
    top_files = [path.name for path in data_root.iterdir() if path.is_file()]
    bad_top = sorted(
        name
        for name in top_files
        if name not in top_exceptions and not _matches_any(name, family_patterns)
    )
    if bad_top:
        errors.append(
            f"{len(bad_top)} top-level file(s) violate registered naming patterns: {_sample(bad_top)}"
        )

    snapshot = manifest.get("counts_snapshot", {})
    snapshot_top = snapshot.get("top_level_files")
    if snapshot_top is not None and snapshot_top != len(top_files):
        infos.append(
            f"top-level file count drift: snapshot={snapshot_top} now={len(top_files)} (informational)"
        )

    # -- 3. Per-directory naming and subdirectory checks -------------------
    for name in sorted(set(directories) & actual_dirs):
        entry = directories[name]
        dir_path = data_root / name
        allowed_subdirs = set(entry.get("allowed_subdirectories", []))
        patterns = _compile(entry.get("filename_patterns", []))
        exceptions = {item["file"] for item in entry.get("registered_exceptions", [])}

        bad_subdirs: list[str] = []
        bad_files: list[str] = []
        file_count = 0
        for item in dir_path.rglob("*"):
            rel = item.relative_to(dir_path).as_posix()
            if item.is_dir():
                if rel not in allowed_subdirs:
                    bad_subdirs.append(rel)
                continue
            file_count += 1
            if item.name in exceptions:
                continue
            if not _matches_any(item.name, patterns):
                bad_files.append(rel)

        if bad_subdirs:
            errors.append(f"{name}/: unregistered subdirectories: {_sample(sorted(bad_subdirs))}")
        if bad_files:
            errors.append(
                f"{name}/: {len(bad_files)} file(s) violate registered naming patterns: "
                f"{_sample(sorted(bad_files))}"
            )

        snapshot_total = entry.get("file_count_snapshot", {}).get("total")
        if snapshot_total is not None and snapshot_total != file_count:
            infos.append(
                f"{name}/ file count drift: snapshot={snapshot_total} now={file_count} (informational)"
            )

    # -- 4. Report ----------------------------------------------------------
    for line in infos:
        print(f"[info] {line}")
    if errors:
        for line in errors:
            print(f"[FAIL] {line}")
        print(f"[FAIL] data_input manifest verification failed with {len(errors)} error(s).")
        return 1

    print(
        f"[ok] data_input manifest verification passed: {len(directories)} registered directories, "
        f"{len(top_files)} top-level files conform to registered patterns."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
