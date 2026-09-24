"""PR consumer for the agent evaluation harness (replay mode).

Selects the evaluation tasks whose ``pr_trigger_scope`` (or legacy
``allowed_scope``) overlaps the PR's changed files, runs ``replay.py`` for each,
and renders one Markdown report
suitable for a GitHub step summary or PR comment.

This consumer is informational: evaluation pass/fail never fails the process.
A non-zero exit means the orchestration itself is broken (bad task JSON, git
failure), which is the only state a CI job should go red on.

Reading the report:

- ``pass`` / ``fail``: the scorecard verdict from ``reward.py``.
- hard failures are split into *real failures* (a probe ran and went red),
  *probe gaps* (the gate has no probe yet and fails closed by design), and
  *missing evidence artifacts* (``required_evidence`` artifacts are runtime
  products — typically under the gitignored ``.codex-tmp/`` — that never exist
  in a fresh CI checkout; they fail closed but are not a probe going red).
- ``void``: the measurement rejected itself — typically because the PR
  modifies the scoring harness or a protected probe file, which by design
  cannot be scored by the thing it modifies. Void is a statement about the
  evaluation, not about the PR's quality.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent_eval import replay
from scripts.agent_eval.collect import CommandOutcome, _check_integrity, compute_task_digest
from scripts.agent_eval.reward import EVIDENCE_FAILURE_PREFIX as _EVIDENCE_FAILURE_PREFIX
from scripts.agent_eval.reward import _path_matches
from scripts.agent_eval.spec import validate_task_spec

COMMENT_MARKER = "<!-- moss-agent-eval-replay -->"
DEFAULT_TASKS_DIR = Path("scripts") / "agent_eval" / "tasks"
DEFAULT_OUT_ROOT = Path(".codex-tmp") / "agent-eval" / "pr-replay"
REUSABLE_PR_CHECKS = frozenset({
    "npm --prefix frontend run typecheck",
})
SHARED_FRONTEND_SCOPES = ("frontend/src/api/", "frontend/src/test/")
# These existing tests exercise Agent-only surfaces. Their production API and
# embedded page boundary files are mapped separately in the task triggers.
# Keep this list exact so a newly added shared test still fails open.
KNOWN_STANDALONE_AGENT_TESTS = frozenset({
    "frontend/src/test/agentclient.test.ts",
    "frontend/src/test/agentrunstream.test.ts",
    "frontend/src/test/agentlabrunstream.test.ts",
    "frontend/src/test/agentcontractsync.test.ts",
    "frontend/src/test/agentworkbenchmodel.test.ts",
})


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    tasks_dir = repo_root / args.tasks_dir
    out_root = Path(args.out_root)

    try:
        changed_files = _changed_files(repo_root, args.base_ref)
        tasks = _load_tasks(tasks_dir)
    except ValueError as error:
        print(f"pr-replay orchestration error: {error}", file=sys.stderr)
        return 2

    unmapped_shared_files = _unmapped_shared_files(changed_files, tasks)
    applicable = [
        (task_path, task)
        for task_path, task in tasks
        if unmapped_shared_files or _task_applies(task, changed_files)
    ]

    if args.preflight:
        try:
            needs_dependency_setup = _needs_dependency_setup(applicable, changed_files, repo_root)
        except (OSError, ValueError) as error:
            print(f"pr-replay orchestration error: {error}", file=sys.stderr)
            return 2
        print(f"needs_dependency_setup={str(needs_dependency_setup).lower()}")
        return 0

    out_root.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    orchestration_failed = False
    command_cache: dict[str, CommandOutcome] = {}
    previous_worktree_state: str | None = None
    for task_path, task in applicable:
        if len(applicable) > 1:
            try:
                worktree_state = _worktree_signature(repo_root)
            except ValueError as error:
                print(f"pr-replay orchestration error: {error}", file=sys.stderr)
                return 2
            if (
                previous_worktree_state is not None
                and worktree_state != previous_worktree_state
            ):
                command_cache.clear()
            previous_worktree_state = worktree_state
        outcome = _run_replay(
            task_path, task, args.base_ref, out_root, repo_root, command_cache
        )
        error = _replay_orchestration_error(outcome)
        if error:
            print(f"pr-replay orchestration error for {task['id']}: {error}", file=sys.stderr)
            orchestration_failed = True
        sections.append(_render_task_section(task, outcome))

    report = _render_report(
        base_ref=args.base_ref,
        changed_count=len(changed_files),
        applicable_count=len(applicable),
        total_count=len(tasks),
        sections=sections,
        unmapped_shared_files=unmapped_shared_files,
    )
    out_md = Path(args.out_md) if args.out_md else out_root / "summary.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(report, encoding="utf-8")
    print(report)
    print(f"pr-replay report: {out_md}", file=sys.stderr)
    return 2 if orchestration_failed else 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run replay evaluations for tasks selected by the PR diff."
    )
    parser.add_argument("--base-ref", required=True, help="Git ref the PR merges into (e.g. origin/main).")
    parser.add_argument("--repo-root", default=".", help="Repository root to evaluate.")
    parser.add_argument(
        "--tasks-dir",
        default=str(DEFAULT_TASKS_DIR),
        help="Task definitions directory, relative to the repo root.",
    )
    parser.add_argument(
        "--out-root",
        default=str(DEFAULT_OUT_ROOT),
        help="Directory for per-task replay archives and the Markdown report.",
    )
    parser.add_argument("--out-md", help="Explicit path for the Markdown report (default: <out-root>/summary.md).")
    parser.add_argument(
        "--preflight", action="store_true",
        help="Print whether selected tasks need dependency setup; the normal replay still creates the report.",
    )
    return parser.parse_args(argv)


def _changed_files(repo_root: Path, base_ref: str) -> list[str]:
    completed = subprocess.run(  # noqa: S603 - fixed git argv, no shell
        ["git", "diff", "--name-only", base_ref],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"git diff --name-only {base_ref} failed (exit {completed.returncode}): {completed.stderr.strip()}"
        )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _load_tasks(tasks_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    if not tasks_dir.is_dir():
        raise ValueError(f"tasks directory not found: {tasks_dir}")
    tasks: list[tuple[Path, dict[str, Any]]] = []
    seen_ids: set[str] = set()
    for task_path in sorted(tasks_dir.glob("*.json")):
        payload = json.loads(task_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object in {task_path}")
        task = validate_task_spec(payload)
        task_id = task["id"]
        if not isinstance(task_id, str) or re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]*", task_id) is None:
            raise ValueError(f"Unsafe task id in {task_path}: {task_id!r}")
        folded_id = task_id.casefold()
        if folded_id in seen_ids:
            raise ValueError(f"Duplicate task id in {task_path}: {task_id}")
        seen_ids.add(folded_id)
        tasks.append((task_path, task))
    return tasks


def _task_applies(task: dict[str, Any], changed_files: list[str]) -> bool:
    scopes = task.get("pr_trigger_scope", task.get("allowed_scope", []))
    return any(
        _trigger_path_matches(changed, scope) for changed in changed_files for scope in scopes
    )


def _trigger_path_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("*"):
        return path.replace("\\", "/").lower().startswith(pattern[:-1].replace("\\", "/").lower())
    return _path_matches(path, pattern)


def _unmapped_shared_files(
    changed_files: list[str], tasks: list[tuple[Path, dict[str, Any]]]
) -> list[str]:
    return sorted(
        path for path in changed_files
        if any(_path_matches(path, scope) for scope in SHARED_FRONTEND_SCOPES)
        and path.replace("\\", "/").lower() not in KNOWN_STANDALONE_AGENT_TESTS
        and not any(_task_applies(task, [path]) for _, task in tasks)
    )


def _needs_dependency_setup(
    applicable: list[tuple[Path, dict[str, Any]]],
    changed_files: list[str],
    repo_root: Path,
) -> bool:
    """Only omit dependency setup when every selected replay is already void."""
    return any(
        _check_integrity(
            task, task_path, repo_root, changed_files, compute_task_digest(task_path)
        )["trusted"]
        for task_path, task in applicable
    )


def _run_replay(
    task_path: Path,
    task: dict[str, Any],
    base_ref: str,
    out_root: Path,
    repo_root: Path,
    command_cache: dict[str, CommandOutcome],
) -> dict[str, Any]:
    task_id = str(task.get("id"))
    out_dir = out_root / task_id
    try:
        if out_dir.is_symlink() or out_dir.resolve().parent != out_root.resolve():
            raise ValueError(f"Task archive escapes output root: {out_dir}")
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in ("task.json", "result.json", "scorecard.json", "summary.txt"):
            (out_dir / name).unlink(missing_ok=True)
    except (OSError, RuntimeError, ValueError) as error:
        return {
            "exit_code": 2,
            "stderr_tail": f"Cannot prepare replay archive {out_dir}: {error}",
            "scorecard": None,
            "result": None,
            "archive": out_dir,
        }
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            exit_code = replay.main(
                [
                    "--task",
                    str(task_path),
                    "--worktree",
                    str(repo_root),
                    "--base-ref",
                    base_ref,
                    "--out-dir",
                    str(out_dir),
                ],
                command_cache=command_cache,
                reusable_checks=REUSABLE_PR_CHECKS,
            )
        except Exception:
            traceback.print_exc(file=stderr)
            exit_code = 2

    try:
        scorecard = _read_json_if_exists(out_dir / "scorecard.json")
        result = _read_json_if_exists(out_dir / "result.json")
    except (OSError, ValueError) as error:
        stderr.write(f"Cannot read replay archive {out_dir}: {error}\n")
        scorecard = None
        result = None
    return {
        "exit_code": exit_code,
        "stderr_tail": stderr.getvalue()[-2000:],
        "scorecard": scorecard,
        "result": result,
        "archive": out_dir,
    }


def _worktree_signature(repo_root: Path) -> str:
    """Invalidate shared command outcomes if source files change between tasks."""

    def git_bytes(*args: str) -> bytes:
        try:
            completed = subprocess.run(  # noqa: S603 - fixed git argv, no shell
                ["git", *args], cwd=str(repo_root), capture_output=True, check=False
            )
        except OSError as error:
            raise ValueError(f"git {' '.join(args)} could not run: {error}") from error
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError(f"git {' '.join(args)} failed: {detail}")
        return completed.stdout

    digest = hashlib.sha256()
    def update_segment(value: bytes) -> None:
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)

    update_segment(git_bytes("rev-parse", "HEAD"))
    update_segment(git_bytes("diff", "--binary", "HEAD", "--"))
    untracked_paths = git_bytes("ls-files", "--others", "--exclude-standard", "-z")
    for relative_path in sorted(filter(None, untracked_paths.split(b"\0"))):
        update_segment(relative_path)
        candidate = repo_root / relative_path.decode("utf-8", errors="surrogateescape")
        if candidate.is_file():
            digest.update(b"\x01")
            try:
                update_segment(candidate.read_bytes())
            except OSError as error:
                raise ValueError(f"Cannot read untracked file {candidate}: {error}") from error
        else:
            digest.update(b"\x00")
    return digest.hexdigest()


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _render_report(
    *,
    base_ref: str,
    changed_count: int,
    applicable_count: int,
    total_count: int,
    sections: list[str],
    unmapped_shared_files: list[str] | None = None,
) -> str:
    lines = [
        COMMENT_MARKER,
        "## Agent 评测（重放模式）",
        "",
        f"基准：`{base_ref}` · 变更文件 {changed_count} 个 · "
        f"适用任务 {applicable_count}/{total_count}（按任务 `pr_trigger_scope` 或旧任务的 `allowed_scope` 选择）",
        "",
    ]
    if unmapped_shared_files:
        lines.append("> 选择器映射待复核：以下共享前端文件未匹配任何任务触发范围，已保守回放全部任务。")
        lines.extend(f"> - `{path}`" for path in unmapped_shared_files)
        lines.append("")
    if not sections:
        lines.append("本次变更不落在任何评测任务的范围内，未运行评测。")
        lines.append("")
        return "\n".join(lines)

    lines.extend(sections)
    lines.append(
        "> 说明：本评测为信息性参考，不阻塞合并。`探针缺口` 是 fail-closed 语义下尚无自动化探针的 gate，"
        "不代表本次变更引入问题；`证据工件缺失` 是 required_evidence 声明的运行期工件（如 `.codex-tmp/` 下产物）"
        "未随本次检出存在，按 fail-closed 计失败，同样不是探针变红；"
        "`void` 表示评测按防篡改设计作废（本次变更触及评分基础设施或受保护探针）。"
    )
    lines.append("")
    return "\n".join(lines)


def _render_task_section(task: dict[str, Any], outcome: dict[str, Any]) -> str:
    task_id = str(task.get("id"))
    error = _replay_orchestration_error(outcome)
    if error:
        return f"### `{task_id}` — **orchestration error**\n\n- 原因：{error}\n"
    scorecard = outcome.get("scorecard")
    result = outcome.get("result") or {}
    measurement = result.get("measurement") or {}
    unprobed = set(measurement.get("unprobed_gates") or [])
    reasons = measurement.get("unprobed_gate_reasons") or {}
    artifact_statuses = {
        str(entry.get("evidence")): str(entry.get("status"))
        for entry in measurement.get("evidence_artifacts") or []
        if isinstance(entry, dict)
    }

    lines: list[str] = []
    if outcome["exit_code"] == 2:
        rejection = _extract_rejection(outcome, measurement)
        lines.append(f"### `{task_id}` — **void**（评测作废）")
        lines.append("")
        lines.append(f"- 原因：{rejection}")
        lines.append("- 含义：本次变更触及评分基础设施或受保护探针文件，按防篡改设计不能由其评分自身；请走人工评审。")
        lines.append("")
        return "\n".join(lines)

    status = str(scorecard.get("status"))
    icon = "✅" if status == "pass" else "❌"
    lines.append(f"### `{task_id}` — {icon} **{status}**，得分 {scorecard.get('score')}")
    lines.append("")

    breakdown = scorecard.get("breakdown") or {}
    lines.append(
        "| 业务 (40) | 页面 (20) | 验证 (20) | 改动纪律 (20) |\n"
        "| --- | --- | --- | --- |\n"
        f"| {breakdown.get('business', '—')} | {breakdown.get('page', '—')} "
        f"| {breakdown.get('verification', '—')} | {breakdown.get('diff', '—')} |"
    )
    lines.append("")

    real_failures, gap_failures, evidence_failures = _split_hard_failures(
        scorecard.get("hard_failures") or [], unprobed
    )
    if real_failures:
        lines.append(f"**真实失败（{len(real_failures)}）** — 探针实际运行并变红：")
        lines.extend(f"- {item}" for item in real_failures)
        lines.append("")
    if gap_failures:
        lines.append(f"**探针缺口（{len(gap_failures)}）** — gate 尚无探针，按 fail-closed 计失败：")
        lines.extend(
            f"- {item}（{reasons.get(_gate_name(item), '缺口原因未登记')}）" for item in gap_failures
        )
        lines.append("")
    if evidence_failures:
        lines.append(
            f"**证据工件缺失（{len(evidence_failures)}）** — required_evidence 声明的运行期工件"
            "未随本次检出存在（如 `.codex-tmp/` 下产物不入库），按 fail-closed 计失败，非探针失败："
        )
        lines.extend(
            f"- {item}（工件状态：{artifact_statuses.get(_evidence_name(item), '未记录')}）"
            for item in evidence_failures
        )
        lines.append("")

    warnings = scorecard.get("warnings") or []
    if warnings:
        lines.append(f"**警告（{len(warnings)}）**：")
        lines.extend(f"- {item}" for item in warnings)
        lines.append("")

    return "\n".join(lines)


def _replay_orchestration_error(outcome: dict[str, Any]) -> str | None:
    code = outcome.get("exit_code")
    scorecard = outcome.get("scorecard")
    result = outcome.get("result")
    measurement = result.get("measurement") if isinstance(result, dict) else None
    integrity = measurement.get("integrity") if isinstance(measurement, dict) else None
    trusted = integrity.get("trusted") if isinstance(integrity, dict) else None
    violations = integrity.get("violations") if isinstance(integrity, dict) else None
    stderr_tail = str(outcome.get("stderr_tail") or "").strip().splitlines()
    detail = stderr_tail[-1] if stderr_tail else "no replay detail"

    is_void = (
        code == 2
        and scorecard is None
        and trusted is False
        and isinstance(violations, list)
        and bool(violations)
    )
    if code == 2 and not is_void:
        return f"replay exited 2 without a valid integrity rejection ({detail})"
    if code not in (0, 1, 2):
        return f"unexpected replay exit code {code} ({detail})"
    if not is_void:
        if not isinstance(result, dict) or trusted is not True:
            return "result.json is missing or has no trusted measurement"
        if not isinstance(scorecard, dict):
            return "scorecard.json is missing or invalid"
        status = scorecard.get("status")
        if (code, status) not in ((0, "pass"), (1, "fail")):
            return f"replay exit code {code} conflicts with scorecard status {status!r}"

    archive = outcome.get("archive")
    if isinstance(archive, Path):
        required = ("task.json", "result.json", "summary.txt")
        if not is_void:
            required += ("scorecard.json",)
        missing = [name for name in required if not (archive / name).is_file()]
        if missing:
            return f"replay archive is missing current artifacts: {', '.join(missing)}"
    return None


def _extract_rejection(outcome: dict[str, Any], measurement: dict[str, Any]) -> str:
    integrity = measurement.get("integrity") or {}
    violations = integrity.get("violations") or []
    if violations:
        return "; ".join(str(item) for item in violations)
    stderr_tail = str(outcome.get("stderr_tail") or "").strip()
    return stderr_tail.splitlines()[-1] if stderr_tail else "未知（见归档 summary.txt）"


def _split_hard_failures(
    hard_failures: list[str], unprobed: set[str]
) -> tuple[list[str], list[str], list[str]]:
    """Split hard failures into (real probe reds, probe gaps, missing evidence artifacts).

    Evidence artifacts live under runtime output directories that a fresh CI
    checkout never contains, so lumping them into "real failures" would make
    every PR replay look like probes went red.
    """

    real: list[str] = []
    gaps: list[str] = []
    missing_evidence: list[str] = []
    for item in hard_failures:
        if item.startswith(_EVIDENCE_FAILURE_PREFIX):
            missing_evidence.append(item)
        elif _gate_name(item) in unprobed:
            gaps.append(item)
        else:
            real.append(item)
    return real, gaps, missing_evidence


def _gate_name(hard_failure: str) -> str:
    return hard_failure.rsplit(": ", 1)[-1].strip()


def _evidence_name(hard_failure: str) -> str:
    return hard_failure[len(_EVIDENCE_FAILURE_PREFIX):].strip()


if __name__ == "__main__":
    raise SystemExit(main())
