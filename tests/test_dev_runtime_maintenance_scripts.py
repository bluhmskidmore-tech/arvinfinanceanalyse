from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType

import pytest


pytestmark = pytest.mark.governance_meta

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
POWERSHELL = shutil.which("powershell")


def _require_powershell() -> str:
    if POWERSHELL is None:
        pytest.skip("Windows PowerShell is unavailable")
    return POWERSHELL


def _load_runtime_control() -> ModuleType:
    name = "test_dev_runtime_maintenance_control"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / "dev_runtime_control.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _stage_scripts(root: Path, *names: str) -> None:
    target = root / "scripts"
    target.mkdir(parents=True)
    for name in names:
        shutil.copy2(SCRIPTS / name, target / name)


def _write_marker(root: Path) -> Path:
    marker = root / "tmp-governance" / "runtime-clean" / "control" / "maintenance.json"
    marker.parent.mkdir(parents=True)
    marker.write_text('{"state":"launch_blocked"}', encoding="utf-8")
    return marker


def _run_ps_file(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_require_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
        text=True,
        capture_output=True,
        timeout=12,
        check=False,
    )


@pytest.mark.parametrize(
    "entry", ["dev-api.ps1", "dev-worker.ps1", "dev-frontend.ps1", "dev-frontend-source.ps1", "dev-up.ps1"]
)
def test_entry_scripts_reject_marker_before_loading_real_dependencies(tmp_path: Path, entry: str) -> None:
    root = tmp_path / "维护 入口 root with space"
    _stage_scripts(root, "dev-runtime-common.ps1", entry)
    _write_marker(root)

    completed = _run_ps_file(root / "scripts" / entry)

    assert completed.returncode != 0
    assert "Maintenance blocks runtime changes" in (completed.stdout + completed.stderr)
    assert not (root / "tmp-governance" / "pgdev").exists()
    assert not (root / "frontend").exists()


@pytest.mark.parametrize(
    ("args", "overrides", "expected_port", "expected_source", "expected_proxy"),
    [
        ([], {}, "5890", "real", "http://127.0.0.1:7888"),
        (
            ["-Port", "5891"],
            {"VITE_DATA_SOURCE": "mock", "MOSS_VITE_API_PROXY": "http://127.0.0.1:8765"},
            "5891", "mock", "http://127.0.0.1:8765",
        ),
    ],
)
def test_source_frontend_uses_guarded_dev_command_without_changing_accepted_selection(
    tmp_path: Path, args: list[str], overrides: dict[str, str], expected_port: str,
    expected_source: str, expected_proxy: str,
) -> None:
    if shutil.which("node") is None:
        pytest.skip("Node is unavailable")
    root = tmp_path / "source frontend root with space"
    _stage_scripts(root, "dev-runtime-common.ps1", "dev_runtime_control.py", "dev-frontend-source.ps1",
                   "dev-frontend-source.mjs")
    vite = root / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    vite.parent.mkdir(parents=True)
    captured = root / "captured-command.json"
    vite.write_text(
        "require('fs').writeFileSync(process.env.TEST_SOURCE_CAPTURE, JSON.stringify({"
        "argv: process.argv.slice(2), cwd: process.cwd(), "
        "source: process.env.VITE_DATA_SOURCE, proxy: process.env.MOSS_VITE_API_PROXY}));\n",
        encoding="utf-8",
    )
    selection = root / "tmp-governance" / "runtime-clean" / "control" / "frontend.json"
    selection.parent.mkdir(parents=True)
    previous_selection = b'{"mode":"accepted","data_source":"real","build_root":"accepted build"}\n'
    selection.write_bytes(previous_selection)
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"VITE_DATA_SOURCE", "MOSS_VITE_API_PROXY", "VITE_API_BASE_URL"}}

    completed = subprocess.run(
        [_require_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(root / "scripts" / "dev-frontend-source.ps1"), *args],
        text=True, capture_output=True, timeout=15, check=False,
        env={**environment, **overrides, "MOSS_PYTHON": sys.executable,
             "TEST_SOURCE_CAPTURE": str(captured)},
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    observed = json.loads(captured.read_text(encoding="utf-8"))
    assert observed == {
        "argv": ["--host", "127.0.0.1", "--port", expected_port, "--strictPort", "--clearScreen", "false"],
        "cwd": str(root / "frontend"), "source": expected_source, "proxy": expected_proxy,
    }
    assert "source development (Vite hot reload)" in completed.stdout
    assert f"http://127.0.0.1:{expected_port}/" in completed.stdout
    assert f"Frontend data source: {expected_source}" in completed.stdout
    assert f"API proxy: {expected_proxy}" in completed.stdout
    assert selection.read_bytes() == previous_selection


@pytest.mark.parametrize("port", ["5888", "5889"])
def test_source_frontend_refuses_reserved_ports_before_loading_dependencies(tmp_path: Path, port: str) -> None:
    root = tmp_path / "source reserved port"
    _stage_scripts(root, "dev-runtime-common.ps1", "dev-frontend-source.ps1", "dev-frontend-source.mjs")

    completed = _run_ps_file(root / "scripts" / "dev-frontend-source.ps1", "-Port", port)

    assert completed.returncode != 0
    assert "reserved for the accepted frontend or Playwright" in completed.stdout + completed.stderr
    assert not (root / "frontend").exists()


def test_keepalive_once_with_marker_does_not_attempt_service_recovery(tmp_path: Path) -> None:
    root = tmp_path / "维护 keeper root with space"
    _stage_scripts(root, "dev-runtime-common.ps1", "dev-keepalive.ps1")
    _write_marker(root)

    completed = _run_ps_file(root / "scripts" / "dev-keepalive.ps1", "-Once")

    assert completed.returncode == 0
    output = completed.stdout + completed.stderr
    log = root / "tmp-governance" / "runtime-clean" / "logs" / "dev-keepalive.log"
    assert "Maintenance blocks runtime changes" in output
    assert log.exists()
    assert "Maintenance blocks runtime changes" in log.read_text(encoding="utf-8")
    assert not (root / "tmp-governance" / "pgdev").exists()
    assert not (root / "frontend").exists()
    assert not (root / "data").exists()


def test_invoke_action_refuses_marker_without_running_action(tmp_path: Path) -> None:
    root = tmp_path / "维护 action root with space"
    _stage_scripts(root, "dev-runtime-common.ps1")
    _write_marker(root)
    command = (
        "$root = $env:TEST_RUNTIME_ROOT; "
        ". (Join-Path $root 'scripts/dev-runtime-common.ps1'); "
        "$script:ran = $false; "
        "try { Invoke-DevRuntimeAction { $script:ran = $true } } catch { }; "
        "if ($script:ran) { exit 41 }; exit 0"
    )

    completed = subprocess.run(
        [_require_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        text=True,
        capture_output=True,
        timeout=12,
        check=False,
        env={**os.environ, "TEST_RUNTIME_ROOT": str(root)},
    )

    assert completed.returncode == 0


def test_dev_env_cluster_print_is_blocked_when_common_marker_is_loaded(tmp_path: Path) -> None:
    root = tmp_path / "维护 env root with space"
    _stage_scripts(root, "dev-runtime-common.ps1", "dev-env.ps1")
    (root / "scripts" / "dev-python.ps1").write_text(
        "function Resolve-DevPython { param([object]$RequiredModules) return $env:TEST_RUNTIME_PYTHON }\n",
        encoding="utf-8",
    )
    flag = root / "cluster-was-run.flag"
    (root / "scripts" / "dev_postgres_cluster.py").write_text(
        "from pathlib import Path\nimport os\nPath(os.environ['TEST_CLUSTER_FLAG']).write_text('ran')\n",
        encoding="utf-8",
    )
    _write_marker(root)
    command = (
        "$root = $env:TEST_RUNTIME_ROOT; "
        ". (Join-Path $root 'scripts/dev-runtime-common.ps1'); "
        ". (Join-Path $root 'scripts/dev-env.ps1')"
    )
    env = {
        **os.environ,
        "TEST_RUNTIME_ROOT": str(root),
        "TEST_RUNTIME_PYTHON": sys.executable,
        "TEST_CLUSTER_FLAG": str(flag),
    }

    completed = subprocess.run(
        [_require_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        text=True,
        capture_output=True,
        timeout=12,
        check=False,
        env=env,
    )

    assert completed.returncode != 0
    assert "Maintenance blocks runtime changes" in (completed.stdout + completed.stderr)
    assert not flag.exists()


def _holder(lock_path: Path) -> subprocess.Popen[str]:
    command = (
        "$lockPath = $env:TEST_RUNTIME_LOCK; "
        "$dir = [IO.Path]::GetDirectoryName($lockPath); [IO.Directory]::CreateDirectory($dir) | Out-Null; "
        "$stream = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None); "
        "[Console]::Out.WriteLine('READY'); [Console]::Out.Flush(); Start-Sleep -Seconds 20; $stream.Dispose()"
    )
    process = subprocess.Popen(
        [_require_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "TEST_RUNTIME_LOCK": str(lock_path)},
    )
    assert process.stdout is not None
    ready = threading.Event()
    line: dict[str, str] = {}

    def read_ready() -> None:
        line["value"] = process.stdout.readline().strip()
        ready.set()

    reader = threading.Thread(target=read_ready, daemon=True)
    reader.start()
    if not ready.wait(timeout=3):
        _close(process)
        pytest.fail("PowerShell lock holder did not become ready")
    assert line["value"] == "READY"
    return process


def _close(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def test_powershell_fileshare_none_blocks_then_releases_python_maintenance_enter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "维护 lock ps to py"
    root.mkdir()
    module = _load_runtime_control()
    lock_path = module.control_dir(root) / "operation.lock"
    holder = _holder(lock_path)
    try:
        original_lock = module.operation_lock

        def short_operation_lock(lock_root: Path, timeout: float = 30):
            return original_lock(lock_root, timeout=0.1)

        monkeypatch.setattr(module, "operation_lock", short_operation_lock)
        started = threading.Event()
        done = threading.Event()
        outcome: dict[str, object] = {}

        def enter_maintenance() -> None:
            started.set()
            try:
                outcome["state"] = module.enter_maintenance(root, "blocked by PowerShell lock")
            except Exception as exc:  # pragma: no cover - asserted below
                outcome["error"] = exc
            finally:
                done.set()

        thread = threading.Thread(target=enter_maintenance, daemon=True)
        thread.start()
        assert started.wait(timeout=1)
        assert done.wait(timeout=2)
        assert isinstance(outcome.get("error"), module.RuntimeControlError)
        assert "lock unavailable" in str(outcome["error"])
        assert not (module.control_dir(root) / "maintenance.json").exists()
    finally:
        _close(holder)

    state = module.enter_maintenance(root, "entered after PowerShell lock release")
    assert state["drained"] is False
    assert (module.control_dir(root) / "maintenance.json").exists()
    sys.modules.pop(module.__name__, None)


def test_python_operation_lock_blocks_powershell_fileshare_none(tmp_path: Path) -> None:
    root = tmp_path / "维护 lock py to ps"
    root.mkdir()
    module = _load_runtime_control()
    lock_path = module.control_dir(root) / "operation.lock"
    command = (
        "$lockPath = $env:TEST_RUNTIME_LOCK; "
        "try { $stream = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None); "
        "$stream.Dispose(); exit 0 } catch [IO.IOException] { exit 42 }"
    )
    try:
        with module.operation_lock(root):
            blocked = subprocess.run(
                [_require_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                text=True,
                capture_output=True,
                timeout=8,
                check=False,
                env={**os.environ, "TEST_RUNTIME_LOCK": str(lock_path)},
            )
        released = subprocess.run(
            [_require_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            text=True,
            capture_output=True,
            timeout=8,
            check=False,
            env={**os.environ, "TEST_RUNTIME_LOCK": str(lock_path)},
        )
    finally:
        sys.modules.pop(module.__name__, None)

    assert blocked.returncode == 42
    assert released.returncode == 0
