from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.responses import PlainTextResponse
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from tests.helpers import load_module


def _load_kpi_route_module():
    return load_module(
        f"tests._kpi_routes.kpi_{uuid.uuid4().hex}",
        "backend/app/api/routes/kpi.py",
    )


def _seed_kpi_sqlite(module, tmp_path):
    repo_module = load_module(
        f"tests._kpi_repo.seed_{uuid.uuid4().hex}",
        "backend/app/repositories/kpi_repo.py",
    )
    model_module = sys.modules["backend.app.models.kpi"]
    dsn = f"sqlite:///{tmp_path / 'kpi.db'}"
    repo = repo_module.KpiRepository(dsn)
    session_factory = sessionmaker(repo.engine, future=True)
    now = datetime.now(timezone.utc)

    with session_factory() as session:
        owner = model_module.KpiOwner(
            owner_name="Fixed Income",
            org_unit="Trading",
            person_name=None,
            year=2026,
            scope_type="department",
            scope_key_json='{"scope":"fi"}',
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(owner)
        session.flush()

        metric = model_module.KpiMetric(
            metric_code="GOAL_FI",
            owner_id=owner.owner_id,
            year=2026,
            major_category="Business Goal",
            indicator_category="Completion",
            metric_name="Goal Completion",
            target_value=100,
            target_text=None,
            score_weight=10,
            unit="%",
            scoring_text=None,
            scoring_rule_type="MANUAL",
            data_source_type="MANUAL",
            progress_plan=None,
            remarks=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(metric)
        session.commit()
        owner_id = owner.owner_id
        metric_id = metric.metric_id

    return dsn, owner_id, metric_id, session_factory, model_module


def _auth(module):
    return module.AuthContext(user_id="kpi-test", role="admin", identity_source="test")


def _allow_writes(monkeypatch, module):
    monkeypatch.setattr(module, "ensure_user_allowed", lambda **_kwargs: None)


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
        lambda **_kwargs: {"owners": [{"owner_id": 1, "owner_name": "Fixed Income"}], "total": 1},
    )
    monkeypatch.setattr(
        module,
        "kpi_period_summary_payload",
        lambda **_kwargs: {
            "owner_id": 1,
            "owner_name": "Fixed Income",
            "year": 2026,
            "period_type": "YEAR",
            "period_value": None,
            "period_label": "2026 Annual",
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
    assert owners["owners"][0]["owner_name"] == "Fixed Income"
    assert summary["owner_id"] == 1
    assert summary["period_label"] == "2026 Annual"


def test_kpi_value_update_recomputes_score_and_updates_metric_target(monkeypatch, tmp_path):
    module = _load_kpi_route_module()
    dsn, _owner_id, metric_id, session_factory, model_module = _seed_kpi_sqlite(module, tmp_path)
    _allow_writes(monkeypatch, module)
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(governance_sql_dsn=dsn, postgres_dsn=dsn),
    )
    now = datetime.now(timezone.utc)

    with session_factory() as session:
        value = model_module.KpiMetricValue(
            metric_id=metric_id,
            as_of_date=date(2026, 3, 31),
            actual_value=40,
            actual_text=None,
            completion_ratio=40,
            progress_pct=40,
            score_value=4,
            source="manual",
            created_at=now,
            updated_at=now,
        )
        session.add(value)
        session.commit()
        value_id = value.value_id

    payload = module.update_kpi_value(
        value_id=value_id,
        body=module.KpiValueUpdateRequest(
            target_value="120",
            actual_value="60",
            progress_pct="50",
            actual_text="manual refresh",
        ),
        auth=_auth(module),
    )

    assert payload["actual_value"] == "60.000000"
    assert payload["progress_pct"] == "50.000000"
    assert payload["completion_ratio"] == "50.000000"
    assert payload["score_value"] == "5.000000"

    with session_factory() as session:
        metric = session.get(model_module.KpiMetric, metric_id)
        assert metric.target_value == 120


def test_kpi_batch_update_upserts_values(monkeypatch, tmp_path):
    module = _load_kpi_route_module()
    dsn, owner_id, metric_id, _session_factory, _model_module = _seed_kpi_sqlite(module, tmp_path)
    _allow_writes(monkeypatch, module)
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(governance_sql_dsn=dsn, postgres_dsn=dsn),
    )

    result = module.batch_update_kpi_values(
        body=module.KpiValuesBatchRequest(
            as_of_date="2026-03-31",
            items=[module.KpiValueBatchItem(metric_id=metric_id, actual_value="55", progress_pct="55")],
        ),
        auth=_auth(module),
    )

    assert result == {"success_count": 1, "failed_count": 0, "errors": []}

    values = module.get_kpi_values(owner_id=owner_id, as_of_date="2026-03-31")
    metric = values["metrics"][0]
    assert metric["actual_value"] == "55.000000"
    assert metric["progress_pct"] == "55.000000"
    assert metric["completion_ratio"] == "55.000000"
    assert metric["score_value"] == "5.500000"


def test_kpi_fetch_and_recalc_scores_manual_metrics(monkeypatch, tmp_path):
    module = _load_kpi_route_module()
    dsn, owner_id, metric_id, session_factory, model_module = _seed_kpi_sqlite(module, tmp_path)
    _allow_writes(monkeypatch, module)
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(governance_sql_dsn=dsn, postgres_dsn=dsn),
    )
    now = datetime.now(timezone.utc)

    with session_factory() as session:
        session.add(
            model_module.KpiMetricValue(
                metric_id=metric_id,
                as_of_date=date(2026, 3, 31),
                actual_value=80,
                actual_text=None,
                completion_ratio=None,
                progress_pct=80,
                score_value=None,
                source="manual",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    result = module.fetch_and_recalc_kpi(
        body=module.KpiFetchAndRecalcRequest(metric_ids=[metric_id]),
        owner_id=owner_id,
        as_of_date="2026-03-31",
        auth=_auth(module),
    )

    assert result["total_metrics"] == 1
    assert result["fetched_count"] == 0
    assert result["scored_count"] == 1
    assert result["skipped_count"] == 1
    assert result["failed_count"] == 0
    assert result["results"][0]["fetch_status"] == "SKIPPED"
    assert result["results"][0]["score_status"] == "SCORED"
    assert result["results"][0]["score_value"] == "8.000000"


def test_kpi_report_can_render_csv(monkeypatch, tmp_path):
    module = _load_kpi_route_module()
    dsn, owner_id, metric_id, session_factory, model_module = _seed_kpi_sqlite(module, tmp_path)
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(governance_sql_dsn=dsn, postgres_dsn=dsn),
    )
    now = datetime.now(timezone.utc)

    with session_factory() as session:
        session.add(
            model_module.KpiMetricValue(
                metric_id=metric_id,
                as_of_date=date(2026, 3, 31),
                actual_value=90,
                actual_text=None,
                completion_ratio=90,
                progress_pct=90,
                score_value=9,
                source="manual",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    response = module.get_kpi_report(
        year=2026,
        owner_id=owner_id,
        as_of_date="2026-03-31",
        format="csv",
    )

    assert isinstance(response, PlainTextResponse)
    assert response.media_type == "text/csv; charset=utf-8"
    assert response.headers["Content-Disposition"] == 'attachment; filename="kpi_report_2026_2026-03-31.csv"'
    body = response.body.decode("utf-8")
    assert "owner_name,org_unit,major_category" in body
    assert "Goal Completion" in body


def test_kpi_route_delegates_to_service_and_maps_exceptions(monkeypatch):
    module = _load_kpi_route_module()
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(governance_sql_dsn="sqlite:///tmp/kpi.db", postgres_dsn="sqlite:///tmp/kpi.db"),
    )

    captured = {}

    def fake_list_metrics(*, dsn, owner_id, year, is_active):
        captured.update({"dsn": dsn, "owner_id": owner_id, "year": year, "is_active": is_active})
        return {"metrics": [{"metric_id": 7}], "total": 1}

    monkeypatch.setattr(module.kpi_workbench_service, "list_metrics", fake_list_metrics)

    payload = module.list_kpi_metrics(owner_id=2, year=2026, is_active=True)

    assert payload == {"metrics": [{"metric_id": 7}], "total": 1}
    assert captured == {
        "dsn": "sqlite:///tmp/kpi.db",
        "owner_id": 2,
        "year": 2026,
        "is_active": True,
    }

    monkeypatch.setattr(
        module.kpi_workbench_service,
        "get_metric",
        lambda **_kwargs: (_ for _ in ()).throw(
            module.kpi_workbench_service.KpiNotFoundError("KPI metric 99 not found")
        ),
    )
    with pytest.raises(HTTPException) as not_found:
        module.get_kpi_metric(99)
    assert not_found.value.status_code == 404
    assert not_found.value.detail == "KPI metric 99 not found"

    monkeypatch.setattr(
        module.kpi_workbench_service,
        "get_values",
        lambda **_kwargs: (_ for _ in ()).throw(
            module.kpi_workbench_service.KpiInvalidDateError("Invalid as_of_date: bad-date")
        ),
    )
    with pytest.raises(HTTPException) as invalid_date:
        module.get_kpi_values(owner_id=1, as_of_date="bad-date")
    assert invalid_date.value.status_code == 422
    assert invalid_date.value.detail == "Invalid as_of_date: bad-date"

    monkeypatch.setattr(
        module.kpi_workbench_service,
        "build_report",
        lambda **_kwargs: (_ for _ in ()).throw(
            module.kpi_workbench_service.KpiStorageError("database unavailable")
        ),
    )
    with pytest.raises(HTTPException) as storage_error:
        module.get_kpi_report(year=2026)
    assert storage_error.value.status_code == 503
    assert storage_error.value.detail == "database unavailable"


def test_kpi_auth_rejects_before_service_call(monkeypatch):
    module = _load_kpi_route_module()
    body = module.KpiMetricUpsertRequest(
        metric_code="T",
        metric_name="Test",
        major_category="A",
        owner_id=1,
        year=2026,
        score_weight="1.0",
        data_source_type="MANUAL",
        scoring_rule_type="LINEAR",
    )
    called = {"service": False}

    monkeypatch.setattr(
        module,
        "ensure_user_allowed",
        lambda **_kwargs: (_ for _ in ()).throw(PermissionError("blocked")),
    )
    monkeypatch.setattr(
        module.kpi_workbench_service,
        "create_metric",
        lambda **_kwargs: called.__setitem__("service", True),
    )

    with pytest.raises(HTTPException) as denied:
        module.create_kpi_metric(body=body, auth=_auth(module))

    assert denied.value.status_code == 403
    assert called["service"] is False
