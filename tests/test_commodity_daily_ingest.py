from __future__ import annotations

from backend.app.tasks.commodity_daily_ingest import (
    COMMODITY_PRODUCTS,
    CommodityProductSpec,
    _estimate_trading_days,
    _fetch_tushare_futures_rows,
    _latest_product_observation,
    _normalize_trade_date,
    _parse_products_arg,
    _records_from_frame,
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

    monkeypatch.setattr("backend.app.tasks.commodity_daily_ingest._fetch_product_rows", fetch_no_rows)

    payload = run_commodity_daily_ingest(
        start_date="2024-01-01",
        end_date="2024-01-10",
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
