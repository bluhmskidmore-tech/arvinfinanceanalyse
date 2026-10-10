from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEV_API = ROOT / "scripts" / "dev-api.ps1"
POWERSHELL = shutil.which("powershell")
SETTINGS_PROBE_EXPRESSION = (
    "import sys; from backend.app.governance.settings import get_settings; s = get_settings(); "
    "(s.environment == 'development' and s.local_only_api) or "
    "sys.exit('Native dev-api local entrance policy is not active'); "
    "print('1' if s.system_read_publication_enabled else '0')"
)


def _require_powershell() -> str:
    if POWERSHELL is None:
        pytest.skip("Windows PowerShell is unavailable")
    return POWERSHELL


def _stage_dev_api_runtime(tmp_path: Path) -> tuple[Path, dict[str, str], Path, Path]:
    owned_root = tmp_path.resolve()
    assert owned_root != ROOT.resolve()
    assert (ROOT / "data").resolve() not in owned_root.parents
    runtime_root = owned_root / "runtime"
    scripts = runtime_root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(DEV_API, scripts / "dev-api.ps1")

    staged_governance = runtime_root / "backend" / "app" / "governance"
    staged_governance.mkdir(parents=True)
    for package_dir in (
        runtime_root / "backend",
        runtime_root / "backend" / "app",
        staged_governance,
    ):
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(
        ROOT / "backend" / "app" / "governance" / "settings.py",
        staged_governance / "settings.py",
    )

    event_log = owned_root / "events.log"
    guard_root = owned_root / "probe-guard"
    guard_root.mkdir()
    guard_log = guard_root / "probe-results.jsonl"
    probe_launcher = owned_root / "settings_probe.py"
    probe_launcher.write_text(
        r"""
import sys
from pathlib import Path

import _pytest_duckdb_guard as guard

owned_root = Path(__import__("os").environ["TEST_OWNED_ROOT"]).resolve()
receipt_root = Path(__import__("os").environ["TEST_GUARD_ROOT"]).resolve()
result_path = Path(__import__("os").environ["TEST_GUARD_LOG"]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.register_pytest_duckdb_temp_root(receipt_root)
guard.set_pytest_duckdb_guard_phase("dev-api-settings-probe")

import json
import os
import socket

http_calls = []

def forbid_http(*args, **kwargs):
    http_calls.append({"args": [str(value) for value in args], "kwargs": kwargs})
    raise AssertionError("HTTP is forbidden in the dev-api settings probe")

socket.create_connection = forbid_http
import requests
requests.Session.request = forbid_http

attempts_before = guard.get_pytest_duckdb_guard_attempts()
exit_code = int(os.environ.get("TEST_SETTINGS_PROBE_EXIT", "0"))
mode = os.environ.get("TEST_SETTINGS_PROBE_MODE", "fixture")
expected_expression = (
    "import sys; from backend.app.governance.settings import get_settings; s = get_settings(); "
    "(s.environment == 'development' and s.local_only_api) or "
    "sys.exit('Native dev-api local entrance policy is not active'); "
    "print('1' if s.system_read_publication_enabled else '0')"
)
probe_details = {
    "argv": sys.argv[1:],
    "mode": mode,
    "settings_source": None,
    "system_read_publication_enabled": None,
    "local_only_api": None,
    "financial_publication_enabled": None,
    "env_files": None,
}
try:
    if mode == "execute":
        if sys.argv[1:] != ["-c", expected_expression]:
            raise AssertionError(f"unexpected settings probe arguments: {sys.argv[1:]!r}")
        exec(compile(sys.argv[2], "<dev-api-settings-probe>", "exec"), {})
        settings_module = sys.modules["backend.app.governance.settings"]
        resolved_settings = settings_module.get_settings()
        probe_details.update(
            {
                "settings_source": str(Path(settings_module.__file__).resolve()),
                "system_read_publication_enabled": bool(
                    resolved_settings.system_read_publication_enabled
                ),
                "financial_publication_enabled": bool(
                    resolved_settings.financial_publication_enabled
                ),
                "local_only_api": bool(resolved_settings.local_only_api),
                "env_files": [str(Path(path).resolve()) for path in settings_module._ENV_FILES],
            }
        )
    else:
        sys.stdout.write(os.environ.get("TEST_SETTINGS_PROBE_OUTPUT", ""))
finally:
    attempts_after = guard.get_pytest_duckdb_guard_attempts()
    receipt_path = guard.finalize_pytest_duckdb_guard()
    with result_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "attempts_before": attempts_before,
                    "attempts_after": attempts_after,
                    "http_calls": http_calls,
                    "receipt_path": str(receipt_path),
                    **probe_details,
                },
                sort_keys=True,
                default=str,
            )
            + "\n"
        )
raise SystemExit(exit_code)
""".lstrip(),
        encoding="utf-8",
    )
    probe_command = owned_root / "settings-probe.cmd"
    probe_command.write_text(
        f'@echo off\r\n"{sys.executable}" "{probe_launcher}" %*\r\nexit /b %errorlevel%\r\n',
        encoding="utf-8",
    )

    (scripts / "dev-runtime-common.ps1").write_text(
        r"""
function Add-TestEvent {
  param([string]$Event)
  [IO.File]::AppendAllText($env:TEST_EVENT_LOG, $Event + [Environment]::NewLine)
}
function Assert-DevRuntimeAllowed { }
function Invoke-DevRuntimeAction {
  param([scriptblock]$Action)
  Add-TestEvent "action"
  & $Action
}
function Invoke-DevRuntimeProcess {
  param([string[]]$Command)
  Add-TestEvent ("process:" + [string]$env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS)
}
function netstat { return @() }
""".lstrip(),
        encoding="utf-8",
    )
    (scripts / "dev-python.ps1").write_text(
        "function Resolve-DevPython { param([object]$RequiredModules) return $env:TEST_RUNTIME_PYTHON }\n",
        encoding="utf-8",
    )
    (scripts / "dev-env.ps1").write_text(
        r"""
$root = Split-Path -Parent $PSScriptRoot
. "$root\scripts\dev-python.ps1"
function Assert-DevBootstrapStorageReady {
  param([string]$ProbeLabel)
  Add-TestEvent "assert"
}
""".lstrip(),
        encoding="utf-8",
    )
    (scripts / "dev-postgres-up.ps1").write_text(
        'Add-TestEvent ("up:" + [string]$env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS)\n'
        '& $env:ComSpec /c "exit 0"\n',
        encoding="utf-8",
    )

    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS",
            "MOSS_SYSTEM_READ_PUBLICATION_ENABLED",
            "MOSS_LOCAL_ONLY_API",
        }
    }
    env.update(
        {
            "PYTHONPATH": os.pathsep.join((str(runtime_root), str(ROOT))),
            "TEST_EVENT_LOG": str(event_log),
            "TEST_GUARD_LOG": str(guard_log),
            "TEST_GUARD_ROOT": str(guard_root),
            "TEST_OWNED_ROOT": str(owned_root),
            "TEST_RUNTIME_PYTHON": str(probe_command),
            "TEST_SETTINGS_PROBE_EXIT": "0",
        }
    )
    return scripts / "dev-api.ps1", env, event_log, guard_log


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _read_json_lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in _read_lines(path) if line.strip()]


def _run_dev_api(
    script: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _require_powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *args,
        ],
        cwd=script.parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


@pytest.mark.parametrize(
    ("probe_output", "financial_enabled", "args", "expected_events"),
    [
        ("1", "0", (), ["process:1"]),
        ("0", "0", (), ["action", "up:", "assert", "process:"]),
        ("0", "1", (), ["action", "up:", "assert", "process:"]),
        (
            "0",
            "0",
            ("-SkipStartupStorageMigrations",),
            ["action", "up:1", "assert", "process:1"],
        ),
    ],
)
def test_dev_api_selects_immutable_or_legacy_startup_from_settings(
    tmp_path: Path,
    probe_output: str,
    financial_enabled: str,
    args: tuple[str, ...],
    expected_events: list[str],
) -> None:
    script, env, event_log, guard_log = _stage_dev_api_runtime(tmp_path)
    env["TEST_SETTINGS_PROBE_OUTPUT"] = probe_output
    env["MOSS_FINANCIAL_PUBLICATION_ENABLED"] = financial_enabled

    completed = _run_dev_api(script, env, *args)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _read_lines(event_log) == expected_events
    probe_receipts = _read_json_lines(guard_log)
    assert len(probe_receipts) == 1
    assert probe_receipts[0]["attempts_before"] == []
    assert probe_receipts[0]["attempts_after"] == []
    assert probe_receipts[0]["http_calls"] == []
    assert Path(probe_receipts[0]["receipt_path"]).parent == tmp_path / "probe-guard"


@pytest.mark.parametrize(
    ("probe_output", "probe_exit"),
    [("", "7"), ("", "0"), ("true", "0"), ("1\n0", "0")],
)
def test_dev_api_settings_probe_fails_before_any_startup_branch(
    tmp_path: Path,
    probe_output: str,
    probe_exit: str,
) -> None:
    script, env, event_log, guard_log = _stage_dev_api_runtime(tmp_path)
    env["TEST_SETTINGS_PROBE_OUTPUT"] = probe_output
    env["TEST_SETTINGS_PROBE_EXIT"] = probe_exit

    completed = _run_dev_api(script, env)

    assert completed.returncode != 0
    assert _read_lines(event_log) == []
    probe_receipts = _read_json_lines(guard_log)
    assert len(probe_receipts) == 1
    assert probe_receipts[0]["attempts_before"] == []
    assert probe_receipts[0]["attempts_after"] == []
    assert probe_receipts[0]["http_calls"] == []


@pytest.mark.parametrize("policy", ["0", "false", "off", "no", "invalid", "2"])
def test_native_dev_api_rejects_disabled_or_invalid_local_policy_before_startup(tmp_path, policy):
    script, env, event_log, guard_log = _stage_dev_api_runtime(tmp_path)
    env["MOSS_LOCAL_ONLY_API"] = policy
    env["TEST_SETTINGS_PROBE_OUTPUT"] = "1"
    completed = _run_dev_api(script, env)
    assert completed.returncode != 0
    assert "MOSS_LOCAL_ONLY_API" in completed.stderr
    assert _read_lines(event_log) == []
    assert _read_json_lines(guard_log) == []


@pytest.mark.parametrize("policy", [None, "true", " ON "])
def test_native_dev_api_enables_and_verifies_actual_local_policy(tmp_path, policy):
    script, env, event_log, guard_log = _stage_dev_api_runtime(tmp_path)
    if policy is not None:
        env["MOSS_LOCAL_ONLY_API"] = policy
    env["MOSS_SYSTEM_READ_PUBLICATION_ENABLED"] = "1"
    env["MOSS_FINANCIAL_PUBLICATION_ROOT"] = str(script.parents[1] / "publication")
    env["TEST_SETTINGS_PROBE_MODE"] = "execute"
    completed = _run_dev_api(script, env)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _read_lines(event_log) == ["process:1"]
    receipt = _read_json_lines(guard_log)[0]
    assert receipt["local_only_api"] is True
    assert receipt["attempts_after"] == []
    assert receipt["http_calls"] == []


def test_native_dev_api_rejects_policy_not_applied_by_settings_even_with_optimization(tmp_path):
    script, env, event_log, guard_log = _stage_dev_api_runtime(tmp_path)
    staged_settings = script.parents[1] / "backend" / "app" / "governance" / "settings.py"
    staged_settings.write_text(
        "from types import SimpleNamespace\n"
        "def get_settings():\n"
        "    return SimpleNamespace(environment='development', local_only_api=False)\n",
        encoding="utf-8",
    )
    env["MOSS_LOCAL_ONLY_API"] = "1"
    env["PYTHONOPTIMIZE"] = "1"
    env["TEST_SETTINGS_PROBE_MODE"] = "execute"
    completed = _run_dev_api(script, env)
    assert completed.returncode != 0
    assert "local entrance policy is not active" in completed.stderr
    assert _read_lines(event_log) == []
    receipt = _read_json_lines(guard_log)[0]
    assert receipt["attempts_after"] == []
    assert receipt["http_calls"] == []


def test_dev_api_forced_skip_does_not_leak_into_later_disabled_startup(
    tmp_path: Path,
) -> None:
    script, env, event_log, guard_log = _stage_dev_api_runtime(tmp_path)
    command = (
        "$env:TEST_SETTINGS_PROBE_OUTPUT = '1'; "
        f"& '{script}'; if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}; "
        "$env:TEST_SETTINGS_PROBE_OUTPUT = '0'; "
        f"& '{script}'; exit $LASTEXITCODE"
    )

    completed = subprocess.run(
        [
            _require_powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        cwd=script.parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=25,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _read_lines(event_log) == [
        "process:1",
        "action",
        "up:",
        "assert",
        "process:",
    ]
    probe_receipts = _read_json_lines(guard_log)
    assert len(probe_receipts) == 2
    assert all(receipt["attempts_after"] == [] for receipt in probe_receipts)
    assert all(receipt["http_calls"] == [] for receipt in probe_receipts)


@pytest.mark.parametrize(
    ("system_read_enabled", "financial_enabled", "expected_events"),
    [
        (False, True, ["action", "up:", "assert", "process:"]),
        (True, False, ["process:1"]),
    ],
)
def test_dev_api_executes_exact_settings_probe_against_owned_env_files(
    tmp_path: Path,
    system_read_enabled: bool,
    financial_enabled: bool,
    expected_events: list[str],
) -> None:
    script, staged_env, event_log, guard_log = _stage_dev_api_runtime(tmp_path)
    runtime_root = script.parents[1]
    publication_root = runtime_root / "publication"
    (runtime_root / "config").mkdir()
    (runtime_root / "config" / ".env").write_text(
        "\n".join(
            (
                f"MOSS_FINANCIAL_PUBLICATION_ENABLED={str(financial_enabled).lower()}",
                f"MOSS_FINANCIAL_PUBLICATION_ROOT={publication_root}",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (runtime_root / ".env").write_text(
        f"MOSS_SYSTEM_READ_PUBLICATION_ENABLED={str(system_read_enabled).lower()}\n",
        encoding="utf-8",
    )
    env = {
        key: value for key, value in staged_env.items() if not key.startswith("MOSS_")
    }
    env["TEST_SETTINGS_PROBE_MODE"] = "execute"

    completed = _run_dev_api(script, env)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _read_lines(event_log) == expected_events
    probe_receipts = _read_json_lines(guard_log)
    assert len(probe_receipts) == 1
    receipt = probe_receipts[0]
    assert receipt["argv"] == ["-c", SETTINGS_PROBE_EXPRESSION]
    assert receipt["mode"] == "execute"
    assert receipt["settings_source"] == str(
        runtime_root / "backend" / "app" / "governance" / "settings.py"
    )
    assert receipt["env_files"] == [
        str(runtime_root / "config" / ".env"),
        str(runtime_root / ".env"),
    ]
    assert receipt["system_read_publication_enabled"] is system_read_enabled
    assert receipt["financial_publication_enabled"] is financial_enabled
    assert receipt["local_only_api"] is True
    assert receipt["attempts_before"] == []
    assert receipt["attempts_after"] == []
    assert receipt["http_calls"] == []


def _run_actual_lifespan(
    settings: object, tmp_path: Path
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    guard_root = tmp_path / "lifespan-guard"
    guard_root.mkdir()
    result_path = guard_root / "result.json"
    child_code = r"""
import sys
from pathlib import Path

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
receipt_root = Path(sys.argv[2]).resolve()
result_path = Path(sys.argv[3]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.register_pytest_duckdb_temp_root(receipt_root)
guard.set_pytest_duckdb_guard_phase("dev-api-immutable-lifespan")

import asyncio
import json
import socket

http_calls = []

def forbid_http(*args, **kwargs):
    http_calls.append({"args": [str(value) for value in args], "kwargs": kwargs})
    raise AssertionError("Network access is forbidden in the immutable lifespan child")

socket.create_connection = forbid_http
import requests
requests.Session.request = forbid_http

attempts_before = guard.get_pytest_duckdb_guard_attempts()
status = "completed"
error_class = None
error_message = None
pretrade_availability = None
storage_operation_events = []
warmup_events = []
try:
    from backend.app.governance.settings import get_settings
    import backend.app.duckdb_schema_bootstrap as duckdb_schema_bootstrap
    import backend.app.main as main_module
    import backend.app.postgres_migrations as postgres_migrations
    from backend.app.repositories.system_read_publication_repo import (
        current_system_read_context,
        system_read_scope,
    )
    from types import SimpleNamespace

    def forbid_postgres_migration(*args, **kwargs):
        storage_operation_events.append("postgres-subprocess")
        raise AssertionError("Postgres migration subprocess must remain skipped")

    def forbid_duckdb_registry(*args, **kwargs):
        storage_operation_events.append("duckdb-registry")
        raise AssertionError("DuckDB migration registry must remain skipped")

    postgres_migrations.subprocess = SimpleNamespace(run=forbid_postgres_migration)
    duckdb_schema_bootstrap.DuckDBSchemaRegistry = forbid_duckdb_registry

    def record_hermes_warmup(settings):
        context = current_system_read_context()
        warmup_events.append(
            {
                "name": "hermes",
                "generation": None if context is None else context.generation,
            }
        )

    def record_home_snapshot_warmup(settings):
        context = current_system_read_context()
        if context is None:
            raise AssertionError("home snapshot warmup was outside system-read scope")
        warmup_events.append(
            {"name": "home-snapshot", "generation": context.generation}
        )

    def record_background_warmup(settings):
        context = current_system_read_context()
        warmup_events.append(
            {
                "name": "background",
                "generation": None if context is None else context.generation,
            }
        )

    main_module.warm_hermes_bridge_if_configured = record_hermes_warmup
    main_module.warm_home_snapshot_cache_if_configured = record_home_snapshot_warmup
    main_module.warm_home_background_caches_if_configured = record_background_warmup
    main_module.stop_managed_hermes_bridge = lambda: None

    settings = get_settings()

    async def exercise_lifespan():
        global pretrade_availability
        async with main_module.lifespan(main_module.app):
            with system_read_scope(settings):
                context = current_system_read_context()
                if context is None:
                    raise AssertionError("system read context was not pinned")
                pretrade_availability = dict(context.pretrade_availability)

    asyncio.run(exercise_lifespan())
except BaseException as exc:
    status = "failed"
    error_class = type(exc).__name__
    error_message = str(exc)
finally:
    attempts_after = guard.get_pytest_duckdb_guard_attempts()
    receipt_path = guard.finalize_pytest_duckdb_guard()
    result_path.write_text(
        json.dumps(
            {
                "status": status,
                "error_class": error_class,
                "error_message": error_message,
                "pretrade_availability": pretrade_availability,
                "attempts_before": attempts_before,
                "attempts_after": attempts_after,
                "http_calls": http_calls,
                "receipt_path": str(receipt_path),
                "storage_operation_events": storage_operation_events,
                "warmup_events": warmup_events,
            },
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )
if status != "completed":
    raise SystemExit(17)
"""
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("MOSS_")
    }
    env.update(
        {
            "PYTHONPATH": str(ROOT),
            "MOSS_ENVIRONMENT": "development",
            "MOSS_SYSTEM_READ_PUBLICATION_ENABLED": "1",
            "MOSS_FINANCIAL_PUBLICATION_ENABLED": "0",
            "MOSS_FINANCIAL_PUBLICATION_ROOT": str(settings.financial_publication_root),
            "MOSS_DUCKDB_PATH": str(settings.duckdb_path),
            "MOSS_GOVERNANCE_PATH": str(settings.governance_path),
            "MOSS_POSTGRES_DSN": "postgresql://moss:moss@127.0.0.1:55432/moss",
            "MOSS_GOVERNANCE_SQL_DSN": "postgresql://moss:moss@127.0.0.1:55432/moss",
            "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS": "1",
            "MOSS_HOME_SNAPSHOT_PREWARM_ENABLED": "0",
            "MOSS_HOME_INCOME_TREND_PREWARM_ENABLED": "0",
            "MOSS_MARKET_HOME_PREWARM_ENABLED": "0",
            "MOSS_AGENT_ENABLED": "0",
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            child_code,
            str(tmp_path),
            str(guard_root),
            str(result_path),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    return completed, json.loads(result_path.read_text(encoding="utf-8"))


def _assert_lifespan_did_not_touch_active_storage(
    payload: dict[str, object], settings: object
) -> None:
    active_path = Path(settings.duckdb_path).resolve()
    attempts = payload["attempts_after"]
    assert isinstance(attempts, list)
    assert payload["attempts_before"] == []
    assert all(
        Path(attempt["canonical_path"]).resolve() != active_path for attempt in attempts
    )
    assert all(attempt["decision"] == "allow" for attempt in attempts)
    assert payload["http_calls"] == []
    assert payload["storage_operation_events"] == []


def test_actual_lifespan_accepts_complete_publication_without_active_storage_access(
    tmp_path: Path,
) -> None:
    from tests import test_system_online_read_boundary as seals

    publication_root = tmp_path / "publication"
    publication_root.mkdir()
    settings = seals._settings(publication_root)
    _, generation = seals._publish_fixture(settings)

    completed, payload = _run_actual_lifespan(settings, tmp_path)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert payload["status"] == "completed"
    assert payload["pretrade_availability"] == {
        "schema": "pretrade_qualification/v1",
        "status": "unavailable",
        "reason": "legacy_system_read_bundle_has_no_pretrade_qualification",
    }
    assert payload["warmup_events"] == [
        {"name": "hermes", "generation": None},
        {"name": "home-snapshot", "generation": generation},
        {"name": "background", "generation": None},
    ]
    _assert_lifespan_did_not_touch_active_storage(payload, settings)
    assert Path(payload["receipt_path"]).parent == tmp_path / "lifespan-guard"


@pytest.mark.parametrize(
    "failure_mode", ["missing", "bad", "incompatible", "invalidated"]
)
def test_actual_lifespan_rejects_unusable_publication_without_active_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    from tests import test_system_online_read_boundary as seals

    publication_root = tmp_path / "publication"
    publication_root.mkdir()
    settings = seals._settings(publication_root)
    generation = None
    if failure_mode != "missing":
        if failure_mode == "incompatible":
            monkeypatch.setattr(
                seals, "SYSTEM_READ_API_VERSION", "system-read/incompatible"
            )
        _, generation = seals._publish_fixture(settings)
        system_root = seals.system_read_publication_root(settings)
        if failure_mode == "bad":
            (system_root / "current.json").write_bytes(b"{")
        elif failure_mode == "invalidated":
            assert generation is not None
            invalidation = seals.generation_invalidation_path(system_root, generation)
            invalidation.parent.mkdir(parents=True, exist_ok=True)
            invalidation.write_bytes(
                seals.canonical_json_bytes({"reason": "test revocation"})
            )

    completed, payload = _run_actual_lifespan(settings, tmp_path)

    assert completed.returncode == 17
    assert payload["status"] == "failed"
    assert payload["error_class"] in {
        "FinancialPublicationIncompatible",
        "FinancialPublicationInvalid",
        "FinancialPublicationUnavailable",
    }
    assert payload["pretrade_availability"] is None
    assert payload["warmup_events"] == []
    _assert_lifespan_did_not_touch_active_storage(payload, settings)
