from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance.ledger_classification import (
    LEDGER_CLASSIFICATION_RULE_VERSION,
)

_CLASSIFICATION_RULE_ROLLUP_SQL = """
case
  when count(*) filter (where rule_version is distinct from ?) = 0
    then ?
  when count(distinct coalesce(rule_version, '__NULL__')) = 1
    then max(rule_version)
  else 'mixed'
end as rule_version,
count(*) filter (where rule_version is distinct from ?) = 0
  as classification_ready
"""
_CLASSIFICATION_RULE_ROLLUP_PARAMS = (
    LEDGER_CLASSIFICATION_RULE_VERSION,
    LEDGER_CLASSIFICATION_RULE_VERSION,
    LEDGER_CLASSIFICATION_RULE_VERSION,
)

POSITION_EXPORT_COLUMNS = (
    "position_key",
    "batch_id",
    "row_no",
    "as_of_date",
    "bond_code",
    "bond_name",
    "portfolio",
    "direction",
    "business_type",
    "business_type_1",
    "account_category_std",
    "cost_center",
    "asset_class_std",
    "channel",
    "currency",
    "face_amount",
    "fair_value",
    "amortized_cost",
    "accrued_interest",
    "interest_receivable_payable",
    "quantity",
    "latest_face_value",
    "interest_method",
    "coupon_rate",
    "yield_to_maturity",
    "interest_start_date",
    "maturity_date",
    "counterparty_name_cn",
    "legal_customer_name",
    "group_customer_name",
)


@dataclass(slots=True)
class LedgerAnalyticsRepository:
    path: str

    def list_dates(self) -> list[dict[str, Any]]:
        if not self._database_exists():
            return []
        with self._connect() as conn:
            if not _table_exists(conn, "position_snapshot"):
                return []
            rows = conn.execute(
                f"""
                select
                  s.as_of_date,
                  s.batch_id,
                  max(s.source_version) as source_version,
                  {_CLASSIFICATION_RULE_ROLLUP_SQL},
                  count(*)::integer as total_rows
                from position_snapshot s
                join (
                  select as_of_date, max(batch_id) as batch_id
                  from position_snapshot
                  group by as_of_date
                ) latest
                  on s.as_of_date = latest.as_of_date
                 and s.batch_id = latest.batch_id
                group by s.as_of_date, s.batch_id
                order by s.as_of_date desc
                """,
                _CLASSIFICATION_RULE_ROLLUP_PARAMS,
            ).fetchall()
        return [
            {
                "as_of_date": str(row[0]),
                "batch_id": int(row[1]),
                "source_version": str(row[2]),
                "rule_version": str(row[3] or "__NULL__"),
                "classification_ready": bool(row[4]),
                "total_rows": int(row[5]),
            }
            for row in rows
        ]

    def dashboard(
        self,
        *,
        requested_as_of_date: str,
    ) -> dict[str, Any] | None:
        if not self._database_exists():
            return None
        with self._connect() as conn:
            resolved = self._resolve_batch(conn, requested_as_of_date=requested_as_of_date)
            if resolved is None:
                return None
            rows = conn.execute(
                """
                select
                  coalesce(nullif(upper(trim(currency)), ''), 'UNKNOWN') as currency,
                  sum(case when direction = 'ASSET' then face_amount end),
                  sum(case when direction = 'LIABILITY' then face_amount end),
                  count(*)::integer,
                  count(*) filter (where direction = 'UNCLASSIFIED')::integer,
                  sum(case when direction = 'UNCLASSIFIED' then face_amount end),
                  count(*) filter (where direction in ('ASSET', 'LIABILITY'))::integer
                from position_snapshot
                where batch_id = ? and as_of_date = ?
                group by 1
                order by 1
                """,
                [resolved["batch_id"], resolved["as_of_date"]],
            ).fetchall()
        if not bool(resolved["classification_ready"]):
            classification_status = "legacy_unassessed"
        elif not bool(resolved["materialization_valid"]):
            classification_status = "invalid_materialization"
        else:
            classification_status = "ready"
        metrics_ready = classification_status == "ready"
        return {
            **resolved,
            "requested_as_of_date": requested_as_of_date,
            "stale": bool(resolved["fallback"]),
            "classification_status": classification_status,
            "classification_rule_version": LEDGER_CLASSIFICATION_RULE_VERSION,
            "currency_breakdown": [
                _currency_breakdown(row, classification_ready=metrics_ready)
                for row in rows
            ],
        }

    def list_positions(
        self,
        *,
        requested_as_of_date: str,
        filters: dict[str, str | None],
        limit: int | None,
        offset: int,
    ) -> dict[str, Any] | None:
        if not self._database_exists():
            return None
        with self._connect() as conn:
            resolved = self._resolve_batch(conn, requested_as_of_date=requested_as_of_date)
            if resolved is None:
                return None
            where, params = _position_where(
                batch_id=int(resolved["batch_id"]),
                as_of_date=str(resolved["as_of_date"]),
                filters=filters,
            )
            total = conn.execute(
                f"select count(*) from position_snapshot where {where}",
                params,
            ).fetchone()[0]
            query = f"""
                select {", ".join(POSITION_EXPORT_COLUMNS)}
                from position_snapshot where {where} order by row_no
            """
            query_params = list(params)
            if limit is not None:
                query += " limit ? offset ?"
                query_params.extend([limit, offset])
            rows = conn.execute(query, query_params).fetchall()
        return {
            **resolved,
            "requested_as_of_date": requested_as_of_date,
            "stale": bool(resolved["fallback"]),
            "total": int(total),
            "items": [_position_row(row) for row in rows],
        }

    def _database_exists(self) -> bool:
        return Path(self.path).is_file()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(Path(self.path)), read_only=True)

    @staticmethod
    def _resolve_batch(
        conn: duckdb.DuckDBPyConnection,
        *,
        requested_as_of_date: str,
    ) -> dict[str, Any] | None:
        if not _table_exists(conn, "position_snapshot"):
            return None
        row = conn.execute(
            f"""
            select batch_id, as_of_date, source_version, rule_version, classification_ready, materialization_valid
            from (
              select
                batch_id,
                as_of_date,
                max(source_version) as source_version,
                {_CLASSIFICATION_RULE_ROLLUP_SQL},
                count(*) filter (
                  where direction is null
                     or direction not in ('ASSET', 'LIABILITY', 'UNCLASSIFIED')
                ) = 0 as materialization_valid
              from position_snapshot
              where as_of_date <= ?
              group by batch_id, as_of_date
            )
            order by as_of_date desc, batch_id desc
            limit 1
            """,
            [*_CLASSIFICATION_RULE_ROLLUP_PARAMS, requested_as_of_date],
        ).fetchone()
        if row is None:
            return None
        resolved_date = str(row[1])
        return {
            "batch_id": int(row[0]),
            "as_of_date": resolved_date,
            "source_version": str(row[2]),
            "rule_version": str(row[3] or "__NULL__"),
            "classification_ready": bool(row[4]),
            "materialization_valid": bool(row[5]),
            "fallback": resolved_date != requested_as_of_date,
        }


def _position_where(
    *,
    batch_id: int,
    as_of_date: str,
    filters: dict[str, str | None],
) -> tuple[str, list[Any]]:
    clauses = ["batch_id = ?", "as_of_date = ?"]
    params: list[Any] = [batch_id, as_of_date]
    for field in (
        "direction",
        "bond_code",
        "portfolio",
        "account_category_std",
        "asset_class_std",
        "cost_center",
    ):
        value = filters.get(field)
        if value is None or value == "":
            continue
        clauses.append(f"{field} = ?")
        params.append(value)
    currency = filters.get("currency")
    if currency:
        clauses.append("coalesce(nullif(upper(trim(currency)), ''), 'UNKNOWN') = ?")
        params.append(currency)
    return " and ".join(clauses), params


def _position_row(row: tuple[Any, ...]) -> dict[str, Any]:
    item = dict(zip(POSITION_EXPORT_COLUMNS, row, strict=True))
    item["batch_id"] = (
        item["batch_id"]
        if isinstance(item["batch_id"], int)
        else str(item["batch_id"])
    )
    item["row_no"] = int(item["row_no"])
    item["currency"] = str(item.get("currency") or "").strip().upper() or "UNKNOWN"
    for field in (
        "face_amount",
        "fair_value",
        "amortized_cost",
        "accrued_interest",
        "interest_receivable_payable",
        "quantity",
        "latest_face_value",
        "coupon_rate",
        "yield_to_maturity",
    ):
        item[field] = _decimal_to_float(item[field])
    return item


def _currency_breakdown(
    row: tuple[Any, ...],
    *,
    classification_ready: bool,
) -> dict[str, object]:
    total_rows = int(row[3])
    if not classification_ready:
        return {
            "currency": str(row[0]),
            "asset_face_amount": None,
            "liability_face_amount": None,
            "net_face_exposure": None,
            "classification_total_row_count": total_rows,
            "unclassified_row_count": None,
            "unclassified_face_amount": None,
            "classification_coverage_pct": None,
        }
    unclassified_rows = int(row[4])
    classified_rows = int(row[6])
    return {
        "currency": str(row[0]),
        "asset_face_amount": _to_100m(row[1]),
        "liability_face_amount": _to_100m(row[2]),
        "net_face_exposure": _to_100m(_net_face_amount(row[1], row[2])),
        "classification_total_row_count": total_rows,
        "unclassified_row_count": unclassified_rows,
        "unclassified_face_amount": (
            0.0 if unclassified_rows == 0 else _to_100m(row[5])
        ),
        "classification_coverage_pct": round(
            classified_rows / total_rows * 100,
            2,
        ),
    }

def _to_100m(value: object) -> float | None:
    if value is None:
        return None
    return float((Decimal(str(value)) / Decimal("100000000")).quantize(Decimal("0.01")))


def _net_face_amount(
    asset_face_amount: object,
    liability_face_amount: object,
) -> Decimal | None:
    if asset_face_amount is None and liability_face_amount is None:
        return None
    return Decimal(str(asset_face_amount or 0)) - Decimal(str(liability_face_amount or 0))


def _decimal_to_float(value: object) -> float | None:
    return None if value is None else float(value)


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_schema = 'main' and table_name = ?
        limit 1
        """,
        [table_name],
    ).fetchone()
    return row is not None
