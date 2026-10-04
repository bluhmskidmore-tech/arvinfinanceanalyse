"""Explicit desktop home response contracts, using synthetic local payloads only."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
import uuid

import pytest
from fastapi import FastAPI
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.executive_dashboard import (
    HomeIncomeTrendPayload,
    HomeResearchReportsPayload,
    HomeSnapshotPayload,
)
from backend.app.schemas.result_meta import ResultMeta
from tests.helpers import load_module

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_executive]

REPORT_DATE = "2026-08-31"
PATHS = ("/ui/home/snapshot", "/ui/home/income-trend", "/ui/home/research-reports")
HANDLERS = ("home_snapshot_envelope", "home_income_trend_envelope", "home_research_reports_envelope")
KINDS = ("home.snapshot", "home.income_trend", "home.research_reports")


def _numeric(raw: float | None = None) -> dict[str, object]:
    return Numeric(raw=Decimal(str(raw)) if raw is not None else None, unit="yuan", display="—" if raw is None else "+1.25", precision=2, sign_aware=True).model_dump(mode="json")


def _payload(index: int, state: str = "ready") -> dict[str, object]:
    partial = state == "partial"
    if index == 0:
        result = HomeSnapshotPayload.model_validate({
            "report_date": REPORT_DATE,
            "mode": "partial" if partial else "strict",
            "source_surface": "executive_analytical",
            "overview": {"title": "Synthetic overview", "metrics": [{
                "id": "aum", "label": "Synthetic asset", "value": _numeric(1.25),
                "delta": _numeric(), "tone": "neutral", "detail": "Synthetic fixture", "history": None,
            }]},
            "attribution": {"title": "Synthetic attribution", "total": _numeric(), "segments": []},
            "domains_missing": ["pnl"] if partial else [],
            "domains_effective_date": {"balance_sheet": REPORT_DATE} if partial else {"balance_sheet": REPORT_DATE, "pnl": REPORT_DATE},
            "verdict": None if partial else {
                "conclusion": "Synthetic conclusion", "tone": "neutral",
                "reasons": [{"label": "Synthetic", "value": "1.25", "detail": "Synthetic fixture", "tone": "neutral"}],
                "suggestions": [{"text": "Synthetic drill", "link": "/product-category-pnl"}],
            },
            "product_category_ytd": None if partial else {
                "view": "ytd", "summary_pnl": _numeric(1.25), "summary_pnl_detail": "Synthetic detail",
                "operating_income": _numeric(1.25), "operating_income_detail": "Synthetic detail",
                "intermediate_business_income": _numeric(), "intermediate_business_income_detail": "Synthetic gap",
            },
            "product_category_monthly": None if partial else {
                "view": "monthly", "monthly_income": _numeric(1.25), "monthly_income_detail": "Synthetic detail",
            },
        }).model_dump(mode="json")
    elif index == 1:
        result = HomeIncomeTrendPayload.model_validate({
            "report_date": REPORT_DATE, "window": 7,
            "source_status": state if state in {"partial", "empty"} else "ready",
            "points": [] if state == "empty" else [{
                "date": REPORT_DATE, "portfolio_pnl": _numeric(1.25),
                "benchmark_pnl": _numeric(None if partial else 1.25),
                "excess_pnl": _numeric(None if partial else 0.0),
                "basis": "product_category_pnl_monthly", "source_status": "partial" if partial else "ready",
            }],
            "missing_components": ["benchmark_pnl", "excess_pnl"] if partial else [],
            "warnings": [] if state == "ready" else ["Synthetic source gap"],
        }).model_dump(mode="json")
    else:
        result = HomeResearchReportsPayload.model_validate({
            "report_date": REPORT_DATE, "source_status": state,
            "items": [] if state == "empty" else [{
                "id": "synthetic-report", "title": "Synthetic report", "category": "rates",
                "published_at": "2026-08-30T12:00:00", "link": None, "source": "synthetic",
                "institution": "Synthetic institution", "source_status": state, "summary": "Synthetic report summary",
            }],
            "warnings": [] if state == "ready" else ["Synthetic source gap"],
        }).model_dump(mode="json")
    meta = ResultMeta(
        trace_id="tr_home_contract_synthetic", basis="analytical", result_kind=KINDS[index],
        formal_use_allowed=False, source_version="sv_synthetic", rule_version="rv_synthetic",
        cache_version="cv_synthetic", source_surface="executive_analytical",
        quality_flag="ok" if state == "ready" else "warning",
        vendor_status="vendor_unavailable" if state == "empty" else "vendor_stale" if state == "stale" else "ok",
        fallback_mode="latest_snapshot" if state == "stale" else "none",
        requested_report_date=REPORT_DATE, resolved_report_date=REPORT_DATE,
        as_of_date=REPORT_DATE, date_basis="synthetic.report_date", fallback_date=REPORT_DATE if state == "stale" else None,
        generated_at=datetime(2026, 8, 31, tzinfo=UTC),
        filters_applied={"report_date": REPORT_DATE, "degraded_components": ["pnl"] if partial else [], "diagnostic": {"available": not partial}},
    ).model_dump(mode="json")
    meta["additional_lineage_hint"] = {"source_status": state}
    return {"result_meta": meta, "result": result}


def _client(monkeypatch, index: int, payload: dict[str, object]) -> TestClient:
    route = load_module(f"tests._home_contract.executive_{uuid.uuid4().hex}", "backend/app/api/routes/executive.py")
    monkeypatch.setattr(route, "_ensure_executive_read_allowed", lambda _auth: None)
    monkeypatch.setattr(route, HANDLERS[index], lambda **_kwargs: deepcopy(payload))
    # Keep this route probe independent from the process-wide response cache.
    monkeypatch.setattr(route.market_home_response_cache, "get_or_build", lambda _key, build: build())
    app = FastAPI()
    app.dependency_overrides[route.get_auth_context] = lambda: object()
    app.include_router(route.router)
    return TestClient(app)


def _resolve(schema: dict[str, object], document: dict[str, object]) -> dict[str, object]:
    while "$ref" in schema:
        ref = str(schema["$ref"])
        assert ref.startswith("#/components/schemas/")
        schema = document["components"]["schemas"][ref.rsplit("/", 1)[1]]
    return schema


@pytest.mark.parametrize("index", range(3))
def test_home_openapi_exposes_required_payload_and_consumed_fields(monkeypatch, index):
    client = _client(monkeypatch, index, _payload(index))
    document = client.app.openapi()
    root = _resolve(document["paths"][PATHS[index]]["get"]["responses"]["200"]["content"]["application/json"]["schema"], document)
    assert root["required"] == ["result_meta", "result"]
    result = _resolve(root["properties"]["result"], document)
    required = [{"report_date", "mode", "source_surface", "overview", "attribution", "domains_missing", "domains_effective_date"}, {"report_date", "window", "source_status"}, {"report_date", "source_status"}][index]
    assert required <= set(result["required"])
    consumed = [{"verdict", "product_category_ytd", "product_category_monthly"}, {"points", "missing_components", "warnings"}, {"items", "warnings"}][index]
    assert consumed <= set(result["properties"])
    if index == 1:
        point = _resolve(result["properties"]["points"]["items"], document)
        number = _resolve(point["properties"]["benchmark_pnl"], document)
        assert {"raw", "unit", "display", "precision", "sign_aware"} <= set(number["required"])


@pytest.mark.parametrize("index", range(3))
def test_home_http_rejects_missing_required_result_fields(monkeypatch, index):
    payload = _payload(index)
    del payload["result"]["report_date"]
    client = _client(monkeypatch, index, payload)
    with pytest.raises(ResponseValidationError):
        client.get(PATHS[index], params={"report_date": REPORT_DATE})


@pytest.mark.parametrize("index,state", [(0, "ready"), (0, "partial"), (1, "ready"), (1, "partial"), (1, "empty"), (2, "ready"), (2, "empty"), (2, "stale")])
def test_home_http_keeps_existing_null_empty_partial_stale_payloads(monkeypatch, index, state):
    payload = _payload(index, state)
    response = _client(monkeypatch, index, payload).get(PATHS[index], params={"report_date": REPORT_DATE, "allow_partial": state == "partial"})
    assert response.status_code == 200
    assert response.json() == payload


@pytest.mark.parametrize("index,field,bad", [(0, "overview", []), (1, "points", [{"date": REPORT_DATE}]), (2, "items", [{"id": "synthetic"}])])
def test_home_envelope_rejects_malformed_nested_consumed_fields(index, field, bad):
    from backend.app.schemas.executive_dashboard import HomeIncomeTrendEnvelope, HomeResearchReportsEnvelope, HomeSnapshotEnvelope
    payload = _payload(index)
    payload["result"][field] = bad
    with pytest.raises(ValidationError):
        (HomeSnapshotEnvelope, HomeIncomeTrendEnvelope, HomeResearchReportsEnvelope)[index].model_validate(payload)


def test_home_income_contract_rejects_unknown_source_status_without_defaulting_to_zero():
    from backend.app.schemas.executive_dashboard import HomeIncomeTrendEnvelope
    payload = _payload(1, "partial")
    payload["result"]["points"][0]["source_status"] = "ready-ish"
    with pytest.raises(ValidationError):
        HomeIncomeTrendEnvelope.model_validate(payload)
