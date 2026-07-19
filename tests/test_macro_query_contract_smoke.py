import logging
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.services.macro_vendor_service import (
    choice_macro_formal_envelope,
    choice_macro_refresh_status,
    load_choice_macro_latest_payload,
)
from tests.helpers import load_module

MACRO_VENDOR_READ_HEADERS = {"X-User-Id": "macro-vendor-read-user", "X-User-Role": "viewer"}


def _perf_records(caplog, endpoint: str):
    return [
        record
        for record in caplog.records
        if record.name == "backend.app.api.perf" and getattr(record, "endpoint", None) == endpoint
    ]


def _configure_macro_vendor_scope_store(tmp_path: Path, monkeypatch):
    sqlite_path = tmp_path / "macro-vendor-read-scope.db"
    auth_dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", auth_dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", auth_dsn)
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_mod = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    return repo_mod.UserScopeRepository(auth_dsn)


def _seed_macro_vendor_read_scope(tmp_path: Path, monkeypatch) -> None:
    _configure_macro_vendor_scope_store(tmp_path, monkeypatch).grant_scope(
        user_id="*",
        role=None,
        resource="macro_vendor",
        action="read",
    )


def _macro_vendor_read_auth(route_module):
    return route_module.AuthContext(
        user_id=MACRO_VENDOR_READ_HEADERS["X-User-Id"],
        role=MACRO_VENDOR_READ_HEADERS["X-User-Role"],
        identity_source="test",
    )


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/ui/market-data/rates", {}),
        ("/ui/market-data/catalog", {}),
        ("/ui/preview/macro-foundation", {}),
        ("/ui/macro/choice-series/latest", {}),
        ("/ui/market-data/fx/formal-status", {}),
        ("/ui/market-data/fx/analytical", {}),
        ("/ui/macro/choice-series/refresh-status", {}),
    ],
)
def test_macro_vendor_read_surfaces_require_explicit_read_scope(
    path: str,
    params: dict[str, object],
    tmp_path: Path,
    monkeypatch,
) -> None:
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )
    _configure_macro_vendor_scope_store(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "missing.duckdb"))
    route_module.market_home_response_cache.invalidate()

    def _unexpected_service_call(*_args, **_kwargs):
        raise AssertionError("Macro vendor read service should not run without macro_vendor/read.")

    monkeypatch.setattr(route_module, "choice_macro_formal_envelope", _unexpected_service_call)
    monkeypatch.setattr(route_module, "macro_foundation_formal_envelope", _unexpected_service_call)
    monkeypatch.setattr(route_module, "macro_vendor_envelope", _unexpected_service_call)
    monkeypatch.setattr(route_module, "choice_macro_latest_envelope", _unexpected_service_call)
    monkeypatch.setattr(route_module, "fx_formal_status_envelope", _unexpected_service_call)
    monkeypatch.setattr(route_module, "fx_analytical_envelope", _unexpected_service_call)
    monkeypatch.setattr(route_module, "choice_macro_refresh_status", _unexpected_service_call)

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(path, params=params, headers=MACRO_VENDOR_READ_HEADERS)

    assert response.status_code == 403, f"Expected 403 for {path}, got {response.status_code}: {response.text}"


def test_choice_macro_refresh_status_reads_governance_runs(tmp_path):
    governance_mod = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    governance_mod.GovernanceRepository(base_dir=tmp_path).append(
        governance_mod.CACHE_BUILD_RUN_STREAM,
        {
            "job_name": "choice_macro_refresh",
            "cache_key": "choice_macro.latest",
            "run_id": "choice-run-1",
            "status": "running",
        },
    )

    payload = choice_macro_refresh_status(tmp_path, run_id="choice-run-1")

    assert payload["run_id"] == "choice-run-1"
    assert payload["trigger_mode"] == "async"
    with pytest.raises(ValueError, match="missing-run"):
        choice_macro_refresh_status(tmp_path, run_id="missing-run")


def test_macro_foundation_preview_is_duckdb_backed_and_returns_result_meta(tmp_path, monkeypatch):
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "empty.duckdb"))
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    response = client.get("/ui/preview/macro-foundation", headers=MACRO_VENDOR_READ_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "preview.macro-foundation"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert payload["result_meta"]["fallback_mode"] == "none"
    assert payload["result"]["read_target"] == "duckdb"
    assert payload["result"]["series"] == []
    get_settings.cache_clear()


def test_market_data_rates_logs_api_perf(tmp_path, monkeypatch, caplog):
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "empty-rates-perf.duckdb"))
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    with caplog.at_level(logging.INFO, logger="backend.app.api.perf"):
        response = client.get("/ui/market-data/rates", headers=MACRO_VENDOR_READ_HEADERS)

    assert response.status_code == 200
    records = _perf_records(caplog, "/ui/market-data/rates")
    assert records
    record = records[-1]
    assert record.getMessage() == (
        f'moss_api_perf endpoint="{record.endpoint}" duration_ms={record.duration_ms} '
        f'trace_id="{record.trace_id}" result_kind="{record.result_kind}" '
        "duckdb_statement_count=null"
    )
    assert getattr(record, "duration_ms") >= 0
    assert getattr(record, "result_kind")
    get_settings.cache_clear()


def test_market_data_rates_merges_formal_yield_curve_history_for_single_point_choice_rates(tmp_path):
    duckdb_path = tmp_path / "market-data-rates-formal-history.duckdb"
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
              fetch_mode varchar,
              fetch_granularity varchar,
              refresh_tier varchar,
              policy_note varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_yield_curve_daily (
              trade_date varchar,
              curve_type varchar,
              tenor varchar,
              rate_pct decimal(18,8),
              vendor_name varchar,
              vendor_version varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              (
                'EMM00166460',
                'China treasury yield 3Y',
                '2026-06-11',
                1.3141,
                'daily',
                'unknown',
                'sv_choice_single_3y',
                'vv_choice_single',
                'rv_choice_macro_thin_slice_v1',
                'ok',
                'choice-single'
              )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              (
                'EMM00166460',
                'China treasury yield 3Y',
                'choice',
                'vv_choice_single',
                'daily',
                'unknown',
                'date_slice',
                'batch',
                'stable',
                'stable rate series'
              )
            """
        )
        conn.execute(
            """
            insert into fact_formal_yield_curve_daily values
              ('2026-05-29', 'treasury', '3Y', 1.2705, 'akshare', 'vv_formal_curve', 'sv_formal_curve_0529', 'rv_yield_curve_formal_materialize_v1'),
              ('2026-04-30', 'treasury', '3Y', 1.2802, 'akshare', 'vv_formal_curve', 'sv_formal_curve_0430', 'rv_yield_curve_formal_materialize_v1')
            """
        )
    finally:
        conn.close()

    payload = choice_macro_formal_envelope(str(duckdb_path))

    series_by_id = {item["series_id"]: item for item in payload["result"]["series"]}
    point = series_by_id["EMM00166460"]
    assert point["trade_date"] == "2026-06-11"
    assert point["unit"] == "%"
    assert point["latest_change"] == pytest.approx(0.0436)
    assert [item["trade_date"] for item in point["recent_points"][:3]] == [
        "2026-06-11",
        "2026-05-29",
        "2026-04-30",
    ]


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
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    response = client.get("/ui/macro/choice-series/latest", headers=MACRO_VENDOR_READ_HEADERS)

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
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )

    payload = route_module.choice_series_latest(auth=_macro_vendor_read_auth(route_module))
    assert [item["series_id"] for item in payload["result"]["series"]] == ["cn_repo_7d"]
    assert payload["result"]["series"][0]["refresh_tier"] is None
    assert "vendor_series_code" not in payload["result"]["series"][0]
    assert "batch_id" not in payload["result"]["series"][0]
    assert payload["result_meta"]["vendor_version"] == "vv_choice_batch_b"
    get_settings.cache_clear()


def test_choice_macro_latest_reads_persisted_market_data_categories(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro-persisted-categories.duckdb"
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
            create table market_data_series_category (
              series_id varchar,
              category_key varchar,
              category_label varchar,
              source_surface varchar,
              fetch_mode varchar,
              fetch_granularity varchar,
              policy_note varchar,
              catalog_version varchar,
              batch_id varchar,
              updated_at varchar,
              run_id varchar
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
        conn.execute(
            """
            insert into market_data_series_category values
              (
                'cn_repo_7d',
                'fallback',
                'Fallback latest-only series',
                'choice_macro',
                'latest',
                'single',
                'persisted category read path',
                '2026-04-11.choice-macro.v2',
                'fallback_latest_single',
                '2026-04-09T14:00:00Z',
                'choice_macro_refresh:2026-04-09T14:00:00Z'
              )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )

    payload = route_module.choice_series_latest(auth=_macro_vendor_read_auth(route_module))
    row = payload["result"]["series"][0]
    assert row["series_id"] == "cn_repo_7d"
    assert row["refresh_tier"] == "fallback"
    assert row["fetch_mode"] == "latest"
    assert row["fetch_granularity"] == "single"
    assert row["policy_note"] == "persisted category read path"
    get_settings.cache_clear()


def test_choice_macro_latest_exposes_vendor_name_without_vendor_code(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro-latest-vendor-name.duckdb"
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
                'CA.MEGA_CAP_WEIGHT',
                '沪深300前十大权重合计',
                '2026-04-10',
                23.5367,
                'daily',
                '%',
                'sv_tushare_index_weight',
                'vv_tushare_index_weight',
                'rv_public_cross_asset_headline_v1',
                'ok',
                'public_cross_asset_refresh:2026-04-10'
              )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              (
                'CA.MEGA_CAP_WEIGHT',
                '沪深300前十大权重合计',
                'tushare',
                'vv_tushare_index_weight',
                'daily',
                '%',
                'index_weight:000300.SH.top10_weight',
                'public_cross_asset_headline',
                '2026-04-21.public-cross-asset-headline.v1',
                'macro_market',
                true,
                '["tushare","market","equity","mega_cap","cross_asset"]',
                'lookback_days=60',
                'date_slice',
                'batch',
                'stable',
                'Tushare index_weight top10 concentration supplement for mega-cap equity leadership'
              )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )

    payload = route_module.choice_series_latest(auth=_macro_vendor_read_auth(route_module))

    point = payload["result"]["series"][0]
    assert point["series_id"] == "CA.MEGA_CAP_WEIGHT"
    assert point["vendor_name"] == "tushare"
    assert "vendor_series_code" not in point
    assert "batch_id" not in point
    get_settings.cache_clear()


def test_choice_macro_refresh_also_runs_public_cross_asset_headlines(monkeypatch):
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )
    calls: list[tuple[str, int | None]] = []

    class _ChoiceRefresh:
        @staticmethod
        def fn(backfill_days: int = 0) -> dict[str, object]:
            calls.append(("choice", backfill_days))
            return {
                "status": "completed",
                "run_id": "choice_macro_refresh:test",
                "series_count": 2,
                "vendor_version": "vv_choice",
                "source_version": "sv_choice",
                "cache_key": "macro.choice.latest",
            }

    def _public_refresh() -> dict[str, object]:
        calls.append(("public_cross_asset", None))
        return {
            "status": "completed",
            "run_id": "public_cross_asset_refresh:test",
            "series_count": 3,
            "row_count": 20,
            "warnings": ["tushare index_weight used latest available date"],
        }

    monkeypatch.setattr(route_module, "refresh_choice_macro_snapshot", _ChoiceRefresh())
    monkeypatch.setattr(route_module, "refresh_public_cross_asset_headlines", _public_refresh, raising=False)
    monkeypatch.setattr(route_module, "ensure_user_allowed", lambda **_kwargs: None)

    payload = route_module.choice_series_refresh(auth=route_module.AuthContext(), backfill_days=7)

    assert calls == [("choice", 7), ("public_cross_asset", None)]
    assert payload["status"] == "completed"
    assert payload["run_id"] == "choice_macro_refresh:test"
    assert payload["choice_macro"]["series_count"] == 2
    assert payload["public_cross_asset"]["series_count"] == 3
    assert payload["public_cross_asset"]["row_count"] == 20
    assert payload["warnings"] == ["tushare index_weight used latest available date"]


def test_choice_macro_refresh_uses_public_and_tushare_backups_when_choice_fails(monkeypatch):
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )
    calls: list[tuple[str, int | None]] = []

    class _ChoiceRefresh:
        @staticmethod
        def fn(backfill_days: int = 0) -> dict[str, object]:
            calls.append(("choice", backfill_days))
            raise RuntimeError("user access for this API expired")

    def _public_refresh() -> dict[str, object]:
        calls.append(("public_cross_asset", None))
        return {
            "status": "completed",
            "run_id": "public_cross_asset_refresh:test",
            "series_count": 16,
            "row_count": 1806,
            "warnings": ["public backup used latest available date"],
        }

    def _tushare_shibor_refresh() -> dict[str, object]:
        calls.append(("tushare_ncd_shibor", None))
        return {
            "status": "completed",
            "run_id": "tushare_ncd_shibor_refresh:test",
            "series_count": 5,
            "row_count": 305,
        }

    monkeypatch.setattr(route_module, "refresh_choice_macro_snapshot", _ChoiceRefresh())
    monkeypatch.setattr(route_module, "refresh_public_cross_asset_headlines", _public_refresh, raising=False)
    monkeypatch.setattr(route_module, "refresh_tushare_ncd_shibor_proxy", _tushare_shibor_refresh, raising=False)
    monkeypatch.setattr(route_module, "ensure_user_allowed", lambda **_kwargs: None)

    payload = route_module.choice_series_refresh(auth=route_module.AuthContext(), backfill_days=30)

    assert calls == [("choice", 30), ("public_cross_asset", None), ("tushare_ncd_shibor", None)]
    assert payload["status"] == "partial"
    assert payload["choice_macro"]["status"] == "failed"
    assert payload["choice_macro"]["error_message"] == "user access for this API expired"
    assert payload["public_cross_asset"]["status"] == "completed"
    assert payload["tushare_ncd_shibor"]["status"] == "completed"
    assert payload["warnings"] == [
        "Choice macro refresh failed: user access for this API expired",
        "public backup used latest available date",
    ]


def test_choice_macro_refresh_invalidates_cached_latest_payload(monkeypatch):
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )
    route_module.market_home_response_cache.invalidate()
    build_calls: list[object] = []

    def _latest_envelope(_duckdb_path: object, *, category: object | None = None) -> dict[str, object]:
        build_calls.append(category)
        return {
            "result_meta": {"result_kind": "macro.choice.latest"},
            "result": {"series": [{"series_id": f"series-{len(build_calls)}"}]},
        }

    class _ChoiceRefresh:
        @staticmethod
        def fn(backfill_days: int = 0) -> dict[str, object]:
            return {"status": "completed", "run_id": f"choice-refresh-{backfill_days}"}

    monkeypatch.setattr(route_module, "choice_macro_latest_envelope", _latest_envelope)
    monkeypatch.setattr(route_module, "refresh_choice_macro_snapshot", _ChoiceRefresh())
    monkeypatch.setattr(route_module, "refresh_public_cross_asset_headlines", lambda: {"status": "completed"})
    monkeypatch.setattr(route_module, "ensure_user_allowed", lambda **_kwargs: None)

    auth = _macro_vendor_read_auth(route_module)
    first = route_module.choice_series_latest(auth=auth)
    second = route_module.choice_series_latest(auth=auth)
    route_module.choice_series_refresh(auth=route_module.AuthContext(), backfill_days=3)
    third = route_module.choice_series_latest(auth=auth)

    assert first["result"]["series"][0]["series_id"] == "series-1"
    assert second["result"]["series"][0]["series_id"] == "series-1"
    assert third["result"]["series"][0]["series_id"] == "series-2"
    assert build_calls == [None, None]
    route_module.market_home_response_cache.invalidate()


def test_choice_macro_refresh_invalidates_cache_when_choice_status_is_degraded(monkeypatch):
    """Choice macro refresh that lands data but reports a non-fatal warning returns
    status="degraded" (see backend/app/tasks/choice_macro.py). The refreshed data is
    already committed to DuckDB, so the response cache must still be invalidated;
    otherwise the market-home page keeps serving pre-refresh cached data for up to
    the cache TTL after the user explicitly triggers a refresh.
    """
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )
    route_module.market_home_response_cache.invalidate()
    build_calls: list[object] = []

    def _latest_envelope(_duckdb_path: object, *, category: object | None = None) -> dict[str, object]:
        build_calls.append(category)
        return {
            "result_meta": {"result_kind": "macro.choice.latest"},
            "result": {"series": [{"series_id": f"series-{len(build_calls)}"}]},
        }

    class _ChoiceRefresh:
        @staticmethod
        def fn(backfill_days: int = 0) -> dict[str, object]:
            return {
                "status": "degraded",
                "run_id": f"choice-refresh-{backfill_days}",
                "quality_flag": "warning",
                "warning_code": "gate_supplement_failed",
                "warnings": [{"code": "gate_supplement_failed", "message": "livermore gate supplement failed"}],
            }

    # Public backup refresh is deliberately NOT "completed"/"partial" here so the
    # invalidation decision is isolated to the choice payload's "degraded" status
    # instead of being masked by the public backup also counting as a success.
    monkeypatch.setattr(route_module, "choice_macro_latest_envelope", _latest_envelope)
    monkeypatch.setattr(route_module, "refresh_choice_macro_snapshot", _ChoiceRefresh())
    monkeypatch.setattr(route_module, "refresh_public_cross_asset_headlines", lambda: {"status": "skipped"})
    monkeypatch.setattr(route_module, "ensure_user_allowed", lambda **_kwargs: None)

    auth = _macro_vendor_read_auth(route_module)
    first = route_module.choice_series_latest(auth=auth)
    second = route_module.choice_series_latest(auth=auth)
    route_module.choice_series_refresh(auth=route_module.AuthContext(), backfill_days=3)
    third = route_module.choice_series_latest(auth=auth)

    assert first["result"]["series"][0]["series_id"] == "series-1"
    assert second["result"]["series"][0]["series_id"] == "series-1"
    assert third["result"]["series"][0]["series_id"] == "series-2"
    route_module.market_home_response_cache.invalidate()


def test_choice_macro_refresh_preserves_degraded_status_and_quality_fields(monkeypatch):
    """The merged refresh response must pass the choice payload's degraded status,
    quality_flag and warning_code through unchanged (not silently promoted to
    "completed"), and must keep the underlying warning detail reachable so callers
    can surface the quality issue instead of assuming a clean refresh.
    """
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )

    class _ChoiceRefresh:
        @staticmethod
        def fn(backfill_days: int = 0) -> dict[str, object]:
            return {
                "status": "degraded",
                "run_id": "choice_macro_refresh:test",
                "series_count": 2,
                "vendor_version": "vv_choice",
                "source_version": "sv_choice",
                "cache_key": "macro.choice.latest",
                "quality_flag": "warning",
                "warning_code": "gate_supplement_failed",
                "warnings": [{"code": "gate_supplement_failed", "message": "livermore gate supplement failed"}],
            }

    def _public_refresh() -> dict[str, object]:
        return {"status": "completed", "run_id": "public_cross_asset_refresh:test", "series_count": 3}

    monkeypatch.setattr(route_module, "refresh_choice_macro_snapshot", _ChoiceRefresh())
    monkeypatch.setattr(route_module, "refresh_public_cross_asset_headlines", _public_refresh, raising=False)
    monkeypatch.setattr(route_module, "ensure_user_allowed", lambda **_kwargs: None)

    payload = route_module.choice_series_refresh(auth=route_module.AuthContext(), backfill_days=7)

    assert payload["status"] == "degraded"
    assert payload["quality_flag"] == "warning"
    assert payload["warning_code"] == "gate_supplement_failed"
    assert payload["choice_macro"]["status"] == "degraded"
    assert payload["choice_macro"]["warnings"] == [
        {"code": "gate_supplement_failed", "message": "livermore gate supplement failed"}
    ]
    assert payload["warnings"] == ["gate_supplement_failed: livermore gate supplement failed"]


def test_refresh_payload_succeeded_treats_degraded_as_success():
    """degraded means the refresh wrote fresh data to DuckDB but surfaced a
    non-fatal warning; it must count as a successful refresh for cache
    invalidation purposes, same as completed/partial.
    """
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )

    assert route_module._refresh_payload_succeeded({"status": "degraded"}) is True
    assert route_module._refresh_payload_succeeded({"status": "failed"}, None, {"status": "degraded"}) is True
    assert route_module._refresh_payload_succeeded({"status": "failed"}) is False


def test_choice_macro_refresh_keeps_auth_dependency_contract():
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )
    app = FastAPI()
    app.include_router(route_module.router)

    route = next(
        item
        for item in app.routes
        if getattr(item, "path", "") == "/ui/macro/choice-series/refresh"
    )

    assert [dependency.name for dependency in route.dependant.dependencies] == ["auth"]
    assert "auth" not in [param.name for param in route.dependant.body_params]
    assert "backfill_days" in [param.name for param in route.dependant.query_params]


def test_choice_macro_latest_filters_persisted_market_data_categories(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro-category-filter.duckdb"
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
            create table market_data_series_category (
              series_id varchar,
              category_key varchar,
              category_label varchar,
              source_surface varchar,
              fetch_mode varchar,
              fetch_granularity varchar,
              policy_note varchar,
              catalog_version varchar,
              batch_id varchar,
              updated_at varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('M_STABLE', 'Stable Series', '2026-04-09', 1.0, 'daily', 'pct', 'sv', 'vv', 'rv', 'ok', 'run'),
              ('M_FALLBACK', 'Fallback Series', '2026-04-09', 2.0, 'daily', 'pct', 'sv', 'vv', 'rv', 'ok', 'run'),
              ('M_ISOLATED', 'Isolated Series', '2026-04-09', 3.0, 'daily', 'pct', 'sv', 'vv', 'rv', 'ok', 'run')
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              ('M_STABLE', 'Stable Series', 'choice', 'vv', 'daily', 'pct'),
              ('M_FALLBACK', 'Fallback Series', 'choice', 'vv', 'daily', 'pct'),
              ('M_ISOLATED', 'Isolated Series', 'choice', 'vv', 'daily', 'pct')
            """
        )
        conn.execute(
            """
            insert into market_data_series_category values
              ('M_STABLE', 'stable', 'Stable governed series', 'choice_macro', 'date_slice', 'batch', 'stable category', 'catalog-v1', 'stable_batch', '2026-04-09T14:00:00Z', 'run'),
              ('M_FALLBACK', 'fallback', 'Fallback latest-only series', 'choice_macro', 'latest', 'single', 'fallback category', 'catalog-v1', 'fallback_single', '2026-04-09T14:00:00Z', 'run'),
              ('M_ISOLATED', 'isolated', 'Isolated vendor-pending series', 'choice_macro', 'latest', 'single', 'isolated category', 'catalog-v1', 'isolated_single', '2026-04-09T14:00:00Z', 'run')
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    default_response = client.get("/ui/macro/choice-series/latest", headers=MACRO_VENDOR_READ_HEADERS)
    fallback_response = client.get(
        "/ui/macro/choice-series/latest",
        params={"category": "fallback"},
        headers=MACRO_VENDOR_READ_HEADERS,
    )
    isolated_response = client.get(
        "/ui/macro/choice-series/latest",
        params={"category": "isolated"},
        headers=MACRO_VENDOR_READ_HEADERS,
    )
    stable_response = client.get(
        "/ui/macro/choice-series/latest",
        params={"category": "stable"},
        headers=MACRO_VENDOR_READ_HEADERS,
    )
    invalid_response = client.get(
        "/ui/macro/choice-series/latest",
        params={"category": "duration"},
        headers=MACRO_VENDOR_READ_HEADERS,
    )

    assert default_response.status_code == 200
    assert fallback_response.status_code == 200
    assert isolated_response.status_code == 200
    assert stable_response.status_code == 200
    assert invalid_response.status_code == 422

    default_payload = default_response.json()
    fallback_payload = fallback_response.json()
    isolated_payload = isolated_response.json()
    stable_payload = stable_response.json()

    assert [item["series_id"] for item in default_payload["result"]["series"]] == [
        "M_FALLBACK",
        "M_STABLE",
    ]
    assert [item["series_id"] for item in fallback_payload["result"]["series"]] == ["M_FALLBACK"]
    assert [item["series_id"] for item in isolated_payload["result"]["series"]] == ["M_ISOLATED"]
    assert [item["series_id"] for item in stable_payload["result"]["series"]] == ["M_STABLE"]
    assert fallback_payload["result"]["series"][0]["policy_note"] == "fallback category"
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
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )

    payload = route_module.choice_series_latest(auth=_macro_vendor_read_auth(route_module))
    assert [item["series_id"] for item in payload["result"]["series"]] == ["cn_repo_7d"]
    assert payload["result"]["series"][0]["refresh_tier"] == "stable"
    assert payload["result"]["series"][0]["fetch_mode"] == "date_slice"
    assert payload["result"]["series"][0]["fetch_granularity"] == "batch"
    assert payload["result"]["series"][0]["policy_note"] == "main refresh date-slice lane"
    assert "vendor_series_code" not in payload["result"]["series"][0]
    assert "batch_id" not in payload["result"]["series"][0]
    get_settings.cache_clear()


def test_macro_foundation_preview_degrades_to_empty_payload_for_corrupt_duckdb(tmp_path, monkeypatch):
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    corrupt_duckdb = tmp_path / "corrupt.duckdb"
    corrupt_duckdb.write_text("not-a-duckdb-file", encoding="utf-8")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(corrupt_duckdb))
    get_settings.cache_clear()

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get("/ui/preview/macro-foundation", headers=MACRO_VENDOR_READ_HEADERS)

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
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    response = client.get("/ui/preview/macro-foundation", headers=MACRO_VENDOR_READ_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["vendor_version"] == "vv_choice_batch_a__vv_choice_batch_b"
    assert payload["result_meta"]["vendor_status"] == "ok"
    assert payload["result_meta"]["fallback_mode"] == "none"
    assert sorted(item["vendor_version"] for item in payload["result"]["series"]) == [
        "vv_choice_batch_a",
        "vv_choice_batch_b",
    ]
    get_settings.cache_clear()


def test_macro_foundation_preview_exposes_policy_metadata_from_catalog(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro-foundation-policy.duckdb"
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
                'IsLatest=0,StartDate=2026-04-10,EndDate=2026-04-10,Ispandas=1,RECVtimeout=5',
                'date_slice',
                'batch',
                'stable',
                'main refresh date-slice lane'
              )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )

    payload = route_module.macro_foundation(auth=_macro_vendor_read_auth(route_module))

    assert payload["result"]["series"][0]["refresh_tier"] == "stable"
    assert payload["result"]["series"][0]["fetch_mode"] == "date_slice"
    assert payload["result"]["series"][0]["fetch_granularity"] == "batch"
    assert payload["result"]["series"][0]["policy_note"] == "main refresh date-slice lane"
    get_settings.cache_clear()


def test_market_data_catalog_tolerates_legacy_policy_metadata(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "market-data-catalog-legacy-policy.duckdb"
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
              unit varchar,
              fetch_mode varchar,
              fetch_granularity varchar,
              refresh_tier varchar,
              policy_note varchar
            )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              (
                'legacy_macro',
                'Legacy macro',
                'tushare',
                'vv_legacy',
                'monthly',
                'pct',
                'live_backfill',
                'monthly',
                'on_demand',
                'legacy external catalog metadata'
              )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    response = client.get("/ui/market-data/catalog", headers=MACRO_VENDOR_READ_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "market_data.catalog"
    assert payload["result"]["series"][0]["series_id"] == "legacy_macro"
    assert payload["result"]["series"][0]["refresh_tier"] is None
    assert payload["result"]["series"][0]["fetch_mode"] is None
    assert payload["result"]["series"][0]["fetch_granularity"] is None
    assert payload["result"]["series"][0]["policy_note"] == "legacy external catalog metadata"
    get_settings.cache_clear()


def test_choice_macro_latest_tolerates_legacy_policy_metadata(tmp_path):
    duckdb_path = tmp_path / "choice-macro-latest-legacy-policy.duckdb"
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
                'legacy_macro',
                'Legacy macro',
                '2026-04-09',
                1.23,
                'monthly',
                'pct',
                'sv_choice_macro_legacy',
                'vv_legacy',
                'rv_choice_macro_thin_slice_v1',
                'ok',
                'choice_macro_refresh:legacy'
              )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              (
                'legacy_macro',
                'Legacy macro',
                'tushare',
                'vv_legacy',
                'monthly',
                'pct',
                'live_backfill',
                'monthly',
                'on_demand',
                'legacy external catalog metadata'
              )
            """
        )
    finally:
        conn.close()

    payload = load_choice_macro_latest_payload(str(duckdb_path))

    assert payload.series[0].series_id == "legacy_macro"
    assert payload.series[0].refresh_tier is None
    assert payload.series[0].fetch_mode is None
    assert payload.series[0].fetch_granularity is None
    assert payload.series[0].policy_note == "legacy external catalog metadata"


def test_choice_macro_latest_returns_up_to_twenty_recent_points(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-recent-points.duckdb"
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
        values = []
        for day in range(1, 7):
            values.append(
                "('cn_repo_7d', 'CN Repo 7D', '2026-04-0{d}', {v}, 'daily', 'pct', 'sv', 'vv', 'rv', 'ok', 'run')".format(
                    d=day,
                    v=1.7 + day / 100,
                )
            )
        conn.execute(f"insert into fact_choice_macro_daily values {', '.join(values)}")
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              (
                'cn_repo_7d',
                'CN Repo 7D',
                'choice',
                'vv',
                'daily',
                'pct',
                'EDB_REPO_7D',
                'stable_daily',
                '2026-04-11.choice-macro.v2',
                'liquidity',
                true,
                '["china","rates","liquidity"]',
                'IsLatest=0,StartDate=2026-04-06,EndDate=2026-04-06,Ispandas=1,RECVtimeout=5',
                'date_slice',
                'batch',
                'stable',
                'main refresh date-slice lane'
              )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    route_module = load_module(
        "backend.app.api.routes.macro_vendor",
        "backend/app/api/routes/macro_vendor.py",
    )

    payload = route_module.choice_series_latest(auth=_macro_vendor_read_auth(route_module))
    series = payload["result"]["series"][0]
    assert len(series["recent_points"]) == 6
    assert series["recent_points"][0]["trade_date"] == "2026-04-06"
    assert series["recent_points"][-1]["trade_date"] == "2026-04-01"
    get_settings.cache_clear()


def test_macro_foundation_preview_reports_snapshot_source_version_when_available(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro-source-version.duckdb"
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
            insert into phase1_macro_vendor_catalog values
              ('cn_cpi_yoy', 'CN CPI YoY', 'choice', 'vv_choice_batch_b', 'monthly', 'pct')
            """
        )
        conn.execute(
            """
            insert into choice_market_snapshot values
              (
                'cn_cpi_yoy',
                'CN CPI YoY',
                'EDB_CPI_YOY',
                'choice',
                '2026-04-11',
                0.7,
                'monthly',
                'pct',
                'sv_choice_macro_20260411',
                'vv_choice_batch_b',
                'rv_choice_macro_thin_slice_v1',
                'run-1'
              )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    response = client.get("/ui/preview/macro-foundation", headers=MACRO_VENDOR_READ_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_choice_macro_20260411"
    assert payload["result_meta"]["vendor_version"] == "vv_choice_batch_b"
    assert payload["result_meta"]["vendor_status"] == "ok"
    assert payload["result_meta"]["fallback_mode"] == "none"
    get_settings.cache_clear()


def test_macro_foundation_preview_keeps_empty_source_version_when_snapshot_exists_without_catalog_payload(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro-source-version-mismatch.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
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
            insert into choice_market_snapshot values
              (
                'cn_cpi_yoy',
                'CN CPI YoY',
                'EDB_CPI_YOY',
                'choice',
                '2026-04-11',
                0.7,
                'monthly',
                'pct',
                'sv_choice_macro_20260411',
                'vv_choice_batch_b',
                'rv_choice_macro_thin_slice_v1',
                'run-1'
              )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    response = client.get("/ui/preview/macro-foundation", headers=MACRO_VENDOR_READ_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["series"] == []
    assert payload["result_meta"]["source_version"] == "sv_macro_vendor_empty"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert payload["result_meta"]["fallback_mode"] == "none"
    get_settings.cache_clear()


def test_choice_macro_latest_returns_stale_result_meta_when_latest_rows_are_stale(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro-stale.duckdb"
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
            insert into fact_choice_macro_daily values
              (
                'cn_repo_7d',
                'CN Repo 7D',
                '2026-04-11',
                1.83,
                'daily',
                'pct',
                'sv_choice_macro_20260411',
                'vv_choice_batch_stale',
                'rv_choice_macro_thin_slice_v1',
                'stale',
                'choice_macro_refresh:2026-04-11T09:00:00Z'
              )
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    _seed_macro_vendor_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    response = client.get("/ui/macro/choice-series/latest", headers=MACRO_VENDOR_READ_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["quality_flag"] == "stale"
    assert payload["result_meta"]["vendor_status"] == "vendor_stale"
    assert payload["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert payload["result_meta"]["vendor_version"] == "vv_choice_batch_stale"
    assert payload["result"]["series"][0]["quality_flag"] == "stale"
    get_settings.cache_clear()
