from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_ruff_ble001_baseline.py"
MYPY_SCRIPT = ROOT / "scripts" / "check_mypy_baseline.py"


def _load_checker(path: Path = SCRIPT):
    module_name = path.stem
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _diagnostic(path: Path, row: int, column: int = 5) -> dict[str, object]:
    return {
        "code": "BLE001",
        "filename": str(path),
        "location": {"row": row, "column": column},
    }


def test_existing_ble001_debt_is_accepted(tmp_path: Path):
    checker = _load_checker()
    source = tmp_path / "backend" / "existing.py"
    source.parent.mkdir()
    source.write_text("try:\n    run()\nexcept Exception:\n    recover()\n", encoding="utf-8")

    baseline = checker.build_violations([_diagnostic(source, 3)], tmp_path)
    current = checker.build_violations([_diagnostic(source, 3)], tmp_path)

    assert checker.compare(baseline, current) == ([], [])


@pytest.mark.parametrize("change, expected", [("add", 1), ("replace", 1), ("remove", 0)])
def test_pr_baseline_cannot_expand_trusted_identities(tmp_path, monkeypatch, change, expected):
    checker = _load_checker()
    monkeypatch.setattr(checker, "resolve_commit", lambda repo, ref: "a" * 40)
    source = tmp_path / "backend" / "debt.py"
    source.parent.mkdir()
    source.write_text("try:\n    old()\nexcept Exception:\n    recover()\n", encoding="utf-8")
    old = checker.build_violations([_diagnostic(source, 3)], tmp_path)
    source.write_text("try:\n    new()\nexcept Exception:\n    recover()\n", encoding="utf-8")
    new = checker.build_violations([_diagnostic(source, 3)], tmp_path)
    working = old + new if change == "add" else new if change == "replace" else []
    monkeypatch.setattr(checker, "require_python_version", lambda: None)
    monkeypatch.setattr(checker, "require_ruff_version", lambda: None)
    monkeypatch.setattr(checker, "run_ruff", lambda: [])
    monkeypatch.setattr(checker, "build_violations", lambda diagnostics: working)
    monkeypatch.setattr(checker, "load_baseline", lambda **kwargs: old if kwargs.get("baseline_ref") else working)
    assert checker.main(["--baseline-ref", "trusted-base"]) == expected


def test_pr_baseline_read_failure_is_closed(monkeypatch):
    checker = _load_checker()
    monkeypatch.setattr(checker, "_run", lambda command: subprocess.CompletedProcess(command, 128, "", "missing ref"))
    with pytest.raises(checker.EvidenceError, match="trusted BLE001"):
        checker.load_baseline(baseline_ref="missing-base")


@pytest.mark.parametrize("derive, expected", [(False, 2), (True, 0)])
def test_first_pr_derives_only_an_absent_baseline(tmp_path, monkeypatch, derive, expected):
    checker = _load_checker()
    monkeypatch.setattr(checker, "resolve_commit", lambda repo, ref: "a" * 40)
    source = tmp_path / "backend" / "existing.py"
    source.parent.mkdir()
    source.write_text("try:\n    run()\nexcept Exception:\n    recover()\n", encoding="utf-8")
    existing = checker.build_violations([_diagnostic(source, 3)], tmp_path)
    monkeypatch.setattr(checker, "require_python_version", lambda: None)
    monkeypatch.setattr(checker, "require_ruff_version", lambda: None)
    monkeypatch.setattr(checker, "run_ruff", lambda: [])
    monkeypatch.setattr(checker, "build_violations", lambda diagnostics: existing)

    def load(**kwargs):
        if kwargs.get("baseline_ref"):
            raise checker.MissingBaselineError("confirmed missing")
        return existing

    monkeypatch.setattr(checker, "load_baseline", load)
    calls = []
    monkeypatch.setattr(checker, "derive_trusted_baseline", lambda ref, parent: calls.append((ref, parent)) or existing)
    argv = ["--baseline-ref", "exact-base"]
    if derive:
        argv.extend(["--derive-missing-baseline", str(tmp_path)])
    assert checker.main(argv) == expected
    assert calls == ([("a" * 40, tmp_path)] if derive else [])


def test_derived_base_does_not_accept_a_pr_rewritten_baseline(tmp_path, monkeypatch):
    checker = _load_checker()
    monkeypatch.setattr(checker, "resolve_commit", lambda repo, ref: "a" * 40)
    source = tmp_path / "backend" / "debt.py"
    source.parent.mkdir()
    source.write_text("try:\n    new()\nexcept Exception:\n    recover()\n", encoding="utf-8")
    new = checker.build_violations([_diagnostic(source, 3)], tmp_path)
    monkeypatch.setattr(checker, "require_python_version", lambda: None)
    monkeypatch.setattr(checker, "require_ruff_version", lambda: None)
    monkeypatch.setattr(checker, "run_ruff", lambda: [])
    monkeypatch.setattr(checker, "build_violations", lambda diagnostics: new)

    def load(**kwargs):
        if kwargs.get("baseline_ref"):
            raise checker.MissingBaselineError("confirmed missing")
        return new

    monkeypatch.setattr(checker, "load_baseline", load)
    monkeypatch.setattr(checker, "derive_trusted_baseline", lambda ref, parent: [])
    assert checker.main(["--baseline-ref", "exact-base", "--derive-missing-baseline", str(tmp_path)]) == 1


def test_corrupt_trusted_baseline_never_uses_source_fallback(tmp_path, monkeypatch):
    checker = _load_checker()
    monkeypatch.setattr(checker, "resolve_commit", lambda repo, ref: "a" * 40)
    monkeypatch.setattr(checker, "require_python_version", lambda: None)
    monkeypatch.setattr(checker, "require_ruff_version", lambda: None)
    monkeypatch.setattr(checker, "run_ruff", lambda: [])

    def load(**kwargs):
        if kwargs.get("baseline_ref"):
            raise checker.EvidenceError("corrupt existing baseline")
        return []

    monkeypatch.setattr(checker, "load_baseline", load)
    monkeypatch.setattr(checker, "derive_trusted_baseline", lambda *args: pytest.fail("corrupt baseline fell back"))
    assert checker.main(["--baseline-ref", "exact-base", "--derive-missing-baseline", str(tmp_path)]) == 2


def test_committed_trusted_baseline_takes_precedence_over_derivation(tmp_path, monkeypatch):
    checker = _load_checker()
    monkeypatch.setattr(checker, "resolve_commit", lambda repo, ref: "a" * 40)
    monkeypatch.setattr(checker, "require_python_version", lambda: None)
    monkeypatch.setattr(checker, "require_ruff_version", lambda: None)
    monkeypatch.setattr(checker, "run_ruff", lambda: [])
    monkeypatch.setattr(checker, "load_baseline", lambda **kwargs: [])
    monkeypatch.setattr(checker, "derive_trusted_baseline", lambda *args: pytest.fail("existing baseline was ignored"))
    assert checker.main(["--baseline-ref", "exact-base", "--derive-missing-baseline", str(tmp_path)]) == 0


def test_moving_ref_cannot_change_missing_baseline_source(tmp_path, monkeypatch):
    checker = _load_checker()
    first_commit, moved_commit = "a" * 40, "b" * 40
    source = tmp_path / "backend" / "new.py"
    source.parent.mkdir()
    source.write_text("try:\n    new()\nexcept Exception:\n    recover()\n", encoding="utf-8")
    diagnostic = _diagnostic(source, 3)
    current = checker.build_violations([diagnostic], tmp_path)
    baseline_path = tmp_path / "scripts" / "ruff_ble001_baseline.json"
    baseline_path.parent.mkdir()
    checker.save_baseline(current, baseline_path)
    baseline_bytes = baseline_path.read_bytes()
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(checker, "require_python_version", lambda: None)
    monkeypatch.setattr(checker, "require_ruff_version", lambda: None)
    monkeypatch.setattr(checker, "run_ruff", lambda: [diagnostic])
    build_violations = checker.build_violations
    monkeypatch.setattr(
        checker, "build_violations",
        lambda diagnostics, repo_root=tmp_path: build_violations(diagnostics, repo_root),
    )
    resolutions, baseline_commits, source_commits = [], [], []

    def resolve(repo, ref):
        resolutions.append(ref)
        if ref == "moving-base":
            return first_commit if resolutions.count(ref) == 1 else moved_commit
        return ref

    def read_blob(repo, commit, path):
        baseline_commits.append(commit)
        return None if commit == first_commit else baseline_bytes

    @contextmanager
    def isolate(repo, commit, parent):
        source_commits.append(commit)
        yield SimpleNamespace(root=tmp_path, commit=commit, provenance=lambda: {"commit": commit})

    def source_run(source, code, arguments):
        diagnostics = [] if source.commit == first_commit else [diagnostic]
        return subprocess.CompletedProcess([], int(bool(diagnostics)), json.dumps(diagnostics), "")

    monkeypatch.setattr(checker, "resolve_commit", resolve)
    monkeypatch.setattr(checker, "read_committed_blob", read_blob)
    monkeypatch.setattr(checker, "isolated_backend_source", isolate)
    monkeypatch.setattr(checker, "run_source_python", source_run)

    assert checker.main([
        "--baseline-ref", "moving-base", "--derive-missing-baseline", str(tmp_path / ".codex-tmp"),
    ]) == 1
    assert resolutions.count("moving-base") == 1
    assert baseline_commits == source_commits == [first_commit]
    assert baseline_path.read_bytes() == baseline_bytes


def test_unresolved_cli_ref_never_uses_source_fallback(tmp_path, monkeypatch, capsys):
    checker = _load_checker()
    monkeypatch.setattr(checker, "require_python_version", lambda: None)
    monkeypatch.setattr(checker, "require_ruff_version", lambda: None)
    monkeypatch.setattr(checker, "run_ruff", lambda: [])
    monkeypatch.setattr(checker, "load_baseline", lambda: [])

    def unresolved(repo, ref):
        raise checker.BaseSourceError("private git failure details")

    monkeypatch.setattr(checker, "resolve_commit", unresolved)
    monkeypatch.setattr(checker, "derive_trusted_baseline", lambda *args: pytest.fail("unresolved ref fell back"))
    assert checker.main([
        "--baseline-ref", "missing-base", "--derive-missing-baseline", str(tmp_path),
    ]) == 2
    error = capsys.readouterr().err
    assert "cannot resolve trusted BLE001 baseline ref" in error
    assert "private git failure details" not in error


def test_one_new_ble001_diagnostic_fails_the_ratchet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    checker = _load_checker()
    source = tmp_path / "backend" / "new.py"
    source.parent.mkdir()
    source.write_text("try:\n    run()\nexcept Exception:\n    recover()\n", encoding="utf-8")

    current = checker.build_violations([_diagnostic(source, 3)], tmp_path)
    new, removed = checker.compare([], current)

    assert len(new) == 1
    assert removed == []
    monkeypatch.setattr(checker, "require_python_version", lambda: None)
    monkeypatch.setattr(checker, "require_ruff_version", lambda: None)
    monkeypatch.setattr(checker, "run_ruff", lambda: [])
    monkeypatch.setattr(checker, "build_violations", lambda diagnostics: current)
    monkeypatch.setattr(checker, "load_baseline", lambda: [])
    assert checker.main([]) == 1


def test_removing_old_debt_cannot_offset_new_debt_elsewhere(tmp_path: Path):
    checker = _load_checker()
    old = tmp_path / "backend" / "old.py"
    new = tmp_path / "backend" / "new.py"
    old.parent.mkdir()
    old.write_text("try:\n    old()\nexcept Exception:\n    recover()\n", encoding="utf-8")
    new.write_text("try:\n    new()\nexcept Exception:\n    recover()\n", encoding="utf-8")

    baseline = checker.build_violations([_diagnostic(old, 3)], tmp_path)
    current = checker.build_violations([_diagnostic(new, 3)], tmp_path)
    added, removed = checker.compare(baseline, current)

    assert len(baseline) == len(current) == 1
    assert [item.path for item in added] == ["backend/new.py"]
    assert [item.path for item in removed] == ["backend/old.py"]


def test_blank_lines_and_comments_do_not_create_a_new_identity(tmp_path: Path):
    checker = _load_checker()
    source = tmp_path / "backend" / "stable.py"
    source.parent.mkdir()
    source.write_text(
        "def run():\n    try:\n        work()\n    except Exception:\n        recover()\n",
        encoding="utf-8",
    )
    baseline = checker.build_violations([_diagnostic(source, 4, 12)], tmp_path)

    source.write_text(
        "# leading comment\n\ndef run():\n    try:\n        work()\n    except Exception:\n        # recovery remains intentional\n        recover()\n",
        encoding="utf-8",
    )
    current = checker.build_violations([_diagnostic(source, 6, 12)], tmp_path)

    assert baseline[0].row != current[0].row
    assert baseline[0].identity == current[0].identity
    assert checker.compare(baseline, current) == ([], [])


def test_moving_the_same_catch_to_another_function_is_new_debt(tmp_path: Path):
    checker = _load_checker()
    source = tmp_path / "backend" / "moved.py"
    source.parent.mkdir()
    source.write_text(
        "def before():\n    try:\n        work()\n    except Exception:\n        recover()\n",
        encoding="utf-8",
    )
    baseline = checker.build_violations([_diagnostic(source, 4, 12)], tmp_path)

    source.write_text(
        "def after():\n    try:\n        work()\n    except Exception:\n        recover()\n",
        encoding="utf-8",
    )
    current = checker.build_violations([_diagnostic(source, 4, 12)], tmp_path)
    new, removed = checker.compare(baseline, current)

    assert len(new) == len(removed) == 1
    assert new[0].scope == "function:after#1"
    assert removed[0].scope == "function:before#1"


def test_identical_handlers_in_one_scope_use_occurrence_numbers(tmp_path: Path):
    checker = _load_checker()
    source = tmp_path / "backend" / "repeated.py"
    source.parent.mkdir()
    source.write_text(
        "def run():\n"
        "    try:\n        work()\n    except Exception:\n        recover()\n"
        "    try:\n        work()\n    except Exception:\n        recover()\n",
        encoding="utf-8",
    )
    baseline = checker.build_violations(
        [_diagnostic(source, 4, 12), _diagnostic(source, 8, 12)], tmp_path
    )

    source.write_text(
        "def run():\n"
        "    try:\n        work()\n    except Exception:\n        recover()\n"
        "    try:\n        work()\n    except Exception:\n        recover()\n"
        "    try:\n        work()\n    except Exception:\n        recover()\n",
        encoding="utf-8",
    )
    current = checker.build_violations(
        [
            _diagnostic(source, 4, 12),
            _diagnostic(source, 8, 12),
            _diagnostic(source, 12, 12),
        ],
        tmp_path,
    )
    new, removed = checker.compare(baseline, current)

    assert [item.occurrence for item in baseline] == [1, 2]
    assert [item.occurrence for item in new] == [3]
    assert removed == []


def test_moving_identical_handler_to_a_different_try_body_is_new_debt(tmp_path: Path):
    checker = _load_checker()
    source = tmp_path / "backend" / "protected_body.py"
    source.parent.mkdir()
    source.write_text(
        "def run():\n"
        "    try:\n        first()\n    except Exception:\n        return None\n"
        "    second()\n",
        encoding="utf-8",
    )
    baseline = checker.build_violations([_diagnostic(source, 4, 12)], tmp_path)

    source.write_text(
        "def run():\n"
        "    first()\n"
        "    try:\n        second()\n    except Exception:\n        return None\n",
        encoding="utf-8",
    )
    current = checker.build_violations([_diagnostic(source, 5, 12)], tmp_path)
    new, removed = checker.compare(baseline, current)

    assert len(new) == len(removed) == 1
    assert new[0].handler_ast_sha256 == removed[0].handler_ast_sha256
    assert new[0].try_body_ast_sha256 != removed[0].try_body_ast_sha256


def test_ruff_tool_failure_is_fatal(monkeypatch: pytest.MonkeyPatch):
    checker = _load_checker()

    def failed_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="boom")

    monkeypatch.setattr(checker.subprocess, "run", failed_run)

    with pytest.raises(checker.EvidenceError, match="Ruff exited 2"):
        checker.run_ruff()


def test_ruff_version_mismatch_is_fatal(monkeypatch: pytest.MonkeyPatch):
    checker = _load_checker()
    monkeypatch.setattr(
        checker,
        "_run",
        lambda command: subprocess.CompletedProcess(
            args=command, returncode=0, stdout="ruff 9.9.9\n", stderr=""
        ),
    )

    with pytest.raises(checker.EvidenceError, match="version mismatch"):
        checker.require_ruff_version()


def test_python_version_mismatch_is_fatal(monkeypatch: pytest.MonkeyPatch):
    checker = _load_checker()
    monkeypatch.setattr(checker, "sys", SimpleNamespace(version_info=(3, 14)))

    with pytest.raises(checker.EvidenceError, match="Python version mismatch"):
        checker.require_python_version()


def test_update_refuses_new_debt_without_changing_baseline_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    checker = _load_checker()
    old = tmp_path / "backend" / "old.py"
    new = tmp_path / "backend" / "new.py"
    old.parent.mkdir()
    old.write_text("try:\n    old()\nexcept Exception:\n    recover()\n", encoding="utf-8")
    new.write_text("try:\n    new()\nexcept Exception:\n    recover()\n", encoding="utf-8")
    baseline = checker.build_violations([_diagnostic(old, 3)], tmp_path)
    current = baseline + checker.build_violations([_diagnostic(new, 3)], tmp_path)
    baseline_path = tmp_path / "baseline.json"
    checker.save_baseline(baseline, baseline_path)
    original = baseline_path.read_bytes()
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(checker, "require_python_version", lambda: None)
    monkeypatch.setattr(checker, "require_ruff_version", lambda: None)
    monkeypatch.setattr(checker, "run_ruff", lambda: [])
    monkeypatch.setattr(checker, "build_violations", lambda diagnostics: current)

    assert checker.main(["--update-baseline"]) == 1
    assert baseline_path.read_bytes() == original


def test_update_writes_a_strictly_reduced_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    checker = _load_checker()
    first = tmp_path / "backend" / "first.py"
    second = tmp_path / "backend" / "second.py"
    first.parent.mkdir()
    first.write_text("try:\n    first()\nexcept Exception:\n    recover()\n", encoding="utf-8")
    second.write_text("try:\n    second()\nexcept Exception:\n    recover()\n", encoding="utf-8")
    kept = checker.build_violations([_diagnostic(first, 3)], tmp_path)
    removed = checker.build_violations([_diagnostic(second, 3)], tmp_path)
    baseline_path = tmp_path / "baseline.json"
    checker.save_baseline(kept + removed, baseline_path)
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(checker, "require_python_version", lambda: None)
    monkeypatch.setattr(checker, "require_ruff_version", lambda: None)
    monkeypatch.setattr(checker, "run_ruff", lambda: [])
    monkeypatch.setattr(checker, "build_violations", lambda diagnostics: kept)

    assert checker.main(["--update-baseline"]) == 0
    assert checker.load_baseline(baseline_path) == kept


def test_update_does_not_seed_a_missing_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    checker = _load_checker()
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(checker, "BASELINE_PATH", missing)
    monkeypatch.setattr(checker, "require_python_version", lambda: None)
    monkeypatch.setattr(checker, "require_ruff_version", lambda: None)
    monkeypatch.setattr(checker, "run_ruff", lambda: [])
    monkeypatch.setattr(checker, "build_violations", lambda diagnostics: [])

    assert checker.main(["--update-baseline"]) == 2
    assert not missing.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "not-a-sha256"),
        ("path", "../escape.py"),
        ("scope", ""),
        ("occurrence", True),
        ("try_body_ast_sha256", "z" * 64),
        ("handler_ast_sha256", "A" * 64),
        ("row", -1),
        ("column", "1"),
        ("source", 123),
    ],
)
def test_invalid_baseline_entries_fail_closed(
    tmp_path: Path, field: str, value: object
):
    checker = _load_checker()
    source = tmp_path / "backend" / "existing.py"
    source.parent.mkdir()
    source.write_text("try:\n    run()\nexcept Exception:\n    recover()\n", encoding="utf-8")
    baseline_path = tmp_path / "baseline.json"
    checker.save_baseline(
        checker.build_violations([_diagnostic(source, 3)], tmp_path), baseline_path
    )
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    payload["violations"][0][field] = value
    baseline_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(checker.EvidenceError):
        checker.load_baseline(baseline_path)


def test_mypy_per_file_ratchet_does_not_allow_cross_file_offset():
    checker = _load_checker(MYPY_SCRIPT)

    regressions, new_files, improvements = checker.compare(
        {"backend/app/old.py": 1, "backend/app/other.py": 1},
        {"backend/app/other.py": 2},
    )

    assert regressions == [("backend/app/other.py", 1, 2)]
    assert new_files == []
    assert improvements == [("backend/app/old.py", 1, 0)]


def test_ci_uses_blocking_ruff_debt_gate():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    ruff_job = workflow.split("\n  mypy-ratchet:", 1)[0].split("\n  backend-lint:", 1)[1]

    assert "python scripts/check_ruff_ble001_baseline.py" in ruff_job
    assert "BLE001" in ruff_job
    assert "|| true" not in ruff_job
