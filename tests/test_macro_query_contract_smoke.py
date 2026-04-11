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


def test_choice_macro_latest_ignores_empty_snapshot_table_when_fact_rows_exist(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro-latest.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_market_snapshot (
              series_id varchar,
              series_name varchar,
              vendor_series_code varchar,
              vendor_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              (
                'cn_cpi_yoy',
                'CN CPI YoY',
                '2026-04-09',
                0.7,
                'monthly',
                'pct',
                'sv_choice_macro_20260409',
                'vv_choice_batch_b',
                'rv_choice_macro_thin_slice_v1',
                'ok',
                'choice_macro_refresh:2026-04-09T14:00:00Z'
              )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    response = client.get("/ui/macro/choice-series/latest")

    assert response.status_code == 200
    payload = response.json()
    assert [item["series_id"] for item in payload["result"]["series"]] == ["cn_cpi_yoy"]
    assert payload["result_meta"]["vendor_version"] == "vv_choice_batch_b"
    get_settings.cache_clear()


def test_choice_macro_latest_supports_legacy_catalog_schema(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro-legacy-catalog.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
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
            insert into fact_choice_macro_daily values
              (
                'cn_repo_7d',
                'CN Repo 7D',
                '2026-04-09',
                1.82,
                'daily',
                'pct',
                'sv_choice_macro_20260409',
                'vv_choice_batch_b',
                'rv_choice_macro_thin_slice_v1',
                'ok',
                'choice_macro_refresh:2026-04-09T14:00:00Z'
              )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              (
                'cn_repo_7d',
                'CN Repo 7D',
                'choice',
                'vv_choice_batch_b',
                'daily',
                'pct'
              )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )

    payload = route_module.choice_series_latest()
    assert [item["series_id"] for item in payload["result"]["series"]] == ["cn_repo_7d"]
    assert payload["result"]["series"][0]["refresh_tier"] is None
    assert "vendor_series_code" not in payload["result"]["series"][0]
    assert "batch_id" not in payload["result"]["series"][0]
    assert payload["result_meta"]["vendor_version"] == "vv_choice_batch_b"
    get_settings.cache_clear()


def test_choice_macro_latest_excludes_isolated_rows_and_exposes_policy_fields(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro-policy-filter.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar,
              series_name varchar,
              vendor_name varchar,
              vendor_version varchar,
              frequency varchar,
              unit varchar,
              vendor_series_code varchar,
              batch_id varchar,
              catalog_version varchar,
              theme varchar,
              is_core boolean,
              tags_json varchar,
              request_options varchar,
              fetch_mode varchar,
              fetch_granularity varchar,
              refresh_tier varchar,
              policy_note varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              (
                'cn_repo_7d',
                'CN Repo 7D',
                '2026-04-09',
                1.82,
                'daily',
                'pct',
                'sv_choice_macro_20260409',
                'vv_choice_batch_b',
                'rv_choice_macro_thin_slice_v1',
                'ok',
                'choice_macro_refresh:2026-04-09T14:00:00Z'
              ),
              (
                'cn_shibor_on',
                'CN Shibor ON',
                '2026-04-09',
                1.95,
                'daily',
                'pct',
                'sv_choice_macro_20260409',
                'vv_choice_batch_b',
                'rv_choice_macro_thin_slice_v1',
                'warning',
                'choice_macro_refresh:2026-04-09T14:00:00Z'
              )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              (
                'cn_repo_7d',
                'CN Repo 7D',
                'choice',
                'vv_choice_batch_b',
                'daily',
                'pct',
                'EDB_REPO_7D',
                'stable_daily',
                '2026-04-11.choice-macro.v2',
                'liquidity',
                true,
                '["china","rates","liquidity"]',
                'IsLatest=0,StartDate=2026-04-09,EndDate=2026-04-09,Ispandas=1,RECVtimeout=5',
                'date_slice',
                'batch',
                'stable',
                'main refresh date-slice lane'
              ),
              (
                'cn_shibor_on',
                'CN Shibor ON',
                'choice',
                'vv_choice_batch_b',
                'daily',
                'pct',
                'EDB_SHIBOR_ON',
                'isolated_vendor_pending',
                '2026-04-11.choice-macro.v2',
                'rates',
                false,
                '["china","rates","vendor_pending"]',
                'IsLatest=1,RowIndex=1,Ispandas=1,RECVtimeout=5',
                'latest',
                'single',
                'isolated',
                'wait for vendor permission or interface confirmation'
              )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )

    payload = route_module.choice_series_latest()
    assert [item["series_id"] for item in payload["result"]["series"]] == ["cn_repo_7d"]
    assert payload["result"]["series"][0]["refresh_tier"] == "stable"
    assert payload["result"]["series"][0]["fetch_mode"] == "date_slice"
    assert payload["result"]["series"][0]["fetch_granularity"] == "batch"
    assert payload["result"]["series"][0]["policy_note"] == "main refresh date-slice lane"
    assert "vendor_series_code" not in payload["result"]["series"][0]
    assert "batch_id" not in payload["result"]["series"][0]
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
