from __future__ import annotations

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.services.external_data_query_service import fetch_series_data_page
from tests.helpers import load_module

SERIES_ID = "research.calendar.supply_auction"


def _register_catalog_entry(conn: duckdb.DuckDBPyConnection) -> ExternalDataCatalogEntry:
    entry = ExternalDataCatalogEntry(
        series_id=SERIES_ID,
        series_name="Research supply and auction calendar",
        vendor_name="choice",
        source_family="research_supply_auction",
        domain="other",
        frequency="event",
        unit="亿元",
        refresh_tier="research_calendar_v1",
        fetch_mode="view_only",
        raw_zone_path=None,
        standardized_table="std_external_supply_auction_calendar",
        view_name="vw_external_supply_auction_calendar",
        access_path=(
            "select * from vw_external_supply_auction_calendar "
            "where series_id = 'research.calendar.supply_auction'"
        ),
        catalog_version="research.calendar.v1",
        created_at="2026-04-23T00:00:00+00:00",
    )
    ExternalDataCatalogRepository(conn=conn).register(entry)
    return entry


def _seed_supply_auction_surface(tmp_path) -> str:
    from backend.app.repositories.research_calendar_repo import (
        ensure_supply_auction_calendar_schema,
    )

    db_path = tmp_path / "supply-auction.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_supply_auction_calendar_schema(conn)
        _register_catalog_entry(conn)
        conn.execute(
            """
            insert into std_external_supply_auction_calendar (
              series_id, event_id, vendor_name, source_family, domain, event_date,
              event_kind, title, issuer, market, instrument_type, term_label,
              amount_numeric, amount_unit, currency, status, severity,
              headline_text, headline_url, headline_published_at,
              source_version, vendor_version, rule_version, ingest_batch_id, created_at
            ) values
            (
              'research.calendar.supply_auction', 'evt-20260424-cdb-3y', 'choice',
              'research_supply_auction', 'other', '2026-04-24', 'auction',
              '国开债 3Y 招标', '国开行', 'interbank', 'policy_bank_bond', '3Y',
              1200.0, '亿元', 'CNY', 'scheduled', 'high',
              '国开债招标窗口开启', 'https://example.com/cdb-3y', '2026-04-23T09:00:00Z',
              'sv_supply_auction_1', 'vv_choice_calendar_1', 'rv_supply_auction_v1',
              'ib_supply_auction_1', timestamp '2026-04-23 09:00:00'
            ),
            (
              'research.calendar.supply_auction', 'evt-20260426-cgb-5y', 'choice',
              'research_supply_auction', 'other', '2026-04-26', 'supply',
              '国债 5Y 发行', '财政部', 'interbank', 'treasury_bond', '5Y',
              980.0, '亿元', 'CNY', 'scheduled', 'medium',
              null, null, null,
              'sv_supply_auction_1', 'vv_choice_calendar_1', 'rv_supply_auction_v1',
              'ib_supply_auction_1', timestamp '2026-04-23 09:00:00'
            ),
            (
              'research.calendar.other_series', 'evt-other-series', 'choice',
              'research_supply_auction', 'other', '2026-04-28', 'auction',
              '其他序列行', '测试发行人', 'interbank', 'other', '1Y',
              10.0, '亿元', 'CNY', 'scheduled', 'low',
              null, null, null,
              'sv_supply_auction_1', 'vv_choice_calendar_1', 'rv_supply_auction_v1',
              'ib_supply_auction_1', timestamp '2026-04-23 09:00:00'
            )
            """,
        )
    finally:
        conn.close()
    return str(db_path)


def test_supply_auction_calendar_route_returns_analytical_envelope(tmp_path, monkeypatch) -> None:
    duckdb_path = _seed_supply_auction_surface(tmp_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", duckdb_path)
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/ui/calendar/supply-auctions",
        params={
            "start_date": "2026-04-23",
            "end_date": "2026-04-30",
            "limit": 10,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["result_kind"] == "calendar.supply_auctions"
    assert payload["result_meta"]["tables_used"] == ["vw_external_supply_auction_calendar"]
    assert payload["result"]["series_id"] == SERIES_ID
    assert payload["result"]["total_rows"] == 2
    assert payload["result"]["limit"] == 10
    assert payload["result"]["offset"] == 0
    assert [row["event_id"] for row in payload["result"]["events"]] == [
        "evt-20260424-cdb-3y",
        "evt-20260426-cgb-5y",
    ]
    assert payload["result"]["events"][0]["headline_text"] == "国开债招标窗口开启"
    get_settings.cache_clear()


def test_external_data_query_service_allows_supply_auction_relations(tmp_path) -> None:
    duckdb_path = _seed_supply_auction_surface(tmp_path)
    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
        entry = ExternalDataCatalogRepository(conn=conn).get_by_series_id(SERIES_ID)
        assert entry is not None
        page = fetch_series_data_page(conn, entry, limit=20, offset=0)
    finally:
        conn.close()

    assert page.table_name == "vw_external_supply_auction_calendar"
    assert len(page.rows) == 2
    assert {row["event_id"] for row in page.rows} == {
        "evt-20260424-cdb-3y",
        "evt-20260426-cgb-5y",
    }
