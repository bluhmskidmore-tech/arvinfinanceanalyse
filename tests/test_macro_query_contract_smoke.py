from pathlib import Path

import duckdb
from backend.app.governance.settings import get_settings
from fastapi.testclient import TestClient

from tests.helpers import load_module


def test_macro_foundation_preview_is_duckdb_backed_and_returns_result_meta(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "empty.duckdb"))
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    response = client.get("/ui/preview/macro-foundation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "preview.macro-foundation"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result"]["read_target"] == "duckdb"
    assert payload["result"]["series"] == []
    get_settings.cache_clear()


def test_macro_foundation_preview_degrades_to_empty_payload_for_corrupt_duckdb(tmp_path, monkeypatch):
    corrupt_duckdb = tmp_path / "corrupt.duckdb"
    corrupt_duckdb.write_text("not-a-duckdb-file", encoding="utf-8")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(corrupt_duckdb))
    get_settings.cache_clear()

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get("/ui/preview/macro-foundation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result"]["read_target"] == "duckdb"
    assert payload["result"]["series"] == []
    get_settings.cache_clear()


def test_macro_foundation_preview_reports_aggregated_vendor_version_from_catalog(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar,
              series_name varchar,
              vendor_name varchar,
              vendor_version varchar,
              frequency varchar,
              unit varchar
            )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              ('cn_cpi_yoy', 'CN CPI YoY', 'choice', 'vv_choice_batch_b', 'monthly', 'pct'),
              ('cn_repo_7d', 'CN Repo 7D', 'choice', 'vv_choice_batch_a', 'daily', 'pct')
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    response = client.get("/ui/preview/macro-foundation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["vendor_version"] == "vv_choice_batch_a__vv_choice_batch_b"
    assert sorted(item["vendor_version"] for item in payload["result"]["series"]) == [
        "vv_choice_batch_a",
        "vv_choice_batch_b",
    ]
    get_settings.cache_clear()
