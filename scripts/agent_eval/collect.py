"""Measured-result collection for MOSS agent evaluation.

Builds the result mapping consumed by `reward.py` from observed repository
state rather than agent self-report: changed files come from git, check and
gate status from real process exit codes, evidence from on-disk artifacts.

A gate without a declared probe is scored as a failure. A gate that cannot be
measured must not be assumed to pass, otherwise the scorecard only measures
whether the reporter was cooperative.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.agent_eval.spec import MEASUREMENT_SCHEMA_VERSION, MEASUREMENT_SOURCE

DEFAULT_TIMEOUT_SECONDS = 1800
OUTPUT_TAIL_CHARS = 2000

# The scoring infrastructure itself is always protected: an agent that edits
# the collector, the reward weights, or a task definition can manufacture any
# score, so such a run is void regardless of what the task declares.
HARNESS_SELF_PATHS = ("scripts/agent_eval/",)

# Conservative extraction of explicit repo test-file paths from probe commands.
# The lookbehind rejects tokens embedded in a longer path (e.g. the `tests/...`
# inside `scripts/tests/...`). Filter-word probes (e.g. a vitest name filter
# such as `LedgerPnlUnitContract`) carry no path and cannot be derived.
_PROBE_COMMAND_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"(?:(?:backend/)?tests/[A-Za-z0-9_/]+\.py|frontend/src/test/[A-Za-z0-9_./-]+)"
)


@dataclass(frozen=True)
class CommandOutcome:
    exit_code: int
    duration_ms: int = 0
    stdout_tail: str = ""
    stderr_tail: str = ""
    timed_out: bool = False


CommandRunner = Callable[[str, Path, int], CommandOutcome]


@dataclass
class _Collector:
    repo_root: Path
    runner: CommandRunner
    timeout_seconds: int
    command_log: list[dict[str, Any]] = field(default_factory=list)
    _cache: dict[str, CommandOutcome] = field(default_factory=dict)

    def run(self, label: str, command: str) -> CommandOutcome:
        cached = self._cache.get(command)
        if cached is not None:
            self.command_log.append(_log_entry(label, command, cached, reused=True))
            return cached

        outcome = self.runner(command, self.repo_root, self.timeout_seconds)
        self._cache[command] = outcome
        self.command_log.append(_log_entry(label, command, outcome, reused=False))
        return outcome


def collect_measured_result(
    task: dict[str, Any],
    *,
    repo_root: str | Path,
    base_ref: str | None = None,
    task_path: str | Path | None = None,
    expected_task_digest: str | None = None,
    run_command: CommandRunner | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Observe the repository and produce a scorable result mapping."""

    root = Path(repo_root).resolve()
    collector = _Collector(
        repo_root=root,
        runner=run_command or run_shell_command,
        timeout_seconds=timeout_seconds,
    )

    tracked_changed, untracked = _collect_change_sets(root, base_ref)
    changed_files = sorted({path for path in tracked_changed + untracked if path})
    checks = _measure_checks(task, collector)
    gate_probes = _gate_probes(task)
    business_gates, unprobed_business = _measure_gates(
        task.get("business_gates", []), gate_probes, collector, "business_gate"
    )
    page_gates, unprobed_page = _measure_gates(
        task.get("page_gates", []), gate_probes, collector, "page_gate"
    )
    evidence, evidence_detail = _measure_evidence(task, root)
    integrity = _check_integrity(task, task_path, root, tracked_changed, expected_task_digest)
    unprobed = sorted(unprobed_business + unprobed_page)

    return {
        "evidence": evidence,
        "checks": checks,
        "business_gates": business_gates,
        "page_gates": page_gates,
        "changed_files": changed_files,
        "measurement": {
            "source": MEASUREMENT_SOURCE,
            "schema_version": MEASUREMENT_SCHEMA_VERSION,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "repo_root": str(root),
            "base_ref": base_ref,
            "head_sha": _head_sha(root),
            "unprobed_gates": unprobed,
            "unprobed_gate_reasons": _gap_reasons(task, unprobed),
            "evidence_artifacts": evidence_detail,
            "commands": collector.command_log,
            "integrity": integrity,
        },
    }


def collect_changed_files(repo_root: str | Path, base_ref: str | None = None) -> list[str]:
    """Return repo-relative posix paths changed relative to `base_ref` plus untracked files."""

    tracked, untracked = _collect_change_sets(Path(repo_root), base_ref)
    return sorted({path for path in tracked + untracked if path})


def compute_task_digest(task_path: str | Path) -> str:
    """Digest a task file so a runner can prove the scoring rules never changed mid-run."""

    return hashlib.sha256(Path(task_path).read_bytes()).hexdigest()


def derive_probe_paths(task: dict[str, Any]) -> list[str]:
    """Derive protected probe file paths from the `gate_probes` command strings.

    Extraction is conservative by design: only explicit repo-relative test-file
    tokens (`tests/**.py`, `backend/tests/**.py`, `frontend/src/test/**`) are
    recognized, normalized to lowercase posix form. A command without such a
    token derives nothing and is surfaced in
    `measurement.integrity.underivable_probe_commands`; its dependencies must be
    declared manually in `probe_protected_paths`.
    """

    derived, _ = _derive_probe_protection(task)
    return derived


def _collect_change_sets(repo_root: Path, base_ref: str | None) -> tuple[list[str], list[str]]:
    # Diff against HEAD by default so staged-but-uncommitted edits stay visible;
    # a bare `git diff` only shows unstaged changes, which lets `git add` hide a
    # modification from both changed_files and the integrity check.
    tracked = _git_lines(repo_root, ["diff", "--name-only", base_ref or "HEAD"])
    untracked = _git_lines(repo_root, ["ls-files", "--others", "--exclude-standard"])
    return tracked, untracked


def run_shell_command(command: str, cwd: Path, timeout_seconds: int) -> CommandOutcome:
    started = time.monotonic()
    try:
        completed = subprocess.run(  # noqa: S602 - task JSON is a reviewed in-repo file
            command,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            # npm/vitest emit UTF-8; without this, zh-CN Windows decodes with
            # GBK and a stray byte kills the reader thread mid-output.
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CommandOutcome(
            exit_code=124,
            duration_ms=_elapsed_ms(started),
            stderr_tail=f"timed out after {timeout_seconds}s",
            timed_out=True,
        )

    return CommandOutcome(
        exit_code=completed.returncode,
        duration_ms=_elapsed_ms(started),
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def _measure_checks(task: dict[str, Any], collector: _Collector) -> dict[str, str]:
    checks: dict[str, str] = {}
    for command in task.get("checks", []):
        outcome = collector.run("check", command)
        checks[command] = "passed" if outcome.exit_code == 0 else "failed"
    return checks


def _measure_gates(
    required: list[str],
    probes: dict[str, str],
    collector: _Collector,
    label: str,
) -> tuple[dict[str, str], list[str]]:
    measured: dict[str, str] = {}
    unprobed: list[str] = []

    for gate in required:
        command = probes.get(gate)
        if not command:
            measured[gate] = "failed"
            unprobed.append(gate)
            continue
        outcome = collector.run(f"{label}:{gate}", command)
        measured[gate] = "passed" if outcome.exit_code == 0 else "failed"

    return measured, unprobed


def _measure_evidence(task: dict[str, Any], repo_root: Path) -> tuple[list[str], list[dict[str, Any]]]:
    probes = _evidence_probes(task)
    satisfied: list[str] = []
    detail: list[dict[str, Any]] = []

    for name in task.get("required_evidence", []):
        artifact = probes.get(name)
        if not artifact:
            detail.append({"evidence": name, "status": "no_artifact_declared"})
            continue

        status, size, source = _classify_evidence_artifact(repo_root / artifact)
        entry: dict[str, Any] = {"evidence": name, "artifact": artifact, "status": status, "bytes": size}
        if status == "present":
            satisfied.append(name)
            entry["source"] = source
        detail.append(entry)

    return satisfied, detail


def _classify_evidence_artifact(path: Path) -> tuple[str, int, str | None]:
    """Apply the minimal evidence schema to a declared artifact.

    Only "present" counts as evidence: a non-empty file that parses to a JSON
    object whose "source" is a non-empty string naming the MCP server or query
    tool the evidence came from — the anchor for a future call-receipt check.
    An artifact that fails the schema is recorded with a dedicated status
    (missing / empty / invalid_json / missing_source) and never satisfies the
    probe, so a placeholder file cannot buy the verification score.
    """

    if not path.is_file():
        return "missing", 0, None
    size = path.stat().st_size
    if size == 0:
        return "empty", 0, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "invalid_json", size, None
    if not isinstance(payload, dict):
        return "invalid_json", size, None
    source = payload.get("source")
    if not isinstance(source, str) or not source.strip():
        return "missing_source", size, None
    return "present", size, source


def _check_integrity(
    task: dict[str, Any],
    task_path: str | Path | None,
    repo_root: Path,
    tracked_changed: list[str],
    expected_task_digest: str | None,
) -> dict[str, Any]:
    """Flag conditions that make the scorecard itself untrustworthy.

    Only tracked modifications count. An untracked task file is a new task
    definition, not evidence that the scoring rules were rewritten mid-run.

    The protected probe list is the union of paths auto-derived from the
    `gate_probes` commands and the manual `probe_protected_paths` declarations,
    so a probe file is protected even when the task author forgot to list it.
    """

    violations: list[str] = []
    changed = set(_lowered(tracked_changed))
    relative_task_path = _relative_posix(task_path, repo_root) if task_path else None
    digest_verified = False

    if expected_task_digest and task_path:
        actual_digest = compute_task_digest(task_path)
        digest_verified = actual_digest == expected_task_digest
        if not digest_verified:
            violations.append(f"Task definition digest changed during the run: {relative_task_path}")
    elif relative_task_path and relative_task_path in changed:
        violations.append(f"Task definition modified during the run: {relative_task_path}")

    derived_paths, underivable_commands = _derive_probe_protection(task)
    protected_paths = sorted(set(_protected_probe_paths(task)) | set(derived_paths))

    for prefix in HARNESS_SELF_PATHS:
        for hit in sorted(path for path in changed if path.startswith(prefix)):
            violations.append(f"Scoring harness file modified during the run: {hit}")

    for probe_path in protected_paths:
        if probe_path.endswith("/"):
            for hit in sorted(path for path in changed if path.startswith(probe_path)):
                violations.append(f"Gate probe target modified during the run: {hit}")
        elif probe_path in changed:
            violations.append(f"Gate probe target modified during the run: {probe_path}")

    return {
        "task_id": task.get("id"),
        "task_path": relative_task_path,
        "task_digest_verified": digest_verified,
        "trusted": not violations,
        "violations": violations,
        "protected_paths": protected_paths,
        "underivable_probe_commands": underivable_commands,
    }


def _protected_probe_paths(task: dict[str, Any]) -> list[str]:
    paths = task.get("probe_protected_paths", [])
    if not isinstance(paths, list):
        return []
    return sorted({path.replace("\\", "/").strip().lower() for path in paths if isinstance(path, str)})


def _derive_probe_protection(task: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Split `gate_probes` commands into derived paths and underivable commands.

    `checks` commands also contribute derived paths (they feed the verification
    score, so their target test files deserve the same tamper protection), but
    only gate probes are reported as underivable: a filter-word check command is
    normal, a filter-word gate probe needs a manual protection entry.
    """

    derived: set[str] = set()
    underivable: set[str] = set()
    for command in _gate_probes(task).values():
        matches = _PROBE_COMMAND_PATH_PATTERN.findall(command.replace("\\", "/"))
        if matches:
            derived.update(match.strip().lower() for match in matches)
        else:
            underivable.add(command)
    for command in task.get("checks", []):
        if isinstance(command, str):
            matches = _PROBE_COMMAND_PATH_PATTERN.findall(command.replace("\\", "/"))
            derived.update(match.strip().lower() for match in matches)
    return sorted(derived), sorted(underivable)


def _gap_reasons(task: dict[str, Any], unprobed: list[str]) -> dict[str, str]:
    declared = task.get("gate_probe_gaps", {})
    if not isinstance(declared, dict):
        declared = {}
    return {gate: str(declared.get(gate, "No probe declared and no gap reason recorded.")) for gate in unprobed}


def _gate_probes(task: dict[str, Any]) -> dict[str, str]:
    probes = task.get("gate_probes", {})
    if not isinstance(probes, dict):
        return {}
    return {key: value for key, value in probes.items() if isinstance(key, str) and isinstance(value, str)}


def _evidence_probes(task: dict[str, Any]) -> dict[str, str]:
    probes = task.get("evidence_probes", {})
    if not isinstance(probes, dict):
        return {}
    return {key: value for key, value in probes.items() if isinstance(key, str) and isinstance(value, str)}


def _git_lines(repo_root: Path, args: list[str]) -> list[str]:
    """Run git and return output lines, failing closed on any git error.

    A silent empty result here would score "measurement failed" as "nothing
    changed", so a broken repo, a missing git binary, or a bad ref must abort
    the collection instead.
    """

    try:
        completed = subprocess.run(  # noqa: S603 - fixed git argv, no shell
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        raise ValueError(f"git {' '.join(args)} could not run in {repo_root}: {error}") from error
    if completed.returncode != 0:
        raise ValueError(
            f"git {' '.join(args)} failed in {repo_root} "
            f"(exit {completed.returncode}): {completed.stderr.strip()}"
        )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _head_sha(repo_root: Path) -> str | None:
    lines = _git_lines(repo_root, ["rev-parse", "HEAD"])
    return lines[0] if lines else None


def _relative_posix(path: str | Path, repo_root: Path) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    try:
        return candidate.resolve().relative_to(repo_root).as_posix().lower()
    except ValueError:
        return candidate.as_posix().lower()


def _lowered(paths: list[str]) -> list[str]:
    return [path.replace("\\", "/").strip().lower() for path in paths]


def _log_entry(label: str, command: str, outcome: CommandOutcome, *, reused: bool) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "label": label,
        "command": command,
        "exit_code": outcome.exit_code,
        "duration_ms": outcome.duration_ms,
    }
    if reused:
        entry["reused_cached_run"] = True
    if outcome.timed_out:
        entry["timed_out"] = True
    if outcome.exit_code != 0:
        entry["stdout_tail"] = outcome.stdout_tail
        entry["stderr_tail"] = outcome.stderr_tail
    return entry


def _tail(text: str | None) -> str:
    if not text:
        return ""
    return text[-OUTPUT_TAIL_CHARS:]


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
