"""MS-017: selected home macro reads over tiny, synthetic DuckDB files.

These tests cover repository contracts, not real business reconciliation or
provider ingestion. Every row, date and identifier is a synthetic fixture.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    active_read_scope,
    duckdb_read_scope,
)
from backend.app.repositories.home_macro_release_context_repo import (
    HomeMacroReleaseContextRepository,
)
pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]

MACRO_TABLES = ("std_external_macro_daily", "fact_choice_macro_daily")
READERS = MACRO_TABLES
CUTOFF = date(2040, 6, 2)
SYNTHETIC_SERIES = "synthetic-ms017-series"


def _seed(path: Path, generation: int, *, schema: bool = True, empty: bool = False,
          values_generation: int | None = None) -> None:
    """Keep all storage real and local, with explicit rows instead of providers."""
    value_base = (generation if values_generation is None else values_generation) * 100
    with duckdb.connect(str(path)) as conn:
        if not schema:
            return
        conn.execute("""CREATE TABLE std_external_macro_daily (
            series_id VARCHAR, trade_date DATE, value_numeric DOUBLE,
            frequency VARCHAR, unit VARCHAR, source_version VARCHAR,
            vendor_version VARCHAR, rule_version VARCHAR, vendor_name VARCHAR,
            ingest_batch_id VARCHAR, created_at TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE fact_choice_macro_daily (
            series_id VARCHAR, trade_date DATE, value_numeric DOUBLE,
            frequency VARCHAR, unit VARCHAR, source_version VARCHAR,
            vendor_version VARCHAR, rule_version VARCHAR, quality_flag VARCHAR,
            run_id VARCHAR
        )""")
        if empty:
            return
        for series, day, value, revision in (
            (SYNTHETIC_SERIES, "2040-06-01", value_base + 1, 2),
            (SYNTHETIC_SERIES, "2040-06-02", value_base + 2, 2),
            (SYNTHETIC_SERIES, "2040-06-02", -999, 1),
            (SYNTHETIC_SERIES, "2040-06-03", value_base + 3, 2),
            ("synthetic-other-series", "2040-06-02", -888, 2),
        ):
            common = [series, day, value, "monthly", "index",
                      f"sv_synthetic_G{generation}", f"vv_synthetic_G{generation}",
                      "rv_synthetic_ms017"]
            conn.execute("INSERT INTO std_external_macro_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         [*common, f"Synthetic publisher G{generation}",
                          f"synthetic-ingest-G{generation}-r{revision}",
                          f"2040-06-04T00:00:0{revision}"])
            conn.execute("INSERT INTO fact_choice_macro_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         [*common, "ok", f"synthetic-G{generation}-20400604T00000{revision}Z"])


@pytest.fixture
def chain(tmp_path):
    active, g1, g2 = (tmp_path / name for name in ("active.duckdb", "G1.duckdb", "G2.duckdb"))
    for path, generation in ((active, 9), (g1, 1), (g2, 2)):
        _seed(path, generation)
    return SimpleNamespace(active=active, g1=g1, g2=g2,
                           selection1=DuckDBReadSelection(active, g1, "synthetic-G1"),
                           selection2=DuckDBReadSelection(active, g2, "synthetic-G2"))


def _read(path, reader, *, limit=2, cutoff=CUTOFF):
    return HomeMacroReleaseContextRepository(path).read_recent_observations(
        table=reader, series_id=SYNTHETIC_SERIES, cutoff_date=cutoff, limit=limit)


def _assert_generation(result, reader, generation, *, values_generation=None):
    value_base = (generation if values_generation is None else values_generation) * 100
    assert result.error is None
    assert [row.observation_date for row in result.observations] == [CUTOFF, date(2040, 6, 1)]
    assert [row.value for row in result.observations] == [value_base + 2, value_base + 1]
    for row in result.observations:
        assert row.source_version == f"sv_synthetic_G{generation}"
        assert row.vendor_version == f"vv_synthetic_G{generation}"
        assert row.rule_version == "rv_synthetic_ms017"
        assert row.cadence == "monthly"
        assert row.unit == "index"
        if reader == MACRO_TABLES[0]:
            assert row.vendor_name == f"Synthetic publisher G{generation}"
            assert row.ingest_batch_id == f"synthetic-ingest-G{generation}-r2"
        else:
            assert row.quality_flag == "ok"
            assert row.run_id == f"synthetic-G{generation}-20400604T000002Z"


def _assert_empty(result, reader, *, schema):
    assert result.observations == []
    assert result.error == (None if schema else "relation_missing")

@pytest.mark.parametrize("reader", READERS)
def test_generation_switches_and_restores_rows_and_lineage(chain, reader):
    _assert_generation(_read(chain.active, reader), reader, 9)
    with duckdb_read_scope(chain.selection1, required_online=True):
        _assert_generation(_read(chain.active, reader), reader, 1)
        with duckdb_read_scope(chain.selection2, required_online=True):
            _assert_generation(_read(chain.active, reader), reader, 2)
        _assert_generation(_read(chain.active, reader), reader, 1)
        with active_read_scope():
            _assert_generation(_read(chain.active, reader), reader, 9)
        _assert_generation(_read(chain.active, reader), reader, 1)
    _assert_generation(_read(chain.active, reader), reader, 9)


@pytest.mark.parametrize("reader", READERS)
def test_selected_snapshot_survives_absent_active_file(chain, reader):
    chain.active.unlink()
    with duckdb_read_scope(chain.selection1, required_online=True):
        _assert_generation(_read(chain.active, reader), reader, 1)
    assert not chain.active.exists()


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("active_present", [True, False])
@pytest.mark.parametrize("missing", ["selection", "deleted_snapshot"])
def test_missing_required_selection_or_deleted_snapshot_fails_closed(chain, reader, active_present, missing):
    if not active_present:
        chain.active.unlink()
    selection = chain.selection1 if missing == "deleted_snapshot" else None
    with duckdb_read_scope(selection, required_online=True, active_path=chain.active):
        if missing == "deleted_snapshot":
            chain.g1.unlink()
        with pytest.raises(DuckDBReadSelectionError):
            _read(chain.active, reader)
    assert chain.active.exists() is active_present


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("schema", [True, False])
@pytest.mark.parametrize("selected", [True, False])
def test_empty_or_missing_relation_remains_honest(tmp_path, reader, schema, selected):
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "empty.duckdb"
    _seed(active, 9, schema=schema if not selected else True, empty=not selected)
    _seed(snapshot, 1, schema=schema, empty=True)
    selection = DuckDBReadSelection(active, snapshot, "synthetic-empty") if selected else None
    with duckdb_read_scope(selection):
        _assert_empty(_read(active, reader), reader, schema=schema)


@pytest.mark.parametrize("reader", READERS)
def test_unbound_missing_file_contract_is_unchanged(tmp_path, reader):
    missing = tmp_path / "missing.duckdb"
    with pytest.raises(duckdb.IOException):
        _read(missing, reader)
    assert not missing.exists()


@pytest.mark.parametrize("reader", MACRO_TABLES)
def test_equal_values_still_select_generation_specific_lineage(tmp_path, reader):
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "G1.duckdb"
    _seed(active, 2, values_generation=1)
    _seed(snapshot, 1, values_generation=1)
    _assert_generation(_read(active, reader), reader, 2, values_generation=1)
    with duckdb_read_scope(DuckDBReadSelection(active, snapshot, "synthetic-G1"), required_online=True):
        _assert_generation(_read(active, reader), reader, 1, values_generation=1)


@pytest.mark.parametrize("reader", READERS)
def test_selected_cutoff_and_limits_keep_canonical_rows(chain, reader):
    with duckdb_read_scope(chain.selection1, required_online=True):
        latest = _read(chain.active, reader, limit=1)
        earlier = _read(chain.active, reader, limit=1, cutoff=date(2040, 6, 1))
    assert [row.value for row in latest.observations] == [102]
    assert [row.value for row in earlier.observations] == [101]

@pytest.mark.parametrize("reader", MACRO_TABLES)
@pytest.mark.parametrize("value", [None, 0.0])
def test_selected_macro_preserves_null_and_zero(chain, reader, value):
    with duckdb.connect(str(chain.g1)) as conn:
        conn.execute(f"UPDATE {reader} SET value_numeric = ? WHERE trade_date = ?", [value, CUTOFF])
    with duckdb_read_scope(chain.selection1, required_online=True):
        result = _read(chain.active, reader)
    assert [row.value for row in result.observations] == [value, 101.0]
    assert result.observations[0].source_version == "sv_synthetic_G1"
    assert result.error is None


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("schema", [True, False])
def test_repository_owned_connections_are_read_only_and_closed(tmp_path, reader, schema, monkeypatch):
    path = tmp_path / "synthetic.duckdb"
    _seed(path, 1, schema=schema)
    original_connect = duckdb.connect
    opened = []

    def capture_connect(database, *args, **kwargs):
        assert kwargs.get("read_only") is True
        conn = original_connect(database, *args, **kwargs)
        opened.append(conn)
        with pytest.raises(duckdb.Error):
            conn.execute("CREATE TABLE forbidden_write(value INTEGER)")
        return conn

    monkeypatch.setattr(duckdb, "connect", capture_connect)
    _read(path, reader)
    assert len(opened) == 1
    with pytest.raises(duckdb.ConnectionException):
        opened[0].execute("SELECT 1")


@pytest.mark.parametrize("reader", READERS)
def test_repository_query_errors_propagate_and_close_owned_connection(tmp_path, reader, monkeypatch):
    path = tmp_path / "synthetic-invalid-schema.duckdb"
    table = reader
    with duckdb.connect(str(path)) as conn:
        conn.execute(f"CREATE TABLE {table} (synthetic_invalid_column INTEGER)")
    original_connect = duckdb.connect
    opened = []

    def capture_connect(database, *args, **kwargs):
        conn = original_connect(database, *args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(duckdb, "connect", capture_connect)
    with pytest.raises(duckdb.BinderException):
        _read(path, reader)
    assert len(opened) == 1
    with pytest.raises(duckdb.ConnectionException):
        opened[0].execute("SELECT 1")


@pytest.mark.parametrize("table,limit", [("synthetic-unsupported", 2), (MACRO_TABLES[0], 0), (MACRO_TABLES[1], -1)])
def test_macro_argument_validation_precedes_connection(tmp_path, table, limit, monkeypatch):
    def unexpected_connect(*args, **kwargs):
        pytest.fail("Invalid arguments must fail before opening a database")

    monkeypatch.setattr(duckdb, "connect", unexpected_connect)
    with pytest.raises(ValueError):
        HomeMacroReleaseContextRepository(tmp_path / "absent.duckdb").read_recent_observations(
            table=table, series_id=SYNTHETIC_SERIES, cutoff_date=CUTOFF, limit=limit)
