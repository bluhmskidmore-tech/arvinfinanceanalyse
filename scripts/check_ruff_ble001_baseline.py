#!/usr/bin/env python3
"""Fail CI when Ruff finds a BLE001 diagnostic outside the frozen baseline.

The baseline records each existing diagnostic by repository path, lexical
class/function scope, normalized protected try-body and handler ASTs, and
same-structure occurrence.
Comparing identities instead of totals means that removing an old blind catch
cannot pay for adding a new one elsewhere. Source locations remain in the
baseline only to make the evidence easy to review.

Exit codes:
    0  every current diagnostic is in the baseline
    1  one or more new diagnostics were found
    2  Ruff, source, or baseline evidence could not be validated
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.trusted_base_source import (  # noqa: E402
    BaseSourceError,
    isolated_backend_source,
    read_committed_blob,
    resolve_commit,
    run_source_python,
)

BASELINE_PATH = REPO_ROOT / "scripts" / "ruff_ble001_baseline.json"
RUFF_TARGET = "backend"
EXPECTED_RUFF_VERSION = "ruff 0.15.7"
EXPECTED_PYTHON_VERSION = (3, 11)
RULE = "BLE001"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class EvidenceError(RuntimeError):
    """The gate could not obtain or validate complete Ruff evidence."""


class MissingBaselineError(EvidenceError):
    """A resolved base commit has no baseline file."""


@dataclass(frozen=True)
class Violation:
    identity: str
    path: str
    scope: str
    occurrence: int
    try_body_ast_sha256: str
    handler_ast_sha256: str
    row: int
    column: int
    source: str

    def as_json(self) -> dict[str, str | int]:
        return {
            "id": self.identity,
            "path": self.path,
            "scope": self.scope,
            "occurrence": self.occurrence,
            "try_body_ast_sha256": self.try_body_ast_sha256,
            "handler_ast_sha256": self.handler_ast_sha256,
            "row": self.row,
            "column": self.column,
            "source": self.source,
        }


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise EvidenceError(f"cannot execute Ruff: {exc}") from exc


def require_ruff_version() -> None:
    proc = _run([sys.executable, "-m", "ruff", "--version"])
    version = (proc.stdout or proc.stderr).strip()
    if proc.returncode != 0:
        raise EvidenceError(
            f"Ruff version probe exited {proc.returncode}: {version or '<no output>'}"
        )
    if version != EXPECTED_RUFF_VERSION:
        raise EvidenceError(
            f"Ruff version mismatch: expected {EXPECTED_RUFF_VERSION!r}, got {version!r}"
        )


def require_python_version() -> None:
    actual = sys.version_info[:2]
    if actual != EXPECTED_PYTHON_VERSION:
        expected = ".".join(map(str, EXPECTED_PYTHON_VERSION))
        observed = ".".join(map(str, actual))
        raise EvidenceError(
            f"Python version mismatch: expected {expected}, got {observed}; "
            "AST fingerprints are interpreter-version specific"
        )


def run_ruff() -> list[dict[str, Any]]:
    proc = _run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            RUFF_TARGET,
            "--select",
            RULE,
            "--output-format",
            "json",
        ]
    )
    return _parse_ruff_output(proc)


def _parse_ruff_output(proc: subprocess.CompletedProcess[str]) -> list[dict[str, Any]]:
    if proc.returncode not in (0, 1):
        detail = (proc.stderr or proc.stdout).strip()
        raise EvidenceError(
            f"Ruff exited {proc.returncode}: {detail or '<no diagnostic output>'}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"Ruff returned invalid JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise EvidenceError("Ruff JSON root must be a list")
    if proc.returncode == 1 and not payload:
        raise EvidenceError("Ruff reported violations but returned an empty JSON list")
    if proc.returncode == 0 and payload:
        raise EvidenceError("Ruff returned diagnostics with a successful exit code")
    return payload


def derive_trusted_baseline(baseline_ref: str, source_parent: Path) -> list[Violation]:
    """Fingerprint only exact base source when the committed baseline is absent."""
    try:
        commit = resolve_commit(REPO_ROOT, baseline_ref)
        with isolated_backend_source(REPO_ROOT, commit, source_parent) as source:
            proc = run_source_python(
                source,
                "import runpy,sys;sys.argv=['ruff','check','backend','--select','BLE001',"
                "'--output-format','json'];runpy.run_module('ruff',run_name='__main__')",
                [],
            )
            trusted = build_violations(_parse_ruff_output(proc), source.root)
            provenance = source.provenance() | {
                "ruff_version": EXPECTED_RUFF_VERSION,
                "python_version": ".".join(map(str, sys.version_info[:3])),
                "command": "python -m ruff check backend --select BLE001 --output-format json",
            }
            print(f"[ruff-ble001] derived trusted base: {json.dumps(provenance, sort_keys=True)}")
            return trusted
    except BaseSourceError as error:
        raise EvidenceError("cannot derive BLE001 evidence from exact trusted base source") from error


def _repo_path(filename: object, repo_root: Path) -> tuple[str, Path]:
    if not isinstance(filename, str) or not filename:
        raise EvidenceError("Ruff diagnostic has no filename")
    candidate = Path(filename)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise EvidenceError(f"Ruff diagnostic is outside the repository: {resolved}") from exc
    return relative.as_posix(), resolved


def _identity(
    path: str,
    scope: str,
    try_body_ast_sha256: str,
    handler_ast_sha256: str,
    occurrence: int,
) -> str:
    evidence = (
        f"{RULE}\0{path}\0{scope}\0{try_body_ast_sha256}\0"
        f"{handler_ast_sha256}\0{occurrence}"
    ).encode("utf-8")
    return hashlib.sha256(evidence).hexdigest()


class _HandlerCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = []
        self.scope_name_counts: dict[tuple[tuple[str, ...], str, str], int] = {}
        self.try_body_digests: list[str] = []
        self.handlers: list[tuple[ast.ExceptHandler, str, str, str]] = []

    def _visit_scope(self, node: ast.AST, kind: str, name: str) -> None:
        parent = tuple(self.scope)
        key = (parent, kind, name)
        index = self.scope_name_counts.get(key, 0) + 1
        self.scope_name_counts[key] = index
        self.scope.append(f"{kind}:{name}#{index}")
        self.generic_visit(node)
        self.scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node, "class", node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node, "function", node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node, "async-function", node.name)

    def _visit_try(self, node: ast.Try | ast.TryStar) -> None:
        canonical_body = "\0".join(
            ast.dump(statement, annotate_fields=True, include_attributes=False)
            for statement in node.body
        )
        self.try_body_digests.append(
            hashlib.sha256(canonical_body.encode("utf-8")).hexdigest()
        )
        self.generic_visit(node)
        self.try_body_digests.pop()

    def visit_Try(self, node: ast.Try) -> None:
        self._visit_try(node)

    def visit_TryStar(self, node: ast.TryStar) -> None:
        self._visit_try(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if not self.try_body_digests:
            raise EvidenceError("exception handler has no parent try statement")
        canonical = ast.dump(node, annotate_fields=True, include_attributes=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        scope = "/".join(self.scope) if self.scope else "<module>"
        self.handlers.append((node, scope, self.try_body_digests[-1], digest))
        self.generic_visit(node)


def _handler_evidence(source: str, path: str) -> dict[int, tuple[str, str, str, int]]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise EvidenceError(f"cannot parse Ruff source {path}: {exc}") from exc
    collector = _HandlerCollector()
    collector.visit(tree)
    occurrences: dict[tuple[str, str, str], int] = {}
    by_row: dict[int, tuple[str, str, str, int]] = {}
    for node, scope, try_body_digest, handler_digest in sorted(
        collector.handlers, key=lambda item: (item[0].lineno, item[0].col_offset)
    ):
        key = (scope, try_body_digest, handler_digest)
        occurrence = occurrences.get(key, 0) + 1
        occurrences[key] = occurrence
        if node.lineno in by_row:
            raise EvidenceError(f"multiple exception handlers start at {path}:{node.lineno}")
        by_row[node.lineno] = (
            scope,
            try_body_digest,
            handler_digest,
            occurrence,
        )
    return by_row


def build_violations(
    diagnostics: list[dict[str, Any]], repo_root: Path = REPO_ROOT
) -> list[Violation]:
    violations: list[Violation] = []
    sources: dict[
        Path, tuple[list[str], dict[int, tuple[str, str, str, int]]]
    ] = {}
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict) or diagnostic.get("code") != RULE:
            raise EvidenceError(f"unexpected Ruff diagnostic: {diagnostic!r}")
        location = diagnostic.get("location")
        if not isinstance(location, dict):
            raise EvidenceError(f"Ruff diagnostic has no location: {diagnostic!r}")
        row = location.get("row")
        column = location.get("column")
        if not isinstance(row, int) or row < 1 or not isinstance(column, int) or column < 1:
            raise EvidenceError(f"invalid Ruff location: {location!r}")
        path, absolute_path = _repo_path(diagnostic.get("filename"), repo_root)
        if absolute_path not in sources:
            try:
                source_text = absolute_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise EvidenceError(f"cannot read Ruff source {path}: {exc}") from exc
            sources[absolute_path] = (
                source_text.splitlines(),
                _handler_evidence(source_text, path),
            )
        lines, handlers = sources[absolute_path]
        if row > len(lines):
            raise EvidenceError(f"Ruff location {path}:{row} is past end of file")
        try:
            scope, try_body_digest, handler_digest, occurrence = handlers[row]
        except KeyError as exc:
            raise EvidenceError(
                f"Ruff diagnostic {path}:{row} does not map to an exception handler"
            ) from exc
        source = lines[row - 1]
        violations.append(
            Violation(
                _identity(
                    path, scope, try_body_digest, handler_digest, occurrence
                ),
                path,
                scope,
                occurrence,
                try_body_digest,
                handler_digest,
                row,
                column,
                source,
            )
        )
    identities = [item.identity for item in violations]
    if len(identities) != len(set(identities)):
        raise EvidenceError("Ruff returned duplicate BLE001 diagnostic identities")
    return sorted(violations, key=lambda item: (item.path, item.row, item.column))


def load_baseline(
    path: Path | None = None, *, baseline_ref: str | None = None
) -> list[Violation]:
    path = path or BASELINE_PATH
    if baseline_ref is not None:
        relative = path.relative_to(REPO_ROOT).as_posix()
        try:
            commit = resolve_commit(REPO_ROOT, baseline_ref)
            blob = read_committed_blob(REPO_ROOT, commit, relative)
            if blob is None:
                raise MissingBaselineError(f"trusted BLE001 baseline is absent at {commit}")
            raw = blob.decode("utf-8")
        except (BaseSourceError, UnicodeError) as error:
            raise EvidenceError("cannot read trusted BLE001 baseline") from error
    else:
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise EvidenceError(f"cannot read BLE001 baseline {path}: {exc}") from exc
    try:
        payload = json.loads(raw)
        meta = payload["_meta"]
        entries = payload["violations"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise EvidenceError(f"cannot read BLE001 baseline {path}: {exc}") from exc
    if not isinstance(meta, dict) or meta.get("schema_version") != 3:
        raise EvidenceError("BLE001 baseline schema_version must be 3")
    if meta.get("ruff_version") != EXPECTED_RUFF_VERSION:
        raise EvidenceError(
            "BLE001 baseline Ruff version does not match the CI-pinned checker version"
        )
    if meta.get("python_version") != "3.11":
        raise EvidenceError(
            "BLE001 baseline Python version does not match the CI-pinned checker version"
        )
    if not isinstance(entries, list):
        raise EvidenceError("BLE001 baseline violations must be a list")

    violations: list[Violation] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise EvidenceError(f"invalid BLE001 baseline entry: {entry!r}")
        required_strings = (
            "id",
            "path",
            "scope",
            "try_body_ast_sha256",
            "handler_ast_sha256",
            "source",
        )
        for key in required_strings:
            value = entry.get(key)
            if not isinstance(value, str) or not value:
                raise EvidenceError(
                    f"BLE001 baseline {key} must be a non-empty string: {entry!r}"
                )
        for key in ("occurrence", "row", "column"):
            value = entry.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise EvidenceError(
                    f"BLE001 baseline {key} must be a positive integer: {entry!r}"
                )
        for key in ("id", "try_body_ast_sha256", "handler_ast_sha256"):
            if not SHA256_RE.fullmatch(entry[key]):
                raise EvidenceError(
                    f"BLE001 baseline {key} must be a lowercase SHA-256: {entry!r}"
                )
        repo_path = PurePosixPath(entry["path"])
        if (
            repo_path.is_absolute()
            or ".." in repo_path.parts
            or "\\" in entry["path"]
            or repo_path.as_posix() != entry["path"]
            or not entry["path"].startswith("backend/")
        ):
            raise EvidenceError(
                f"BLE001 baseline path must be a normalized backend-relative path: {entry!r}"
            )
        violation = Violation(
            identity=entry["id"],
            path=entry["path"],
            scope=entry["scope"],
            occurrence=entry["occurrence"],
            try_body_ast_sha256=entry["try_body_ast_sha256"],
            handler_ast_sha256=entry["handler_ast_sha256"],
            row=entry["row"],
            column=entry["column"],
            source=entry["source"],
        )
        expected = _identity(
            violation.path,
            violation.scope,
            violation.try_body_ast_sha256,
            violation.handler_ast_sha256,
            violation.occurrence,
        )
        if violation.identity != expected:
            raise EvidenceError(
                f"BLE001 baseline identity does not match its evidence at "
                f"{violation.path}:{violation.row}:{violation.column}"
            )
        violations.append(violation)
    identities = [item.identity for item in violations]
    if len(identities) != len(set(identities)):
        raise EvidenceError("BLE001 baseline contains duplicate identities")
    total = meta.get("total_violations")
    if isinstance(total, bool) or not isinstance(total, int) or total != len(violations):
        raise EvidenceError("BLE001 baseline total_violations does not match its entries")
    return violations


def compare(
    baseline: list[Violation], current: list[Violation]
) -> tuple[list[Violation], list[Violation]]:
    baseline_by_id = {item.identity: item for item in baseline}
    current_by_id = {item.identity: item for item in current}
    new = [item for key, item in current_by_id.items() if key not in baseline_by_id]
    removed = [item for key, item in baseline_by_id.items() if key not in current_by_id]
    return (
        sorted(new, key=lambda item: (item.path, item.row, item.column)),
        sorted(removed, key=lambda item: (item.path, item.row, item.column)),
    )


def save_baseline(violations: list[Violation], path: Path | None = None) -> None:
    path = path or BASELINE_PATH
    payload = {
        "_meta": {
            "schema_version": 3,
            "description": (
                "Frozen Ruff BLE001 diagnostics. Stable identities bind repository path, "
                "lexical scope, normalized protected try-body AST, normalized handler AST, "
                "and same-structure occurrence; row/column/source are audit display fields only."
            ),
            "command": "python -m ruff check backend --select BLE001 --output-format json",
            "ruff_version": EXPECTED_RUFF_VERSION,
            "python_version": "3.11",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_violations": len(violations),
        },
        "violations": [item.as_json() for item in violations],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="rewrite the baseline only after reviewed debt removal",
    )
    parser.add_argument("--baseline-ref", help="trusted PR base commit used to reject baseline expansion")
    parser.add_argument(
        "--derive-missing-baseline", metavar="SOURCE_PARENT", type=Path,
        help="if the trusted commit has no baseline, compare against its isolated source under .codex-tmp",
    )
    args = parser.parse_args(argv)
    if args.derive_missing_baseline and not args.baseline_ref:
        parser.error("--derive-missing-baseline requires --baseline-ref")
    try:
        require_python_version()
        require_ruff_version()
        current = build_violations(run_ruff())
        baseline = load_baseline()
        if args.baseline_ref:
            try:
                trusted_commit = resolve_commit(REPO_ROOT, args.baseline_ref)
            except BaseSourceError as error:
                raise EvidenceError("cannot resolve trusted BLE001 baseline ref") from error
            try:
                trusted = load_baseline(baseline_ref=trusted_commit)
            except MissingBaselineError:
                if not args.derive_missing_baseline:
                    raise
                trusted = derive_trusted_baseline(trusted_commit, args.derive_missing_baseline)
            expanded, _ = compare(trusted, baseline)
            if expanded:
                print("[ruff-ble001] REFUSED: working baseline adds identities absent from the trusted PR base.", file=sys.stderr)
                for item in expanded:
                    print(f"  {item.path}:{item.row}:{item.column}: {item.identity}", file=sys.stderr)
                return 1
    except EvidenceError as exc:
        print(f"[ruff-ble001] FATAL: {exc}", file=sys.stderr)
        return 2

    new, removed = compare(baseline, current)
    if args.update_baseline:
        if new:
            print(
                "[ruff-ble001] REFUSED: baseline update contains new or changed "
                "BLE001 identities; baseline bytes were not changed.",
                file=sys.stderr,
            )
            for item in new:
                print(
                    f"  {item.path}:{item.row}:{item.column}: {item.source.strip()}",
                    file=sys.stderr,
                )
            return 1
        if not removed:
            print("[ruff-ble001] baseline already matches; no rewrite needed.")
            return 0
        save_baseline(current)
        print(
            f"[ruff-ble001] baseline reduced: {len(baseline)} -> {len(current)} violation(s)"
        )
        return 0

    print(
        f"[ruff-ble001] current {len(current)} / baseline {len(baseline)}; "
        f"new or changed {len(new)}, removed or changed {len(removed)}"
    )
    if removed:
        if new:
            print(
                "[ruff-ble001] BASELINE UNCHANGED: removed identities cannot be locked in "
                "while new or changed identities remain."
            )
        else:
            print(
                "[ruff-ble001] IMPROVEMENT: baseline identities disappeared; "
                "run --update-baseline after review to lock them in."
            )
    if not new:
        print("[ruff-ble001] OK: every current BLE001 diagnostic is frozen debt.")
        return 0

    print("[ruff-ble001] RATCHET VIOLATION: new BLE001 diagnostics:", file=sys.stderr)
    for item in new:
        print(
            f"  {item.path}:{item.row}:{item.column}: {item.source.strip()}",
            file=sys.stderr,
        )
    print(
        "[ruff-ble001] Narrow the caught exception or add a reasoned noqa at a deliberate "
        "top-level durability boundary.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
