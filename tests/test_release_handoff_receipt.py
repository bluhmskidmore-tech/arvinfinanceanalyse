from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime, timedelta
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

import scripts.release_handoff_receipt as handoff_module
from scripts.release_handoff_receipt import build_handoff_receipt

pytestmark = pytest.mark.governance_meta


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _fixture(root: Path, *, closed_source: bool = True) -> dict[str, Path | dict[str, str]]:
    source = root / "src" / "feature.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    rows = [{"path": "src/feature.py", "sha256": _sha(source)}]
    source_manifest = _write_json(
        root / "source.json",
        {"files": rows, "roots": ["src"]} if closed_source else rows,
    )

    build = root / "candidate build"
    asset = build / "assets" / "entry.js"
    asset.parent.mkdir(parents=True)
    index = build / "index.html"
    index.write_text('<script type="module" src="/assets/entry.js"></script>', encoding="utf-8")
    asset.write_text("window.release = true;", encoding="utf-8")
    manifest = _write_json(
        root / "build-manifest.json",
        [
            {"path": "index.html", "sha256": _sha(index)},
            {"path": "assets/entry.js", "sha256": _sha(asset)},
        ],
    )
    vite = root / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    vite.parent.mkdir(parents=True)
    vite.write_text("// test fixture", encoding="utf-8")
    selection: dict[str, str] = {
        "mode": "accepted",
        "data_source": "real",
        "build_root": build.relative_to(root).as_posix(),
        "manifest_path": manifest.relative_to(root).as_posix(),
        "manifest_sha256": _sha(manifest),
    }
    selection_path = _write_json(root / "candidate.json", selection)
    registered = root / "tmp-governance" / "runtime-clean" / "control" / "frontend.json"
    _write_json(registered, selection)
    source_manifest_sha = _sha(source_manifest)
    test_receipt = _write_json(
        root / "test-receipt.json",
        {
            "source_manifest_sha256": source_manifest_sha,
            "command": ["python", "-m", "pytest", "tests/test_feature.py"],
            "exit_code": 0,
            "results": [{"name": "tests/test_feature.py", "status": "passed"}],
        },
    )
    build_receipt = _write_json(
        root / "build-receipt.json",
        {
            "source_manifest_sha256": source_manifest_sha,
            "build_manifest_sha256": selection["manifest_sha256"],
        },
    )
    return {
        "source": source,
        "source_manifest": source_manifest,
        "build": build,
        "manifest": manifest,
        "selection": selection,
        "selection_path": selection_path,
        "registered": registered,
        "test_receipt": test_receipt,
        "build_receipt": build_receipt,
    }


class _Server:
    def __init__(self, directory: Path) -> None:
        handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
        self.server = HTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}/"

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()


class _HandlerServer:
    def __init__(self, handler: type[BaseHTTPRequestHandler]) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}/"

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()


def _evaluate(root: Path, fixture: dict[str, Path | dict[str, str]], base_url: str, **overrides: object) -> dict:
    arguments = {
        "root": root,
        "source_manifest": fixture["source_manifest"],
        "test_receipt": fixture["test_receipt"],
        "build_receipt": fixture["build_receipt"],
        "selection_path": fixture["selection_path"],
        "base_url": base_url,
    }
    arguments.update(overrides)
    return build_handoff_receipt(**arguments)


def test_complete_isolated_evidence_passes_and_identity_is_stable(tmp_path: Path) -> None:
    root = tmp_path / "repo with space"
    root.mkdir()
    fixture = _fixture(root)
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}

    with _Server(fixture["build"]) as base_url:
        first = _evaluate(root, fixture, base_url)
        second = _evaluate(root, fixture, base_url)

    assert first["status"] == "passed"
    assert first["identity_sha256"] == second["identity_sha256"]
    assert first["layers"]["source"]["coverage"] == "root_closed"
    assert first["layers"]["tests"]["status"] == "passed"
    assert first["layers"]["registration"]["status"] == "passed"
    assert first["layers"]["http"]["status"] == "passed"
    assert first["business_acceptance"] == "not assessed"
    assert {path: path.read_bytes() for path in root.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("change", ["modified", "missing", "added"])
def test_closed_source_roots_reject_any_inventory_drift(tmp_path: Path, change: str) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    source = fixture["source"]
    if change == "modified":
        source.write_text("VALUE = 2\n", encoding="utf-8")
    elif change == "missing":
        source.unlink()
    else:
        (source.parent / "new_file.py").write_text("NEW = True\n", encoding="utf-8")

    result = _evaluate(root, fixture, "http://127.0.0.1:1/")

    assert result["status"] == "failed"
    assert result["layers"]["source"]["status"] == "failed"


def test_legacy_list_manifest_is_explicitly_limited_to_listed_files(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root, closed_source=False)
    (root / "src" / "unlisted.py").write_text("UNLISTED = True\n", encoding="utf-8")

    with _Server(fixture["build"]) as base_url:
        result = _evaluate(root, fixture, base_url)

    source_layer = result["layers"]["source"]
    assert source_layer["status"] == "passed"
    assert source_layer["expected_manifest_sha256"] == _sha(fixture["source_manifest"])
    assert source_layer["coverage"] == "listed_files_only"
    assert source_layer["mismatch_count"] == 0
    assert source_layer["mismatches"] == []
    assert len(source_layer["observed_files_sha256"]) == 64


def test_dependency_directory_cannot_be_declared_as_a_source_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    manifest = json.loads(fixture["source_manifest"].read_text(encoding="utf-8"))
    manifest["roots"] = ["frontend/node_modules"]
    _write_json(fixture["source_manifest"], manifest)

    result = _evaluate(root, fixture, "http://127.0.0.1:1/")

    assert result["layers"]["source"]["status"] == "failed"


def test_closed_source_walk_error_is_not_silently_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)

    def denied_walk(_directory: Path, *, followlinks: bool, onerror: object):
        assert followlinks is False
        assert callable(onerror)
        onerror(PermissionError("synthetic denied subtree"))
        return iter(())

    monkeypatch.setattr(handoff_module.os, "walk", denied_walk)
    result = _evaluate(root, fixture, "http://127.0.0.1:1/")

    assert result["layers"]["source"]["status"] == "failed"
    assert "denied" in result["layers"]["source"]["reason"]


@pytest.mark.parametrize("protected", ["data/secret.csv", "data_input/secret.csv"])
def test_listed_source_cannot_read_protected_business_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, protected: str
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root, closed_source=False)
    business_file = root / protected
    business_file.parent.mkdir(parents=True, exist_ok=True)
    business_file.write_text("sensitive", encoding="utf-8")
    _write_json(
        fixture["source_manifest"],
        [{"path": protected, "sha256": hashlib.sha256(b"sensitive").hexdigest()}],
    )
    original_read_bytes = Path.read_bytes
    business_reads: list[Path] = []

    def guarded_read_bytes(path: Path) -> bytes:
        if path == business_file:
            business_reads.append(path)
            raise AssertionError("protected business file must not be read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    result = _evaluate(root, fixture, "http://127.0.0.1:1/")

    assert result["layers"]["source"]["status"] == "failed"
    assert business_reads == []


@pytest.mark.parametrize("exit_code", [True, False, 1])
def test_test_receipt_never_treats_boolean_or_nonzero_exit_as_passing(
    tmp_path: Path, exit_code: object
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    receipt = json.loads(fixture["test_receipt"].read_text(encoding="utf-8"))
    receipt["exit_code"] = exit_code
    _write_json(fixture["test_receipt"], receipt)

    result = _evaluate(root, fixture, "http://127.0.0.1:1/")

    assert result["layers"]["tests"]["status"] != "passed"
    if exit_code == 1:
        assert result["layers"]["tests"]["command"] == receipt["command"]
        assert result["layers"]["tests"]["exit_code"] == 1
        assert result["layers"]["tests"]["results"] == receipt["results"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda receipt: receipt.update(command=[None]),
        lambda receipt: receipt.update(results=[{"status": "passed"}]),
    ],
)
def test_malformed_test_details_cannot_pass(
    tmp_path: Path, mutation: object
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    receipt = json.loads(fixture["test_receipt"].read_text(encoding="utf-8"))
    mutation(receipt)
    _write_json(fixture["test_receipt"], receipt)

    result = _evaluate(root, fixture, "http://127.0.0.1:1/")

    assert result["layers"]["tests"]["status"] != "passed"


def test_duplicate_test_result_names_cannot_pass(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    receipt = json.loads(fixture["test_receipt"].read_text(encoding="utf-8"))
    receipt["results"] = [
        {"name": "same-test", "status": "passed"},
        {"name": "same-test", "status": "passed"},
    ]
    _write_json(fixture["test_receipt"], receipt)

    result = _evaluate(root, fixture, "http://127.0.0.1:1/")

    assert result["layers"]["tests"]["status"] != "passed"


def test_missing_receipts_remain_unknown_while_other_layers_are_reported(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)

    with _Server(fixture["build"]) as base_url:
        result = _evaluate(root, fixture, base_url, test_receipt=None, build_receipt=None)

    assert result["status"] == "unknown"
    assert result["layers"]["tests"]["status"] == "unknown"
    assert result["layers"]["build_binding"]["status"] == "unknown"
    assert result["layers"]["source"]["status"] == "passed"
    assert result["layers"]["candidate"]["status"] == "passed"
    assert result["layers"]["registration"]["status"] == "passed"
    assert result["layers"]["http"]["status"] == "passed"


@pytest.mark.parametrize("change", ["added", "modified", "missing"])
def test_build_manifest_inventory_fails_closed(tmp_path: Path, change: str) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    if change == "added":
        (fixture["build"] / "unlisted.js").write_text("extra", encoding="utf-8")
    elif change == "modified":
        (fixture["build"] / "assets" / "entry.js").write_text("changed", encoding="utf-8")
    else:
        (fixture["build"] / "assets" / "entry.js").unlink()
    result = _evaluate(root, fixture, "http://127.0.0.1:1/")

    assert result["layers"]["candidate"]["status"] == "failed"
    assert result["layers"]["http"]["status"] != "passed"


def test_registration_mismatch_does_not_suppress_independent_http_probe(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    registered = json.loads(fixture["registered"].read_text(encoding="utf-8"))
    registered["build_root"] = "some other accepted build"
    _write_json(fixture["registered"], registered)

    with _Server(fixture["build"]) as base_url:
        result = _evaluate(root, fixture, base_url)

    assert result["layers"]["registration"]["status"] == "failed"
    assert result["layers"]["http"]["status"] == "passed"
    assert result["status"] == "failed"


def test_unreachable_or_wrong_http_content_cannot_claim_live_entry(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)

    unreachable = _evaluate(root, fixture, "http://127.0.0.1:1/")
    wrong = root / "wrong"
    wrong.mkdir()
    (wrong / "index.html").write_text("wrong package", encoding="utf-8")
    with _Server(wrong) as base_url:
        wrong_content = _evaluate(root, fixture, base_url)

    assert unreachable["layers"]["http"]["status"] == "failed"
    assert wrong_content["layers"]["http"]["status"] == "failed"
    assert unreachable["status"] != "passed"
    assert wrong_content["status"] != "passed"


@pytest.mark.parametrize("entry_response", ["wrong", "missing"])
def test_correct_http_index_cannot_hide_wrong_or_missing_entry(
    tmp_path: Path, entry_response: str
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    index = (fixture["build"] / "index.html").read_bytes()

    class EntryHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/index.html":
                payload, status = index, 200
            elif entry_response == "wrong":
                payload, status = b"wrong entry package", 200
            else:
                payload, status = b"missing", 404
            self.send_response(status)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *args: object) -> None:
            return None

    with _HandlerServer(EntryHandler) as base_url:
        result = _evaluate(root, fixture, base_url)

    assert result["layers"]["http"]["status"] == "failed"
    assert result["layers"]["http"]["url"] == base_url
    assert result["status"] == "failed"


def test_http_redirect_is_rejected_even_when_final_content_matches(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    index = (fixture["build"] / "index.html").read_bytes()
    entry = (fixture["build"] / "assets" / "entry.js").read_bytes()

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/index.html":
                self.send_response(302)
                self.send_header("Location", "/redirected-index")
                self.end_headers()
                return
            payload = index if self.path == "/redirected-index" else entry
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *args: object) -> None:
            return None

    with _HandlerServer(RedirectHandler) as base_url:
        result = _evaluate(root, fixture, base_url)

    assert result["layers"]["http"]["status"] == "failed"
    assert result["layers"]["http"]["url"] == base_url


def test_distinct_observed_source_drift_produces_distinct_identity(tmp_path: Path) -> None:
    identities: list[str] = []
    for value in ("VALUE = 2\n", "VALUE = 3\n"):
        root = tmp_path / value.strip().replace(" ", "_")
        root.mkdir()
        fixture = _fixture(root)
        fixture["source"].write_text(value, encoding="utf-8")
        result = _evaluate(root, fixture, "http://127.0.0.1:1/")
        assert result["layers"]["source"]["status"] == "failed"
        identities.append(result["identity_sha256"])

    assert identities[0] != identities[1]


def test_receipts_changed_during_http_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    original = handoff_module._http_snapshot

    def mutate_receipts(*args: object, **kwargs: object) -> object:
        observed = original(*args, **kwargs)
        fixture["test_receipt"].write_text("{}", encoding="utf-8")
        fixture["build_receipt"].write_text("{}", encoding="utf-8")
        return observed

    monkeypatch.setattr(handoff_module, "_http_snapshot", mutate_receipts)
    with _Server(fixture["build"]) as base_url:
        result = _evaluate(root, fixture, base_url)

    assert result["status"] == "failed"
    assert result["layers"]["tests"]["status"] == "failed"
    assert result["layers"]["build_binding"]["status"] == "failed"


@pytest.mark.parametrize("manifest_change", ["expected_hash", "roots"])
def test_source_manifest_metadata_changed_during_http_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, manifest_change: str
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    original = handoff_module._http_snapshot

    def mutate_manifest(*args: object, **kwargs: object) -> object:
        observed = original(*args, **kwargs)
        manifest = json.loads(fixture["source_manifest"].read_text(encoding="utf-8"))
        if manifest_change == "expected_hash":
            manifest["files"][0]["sha256"] = "0" * 64
        else:
            manifest["roots"] = ["src", "frontend/node_modules"]
        _write_json(fixture["source_manifest"], manifest)
        return observed

    monkeypatch.setattr(handoff_module, "_http_snapshot", mutate_manifest)
    with _Server(fixture["build"]) as base_url:
        result = _evaluate(root, fixture, base_url)

    assert result["status"] == "failed"
    assert result["layers"]["source"]["status"] == "failed"


@pytest.mark.parametrize("changed", ["candidate", "registration"])
def test_candidate_or_registration_changed_during_http_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    original = handoff_module._http_snapshot

    def mutate_runtime_identity(*args: object, **kwargs: object) -> object:
        observed = original(*args, **kwargs)
        path = fixture["selection_path"] if changed == "candidate" else fixture["registered"]
        value = json.loads(path.read_text(encoding="utf-8"))
        value["manifest_sha256"] = "0" * 64
        _write_json(path, value)
        return observed

    monkeypatch.setattr(handoff_module, "_http_snapshot", mutate_runtime_identity)
    with _Server(fixture["build"]) as base_url:
        result = _evaluate(root, fixture, base_url)

    assert result["status"] == "failed"
    assert result["layers"][changed]["status"] == "failed"


def test_local_port_participates_in_identity_and_failed_http_keeps_url(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture = _fixture(root)
    results: list[dict] = []
    for _ in range(2):
        with _Server(fixture["build"]) as base_url:
            results.append(_evaluate(root, fixture, base_url))

    failed_url = "http://127.0.0.1:1/"
    failed = _evaluate(root, fixture, failed_url)

    assert results[0]["status"] == results[1]["status"] == "passed"
    assert results[0]["identity_sha256"] != results[1]["identity_sha256"]
    assert failed["layers"]["http"]["status"] == "failed"
    assert failed["layers"]["http"]["url"] == failed_url


def _home_receipts(root: Path, fixture: dict, base_url: str) -> dict:
    now = datetime.now(UTC).isoformat()
    common = {"schema_version": 1, "scope": "dashboard-home-desktop", "status": "passed",
              "started_at": now, "finished_at": now, "failures": []}
    source = root / "backend/app/schemas/home.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("CONTRACT = 1\n", encoding="utf-8")
    runtime = {**common, "receipt_kind": "dashboard_home_runtime", "base_url": base_url,
               "frontend_probes": json.loads(fixture["manifest"].read_text(encoding="utf-8")),
               "home": {"fullPage": {
                   "research_tab": True,
                   "required_decision_items": False,
                   "sections": [{"id": name, "seen": True} for name in sorted(handoff_module.HOME_SECTIONS)],
                   "requests": [{"path": name, "status": 200, "finished": True}
                                for name in sorted(handoff_module.HOME_REQUIRED_PATHS)],
                   "states": {"loading": 0, "errors": 0, "unavailable": 2}, "failures": [],
               }}}
    backend = {**common, "receipt_kind": "dashboard_home_backend_contract",
               "base_url": base_url, "expected_contract_sha256": "a" * 64,
               "observed_contract_sha256": "a" * 64,
               "checked_paths": list(handoff_module.HOME_GET_PATHS),
               "coverage_gaps": [],
               "source_stable": True,
               "source_files": [{"path": source.relative_to(root).as_posix(), "sha256": _sha(source)}]}
    return {"page": "dashboard-home",
            "runtime_receipt": _write_json(root / "home-runtime.json", runtime),
            "backend_contract_receipt": _write_json(root / "backend-contract.json", backend)}


def test_home_acceptance_requires_both_checks_even_when_original_layers_pass(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with _Server(fixture["build"]) as base_url:
        legacy = _evaluate(tmp_path, fixture, base_url)
        home = _evaluate(tmp_path, fixture, base_url, page="dashboard-home")
    assert legacy["status"] == "passed"
    assert home["status"] == "failed"
    assert home["layers"]["home_runtime"]["status"] == "failed"
    assert home["layers"]["backend_contract"]["status"] == "failed"


def test_home_acceptance_passes_with_complete_live_checks_and_legal_empty_states(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with _Server(fixture["build"]) as base_url:
        arguments = _home_receipts(tmp_path, fixture, base_url)
        result = _evaluate(tmp_path, fixture, base_url, **arguments)
    assert result["status"] == "passed"
    assert result["scope"] == "dashboard-home-desktop"
    assert result["layers"]["home_runtime"]["request_count"] == len(handoff_module.HOME_REQUIRED_PATHS)
    assert result["layers"]["backend_contract"]["coverage"] == "response_contract_only"


@pytest.mark.parametrize("mutation", [
    "http_500", "http_502", "unfinished", "failed_transport", "missing_request", "missing_middle",
    "persistent_loading", "wrong_build", "wrong_url", "stale", "boolean_status", "bad_states", "tab_not_exercised",
    "missing_decision",
])
def test_home_failed_or_incomplete_runtime_cannot_pass(tmp_path: Path, mutation: str) -> None:
    fixture = _fixture(tmp_path)
    with _Server(fixture["build"]) as base_url:
        arguments = _home_receipts(tmp_path, fixture, base_url)
        path = arguments["runtime_receipt"]
        value = json.loads(path.read_text(encoding="utf-8"))
        full = value["home"]["fullPage"]
        if mutation.startswith("http_"):
            full["requests"][0]["status"] = int(mutation.split("_")[1])
        elif mutation == "unfinished":
            full["requests"][0]["finished"] = False
        elif mutation == "failed_transport":
            full["requests"][0]["failed"] = "net::ERR_CONNECTION_RESET"
        elif mutation == "missing_request":
            full["requests"].pop()
        elif mutation == "missing_middle":
            full["sections"][1]["seen"] = False
        elif mutation == "persistent_loading":
            full["failures"] = ["research still loading"]
        elif mutation == "wrong_build":
            value["frontend_probes"][1]["sha256"] = "f" * 64
        elif mutation == "wrong_url":
            value["base_url"] = "http://127.0.0.1:5991/"
        elif mutation == "stale":
            value["started_at"] = value["finished_at"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        elif mutation == "boolean_status":
            full["requests"][0]["status"] = True
        elif mutation == "bad_states":
            full["states"]["loading"] = 1
        elif mutation == "tab_not_exercised":
            full["research_tab"] = False
        elif mutation == "missing_decision":
            full["required_decision_items"] = True
        _write_json(path, value)
        result = _evaluate(tmp_path, fixture, base_url, **arguments)
    assert result["layers"]["home_runtime"]["status"] == "failed"
    assert result["status"] == "failed"


@pytest.mark.parametrize("mutation", [
    "old_schema", "missing_route", "source_changed", "wrong_url", "failed", "opaque_result", "coverage_absent",
])
def test_home_backend_contract_gap_cannot_pass(tmp_path: Path, mutation: str) -> None:
    fixture = _fixture(tmp_path)
    with _Server(fixture["build"]) as base_url:
        arguments = _home_receipts(tmp_path, fixture, base_url)
        path = arguments["backend_contract_receipt"]
        value = json.loads(path.read_text(encoding="utf-8"))
        if mutation == "old_schema":
            value["observed_contract_sha256"] = "b" * 64
        elif mutation == "missing_route":
            value["checked_paths"].pop()
        elif mutation == "source_changed":
            (tmp_path / value["source_files"][0]["path"]).write_text("CONTRACT = 2\n", encoding="utf-8")
        elif mutation == "wrong_url":
            value["base_url"] = "http://127.0.0.1:7889/"
        elif mutation == "opaque_result":
            value["coverage_gaps"] = ["GET /ui/home/snapshot response 200 has no named response fields"]
        elif mutation == "coverage_absent":
            value.pop("coverage_gaps")
        else:
            value["status"] = "failed"
            value["failures"] = ["principal_evidence absent in runtime schema"]
        _write_json(path, value)
        result = _evaluate(tmp_path, fixture, base_url, **arguments)
    assert result["layers"]["backend_contract"]["status"] == "failed"
    assert result["status"] == "failed"


def test_home_cli_executes_checks_and_rejects_failed_invocation_with_old_passing_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    output = tmp_path / "acceptance.json"
    calls = []
    with _Server(fixture["build"]) as base_url:
        arguments = _home_receipts(tmp_path, fixture, base_url)
        runtime_output = output.with_name("acceptance.home-runtime.json")
        runtime_output.write_bytes(arguments["runtime_receipt"].read_bytes())

        def run(command: list[str], **kwargs: object) -> object:
            calls.append(command)
            destination = Path(command[command.index("--output") + 1])
            if command[0] == "node":
                return type("Completed", (), {"returncode": 1, "stderr": b"synthetic launch failure"})()
            backend = json.loads(arguments["backend_contract_receipt"].read_text(encoding="utf-8"))
            backend["started_at"] = backend["finished_at"] = datetime.now(UTC).isoformat()
            _write_json(destination, backend)
            return type("Completed", (), {"returncode": 0, "stderr": b""})()

        monkeypatch.setattr(handoff_module.subprocess, "run", run)
        code = handoff_module.main([
            "--repo-root", str(tmp_path), "--source-manifest", str(fixture["source_manifest"]),
            "--test-receipt", str(fixture["test_receipt"]), "--build-receipt", str(fixture["build_receipt"]),
            "--selection", str(fixture["selection_path"]), "--base-url", base_url,
            "--page", "dashboard-home", "--output", str(output),
        ])
    result = json.loads(output.read_text(encoding="utf-8"))
    assert len(calls) == 2
    assert code == 1
    assert result["status"] == "failed"
    assert result["layers"]["home_runtime"]["status"] == "failed"
    assert result["layers"]["backend_contract"]["status"] == "passed"


def test_source_root_can_bind_immutable_build_source_without_claiming_current_checkout(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    immutable = tmp_path / "immutable"
    (immutable / "src").mkdir(parents=True)
    (immutable / "src/feature.py").write_bytes(fixture["source"].read_bytes())
    fixture["source"].write_text("VALUE = 2\n", encoding="utf-8")
    with _Server(fixture["build"]) as base_url:
        checkout = _evaluate(tmp_path, fixture, base_url)
        accepted = _evaluate(tmp_path, fixture, base_url, source_root=immutable)
    assert checkout["layers"]["source"]["status"] == "failed"
    assert accepted["layers"]["source"]["status"] == "passed"


@pytest.mark.parametrize("write_fresh", [True, False])
def test_home_cli_requires_receipts_from_this_invocation_even_when_children_exit_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_fresh: bool,
) -> None:
    fixture = _fixture(tmp_path)
    output = tmp_path / "acceptance.json"
    with _Server(fixture["build"]) as base_url:
        arguments = _home_receipts(tmp_path, fixture, base_url)
        for key, suffix in [("runtime_receipt", "home-runtime"), ("backend_contract_receipt", "backend-contract")]:
            output.with_name(f"acceptance.{suffix}.json").write_bytes(arguments[key].read_bytes())

        def run(command: list[str], **kwargs: object) -> object:
            if command[0] != "node":
                assert command[command.index("--base-url") + 1] == base_url
            assert kwargs["env"]["MOSS_HOME_STARTUP_READY_URL"] == base_url + "health/ready"
            if write_fresh:
                key = "runtime_receipt" if command[0] == "node" else "backend_contract_receipt"
                value = json.loads(arguments[key].read_text(encoding="utf-8"))
                value["started_at"] = value["finished_at"] = datetime.now(UTC).isoformat()
                _write_json(Path(command[command.index("--output") + 1]), value)
            return type("Completed", (), {"returncode": 0, "stderr": b""})()

        monkeypatch.setattr(handoff_module.subprocess, "run", run)
        code = handoff_module.main([
            "--repo-root", str(tmp_path), "--source-manifest", str(fixture["source_manifest"]),
            "--test-receipt", str(fixture["test_receipt"]), "--build-receipt", str(fixture["build_receipt"]),
            "--selection", str(fixture["selection_path"]), "--base-url", base_url,
            "--page", "dashboard-home", "--output", str(output),
        ])
    result = json.loads(output.read_text(encoding="utf-8"))
    assert code == (0 if write_fresh else 1)
    assert result["status"] == ("passed" if write_fresh else "failed")


@pytest.mark.parametrize("error_kind", ["FileNotFoundError", "TimeoutExpired"])
def test_home_cli_preserves_launch_and_timeout_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_kind: str,
) -> None:
    fixture = _fixture(tmp_path)
    output = tmp_path / "acceptance.json"

    def run(command: list[str], **kwargs: object) -> object:
        if error_kind == "TimeoutExpired":
            raise handoff_module.subprocess.TimeoutExpired(command, 150, stderr=b"synthetic timeout diagnostic")
        raise FileNotFoundError("synthetic missing executable")

    monkeypatch.setattr(handoff_module.subprocess, "run", run)
    with _Server(fixture["build"]) as base_url:
        code = handoff_module.main([
            "--repo-root", str(tmp_path), "--source-manifest", str(fixture["source_manifest"]),
            "--test-receipt", str(fixture["test_receipt"]), "--build-receipt", str(fixture["build_receipt"]),
            "--selection", str(fixture["selection_path"]), "--base-url", base_url,
            "--page", "dashboard-home", "--output", str(output),
        ])
    result = json.loads(output.read_text(encoding="utf-8"))
    assert code == 1
    assert result["executed_checks"][0]["error_kind"] == error_kind
    diagnostic = Path(result["executed_checks"][0]["stderr_path"])
    assert diagnostic.is_file()
    if error_kind == "TimeoutExpired":
        assert diagnostic.read_bytes() == b"synthetic timeout diagnostic"

