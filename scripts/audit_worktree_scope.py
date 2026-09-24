from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class WorktreeChange:
    status: str
    path: str
    original_path: str | None = None


def _decode_path(raw: bytes) -> str:
    return raw.decode("utf-8", errors="surrogateescape")


def parse_porcelain_z(raw: bytes) -> list[WorktreeChange]:
    """Parse git status porcelain v1 Z output without losing spaces or rename paths."""
    tokens = raw.split(bytes([0]))
    changes: list[WorktreeChange] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        if len(token) < 4 or token[2:3] != b" ":
            raise ValueError(f"Unexpected git porcelain record: {token!r}")
        status = token[:2].decode("ascii", errors="strict")
        path = _decode_path(token[3:])
        original_path = None
        if "R" in status or "C" in status:
            if index >= len(tokens) or not tokens[index]:
                raise ValueError(f"Missing original path for git status {status!r}: {path}")
            original_path = _decode_path(tokens[index])
            index += 1
        changes.append(
            WorktreeChange(
                status=status,
                path=path,
                original_path=original_path,
            )
        )
    return changes


def _normalize_scope_path(value: str) -> str:
    normalized = str(PurePosixPath(value.replace(chr(92), "/"))).removeprefix("./")
    normalized = normalized.rstrip("/")
    if not normalized or normalized == "." or normalized.startswith("../"):
        raise ValueError(f"Allowed path must stay inside the repository: {value!r}")
    return normalized


def _path_is_allowed(path: str, allowed_paths: Sequence[str]) -> bool:
    return any(path == allowed or path.startswith(f"{allowed}/") for allowed in allowed_paths)


def audit_worktree_scope(
    changes: Sequence[WorktreeChange],
    *,
    allowed_paths: Sequence[str],
) -> dict[str, object]:
    normalized_allowed = sorted({_normalize_scope_path(path) for path in allowed_paths})
    changed_paths = sorted(
        {
            path
            for change in changes
            for path in (change.path, change.original_path)
            if path is not None
        }
    )
    outside_paths = [
        path for path in changed_paths if not _path_is_allowed(path, normalized_allowed)
    ]
    return {
        "scope_ok": not outside_paths,
        "strict_required_to_block": True,
        "allowed_paths": normalized_allowed,
        "changed_path_count": len(changed_paths),
        "inside_paths": [path for path in changed_paths if path not in outside_paths],
        "outside_paths": outside_paths,
        "changes": [
            {
                "status": change.status,
                "path": change.path,
                "original_path": change.original_path,
            }
            for change in changes
        ],
    }


def _git_status_porcelain(repo_root: Path) -> bytes:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def main(
    argv: list[str] | None = None,
    *,
    status_bytes: bytes | None = None,
    repo_root: Path = ROOT,
) -> int:
    parser = argparse.ArgumentParser(
        description="Report changed files outside an explicitly allowed task scope.",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="REPO_PATH",
        help="Allowed repository path or directory prefix; repeat as needed.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 1 when any changed path is outside the allowlist.",
    )
    args = parser.parse_args(argv)

    raw_status = status_bytes if status_bytes is not None else _git_status_porcelain(repo_root)
    report = audit_worktree_scope(
        parse_porcelain_z(raw_status),
        allowed_paths=args.allow,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.strict and not report["scope_ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
