from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell")
GIT = shutil.which("git")
pytestmark = [pytest.mark.governance_meta, pytest.mark.skipif(os.name != "nt", reason="Windows entry resolver")]


@pytest.fixture
def resolver_root(tmp_path: Path) -> Path:
    assert sys.version_info[:2] == (3, 11), "Use the project Python 3.11 environment"
    assert POWERSHELL is not None
    assert GIT is not None
    root = tmp_path / "resolver root"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in ("codex-python-helper.ps1", "dev-python.ps1"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    _git(root, "init", "-q")
    return root


def _git(root: Path, *args: str) -> None:
    subprocess.run([GIT, "-C", str(root), *args], check=True, capture_output=True, timeout=20)


def _venv(root: Path, name: str, *, wrong_version: bool = False) -> Path:
    directory = root / name
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(directory)], check=True,
                   capture_output=True, timeout=20)
    if wrong_version:
        (directory / "Lib/site-packages/sitecustomize.py").write_text(
            "import sys\nsys.version_info=(3,14,0,'final',0)\n", encoding="utf-8")
    return directory / "Scripts/python.exe"


def _resolve(root: Path, *, modules: tuple[str, ...] = (), fallback_roots: tuple[Path, ...] | None = None,
             **overrides: str) -> subprocess.CompletedProcess[str]:
    environment = {key: value for key, value in os.environ.items() if key not in {"MOSS_PYTHON", "VIRTUAL_ENV"}}
    environment.update(overrides)
    module_array = "@(" + ",".join("'" + name + "'" for name in modules) + ")"
    script, function = ("codex-python-helper.ps1", "Resolve-CodexPython")
    options = ""
    if fallback_roots is not None:
        script, function = ("dev-python.ps1", "Resolve-DevPython")
        options = " -FallbackProjectRoots @(" + ",".join("'" + str(p).replace("'", "''") + "'" for p in fallback_roots) + ")"
    command = f"$ErrorActionPreference='Stop'; . './scripts/{script}'; $selected={function} -RequiredModules "
    command += module_array + options + "; Write-Output ('SELECTED=' + $selected)"
    return subprocess.run([POWERSHELL, "-NoProfile", "-Command", command], cwd=root, env=environment,
                          capture_output=True, text=True, encoding="utf-8", timeout=20, check=False)


def _assert_selected(result: subprocess.CompletedProcess[str], python: Path) -> None:
    assert result.returncode == 0, result.stderr
    assert f"SELECTED={python}" in result.stdout
    assert f"Runtime Python: {python} (3.11." in result.stdout


def _assert_rejected(result: subprocess.CompletedProcess[str], *, explicit: bool = False) -> None:
    assert result.returncode != 0
    assert "Explicit Python selection is unusable" in result.stderr if explicit else "No compatible project Python environment" in result.stderr
    assert "SELECTED=" not in result.stdout


def _worktree(root: Path) -> Path:
    _git(root, "add", "scripts")
    _git(root, "-c", "user.name=Resolver Fixture", "-c", "user.email=resolver@example.invalid", "commit", "-qm", "Fixture scripts")
    worktree = root.parent / "worktree root"
    _git(root, "worktree", "add", "--detach", str(worktree))
    return worktree


def test_codex_prefers_compatible_backend_over_root(resolver_root: Path) -> None:
    backend = _venv(resolver_root, "backend/.venv")
    _venv(resolver_root, ".venv")
    _assert_selected(_resolve(resolver_root), backend)


def test_codex_falls_back_to_root_when_backend_lacks_required_module(resolver_root: Path) -> None:
    _venv(resolver_root, "backend/.venv")
    python = _venv(resolver_root, ".venv")
    (resolver_root / ".venv/Lib/site-packages/resolver_probe.py").write_text("\n", encoding="utf-8")
    _assert_selected(_resolve(resolver_root, modules=("resolver_probe",)), python)


@pytest.mark.parametrize("selection", ["MOSS_PYTHON", "VIRTUAL_ENV"])
def test_codex_invalid_explicit_selection_never_falls_back(resolver_root: Path, selection: str) -> None:
    _venv(resolver_root, ".venv")
    _assert_rejected(_resolve(resolver_root, **{selection: str(resolver_root / "missing")}), explicit=True)


@pytest.mark.parametrize("explicit", [False, True])
def test_codex_rejects_python_314_even_with_required_modules(resolver_root: Path, explicit: bool) -> None:
    python = _venv(resolver_root, ".venv", wrong_version=True)
    _assert_rejected(_resolve(resolver_root, **({"MOSS_PYTHON": str(python)} if explicit else {})), explicit=explicit)


def test_codex_explicit_missing_module_never_falls_back(resolver_root: Path) -> None:
    _venv(resolver_root, ".venv")
    (resolver_root / ".venv/Lib/site-packages/resolver_probe.py").write_text("\n", encoding="utf-8")
    result = _resolve(resolver_root, MOSS_PYTHON=sys.executable, modules=("resolver_probe",))
    _assert_rejected(result, explicit=True)
    assert "resolver_probe" in result.stderr


def test_codex_moss_python_precedes_virtual_environment(resolver_root: Path) -> None:
    _venv(resolver_root, ".venv")
    _assert_selected(_resolve(resolver_root, MOSS_PYTHON=sys.executable,
                              VIRTUAL_ENV=str(resolver_root / "missing")), Path(sys.executable))


def test_codex_uses_explicit_virtual_environment(resolver_root: Path) -> None:
    _venv(resolver_root, ".venv")
    python = _venv(resolver_root, "explicit")
    _assert_selected(_resolve(resolver_root, VIRTUAL_ENV=str(python.parent.parent)), python)


def test_codex_does_not_select_path_python_without_project_environment(resolver_root: Path) -> None:
    path = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    _assert_rejected(_resolve(resolver_root, PATH=path))


@pytest.mark.parametrize("environment", ["backend/.venv", ".venv"])
def test_codex_worktree_reuses_only_compatible_common_project_environment(resolver_root: Path, environment: str) -> None:
    worktree = _worktree(resolver_root)
    python = _venv(resolver_root, environment)
    _assert_selected(_resolve(worktree), python)


def test_codex_worktree_rejects_incompatible_common_environment(resolver_root: Path) -> None:
    worktree = _worktree(resolver_root)
    _venv(resolver_root, ".venv", wrong_version=True)
    _assert_rejected(_resolve(worktree))


def test_codex_worktree_never_overrides_invalid_explicit_selection(resolver_root: Path) -> None:
    worktree = _worktree(resolver_root)
    _venv(resolver_root, ".venv")
    _assert_rejected(_resolve(worktree, MOSS_PYTHON=str(worktree / "missing")), explicit=True)


def test_shared_fallback_roots_preserve_default_local_priority(resolver_root: Path) -> None:
    backend = _venv(resolver_root, "backend/.venv")
    common = resolver_root.parent / "fallback project"
    _venv(common, "backend/.venv")
    _assert_selected(_resolve(resolver_root, fallback_roots=()), backend)
    _assert_selected(_resolve(resolver_root, fallback_roots=(common,)), backend)
