"""PR consumer for the agent evaluation harness (replay mode).

Selects the evaluation tasks whose ``allowed_scope`` overlaps the PR's
changed files, runs ``replay.py`` for each, and renders one Markdown report
suitable for a GitHub step summary or PR comment.

This consumer is informational: evaluation pass/fail never fails the process.
A non-zero exit means the orchestration itself is broken (bad task JSON, git
failure), which is the only state a CI job should go red on.

Reading the report:

- ``pass`` / ``fail``: the scorecard verdict from ``reward.py``.
- hard failures are split into *real failures* (a probe ran and went red) and
  *probe gaps* (the gate has no probe yet and fails closed by design).
- ``void``: the measurement rejected itself — typically because the PR
  modifies the scoring harness or a protected probe file, which by design
  cannot be scored by the thing it modifies. Void is a statement about the
  evaluation, not about the PR's quality.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent_eval.reward import _path_matches
from scripts.agent_eval.spec import validate_task_spec

COMMENT_MARKER = "<!-- moss-agent-eval-replay -->"
DEFAULT_TASKS_DIR = Path("scripts") / "agent_eval" / "tasks"
DEFAULT_OUT_ROOT = Path(".codex-tmp") / "agent-eval" / "pr-replay"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    tasks_dir = repo_root / args.tasks_dir
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    try:
        changed_files = _changed_files(repo_root, args.base_ref)
        tasks = _load_tasks(tasks_dir)
    except ValueError as error:
        print(f"pr-replay orchestration error: {error}", file=sys.stderr)
        return 2

    applicable = [
        (task_path, task)
        for task_path, task in tasks
        if _task_applies(task, changed_files)
    ]

    sections: list[str] = []
    for task_path, task in applicable:
        outcome = _run_replay(task_path, task, args.base_ref, out_root, repo_root)
        sections.append(_render_task_section(task, outcome))

    report = _render_report(
        base_ref=args.base_ref,
        changed_count=len(changed_files),
        applicable_count=len(applicable),
        total_count=len(tasks),
        sections=sections,
    )
    out_md = Path(args.out_md) if args.out_md else out_root / "summary.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(report, encoding="utf-8")
    print(report)
    print(f"pr-replay report: {out_md}", file=sys.stderr)
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run replay evaluations for every task whose scope overlaps the PR diff."
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
    for task_path in sorted(tasks_dir.glob("*.json")):
        payload = json.loads(task_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object in {task_path}")
        tasks.append((task_path, validate_task_spec(payload)))
    return tasks


def _task_applies(task: dict[str, Any], changed_files: list[str]) -> bool:
    scopes = task.get("allowed_scope", [])
    return any(
        _path_matches(changed, scope) for changed in changed_files for scope in scopes
    )


def _run_replay(
    task_path: Path,
    task: dict[str, Any],
    base_ref: str,
    out_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    task_id = str(task.get("id"))
    out_dir = out_root / task_id
    replay_script = Path(__file__).resolve().parent / "replay.py"
    completed = subprocess.run(  # noqa: S603 - fixed argv over reviewed in-repo scripts
        [
            sys.executable,
            str(replay_script),
            "--task",
            str(task_path),
            "--worktree",
            str(repo_root),
            "--base-ref",
            base_ref,
            "--out-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    scorecard = _read_json_if_exists(out_dir / "scorecard.json")
    result = _read_json_if_exists(out_dir / "result.json")
    return {
        "exit_code": completed.returncode,
        "stderr_tail": completed.stderr[-2000:],
        "scorecard": scorecard,
        "result": result,
        "archive": out_dir,
    }


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
) -> str:
    lines = [
        COMMENT_MARKER,
        "## Agent 评测（重放模式）",
        "",
        f"基准：`{base_ref}` · 变更文件 {changed_count} 个 · "
        f"适用任务 {applicable_count}/{total_count}（按任务 `allowed_scope` 与 diff 的交集选择）",
        "",
    ]
    if not sections:
        lines.append("本次变更不落在任何评测任务的范围内，未运行评测。")
        lines.append("")
        return "\n".join(lines)

    lines.extend(sections)
    lines.append(
        "> 说明：本评测为信息性参考，不阻塞合并。`探针缺口` 是 fail-closed 语义下尚无自动化探针的 gate，"
        "不代表本次变更引入问题；`void` 表示评测按防篡改设计作废（本次变更触及评分基础设施或受保护探针）。"
    )
    lines.append("")
    return "\n".join(lines)


def _render_task_section(task: dict[str, Any], outcome: dict[str, Any]) -> str:
    task_id = str(task.get("id"))
    scorecard = outcome.get("scorecard")
    result = outcome.get("result") or {}
    measurement = result.get("measurement") or {}
    unprobed = set(measurement.get("unprobed_gates") or [])
    reasons = measurement.get("unprobed_gate_reasons") or {}

    lines: list[str] = []
    if outcome["exit_code"] == 2 or scorecard is None:
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

    real_failures, gap_failures = _split_hard_failures(scorecard.get("hard_failures") or [], unprobed)
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

    warnings = scorecard.get("warnings") or []
    if warnings:
        lines.append(f"**警告（{len(warnings)}）**：")
        lines.extend(f"- {item}" for item in warnings)
        lines.append("")

    return "\n".join(lines)


def _extract_rejection(outcome: dict[str, Any], measurement: dict[str, Any]) -> str:
    integrity = measurement.get("integrity") or {}
    violations = integrity.get("violations") or []
    if violations:
        return "; ".join(str(item) for item in violations)
    stderr_tail = str(outcome.get("stderr_tail") or "").strip()
    return stderr_tail.splitlines()[-1] if stderr_tail else "未知（见归档 summary.txt）"


def _split_hard_failures(hard_failures: list[str], unprobed: set[str]) -> tuple[list[str], list[str]]:
    real: list[str] = []
    gaps: list[str] = []
    for item in hard_failures:
        (gaps if _gate_name(item) in unprobed else real).append(item)
    return real, gaps


def _gate_name(hard_failure: str) -> str:
    return hard_failure.rsplit(": ", 1)[-1].strip()


if __name__ == "__main__":
    raise SystemExit(main())
