"""Replay-mode runner tests: archive layout, digest tamper detection, exit codes.

Follows the temporary-git-repo fixture pattern from test_agent_eval_collect.py
and injects a fake CommandRunner through replay.main's run_command seam so the
full CLI path (argparse -> collect -> validate -> score -> archive -> print)
is exercised without running real probe commands.
"""

import json
import subprocess
import sys

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_eval,
]

from scripts.agent_eval import replay
from scripts.agent_eval.collect import CommandOutcome, compute_task_digest

PASS_TASK = {
    "id": "replay_demo_001",
    "page": "ledger-pnl",
    "goal": "Replay-mode demo task with fully probed gates.",
    "required_evidence": ["moss-metric-contracts"],
    "evidence_probes": {"moss-metric-contracts": "evidence/contracts.json"},
    "checks": ["run-unit-tests"],
    "business_gates": ["unit_consistency"],
    "page_gates": ["no_console_errors"],
    "gate_probes": {
        "unit_consistency": "python -m pytest tests/fake_probe_unit.py -q",
        "no_console_errors": "python -m pytest tests/fake_probe_console.py -q",
    },
    "allowed_scope": ["frontend/src/features/ledger-pnl/", "evidence/"],
    "forbidden": ["frontend/src/api/client.ts"],
}

GAPPED_TASK = {
    "id": "replay_demo_002",
    "page": "ledger-pnl",
    "goal": "Replay-mode demo task with one unprobed gate.",
    "required_evidence": [],
    "checks": ["run-unit-tests"],
    "business_gates": ["unit_consistency", "date_semantics"],
    "page_gates": [],
    "gate_probes": {"unit_consistency": "python -m pytest tests/fake_probe_unit.py -q"},
    "gate_probe_gaps": {"date_semantics": "Needs a trade-date basis assertion."},
    "allowed_scope": ["frontend/src/features/ledger-pnl/"],
    "forbidden": [],
}

ARCHIVE_FILES = ["task.json", "result.json", "scorecard.json", "summary.txt"]


def _runner(exit_codes=None):
    codes = exit_codes or {}
    calls = []

    def run(command, cwd, timeout_seconds):
        calls.append(command)
        return CommandOutcome(exit_code=codes.get(command, 0), duration_ms=1)

    run.calls = calls
    return run


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _commit(repo, relative_path, content):
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", relative_path)
    _git(repo, "commit", "-m", f"add {relative_path}")
    return path


def _write_task(directory, task, name="task.json"):
    path = directory / name
    path.write_text(json.dumps(task), encoding="utf-8")
    return path


def _write_evidence(worktree):
    artifact = worktree / "evidence" / "contracts.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps({"source": "moss-metric-contracts", "metric_id": "ledger_pnl_net_interest"}),
        encoding="utf-8",
    )
    return artifact


@pytest.fixture
def worktree(tmp_path):
    """Evaluated worktree kept separate from the task file, as in real replay use."""

    repo = tmp_path / "worktree"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "harness@example.com")
    _git(repo, "config", "user.name", "harness")
    _commit(repo, "seed.txt", "seed\n")
    return repo


def test_replay_pass_archives_four_artifacts_and_exits_zero(worktree, tmp_path, monkeypatch, capsys):
    task_path = _write_task(tmp_path, PASS_TASK)
    _write_evidence(worktree)
    out_dir = tmp_path / "archive" / "run1"

    monkeypatch.setattr(
        sys,
        "argv",
        ["replay.py", "--task", str(task_path), "--worktree", str(worktree), "--out-dir", str(out_dir)],
    )

    assert replay.main(run_command=_runner()) == 0

    for name in ARCHIVE_FILES:
        assert (out_dir / name).is_file()

    # The archived task snapshot is byte-identical, so its digest matches the pinned one.
    assert compute_task_digest(out_dir / "task.json") == compute_task_digest(task_path)

    scorecard = json.loads((out_dir / "scorecard.json").read_text(encoding="utf-8"))
    assert scorecard["status"] == "pass"
    assert scorecard["score"] == 100
    assert scorecard["measured"] is True

    result = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
    assert result["measurement"]["integrity"]["task_digest_verified"] is True
    assert result["changed_files"] == ["evidence/contracts.json"]

    summary = (out_dir / "summary.txt").read_text(encoding="utf-8")
    for expected in [
        "task_id: replay_demo_001",
        f"worktree: {worktree.resolve()}",
        f"head_sha: {result['measurement']['head_sha']}",
        "base_ref: (none)",
        f"task_digest: {compute_task_digest(task_path)}",
        "task_digest_source: computed at replay start",
        "status: pass",
        "score: 100",
        "hard_failures: 0",
        "unprobed_gates: 0",
    ]:
        assert expected in summary

    captured = capsys.readouterr()
    assert "status: pass" in captured.out
    assert "score: 100" in captured.out
    assert str(out_dir / "scorecard.json") in captured.out
    assert captured.err == ""


def test_replay_unprobed_gate_fails_with_reason_on_stderr_and_in_summary(worktree, tmp_path, capsys):
    task_path = _write_task(tmp_path, GAPPED_TASK)
    out_dir = tmp_path / "archive"

    exit_code = replay.main(
        [
            "--task",
            str(task_path),
            "--worktree",
            str(worktree),
            "--base-ref",
            "HEAD",
            "--out-dir",
            str(out_dir),
        ],
        run_command=_runner(),
    )

    assert exit_code == 1

    scorecard = json.loads((out_dir / "scorecard.json").read_text(encoding="utf-8"))
    assert scorecard["status"] == "fail"
    assert "Business gate failed: date_semantics" in scorecard["hard_failures"]

    summary = (out_dir / "summary.txt").read_text(encoding="utf-8")
    assert "status: fail" in summary
    assert "base_ref: HEAD" in summary
    assert "hard_failures: 1" in summary
    assert "date_semantics: Needs a trade-date basis assertion." in summary

    err = capsys.readouterr().err
    assert "date_semantics" in err
    assert "Needs a trade-date basis assertion." in err


def test_replay_external_digest_mismatch_archives_rejection_and_exits_two(worktree, tmp_path, capsys):
    task_path = _write_task(tmp_path, PASS_TASK)
    digest_before = compute_task_digest(task_path)
    _write_task(tmp_path, dict(PASS_TASK, goal="Tampered after the digest was captured."))
    out_dir = tmp_path / "archive"

    exit_code = replay.main(
        [
            "--task",
            str(task_path),
            "--worktree",
            str(worktree),
            "--out-dir",
            str(out_dir),
            "--task-digest",
            digest_before,
        ],
        run_command=_runner(),
    )

    assert exit_code == 2
    assert (out_dir / "result.json").is_file()
    assert (out_dir / "summary.txt").is_file()
    assert not (out_dir / "scorecard.json").exists()

    result = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
    assert result["measurement"]["integrity"]["trusted"] is False
    assert result["measurement"]["integrity"]["task_digest_verified"] is False

    summary = (out_dir / "summary.txt").read_text(encoding="utf-8")
    assert "status: invalid" in summary
    assert "task_digest_source: provided externally before the run" in summary
    assert "digest changed during the run" in summary

    err = capsys.readouterr().err
    assert "Invalid agent eval measurement" in err
    assert str(out_dir) in err


def test_replay_self_computed_digest_detects_mid_run_task_edit(worktree, tmp_path):
    task_path = _write_task(tmp_path, PASS_TASK)
    out_dir = tmp_path / "archive"

    def tampering_runner(command, cwd, timeout_seconds):
        _write_task(tmp_path, dict(PASS_TASK, goal="Rewritten while probes were running."))
        return CommandOutcome(exit_code=0, duration_ms=1)

    exit_code = replay.main(
        ["--task", str(task_path), "--worktree", str(worktree), "--out-dir", str(out_dir)],
        run_command=tampering_runner,
    )

    assert exit_code == 2
    summary = (out_dir / "summary.txt").read_text(encoding="utf-8")
    assert "task_digest_source: computed at replay start" in summary
    assert "digest changed during the run" in summary
    assert not (out_dir / "scorecard.json").exists()


def test_replay_default_out_dir_is_created_and_unique_per_run(worktree, tmp_path, monkeypatch):
    task_path = _write_task(tmp_path, PASS_TASK)
    _write_evidence(worktree)
    monkeypatch.chdir(tmp_path)

    argv = ["--task", str(task_path), "--worktree", str(worktree)]
    assert replay.main(argv, run_command=_runner()) == 0
    assert replay.main(argv, run_command=_runner()) == 0

    replays_root = tmp_path / ".codex-tmp" / "agent-eval" / "replays"
    run_dirs = sorted(path for path in replays_root.iterdir() if path.is_dir())
    assert len(run_dirs) == 2
    for run_dir in run_dirs:
        assert run_dir.name.startswith("replay_demo_001-")
        for name in ARCHIVE_FILES:
            assert (run_dir / name).is_file()


def test_replay_invalid_task_input_exits_two_without_archive(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bad_task = dict(PASS_TASK, gate_probes={"unknown_gate": "probe"})
    task_path = _write_task(tmp_path, bad_task)

    assert replay.main(["--task", str(task_path)], run_command=_runner()) == 2
    assert "Invalid agent eval input" in capsys.readouterr().err

    assert replay.main(["--task", str(tmp_path / "missing.json")], run_command=_runner()) == 2
    assert "Invalid agent eval input" in capsys.readouterr().err

    assert not (tmp_path / ".codex-tmp").exists()
