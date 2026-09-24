"""Prove that declaring `response_model` did not drop a single response field.

FastAPI filters a response through its `response_model`: any key the handler
returns that the model does not declare is removed, silently, with a 200. On a
PnL or risk surface that is the worst possible failure mode — the response still
looks well-formed while a number has quietly vanished.

Every endpoint that gains a `response_model` must therefore be pinned here. The
test calls the service function directly (the shape the handler *would* have
returned) and the HTTP endpoint (the shape after model filtering), then asserts
the two field-path sets are identical. It is deliberately shape-only: values,
trace ids and timestamps legitimately differ between two calls.

The envelope models also set `extra="forbid"`, which upgrades "field silently
dropped" into a 500. That is the structural guard; this test is the evidence.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_bond_dashboard_api_contract import (
    REPORT_DATE,
    _bond_dashboard_client_with_read_scope,
    _make_bond_analytics_row,
    _replace_bond_dashboard_rows,
)

BUNDLE_SECTIONS = "headline-kpis,risk-indicators,yield-distribution,industry-distribution"
GOLDEN_SAMPLES_DIR = Path(__file__).resolve().parent / "golden_samples"


def field_paths(value: Any, prefix: str = "") -> set[str]:
    """Every key path in a JSON value, with list indices collapsed to `[]`.

    Collapsing indices keeps the comparison about *shape*: two calls may return
    a different number of rows, but every row must expose the same keys.
    """
    if isinstance(value, dict):
        paths: set[str] = set()
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.add(child_prefix)
            paths |= field_paths(child, child_prefix)
        return paths
    if isinstance(value, list):
        paths = set()
        for item in value:
            paths |= field_paths(item, f"{prefix}[]")
        return paths
    return set()


def null_valued_paths(value: Any, prefix: str = "") -> set[str]:
    """Key paths whose value is JSON null, addressed the same way as `field_paths`."""
    if isinstance(value, dict):
        paths: set[str] = set()
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if child is None:
                paths.add(child_prefix)
            paths |= null_valued_paths(child, child_prefix)
        return paths
    if isinstance(value, list):
        paths = set()
        for item in value:
            paths |= null_valued_paths(item, f"{prefix}[]")
        return paths
    return set()


def _bond_dashboard_service():
    return load_module(
        "backend.app.services.bond_dashboard_service",
        "backend/app/services/bond_dashboard_service.py",
    )


def _bond_dashboard_cases() -> list[tuple[str, dict[str, Any], Callable[[Any], dict[str, Any]]]]:
    """`(path, query params, service call)` for each endpoint that gained a model."""
    report_date = date.fromisoformat(REPORT_DATE)
    return [
        ("/api/bond-dashboard/dates", {}, lambda svc: svc.get_bond_dashboard_dates()),
        (
            "/api/bond-dashboard/headline-kpis",
            {"report_date": REPORT_DATE},
            lambda svc: svc.get_bond_dashboard_headline_kpis(report_date),
        ),
        (
            "/api/bond-dashboard/home-summary",
            {"report_date": REPORT_DATE},
            lambda svc: svc.get_bond_dashboard_home_summary(report_date),
        ),
        (
            "/api/bond-dashboard/asset-structure",
            {"report_date": REPORT_DATE, "group_by": "bond_type"},
            lambda svc: svc.get_bond_dashboard_asset_structure(report_date, "bond_type"),
        ),
        (
            "/api/bond-dashboard/yield-distribution",
            {"report_date": REPORT_DATE},
            lambda svc: svc.get_bond_dashboard_yield_distribution(report_date),
        ),
        (
            "/api/bond-dashboard/portfolio-comparison",
            {"report_date": REPORT_DATE},
            lambda svc: svc.get_bond_dashboard_portfolio_comparison(report_date),
        ),
        (
            "/api/bond-dashboard/spread-analysis",
            {"report_date": REPORT_DATE},
            lambda svc: svc.get_bond_dashboard_spread_analysis(report_date),
        ),
        (
            "/api/bond-dashboard/maturity-structure",
            {"report_date": REPORT_DATE},
            lambda svc: svc.get_bond_dashboard_maturity_structure(report_date),
        ),
        (
            "/api/bond-dashboard/industry-distribution",
            {"report_date": REPORT_DATE, "top_n": 10},
            lambda svc: svc.get_bond_dashboard_industry_distribution(report_date, 10),
        ),
        (
            "/api/bond-dashboard/risk-indicators",
            {"report_date": REPORT_DATE},
            lambda svc: svc.get_bond_dashboard_risk_indicators(report_date),
        ),
        (
            "/api/bond-dashboard/business-type-metrics",
            {"report_date": REPORT_DATE},
            lambda svc: svc.get_bond_dashboard_business_type_metrics(report_date),
        ),
        (
            "/api/bond-dashboard/bundle",
            {"report_date": REPORT_DATE, "sections": BUNDLE_SECTIONS},
            lambda svc: svc.get_bond_dashboard_bundle(
                sections=[BUNDLE_SECTIONS],
                report_date=report_date,
            ),
        ),
    ]


def _seed_bond_dashboard_facts() -> None:
    """Non-empty facts, so optional branches (`prev_kpis`, item rows) are exercised."""
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    repo = BondAnalyticsRepository(str(get_settings().duckdb_path))
    previous_date = "2026-03-30"
    for report_date, market_value in ((previous_date, Decimal("900")), (REPORT_DATE, Decimal("100"))):
        rows = [
            _make_bond_analytics_row(
                report_date=report_date,
                instrument_code="RATE",
                portfolio_name="P1",
                asset_class_std="rate",
                market_value=market_value,
                ytm=Decimal("0.02"),
                modified_duration=Decimal("2"),
                bond_type_label="Rate",
            ),
            _make_bond_analytics_row(
                report_date=report_date,
                instrument_code="CREDIT",
                portfolio_name="P2",
                asset_class_std="credit",
                market_value=Decimal("300"),
                ytm=Decimal("0.04"),
                modified_duration=Decimal("6"),
                bond_type_label="Credit",
            ),
        ]
        _replace_bond_dashboard_rows(repo, report_date=report_date, rows=rows)


@pytest.mark.parametrize("seeded", [False, True], ids=["empty-duckdb", "seeded-duckdb"])
def test_bond_dashboard_response_model_preserves_every_service_field(
    tmp_path,
    monkeypatch,
    seeded: bool,
) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "field-preservation.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    service = _bond_dashboard_service()
    service.clear_bond_dashboard_runtime_cache()
    if seeded:
        _seed_bond_dashboard_facts()
        service.clear_bond_dashboard_runtime_cache()

    client = _bond_dashboard_client_with_read_scope(tmp_path, monkeypatch)

    for path, params, call_service in _bond_dashboard_cases():
        raw = call_service(service)
        response = client.get(path, params=params)
        assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"

        served = field_paths(response.json())
        produced = field_paths(raw)
        assert served == produced, (
            f"{path} lost or invented fields through response_model.\n"
            f"  dropped by the model: {sorted(produced - served)}\n"
            f"  added by the model:   {sorted(served - produced)}"
        )
        assert produced, f"{path}: the service returned no fields at all"

    get_settings.cache_clear()


def test_risk_tensor_response_model_preserves_every_service_field(tmp_path, monkeypatch) -> None:
    """Same proof for `/api/risk/tensor*`, against a materialized tensor fact.

    This one also pins the `window.from` alias: `from` is a Python keyword, so the
    model field is `from_`, and a serializer that forgot `by_alias` would rename a
    live field instead of dropping it.
    """
    from tests.test_risk_tensor_api import _risk_tensor_client
    from tests.test_risk_tensor_service import _configure_and_materialize_risk_tensor

    duckdb_path, governance_dir, _task = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    common = {"duckdb_path": str(duckdb_path), "governance_dir": str(governance_dir)}

    cases: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
        ("/api/risk/tensor/dates", {}, service.risk_tensor_dates_envelope(**common)),
        (
            "/api/risk/tensor",
            {"report_date": REPORT_DATE},
            service.risk_tensor_envelope(report_date=REPORT_DATE, **common),
        ),
        (
            "/api/risk/tensor/history",
            {"report_date": REPORT_DATE, "periods": 24},
            service.risk_tensor_history_envelope(report_date=REPORT_DATE, periods=24, **common),
        ),
    ]

    client = _risk_tensor_client(tmp_path, monkeypatch)
    for path, params, raw in cases:
        response = client.get(path, params=params)
        assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"

        served = field_paths(response.json())
        produced = field_paths(raw)
        assert served == produced, (
            f"{path} lost or invented fields through response_model.\n"
            f"  dropped by the model: {sorted(produced - served)}\n"
            f"  added by the model:   {sorted(served - produced)}"
        )
        assert produced, f"{path}: the service returned no fields at all"

    history = client.get("/api/risk/tensor/history", params={"report_date": REPORT_DATE, "periods": 24}).json()
    assert "from" in history["result"]["window"], "the `from` alias did not survive serialization"

    get_settings.cache_clear()


def _registered_routes() -> dict[tuple[str, str], Any]:
    """`(METHOD, path) -> APIRoute` for the whole registered API surface."""
    import importlib

    from fastapi.routing import APIRoute

    api_module = importlib.import_module("backend.app.api")
    app = FastAPI()
    app.include_router(api_module.router)
    return {
        (method, route.path): route
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in (route.methods or ())
    }


def _golden_samples_with_response_models() -> list[tuple[str, Any, dict[str, Any]]]:
    """Captured real responses for endpoints that now declare a `response_model`."""
    routes = _registered_routes()
    cases: list[tuple[str, Any, dict[str, Any]]] = []
    for request_path in sorted(GOLDEN_SAMPLES_DIR.glob("*/request.json")):
        response_path = request_path.with_name("response.json")
        if not response_path.exists():
            continue
        request = json.loads(request_path.read_text(encoding="utf-8"))
        route = routes.get((str(request.get("method", "GET")).upper(), str(request.get("path", ""))))
        if route is None or route.response_model is None:
            continue
        if route.response_model is dict:
            # `response_model=dict` filters nothing, so it would pass vacuously and
            # dilute the count of samples that actually prove something.
            continue
        cases.append(
            (
                request_path.parent.name,
                route.response_model,
                json.loads(response_path.read_text(encoding="utf-8")),
            )
        )
    return cases


def test_golden_sample_responses_survive_their_response_model() -> None:
    """The strongest available evidence: a captured production-shaped body, unchanged.

    Golden samples were recorded before any `response_model` existed, so pushing
    one back through the model reproduces exactly the "did the declaration eat a
    field?" question against real data rather than a fixture.
    """
    cases = _golden_samples_with_response_models()
    covered = {model.__name__ for _, model, _ in cases}
    assert {
        "BondDashboardHeadlineEnvelope",
        "CashflowProjectionEnvelope",
        "RiskTensorEnvelope",
    } <= covered, f"this batch lost its captured-response evidence; only covered {sorted(covered)}"

    for sample_id, model, captured in cases:
        app = FastAPI()
        app.add_api_route(
            "/probe",
            lambda captured=captured: captured,
            methods=["GET"],
            response_model=model,
        )
        response = TestClient(app, raise_server_exceptions=False).get("/probe")

        assert response.status_code == 200, (
            f"{sample_id}: {model.__name__} rejected the captured response "
            f"({response.status_code}). The model does not describe what the endpoint really returns."
        )
        served = field_paths(response.json())
        recorded = field_paths(captured)

        assert recorded - served == set(), (
            f"{sample_id}: {model.__name__} dropped fields the endpoint really returned: "
            f"{sorted(recorded - served)}"
        )
        # Samples predate later `ResultMeta` fields, so governance metadata may have
        # grown since the capture.
        payload_additions = {path for path in served - recorded if not path.startswith("result_meta")}
        # An optional model field the handler never set is materialized as an
        # explicit null rather than staying absent. That is the "may be null" vs
        # "may be missing" distinction: tolerable, but it must never introduce a
        # value the endpoint did not compute.
        invented = payload_additions - null_valued_paths(response.json())
        assert invented == set(), (
            f"{sample_id}: {model.__name__} invented business fields the endpoint never returned: "
            f"{sorted(invented)}"
        )


def _ledger_pnl_client(monkeypatch) -> TestClient:
    """The real route module and the real service, with only the scope check removed."""
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    monkeypatch.setattr(route_module, "_ensure_ledger_pnl_read_allowed", lambda _auth: None)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"X-User-Id": "field-preservation", "X-User-Role": "viewer"})
    return client


def _install_populated_ledger_source(monkeypatch) -> None:
    """Point the ledger service at an in-memory general ledger.

    The read endpoints degrade to an empty-source branch when no workbook pair is
    discoverable, and that branch exercises none of the row-level fields. Both
    states have to be pinned, so this installs a balanced synthetic ledger for
    the populated one.
    """
    from backend.app.services import ledger_pnl_service as svc
    from backend.app.services import qdb_gl_monthly_analysis_service as monthly_svc
    from tests.test_ledger_financial_indicator_summary import _synthetic_rows
    from tests.test_ledger_pnl_service import _fact

    months = ["202501", "202502", "202512", "202601", "202602"]
    facts = [
        _fact("10101000001", "CNX", ending_balance="100"),
        _fact("12301000001", "CNX", ending_balance="40"),
        _fact("20101000001", "CNX", ending_balance="-50"),
        _fact("51401000001", "CNX", monthly_pnl="7"),
        _fact("51601000001", "CNX", monthly_pnl="3"),
        _fact("51601000001", "CNY", monthly_pnl="2"),
    ]
    previous = [_fact("51601000001", "CNX", monthly_pnl="1", report_date=date(2026, 3, 31))]

    class _Pair:
        def __init__(self, month_key: str) -> None:
            self.month_key = month_key
            self.ledger_path = f"ledger_{month_key}.xlsx"
            self.source_version = f"sv_{month_key}"
            self.report_date = date(int(month_key[:4]), int(month_key[4:]), 28)

    pairs = [*(_Pair(month) for month in months), _Pair("202604")]
    pairs[-1].report_date = date(2026, 4, 30)

    monkeypatch.setattr(svc, "discover_source_pairs", lambda _source_dir: pairs)
    monkeypatch.setattr(
        svc,
        "_load_facts_for_date",
        lambda _source_dir, report_date: (
            (previous, "sv_prev") if report_date == date(2026, 3, 31) else (facts, "sv_probe")
        ),
    )
    monkeypatch.setattr(
        svc,
        "_cached_ledger_only_facts",
        lambda _pair: [
            _fact(row.account_code, "CNX", ending_balance=str(row.ending_balance_yuan))
            for row in _synthetic_rows()
        ],
    )
    monkeypatch.setattr(monthly_svc, "_discover_report_months", lambda _source_dir: ["202601"])


def _ledger_pnl_cases() -> list[tuple[str, dict[str, Any], Callable[[Any, Any], dict[str, Any]]]]:
    """`(path, query params, service call)` mirroring exactly what each handler calls."""
    return [
        (
            "/api/ledger-pnl/dates",
            {},
            lambda svc, _monthly: svc.ledger_pnl_dates_envelope(source_dir="src"),
        ),
        (
            "/api/ledger-pnl/data",
            {"date": "2026-04-30", "currency": "CNX"},
            lambda svc, _monthly: svc.ledger_pnl_data_envelope(
                source_dir="src", report_date="2026-04-30", currency="CNX"
            ),
        ),
        (
            "/api/ledger-pnl/summary",
            {"date": "2026-04-30", "currency": "CNX"},
            lambda svc, _monthly: svc.ledger_pnl_summary_envelope(
                source_dir="src", report_date="2026-04-30", currency="CNX"
            ),
        ),
        (
            "/api/ledger-pnl/financial-indicator-summary",
            {"report_month": "202602", "currency": "CNX"},
            lambda svc, _monthly: svc.ledger_pnl_financial_indicator_summary_envelope(
                source_dir="src", report_month="202602", currency="CNX"
            ),
        ),
        (
            "/api/ledger-pnl/monthly-analysis/dates",
            {},
            lambda _svc, monthly: monthly.qdb_gl_monthly_analysis_dates_envelope(
                source_dir="src"
            ),
        ),
    ]


@pytest.mark.parametrize("populated", [False, True], ids=["empty-source", "populated-source"])
def test_ledger_pnl_response_model_preserves_every_service_field(
    tmp_path,
    monkeypatch,
    populated: bool,
) -> None:
    """Same proof for the `/api/ledger-pnl/*` reads that gained a model this batch.

    Both the empty-source degradation and a populated ledger are pinned, because
    the two branches emit different keys and only the union is the real contract.
    """
    from fastapi.encoders import jsonable_encoder

    empty_dir = tmp_path / "ledger-src"
    empty_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(empty_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "ledger-preservation.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    from backend.app.services import ledger_pnl_service as service
    from backend.app.services import qdb_gl_monthly_analysis_service as monthly_service

    if populated:
        _install_populated_ledger_source(monkeypatch)

    client = _ledger_pnl_client(monkeypatch)
    for path, params, call_service in _ledger_pnl_cases():
        raw = jsonable_encoder(call_service(service, monthly_service))
        response = client.get(path, params=params)
        assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"

        served = field_paths(response.json())
        produced = field_paths(raw)
        assert served == produced, (
            f"{path} lost or invented fields through response_model.\n"
            f"  dropped by the model: {sorted(produced - served)}\n"
            f"  added by the model:   {sorted(served - produced)}"
        )
        assert produced, f"{path}: the service returned no fields at all"

    get_settings.cache_clear()


def _pnl_attribution_workbench_cases() -> list[tuple[str, dict[str, Any], str, dict[str, Any]]]:
    """`(path, query params, service function name, service kwargs)` per endpoint."""
    return [
        ("/api/pnl-attribution/volume-rate", {"compare_type": "mom"},
         "volume_rate_attribution_envelope", {"report_date": None, "compare_type": "mom"}),
        ("/api/pnl-attribution/tpl-market", {"months": 12},
         "tpl_market_correlation_envelope", {"months": 12, "report_date": None}),
        ("/api/pnl-attribution/composition", {"include_trend": "true", "trend_months": 6},
         "pnl_composition_envelope",
         {"report_date": None, "include_trend": True, "trend_months": 6}),
        ("/api/pnl-attribution/advanced/carry-rolldown", {},
         "carry_roll_down_envelope", {"report_date": None}),
        ("/api/pnl-attribution/advanced/spread", {"lookback_days": 30},
         "spread_attribution_envelope", {"report_date": None, "lookback_days": 30}),
        ("/api/pnl-attribution/advanced/krd", {"lookback_days": 30},
         "krd_attribution_envelope", {"report_date": None, "lookback_days": 30}),
        ("/api/pnl-attribution/advanced/summary", {},
         "advanced_attribution_summary_envelope", {"report_date": None}),
    ]


def test_pnl_attribution_response_model_preserves_every_service_field(
    tmp_path,
    monkeypatch,
) -> None:
    """Same proof for the seven `/api/pnl-attribution/*` workbench reads.

    These run against an empty DuckDB, which is the branch that actually carries
    the risk: it is where the service attaches the `warnings` key that the
    payload models did not previously declare.
    """
    from fastapi.encoders import jsonable_encoder

    from tests.test_pnl_attribution_api_contract import (
        PNL_ATTRIBUTION_READ_HEADERS,
        _grant_pnl_attribution_read_scope,
    )

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "attribution-preservation.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    from backend.app.services import pnl_attribution_service as service

    route_module = load_module(
        "backend.app.api.routes.pnl_attribution",
        "backend/app/api/routes/pnl_attribution.py",
    )
    _grant_pnl_attribution_read_scope(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "attribution-preservation.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update(PNL_ATTRIBUTION_READ_HEADERS)
    for path, params, function_name, kwargs in _pnl_attribution_workbench_cases():
        raw = jsonable_encoder(getattr(service, function_name)(**kwargs))
        response = client.get(path, params=params)
        assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"

        served = field_paths(response.json())
        produced = field_paths(raw)
        assert served == produced, (
            f"{path} lost or invented fields through response_model.\n"
            f"  dropped by the model: {sorted(produced - served)}\n"
            f"  added by the model:   {sorted(served - produced)}"
        )
        assert produced, f"{path}: the service returned no fields at all"

    get_settings.cache_clear()


def _campisi_degradation_variants() -> dict[str, dict[str, Any]]:
    """Portfolio states whose key sets differ, so all of them have to be pinned.

    `/campisi/*` emits `diagnostics`, `effect_availability`, `formal_closure` and
    `input_quality` only once there is a position to analyse, and the contents of
    those blocks change again when the yield curve, the maturity date or the
    formal-PnL bridge is unavailable.
    """
    from tests.test_campisi_attribution_service import _bond_row, _flat_treasury

    def rows(**overrides: Any) -> list[dict[str, Any]]:
        base = [
            {
                "code": "PRESERVE_CREDIT",
                "market_value": Decimal("1000"),
                "face_value": Decimal("1000"),
                "accrued_interest": Decimal("5"),
                "coupon_rate": Decimal("0.0300"),
                "ytm": Decimal("0.0320"),
                "rating": "AAA",
                "asset_class": "credit",
            },
            {
                "code": "PRESERVE_RATE",
                "market_value": Decimal("500"),
                "face_value": Decimal("500"),
                "accrued_interest": Decimal("2"),
                "coupon_rate": Decimal("0.0250"),
                "ytm": Decimal("0.0260"),
                "rating": None,
                "asset_class": "rate",
            },
        ]
        return [_bond_row(**{**row, **overrides}) for row in base]

    curves = {
        ("2026-01-01", "treasury"): _flat_treasury(Decimal("2.00")),
        ("2026-01-31", "treasury"): _flat_treasury(Decimal("2.10")),
        ("2026-01-01", "credit_spread_aaa"): {"3Y": 30.0},
        ("2026-01-31", "credit_spread_aaa"): {"3Y": 35.0},
    }
    return {
        "no-positions": {"rows": [], "curves": curves, "closure": "closed"},
        "priced": {"rows": rows(), "curves": curves, "closure": "closed"},
        "no-curve": {"rows": rows(), "curves": {}, "closure": "closed"},
        "no-maturity": {"rows": rows(maturity_date=None), "curves": curves, "closure": "closed"},
        "bridge-open": {"rows": rows(), "curves": curves, "closure": "open"},
        "no-coupon": {
            "rows": rows(coupon_rate=None, ytm=None, accrued_interest=Decimal("0")),
            "curves": curves,
            "closure": "closed",
        },
    }


@pytest.mark.parametrize("variant", sorted(_campisi_degradation_variants()))
def test_campisi_response_model_preserves_every_service_field(
    tmp_path,
    monkeypatch,
    variant: str,
) -> None:
    """Same proof for `/api/pnl-attribution/campisi/*`, across six portfolio states."""
    from fastapi.encoders import jsonable_encoder

    from backend.app.services import campisi_attribution_service as service
    from tests.test_campisi_attribution_service import (
        _clear_four_effects_cache,
        _install_full_service_fakes,
    )
    from tests.test_pnl_attribution_api_contract import (
        PNL_ATTRIBUTION_READ_HEADERS,
        _grant_pnl_attribution_read_scope,
    )

    spec = _campisi_degradation_variants()[variant]
    start_rows = spec["rows"]
    end_rows = [{**row, "market_value": row["market_value"] - Decimal("5")} for row in start_rows]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-01"],
        rows_by_date={"2026-01-01": start_rows, "2026-01-31": end_rows},
        curves=spec["curves"],
        closure_status=spec["closure"],
    )

    route_module = load_module(
        "backend.app.api.routes.campisi_attribution",
        "backend/app/api/routes/campisi_attribution.py",
    )
    monkeypatch.setattr(route_module, "_ensure_pnl_attribution_read_allowed", lambda _auth: None)
    _grant_pnl_attribution_read_scope(tmp_path, monkeypatch)

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update(PNL_ATTRIBUTION_READ_HEADERS)

    window = {"start_date": "2026-01-01", "end_date": "2026-01-31"}
    cases: list[tuple[str, dict[str, Any], Callable[[], dict[str, Any]]]] = [
        (
            "/api/pnl-attribution/campisi/four-effects",
            {**window, "detail": "full"},
            lambda: service.campisi_four_effects_envelope(**window),
        ),
        (
            "/api/pnl-attribution/campisi/four-effects",
            {**window, "detail": "summary"},
            lambda: service.campisi_four_effects_summary_envelope(**window),
        ),
        (
            "/api/pnl-attribution/campisi/enhanced",
            window,
            lambda: service.campisi_enhanced_envelope(**window),
        ),
        (
            "/api/pnl-attribution/campisi/maturity-buckets",
            window,
            lambda: service.campisi_maturity_bucket_envelope(**window),
        ),
    ]

    for path, params, call_service in cases:
        _clear_four_effects_cache()
        raw = jsonable_encoder(call_service())
        _clear_four_effects_cache()
        route_module.market_home_response_cache.invalidate()
        response = client.get(path, params=params)
        label = f"{path}?detail={params.get('detail', '-')}"
        assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"

        served = field_paths(response.json())
        produced = field_paths(raw)
        assert served == produced, (
            f"{label} lost or invented fields through response_model.\n"
            f"  dropped by the model: {sorted(produced - served)}\n"
            f"  added by the model:   {sorted(served - produced)}"
        )
        assert produced, f"{label}: the service returned no fields at all"


def test_second_batch_envelopes_forbid_undeclared_fields() -> None:
    """`extra="forbid"` on every envelope added in the ledger/attribution batch."""
    from backend.app.api.routes import campisi_attribution as campisi_routes
    from backend.app.api.routes import ledger_pnl as ledger_routes
    from backend.app.api.routes import pnl_attribution as attribution_routes
    from fastapi.routing import APIRoute

    expected = {
        "/api/ledger-pnl/dates",
        "/api/ledger-pnl/data",
        "/api/ledger-pnl/summary",
        "/api/ledger-pnl/financial-indicator-summary",
        "/api/ledger-pnl/monthly-analysis/dates",
        "/api/pnl-attribution/volume-rate",
        "/api/pnl-attribution/tpl-market",
        "/api/pnl-attribution/composition",
        "/api/pnl-attribution/advanced/carry-rolldown",
        "/api/pnl-attribution/advanced/spread",
        "/api/pnl-attribution/advanced/krd",
        "/api/pnl-attribution/advanced/summary",
        "/api/pnl-attribution/campisi/four-effects",
        "/api/pnl-attribution/campisi/enhanced",
        "/api/pnl-attribution/campisi/maturity-buckets",
    }
    routes = {
        route.path: route
        for module in (ledger_routes, attribution_routes, campisi_routes)
        for route in module.router.routes
        if isinstance(route, APIRoute)
    }
    missing = expected - set(routes)
    assert not missing, f"these endpoints disappeared from the routers: {sorted(missing)}"

    for path in sorted(expected):
        model = routes[path].response_model
        assert model is not None, f"{path} lost its response_model"
        assert model.model_config.get("extra") == "forbid", (
            f"{path} response model {model.__name__} allows extra keys, so a field the "
            "service adds would be dropped silently instead of failing"
        )
        assert set(model.model_fields) == {"result_meta", "result"}, (
            f"{path} response model {model.__name__} does not match the envelope contract"
        )


def test_bond_dashboard_envelopes_forbid_undeclared_fields() -> None:
    """The `extra="forbid"` guard is what makes a future dropped field loud."""
    from backend.app.api.routes import bond_dashboard as routes
    from fastapi.routing import APIRoute

    declared = [route for route in routes.router.routes if isinstance(route, APIRoute)]
    assert declared, "bond_dashboard router exposes no APIRoute"

    for route in declared:
        model = route.response_model
        assert model is not None, f"{route.path} has no response_model"
        assert model.model_config.get("extra") == "forbid", (
            f"{route.path} response model {model.__name__} allows extra keys, so a field the "
            "service adds would be dropped silently instead of failing"
        )
        assert set(model.model_fields) == {"result_meta", "result", "data_source"}, (
            f"{route.path} response model {model.__name__} does not match the envelope contract"
        )
