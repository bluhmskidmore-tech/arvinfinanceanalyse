from __future__ import annotations

import io
import json
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module
from tests.test_ledger_import_flow import (
    _configure_ledger_import_env,
    _ledger_csv_bytes,
    _ledger_row_values,
    _pack_sample,
    _scoped_import,
)

LEDGER_READ_HEADERS = {"X-User-Id": "ledger-read-user", "X-User-Role": "viewer"}


def test_ledger_read_surfaces_require_explicit_read_scope(tmp_path, monkeypatch):
    route_mod = load_module(
        "backend.app.api.routes.ledger",
        "backend/app/api/routes/ledger.py",
    )

    class _StubImportService:
        def __init__(self, _duckdb_path):
            pass

        def list_imports(self):
            return {"data": {"items": []}, "metadata": {"no_data": True}}

    class _StubAnalyticsService:
        def __init__(self, _duckdb_path):
            pass

        def dates(self):
            return {"data": {"items": []}, "metadata": {"no_data": True}}

        def dashboard(self, **_kwargs):
            return {"data": {}, "metadata": {}}

        def positions(self, **_kwargs):
            return {"data": {"items": []}, "metadata": {"no_data": True}}

        def export_positions(self, **_kwargs):
            return "ledger.xlsx", b"xlsx", {}

    class _StubImportModule:
        LedgerImportService = _StubImportService

    class _StubAnalyticsModule:
        XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        LedgerAnalyticsService = _StubAnalyticsService

        @staticmethod
        def normalize_requested_date(*, as_of_date=None):
            return as_of_date

        @staticmethod
        def normalize_filters(**kwargs):
            return kwargs

    monkeypatch.setattr(route_mod, "_svc", lambda: _StubImportModule)
    monkeypatch.setattr(route_mod, "_analytics_svc", lambda: _StubAnalyticsModule)
    sqlite_path = tmp_path / "ledger-read-denied.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", "")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)

    for path, params in (
        ("/api/ledger/import-status", {"run_id": "ledger_import:denied"}),
        ("/api/ledger/imports", {}),
        ("/api/ledger/dates", {}),
        ("/api/ledger/dashboard", {"as_of_date": "2026-03-17"}),
        ("/api/ledger/positions", {"as_of_date": "2026-03-17"}),
        ("/api/ledger/export/positions", {"as_of_date": "2026-03-17"}),
    ):
        response = client.get(path, params=params or None, headers=LEDGER_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_fastapi_application_registers_ledger_analytics_routes(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)

    app = load_module("backend.app.main", "backend/app/main.py").app
    paths = {route.path for route in app.routes}

    assert "/api/ledger/dates" in paths
    assert "/api/ledger/import-status" in paths
    assert "/api/ledger/dashboard" in paths
    assert "/api/ledger/positions" in paths
    assert "/api/ledger/export/positions" in paths
    get_settings.cache_clear()


def test_ledger_dates_dashboard_positions_and_export_use_imported_snapshot(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_two_position_fixture(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    dates = client.get("/api/ledger/dates")
    assert dates.status_code == 200
    assert dates.json()["data"]["items"] == ["2026-03-17"]
    assert dates.json()["metadata"]["batch_id"] == 1
    assert dates.json()["metadata"]["no_data"] is False

    dashboard = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-17"})
    assert dashboard.status_code == 200
    dashboard_payload = dashboard.json()
    assert dashboard_payload["data"] == {
        "as_of_date": "2026-03-17",
        "classification_status": "ready",
        "classification_rule_version": "rv_ledger_classification_v2",
        "currency_breakdown": [
            {"currency": "CNY", "asset_face_amount": 1.0, "liability_face_amount": 0.5, "net_face_exposure": 0.5, "classification_total_row_count": 2, "unclassified_row_count": 0, "unclassified_face_amount": 0.0, "classification_coverage_pct": 100.0},
        ],
    }
    assert dashboard_payload["metadata"]["stale"] is False
    assert dashboard_payload["metadata"]["fallback"] is False
    assert dashboard_payload["trace"]["requested_as_of_date"] == "2026-03-17"
    assert dashboard_payload["trace"]["resolved_as_of_date"] == "2026-03-17"

    positions = client.get(
        "/api/ledger/positions",
        params={
            "as_of_date": "2026-03-17",
            "direction": "ASSET",
            "account_category_std": "银行账户",
            "page": 1,
            "page_size": 10,
        },
    )
    assert positions.status_code == 200
    positions_payload = positions.json()
    assert positions_payload["data"]["total"] == 1
    assert positions_payload["metadata"]["no_data"] is False
    item = positions_payload["data"]["items"][0]
    assert item["direction"] == "ASSET"
    assert item["batch_id"] == 1
    assert item["row_no"] == 1
    assert item["trace"] == {
        "position_key": item["position_key"],
        "batch_id": 1,
        "row_no": 1,
    }
    assert positions_payload["trace"]["filters"]["account_category_std"] == "银行账户"

    exported = client.get(
        "/api/ledger/export/positions",
        params={"as_of_date": "2026-03-17", "direction": "ASSET"},
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert exported.headers["x-ledger-batch-id"] == "1"
    workbook = load_workbook(io.BytesIO(exported.content), read_only=True)
    try:
        rows = list(workbook["positions"].iter_rows(values_only=True))
        metadata = dict(workbook["metadata"].iter_rows(min_row=2, values_only=True))
    finally:
        workbook.close()

    assert rows[0][:3] == ("position_key", "batch_id", "row_no")
    assert len(rows) == 2
    assert rows[1][1:3] == (1, 1)
    assert metadata["as_of_date"] == "2026-03-17"
    assert metadata["requested_as_of_date"] == "2026-03-17"
    assert metadata["resolved_as_of_date"] == "2026-03-17"
    assert metadata["total"] == 1
    assert json.loads(metadata["filters"]) == {
        "account_category_std": None,
        "asset_class_std": None,
        "bond_code": None,
        "cost_center": None,
        "currency": None,
        "direction": "ASSET",
        "portfolio": None,
    }
    get_settings.cache_clear()


def test_dashboard_reports_materialized_classification_quality_and_unclassified_drilldown(
    tmp_path,
    monkeypatch,
):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317-quality.csv",
        content=_ledger_csv_bytes(
            service_mod,
            [
                _ledger_row_values(service_mod, bond_code="A", account_category="银行账户", asset_class="持有至到期类资产", face_amount="100000000", as_of_date="2026-03-17"),
                _ledger_row_values(service_mod, bond_code="L", account_category="发行类债券", asset_class="发行类债券", face_amount="50000000", as_of_date="2026-03-17"),
                _ledger_row_values(service_mod, bond_code="U", account_category="银行账户", asset_class="未知分类", face_amount="25000000", as_of_date="2026-03-17"),
            ],
        ),
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    dashboard = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-17"}).json()
    assert dashboard["data"] == {
        "as_of_date": "2026-03-17",
        "classification_status": "ready",
        "classification_rule_version": "rv_ledger_classification_v2",
        "currency_breakdown": [
            {
                "currency": "CNY",
                "asset_face_amount": 1.0,
                "liability_face_amount": 0.5,
                "net_face_exposure": 0.5,
                "classification_total_row_count": 3,
                "unclassified_row_count": 1,
                "unclassified_face_amount": 0.25,
                "classification_coverage_pct": 66.67,
            }
        ],
    }
    positions = client.get(
        "/api/ledger/positions",
        params={"as_of_date": "2026-03-17", "direction": "UNCLASSIFIED"},
    )
    assert positions.status_code == 200
    assert positions.json()["data"]["items"][0]["bond_code"] == "U"
    assert positions.json()["trace"]["filters"]["direction"] == "UNCLASSIFIED"

    exported = client.get(
        "/api/ledger/export/positions",
        params={"as_of_date": "2026-03-17", "direction": "unclassified"},
    )
    assert exported.status_code == 200
    workbook = load_workbook(io.BytesIO(exported.content), read_only=True)
    try:
        rows = list(workbook["positions"].iter_rows(values_only=True))
        metadata = dict(workbook["metadata"].iter_rows(min_row=2, values_only=True))
    finally:
        workbook.close()
    assert len(rows) == 2
    header, item = rows
    assert item[header.index("direction")] == "UNCLASSIFIED"
    assert item[header.index("position_key")]
    assert item[header.index("batch_id")] == 1
    assert item[header.index("row_no")] == 3
    assert item[header.index("account_category_std")] == "银行账户"
    assert item[header.index("asset_class_std")] == "未知分类"
    assert json.loads(metadata["filters"])["direction"] == "UNCLASSIFIED"


@pytest.mark.parametrize("noncurrent_rule", ["position_key_contract_v1", None, "rv_other"])
def test_dashboard_mixed_rule_batch_is_legacy_unassessed(
    tmp_path,
    monkeypatch,
    noncurrent_rule,
):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_two_position_fixture(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            "update position_snapshot set rule_version = ? where row_no = 1",
            [noncurrent_rule],
        )
    finally:
        conn.close()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    dates = client.get("/api/ledger/dates").json()
    assert dates["metadata"]["rule_version"] == "mixed"

    payload = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-17"}).json()
    assert payload["data"]["classification_status"] == "legacy_unassessed"
    assert payload["metadata"]["rule_version"] != "rv_ledger_classification_v2"
    assert payload["data"]["currency_breakdown"] == [
        {
            "currency": "CNY",
            "asset_face_amount": None,
            "liability_face_amount": None,
            "net_face_exposure": None,
            "classification_total_row_count": 2,
            "unclassified_row_count": None,
            "unclassified_face_amount": None,
            "classification_coverage_pct": None,
        }
    ]

@pytest.mark.parametrize("invalid_direction", [None, "ASSETT", "OTHER"])
def test_dashboard_invalid_materialized_direction_fails_closed(
    tmp_path,
    monkeypatch,
    invalid_direction,
):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_two_position_fixture(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            "update position_snapshot set direction = ? where row_no = 1",
            [invalid_direction],
        )
    finally:
        conn.close()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    payload = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-17"}).json()
    assert payload["metadata"]["rule_version"] == "rv_ledger_classification_v2"
    assert payload["data"]["classification_status"] == "invalid_materialization"
    assert payload["data"]["currency_breakdown"] == [
        {
            "currency": "CNY",
            "asset_face_amount": None,
            "liability_face_amount": None,
            "net_face_exposure": None,
            "classification_total_row_count": 2,
            "unclassified_row_count": None,
            "unclassified_face_amount": None,
            "classification_coverage_pct": None,
        }
    ]

def test_dashboard_only_unclassified_with_null_face_keeps_all_amounts_null(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317-unclassified-null.csv",
        content=_ledger_csv_bytes(
            service_mod,
            [_ledger_row_values(service_mod, bond_code="U-NULL", account_category="银行账户", asset_class="未知分类", face_amount="", as_of_date="2026-03-17")],
        ),
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    bucket = client.get(
        "/api/ledger/dashboard",
        params={"as_of_date": "2026-03-17"},
    ).json()["data"]["currency_breakdown"][0]
    assert bucket == {
        "currency": "CNY",
        "asset_face_amount": None,
        "liability_face_amount": None,
        "net_face_exposure": None,
        "classification_total_row_count": 1,
        "unclassified_row_count": 1,
        "unclassified_face_amount": None,
        "classification_coverage_pct": 0.0,
    }

def test_dashboard_fails_closed_for_legacy_classification_rule(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_two_position_fixture(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("update position_snapshot set rule_version = 'position_key_contract_v1'")
    finally:
        conn.close()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    payload = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-17"}).json()
    assert payload["data"] == {
        "as_of_date": "2026-03-17",
        "classification_status": "legacy_unassessed",
        "classification_rule_version": "rv_ledger_classification_v2",
        "currency_breakdown": [
            {
                "currency": "CNY",
                "asset_face_amount": None,
                "liability_face_amount": None,
                "net_face_exposure": None,
                "classification_total_row_count": 2,
                "unclassified_row_count": None,
                "unclassified_face_amount": None,
                "classification_coverage_pct": None,
            }
        ],
    }

def test_ledger_get_read_surfaces_open_duckdb_read_only(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_two_position_fixture(duckdb_path)
    original_connect = duckdb.connect
    observed_read_modes: list[bool | None] = []

    def guarded_connect(database=":memory:", *args, **kwargs):
        read_only = kwargs.get("read_only")
        if read_only is None and args and isinstance(args[0], bool):
            read_only = args[0]
        if str(database) == str(duckdb_path):
            observed_read_modes.append(read_only)
            if read_only is False:
                raise RuntimeError("ledger GET read surfaces must open DuckDB read-only")
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", guarded_connect)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    requests = (
        ("/api/ledger/imports", {}),
        ("/api/ledger/dates", {}),
        ("/api/ledger/dashboard", {"as_of_date": "2026-03-17"}),
        ("/api/ledger/positions", {"as_of_date": "2026-03-17", "page": 1, "page_size": 10}),
        ("/api/ledger/export/positions", {"as_of_date": "2026-03-17"}),
    )

    for path, params in requests:
        response = client.get(path, params=params or None)
        assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"

    assert observed_read_modes
    assert set(observed_read_modes) == {True}
    get_settings.cache_clear()


def test_ledger_dashboard_ignores_existing_zqtz_snapshot_source(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _insert_zqtz_snapshot_fixture(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    dates = client.get("/api/ledger/dates").json()
    assert dates["data"]["items"] == []
    assert dates["metadata"]["no_data"] is True
    dashboard = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-31"}).json()
    assert dashboard["data"] == {"as_of_date": None, "classification_status": "ready", "classification_rule_version": "rv_ledger_classification_v2", "currency_breakdown": []}
    assert dashboard["metadata"]["no_data"] is True
    positions = client.get("/api/ledger/positions", params={"as_of_date": "2026-03-31"}).json()
    assert positions["data"]["total"] == 0
    get_settings.cache_clear()

def test_ledger_imports_and_dates_reject_unknown_query_parameters(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_two_position_fixture(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    imports = client.get("/api/ledger/imports", params={"foo": "bar"})
    dates = client.get("/api/ledger/dates", params={"foo": "bar"})

    assert imports.status_code == 400
    assert imports.json()["error"]["code"] == "LEDGER_IMPORTS_INVALID_REQUEST"
    assert dates.status_code == 400
    assert dates.json()["error"]["code"] == "LEDGER_DATES_INVALID_REQUEST"
    get_settings.cache_clear()


def test_ledger_import_rejects_unknown_query_parameters(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post("/api/ledger/import", params={"foo": "bar"}, content=b"")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LEDGER_IMPORT_INVALID_REQUEST"
    assert "Unsupported query parameter" in response.json()["error"]["message"]
    get_settings.cache_clear()


def test_ledger_dashboard_falls_back_to_latest_snapshot(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_two_position_fixture(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-18"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["as_of_date"] == "2026-03-17"
    assert payload["metadata"]["stale"] is True
    assert payload["metadata"]["fallback"] is True
    assert payload["trace"]["requested_as_of_date"] == "2026-03-18"
    assert payload["trace"]["resolved_as_of_date"] == "2026-03-17"
    get_settings.cache_clear()


def test_ledger_export_fallback_metadata_preserves_requested_and_resolved_dates(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_two_position_fixture(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get(
        "/api/ledger/export/positions",
        params={"as_of_date": "2026-03-18", "direction": "ASSET"},
    )

    assert response.status_code == 200
    assert response.headers["x-ledger-fallback"] == "true"
    workbook = load_workbook(io.BytesIO(response.content), read_only=True)
    try:
        metadata = dict(workbook["metadata"].iter_rows(min_row=2, values_only=True))
    finally:
        workbook.close()
    assert metadata["requested_as_of_date"] == "2026-03-18"
    assert metadata["resolved_as_of_date"] == "2026-03-17"
    assert metadata["fallback"] is True
    get_settings.cache_clear()


def test_ledger_dashboard_keeps_missing_side_null_but_net_uses_known_side(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="LIABILITY-ONLY",
                account_category="发行类债券",
                asset_class="发行类债券",
                face_amount="100000000",
                as_of_date="2026-03-17",
            ),
        ],
    )
    _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317.csv",
        content=csv_bytes,
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-17"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["currency_breakdown"] == [
        {"currency": "CNY", "asset_face_amount": None, "liability_face_amount": 1.0, "net_face_exposure": -1.0, "classification_total_row_count": 1, "unclassified_row_count": 0, "unclassified_face_amount": 0.0, "classification_coverage_pct": 100.0},
    ]
    get_settings.cache_clear()


def test_ledger_dashboard_no_data_keeps_all_kpis_null(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-17"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] == {"as_of_date": None, "classification_status": "ready", "classification_rule_version": "rv_ledger_classification_v2", "currency_breakdown": []}

    assert payload["metadata"]["no_data"] is True
    get_settings.cache_clear()


def test_ledger_batch2_rejects_non_contract_query_aliases_and_bad_dates(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_two_position_fixture(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    date_alias = client.get("/api/ledger/dashboard", params={"date": "2026-03-17"})
    bad_date = client.get("/api/ledger/dashboard", params={"as_of_date": "20260317"})
    account_alias = client.get(
        "/api/ledger/positions",
        params={"as_of_date": "2026-03-17", "account_category": "银行账户"},
    )
    asset_alias = client.get(
        "/api/ledger/export/positions",
        params={"as_of_date": "2026-03-17", "asset_class": "持有至到期类资产"},
    )

    assert date_alias.status_code == 400
    assert "Unsupported query parameter" in date_alias.json()["error"]["message"]
    assert bad_date.status_code == 400
    assert "YYYY-MM-DD" in bad_date.json()["error"]["message"]
    assert account_alias.status_code == 400
    assert "account_category" in account_alias.json()["error"]["message"]
    assert asset_alias.status_code == 400
    assert "asset_class" in asset_alias.json()["error"]["message"]
    get_settings.cache_clear()


def test_ledger_positions_no_data_and_invalid_direction_are_explicit(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_two_position_fixture(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    no_data = client.get(
        "/api/ledger/positions",
        params={"as_of_date": "2026-03-17", "direction": "ASSET", "portfolio": "NO-SUCH"},
    )
    assert no_data.status_code == 200
    assert no_data.json()["data"]["items"] == []
    assert no_data.json()["data"]["total"] == 0
    assert no_data.json()["metadata"]["no_data"] is True

    invalid = client.get(
        "/api/ledger/positions",
        params={"as_of_date": "2026-03-17", "direction": "SIDEWAYS"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "LEDGER_POSITIONS_INVALID_REQUEST"
    get_settings.cache_clear()


def test_ledger_dashboard_real_pack_20260317_golden_kpis(tmp_path, monkeypatch):
    sample = _pack_sample("ZQTZSHOW-20260317.xls")
    if sample is None:
        pytest.skip("bank ledger pack sample ZQTZSHOW-20260317.xls is not available")
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    _scoped_import(
        service_mod,
        duckdb_path,
        file_name=Path(sample).name,
        content=Path(sample).read_bytes(),
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-17"})

    assert response.status_code == 200
    payload = response.json()
    cny = next(
        item for item in payload["data"]["currency_breakdown"] if item["currency"] == "CNY"
    )
    assert cny["asset_face_amount"] == 3289.07
    assert cny["liability_face_amount"] == 1231.77
    assert cny["net_face_exposure"] == 2057.31
    assert "asset_face_amount" not in payload["data"]
    assert "liability_face_amount" not in payload["data"]
    assert "net_face_exposure" not in payload["data"]
    assert "alert_count" not in payload["data"]
    assert payload["metadata"]["source_version"].startswith("sv_ledger_")
    assert payload["metadata"]["rule_version"] == "rv_ledger_classification_v2"
    get_settings.cache_clear()


def test_ledger_schema_registry_adds_position_snapshot_agg():
    loader = load_module(
        "backend.app.schema_registry.duckdb_loader",
        "backend/app/schema_registry/duckdb_loader.py",
    )
    conn = duckdb.connect(":memory:")
    try:
        loader.apply_registry_sql(conn)
        tables = {
            row[0]
            for row in conn.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'main'
                """
            ).fetchall()
        }
    finally:
        conn.close()

    assert "position_snapshot_agg" in tables


def _import_two_position_fixture(duckdb_path: Path) -> None:
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="ASSET-001",
                account_category="银行账户",
                asset_class="持有至到期类资产",
                face_amount="100000000",
                as_of_date="2026-03-17",
            ),
            _ledger_row_values(
                service_mod,
                bond_code="LIABILITY-001",
                account_category="发行类债券",
                asset_class="发行类债券",
                face_amount="50000000",
                as_of_date="2026-03-17",
            ),
        ],
    )
    _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317.csv",
        content=csv_bytes,
    )


def _insert_zqtz_snapshot_fixture(duckdb_path: Path) -> None:
    snapshot_mod = load_module(
        "backend.app.repositories.snapshot_repo",
        "backend/app/repositories/snapshot_repo.py",
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        snapshot_mod.ensure_snapshot_tables(conn)
        rows = [
            ("ASSET-ZQTZ-001", "Asset bond", False, "asset-trace", 100000000),
            ("LIAB-ZQTZ-001", "Issued bond", True, "liability-trace", 50000000),
        ]
        conn.executemany(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, business_type_primary, issuer_name,
              industry_name, rating, currency_code, face_value_native, market_value_native,
              amortized_cost_native, accrued_interest_native, coupon_rate, ytm_value,
              maturity_date, next_call_date, overdue_days, is_issuance_like, interest_mode,
              source_version, rule_version, ingest_batch_id, trace_id, value_date, customer_attribute
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                [
                    "2026-03-31",
                    code,
                    name,
                    "BANK-BOOK",
                    "5010",
                    "ISSUANCE" if issuance else "BANK",
                    "ISSUANCE" if issuance else "HOLD_TO_MATURITY",
                    "TEST",
                    "TEST_BUSINESS",
                    "Issuer",
                    "Banking",
                    "AAA",
                    "CNY",
                    face,
                    face,
                    face,
                    0,
                    "0.03",
                    "0.031",
                    "2030-03-31",
                    None,
                    0,
                    issuance,
                    "FIXED",
                    "sv-existing-zqtz",
                    "rv_snapshot_zqtz_tyw_v1",
                    "ib-existing-zqtz",
                    trace_id,
                    "2026-03-31",
                    "CORP",
                ]
                for code, name, issuance, trace_id, face in rows
            ],
        )
    finally:
        conn.close()


def test_ledger_unblock_prefers_imported_snapshot_and_splits_currency(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_currency_position_fixture(duckdb_path)
    _insert_zqtz_snapshot_fixture(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    assert client.get("/api/ledger/dates").json()["data"]["items"] == ["2026-03-17"]
    payload = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-17"}).json()
    assert payload["data"] == {
        "as_of_date": "2026-03-17",
        "classification_status": "ready",
        "classification_rule_version": "rv_ledger_classification_v2",
        "currency_breakdown": [
            {"currency": "CNY", "asset_face_amount": 1.0, "liability_face_amount": 0.5, "net_face_exposure": 0.5, "classification_total_row_count": 2, "unclassified_row_count": 0, "unclassified_face_amount": 0.0, "classification_coverage_pct": 100.0},
            {"currency": "USD", "asset_face_amount": 2.0, "liability_face_amount": None, "net_face_exposure": 2.0, "classification_total_row_count": 1, "unclassified_row_count": 0, "unclassified_face_amount": 0.0, "classification_coverage_pct": 100.0},
        ],
    }
    assert "asset_face_amount" not in payload["data"]
    assert "alert_count" not in payload["data"]
    get_settings.cache_clear()


def test_ledger_unblock_zqtz_only_is_no_data(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _insert_zqtz_snapshot_fixture(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    assert client.get("/api/ledger/dates").json()["data"]["items"] == []
    payload = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-31"}).json()
    assert payload["data"] == {"as_of_date": None, "classification_status": "ready", "classification_rule_version": "rv_ledger_classification_v2", "currency_breakdown": []}
    assert payload["metadata"]["no_data"] is True
    get_settings.cache_clear()


def test_ledger_unblock_fallback_is_past_only(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_two_position_fixture(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    before = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-16"}).json()
    assert before["data"] == {"as_of_date": None, "classification_status": "ready", "classification_rule_version": "rv_ledger_classification_v2", "currency_breakdown": []}
    assert before["metadata"]["no_data"] is True
    after = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-18"}).json()
    assert after["data"]["as_of_date"] == "2026-03-17"
    assert after["metadata"]["fallback"] is True
    get_settings.cache_clear()


def test_ledger_unblock_currency_filters_positions_and_export(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    _import_currency_position_fixture(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    positions = client.get("/api/ledger/positions", params={"as_of_date": "2026-03-17", "currency": " usd "})
    assert positions.status_code == 200
    payload = positions.json()
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["currency"] == "USD"
    assert payload["trace"]["filters"]["currency"] == "USD"

    exported = client.get("/api/ledger/export/positions", params={"as_of_date": "2026-03-17", "currency": "usd"})
    assert exported.status_code == 200
    workbook = load_workbook(io.BytesIO(exported.content), read_only=True)
    try:
        rows = list(workbook["positions"].iter_rows(values_only=True))
        metadata = dict(workbook["metadata"].iter_rows(min_row=2, values_only=True))
    finally:
        workbook.close()
    assert len(rows) == 2
    assert rows[1][rows[0].index("currency")] == "USD"
    assert json.loads(metadata["filters"])["currency"] == "USD"
    get_settings.cache_clear()


def _import_currency_position_fixture(duckdb_path: Path) -> None:
    service_mod = load_module("backend.app.services.ledger_import_service", "backend/app/services/ledger_import_service.py")
    rows = [
        _ledger_row_values(service_mod, bond_code="ASSET-CNY", account_category="\u94f6\u884c\u8d26\u6237", asset_class="持有至到期类资产", face_amount="100000000", as_of_date="2026-03-17"),
        _ledger_row_values(service_mod, bond_code="LIABILITY-CNY", account_category="\u53d1\u884c\u7c7b\u503a\u5238", asset_class="\u53d1\u884c\u7c7b\u503a\u5238", face_amount="50000000", as_of_date="2026-03-17"),
        _ledger_row_values(service_mod, bond_code="ASSET-USD", account_category="\u94f6\u884c\u8d26\u6237", asset_class="持有至到期类资产", face_amount="200000000", as_of_date="2026-03-17"),
    ]
    currency_index = next(index for index, spec in enumerate(service_mod.FIELD_SPECS) if spec.standard_field == "currency")
    rows[2][currency_index] = " usd "
    _scoped_import(service_mod, duckdb_path, file_name="ZQTZSHOW-20260317-currency.csv", content=_ledger_csv_bytes(service_mod, rows))


def test_ledger_backfill_unblocks_same_kpis_without_changing_values(tmp_path, monkeypatch):
    import shutil
    from backend.app.tasks.ledger_classification_backfill import apply_backfill_plan, build_backfill_plan

    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    content = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(service_mod, bond_code="A", account_category="银行账户", asset_class="持有至到期类资产", face_amount="100000000", as_of_date="2026-03-17"),
            _ledger_row_values(service_mod, bond_code="L", account_category="发行类债券", asset_class="发行类债券", face_amount="50000000", as_of_date="2026-03-17"),
        ],
    )
    _scoped_import(service_mod, duckdb_path, file_name="source.csv", content=content)
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "renamed.csv").write_bytes(content)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        before_rows = conn.execute(
            "select batch_id, row_no, direction, face_amount, position_key from position_snapshot order by batch_id, row_no"
        ).fetchall()
        for table in ("ledger_import_batch", "ledger_raw_row", "position_snapshot"):
            conn.execute(f"update {table} set rule_version = 'position_key_contract_v1'")
    finally:
        conn.close()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    legacy = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-17"}).json()
    assert legacy["data"]["classification_status"] == "legacy_unassessed"
    assert legacy["data"]["currency_breakdown"][0]["asset_face_amount"] is None

    plan = build_backfill_plan(duckdb_path, [1], source_dir)
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(duckdb_path, backup)
    apply_backfill_plan(
        db_path=duckdb_path,
        batch_ids=[1],
        source_dir=source_dir,
        expected_plan_digest=plan["plan_digest"],
        target_backup_path=backup,
        receipt_path=tmp_path / "receipt.json",
    )
    ready = client.get("/api/ledger/dashboard", params={"as_of_date": "2026-03-17"}).json()
    assert ready["data"]["classification_status"] == "ready"
    assert ready["data"]["currency_breakdown"][0]["asset_face_amount"] == 1.0
    assert ready["data"]["currency_breakdown"][0]["liability_face_amount"] == 0.5
    assert ready["data"]["currency_breakdown"][0]["net_face_exposure"] == 0.5
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        after_rows = conn.execute(
            "select batch_id, row_no, direction, face_amount, position_key from position_snapshot order by batch_id, row_no"
        ).fetchall()
    finally:
        conn.close()
    assert after_rows == before_rows