from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import duckdb

from backend.scripts import backfill_stock_factor_market_cap_tushare as module


class _FakeFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.empty = not rows

    def __len__(self) -> int:
        return len(self._rows)

    def to_dict(self, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return list(self._rows)


def _create_factor_table(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table choice_stock_factor_snapshot (
              as_of_date varchar, stock_code varchar, pe double, pb double, ps double,
              roe double, gross_margin double, three_month_return double,
              twelve_month_return double, volatility double, dividend_yield double,
              total_mv double, circ_mv double, industry varchar, source_version varchar,
              vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_stock_factor_snapshot values (
              '2026-09-04', '000001.SZ', 8.0, 1.0, 2.0, 0.1, 0.2,
              0.03, 0.08, 0.15, 0.02, null, null, '银行', 'sv_existing',
              'vv_existing', 'rv_existing', 'run_existing'
            )
            """
        )
    finally:
        conn.close()


def test_run_updates_existing_and_inserts_missing_factor_rows(
    tmp_path: Path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "market-cap-backfill.duckdb"
    _create_factor_table(duckdb_path)
    frame = _FakeFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20260904",
                "total_mv": 12.5,
                "circ_mv": 10.0,
            },
            {
                "ts_code": "000002.SZ",
                "trade_date": "20260904",
                "total_mv": 20.0,
                "circ_mv": 16.0,
            },
        ]
    )
    pro = SimpleNamespace(daily_basic=lambda **_kwargs: frame)
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=duckdb_path),
    )
    monkeypatch.setattr(
        module,
        "resolve_tushare_token_with_settings_fallback",
        lambda _settings: "test-token",
    )
    monkeypatch.setattr(
        module,
        "import_tushare_pro",
        lambda: SimpleNamespace(pro_api=lambda _token: pro),
    )

    result = module.run("2026-09-04")

    assert result["updated"] == 1
    assert result["inserted"] == 1
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, total_mv, circ_mv, source_version
            from choice_stock_factor_snapshot
            order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()
    assert rows == [
        ("000001.SZ", 125000.0, 100000.0, "sv_existing"),
        ("000002.SZ", 200000.0, 160000.0, module.SOURCE_VERSION),
    ]
