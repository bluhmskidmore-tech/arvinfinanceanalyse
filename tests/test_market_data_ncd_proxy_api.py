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
    *,
    vendor_name: str = "tushare",
    trade_date: str = "2026-04-23",
) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        conn.execute(
            """
            create table if not exists choice_market_snapshot (
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
        series_prefix = "CHOICE.SHIBOR" if vendor_name == "choice" else "NCD.SHIBOR"
        rows_by_tenor = {
            "1M": (f"{series_prefix}.1M", "SHIBOR:1M", f"{vendor_name}:shibor:1m", 1.412),
            "3M": (f"{series_prefix}.3M", "SHIBOR:3M", f"{vendor_name}:shibor:3m", 1.4345),
            "6M": (f"{series_prefix}.6M", "SHIBOR:6M", f"{vendor_name}:shibor:6m", 1.4535),
            "9M": (f"{series_prefix}.9M", "SHIBOR:9M", f"{vendor_name}:shibor:9m", 1.4695),
            "1Y": (f"{series_prefix}.1Y", "SHIBOR:1Y", f"{vendor_name}:shibor:1y", 1.4825),
        }
        conn.executemany(
            """
            insert into choice_market_snapshot values (
              ?, ?, ?, ?, ?, ?, 'daily', 'pct', ?, ?, 'rv_landed_shibor', 'run_landed'
            )
            """,
            [
                (
                    rows_by_tenor[tenor][0],
                    rows_by_tenor[tenor][1],
                    rows_by_tenor[tenor][2],
                    vendor_name,
                    trade_date,
                    rows_by_tenor[tenor][3],
                    f"sv_{vendor_name}_shibor",
                    f"vv_{vendor_name}_shibor",
                )
                for tenor in tenors
            ],
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
    assert payload.proxy_label == "Tushare Shibor funding proxy"
    assert payload.warnings == [
        "Proxy only; not actual NCD issuance matrix.",
        "Using landed Tushare Shibor; quote medians unavailable.",
    ]

    get_settings.cache_clear()


def test_ncd_proxy_missing_landed_data_does_not_live_call_tushare(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "ncd-proxy-empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_ENABLE_TUSHARE_NCD_PROXY_LIVE", "1")
    get_settings.cache_clear()

    service = _service_module()
    payload = service.load_ncd_funding_proxy_payload()

    assert payload.rows == []
    assert any("Landed Choice/Tushare Shibor proxy data unavailable" in warning for warning in payload.warnings)

    get_settings.cache_clear()


def test_ncd_proxy_envelope_uses_landed_lineage_when_rows_exist(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "ncd-proxy-lineage.duckdb"
    _seed_landed_shibor_proxy(str(duckdb_path))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    service = _service_module()
    envelope = service.ncd_funding_proxy_envelope()

    assert envelope["result_meta"]["source_version"] == "sv_tushare_shibor"
    assert envelope["result_meta"]["vendor_version"] == "vv_tushare_shibor"
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
    assert any("Landed Choice/Tushare Shibor proxy data unavailable" in warning for warning in envelope["result"]["warnings"])

    get_settings.cache_clear()


def test_ncd_proxy_uses_choice_when_choice_has_complete_landed_data(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "ncd-proxy-choice.duckdb"
    _seed_landed_shibor_proxy(str(duckdb_path), vendor_name="choice")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    service = _service_module()
    envelope = service.ncd_funding_proxy_envelope()

    assert envelope["result"]["proxy_label"] == "Choice Shibor funding proxy"
    assert envelope["result"]["rows"][0]["1M"] == 1.412
    assert envelope["result"]["warnings"] == [
        "Proxy only; not actual NCD issuance matrix.",
        "Using landed Choice Shibor; quote medians unavailable.",
    ]
    assert envelope["result_meta"]["source_version"] == "sv_choice_shibor"
    assert envelope["result_meta"]["vendor_version"] == "vv_choice_shibor"

    get_settings.cache_clear()


def test_ncd_proxy_falls_back_to_tushare_when_choice_landed_data_is_incomplete(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "ncd-proxy-choice-partial-tushare.duckdb"
    _seed_landed_shibor_proxy(str(duckdb_path), tenors=("1M", "3M"), vendor_name="choice")
    _seed_landed_shibor_proxy(str(duckdb_path), vendor_name="tushare")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    service = _service_module()
    envelope = service.ncd_funding_proxy_envelope()

    assert envelope["result"]["proxy_label"] == "Tushare Shibor funding proxy"
    assert envelope["result"]["rows"][0]["1Y"] == 1.4825
    assert envelope["result_meta"]["source_version"] == "sv_tushare_shibor"
    assert envelope["result_meta"]["vendor_version"] == "vv_tushare_shibor"

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
                "source_version": "sv_tushare_shibor",
                "vendor_version": "vv_tushare_shibor",
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
                "warnings": [
                    "Proxy only; not actual NCD issuance matrix.",
                    "Using landed Tushare Shibor; quote medians unavailable.",
                ],
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
    assert payload["result"]["warnings"] == [
        "Proxy only; not actual NCD issuance matrix.",
        "Using landed Tushare Shibor; quote medians unavailable.",
    ]
