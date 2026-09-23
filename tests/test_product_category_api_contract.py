"""HTTP response contracts with stubbed services; no business storage or jobs run."""

from __future__ import annotations

import copy
import importlib
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient

from backend.app.security.auth_context import AuthContext
from scripts.api_contract_check import diff_contracts


@pytest.fixture
def contract_client(monkeypatch, tmp_path):
    route = importlib.import_module("backend.app.api.routes.product_category_pnl")
    service = importlib.import_module("backend.app.services.product_category_pnl_service")
    monkeypatch.setattr(route, "get_settings", lambda: SimpleNamespace(duckdb_path=tmp_path / "unused.duckdb"))
    # Authorization is outside this schema-only fixture; route/auth regressions
    # are exercised separately in test_product_category_pnl_flow.py.
    monkeypatch.setattr(route, "ensure_user_allowed", lambda **_kwargs: None)
    app = FastAPI()
    app.dependency_overrides[route.get_auth_context] = lambda: AuthContext(user_id="contract-test")
    app.include_router(route.router)
    with TestClient(app) as client:
        yield client, route, service


def _refresh_receipt(status: str) -> dict[str, object]:
    return {
        "status": status,
        "run_id": "pcp-contract-run",
        "job_name": "product_category_pnl",
        "trigger_mode": "async" if status in {"queued", "running"} else "terminal",
        "cache_key": "product_category_pnl.formal",
        "lock": "lock:duckdb:product-category-pnl",
        "source_version": "sv_contract",
        "vendor_version": "vv_none",
        "rule_version": None,
        "queued_at": "2026-02-28T09:00:00+00:00",
        "error_message": "build failed" if status == "failed" else None,
        "failure_reason": "fixture_failure" if status == "failed" else None,
        "idempotency_key": "contract-request",
        "idempotency_replay": False,
        "receipt_extension": {"zero": 0, "nullable": None},
    }


@pytest.mark.parametrize("status", ["queued", "running", "completed", "failed"])
@pytest.mark.parametrize("path", ["/refresh", "/refresh-status"])
def test_refresh_contract_preserves_receipt(contract_client, monkeypatch, status, path):
    client, route, service = contract_client
    expected = _refresh_receipt(status)
    if path == "/refresh":
        monkeypatch.setattr(route, "refresh_product_category_pnl", lambda *_a, **_kw: expected)
        response = client.post("/ui/pnl/product-category/refresh")
    else:
        monkeypatch.setattr(service, "product_category_refresh_status", lambda *_a, **_kw: expected)
        response = client.get("/ui/pnl/product-category/refresh-status", params={"run_id": "pcp-contract-run"})
    assert response.status_code == 200
    assert response.json() == expected


def test_refresh_contract_preserves_sync_fallback_and_omitted_fields(contract_client, monkeypatch):
    client, route, _ = contract_client
    expected = {
        "status": "completed", "run_id": "pcp-contract-run", "job_name": "product_category_pnl",
        "trigger_mode": "sync-fallback", "month_count": 0, "report_dates": [],
        "idempotency_key": None, "idempotency_replay": False,
    }
    monkeypatch.setattr(route, "refresh_product_category_pnl", lambda *_a, **_kw: expected)
    response = client.post("/ui/pnl/product-category/refresh")
    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.parametrize("path", ["/refresh", "/refresh-status"])
@pytest.mark.parametrize("drift", ["missing-run", "invalid-status"])
def test_refresh_contract_rejects_broken_receipt(contract_client, monkeypatch, path, drift):
    client, route, service = contract_client
    receipt = _refresh_receipt("queued")
    if drift == "missing-run":
        del receipt["run_id"]
    else:
        receipt["status"] = "typo-completed"
    monkeypatch.setattr(route, "refresh_product_category_pnl", lambda *_a, **_kw: receipt)
    monkeypatch.setattr(service, "product_category_refresh_status", lambda *_a, **_kw: receipt)
    with pytest.raises(ResponseValidationError):
        if path == "/refresh":
            client.post("/ui/pnl/product-category/refresh")
        else:
            client.get("/ui/pnl/product-category/refresh-status", params={"run_id": "pcp-contract-run"})


def _incomplete_attribution():
    return {
        "result_meta": {
            "basis": "formal", "scenario_flag": False, "quality_flag": "warning",
            "source_version": "sv_contract", "extension": {"zero": 0, "null": None},
        },
        "result": {
            "report_date": "2026-02-28", "compare": "mom", "current_report_date": "2026-02-28",
            "prior_report_date": "2026-01-31", "state": "incomplete", "reason": "no_prior_month",
            "rows": [], "totals": None,
        },
    }


@pytest.mark.parametrize("history", [False, True])
def test_attribution_contract_preserves_incomplete_periods(contract_client, monkeypatch, history):
    client, route, _ = contract_client
    expected = _incomplete_attribution()
    path = "/attribution"
    params = {"report_date": "2026-02-28"}
    service_name = "product_category_attribution_envelope"
    if history:
        expected = {
            "result_meta": copy.deepcopy(expected["result_meta"]),
            "result": {"compare": "mom", "items": [
                {"report_date": "2026-02-28", "status": "ok", **expected},
                {"report_date": "2026-01-31", "status": "not_found", "detail": "not materialized", "result": None, "result_meta": None},
            ]},
        }
        path = "/attribution/history"
        params = {"report_dates": "2026-02-28,2026-01-31"}
        service_name = "product_category_attribution_history_envelope"
    monkeypatch.setattr(route, service_name, lambda *_a, **_kw: expected)
    response = client.get(f"/ui/pnl/product-category{path}", params=params)
    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.parametrize("path,method,schema,field", [
    ("", "get", "ProductCategoryPnlRow", "business_net_income"),
    ("/history", "get", "ProductCategoryHistoryItem", "status"),
    ("/attribution", "get", "ProductCategoryAttributionPayload", "state"),
    ("/attribution/history", "get", "ProductCategoryAttributionHistoryItem", "status"),
    ("/refresh", "post", "ProductCategoryRefreshPayload", "run_id"),
    ("/refresh-status", "get", "ProductCategoryRefreshPayload", "status"),
])
def test_openapi_gate_detects_removed_product_category_fields(contract_client, path, method, schema, field):
    client, _, _ = contract_client
    baseline = client.get("/openapi.json").json()
    operation = f"{method.upper()} /ui/pnl/product-category{path}"
    response = baseline["paths"][f"/ui/pnl/product-category{path}"][method]["responses"]["200"]
    assert "$ref" in response["content"]["application/json"]["schema"]
    changed = copy.deepcopy(baseline)
    payload = changed["components"]["schemas"][schema]
    del payload["properties"][field]
    if field in payload.get("required", []):
        payload["required"].remove(field)
    breaking = [finding for finding in diff_contracts("default", baseline, changed)
                if finding["severity"] == "breaking" and finding["operation"] == operation]
    assert any(finding["kind"] == "response_field_removed" and field in finding["target"]
               for finding in breaking)


def test_named_contracts_are_coverage_gains_without_baseline_acknowledgements(contract_client):
    client, _, _ = contract_client
    current = client.get("/openapi.json").json()
    prior = copy.deepcopy(current)
    operations = [("/attribution", "get"), ("/attribution/history", "get"),
                  ("/refresh", "post"), ("/refresh-status", "get")]
    for path, method in operations:
        response = prior["paths"][f"/ui/pnl/product-category{path}"][method]["responses"]["200"]
        response["content"]["application/json"]["schema"] = {"type": "object", "additionalProperties": True}
    findings = diff_contracts("default", prior, current)
    assert not [finding for finding in findings if finding["severity"] == "breaking"]
    assert {finding["operation"] for finding in findings if finding["kind"] == "response_contract_tightened"} == {
        f"{method.upper()} /ui/pnl/product-category{path}" for path, method in operations
    }
