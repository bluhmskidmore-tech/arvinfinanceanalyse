from __future__ import annotations

import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _service_module():
    return load_module(
        "backend.app.services.market_data_ncd_proxy_service",
        "backend/app/services/market_data_ncd_proxy_service.py",
    )


def _seed_landed_shibor_proxy(
    duckdb_path: str,
    tenors: tuple[str, ...] = ("1M", "3M", "6M", "9M", "1Y"),
) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
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
        rows_by_tenor = {
            "1M": ("NCD.SHIBOR.1M", "SHIBOR:1M", "NCD.SHIBOR.1M", 1.412),
            "3M": ("NCD.SHIBOR.3M", "SHIBOR:3M", "NCD.SHIBOR.3M", 1.4345),
            "6M": ("NCD.SHIBOR.6M", "SHIBOR:6M", "NCD.SHIBOR.6M", 1.4535),
            "9M": ("NCD.SHIBOR.9M", "SHIBOR:9M", "NCD.SHIBOR.9M", 1.4695),
            "1Y": ("NCD.SHIBOR.1Y", "SHIBOR:1Y", "NCD.SHIBOR.1Y", 1.4825),
        }
        conn.executemany(
            """
            insert into choice_market_snapshot values (
              ?, ?, ?, 'choice', '2026-04-23', ?, 'daily', 'pct', 'sv_landed_shibor', 'vv_landed_shibor', 'rv_landed_shibor', 'run_landed'
            )
            """,
            [rows_by_tenor[tenor] for tenor in tenors],
        )
    finally:
        conn.close()


def test_ncd_proxy_reads_landed_shibor_with_live_env_ignored(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "ncd-proxy.duckdb"
    _seed_landed_shibor_proxy(str(duckdb_path))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_ENABLE_TUSHARE_NCD_PROXY_LIVE", "1")
    get_settings.cache_clear()

    service = _service_module()

    payload = service.load_ncd_funding_proxy_payload()

    assert payload.as_of_date == "2026-04-23"
    assert payload.rows[0].tenor_1m == 1.412
    assert payload.rows[0].tenor_3m == 1.4345
    assert payload.rows[0].tenor_1y == 1.4825

    get_settings.cache_clear()


def test_ncd_proxy_missing_landed_data_does_not_live_call_tushare(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "ncd-proxy-empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_ENABLE_TUSHARE_NCD_PROXY_LIVE", "1")
    get_settings.cache_clear()

    service = _service_module()
    payload = service.load_ncd_funding_proxy_payload()

    assert payload.rows == []
    assert any("Landed Shibor proxy data unavailable" in warning for warning in payload.warnings)

    get_settings.cache_clear()


def test_ncd_proxy_envelope_uses_landed_lineage_when_rows_exist(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "ncd-proxy-lineage.duckdb"
    _seed_landed_shibor_proxy(str(duckdb_path))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    service = _service_module()
    envelope = service.ncd_funding_proxy_envelope()

    assert envelope["result_meta"]["source_version"] == "sv_ncd_proxy_landed"
    assert envelope["result_meta"]["vendor_version"] == "vv_landed_shibor"
    assert envelope["result_meta"]["vendor_status"] == "ok"

    get_settings.cache_clear()


def test_ncd_proxy_envelope_uses_empty_lineage_when_warehouse_missing(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "ncd-proxy-lineage-empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_ENABLE_TUSHARE_NCD_PROXY_LIVE", "1")
    get_settings.cache_clear()

    service = _service_module()
    envelope = service.ncd_funding_proxy_envelope()

    assert envelope["result_meta"]["source_version"] == "sv_ncd_proxy_empty"
    assert envelope["result_meta"]["vendor_version"] == "vv_none"
    assert envelope["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert envelope["result"]["rows"] == []

    get_settings.cache_clear()


def test_ncd_proxy_partial_landed_shibor_uses_empty_lineage(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "ncd-proxy-lineage-partial.duckdb"
    _seed_landed_shibor_proxy(str(duckdb_path), tenors=("1M", "3M"))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_ENABLE_TUSHARE_NCD_PROXY_LIVE", "1")
    get_settings.cache_clear()

    service = _service_module()
    envelope = service.ncd_funding_proxy_envelope()

    assert envelope["result_meta"]["source_version"] == "sv_ncd_proxy_empty"
    assert envelope["result_meta"]["vendor_version"] == "vv_none"
    assert envelope["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert envelope["result"]["rows"] == []
    assert any("Landed Shibor proxy data unavailable" in warning for warning in envelope["result"]["warnings"])

    get_settings.cache_clear()


def test_market_data_ncd_proxy_endpoint_returns_explicit_proxy_payload(monkeypatch) -> None:
    route_mod = load_module(
        "backend.app.api.routes.market_data_ncd_proxy",
        "backend/app/api/routes/market_data_ncd_proxy.py",
    )
    monkeypatch.setattr(
        route_mod,
        "ncd_funding_proxy_envelope",
        lambda: {
            "result_meta": {
                "trace_id": "tr_ncd_proxy_test",
                "basis": "analytical",
                "result_kind": "market_data.ncd_proxy",
                "formal_use_allowed": False,
                "source_version": "sv_ncd_proxy_landed",
                "vendor_version": "vv_landed_shibor",
                "rule_version": "rv_ncd_proxy_v1",
                "cache_version": "cv_ncd_proxy_v1",
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "scenario_flag": False,
                "generated_at": "2026-04-23T10:00:00Z",
            },
            "result": {
                "as_of_date": "2026-04-23",
                "proxy_label": "Tushare Shibor funding proxy",
                "is_actual_ncd_matrix": False,
                "rows": [
                    {
                        "row_key": "shibor_fixing",
                        "label": "Shibor fixing",
                        "1M": 1.412,
                        "3M": 1.4345,
                        "6M": 1.4535,
                        "9M": 1.4695,
                        "1Y": 1.4825,
                        "quote_count": None,
                    }
                ],
                "warnings": ["Proxy only; not actual NCD issuance matrix."],
            },
        },
    )
    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)

    response = client.get("/ui/market-data/ncd-funding-proxy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "market_data.ncd_proxy"
    assert payload["result"]["proxy_label"] == "Tushare Shibor funding proxy"
    assert payload["result"]["is_actual_ncd_matrix"] is False
    assert payload["result"]["rows"][0]["label"] == "Shibor fixing"
