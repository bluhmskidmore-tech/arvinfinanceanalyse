from __future__ import annotations

from backend.app.tasks.commodity_daily_ingest import (
    COMMODITY_PRODUCTS,
    CommodityProductSpec,
    _estimate_trading_days,
    _fetch_tushare_futures_rows,
    _normalize_trade_date,
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
