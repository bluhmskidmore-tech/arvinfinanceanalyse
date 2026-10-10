from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import urlopen

import pytest

from tests.test_dev_frontend_source_entry import (
    NODE,
    ROOT,
    _close,
    _environment,
    _interrupt,
    _pid_is_running,
    _process_options,
    _run,
    source_root as _source_root,
)


pytestmark = pytest.mark.governance_meta
source_root = _source_root


def _port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _get(base: str, resource: str) -> str:
    with urlopen(base + resource, timeout=2) as response:
        return response.read().decode("utf-8")


def _wait_for_file(path: Path, process: subprocess.Popen, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert path.exists(), f"Process did not produce {path.name}; exit={process.poll()}"


@pytest.fixture
def live_frontend(source_root: Path) -> Path:
    dependencies = Path(os.environ.get("MOSS_TEST_VITE_DEPENDENCIES", ROOT / "frontend" / "node_modules"))
    if not (dependencies / "vite" / "bin" / "vite.js").is_file():
        pytest.skip("Real Vite dependencies are unavailable; run npm ci before source live acceptance")
    frontend = source_root / "frontend"
    frontend.mkdir()
    link = frontend / "node_modules"
    try:
        link.symlink_to(dependencies, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        # Directory junctions do not require Windows symlink privilege. Both
        # paths are explicit; pytest removes the junction without its target.
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(dependencies)],
                       check=True, capture_output=True, timeout=5)
    (frontend / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
    (frontend / "index.html").write_text('<script type="module" src="/src/probe.js"></script>', encoding="utf-8")
    source = frontend / "src" / "probe.js"
    source.parent.mkdir()
    source.write_text("globalThis.source = import.meta.env.VITE_DATA_SOURCE;\n"
                      "globalThis.sourceProbe = 'before';\nif (import.meta.hot) import.meta.hot.accept();\n", encoding="utf-8")
    (frontend / "vite.config.mjs").write_text(
        "import fs from 'node:fs';\nexport default {\n"
        "plugins: [{ name: 'source-process-identity', configureServer(server) {"
        "server.httpServer.once('listening', () => fs.writeFileSync(process.env.TEST_SOURCE_PID,"
        "JSON.stringify({pid: process.pid, address: server.httpServer.address()}))); } }],\n"
        "server: { watch: { usePolling: true, interval: 100 }, proxy: Object.fromEntries("
        "['/api', '/ui', '/health'].map(prefix => [prefix, {target: process.env.MOSS_VITE_API_PROXY}])) }\n};\n",
        encoding="utf-8",
    )
    return source_root


def test_source_entry_live_vite_hot_reload_proxy_and_ctrl_c(live_frontend: Path) -> None:
    class SyntheticApi(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = json.dumps({"identity": "isolated source acceptance", "path": self.path}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:
            pass

    api = HTTPServer(("127.0.0.1", 0), SyntheticApi)
    api_thread = threading.Thread(target=api.serve_forever, daemon=True)
    api_thread.start()
    port = _port()
    base = f"http://127.0.0.1:{port}"
    pid_file = live_frontend / "vite-pid.json"
    process = subprocess.Popen(
        [NODE, str(live_frontend / "scripts" / "dev-frontend-source.mjs"), "--port", str(port)],
        cwd=live_frontend, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        env=_environment(MOSS_VITE_API_PROXY=f"http://127.0.0.1:{api.server_port}", TEST_SOURCE_PID=str(pid_file)),
        **_process_options(),
    )
    websocket = None
    child_pid = None
    try:
        _wait_for_file(pid_file, process)
        observed = json.loads(pid_file.read_text(encoding="utf-8"))
        child_pid = observed["pid"]
        assert observed["address"]["address"] == "127.0.0.1"
        assert observed["address"]["port"] == port
        deadline = time.monotonic() + 20
        while True:
            try:
                assert '/@vite/client' in _get(base, "/")
                break
            except OSError:
                assert process.poll() is None and time.monotonic() < deadline
                time.sleep(0.05)
        served = _get(base, "/src/probe.js")
        assert re.search(r'"VITE_DATA_SOURCE":\s*"real"', served)
        for resource in ("/api/source-probe", "/ui/source-probe", "/health"):
            assert json.loads(_get(base, resource)) == {"identity": "isolated source acceptance", "path": resource}
        ready = live_frontend / "websocket-ready"
        update = live_frontend / "websocket-update.json"
        client = _get(base, "/@vite/client")
        token = re.search(r'const wsToken = "([^"]+)"', client)
        assert token, "Vite client did not disclose its normal websocket token"
        websocket_code = (
            "const fs=require('fs'); const ws=new WebSocket(process.env.TEST_WS_URL, 'vite-hmr');"
            "const timer=setTimeout(()=>{console.error('No HMR update');process.exit(1)},20000);"
            "ws.addEventListener('message', event=>{const data=JSON.parse(event.data);"
            "if(data.type==='connected')fs.writeFileSync(process.env.TEST_WS_READY,'ready');"
            "if(data.type==='update' && data.updates.some(u=>u.path==='/src/probe.js')){"
            "fs.writeFileSync(process.env.TEST_WS_UPDATE,JSON.stringify(data));clearTimeout(timer);ws.close();}});"
            "ws.addEventListener('error',()=>process.exit(2));"
        )
        websocket = subprocess.Popen([NODE, "-e", websocket_code], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     env={**_environment(), "TEST_WS_URL": f"ws://127.0.0.1:{port}/?token={token.group(1)}",
                                          "TEST_WS_READY": str(ready), "TEST_WS_UPDATE": str(update)})
        _wait_for_file(ready, websocket)
        source = live_frontend / "frontend" / "src" / "probe.js"
        source.write_text(source.read_text(encoding="utf-8").replace("'before'", "'after'"), encoding="utf-8")
        _wait_for_file(update, websocket)
        websocket.communicate(timeout=5)
        assert websocket.returncode == 0
        assert "'after'" in _get(base, "/src/probe.js")
        _interrupt(process)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 130, stdout + stderr
        assert not _pid_is_running(child_pid), "Vite process survived Ctrl+C"
        with pytest.raises(OSError):
            _get(base, "/")
    finally:
        if websocket is not None and websocket.poll() is None:
            websocket.kill()
            websocket.communicate(timeout=5)
        _close(process, child_pid)
        api.shutdown()
        api.server_close()
        api_thread.join(timeout=5)


def test_source_entry_live_vite_refuses_occupied_port(live_frontend: Path) -> None:
    pid_file = live_frontend / "conflict-vite-pid.json"
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        completed = _run(live_frontend, "--port", str(port), environment=_environment(TEST_SOURCE_PID=str(pid_file)))

    assert completed.returncode != 0
    assert f"Port {port} is already in use" in completed.stderr
