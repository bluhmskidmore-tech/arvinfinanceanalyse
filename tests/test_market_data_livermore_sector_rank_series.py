from __future__ import annotations

import sys
from datetime import date, timedelta

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _seed_sector_series_fixture(
    duckdb_path: str,
    *,
    days: list[date],
    sector_specs: list[tuple[str, str]],
    pct_matrix: list[list[float]],
) -> None:
    """pct_matrix[len(days)][len(sector_specs)] — avg pctchange driver per sector per day (single stock per sector)."""
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
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
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              pctchange double,
              turn double,
              amplitude double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        assert len(pct_matrix) == len(days)
        assert all(len(row) == len(sector_specs) for row in pct_matrix)
        for day_idx, d in enumerate(days):
            for sec_idx, (code, name) in enumerate(sector_specs):
                stock = f"S{sec_idx:03d}.SZ"
                pct = pct_matrix[day_idx][sec_idx]
                conn.execute(
                    """
                    insert into choice_stock_sector_membership
                    (as_of_date, stock_code, sw2021, sw2021code, source_version, vendor_version)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (d.isoformat(), stock, name, code, "sv_test_sec", "vv_test_sec"),
                )
                conn.execute(
                    """
                    insert into choice_stock_daily_observation
                    (trade_date, stock_code, pctchange, turn, amplitude, source_version, vendor_version)
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        d.isoformat(),
                        stock,
                        pct,
                        float(sec_idx + 1),
                        float(sec_idx + 1) * 0.5,
                        "sv_test_obs",
                        "vv_test_obs",
                    ),
                )
    finally:
        conn.close()


def _build_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(tmp_path / "data_input"))
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_CHOICE_STOCK_CATALOG_FILE", str(tmp_path / "missing-choice-stock-catalog.json"))
    get_settings.cache_clear()
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    return TestClient(load_module("backend.app.main", "backend/app/main.py").app)


def _five_weekdays(end: date) -> list[date]:
    return [end - timedelta(days=4 - i) for i in range(5)]


def test_sector_rank_series_happy_path_window_5(tmp_path, monkeypatch) -> None:
    end = date(2026, 4, 10)
    days = _five_weekdays(end)
    sectors = [
        ("SW801010", "Sect01"),
        ("SW801020", "Sect02"),
        ("SW801030", "Sect03"),
        ("SW801040", "Sect04"),
    ]
    pct_matrix = [[float(i + j) * 0.1 for j in range(len(sectors))] for i in range(len(days))]
    db_path = tmp_path / "moss.duckdb"
    _seed_sector_series_fixture(str(db_path), days=days, sector_specs=sectors, pct_matrix=pct_matrix)
    client = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/market-data/livermore/sector-rank-series",
        params={"window_days": 5, "top_k": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "market_data.livermore.sector_rank_series"
    assert payload["result_meta"]["quality_flag"] == "ok"
    result = payload["result"]
    assert result["state"] == "ok"
    assert result["window_days"] == 5
    series = result["series"]
    distinct_dates = {row["trade_date"] for row in series}
    assert distinct_dates == {d.isoformat() for d in days}
    assert len(series) == len(days) * len(sectors)
    notes = result["unsupported_notes"]
    assert "momentum_persistence: needs metric definition review (P1)" in notes
    assert "sector_money_flow: needs vendor approval & new schema (P1)" in notes
    get_settings.cache_clear()


def test_sector_rank_series_window_20(tmp_path, monkeypatch) -> None:
    end = date(2026, 4, 10)
    days = _five_weekdays(end)
    sectors = [
        ("SW801010", "Sect01"),
        ("SW801020", "Sect02"),
        ("SW801030", "Sect03"),
    ]
    pct_matrix = [[float(i + j) * 0.05 for j in range(len(sectors))] for i in range(len(days))]
    db_path = tmp_path / "moss.duckdb"
    _seed_sector_series_fixture(str(db_path), days=days, sector_specs=sectors, pct_matrix=pct_matrix)
    client = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/market-data/livermore/sector-rank-series",
        params={"window_days": 20, "top_k": 10},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["window_days"] == 20
    assert len({row["trade_date"] for row in result["series"]}) == 5
    get_settings.cache_clear()


def test_sector_rank_series_sector_code_filter(tmp_path, monkeypatch) -> None:
    end = date(2026, 4, 10)
    days = _five_weekdays(end)
    sectors = [
        ("SW801010", "Sect01"),
        ("SW801020", "Sect02"),
        ("SW801030", "Sect03"),
    ]
    pct_matrix = [[float(i + j) * 0.03 for j in range(len(sectors))] for i in range(len(days))]
    db_path = tmp_path / "moss.duckdb"
    _seed_sector_series_fixture(str(db_path), days=days, sector_specs=sectors, pct_matrix=pct_matrix)
    client = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/market-data/livermore/sector-rank-series",
        params={"window_days": 5, "sector_code": "SW801020", "top_k": 10},
    )

    assert response.status_code == 200
    series = response.json()["result"]["series"]
    codes = {row["sector_code"] for row in series}
    assert codes == {"SW801020"}
    assert len(series) == len(days)
    get_settings.cache_clear()


def test_sector_rank_series_top_k_limit(tmp_path, monkeypatch) -> None:
    end = date(2026, 4, 10)
    days = _five_weekdays(end)
    sectors = [(f"SW801{i:03d}", f"Sx{i}") for i in range(6)]
    pct_matrix = []
    for i in range(len(days)):
        row = [float(10 - j + i * 0.01) for j in range(len(sectors))]
        pct_matrix.append(row)
    db_path = tmp_path / "moss.duckdb"
    _seed_sector_series_fixture(str(db_path), days=days, sector_specs=sectors, pct_matrix=pct_matrix)
    client = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/market-data/livermore/sector-rank-series",
        params={"window_days": 5, "top_k": 2},
    )

    assert response.status_code == 200
    series = response.json()["result"]["series"]
    codes_latest = {
        row["sector_code"] for row in series if row["trade_date"] == end.isoformat()
    }
    assert len(codes_latest) <= 2
    assert len({row["sector_code"] for row in series}) <= 2
    get_settings.cache_clear()


def test_sector_rank_series_missing_empty_tables(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path)).close()
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/ui/market-data/livermore/sector-rank-series")

    assert response.status_code == 200
    meta = response.json()["result_meta"]
    assert meta["quality_flag"] == "warning"
    result = response.json()["result"]
    assert result["state"] == "missing"
    assert result["series"] == []
    get_settings.cache_clear()


def test_sector_rank_series_param_validation(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path)).close()
    client = _build_client(tmp_path, monkeypatch)

    assert (
        client.get("/ui/market-data/livermore/sector-rank-series", params={"window_days": 1}).status_code == 422
    )
    assert (
        client.get("/ui/market-data/livermore/sector-rank-series", params={"window_days": 61}).status_code == 422
    )
    assert (
        client.get(
            "/ui/market-data/livermore/sector-rank-series",
            params={"as_of_date": "not-a-date"},
        ).status_code
        == 422
    )
    get_settings.cache_clear()


def test_sector_rank_series_cum_pctchange_window(tmp_path, monkeypatch) -> None:
    end = date(2026, 4, 10)
    days = _five_weekdays(end)
    sectors = [
        ("SW801010", "Sect01"),
        ("SW801020", "Sect02"),
        ("SW801030", "Sect03"),
    ]
    pct_matrix = [[1.0 + float(j) * 0.01 for j in range(len(sectors))] for _ in days]
    db_path = tmp_path / "moss.duckdb"
    _seed_sector_series_fixture(str(db_path), days=days, sector_specs=sectors, pct_matrix=pct_matrix)
    client = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/market-data/livermore/sector-rank-series",
        params={"window_days": 5, "sector_code": "SW801020", "top_k": 10},
    )

    assert response.status_code == 200
    series = response.json()["result"]["series"]
    latest_rows = [r for r in series if r["trade_date"] == end.isoformat()]
    assert len(latest_rows) == 1
    row = latest_rows[0]
    expected = sum(float(r["avg_pctchange"]) for r in series if r["sector_code"] == "SW801020")
    assert abs(float(row["cum_pctchange_window"]) - round(expected, 6)) < 1e-5
    non_latest = [r for r in series if r["trade_date"] != end.isoformat()]
    assert all(r["cum_pctchange_window"] is None for r in non_latest)
    get_settings.cache_clear()


def test_sector_rank_series_unsupported_notes_complete(tmp_path, monkeypatch) -> None:
    end = date(2026, 4, 10)
    days = _five_weekdays(end)
    sectors = [
        ("SW801010", "Sect01"),
        ("SW801020", "Sect02"),
        ("SW801030", "Sect03"),
    ]
    pct_matrix = [[0.01 for _ in sectors] for _ in days]
    db_path = tmp_path / "moss.duckdb"
    _seed_sector_series_fixture(str(db_path), days=days, sector_specs=sectors, pct_matrix=pct_matrix)
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/ui/market-data/livermore/sector-rank-series", params={"window_days": 5})

    notes = response.json()["result"]["unsupported_notes"]
    assert len(notes) >= 2
    assert any("momentum_persistence" in n for n in notes)
    assert any("sector_money_flow" in n for n in notes)
    get_settings.cache_clear()
