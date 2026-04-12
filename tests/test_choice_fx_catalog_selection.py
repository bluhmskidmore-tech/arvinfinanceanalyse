from __future__ import annotations

import json
from pathlib import Path

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
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_choice_fx_catalog_selects_only_middle_rate_candidates(tmp_path):
    module = load_module(
        "backend.app.repositories.choice_fx_catalog",
        "backend/app/repositories/choice_fx_catalog.py",
    )
    catalog_path = tmp_path / "choice_macro_catalog.json"
    _write_catalog(catalog_path)

    candidates = module.discover_formal_fx_candidates(catalog_path=catalog_path)

    assert [candidate.vendor_series_code for candidate in candidates] == [
        "EMM00058124",
        "EMM01588399",
    ]
    assert candidates[0].pair_label == "USD/CNY"
    assert candidates[1].pair_label == "HKD/CNY"
    assert candidates[1].invert_result is True


def test_choice_fx_catalog_classifies_fx_analytical_groups_without_using_tags_alone():
    module = load_module(
        "backend.app.repositories.choice_fx_catalog",
        "backend/app/repositories/choice_fx_catalog.py",
    )

    assert module.classify_fx_series_group("中间价:美元兑人民币") == "middle_rate"
    assert module.classify_fx_series_group("人民币汇率预估指数") == "fx_index"
    assert module.classify_fx_series_group("美元对人民币外汇掉期C-Swap定盘曲线:全价汇率:ON") == "fx_swap_curve"
    assert module.classify_fx_series_group("中债国债到期收益率:1年") is None
