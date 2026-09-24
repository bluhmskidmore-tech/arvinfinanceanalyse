"""Rollout-mode runner for the MOSS agent evaluation harness.

Rollout mode is the trusted orchestration shell around an agent run. Where
replay mode (``replay.py``) evaluates a change set that already exists in a
working tree, rollout mode produces that change set first: it pins the scoring
rules, prepares an isolated git worktree, drives one agent command inside it,
and then delegates every measurement and scoring decision to the replay
pipeline. It adds no scoring logic of its own.

Pipeline:

1. validate the task spec read from the source repository task file
2. pin the task digest with ``compute_task_digest`` BEFORE the worktree exists
   and before any agent code runs
3. ``git worktree add --detach <out-dir>/workdir <base-ref>`` for isolation
4. run ``--agent-cmd`` with a shell in the worktree root, streaming its full
   stdout+stderr to ``agent.log`` (non-zero exit or timeout stops the run with
   exit code 3 after the log is archived)
5. evaluate the worktree via ``replay.main`` with ``--task-digest`` set to the
   pinned value; the task path still points at the source repository file, so
   nothing the agent wrote inside the worktree can redefine the scoring rules
6. remove the worktree in a ``finally`` block (``--keep-worktree`` skips the
   removal for debugging and prints the preserved path)

Security boundary: this runner is a TRUSTED orchestration layer. ``--agent-cmd``
is executed with ``shell=True`` and the task JSON drives shell probe commands,
so both must come from the trusted caller side — a reviewed, in-repo task file
and an operator-supplied agent command — never from the agent under
evaluation. What the agent can touch is only the isolated worktree, and the
replay integrity checks (pinned digest, ``HARNESS_SELF_PATHS``, protected probe
paths) void the evaluation when it tampers with scoring inputs there.

Archive layout (``<out-dir>/``):

- ``agent.log``: full interleaved agent stdout+stderr with header/footer
- ``task.json`` / ``result.json`` / ``scorecard.json`` / ``summary.txt``:
  written by the replay pipeline (``scorecard.json`` is absent when the
  measurement is rejected; all four are absent when the agent command itself
  failed and evaluation never started)
- ``workdir/``: the isolated worktree, present only with ``--keep-worktree``

Exit codes:

- 0: evaluation pass
- 1: evaluation fail
- 2: invalid input (task spec, repository, worktree creation) or rejected
  measurement (digest/integrity violation), matching ``replay.py``
- 3: the agent command exited non-zero or timed out; ``agent.log`` is archived
  before exiting and the evaluation is skipped

Windows notes: the worktree lives in a short ``workdir`` directory under the
archive to limit path length (enable ``git config core.longpaths true`` for
deep repositories). Removal uses ``git worktree remove --force`` with a retry,
then an rmtree fallback plus ``git worktree prune``, because a straggling agent
child process or an antivirus scanner can hold file locks; a leftover path is
reported on stderr but never changes the exit code.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent_eval import replay
from scripts.agent_eval.collect import CommandRunner, compute_task_digest
from scripts.agent_eval.spec import validate_task_spec

DEFAULT_OUT_ROOT = Path(".codex-tmp") / "agent-eval" / "rollouts"
WORKTREE_DIR_NAME = "workdir"
AGENT_LOG_NAME = "agent.log"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INVALID = 2
EXIT_AGENT_FAILURE = 3


@dataclass(frozen=True)
class AgentOutcome:
    exit_code: int
    timed_out: bool
    duration_ms: int


def main(argv: list[str] | None = None, *, run_command: CommandRunner | None = None) -> int:
    args = _parse_args(argv)
    repo = Path(args.repo).resolve()
    task_path = Path(args.task).resolve()

    try:
        task = validate_task_spec(_load_task_object(task_path))
    except (OSError, ValueError) as error:
        print(f"Invalid agent eval input: {error}", file=sys.stderr)
        return EXIT_INVALID

    # Pin the scoring rules from the source repository before the worktree
    # exists and before any agent code runs; the evaluation later verifies the
    # source task file against this digest, so an agent rewriting its worktree
    # task copy (or the source file) cannot change what it is scored against.
    task_digest = compute_task_digest(task_path)

    out_dir = Path(args.out_dir) if args.out_dir else _default_out_dir(str(task["id"]))
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"Invalid agent eval input: cannot create out dir {out_dir}: {error}", file=sys.stderr)
        return EXIT_INVALID
    workdir = (out_dir / WORKTREE_DIR_NAME).resolve()

    try:
        added = _run_git(repo, "worktree", "add", "--detach", str(workdir), args.base_ref)
    except OSError as error:
        print(f"Invalid agent eval input: git could not run in {repo}: {error}", file=sys.stderr)
        return EXIT_INVALID
    if added.returncode != 0:
        print(
            f"Invalid agent eval input: git worktree add --detach {args.base_ref} failed in {repo} "
            f"(exit {added.returncode}): {added.stderr.strip()}",
            file=sys.stderr,
        )
        return EXIT_INVALID

    print(f"task_digest: {task_digest}")
    print(f"worktree: {workdir}")

    try:
        log_path = out_dir / AGENT_LOG_NAME
        outcome = _run_agent(args.agent_cmd, workdir, log_path, args.timeout_seconds)
        print(f"agent_exit_code: {outcome.exit_code}")
        print(f"agent_log: {log_path}")
        if outcome.timed_out or outcome.exit_code != 0:
            detail = (
                f"timed out after {args.timeout_seconds}s"
                if outcome.timed_out
                else f"exited with code {outcome.exit_code}"
            )
            print(
                f"Agent command {detail}; evaluation skipped, agent.log archived to {out_dir}",
                file=sys.stderr,
            )
            return EXIT_AGENT_FAILURE
        return _evaluate(task_path, workdir, args.base_ref, task_digest, out_dir, run_command)
    finally:
        if args.keep_worktree:
            print(f"worktree kept: {workdir}")
        else:
            _remove_worktree(repo, workdir)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rollout-mode runner: drive one agent command inside an isolated git worktree, "
            "then evaluate and archive the outcome through the replay pipeline."
        )
    )
    parser.add_argument("--task", required=True, help="Path to the task JSON file in the source repository.")
    parser.add_argument(
        "--base-ref",
        required=True,
        help="Git ref the isolated worktree is detached from; also the diff base for the evaluation.",
    )
    parser.add_argument(
        "--agent-cmd",
        required=True,
        help=(
            "Agent command executed with a shell in the worktree root. Trusted-caller input: "
            "this runner never sanitizes it."
        ),
    )
    parser.add_argument(
        "--out-dir",
        help=(
            "Archive directory. Default: .codex-tmp/agent-eval/rollouts/<task_id>-<UTC timestamp> "
            "under the current directory. Must not already contain a 'workdir' entry."
        ),
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Source repository the worktree is created from (default: current directory).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3600,
        help="Timeout for the agent command in seconds (default: 3600).",
    )
    parser.add_argument(
        "--keep-worktree",
        action="store_true",
        help="Keep the isolated worktree for debugging instead of removing it; its path is printed.",
    )
    return parser.parse_args(argv)


def _evaluate(
    task_path: Path,
    workdir: Path,
    base_ref: str,
    task_digest: str,
    out_dir: Path,
    run_command: CommandRunner | None,
) -> int:
    replay_argv = [
        "--task",
        str(task_path),
        "--worktree",
        str(workdir),
        "--base-ref",
        base_ref,
        "--task-digest",
        task_digest,
        "--out-dir",
        str(out_dir),
    ]
    try:
        return replay.main(replay_argv, run_command=run_command)
    except ValueError as error:
        # The collector fails closed (e.g. git broke mid-collection); a
        # measurement that cannot be completed is void, matching replay's
        # exit-2 semantics.
        print(f"Invalid agent eval measurement: {error}", file=sys.stderr)
        return EXIT_INVALID


def _run_agent(command: str, workdir: Path, log_path: Path, timeout_seconds: int) -> AgentOutcome:
    """Run the agent command in the worktree root, streaming all output to the log.

    stdout and stderr share one file descriptor so ``agent.log`` keeps the full
    interleaved output without buffering it in memory; header and footer bracket
    the child's own writes because duplicated descriptors share the file offset.
    """

    started = time.monotonic()
    header = (
        "# MOSS agent eval rollout agent log\n"
        f"# agent_cmd: {command}\n"
        f"# cwd: {workdir}\n"
        f"# started_at: {datetime.now(timezone.utc).isoformat()}\n"
    )
    with log_path.open("wb") as log:
        log.write(header.encode("utf-8"))
        log.flush()
        process = subprocess.Popen(  # noqa: S602 - agent command comes from the trusted caller side
            command,
            cwd=str(workdir),
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=(os.name != "nt"),
        )
        timed_out = False
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_tree(process)
            exit_code = process.wait()
        duration_ms = int((time.monotonic() - started) * 1000)
        footer = (
            f"\n# exit_code: {exit_code}\n"
            f"# timed_out: {str(timed_out).lower()}\n"
            f"# duration_ms: {duration_ms}\n"
        )
        log.write(footer.encode("utf-8"))
    return AgentOutcome(exit_code=exit_code, timed_out=timed_out, duration_ms=duration_ms)


def _kill_process_tree(process: subprocess.Popen[bytes]) -> None:
    """Kill the shell and all its descendants on timeout.

    An orphaned agent child whose working directory is inside the worktree
    would keep the directory locked on Windows, so ``taskkill /T`` takes the
    whole tree down; on POSIX the agent runs in its own session and the process
    group is killed.
    """

    if os.name == "nt":
        subprocess.run(  # noqa: S603 - fixed taskkill argv, no shell
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        process.kill()
    except OSError:
        pass


def _remove_worktree(repo: Path, workdir: Path) -> None:
    """Best-effort worktree removal that never masks the run's exit code.

    ``git worktree remove --force`` handles the dirty tree the agent leaves
    behind. On Windows a transient file lock (agent child, antivirus scan) can
    fail the first attempt, so retry once, then fall back to rmtree plus
    ``git worktree prune``. A leftover path is reported but not fatal.
    """

    failure = ""
    for attempt in range(2):
        if attempt:
            time.sleep(0.5)
        try:
            removed = _run_git(repo, "worktree", "remove", "--force", str(workdir))
        except OSError as error:
            failure = str(error)
            break
        if removed.returncode == 0:
            return
        failure = removed.stderr.strip()

    if workdir.exists():
        try:
            shutil.rmtree(workdir, onerror=_force_remove)
        except OSError as error:
            failure = f"{failure}; rmtree fallback failed: {error}" if failure else str(error)
    try:
        _run_git(repo, "worktree", "prune")
    except OSError:
        pass

    if workdir.exists():
        print(f"WARNING: worktree left behind at {workdir}: {failure}", file=sys.stderr)


def _force_remove(func: Any, path: Any, exc_info: Any) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed git argv, no shell
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _default_out_dir(task_id: str) -> Path:
    safe_task_id = re.sub(r"[^A-Za-z0-9._-]+", "_", task_id) or "task"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    candidate = DEFAULT_OUT_ROOT / f"{safe_task_id}-{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = DEFAULT_OUT_ROOT / f"{safe_task_id}-{stamp}-{suffix}"
        suffix += 1
    return candidate


def _load_task_object(task_path: Path) -> dict[str, Any]:
    data = json.loads(task_path.read_bytes())
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {task_path}")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
