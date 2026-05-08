from __future__ import annotations

import sys
from datetime import date, timedelta

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.tasks.livermore_candidate_history_materialize import materialize_livermore_candidate_history
from tests.helpers import load_module


def _minimal_observation_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double
        )
        """
    )


def _fake_payload(
    *,
    as_of_date: str,
    items: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    return (
        {
            "as_of_date": as_of_date,
            "requested_as_of_date": as_of_date,
            "stock_candidates": {"items": items},
            "market_gate": {"state": "HOT"},
        },
        {
            "source_version": "sv_test_candidate_meta",
            "vendor_version": "vv_test_candidate_meta",
            "quality_flag": "ok",
        },
    )


def _seed_calendar_observations(
    duckdb_path: str,
    *,
    stock_code: str,
    start: date,
    days: int,
    base_close: float = 100.0,
    step: float = 0.1,
) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        _minimal_observation_schema(conn)
        rows = []
        for i in range(days):
            d = (start + timedelta(days=i)).isoformat()
            rows.append((d, stock_code, base_close + step * i))
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            rows,
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


def test_task_happy_path_forward_returns(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "hist.duckdb"
    snap = date(2026, 1, 6)
    stock = "000001.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=35)

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[
                {"rank": 1, "stock_code": stock, "stock_name": "Ping", "sector_code": "S1", "sector_name": "银行"},
            ],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    out = materialize_livermore_candidate_history(str(db_path))
    assert out["status"] == "ok"
    assert out["row_count"] == 1

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute("select selection_close, return_1d, return_5d, return_20d, data_status from livermore_candidate_history").fetchone()
        assert row is not None
        selection_close, r1, r5, r20, dst = row
        assert selection_close == 100.0
        # bar 2026-01-07 closes at 100.1
        assert abs(float(r1) - 0.001) < 1e-9
        tgt5 = conn.execute(
            """
            select close_value from choice_stock_daily_observation
            where stock_code = ? and trade_date > ? order by trade_date limit 5
            """,
            [stock, snap.isoformat()],
        ).fetchall()
        tgt20 = conn.execute(
            """
            select close_value from choice_stock_daily_observation
            where stock_code = ? and trade_date > ? order by trade_date limit 20
            """,
            [stock, snap.isoformat()],
        ).fetchall()
        expected_r5 = (float(tgt5[-1][0]) - selection_close) / selection_close
        expected_r20 = (float(tgt20[-1][0]) - selection_close) / selection_close
        assert abs(float(r5) - expected_r5) < 1e-9
        assert abs(float(r20) - expected_r20) < 1e-9
        assert dst == "complete"
    finally:
        conn.close()


def test_task_partial_halt_long_gap(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "halt.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    snap = date(2026, 3, 2)
    stock = "600000.SH"
    try:
        _minimal_observation_schema(conn)
        conn.executemany(
            "insert into choice_stock_daily_observation (trade_date, stock_code, close_value) values (?, ?, ?)",
            [
                (snap.isoformat(), stock, 10.0),
                ((snap + timedelta(days=10)).isoformat(), stock, 11.0),
                ((snap + timedelta(days=11)).isoformat(), stock, 11.05),
                ((snap + timedelta(days=12)).isoformat(), stock, 11.1),
                ((snap + timedelta(days=13)).isoformat(), stock, 11.15),
                ((snap + timedelta(days=14)).isoformat(), stock, 11.2),
            ],
        )
    finally:
        conn.close()

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[{"rank": 1, "stock_code": stock, "stock_name": "GapCo", "sector_code": "", "sector_name": ""}],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )
    materialize_livermore_candidate_history(str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute("select data_status, return_1d, forward_trade_date_1d from livermore_candidate_history").fetchone()
        assert row is not None
        assert row[0] == "partial_halt"
        assert row[1] is not None
        assert str(row[2])[:10] == (snap + timedelta(days=10)).isoformat()
    finally:
        conn.close()


def test_task_pending_insufficient_forward_bars(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "pend.duckdb"
    snap = date(2026, 5, 1)
    stock = "000002.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=12)

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[{"rank": 1, "stock_code": stock, "stock_name": "Beta", "sector_code": "", "sector_name": ""}],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )
    materialize_livermore_candidate_history(str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            "select return_20d, forward_trade_date_20d, data_status from livermore_candidate_history"
        ).fetchone()
        assert row is not None
        assert row[0] is None
        assert row[1] is None
        assert row[2] == "pending"
    finally:
        conn.close()


def test_task_dedupe_second_run(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "ded.duckdb"
    snap = date(2026, 2, 2)
    stock = "000003.SZ"
    _seed_calendar_observations(str(db_path), stock_code=stock, start=snap, days=30)

    def _mock_load(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return _fake_payload(
            as_of_date=snap.isoformat(),
            items=[{"rank": 1, "stock_code": stock, "stock_name": "Ded", "sector_code": "", "sector_name": ""}],
        )

    monkeypatch.setattr(
        "backend.app.tasks.livermore_candidate_history_materialize.load_livermore_strategy_payload",
        _mock_load,
    )

    materialize_livermore_candidate_history(str(db_path))
    materialize_livermore_candidate_history(str(db_path))

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        n = conn.execute(
            "select count(*)::integer from livermore_candidate_history where snapshot_as_of_date = ?",
            [snap.isoformat()],
        ).fetchone()
        assert n is not None and int(n[0]) == 1
    finally:
        conn.close()


def test_api_happy_and_filters(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              candidate_rank integer,
              sector_code varchar,
              sector_name varchar,
              selection_close double,
              forward_trade_date_1d varchar,
              forward_trade_date_5d varchar,
              forward_trade_date_20d varchar,
              return_1d double,
              return_5d double,
              return_20d double,
              data_status varchar,
              formula_version varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            """
            insert into livermore_candidate_history values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-04-01",
                    "000001.SZ",
                    "A",
                    1,
                    "S",
                    "Sec",
                    10.0,
                    "2026-04-02",
                    "2026-04-08",
                    "2026-04-28",
                    0.01,
                    0.02,
                    0.03,
                    "complete",
                    "fv1",
                    "sv1",
                    "vv1",
                    "rv1",
                    "r1",
                ),
                (
                    "2026-03-15",
                    "000001.SZ",
                    "A",
                    1,
                    None,
                    None,
                    9.5,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "pending",
                    "fv1",
                    "sv2",
                    "vv2",
                    "rv1",
                    "r2",
                ),
            ],
        )
    finally:
        conn.close()

    client = _build_client(tmp_path, monkeypatch)
    r = client.get(
        "/ui/market-data/livermore/candidate-history",
        params={"stock_code": "000001.SZ", "snapshot_from": "2026-04-01", "snapshot_to": "2026-04-30", "limit": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result_meta"]["basis"] == "analytical"
    assert body["result_meta"]["rule_version"] == "rv_livermore_candidate_history_v1"
    assert "livermore_candidate_history" in body["result_meta"]["tables_used"]
    assert len(body["result"]["items"]) == 1

    r2 = client.get(
        "/ui/market-data/livermore/candidate-history",
        params={"stock_code": "000001.SZ"},
    )
    assert r2.status_code == 200
    assert len(r2.json()["result"]["items"]) == 2
    get_settings.cache_clear()


def test_api_empty_table(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              candidate_rank integer,
              sector_code varchar,
              sector_name varchar,
              selection_close double,
              forward_trade_date_1d varchar,
              forward_trade_date_5d varchar,
              forward_trade_date_20d varchar,
              return_1d double,
              return_5d double,
              return_20d double,
              data_status varchar,
              formula_version varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    client = _build_client(tmp_path, monkeypatch)
    r = client.get("/ui/market-data/livermore/candidate-history")
    assert r.status_code == 200
    assert r.json()["result"]["items"] == []
    get_settings.cache_clear()


def test_api_limit_validation(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn_tbl = duckdb.connect(str(db_path), read_only=False)
    try:
        conn_tbl.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              candidate_rank integer,
              sector_code varchar,
              sector_name varchar,
              selection_close double,
              forward_trade_date_1d varchar,
              forward_trade_date_5d varchar,
              forward_trade_date_20d varchar,
              return_1d double,
              return_5d double,
              return_20d double,
              data_status varchar,
              formula_version varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn_tbl.close()

    client = _build_client(tmp_path, monkeypatch)
    assert client.get("/ui/market-data/livermore/candidate-history", params={"limit": 0}).status_code == 422
    assert client.get("/ui/market-data/livermore/candidate-history", params={"limit": 501}).status_code == 422
    get_settings.cache_clear()
