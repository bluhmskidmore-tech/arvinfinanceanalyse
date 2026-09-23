#!/usr/bin/env python3
"""Ratchet gate for individual mypy diagnostics in ``backend/app``.

Diagnostic identities bind the path, error code, message, lexical scope and
normalized statement AST. Counts are reporting data, never permission to replace
an old error with a new one. A count-only baseline fails closed until historical
diagnostics have been recovered with matching per-file counts and provenance.

Usage::

    python scripts/check_mypy_baseline.py                    # ratchet gate
    python scripts/check_mypy_baseline.py --update-baseline  # refresh baseline

``--update-baseline`` only removes identities from an existing validated baseline.
It cannot seed a missing baseline, migrate counts, or absorb new diagnostics.

Exit codes:
    0  ratchet satisfied
    1  ratchet violated (new or changed diagnostic identities)
    2  missing/untrustworthy evidence, migration required, or tooling problem
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "scripts" / "mypy_baseline.json"
MYPY_TARGET = "backend/app"
MYPY_CONFIG = "backend/pyproject.toml"
EXPECTED_MYPY_VERSION = "mypy 1.20.1"
EXPECTED_PYTHON_VERSION = (3, 11)
BASELINE_SCHEMA_VERSION = 2
# Keep the cache under .tmp/ (already gitignored) instead of ./.mypy_cache,
# which is not covered by the repo .gitignore.
DEFAULT_CACHE_DIR = REPO_ROOT / ".tmp" / "mypy_cache"

# `backend/app/x.py:12: error: ...` (Windows runs emit backslash separators).
ERROR_LINE_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+)(?::\d+)?: error: ")
SUMMARY_RE = re.compile(r"^Found (?P<errors>\d+) errors? in (?P<files>\d+) files?")
DIAGNOSTIC_RE = re.compile(
    r"^(?P<path>.+?):(?P<row>\d+)(?::(?P<column>\d+))?: error: "
    r"(?P<message>.+?)\s+\[(?P<code>[a-z0-9-]+)\]$"
)
SHA256_RE = re.compile(r"[a-f0-9]{64}\Z")
GIT_SHA_RE = re.compile(r"[a-f0-9]{40}\Z")

MAX_DETAIL_LINES_PER_FILE = 10


class EvidenceError(ValueError):
    """The gate cannot make a trustworthy diagnostic comparison."""


@dataclass(frozen=True)
class Diagnostic:
    path: str
    code: str
    message: str
    scope: str
    statement_ast_sha256: str
    control_flow_sha256: str
    statement_occurrence: int
    occurrence: int
    row: int
    column: int

    @property
    def identity(self) -> str:
        # Locations are retained for audit display, not used as identities.
        fields = asdict(self)
        fields.pop("row")
        fields.pop("column")
        return _digest(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require_tool_versions() -> None:
    if sys.version_info[:2] != EXPECTED_PYTHON_VERSION:
        raise EvidenceError("Python version mismatch: expected 3.11; AST identities require the pinned interpreter")
    observed = mypy_version()
    if observed not in {
        EXPECTED_MYPY_VERSION,
        f"{EXPECTED_MYPY_VERSION} (compiled: yes)",
        f"{EXPECTED_MYPY_VERSION} (compiled: no)",
    }:
        raise EvidenceError(f"mypy version mismatch: expected {EXPECTED_MYPY_VERSION}, got {observed}")


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
        "--show-error-codes",
        "--show-column-numbers",
        "--cache-dir",
        str(DEFAULT_CACHE_DIR),
    ]
    print(f"[mypy-ratchet] running: {' '.join(cmd[1:])}", flush=True)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
        )
    except (OSError, UnicodeError) as exc:
        raise EvidenceError(f"cannot execute mypy: {exc}") from exc
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
        print(
            "[mypy-ratchet] FATAL: mypy is not installed in this interpreter "
            f"({sys.executable}). Install mypy and retry.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if returncode not in (0, 1):
        print(f"[mypy-ratchet] FATAL: mypy exited with unexpected code {returncode}.", file=sys.stderr)
        _dump_output_tail(stdout, stderr)
        raise SystemExit(2)

    counts, lines_by_file, summary = parse_errors(stdout)

    if returncode == 1 and not counts:
        print("[mypy-ratchet] FATAL: mypy reported failure but no error lines could be parsed.", file=sys.stderr)
        _dump_output_tail(stdout, stderr)
        raise SystemExit(2)

    if returncode == 0 and (counts or not stdout.startswith("Success: no issues found")):
        raise EvidenceError("mypy success response is missing or contradicts its diagnostics")
    if returncode == 1 and summary is None:
        raise EvidenceError("mypy failure has no complete diagnostic summary")

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


def _normalized_path(value: str, repo_root: Path) -> str:
    path = Path(value)
    if path.is_absolute():
        try:
            value = path.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError as exc:
            raise EvidenceError(f"diagnostic is outside repository: {value}") from exc
    else:
        value = value.replace("\\", "/")
    normalized = PurePosixPath(value)
    if (
        normalized.is_absolute()
        or ".." in normalized.parts
        or ":" in value
        or normalized.as_posix() != value
        or not value.startswith(("backend/", "scripts/"))
        or not value.endswith(".py")
    ):
        raise EvidenceError(f"diagnostic path must be normalized under backend or scripts: {value}")
    try:
        (repo_root / value).resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise EvidenceError(f"diagnostic source resolves outside repository: {value}") from exc
    return value


def _statement_contexts(source: str, path: str) -> list[tuple[ast.stmt, str, str, str, int]]:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise EvidenceError(f"cannot parse diagnostic source {path}: {exc}") from exc
    contexts: list[tuple[ast.stmt, str, str, str, int]] = []
    scopes: Counter[tuple[str, ...]] = Counter()
    occurrences: Counter[tuple[str, str, str]] = Counter()
    control_nodes = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.With,
        ast.AsyncWith,
        ast.Try,
        ast.TryStar,
        ast.ExceptHandler,
        ast.Match,
        ast.match_case,
    )
    block_fields = {"body", "orelse", "finalbody", "handlers", "cases"}

    def visit(node: ast.AST, scope: tuple[str, ...], control_path: tuple[str, ...]) -> None:
        scope_name = "/".join(scope) or "<module>"
        if isinstance(node, ast.stmt):
            digest = _digest(ast.dump(node, include_attributes=False).encode("utf-8"))
            control_digest = _digest("\0".join(control_path).encode("utf-8"))
            key = (scope_name, digest, control_digest)
            occurrences[key] += 1
            contexts.append((node, scope_name, digest, control_digest, occurrences[key]))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = f"{type(node).__name__}:{node.name}"
            scopes[(*scope, name)] += 1
            scope = (*scope, f"{name}#{scopes[(*scope, name)]}")
        for field, value in ast.iter_fields(node):
            children = value if isinstance(value, list) else [value]
            for index, child in enumerate(children):
                if not isinstance(child, ast.AST):
                    continue
                child_path = control_path
                if isinstance(node, control_nodes) and field in block_fields:
                    # Retain tests/iterators/handler types/patterns and which branch
                    # contains the statement, without fingerprinting sibling bodies.
                    header = []
                    for name, header_value in ast.iter_fields(node):
                        if name in block_fields:
                            continue
                        values = header_value if isinstance(header_value, list) else [header_value]
                        header.append((name, tuple(
                            ast.dump(value, include_attributes=False) if isinstance(value, ast.AST) else repr(value)
                            for value in values
                        )))
                    branch = f"{field}[{index}]" if field in {"handlers", "cases"} else field
                    frame = f"{type(node).__name__}:{header!r}:{branch}"
                    child_path = (*control_path, frame)
                visit(child, scope, child_path)

    visit(tree, (), ())
    return contexts


def build_diagnostics(
    lines_by_file: dict[str, list[str]],
    repo_root: Path | None = None,
) -> list[Diagnostic]:
    """Bind parsed diagnostics to the exact source tree used by that mypy run."""
    root = repo_root or REPO_ROOT
    diagnostics: list[Diagnostic] = []
    occurrences: Counter[tuple[str, str, str, str, str, str, int]] = Counter()
    for file_path, lines in sorted(lines_by_file.items()):
        path = _normalized_path(file_path, root)
        try:
            source = (root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise EvidenceError(f"cannot read diagnostic source {path}: {exc}") from exc
        contexts = _statement_contexts(source, path)
        for raw_line in lines:
            match = DIAGNOSTIC_RE.fullmatch(raw_line)
            if match is None or _normalized_path(match["path"], root) != path:
                raise EvidenceError(f"diagnostic has no trustworthy path/code/location: {raw_line}")
            row, column = int(match["row"]), int(match["column"] or 0)
            if not column and match["code"] != "unused-ignore":
                raise EvidenceError(f"diagnostic lacks column evidence; rerun with --show-column-numbers: {raw_line}")
            candidates = [
                item
                for item in contexts
                if item[0].lineno <= row <= (item[0].end_lineno or item[0].lineno)
                and (not column or item[0].lineno != row or item[0].col_offset < column)
            ]
            if not candidates:
                raise EvidenceError(f"diagnostic does not map to a statement: {raw_line}")
            if not column:
                span = min((item[0].end_lineno or item[0].lineno) - item[0].lineno for item in candidates)
                if sum((item[0].end_lineno or item[0].lineno) - item[0].lineno == span for item in candidates) > 1:
                    raise EvidenceError(f"columnless diagnostic maps to multiple statements: {raw_line}")
            _, scope, digest, control_digest, statement_occurrence = min(
                candidates,
                key=lambda item: (
                    (item[0].end_lineno or item[0].lineno) - item[0].lineno,
                    -item[0].col_offset,
                ),
            )
            key = (path, match["code"], match["message"], scope, digest, control_digest, statement_occurrence)
            occurrences[key] += 1
            diagnostics.append(Diagnostic(*key, occurrences[key], row, column))
    return diagnostics


def compare_diagnostics(
    baseline: list[Diagnostic],
    current: list[Diagnostic],
) -> tuple[list[Diagnostic], list[Diagnostic]]:
    old = {item.identity for item in baseline}
    new = {item.identity for item in current}
    if len(old) != len(baseline) or len(new) != len(current):
        raise EvidenceError("duplicate diagnostic identities")
    return (
        [item for item in current if item.identity not in old],
        [item for item in baseline if item.identity not in new],
    )


def _source_manifest_digest(sources: list[list[str]]) -> str:
    return _digest(json.dumps(sources, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _validate_provenance(meta: dict[str, Any]) -> set[str]:
    if (
        meta.get("python_version") != "3.11"
        or meta.get("mypy_version") != EXPECTED_MYPY_VERSION
        or meta.get("target") != MYPY_TARGET
    ):
        raise EvidenceError("baseline toolchain or target does not match the pinned gate")
    origin = meta.get("origin")
    if not isinstance(origin, dict) or origin.get("kind") != "historical_replay":
        raise EvidenceError("baseline requires historical replay provenance; current output cannot seed old debt")
    for field in ("git_commit", "git_tree"):
        if not isinstance(origin.get(field), str) or not GIT_SHA_RE.fullmatch(origin[field]):
            raise EvidenceError(f"baseline origin {field} must identify an immutable git source")
    for field in ("legacy_baseline_sha256", "stdout_sha256", "config_sha256", "lock_sha256"):
        if not isinstance(origin.get(field), str) or not SHA256_RE.fullmatch(origin[field]):
            raise EvidenceError(f"baseline origin {field} is missing or invalid")
    if origin.get("per_file_counts_verified") is not True:
        raise EvidenceError("historical replay must match every legacy per-file count")
    environment = origin.get("environment")
    if (
        not isinstance(environment, dict)
        or environment.get("mypy") != "1.20.1"
        or not str(environment.get("python", "")).startswith("3.11.")
        or not isinstance(environment.get("editable_source"), str)
        or not environment["editable_source"]
        or not isinstance(environment.get("executable"), str)
        or not environment["executable"]
    ):
        raise EvidenceError("baseline requires the isolated historical interpreter and editable-source evidence")
    if (
        not isinstance(origin.get("command"), list)
        or not origin["command"]
        or not all(isinstance(item, str) and item for item in origin["command"])
    ):
        raise EvidenceError("baseline origin must retain the historical replay command")
    if not isinstance(origin.get("captured_at"), str) or not origin["captured_at"]:
        raise EvidenceError("baseline origin must retain its capture time")
    sources = origin.get("sources_sha256")
    if not isinstance(sources, list) or not sources:
        raise EvidenceError("baseline origin must retain diagnostic source hashes")
    source_paths: list[str] = []
    for entry in sources:
        if not isinstance(entry, list) or len(entry) != 2:
            raise EvidenceError("baseline source hash entry must be a path/hash pair")
        path, value = entry
        if not isinstance(path, str) or not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            raise EvidenceError("baseline source path or SHA-256 is invalid")
        normalized = PurePosixPath(path)
        if (
            normalized.is_absolute()
            or normalized.as_posix() != path
            or ".." in normalized.parts
            or ":" in path
            or not path.startswith(("backend/", "scripts/"))
        ):
            raise EvidenceError(f"baseline source path is not normalized: {path}")
        try:
            (REPO_ROOT / path).resolve().relative_to(REPO_ROOT.resolve())
        except ValueError as exc:
            raise EvidenceError(f"baseline source resolves outside repository: {path}") from exc
        source_paths.append(path)
    if source_paths != sorted(set(source_paths)):
        raise EvidenceError("baseline source paths must be unique and sorted")
    if origin.get("sources_manifest_sha256") != _source_manifest_digest(sources):
        raise EvidenceError("baseline source manifest checksum does not match its path/hash pairs")
    return set(source_paths)


def require_check_inputs(meta: dict[str, Any]) -> None:
    for path, key in ((MYPY_CONFIG, "config_sha256"), ("backend/uv.lock", "lock_sha256")):
        if _digest((REPO_ROOT / path).read_bytes()) != meta["origin"][key]:
            raise EvidenceError(f"verification input changed: {path}; a reviewed toolchain transition is required")


def load_baseline(path: Path | None = None) -> tuple[dict[str, Any], list[Diagnostic], bytes]:
    path = path or BASELINE_PATH
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"cannot read baseline {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise EvidenceError("baseline must be a JSON object")
    meta = data.get("_meta")
    if not isinstance(meta, dict) or meta.get("schema_version") != BASELINE_SCHEMA_VERSION:
        if "files" in data:
            raise EvidenceError(
                "MIGRATION_REQUIRED: count-only baseline cannot identify historical diagnostics. "
                "Recover diagnostics from the recorded historical source with matching per-file counts; "
                "--update-baseline cannot migrate or accept current errors."
            )
        raise EvidenceError("baseline diagnostic schema is missing or unsupported")
    source_paths = _validate_provenance(meta)
    entries = data.get("diagnostics")
    if not isinstance(entries, list):
        raise EvidenceError("baseline diagnostics must be a list")
    diagnostics: list[Diagnostic] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise EvidenceError("baseline diagnostic must be an object")
        fields = {key: value for key, value in entry.items() if key != "id"}
        try:
            item = Diagnostic(**fields)
        except TypeError as exc:
            raise EvidenceError(f"invalid diagnostic fields: {exc}") from exc
        for key in ("path", "code", "message", "scope", "statement_ast_sha256", "control_flow_sha256"):
            if not isinstance(getattr(item, key), str) or not getattr(item, key):
                raise EvidenceError(f"diagnostic {key} must be non-empty text")
        _normalized_path(item.path, REPO_ROOT)
        if item.path not in source_paths:
            raise EvidenceError(f"baseline has no historical source hash for {item.path}")
        if not all(SHA256_RE.fullmatch(value) for value in (item.statement_ast_sha256, item.control_flow_sha256)):
            raise EvidenceError("invalid statement or control-flow AST digest")
        for key in ("statement_occurrence", "occurrence", "row", "column"):
            value = getattr(item, key)
            if isinstance(value, bool) or not isinstance(value, int) or value < (0 if key == "column" else 1):
                raise EvidenceError(f"invalid diagnostic {key}")
        if entry.get("id") != item.identity:
            raise EvidenceError("diagnostic identity does not match its evidence")
        diagnostics.append(item)
    compare_diagnostics(diagnostics, diagnostics)
    counts = dict(Counter(item.path for item in diagnostics))
    if (
        type(meta.get("total_errors")) is not int
        or type(meta.get("total_files")) is not int
        or not isinstance(data.get("files"), dict)
        or any(type(count) is not int for count in data["files"].values())
        or data.get("files") != counts
        or meta.get("total_errors") != len(diagnostics)
        or meta.get("total_files") != len(counts)
    ):
        raise EvidenceError("baseline counts do not match individual diagnostic evidence")
    return data, diagnostics, raw


def save_baseline(
    data: dict[str, Any],
    baseline: list[Diagnostic],
    current: list[Diagnostic],
    original: bytes,
) -> None:
    """Atomically remove reviewed identities; retain their historical evidence."""
    require_check_inputs(data["_meta"])
    new, _ = compare_diagnostics(baseline, current)
    if new:
        raise EvidenceError("refusing to write new diagnostic identities into the baseline")
    kept_ids = {item.identity for item in current}
    kept = [item for item in baseline if item.identity in kept_ids]
    counts = dict(sorted(Counter(item.path for item in kept).items()))
    payload = {
        "_meta": {
            **data["_meta"],
            "total_errors": len(kept),
            "total_files": len(counts),
            "updated_at": datetime.now(UTC).isoformat(),
        },
        "files": counts,
        "diagnostics": [{"id": item.identity, **asdict(item)} for item in kept],
    }
    if BASELINE_PATH.read_bytes() != original:
        raise EvidenceError("baseline changed during the check; refusing to overwrite concurrent edits")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=BASELINE_PATH.parent, delete=False) as temp:
            temp_path = Path(temp.name)
            temp.write((json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        os.replace(temp_path, BASELINE_PATH)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def replay_environment(historical_root: Path, interpreter: str) -> dict[str, Any]:
    """Reject a replay interpreter whose editable install reads the live tree."""
    probe = (
        "import importlib.metadata as m,importlib.util,json,sys;from pathlib import Path;"
        "d=m.distribution('moss-agent-analytics-os-backend');"
        "s=importlib.util.find_spec('backend');"
        "print(json.dumps({'python':sys.version.split()[0],'executable':sys.executable,"
        "'mypy':m.version('mypy'),'editable':json.loads(d.read_text('direct_url.json') or '{}'),"
        "'sys_path':[str(Path(p or '.').resolve()) for p in sys.path],"
        "'backend_paths':list(s.submodule_search_locations or []) if s else []}))"
    )
    completed = subprocess.run(
        [interpreter, "-c", probe],
        cwd=historical_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode:
        raise EvidenceError(f"cannot inspect historical replay environment: {completed.stderr.strip()}")
    try:
        evidence = json.loads(completed.stdout)
        editable = evidence["editable"]
        url = urlparse(editable["url"])
        source = Path(url2pathname(url.path)).resolve()
        expected = (historical_root / "backend").resolve()
        search_paths = {Path(value).resolve() for value in evidence["sys_path"]}
        backend_paths = {Path(value).resolve() for value in evidence["backend_paths"]}
        historical = historical_root.resolve()
        live = REPO_ROOT.resolve()
        mixed_live_paths = historical != live and any(
            path.is_relative_to(live) and not path.is_relative_to(historical) for path in search_paths
        )
        valid = (
            url.scheme == "file"
            and url.netloc in {"", "localhost"}
            and editable.get("dir_info", {}).get("editable") is True
            and source == expected
            and expected in search_paths and backend_paths == {expected} and not mixed_live_paths
            and evidence["mypy"] == "1.20.1"
            and evidence["python"].startswith("3.11.")
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvidenceError("historical replay environment probe is incomplete") from exc
    if not valid:
        raise EvidenceError(
            "historical replay interpreter must use the pinned tools and isolated historical editable source"
        )
    return {
        "python": evidence["python"],
        "mypy": evidence["mypy"],
        "executable": evidence["executable"],
        "editable_source": str(source),
        "backend_paths": sorted(map(str, backend_paths)),
    }


def build_legacy_migration(
    historical_root: Path,
    stdout_path: Path,
    source_commit: str,
    command: list[str],
) -> tuple[dict[str, Any], dict[str, int]]:
    """Build, never write, a count-preserving migration from an audited replay.

    The caller retains the actual replay receipt. Git blobs, dependency inputs,
    and every registered per-file count are checked here. Extra historical files
    remain unwaived. This recovery is never an --update-baseline fallback.
    """
    require_tool_versions()
    if not command:
        raise EvidenceError("historical replay command is missing")
    environment = replay_environment(historical_root, command[0])
    legacy_raw = BASELINE_PATH.read_bytes()
    legacy = json.loads(legacy_raw)
    if legacy.get("_meta", {}).get("schema_version") is not None:
        raise EvidenceError("migration only accepts the original count-only baseline")
    if legacy.get("_meta", {}).get("mypy_version") not in {
        EXPECTED_MYPY_VERSION,
        f"{EXPECTED_MYPY_VERSION} (compiled: yes)",
        f"{EXPECTED_MYPY_VERSION} (compiled: no)",
    }:
        raise EvidenceError("legacy baseline was not measured with the pinned mypy version")
    counts = legacy.get("files")
    if (
        not isinstance(counts, dict)
        or not counts
        or any(not isinstance(count, int) or isinstance(count, bool) or count < 1 for count in counts.values())
    ):
        raise EvidenceError("legacy baseline has invalid per-file counts")
    if legacy["_meta"].get("total_errors") != sum(counts.values()) or legacy["_meta"].get("total_files") != len(counts):
        raise EvidenceError("legacy totals do not match its per-file counts")
    for path in counts:
        _normalized_path(path, historical_root)
    if not GIT_SHA_RE.fullmatch(source_commit):
        raise EvidenceError("migration requires a full historical commit id")
    latest = (
        subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", "scripts/mypy_baseline.json"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode("ascii")
        .strip()
    )
    if source_commit != latest:
        raise EvidenceError("migration source must be the commit that last recorded the legacy baseline")
    paths = ["scripts/mypy_baseline.json", MYPY_CONFIG, "backend/uv.lock", *sorted(counts)]
    process = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        input="".join(f"{source_commit}:{path}\n" for path in paths).encode("utf-8"),
    )
    stream = io.BytesIO(process.stdout)
    blobs: dict[str, bytes] = {}
    for path in paths:
        header = stream.readline().split()
        if len(header) != 3 or header[1] != b"blob":
            raise EvidenceError(f"historical git blob is unavailable: {path}")
        blobs[path] = stream.read(int(header[2]))
        if stream.read(1) != b"\n":
            raise EvidenceError("historical git blob stream is incomplete")
    if blobs["scripts/mypy_baseline.json"] != legacy_raw:
        raise EvidenceError("working legacy baseline differs from its historical source")
    for path in (MYPY_CONFIG, "backend/uv.lock", *counts):
        if (historical_root / path).read_bytes() != blobs[path]:
            raise EvidenceError(f"replay source differs from the immutable git blob: {path}")
    for path in (MYPY_CONFIG, "backend/uv.lock"):
        if (REPO_ROOT / path).read_bytes() != blobs[path]:
            raise EvidenceError(f"current verification environment has different dependency/config input: {path}")
    required_args = {
        "-m",
        "mypy",
        MYPY_TARGET,
        "--config-file",
        MYPY_CONFIG,
        "--explicit-package-bases",
        "--no-incremental",
        "--show-error-codes",
        "--show-column-numbers",
    }
    if not required_args.issubset(command):
        raise EvidenceError("historical replay receipt does not contain the required pinned command")
    raw_stdout = stdout_path.read_bytes()
    replay_counts, lines_by_file, summary = parse_errors(raw_stdout.decode("utf-8"))
    if summary != (sum(replay_counts.values()), len(replay_counts)):
        raise EvidenceError("historical replay has no matching complete diagnostic summary")
    for path, expected in counts.items():
        if replay_counts.get(path) != expected:
            raise EvidenceError(f"historical count mismatch for {path}: {replay_counts.get(path)} != {expected}")
    diagnostics = build_diagnostics({path: lines_by_file[path] for path in counts}, historical_root)
    if len(diagnostics) != sum(counts.values()):
        raise EvidenceError("migration did not identify every historical diagnostic")
    compare_diagnostics(diagnostics, diagnostics)
    source_tree = (
        subprocess.run(
            ["git", "rev-parse", f"{source_commit}^{{tree}}"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode("ascii")
        .strip()
    )
    source_hashes = [[path, _digest(blobs[path])] for path in sorted(counts)]
    origin = {
        "kind": "historical_replay",
        "git_commit": source_commit,
        "git_tree": source_tree,
        "legacy_baseline_sha256": _digest(legacy_raw),
        "stdout_sha256": _digest(raw_stdout),
        "config_sha256": _digest(blobs[MYPY_CONFIG]),
        "lock_sha256": _digest(blobs["backend/uv.lock"]),
        "per_file_counts_verified": True,
        "environment": environment,
        "command": command,
        "captured_at": datetime.fromtimestamp(stdout_path.stat().st_mtime, UTC).isoformat(),
        "sources_sha256": source_hashes,
        "sources_manifest_sha256": _source_manifest_digest(source_hashes),
    }
    return {
        "_meta": {
            "schema_version": BASELINE_SCHEMA_VERSION,
            "python_version": "3.11",
            "mypy_version": EXPECTED_MYPY_VERSION,
            "target": MYPY_TARGET,
            "total_errors": len(diagnostics),
            "total_files": len(counts),
            "origin": origin,
        },
        "files": dict(sorted(counts.items())),
        "diagnostics": [{"id": item.identity, **asdict(item)} for item in diagnostics],
    }, {path: count for path, count in replay_counts.items() if path not in counts}


def compare(
    baseline: dict[str, int], counts: dict[str, int]
) -> tuple[list[tuple[str, int, int]], list[tuple[str, int]], list[tuple[str, int, int]]]:
    """Legacy count summary only; never used to decide the diagnostic gate."""
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="remove absent diagnostic identities only; never seed or increase a baseline",
    )
    args = parser.parse_args(argv)
    try:
        data, baseline, original = load_baseline()
        require_check_inputs(data["_meta"])
        require_tool_versions()
        counts, lines_by_file = collect_current_errors()
        require_check_inputs(data["_meta"])
        current = build_diagnostics(lines_by_file)
        if len(current) != sum(counts.values()):
            raise EvidenceError("diagnostic identities do not cover every reported error")
        new, removed = compare_diagnostics(baseline, current)
        print(
            f"[mypy-ratchet] current {len(current)} / baseline {len(baseline)}; "
            f"new or changed {len(new)}, removed or changed {len(removed)}"
        )
        if new:
            print("[mypy-ratchet] RATCHET VIOLATION: baseline bytes were not changed.", file=sys.stderr)
            shown: Counter[str] = Counter()
            for item in new:
                shown[item.path] += 1
                if shown[item.path] <= MAX_DETAIL_LINES_PER_FILE:
                    print(f"  {item.path}:{item.row}:{item.column}: {item.message} [{item.code}]", file=sys.stderr)
            return 1
        if args.update_baseline and removed:
            save_baseline(data, baseline, current, original)
            print(f"[mypy-ratchet] baseline reduced: {len(baseline)} -> {len(current)}")
        elif removed:
            print("[mypy-ratchet] IMPROVEMENT: use --update-baseline after review to remove old identities.")
        print("[mypy-ratchet] OK: every current diagnostic is frozen historical debt.")
        return 0
    except (EvidenceError, OSError, UnicodeError) as exc:
        print(f"[mypy-ratchet] FATAL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
