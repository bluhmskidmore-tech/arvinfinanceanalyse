from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import load_module


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
                "source_version": "sv_ncd_proxy_test",
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
                "warnings": ["Proxy only; not actual NCD issuance matrix."],
            },
        },
    )
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)

    response = client.get("/ui/market-data/ncd-funding-proxy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "market_data.ncd_proxy"
    assert payload["result"]["proxy_label"] == "Tushare Shibor funding proxy"
    assert payload["result"]["is_actual_ncd_matrix"] is False
    assert payload["result"]["rows"][0]["label"] == "Shibor fixing"
