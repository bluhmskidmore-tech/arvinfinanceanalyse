from __future__ import annotations

import copy
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from scripts import verify_home_runtime_contract as guard


@pytest.fixture
def expectation_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "schema.py").write_text("# isolated expected schema\n", encoding="utf-8")
    monkeypatch.setattr(guard, "CONTRACT_SOURCE_PATHS", ("schema.py",))
    # Small synthetic payload obligations isolate guard behavior. The current
    # application's full twenty-path obligations are checked independently below.
    monkeypatch.setattr(
        guard, "HOME_CONSUMED_FIELDS",
        {path: ("result.principal_evidence", "result.title") for path in guard.HOME_CONSUMED_FIELDS},
    )
    return tmp_path


@pytest.fixture
def spec() -> dict[str, Any]:
    response = {"200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Envelope"}}}}}
    return {
        "openapi": "3.1.0",
        "paths": {path: {"get": {"responses": copy.deepcopy(response)}} for path in guard.HOME_GET_PATHS},
        "components": {
            "schemas": {
                "Envelope": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["result", "result_meta"],
                    "properties": {
                        "result": {"$ref": "#/components/schemas/FourEffects"},
                        "result_meta": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "basis": {"type": "string"},
                                "quality_flag": {"type": "string"},
                                "formal_use_allowed": {"type": "boolean"},
                                "filters_applied": {"type": "object", "additionalProperties": True},
                            },
                        },
                    },
                },
                "FourEffects": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "principal_evidence": {"anyOf": [{"$ref": "#/components/schemas/Evidence"}, {"type": "null"}]},
                        "title": {"type": "string"},
                    },
                },
                "Evidence": {"type": "object", "properties": {"source": {"type": "string"}}},
            },
        },
    }


@contextmanager
def live_openapi(
    payload: dict[str, Any] | bytes,
    *,
    content_type: str = "application/json",
    status: int = 200,
    location: str | None = None,
) -> Iterator[tuple[str, list[str]]]:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            if location:
                self.send_header("Location", location)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def check(base_url: str, spec: dict[str, Any], source_root: Path, **kwargs: Any) -> dict[str, Any]:
    return guard.verify_home_runtime_contract(
        base_url, expected_loader=lambda: spec, source_root=source_root, timeout=0.5, **kwargs
    )


def test_current_home_scope_passes_without_recording_openapi_or_business_payload(
    spec: dict[str, Any], expectation_source: Path
) -> None:
    with live_openapi(spec) as (base_url, requests):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "passed"
    assert receipt["receipt_kind"] == "dashboard_home_backend_contract"
    assert receipt["scope"] == "dashboard-home-desktop"
    assert receipt["schema_version"] == 1
    assert receipt["checked_paths"] == list(guard.HOME_GET_PATHS)
    assert receipt["expected_contract_sha256"] == receipt["observed_contract_sha256"]
    assert len(receipt["expected_contract_sha256"]) == 64
    assert receipt["source_stable"] is True
    assert receipt["source_files"][0]["path"] == "schema.py"
    assert receipt["failures"] == []
    assert receipt["coverage_gaps"] == []
    assert requests == ["/openapi.json"]
    assert "principal_evidence" not in json.dumps(receipt)
    assert "implementation" in receipt["limitations"][0]


def test_old_strict_schema_missing_principal_evidence_cannot_pass(
    spec: dict[str, Any], expectation_source: Path
) -> None:
    old = copy.deepcopy(spec)
    del old["components"]["schemas"]["FourEffects"]["properties"]["principal_evidence"]
    with live_openapi(old) as (base_url, _):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "failed"
    assert receipt["expected_contract_sha256"] != receipt["observed_contract_sha256"]
    assert "running GET response contract differs: /api/pnl-attribution/campisi/four-effects" in receipt["failures"]


@pytest.mark.parametrize(
    "change", ["missing_route", "missing_ref", "external_ref", "missing_shape", "typed_shape_lost", "extra_allowed"]
)
def test_incomplete_or_changed_response_contract_is_failed(
    change: str, spec: dict[str, Any], expectation_source: Path
) -> None:
    observed = copy.deepcopy(spec)
    if change == "missing_route":
        del observed["paths"]["/ui/home/research-reports"]
    elif change == "missing_ref":
        del observed["components"]["schemas"]["Evidence"]
    elif change == "external_ref":
        observed["components"]["schemas"]["Evidence"] = {"$ref": "https://example.invalid/schema.json"}
    elif change == "missing_shape":
        observed["paths"]["/ui/home/snapshot"]["get"]["responses"]["200"] = {"description": "OK"}
    elif change == "typed_shape_lost":
        observed["paths"]["/ui/home/snapshot"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] = {}
    else:
        observed["components"]["schemas"]["FourEffects"]["additionalProperties"] = True
    with live_openapi(observed) as (base_url, _):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "failed"
    assert receipt["failures"]


def test_irrelevant_routes_schemas_and_annotations_do_not_fail(
    spec: dict[str, Any], expectation_source: Path
) -> None:
    observed = copy.deepcopy(spec)
    observed["components"]["schemas"]["Unrelated"] = {"type": "number"}
    observed["paths"]["/api/unrelated"] = {"get": {"responses": {}}}
    observed["components"]["schemas"]["Evidence"]["description"] = "Changed documentation"
    observed["components"]["schemas"]["Evidence"]["title"] = "Changed title annotation"
    with live_openapi(observed) as (base_url, _):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "passed"


@pytest.mark.parametrize(
    "schema",
    [{}, {"type": "object", "additionalProperties": True}, {"type": "array", "items": {"type": "object", "additionalProperties": True}}],
)
def test_matching_opaque_roots_cannot_pass_after_home_contract_closure(
    schema: dict[str, Any], spec: dict[str, Any], expectation_source: Path
) -> None:
    path = "/api/bond-analytics/top-holdings"
    spec["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]["schema"] = schema
    with live_openapi(spec) as (base_url, _):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "failed"
    assert len(receipt["coverage_gaps"]) == 1
    assert path in receipt["coverage_gaps"][0]
    assert "no named root response fields" in receipt["coverage_gaps"][0]
    assert receipt["observed_contract_sha256"] is None


@pytest.mark.parametrize("shape", [{}, {"type": "object", "additionalProperties": True}, {"type": "array", "items": {}}])
def test_matching_named_envelope_with_opaque_consumed_field_cannot_pass(
    shape: dict[str, Any], spec: dict[str, Any], expectation_source: Path
) -> None:
    spec["components"]["schemas"]["FourEffects"]["properties"]["principal_evidence"] = shape
    with live_openapi(spec) as (base_url, _):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "failed"
    assert receipt["coverage_gaps"]
    assert any("result.principal_evidence" in gap for gap in receipt["coverage_gaps"])


def test_named_envelope_cannot_hide_a_free_form_result(spec: dict[str, Any], expectation_source: Path) -> None:
    spec["components"]["schemas"]["Envelope"]["properties"]["result"] = {
        "type": "object", "additionalProperties": True,
    }
    with live_openapi(spec) as (base_url, _):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "failed"
    assert any("result.title" in gap for gap in receipt["coverage_gaps"])


def test_declared_nullable_type_and_dynamic_metadata_remain_supported(
    spec: dict[str, Any], expectation_source: Path
) -> None:
    spec["components"]["schemas"]["FourEffects"]["properties"]["title"] = {"type": ["string", "null"]}
    with live_openapi(spec) as (base_url, _):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "passed"
    assert receipt["coverage_gaps"] == []


def test_current_app_openapi_can_extract_home_scope_without_lifespan() -> None:
    # The established exporter imports main/OpenAPI only. It never enters
    # lifespan or calls a route, so no database is opened or business rows read.
    current = guard._load_openapi("current")
    contract = guard.extract_home_response_contract(current)
    gaps = guard._coverage_gaps(current)
    assert set(contract["paths"]) == set(guard.HOME_GET_PATHS)
    assert gaps == []
    assert len(guard.HOME_CONSUMED_FIELDS) == 13
    assert {
        "backend/app/schemas/home_bond_read_contracts.py",
        "backend/app/schemas/home_support_read_contracts.py",
        "backend/app/schemas/macro_vendor.py",
        "backend/app/schemas/research_calendar.py",
    } <= set(guard.CONTRACT_SOURCE_PATHS)
    campisi = contract["paths"]["/api/pnl-attribution/campisi/four-effects"]
    assert "principal_evidence" in json.dumps(campisi)
    assert "\"additionalProperties\": false" in json.dumps(campisi)


def test_property_named_title_is_part_of_the_response_shape(
    spec: dict[str, Any], expectation_source: Path
) -> None:
    observed = copy.deepcopy(spec)
    observed["components"]["schemas"]["FourEffects"]["properties"]["title"] = {"type": "number"}
    with live_openapi(observed) as (base_url, _):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "failed"


def test_cyclic_transitive_references_are_checked_and_finite(spec: dict[str, Any], expectation_source: Path) -> None:
    spec["components"]["schemas"]["Evidence"]["properties"]["parent"] = {"$ref": "#/components/schemas/Evidence"}
    with live_openapi(spec) as (base_url, _):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "passed"


@pytest.mark.parametrize(
    ("body", "content_type"),
    [(b"not JSON", "application/json"), (b"{}", "text/html"), (b"[]", "application/json")],
)
def test_non_openapi_response_is_failed(
    body: bytes, content_type: str, spec: dict[str, Any], expectation_source: Path
) -> None:
    with live_openapi(body, content_type=content_type) as (base_url, _):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "failed"
    assert receipt["observed_contract_sha256"] is None


def test_redirect_is_failed_without_following_it(spec: dict[str, Any], expectation_source: Path) -> None:
    with live_openapi(spec, status=302, location="http://example.invalid/openapi.json") as (base_url, requests):
        receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "failed"
    assert receipt["failures"] == ["live OpenAPI redirected"]
    assert requests == ["/openapi.json"]


def test_unreachable_local_api_is_failed(spec: dict[str, Any], expectation_source: Path) -> None:
    with live_openapi(spec) as (base_url, _):
        pass
    receipt = check(base_url, spec, expectation_source)
    assert receipt["status"] == "failed"
    assert receipt["failures"] == ["live OpenAPI is unreachable or timed out"]


@pytest.mark.parametrize(
    "base_url",
    ["http://example.invalid", "http://user:secret@127.0.0.1:7888", "http://127.0.0.1:7888/api", "file:///local"],
)
def test_only_local_origins_are_accepted_without_echoing_credentials(base_url: str, expectation_source: Path) -> None:
    def unexpected_loader() -> dict[str, Any]:
        raise AssertionError("invalid origin must be rejected before export or network")

    receipt = guard.verify_home_runtime_contract(base_url, expected_loader=unexpected_loader, source_root=expectation_source)
    assert receipt["status"] == "failed"
    assert receipt["base_url"] is None
    assert "secret" not in json.dumps(receipt)


def test_source_drift_during_export_is_failed_before_network(spec: dict[str, Any], expectation_source: Path) -> None:
    def changing_loader() -> dict[str, Any]:
        (expectation_source / "schema.py").write_text("# changed during export\n", encoding="utf-8")
        return spec

    receipt = guard.verify_home_runtime_contract(
        "http://127.0.0.1:1", expected_loader=changing_loader, source_root=expectation_source
    )
    assert receipt["status"] == "failed"
    assert receipt["source_stable"] is False
    assert receipt["failures"] == ["expected contract source files changed during export"]


def test_cli_writes_the_receipt_and_returns_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt = {"status": "failed", "failures": ["synthetic contract mismatch"]}
    monkeypatch.setattr(guard, "verify_home_runtime_contract", lambda *args, **kwargs: receipt)
    output = tmp_path / "receipt.json"
    assert guard.main(["--output", str(output)]) == 1
    assert json.loads(output.read_text(encoding="utf-8")) == receipt
