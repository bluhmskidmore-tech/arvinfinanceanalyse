"""Guard tests for the caliber path-trigger gate (scripts/check_caliber_gate.py).

Covers three surfaces:

1. ``CALIBER_GATE_MAP`` integrity: every mapped source path exists in the
   repository, and the map covers every ``tests/test_caliber_rule_*.py`` file
   on disk (so a future caliber test cannot silently stay outside the gate).
2. Pure matching semantics of ``resolve_required_tests`` (exact path, prefix,
   dedup, deterministic ordering).
3. CLI + git diff behavior against a temporary git repository with an
   injected small gate map: mapped change -> matched tests in dry-run JSON,
   unrelated change -> empty match, invalid base ref -> fail-closed non-zero
   exit.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import check_caliber_gate as gate

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CALIBER_TESTS = {
    "tests/test_caliber_rule_accounting_basis.py",
    "tests/test_caliber_rule_formal_scenario_gate.py",
    "tests/test_caliber_rule_fx_mid_conversion.py",
    "tests/test_caliber_rule_hat_mapping.py",
    "tests/test_caliber_rule_issuance_exclusion.py",
    "tests/test_caliber_rule_subject_514_516_517_merge.py",
}


def test_every_mapped_source_path_exists_in_repo() -> None:
    for source in gate.CALIBER_GATE_MAP:
        target = REPO_ROOT / source
        if source.endswith("/"):
            assert target.is_dir(), f"mapped prefix does not exist: {source}"
        else:
            assert target.is_file(), f"mapped source file does not exist: {source}"


def test_map_covers_every_caliber_rule_test_file() -> None:
    mapped_tests = {
        test_file
        for test_files in gate.CALIBER_GATE_MAP.values()
        for test_file in test_files
    }
    on_disk = {
        f"tests/{path.name}"
        for path in (REPO_ROOT / "tests").glob("test_caliber_rule_*.py")
    }
    # Guard the guard: the six known red-line tests must be on disk, so the
    # equality below cannot pass vacuously against an empty glob.
    assert EXPECTED_CALIBER_TESTS <= on_disk
    assert mapped_tests == on_disk, (
        "CALIBER_GATE_MAP must map to exactly the caliber rule test files on "
        "disk; update scripts/check_caliber_gate.py when adding a caliber test"
    )


def test_resolve_required_tests_exact_prefix_dedup_and_order() -> None:
    small_map = {
        "src/exact.py": ("tests/test_b.py",),
        "pkg/": ("tests/test_a.py", "tests/test_b.py"),
    }
    matched = gate.resolve_required_tests(
        ["src/exact.py", "pkg\\inner\\mod.py", "unrelated.md"],
        gate_map=small_map,
    )
    assert matched == ["tests/test_a.py", "tests/test_b.py"]
    assert gate.resolve_required_tests(["unrelated.md"], gate_map=small_map) == []
    assert gate.resolve_required_tests([], gate_map=small_map) == []


def _run_git(repo: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert completed.returncode == 0, f"git {args} failed: {completed.stderr}"


@pytest.fixture()
def gate_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temporary git repo with one gated file, one unrelated file, tag 'base'.

    Also points the gate script at this repo and injects a small gate map, so
    the tests below exercise diff matching without rebuilding the real
    core_finance tree.
    """
    empty_config = tmp_path / "empty-gitconfig"
    empty_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "-c", "init.defaultBranch=main", "init", "--quiet")
    _run_git(repo, "config", "user.email", "caliber-gate@example.invalid")
    _run_git(repo, "config", "user.name", "Caliber Gate Test")
    (repo / "src").mkdir()
    (repo / "src" / "gated_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "unrelated.txt").write_text("base\n", encoding="utf-8")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "--quiet", "-m", "base")
    _run_git(repo, "tag", "base")

    monkeypatch.setattr(gate, "ROOT", repo)
    monkeypatch.setattr(
        gate,
        "CALIBER_GATE_MAP",
        {"src/gated_module.py": ("tests/test_caliber_rule_hat_mapping.py",)},
    )
    return repo


def test_dry_run_reports_matched_tests_for_gated_change(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "touch gated module")

    exit_code = gate.main(["--base-ref", "base", "--dry-run"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["base_ref"] == "base"
    assert payload["changed_files"] == ["src/gated_module.py"]
    assert payload["matched_tests"] == ["tests/test_caliber_rule_hat_mapping.py"]


def test_dry_run_reports_no_tests_for_unrelated_change(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (gate_repo / "unrelated.txt").write_text("changed\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "touch unrelated file")

    exit_code = gate.main(["--base-ref", "base", "--dry-run"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["changed_files"] == ["unrelated.txt"]
    assert payload["matched_tests"] == []


def test_invalid_base_ref_fails_closed(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = gate.main(["--base-ref", "no-such-ref", "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "FAIL-CLOSED" in captured.err
    assert "no-such-ref" in captured.err
