from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _checker():
    name = "mypy_baseline_under_test"
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/check_mypy_baseline.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _legacy_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, current: int, update: bool):
    checker = _checker()
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"files": {"backend/app/example.py": 1}}), encoding="utf-8")
    original = baseline.read_bytes()
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline)
    monkeypatch.setattr(checker, "mypy_version", lambda: "mypy 1.20.1 (compiled: yes)")
    monkeypatch.setattr(
        checker,
        "collect_current_errors",
        lambda: (
            {"backend/app/example.py": current},
            {
                "backend/app/example.py": [
                    'backend/app/example.py:2: error: Name "new_error" is not defined  [name-defined]'
                ]
                * current
            },
        ),
    )
    monkeypatch.setattr(sys, "argv", ["check_mypy_baseline.py"] + (["--update-baseline"] if update else []))
    result = checker.main()
    return result, original, baseline.read_bytes()


def test_count_only_baseline_cannot_certify_same_count_replacement(tmp_path, monkeypatch, capsys):
    result, original, after = _legacy_run(tmp_path, monkeypatch, current=1, update=False)
    assert result == 2
    assert after == original
    assert "MIGRATION_REQUIRED" in capsys.readouterr().err


@pytest.mark.parametrize("current", [1, 2])
def test_update_never_absorbs_new_diagnostics_into_legacy_counts(tmp_path, monkeypatch, current):
    result, original, after = _legacy_run(tmp_path, monkeypatch, current=current, update=True)
    assert result == 2
    assert after == original


def _source(tmp_path: Path, source: str, row: int = 2, message: str = "Incompatible return value type"):
    path = tmp_path / "backend/app/example.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8", newline="\n")
    return {"backend/app/example.py": [f"backend/app/example.py:{row}:12: error: {message}  [return-value]"]}


def _identity_baseline(checker, tmp_path: Path, diagnostics):
    counts = dict(checker.Counter(item.path for item in diagnostics))
    source_hashes = [[path, "1" * 64] for path in sorted(counts)]
    config, lock = tmp_path / "backend/pyproject.toml", tmp_path / "backend/uv.lock"
    if not config.exists():
        config.write_text("[tool.mypy]\npython_version='3.11'\n", encoding="utf-8")
    if not lock.exists():
        lock.write_text("version=1\n", encoding="utf-8")
    payload = {
        "_meta": {
            "schema_version": 2,
            "python_version": "3.11",
            "mypy_version": "mypy 1.20.1",
            "target": "backend/app",
            "total_errors": len(diagnostics),
            "total_files": len(counts),
            "origin": {
                "kind": "historical_replay",
                "git_commit": "a" * 40,
                "git_tree": "b" * 40,
                "legacy_baseline_sha256": "c" * 64,
                "stdout_sha256": "d" * 64,
                "config_sha256": checker._digest(config.read_bytes()),
                "lock_sha256": checker._digest(lock.read_bytes()),
                "per_file_counts_verified": True,
                "environment": {
                    "python": "3.11.9",
                    "mypy": "1.20.1",
                    "executable": "isolated-fixture-python",
                    "editable_source": str(tmp_path / "backend"),
                },
                "command": ["fixture-mypy"],
                "captured_at": "2026-08-15T12:32:14Z",
                "sources_sha256": source_hashes,
                "sources_manifest_sha256": checker._source_manifest_digest(source_hashes),
            },
        },
        "files": counts,
        "diagnostics": [{"id": item.identity, **asdict(item)} for item in diagnostics],
    }
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_real_baseline_retains_separate_paths_and_all_source_hashes():
    checker = _checker()
    baseline = json.loads((ROOT / "scripts/mypy_baseline.json").read_text(encoding="utf-8"))
    sources = baseline["_meta"]["origin"]["sources_sha256"]

    assert isinstance(sources, list)
    assert len(sources) == 971
    assert len({path for path, _ in sources}) == 971
    checker.load_baseline()


@pytest.mark.parametrize("corruption", ["hash", "path", "duplicate", "traversal"])
def test_source_hash_manifest_tampering_fails_before_mypy(tmp_path, monkeypatch, corruption):
    checker = _checker()
    diagnostics = checker.build_diagnostics(_source(tmp_path, "def run():\n    return value\n"), tmp_path)
    baseline_path = _identity_baseline(checker, tmp_path, diagnostics)
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    origin = data["_meta"]["origin"]
    sources = origin["sources_sha256"]
    if corruption == "hash":
        sources[0][1] = "2" * 64
    elif corruption == "path":
        sources[0][0] = "backend/app/renamed.py"
        origin["sources_manifest_sha256"] = checker._source_manifest_digest(sources)
    elif corruption == "duplicate":
        sources.append(list(sources[0]))
        origin["sources_manifest_sha256"] = checker._source_manifest_digest(sources)
    else:
        sources[0][0] = "backend/../outside.py"
        origin["sources_manifest_sha256"] = checker._source_manifest_digest(sources)
    baseline_path.write_text(json.dumps(data), encoding="utf-8")
    original = baseline_path.read_bytes()
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(checker, "run_mypy", lambda: pytest.fail("invalid source manifest must fail before mypy"))

    assert checker.main(["--update-baseline"]) == 2
    assert baseline_path.read_bytes() == original


def _run_identity_gate(checker, monkeypatch, root, baseline_path, lines, *, update=False):
    monkeypatch.setattr(checker, "REPO_ROOT", root)
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(checker, "require_tool_versions", lambda: None)
    monkeypatch.setattr(
        checker,
        "collect_current_errors",
        lambda: (
            {path: len(items) for path, items in lines.items()},
            lines,
        ),
    )
    return checker.main(["--update-baseline"] if update else [])


@pytest.mark.parametrize("update", [False, True])
def test_equal_count_statement_replacement_is_rejected(tmp_path, monkeypatch, update):
    checker = _checker()
    old = _source(tmp_path, "def run():\n    return old_value\n")
    diagnostics = checker.build_diagnostics(old, tmp_path)
    baseline_path = _identity_baseline(checker, tmp_path, diagnostics)
    original = baseline_path.read_bytes()
    new = _source(tmp_path, "def run():\n    return new_value\n")

    assert _run_identity_gate(checker, monkeypatch, tmp_path, baseline_path, new, update=update) == 1
    assert baseline_path.read_bytes() == original


def test_identity_includes_diagnostic_message_and_code(tmp_path):
    checker = _checker()
    lines = _source(tmp_path, "def run():\n    return value\n")
    old = checker.build_diagnostics(lines, tmp_path)
    changed_message = _source(tmp_path, "def run():\n    return value\n", message="A different return failure")
    changed_code = {
        path: [line.replace("[return-value]", "[name-defined]") for line in items] for path, items in lines.items()
    }

    for replacement in (changed_message, changed_code):
        new, removed = checker.compare_diagnostics(old, checker.build_diagnostics(replacement, tmp_path))
        assert len(new) == len(removed) == 1


def test_comment_and_line_shifts_preserve_identity(tmp_path):
    checker = _checker()
    old = checker.build_diagnostics(_source(tmp_path, "def run():\n    return value\n"), tmp_path)
    current = checker.build_diagnostics(
        _source(tmp_path, "# comment\n\ndef run():\n    return value\n", row=4),
        tmp_path,
    )
    assert old[0].row != current[0].row
    assert checker.compare_diagnostics(old, current) == ([], [])


def test_update_removes_only_resolved_identities_and_preserves_origin(tmp_path, monkeypatch):
    checker = _checker()
    lines = _source(tmp_path, "def run():\n    return value\n")
    diagnostics = checker.build_diagnostics(lines, tmp_path)
    baseline_path = _identity_baseline(checker, tmp_path, diagnostics)
    origin = json.loads(baseline_path.read_text(encoding="utf-8"))["_meta"]["origin"]

    assert _run_identity_gate(checker, monkeypatch, tmp_path, baseline_path, {}, update=True) == 0
    data, remaining, _ = checker.load_baseline(baseline_path)
    assert remaining == []
    assert data["files"] == {}
    assert data["_meta"]["origin"] == origin


def test_reduction_keeps_original_evidence_for_a_moved_survivor(tmp_path, monkeypatch):
    checker = _checker()
    lines = _source(tmp_path, "def fixed():\n    return old\n\ndef kept():\n    return value\n")
    lines["backend/app/example.py"].append(
        "backend/app/example.py:5:12: error: Incompatible return value type  [return-value]"
    )
    diagnostics = checker.build_diagnostics(lines, tmp_path)
    baseline_path = _identity_baseline(checker, tmp_path, diagnostics)
    current = _source(tmp_path, "def kept():\n    return value\n")

    assert _run_identity_gate(checker, monkeypatch, tmp_path, baseline_path, current, update=True) == 0
    _, remaining, _ = checker.load_baseline(baseline_path)
    assert remaining == [diagnostics[1]]
    assert remaining[0].row == 5


def test_update_does_not_seed_missing_baseline(tmp_path, monkeypatch):
    checker = _checker()
    baseline_path = tmp_path / "missing.json"
    assert _run_identity_gate(checker, monkeypatch, tmp_path, baseline_path, {}, update=True) == 2
    assert not baseline_path.exists()


@pytest.mark.parametrize(
    "python_version,mypy_version",
    [
        ((3, 14), "mypy 1.20.1 (compiled: yes)"),
        ((3, 11), "mypy 1.20.2 (compiled: yes)"),
        ((3, 11), "unknown"),
    ],
)
def test_tool_version_mismatch_is_fatal(monkeypatch, python_version, mypy_version):
    checker = _checker()
    monkeypatch.setattr(checker, "sys", SimpleNamespace(version_info=python_version))
    monkeypatch.setattr(checker, "mypy_version", lambda: mypy_version)
    with pytest.raises(checker.EvidenceError, match="version mismatch"):
        checker.require_tool_versions()


@pytest.mark.parametrize("corruption", ["origin", "digest", "count", "duplicate", "path"])
def test_untrustworthy_baseline_never_runs_mypy_or_changes_bytes(tmp_path, monkeypatch, corruption):
    checker = _checker()
    diagnostics = checker.build_diagnostics(_source(tmp_path, "def run():\n    return value\n"), tmp_path)
    baseline_path = _identity_baseline(checker, tmp_path, diagnostics)
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    if corruption == "origin":
        data["_meta"].pop("origin")
    elif corruption == "digest":
        data["diagnostics"][0]["id"] = "0" * 64
    elif corruption == "count":
        data["files"]["backend/app/example.py"] = 0
    elif corruption == "duplicate":
        data["diagnostics"] *= 2
    else:
        data["diagnostics"][0]["path"] = "../outside.py"
    baseline_path.write_text(json.dumps(data), encoding="utf-8")
    original = baseline_path.read_bytes()
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(checker, "run_mypy", lambda: pytest.fail("invalid baseline must fail before mypy"))

    assert checker.main(["--update-baseline"]) == 2
    assert baseline_path.read_bytes() == original


@pytest.mark.parametrize(
    "stdout,code",
    [
        ("Success: no issues found in 1 source file\nbackend/app/example.py:1: error: bad [assignment]\n", 0),
        ("backend/app/example.py:1: error: bad  [assignment]\n", 1),
        ("backend/app/example.py:1: error: bad  [assignment]\nFound 2 errors in 1 file\n", 1),
        ("", 0),
    ],
)
def test_incomplete_or_contradictory_tool_output_fails_closed(monkeypatch, stdout, code):
    checker = _checker()
    monkeypatch.setattr(checker, "run_mypy", lambda: (code, stdout, ""))
    with pytest.raises((checker.EvidenceError, SystemExit)):
        checker.collect_current_errors()


def _migration_fixture(tmp_path, monkeypatch):
    checker = _checker()
    repo, historical = tmp_path / "repo", tmp_path / "historical"
    repo.mkdir()
    historical.mkdir()
    for root in (repo, historical):
        _source(root, "def run():\n    return value\n")
        (root / "backend/pyproject.toml").write_text(
            "[tool.mypy]\npython_version='3.11'\n", encoding="utf-8", newline="\n"
        )
        (root / "backend/uv.lock").write_text("version=1\n", encoding="utf-8", newline="\n")
    baseline = repo / "scripts/mypy_baseline.json"
    baseline.parent.mkdir()
    baseline.write_text(
        json.dumps(
            {
                "_meta": {"mypy_version": "mypy 1.20.1 (compiled: yes)", "total_errors": 1, "total_files": 1},
                "files": {"backend/app/example.py": 1},
            }
        ),
        encoding="utf-8",
    )
    for args in (
        ["init", "-q"],
        ["add", "."],
        ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "historical fixture"],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    commit = (
        subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()
    )
    stdout = tmp_path / "replay.stdout"
    stdout.write_text(
        "backend/app/example.py:2:12: error: Incompatible return value type  [return-value]\n"
        "backend/scripts/unwaived.py:1:1: error: Historical but not frozen  [name-defined]\n"
        "Found 2 errors in 2 files (checked 1 source file)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(checker, "REPO_ROOT", repo)
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline)
    monkeypatch.setattr(checker, "require_tool_versions", lambda: None)
    monkeypatch.setattr(
        checker,
        "replay_environment",
        lambda root, executable: {
            "python": "3.11.9",
            "mypy": "1.20.1",
            "executable": executable,
            "editable_source": str(root / "backend"),
        },
    )
    command = [
        "python",
        "-m",
        "mypy",
        "backend/app",
        "--config-file",
        "backend/pyproject.toml",
        "--explicit-package-bases",
        "--no-incremental",
        "--show-error-codes",
        "--show-column-numbers",
    ]
    return checker, historical, stdout, commit, command


def test_migration_only_freezes_registered_historical_counts(tmp_path, monkeypatch):
    checker, historical, stdout, commit, command = _migration_fixture(tmp_path, monkeypatch)
    original = checker.BASELINE_PATH.read_bytes()
    payload, unwaived = checker.build_legacy_migration(historical, stdout, commit, command)

    assert payload["files"] == {"backend/app/example.py": 1}
    assert len(payload["diagnostics"]) == 1
    assert unwaived == {"backend/scripts/unwaived.py": 1}
    assert payload["_meta"]["origin"]["git_commit"] == commit
    assert payload["_meta"]["origin"]["legacy_baseline_sha256"] == checker._digest(original)
    assert payload["_meta"]["origin"]["stdout_sha256"] == checker._digest(stdout.read_bytes())
    assert payload["_meta"]["origin"]["sources_sha256"] == [
        ["backend/app/example.py", checker._digest((historical / "backend/app/example.py").read_bytes())]
    ]
    assert payload["_meta"]["origin"]["sources_manifest_sha256"] == checker._source_manifest_digest(
        payload["_meta"]["origin"]["sources_sha256"]
    )
    assert checker.BASELINE_PATH.read_bytes() == original


@pytest.mark.parametrize("corruption", ["source", "count", "baseline", "commit"])
def test_migration_rejects_unverified_historical_evidence(tmp_path, monkeypatch, corruption):
    checker, historical, stdout, commit, command = _migration_fixture(tmp_path, monkeypatch)
    if corruption == "source":
        (historical / "backend/app/example.py").write_text("def run():\n    return other\n", encoding="utf-8")
    elif corruption == "count":
        stdout.write_text(
            "backend/app/example.py:2: error: Different error  [return-value]\n"
            "backend/app/example.py:2: error: Another error  [name-defined]\n"
            "Found 2 errors in 1 file (checked 1 source file)\n",
            encoding="utf-8",
        )
    elif corruption == "baseline":
        checker.BASELINE_PATH.write_bytes(checker.BASELINE_PATH.read_bytes() + b"\n")
    else:
        commit = "0" * 40
    original = checker.BASELINE_PATH.read_bytes()
    with pytest.raises(checker.EvidenceError):
        checker.build_legacy_migration(historical, stdout, commit, command)
    assert checker.BASELINE_PATH.read_bytes() == original


@pytest.mark.parametrize("changed_input", ["backend/pyproject.toml", "backend/uv.lock"])
def test_changed_verification_inputs_cannot_clear_baseline(tmp_path, monkeypatch, changed_input):
    checker = _checker()
    diagnostics = checker.build_diagnostics(_source(tmp_path, "def run():\n    return value\n"), tmp_path)
    baseline_path = _identity_baseline(checker, tmp_path, diagnostics)
    original = baseline_path.read_bytes()
    target = tmp_path / changed_input
    target.write_text("[tool.mypy]\nignore_errors = true\n", encoding="utf-8")
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(checker, "require_tool_versions", lambda: None)
    monkeypatch.setattr(checker, "collect_current_errors", lambda: ({}, {}))

    assert checker.main(["--update-baseline"]) == 2
    assert baseline_path.read_bytes() == original


def test_error_in_another_control_flow_branch_cannot_replace_old_error(tmp_path):
    checker = _checker()
    path = tmp_path / "backend/app/example.py"
    old_lines = _source(
        tmp_path,
        "def takes_str(x: str) -> None:\n    pass\n\ndef run(flag: bool) -> None:\n"
        "    x: int | str\n    if flag:\n        x = 1\n        takes_str(x)\n"
        "    else:\n        x = 'ok'\n        takes_str(x)\n",
    )
    old_lines["backend/app/example.py"] = [
        'backend/app/example.py:8:19: error: Argument 1 to "takes_str" has incompatible type "int"; expected "str"  [arg-type]'
    ]
    old = checker.build_diagnostics(old_lines, tmp_path)
    path.write_text(
        "def takes_str(x: str) -> None:\n    pass\n\ndef run(flag: bool) -> None:\n"
        "    x: int | str\n    if not flag:\n        x = 1\n        takes_str(x)\n",
        encoding="utf-8",
    )
    current = checker.build_diagnostics(old_lines, tmp_path)
    new, removed = checker.compare_diagnostics(old, current)
    assert len(new) == len(removed) == 1


def test_imported_repository_script_is_not_dropped_from_diagnostics(tmp_path):
    checker = _checker()
    path = tmp_path / "scripts/tool.py"
    path.parent.mkdir()
    path.write_text("value: int = 'bad'\n", encoding="utf-8")
    diagnostics = checker.build_diagnostics(
        {"scripts/tool.py": ["scripts/tool.py:1:14: error: Incompatible assignment  [assignment]"]}, tmp_path
    )
    new, removed = checker.compare_diagnostics([], diagnostics)
    assert len(new) == 1 and removed == []


def test_columnless_ambiguous_statement_diagnostic_fails_closed(tmp_path):
    checker = _checker()
    lines = _source(tmp_path, "def run():\n    a: int = 'bad'; b: int = 1\n")
    lines = {path: [line.replace(":2:12:", ":2:") for line in items] for path, items in lines.items()}
    with pytest.raises(checker.EvidenceError):
        checker.build_diagnostics(lines, tmp_path)


def test_unused_ignore_without_column_requires_a_unique_statement(tmp_path):
    checker = _checker()
    _source(tmp_path, "def run():\n    value = 1  # type: ignore\n")
    lines = {
        "backend/app/example.py": ['backend/app/example.py:2: error: Unused "type: ignore" comment  [unused-ignore]']
    }
    assert len(checker.build_diagnostics(lines, tmp_path)) == 1
    _source(tmp_path, "def run():\n    a = 1; b = 1  # type: ignore\n")
    with pytest.raises(checker.EvidenceError, match="multiple statements"):
        checker.build_diagnostics(lines, tmp_path)


@pytest.mark.parametrize("live_editable", [False, True])
def test_replay_environment_requires_the_historical_editable_source(tmp_path, monkeypatch, live_editable):
    checker = _checker()
    historical = tmp_path / "historical"
    expected = historical / "backend"
    source = tmp_path / "live/backend" if live_editable else expected
    payload = {
        "python": "3.11.9",
        "mypy": "1.20.1",
        "executable": "fixture-python",
        "editable": {"url": source.as_uri(), "dir_info": {"editable": True}},
        "sys_path": [str(source)],
        "backend_paths": [str(source)],
    }
    monkeypatch.setattr(
        checker.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        ),
    )
    if live_editable:
        with pytest.raises(checker.EvidenceError, match="isolated historical editable source"):
            checker.replay_environment(historical, "fixture-python")
    else:
        assert checker.replay_environment(historical, "fixture-python")["editable_source"] == str(expected)


def test_historical_editable_cannot_hide_a_mixed_live_search_path(tmp_path, monkeypatch):
    checker = _checker()
    historical = tmp_path / "historical"
    expected = historical / "backend"
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    payload = {
        "python": "3.11.9",
        "mypy": "1.20.1",
        "executable": "fixture-python",
        "editable": {"url": expected.as_uri(), "dir_info": {"editable": True}},
        "sys_path": [str(expected), str(tmp_path)],
        "backend_paths": [str(expected)],
    }
    monkeypatch.setattr(
        checker.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        ),
    )
    with pytest.raises(checker.EvidenceError, match="isolated historical editable source"):
        checker.replay_environment(historical, "fixture-python")
