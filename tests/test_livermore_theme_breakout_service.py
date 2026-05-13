from __future__ import annotations

import json

import duckdb

from backend.app.core_finance.livermore_theme_breakout import compute_theme_breakout
from backend.app.repositories.choice_stock_adapter import (
    CHOICE_STOCK_REQUIRED_INPUT_FAMILIES,
    load_choice_stock_readiness,
)
from backend.app.services.market_data_livermore_service import (
    _ThemeBreakoutEvidenceProvenance,
    _build_theme_breakout_evidence_state,
    _load_theme_breakout_snapshots,
)


def _write_theme_catalog(
    tmp_path,
    *,
    concept_confirmed: bool,
    movement_confirmed: bool,
):
    catalog_path = tmp_path / "choice_stock_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "catalog_version": "test_theme_catalog",
                "vendor_name": "choice",
                "generated_from": "unit_test",
                "fields": [
                    *[
                        {
                            "input_family": family,
                            "field_key": f"{family}_field",
                            "vendor_indicator": f"{family}_indicator",
                            "call": "csd" if family == "stock_ohlcv" else "css",
                            "confirmed": True,
                            "confirmation_source": "unit test",
                            "confirmed_at": "2026-05-11",
                        }
                        for family in CHOICE_STOCK_REQUIRED_INPUT_FAMILIES
                    ],
                    {
                        "input_family": "concept_membership",
                        "field_key": "choice_concept_membership",
                        "vendor_indicator": "CONCEPTCODE,CONCEPTNAME" if concept_confirmed else "",
                        "call": "css",
                        "required": False,
                        "confirmed": concept_confirmed,
                        "confirmation_source": "unit test optional concept probe" if concept_confirmed else "",
                        "confirmed_at": "2026-05-11" if concept_confirmed else "",
                    },
                    {
                        "input_family": "intraday_movement",
                        "field_key": "choice_intraday_movement",
                        "vendor_indicator": "STOCK_INTRADAY_MOVEMENT" if movement_confirmed else "",
                        "call": "ctr",
                        "required": False,
                        "confirmed": movement_confirmed,
                        "confirmation_source": "unit test optional movement probe" if movement_confirmed else "",
                        "confirmed_at": "2026-05-11" if movement_confirmed else "",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return load_choice_stock_readiness(catalog_path)


def test_theme_breakout_loader_reads_current_stock_rows_with_sector_rank(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_universe (
              stock_code varchar,
              stock_name varchar,
              as_of_date varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              stock_code varchar,
              as_of_date varchar,
              sw2021code varchar,
              sw2021 varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              stock_code varchar,
              trade_date varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              pctchange double,
              turn double,
              amplitude double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_limit_quality (
              stock_code varchar,
              as_of_date varchar,
              issurgedlimit boolean,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_universe values (?, ?, ?, ?, ?)",
            [
                ("688001.SH", "Alpha Semiconductor", "2026-05-08", "sv_u", "vv_u"),
                ("688002.SH", "Beta Chip", "2026-05-08", "sv_u", "vv_u"),
            ],
        )
        conn.executemany(
            "insert into choice_stock_sector_membership values (?, ?, ?, ?, ?, ?)",
            [
                ("688001.SH", "2026-05-08", "801080", "Electronic", "sv_s", "vv_s"),
                ("688002.SH", "2026-05-08", "801080", "Electronic", "sv_s", "vv_s"),
            ],
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("688001.SH", "2026-05-08", 9.6, 10.1, 9.4, 10.0, 12.1, 4.2, 7.0, "sv_d", "vv_d"),
                ("688002.SH", "2026-05-08", 8.8, 9.4, 8.6, 9.3, 10.4, 5.2, 8.0, "sv_d", "vv_d"),
            ],
        )
        conn.executemany(
            "insert into choice_stock_limit_quality values (?, ?, ?, ?, ?)",
            [
                ("688001.SH", "2026-05-08", True, "sv_l", "vv_l"),
                ("688002.SH", "2026-05-08", False, "sv_l", "vv_l"),
            ],
        )
    finally:
        conn.close()

    snapshots, tables_used, source_versions, vendor_versions, provenance = _load_theme_breakout_snapshots(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-08",
        sector_rank_payload={
            "items": [
                {
                    "rank": 9,
                    "sector_code": "801080",
                    "sector_name": "Electronic",
                }
            ]
        },
    )

    assert [snapshot.stock_code for snapshot in snapshots] == ["688001.SH", "688002.SH"]
    assert snapshots[0].sector_rank == 9
    assert snapshots[0].closed_up_limit is True
    assert set(tables_used) == {
        "choice_stock_universe",
        "choice_stock_sector_membership",
        "choice_stock_daily_observation",
        "choice_stock_limit_quality",
    }
    assert source_versions
    assert vendor_versions
    assert provenance.concept_date_row_count == 0
    assert provenance.movement_date_row_count == 0


def test_theme_breakout_loader_handles_varchar_limit_flags(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_universe (
              stock_code varchar,
              stock_name varchar,
              as_of_date varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              stock_code varchar,
              as_of_date varchar,
              sw2021code varchar,
              sw2021 varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              stock_code varchar,
              trade_date varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              pctchange double,
              turn double,
              amplitude double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_limit_quality (
              stock_code varchar,
              as_of_date varchar,
              issurgedlimit varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            "insert into choice_stock_universe values (?, ?, ?, ?, ?)",
            ("688001.SH", "Alpha Semiconductor", "2026-05-08", "sv_u", "vv_u"),
        )
        conn.execute(
            "insert into choice_stock_sector_membership values (?, ?, ?, ?, ?, ?)",
            ("688001.SH", "2026-05-08", "801080", "Electronic", "sv_s", "vv_s"),
        )
        conn.execute(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("688001.SH", "2026-05-08", 9.6, 10.1, 9.4, 10.0, 12.1, 4.2, 7.0, "sv_d", "vv_d"),
        )
        conn.execute(
            "insert into choice_stock_limit_quality values (?, ?, ?, ?, ?)",
            ("688001.SH", "2026-05-08", "1", "sv_l", "vv_l"),
        )
    finally:
        conn.close()

    snapshots, tables_used, _, _, provenance = _load_theme_breakout_snapshots(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-08",
        sector_rank_payload={
            "items": [
                {
                    "rank": 9,
                    "sector_code": "801080",
                    "sector_name": "Electronic",
                }
            ]
        },
    )

    assert [snapshot.stock_code for snapshot in snapshots] == ["688001.SH"]
    assert snapshots[0].closed_up_limit is True
    assert "choice_stock_limit_quality" in tables_used
    assert provenance.concept_date_row_count == 0


def test_theme_breakout_loader_enriches_snapshots_with_real_concept_and_movement_rows(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_universe (
              stock_code varchar,
              stock_name varchar,
              as_of_date varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              stock_code varchar,
              as_of_date varchar,
              sw2021code varchar,
              sw2021 varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              stock_code varchar,
              trade_date varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              pctchange double,
              turn double,
              amplitude double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_concept_membership (
              as_of_date varchar,
              stock_code varchar,
              concept_code varchar,
              concept_name varchar,
              concept_source varchar,
              field_key varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_intraday_movement_event (
              as_of_date varchar,
              event_time varchar,
              stock_code varchar,
              stock_name varchar,
              concept_code varchar,
              concept_name varchar,
              event_type varchar,
              event_title varchar,
              pctchange double,
              turn double,
              source_url varchar,
              field_key varchar,
              raw_json varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            "insert into choice_stock_universe values (?, ?, ?, ?, ?)",
            ("688001.SH", "Alpha Semiconductor", "2026-05-08", "sv_u", "vv_u"),
        )
        conn.execute(
            "insert into choice_stock_sector_membership values (?, ?, ?, ?, ?, ?)",
            ("688001.SH", "2026-05-08", "801080", "Electronic", "sv_s", "vv_s"),
        )
        conn.execute(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("688001.SH", "2026-05-08", 9.6, 10.1, 9.4, 10.0, 12.1, 4.2, 7.0, "sv_d", "vv_d"),
        )
        conn.execute(
            "insert into choice_stock_concept_membership values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-05-08",
                "688001.SH",
                "C001",
                "Chiplet",
                "choice",
                "choice_concept_membership",
                "sv_c",
                "vv_c",
                "rv",
                "run",
            ),
        )
        conn.executemany(
            "insert into choice_stock_intraday_movement_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-05-08",
                    "2026-05-08 10:05:00",
                    "688001.SH",
                    "Alpha Semiconductor",
                    "C001",
                    "Chiplet",
                    "intraday_surge",
                    "Chiplet concept intraday surge",
                    12.1,
                    4.2,
                    "https://choice.example/news/1",
                    "choice_intraday_movement",
                    "{}",
                    "sv_m",
                    "vv_m",
                    "rv",
                    "run",
                ),
                (
                    "2026-05-08",
                    "2026-05-08 10:08:00",
                    "688001.SH",
                    "Alpha Semiconductor",
                    "C001",
                    "Chiplet",
                    "intraday_surge",
                    "Chiplet concept extends gains",
                    12.3,
                    4.4,
                    "https://choice.example/news/2",
                    "choice_intraday_movement",
                    "{}",
                    "sv_m",
                    "vv_m",
                    "rv",
                    "run",
                ),
            ],
        )
    finally:
        conn.close()

    snapshots, tables_used, _, _, provenance = _load_theme_breakout_snapshots(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-08",
        sector_rank_payload={
            "items": [
                {
                    "rank": 9,
                    "sector_code": "801080",
                    "sector_name": "Electronic",
                }
            ]
        },
    )

    assert len(snapshots) == 1
    assert snapshots[0].concept_code == "C001"
    assert snapshots[0].concept_name == "Chiplet"
    assert snapshots[0].movement_event_count == 2
    assert snapshots[0].latest_event_title == "Chiplet concept extends gains"
    assert "choice_stock_concept_membership" in tables_used
    assert "choice_stock_intraday_movement_event" in tables_used
    assert provenance.concept_date_row_count == 1
    assert provenance.concept_matched_row_count == 1
    assert provenance.movement_date_row_count == 2
    assert provenance.movement_matched_row_count == 2


def test_theme_breakout_evidence_state_prefers_catalog_unconfirmed_over_table_state(tmp_path) -> None:
    readiness = _write_theme_catalog(tmp_path, concept_confirmed=False, movement_confirmed=False)

    evidence_state = _build_theme_breakout_evidence_state(
        stock_readiness=readiness,
        tables_used=[
            "choice_stock_concept_membership",
            "choice_stock_intraday_movement_event",
        ],
        provenance=_ThemeBreakoutEvidenceProvenance(
            concept_date_row_count=3,
            concept_matched_row_count=3,
            movement_date_row_count=2,
            movement_matched_row_count=2,
        ),
    )

    assert evidence_state["concept_membership"]["state"] == "catalog_unconfirmed"
    assert evidence_state["concept_membership"]["status"] == "catalog_unconfirmed"
    assert evidence_state["concept_membership"]["input_family"] == "concept_membership"
    assert evidence_state["intraday_movement"]["state"] == "catalog_unconfirmed"
    assert evidence_state["intraday_movement"]["status"] == "catalog_unconfirmed"


def test_theme_breakout_evidence_state_marks_confirmed_optional_tables_missing(tmp_path) -> None:
    readiness = _write_theme_catalog(tmp_path, concept_confirmed=True, movement_confirmed=True)

    evidence_state = _build_theme_breakout_evidence_state(
        stock_readiness=readiness,
        tables_used=[],
        provenance=_ThemeBreakoutEvidenceProvenance(),
    )

    assert evidence_state["concept_membership"]["state"] == "table_missing"
    assert evidence_state["concept_membership"]["table"] == "choice_stock_concept_membership"
    assert evidence_state["intraday_movement"]["state"] == "table_missing"


def test_theme_breakout_evidence_state_marks_confirmed_optional_tables_with_zero_rows_as_landed_no_rows(
    tmp_path,
) -> None:
    readiness = _write_theme_catalog(tmp_path, concept_confirmed=True, movement_confirmed=True)

    evidence_state = _build_theme_breakout_evidence_state(
        stock_readiness=readiness,
        tables_used=[
            "choice_stock_concept_membership",
            "choice_stock_intraday_movement_event",
        ],
        provenance=_ThemeBreakoutEvidenceProvenance(),
    )

    assert evidence_state["concept_membership"]["state"] == "landed_no_rows"
    assert evidence_state["concept_membership"]["row_count"] == 0
    assert evidence_state["intraday_movement"]["state"] == "landed_no_rows"


def test_theme_breakout_tracks_concept_and_movement_evidence_independently_without_changing_selected_items(
    tmp_path,
) -> None:
    readiness = _write_theme_catalog(tmp_path, concept_confirmed=True, movement_confirmed=True)
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_universe (
              stock_code varchar,
              stock_name varchar,
              as_of_date varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              stock_code varchar,
              as_of_date varchar,
              sw2021code varchar,
              sw2021 varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              stock_code varchar,
              trade_date varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              pctchange double,
              turn double,
              amplitude double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_concept_membership (
              as_of_date varchar,
              stock_code varchar,
              concept_code varchar,
              concept_name varchar,
              concept_source varchar,
              field_key varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_intraday_movement_event (
              as_of_date varchar,
              event_time varchar,
              stock_code varchar,
              stock_name varchar,
              concept_code varchar,
              concept_name varchar,
              event_type varchar,
              event_title varchar,
              pctchange double,
              turn double,
              source_url varchar,
              field_key varchar,
              raw_json varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_universe values (?, ?, ?, ?, ?)",
            [
                ("688001.SH", "Alpha Semiconductor", "2026-05-08", "sv_u", "vv_u"),
                ("688002.SH", "Beta Chip", "2026-05-08", "sv_u", "vv_u"),
                ("688003.SH", "Gamma Micro", "2026-05-08", "sv_u", "vv_u"),
            ],
        )
        conn.executemany(
            "insert into choice_stock_sector_membership values (?, ?, ?, ?, ?, ?)",
            [
                ("688001.SH", "2026-05-08", "801080", "Electronic", "sv_s", "vv_s"),
                ("688002.SH", "2026-05-08", "801080", "Electronic", "sv_s", "vv_s"),
                ("688003.SH", "2026-05-08", "801080", "Electronic", "sv_s", "vv_s"),
            ],
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("688001.SH", "2026-05-08", 9.6, 10.1, 9.4, 10.0, 12.1, 4.2, 7.0, "sv_d", "vv_d"),
                ("688002.SH", "2026-05-08", 8.8, 9.4, 8.6, 9.3, 10.4, 5.2, 8.0, "sv_d", "vv_d"),
                ("688003.SH", "2026-05-08", 8.7, 9.0, 8.5, 8.9, 6.8, 3.8, 5.8, "sv_d", "vv_d"),
            ],
        )
        conn.executemany(
            "insert into choice_stock_concept_membership values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-05-08", "688001.SH", "C001", "Chiplet", "choice", "choice_concept_membership", "sv_c", "vv_c", "rv", "run"),
                ("2026-05-08", "688002.SH", "C001", "Chiplet", "choice", "choice_concept_membership", "sv_c", "vv_c", "rv", "run"),
                ("2026-05-08", "688003.SH", "C001", "Chiplet", "choice", "choice_concept_membership", "sv_c", "vv_c", "rv", "run"),
            ],
        )
    finally:
        conn.close()

    snapshots, tables_used, _, _, provenance = _load_theme_breakout_snapshots(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-08",
        sector_rank_payload={
            "items": [
                {
                    "rank": 9,
                    "sector_code": "801080",
                    "sector_name": "Electronic",
                }
            ]
        },
    )

    payload = compute_theme_breakout(as_of_date="2026-05-08", snapshots=snapshots).payload
    payload["evidence_state"] = _build_theme_breakout_evidence_state(
        stock_readiness=readiness,
        tables_used=tables_used,
        provenance=provenance,
    )

    assert [item["theme_key"] for item in payload["items"]] == ["concept:C001"]
    assert payload["evidence_state"]["concept_membership"]["state"] == "matched_rows"
    assert payload["evidence_state"]["intraday_movement"]["state"] == "landed_no_rows"
