"""Synthetic wire-equivalence and failure cases for the home bond read DTOs."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient

from backend.app.api.routes import bond_analytics as routes
from backend.app.schemas import bond_analytics as construction
from backend.app.schemas.common_numeric import numeric_from_raw
from backend.app.schemas.result_meta import ResultMeta
from backend.app.schemas.yield_curve_term_structure import (
    YieldCurveTermPoint,
    YieldCurveTermStructureCurve,
    YieldCurveTermStructureResponse,
)
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services.bond_analytics_service import _bond_analytics_api_payload

REPORT_DATE = date(2026, 3, 31)
CASES = [
    ("top-holdings", "get_top_holdings", "items"),
    ("position-changes", "get_position_changes", "source_status"),
    ("portfolio-headlines", "get_portfolio_headlines", "weighted_duration"),
    ("credit-spread-migration", "get_credit_spread_migration", "spread_scenarios"),
    ("return-decomposition", "get_return_decomposition", "actual_pnl"),
    ("yield-curve-term-structure", "get_yield_curve_term_structure", "curves"),
    ("krd-curve-risk", "get_krd_curve_risk", "krd_buckets"),
]


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext()
    return app


def _numeric(raw=Decimal("123.12345678"), unit="yuan"):
    return numeric_from_raw(raw=raw, unit=unit, sign_aware=True).model_dump(mode="json")


def _payloads() -> dict[str, dict]:
    common = {"report_date": REPORT_DATE, "computed_at": "2026-03-31T00:00:00Z", "warnings": []}
    top = construction.BondTopHoldingsResponse(
        **common, top_n=20, total_market_value="123.12345678", items=[{
            "instrument_code": "SYNTHETIC", "asset_class": "rate", "market_value": "123.12345678",
            "face_value": "123.12345678", "ytm": "0.0085", "modified_duration": None,
            "duration_quality_flag": "maturity_unavailable", "maturity_category": "unknown", "weight": "1",
        }],
    )
    changes = construction.BondPositionChangesResponse(
        **common, top_n=5, prev_report_date=None, source_status="empty", items=[],
        total_market_value=_numeric(), prev_total_market_value=_numeric(Decimal("0")),
    )
    headlines = construction.PortfolioHeadlinesResponse(
        **common, total_market_value="123.12345678", weighted_ytm="0.0085", weighted_duration="1.1",
        weighted_coupon="0.01", total_dv01="0", bond_count=1, credit_weight="0", issuer_hhi="1",
        issuer_top5_weight="1", by_asset_class=[{
            "asset_class": "rate", "market_value": "123.12345678", "duration": "1.1", "dv01": "0", "weight": "1",
        }],
    )
    credit = construction.CreditSpreadMigrationResponse(
        **common, credit_bond_count=0, credit_market_value="0", credit_weight="0", spread_dv01="0",
        weighted_avg_spread="0", weighted_avg_spread_duration="0", spread_scenarios=[{
            "scenario_name": "synthetic spread +10", "spread_change_bp": _numeric(10, "bp"),
            "pnl_impact": "-0.01", "oci_impact": "-0.01", "tpl_impact": "0",
        }], migration_scenarios=[{
            "scenario_name": "synthetic migration", "from_rating": "AAA", "to_rating": "AA",
            "affected_bonds": 0, "affected_market_value": "0", "pnl_impact": "0", "oci_impact": None,
        }], concentration_by_issuer={
            "dimension": "issuer", "hhi": "1", "top5_concentration": "1", "top_items": [
                {"name": "synthetic issuer", "weight": "1", "market_value": "123.12345678"},
            ],
        }, display_limits={
            "issuer_single_max": 0.1, "issuer_top5_max": 0.4, "hhi_warning": 0.15,
            "below_aa_max": 0.2, "credit_weight_max": 0.85,
        },
    )
    returns = construction.ReturnDecompositionResponse(
        **common, period_type="MoM", period_start=date(2026, 2, 28), period_end=REPORT_DATE,
        carry="123.12345678", roll_down="0", rate_effect="-0.01", spread_effect="0", trading="0",
        explained_pnl="123.11345678", actual_pnl="123.11345678", recon_error="0", recon_error_pct="0",
        warnings_detail=[{"code": "synthetic_partial", "level": "warning", "message": "synthetic"},
                         {"code": "synthetic_gap", "level": "warning", "component": "trading", "detail": "pending"}],
        by_asset_class=[{"asset_class": "rate", "carry": "123.12345678", "market_value": "123.12345678"}],
        by_accounting_class=[{"asset_class": "OCI", "carry": "123.12345678", "market_value": "123.12345678"}],
        bond_details=[{
            "bond_code": "SYNTHETIC", "asset_class": "rate", "accounting_class": "OCI",
            "market_value": "123.12345678", "carry": "123.12345678",
        }],
    )
    curve = YieldCurveTermStructureResponse(
        **common, curves=[YieldCurveTermStructureCurve(
            curve_type="treasury", trade_date_requested=REPORT_DATE.isoformat(), trade_date_resolved=None,
            points=[YieldCurveTermPoint(tenor="1Y", yield_pct=None, delta_bp_prev=None),
                    YieldCurveTermPoint(tenor="5Y", yield_pct=_numeric(0, "pct"), delta_bp_prev=_numeric(None, "bp"))],
        )],
    )
    krd = construction.KRDCurveRiskResponse(
        **common, portfolio_duration="0", portfolio_modified_duration="0", portfolio_dv01="0", portfolio_convexity="0",
        krd_buckets=[{"tenor": "5Y", "avg_modified_duration": "1.1", "dv01": "123.12345678", "market_value_weight": "1"}],
        scenarios=[{
            "scenario_name": "synthetic", "scenario_description": "synthetic", "shocks": {"custom-tenor": -25.0},
            "pnl_economic": "0", "pnl_oci": "0", "pnl_tpl": "0", "rate_contribution": "0", "convexity_contribution": "0",
            "by_asset_class": {"custom-asset": {"pnl_economic": "0", "pnl_oci": "0", "pnl_tpl": "0"}},
        }],
    )
    models = {
        "top-holdings": top, "position-changes": changes, "portfolio-headlines": headlines,
        "credit-spread-migration": credit, "return-decomposition": returns,
        "yield-curve-term-structure": curve, "krd-curve-risk": krd,
    }
    result = {}
    for path, model in models.items():
        payload = model.model_dump(mode="json")
        if path not in {"position-changes", "yield-curve-term-structure"}:
            payload = _bond_analytics_api_payload(payload)
        meta = ResultMeta(
            trace_id="synthetic_contract", source_version="synthetic", rule_version="synthetic", cache_version="synthetic",
            result_kind=f"bond_analytics.{path.replace('-', '_')}", source_surface="bond_analytics",
            generated_at="2026-03-31T00:00:00Z", quality_flag="warning", vendor_status="vendor_unavailable",
            fallback_mode="latest_snapshot", requested_report_date=REPORT_DATE.isoformat(), resolved_report_date="2026-03-30",
        ).model_dump(mode="json")
        result[path] = {"result_meta": meta, "result": payload}
    return result


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes, "_ensure_bond_analytics_read_allowed", lambda _auth: None)
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(duckdb_path="synthetic-no-read.duckdb"))
    monkeypatch.setattr(routes.market_home_response_cache, "get_or_build", lambda _key, build: build())
    return TestClient(_app())


@pytest.mark.parametrize("path,_service,field", CASES)
def test_home_bond_openapi_declares_success_fields(path, _service, field):
    document = _app().openapi()
    schema = document["paths"][f"/api/bond-analytics/{path}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    envelope = document["components"]["schemas"][schema["$ref"].split("/")[-1]]
    assert {"result_meta", "result"} <= set(envelope["required"])
    result = document["components"]["schemas"][envelope["properties"]["result"]["$ref"].split("/")[-1]]
    assert field in result["required"]


@pytest.mark.parametrize("path,service,_field", CASES)
def test_home_bond_response_serialization_matches_existing_service_wire(client, monkeypatch, path, service, _field):
    payload = _payloads()[path]
    monkeypatch.setattr(routes, service, lambda *_args, **_kwargs: deepcopy(payload))
    response = client.get(f"/api/bond-analytics/{path}", params={"report_date": REPORT_DATE.isoformat()})
    assert response.status_code == 200
    assert response.json() == payload


@pytest.mark.parametrize("path,service,field", CASES)
def test_home_bond_missing_consumed_field_is_rejected(client, monkeypatch, path, service, field):
    payload = _payloads()[path]
    del payload["result"][field]
    monkeypatch.setattr(routes, service, lambda *_args, **_kwargs: payload)
    with pytest.raises(ResponseValidationError):
        client.get(f"/api/bond-analytics/{path}", params={"report_date": REPORT_DATE.isoformat()})


@pytest.mark.parametrize("path,service,_field", CASES)
def test_home_bond_legal_empty_response_is_not_a_contract_failure(client, monkeypatch, path, service, _field):
    payload = _payloads()[path]
    result = payload["result"]
    for key, value in result.items():
        if isinstance(value, list) and key not in {"warnings", "warning_codes"}:
            result[key] = []
        if key.startswith("concentration_by_"):
            result[key] = None
    result["warnings"] = ["synthetic unavailable input"]
    monkeypatch.setattr(routes, service, lambda *_args, **_kwargs: payload)
    response = client.get(f"/api/bond-analytics/{path}", params={"report_date": REPORT_DATE.isoformat()})
    assert response.status_code == 200
    assert response.json() == payload


@pytest.mark.parametrize("path,service,_field", CASES)
def test_home_bond_wrong_nested_shape_is_rejected(client, monkeypatch, path, service, _field):
    payload = _payloads()[path]
    result = payload["result"]
    if path == "top-holdings":
        result["items"][0]["market_value"] = _numeric()
    elif path == "position-changes":
        result["total_market_value"]["raw"] = "123.12345678"
    elif path == "portfolio-headlines":
        del result["by_asset_class"][0]["duration"]
    elif path == "credit-spread-migration":
        result["concentration_by_issuer"]["top_items"] = {}
    elif path == "return-decomposition":
        result["bond_details"][0]["trading"] = None
    elif path == "yield-curve-term-structure":
        result["curves"][0]["points"][0]["yield_pct"] = "0.00850000"
    else:
        del result["scenarios"][0]["by_asset_class"]["custom-asset"]["pnl_tpl"]
    monkeypatch.setattr(routes, service, lambda *_args, **_kwargs: payload)
    with pytest.raises(ResponseValidationError):
        client.get(f"/api/bond-analytics/{path}", params={"report_date": REPORT_DATE.isoformat()})


@pytest.mark.parametrize("location", ["envelope", "metadata", "result", "item"])
def test_home_bond_unknown_fields_fail_loudly_instead_of_being_filtered(client, monkeypatch, location):
    payload = _payloads()["top-holdings"]
    target = {"envelope": payload, "metadata": payload["result_meta"], "result": payload["result"],
              "item": payload["result"]["items"][0]}[location]
    target["unreviewed_extension"] = "must not disappear"
    monkeypatch.setattr(routes, "get_top_holdings", lambda *_args, **_kwargs: payload)
    with pytest.raises(ResponseValidationError):
        client.get("/api/bond-analytics/top-holdings", params={"report_date": REPORT_DATE.isoformat()})


def test_home_bond_summary_keeps_fields_and_omits_only_detail_rows(client, monkeypatch):
    payload = _payloads()["return-decomposition"]
    payload["result"]["bond_details"] = []
    monkeypatch.setattr(routes, "get_return_decomposition_summary", lambda *_args, **_kwargs: payload)
    monkeypatch.setattr(routes, "get_return_decomposition", lambda *_args: pytest.fail("full service was used"))
    response = client.get("/api/bond-analytics/return-decomposition", params={
        "report_date": REPORT_DATE.isoformat(), "detail": "summary", "period_type": "YTD",
    })
    assert response.status_code == 200
    assert response.json() == payload


def test_home_bond_ready_position_changes_preserve_numeric_null_and_decimal_text(client, monkeypatch):
    payload = _payloads()["position-changes"]
    payload["result"].update({"source_status": "ready", "prev_report_date": "2026-03-30"})
    payload["result"]["items"] = [construction.BondPositionChangeItem(
        instrument_code="SYNTHETIC", asset_class="rate", previous_market_value=_numeric(None),
        current_market_value=_numeric(), change_market_value=_numeric(), previous_weight=_numeric(None, "ratio"),
        current_weight=_numeric(0, "ratio"), change_weight=_numeric(0, "ratio"), direction="increase", reason_label="synthetic",
    ).model_dump(mode="json")]
    monkeypatch.setattr(routes, "get_position_changes", lambda *_args, **_kwargs: payload)
    response = client.get("/api/bond-analytics/position-changes", params={"report_date": REPORT_DATE.isoformat()})
    assert response.status_code == 200
    assert response.json() == payload
    assert response.json()["result"]["items"][0]["previous_market_value"]["raw"] is None
    assert response.json()["result"]["items"][0]["current_market_value"]["raw_text"] == "123.12345678"


@pytest.mark.parametrize("warning_codes", [None, ["synthetic_partial"]])
def test_home_bond_optional_warning_codes_keep_omission_and_null_semantics(client, monkeypatch, warning_codes):
    payload = _payloads()["top-holdings"]
    assert "warning_codes" not in payload["result"]
    payload["result"]["warning_codes"] = warning_codes
    monkeypatch.setattr(routes, "get_top_holdings", lambda *_args, **_kwargs: payload)
    response = client.get("/api/bond-analytics/top-holdings", params={"report_date": REPORT_DATE.isoformat()})
    assert response.status_code == 200
    assert response.json() == payload
