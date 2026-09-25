import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cleanup-dev-artifacts.ps1"


def _timestamp(days: int = 30) -> float:
    return time.time() - days * 24 * 60 * 60


def _write_old(path: Path, content: str = "synthetic") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    old = _timestamp()
    os.utime(path, (old, old))
    return path


def _age_directory(path: Path) -> None:
    old = _timestamp()
    os.utime(path, (old, old))


def _run_dry_run(repo_root: Path) -> tuple[str, set[str]]:
    repo_root = repo_root.resolve()
    assert repo_root != ROOT.resolve()
    shell = next((name for name in ("powershell", "pwsh") if shutil.which(name)), None)
    if shell is None:
        raise RuntimeError("PowerShell (powershell or pwsh) is required for cleanup dry-run tests")
    command = [
        shell,
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(SCRIPT),
        "-RepoRoot",
        str(repo_root),
    ]
    completed = subprocess.run(
        command,
        cwd=repo_root,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=30,
    )
    output = completed.stdout.replace("\\", "/")
    candidates = {
        line.split("\t", 2)[1]
        for line in output.splitlines()
        if line.startswith("DRY-RUN\t")
    }
    return output, candidates


def test_dry_run_preserves_unverifiable_runs_and_evidence_but_selects_old_cache(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    cache = _write_old(repo_root / ".pytest_cache" / "v" / "cache" / "nodeids")
    _age_directory(cache.parents[2])
    _age_directory(cache.parents[1])
    _age_directory(cache.parents[0])

    active_run = _write_old(
        repo_root / ".codex-tmp" / f"pytest-{os.getpid()}" / "artifact.txt"
    )
    unknown_run = _write_old(
        repo_root / ".codex-tmp" / "pytest-user-created" / "artifact.txt"
    )
    legacy_run = _write_old(
        repo_root / ".pytest-basetemp" / "run-001" / "result.duckdb"
    )
    historical_output = _write_old(
        repo_root / "test_output" / "accounting_asset_movement" / "run-001" / "result.duckdb"
    )
    protected_evidence = _write_old(
        repo_root / ".mypy_cache" / "manual-audit-notes.md"
    )
    protected_manifest = _write_old(
        repo_root / ".ruff_cache" / "formal-result-manifest.json"
    )
    _age_directory(repo_root / ".pytest-basetemp" / "run-001")
    _age_directory(repo_root / ".pytest-basetemp")
    _age_directory(repo_root / "test_output" / "accounting_asset_movement" / "run-001")
    _age_directory(repo_root / "test_output" / "accounting_asset_movement")
    _age_directory(repo_root / "test_output")
    _age_directory(repo_root / ".mypy_cache")
    _age_directory(repo_root / ".ruff_cache")

    output, candidates = _run_dry_run(repo_root)

    assert "DRY-RUN cleanup-dev-artifacts" in output
    assert ".pytest_cache" in candidates
    assert not any("pytest-" in path or ".pytest-basetemp" in path for path in candidates)
    assert not any(path.startswith("test_output/") for path in candidates)
    assert ".mypy_cache" not in candidates
    assert ".ruff_cache" not in candidates
    assert all(path.exists() for path in (
        active_run,
        unknown_run,
        legacy_run,
        historical_output,
        protected_evidence,
        protected_manifest,
    ))


def test_dry_run_rejects_old_cache_with_recent_descendant_or_protected_extension(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    recent_child = repo_root / ".pytest_cache" / "v" / "cache" / "lastfailed"
    recent_child.parent.mkdir(parents=True)
    recent_child.write_text("synthetic recent child", encoding="utf-8")
    _age_directory(repo_root / ".pytest_cache" / "v" / "cache")
    _age_directory(repo_root / ".pytest_cache" / "v")
    _age_directory(repo_root / ".pytest_cache")

    protected_cache = _write_old(repo_root / ".ruff_cache" / "research.duckdb")
    _age_directory(repo_root / ".ruff_cache")

    output, candidates = _run_dry_run(repo_root)

    assert ".pytest_cache" not in candidates
    assert ".ruff_cache" not in candidates
    assert recent_child.exists()
    assert protected_cache.exists()


def test_dry_run_rejects_cache_tree_containing_symlink(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cache_file = _write_old(repo_root / ".pytest_cache" / "v" / "cache" / "nodeids")
    _age_directory(cache_file.parents[2])
    _age_directory(cache_file.parents[1])
    _age_directory(cache_file.parents[0])
    target = tmp_path / "external-synthetic-target"
    target.mkdir()
    _write_old(target / "kept.txt")
    link = repo_root / ".pytest_cache" / "evidence-link"
    link.symlink_to(target, target_is_directory=True)
    _age_directory(repo_root / ".pytest_cache")

    output, candidates = _run_dry_run(repo_root)

    assert ".pytest_cache" not in candidates
    assert link.is_symlink()
    assert (target / "kept.txt").exists()


def test_dry_run_prunes_bytecode_cache_scan_at_protected_roots(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    protected_roots = (
        ".codex-tmp/pytest-12345",
        "test_output/accounting_asset_movement/run-001",
        ".pytest-basetemp/run-001",
        ".pytest-tmp-old",
        "frontend/test-results/run-001",
        ".git/objects",
        "data/snapshots",
        "node_modules/package",
    )
    pyc_files = []
    for relative_root in protected_roots:
        pycache = repo_root / relative_root / "__pycache__"
        pycache.mkdir(parents=True)
        pyc_files.append(_write_old(pycache / "synthetic.pyc"))
        _age_directory(pycache)
        _age_directory(pycache.parent)
        _age_directory(pycache.parent.parent)

    output, candidates = _run_dry_run(repo_root)

    assert "DRY-RUN cleanup-dev-artifacts" in output
    assert not any("__pycache__" in path for path in candidates)
    assert all(path.exists() for path in pyc_files)
