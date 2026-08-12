"""Replay-mode runner for the MOSS agent evaluation harness.

Replay mode evaluates a change set that already exists in a working tree,
whether a human or an agent produced it. This runner does NOT launch or
drive an agent: it only measures the worktree, scores the result, and
archives the evidence. Spawning an agent from a task definition is the job
of a rollout-mode runner, which is not implemented yet.

Pipeline: validate the task spec, pin the task digest, collect the measured
result from the worktree (git change set, probe exit codes, evidence
artifacts, integrity), validate the measurement, score it, archive
everything, and print a short summary.

Isolation: evaluate a dedicated git worktree or clone instead of a busy
main workspace, otherwise unrelated uncommitted files pollute
``changed_files`` and the diff-scope score. Example:

    git worktree add ../moss-replay-demo main
    # ...produce or apply the change inside that worktree...
    python scripts/agent_eval/replay.py --task scripts/agent_eval/tasks/demo.json --worktree ../moss-replay-demo --base-ref main

Task digest semantics:

- ``--task-digest``: sha256 of the task file captured externally before the
  change was produced; proves the scoring rules never changed across the
  whole run.
- omitted: the digest is computed here at replay start; it still proves the
  task file did not change while this evaluation was running.

Archive layout (``<out-dir>/``):

- ``task.json``: byte-for-byte snapshot of the task definition
- ``result.json``: measured result from ``collect_measured_result``
- ``scorecard.json``: ``evaluate_result`` output (absent when the
  measurement is rejected)
- ``summary.txt``: human-readable run summary; records the rejection reason
  when the measurement is rejected

Exit codes match ``validate_task.py``: 0 pass, 1 fail, 2 invalid input or
rejected measurement.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent_eval.collect import CommandRunner, collect_measured_result, compute_task_digest
from scripts.agent_eval.reward import evaluate_result
from scripts.agent_eval.spec import validate_measured_result, validate_task_spec

DEFAULT_OUT_ROOT = Path(".codex-tmp") / "agent-eval" / "replays"


def main(argv: list[str] | None = None, *, run_command: CommandRunner | None = None) -> int:
    args = _parse_args(argv)
    task_path = Path(args.task)

    try:
        task_bytes = task_path.read_bytes()
        task = validate_task_spec(_parse_task_object(task_bytes, task_path))
    except (OSError, ValueError) as error:
        print(f"Invalid agent eval input: {error}", file=sys.stderr)
        return 2

    if args.task_digest:
        task_digest = args.task_digest
        digest_source = "provided externally before the run"
    else:
        task_digest = compute_task_digest(task_path)
        digest_source = "computed at replay start"

    worktree = Path(args.worktree).resolve()
    out_dir = Path(args.out_dir) if args.out_dir else _default_out_dir(str(task["id"]))
    out_dir.mkdir(parents=True, exist_ok=True)

    result = collect_measured_result(
        task,
        repo_root=worktree,
        base_ref=args.base_ref,
        task_path=task_path,
        expected_task_digest=task_digest,
        run_command=run_command,
    )

    (out_dir / "task.json").write_bytes(task_bytes)
    _write_json(out_dir / "result.json", result)

    try:
        validate_measured_result(result)
    except ValueError as error:
        summary = _render_summary(
            task=task,
            result=result,
            worktree=worktree,
            base_ref=args.base_ref,
            task_digest=task_digest,
            digest_source=digest_source,
            scorecard=None,
            rejection=str(error),
        )
        (out_dir / "summary.txt").write_text(summary, encoding="utf-8")
        print(f"Invalid agent eval measurement: {error}", file=sys.stderr)
        print(f"Rejected measurement archived to: {out_dir}", file=sys.stderr)
        return 2

    scorecard = evaluate_result(task, result)
    scorecard["measured"] = "measurement" in result
    scorecard_path = out_dir / "scorecard.json"
    _write_json(scorecard_path, scorecard)
    summary = _render_summary(
        task=task,
        result=result,
        worktree=worktree,
        base_ref=args.base_ref,
        task_digest=task_digest,
        digest_source=digest_source,
        scorecard=scorecard,
        rejection=None,
    )
    (out_dir / "summary.txt").write_text(summary, encoding="utf-8")

    print(f"status: {scorecard['status']}")
    print(f"score: {scorecard['score']}")
    print(f"scorecard: {scorecard_path}")
    _report_unprobed_gates(result)

    return 0 if scorecard["status"] == "pass" else 1


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay-mode runner: evaluate and archive changes that already exist in a worktree."
    )
    parser.add_argument("--task", required=True, help="Path to the task JSON file.")
    parser.add_argument(
        "--worktree",
        default=".",
        help="Root of the git worktree or clone whose changes are evaluated (default: current directory).",
    )
    parser.add_argument("--base-ref", help="Git ref to diff against when collecting changed files.")
    parser.add_argument(
        "--out-dir",
        help=(
            "Archive directory. Default: .codex-tmp/agent-eval/replays/<task_id>-<UTC timestamp> "
            "under the current directory."
        ),
    )
    parser.add_argument(
        "--task-digest",
        help=(
            "sha256 of the task file captured before the change was produced. "
            "Omitted: computed at replay start, proving the task file stays unchanged during this evaluation."
        ),
    )
    return parser.parse_args(argv)


def _default_out_dir(task_id: str) -> Path:
    safe_task_id = re.sub(r"[^A-Za-z0-9._-]+", "_", task_id) or "task"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    candidate = DEFAULT_OUT_ROOT / f"{safe_task_id}-{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = DEFAULT_OUT_ROOT / f"{safe_task_id}-{stamp}-{suffix}"
        suffix += 1
    return candidate


def _render_summary(
    *,
    task: dict[str, Any],
    result: dict[str, Any],
    worktree: Path,
    base_ref: str | None,
    task_digest: str,
    digest_source: str,
    scorecard: dict[str, Any] | None,
    rejection: str | None,
) -> str:
    measurement = result.get("measurement")
    if not isinstance(measurement, dict):
        measurement = {}

    lines = [
        "MOSS agent eval replay summary",
        f"task_id: {task.get('id')}",
        f"worktree: {worktree}",
        f"head_sha: {measurement.get('head_sha') or '(unknown)'}",
        f"base_ref: {base_ref or '(none)'}",
        f"task_digest: {task_digest}",
        f"task_digest_source: {digest_source}",
        f"collected_at: {measurement.get('collected_at') or '(unknown)'}",
    ]

    if rejection is not None:
        lines.append("status: invalid (measurement rejected, evaluation void)")
        lines.append(f"rejection_reason: {rejection}")
    elif scorecard is not None:
        lines.append(f"status: {scorecard.get('status')}")
        lines.append(f"score: {scorecard.get('score')}")
        hard_failures = scorecard.get("hard_failures") or []
        lines.append(f"hard_failures: {len(hard_failures)}")
        lines.extend(f"  - {item}" for item in hard_failures)

    unprobed = measurement.get("unprobed_gates") or []
    reasons = measurement.get("unprobed_gate_reasons") or {}
    lines.append(f"unprobed_gates: {len(unprobed)}")
    lines.extend(
        f"  - {gate}: {reasons.get(gate, 'No probe declared and no gap reason recorded.')}"
        for gate in unprobed
    )
    return "\n".join(lines) + "\n"


def _report_unprobed_gates(result: dict[str, Any]) -> None:
    measurement = result.get("measurement")
    if not isinstance(measurement, dict):
        return
    unprobed = measurement.get("unprobed_gates") or []
    reasons = measurement.get("unprobed_gate_reasons") or {}
    for gate in unprobed:
        reason = reasons.get(gate, "No probe declared and no gap reason recorded.")
        print(f"Unprobed gate scored as failed: {gate} ({reason})", file=sys.stderr)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_task_object(raw: bytes, path: Path) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
