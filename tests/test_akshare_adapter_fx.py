from __future__ import annotations

from decimal import Decimal

import pytest

from tests.helpers import load_module


def test_akshare_fx_snapshot_matches_direct_and_reverse_pairs(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )

    monkeypatch.delenv("MOSS_AKSHARE_BASE_URL", raising=False)
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_fx_records_locally",
        lambda self, trade_date: [
            {"pair": "USD/CNY", "trade_date": trade_date, "mid_rate": "7.24", "source_name": "AKSHARE"},
            {"pair": "CNY/HKD", "trade_date": trade_date, "mid_rate": "1.09", "source_name": "AKSHARE"},
        ],
    )

    payload = module.VendorAdapter().fetch_fx_mid_snapshot(
        report_date="2026-02-27",
        candidates=[
            {
                "base_currency": "USD",
                "quote_currency": "CNY",
                "invert_result": False,
            },
            {
                "base_currency": "HKD",
                "quote_currency": "CNY",
                "invert_result": True,
            },
        ],
    )

    assert payload["vendor_name"] == "akshare"
    assert payload["vendor_version"].startswith("vv_akshare_fx_20260227_")
    assert payload["source_version"].startswith("sv_fx_akshare_")
    assert payload["rows"] == [
        {
            "base_currency": "USD",
            "mid_rate": Decimal("7.24"),
            "observed_trade_date": "2026-02-27",
            "source_name": "AKSHARE",
            "pair_value": "USD/CNY",
        },
        {
            "base_currency": "HKD",
            "mid_rate": Decimal("0.9174311926605504587155963303"),
            "observed_trade_date": "2026-02-27",
            "source_name": "AKSHARE",
            "pair_value": "CNY/HKD",
        },
    ]


def test_akshare_fx_snapshot_fails_when_candidate_is_missing(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )

    monkeypatch.delenv("MOSS_AKSHARE_BASE_URL", raising=False)
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_fx_records_locally",
        lambda self, trade_date: [
            {"pair": "USD/CNY", "trade_date": trade_date, "mid_rate": "7.24", "source_name": "AKSHARE"},
        ],
    )

    with pytest.raises(RuntimeError, match="no formal FX middle-rate"):
        module.VendorAdapter().fetch_fx_mid_snapshot(
            report_date="2026-02-27",
            candidates=[{"base_currency": "EUR", "quote_currency": "CNY", "invert_result": False}],
        )


def test_akshare_fx_snapshot_matches_safe_wide_middle_rate_records(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )

    monkeypatch.delenv("MOSS_AKSHARE_BASE_URL", raising=False)
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_fx_records_locally",
        lambda self, trade_date: [
            {
                "\u65e5\u671f": "2026-07-30",
                "\u7f8e\u5143": "679.01",
                "\u6b27\u5143": "779.02",
                "\u6e2f\u5143": "86.601",
                "\u6fb3\u5143": "473.02",
                "\u52a0\u5143": "481.03",
            },
            {
                "\u65e5\u671f": trade_date,
                "\u7f8e\u5143": "678.94",
                "\u6b27\u5143": "778.86",
                "\u6e2f\u5143": "86.559",
                "\u6fb3\u5143": "474.41",
                "\u52a0\u5143": "482.06",
            },
        ],
    )

    payload = module.VendorAdapter().fetch_fx_mid_snapshot(
        report_date="2026-07-31",
        candidates=[
            {"base_currency": "USD", "quote_currency": "CNY", "invert_result": False},
            {"base_currency": "EUR", "quote_currency": "CNY", "invert_result": False},
            {"base_currency": "AUD", "quote_currency": "CNY", "invert_result": False},
            {"base_currency": "CAD", "quote_currency": "CNY", "invert_result": False},
            {"base_currency": "HKD", "quote_currency": "CNY", "invert_result": True},
        ],
    )

    assert [row["mid_rate"] for row in payload["rows"]] == [
        Decimal("6.7894"),
        Decimal("7.7886"),
        Decimal("4.7441"),
        Decimal("4.8206"),
        Decimal("0.86559"),
    ]
    assert {row["observed_trade_date"] for row in payload["rows"]} == {"2026-07-31"}
    assert {row["source_name"] for row in payload["rows"]} == {"CFETS"}
