#!/usr/bin/env python3
"""Ratchet gate for mypy errors in ``backend/app``.

The repository carries a known stock of mypy errors, recorded per file in
``scripts/mypy_baseline.json``. This script keeps that debt from growing:

* runs mypy with the repo config (``backend/pyproject.toml`` ``[tool.mypy]``)
  plus ``--explicit-package-bases`` (required: without it mypy aborts on
  duplicate module names after reporting a single error),
* counts ``error:`` lines per file and compares them with the baseline,
* exits 1 when any file exceeds its baseline count, or when a file that is
  not in the baseline produces errors (the ratchet only goes down, never up),
* reports files that improved so the baseline can be lowered.

Usage::

    python scripts/check_mypy_baseline.py                    # ratchet gate
    python scripts/check_mypy_baseline.py --update-baseline  # refresh baseline

``--update-baseline`` rewrites ``scripts/mypy_baseline.json`` from the current
run. It exists to lock in improvements; any change that *raises* a per-file
count requires explicit reviewer sign-off in the PR description.

Exit codes:
    0  ratchet satisfied
    1  ratchet violated (new or increased mypy errors)
    2  tooling problem (mypy missing, crashed, or output was unparseable)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "scripts" / "mypy_baseline.json"
MYPY_TARGET = "backend/app"
MYPY_CONFIG = "backend/pyproject.toml"
# Keep the cache under .tmp/ (already gitignored) instead of ./.mypy_cache,
# which is not covered by the repo .gitignore.
DEFAULT_CACHE_DIR = REPO_ROOT / ".tmp" / "mypy_cache"

# `backend/app/x.py:12: error: ...` (Windows runs emit backslash separators).
ERROR_LINE_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+)(?::\d+)?: error: ")
SUMMARY_RE = re.compile(r"^Found (?P<errors>\d+) errors? in (?P<files>\d+) files?")

MAX_DETAIL_LINES_PER_FILE = 10


def run_mypy() -> tuple[int, str, str]:
    cmd = [
        sys.executable,
        "-m",
        "mypy",
        MYPY_TARGET,
        "--config-file",
        MYPY_CONFIG,
        "--explicit-package-bases",
        "--no-color-output",
        "--no-pretty",
        "--cache-dir",
        str(DEFAULT_CACHE_DIR),
    ]
    print(f"[mypy-ratchet] running: {' '.join(cmd[1:])}", flush=True)
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def mypy_version() -> str:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "mypy", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return (proc.stdout or proc.stderr).strip()
    except OSError:
        return "unknown"


def parse_errors(stdout: str) -> tuple[dict[str, int], dict[str, list[str]], tuple[int, int] | None]:
    """Return (per-file error counts, per-file error lines, mypy summary)."""
    counts: dict[str, int] = {}
    lines_by_file: dict[str, list[str]] = {}
    summary: tuple[int, int] | None = None
    for raw_line in stdout.splitlines():
        line = raw_line.rstrip()
        match = ERROR_LINE_RE.match(line)
        if match:
            path = match.group("path").replace("\\", "/")
            counts[path] = counts.get(path, 0) + 1
            lines_by_file.setdefault(path, []).append(line)
            continue
        match = SUMMARY_RE.match(line)
        if match:
            summary = (int(match.group("errors")), int(match.group("files")))
    return counts, lines_by_file, summary


def collect_current_errors() -> tuple[dict[str, int], dict[str, list[str]]]:
    """Run mypy and return validated per-file error counts. Exits 2 on tooling problems."""
    returncode, stdout, stderr = run_mypy()

    if "No module named mypy" in stderr:
        print("[mypy-ratchet] FATAL: mypy is not installed in this interpreter "
              f"({sys.executable}). Install mypy and retry.", file=sys.stderr)
        raise SystemExit(2)
    if returncode not in (0, 1):
        print(f"[mypy-ratchet] FATAL: mypy exited with unexpected code {returncode}.", file=sys.stderr)
        _dump_output_tail(stdout, stderr)
        raise SystemExit(2)

    counts, lines_by_file, summary = parse_errors(stdout)

    if returncode == 1 and not counts:
        print("[mypy-ratchet] FATAL: mypy reported failure but no error lines could be parsed.",
              file=sys.stderr)
        _dump_output_tail(stdout, stderr)
        raise SystemExit(2)

    # Cross-check our parser against mypy's own summary so the ratchet cannot
    # silently pass because of a parsing bug.
    if summary is not None:
        parsed_total = sum(counts.values())
        if parsed_total != summary[0] or len(counts) != summary[1]:
            print(
                "[mypy-ratchet] FATAL: parsed totals "
                f"({parsed_total} errors / {len(counts)} files) do not match mypy summary "
                f"({summary[0]} errors / {summary[1]} files). Parser needs fixing.",
                file=sys.stderr,
            )
            raise SystemExit(2)

    return counts, lines_by_file


def _dump_output_tail(stdout: str, stderr: str, limit: int = 30) -> None:
    for label, stream in (("stdout", stdout), ("stderr", stderr)):
        tail = stream.strip().splitlines()[-limit:]
        if tail:
            print(f"--- mypy {label} (last {len(tail)} lines) ---", file=sys.stderr)
            for line in tail:
                print(line, file=sys.stderr)


def load_baseline() -> dict[str, int]:
    if not BASELINE_PATH.exists():
        print(f"[mypy-ratchet] FATAL: baseline file not found: {BASELINE_PATH}\n"
              "Generate it with: python scripts/check_mypy_baseline.py --update-baseline",
              file=sys.stderr)
        raise SystemExit(2)
    try:
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        files = data["files"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"[mypy-ratchet] FATAL: baseline file is invalid ({exc}): {BASELINE_PATH}",
              file=sys.stderr)
        raise SystemExit(2)
    return {str(path): int(count) for path, count in files.items()}


def save_baseline(counts: dict[str, int]) -> None:
    data = {
        "_meta": {
            "description": (
                "Per-file mypy error baseline for the ratchet gate "
                "(scripts/check_mypy_baseline.py). Counts may only decrease; "
                "raising any count requires explicit reviewer sign-off."
            ),
            "command": (
                "mypy backend/app --config-file backend/pyproject.toml --explicit-package-bases"
            ),
            "mypy_version": mypy_version(),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_errors": sum(counts.values()),
            "total_files": len(counts),
        },
        "files": {path: counts[path] for path in sorted(counts)},
    }
    BASELINE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def compare(
    baseline: dict[str, int], counts: dict[str, int]
) -> tuple[list[tuple[str, int, int]], list[tuple[str, int]], list[tuple[str, int, int]]]:
    regressions: list[tuple[str, int, int]] = []
    new_files: list[tuple[str, int]] = []
    improvements: list[tuple[str, int, int]] = []
    for path in sorted(counts):
        current = counts[path]
        base = baseline.get(path)
        if base is None:
            new_files.append((path, current))
        elif current > base:
            regressions.append((path, base, current))
        elif current < base:
            improvements.append((path, base, current))
    for path in sorted(baseline):
        if baseline[path] > 0 and path not in counts:
            improvements.append((path, baseline[path], 0))
    return regressions, new_files, improvements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="rewrite scripts/mypy_baseline.json from the current mypy run "
             "(requires reviewer sign-off when any count increases)",
    )
    args = parser.parse_args()

    counts, lines_by_file = collect_current_errors()
    current_total = sum(counts.values())
    print(f"[mypy-ratchet] current: {current_total} error(s) in {len(counts)} file(s)")

    if args.update_baseline:
        had_previous = BASELINE_PATH.exists()
        previous = {}
        if had_previous:
            try:
                previous = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("files", {})
            except json.JSONDecodeError:
                previous = {}
        save_baseline(counts)
        print(f"[mypy-ratchet] baseline written: {BASELINE_PATH}")
        if not had_previous:
            print(f"[mypy-ratchet] initial baseline: {current_total} error(s) in {len(counts)} file(s)")
            print("WARNING: commit the new baseline together with a PR note explaining its origin.")
            return 0
        prev_total = sum(previous.values())
        print(f"[mypy-ratchet] totals: {prev_total} error(s) in {len(previous)} file(s) "
              f"-> {current_total} error(s) in {len(counts)} file(s)")
        increased = sorted(
            path for path, count in counts.items() if count > int(previous.get(path, 0))
        )
        print("=" * 72)
        print("WARNING: mypy baseline was rewritten in place.")
        print("  - Commit this file only together with a PR note explaining WHY.")
        if increased:
            print(f"  - {len(increased)} file(s) INCREASED vs the previous baseline; this weakens")
            print("    the ratchet and REQUIRES explicit reviewer sign-off:")
            for path in increased[:20]:
                print(f"      {path}: {int(previous.get(path, 0))} -> {counts[path]}")
            if len(increased) > 20:
                print(f"      ... and {len(increased) - 20} more")
        else:
            print("  - No per-file count increased (lock-in of improvements only).")
        print("=" * 72)
        return 0

    baseline = load_baseline()
    baseline_total = sum(baseline.values())
    print(f"[mypy-ratchet] baseline: {baseline_total} error(s) in {len(baseline)} file(s)")

    regressions, new_files, improvements = compare(baseline, counts)

    if improvements:
        improved_by = sum(base - current for _, base, current in improvements)
        print(f"[mypy-ratchet] IMPROVEMENT: {len(improvements)} file(s) below baseline "
              f"(-{improved_by} error(s)). Consider locking this in with --update-baseline.")

    if not regressions and not new_files:
        print("[mypy-ratchet] OK: no new mypy errors; ratchet satisfied.")
        return 0

    print()
    if regressions:
        print(f"[mypy-ratchet] RATCHET VIOLATION: {len(regressions)} file(s) exceed the baseline:")
        for path, base, current in regressions:
            print(f"  {path}: baseline {base} -> current {current} (+{current - base})")
            for line in lines_by_file.get(path, [])[:MAX_DETAIL_LINES_PER_FILE]:
                print(f"    {line}")
    if new_files:
        print(f"[mypy-ratchet] RATCHET VIOLATION: {len(new_files)} file(s) with errors "
              "are not in the baseline:")
        for path, current in new_files:
            print(f"  {path}: {current} error(s)")
            for line in lines_by_file.get(path, [])[:MAX_DETAIL_LINES_PER_FILE]:
                print(f"    {line}")
    print()
    print("[mypy-ratchet] Fix the new type errors (preferred). If the increase is truly")
    print("[mypy-ratchet] unavoidable, refresh with --update-baseline and obtain reviewer sign-off.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
