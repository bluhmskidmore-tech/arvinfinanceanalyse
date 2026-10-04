"""Preview archive relocation or copy during an owned offline maintenance window.

The receipt records physical locations, not new source or governance identities.
Creation trusts the operator's local filesystem access and a stopped immutable
source archive. The operator must protect the receipt/archive ACLs after a real
maintenance-window migration; its SHA256 values are not an external signature.
Receipts use the generating host's absolute-path semantics. Moving historical
archive identities between Windows and Linux is outside this tool's scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.repositories.object_store_repo import (  # noqa: E402
    ARCHIVE_RELOCATION_RECEIPT,
    _require_no_archive_links,
    _require_host_archive_path,
    _unique_archive_receipt_object,
)
from scripts.dev_runtime_control import operation_lock, require_owner  # noqa: E402

SAMPLE_OWNERSHIP_MARKER = ".moss-archive-migration-sample.json"
OFFLINE_RECEIPT_PURPOSE = "moss-archive-migration-offline"
WRITER_EXCLUSION_FIELDS = frozenset({
    "new_requests_paused", "inflight_writers_drained", "automatic_restarts_paused", "source_archive_frozen",
})


def _raise_walk_error(error: OSError) -> None:
    raise error


def _file_sha256(path: Path) -> str:
    _require_no_archive_links(path)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        before = os.fstat(source.fileno())
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(source.fileno())
    _require_no_archive_links(path)
    current = path.stat()
    def identity(item):
        return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns
    if not stat.S_ISREG(before.st_mode) or identity(before) != identity(after) or identity(after) != identity(current):
        raise ValueError("archive source changed during relocation preflight")
    return digest.hexdigest()


def plan_archive_relocation(source_root: Path, target_root: Path) -> dict:
    _require_host_archive_path(source_root)
    _require_host_archive_path(target_root)
    source_root = Path(os.path.abspath(source_root))
    target_root = Path(os.path.abspath(target_root))
    _require_no_archive_links(source_root)
    _require_no_archive_links(target_root)
    _require_no_archive_links(target_root / ARCHIVE_RELOCATION_RECEIPT)
    if not source_root.is_dir():
        raise ValueError("source archive must be an existing directory")
    if source_root.is_relative_to(target_root) or target_root.is_relative_to(source_root):
        raise ValueError("source and target archives must not overlap")
    if (target_root / ARCHIVE_RELOCATION_RECEIPT).exists():
        raise ValueError("target already has an archive relocation receipt")
    entries = []
    source_metadata = {}
    for current, directories, files in os.walk(source_root, followlinks=False, onerror=_raise_walk_error):
        for name in [*directories, *files]:
            _require_no_archive_links(Path(current) / name)
        for name in sorted(files):
            path = Path(current) / name
            if name == ARCHIVE_RELOCATION_RECEIPT:
                raise ValueError("chained archive relocations require an explicit maintenance plan")
            relative = path.relative_to(source_root).as_posix()
            if "\\" in relative or ":" in relative:
                raise ValueError("archive filename cannot form a portable relocation target")
            target = target_root / relative
            digest = _file_sha256(path)
            metadata = path.stat()
            source_metadata[str(path)] = {"bytes": metadata.st_size, "mtime_ns": metadata.st_mtime_ns}
            if target.exists() and _file_sha256(target) != digest:
                raise ValueError("target archive has a conflicting file")
            entries.append({"source_path": str(path), "target_relative_path": relative, "sha256": digest})
    entries.sort(key=lambda entry: entry["source_path"])
    return {
        "source_root": str(source_root),
        "target_root": str(target_root),
        "source_metadata": source_metadata,
        "receipt": {"format_version": 1, "source_archive_root": str(source_root), "entries": entries},
    }


def _copy_archive_and_write_receipt(plan: dict, *, before_publish: Callable[[], None] | None = None) -> Path:
    """Reusable copy core; callers must establish ownership and write exclusion."""
    source_root, target_root = Path(plan["source_root"]), Path(plan["target_root"])
    # Rebuild immediately before copying so a stale caller-supplied plan cannot
    # invent source identities or self-assert content hashes.
    verified_plan = plan_archive_relocation(source_root, target_root)
    if json.dumps(verified_plan, sort_keys=True) != json.dumps(plan, sort_keys=True):
        raise ValueError("archive relocation plan changed before execution")
    plan = verified_plan
    target_root.mkdir(parents=True, exist_ok=True)
    for entry in plan["receipt"]["entries"]:
        source = Path(entry["source_path"])
        target = target_root / entry["target_relative_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        _require_no_archive_links(target)
        if target.exists():
            if _file_sha256(target) != entry["sha256"]:
                raise ValueError("target archive changed before copying")
            continue
        with source.open("rb") as reader, target.open("xb") as writer:
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        os.utime(target, ns=(source.stat().st_atime_ns, plan["source_metadata"][entry["source_path"]]["mtime_ns"]))
        if _file_sha256(source) != entry["sha256"] or _file_sha256(target) != entry["sha256"]:
            raise ValueError("archive source or copy differs from relocation preflight")
    # A previously copied file or the source file set could change while later
    # files are copied. Publish no receipt until the complete copy is rechecked.
    final_plan = plan_archive_relocation(source_root, target_root)
    if json.dumps(final_plan, sort_keys=True) != json.dumps(plan, sort_keys=True):
        raise ValueError("archive source set changed during copying")
    actual_targets = set()
    for current, directories, files in os.walk(target_root, followlinks=False, onerror=_raise_walk_error):
        for name in [*directories, *files]:
            _require_no_archive_links(Path(current) / name)
        actual_targets.update((Path(current) / name).relative_to(target_root).as_posix() for name in files)
    if actual_targets != {entry["target_relative_path"] for entry in plan["receipt"]["entries"]}:
        raise ValueError("archive copy file set differs from relocation preflight")
    for entry in plan["receipt"]["entries"]:
        if (target_root / entry["target_relative_path"]).stat().st_mtime_ns != plan["source_metadata"][entry["source_path"]]["mtime_ns"]:
            raise ValueError("archive copy did not preserve source modification time")
    if before_publish is not None:
        before_publish()
    receipt_path = target_root / ARCHIVE_RELOCATION_RECEIPT
    _require_no_archive_links(receipt_path)
    # Exclusive creation preserves any existing unique receipt. Write through
    # one handle, flush it, then publish atomically without replacing a receipt.
    staging = target_root / f"{ARCHIVE_RELOCATION_RECEIPT}.{uuid4().hex}.tmp"
    with staging.open("xb") as writer:
        writer.write((json.dumps(plan["receipt"], ensure_ascii=True, sort_keys=True) + "\n").encode("utf-8"))
        writer.flush()
        os.fsync(writer.fileno())
    if receipt_path.exists():
        raise ValueError("target relocation receipt appeared during copying")
    if os.name == "nt":
        staging.rename(receipt_path)
    else:
        # link() creates an exclusive new name; rename() would overwrite on POSIX.
        os.link(staging, receipt_path)
        staging.unlink()
    receipt_path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    return receipt_path


def apply_sample_archive_relocation(plan: dict, owned_sample_root: Path) -> Path:
    owned = Path(os.path.abspath(owned_sample_root))
    _require_no_archive_links(owned)
    temp_root = Path(tempfile.gettempdir()).resolve()
    if owned == temp_root or not owned.is_relative_to(temp_root):
        raise ValueError("sample ownership must be a specific task temporary directory")
    marker = owned / SAMPLE_OWNERSHIP_MARKER
    _require_no_archive_links(marker)
    ownership = json.loads(marker.read_bytes())
    if (
        not isinstance(ownership, dict)
        or set(ownership) != {"format_version", "purpose"}
        or type(ownership["format_version"]) is not int
        or ownership != {"format_version": 1, "purpose": "moss-archive-migration-sample"}
    ):
        raise ValueError("sample ownership marker is invalid")
    for value in (plan["source_root"], plan["target_root"]):
        path = Path(value)
        if path == owned or not path.is_relative_to(owned):
            raise ValueError("archive relocation escapes the owned sample directory")
    return _copy_archive_and_write_receipt(plan)


def _require_offline_receipt(plan: dict, repo_root: Path, maintenance: dict, receipt_path: Path) -> None:
    """Check the operator's exact-path attestation; this is not a process drain probe."""
    evidence_root = repo_root / ".codex-tmp"
    receipt_path = Path(os.path.abspath(receipt_path))
    _require_no_archive_links(receipt_path)
    if not receipt_path.is_relative_to(evidence_root) or not receipt_path.is_file():
        raise ValueError("offline receipt must be a local task file under repository .codex-tmp")
    receipt = json.loads(receipt_path.read_bytes(), object_pairs_hook=_unique_archive_receipt_object)
    expected_keys = {
        "format_version", "purpose", "repo_root", "source_root", "target_root",
        "maintenance_entered_at", "writer_exclusion", "evidence_files",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != expected_keys
        or type(receipt["format_version"]) is not int
        or receipt["format_version"] != 1
        or receipt["purpose"] != OFFLINE_RECEIPT_PURPOSE
        or receipt["repo_root"] != str(repo_root)
        or receipt["source_root"] != plan["source_root"]
        or receipt["target_root"] != plan["target_root"]
        or type(receipt["maintenance_entered_at"]) not in {int, float}
        or receipt["maintenance_entered_at"] != maintenance.get("entered_at")
    ):
        raise ValueError("offline receipt does not match this maintenance relocation")
    exclusion = receipt["writer_exclusion"]
    if (
        not isinstance(exclusion, dict)
        or set(exclusion) != WRITER_EXCLUSION_FIELDS
        or any(value is not True for value in exclusion.values())
    ):
        raise ValueError("offline receipt must explicitly attest all writer exclusions")
    evidence_files = receipt["evidence_files"]
    if not isinstance(evidence_files, list) or not evidence_files:
        raise ValueError("offline receipt must bind local writer exclusion evidence")
    seen = set()
    for evidence in evidence_files:
        if not isinstance(evidence, dict) or set(evidence) != {"path", "sha256"}:
            raise ValueError("offline receipt evidence entry is invalid")
        value = evidence["path"]
        if not isinstance(value, str):
            raise ValueError("offline receipt evidence path is invalid")
        _require_host_archive_path(value)
        path = Path(os.path.abspath(value))
        if (
            str(path) != value or path == receipt_path or not path.is_relative_to(evidence_root)
            or path in seen or not path.is_file()
        ):
            raise ValueError("offline receipt evidence must be unique local task files")
        seen.add(path)
        if _file_sha256(path) != evidence["sha256"]:
            raise ValueError("offline receipt writer exclusion evidence changed")


def apply_maintenance_archive_relocation(
    plan: dict, *, repo_root: Path, owner_token: str, offline_receipt: Path,
) -> Path:
    """Copy only; the maintenance owner remains responsible for drain and cutover."""
    repo_root = Path(os.path.abspath(repo_root))
    _require_host_archive_path(repo_root)
    _require_no_archive_links(repo_root)
    if not (repo_root / "scripts" / "dev_runtime_control.py").is_file():
        raise ValueError("maintenance repository must have the existing runtime controller")
    source_root, target_root = Path(plan["source_root"]), Path(plan["target_root"])
    if not source_root.is_relative_to(repo_root) or target_root.is_relative_to(repo_root):
        raise ValueError("maintenance relocation must copy a repository archive to an external target")
    # The existing lock prevents cooperating launchers or another owner changing
    # maintenance while the offline archive and its receipt are copied.
    with operation_lock(repo_root):
        maintenance = require_owner(repo_root, owner_token)
        _require_offline_receipt(plan, repo_root, maintenance, offline_receipt)
        _require_no_archive_links(target_root)
        if target_root.exists() and (not target_root.is_dir() or any(target_root.iterdir())):
            raise ValueError("maintenance relocation target must be absent or empty")
        def require_current_exclusion() -> None:
            current_maintenance = require_owner(repo_root, owner_token)
            _require_offline_receipt(plan, repo_root, current_maintenance, offline_receipt)
        return _copy_archive_and_write_receipt(plan, before_publish=require_current_exclusion)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-sample", action="store_true")
    mode.add_argument("--apply-maintenance", action="store_true")
    parser.add_argument("--owned-sample-root", type=Path)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--owner-token")
    parser.add_argument("--offline-receipt", type=Path)
    args = parser.parse_args()
    plan = plan_archive_relocation(args.source_root, args.target_root)
    if args.write_sample:
        if args.owned_sample_root is None:
            parser.error("--write-sample requires --owned-sample-root")
        receipt = apply_sample_archive_relocation(plan, args.owned_sample_root)
        result = {"mode": "sample-written", "receipt": str(receipt)}
    elif args.apply_maintenance:
        if args.repo_root is None or not args.owner_token or args.offline_receipt is None:
            parser.error("--apply-maintenance requires --repo-root, --owner-token and --offline-receipt")
        receipt = apply_maintenance_archive_relocation(
            plan, repo_root=args.repo_root, owner_token=args.owner_token, offline_receipt=args.offline_receipt,
        )
        result = {"mode": "maintenance-copied", "receipt": str(receipt)}
    else:
        result = {"mode": "preview", "source_root": plan["source_root"], "target_root": plan["target_root"]}
    result["file_count"] = len(plan["receipt"]["entries"])
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
