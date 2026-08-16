from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from tests.helpers import load_module
from tests.test_fx_analytical_view_service import _seed_fx_duckdb, _write_catalog


def _grant_macro_vendor_read_scope() -> None:
    settings = get_settings()
    UserScopeRepository(settings.governance_sql_dsn or settings.postgres_dsn).grant_scope(
        user_id="*",
        role=None,
        resource="macro_vendor",
        action="read",
    )


def test_fx_api_exposes_formal_status_and_analytical_groups(tmp_path, monkeypatch, seed_wildcard_scope):
    catalog_path = tmp_path / "choice_macro_catalog.json"
    duckdb_path = tmp_path / "market-data.duckdb"
    _write_catalog(catalog_path)
    _seed_fx_duckdb(duckdb_path)
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", str(catalog_path))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    _grant_macro_vendor_read_scope()

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    formal_response = client.get("/ui/market-data/fx/formal-status")
    analytical_response = client.get("/ui/market-data/fx/analytical")

    assert formal_response.status_code == 200
    assert analytical_response.status_code == 200

    formal_payload = formal_response.json()
    analytical_payload = analytical_response.json()

    assert formal_payload["result_meta"]["basis"] == "formal"
    assert formal_payload["result_meta"]["formal_use_allowed"] is True
    assert formal_payload["result"]["candidate_count"] == 2
    assert formal_payload["result"]["carry_forward_count"] == 1
    assert [row["base_currency"] for row in formal_payload["result"]["rows"]] == ["USD", "HKD"]

    assert analytical_payload["result_meta"]["basis"] == "analytical"
    assert analytical_payload["result_meta"]["formal_use_allowed"] is False
    assert [group["group_key"] for group in analytical_payload["result"]["groups"]] == [
        "middle_rate",
        "fx_index",
        "fx_swap_curve",
    ]
    assert analytical_payload["result"]["groups"][0]["series"][0]["series_id"] == "EMM00058124"
    get_settings.cache_clear()
