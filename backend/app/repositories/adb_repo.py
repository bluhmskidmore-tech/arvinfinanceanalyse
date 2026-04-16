from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd


_BONDS_COLUMNS = [
    "report_date",
    "market_value",
    "yield_to_maturity",
    "coupon_rate",
    "interest_rate",
    "asset_class",
    "sub_type",
    "is_issuance_like",
]

_INTERBANK_COLUMNS = [
    "report_date",
    "amount",
    "interest_rate",
    "product_type",
    "direction",
]


@dataclass
class AdbRepository:
    duckdb_path: str

    def load_raw_data(
        self,
        start_date: date,
        end_date: date,
    ) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
        if not Path(self.duckdb_path).exists():
            return _empty_bonds_df(), _empty_interbank_df(), [], []

        zqtz_asset_rows: list[dict[str, object]] = []
        zqtz_liability_rows: list[dict[str, object]] = []
        tyw_asset_rows: list[dict[str, object]] = []
        tyw_liability_rows: list[dict[str, object]] = []

        conn = _conn_ro(self.duckdb_path)
        try:
            if _table_exists(conn, "fact_formal_zqtz_balance_daily"):
                zqtz_rows = _fetch_formal_zqtz_rows(conn, start_date, end_date)
                concrete_zqtz_rows = [
                    row for row in zqtz_rows if str(row.get("position_scope") or "").lower() in {"asset", "liability"}
                ]
                scoped_zqtz_rows = concrete_zqtz_rows if concrete_zqtz_rows else zqtz_rows
                for row in scoped_zqtz_rows:
                    position_scope = str(row.get("position_scope") or "").lower()
                    if position_scope == "liability" or bool(row.get("is_issuance_like")):
                        zqtz_liability_rows.append(row)
                    else:
                        zqtz_asset_rows.append(row)

            if _table_exists(conn, "fact_formal_tyw_balance_daily"):
                tyw_rows = _fetch_formal_tyw_rows(conn, start_date, end_date)
                concrete_tyw_rows = [
                    row for row in tyw_rows if str(row.get("position_scope") or "").lower() in {"asset", "liability"}
                ]
                scoped_tyw_rows = concrete_tyw_rows if concrete_tyw_rows else tyw_rows
                for row in scoped_tyw_rows:
                    position_scope = str(row.get("position_scope") or "").lower()
                    position_side_raw = str(row.get("position_side") or "")
                    position_side = position_side_raw.lower()
                    is_asset = position_scope == "asset" or (
                        position_scope not in {"asset", "liability"}
                        and ("asset" in position_side or "资产" in position_side_raw)
                    )
                    if is_asset:
                        tyw_asset_rows.append(row)
                    else:
                        tyw_liability_rows.append(row)
        finally:
            conn.close()

        source_versions = [
            *[str(row.get("source_version") or "") for row in zqtz_asset_rows],
            *[str(row.get("source_version") or "") for row in zqtz_liability_rows],
            *[str(row.get("source_version") or "") for row in tyw_asset_rows],
            *[str(row.get("source_version") or "") for row in tyw_liability_rows],
        ]
        rule_versions = [
            *[str(row.get("rule_version") or "") for row in zqtz_asset_rows],
            *[str(row.get("rule_version") or "") for row in zqtz_liability_rows],
            *[str(row.get("rule_version") or "") for row in tyw_asset_rows],
            *[str(row.get("rule_version") or "") for row in tyw_liability_rows],
        ]

        bonds_df = pd.DataFrame(
            [
                {
                    "report_date": row["report_date"],
                    "market_value": row["market_value_amount"],
                    "yield_to_maturity": row["ytm_value"],
                    "coupon_rate": row["coupon_rate"],
                    "interest_rate": 0.0,
                    "asset_class": row.get("asset_class") or "",
                    "sub_type": row.get("bond_type") or "",
                    "is_issuance_like": False,
                }
                for row in zqtz_asset_rows
            ]
            + [
                {
                    "report_date": row["report_date"],
                    "market_value": row["market_value_amount"],
                    "yield_to_maturity": row["ytm_value"],
                    "coupon_rate": row["coupon_rate"],
                    "interest_rate": 0.0,
                    "asset_class": row.get("asset_class") or "",
                    "sub_type": row.get("bond_type") or "",
                    "is_issuance_like": True,
                }
                for row in zqtz_liability_rows
            ],
            columns=_BONDS_COLUMNS,
        )
        interbank_df = pd.DataFrame(
            [
                {
                    "report_date": row["report_date"],
                    "amount": row["principal_amount"],
                    "interest_rate": row["funding_cost_rate"],
                    "product_type": row.get("product_type") or "",
                    "direction": "ASSET",
                }
                for row in tyw_asset_rows
            ]
            + [
                {
                    "report_date": row["report_date"],
                    "amount": row["principal_amount"],
                    "interest_rate": row["funding_cost_rate"],
                    "product_type": row.get("product_type") or "",
                    "direction": "LIABILITY",
                }
                for row in tyw_liability_rows
            ],
            columns=_INTERBANK_COLUMNS,
        )

        _normalize_bonds_df(bonds_df)
        _normalize_interbank_df(interbank_df)
        return bonds_df, interbank_df, source_versions, rule_versions


def _empty_bonds_df() -> pd.DataFrame:
    return pd.DataFrame(columns=_BONDS_COLUMNS)


def _empty_interbank_df() -> pd.DataFrame:
    return pd.DataFrame(columns=_INTERBANK_COLUMNS)


def _normalize_bonds_df(bonds_df: pd.DataFrame) -> None:
    if bonds_df.empty:
        return
    bonds_df["report_date"] = pd.to_datetime(bonds_df["report_date"])
    for column in ("market_value", "yield_to_maturity", "coupon_rate", "interest_rate"):
        bonds_df[column] = pd.to_numeric(bonds_df[column], errors="coerce").fillna(0.0)
    bonds_df["is_issuance_like"] = bonds_df["is_issuance_like"].fillna(False).astype(bool)


def _normalize_interbank_df(interbank_df: pd.DataFrame) -> None:
    if interbank_df.empty:
        return
    interbank_df["report_date"] = pd.to_datetime(interbank_df["report_date"])
    for column in ("amount", "interest_rate"):
        interbank_df[column] = pd.to_numeric(interbank_df[column], errors="coerce").fillna(0.0)


def _conn_ro(path: str) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(path, read_only=True)


def _table_exists(conn: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_name = ?
        limit 1
        """,
        [name],
    ).fetchone()
    return row is not None


def _dict_from_row(description: list[tuple], row: tuple) -> dict[str, object]:
    return {str(column[0]): value for column, value in zip(description, row, strict=True)}


def _fetch_formal_zqtz_rows(
    conn: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
) -> list[dict[str, object]]:
    cursor = conn.execute(
        """
        select
          report_date,
          position_scope,
          currency_basis,
          market_value_amount,
          ytm_value,
          coupon_rate,
          asset_class,
          bond_type,
          is_issuance_like,
          source_version,
          rule_version
        from fact_formal_zqtz_balance_daily
        where cast(report_date as date) between ? and ?
          and currency_basis = 'CNY'
        """,
        [start_date, end_date],
    )
    description = list(cursor.description or [])
    return [_dict_from_row(description, row) for row in cursor.fetchall()]


def _fetch_formal_tyw_rows(
    conn: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
) -> list[dict[str, object]]:
    cursor = conn.execute(
        """
        select
          report_date,
          position_scope,
          position_side,
          currency_basis,
          principal_amount,
          funding_cost_rate,
          product_type,
          source_version,
          rule_version
        from fact_formal_tyw_balance_daily
        where cast(report_date as date) between ? and ?
          and currency_basis = 'CNY'
        """,
        [start_date, end_date],
    )
    description = list(cursor.description or [])
    return [_dict_from_row(description, row) for row in cursor.fetchall()]
