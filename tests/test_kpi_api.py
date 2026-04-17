from __future__ import annotations

import uuid
from types import SimpleNamespace

from tests.helpers import load_module


def _load_kpi_route_module():
    return load_module(
        f"tests._kpi_routes.kpi_{uuid.uuid4().hex}",
        "backend/app/api/routes/kpi.py",
    )


def test_fastapi_application_exposes_kpi_routes():
    module = load_module("backend.app.main", "backend/app/main.py")
    app = getattr(module, "app", None)
    paths = {route.path for route in app.routes}
    assert "/api/kpi/owners" in paths
    assert "/api/kpi/values/summary" in paths


def test_kpi_routes_return_read_models(monkeypatch):
    module = _load_kpi_route_module()
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(governance_sql_dsn="sqlite:///tmp/kpi.db", postgres_dsn="sqlite:///tmp/kpi.db"),
    )
    monkeypatch.setattr(
        module,
        "kpi_owners_payload",
        lambda **_kwargs: {"owners": [{"owner_id": 1, "owner_name": "固定收益部"}], "total": 1},
    )
    monkeypatch.setattr(
        module,
        "kpi_period_summary_payload",
        lambda **_kwargs: {
            "owner_id": 1,
            "owner_name": "固定收益部",
            "year": 2026,
            "period_type": "YEAR",
            "period_value": None,
            "period_label": "2026年度",
            "period_start_date": "2026-01-01",
            "period_end_date": "2026-12-31",
            "metrics": [],
            "total": 0,
            "total_weight": "100.000000",
            "total_score": "0.000000",
        },
    )

    owners = module.kpi_owners(year=2026, is_active=True)
    summary = module.kpi_values_summary(owner_id=1, year=2026, period_type="YEAR", period_value=None)

    assert owners["total"] == 1
    assert owners["owners"][0]["owner_name"] == "固定收益部"
    assert summary["owner_id"] == 1
    assert summary["period_label"] == "2026年度"
