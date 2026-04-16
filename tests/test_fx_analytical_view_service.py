from __future__ import annotations

import json
from pathlib import Path

import duckdb

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _write_catalog(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "catalog_version": "2026-04-12.choice-macro.v3",
                "vendor_name": "choice",
                "generated_at": "2026-04-12T10:00:00Z",
                "generated_from": "tests.fixture.choice_fx_catalog",
                "batches": [
                    {
                        "batch_id": "stable_daily",
                        "fetch_mode": "date_slice",
                        "fetch_granularity": "batch",
                        "refresh_tier": "stable",
                        "policy_note": "main refresh date-slice lane",
                        "request_options": {
                            "IsLatest": 0,
                            "StartDate": "__RUN_DATE__",
                            "EndDate": "__RUN_DATE__",
                            "Ispandas": 1,
                            "RECVtimeout": 5,
                        },
                        "series": [
                            {
                                "series_id": "EMM00058124",
                                "series_name": "中间价:美元兑人民币",
                                "vendor_series_code": "EMM00058124",
                                "frequency": "daily",
                                "unit": "CNY",
                                "theme": "macro_market",
                                "is_core": True,
                                "tags": ["choice", "macro", "market", "rates", "fx"],
                            },
                            {
                                "series_id": "EMM01588399",
                                "series_name": "中间价:人民币兑港元",
                                "vendor_series_code": "EMM01588399",
                                "frequency": "daily",
                                "unit": "HKD",
                                "theme": "macro_market",
                                "is_core": True,
                                "tags": ["choice", "macro", "market", "rates", "fx"],
                            },
                            {
                                "series_id": "EMM01607834",
                                "series_name": "人民币汇率预估指数",
                                "vendor_series_code": "EMM01607834",
                                "frequency": "daily",
                                "unit": "index",
                                "theme": "macro_market",
                                "is_core": False,
                                "tags": ["choice", "macro", "market", "rates", "fx"],
                            },
                            {
                                "series_id": "EMI01743799",
                                "series_name": "美元对人民币外汇掉期C-Swap定盘曲线:全价汇率:ON",
                                "vendor_series_code": "EMI01743799",
                                "frequency": "daily",
                                "unit": "points",
                                "theme": "macro_market",
                                "is_core": False,
                                "tags": ["choice", "macro", "market", "rates", "fx"],
                            },
                            {
                                "series_id": "EMM00166458",
                                "series_name": "中债国债到期收益率:1年",
                                "vendor_series_code": "EMM00166458",
                                "frequency": "daily",
                                "unit": "%",
                                "theme": "macro_market",
                                "is_core": True,
                                "tags": ["choice", "macro", "market", "rates", "fx"],
                            },
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _seed_fx_duckdb(duckdb_path: Path) -> None:
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
            create table fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              vendor_name varchar,
              vendor_version varchar,
              vendor_series_code varchar,
              observed_trade_date date
            )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              ('EMM00058124', '中间价:美元兑人民币', 'choice', 'vv_choice_batch', 'daily', 'CNY', 'EMM00058124', 'stable_daily', 'catalog-v1', 'macro_market', true, '["fx"]', 'opts', 'date_slice', 'batch', 'stable', 'main refresh date-slice lane'),
              ('EMM01588399', '中间价:人民币兑港元', 'choice', 'vv_choice_batch', 'daily', 'HKD', 'EMM01588399', 'stable_daily', 'catalog-v1', 'macro_market', true, '["fx"]', 'opts', 'date_slice', 'batch', 'stable', 'main refresh date-slice lane'),
              ('EMM01607834', '人民币汇率预估指数', 'choice', 'vv_choice_batch', 'daily', 'index', 'EMM01607834', 'stable_daily', 'catalog-v1', 'macro_market', false, '["fx"]', 'opts', 'latest', 'single', 'fallback', 'analytical index lane'),
              ('EMI01743799', '美元对人民币外汇掉期C-Swap定盘曲线:全价汇率:ON', 'choice', 'vv_choice_batch', 'daily', 'points', 'EMI01743799', 'stable_daily', 'catalog-v1', 'macro_market', false, '["fx"]', 'opts', 'latest', 'single', 'fallback', 'analytical swap lane'),
              ('EMM00166458', '中债国债到期收益率:1年', 'choice', 'vv_choice_batch', 'daily', '%', 'EMM00166458', 'stable_daily', 'catalog-v1', 'macro_market', true, '["fx"]', 'opts', 'date_slice', 'batch', 'stable', 'curve lane')
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('EMM00058124', '中间价:美元兑人民币', '2026-02-27', 7.24, 'daily', 'CNY', 'sv_choice_fx', 'vv_choice_fx', 'rv_choice_macro_thin_slice_v1', 'ok', 'run-1'),
              ('EMM00058124', '中间价:美元兑人民币', '2026-02-26', 7.23, 'daily', 'CNY', 'sv_choice_fx_prev', 'vv_choice_fx_prev', 'rv_choice_macro_thin_slice_v1', 'ok', 'run-1'),
              ('EMM01607834', '人民币汇率预估指数', '2026-02-27', 101.2, 'daily', 'index', 'sv_choice_fx', 'vv_choice_fx', 'rv_choice_macro_thin_slice_v1', 'warning', 'run-1'),
              ('EMI01743799', '美元对人民币外汇掉期C-Swap定盘曲线:全价汇率:ON', '2026-02-27', 15.0, 'daily', 'points', 'sv_choice_fx', 'vv_choice_fx', 'rv_choice_macro_thin_slice_v1', 'warning', 'run-1'),
              ('EMM00166458', '中债国债到期收益率:1年', '2026-02-27', 1.5, 'daily', '%', 'sv_choice_curve', 'vv_choice_curve', 'rv_choice_macro_thin_slice_v1', 'ok', 'run-1')
            """
        )
        conn.execute(
            """
            insert into choice_market_snapshot values
              ('EMM00058124', '中间价:美元兑人民币', 'EMM00058124', 'choice', '2026-02-27', 7.24, 'daily', 'CNY', 'sv_choice_fx', 'vv_choice_fx', 'rv_choice_macro_thin_slice_v1', 'run-1'),
              ('EMM01607834', '人民币汇率预估指数', 'EMM01607834', 'choice', '2026-02-27', 101.2, 'daily', 'index', 'sv_choice_fx', 'vv_choice_fx', 'rv_choice_macro_thin_slice_v1', 'run-1'),
              ('EMI01743799', '美元对人民币外汇掉期C-Swap定盘曲线:全价汇率:ON', 'EMI01743799', 'choice', '2026-02-27', 15.0, 'daily', 'points', 'sv_choice_fx', 'vv_choice_fx', 'rv_choice_macro_thin_slice_v1', 'run-1')
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid values
              ('2026-02-27', 'USD', 'CNY', 7.24, 'CFETS', true, false, 'sv_fx_choice', 'choice', 'vv_fx_choice', 'EMM00058124', '2026-02-27'),
              ('2026-02-27', 'HKD', 'CNY', 0.91743119, 'CFETS', false, true, 'sv_fx_choice', 'choice', 'vv_fx_choice', 'EMM01588399', '2026-02-26')
            """
        )
    finally:
        conn.close()


def test_fx_service_separates_formal_status_from_analytical_groups(tmp_path, monkeypatch):
    catalog_path = tmp_path / "choice_macro_catalog.json"
    duckdb_path = tmp_path / "market-data.duckdb"
    _write_catalog(catalog_path)
    _seed_fx_duckdb(duckdb_path)
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", str(catalog_path))
    get_settings.cache_clear()

    module = load_module(
        "backend.app.services.macro_vendor_service",
        "backend/app/services/macro_vendor_service.py",
    )

    formal = module.load_fx_formal_status_payload(str(duckdb_path))
    analytical = module.load_fx_analytical_payload(str(duckdb_path))

    assert formal.candidate_count == 2
    assert formal.materialized_count == 2
    assert formal.carry_forward_count == 1
    assert [row.base_currency for row in formal.rows] == ["USD", "HKD"]
    assert [group.group_key for group in analytical.groups] == ["middle_rate", "fx_index", "fx_swap_curve"]
    assert analytical.groups[0].series[0].series_id == "EMM00058124"
    assert analytical.groups[1].series[0].series_id == "EMM01607834"
    assert analytical.groups[2].series[0].series_id == "EMI01743799"
    get_settings.cache_clear()


def test_fx_analytical_usd_middle_rate_consumes_fx_rates_helper(tmp_path, monkeypatch):
    catalog_path = tmp_path / "choice_macro_catalog.json"
    duckdb_path = tmp_path / "market-data.duckdb"
    _write_catalog(catalog_path)
    _seed_fx_duckdb(duckdb_path)
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", str(catalog_path))
    get_settings.cache_clear()

    module = load_module(
        "backend.app.services.macro_vendor_service",
        "backend/app/services/macro_vendor_service.py",
    )
    calls = []

    def fake_get_usd_cny_rate(rows, target_date):
        calls.append((rows, target_date))
        return 7.77, target_date, ["synthetic analytical fallback"]

    monkeypatch.setattr(module, "get_usd_cny_rate", fake_get_usd_cny_rate)

    analytical = module.load_fx_analytical_payload(str(duckdb_path))

    middle_rate = analytical.groups[0].series[0]
    assert middle_rate.series_id == "EMM00058124"
    assert middle_rate.value_numeric == 7.77
    assert calls
    get_settings.cache_clear()


def test_fx_formal_status_missing_catalog_degrades_to_empty_warning_envelope(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "market-data.duckdb"
    _seed_fx_duckdb(duckdb_path)
    monkeypatch.setenv(
        "MOSS_CHOICE_MACRO_CATALOG_FILE",
        str(tmp_path / "missing-choice-macro-catalog.json"),
    )
    get_settings.cache_clear()

    module = load_module(
        "backend.app.services.macro_vendor_service",
        "backend/app/services/macro_vendor_service.py",
    )

    payload = module.load_fx_formal_status_payload(str(duckdb_path))
    envelope = module.fx_formal_status_envelope(str(duckdb_path))

    assert payload.candidate_count == 0
    assert payload.materialized_count == 0
    assert payload.rows == []
    assert envelope["result_meta"]["basis"] == "formal"
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert envelope["result"]["candidate_count"] == 0
    get_settings.cache_clear()
