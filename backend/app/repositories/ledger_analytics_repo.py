from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.snapshot_repo import ensure_snapshot_tables
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

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


def ensure_ledger_analytics_tables(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "20_ledger_analytics.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def refresh_position_snapshot_agg(conn: duckdb.DuckDBPyConnection) -> None:
    ensure_ledger_analytics_tables(conn)
    conn.execute(
        """
        insert or replace into position_snapshot_agg (
          batch_id, as_of_date, total_rows, asset_rows, liability_rows,
          asset_face_amount, liability_face_amount, net_face_exposure,
          source_version, rule_version, refreshed_at
        )
        with grouped as (
          select
            batch_id,
            as_of_date,
            count(*)::integer as total_rows,
            sum(case when direction = 'ASSET' then 1 else 0 end)::integer as asset_rows,
            sum(case when direction = 'LIABILITY' then 1 else 0 end)::integer as liability_rows,
            sum(case when direction = 'ASSET' then face_amount end) as asset_face_amount,
            sum(case when direction = 'LIABILITY' then face_amount end) as liability_face_amount,
            max(source_version) as source_version,
            max(rule_version) as rule_version
          from position_snapshot
          group by batch_id, as_of_date
        )
        select
          batch_id,
          as_of_date,
          total_rows,
          asset_rows,
          liability_rows,
          asset_face_amount,
          liability_face_amount,
          case
            when asset_face_amount is null and liability_face_amount is null then null
            else coalesce(asset_face_amount, 0) - coalesce(liability_face_amount, 0)
          end as net_face_exposure,
          source_version,
          rule_version,
          current_timestamp::varchar as refreshed_at
        from grouped
        """
    )
    conn.execute(
        """
        delete from position_snapshot_agg a
        where not exists (
          select 1
          from position_snapshot s
          where s.batch_id = a.batch_id and s.as_of_date = a.as_of_date
        )
        """
    )


@dataclass(slots=True)
class LedgerAnalyticsRepository:
    path: str

    def list_dates(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._prepare(conn)
            if self._has_zqtz_rows(conn):
                rows = conn.execute(
                    """
                    select
                      cast(report_date as varchar) as as_of_date,
                      max(ingest_batch_id) as batch_id,
                      max(source_version) as source_version,
                      max(rule_version) as rule_version,
                      count(*)::integer as total_rows
                    from zqtz_bond_daily_snapshot
                    group by report_date
                    order by report_date desc
                    """
                ).fetchall()
                return [
                    {
                        "as_of_date": str(row[0]),
                        "batch_id": _snapshot_batch_id(row[1], row[0]),
                        "source_version": str(row[2]),
                        "rule_version": str(row[3]),
                        "total_rows": int(row[4]),
                    }
                    for row in rows
                ]

            refresh_position_snapshot_agg(conn)
            rows = conn.execute(
                """
                select a.as_of_date, a.batch_id, a.source_version, a.rule_version, a.total_rows
                from position_snapshot_agg a
                join (
                  select as_of_date, max(batch_id) as batch_id
                  from position_snapshot_agg
                  group by as_of_date
                ) latest using (as_of_date, batch_id)
                order by a.as_of_date desc
                """
            ).fetchall()
        return [
            {
                "as_of_date": str(row[0]),
                "batch_id": int(row[1]),
                "source_version": str(row[2]),
                "rule_version": str(row[3]),
                "total_rows": int(row[4]),
            }
            for row in rows
        ]

    def dashboard(self, *, requested_as_of_date: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            self._prepare(conn)
            if self._has_zqtz_rows(conn):
                return self._dashboard_from_zqtz(conn, requested_as_of_date=requested_as_of_date)

            refresh_position_snapshot_agg(conn)
            resolved = self._resolve_batch(conn, requested_as_of_date=requested_as_of_date)
            if resolved is None:
                return None
            row = conn.execute(
                """
                select
                  batch_id, as_of_date, asset_face_amount, liability_face_amount,
                  net_face_exposure, source_version, rule_version, total_rows
                from position_snapshot_agg
                where batch_id = ? and as_of_date = ?
                """,
                [resolved["batch_id"], resolved["as_of_date"]],
            ).fetchone()
        if row is None:
            return None
        return {
            "batch_id": int(row[0]),
            "as_of_date": str(row[1]),
            "requested_as_of_date": requested_as_of_date,
            "fallback": bool(resolved["fallback"]),
            "stale": bool(resolved["fallback"]),
            "asset_face_amount": _to_100m(row[2]),
            "liability_face_amount": _to_100m(row[3]),
            "net_face_exposure": _to_100m(row[4]),
            "source_version": str(row[5]),
            "rule_version": str(row[6]),
            "total_rows": int(row[7]),
        }

    def list_positions(
        self,
        *,
        requested_as_of_date: str,
        filters: dict[str, str | None],
        limit: int | None,
        offset: int,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            self._prepare(conn)
            if self._has_zqtz_rows(conn):
                return self._list_positions_from_zqtz(
                    conn,
                    requested_as_of_date=requested_as_of_date,
                    filters=filters,
                    limit=limit,
                    offset=offset,
                )

            refresh_position_snapshot_agg(conn)
            resolved = self._resolve_batch(conn, requested_as_of_date=requested_as_of_date)
            if resolved is None:
                return None
            where, params = _position_where(
                batch_id=int(resolved["batch_id"]),
                as_of_date=str(resolved["as_of_date"]),
                filters=filters,
            )
            total = conn.execute(f"select count(*) from position_snapshot where {where}", params).fetchone()[0]
            query = f"""
                select {", ".join(POSITION_EXPORT_COLUMNS)}
                from position_snapshot
                where {where}
                order by row_no
            """
            query_params = list(params)
            if limit is not None:
                query += " limit ? offset ?"
                query_params.extend([limit, offset])
            rows = conn.execute(query, query_params).fetchall()
        return {
            "batch_id": int(resolved["batch_id"]),
            "as_of_date": str(resolved["as_of_date"]),
            "requested_as_of_date": requested_as_of_date,
            "fallback": bool(resolved["fallback"]),
            "stale": bool(resolved["fallback"]),
            "source_version": str(resolved["source_version"]),
            "rule_version": str(resolved["rule_version"]),
            "total": int(total),
            "items": [_position_row(row) for row in rows],
        }

    def _prepare(self, conn: duckdb.DuckDBPyConnection) -> None:
        apply_pending_migrations_on_connection(conn)
        ensure_snapshot_tables(conn)
        ensure_ledger_analytics_tables(conn)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        duckdb_file = Path(self.path)
        duckdb_file.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(duckdb_file), read_only=False)

    @staticmethod
    def _has_zqtz_rows(conn: duckdb.DuckDBPyConnection) -> bool:
        if not _table_exists(conn, "zqtz_bond_daily_snapshot"):
            return False
        row = conn.execute("select count(*) from zqtz_bond_daily_snapshot").fetchone()
        return bool(row and int(row[0]) > 0)

    @staticmethod
    def _resolve_zqtz_date(
        conn: duckdb.DuckDBPyConnection,
        *,
        requested_as_of_date: str,
    ) -> dict[str, Any] | None:
        exact = conn.execute(
            """
            select cast(report_date as varchar), max(ingest_batch_id), max(source_version), max(rule_version)
            from zqtz_bond_daily_snapshot
            where report_date = ?::date
            group by report_date
            limit 1
            """,
            [requested_as_of_date],
        ).fetchone()
        if exact is not None:
            return {
                "as_of_date": str(exact[0]),
                "batch_id": _snapshot_batch_id(exact[1], exact[0]),
                "source_version": str(exact[2]),
                "rule_version": str(exact[3]),
                "fallback": False,
            }
        fallback = conn.execute(
            """
            select cast(report_date as varchar), max(ingest_batch_id), max(source_version), max(rule_version)
            from zqtz_bond_daily_snapshot
            group by report_date
            order by report_date desc
            limit 1
            """
        ).fetchone()
        if fallback is None:
            return None
        return {
            "as_of_date": str(fallback[0]),
            "batch_id": _snapshot_batch_id(fallback[1], fallback[0]),
            "source_version": str(fallback[2]),
            "rule_version": str(fallback[3]),
            "fallback": True,
        }

    def _dashboard_from_zqtz(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        requested_as_of_date: str,
    ) -> dict[str, Any] | None:
        resolved = self._resolve_zqtz_date(conn, requested_as_of_date=requested_as_of_date)
        if resolved is None:
            return None
        row = conn.execute(
            """
            select
              count(*)::integer as total_rows,
              sum(case when not coalesce(is_issuance_like, false) then face_value_native end) as asset_face_amount,
              sum(case when coalesce(is_issuance_like, false) then face_value_native end) as liability_face_amount
            from zqtz_bond_daily_snapshot
            where report_date = ?::date
            """,
            [resolved["as_of_date"]],
        ).fetchone()
        if row is None:
            return None
        asset_face_amount = row[1]
        liability_face_amount = row[2]
        return {
            "batch_id": resolved["batch_id"],
            "as_of_date": str(resolved["as_of_date"]),
            "requested_as_of_date": requested_as_of_date,
            "fallback": bool(resolved["fallback"]),
            "stale": bool(resolved["fallback"]),
            "asset_face_amount": _to_100m(asset_face_amount),
            "liability_face_amount": _to_100m(liability_face_amount),
            "net_face_exposure": _to_100m(_net_face_amount(asset_face_amount, liability_face_amount)),
            "source_version": str(resolved["source_version"]),
            "rule_version": str(resolved["rule_version"]),
            "total_rows": int(row[0]),
        }

    def _list_positions_from_zqtz(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        requested_as_of_date: str,
        filters: dict[str, str | None],
        limit: int | None,
        offset: int,
    ) -> dict[str, Any] | None:
        resolved = self._resolve_zqtz_date(conn, requested_as_of_date=requested_as_of_date)
        if resolved is None:
            return None
        where, params = _zqtz_where(as_of_date=str(resolved["as_of_date"]), filters=filters)
        total = conn.execute(f"select count(*) from zqtz_bond_daily_snapshot where {where}", params).fetchone()[0]
        query = f"""
            with numbered as (
              select
                row_number() over (
                  order by instrument_code, portfolio_name, cost_center, trace_id
                )::integer as row_no,
                *
              from zqtz_bond_daily_snapshot
              where {where}
            )
            select
              coalesce(
                nullif(trace_id, ''),
                concat(
                  'zqtz:', cast(report_date as varchar), ':',
                  coalesce(instrument_code, ''), ':', cast(row_no as varchar)
                )
              ) as position_key,
              coalesce(nullif(ingest_batch_id, ''), concat('zqtz:', cast(report_date as varchar))) as batch_id,
              row_no,
              cast(report_date as varchar) as as_of_date,
              coalesce(instrument_code, '') as bond_code,
              coalesce(instrument_name, '') as bond_name,
              coalesce(portfolio_name, '') as portfolio,
              case when coalesce(is_issuance_like, false) then 'LIABILITY' else 'ASSET' end as direction,
              coalesce(business_type_primary, '') as business_type,
              coalesce(bond_type, '') as business_type_1,
              coalesce(account_category, '') as account_category_std,
              coalesce(cost_center, '') as cost_center,
              coalesce(asset_class, '') as asset_class_std,
              'ZQTZSHOW' as channel,
              coalesce(currency_code, '') as currency,
              face_value_native as face_amount,
              market_value_native as fair_value,
              amortized_cost_native as amortized_cost,
              accrued_interest_native as accrued_interest,
              null as interest_receivable_payable,
              null as quantity,
              null as latest_face_value,
              coalesce(interest_mode, '') as interest_method,
              coupon_rate,
              ytm_value as yield_to_maturity,
              null as interest_start_date,
              cast(maturity_date as varchar) as maturity_date,
              coalesce(issuer_name, '') as counterparty_name_cn,
              coalesce(issuer_name, '') as legal_customer_name,
              '' as group_customer_name
            from numbered
            order by row_no
        """
        query_params = list(params)
        if limit is not None:
            query += " limit ? offset ?"
            query_params.extend([limit, offset])
        rows = conn.execute(query, query_params).fetchall()
        return {
            "batch_id": resolved["batch_id"],
            "as_of_date": str(resolved["as_of_date"]),
            "requested_as_of_date": requested_as_of_date,
            "fallback": bool(resolved["fallback"]),
            "stale": bool(resolved["fallback"]),
            "source_version": str(resolved["source_version"]),
            "rule_version": str(resolved["rule_version"]),
            "total": int(total),
            "items": [_position_row(row) for row in rows],
        }

    @staticmethod
    def _resolve_batch(
        conn: duckdb.DuckDBPyConnection,
        *,
        requested_as_of_date: str,
    ) -> dict[str, Any] | None:
        exact = conn.execute(
            """
            select batch_id, as_of_date, source_version, rule_version
            from position_snapshot_agg
            where as_of_date = ?
            order by batch_id desc
            limit 1
            """,
            [requested_as_of_date],
        ).fetchone()
        if exact is not None:
            return {
                "batch_id": int(exact[0]),
                "as_of_date": str(exact[1]),
                "source_version": str(exact[2]),
                "rule_version": str(exact[3]),
                "fallback": False,
            }
        fallback = conn.execute(
            """
            select batch_id, as_of_date, source_version, rule_version
            from position_snapshot_agg
            order by as_of_date desc, batch_id desc
            limit 1
            """
        ).fetchone()
        if fallback is None:
            return None
        return {
            "batch_id": int(fallback[0]),
            "as_of_date": str(fallback[1]),
            "source_version": str(fallback[2]),
            "rule_version": str(fallback[3]),
            "fallback": True,
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
    return " and ".join(clauses), params


def _zqtz_where(
    *,
    as_of_date: str,
    filters: dict[str, str | None],
) -> tuple[str, list[Any]]:
    clauses = ["report_date = ?::date"]
    params: list[Any] = [as_of_date]
    direction = filters.get("direction")
    if direction == "ASSET":
        clauses.append("not coalesce(is_issuance_like, false)")
    elif direction == "LIABILITY":
        clauses.append("coalesce(is_issuance_like, false)")
    field_map = {
        "bond_code": "instrument_code",
        "portfolio": "portfolio_name",
        "account_category_std": "account_category",
        "asset_class_std": "asset_class",
        "cost_center": "cost_center",
    }
    for filter_name, column_name in field_map.items():
        value = filters.get(filter_name)
        if value is None or value == "":
            continue
        clauses.append(f"{column_name} = ?")
        params.append(value)
    return " and ".join(clauses), params


def _position_row(row: tuple[Any, ...]) -> dict[str, Any]:
    item = dict(zip(POSITION_EXPORT_COLUMNS, row, strict=True))
    item["batch_id"] = item["batch_id"] if isinstance(item["batch_id"], int) else str(item["batch_id"])
    item["row_no"] = int(item["row_no"])
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


def _to_100m(value: object) -> float | None:
    if value is None:
        return None
    return float((Decimal(str(value)) / Decimal("100000000")).quantize(Decimal("0.01")))


def _net_face_amount(asset_face_amount: object, liability_face_amount: object) -> Decimal | None:
    if asset_face_amount is None and liability_face_amount is None:
        return None
    return Decimal(str(asset_face_amount or 0)) - Decimal(str(liability_face_amount or 0))


def _decimal_to_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _snapshot_batch_id(batch_id: object, as_of_date: object) -> str:
    text = str(batch_id or "").strip()
    return text or f"zqtz:{as_of_date}"


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
