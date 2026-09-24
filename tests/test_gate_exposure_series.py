from __future__ import annotations

from datetime import date, timedelta

import duckdb
import pytest

from backend.app.core_finance.gate_exposure_series import load_gate_exposure_by_date


def test_load_gate_exposure_prefers_persisted_candidate_history() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              signal_evidence_json varchar
            )
            """
        )
        conn.execute(
            "insert into livermore_candidate_history values (?, ?)",
            [
                "2026-06-01",
                '{"market_gate":{"state":"WARM","exposure":0.25}}',
            ],
        )

        points = load_gate_exposure_by_date(conn, "2026-06-01", "2026-06-01")
    finally:
        conn.close()

    assert points["2026-06-01"].exposure == pytest.approx(0.25)
    assert points["2026-06-01"].state == "WARM"
    assert points["2026-06-01"].source == "persisted:livermore_candidate_history"


def test_load_gate_exposure_prefers_gate_history_over_candidate_evidence() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              signal_evidence_json varchar
            )
            """
        )
        conn.execute(
            """
            create table livermore_monitor_append (
              trade_date varchar,
              exposure double,
              market_state varchar
            )
            """
        )
        conn.execute(
            "insert into livermore_candidate_history values (?, ?)",
            [
                "2026-06-01",
                '{"market_gate":{"state":"WARM","exposure":0.25}}',
            ],
        )
        conn.execute(
            "insert into livermore_monitor_append values (?, ?, ?)",
            ["2026-06-01", 0.5, "HOT"],
        )

        points = load_gate_exposure_by_date(conn, "2026-06-01", "2026-06-01")
    finally:
        conn.close()

    assert points["2026-06-01"].exposure == pytest.approx(0.5)
    assert points["2026-06-01"].state == "HOT"
    assert points["2026-06-01"].source == "persisted:livermore_monitor_append"


def test_load_gate_exposure_does_not_guess_conflicting_same_day_persisted_values() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              signal_evidence_json varchar
            )
            """
        )
        conn.executemany(
            "insert into livermore_candidate_history values (?, ?)",
            [
                ("2026-06-01", '{"market_gate":{"state":"WARM","exposure":0.25}}'),
                ("2026-06-01", '{"market_gate":{"state":"WARM","exposure":0.50}}'),
            ],
        )

        points = load_gate_exposure_by_date(conn, "2026-06-01", "2026-06-01")
    finally:
        conn.close()

    assert points["2026-06-01"].exposure == 0.0
    assert points["2026-06-01"].state == "NO_DATA"
    assert points["2026-06-01"].source == "missing"


def test_load_gate_exposure_replays_when_persisted_missing() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              trade_date varchar,
              value_numeric double,
              quality_flag varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_livermore_gate_supplement_daily (
              trade_date varchar,
              breadth_5d double,
              limit_up_quality_ok boolean,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        dates = [(date(2026, 1, 1) + timedelta(days=index)).isoformat() for index in range(65)]
        conn.executemany(
            "insert into fact_choice_macro_daily values ('CA.CSI300', ?, ?, 'ok')",
            [(trade_date, 3000.0 + index * 10) for index, trade_date in enumerate(dates, start=1)],
        )
        conn.execute(
            "insert into fact_livermore_gate_supplement_daily values (?, 0.2, false, 'sv', 'vv', 'rv', 'run')",
            [dates[-1]],
        )

        points = load_gate_exposure_by_date(conn, dates[-1], dates[-1])
    finally:
        conn.close()

    assert points[dates[-1]].exposure == pytest.approx(0.75)
    assert points[dates[-1]].state == "HOT"
    assert points[dates[-1]].source == "replayed"


def test_load_gate_exposure_marks_dates_missing_without_sources() -> None:
    conn = duckdb.connect(":memory:")
    try:
        points = load_gate_exposure_by_date(conn, "2026-06-01", "2026-06-02")
    finally:
        conn.close()

    assert sorted(points) == ["2026-06-01", "2026-06-02"]
    assert points["2026-06-01"].exposure == 0.0
    assert points["2026-06-01"].state == "NO_DATA"
    assert points["2026-06-01"].source == "missing"
    assert points["2026-06-02"].source == "missing"
