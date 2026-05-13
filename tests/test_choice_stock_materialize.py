from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import duckdb
import pandas as pd
import pytest

from backend.app.repositories.duckdb_migrations import register_all
from backend.app.repositories.duckdb_schema_registry import DuckDBSchemaRegistry
from backend.app.tasks.choice_stock_materialize import (
    _DefaultChoiceStockClient,
    _load_tushare_financial_factors,
    ensure_choice_stock_schema,
    load_choice_stock_materialization_coverage,
    materialize_choice_stock_factor_snapshot,
    materialize_choice_stock_inputs,
)


def _write_confirmed_catalog(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "catalog_version": "test_choice_stock_materialize",
                "vendor_name": "choice",
                "generated_from": "unit_test",
                "fields": [
                    {
                        "input_family": "stock_universe",
                        "field_key": "a_share_universe_sector_001004",
                        "vendor_indicator": "001004",
                        "call": "sector",
                        "request_options": {"Ispandas": 0, "RECVtimeout": 7},
                        "confirmed": True,
                        "confirmation_source": "unit test",
                        "confirmed_at": "2026-04-29",
                    },
                    {
                        "input_family": "sector_membership",
                        "field_key": "sw2021_industry_membership",
                        "vendor_indicator": "SW2021,SW2021CODE",
                        "call": "css",
                        "request_options": {"EndDate": "__AS_OF_DATE__", "ClassiFication": 1, "Ispandas": 0},
                        "confirmed": True,
                        "confirmation_source": "unit test",
                        "confirmed_at": "2026-04-29",
                    },
                    {
                        "input_family": "sector_strength",
                        "field_key": "daily_return_turnover_amplitude",
                        "vendor_indicator": "PCTCHANGE,TURN,AMPLITUDE",
                        "call": "csd",
                        "request_options": {"RowIndex": 1, "period": 1, "Ispandas": 0},
                        "confirmed": True,
                        "confirmation_source": "unit test",
                        "confirmed_at": "2026-04-29",
                    },
                    {
                        "input_family": "stock_ohlcv",
                        "field_key": "daily_ohlcv_amount",
                        "vendor_indicator": "OPEN,HIGH,LOW,CLOSE,VOLUME,AMOUNT",
                        "call": "csd",
                        "request_options": {"RowIndex": 1, "period": 1, "Ispandas": 0},
                        "confirmed": True,
                        "confirmation_source": "unit test",
                        "confirmed_at": "2026-04-29",
                    },
                    {
                        "input_family": "stock_status",
                        "field_key": "daily_trade_status",
                        "vendor_indicator": "TRADESTATUS",
                        "call": "csd",
                        "request_options": {"RowIndex": 1, "period": 1, "Ispandas": 0},
                        "confirmed": True,
                        "confirmation_source": "unit test",
                        "confirmed_at": "2026-04-29",
                    },
                    {
                        "input_family": "limit_up_quality",
                        "field_key": "daily_limit_flags",
                        "vendor_indicator": "HIGHLIMIT,LOWLIMIT",
                        "call": "csd",
                        "request_options": {"RowIndex": 1, "period": 1, "Ispandas": 0},
                        "confirmed": True,
                        "confirmation_source": "unit test",
                        "confirmed_at": "2026-04-29",
                    },
                    {
                        "input_family": "limit_up_quality",
                        "field_key": "point_in_time_limit_streaks",
                        "vendor_indicator": "ISSURGEDLIMIT,ISDECLINELIMIT,HLIMITEDAYS,LLIMITEDDAYS",
                        "call": "css",
                        "request_options": {"TradeDate": "__AS_OF_DATE__", "Ispandas": 0},
                        "confirmed": True,
                        "confirmation_source": "unit test",
                        "confirmed_at": "2026-04-29",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_confirmed_catalog_with_theme_inputs(path: Path) -> None:
    raw = {
        "catalog_version": "test_choice_stock_theme_materialize",
        "vendor_name": "choice",
        "generated_from": "unit_test",
        "fields": json.loads(path.read_text(encoding="utf-8"))["fields"],
    }
    raw["fields"].extend(
        [
            {
                "input_family": "concept_membership",
                "field_key": "choice_concept_membership",
                "vendor_indicator": "CONCEPTCODE,CONCEPTNAME",
                "call": "css",
                "required": False,
                "request_options": {"TradeDate": "__AS_OF_DATE__", "Ispandas": 0},
                "confirmed": True,
                "confirmation_source": "unit test optional concept probe",
                "confirmed_at": "2026-05-11",
            },
            {
                "input_family": "intraday_movement",
                "field_key": "choice_intraday_movement",
                "vendor_indicator": "STOCK_INTRADAY_MOVEMENT",
                "call": "ctr",
                "required": False,
                "request_options": {"TradeDate": "__AS_OF_DATE__", "Ispandas": 0},
                "confirmed": True,
                "confirmation_source": "unit test optional movement probe",
                "confirmed_at": "2026-05-11",
            },
        ]
    )
    path.write_text(json.dumps(raw), encoding="utf-8")


class FakeChoiceStockClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], str]] = []

    def sector(self, *args: object, options: str = "") -> Any:
        self.calls.append(("sector", args, options))
        return SimpleNamespace(
            ErrorCode=0,
            Indicators=["SECUCODE", "SECURITYSHORTNAME"],
            Data={
                "001004": [
                    {"SECUCODE": "600000.SH", "SECURITYSHORTNAME": "SPDB"},
                    {"SECUCODE": "000001.SZ", "SECURITYSHORTNAME": "PAB"},
                    {"SECUCODE": "600000.SH", "SECURITYSHORTNAME": "SPDB"},
                ]
            },
        )

    def css(self, *args: object, options: str = "") -> Any:
        self.calls.append(("css", args, options))
        indicators = str(args[1]).split(",")
        if "SW2021" in indicators:
            return SimpleNamespace(
                ErrorCode=0,
                Indicators=indicators,
                Data={
                    "000001.SZ": ["Bank", "801780"],
                    "600000.SH": ["Bank", "801780"],
                },
            )
        return SimpleNamespace(
            ErrorCode=0,
            Indicators=indicators,
            Data={
                "000001.SZ": ["1", "0", 2, 0],
                "600000.SH": ["0", "0", 0, 0],
            },
        )

    def csd(self, *args: object, options: str = "") -> Any:
        self.calls.append(("csd", args, options))
        requested_codes = [code for code in str(args[0]).split(",") if code]
        indicators = str(args[1]).split(",")
        values_by_indicator = {
            "OPEN": [10.0],
            "HIGH": [11.0],
            "LOW": [9.5],
            "CLOSE": [10.5],
            "VOLUME": [1000.0],
            "AMOUNT": [10500.0],
            "PCTCHANGE": [1.2],
            "TURN": [0.8],
            "AMPLITUDE": [2.1],
            "TRADESTATUS": ["Trading"],
            "HIGHLIMIT": ["N"],
            "LOWLIMIT": ["N"],
        }
        return SimpleNamespace(
            ErrorCode=0,
            Indicators=indicators,
            Dates=["2026-04-28"],
            Data={
                code: [values_by_indicator[indicator] for indicator in indicators]
                for code in requested_codes
            },
        )


class ThemeChoiceStockClient(FakeChoiceStockClient):
    def css(self, *args: object, options: str = "") -> Any:
        indicators = str(args[1]).split(",")
        if "CONCEPTCODE" in indicators or "CONCEPTNAME" in indicators:
            self.calls.append(("css", args, options))
            return SimpleNamespace(
                ErrorCode=0,
                Indicators=indicators,
                Data={
                    "000001.SZ": ["C001", "Semiconductor"],
                    "600000.SH": ["C002", "Banking"],
                },
            )
        return super().css(*args, options=options)

    def ctr(self, *args: object, options: str = "") -> Any:
        self.calls.append(("ctr", args, options))
        return SimpleNamespace(
            ErrorCode=0,
            Indicators=[
                "EVENTTIME",
                "CODE",
                "NAME",
                "CONCEPTCODE",
                "CONCEPTNAME",
                "EVENTTYPE",
                "TITLE",
                "PCTCHANGE",
                "TURN",
                "URL",
            ],
            Data=[
                [
                    "2026-04-28 10:05:00",
                    "000001.SZ",
                    "PAB",
                    "C001",
                    "Semiconductor",
                    "intraday_surge",
                    "Semiconductor concept intraday surge",
                    10.2,
                    5.1,
                    "https://choice.example/news/1",
                ]
            ],
        )


class FailingCsdChoiceStockClient(FakeChoiceStockClient):
    def csd(self, *args: object, options: str = "") -> Any:
        del args, options
        return SimpleNamespace(ErrorCode=1001, ErrorMsg="Choice csd failed in unit test")


class PermissionDeniedCsdChoiceStockClient(FakeChoiceStockClient):
    def csd(self, *args: object, options: str = "") -> Any:
        self.calls.append(("csd", args, options))
        return SimpleNamespace(ErrorCode=10001012, ErrorMsg="insufficient user access")


class FakeTushareStockClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def trade_cal(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(("trade_cal", kwargs))
        return pd.DataFrame([{"cal_date": "20260428", "is_open": 1}])

    def daily(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(("daily", kwargs))
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260428",
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.5,
                    "pre_close": 10.0,
                    "vol": 1000.0,
                    "amount": 10500.0,
                    "pct_chg": 5.0,
                },
                {
                    "ts_code": "600000.SH",
                    "trade_date": "20260428",
                    "open": 20.0,
                    "high": 22.0,
                    "low": 18.0,
                    "close": 21.0,
                    "pre_close": 20.0,
                    "vol": 2000.0,
                    "amount": 42000.0,
                    "pct_chg": 5.0,
                },
            ]
        )

    def daily_basic(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(("daily_basic", kwargs))
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260428",
                    "turnover_rate": 0.9,
                    "turnover_rate_f": 1.4,
                    "pe": 8.0,
                    "pb": 0.8,
                    "ps": 1.2,
                    "dv_ttm": 3.5,
                },
                {
                    "ts_code": "600000.SH",
                    "trade_date": "20260428",
                    "turnover_rate": 0.8,
                    "turnover_rate_f": 1.2,
                    "pe": 12.0,
                    "pb": 1.1,
                    "ps": 1.8,
                    "dv_ttm": 2.5,
                },
            ]
        )

    def stk_limit(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(("stk_limit", kwargs))
        return pd.DataFrame(
            [
                {"ts_code": "000001.SZ", "trade_date": "20260428", "up_limit": 11.0, "down_limit": 9.0},
                {"ts_code": "600000.SH", "trade_date": "20260428", "up_limit": 22.0, "down_limit": 18.0},
            ]
        )

    def fina_indicator(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(("fina_indicator", kwargs))
        values = {
            "000001.SZ": {"roe": 18.0, "grossprofit_margin": 42.0},
            "600000.SH": {"roe": 12.0, "grossprofit_margin": 35.0},
        }
        codes: list[str]
        raw = kwargs.get("ts_code")
        if raw is None:
            codes = sorted(values.keys())
        else:
            codes = [part.strip() for part in str(raw).split(",") if part.strip()]
        rows = []
        for stock_code in codes:
            row_values = values[stock_code]
            rows.append(
                {
                    "ts_code": stock_code,
                    "ann_date": "20260401",
                    "end_date": "20260331",
                    **row_values,
                }
            )
        return pd.DataFrame(rows)


class MultiDateTushareStockClient(FakeTushareStockClient):
    def trade_cal(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(("trade_cal", kwargs))
        return pd.DataFrame(
            [
                {"cal_date": "20260427", "is_open": 1},
                {"cal_date": "20260428", "is_open": 1},
            ]
        )

    def daily(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(("daily", kwargs))
        trade_date = str(kwargs["trade_date"])
        values = {
            "20260427": (10.0, 11.0, 9.0, 10.5, 10.0, 1000.0, 10500.0, 5.0),
            "20260428": (20.0, 22.0, 18.0, 21.0, 20.0, 2000.0, 42000.0, 5.0),
        }[trade_date]
        open_value, high_value, low_value, close_value, pre_close, volume, amount, pct_chg = values
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": trade_date,
                    "open": open_value,
                    "high": high_value,
                    "low": low_value,
                    "close": close_value,
                    "pre_close": pre_close,
                    "vol": volume,
                    "amount": amount,
                    "pct_chg": pct_chg,
                },
                {
                    "ts_code": "600000.SH",
                    "trade_date": trade_date,
                    "open": open_value * 2,
                    "high": high_value * 2,
                    "low": low_value * 2,
                    "close": close_value * 2,
                    "pre_close": pre_close * 2,
                    "vol": volume * 2,
                    "amount": amount * 2,
                    "pct_chg": pct_chg,
                },
            ]
        )

    def daily_basic(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(("daily_basic", kwargs))
        trade_date = str(kwargs["trade_date"])
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": trade_date,
                    "turnover_rate": 0.9,
                    "turnover_rate_f": 1.4,
                },
                {
                    "ts_code": "600000.SH",
                    "trade_date": trade_date,
                    "turnover_rate": 0.8,
                    "turnover_rate_f": 1.2,
                },
            ]
        )

    def stk_limit(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(("stk_limit", kwargs))
        trade_date = str(kwargs["trade_date"])
        base = 11.0 if trade_date == "20260427" else 22.0
        return pd.DataFrame(
            [
                {"ts_code": "000001.SZ", "trade_date": trade_date, "up_limit": base, "down_limit": base - 2.0},
                {"ts_code": "600000.SH", "trade_date": trade_date, "up_limit": base * 2, "down_limit": (base - 2.0) * 2},
            ]
        )


class FlakyLimitTushareStockClient(MultiDateTushareStockClient):
    def __init__(self) -> None:
        super().__init__()
        self._limit_failures: set[str] = set()

    def stk_limit(self, **kwargs: object) -> pd.DataFrame:
        trade_date = str(kwargs["trade_date"])
        if trade_date == "20260427" and trade_date not in self._limit_failures:
            self._limit_failures.add(trade_date)
            self.calls.append(("stk_limit", kwargs))
            raise TimeoutError("temporary Tushare timeout")
        return super().stk_limit(**kwargs)


class TsRequiredFinaFakeTushare(FakeTushareStockClient):
    """Simulates APIs that refuse fina_indicator without ts_code (comma-batch path)."""

    def fina_indicator(self, **kwargs: object) -> pd.DataFrame:
        if kwargs.get("ts_code") is None:
            self.calls.append(("fina_indicator", kwargs))
            raise RuntimeError("参数有误, ts_code")
        return super().fina_indicator(**kwargs)


def test_load_tushare_financial_factors_uses_single_unscoped_batch_call_when_available() -> None:
    client = FakeTushareStockClient()
    codes = ["000001.SZ", "600000.SH"]
    out = _load_tushare_financial_factors(client, "2026-04-28", codes)
    fins = [c for c in client.calls if c[0] == "fina_indicator"]
    assert len(fins) == 1
    assert fins[0][1].get("ts_code") is None
    assert out["000001.SZ"]["roe"] == pytest.approx(0.18)
    assert out["600000.SH"]["gross_margin"] == pytest.approx(0.35)


def test_load_tushare_financial_factors_batches_comma_ts_code_when_scope_required() -> None:
    client = TsRequiredFinaFakeTushare()
    codes = ["000001.SZ", "600000.SH"]
    out = _load_tushare_financial_factors(client, "2026-04-28", codes)
    fins = [c for c in client.calls if c[0] == "fina_indicator"]
    assert len(fins) == 2
    assert fins[0][1].get("ts_code") is None
    comma_arg = fins[1][1].get("ts_code") or ""
    assert "," in str(comma_arg)
    assert out["000001.SZ"]["roe"] == pytest.approx(0.18)


def test_default_choice_stock_client_keeps_sector_call_local(monkeypatch) -> None:
    calls: list[tuple[str, tuple[object, ...], str]] = []

    class FakeChoiceClient:
        settings = SimpleNamespace(choice_request_options="recvTimeout=3")

        def start(self) -> int:
            calls.append(("start", (), ""))
            return 0

    class FakeEmC:
        def sector(self, *args: object) -> object:
            *pos, merged = args
            calls.append(("sector", tuple(pos), str(merged)))
            return SimpleNamespace(ErrorCode=0)

    monkeypatch.setattr("backend.app.tasks.choice_stock_materialize._get_em_c", lambda: FakeEmC())
    client = _DefaultChoiceStockClient(choice_client=FakeChoiceClient())

    result = cast(SimpleNamespace, client.sector("001004", "2026-04-28", options="fmt=1"))

    assert result.ErrorCode == 0
    assert calls == [
        ("start", (), ""),
        ("sector", ("001004", "2026-04-28"), "recvTimeout=3,fmt=1"),
    ]


def test_v20_database_upgrades_to_v21_choice_stock_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "moss.duckdb"
    registry = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry)
    registry._migrations = [item for item in registry._migrations if item[0] <= 20]
    assert len(registry.apply_pending()) == 20

    registry_v21 = DuckDBSchemaRegistry(db_path=str(db_path))
    register_all(registry_v21)
    applied = registry_v21.apply_pending()

    assert applied == [
        "v21: Choice stock materialization front layer",
        "v22: Livermore position snapshot read model",
        "v23: Livermore gate supplement daily (breadth/limit-up)",
        "v24: ZQTZ accounting sub_type on snapshot + formal facts",
        "v25: CFFEX member-rank daily from Choice/Tushare",
        "v26: PnL by-business page precompute read model",
        "v27: Choice stock factor snapshot for equity strategies",
        "v28: Livermore candidate history analytical replay",
    ]
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
    finally:
        conn.close()
    assert "choice_stock_materialize_run" in tables
    assert "choice_stock_daily_observation" in tables
    assert "choice_stock_factor_snapshot" in tables
    assert "livermore_position_snapshot" in tables


def test_choice_stock_materialize_resolves_runtime_placeholders_and_is_idempotent(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)
    client = FakeChoiceStockClient()

    result = materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=client,
    )

    assert result["status"] == "completed"
    assert result["stock_code_count"] == 2
    assert client.calls[0] == ("sector", ("001004", "2026-04-28"), "Ispandas=0,RECVtimeout=7")
    downstream_calls = [call for call in client.calls if call[0] in {"css", "csd"}]
    assert downstream_calls
    assert {call[1][0] for call in downstream_calls} == {"000001.SZ,600000.SH"}
    assert [call for call in client.calls if call[0] == "css"][0][2] == (
        "EndDate=2026-04-28,ClassiFication=1,Ispandas=0"
    )
    assert [call for call in client.calls if call[0] == "csd"][0][1][2:] == (
        "2025-09-20",
        "2026-04-28",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        counts = {
            table: conn.execute(f"select count(*) from {table}").fetchone()[0]
            for table in (
                "choice_stock_universe",
                "choice_stock_sector_membership",
                "choice_stock_daily_observation",
                "choice_stock_limit_quality",
            )
        }
        daily = conn.execute(
            """
            select stock_code, close_value, pctchange, tradestatus, highlimit
            from choice_stock_daily_observation
            order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert counts == {
        "choice_stock_universe": 2,
        "choice_stock_sector_membership": 2,
        "choice_stock_daily_observation": 2,
        "choice_stock_limit_quality": 2,
    }
    assert daily == [
        ("000001.SZ", 10.5, 1.2, "Trading", "N"),
        ("600000.SH", 10.5, 1.2, "Trading", "N"),
    ]

    second_client = FakeChoiceStockClient()
    materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=second_client,
    )
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rerun_daily_count = conn.execute("select count(*) from choice_stock_daily_observation").fetchone()[0]
        audit_count = conn.execute("select count(*) from choice_stock_request_audit").fetchone()[0]
    finally:
        conn.close()
    assert rerun_daily_count == 2
    assert audit_count == 14

    coverage = load_choice_stock_materialization_coverage(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-04-28",
    )
    assert coverage.full_coverage is True
    assert coverage.missing_request_items == []


def test_choice_stock_materialize_persists_optional_concept_and_movement_inputs(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)
    _write_confirmed_catalog_with_theme_inputs(catalog_path)
    client = ThemeChoiceStockClient()

    result = materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=client,
    )

    assert result["status"] == "completed"
    assert any(call[0] == "ctr" for call in client.calls)

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        concept_rows = conn.execute(
            """
            select stock_code, concept_code, concept_name, field_key
            from choice_stock_concept_membership
            order by stock_code
            """
        ).fetchall()
        movement_rows = conn.execute(
            """
            select stock_code, concept_code, concept_name, event_type, event_title, pctchange, turn
            from choice_stock_intraday_movement_event
            order by event_time, stock_code
            """
        ).fetchall()
        coverage = load_choice_stock_materialization_coverage(
            duckdb_path=str(duckdb_path),
            as_of_date="2026-04-28",
        )
    finally:
        conn.close()

    assert concept_rows == [
        ("000001.SZ", "C001", "Semiconductor", "choice_concept_membership"),
        ("600000.SH", "C002", "Banking", "choice_concept_membership"),
    ]
    assert movement_rows == [
        (
            "000001.SZ",
            "C001",
            "Semiconductor",
            "intraday_surge",
            "Semiconductor concept intraday surge",
            10.2,
            5.1,
        )
    ]
    assert coverage.full_coverage is True
    assert coverage.missing_request_items == []


def test_choice_stock_materialize_batches_csd_history_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)
    client = FakeChoiceStockClient()
    monkeypatch.setattr("backend.app.tasks.choice_stock_materialize.CHOICE_STOCK_CSD_CODE_CHUNK_SIZE", 1)

    result = materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=client,
    )

    assert result["status"] == "completed"
    css_calls = [call for call in client.calls if call[0] == "css"]
    csd_calls = [call for call in client.calls if call[0] == "csd"]
    assert {call[1][0] for call in css_calls} == {"000001.SZ,600000.SH"}
    assert {call[1][0] for call in csd_calls} == {"000001.SZ", "600000.SH"}
    assert len(csd_calls) == 8

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        daily_count = conn.execute("select count(*) from choice_stock_daily_observation").fetchone()[0]
        request_rows = conn.execute(
            """
            select field_key, row_count
            from choice_stock_request_audit
            where call = 'csd'
            order by field_key
            """
        ).fetchall()
    finally:
        conn.close()

    assert daily_count == 2
    assert request_rows == [
        ("daily_limit_flags", 2),
        ("daily_ohlcv_amount", 2),
        ("daily_return_turnover_amplitude", 2),
        ("daily_trade_status", 2),
    ]


def test_choice_stock_materialize_falls_back_to_tushare_when_choice_csd_is_denied(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)
    tushare_client = FakeTushareStockClient()

    result = materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=PermissionDeniedCsdChoiceStockClient(),
        tushare_client=tushare_client,
    )

    assert result["status"] == "completed"
    assert str(result["vendor_version"]).startswith("vv_choice_tushare_stock_20260428_")
    assert [name for name, _ in tushare_client.calls] == [
        "trade_cal",
        "daily",
        "daily_basic",
        "stk_limit",
    ]

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        daily = conn.execute(
            """
            select stock_code, open_value, high_value, low_value, close_value,
                   pctchange, turn, amplitude, tradestatus, highlimit, lowlimit
            from choice_stock_daily_observation
            order by stock_code
            """
        ).fetchall()
        audit_rows = conn.execute(
            """
            select field_key, status, row_count, error_code, error_msg
            from choice_stock_request_audit
            where call = 'csd'
            order by field_key
            """
        ).fetchall()
    finally:
        conn.close()

    assert daily == [
        ("000001.SZ", 10.0, 11.0, 9.0, 10.5, 5.0, 1.4, 20.0, "Trading", "11.0", "9.0"),
        ("600000.SH", 20.0, 22.0, 18.0, 21.0, 5.0, 1.2, 20.0, "Trading", "22.0", "18.0"),
    ]
    assert [row[:4] for row in audit_rows] == [
        ("daily_limit_flags", "completed_tushare_fallback", 2, 10001012),
        ("daily_ohlcv_amount", "completed_tushare_fallback", 2, 10001012),
        ("daily_return_turnover_amplitude", "completed_tushare_fallback", 2, 10001012),
        ("daily_trade_status", "completed_tushare_fallback", 2, 10001012),
    ]
    assert all("Tushare stock fallback" in row[4] for row in audit_rows)
    coverage = load_choice_stock_materialization_coverage(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-04-28",
    )
    assert coverage.full_coverage is True


def test_choice_stock_tushare_fallback_loads_limit_flags_for_each_trade_date(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)
    tushare_client = MultiDateTushareStockClient()

    materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=PermissionDeniedCsdChoiceStockClient(),
        tushare_client=tushare_client,
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select trade_date, stock_code, highlimit, lowlimit, field_keys_json
            from choice_stock_daily_observation
            order by trade_date, stock_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert [kwargs["trade_date"] for name, kwargs in tushare_client.calls if name == "stk_limit"] == [
        "20260427",
        "20260428",
    ]
    assert rows == [
        ("2026-04-27", "000001.SZ", "11.0", "9.0", '["daily_limit_flags","daily_ohlcv_amount","daily_return_turnover_amplitude","daily_trade_status"]'),
        ("2026-04-27", "600000.SH", "22.0", "18.0", '["daily_limit_flags","daily_ohlcv_amount","daily_return_turnover_amplitude","daily_trade_status"]'),
        ("2026-04-28", "000001.SZ", "22.0", "20.0", '["daily_limit_flags","daily_ohlcv_amount","daily_return_turnover_amplitude","daily_trade_status"]'),
        ("2026-04-28", "600000.SH", "44.0", "40.0", '["daily_limit_flags","daily_ohlcv_amount","daily_return_turnover_amplitude","daily_trade_status"]'),
    ]


def test_choice_stock_tushare_fallback_retries_transient_limit_timeout(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)
    tushare_client = FlakyLimitTushareStockClient()

    result = materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=PermissionDeniedCsdChoiceStockClient(),
        tushare_client=tushare_client,
    )

    limit_call_dates = [kwargs["trade_date"] for name, kwargs in tushare_client.calls if name == "stk_limit"]
    assert result["status"] == "completed"
    assert limit_call_dates == ["20260427", "20260427", "20260428"]


def test_choice_stock_factor_snapshot_materializes_into_stock_database(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)
    stock_client = PermissionDeniedCsdChoiceStockClient()
    tushare_client = FakeTushareStockClient()
    materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=stock_client,
        tushare_client=tushare_client,
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.executemany(
            """
            insert into choice_stock_daily_observation values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    trade_date,
                    stock_code,
                    close_value,
                    close_value,
                    close_value,
                    close_value,
                    1000.0,
                    close_value * 1000,
                    0.0,
                    1.0,
                    0.0,
                    "Trading",
                    "",
                    "",
                    '["daily_ohlcv_amount"]',
                    "sv_history",
                    "vv_history",
                    "rv_history",
                    "run-history",
                )
                for trade_date, close_a, close_b in [
                    ("2025-04-28", 5.25, 10.5),
                    ("2026-01-28", 7.0, 14.0),
                ]
                for stock_code, close_value in (("000001.SZ", close_a), ("600000.SH", close_b))
            ],
        )
    finally:
        conn.close()

    result = materialize_choice_stock_factor_snapshot(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        tushare_client=tushare_client,
        use_choice_financial_fallback=False,
    )

    assert result["status"] == "completed"
    assert result["row_count"] == 2
    assert result["table"] == "choice_stock_factor_snapshot"
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, industry, pe, pb, ps, roe, gross_margin,
                   three_month_return, twelve_month_return, volatility, dividend_yield
            from choice_stock_factor_snapshot
            order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows[0][:7] == ("000001.SZ", "Bank", 8.0, 0.8, 1.2, 0.18, 0.42)
    assert rows[0][7] == pytest.approx(0.5)
    assert rows[0][8] == pytest.approx(1.0)
    assert rows[0][9] > 0
    assert rows[0][10] == 0.035
    assert rows[1][:7] == ("600000.SH", "Bank", 12.0, 1.1, 1.8, 0.12, 0.35)
    assert rows[1][7] == pytest.approx(0.5)
    assert rows[1][8] == pytest.approx(1.0)
    assert rows[1][9] > 0
    assert rows[1][10] == 0.025


def test_choice_stock_factor_snapshot_keeps_rows_when_dividend_yield_missing(tmp_path: Path) -> None:
    class NanDividendTushareStockClient(FakeTushareStockClient):
        def daily_basic(self, **kwargs: object) -> pd.DataFrame:
            frame = super().daily_basic(**kwargs)
            frame.loc[frame["ts_code"] == "000001.SZ", "dv_ttm"] = float("nan")
            return frame

    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)
    tushare_client = NanDividendTushareStockClient()
    materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=PermissionDeniedCsdChoiceStockClient(),
        tushare_client=tushare_client,
    )

    result = materialize_choice_stock_factor_snapshot(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        tushare_client=tushare_client,
        use_choice_financial_fallback=False,
    )

    assert result["row_count"] == 2
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            "select stock_code, dividend_yield from choice_stock_factor_snapshot order by stock_code"
        ).fetchall()
    finally:
        conn.close()

    assert rows[0][0] == "000001.SZ"
    assert rows[0][1] is None or (isinstance(rows[0][1], float) and math.isnan(rows[0][1]))
    assert rows[1][0] == "600000.SH"
    assert rows[1][1] is not None


class SparseFinaFakeTushare(FakeTushareStockClient):
    """Emits fina_indicator rows without 000001.SZ — exercises Choice css patching."""

    def fina_indicator(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(("fina_indicator", kwargs))
        frame = FakeTushareStockClient.fina_indicator(self, **kwargs)
        return frame[frame["ts_code"] != "000001.SZ"].reset_index(drop=True)


class CssFinancialPatchClient:
    def __init__(self) -> None:
        self.css_calls: list[tuple[str, str, str]] = []

    def css(self, codes: object, indicators: object, *, options: str = "") -> object:
        codes_text = str(codes)
        indicators_text = str(indicators)
        self.css_calls.append((codes_text, indicators_text, options))
        return SimpleNamespace(
            ErrorCode=0,
            Indicators=["ROEWA", "GPMARGIN"],
            Data={"000001.SZ": [16.0, 44.5]},
        )


def test_choice_stock_factor_snapshot_merges_choice_css_financials(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss_css_fin.duckdb"
    _write_confirmed_catalog(catalog_path)

    sparse_tushare = SparseFinaFakeTushare()
    materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=PermissionDeniedCsdChoiceStockClient(),
        tushare_client=sparse_tushare,
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.executemany(
            """
            insert into choice_stock_daily_observation values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    trade_date,
                    stock_code,
                    close_value,
                    close_value,
                    close_value,
                    close_value,
                    1000.0,
                    close_value * 1000,
                    0.0,
                    1.0,
                    0.0,
                    "Trading",
                    "",
                    "",
                    '["daily_ohlcv_amount"]',
                    "sv_history",
                    "vv_history",
                    "rv_history",
                    "run-history",
                )
                for trade_date, close_a, close_b in [
                    ("2025-04-28", 5.25, 10.5),
                    ("2026-01-28", 7.0, 14.0),
                ]
                for stock_code, close_value in (("000001.SZ", close_a), ("600000.SH", close_b))
            ],
        )
    finally:
        conn.close()

    choice_css = CssFinancialPatchClient()
    result = materialize_choice_stock_factor_snapshot(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        tushare_client=sparse_tushare,
        choice_stock_client=choice_css,
        use_choice_financial_fallback=True,
    )

    assert result["status"] == "completed"
    assert choice_css.css_calls, "expected Choice css fallback for sparse fina_indicator coverage"
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, roe, gross_margin
            from choice_stock_factor_snapshot order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()

    by_code = {str(r[0]): (r[1], r[2]) for r in rows}
    assert by_code["000001.SZ"][0] == pytest.approx(0.16)
    assert by_code["000001.SZ"][1] == pytest.approx(0.445)
    assert by_code["600000.SH"][0] == pytest.approx(0.12)
    assert by_code["600000.SH"][1] == pytest.approx(0.35)


def test_choice_stock_materialize_accepts_choice_sector_flat_codes_payload(tmp_path: Path) -> None:
    class FlatSectorChoiceStockClient(FakeChoiceStockClient):
        def sector(self, *args: object, options: str = "") -> Any:
            self.calls.append(("sector", args, options))
            return SimpleNamespace(
                ErrorCode=0,
                ErrorMsg="success",
                Indicators=["SECUCODE", "SECURITYSHORTNAME"],
                Codes=["600000.SH", "000001.SZ", "600000.SH"],
                Data=["600000.SH", "SPDB", "000001.SZ", "PAB", "600000.SH", "SPDB"],
            )

        def csd(self, *args: object, options: str = "") -> Any:
            result = super().csd(*args, options=options)
            result.Dates = ["2026-4-28"]
            return result

    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)

    result = materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=FlatSectorChoiceStockClient(),
    )

    assert result["status"] == "completed"
    assert result["stock_code_count"] == 2
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        universe = conn.execute(
            """
            select stock_code, stock_name
            from choice_stock_universe
            order by stock_code
            """
        ).fetchall()
        daily_dates = conn.execute(
            """
            select trade_date, count(*)
            from choice_stock_daily_observation
            group by trade_date
            """
        ).fetchall()
    finally:
        conn.close()
    assert universe == [
        ("000001.SZ", "PAB"),
        ("600000.SH", "SPDB"),
    ]
    assert daily_dates == [("2026-04-28", 2)]


def test_choice_stock_materialize_accepts_choice_dataframe_payloads(tmp_path: Path) -> None:
    class DataFrameChoiceStockClient(FakeChoiceStockClient):
        def sector(self, *args: object, options: str = "") -> object:
            self.calls.append(("sector", args, options))
            return pd.DataFrame(
                [
                    {"SECUCODE": "600000.SH", "SECURITYSHORTNAME": "SPDB"},
                    {"SECUCODE": "000001.SZ", "SECURITYSHORTNAME": "PAB"},
                    {"SECUCODE": "600000.SH", "SECURITYSHORTNAME": "SPDB"},
                ]
            )

        def css(self, *args: object, options: str = "") -> object:
            self.calls.append(("css", args, options))
            indicators = str(args[1]).split(",")
            if "SW2021" in indicators:
                frame = pd.DataFrame(
                    [
                        {"SW2021": "Bank", "SW2021CODE": "801780"},
                        {"SW2021": "Bank", "SW2021CODE": "801780"},
                    ],
                    index=["000001.SZ", "600000.SH"],
                )
                frame.index.name = "CODES"
                return frame
            frame = pd.DataFrame(
                [
                    {"ISSURGEDLIMIT": "1", "ISDECLINELIMIT": "0", "HLIMITEDAYS": 2, "LLIMITEDDAYS": 0},
                    {"ISSURGEDLIMIT": "0", "ISDECLINELIMIT": "0", "HLIMITEDAYS": 0, "LLIMITEDDAYS": 0},
                ],
                index=["000001.SZ", "600000.SH"],
            )
            frame.index.name = "CODES"
            return frame

        def csd(self, *args: object, options: str = "") -> object:
            self.calls.append(("csd", args, options))
            indicators = str(args[1]).split(",")
            values_by_indicator = {
                "OPEN": [10.0, 20.0],
                "HIGH": [11.0, 21.0],
                "LOW": [9.5, 19.5],
                "CLOSE": [10.5, 20.5],
                "VOLUME": [1000.0, 2000.0],
                "AMOUNT": [10500.0, 41000.0],
                "PCTCHANGE": [1.2, -0.3],
                "TURN": [0.8, 0.5],
                "AMPLITUDE": [2.1, 1.4],
                "TRADESTATUS": ["Trading", "Trading"],
                "HIGHLIMIT": ["N", "N"],
                "LOWLIMIT": ["N", "N"],
            }
            frame = pd.DataFrame(
                {
                    "DATES": ["2026/04/28", "2026/04/28"],
                    **{indicator: values_by_indicator[indicator] for indicator in indicators},
                },
                index=["000001.SZ", "600000.SH"],
            )
            frame.index.name = "CODES"
            return frame

    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)

    result = materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=DataFrameChoiceStockClient(),
    )

    assert result["status"] == "completed"
    assert result["stock_code_count"] == 2
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        daily = conn.execute(
            """
            select stock_code, close_value, pctchange, tradestatus, highlimit
            from choice_stock_daily_observation
            order by stock_code
            """
        ).fetchall()
        sector_membership = conn.execute(
            """
            select stock_code, sw2021, sw2021code
            from choice_stock_sector_membership
            order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert daily == [
        ("000001.SZ", 10.5, 1.2, "Trading", "N"),
        ("600000.SH", 20.5, -0.3, "Trading", "N"),
    ]
    assert sector_membership == [
        ("000001.SZ", "Bank", "801780"),
        ("600000.SH", "Bank", "801780"),
    ]


def test_choice_stock_materialize_requires_exact_request_items_before_choice_calls(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["fields"] = [
        row for row in catalog["fields"] if row["field_key"] != "point_in_time_limit_streaks"
    ]
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    client = FakeChoiceStockClient()

    with pytest.raises(ValueError, match="missing required Choice stock request items"):
        materialize_choice_stock_inputs(
            as_of_date="2026-04-28",
            duckdb_path=str(duckdb_path),
            catalog_path=str(catalog_path),
            client=client,
        )

    assert client.calls == []


def test_choice_stock_materialization_coverage_requires_all_request_items(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "partial.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_choice_stock_schema(conn)
        conn.execute(
            """
            insert into choice_stock_request_audit values (
              'run-1', '2026-04-28', 'stock_universe', 'a_share_universe_sector_001004',
              'sector', '001004', '[]', '{}', 'completed', 1, 0, '',
              'sv', 'vv', 'rv'
            )
            """
        )
    finally:
        conn.close()

    coverage = load_choice_stock_materialization_coverage(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-04-28",
    )

    assert coverage.full_coverage is False
    assert coverage.status == "partial"
    assert "limit_up_quality:daily_limit_flags" in coverage.missing_request_items
    assert "limit_up_quality:point_in_time_limit_streaks" in coverage.missing_request_items


def test_choice_stock_materialization_coverage_requires_landed_daily_request_items(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)
    materialize_choice_stock_inputs(
        as_of_date="2026-04-28",
        duckdb_path=str(duckdb_path),
        catalog_path=str(catalog_path),
        client=FakeChoiceStockClient(),
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            "update choice_stock_daily_observation set field_keys_json = ?",
            [json.dumps(["daily_ohlcv_amount"])],
        )
    finally:
        conn.close()

    coverage = load_choice_stock_materialization_coverage(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-04-28",
    )

    assert coverage.full_coverage is False
    assert coverage.status == "partial"
    assert "stock_ohlcv:daily_ohlcv_amount" in coverage.completed_request_items
    assert "sector_strength:daily_return_turnover_amplitude" in coverage.missing_request_items
    assert "stock_status:daily_trade_status" in coverage.missing_request_items
    assert "limit_up_quality:daily_limit_flags" in coverage.missing_request_items


def test_choice_stock_materialization_persists_failed_request_audit(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_confirmed_catalog(catalog_path)

    with pytest.raises(RuntimeError, match="Choice csd failed in unit test"):
        materialize_choice_stock_inputs(
            as_of_date="2026-04-28",
            duckdb_path=str(duckdb_path),
            catalog_path=str(catalog_path),
            client=FailingCsdChoiceStockClient(),
        )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        run_row = conn.execute(
            """
            select status, request_count, row_count, error_message
            from choice_stock_materialize_run
            """
        ).fetchone()
        audit_rows = conn.execute(
            """
            select input_family, field_key, status, row_count, error_code, error_msg
            from choice_stock_request_audit
            order by input_family, field_key
            """
        ).fetchall()
        landed_counts = {
            table: conn.execute(f"select count(*) from {table}").fetchone()[0]
            for table in (
                "choice_stock_universe",
                "choice_stock_sector_membership",
                "choice_stock_daily_observation",
                "choice_stock_limit_quality",
            )
        }
    finally:
        conn.close()

    assert run_row == ("failed", 3, 0, "Choice csd failed in unit test")
    assert (
        "sector_strength",
        "daily_return_turnover_amplitude",
        "failed",
        0,
        1001,
        "Choice csd failed in unit test",
    ) in audit_rows
    assert ("stock_universe", "a_share_universe_sector_001004", "completed", 2, 0, "") in audit_rows
    assert ("sector_membership", "sw2021_industry_membership", "completed", 2, 0, "") in audit_rows
    assert landed_counts == {
        "choice_stock_universe": 0,
        "choice_stock_sector_membership": 0,
        "choice_stock_daily_observation": 0,
        "choice_stock_limit_quality": 0,
    }


def test_choice_stock_materialization_coverage_fails_closed_for_unreadable_duckdb(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "broken.duckdb"
    duckdb_path.write_text("not a duckdb database", encoding="utf-8")

    coverage = load_choice_stock_materialization_coverage(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-04-28",
    )

    assert coverage.full_coverage is False
    assert coverage.status == "not_materialized"
    assert "stock_universe:a_share_universe_sector_001004" in coverage.missing_request_items
