from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from backend.app.services import (
    candidate_financial_indicator_period_comparison_service as actual_service,
)
from tests.helpers import load_module
from tests.synthetic_ledger_pnl_fixture import (
    SYNTHETIC_REPORT_MONTH,
    write_synthetic_ledger_source_dir,
)


@pytest.fixture
def synthetic_source_dir(tmp_path: Path) -> Path:
    return write_synthetic_ledger_source_dir(tmp_path / "synthetic-ledger")


class _FakePeriodComparisonService:
    CandidateFinancialIndicatorPeriodComparisonRequestError = (
        actual_service.CandidateFinancialIndicatorPeriodComparisonRequestError
    )

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def candidate_financial_indicator_period_comparison_envelope(
        self, **kwargs: Any
    ) -> dict[str, Any]:
        self.calls.append(kwargs)
        return actual_service.candidate_financial_indicator_period_comparison_envelope(
            **kwargs
        )

    def candidate_financial_indicator_component_detail_envelope(
        self, **kwargs: Any
    ) -> dict[str, Any]:
        self.calls.append(kwargs)
        return actual_service.candidate_financial_indicator_component_detail_envelope(
            **kwargs
        )


def test_period_comparison_route_uses_read_boundary_fixed_source_and_strict_model(
    monkeypatch,
    synthetic_source_dir: Path,
) -> None:
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    service = _FakePeriodComparisonService()
    permission_calls: list[object] = []
    monkeypatch.setattr(
        route_module,
        "_ensure_ledger_pnl_read_allowed",
        lambda auth: permission_calls.append(auth),
    )
    monkeypatch.setattr(route_module, "_period_comparison_svc", lambda: service)
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: SimpleNamespace(product_category_source_dir=synthetic_source_dir),
    )
    app = FastAPI()
    app.include_router(route_module.router)

    response = TestClient(app).get(
        "/api/ledger-pnl/candidate-financial-indicators/period-comparison",
        params={"report_month": SYNTHETIC_REPORT_MONTH},
    )

    assert response.status_code == 200
    assert len(permission_calls) == 1
    assert response.json()["overall_status"] == "partial"
    assert all(
        item["lock_status"] == "unlocked" for item in response.json()["source_periods"]
    )
    assert service.calls == [
        {"source_dir": str(synthetic_source_dir), "report_month": SYNTHETIC_REPORT_MONTH}
    ]
    target_route = next(
        route
        for route in route_module.router.routes
        if getattr(route, "path", None)
        == "/api/ledger-pnl/candidate-financial-indicators/period-comparison"
    )
    assert target_route.response_model.__name__ == (
        "CandidateFinancialIndicatorPeriodComparisonEnvelope"
    )


def test_period_comparison_route_rejects_before_service_when_read_is_forbidden(
    monkeypatch,
) -> None:
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    service = _FakePeriodComparisonService()

    def reject(_auth: object) -> None:
        raise HTTPException(status_code=403, detail="forbidden")

    monkeypatch.setattr(route_module, "_ensure_ledger_pnl_read_allowed", reject)
    monkeypatch.setattr(route_module, "_period_comparison_svc", lambda: service)
    app = FastAPI()
    app.include_router(route_module.router)

    response = TestClient(app).get(
        "/api/ledger-pnl/candidate-financial-indicators/period-comparison",
        params={"report_month": "202606"},
    )

    assert response.status_code == 403
    assert service.calls == []


def test_component_detail_route_uses_visible_parent_key_and_strict_model(
    monkeypatch,
    synthetic_source_dir: Path,
) -> None:
    parent = actual_service.candidate_financial_indicator_period_comparison_envelope(
        source_dir=str(synthetic_source_dir),
        report_month=SYNTHETIC_REPORT_MONTH,
    )
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    service = _FakePeriodComparisonService()
    monkeypatch.setattr(route_module, "_ensure_ledger_pnl_read_allowed", lambda _auth: None)
    monkeypatch.setattr(route_module, "_period_comparison_svc", lambda: service)
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: SimpleNamespace(product_category_source_dir=synthetic_source_dir),
    )
    app = FastAPI()
    app.include_router(route_module.router)

    response = TestClient(app).get(
        "/api/ledger-pnl/candidate-financial-indicators/period-comparison/component-detail",
        params={
            "report_month": SYNTHETIC_REPORT_MONTH,
            "metric_id": "income.interest.investment",
            "parent_idempotency_key": parent["idempotency_key"],
        },
    )

    assert response.status_code == 200
    assert response.json()["rows"][0]["account_code"] == "51402010003"
    assert service.calls == [
        {
            "source_dir": str(synthetic_source_dir),
            "report_month": SYNTHETIC_REPORT_MONTH,
            "metric_id": "income.interest.investment",
            "parent_idempotency_key": parent["idempotency_key"],
        }
    ]
    target_route = next(
        route
        for route in route_module.router.routes
        if getattr(route, "path", None)
        == "/api/ledger-pnl/candidate-financial-indicators/period-comparison/component-detail"
    )
    assert target_route.response_model.__name__ == (
        "CandidateFinancialIndicatorComponentDetailEnvelope"
    )


def test_component_detail_route_rejects_invalid_query_before_service(monkeypatch) -> None:
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    service = _FakePeriodComparisonService()
    monkeypatch.setattr(route_module, "_ensure_ledger_pnl_read_allowed", lambda _auth: None)
    monkeypatch.setattr(route_module, "_period_comparison_svc", lambda: service)
    app = FastAPI()
    app.include_router(route_module.router)

    response = TestClient(app).get(
        "/api/ledger-pnl/candidate-financial-indicators/period-comparison/component-detail",
        params={
            "report_month": "202606",
            "metric_id": "income.interest.net",
            "parent_idempotency_key": "not-a-sha",
        },
    )

    assert response.status_code == 422
    assert service.calls == []


def test_component_detail_route_translates_caller_error_to_422(monkeypatch, tmp_path) -> None:
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    service = _FakePeriodComparisonService()

    def caller_error(**_kwargs: Any) -> dict[str, Any]:
        raise service.CandidateFinancialIndicatorPeriodComparisonRequestError(
            "controlled component request error"
        )

    service.candidate_financial_indicator_component_detail_envelope = caller_error
    monkeypatch.setattr(route_module, "_ensure_ledger_pnl_read_allowed", lambda _auth: None)
    monkeypatch.setattr(route_module, "_period_comparison_svc", lambda: service)
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: SimpleNamespace(product_category_source_dir=tmp_path),
    )
    app = FastAPI()
    app.include_router(route_module.router)

    response = TestClient(app).get(
        "/api/ledger-pnl/candidate-financial-indicators/period-comparison/component-detail",
        params={
            "report_month": "202606",
            "metric_id": "income.interest.investment",
            "parent_idempotency_key": "a" * 64,
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "controlled component request error"}


def test_component_detail_route_does_not_expose_internal_errors(monkeypatch, tmp_path) -> None:
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    service = _FakePeriodComparisonService()

    def internal_error(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("sensitive workbook path")

    service.candidate_financial_indicator_component_detail_envelope = internal_error
    monkeypatch.setattr(route_module, "_ensure_ledger_pnl_read_allowed", lambda _auth: None)
    monkeypatch.setattr(route_module, "_period_comparison_svc", lambda: service)
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: SimpleNamespace(product_category_source_dir=tmp_path),
    )
    app = FastAPI()
    app.include_router(route_module.router)

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/ledger-pnl/candidate-financial-indicators/period-comparison/component-detail",
        params={
            "report_month": "202606",
            "metric_id": "income.interest.investment",
            "parent_idempotency_key": "a" * 64,
        },
    )

    assert response.status_code == 500
    assert "sensitive workbook path" not in response.text
