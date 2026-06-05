from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from backend.scripts.backfill_cross_asset_macro_environment import (
    CHOICE_SERIES,
    PUBLIC_REPO_SERIES,
    TUSHARE_SHIBOR_SERIES,
    MacroRow,
    choice_edb_rows,
    persist_macro_environment_rows,
    public_dr007_rows,
    tushare_shibor_rows,
)


def test_choice_edb_rows_keep_all_history_and_skip_empty_values() -> None:
    frame = pd.DataFrame(
        [
            {"DATES": "2026/03/01", "RESULT": 7.7},
            {"DATES": "2026/04/01", "RESULT": None},
            {"DATES": "2026/05/01", "RESULT": "5.8"},
        ],
        index=pd.Index(["EMM00008445", "EMM00008445", "EMM00008445"], name="CODES"),
    )

    rows = choice_edb_rows(frame, {"EMM00008445": CHOICE_SERIES["EMM00008445"]})

    assert rows == [
        {
            "series_id": "EMM00008445",
            "series_name": "工业增加值:当月同比",
            "vendor_series_code": "EMM00008445",
            "trade_date": "2026-03-01",
            "value_numeric": 7.7,
            "frequency": "monthly",
            "unit": "%",
        },
        {
            "series_id": "EMM00008445",
            "series_name": "工业增加值:当月同比",
            "vendor_series_code": "EMM00008445",
            "trade_date": "2026-05-01",
            "value_numeric": 5.8,
            "frequency": "monthly",
            "unit": "%",
        },
    ]


def test_tushare_shibor_rows_map_on_and_one_week_to_environment_series() -> None:
    rows = tushare_shibor_rows(
        [
            {"date": "20260513", "on": 1.267, "1w": "1.299"},
            {"date": "20260512", "on": None, "1w": 1.308},
        ]
    )

    assert rows == [
        {
            "series_id": "EMM00166252",
            "series_name": "SHIBOR:隔夜",
            "vendor_series_code": "shibor:on",
            "trade_date": "2026-05-13",
            "value_numeric": 1.267,
            "frequency": "daily",
            "unit": "%",
        },
        {
            "series_id": "EMM00166253",
            "series_name": "SHIBOR:1周",
            "vendor_series_code": "shibor:1w",
            "trade_date": "2026-05-12",
            "value_numeric": 1.308,
            "frequency": "daily",
            "unit": "%",
        },
        {
            "series_id": "EMM00166253",
            "series_name": "SHIBOR:1周",
            "vendor_series_code": "shibor:1w",
            "trade_date": "2026-05-13",
            "value_numeric": 1.299,
            "frequency": "daily",
            "unit": "%",
        },
    ]


def test_public_dr007_rows_map_fdr007_to_environment_series() -> None:
    meta = PUBLIC_REPO_SERIES["CA.DR007"][0]

    rows = public_dr007_rows(
        [
            {"date": "2026-05-11", "FDR007": 1.31},
            {"date": "2026-05-12", "FDR007": "1.30"},
            {"date": "2026-05-12", "FDR007": "1.32"},
            {"date": "2026-05-13", "FDR007": 1.29},
            {"date": "2026-05-14", "FDR007": None},
        ],
        start_date="2026-05-12",
        end_date="2026-05-13",
    )

    assert rows == [
        {
            "series_id": "CA.DR007",
            "series_name": meta.series_name,
            "vendor_series_code": "repo_rate_hist:FDR007",
            "trade_date": "2026-05-12",
            "value_numeric": 1.30,
            "frequency": "daily",
            "unit": "%",
        },
        {
            "series_id": "CA.DR007",
            "series_name": meta.series_name,
            "vendor_series_code": "repo_rate_hist:FDR007",
            "trade_date": "2026-05-13",
            "value_numeric": 1.29,
            "frequency": "daily",
            "unit": "%",
        },
    ]


def test_persist_macro_environment_rows_replaces_target_window(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    meta = TUSHARE_SHIBOR_SERIES["EMM00166252"][0]

    first_rows = [
        MacroRow(
            series_id=meta.series_id,
            series_name=meta.series_name,
            vendor_series_code=meta.vendor_series_code,
            vendor_name=meta.vendor_name,
            trade_date="2026-05-12",
            value_numeric=1.25,
            frequency=meta.frequency,
            unit=meta.unit,
            source_version="sv_old",
            vendor_version="vv_old",
        )
    ]
    replacement_rows = [
        MacroRow(
            series_id=meta.series_id,
            series_name=meta.series_name,
            vendor_series_code=meta.vendor_series_code,
            vendor_name=meta.vendor_name,
            trade_date="2026-05-12",
            value_numeric=1.27,
            frequency=meta.frequency,
            unit=meta.unit,
            source_version="sv_new",
            vendor_version="vv_new",
        )
    ]

    assert (
        persist_macro_environment_rows(
            duckdb_path=db_path,
            rows=first_rows,
            metas={meta.series_id: meta},
            run_id="run-old",
            start_date="2026-05-12",
            end_date="2026-05-12",
        )
        == 1
    )
    assert (
        persist_macro_environment_rows(
            duckdb_path=db_path,
            rows=replacement_rows,
            metas={meta.series_id: meta},
            run_id="run-new",
            start_date="2026-05-12",
            end_date="2026-05-12",
        )
        == 1
    )

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        fact_rows = conn.execute(
            """
            select value_numeric, source_version, vendor_version, run_id
            from fact_choice_macro_daily
            where series_id = 'EMM00166252'
            """
        ).fetchall()
        category_rows = conn.execute(
            """
            select category_key, category_label, source_surface
            from market_data_series_category
            where series_id = 'EMM00166252'
            """
        ).fetchall()
    finally:
        conn.close()

    assert fact_rows == [(pytest.approx(1.27), "sv_new", "vv_new", "run-new")]
    assert category_rows == [("fallback", "Fallback latest-only series", "choice_macro")]
