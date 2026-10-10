"""Disclosure reads honor selected generations using only owned synthetic files."""
from __future__ import annotations

import socket
from datetime import date
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    active_read_scope,
    duckdb_read_scope,
)
from backend.app.repositories.stock_official_disclosure_repo import (
    ensure_stock_official_disclosure_tables,
    get_stock_official_disclosure_sync_status,
    list_stock_official_disclosures,
)

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]
CUTOFF = date(2040, 6, 2)
CODE = "SYNTHETIC.SELECTED"
LANES = ("official_announcement", "financial_report")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        pytest.fail("Disclosure regression must not access a provider or network")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def _seed(path, generation, *, schema=True, empty=False):
    with duckdb.connect(str(path)) as conn:
        if not schema:
            return
        ensure_stock_official_disclosure_tables(conn)
        if empty:
            return
        for lane in LANES:
            for stock, day in ((CODE, "2040-06-01"), (CODE, "2040-06-02"),
                               (CODE, "2040-06-03"), ("SYNTHETIC.OTHER", "2040-06-02")):
                key = f"synthetic-{generation}-{stock}-{lane}-{day}"
                conn.execute("INSERT INTO fact_stock_official_disclosure VALUES ("
                             "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             [key, stock, "Synthetic issuer", lane, day, "2040-03-31",
                              f"Synthetic {generation} {lane} {day}",
                              f"https://example.invalid/{key}", "synthetic-source", "Synthetic publisher",
                              f"sv_{generation}", f"vv_{generation}", "2040-06-04T00:00:00+00:00",
                              "2040-06-04T01:00:00+00:00", f"run_{generation}", "{}"])
        conn.execute("INSERT INTO stock_official_disclosure_sync_status VALUES ("
                     "?, '2040-01-01', '2040-06-02', '2040-06-04T01:00:00+00:00', "
                     "'2040-06-04T01:00:00+00:00', 'success', 8, 8, NULL, ?, ?)",
                     [CODE, f"sync_{generation}", f"sv_sync_{generation}"])


@pytest.fixture
def chain(tmp_path):
    active, g1, g2 = (tmp_path / name for name in ("active.duckdb", "g1.duckdb", "g2.duckdb"))
    for path, generation in ((active, "active"), (g1, "g1"), (g2, "g2")):
        _seed(path, generation)
    return SimpleNamespace(active=active, g1=g1, g2=g2,
                           selection1=DuckDBReadSelection(active, g1, "synthetic-g1"),
                           selection2=DuckDBReadSelection(active, g2, "synthetic-g2"))


def _read(path, *, limit=2, cutoff=CUTOFF):
    return list_stock_official_disclosures(duckdb_path=str(path), stock_code=f" {CODE.lower()} ",
                                          as_of_date=cutoff, limit_per_type=limit)


def _assert_generation(result, generation):
    for field, lane in (("announcements", LANES[0]), ("financial_reports", LANES[1])):
        rows = result[field]
        assert [row["publish_date"] for row in rows] == ["2040-06-02", "2040-06-01"]
        assert [row["title"] for row in rows] == [
            f"Synthetic {generation} {lane} {day}" for day in ("2040-06-02", "2040-06-01")]
        assert {row["source_version"] for row in rows} == {f"sv_{generation}"}
        assert {row["vendor_version"] for row in rows} == {f"vv_{generation}"}
        assert {row["run_id"] for row in rows} == {f"run_{generation}"}
        assert result["source_versions"][lane] == f"sv_{generation}"
        assert result["sync_status"][lane]["source_version"] == f"sv_sync_{generation}"
        assert result["sync_status"][lane]["status"] == "success"
        assert result["table_available"][lane]["available"] is True
    assert result["excluded_future_rows"] == 2
    assert result["latest_publish_date"] == "2040-06-02"
    assert result["latest_ingested_at"] == "2040-06-04T01:00:00+00:00"


def test_selected_generation_restores_rows_and_lineage(chain):
    _assert_generation(_read(chain.active), "active")
    with duckdb_read_scope(chain.selection1, required_online=True):
        _assert_generation(_read(chain.active), "g1")
        with duckdb_read_scope(chain.selection2, required_online=True):
            _assert_generation(_read(chain.active), "g2")
        _assert_generation(_read(chain.active), "g1")
        with active_read_scope():
            _assert_generation(_read(chain.active), "active")
        _assert_generation(_read(chain.active), "g1")
    _assert_generation(_read(chain.active), "active")


def test_selected_snapshot_survives_absent_active_file(chain):
    chain.active.unlink()
    with duckdb_read_scope(chain.selection1, required_online=True):
        _assert_generation(_read(chain.active), "g1")
    assert not chain.active.exists()


@pytest.mark.parametrize("active_present", [True, False])
@pytest.mark.parametrize("missing", ["selection", "snapshot"])
def test_missing_required_selection_or_deleted_snapshot_never_uses_active(chain, active_present, missing, monkeypatch):
    if not active_present:
        chain.active.unlink()
    selection = chain.selection1 if missing == "snapshot" else None
    def reject_connect(*args, **kwargs):
        pytest.fail("Missing required generation must fail before opening any database")
    monkeypatch.setattr(duckdb, "connect", reject_connect)
    with duckdb_read_scope(selection, required_online=True, active_path=chain.active):
        if missing == "snapshot":
            chain.g1.unlink()
        with pytest.raises(DuckDBReadSelectionError):
            _read(chain.active)
    assert chain.active.exists() is active_present


@pytest.mark.parametrize("schema", [True, False])
def test_empty_selected_snapshot_does_not_borrow_active_rows(tmp_path, schema):
    active, selected = tmp_path / "active.duckdb", tmp_path / "selected.duckdb"
    _seed(active, "active")
    _seed(selected, "empty", schema=schema, empty=True)
    with duckdb_read_scope(DuckDBReadSelection(active, selected, "synthetic-empty"), required_online=True):
        result = _read(active)
    assert result["announcements"] == result["financial_reports"] == []
    assert result["excluded_future_rows"] == 0
    assert result["latest_publish_date"] is None
    for lane in LANES:
        assert result["source_versions"][lane] is None
        assert result["table_available"][lane]["available"] is schema
        assert result["sync_status"][lane]["status"] == "unavailable"


def test_selected_cutoff_and_lane_limits_are_preserved(chain):
    with duckdb_read_scope(chain.selection1, required_online=True):
        latest = _read(chain.active, limit=1)
        earlier = _read(chain.active, limit=1, cutoff=date(2040, 6, 1))
    for field in ("announcements", "financial_reports"):
        assert len(latest[field]) == len(earlier[field]) == 1
        assert latest[field][0]["publish_date"] == "2040-06-02"
        assert earlier[field][0]["publish_date"] == "2040-06-01"
        assert latest[field][0]["source_version"] == earlier[field][0]["source_version"] == "sv_g1"
    assert earlier["excluded_future_rows"] == 4


def test_sync_helper_respects_injected_connection_ownership(chain):
    with duckdb.connect(str(chain.active), read_only=True) as conn:
        with duckdb_read_scope(chain.selection1, required_online=True):
            sync = get_stock_official_disclosure_sync_status(conn, stock_code=CODE)
        assert sync["source_version"] == "sv_sync_active"
        assert conn.execute("SELECT 1").fetchone() == (1,)
