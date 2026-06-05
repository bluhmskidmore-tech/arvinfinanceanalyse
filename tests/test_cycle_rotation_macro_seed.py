from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from backend.app.services.market_data_livermore_service import _load_cycle_input_evidence
from backend.app.tasks.cycle_rotation_macro_seed import materialize_cycle_rotation_macro_fixture


def test_seed_fixture_makes_macro_score_ready(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "CA.CSI300_PE",
                    "CSI300 PE",
                    "2026-05-08",
                    14.0,
                    "daily",
                    "x",
                    "sv_pe",
                    "vv_pe",
                    "rv_pe",
                    "ok",
                    "run-pe",
                ),
                (
                    "EMM00166466",
                    "CN10Y",
                    "2026-05-08",
                    2.1,
                    "daily",
                    "%",
                    "sv_y",
                    "vv_y",
                    "rv_y",
                    "ok",
                    "run-y",
                ),
            ],
        )
    finally:
        conn.close()

    seed_payload = materialize_cycle_rotation_macro_fixture(duckdb_path=str(db_path))
    assert seed_payload["row_count"] >= 4
    assert "M0017126" in seed_payload["series_ids"]
    assert "M5525763" in seed_payload["series_ids"]

    evidence = _load_cycle_input_evidence(duckdb_path=str(db_path), as_of_date=date(2026, 5, 8))
    assert evidence.pmi_ready is True
    assert evidence.credit_impulse_ready is True
    assert evidence.price_spread_ready is True
    assert evidence.macro_score is not None
    assert evidence.macro_score_ready is True
    assert "MacroScore" in evidence.macro_score_evidence


def test_seed_fixture_preserves_existing_fact_rows_without_force(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('M0017126', '制造业PMI', '2026-03-01', 49.9, 'monthly', 'index', 'sv_vendor', 'vv_vendor', 'rv_vendor', 'ok', 'run-vendor')
            """
        )
    finally:
        conn.close()

    seed_payload = materialize_cycle_rotation_macro_fixture(duckdb_path=str(db_path))
    assert seed_payload["overwrite_existing"] is False

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select value_numeric, source_version, rule_version
            from fact_choice_macro_daily
            where series_id = 'M0017126' and trade_date = '2026-03-01'
            """
        ).fetchone()
    finally:
        conn.close()

    assert row == (49.9, "sv_vendor", "rv_vendor")

    force_payload = materialize_cycle_rotation_macro_fixture(
        duckdb_path=str(db_path),
        overwrite_existing=True,
    )
    assert force_payload["overwrite_existing"] is True

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        overwritten = conn.execute(
            """
            select value_numeric, source_version, rule_version
            from fact_choice_macro_daily
            where series_id = 'M0017126' and trade_date = '2026-03-01'
            """
        ).fetchone()
    finally:
        conn.close()

    assert overwritten == (50.2, "sv_cycle_rotation_macro_fixture_v1", "rv_cycle_rotation_macro_seed_v1")
