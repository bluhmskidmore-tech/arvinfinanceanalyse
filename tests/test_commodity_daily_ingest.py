from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import duckdb
import pytest

from backend.app.tasks.commodity_daily_ingest import (
    COMMODITY_PRODUCTS,
    COMMODITY_DAILY_LOCK,
    CommodityProductSpec,
    _estimate_trading_days,
    _fetch_tushare_futures_rows,
    _latest_product_observation,
    _normalize_trade_date,
    _parse_products_arg,
    _records_from_frame,
    ensure_commodity_futures_daily_schema,
    normalize_existing_commodity_trade_dates,
    run_commodity_daily_ingest,
)


class _FakeFrame:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self._records = records

    def __len__(self) -> int:
        return len(self._records)

    def to_dict(self, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return self._records


class _FakePro:
    def trade_cal(self, **kwargs: object) -> _FakeFrame:
        _ = kwargs
        return _FakeFrame(
            [
                {"cal_date": "20240102", "is_open": 1},
                {"cal_date": "20240103", "is_open": 1},
            ]
        )


class _FakeFuturesPro:
    def fut_mapping(self, **kwargs: object) -> _FakeFrame:
        _ = kwargs
        return _FakeFrame(
            [
                {
                    "trade_date": "20240102",
                    "mapping_ts_code": "RB2405.SHF",
                }
            ]
        )

    def fut_daily(self, **kwargs: object) -> _FakeFrame:
        _ = kwargs
        return _FakeFrame(
            [
                {
                    "trade_date": "20240102",
                    "ts_code": "RB2405.SHF",
                    "open": 3900,
                    "high": 3920,
                    "low": 3880,
                    "close": 3910,
                    "settle": 3905,
                    "vol": 12000,
                    "oi": 80000,
                }
            ]
        )


def test_normalize_trade_date_accepts_compact_and_iso() -> None:
    assert _normalize_trade_date("20240102") == "2024-01-02"
    assert _normalize_trade_date("2024-01-02") == "2024-01-02"


def test_records_from_frame_empty() -> None:
    assert _records_from_frame(_FakeFrame([])) == []


def test_estimate_trading_days_prefers_trade_cal() -> None:
    dates = _estimate_trading_days(start_date="2024-01-01", end_date="2024-01-10", pro=_FakePro())
    assert dates == ["2024-01-02", "2024-01-03"]


def test_fetch_tushare_futures_rows_keeps_normalized_trade_date(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.tasks.commodity_daily_ingest.TUSHARE_API_PACE_SECONDS", 0)
    spec = CommodityProductSpec("RB", "rebar", "futures", "SHF", "RB.SHF", "RB0")

    rows = _fetch_tushare_futures_rows(
        spec=spec,
        pro=_FakeFuturesPro(),
        start_date="2024-01-01",
        end_date="2024-01-03",
    )

    assert rows[0]["trade_date"] == "2024-01-02"
    assert rows[0]["contract_code"] == "RB2405.SHF"


def test_normalize_existing_commodity_trade_dates_updates_compact_dates_and_drops_duplicates(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"

    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(
            """
            create table fact_commodity_futures_daily (
              trade_date varchar not null,
              product_code varchar not null,
              contract_code varchar,
              exchange varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              settle_value double,
              volume double,
              open_interest double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar default 'rv_commodity_daily_v1',
              created_at timestamp default current_timestamp,
              primary key (trade_date, product_code)
            )
            """
        )
        conn.executemany(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange, close_value,
              source_version, vendor_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("20240102", "RB", "RB0", "SHF", 3900, "sv_old", "vv_old", "rv_commodity_daily_v1"),
                ("2024-01-02", "RB", "RB0", "SHF", 3901, "sv_new", "vv_new", "rv_commodity_daily_v1"),
                ("20240103", "CU", "CU0", "SHF", 69000, "sv_old", "vv_old", "rv_commodity_daily_v1"),
            ],
        )
    finally:
        conn.close()

    payload = normalize_existing_commodity_trade_dates(str(duckdb_path))

    assert payload == {
        "status": "completed",
        "table": "fact_commodity_futures_daily",
        "duplicate_compact_rows_deleted": 1,
        "compact_rows_updated": 1,
        "invalid_compact_dates": 0,
        "remaining_non_iso_dates": 0,
    }

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select trade_date, product_code, close_value, source_version
            from fact_commodity_futures_daily
            order by trade_date, product_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("2024-01-02", "RB", 3901.0, "sv_new"),
        ("2024-01-03", "CU", 69000.0, "sv_old"),
    ]


def test_normalize_existing_commodity_trade_dates_reuses_ingest_lock(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    calls: list[tuple[str, Path]] = []

    @contextmanager
    def fake_acquire_lock(lock_definition, *, base_dir):
        calls.append((lock_definition.key, Path(base_dir)))
        yield

    monkeypatch.setattr("backend.app.tasks.commodity_daily_ingest.acquire_lock", fake_acquire_lock)

    payload = normalize_existing_commodity_trade_dates(str(duckdb_path))

    assert payload["status"] == "completed"
    assert calls == [(COMMODITY_DAILY_LOCK.key, duckdb_path.parent)]


def test_normalize_existing_commodity_trade_dates_preserves_schema_error(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"

    def fail_schema(_conn) -> None:
        raise RuntimeError("schema boom")

    monkeypatch.setattr("backend.app.tasks.commodity_daily_ingest.ensure_commodity_futures_daily_schema", fail_schema)

    with pytest.raises(RuntimeError, match="schema boom"):
        normalize_existing_commodity_trade_dates(str(duckdb_path))


def test_normalize_existing_commodity_trade_dates_leaves_invalid_compact_dates(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(
            """
            create table fact_commodity_futures_daily (
              trade_date varchar not null,
              product_code varchar not null,
              contract_code varchar,
              exchange varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              settle_value double,
              volume double,
              open_interest double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar default 'rv_commodity_daily_v1',
              created_at timestamp default current_timestamp,
              primary key (trade_date, product_code)
            )
            """
        )
        conn.execute(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange, close_value,
              source_version, vendor_version, rule_version
            ) values ('20241340', 'RB', 'RB0', 'SHF', 3900, 'sv_bad', 'vv_bad', 'rv_commodity_daily_v1')
            """
        )
    finally:
        conn.close()

    payload = normalize_existing_commodity_trade_dates(str(duckdb_path))

    assert payload["duplicate_compact_rows_deleted"] == 0
    assert payload["compact_rows_updated"] == 0
    assert payload["invalid_compact_dates"] == 1
    assert payload["remaining_non_iso_dates"] == 1

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select trade_date, product_code
            from fact_commodity_futures_daily
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("20241340", "RB")]


def test_latest_product_observation_reports_latest_date_value_and_series() -> None:
    rows = [
        {"product_code": "NHCI", "trade_date": "2024-01-02", "close_value": 101.2},
        {"product_code": "NHCI", "trade_date": "2024-01-03", "close_value": 102.4},
    ]

    summary = _latest_product_observation(rows)

    assert summary == {
        "latest_date": "2024-01-03",
        "latest_value": 102.4,
        "series_id": "NHCI.NH",
    }


def test_dry_run_reports_sixteen_products_without_db_write(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "unused.duckdb"))
    monkeypatch.delenv("MOSS_TUSHARE_TOKEN", raising=False)

    payload = run_commodity_daily_ingest(
        start_date="2024-01-01",
        end_date="2024-01-10",
        dry_run=True,
    )

    assert payload["status"] == "dry_run"
    assert payload["product_count"] == len(COMMODITY_PRODUCTS)
    assert len(payload["products"]) == len(COMMODITY_PRODUCTS)
    assert payload["estimated_total_rows"] == len(COMMODITY_PRODUCTS) * int(payload["estimated_trading_days"])
    assert not (tmp_path / "unused.duckdb").exists()
    assert {item.product_code for item in COMMODITY_PRODUCTS} == {
        str(item["product_code"]) for item in payload["products"]
    }


def test_product_specs_include_bond_futures_contracts() -> None:
    specs = {item.product_code: item for item in COMMODITY_PRODUCTS}

    assert specs["TS"].tushare_ts_code == "TS.CFX"
    assert specs["TF"].tushare_ts_code == "TF.CFX"
    assert specs["T"].tushare_ts_code == "T.CFX"
    assert specs["TL"].tushare_ts_code == "TL.CFX"
    assert specs["TS"].akshare_symbol == "TS0"


def test_dry_run_can_limit_to_selected_products(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "unused.duckdb"))
    monkeypatch.delenv("MOSS_TUSHARE_TOKEN", raising=False)

    payload = run_commodity_daily_ingest(
        start_date="2024-01-01",
        end_date="2024-01-10",
        products=("TS", "T"),
        dry_run=True,
    )

    assert payload["product_count"] == 2
    assert [item["product_code"] for item in payload["products"]] == ["TS", "T"]


def test_dry_run_reports_public_macro_series_ids_for_metals(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "unused.duckdb"))
    monkeypatch.delenv("MOSS_TUSHARE_TOKEN", raising=False)

    payload = run_commodity_daily_ingest(
        start_date="2024-01-01",
        end_date="2024-01-10",
        products=("CU", "AL", "RB"),
        dry_run=True,
    )

    series_by_product = {item["product_code"]: item["series_id"] for item in payload["products"]}
    assert series_by_product == {
        "CU": "CA.COPPER",
        "AL": "CA.ALUMINUM",
        "RB": "COMMODITY.RB",
    }


def test_completed_ingest_reports_series_id_when_product_has_no_rows(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.delenv("MOSS_TUSHARE_TOKEN", raising=False)

    def fetch_no_rows(**kwargs: object) -> tuple[list[dict[str, object]], str]:
        _ = kwargs
        return [], "none"

    monkeypatch.setitem(run_commodity_daily_ingest.__globals__, "_fetch_product_rows", fetch_no_rows)

    payload = run_commodity_daily_ingest(
        start_date="2024-01-01",
        end_date="2024-01-10",
        duckdb_path=str(duckdb_path),
        products=("RB",),
        dry_run=False,
    )

    assert payload["status"] == "completed"
    assert payload["row_count"] == 0
    product = payload["products"][0]
    assert product["product_code"] == "RB"
    assert product["row_count"] == 0
    assert product["vendor"] == "none"
    assert product["series_id"] == "COMMODITY.RB"
    assert "latest_date" not in product
    assert "latest_value" not in product


def test_completed_ingest_preserves_unreturned_existing_trade_dates(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.delenv("MOSS_TUSHARE_TOKEN", raising=False)

    conn = duckdb.connect(str(duckdb_path))
    try:
        ensure_commodity_futures_daily_schema(conn)
        conn.executemany(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange, close_value,
              source_version, vendor_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2024-01-02", "RB", "RB0", "SHF", 3900, "sv_old", "vv_old", "rv_commodity_daily_v1"),
                ("2024-01-03", "RB", "RB0", "SHF", 3901, "sv_old", "vv_old", "rv_commodity_daily_v1"),
                ("2024-01-04", "RB", "RB0", "SHF", 3902, "sv_old", "vv_old", "rv_commodity_daily_v1"),
            ],
        )
    finally:
        conn.close()

    fetched_rows = [
        {
            "trade_date": "2024-01-02",
            "product_code": "RB",
            "contract_code": "RB0",
            "exchange": "SHF",
            "close_value": 3910.0,
            "source_version": "sv_new",
            "vendor_version": "vv_new",
            "rule_version": "rv_commodity_daily_v1",
        },
        {
            "trade_date": "2024-01-04",
            "product_code": "RB",
            "contract_code": "RB0",
            "exchange": "SHF",
            "close_value": 3912.0,
            "source_version": "sv_new",
            "vendor_version": "vv_new",
            "rule_version": "rv_commodity_daily_v1",
        },
    ]

    def fetch_sparse_rows(**kwargs: object) -> tuple[list[dict[str, object]], str]:
        assert kwargs["start_date"] == "2024-01-02"
        assert kwargs["end_date"] == "2024-01-04"
        assert kwargs["spec"].product_code == "RB"
        return fetched_rows, "test_vendor"

    monkeypatch.setitem(run_commodity_daily_ingest.__globals__, "_fetch_product_rows", fetch_sparse_rows)

    payload = run_commodity_daily_ingest(
        start_date="2024-01-02",
        end_date="2024-01-04",
        duckdb_path=str(duckdb_path),
        products=("RB",),
        dry_run=False,
    )

    assert payload["row_count"] == 2
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select trade_date, product_code, close_value, source_version
            from fact_commodity_futures_daily
            where product_code = 'RB'
            order by trade_date
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("2024-01-02", "RB", 3910.0, "sv_new"),
        ("2024-01-03", "RB", 3901.0, "sv_old"),
        ("2024-01-04", "RB", 3912.0, "sv_new"),
    ]


def test_dry_run_rejects_explicit_empty_products(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "unused.duckdb"))
    monkeypatch.delenv("MOSS_TUSHARE_TOKEN", raising=False)

    try:
        run_commodity_daily_ingest(
            start_date="2024-01-01",
            end_date="2024-01-10",
            products=(),
            dry_run=True,
        )
    except ValueError as exc:
        assert "At least one commodity product is required" in str(exc)
    else:
        raise AssertionError("explicit empty products should be rejected")

    assert not (tmp_path / "unused.duckdb").exists()


def test_dry_run_rejects_unknown_products(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "unused.duckdb"))
    monkeypatch.delenv("MOSS_TUSHARE_TOKEN", raising=False)

    try:
        run_commodity_daily_ingest(
            start_date="2024-01-01",
            end_date="2024-01-10",
            products=("TS", "BAD"),
            dry_run=True,
        )
    except ValueError as exc:
        assert "Unknown commodity product: BAD" in str(exc)
    else:
        raise AssertionError("unknown products should be rejected")

    assert not (tmp_path / "unused.duckdb").exists()


def test_parse_products_arg_preserves_explicit_empty_selection() -> None:
    assert _parse_products_arg(None) is None
    assert _parse_products_arg("TS, T") == ("TS", "T")
    assert _parse_products_arg("") == ()
    assert _parse_products_arg(" , ") == ()
