"""Regression tests: macro refresh tasks must not wipe backfilled history.

Context: docs/plans/2026-07-19-macro-data-freshness-remediation.md backfilled
NCD.SHIBOR.* to 632 rows per series, but refresh_tushare_ncd_shibor_proxy and
refresh_public_cross_asset_headlines used delete-all-then-insert-window
semantics, which would wipe the backfilled history on the next run.
"""

from __future__ import annotations

import sys

import duckdb

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _load_task_module():
    task_module = sys.modules.get("backend.app.tasks.choice_macro")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_macro",
            "backend/app/tasks/choice_macro.py",
        )
    return task_module


def _seed_fact_rows(task_module, duckdb_path: str, rows: list[tuple[str, str, float]]) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        task_module._ensure_tables(conn)
        for series_id, trade_date, value in rows:
            conn.execute(
                "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    series_id,
                    f"seed:{series_id}",
                    trade_date,
                    value,
                    "daily",
                    "%",
                    "sv_seed_backfill",
                    "vv_seed_backfill",
                    "rv_seed_backfill",
                    "ok",
                    "seed_backfill_run",
                ],
            )
    finally:
        conn.close()


def _fact_rows(duckdb_path: str, series_like: str) -> list[tuple[str, str, float]]:
    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
        return conn.execute(
            """
            select series_id, trade_date, value_numeric
            from fact_choice_macro_daily
            where series_id like ?
            order by series_id, trade_date
            """,
            [series_like],
        ).fetchall()
    finally:
        conn.close()


def _duplicate_keys(duckdb_path: str) -> list[tuple[str, str]]:
    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
        return conn.execute(
            """
            select series_id, trade_date
            from fact_choice_macro_daily
            group by series_id, trade_date
            having count(*) > 1
            """
        ).fetchall()
    finally:
        conn.close()


def _shibor_row(series_id: str, trade_date: str, value: float) -> dict[str, object]:
    return {
        "series_id": series_id,
        "trade_date": trade_date,
        "value_numeric": value,
        "vendor_version": "vv_tushare_shibor",
        "source_version": "sv_tushare_shibor",
    }


def test_ncd_shibor_refresh_preserves_history_outside_window(tmp_path, monkeypatch):
    duckdb_path = str(tmp_path / "moss.duckdb")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", duckdb_path)
    get_settings.cache_clear()

    task_module = _load_task_module()

    # Backfilled history far before the refresh window + a stale in-window row.
    _seed_fact_rows(
        task_module,
        duckdb_path,
        [
            ("NCD.SHIBOR.3M", "2024-01-05", 2.5),
            ("NCD.SHIBOR.3M", "2025-06-30", 1.9),
            ("NCD.SHIBOR.3M", "2026-04-09", 9.9),
        ],
    )

    monkeypatch.setattr(
        task_module,
        "_fetch_tushare_ncd_shibor_history_rows",
        lambda **_: [
            _shibor_row("NCD.SHIBOR.3M", "2026-04-09", 1.4345),
            _shibor_row("NCD.SHIBOR.1M", "2026-04-10", 1.422),
            _shibor_row("NCD.SHIBOR.3M", "2026-04-10", 1.4445),
            _shibor_row("NCD.SHIBOR.6M", "2026-04-10", 1.4635),
            _shibor_row("NCD.SHIBOR.9M", "2026-04-10", 1.4795),
            _shibor_row("NCD.SHIBOR.1Y", "2026-04-10", 1.4925),
        ],
    )

    payload = task_module.refresh_tushare_ncd_shibor_proxy(
        duckdb_path=duckdb_path,
        report_date="2026-04-10",
        lookback_days=7,
    )
    assert payload["status"] == "completed"

    rows = dict()
    for series_id, trade_date, value in _fact_rows(duckdb_path, "NCD.SHIBOR.3M"):
        rows[(series_id, trade_date)] = value

    # History outside the refresh window (window start = 2026-04-03) survives.
    assert rows.get(("NCD.SHIBOR.3M", "2024-01-05")) == 2.5
    assert rows.get(("NCD.SHIBOR.3M", "2025-06-30")) == 1.9
    # Stale in-window row is rewritten by the fetched value.
    assert rows.get(("NCD.SHIBOR.3M", "2026-04-09")) == 1.4345
    assert rows.get(("NCD.SHIBOR.3M", "2026-04-10")) == 1.4445
    # No duplicated (series_id, trade_date) keys.
    assert _duplicate_keys(duckdb_path) == []

    get_settings.cache_clear()


def _headline_row(series_id: str, trade_date: str, value: float) -> dict[str, object]:
    return {
        "series_id": series_id,
        "trade_date": trade_date,
        "value_numeric": value,
        "vendor_version": "vv_public_fixture",
        "source_version": "sv_public_fixture",
    }


def test_public_cross_asset_refresh_preserves_history_outside_window(tmp_path, monkeypatch):
    duckdb_path = str(tmp_path / "moss.duckdb")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", duckdb_path)
    get_settings.cache_clear()

    task_module = _load_task_module()

    # Backfilled history before each series' fetched window + a stale in-window row.
    _seed_fact_rows(
        task_module,
        duckdb_path,
        [
            ("E1003238", "2024-02-01", 4.0),
            ("E1003238", "2026-04-09", 9.9),
            ("CA.BRENT", "2026-03-01", 70.0),
        ],
    )

    # Per-series fetch depth differs: E1003238 window starts 2026-04-09,
    # CA.BRENT window starts 2026-04-10.
    monkeypatch.setattr(
        task_module,
        "_load_public_cross_asset_history_rows",
        lambda **_: [
            _headline_row("E1003238", "2026-04-09", 4.2),
            _headline_row("E1003238", "2026-04-10", 4.26),
            _headline_row("CA.BRENT", "2026-04-10", 64.8),
        ],
    )

    payload = task_module.refresh_public_cross_asset_headlines(
        duckdb_path=duckdb_path,
        report_date="2026-04-10",
        lookback_days=60,
    )
    assert payload["status"] == "completed"

    rows = dict()
    for series_id, trade_date, value in _fact_rows(duckdb_path, "%"):
        rows[(series_id, trade_date)] = value

    # History before each series' fetched window survives.
    assert rows.get(("E1003238", "2024-02-01")) == 4.0
    assert rows.get(("CA.BRENT", "2026-03-01")) == 70.0
    # Stale in-window row is rewritten by the fetched value.
    assert rows.get(("E1003238", "2026-04-09")) == 4.2
    assert rows.get(("E1003238", "2026-04-10")) == 4.26
    assert rows.get(("CA.BRENT", "2026-04-10")) == 64.8
    # No duplicated (series_id, trade_date) keys.
    assert _duplicate_keys(duckdb_path) == []

    get_settings.cache_clear()
