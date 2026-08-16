from __future__ import annotations

from pathlib import Path
from datetime import date

import duckdb

from backend.app.repositories.stock_analysis_theme_overlay_reader import (
    ThemeOverlayReadResult,
)
from backend.app.schemas.stock_analysis_theme_overlay import ThemeOverlayMember
from backend.app.services import market_data_livermore_service as service

import pytest

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]



def _seed_theme_inputs(path: Path, *, with_choice_concept: bool) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            "create table choice_stock_universe "
            "(as_of_date date, stock_code varchar, stock_name varchar, source_version varchar, vendor_version varchar)"
        )
        conn.execute(
            "create table choice_stock_sector_membership "
            "(as_of_date date, stock_code varchar, sw2021code varchar, sw2021 varchar, "
            "source_version varchar, vendor_version varchar)"
        )
        conn.execute(
            "create table choice_stock_daily_observation "
            "(trade_date date, stock_code varchar, open_value double, high_value double, low_value double, "
            "close_value double, pctchange double, turn double, amplitude double, "
            "source_version varchar, vendor_version varchar)"
        )
        conn.execute(
            "create table choice_stock_concept_membership "
            "(as_of_date date, stock_code varchar, concept_code varchar, concept_name varchar, "
            "concept_source varchar, source_version varchar, vendor_version varchar)"
        )
        conn.execute(
            "create table choice_stock_intraday_movement_event "
            "(as_of_date date, stock_code varchar, concept_code varchar, concept_name varchar, "
            "event_time varchar, event_title varchar, source_version varchar, vendor_version varchar)"
        )
        for index, stock_code in enumerate(
            ("000001.SZ", "000002.SZ", "000003.SZ"), start=1
        ):
            conn.execute(
                "insert into choice_stock_universe values (?, ?, ?, 'sv_universe', 'vv_universe')",
                ["2026-07-08", stock_code, f"Stock {index}"],
            )
            conn.execute(
                "insert into choice_stock_sector_membership values (?, ?, '801080', 'Electronic', "
                "'sv_sector', 'vv_sector')",
                ["2026-07-08", stock_code],
            )
            conn.execute(
                "insert into choice_stock_daily_observation values (?, ?, 9.5, 10.2, 9.4, 10.0, ?, 4.0, "
                "8.0, 'sv_daily', 'vv_daily')",
                ["2026-07-08", stock_code, 9.0 - index],
            )
            if with_choice_concept:
                conn.execute(
                    "insert into choice_stock_concept_membership values (?, ?, 'C-CHOICE', 'Choice theme', "
                    "'choice', 'sv_choice_concept', 'vv_choice_concept')",
                    ["2026-07-08", stock_code],
                )
        if with_choice_concept:
            movement_rows = [
                ("000001.SZ", "C-CHOICE", "Choice theme", "10:00:00", "Exact event"),
                ("000001.SZ", "C-CHOICE", "Choice theme", "10:00:00", "Exact event"),
                (
                    "000001.SZ",
                    "C-OTHER",
                    "Other theme",
                    "10:01:00",
                    "Other concept event",
                ),
                ("000001.SZ", "", "", "10:02:00", "Unassigned stock event"),
            ]
            for (
                stock_code,
                concept_code,
                concept_name,
                event_time,
                title,
            ) in movement_rows:
                conn.execute(
                    "insert into choice_stock_intraday_movement_event values (?, ?, ?, ?, ?, ?, "
                    "'sv_movement', 'vv_movement')",
                    [
                        "2026-07-08",
                        stock_code,
                        concept_code,
                        concept_name,
                        event_time,
                        title,
                    ],
                )
    finally:
        conn.close()


def _overlay_result() -> ThemeOverlayReadResult:
    return ThemeOverlayReadResult(
        status="available",
        reason="current_overlay_available",
        fingerprint="a" * 64,
        report_date="2026-07-08",
        run_id="theme-overlay:fixture",
        source_version="sv_overlay",
        vendor_version="vv_overlay",
        members=tuple(
            ThemeOverlayMember(
                stock_code=stock_code,
                stock_name=f"Overlay {index}",
                theme_key="885002.TI",
                theme_name="Overlay theme",
            )
            for index, stock_code in enumerate(
                ("000001.SZ", "000002.SZ", "000003.SZ"),
                start=1,
            )
        ),
    )


def _load(path: Path, overlay: ThemeOverlayReadResult):
    return service._load_theme_breakout_snapshots(
        duckdb_path=str(path),
        as_of_date="2026-07-08",
        sector_rank_payload={
            "items": [{"rank": 1, "sector_code": "801080", "sector_name": "Electronic"}]
        },
        theme_overlay_result=overlay,
    )


def test_current_overlay_is_used_only_when_exact_choice_concepts_are_empty(
    tmp_path: Path,
) -> None:
    path = tmp_path / "overlay.duckdb"
    _seed_theme_inputs(path, with_choice_concept=False)

    snapshots, _tables, sources, vendors, provenance = _load(path, _overlay_result())

    assert len(snapshots) == 3
    assert {snapshot.concept_code for snapshot in snapshots} == {"885002.TI"}
    assert {snapshot.concept_source_kind for snapshot in snapshots} == {
        "tushare_current_overlay"
    }
    assert "sv_overlay" in sources
    assert "vv_overlay" in vendors
    assert provenance.concept_source_kind == "tushare_current_overlay"
    assert provenance.overlay_status == "available"
    assert provenance.overlay_run_id == "theme-overlay:fixture"
    evidence = service._build_theme_breakout_evidence_state(
        stock_readiness=service.choice_stock_readiness_missing("fixture"),
        tables_used=[],
        provenance=provenance,
    )
    assert evidence["concept_membership"]["status"] == "current_overlay"
    assert evidence["concept_membership"]["point_in_time"] is False
    assert evidence["concept_membership"]["historical_use_allowed"] is False
    overlay_payload = {
        "is_proxy": False,
        "items": [{"source_kind": "tushare_current_overlay", "items": []}],
        "evidence_state": evidence,
    }
    assert "non-point-in-time" in service._theme_breakout_gap_evidence(overlay_payload)


def test_choice_concepts_take_precedence_and_movement_events_are_exactly_deduped(
    tmp_path: Path,
) -> None:
    path = tmp_path / "choice.duckdb"
    _seed_theme_inputs(path, with_choice_concept=True)

    snapshots, _tables, _sources, _vendors, provenance = _load(path, _overlay_result())

    choice_rows = [
        snapshot for snapshot in snapshots if snapshot.concept_code == "C-CHOICE"
    ]
    unassigned_rows = [
        snapshot
        for snapshot in snapshots
        if not snapshot.concept_code and not snapshot.concept_name
    ]
    assert len(choice_rows) == 3
    assert {snapshot.concept_source_kind for snapshot in choice_rows} == {
        "real_concept"
    }
    assert choice_rows[0].movement_event_count == 1
    assert choice_rows[0].latest_event_title == "Exact event"
    assert len(unassigned_rows) == 1
    assert unassigned_rows[0].stock_code == "000001.SZ"
    assert unassigned_rows[0].movement_event_count == 1
    assert unassigned_rows[0].latest_event_title == "Unassigned stock event"
    assert provenance.concept_source_kind == "real_concept"
    assert provenance.overlay_status == "choice_exact_precedence"


def test_mixed_choice_and_non_pit_concepts_use_only_explicit_choice_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "mixed-concepts.duckdb"
    _seed_theme_inputs(path, with_choice_concept=False)
    conn = duckdb.connect(str(path))
    try:
        conn.executemany(
            "insert into choice_stock_concept_membership values (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-07-08",
                    "000001.SZ",
                    "C-CHOICE",
                    "Choice theme",
                    "choice",
                    "sv_choice",
                    "vv_choice",
                ),
                (
                    "2026-07-08",
                    "000002.SZ",
                    "885999.TI",
                    "Legacy current theme",
                    "tushare_ths_current",
                    "sv_tushare_current",
                    "vv_tushare_current",
                ),
            ],
        )
    finally:
        conn.close()

    snapshots, _tables, sources, _vendors, provenance = _load(path, _overlay_result())

    assert [
        (snapshot.stock_code, snapshot.concept_code, snapshot.concept_source_kind)
        for snapshot in snapshots
        if snapshot.concept_code
    ] == [("000001.SZ", "C-CHOICE", "real_concept")]
    assert "sv_tushare_current" not in sources
    assert provenance.concept_source_kind == "real_concept"
    assert provenance.overlay_status == "choice_exact_precedence"


def test_only_non_pit_choice_table_rows_defer_to_governed_current_overlay(
    tmp_path: Path,
) -> None:
    path = tmp_path / "only-non-pit-concepts.duckdb"
    _seed_theme_inputs(path, with_choice_concept=False)
    conn = duckdb.connect(str(path))
    try:
        conn.executemany(
            "insert into choice_stock_concept_membership values (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-07-08",
                    stock_code,
                    "885999.TI",
                    "Legacy current theme",
                    "tushare_ths_current",
                    "sv_tushare_current",
                    "vv_tushare_current",
                )
                for stock_code in ("000001.SZ", "000002.SZ", "000003.SZ")
            ],
        )
    finally:
        conn.close()

    snapshots, _tables, sources, _vendors, provenance = _load(path, _overlay_result())

    assert {snapshot.concept_code for snapshot in snapshots} == {"885002.TI"}
    assert {snapshot.concept_source_kind for snapshot in snapshots} == {
        "tushare_current_overlay"
    }
    assert "sv_tushare_current" not in sources
    assert provenance.concept_source_kind == "tushare_current_overlay"
    assert provenance.overlay_status == "available"


def test_strategy_reader_receives_none_when_no_market_date_resolves(
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    class RecordingReader:
        def read(self, **kwargs: object) -> ThemeOverlayReadResult:
            calls.append(kwargs)
            return ThemeOverlayReadResult(
                status="unavailable",
                reason="no_resolved_market_date",
                fingerprint="f" * 64,
            )

    service._load_livermore_strategy_payload_uncached(
        duckdb_path=str(tmp_path / "missing.duckdb"),
        as_of_date=date(2026, 7, 8),
        stock_readiness=service.choice_stock_readiness_missing("fixture"),
        backfill_mode=False,
        stock_candidate_policy=None,
        theme_overlay_reader=RecordingReader(),  # type: ignore[arg-type]
    )

    assert calls == [
        {
            "requested_as_of_date": "2026-07-08",
            "effective_as_of_date": None,
            "backfill_mode": False,
        }
    ]


def test_internal_strategy_payload_cache_key_includes_overlay_fingerprint(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cache.duckdb"
    duckdb.connect(str(path)).close()
    readiness = service.choice_stock_readiness_missing("fixture")

    first = service._livermore_strategy_payload_cache_key(
        duckdb_path=str(path),
        as_of_date=date(2026, 7, 8),
        stock_readiness=readiness,
        backfill_mode=False,
        stock_candidate_policy=None,
        theme_overlay_fingerprint="overlay-a",
    )
    second = service._livermore_strategy_payload_cache_key(
        duckdb_path=str(path),
        as_of_date=date(2026, 7, 8),
        stock_readiness=readiness,
        backfill_mode=False,
        stock_candidate_policy=None,
        theme_overlay_fingerprint="overlay-b",
    )

    assert first is not None
    assert second is not None
    assert first != second


def test_signal_confluence_passes_the_same_overlay_reader_to_strategy(
    monkeypatch,
) -> None:
    from backend.app.services import livermore_signal_confluence_service as confluence

    reader = object()
    calls: list[object] = []

    def fake_strategy(**kwargs):
        calls.append(kwargs.get("theme_overlay_reader"))
        return {
            "result_meta": {"quality_flag": "ok"},
            "result": {"as_of_date": None, "market_gate": {"state": "NO_DATA"}},
        }

    monkeypatch.setattr(
        confluence, "livermore_strategy_envelope_from_catalog", fake_strategy
    )
    monkeypatch.setattr(
        confluence,
        "load_macro_adversarial_signal_payload",
        lambda **_kwargs: ({}, {}),
    )
    monkeypatch.setattr(
        confluence,
        "livermore_candidate_history_backtest_window_summary",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(
        confluence, "_attach_replay_evidence", lambda *_args, **_kwargs: None
    )

    confluence.livermore_signal_confluence_envelope(
        duckdb_path="missing.duckdb",
        as_of_date=None,
        choice_stock_catalog_file="missing.json",
        theme_overlay_reader=reader,
    )

    assert calls == [reader]
