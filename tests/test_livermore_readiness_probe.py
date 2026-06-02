from __future__ import annotations

from datetime import date, timedelta

import duckdb

from backend.app.services.livermore_readiness_probe import probe_livermore_readiness


def _seed_csi300(
    duckdb_path: str,
    *,
    start: date,
    n_days: int,
    quality_flag: str = "ok",
) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
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
        rows = []
        for offset in range(n_days):
            trade_date = (start + timedelta(days=offset)).isoformat()
            close = 3200.0 + offset * 8.0
            rows.append(
                (
                    "CA.CSI300",
                    "沪深300指数收盘价",
                    trade_date,
                    close,
                    "daily",
                    "index",
                    "sv_probe",
                    "vv_probe",
                    "rv_probe",
                    quality_flag,
                    f"run:{trade_date}",
                )
            )
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        conn.close()


def test_probe_missing_duckdb_file(tmp_path) -> None:
    missing_db = tmp_path / "nope.duckdb"
    catalog = tmp_path / "cat.json"
    catalog.write_text("{}", encoding="utf-8")
    r = probe_livermore_readiness(
        duckdb_path=str(missing_db),
        catalog_path=str(catalog),
    )
    assert r.duckdb_exists is False
    assert r.history_count == 0
    assert r.tables_used == ()


def test_probe_history_and_as_of_resolution(tmp_path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_csi300(str(db), start=date(2026, 2, 1), n_days=65)
    catalog = tmp_path / "choice_stock_catalog.json"
    catalog.write_text(
        '{"catalog_version":"t","vendor_name":"choice","fields":[]}',
        encoding="utf-8",
    )

    r = probe_livermore_readiness(
        duckdb_path=str(db),
        catalog_path=str(catalog),
        as_of_date=date(2026, 5, 3),
    )
    assert r.duckdb_exists is True
    assert "fact_choice_macro_daily" in r.tables_used
    assert r.history_count == 65
    assert r.last_trade_date == "2026-04-06"
    assert r.resolved_differs_from_as_of is True
    assert r.stock_ready is False
    assert r.stock_status == "incomplete_catalog"
