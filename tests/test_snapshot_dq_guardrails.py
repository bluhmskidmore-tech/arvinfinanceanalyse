from __future__ import annotations

from decimal import Decimal

import pytest

import duckdb

from backend.app.repositories.snapshot_repo import merge_tyw_rows_by_grain, replace_tyw_snapshot_rows


def _tyw_row(*, position_id: str, principal: str, accrued: str = "0", rate: str = "0.015", counterparty: str = "银行A") -> dict[str, object]:
    return {
        "report_date": "2026-02-26",
        "position_id": position_id,
        "product_type": "卖出回购证券",
        "position_side": "liability",
        "counterparty_name": counterparty,
        "account_type": "acct",
        "special_account_type": None,
        "core_customer_type": "银行",
        "currency_code": "CNY",
        "principal_native": Decimal(principal),
        "accrued_interest_native": Decimal(accrued),
        "funding_cost_rate": Decimal(rate),
        "maturity_date": "2026-02-27",
        "pledged_bond_code": None,
        "source_version": "sv",
        "rule_version": "rv",
        "ingest_batch_id": "ib",
        "trace_id": f"trace-{position_id}-{principal}",
    }


def test_merge_tyw_rows_by_grain_sums_duplicate_position_rows() -> None:
    rows = [
        _tyw_row(position_id="3747070", principal="2565000000"),
        _tyw_row(position_id="3747070", principal="435000000"),
    ]

    merged = merge_tyw_rows_by_grain(rows)

    assert len(merged) == 1
    assert merged[0]["position_id"] == "3747070"
    assert merged[0]["principal_native"] == Decimal("3000000000")


def test_merge_tyw_rows_by_grain_fails_closed_on_conflicting_metadata() -> None:
    rows = [
        _tyw_row(position_id="3747070", principal="2565000000", counterparty="国家开发银行"),
        _tyw_row(position_id="3747070", principal="435000000", counterparty="中国农业银行股份有限公司"),
    ]

    with pytest.raises(ValueError, match="conflicting TYW snapshot rows share the same canonical grain"):
        merge_tyw_rows_by_grain(rows)


def test_replace_tyw_snapshot_rows_can_replace_all_rows_for_report_date(tmp_path) -> None:
    db_path = tmp_path / "snapshot.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table tyw_interbank_daily_snapshot (
              report_date date,
              position_id varchar,
              product_type varchar,
              position_side varchar,
              counterparty_name varchar,
              account_type varchar,
              special_account_type varchar,
              core_customer_type varchar,
              currency_code varchar,
              principal_native decimal(24, 8),
              accrued_interest_native decimal(24, 8),
              funding_cost_rate decimal(18, 8),
              maturity_date date,
              pledged_bond_code varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot values
            ('2026-02-26','old-1','同业拆入','liability','银行A','acct',null,'银行','CNY',100,0,0.015,'2026-03-01',null,'sv-old','rv','ib-old','trace-old')
            """
        )

        rows = [_tyw_row(position_id="new-1", principal="200", counterparty="银行B")]
        replace_tyw_snapshot_rows(
            conn,
            rows,
            ingest_batch_ids=["ib-new"],
            report_dates=["2026-02-26"],
            replace_all_for_report_dates=True,
        )

        result = conn.execute(
            "select position_id, ingest_batch_id, principal_native from tyw_interbank_daily_snapshot order by position_id"
        ).fetchall()
    finally:
        conn.close()

    assert result == [("new-1", "ib", 200)]
