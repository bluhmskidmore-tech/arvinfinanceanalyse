"""Opt-in real application acceptance on synthetic storage, without a worker."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import signal
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.request import urlopen

import pytest

from tests.test_dev_frontend_source_entry import NODE, ROOT, _close, _environment, _interrupt, _pid_is_running, _process_options

pytestmark = pytest.mark.governance_meta


def _port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _get(base: str, path: str) -> bytes:
    with urlopen(base + path, timeout=5) as response:
        assert response.status == 200
        return response.read()


def _wait(base: str, path: str, process: subprocess.Popen, log: Path) -> None:
    deadline = time.monotonic() + 90
    while process.poll() is None and time.monotonic() < deadline:
        try:
            _get(base, path)
            return
        except OSError:
            time.sleep(0.1)
    pytest.fail(f"Service unavailable at {base}{path}: {log.read_text(encoding='utf-8', errors='replace')}")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _api_pid(log: Path) -> int:
    # Windows may add conhost.exe or a venv launcher below the controller;
    # Uvicorn discloses the actual serving process in its normal startup log.
    match = re.search(r"Started server process \[(\d+)\]", log.read_text(encoding="utf-8"))
    assert match, "Real Uvicorn did not disclose its serving process"
    return int(match.group(1))


def _vite_pid(wrapper_pid: int) -> int:
    # npm may insert cmd.exe/sh before the Node entry, so inspect its real descendants.
    pending = [wrapper_pid]
    while pending:
        parent = pending.pop()
        if os.name == "nt":
            query = f"@(Get-CimInstance Win32_Process -Filter 'ParentProcessId = {parent}' | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress"
            result = subprocess.run(["powershell", "-NoProfile", "-Command", query], capture_output=True,
                                    text=True, timeout=10, check=True)
            records = json.loads(result.stdout) if result.stdout.strip() else []
            if isinstance(records, dict):
                records = [records]
        else:
            result = subprocess.run(
                ["ps", "-A", "-ww", "-o", "pid=", "-o", "ppid=", "-o", "command="],
                capture_output=True, text=True, timeout=10, check=True,
            )
            rows = (line.split(None, 2) for line in result.stdout.splitlines() if line.strip())
            records = [{"ProcessId": int(pid), "CommandLine": command}
                       for pid, ppid, command in rows if int(ppid) == parent]
        for record in records:
            if "vite/bin/vite.js" in (record["CommandLine"] or "").replace("\\", "/"):
                return record["ProcessId"]
            pending.append(record["ProcessId"])
    pytest.fail("npm source process did not own a Vite child")


def _isolated_posix_query(monkeypatch, output: str, error: Exception | None = None) -> list[list[str]]:
    queries = []

    def query(argv, **_kwargs):
        queries.append(argv)
        if error is not None:
            raise error
        return SimpleNamespace(stdout=output)

    def no_proc(path):
        pytest.fail(f"Process discovery must not depend on Linux procfs: {path}")

    monkeypatch.setitem(_vite_pid.__globals__, "os", SimpleNamespace(name="posix"))
    monkeypatch.setitem(_vite_pid.__globals__, "subprocess", SimpleNamespace(run=query))
    monkeypatch.setitem(_vite_pid.__globals__, "Path", no_proc)
    return queries


def test_vite_pid_posix_without_proc_finds_only_owned_nested_child(monkeypatch) -> None:
    queries = _isolated_posix_query(monkeypatch, "\n".join([
        '900 800 node /other/frontend/node_modules/vite/bin/vite.js',
        '100 1 npm run dev:source',
        '101 100 /bin/sh -c node ../scripts/dev-frontend-source.mjs',
        '102 101 python /workspace with spaces/源码/scripts/dev_runtime_control.py run',
        '103 102 node /workspace with spaces/源码/frontend/node_modules/vite/bin/vite.js --host 127.0.0.1',
    ]))

    assert _vite_pid(100) == 103
    assert queries
    assert queries[0] == ["ps", "-A", "-ww", "-o", "pid=", "-o", "ppid=", "-o", "command="]


def test_vite_pid_posix_without_proc_rejects_unrelated_vite(monkeypatch) -> None:
    _isolated_posix_query(monkeypatch, "\n".join([
        '900 800 node /other/frontend/node_modules/vite/bin/vite.js',
        '101 100 /bin/sh -c npm run another-script',
    ]))

    with pytest.raises(pytest.fail.Exception, match="npm source process did not own a Vite child"):
        _vite_pid(100)


def test_vite_pid_posix_query_failure_is_not_accepted(monkeypatch) -> None:
    _isolated_posix_query(monkeypatch, "", error=OSError("process inspection unavailable"))

    with pytest.raises(OSError, match="process inspection unavailable"):
        _vite_pid(100)


def _stage_frontend(root: Path, dependencies: Path) -> dict[str, str]:
    frontend = root / "frontend"
    frontend.mkdir(exist_ok=True)
    assert not list(frontend.glob(".env*")), "Isolated frontend must not contain dotenv configuration"
    hashes = {}
    trees = ("src", "public", "scripts")
    files = ("index.html", "vite.config.ts", "package.json",
             "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json")
    # Byte-identical current source/config; no .env, business data, dist or cache.
    for name in (*trees, *files):
        original = ROOT / "frontend" / name
        target = frontend / name
        if target.exists():
            continue
        if original.is_dir():
            shutil.copytree(original, target)
        elif original.is_file():
            shutil.copy2(original, target)
    source_tree = hashlib.sha256()
    for name in trees:
        originals = sorted((ROOT / "frontend" / name).rglob("*"), key=lambda item: item.relative_to(ROOT / "frontend").as_posix())
        original_files = {item.relative_to(ROOT / "frontend" / name).as_posix()
                          for item in originals if item.is_file()}
        staged_files = {item.relative_to(frontend / name).as_posix()
                        for item in (frontend / name).rglob("*") if item.is_file()}
        assert staged_files == original_files, f"Isolated {name} file set differs from current source"
        for original in originals:
            if original.is_file():
                relative = original.relative_to(ROOT / "frontend")
                digest = _digest(original)
                assert _digest(frontend / relative) == digest
                source_tree.update(relative.as_posix().encode() + digest.encode())
    hashes["source_tree_sha256"] = source_tree.hexdigest()
    for name in files:
        hashes[name] = _digest(frontend / name)
        assert hashes[name] == _digest(ROOT / "frontend" / name)
    for config in (Path("config/dashboard_macro_release_calendar_2026.json"),
                   Path("config/macro_decision_observation_keys.json")):
        target_config = root / config
        if not target_config.exists():
            target_config.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / config, target_config)
        hashes[config.as_posix()] = _digest(target_config)
        assert hashes[config.as_posix()] == _digest(ROOT / config)
    link = frontend / "node_modules"
    if link.exists():
        assert link.resolve() == dependencies
        return hashes
    try:
        link.symlink_to(dependencies, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(dependencies)],
                       check=True, capture_output=True, timeout=5)
    return hashes


def test_stage_frontend_prepares_required_static_config_without_overwriting_local_config(tmp_path, monkeypatch) -> None:
    source, staged = tmp_path / "source", tmp_path / "staged"
    for tree in ("src", "public", "scripts"):
        (source / "frontend" / tree).mkdir(parents=True)
    (source / "frontend/src/mocks").mkdir()
    (source / "frontend/src/mocks/probe.js").write_text(
        "import keys from '../../../config/macro_decision_observation_keys.json';\n", encoding="utf-8",
    )
    for name in ("index.html", "vite.config.ts", "package.json", "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json"):
        (source / "frontend" / name).write_text("synthetic source\n", encoding="utf-8")
    calendar = Path("config/dashboard_macro_release_calendar_2026.json")
    keys = Path("config/macro_decision_observation_keys.json")
    (source / "config").mkdir()
    (source / calendar).write_text('{"calendar": []}\n', encoding="utf-8")
    (source / keys).write_text('{"excluded": ["synthetic"]}\n', encoding="utf-8")
    (staged / "config").mkdir(parents=True)
    shutil.copy2(source / calendar, staged / calendar)
    extra = staged / "config/local-only.json"
    extra.write_text('{"owner": "synthetic fixture"}\n', encoding="utf-8")
    preserved = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in (staged / calendar, extra)}
    dependencies = staged / "frontend/node_modules"
    dependencies.mkdir(parents=True)
    monkeypatch.setitem(_stage_frontend.__globals__, "ROOT", source)

    hashes = _stage_frontend(staged, dependencies.resolve())

    assert (staged / keys).read_bytes() == (source / keys).read_bytes()
    assert hashes[keys.as_posix()] == _digest(source / keys)
    for path, identity in preserved.items():
        assert (path.read_bytes(), path.stat().st_mtime_ns) == identity
    changed = b'{"excluded": ["local synthetic override"]}\n'
    (staged / keys).write_bytes(changed)
    with pytest.raises(AssertionError):
        _stage_frontend(staged, dependencies.resolve())
    assert (staged / keys).read_bytes() == changed


@pytest.mark.skipif(os.environ.get("MOSS_TEST_FULL_APP") != "1", reason="Opt in to real application services")
def test_real_application_source_proxy_reads_isolated_positions_and_stops(tmp_path: Path) -> None:
    from tests.test_positions_api_contract import _seed_positions_db

    assert sys.version_info[:2] == (3, 11)
    assert NODE is not None
    npm_candidates = [Path(NODE).parent / "node_modules/npm/bin/npm-cli.js",
                      Path(NODE).parent.parent / "lib/node_modules/npm/bin/npm-cli.js"]
    npm_cli = next((candidate for candidate in npm_candidates if candidate.is_file()), None)
    assert npm_cli is not None, "The selected Node installation must provide npm"
    dependencies = Path(os.environ.get("MOSS_TEST_VITE_DEPENDENCIES", ROOT / "frontend/node_modules")).resolve()
    assert (dependencies / "@playwright/test").is_dir(), "Prepare the complete locked frontend dependencies"
    workspace = os.environ.get("MOSS_TEST_FULL_APP_WORKSPACE")
    root = Path(workspace).resolve() if workspace else tmp_path / "real-application"
    owner_marker = root / "synthetic-application-owner.json"
    ownership = {"purpose": "synthetic source application", "repo_root": str(ROOT.resolve()), "workspace": str(root.resolve())}
    if workspace:
        assert root.is_relative_to((ROOT / ".codex-tmp").resolve()), "Only owned task workspaces may be reused"
        assert json.loads(owner_marker.read_text(encoding="utf-8")) == ownership
        from _pytest_duckdb_guard import register_pytest_duckdb_temp_root
        register_pytest_duckdb_temp_root(root)
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    owner_marker.write_text(json.dumps(ownership, indent=2), encoding="utf-8")
    for name in ("dev-frontend-source.mjs", "dev_runtime_control.py"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    source_hashes = _stage_frontend(root, dependencies)
    storage = root / "sample-storage"
    storage.mkdir(exist_ok=True)
    db = storage / "positions.duckdb"
    _seed_positions_db(db)
    before = _digest(db)
    dsn = f"sqlite:///{(storage / 'scopes.sqlite').as_posix()}"
    from backend.app.repositories.user_scope_repo import UserScopeRepository
    scopes = UserScopeRepository(dsn)
    for resource in ("positions", "balance_analysis"):
        scopes.grant_scope(user_id="source-application-sample", role="viewer", resource=resource, action="read")
    scopes.engine.dispose()
    paths = {name: str(storage / name) for name in ("governance", "input", "archive", "publication", "balance-publication")}
    for path in paths.values():
        Path(path).mkdir(exist_ok=True)
    api_port, frontend_port = _port(), _port()
    while frontend_port == api_port:
        frontend_port = _port()
    api_base = f"http://127.0.0.1:{api_port}"
    base = f"http://127.0.0.1:{frontend_port}"
    sample_settings = dict(
        MOSS_ENVIRONMENT="development", MOSS_DUCKDB_PATH=str(db), MOSS_POSTGRES_DSN=dsn,
        MOSS_GOVERNANCE_SQL_DSN=dsn, MOSS_JOB_STATE_DSN=dsn, MOSS_GOVERNANCE_BACKEND="jsonl",
        MOSS_SOURCE_PREVIEW_GOVERNANCE_BACKEND="jsonl", MOSS_GOVERNANCE_PATH=paths["governance"],
        MOSS_DATA_INPUT_ROOT=paths["input"], MOSS_PRODUCT_CATEGORY_SOURCE_DIR=paths["input"],
        MOSS_LOCAL_ARCHIVE_PATH=paths["archive"], MOSS_OBJECT_STORE_MODE="local", MOSS_REDIS_DSN="",
        MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS="1", MOSS_SKIP_POSTGRES_MIGRATIONS="1",
        MOSS_SKIP_STORAGE_READINESS_CHECKS="1", MOSS_HOME_SNAPSHOT_PREWARM_ENABLED="0",
        MOSS_HOME_INCOME_TREND_PREWARM_ENABLED="0", MOSS_MARKET_HOME_PREWARM_ENABLED="0",
        MOSS_AGENT_ENABLED="0", MOSS_OTEL_ENABLED="0", MOSS_SYSTEM_READ_PUBLICATION_ENABLED="0",
        MOSS_FINANCIAL_PUBLICATION_ENABLED="0", MOSS_BALANCE_ANALYSIS_PUBLICATION_ENABLED="0",
        MOSS_FINANCIAL_PUBLICATION_ROOT=paths["publication"], MOSS_BALANCE_ANALYSIS_PUBLICATION_ROOT=paths["balance-publication"],
        MOSS_USER_ID="source-application-sample", MOSS_USER_ROLE="viewer", MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST="0",
        VITE_DATA_SOURCE="real", VITE_API_BASE_URL="", MOSS_VITE_API_PROXY=api_base, PYTHONPATH=str(ROOT),
    )
    environment = {key: value for key, value in _environment().items()
                   if not key.startswith("MOSS_") and key not in {"RAW_FILES_DIR", "NODE_OPTIONS", "NODE_PATH"}}
    environment.update(sample_settings, MOSS_PYTHON=sys.executable)
    # This process-local bootstrap disables repository dotenv loading before the
    # real app is imported. Application code and its lifespan remain unchanged.
    (root / "isolated_app.py").write_text(
        "from backend.app.governance.settings import Settings, get_settings\n"
        "Settings.model_config = {**Settings.model_config, 'env_file': None}\n"
        "get_settings.cache_clear()\n"
        "from backend.app.main import app\n", encoding="utf-8",
    )
    command = base64.b64encode(json.dumps({
        "argv": [sys.executable, "-X", "utf8", "-m", "uvicorn", "isolated_app:app", "--host", "127.0.0.1",
                 "--port", str(api_port), "--app-dir", str(root)], "cwd": str(root),
    }).encode()).decode()
    api_log, frontend_log = root / "api.log", root / "frontend.log"
    api = frontend = browser = None
    api_pid = vite_pid = None
    try:
        with api_log.open("w", encoding="utf-8") as api_output, frontend_log.open("w", encoding="utf-8") as frontend_output:
            api = subprocess.Popen([sys.executable, str(scripts / "dev_runtime_control.py"), "--repo-root", str(root),
                                    "run", "--command-base64", command], cwd=root, env=environment,
                                   stdout=api_output, stderr=subprocess.STDOUT, **_process_options())
            _wait(api_base, "/health", api, api_log)
            frontend = subprocess.Popen([NODE, str(npm_cli), "run", "dev:source", "--", "--port", str(frontend_port)],
                                        cwd=root / "frontend", env=environment, stdout=frontend_output,
                                        stderr=subprocess.STDOUT, **_process_options())
            _wait(base, "/positions?report_date=2026-01-10", frontend, frontend_log)
            api_pid = _api_pid(api_log)
            vite_pid = _vite_pid(frontend.pid)
            assert b"/@vite/client" in _get(base, "/positions?report_date=2026-01-10")
            bonds_path = "/api/positions/bonds?report_date=2026-01-10&page=1&page_size=20"
            direct = json.loads(_get(api_base, bonds_path))
            proxied = json.loads(_get(base, bonds_path))
            assert direct["result"] == proxied["result"]
            assert proxied["result"]["total"] == 2
            assert proxied["result_meta"]["source_version"] == "sv-pos-test"
            assert proxied["result_meta"]["evidence_rows"] == 2
            assert proxied["result_meta"]["formal_use_allowed"] is False
            items = {item["bond_code"]: item for item in proxied["result"]["items"]}
            assert set(items) == {"B001", "B003"}
            assert items["B001"]["market_value"] == "100.00000000"
            assert items["B003"]["market_value"] == "50.00000000"
            browser_script = root / "frontend" / "application-acceptance.mjs"
            browser_script.write_text(
                "import fs from 'node:fs'; import assert from 'node:assert/strict'; import {chromium,expect} from '@playwright/test';\n"
                "const browser=await chromium.launch({headless:true}); const page=await browser.newPage();\n"
                "const requests=[]; const errors=[]; page.on('pageerror',e=>errors.push(e.message));\n"
                "page.on('request',r=>requests.push({method:r.method(),url:r.url()}));\n"
                "try { const responsePromise=page.waitForResponse(r=>r.url().includes('/api/positions/bonds?')&&r.status()===200);\n"
                "const tickerResponsePromise=page.waitForResponse(r=>new URL(r.url()).pathname==='/ui/macro/choice-series/latest');\n"
                "await page.goto(process.env.TEST_APP_URL+'/positions?report_date=2026-01-10');\n"
                "const payload=await (await responsePromise).json(); assert.equal(payload.result_meta.source_version,'sv-pos-test');\n"
                "assert.equal(payload.result.total,2); await page.getByText('B001',{exact:true}).waitFor({state:'visible',timeout:60000});\n"
                "await page.getByText('B003',{exact:true}).waitFor({state:'visible'});\n"
                "assert.equal(await page.getByText('本地演示数据',{exact:true}).count(),0);\n"
                "const tickerResponse=await tickerResponsePromise; const tickerPayload=await tickerResponse.json();\n"
                "const ticker=page.getByTestId('workbench-market-ticker');\n"
                "const tickerState=tickerResponse.ok()?'empty':'unavailable';\n"
                "const tickerMessage=tickerResponse.ok()?'暂无可用行情':'行情加载失败';\n"
                "await expect(ticker).toHaveAttribute('data-market-ticker-state',tickerState,{timeout:60000});\n"
                "await expect(ticker.getByRole('status')).toHaveText(tickerMessage);\n"
                "assert.equal(await ticker.locator('.workbench-market-ticker-item').count(),0);\n"
                "assert.equal(await ticker.getByTestId('workbench-market-ticker-fallback-flag').count(),0);\n"
                "assert(!((await ticker.innerText()).includes('演示')));\n"
                "const tickerEvidence={status:tickerResponse.status(),series:tickerPayload?.result?.series??null,"
                "state:await ticker.getAttribute('data-market-ticker-state'),statusText:await ticker.getByRole('status').innerText()};\n"
                "const interbank=page.waitForResponse(r=>r.url().includes('/api/positions/interbank?')&&r.status()===200);\n"
                "await page.getByRole('tab',{name:'同业持仓',exact:true}).click(); const ib=await (await interbank).json();\n"
                "assert.equal(ib.result.total,1); await page.getByText('T1',{exact:true}).waitFor({state:'visible'});\n"
                "assert.equal(ib.result.items[0].direction,'Asset'); assert.deepEqual(errors,[]);\n"
                "assert(requests.filter(r=>new URL(r.url).pathname.startsWith('/api/')||new URL(r.url).pathname.startsWith('/ui/')).every(r=>r.method==='GET'));\n"
                "await page.screenshot({path:process.env.TEST_APP_SCREENSHOT,fullPage:true});\n"
                "fs.writeFileSync(process.env.TEST_APP_RESULT,JSON.stringify({bonds:payload,interbank:ib,ticker:tickerEvidence,requests,errors},null,2));\n"
                "} finally { await browser.close(); }\n", encoding="utf-8",
            )
            browser = subprocess.Popen([NODE, str(browser_script)], cwd=root / "frontend", env={
                **environment, "TEST_APP_URL": base, "TEST_APP_RESULT": str(root / "browser-result.json"),
                "TEST_APP_SCREENSHOT": str(root / "positions.png"),
            }, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_process_options())
            output, error = browser.communicate(timeout=120)
            assert browser.returncode == 0, (output + error).decode(errors="replace")
            assert frontend.poll() is None, "Source process exited before the requested interrupt"
            if os.name == "nt":
                _interrupt(frontend)
            else:
                # A terminal sends Ctrl+C to its foreground process group, which
                # includes npm's shell, the entry wrapper, controller and Vite.
                os.killpg(frontend.pid, signal.SIGINT)
            frontend.wait(timeout=15)
            # Windows npm also returns 1 for console Ctrl+C in an otherwise
            # idle successful script. This allowance applies only after the
            # completed browser assertions and explicit owned-console event;
            # the serving PID and TCP assertions below still require shutdown.
            expected_interrupt = (130, 1) if os.name == "nt" else (130, -signal.SIGINT)
            assert frontend.returncode in expected_interrupt, frontend_log.read_text(encoding="utf-8")
            _interrupt(api)
            api.wait(timeout=15)
            assert api.returncode == 130, api_log.read_text(encoding="utf-8")
        assert not _pid_is_running(vite_pid), "Vite child survived shutdown"
        assert not _pid_is_running(api_pid), "API child survived shutdown"
        for stopped_port in (frontend_port, api_port):
            with socket.socket() as connection:
                connection.settimeout(2)
                assert connection.connect_ex(("127.0.0.1", stopped_port)) != 0, "Stopped service still accepted TCP"
        assert _digest(db) == before, "Read-only application changed the seeded DuckDB"
        assert not list(storage.glob("**/*.jsonl")), "Read-only sample created governance events"
        (root / "acceptance.json").write_text(json.dumps({
            "python": sys.version, "node": subprocess.check_output([NODE, "--version"], text=True).strip(),
            "node_executable": NODE, "source_hashes": source_hashes, "duckdb_sha256_before_and_after": before,
            "ticker": json.loads((root / "browser-result.json").read_text(encoding="utf-8"))["ticker"],
            "api": api_base, "frontend": base, "sample_rows": {"bonds": 4, "interbank": 2},
            "permissions": ["positions/read", "balance_analysis/read"], "services_stopped": True,
            "stopped_child_pids": {"api": api_pid, "vite": vite_pid},
            "migration_and_prewarm_skipped": True, "compose_executed": False,
            "repository_dotenv_disabled_in_test_process": True,
            "browser_executed": True, "shutdown_trigger": "Ctrl+C sent to the owned terminal process group",
            "npm_interrupt_returncode": frontend.returncode, "api_interrupt_returncode": api.returncode,
        }, indent=2), encoding="utf-8")
    finally:
        if browser is not None:
            _close(browser)
        if frontend is not None:
            _close(frontend, vite_pid)
        if api is not None:
            _close(api, api_pid)
