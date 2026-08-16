from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from backend.app.repositories.choice_stock_adapter import ChoiceStockReadiness
from backend.app.repositories.livermore_gate_supplement_repo import fetch_market_gate_supplement
from backend.app.services import market_data_livermore_service as livermore_service
from backend.app.tasks import choice_stock_materialize as choice_stock_materialize_task
from backend.app.tasks.choice_stock_materialize import load_choice_stock_materialization_coverage


def _ready_choice_stock_catalog() -> ChoiceStockReadiness:
    return ChoiceStockReadiness(
        ready=True,
        status="ready",
        catalog_path="test-catalog.json",
        missing_input_families=[],
        message="ready",
    )


def test_fetch_market_gate_supplement_keeps_borrowed_connection_open() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table fact_livermore_gate_supplement_daily (
                trade_date date,
                breadth_5d double,
                limit_up_quality_ok boolean
            )
            """
        )
        conn.execute(
            "insert into fact_livermore_gate_supplement_daily values ('2026-07-22', 0.25, true)"
        )

        result = fetch_market_gate_supplement(
            duckdb_path="unused-when-connection-is-borrowed.duckdb",
            trade_date=date(2026, 7, 22),
            conn=conn,
        )

        assert result is not None
        assert result.breadth_5d == 0.25
        assert result.limit_up_quality_ok is True
        assert conn.execute("select 1").fetchone() == (1,)
    finally:
        conn.close()


def test_materialization_coverage_keeps_borrowed_connection_open(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    duckdb_path = tmp_path / "coverage.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        monkeypatch.setattr(
            choice_stock_materialize_task,
            "get_runtime_cache",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("borrowed connection must bypass cache")),
        )
        coverage = load_choice_stock_materialization_coverage(
            duckdb_path=str(duckdb_path),
            as_of_date="2026-07-22",
            conn=conn,
        )

        assert coverage.status == "not_materialized"
        assert conn.execute("select 1").fetchone() == (1,)
    finally:
        conn.close()


def test_stock_output_loader_reuses_one_connection_for_coverage_and_candidates(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    duckdb_path = tmp_path / "stock-output.duckdb"
    bootstrap = duckdb.connect(str(duckdb_path))
    bootstrap.close()
    original_connect = duckdb.connect
    connect_calls: list[tuple[object, ...]] = []

    def counted_connect(*args: object, **kwargs: object) -> duckdb.DuckDBPyConnection:
        connect_calls.append(args)
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(livermore_service.duckdb, "connect", counted_connect)

    outputs = livermore_service._load_choice_stock_outputs(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-07-22",
        market_state="OFF",
        stock_readiness=_ready_choice_stock_catalog(),
    )

    assert outputs.stock_coverage is not None
    assert outputs.stock_coverage.status == "not_materialized"
    assert len(connect_calls) == 1
