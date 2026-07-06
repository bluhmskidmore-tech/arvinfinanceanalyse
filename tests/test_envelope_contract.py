from __future__ import annotations

import importlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.schemas.executive_dashboard import ExecutiveOverviewEnvelope
from backend.app.schemas.pnl_attribution import (
    CampisiAttributionPayload,
    CampisiAttributionEnvelope,
    PnlAttributionAnalysisSummary,
    PnlAttributionAnalysisSummaryEnvelope,
)
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV, AuthContext
from tests.helpers import load_module

READ_HEADERS = {"X-User-Id": "envelope-contract-user", "X-User-Role": "viewer"}

ENDPOINT_CONTRACTS = [
    ("/api/pnl-attribution/advanced/campisi", {"lookback_days": 7}, CampisiAttributionEnvelope),
    ("/api/pnl-attribution/summary", None, PnlAttributionAnalysisSummaryEnvelope),
    ("/ui/home/overview", None, ExecutiveOverviewEnvelope),
]


def _configure_runtime(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    governance_dir = tmp_path / "gov"
    scope_db = tmp_path / "envelope-contract-scope.db"

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{scope_db.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()

    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo = repo_module.UserScopeRepository(f"sqlite:///{scope_db.as_posix()}")
    repo.grant_scope(user_id="*", role=None, resource="executive", action="read")
    repo.grant_scope(user_id="*", role=None, resource="pnl_attribution", action="read")


def _main_app_client(tmp_path, monkeypatch) -> TestClient:
    _configure_runtime(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    client.headers.update(READ_HEADERS)
    return client


def _pnl_route_client(tmp_path, monkeypatch):
    _configure_runtime(tmp_path, monkeypatch)
    route_module = load_module(
        "backend.app.api.routes.pnl_attribution",
        "backend/app/api/routes/pnl_attribution.py",
    )
    monkeypatch.setattr(route_module, "_ensure_pnl_attribution_read_allowed", lambda _auth: None)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    client.headers.update(READ_HEADERS)
    return route_module, client


def _numeric(raw: float, unit: str, display: str, *, precision: int = 2, sign_aware: bool = True) -> dict[str, object]:
    return {
        "raw": raw,
        "unit": unit,
        "display": display,
        "precision": precision,
        "sign_aware": sign_aware,
    }


@pytest.mark.parametrize(("path", "params", "schema_cls"), ENDPOINT_CONTRACTS)
def test_scoped_endpoints_validate_against_typed_envelopes(path, params, schema_cls, tmp_path, monkeypatch) -> None:
    client = _main_app_client(tmp_path, monkeypatch)

    response = client.get(path, params=params)

    assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"
    body = response.json()
    meta = body["result_meta"]
    assert meta["source_version"]
    assert meta["rule_version"]
    assert meta["cache_version"]
    assert meta["basis"]
    envelope = schema_cls.model_validate(body)
    assert envelope.result_meta.source_version == meta["source_version"]

    get_settings.cache_clear()


def test_openapi_includes_scoped_envelope_components(tmp_path, monkeypatch) -> None:
    _configure_runtime(tmp_path, monkeypatch)
    openapi = load_module("backend.app.main", "backend/app/main.py").app.openapi()
    schemas = openapi["components"]["schemas"]

    assert "CampisiAttributionEnvelope" in schemas
    assert "PnlAttributionAnalysisSummaryEnvelope" in schemas
    assert "ExecutiveOverviewEnvelope" in schemas

    get_settings.cache_clear()


def test_home_overview_response_model_preserves_response_bytes(tmp_path, monkeypatch) -> None:
    _configure_runtime(tmp_path, monkeypatch)
    route_module = load_module(
        "backend.app.api.routes.executive",
        "backend/app/api/routes/executive.py",
    )
    executive_service = importlib.import_module("backend.app.services.executive_service")
    service_payload = executive_service.executive_overview(report_date=None)

    monkeypatch.setattr(route_module, "executive_overview", lambda report_date=None: service_payload)

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    client.headers.update(READ_HEADERS)

    route_payload = route_module.overview(
        auth=AuthContext(
            user_id=READ_HEADERS["X-User-Id"],
            role=READ_HEADERS["X-User-Role"],
            identity_source="header",
        ),
        report_date=None,
    )
    expected_bytes = json.dumps(
        route_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    response = client.get("/ui/home/overview")

    assert response.status_code == 200, response.text
    assert response.content == expected_bytes

    get_settings.cache_clear()


def test_summary_schema_dump_omits_warnings_when_input_omits_it() -> None:
    payload = PnlAttributionAnalysisSummary.model_validate(
        {
            "report_date": "2026-04-30",
            "primary_driver": "volume",
            "primary_driver_pct": _numeric(0.25, "pct", "+25.00%"),
            "key_findings": ["clean-summary"],
            "tpl_market_aligned": True,
            "tpl_market_note": "aligned",
        }
    ).model_dump(mode="json")

    assert "warnings" not in payload


def test_summary_schema_dump_preserves_warnings_when_input_includes_it() -> None:
    payload = PnlAttributionAnalysisSummary.model_validate(
        {
            "report_date": "2026-04-30",
            "primary_driver": "unknown",
            "primary_driver_pct": _numeric(0.0, "pct", "+0.00%"),
            "key_findings": ["warn-summary"],
            "tpl_market_aligned": False,
            "tpl_market_note": "warning-path",
            "warnings": ["materialization warning"],
        }
    ).model_dump(mode="json")

    assert payload["warnings"] == ["materialization warning"]


def test_campisi_schema_dump_omits_basis_and_warnings_when_input_omits_them() -> None:
    payload = CampisiAttributionPayload.model_validate(
        {
            "report_date": "2026-04-30",
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
            "num_days": 29,
            "total_market_value": _numeric(100.0, "yuan", "100.00", sign_aware=False),
            "total_return": _numeric(1.0, "yuan", "+1.00"),
            "total_return_pct": _numeric(0.01, "pct", "+1.00%"),
            "total_income": _numeric(0.4, "yuan", "+0.40"),
            "total_treasury_effect": _numeric(0.2, "yuan", "+0.20"),
            "total_spread_effect": _numeric(0.2, "yuan", "+0.20"),
            "total_selection_effect": _numeric(0.2, "yuan", "+0.20"),
            "income_contribution_pct": _numeric(0.4, "pct", "+40.00%"),
            "treasury_contribution_pct": _numeric(0.2, "pct", "+20.00%"),
            "spread_contribution_pct": _numeric(0.2, "pct", "+20.00%"),
            "selection_contribution_pct": _numeric(0.2, "pct", "+20.00%"),
            "primary_driver": "income",
            "interpretation": "clean-campisi",
            "items": [],
        }
    ).model_dump(mode="json")

    assert "basis" not in payload
    assert "warnings" not in payload


def test_campisi_schema_dump_preserves_basis_and_warnings_when_input_includes_them() -> None:
    payload = CampisiAttributionPayload.model_validate(
        {
            "report_date": "2026-04-30",
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
            "num_days": 29,
            "basis": "formal_report_pnl_bridge",
            "total_market_value": _numeric(100.0, "yuan", "100.00", sign_aware=False),
            "total_return": _numeric(1.0, "yuan", "+1.00"),
            "total_return_pct": _numeric(0.01, "pct", "+1.00%"),
            "total_income": _numeric(0.4, "yuan", "+0.40"),
            "total_treasury_effect": _numeric(0.2, "yuan", "+0.20"),
            "total_spread_effect": _numeric(0.2, "yuan", "+0.20"),
            "total_selection_effect": _numeric(0.2, "yuan", "+0.20"),
            "income_contribution_pct": _numeric(0.4, "pct", "+40.00%"),
            "treasury_contribution_pct": _numeric(0.2, "pct", "+20.00%"),
            "spread_contribution_pct": _numeric(0.2, "pct", "+20.00%"),
            "selection_contribution_pct": _numeric(0.2, "pct", "+20.00%"),
            "primary_driver": "income",
            "interpretation": "bridge-campisi",
            "warnings": ["bridge warning"],
            "items": [],
        }
    ).model_dump(mode="json")

    assert payload["basis"] == "formal_report_pnl_bridge"
    assert payload["warnings"] == ["bridge warning"]


def test_summary_response_model_omits_warnings_when_service_omits_it(tmp_path, monkeypatch) -> None:
    route_module, client = _pnl_route_client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        route_module,
        "attribution_analysis_summary_envelope",
        lambda report_date=None: {
            "result_meta": {
                "trace_id": "tr_summary_clean",
                "basis": "formal",
                "result_kind": "pnl_attribution.summary",
                "formal_use_allowed": True,
                "source_version": "sv_summary_clean",
                "vendor_version": "vv_none",
                "rule_version": "rv_summary_clean",
                "cache_version": "cv_summary_clean",
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "scenario_flag": False,
                "filters_applied": {},
                "tables_used": [],
                "next_drill": [],
                "source_surface": "formal_pnl",
            },
            "result": {
                "report_date": "2026-04-30",
                "primary_driver": "volume",
                "primary_driver_pct": {
                    "raw": 0.25,
                    "unit": "pct",
                    "display": "+25.00%",
                    "precision": 2,
                    "sign_aware": True,
                },
                "key_findings": ["clean-summary"],
                "tpl_market_aligned": True,
                "tpl_market_note": "aligned",
            },
        },
    )

    response = client.get("/api/pnl-attribution/summary")

    assert response.status_code == 200, response.text
    body = response.json()
    assert "warnings" not in body["result"]

    get_settings.cache_clear()


def test_summary_response_model_preserves_warnings_when_service_includes_it(tmp_path, monkeypatch) -> None:
    route_module, client = _pnl_route_client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        route_module,
        "attribution_analysis_summary_envelope",
        lambda report_date=None: {
            "result_meta": {
                "trace_id": "tr_summary_warn",
                "basis": "formal",
                "result_kind": "pnl_attribution.summary",
                "formal_use_allowed": True,
                "source_version": "sv_summary_warn",
                "vendor_version": "vv_none",
                "rule_version": "rv_summary_warn",
                "cache_version": "cv_summary_warn",
                "quality_flag": "warning",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "scenario_flag": False,
                "filters_applied": {},
                "tables_used": [],
                "next_drill": [],
                "source_surface": "formal_pnl",
            },
            "result": {
                "report_date": "2026-04-30",
                "primary_driver": "unknown",
                "primary_driver_pct": {
                    "raw": 0.0,
                    "unit": "pct",
                    "display": "+0.00%",
                    "precision": 2,
                    "sign_aware": True,
                },
                "key_findings": ["warn-summary"],
                "tpl_market_aligned": False,
                "tpl_market_note": "warning-path",
                "warnings": ["materialization warning"],
            },
        },
    )

    response = client.get("/api/pnl-attribution/summary")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result"]["warnings"] == ["materialization warning"]

    get_settings.cache_clear()


def test_campisi_response_model_preserves_result_basis_when_service_includes_it(tmp_path, monkeypatch) -> None:
    route_module, client = _pnl_route_client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        route_module,
        "campisi_attribution_envelope",
        lambda start_date=None, end_date=None, lookback_days=30: {
            "result_meta": {
                "trace_id": "tr_campisi_basis",
                "basis": "formal",
                "result_kind": "pnl_attribution.campisi",
                "formal_use_allowed": True,
                "source_version": "sv_campisi_basis",
                "vendor_version": "vv_none",
                "rule_version": "rv_campisi_basis",
                "cache_version": "cv_campisi_basis",
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "scenario_flag": False,
                "filters_applied": {},
                "tables_used": [],
                "next_drill": [],
                "source_surface": "formal_pnl",
            },
            "result": {
                "report_date": "2026-04-30",
                "period_start": "2026-04-01",
                "period_end": "2026-04-30",
                "num_days": 29,
                "basis": "formal_report_pnl_bridge",
                "total_market_value": {
                    "raw": 100.0,
                    "unit": "yuan",
                    "display": "100.00",
                    "precision": 2,
                    "sign_aware": False,
                },
                "total_return": {
                    "raw": 1.0,
                    "unit": "yuan",
                    "display": "+1.00",
                    "precision": 2,
                    "sign_aware": True,
                },
                "total_return_pct": {
                    "raw": 0.01,
                    "unit": "pct",
                    "display": "+1.00%",
                    "precision": 2,
                    "sign_aware": True,
                },
                "total_income": {
                    "raw": 0.4,
                    "unit": "yuan",
                    "display": "+0.40",
                    "precision": 2,
                    "sign_aware": True,
                },
                "total_treasury_effect": {
                    "raw": 0.2,
                    "unit": "yuan",
                    "display": "+0.20",
                    "precision": 2,
                    "sign_aware": True,
                },
                "total_spread_effect": {
                    "raw": 0.2,
                    "unit": "yuan",
                    "display": "+0.20",
                    "precision": 2,
                    "sign_aware": True,
                },
                "total_selection_effect": {
                    "raw": 0.2,
                    "unit": "yuan",
                    "display": "+0.20",
                    "precision": 2,
                    "sign_aware": True,
                },
                "income_contribution_pct": {
                    "raw": 0.4,
                    "unit": "pct",
                    "display": "+40.00%",
                    "precision": 2,
                    "sign_aware": True,
                },
                "treasury_contribution_pct": {
                    "raw": 0.2,
                    "unit": "pct",
                    "display": "+20.00%",
                    "precision": 2,
                    "sign_aware": True,
                },
                "spread_contribution_pct": {
                    "raw": 0.2,
                    "unit": "pct",
                    "display": "+20.00%",
                    "precision": 2,
                    "sign_aware": True,
                },
                "selection_contribution_pct": {
                    "raw": 0.2,
                    "unit": "pct",
                    "display": "+20.00%",
                    "precision": 2,
                    "sign_aware": True,
                },
                "primary_driver": "income",
                "interpretation": "formal-bridge",
                "items": [],
            },
        },
    )

    response = client.get("/api/pnl-attribution/advanced/campisi", params={"lookback_days": 7})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result"]["basis"] == "formal_report_pnl_bridge"

    get_settings.cache_clear()
