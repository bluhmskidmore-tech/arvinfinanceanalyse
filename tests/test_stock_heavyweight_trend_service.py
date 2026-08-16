from __future__ import annotations

import sys
from datetime import date, timedelta

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.services.stock_heavyweight_trend_service import stock_heavyweight_trend_envelope
from tests.helpers import load_module

SECTORS = [
    ("SW801010", "Sect01"),
    ("SW801020", "Sect02"),
    ("SW801030", "Sect03"),
]
STOCKS_PER_SECTOR = 3


def _weekdays(end: date, count: int) -> list[date]:
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(days))


def _stock_code(sector_index: int, stock_index: int) -> str:
    return f"S{sector_index}{stock_index}0000.SZ"


def _create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_sector_membership (
          as_of_date varchar,
          stock_code varchar,
          sw2021 varchar,
          sw2021code varchar,
          source_version varchar,
          vendor_version varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_universe (
          as_of_date varchar,
          stock_code varchar,
          stock_name varchar,
          source_version varchar,
          vendor_version varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double,
          pctchange double,
          turn double,
          amplitude double,
          tradestatus varchar,
          source_version varchar,
          vendor_version varchar
        )
        """
    )


def _seed_fixture(
    duckdb_path: str,
    *,
    days: list[date],
    closes_by_stock: dict[str, list[float | None]],
    suspended_by_stock: dict[str, set[str]] | None = None,
) -> None:
    """Seed 3 sectors x 3 stocks. ``closes_by_stock`` is aligned with ``days``.

    A date in ``suspended_by_stock[code]`` is written with a non-trading
    ``tradestatus`` so the read path must drop it exactly like a real halt.
    """
    suspended = suspended_by_stock or {}
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        _create_schema(conn)
        membership_date = days[-1].isoformat()
        for sector_index, (sector_code, sector_name) in enumerate(SECTORS):
            for stock_index in range(STOCKS_PER_SECTOR):
                code = _stock_code(sector_index, stock_index)
                conn.execute(
                    """
                    insert into choice_stock_sector_membership
                    (as_of_date, stock_code, sw2021, sw2021code, source_version, vendor_version)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (membership_date, code, sector_name, sector_code, "sv_mem", "vv_mem"),
                )
                conn.execute(
                    """
                    insert into choice_stock_universe
                    (as_of_date, stock_code, stock_name, source_version, vendor_version)
                    values (?, ?, ?, ?, ?)
                    """,
                    (membership_date, code, f"名称{sector_index}{stock_index}", "sv_uni", "vv_uni"),
                )
                closes = closes_by_stock[code]
                halted = suspended.get(code, set())
                # turn descends with stock_index so leader order is deterministic.
                turn = float(STOCKS_PER_SECTOR - stock_index)
                for day, close in zip(days, closes, strict=True):
                    iso = day.isoformat()
                    conn.execute(
                        """
                        insert into choice_stock_daily_observation
                        (trade_date, stock_code, close_value, pctchange, turn, amplitude,
                         tradestatus, source_version, vendor_version)
                        values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            iso,
                            code,
                            close,
                            1.0 + sector_index,
                            turn,
                            2.0 + sector_index,
                            "停牌" if iso in halted else "Trading",
                            "sv_obs",
                            "vv_obs",
                        ),
                    )
    finally:
        conn.close()


def _linear_closes(base: float, step: float, count: int) -> list[float | None]:
    return [base + step * index for index in range(count)]


def _default_closes(days: list[date]) -> dict[str, list[float | None]]:
    closes: dict[str, list[float | None]] = {}
    for sector_index in range(len(SECTORS)):
        for stock_index in range(STOCKS_PER_SECTOR):
            closes[_stock_code(sector_index, stock_index)] = _linear_closes(
                10.0 + sector_index + stock_index,
                0.5,
                len(days),
            )
    return closes


def _build_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(tmp_path / "data_input"))
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    monkeypatch.setenv(
        "MOSS_CHOICE_STOCK_CATALOG_FILE", str(tmp_path / "missing-choice-stock-catalog.json")
    )
    get_settings.cache_clear()
    from backend.app.repositories.user_scope_repo import UserScopeRepository

    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="*",
        role=None,
        resource="market_data.livermore",
        action="read",
    )
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    client.headers.update({"X-User-Id": "livermore-read-user", "X-User-Role": "viewer"})
    return client


def _find_stock(result: dict, stock_code: str) -> dict:
    for sector in result["sectors"]:
        for stock in sector["stocks"]:
            if stock["stock_code"] == stock_code:
                return stock
    raise AssertionError(f"{stock_code} not present in heavyweight trend payload")


def test_heavyweight_trends_golden_normalized_series(tmp_path) -> None:
    end = date(2026, 4, 10)
    days = _weekdays(end, 20)
    db_path = tmp_path / "moss.duckdb"
    _seed_fixture(str(db_path), days=days, closes_by_stock=_default_closes(days))

    envelope = stock_heavyweight_trend_envelope(duckdb_path=str(db_path), as_of_date=end)

    meta = envelope["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["result_kind"] == "market_data.stock_analysis.heavyweight_trends"
    assert meta["formal_use_allowed"] is False

    result = envelope["result"]
    assert result["state"] == "ok"
    assert result["as_of_date"] == end.isoformat()
    assert result["series_basis"] == "cum_pct_from_first_close"
    assert result["window_trade_dates"] == [day.isoformat() for day in days]
    assert result["warnings"] == []
    assert result["coverage"] == {
        "sector_count": 3,
        "stock_count": 9,
        "stock_with_series_count": 9,
        "stock_missing_series_count": 0,
        "window_trade_date_count": 20,
    }

    # base 10.0, +0.5 per session -> cumulative percent is exact to 4 decimals.
    leader = _find_stock(result, _stock_code(0, 0))
    assert leader["rank"] == 1
    assert leader["stock_name"] == "名称00"
    assert leader["trend_state"] == "ok"
    assert leader["point_count"] == 20
    assert leader["missing_point_count"] == 0
    assert leader["trend_note"] is None
    assert leader["trade_dates"] == [day.isoformat() for day in days]
    assert leader["close_values"][0] == 10.0
    assert leader["close_values"][-1] == 19.5
    assert leader["cum_pct_changes"][0] == 0.0
    assert leader["cum_pct_changes"][1] == 5.0
    assert leader["cum_pct_changes"][-1] == 95.0
    assert leader["window_return_pct"] == 95.0
    # single-day pctchange is echoed for reconciliation against the workbench card.
    assert leader["pctchange"] == 1.0

    # every ranked sector carries exactly the requested leader count.
    assert len(result["sectors"]) == 3
    for sector in result["sectors"]:
        assert len(sector["stocks"]) == STOCKS_PER_SECTOR
        assert [stock["rank"] for stock in sector["stocks"]] == [1, 2, 3]


def test_heavyweight_trends_skips_suspended_sessions(tmp_path) -> None:
    end = date(2026, 4, 10)
    days = _weekdays(end, 20)
    halted_days = {days[5].isoformat(), days[6].isoformat(), days[7].isoformat()}
    db_path = tmp_path / "moss.duckdb"
    _seed_fixture(
        str(db_path),
        days=days,
        closes_by_stock=_default_closes(days),
        suspended_by_stock={_stock_code(0, 0): halted_days},
    )

    result = stock_heavyweight_trend_envelope(duckdb_path=str(db_path), as_of_date=end)["result"]

    halted_stock = _find_stock(result, _stock_code(0, 0))
    assert halted_stock["point_count"] == 17
    assert halted_stock["missing_point_count"] == 3
    assert halted_stock["trend_state"] == "partial"
    assert halted_stock["trend_note"] == "missing_3_sessions"
    assert halted_days.isdisjoint(set(halted_stock["trade_dates"]))
    assert len(halted_stock["close_values"]) == 17
    assert len(halted_stock["cum_pct_changes"]) == 17
    # halted sessions are dropped, never interpolated: the base is still day 0.
    assert halted_stock["cum_pct_changes"][0] == 0.0
    assert halted_stock["close_values"][0] == 10.0

    healthy_stock = _find_stock(result, _stock_code(1, 0))
    assert healthy_stock["trend_state"] == "ok"
    assert healthy_stock["point_count"] == 20

    assert result["coverage"]["stock_with_series_count"] == 9
    assert result["warnings"] == []


def test_heavyweight_trends_returns_available_segment_when_short_of_window(tmp_path) -> None:
    end = date(2026, 4, 10)
    days = _weekdays(end, 8)
    db_path = tmp_path / "moss.duckdb"
    _seed_fixture(str(db_path), days=days, closes_by_stock=_default_closes(days))

    result = stock_heavyweight_trend_envelope(
        duckdb_path=str(db_path),
        as_of_date=end,
        window_days=20,
    )["result"]

    assert result["state"] == "ok"
    assert result["window_days"] == 20
    assert len(result["window_trade_dates"]) == 8
    assert result["coverage"]["window_trade_date_count"] == 8
    assert any(warning.startswith("window_shortfall:") for warning in result["warnings"])

    leader = _find_stock(result, _stock_code(0, 0))
    assert leader["point_count"] == 8
    assert leader["missing_point_count"] == 0
    assert leader["trend_state"] == "ok"
    assert len(leader["cum_pct_changes"]) == 8


def test_heavyweight_trends_missing_stock_series_degrades_quietly(tmp_path) -> None:
    end = date(2026, 4, 10)
    days = _weekdays(end, 20)
    db_path = tmp_path / "moss.duckdb"
    closes = _default_closes(days)
    # Only the as-of session trades: the stock still ranks as a leader but has
    # no usable multi-session line.
    target = _stock_code(0, 0)
    _seed_fixture(
        str(db_path),
        days=days,
        closes_by_stock=closes,
        suspended_by_stock={target: {day.isoformat() for day in days[:-1]}},
    )

    result = stock_heavyweight_trend_envelope(duckdb_path=str(db_path), as_of_date=end)["result"]

    thin_stock = _find_stock(result, target)
    assert thin_stock["point_count"] == 1
    assert thin_stock["trend_state"] == "insufficient"
    assert thin_stock["trend_note"] == "single_session_only"
    assert thin_stock["cum_pct_changes"] == [0.0]
    # the sector card still renders: sibling stocks keep full series
    sibling = _find_stock(result, _stock_code(0, 1))
    assert sibling["trend_state"] == "ok"
    assert result["state"] == "ok"


def test_heavyweight_trends_empty_database_returns_empty_with_reason(tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path)).close()

    envelope = stock_heavyweight_trend_envelope(duckdb_path=str(db_path), as_of_date=None)

    assert envelope["result_meta"]["quality_flag"] == "warning"
    result = envelope["result"]
    assert result["state"] == "missing"
    assert result["sectors"] == []
    assert result["window_trade_dates"] == []
    assert result["reason_code"] == "source_table_unavailable"
    assert result["warnings"] == ["source_table_unavailable"]
    assert result["coverage"]["stock_count"] == 0


def test_heavyweight_trends_missing_duckdb_file_returns_reason(tmp_path) -> None:
    envelope = stock_heavyweight_trend_envelope(
        duckdb_path=str(tmp_path / "absent.duckdb"),
        as_of_date=None,
    )

    result = envelope["result"]
    assert result["state"] == "missing"
    assert result["reason_code"] == "duckdb_missing"
    assert result["sectors"] == []


def test_heavyweight_trends_duckdb_read_error_degrades_instead_of_raising(
    tmp_path, monkeypatch
) -> None:
    end = date(2026, 4, 10)
    days = _weekdays(end, 20)
    db_path = tmp_path / "moss.duckdb"
    _seed_fixture(str(db_path), days=days, closes_by_stock=_default_closes(days))

    from backend.app.repositories.livermore_market_read_repo import (
        LivermoreMarketReadRepository,
    )

    def boom(*_args, **_kwargs):
        raise duckdb.Error("simulated writer lock")

    monkeypatch.setattr(LivermoreMarketReadRepository, "list_table_names", boom)

    envelope = stock_heavyweight_trend_envelope(duckdb_path=str(db_path), as_of_date=end)

    result = envelope["result"]
    assert result["state"] == "missing"
    assert result["reason_code"] == "duckdb_read_failed"
    assert result["sectors"] == []


def test_heavyweight_trends_endpoint_contract(tmp_path, monkeypatch) -> None:
    end = date(2026, 4, 10)
    days = _weekdays(end, 20)
    db_path = tmp_path / "moss.duckdb"
    _seed_fixture(str(db_path), days=days, closes_by_stock=_default_closes(days))
    client = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/market-data/stock-analysis/heavyweight-trends",
        params={"as_of_date": end.isoformat()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload).issuperset({"result", "result_meta"})
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["result_kind"] == "market_data.stock_analysis.heavyweight_trends"
    assert payload["result"]["state"] == "ok"
    assert len(payload["result"]["sectors"]) == 3
    assert response.headers["Server-Timing"].startswith("heavyweight-trends;dur=")
    get_settings.cache_clear()


def test_heavyweight_trends_endpoint_rejects_bad_params(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path)).close()
    client = _build_client(tmp_path, monkeypatch)

    base = "/ui/market-data/stock-analysis/heavyweight-trends"
    assert client.get(base, params={"as_of_date": "not-a-date"}).status_code == 422
    assert client.get(base, params={"window_days": 4}).status_code == 422
    assert client.get(base, params={"window_days": 61}).status_code == 422
    assert client.get(base, params={"sector_limit": 0}).status_code == 422
    assert client.get(base, params={"stocks_per_sector": 11}).status_code == 422
    get_settings.cache_clear()
