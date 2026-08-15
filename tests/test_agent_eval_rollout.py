"""Rollout-mode runner tests: isolation, agent logging, tamper resistance, cleanup.

Follows the temporary-git-repo fixture pattern from test_agent_eval_replay.py.
The fake agent is a real `python -c` one-liner executed through rollout's shell
path (cross-platform via sys.executable), while probe/check commands go through
the injected CommandRunner seam so no real pytest/npm probes run. Every test
uses its own tmp_path-derived out-dir, so worktree paths never collide across
tests or xdist workers.
"""

import json
import subprocess
import sys

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_eval,
]

from scripts.agent_eval import rollout
from scripts.agent_eval.collect import CommandOutcome, compute_task_digest

PROBED_TASK = {
    "id": "rollout_demo_001",
    "page": "ledger-pnl",
    "goal": "Rollout-mode demo task with fully probed gates.",
    "required_evidence": ["moss-metric-contracts"],
    "evidence_probes": {"moss-metric-contracts": "evidence/contracts.json"},
    "checks": ["run-unit-tests"],
    "business_gates": ["unit_consistency"],
    "page_gates": ["no_console_errors"],
    "gate_probes": {
        "unit_consistency": "python -m pytest tests/fake_probe_unit.py -q",
        "no_console_errors": "python -m pytest tests/fake_probe_console.py -q",
    },
    "allowed_scope": ["notes/", "evidence/"],
    "forbidden": ["frontend/src/api/client.ts"],
}

# Spec floor: validate_task_spec rejects a task whose business/page gates,
# checks, and required evidence are all empty (it would always score 100).
# The minimal fixture therefore carries exactly one probed gate; the injected
# runner answers exit 0, so rollout-mechanics assertions keep their semantics.
MINIMAL_TASK = {
    "id": "rollout_min_001",
    "goal": "Minimal rollout task: one probed gate, no checks, no evidence.",
    "required_evidence": [],
    "checks": [],
    "business_gates": ["unit_consistency"],
    "page_gates": [],
    "gate_probes": {"unit_consistency": "python -m pytest tests/fake_probe_min.py -q"},
    "allowed_scope": ["notes/"],
    "forbidden": [],
}

TASK_RELATIVE_PATH = "scripts/agent_eval/tasks/demo.json"
EVAL_ARCHIVE_FILES = ["task.json", "result.json", "scorecard.json", "summary.txt"]


def _runner(exit_codes=None):
    codes = exit_codes or {}
    calls = []

    def run(command, cwd, timeout_seconds):
        calls.append((command, cwd))
        return CommandOutcome(exit_code=codes.get(command, 0), duration_ms=1)

    run.calls = calls
    return run


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _commit_file(repo, relative_path, content):
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", relative_path)
    _git(repo, "commit", "-m", f"add {relative_path}")
    return path


def _commit_task(repo, task, relative_path=TASK_RELATIVE_PATH):
    return _commit_file(repo, relative_path, json.dumps(task))


def _agent_cmd(code):
    """Cross-platform shell one-liner; the code must avoid double quotes."""

    return f'"{sys.executable}" -c "{code}"'


def _rollout_argv(task_path, repo, out_dir, agent_cmd, base_ref="HEAD"):
    return [
        "--task",
        str(task_path),
        "--repo",
        str(repo),
        "--base-ref",
        base_ref,
        "--agent-cmd",
        agent_cmd,
        "--out-dir",
        str(out_dir),
    ]


def _worktree_registered(repo, workdir):
    listed = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return workdir.resolve().as_posix().lower() in listed.lower()


@pytest.fixture
def source_repo(tmp_path):
    """Source repository the isolated worktree is detached from."""

    repo = tmp_path / "source"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "harness@example.com")
    _git(repo, "config", "user.name", "harness")
    _commit_file(repo, "seed.txt", "seed\n")
    return repo


def test_rollout_pass_archives_agent_log_and_artifacts_and_cleans_worktree(source_repo, tmp_path, capsys):
    task_path = _commit_task(source_repo, PROBED_TASK)
    out_dir = tmp_path / "archive"
    workdir = out_dir / "workdir"
    agent_cmd = _agent_cmd(
        "import json, pathlib; "
        "pathlib.Path('notes').mkdir(exist_ok=True); "
        "pathlib.Path('notes/fix.txt').write_text('agent change'); "
        "pathlib.Path('evidence').mkdir(exist_ok=True); "
        "json.dump({'source': 'moss-metric-contracts'}, open('evidence/contracts.json', 'w'))"
    )
    runner = _runner()

    exit_code = rollout.main(_rollout_argv(task_path, source_repo, out_dir, agent_cmd), run_command=runner)

    assert exit_code == 0

    for name in ["agent.log", *EVAL_ARCHIVE_FILES]:
        assert (out_dir / name).is_file()

    agent_log = (out_dir / "agent.log").read_text(encoding="utf-8")
    assert agent_cmd in agent_log
    assert "# exit_code: 0" in agent_log
    assert "# timed_out: false" in agent_log

    # The archived task snapshot matches the digest pinned before the agent ran.
    assert compute_task_digest(out_dir / "task.json") == compute_task_digest(task_path)

    scorecard = json.loads((out_dir / "scorecard.json").read_text(encoding="utf-8"))
    assert scorecard["status"] == "pass"
    assert scorecard["score"] == 100
    assert scorecard["measured"] is True

    result = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
    assert result["changed_files"] == ["evidence/contracts.json", "notes/fix.txt"]
    assert result["measurement"]["integrity"]["task_digest_verified"] is True
    assert result["measurement"]["integrity"]["trusted"] is True

    # One check plus two gate probes, all executed inside the isolated worktree.
    assert len(runner.calls) == 3
    assert all(cwd == workdir.resolve() for _command, cwd in runner.calls)

    summary = (out_dir / "summary.txt").read_text(encoding="utf-8")
    assert "task_digest_source: provided externally before the run" in summary
    assert "status: pass" in summary

    assert not workdir.exists()
    assert not _worktree_registered(source_repo, workdir)

    out = capsys.readouterr().out
    assert f"task_digest: {compute_task_digest(task_path)}" in out
    assert "agent_exit_code: 0" in out
    assert "status: pass" in out


def test_rollout_agent_nonzero_exit_archives_log_exits_three_and_cleans_worktree(
    source_repo, tmp_path, capsys
):
    task_path = _commit_task(source_repo, MINIMAL_TASK)
    out_dir = tmp_path / "archive"
    runner = _runner()

    exit_code = rollout.main(
        _rollout_argv(task_path, source_repo, out_dir, _agent_cmd("import sys; sys.exit(7)")),
        run_command=runner,
    )

    assert exit_code == 3

    agent_log = (out_dir / "agent.log").read_text(encoding="utf-8")
    assert "# exit_code: 7" in agent_log
    assert "# timed_out: false" in agent_log

    # Evaluation never started: no eval artifacts, no probe/check executions.
    for name in EVAL_ARCHIVE_FILES:
        assert not (out_dir / name).exists()
    assert runner.calls == []

    assert not (out_dir / "workdir").exists()
    assert not _worktree_registered(source_repo, out_dir / "workdir")
    assert "exited with code 7" in capsys.readouterr().err


def test_rollout_agent_timeout_exits_three_and_cleans_worktree(source_repo, tmp_path, capsys):
    task_path = _commit_task(source_repo, MINIMAL_TASK)
    out_dir = tmp_path / "archive"

    exit_code = rollout.main(
        _rollout_argv(task_path, source_repo, out_dir, _agent_cmd("import time; time.sleep(60)"))
        + ["--timeout-seconds", "1"],
        run_command=_runner(),
    )

    assert exit_code == 3

    agent_log = (out_dir / "agent.log").read_text(encoding="utf-8")
    assert "# timed_out: true" in agent_log

    assert not (out_dir / "scorecard.json").exists()
    assert not (out_dir / "workdir").exists()
    assert not _worktree_registered(source_repo, out_dir / "workdir")
    assert "timed out after 1s" in capsys.readouterr().err


def test_rollout_worktree_task_copy_tamper_is_void_and_scored_from_source_task(source_repo, tmp_path):
    task_path = _commit_task(source_repo, dict(MINIMAL_TASK, id="rollout_tamper_001"))
    pinned_digest = compute_task_digest(task_path)
    out_dir = tmp_path / "archive"
    agent_cmd = _agent_cmd(
        "import pathlib; "
        f"pathlib.Path('{TASK_RELATIVE_PATH}').write_text('tampered by agent')"
    )

    exit_code = rollout.main(
        _rollout_argv(task_path, source_repo, out_dir, agent_cmd), run_command=_runner()
    )

    assert exit_code == 2

    # The evaluation consumed the source-repo task file, not the tampered
    # worktree copy: the archived snapshot still matches the pinned digest.
    assert compute_task_digest(out_dir / "task.json") == pinned_digest
    assert compute_task_digest(task_path) == pinned_digest

    result = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
    integrity = result["measurement"]["integrity"]
    assert integrity["trusted"] is False
    assert integrity["task_digest_verified"] is True
    assert f"Scoring harness file modified during the run: {TASK_RELATIVE_PATH}" in integrity["violations"]
    assert not (out_dir / "scorecard.json").exists()

    summary = (out_dir / "summary.txt").read_text(encoding="utf-8")
    assert "status: invalid" in summary
    assert "task_digest_source: provided externally before the run" in summary

    assert not (out_dir / "workdir").exists()
    assert not _worktree_registered(source_repo, out_dir / "workdir")


def test_rollout_keep_worktree_preserves_isolated_tree_and_prints_path(source_repo, tmp_path, capsys):
    task_path = _commit_task(source_repo, MINIMAL_TASK)
    out_dir = tmp_path / "archive"
    workdir = out_dir / "workdir"
    agent_cmd = _agent_cmd(
        "import pathlib; "
        "pathlib.Path('notes').mkdir(exist_ok=True); "
        "pathlib.Path('notes/fix.txt').write_text('kept')"
    )

    exit_code = rollout.main(
        _rollout_argv(task_path, source_repo, out_dir, agent_cmd) + ["--keep-worktree"],
        run_command=_runner(),
    )

    assert exit_code == 0
    assert (workdir / "notes" / "fix.txt").read_text(encoding="utf-8") == "kept"
    assert (workdir / "seed.txt").is_file()  # detached checkout of base-ref content
    assert _worktree_registered(source_repo, workdir)
    assert f"worktree kept: {workdir.resolve()}" in capsys.readouterr().out


def test_rollout_bad_base_ref_exits_two_without_leftover_worktree(source_repo, tmp_path, capsys):
    task_path = _commit_task(source_repo, MINIMAL_TASK)
    out_dir = tmp_path / "archive"

    exit_code = rollout.main(
        _rollout_argv(task_path, source_repo, out_dir, _agent_cmd("pass"), base_ref="no-such-ref"),
        run_command=_runner(),
    )

    assert exit_code == 2
    assert not (out_dir / "workdir").exists()
    assert not (out_dir / "agent.log").exists()
    assert not _worktree_registered(source_repo, out_dir / "workdir")
    assert "worktree add" in capsys.readouterr().err


def test_rollout_invalid_task_exits_two_before_creating_worktree(source_repo, tmp_path, capsys):
    bad_task = dict(MINIMAL_TASK)
    bad_task.pop("allowed_scope")
    task_path = tmp_path / "bad_task.json"
    task_path.write_text(json.dumps(bad_task), encoding="utf-8")
    out_dir = tmp_path / "archive"

    exit_code = rollout.main(
        _rollout_argv(task_path, source_repo, out_dir, _agent_cmd("pass")), run_command=_runner()
    )

    assert exit_code == 2
    assert not out_dir.exists()
    assert "Invalid agent eval input" in capsys.readouterr().err
