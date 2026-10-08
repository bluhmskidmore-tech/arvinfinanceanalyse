"""BD-024 calendar addendum: synthetic storage and real route/scope enforcement.

HTTP tests mount the existing router and publication middleware. Only settings
and inbound identity are test-supplied; read authorization uses isolated SQLite
grants. This is not production authentication, real auction data, or UI QA.
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import research_calendar as routes
from backend.app.main import SystemReadPublicationMiddleware
from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection, DuckDBReadSelectionError, active_read_scope, duckdb_read_scope,
)
from backend.app.repositories.financial_result_publication_repo import canonical_json_bytes, sha256_bytes, sha256_file
from backend.app.repositories.research_calendar_repo import (
    ResearchCalendarRepository, SUPPLY_AUCTION_SERIES_ID, ensure_supply_auction_calendar_schema,
)
from backend.app.repositories.system_read_publication_repo import SYSTEM_READ_GENERATION_HEADER, system_read_publication_root
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services.research_calendar_service import supply_auction_calendar_envelope
from tests.test_system_online_read_boundary import _bundle, _seal_generation, _settings, _write_pointer


def _seed(path, number, *, empty=False, schema=True):
    with duckdb.connect(str(path)) as conn:
        if not schema:
            return
        ensure_supply_auction_calendar_schema(conn)
        if empty:
            return
        for index, day in enumerate(("2026-09-29", "2026-09-30"), 1):
            conn.execute("""INSERT INTO std_external_supply_auction_calendar(
                series_id, event_id, vendor_name, source_family, domain, event_date,
                event_kind, title, amount_numeric, amount_unit, currency, status,
                severity, source_version, vendor_version, rule_version, ingest_batch_id, created_at)
                VALUES (?, ?, 'synthetic', 'synthetic', 'synthetic', ?, 'auction', ?, ?,
                        'yuan', 'CNY', 'scheduled', 'low', ?, 'vv_synthetic', 'rv_supply_auction_v1', ?, ?)
            """, [SUPPLY_AUCTION_SERIES_ID, f"synthetic-{index}", day,
                  f"Synthetic G{number} event {index}", number * 1000 + index,
                  f"sv_calendar_G{number}", f"synthetic-G{number}", "2026-09-01T00:00:00"])


@pytest.fixture
def chain(tmp_path):
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "G1.duckdb"
    _seed(active, 2)
    _seed(snapshot, 1)
    return SimpleNamespace(active=active, snapshot=snapshot,
                           selection=DuckDBReadSelection(active, snapshot, "G1"))


def _page(path, **kwargs):
    return ResearchCalendarRepository(path=str(path)).fetch_supply_auction_page(
        start_date=kwargs.get("start_date"), end_date=kwargs.get("end_date"),
        limit=kwargs.get("limit", 50), offset=kwargs.get("offset", 0))


def _assert_envelope(envelope, number, *, indexes=(1, 2), total=2):
    result, meta = envelope["result"], envelope["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["source_version"] == f"sv_calendar_G{number}"
    assert result["total_rows"] == total
    assert [event["title"] for event in result["events"]] == [f"Synthetic G{number} event {i}" for i in indexes]
    assert [event["amount"] for event in result["events"]] == [number * 1000 + i for i in indexes]


def test_calendar_repository_and_service_honor_pin_and_explicit_active(chain):
    _assert_envelope(supply_auction_calendar_envelope(str(chain.active)), 2)
    with duckdb_read_scope(chain.selection, required_online=True):
        page = _page(chain.active)
        assert page.source_version == "sv_calendar_G1"
        assert page.events[0].amount == 1001
        _assert_envelope(supply_auction_calendar_envelope(str(chain.active)), 1)
        with active_read_scope():
            _assert_envelope(supply_auction_calendar_envelope(str(chain.active)), 2)
        _assert_envelope(supply_auction_calendar_envelope(str(chain.active)), 1)


def test_calendar_valid_snapshot_does_not_require_active_file(chain):
    chain.active.unlink()
    with duckdb_read_scope(chain.selection, required_online=True):
        _assert_envelope(supply_auction_calendar_envelope(str(chain.active)), 1)
    assert not chain.active.exists()


def test_calendar_revalidates_pin_after_service_existence_check(chain, monkeypatch):
    original = ResearchCalendarRepository.fetch_supply_auction_page

    def lose_snapshot_before_connect(repo, **kwargs):
        chain.snapshot.unlink()
        return original(repo, **kwargs)

    monkeypatch.setattr(ResearchCalendarRepository, "fetch_supply_auction_page", lose_snapshot_before_connect)
    with duckdb_read_scope(chain.selection, required_online=True):
        with pytest.raises(DuckDBReadSelectionError):
            supply_auction_calendar_envelope(str(chain.active))


@pytest.mark.parametrize("reader", [_page, supply_auction_calendar_envelope])
@pytest.mark.parametrize("missing", ["selection", "deleted_snapshot"])
def test_calendar_required_or_deleted_pin_never_returns_live_or_empty(chain, reader, missing):
    selection = chain.selection if missing == "deleted_snapshot" else None
    with duckdb_read_scope(selection, required_online=True, active_path=chain.active):
        if missing == "deleted_snapshot":
            chain.snapshot.unlink()
        with pytest.raises(DuckDBReadSelectionError):
            reader(str(chain.active))


def test_calendar_required_pin_is_checked_even_when_active_is_absent(tmp_path):
    missing = tmp_path / "missing.duckdb"
    with duckdb_read_scope(None, required_online=True, active_path=missing):
        with pytest.raises(DuckDBReadSelectionError):
            supply_auction_calendar_envelope(str(missing))
    assert not missing.exists()


@pytest.mark.parametrize("schema", [False, True])
def test_calendar_valid_empty_snapshot_stays_empty(tmp_path, schema):
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "empty.duckdb"
    _seed(active, 2)
    _seed(snapshot, 1, empty=True, schema=schema)
    with duckdb_read_scope(DuckDBReadSelection(active, snapshot, "empty"), required_online=True):
        envelope = supply_auction_calendar_envelope(str(active))
        assert envelope["result"]["events"] == []
        assert envelope["result"]["total_rows"] == 0
        assert envelope["result_meta"]["source_version"] == "sv_supply_auction_empty"
        assert envelope["result_meta"]["quality_flag"] == "warning"


def test_calendar_filters_and_paging_keep_frozen_source(chain):
    with duckdb_read_scope(chain.selection, required_online=True):
        result = supply_auction_calendar_envelope(str(chain.active), limit=1, offset=1)
        _assert_envelope(result, 1, indexes=(2,), total=2)
        filtered = supply_auction_calendar_envelope(str(chain.active), start_date=date(2026, 9, 30), end_date=date(2026, 9, 30))
        _assert_envelope(filtered, 1, indexes=(2,), total=1)
        assert filtered["result_meta"]["filters_applied"]["start_date"] == "2026-09-30"


def test_calendar_unbound_missing_file_contract_unchanged(tmp_path):
    path = tmp_path / "absent.duckdb"
    envelope = supply_auction_calendar_envelope(str(path))
    assert envelope["result"]["events"] == []
    assert envelope["result_meta"]["formal_use_allowed"] is False
    with pytest.raises(duckdb.IOException):
        _page(path)
    assert not path.exists()


def test_calendar_owned_connection_is_read_only_and_closed(chain):
    with duckdb_read_scope(chain.selection, required_online=True):
        with ResearchCalendarRepository(path=str(chain.active))._connection() as conn:
            with pytest.raises(duckdb.Error):
                conn.execute("CREATE TABLE forbidden_write(value INTEGER)")
        with pytest.raises(duckdb.ConnectionException):
            conn.execute("SELECT 1")


def test_calendar_injected_connection_remains_caller_owned(chain):
    with duckdb.connect(str(chain.active), read_only=True) as conn:
        repo = ResearchCalendarRepository(conn=conn)
        with duckdb_read_scope(chain.selection, required_online=True):
            page = repo.fetch_supply_auction_page(start_date=None, end_date=None, limit=50, offset=0)
            assert page.source_version == "sv_calendar_G2"
        assert conn.execute("SELECT 1").fetchone() == (1,)


def _published_calendar(root, number, settings, pnl_digest):
    generation = f"system-read-2026-09-15-{str(number) * 20}"
    _seal_generation(root, generation, f"synthetic-G{number}", system_read_bundle=_bundle(settings, "pnl-synthetic", pnl_digest))
    database = root / "generations" / f"{generation}.duckdb"
    _seed(database, number)
    manifest_path = root / "generations" / f"{generation}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest["database"].update(size_bytes=database.stat().st_size, sha256=sha256_file(database))
    content = canonical_json_bytes(manifest)
    manifest_path.write_bytes(content)
    return generation, sha256_bytes(content)


def test_real_calendar_route_header_values_source_and_read_scope(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _seed(Path(settings.duckdb_path), 2)
    settings.governance_sql_dsn = f"sqlite:///{tmp_path / 'synthetic-scopes.sqlite'}"
    settings.postgres_dsn = settings.governance_sql_dsn
    scopes = UserScopeRepository(settings.governance_sql_dsn)
    try:
        scopes.grant_scope(user_id="synthetic-reader", role="viewer", resource="research_calendar", action="read",
                           operator="synthetic-test", reason="Isolated test-only read permission")
    finally:
        scopes.engine.dispose()
    pnl_root = Path(settings.financial_publication_root)
    pnl_digest = _seal_generation(pnl_root, "pnl-synthetic", "SYNTHETIC")
    _write_pointer(pnl_root, "pnl-synthetic", [("pnl-synthetic", pnl_digest)])
    root = system_read_publication_root(settings)
    g1 = _published_calendar(root, 1, settings, pnl_digest)
    g2 = _published_calendar(root, 2, settings, pnl_digest)
    _write_pointer(root, g2[0], [g2, g1])
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(user_id="synthetic-reader", role="viewer", identity_source="synthetic-test")
    with TestClient(app) as client:
        for number, generation in ((1, g1[0]), (2, g2[0]), (1, g1[0])):
            response = client.get("/ui/calendar/supply-auctions", headers={SYSTEM_READ_GENERATION_HEADER: generation})
            assert response.status_code == 200
            assert response.headers[SYSTEM_READ_GENERATION_HEADER] == generation
            _assert_envelope(response.json(), number)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(user_id="synthetic-no-grant", role="viewer", identity_source="synthetic-test")
        denied = client.get("/ui/calendar/supply-auctions", headers={SYSTEM_READ_GENERATION_HEADER: g1[0]})
        assert denied.status_code == 403
        assert "not allowed" in denied.json()["detail"]
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(user_id="synthetic-reader", role="viewer", identity_source="synthetic-test")
        (root / "generations" / f"{g1[0]}.duckdb").unlink()
        unavailable = client.get("/ui/calendar/supply-auctions", headers={SYSTEM_READ_GENERATION_HEADER: g1[0]})
        assert unavailable.status_code == 503
        assert SYSTEM_READ_GENERATION_HEADER not in unavailable.headers
