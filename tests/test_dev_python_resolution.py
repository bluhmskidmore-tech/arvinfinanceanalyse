from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell")
pytestmark = [pytest.mark.governance_meta, pytest.mark.skipif(os.name != "nt", reason="Windows entry resolver")]


@pytest.fixture
def resolver_root(tmp_path: Path) -> Path:
    assert sys.version_info[:2] == (3, 11), "Use the project Python 3.11 environment"
    if POWERSHELL is None:
        pytest.skip("Windows PowerShell unavailable")
    root = tmp_path / "resolver root"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/dev-python.ps1", scripts / "dev-python.ps1")
    return root


def _venv(root: Path, name: str) -> Path:
    directory = root / name
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(directory)], check=True,
                   capture_output=True, timeout=20)
    return directory / "Scripts/python.exe"


def _resolve(root: Path, *, modules: tuple[str, ...] = (), **overrides: str) -> subprocess.CompletedProcess[str]:
    environment = {key: value for key, value in os.environ.items() if key not in {"MOSS_PYTHON", "VIRTUAL_ENV"}}
    environment.update(overrides)
    module_array = "@(" + ",".join("'" + name + "'" for name in modules) + ")"
    command = "$ErrorActionPreference='Stop'; . './scripts/dev-python.ps1'; $selected=Resolve-DevPython -RequiredModules "
    command += module_array + "; Write-Output ('SELECTED=' + $selected)"
    return subprocess.run([POWERSHELL, "-NoProfile", "-Command", command], cwd=root, env=environment,
                          capture_output=True, text=True, encoding="utf-8", timeout=20, check=False)


def test_default_prefers_compatible_backend_environment(resolver_root: Path) -> None:
    backend = _venv(resolver_root, "backend/.venv")
    _venv(resolver_root, ".venv")
    result = _resolve(resolver_root)
    assert result.returncode == 0, result.stderr
    assert f"SELECTED={backend}" in result.stdout
    assert f"Runtime Python: {backend} (3.11." in result.stdout


@pytest.mark.parametrize("backend_state", ["missing", "wrong_version", "missing_module"])
def test_default_falls_back_only_to_compatible_root_environment(resolver_root: Path, backend_state: str) -> None:
    root_python = _venv(resolver_root, ".venv")
    modules = ()
    if backend_state != "missing":
        _venv(resolver_root, "backend/.venv")
        backend_packages = resolver_root / "backend/.venv/Lib/site-packages"
        if backend_state == "wrong_version":
            (backend_packages / "sitecustomize.py").write_text("import sys\nsys.version_info=(3,14,0,'final',0)\n", encoding="utf-8")
        else:
            modules = ("resolver_probe",)
            (resolver_root / ".venv/Lib/site-packages/resolver_probe.py").write_text("\n", encoding="utf-8")
    result = _resolve(resolver_root, modules=modules)
    assert result.returncode == 0, result.stderr
    assert f"SELECTED={root_python}" in result.stdout


def test_moss_python_precedes_explicit_virtual_environment(resolver_root: Path) -> None:
    result = _resolve(resolver_root, MOSS_PYTHON=sys.executable, VIRTUAL_ENV=str(resolver_root / "absent"))
    assert result.returncode == 0, result.stderr
    assert f"SELECTED={sys.executable}" in result.stdout


def test_explicit_virtual_environment_is_used(resolver_root: Path) -> None:
    python = _venv(resolver_root, "explicit")
    result = _resolve(resolver_root, VIRTUAL_ENV=str(python.parent.parent))
    assert result.returncode == 0, result.stderr
    assert f"SELECTED={python}" in result.stdout


@pytest.mark.parametrize("selection", ["MOSS_PYTHON", "VIRTUAL_ENV"])
def test_invalid_explicit_selection_never_falls_back(resolver_root: Path, selection: str) -> None:
    _venv(resolver_root, "backend/.venv")
    result = _resolve(resolver_root, **{selection: str(resolver_root / "missing")})
    assert result.returncode != 0
    assert "Explicit Python selection is unusable" in result.stderr
    assert "SELECTED=" not in result.stdout


def test_explicit_missing_module_never_falls_back(resolver_root: Path) -> None:
    _venv(resolver_root, "backend/.venv")
    result = _resolve(resolver_root, MOSS_PYTHON=sys.executable, modules=("absent_moss_dev_requirement",))
    assert result.returncode != 0
    assert "Explicit Python selection is unusable" in result.stderr
    assert "absent_moss_dev_requirement" in result.stderr


def test_no_project_environment_does_not_select_path_python(resolver_root: Path) -> None:
    result = _resolve(resolver_root)
    assert result.returncode != 0
    assert "No compatible project Python environment" in result.stderr
    assert "SELECTED=" not in result.stdout


@pytest.mark.parametrize("explicit", [False, True])
def test_incompatible_root_interpreter_is_rejected(resolver_root: Path, explicit: bool) -> None:
    python = _venv(resolver_root, ".venv")
    (resolver_root / ".venv/Lib/site-packages/sitecustomize.py").write_text(
        "import sys\nsys.version_info=(3,14,0,'final',0)\n", encoding="utf-8")
    result = _resolve(resolver_root, **({"MOSS_PYTHON": str(python)} if explicit else {}))
    assert result.returncode != 0
    assert "Python 3.11" in result.stderr
    assert "SELECTED=" not in result.stdout


@pytest.mark.parametrize("explicit", [False, True])
def test_balance_timer_generator_uses_selected_python_without_running_task(tmp_path: Path, explicit: bool) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    installer = scripts / "install_balance_movement_freshness_timer.ps1"
    shutil.copy2(ROOT / "scripts/install_balance_movement_freshness_timer.ps1", installer)
    selected = tmp_path / ("explicit runtime/python.exe" if explicit else "backend/.venv/Scripts/python.exe")
    selected.parent.mkdir(parents=True)
    selected.write_bytes(b"synthetic interpreter; never executed")
    legacy = tmp_path / ".venv/Scripts/python.exe"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"legacy interpreter; never executed")
    resolver_called = tmp_path / "resolver-called.txt"
    (scripts / "dev-python.ps1").write_text(
        "function Resolve-DevPython { param([string[]]$RequiredModules)\n"
        "  [IO.File]::WriteAllText($env:MOSS_TEST_RESOLVER_CALLED, ($RequiredModules -join ','))\n"
        "  return $env:MOSS_TEST_SELECTED_PYTHON\n}\n",
        encoding="utf-8",
    )
    harness = tmp_path / "installer-harness.ps1"
    harness.write_text(
        "function schtasks { $global:LASTEXITCODE = 0 }\n"
        "function New-ScheduledTaskSettingsSet { return @{ synthetic = $true } }\n"
        "function Set-ScheduledTask {}\n"
        "& $env:MOSS_TEST_INSTALLER -RepoRoot $env:MOSS_TEST_REPO_ROOT "
        + ("-PythonExe $env:MOSS_TEST_SELECTED_PYTHON\n" if explicit else "\n"),
        encoding="utf-8",
    )
    environment = {key: value for key, value in os.environ.items() if key not in {"MOSS_PYTHON", "VIRTUAL_ENV"}}
    environment.update(
        MOSS_TEST_INSTALLER=str(installer), MOSS_TEST_REPO_ROOT=str(tmp_path),
        MOSS_TEST_SELECTED_PYTHON=str(selected), MOSS_TEST_RESOLVER_CALLED=str(resolver_called),
    )
    result = subprocess.run([POWERSHELL, "-NoProfile", "-File", str(harness)], env=environment,
                            capture_output=True, text=True, encoding="utf-8", timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    wrapper = (tmp_path / "data/logs/balance_movement_freshness_runner.cmd").read_text(encoding="ascii")
    invocation = next(line for line in wrapper.splitlines() if "scripts\\balance_movement_freshness_watch.py" in line)
    assert invocation.startswith(f'"{selected}" scripts\\balance_movement_freshness_watch.py ')
    assert "--run-once --run-kind scheduled --receipt-path" in invocation
    assert str(legacy) not in invocation
    assert resolver_called.exists() is (not explicit)
    if not explicit:
        assert resolver_called.read_text(encoding="utf-8") == "duckdb"


@pytest.mark.parametrize("selection", ["backend/.venv/Scripts/python.exe", "explicit runtime/python.exe"])
def test_queue_launcher_preserves_dev_env_python_without_executing_worker(tmp_path: Path, selection: str) -> None:
    scripts = tmp_path / "scripts"
    scheduling = scripts / "scheduling"
    scheduling.mkdir(parents=True)
    launcher = scheduling / "drain_data_updates.ps1"
    shutil.copy2(ROOT / "scripts/scheduling/drain_data_updates.ps1", launcher)
    (scripts / "dev-env.ps1").write_text("$devEnvPython = $env:MOSS_TEST_SELECTED_PYTHON\n", encoding="utf-8")
    (scripts / "dev-runtime-common.ps1").write_text(
        "function Assert-DevRuntimeAllowed {}\n"
        "function Invoke-DevRuntimeProcess { param([string[]]$Command)\n"
        "  [IO.File]::WriteAllText($env:MOSS_TEST_RUNTIME_CALLS, (ConvertTo-Json -InputObject @($Command) -Compress))\n"
        "  $global:LASTEXITCODE = 0\n}\n",
        encoding="utf-8",
    )
    selected = tmp_path / selection
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_bytes(b"")
    calls = tmp_path / "runtime-calls.json"
    environment = dict(os.environ, MOSS_TEST_SELECTED_PYTHON=str(selected), MOSS_TEST_RUNTIME_CALLS=str(calls))
    result = subprocess.run([POWERSHELL, "-NoProfile", "-File", str(launcher)], env=environment,
                            capture_output=True, text=True, encoding="utf-8", timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(calls.read_text(encoding="utf-8")) == [str(selected), "-m", "backend.app.tasks.data_update_center"]
