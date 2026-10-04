from __future__ import annotations

import json
from decimal import Decimal

import duckdb
import pytest

from backend.app.repositories import pnl_repo
from backend.app.repositories.duckdb_read_context import DuckDBReadSelection, duckdb_read_scope


def _seed_precompute(path, *, label="current"):
    with duckdb.connect(str(path), read_only=False) as conn:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
                report_date varchar, instrument_code varchar, rule_version varchar,
                interest_income_514 decimal(18, 2), fair_value_change_516 decimal(18, 2),
                capital_gain_517 decimal(18, 2), manual_adjustment decimal(18, 2),
                total_pnl decimal(18, 2)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
                ('2026-08-31', 'synthetic-a', 'rule-test', 10, 0, 0, 0, 10),
                ('2026-08-31', 'synthetic-b', 'rule-test', 20, 0, 0, 0, 20)
            """
        )
        conn.execute(
            """
            create table fact_pnl_by_business_precompute (
                year integer, as_of_date varchar, result_kind varchar,
                dimension varchar, business_key varchar, payload_json varchar,
                source_version varchar, rule_version varchar, generated_at timestamp
            )
            """
        )
    repo = pnl_repo.PnlRepository(str(path))
    source_version = repo.pnl_by_business_precompute_source_version(
        year=2026, as_of_date="2026-08-31", effective_ftp_rate_pct=Decimal("1.6")
    )
    payload = {"label": label, "total_pnl": "30.00"}
    with duckdb.connect(str(path), read_only=False) as conn:
        conn.execute(
            """
            insert into fact_pnl_by_business_precompute values
                (2026, '2026-08-31', 'ytd', '', '', ?, ?, ?, current_timestamp)
            """,
            [json.dumps(payload), source_version, pnl_repo.PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION],
        )
    return repo, payload


def _fetch(repo, **overrides):
    kwargs = {
        "year": 2026,
        "as_of_date": "2026-08-31",
        "result_kind": "ytd",
        "dimension": "",
        "business_key": "",
        "effective_ftp_rate_pct": Decimal("1.6"),
    }
    return repo.fetch_pnl_by_business_precompute(**(kwargs | overrides))


def _record_connections(monkeypatch):
    original_connect = duckdb.connect
    connections = []

    def connect(path, **kwargs):
        assert kwargs.get("read_only") is True
        conn = original_connect(path, **kwargs)
        connections.append((str(path), conn))
        return conn

    monkeypatch.setattr(pnl_repo.duckdb, "connect", connect)
    return connections


def _assert_closed(connections):
    for _, conn in connections:
        with pytest.raises(duckdb.ConnectionException, match="closed"):
            conn.execute("select 1")


def test_precompute_payload_and_full_fingerprint_share_one_read_only_connection(tmp_path, monkeypatch):
    repo, expected = _seed_precompute(tmp_path / "precompute.duckdb")
    original_fingerprint = repo.pnl_by_business_precompute_source_version_on_connection
    fingerprint_connections = []

    def fingerprint(conn, **kwargs):
        fingerprint_connections.append(conn)
        return original_fingerprint(conn, **kwargs)

    monkeypatch.setattr(repo, "pnl_by_business_precompute_source_version_on_connection", fingerprint)
    connections = _record_connections(monkeypatch)

    assert _fetch(repo) == expected
    _assert_closed(connections)
    assert len(connections) == 1
    assert fingerprint_connections == [connections[0][1]]


def test_next_request_revalidates_source_even_when_totals_stay_equal(tmp_path):
    path = tmp_path / "changed-source.duckdb"
    repo, expected = _seed_precompute(path)
    assert _fetch(repo) == expected

    with duckdb.connect(str(path), read_only=False) as conn:
        conn.execute(
            """
            update fact_formal_pnl_fi
            set interest_income_514 = case instrument_code when 'synthetic-a' then 11 else 19 end,
                total_pnl = case instrument_code when 'synthetic-a' then 11 else 19 end
            """
        )

    assert _fetch(repo) is None


def test_precompute_rejects_changed_ftp_and_adjustment_versions(tmp_path):
    repo, expected = _seed_precompute(tmp_path / "dependencies.duckdb")
    assert _fetch(repo) == expected
    assert _fetch(repo, effective_ftp_rate_pct=Decimal("1.61")) is None
    assert _fetch(repo, supplemental_source_version="approved-adjustment-new") is None


def test_source_fingerprint_preserves_caller_owned_connection(tmp_path):
    path = tmp_path / "borrowed-connection.duckdb"
    repo, _ = _seed_precompute(path)
    kwargs = {
        "year": 2026,
        "as_of_date": "2026-08-31",
        "effective_ftp_rate_pct": Decimal("1.6"),
    }
    expected = repo.pnl_by_business_precompute_source_version(**kwargs)

    with duckdb.connect(str(path), read_only=True) as conn:
        assert repo.pnl_by_business_precompute_source_version(**kwargs, connection=conn) == expected
        assert conn.execute("select count(*) from fact_formal_pnl_fi").fetchone() == (2,)


def test_source_fingerprint_failure_preserves_caller_owned_connection(tmp_path, monkeypatch):
    path = tmp_path / "borrowed-failed-connection.duckdb"
    repo, _ = _seed_precompute(path)

    def fingerprint(_conn, **_kwargs):
        raise duckdb.IOException("synthetic IO failure")

    monkeypatch.setattr(repo, "pnl_by_business_precompute_source_version_on_connection", fingerprint)
    with duckdb.connect(str(path), read_only=True) as conn:
        with pytest.raises(RuntimeError, match="Formal pnl storage is unavailable"):
            repo.pnl_by_business_precompute_source_version(
                year=2026,
                as_of_date="2026-08-31",
                effective_ftp_rate_pct=Decimal("1.6"),
                connection=conn,
            )
        assert conn.execute("select count(*) from fact_formal_pnl_fi").fetchone() == (2,)


def test_precompute_uses_selected_snapshot_and_closes_connection(tmp_path, monkeypatch):
    active_path = tmp_path / "active.duckdb"
    snapshot_path = tmp_path / "snapshot.duckdb"
    repo, _ = _seed_precompute(active_path, label="active")
    _, expected = _seed_precompute(snapshot_path, label="snapshot")
    connections = _record_connections(monkeypatch)
    selection = DuckDBReadSelection(active_path, snapshot_path, "test-generation")

    with duckdb_read_scope(selection, required_online=True):
        assert _fetch(repo) == expected

    assert {path for path, _ in connections} == {str(snapshot_path)}
    _assert_closed(connections)


@pytest.mark.parametrize("failure", [duckdb.IOException("synthetic IO failure"), ValueError("invalid source")])
def test_precompute_fingerprint_failure_closes_connection(tmp_path, monkeypatch, failure):
    repo, _ = _seed_precompute(tmp_path / "failed-fingerprint.duckdb")

    def fingerprint(_conn, **_kwargs):
        raise failure

    monkeypatch.setattr(repo, "pnl_by_business_precompute_source_version_on_connection", fingerprint)
    connections = _record_connections(monkeypatch)
    expected_type = RuntimeError if isinstance(failure, duckdb.Error) else ValueError
    with pytest.raises(expected_type):
        _fetch(repo)

    _assert_closed(connections)
