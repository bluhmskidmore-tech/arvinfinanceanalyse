from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import threading
from contextlib import contextmanager
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


pytestmark = pytest.mark.governance_meta

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dev_runtime_control.py"


def _load_module() -> ModuleType:
    name = "test_dev_runtime_control_module"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runtime_root(tmp_path: Path) -> tuple[ModuleType, Path]:
    root = tmp_path / "临时 runtime root with space"
    root.mkdir()
    module = _load_module()
    try:
        yield module, root
    finally:
        sys.modules.pop(module.__name__, None)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _accepted_selection(
    root: Path,
    *,
    rows: list[dict[str, str]] | None = None,
) -> tuple[dict[str, str], Path, Path]:
    build = root / "accepted build"
    asset = build / "assets" / "entry.js"
    chunk = build / "assets" / "small-chunk.js"
    vite = root / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    asset.parent.mkdir(parents=True)
    vite.parent.mkdir(parents=True)
    index = build / "index.html"
    index.write_text(
        '<main>accepted</main><script type="module" src="/assets/entry.js"></script>',
        encoding="utf-8",
    )
    asset.write_text("window.accepted = true;", encoding="utf-8")
    chunk.write_text("// unchanged chunk", encoding="utf-8")
    vite.write_text("// fixture vite entry", encoding="utf-8")
    manifest = root / "accepted manifest.json"
    manifest_rows = rows or [
        {"path": "index.html", "sha256": _digest(index)},
        {"path": "assets/entry.js", "sha256": _digest(asset)},
        {"path": "assets/small-chunk.js", "sha256": _digest(chunk)},
    ]
    manifest.write_text(json.dumps(manifest_rows), encoding="utf-8")
    return (
        {
            "mode": "accepted",
            "data_source": "real",
            "build_root": build.relative_to(root).as_posix(),
            "manifest_path": manifest.relative_to(root).as_posix(),
            "manifest_sha256": _digest(manifest),
        },
        build,
        manifest,
    )


def test_enter_persists_launch_block_and_not_drained(runtime_root: tuple[ModuleType, Path]) -> None:
    module, root = runtime_root

    state = module.enter_maintenance(root, "safe drain")

    assert state["state"] == "launch_blocked"
    assert state["drained"] is False
    assert json.loads((module.control_dir(root) / "maintenance.json").read_text(encoding="utf-8")) == state


def test_wrong_owner_cannot_leave_maintenance(runtime_root: tuple[ModuleType, Path]) -> None:
    module, root = runtime_root
    state = module.enter_maintenance(root, "approved window")

    with pytest.raises(module.RuntimeControlError, match="owner token"):
        module.leave_maintenance(root, "not-the-owner")

    assert (module.control_dir(root) / "maintenance.json").exists()
    module.leave_maintenance(root, state["owner_token"])


@pytest.mark.parametrize("kind", ["malformed", "directory"])
def test_run_child_fails_closed_for_any_maintenance_marker(
    runtime_root: tuple[ModuleType, Path], monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    module, root = runtime_root
    marker = module.control_dir(root) / "maintenance.json"
    marker.parent.mkdir(parents=True)
    if kind == "malformed":
        marker.write_text("not json", encoding="utf-8")
    else:
        marker.mkdir()
    called: list[object] = []
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: called.append(args))

    with pytest.raises(module.RuntimeControlError, match="maintenance blocks"):
        module.run_child(root, {"argv": ["never"], "cwd": str(root)})

    assert called == []


@pytest.mark.parametrize(
    "case",
    ["wrong_manifest_hash", "missing", "extra", "duplicate", "parent", "absolute", "symlink"],
)
def test_select_rejects_invalid_accepted_manifest_without_writing_selection(
    runtime_root: tuple[ModuleType, Path], case: str
) -> None:
    module, root = runtime_root
    selection, build, manifest = _accepted_selection(root)
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    if case == "wrong_manifest_hash":
        selection["manifest_sha256"] = "0" * 64
    elif case == "missing":
        (build / "assets" / "entry.js").unlink()
    elif case == "extra":
        (build / "unlisted.txt").write_text("extra", encoding="utf-8")
    elif case == "duplicate":
        rows.append(dict(rows[0]))
    elif case == "parent":
        rows[1] = {"path": "../escape.js", "sha256": "a" * 64}
    elif case == "absolute":
        rows[1] = {"path": "/escape.js", "sha256": "a" * 64}
    else:
        outside = root.parent / "outside.js"
        outside.write_text("outside", encoding="utf-8")
        try:
            (build / "linked.js").symlink_to(outside)
        except OSError:
            pytest.skip("symbolic link creation is unavailable")
        rows.append({"path": "linked.js", "sha256": _digest(outside)})
    if case not in {"wrong_manifest_hash", "missing", "extra"}:
        manifest.write_text(json.dumps(rows), encoding="utf-8")
        selection["manifest_sha256"] = _digest(manifest)
    state = module.enter_maintenance(root, "select accepted build")

    with pytest.raises(module.RuntimeControlError):
        module.select_frontend(root, selection, state["owner_token"])

    assert not (module.control_dir(root) / "frontend.json").exists()


def test_select_then_leave_keeps_a_real_accepted_preview_plan(
    runtime_root: tuple[ModuleType, Path]
) -> None:
    module, root = runtime_root
    selection, build, _manifest = _accepted_selection(root)
    state = module.enter_maintenance(root, "select accepted build")
    module.select_frontend(root, selection, state["owner_token"])
    module.leave_maintenance(root, state["owner_token"])

    plan = module.frontend_plan(root, "node")

    assert plan["mode"] == "accepted"
    assert plan["argv"][2:4] == ["preview", "--outDir"]
    assert plan["argv"][4] == str(build)
    assert {probe["path"] for probe in plan["probes"]} == {"index.html", "assets/entry.js"}
    assert not (module.control_dir(root) / "maintenance.json").exists()


@pytest.mark.parametrize("changed", ["build", "manifest"])
def test_changed_selected_build_refuses_run_before_starting_child(
    runtime_root: tuple[ModuleType, Path], monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    module, root = runtime_root
    selection, build, manifest = _accepted_selection(root)
    state = module.enter_maintenance(root, "select accepted build")
    module.select_frontend(root, selection, state["owner_token"])
    module.leave_maintenance(root, state["owner_token"])
    if changed == "build":
        (build / "assets" / "entry.js").write_text("changed", encoding="utf-8")
    else:
        manifest.write_text("[]", encoding="utf-8")
    started: list[object] = []
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: started.append(args))

    with pytest.raises(module.RuntimeControlError):
        module.run_child(root, None, node="node")

    assert started == []


def test_entry_change_is_rejected_even_when_small_chunk_is_unchanged(
    runtime_root: tuple[ModuleType, Path]
) -> None:
    module, root = runtime_root
    selection, build, _manifest = _accepted_selection(root)
    state = module.enter_maintenance(root, "select accepted build")
    module.select_frontend(root, selection, state["owner_token"])
    module.leave_maintenance(root, state["owner_token"])
    (build / "index.html").write_text(
        '<script type="module" src="/assets/replaced-entry.js"></script>',
        encoding="utf-8",
    )

    with pytest.raises(module.RuntimeControlError):
        module.frontend_plan(root, shutil.which("node") or "node", verify_files=False)

    assert (build / "assets" / "small-chunk.js").read_text(encoding="utf-8") == "// unchanged chunk"


def test_accepted_plan_requires_resolvable_node_and_vite_entry(
    runtime_root: tuple[ModuleType, Path]
) -> None:
    module, root = runtime_root
    selection, _build, _manifest = _accepted_selection(root)
    state = module.enter_maintenance(root, "select accepted build")
    module.select_frontend(root, selection, state["owner_token"])
    module.leave_maintenance(root, state["owner_token"])
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is unavailable on this host")
    vite = root / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    vite.unlink()

    with pytest.raises(module.RuntimeControlError):
        module.frontend_plan(root, node)


@pytest.mark.parametrize("invalid", ["no_module", "missing_vite", "missing_node"])
def test_invalid_replacement_does_not_overwrite_existing_accepted_selection(
    runtime_root: tuple[ModuleType, Path], monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    module, root = runtime_root
    valid, build, manifest = _accepted_selection(root)
    state = module.enter_maintenance(root, "select accepted build")
    module.select_frontend(root, valid, state["owner_token"])
    selected_path = module.control_dir(root) / "frontend.json"
    previous = selected_path.read_bytes()
    replacement = dict(valid)
    if invalid == "no_module":
        (build / "index.html").write_text("<main>no module entry</main>", encoding="utf-8")
        rows = json.loads(manifest.read_text(encoding="utf-8"))
        rows[0]["sha256"] = _digest(build / "index.html")
        manifest.write_text(json.dumps(rows), encoding="utf-8")
        replacement["manifest_sha256"] = _digest(manifest)
    elif invalid == "missing_vite":
        (root / "frontend" / "node_modules" / "vite" / "bin" / "vite.js").unlink()
    else:
        monkeypatch.setattr(module.shutil, "which", lambda _node: None)

    with pytest.raises(module.RuntimeControlError):
        module.select_frontend(root, replacement, state["owner_token"])

    assert selected_path.read_bytes() == previous


def test_run_child_starts_under_lock_waits_outside_lock_and_returns_exit_code(
    runtime_root: tuple[ModuleType, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, root = runtime_root
    original_lock = module.operation_lock
    state = {"inside_lock": False, "popen_called": False}

    @contextmanager
    def tracking_lock(lock_root: Path, timeout: float = 30):
        with original_lock(lock_root, timeout):
            state["inside_lock"] = True
            try:
                yield
            finally:
                state["inside_lock"] = False

    class Child:
        def wait(self) -> int:
            assert state["inside_lock"] is False
            entered = module.enter_maintenance(root, "started while waiting")
            assert entered["drained"] is False
            return 23

    def popen(*args: Any, **kwargs: Any) -> Child:
        assert state["inside_lock"] is True
        state["popen_called"] = True
        return Child()

    monkeypatch.setattr(module, "operation_lock", tracking_lock)
    monkeypatch.setattr(module.subprocess, "Popen", popen)

    assert module.run_child(root, {"argv": ["synthetic"], "cwd": str(root)}) == 23
    assert state["popen_called"] is True
    assert (module.control_dir(root) / "maintenance.json").exists()


def test_run_child_locks_accepted_frontend_to_real_data_and_proxy(
    runtime_root: tuple[ModuleType, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, root = runtime_root
    selection, _build, _manifest = _accepted_selection(root)
    state = module.enter_maintenance(root, "select accepted build")
    module.select_frontend(root, selection, state["owner_token"])
    module.leave_maintenance(root, state["owner_token"])
    observed: dict[str, str] = {}

    class Child:
        def wait(self) -> int:
            return 0

    def popen(_argv: list[str], *, cwd: str, env: dict[str, str]) -> Child:
        del cwd
        observed.update(env)
        return Child()

    monkeypatch.setattr(module.subprocess, "Popen", popen)

    assert module.run_child(root, None, node="node") == 0
    assert observed["VITE_DATA_SOURCE"] == "real"
    assert observed["MOSS_VITE_API_PROXY"] == "http://127.0.0.1:7888"


def test_run_child_preserves_existing_dev_environment(
    runtime_root: tuple[ModuleType, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    module, root = runtime_root
    observed: dict[str, str] = {}
    monkeypatch.setenv("VITE_DATA_SOURCE", "dev-fixture")
    monkeypatch.setenv("MOSS_VITE_API_PROXY", "http://example.test:9999")

    class Child:
        def wait(self) -> int:
            return 0

    def popen(_argv: list[str], *, cwd: str, env: dict[str, str]) -> Child:
        del cwd
        observed.update(env)
        return Child()

    monkeypatch.setattr(module.subprocess, "Popen", popen)

    assert module.run_child(root, None, node="node") == 0
    assert observed["VITE_DATA_SOURCE"] == "dev-fixture"
    assert observed["MOSS_VITE_API_PROXY"] == "http://example.test:9999"


@contextmanager
def _http_server(handler: type[BaseHTTPRequestHandler]):
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def test_probe_frontend_accepts_exact_index_and_asset_hashes(runtime_root: tuple[ModuleType, Path]) -> None:
    module, root = runtime_root
    selection, build, _manifest = _accepted_selection(root)
    state = module.enter_maintenance(root, "select accepted build")
    module.select_frontend(root, selection, state["owner_token"])
    module.leave_maintenance(root, state["owner_token"])
    handler = partial(SimpleHTTPRequestHandler, directory=str(build))

    with _http_server(handler) as base_url:
        module.probe_frontend(root, base_url)


def test_probe_frontend_rejects_http_200_with_wrong_asset_content(
    runtime_root: tuple[ModuleType, Path]
) -> None:
    module, root = runtime_root
    selection, build, _manifest = _accepted_selection(root)
    state = module.enter_maintenance(root, "select accepted build")
    module.select_frontend(root, selection, state["owner_token"])
    module.leave_maintenance(root, state["owner_token"])
    index = (build / "index.html").read_bytes()

    class WrongContentHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            payload = index if self.path == "/index.html" else b"not the selected asset"
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *args: Any) -> None:
            return None

    with _http_server(WrongContentHandler) as base_url:
        with pytest.raises(module.RuntimeControlError, match="response does not match"):
            module.probe_frontend(root, base_url)
