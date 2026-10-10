"""Analytical FX respects an already validated immutable read selection.

These are actual synthetic DuckDB reads. The read context, resolver, service,
SQL and selectors are not mocked. The independent API suite covers middleware.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.fx_rates import FxRateUnavailableError
from backend.app.repositories.duckdb_read_context import (
    DuckDBOnlineReadRequiredError,
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    duckdb_read_scope,
)
from backend.app.services import macro_vendor_service as service
from tests.test_fx_analytical_fallback_lineage import TARGET, _row, _seed

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]


def _rows(tag, value, *, gap=0):
    observed = TARGET - timedelta(days=gap)
    rows = [_row(observed, value, tag), _row(observed - timedelta(days=1), value - 0.1, f"{tag}_prior")]
    if gap:
        rows.insert(0, _row(TARGET, 0, f"{tag}_invalid"))
    return rows


def _read(path, wrapper="envelope"):
    if wrapper == "payload":
        return service.load_fx_analytical_payload(str(path)).model_dump(mode="json")
    return service.fx_analytical_envelope(str(path))["result"]


def _assert_observation(body, rows, *, gap=0):
    assert len(body["groups"]) == 1
    assert len(body["groups"][0]["series"]) == 1
    point = body["groups"][0]["series"][0]
    chosen = rows[1] if gap else rows[0]
    for key in ("value_numeric", "trade_date", "source_version", "vendor_version", "frequency", "unit"):
        assert point[key] == chosen[key], key
    assert point["latest_change"] == (None if gap else pytest.approx(0.1))
    assert point["recent_points"] == [{key: row[key] for key in point["recent_points"][0]} for row in rows]


@pytest.mark.parametrize("active_exists", [False, True])
@pytest.mark.parametrize("wrapper", ["payload", "envelope"])
@pytest.mark.parametrize("gap", [0, 2])
def test_selected_g1_g2_g1_value_date_lineage_history(tmp_path, active_exists, wrapper, gap):
    active = tmp_path / "active.duckdb"
    if active_exists:
        _seed(active, _rows("active", 9.9))
    snapshots = []
    for number, value in ((1, 7.1), (2, 8.2)):
        rows = _rows(f"G{number}", value, gap=gap)
        path = _seed(tmp_path / f"G{number}.duckdb", rows)
        snapshots.append((DuckDBReadSelection(active, path, f"G{number}"), rows))
    hashes = {str(selection.snapshot_path): hashlib.sha256(Path(selection.snapshot_path).read_bytes()).hexdigest()
              for selection, _ in snapshots}
    bodies = []
    for selection, rows in (snapshots[0], snapshots[1], snapshots[0]):
        with duckdb_read_scope(selection, required_online=True):
            body = _read(active, wrapper)
        _assert_observation(body, rows, gap=gap)
        bodies.append(body)
    assert bodies[0] == bodies[2]
    assert active.exists() is active_exists
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in hashes.items())


def test_selected_read_stays_available_after_active_disappears(tmp_path):
    active = _seed(tmp_path / "active.duckdb", _rows("active", 9.9))
    selected = _seed(tmp_path / "selected.duckdb", _rows("selected", 7.4))
    with duckdb_read_scope(DuckDBReadSelection(active, selected, "selected"), required_online=True):
        before = service.fx_analytical_envelope(str(active))
        active.unlink()  # Only this test-owned active file is removed.
        after = service.fx_analytical_envelope(str(active))
    assert after["result"] == before["result"]
    for key in ("source_version", "vendor_version", "basis", "formal_use_allowed", "quality_flag", "filters_applied"):
        assert after["result_meta"][key] == before["result_meta"][key]
    _assert_observation(after["result"], _rows("selected", 7.4))
    assert not active.exists()


@pytest.mark.parametrize("active_exists", [False, True])
def test_required_selection_missing_remains_explicit_error(tmp_path, active_exists):
    active = tmp_path / "active.duckdb"
    if active_exists:
        _seed(active, _rows("active", 9.9))
    with duckdb_read_scope(None, required_online=True, active_path=active):
        with pytest.raises(DuckDBOnlineReadRequiredError, match="immutable DuckDB read selection is required"):
            service.fx_analytical_envelope(str(active))
    assert active.exists() is active_exists


@pytest.mark.parametrize("active_exists", [False, True])
def test_deleted_selection_never_falls_back_or_returns_quiet_empty(tmp_path, active_exists):
    active = tmp_path / "active.duckdb"
    if active_exists:
        _seed(active, _rows("active", 9.9))
    selected = _seed(tmp_path / "selected.duckdb", _rows("selected", 7.4))
    selection = DuckDBReadSelection(active, selected, "selected")
    selected.unlink()  # Exercise the real resolver after a valid selection.
    with duckdb_read_scope(selection, required_online=True):
        with pytest.raises(DuckDBReadSelectionError, match="generation 'selected' is unavailable"):
            service.fx_analytical_envelope(str(active))
    assert not selected.exists()
    assert active.exists() is active_exists


def test_unbound_missing_file_preserves_empty_without_creating_database(tmp_path):
    missing = tmp_path / "missing.duckdb"
    with duckdb_read_scope(None, required_online=False):
        body = service.fx_analytical_envelope(str(missing))
    assert body["result"]["groups"] == []
    assert body["result_meta"]["source_version"] == "sv_fx_analytical_empty"
    assert not body["result_meta"]["filters_applied"].get("warnings")
    assert not missing.exists()


@pytest.mark.parametrize("state", ["no_schema", "empty", "broken_schema", "corrupt_database"])
@pytest.mark.parametrize("active_exists", [False, True])
def test_selected_empty_and_query_warning_contracts(tmp_path, state, active_exists):
    active = tmp_path / "active.duckdb"
    if active_exists:
        _seed(active, _rows("active", 9.9))
    selected = tmp_path / "selected.duckdb"
    if state == "empty":
        _seed(selected, [])
    elif state == "corrupt_database":
        selected.write_bytes(b"synthetic corrupt database")
    else:
        with duckdb.connect(str(selected)) as conn:
            if state == "no_schema":
                conn.execute("create table unrelated(value integer)")
            else:
                conn.execute("create table fact_choice_macro_daily(wrong_column integer)")
                conn.execute("create table phase1_macro_vendor_catalog(wrong_column integer)")
    with duckdb_read_scope(DuckDBReadSelection(active, selected, "selected"), required_online=True):
        if state in {"broken_schema", "corrupt_database"}:
            with pytest.raises(service.FxAnalyticalReadError, match="DuckDB query failed surface=fx_analytical"):
                service.fx_analytical_envelope(str(active))
        else:
            body = service.fx_analytical_envelope(str(active))
            assert body["result"]["groups"] == []
            assert body["result_meta"]["filters_applied"].get("warnings", []) == []
            assert body["result_meta"]["source_version"] == "sv_fx_analytical_empty"
    assert active.exists() is active_exists


def test_selected_all_invalid_usd_retains_selector_failure_with_no_active_file(tmp_path):
    active = tmp_path / "active.duckdb"
    selected = _seed(tmp_path / "selected.duckdb", [_row(TARGET, 0, "invalid")])
    with duckdb_read_scope(DuckDBReadSelection(active, selected, "selected"), required_online=True):
        with pytest.raises(FxRateUnavailableError, match="no valid input rows"):
            service.fx_analytical_envelope(str(active))
    assert not active.exists()


def test_unrelated_selection_does_not_retarget_missing_path(tmp_path):
    other_active = tmp_path / "other-active.duckdb"
    missing = tmp_path / "missing.duckdb"
    selected = _seed(tmp_path / "selected.duckdb", _rows("selected", 7.4))
    with duckdb_read_scope(DuckDBReadSelection(other_active, selected, "selected"), required_online=True):
        assert _read(missing)["groups"] == []
    assert not missing.exists()


def test_nested_scope_restores_selected_then_unbound_active(tmp_path):
    active_rows = _rows("active", 9.9)
    active = _seed(tmp_path / "active.duckdb", active_rows)
    first_rows, second_rows = _rows("first", 7.1), _rows("second", 8.2)
    first = DuckDBReadSelection(active, _seed(tmp_path / "first.duckdb", first_rows), "first")
    second = DuckDBReadSelection(active, _seed(tmp_path / "second.duckdb", second_rows), "second")
    with duckdb_read_scope(first, required_online=True):
        _assert_observation(_read(active), first_rows)
        with duckdb_read_scope(second):
            _assert_observation(_read(active), second_rows)
        _assert_observation(_read(active), first_rows)
    with duckdb_read_scope(None, required_online=False):
        _assert_observation(_read(active), active_rows)
