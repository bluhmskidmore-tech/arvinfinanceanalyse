from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest


pytestmark = pytest.mark.governance_meta

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


def _environment(**overrides: str) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"MOSS_PYTHON", "VIRTUAL_ENV", "VITE_DATA_SOURCE",
                                  "MOSS_VITE_API_PROXY", "VITE_API_BASE_URL"}}
    return {**environment, "MOSS_PYTHON": sys.executable, **overrides}


@pytest.fixture
def source_root(tmp_path: Path) -> Path:
    if NODE is None:
        pytest.skip("Node is unavailable")
    assert sys.version_info[:2] == (3, 11), "Run source-entry checks with the project's Python 3.11 environment"
    root = tmp_path / "源码 root with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in ("dev-frontend-source.mjs", "dev_runtime_control.py"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    return root


def _run(root: Path, *args: str, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [NODE, str(root / "scripts" / "dev-frontend-source.mjs"), *args],
        cwd=root, env=environment or _environment(), capture_output=True, text=True,
        encoding="utf-8", timeout=20, check=False,
    )


def _vite(root: Path, content: str) -> Path:
    entry = root / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    entry.parent.mkdir(parents=True)
    entry.write_text(content, encoding="utf-8")
    return entry


def _process_options() -> dict:
    if os.name != "nt":
        return {"start_new_session": True}
    import ctypes

    # Git Bash can give pytest an inheritable Ctrl+C ignore attribute. Clear it
    # before starting an owned console so the interrupt reaches its whole tree.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel.SetConsoleCtrlHandler(None, False):
        error = ctypes.get_last_error()
        if error != 6:  # ERROR_INVALID_HANDLE: pytest has no attached console.
            raise ctypes.WinError(error)
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": subprocess.CREATE_NEW_CONSOLE, "startupinfo": startup}


def _interrupt(process: subprocess.Popen) -> None:
    if os.name != "nt":
        process.send_signal(signal.SIGINT)
        return
    # Attach a short-lived helper to this test's hidden console only.
    # Ctrl+C reaches the wrapper, controller and synthetic Vite child.
    interrupt = (
        "import ctypes, sys, time; k=ctypes.WinDLL('kernel32', use_last_error=True); "
        "k.FreeConsole(); "
        "assert k.AttachConsole(int(sys.argv[1])), ctypes.get_last_error(); "
        "assert k.SetConsoleCtrlHandler(None, True), ctypes.get_last_error(); "
        "assert k.GenerateConsoleCtrlEvent(0, 0), ctypes.get_last_error(); "
        "time.sleep(0.3); k.FreeConsole()"
    )
    subprocess.run([sys.executable, "-c", interrupt, str(process.pid)], check=True,
                   capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)


def _pid_is_running(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87
        try:
            exit_code = ctypes.c_ulong()
            if not kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(exit_code)):
                return True
            return exit_code.value == 259
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _close(process: subprocess.Popen, child_pid: int | None = None) -> None:
    if process.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=5, check=False)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate(timeout=5)
    if child_pid is not None and _pid_is_running(child_pid):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(child_pid), "/T", "/F"],
                           capture_output=True, timeout=5, check=False)
        else:
            os.kill(child_pid, signal.SIGKILL)


@pytest.mark.parametrize(
    ("args", "overrides", "port", "source", "proxy"),
    [
        ([], {}, "5890", "real", "http://127.0.0.1:7888"),
        (["--port", "5891"], {"VITE_DATA_SOURCE": "mock", "MOSS_VITE_API_PROXY": "http://127.0.0.1:8765"},
         "5891", "mock", "http://127.0.0.1:8765"),
    ],
)
def test_source_entry_runs_guarded_child_and_preserves_accepted_selection(
    source_root: Path, args: list[str], overrides: dict[str, str], port: str, source: str, proxy: str,
) -> None:
    capture = source_root / "captured.json"
    _vite(source_root, "require('fs').writeFileSync(process.env.TEST_SOURCE_CAPTURE, JSON.stringify({"
          "argv: process.argv.slice(2), cwd: process.cwd(), source: process.env.VITE_DATA_SOURCE,"
          "proxy: process.env.MOSS_VITE_API_PROXY}));\n")
    control = source_root / "tmp-governance" / "runtime-clean" / "control"
    control.mkdir(parents=True)
    selection = control / "frontend.json"
    before = b'{"mode":"accepted","build_root":"do not change"}\n'
    selection.write_bytes(before)

    completed = _run(source_root, *args, environment=_environment(TEST_SOURCE_CAPTURE=str(capture), **overrides))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "argv": ["--host", "127.0.0.1", "--port", port, "--strictPort", "--clearScreen", "false"],
        "cwd": str(source_root / "frontend"), "source": source, "proxy": proxy,
    }
    assert f"Frontend data source: {source}" in completed.stdout
    assert f"Runtime Python: {sys.executable}" in completed.stdout
    assert selection.read_bytes() == before


def test_source_entry_maintenance_blocks_before_frontend_dependencies(source_root: Path) -> None:
    marker = source_root / "tmp-governance" / "runtime-clean" / "control" / "maintenance.json"
    marker.parent.mkdir(parents=True)
    marker.write_text('{"state":"launch_blocked"}', encoding="utf-8")

    completed = _run(source_root)

    assert completed.returncode == 73
    assert "maintenance blocks runtime changes" in completed.stderr
    assert "Frontend dependencies are missing" not in completed.stderr
    assert not (source_root / "frontend").exists()


@pytest.mark.parametrize("port", ["5888", "5889"])
def test_source_entry_refuses_reserved_ports_before_environment_probe(source_root: Path, port: str) -> None:
    completed = _run(source_root, "--port", port, environment=_environment(MOSS_PYTHON="missing-python"))

    assert completed.returncode == 73
    assert "reserved for the accepted frontend or Playwright" in completed.stderr
    assert not (source_root / "tmp-governance").exists()


@pytest.mark.parametrize("args", [["--port", "0"], ["--port", "65536"], ["--port", "5890.5"], ["--host", "0.0.0.0"]])
def test_source_entry_refuses_invalid_or_exposed_server_arguments(source_root: Path, args: list[str]) -> None:
    completed = _run(source_root, *args)

    assert completed.returncode == 73
    assert "Use --port" in completed.stderr
    assert not (source_root / "tmp-governance").exists()


def test_source_entry_refuses_invalid_data_source(source_root: Path) -> None:
    completed = _run(source_root, environment=_environment(VITE_DATA_SOURCE="fallback"))

    assert completed.returncode == 73
    assert "VITE_DATA_SOURCE must be real or mock" in completed.stderr
    assert not (source_root / "tmp-governance").exists()


def test_source_entry_reports_missing_locked_frontend_dependencies(source_root: Path) -> None:
    completed = _run(source_root)

    assert completed.returncode == 73
    assert "Run npm ci from the frontend directory" in completed.stderr


def test_source_entry_rejects_an_explicit_incompatible_python_version(source_root: Path) -> None:
    startup = source_root / "probe startup"
    startup.mkdir()
    (startup / "sitecustomize.py").write_text("import sys\nsys.version_info = (3, 14, 2, 'final', 0)\n", encoding="utf-8")

    completed = _run(source_root, environment=_environment(PYTHONPATH=str(startup)))

    assert completed.returncode == 73
    assert "Python 3.11 is required" in completed.stderr
    assert "3.14.2" in completed.stderr
    assert not (source_root / "tmp-governance").exists()


def test_source_entry_default_uses_existing_backend_environment(source_root: Path) -> None:
    backend_venv = source_root / "backend" / ".venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(backend_venv)],
                   check=True, capture_output=True, timeout=30)
    _vite(source_root, "process.exit(17);\n")
    environment = _environment()
    environment.pop("MOSS_PYTHON")

    completed = _run(source_root, environment=environment)

    assert completed.returncode == 17, completed.stdout + completed.stderr
    assert f"Runtime Python: {backend_venv}" in completed.stdout
    assert "(3.11." in completed.stdout


@pytest.mark.parametrize("explicit", ["MOSS_PYTHON", "VIRTUAL_ENV"])
def test_source_entry_invalid_explicit_environment_never_falls_back(source_root: Path, explicit: str) -> None:
    backend_venv = source_root / "backend" / ".venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(backend_venv)],
                   check=True, capture_output=True, timeout=30)
    environment = _environment()
    environment.pop("MOSS_PYTHON")
    environment[explicit] = str(source_root / "missing explicit environment")

    completed = _run(source_root, environment=environment)

    assert completed.returncode == 73
    assert "Python 3.11 is required" in completed.stderr
    assert not (source_root / "tmp-governance").exists()


@pytest.mark.parametrize("stop_signal", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("controller_code", [0, 1, 73, 130])
def test_source_entry_interrupt_preserves_controller_failures(
    source_root: Path, stop_signal: int, controller_code: int,
) -> None:
    if os.name == "nt" and stop_signal == signal.SIGTERM:
        pytest.skip("POSIX SIGTERM forwarding; Windows uses console Ctrl+C")
    # A synthetic controller can report cleanup failures without leaving a real
    # Vite child behind or changing the shared runtime controller's policy.
    ready = source_root / "controller-ready"
    (source_root / "scripts" / "dev_runtime_control.py").write_text(
        "import os, signal, sys, time\nfrom pathlib import Path\n"
        "if 'check' in sys.argv:\n    raise SystemExit(0)\n"
        "interrupted = False\n"
        "def on_interrupt(*_args):\n    global interrupted\n    interrupted = True\n"
        "signal.signal(signal.SIGINT, on_interrupt)\n"
        "Path(os.environ['TEST_CONTROLLER_READY']).write_text('ready', encoding='utf-8')\n"
        "while not interrupted:\n    time.sleep(0.02)\n"
        "code = int(os.environ['TEST_CONTROLLER_EXIT'])\n"
        "print(f'controller cleanup result: {code}', file=sys.stderr, flush=True)\n"
        "raise SystemExit(code)\n",
        encoding="utf-8",
    )
    _vite(source_root, "")
    process = subprocess.Popen(
        [NODE, str(source_root / "scripts" / "dev-frontend-source.mjs")], cwd=source_root,
        env=_environment(TEST_CONTROLLER_READY=str(ready), TEST_CONTROLLER_EXIT=str(controller_code)),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", **_process_options(),
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists(), "Synthetic controller never started"
        if stop_signal == signal.SIGINT:
            _interrupt(process)
        else:
            process.send_signal(stop_signal)
        stdout, stderr = process.communicate(timeout=10)
        expected = (130 if stop_signal == signal.SIGINT else 143) if controller_code in {0, 130} else controller_code
        assert f"controller cleanup result: {controller_code}" in stderr, stdout + stderr
        assert process.returncode == expected, stdout + stderr
    finally:
        _close(process)


def test_source_entry_exit_status_contract_with_posix_signal_events(source_root: Path) -> None:
    # Evaluate the real entry module with deterministic event ordering. This
    # covers POSIX SIGTERM on Windows and signals/errors a clean controller
    # cannot safely manufacture in the real-process tests above.
    outcomes = [(0, None), (1, None), (17, None), (73, None), (130, None),
                (None, "SIGINT"), (None, "SIGTERM"), (None, "SIGKILL"), (None, None), "error"]
    cases = []
    for stop_signal, expected_codes in [
        (None, [0, 1, 17, 73, 130, 130, 1, 1, 1, 73]),
        ("SIGINT", [130, 1, 17, 73, 130, 130, 1, 1, 1, 73]),
        ("SIGTERM", [143, 1, 17, 73, 143, 143, 1, 1, 1, 73]),
    ]:
        cases.extend({"interrupt": stop_signal, "outcome": outcome, "expected": expected}
                     for outcome, expected in zip(outcomes, expected_codes, strict=True))
    harness = """
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { EventEmitter } from 'node:events';
import { createContext, SourceTextModule, SyntheticModule } from 'node:vm';
const source = readFileSync(process.argv[1], 'utf8');
const results = [];
for (const scenario of JSON.parse(process.env.TEST_SOURCE_EXIT_CASES)) {
  const entryProcess = Object.assign(new EventEmitter(), {
    argv: [process.execPath, process.argv[1]], execPath: process.execPath,
    platform: 'linux', env: {},
  });
  const child = Object.assign(new EventEmitter(), { exitCode: null });
  const forwarded = [];
  const errors = [];
  child.kill = signal => { forwarded.push(signal); return true; };
  const context = createContext({ process: entryProcess, Buffer,
    console: { log() {}, error(message) { errors.push(message); } },
  });
  const dependencies = {
    'node:child_process': {
      spawnSync: () => ({ status: 0, stdout: JSON.stringify({ path: 'synthetic-python', version: [3, 11, 9] }) }),
      spawn: () => {
        queueMicrotask(() => {
          if (scenario.interrupt) entryProcess.emit(scenario.interrupt);
          if (scenario.outcome === 'error') child.emit('error', new Error('synthetic spawn failure'));
          else child.emit('exit', ...scenario.outcome);
        });
        return child;
      },
    },
    'node:fs': { existsSync: () => true },
    'node:path': { default: path },
    'node:url': { fileURLToPath },
  };
  const entry = new SourceTextModule(source, { context,
    initializeImportMeta(meta) { meta.url = pathToFileURL(process.argv[1]).href; },
  });
  await entry.link(specifier => {
    const values = dependencies[specifier];
    return new SyntheticModule(Object.keys(values), function () {
      for (const [name, value] of Object.entries(values)) this.setExport(name, value);
    }, { context });
  });
  await entry.evaluate();
  results.push({ code: entryProcess.exitCode, forwarded, errors,
    listeners: entryProcess.listenerCount('SIGINT') + entryProcess.listenerCount('SIGTERM') });
}
console.log(JSON.stringify(results));
"""
    completed = subprocess.run(
        [NODE, "--experimental-vm-modules", "--input-type=module", "-e", harness,
         str(source_root / "scripts" / "dev-frontend-source.mjs")], cwd=source_root,
        env=_environment(TEST_SOURCE_EXIT_CASES=json.dumps(cases)), capture_output=True,
        text=True, encoding="utf-8", timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    for scenario, result in zip(cases, json.loads(completed.stdout), strict=True):
        assert result["code"] == scenario["expected"], (scenario, result)
        assert result["forwarded"] == (["SIGINT"] if scenario["interrupt"] else []), (scenario, result)
        assert result["listeners"] == 0, (scenario, result)
        assert result["errors"] == (["Source development refused: synthetic spawn failure"]
                                    if scenario["outcome"] == "error" else []), (scenario, result)


@pytest.mark.parametrize("stop_signal", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("stalls", [False, True])
def test_source_entry_interrupt_waits_for_controller_to_remove_child(
    source_root: Path, stop_signal: int, stalls: bool,
) -> None:
    if os.name == "nt" and stop_signal == signal.SIGTERM:
        pytest.skip("POSIX SIGTERM forwarding; Windows uses console Ctrl+C")
    capture = source_root / "child-pid.json"
    shutdown = "process.on('SIGINT', () => {}); process.on('SIGTERM', () => {});" if stalls else ""
    _vite(source_root, shutdown + "require('fs').writeFileSync(process.env.TEST_SOURCE_CAPTURE, JSON.stringify(process.pid));"
          "setInterval(() => {}, 1000);\n")
    process = subprocess.Popen(
        [NODE, str(source_root / "scripts" / "dev-frontend-source.mjs")], cwd=source_root,
        env=_environment(TEST_SOURCE_CAPTURE=str(capture)), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", **_process_options(),
    )
    child_pid = None
    try:
        deadline = time.monotonic() + 10
        while not capture.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert capture.exists(), "Synthetic Vite child never started"
        child_pid = json.loads(capture.read_text(encoding="utf-8"))
        if stop_signal == signal.SIGINT:
            _interrupt(process)
        else:
            process.send_signal(stop_signal)
        output = process.communicate(timeout=10)
        assert process.returncode == (130 if stop_signal == signal.SIGINT else 143), "".join(output)
        assert not _pid_is_running(child_pid), "Synthetic Vite process survived Ctrl+C"
    finally:
        _close(process, child_pid)


@pytest.mark.skipif(os.name != "nt", reason="Windows inherits the console Ctrl+C ignore attribute")
def test_source_entry_interrupt_when_parent_ignores_ctrl_c(tmp_path: Path) -> None:
    # Git Bash may disable Ctrl+C in the pytest parent. Reuse the original
    # interrupt acceptance body inside an owned console with that exact state.
    driver = (
        "import ctypes, sys, pytest; kernel=ctypes.WinDLL('kernel32', use_last_error=True); "
        "assert kernel.SetConsoleCtrlHandler(None, True), ctypes.get_last_error(); "
        "raise SystemExit(pytest.main(["
        "'tests/test_dev_frontend_source_entry.py::test_source_entry_interrupt_waits_for_controller_to_remove_child[False-2]', "
        "'-q', '--basetemp='+sys.argv[1], '-o', 'cache_dir='+sys.argv[1]+'-cache']))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", driver, str(tmp_path / "ignored-parent")], cwd=ROOT,
        env=_environment(), capture_output=True, text=True, encoding="utf-8", timeout=40,
        **_process_options(),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
