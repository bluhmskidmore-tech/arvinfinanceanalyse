"""MS-011: execute actual refresh functions against owned synthetic DuckDB.

AST loading isolates the task from real actor registration and provider setup;
only its date/schema/vendor boundaries are supplied below. The SQL writer, transaction orchestration, universe selection,
failure guard and column checks are compiled directly from the current source.
This is not a provider integration test.
"""
from __future__ import annotations

import ast
import logging
import socket
import uuid
from contextlib import nullcontext
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock

ROOT = Path(__file__).resolve().parents[1]
pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_market_data]


def _schema(conn):
    conn.execute((ROOT / "backend/app/schema_registry/duckdb/27_choice_stock_factor_snapshot.sql").read_text(encoding="utf-8"))
    conn.execute("create table if not exists choice_stock_universe (as_of_date varchar, stock_code varchar)")


@pytest.fixture
def refresh(tmp_path, monkeypatch):
    def deny_network(*args, **kwargs):
        raise AssertionError("No provider or network access is allowed in this regression")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "getaddrinfo", deny_network)
    path = tmp_path / "synthetic-factors.duckdb"
    with duckdb.connect(str(path)) as conn:
        _schema(conn)
        conn.executemany(
            "insert into choice_stock_factor_snapshot (as_of_date, stock_code, pe, pb, roe, total_mv, industry, "
            "source_version, vendor_version, rule_version, run_id) values (?, ?, ?, 2, .12, 1000, 'synthetic', "
            "'old-source', 'old-vendor', 'old-rule', 'old-run')",
            [("2026-09-30", "SYNTH-A", 10), ("2026-09-30", "SYNTH-B", 20),
             ("2026-09-29", "SYNTH-A", 9), ("2026-09-29", "SYNTH-B", 19)],
        )
        conn.executemany("insert into choice_stock_universe values (?, ?)",
                         [("2026-09-30", "SYNTH-A"), ("2026-09-30", "SYNTH-B")])
    source_path = ROOT / "backend/app/tasks/stock_factor_refresh.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    sql_calls = []
    real_connect = duckdb.connect

    class TracedConnection:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, sql, *args, **kwargs):
            sql_calls.append(" ".join(sql.lower().split()))
            return self.conn.execute(sql, *args, **kwargs)

        def executemany(self, sql, *args, **kwargs):
            sql_calls.append(" ".join(sql.lower().split()))
            return self.conn.executemany(sql, *args, **kwargs)

        def close(self):
            return self.conn.close()

    def traced_connect(database, *, read_only=False):
        assert Path(database).resolve() == path.resolve()
        return TracedConnection(real_connect(database, read_only=read_only))

    # Include every function, so newly factored production validation also runs.
    functions = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef)], type_ignores=[])
    namespace = {
        "duckdb": SimpleNamespace(connect=traced_connect, Error=duckdb.Error),
        "Path": Path, "date": date, "datetime": datetime,
        "UTC": UTC, "uuid": uuid, "nullcontext": nullcontext,
        "acquire_lock": acquire_lock, "resolve_duckdb_writer_lock": resolve_duckdb_writer_lock,
        "logger": logging.getLogger(__name__),
        "get_settings": lambda: SimpleNamespace(duckdb_path=str(path)),
        "ensure_choice_stock_schema": _schema,
        "_normalize_date": lambda value: date.fromisoformat(value).isoformat(),
        "_text": lambda value: str(value or "").strip(),
        "CHOICE_VERIFIED_PERCENT_INDICATORS": frozenset(),
    }
    exec(compile(functions, str(source_path), "exec"), namespace)
    # Keep all factor declarations from source; no reimplementation of the writer.
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [target.id for target in targets if isinstance(target, ast.Name)]
            if set(names) & {"SOURCE_VERSION", "RULE_VERSION", "FACTOR_FIELDS", "_INDICATOR_FIELD_MAP"}:
                exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), "exec"), namespace)
    namespace.update(CHOICE_CSS_FACTOR_INDICATORS="PETTM", CHOICE_CSS_FACTOR_MAX_FAILED_CHUNKS=0)
    namespace["_sql_calls"] = sql_calls
    return path, namespace


def _snapshot(path):
    with duckdb.connect(str(path), read_only=True) as conn:
        rows = conn.execute(
            "select * from choice_stock_factor_snapshot order by as_of_date, stock_code").fetchall()
        result = {(row[0], row[1]): row for row in rows}
        assert len(result) == len(rows), "Refresh must not create duplicate snapshot keys"
        return result


def _run(refresh, rows, *, codes=("SYNTH-A",), failures=0, dry_run=False):
    path, namespace = refresh
    namespace["_fetch_choice_factor_rows"] = lambda *args, **kwargs: (rows, failures, 2)
    return namespace["refresh_stock_factors"](
        duckdb_path=str(path), as_of_date="2026-09-30",
        stock_codes=list(codes) if codes is not None else None,
        choice_client=object(), dry_run=dry_run,
    )


def _row(code="SYNTH-A", *, day="2026-09-30", pe=30):
    return {"as_of_date": day, "stock_code": code, "pe": pe, "pb": None,
            "ps": None, "roe": None, "gross_margin": None, "dividend_yield": None}


def _assert_no_row_mutation(refresh):
    assert not any(sql.startswith(("delete ", "insert ", "update "))
                   for sql in refresh[1]["_sql_calls"])


def test_scoped_refresh_preserves_other_stocks_dates_and_lineage(refresh):
    path, _ = refresh
    before = _snapshot(path)
    result = _run(refresh, [_row()])
    after = _snapshot(path)
    assert result["row_count"] == 1
    assert result["stock_code_count"] == 1
    assert set(after) == set(before)
    for key in before.keys() - {("2026-09-30", "SYNTH-A")}:
        assert after[key] == before[key]
    assert after[("2026-09-30", "SYNTH-A")][2] == 30
    assert after[("2026-09-30", "SYNTH-A")][-1] == result["run_id"]
    # Partial-null factors are an existing business contract, not a missing row.
    assert after[("2026-09-30", "SYNTH-A")][3] is None


@pytest.mark.parametrize("codes", [("SYNTH-A", "SYNTH-B"), None])
def test_missing_requested_row_aborts_without_mutating_any_snapshot(refresh, codes):
    before = _snapshot(refresh[0])
    with pytest.raises(RuntimeError, match="incomplete|scope"):
        _run(refresh, [_row()], codes=codes)
    _assert_no_row_mutation(refresh)
    assert _snapshot(refresh[0]) == before


@pytest.mark.parametrize("rows", [
    [_row(), _row()], [_row("SYNTH-B")], [_row(day="2026-09-29")],
])
def test_duplicate_or_out_of_scope_rows_reject_without_mutation(refresh, rows):
    before = _snapshot(refresh[0])
    with pytest.raises(RuntimeError, match="scope|duplicate|incomplete"):
        _run(refresh, rows)
    _assert_no_row_mutation(refresh)
    assert _snapshot(refresh[0]) == before


def test_failed_chunks_remain_fail_closed_even_when_partial_chunks_are_allowed(refresh):
    refresh[1]["CHOICE_CSS_FACTOR_MAX_FAILED_CHUNKS"] = 1
    before = _snapshot(refresh[0])
    with pytest.raises(RuntimeError, match="incomplete|scope"):
        _run(refresh, [_row()], codes=("SYNTH-A", "SYNTH-B"), failures=1)
    _assert_no_row_mutation(refresh)
    assert _snapshot(refresh[0]) == before


def test_existing_failed_chunk_guard_and_empty_result_guard(refresh):
    before = _snapshot(refresh[0])
    with pytest.raises(RuntimeError, match="chunks failed"):
        _run(refresh, [_row()], failures=1)
    with pytest.raises(RuntimeError, match="no factor rows"):
        _run(refresh, [])
    _assert_no_row_mutation(refresh)
    assert _snapshot(refresh[0]) == before


def test_full_universe_refresh_and_repeated_refresh_keep_previous_dates(refresh):
    before = _snapshot(refresh[0])
    for _ in range(2):
        _run(refresh, [_row(), _row("SYNTH-B", pe=40)], codes=None)
    after = _snapshot(refresh[0])
    assert set(after) == set(before)
    assert after[("2026-09-30", "SYNTH-B")][2] == 40
    for key in before:
        if key[0] == "2026-09-29":
            assert after[key] == before[key]


def test_insert_failure_rolls_back_exact_replacement(refresh):
    before = _snapshot(refresh[0])
    with pytest.raises(duckdb.Error):
        _run(refresh, [_row(pe="not-a-number")])
    assert _snapshot(refresh[0]) == before


def test_dry_run_does_not_fetch_or_write(refresh):
    before = _snapshot(refresh[0])
    result = _run(refresh, [], dry_run=True)
    assert result["status"] == "dry_run"
    assert _snapshot(refresh[0]) == before


def test_writer_replaces_each_exact_date_stock_key_and_empty_batch_is_noop(refresh):
    path, namespace = refresh
    before = _snapshot(path)
    with duckdb.connect(str(path)) as conn:
        conn.execute("begin transaction")
        namespace["_upsert_factor_snapshot_rows"](
            conn, rows=[_row(), _row("SYNTH-B", day="2026-09-29", pe=22)],
            run_id="synthetic-writer", source_version="synthetic", vendor_version="synthetic",
        )
        namespace["_upsert_factor_snapshot_rows"](
            conn, rows=[], run_id="empty", source_version="empty", vendor_version="empty",
        )
        conn.execute("commit")
    after = _snapshot(path)
    assert set(after) == set(before)
    assert after[("2026-09-30", "SYNTH-B")] == before[("2026-09-30", "SYNTH-B")]
    assert after[("2026-09-29", "SYNTH-A")] == before[("2026-09-29", "SYNTH-A")]
    assert after[("2026-09-29", "SYNTH-B")][2] == 22
