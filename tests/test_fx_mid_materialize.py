from __future__ import annotations

import csv
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _load_fx_task_module():
    fx_mod = sys.modules.get("backend.app.tasks.fx_mid_materialize")
    if fx_mod is None:
        fx_mod = load_module(
            "backend.app.tasks.fx_mid_materialize",
            "backend/app/tasks/fx_mid_materialize.py",
        )
    return fx_mod


def _write_choice_fx_catalog(path: Path) -> None:
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
                                "series_id": "EMM00058129",
                                "series_name": "中间价:澳元兑人民币",
                                "vendor_series_code": "EMM00058129",
                                "frequency": "daily",
                                "unit": "CNY",
                                "theme": "macro_market",
                                "is_core": True,
                                "tags": ["choice", "macro", "market", "rates", "fx"],
                            },
                            {
                                "series_id": "EMM00058125",
                                "series_name": "中间价:欧元兑人民币",
                                "vendor_series_code": "EMM00058125",
                                "frequency": "daily",
                                "unit": "CNY",
                                "theme": "macro_market",
                                "is_core": True,
                                "tags": ["choice", "macro", "market", "rates", "fx"],
                            },
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
                                "series_id": "EMM00058130",
                                "series_name": "中间价:加拿大元兑人民币",
                                "vendor_series_code": "EMM00058130",
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
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class _ChoiceMultiResult:
    Codes = ["EMM00058129", "EMM00058125", "EMM00058124", "EMM00058130", "EMM01588399"]
    Dates = ["2026-02-27"]
    Data = {
        "EMM00058129": [[Decimal("4.61")]],
        "EMM00058125": [[Decimal("7.82")]],
        "EMM00058124": [[Decimal("7.24")]],
        "EMM00058130": [[Decimal("5.33")]],
        "EMM01588399": [[Decimal("1.09")]],
    }


class _ChoiceIncompleteResult:
    Codes = ["EMM00058124"]
    Dates = ["2026-02-27"]
    Data = {
        "EMM00058124": [[Decimal("7.24")]],
    }


def test_fx_mid_materialize_populates_duckdb_from_csv_override(tmp_path):
    fx_mod = _load_fx_task_module()

    csv_path = tmp_path / "fx_mid.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "trade_date",
                "base_currency",
                "quote_currency",
                "mid_rate",
                "source_name",
                "is_business_day",
                "is_carry_forward",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "trade_date": "2026-02-27",
                "base_currency": "美元",
                "quote_currency": "人民币",
                "mid_rate": "7.24",
                "source_name": "CFETS",
                "is_business_day": "true",
                "is_carry_forward": "false",
            }
        )

    payload = fx_mod.materialize_fx_mid_rows.fn(
        csv_path=str(csv_path),
        duckdb_path=str(duckdb_path),
    )

    assert payload["status"] == "completed"
    assert payload["row_count"] == 1

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select trade_date, base_currency, quote_currency, mid_rate, source_name,
                   is_business_day, is_carry_forward, vendor_name
            from fx_daily_mid
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        (date(2026, 2, 27), "USD", "CNY", Decimal("7.24000000"), "CFETS", True, False, "csv")
    ]


def test_resolve_fx_mid_csv_path_returns_none_without_explicit_override(tmp_path):
    fx_mod = _load_fx_task_module()

    resolved = fx_mod.resolve_fx_mid_csv_path(
        explicit_csv_path="",
        data_input_root=tmp_path / "data_input",
    )

    assert resolved is None


def test_resolve_fx_mid_csv_path_fails_closed_when_explicit_path_is_missing(tmp_path):
    fx_mod = _load_fx_task_module()

    with pytest.raises(FileNotFoundError):
        fx_mod.resolve_fx_mid_csv_path(
            explicit_csv_path=str(tmp_path / "missing.csv"),
            data_input_root=tmp_path / "data_input",
        )


def test_discover_formal_fx_candidates_reads_only_middle_rate_pairs(tmp_path):
    fx_mod = _load_fx_task_module()
    catalog_path = tmp_path / "choice_macro_catalog.json"
    _write_choice_fx_catalog(catalog_path)

    candidates = fx_mod.discover_formal_fx_candidates(catalog_path=catalog_path)

    assert [candidate.vendor_series_code for candidate in candidates] == [
        "EMM00058124",
        "EMM00058125",
        "EMM00058129",
        "EMM00058130",
        "EMM01588399",
    ]
    assert [candidate.base_currency for candidate in candidates] == ["USD", "EUR", "AUD", "CAD", "HKD"]
    assert [candidate.invert_result for candidate in candidates] == [False, False, False, False, True]


def test_materialize_fx_mid_for_report_date_uses_choice_for_complete_candidate_set(
    tmp_path,
    monkeypatch,
):
    fx_mod = _load_fx_task_module()
    catalog_path = tmp_path / "choice_macro_catalog.json"
    _write_choice_fx_catalog(catalog_path)
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", str(catalog_path))
    get_settings.cache_clear()

    duckdb_path = tmp_path / "moss.duckdb"
    data_input_root = tmp_path / "data_input"

    class _FakeChoiceClient:
        def edb(self, codes, options=""):
            assert codes == [
                "EMM00058124",
                "EMM00058125",
                "EMM00058129",
                "EMM00058130",
                "EMM01588399",
            ]
            assert "StartDate=2026-02-27" in options
            assert "EndDate=2026-02-27" in options
            return _ChoiceMultiResult()

    class _UnexpectedAkShareVendor:
        def fetch_fx_mid_snapshot(self, **_kwargs):
            raise AssertionError("AkShare should not be called when Choice returns a complete middle-rate set.")

    monkeypatch.setattr(fx_mod, "ChoiceClient", lambda: _FakeChoiceClient())
    monkeypatch.setattr(fx_mod, "AkShareVendorAdapter", lambda: _UnexpectedAkShareVendor())

    payload = fx_mod.materialize_fx_mid_for_report_date.fn(
        report_date="2026-02-27",
        duckdb_path=str(duckdb_path),
        data_input_root=str(data_input_root),
    )

    assert payload["status"] == "completed"
    assert payload["row_count"] == 5
    assert payload["source_kind"] == "choice"

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select base_currency, quote_currency, mid_rate, vendor_name, vendor_series_code, observed_trade_date
            from fx_daily_mid
            order by base_currency
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("AUD", "CNY", Decimal("4.61000000"), "choice", "EMM00058129", date(2026, 2, 27)),
        ("CAD", "CNY", Decimal("5.33000000"), "choice", "EMM00058130", date(2026, 2, 27)),
        ("EUR", "CNY", Decimal("7.82000000"), "choice", "EMM00058125", date(2026, 2, 27)),
        ("HKD", "CNY", Decimal("0.91743119"), "choice", "EMM01588399", date(2026, 2, 27)),
        ("USD", "CNY", Decimal("7.24000000"), "choice", "EMM00058124", date(2026, 2, 27)),
    ]
    get_settings.cache_clear()


def test_materialize_fx_mid_for_report_date_uses_akshare_when_choice_is_incomplete(
    tmp_path,
    monkeypatch,
):
    fx_mod = _load_fx_task_module()
    catalog_path = tmp_path / "choice_macro_catalog.json"
    _write_choice_fx_catalog(catalog_path)
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", str(catalog_path))
    get_settings.cache_clear()

    duckdb_path = tmp_path / "moss.duckdb"

    class _FakeChoiceClient:
        def edb(self, codes, options=""):
            return _ChoiceIncompleteResult()

    class _FakeAkShareVendor:
        def fetch_fx_mid_snapshot(self, *, report_date, candidates):
            assert report_date == "2026-02-27"
            assert len(candidates) == 5
            return {
                "vendor_name": "akshare",
                "vendor_version": "vv_akshare_fx_fixture",
                "source_version": "sv_fx_akshare_fixture",
                "rows": [
                    {"base_currency": "AUD", "mid_rate": Decimal("4.61"), "observed_trade_date": "2026-02-27", "source_name": "AKSHARE"},
                    {"base_currency": "CAD", "mid_rate": Decimal("5.33"), "observed_trade_date": "2026-02-27", "source_name": "AKSHARE"},
                    {"base_currency": "EUR", "mid_rate": Decimal("7.82"), "observed_trade_date": "2026-02-27", "source_name": "AKSHARE"},
                    {"base_currency": "HKD", "mid_rate": Decimal("0.91743119"), "observed_trade_date": "2026-02-27", "source_name": "AKSHARE"},
                    {"base_currency": "USD", "mid_rate": Decimal("7.24"), "observed_trade_date": "2026-02-27", "source_name": "AKSHARE"},
                ],
            }

    monkeypatch.setattr(fx_mod, "ChoiceClient", lambda: _FakeChoiceClient())
    monkeypatch.setattr(fx_mod, "AkShareVendorAdapter", lambda: _FakeAkShareVendor())

    payload = fx_mod.materialize_fx_mid_for_report_date.fn(
        report_date="2026-02-27",
        duckdb_path=str(duckdb_path),
        data_input_root=str(tmp_path / "data_input"),
    )

    assert payload["status"] == "completed"
    assert payload["row_count"] == 5
    assert payload["source_kind"] == "akshare"
    assert payload["vendor_version"] == "vv_akshare_fx_fixture"

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select distinct vendor_name, source_version, vendor_version
            from fx_daily_mid
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("akshare", "sv_fx_akshare_fixture", "vv_akshare_fx_fixture")]
    get_settings.cache_clear()


def test_materialize_fx_mid_for_report_date_fails_closed_without_silent_csv_fallback(
    tmp_path,
    monkeypatch,
):
    fx_mod = _load_fx_task_module()
    catalog_path = tmp_path / "choice_macro_catalog.json"
    _write_choice_fx_catalog(catalog_path)
    monkeypatch.setenv("MOSS_CHOICE_MACRO_CATALOG_FILE", str(catalog_path))
    get_settings.cache_clear()

    class _FailingChoiceClient:
        def edb(self, codes, options=""):
            raise RuntimeError("choice unavailable")

    class _FailingAkShareVendor:
        def fetch_fx_mid_snapshot(self, **_kwargs):
            raise RuntimeError("akshare unavailable")

    monkeypatch.setattr(fx_mod, "ChoiceClient", lambda: _FailingChoiceClient())
    monkeypatch.setattr(fx_mod, "AkShareVendorAdapter", lambda: _FailingAkShareVendor())

    with pytest.raises(ValueError, match="Choice failed: choice unavailable"):
        fx_mod.materialize_fx_mid_for_report_date.fn(
            report_date="2026-02-27",
            duckdb_path=str(tmp_path / "moss.duckdb"),
            data_input_root=str(tmp_path / "data_input"),
        )
    get_settings.cache_clear()
