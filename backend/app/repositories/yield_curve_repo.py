from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import duckdb

from backend.app.schemas.yield_curve import YieldCurveSnapshot


FORMAL_FACT_TABLE = "fact_formal_yield_curve_daily"
READ_VIEW = "yield_curve_daily"


@dataclass(slots=True)
class YieldCurveRepository:
    path: str

    def fetch_curve(self, trade_date: str, curve_type: str) -> dict[str, Decimal]:
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return {}
        try:
            if not _relation_exists(conn, READ_VIEW):
                return {}
            rows = conn.execute(
                f"""
                select tenor, rate_pct
                from {READ_VIEW}
                where trade_date = ?
                  and curve_type = ?
                order by tenor
                """,
                [trade_date, curve_type],
            ).fetchall()
            return {str(tenor): Decimal(str(rate_pct)) for tenor, rate_pct in rows}
        finally:
            conn.close()

    def fetch_latest_trade_date(self, curve_type: str) -> str | None:
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return None
        try:
            if not _relation_exists(conn, READ_VIEW):
                return None
            row = conn.execute(
                f"""
                select max(cast(trade_date as varchar))
                from {READ_VIEW}
                where curve_type = ?
                """,
                [curve_type],
            ).fetchone()
            if row is None or row[0] in (None, ""):
                return None
            return str(row[0])
        finally:
            conn.close()

    def fetch_latest_trade_date_on_or_before(self, curve_type: str, trade_date: str) -> str | None:
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return None
        try:
            if not _relation_exists(conn, READ_VIEW):
                return None
            row = conn.execute(
                f"""
                select max(cast(trade_date as varchar))
                from {READ_VIEW}
                where curve_type = ?
                  and cast(trade_date as varchar) <= ?
                """,
                [curve_type, trade_date],
            ).fetchone()
            if row is None or row[0] in (None, ""):
                return None
            return str(row[0])
        finally:
            conn.close()

    def list_trade_dates(self, curve_type: str) -> list[str]:
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return []
        try:
            if not _relation_exists(conn, READ_VIEW):
                return []
            rows = conn.execute(
                f"""
                select distinct cast(trade_date as varchar)
                from {READ_VIEW}
                where curve_type = ?
                order by cast(trade_date as varchar) desc
                """,
                [curve_type],
            ).fetchall()
            return [str(row[0]) for row in rows]
        finally:
            conn.close()

    def fetch_curve_snapshot(self, trade_date: str, curve_type: str) -> dict[str, object] | None:
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return None
        try:
            if not _relation_exists(conn, FORMAL_FACT_TABLE):
                return None
            rows = conn.execute(
                f"""
                select tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version
                from {FORMAL_FACT_TABLE}
                where trade_date = ?
                  and curve_type = ?
                order by tenor
                """,
                [trade_date, curve_type],
            ).fetchall()
            if not rows:
                return None
            first = rows[0]
            vendor_name = str(first[2] or "")
            vendor_version = str(first[3] or "")
            source_version = str(first[4] or "")
            rule_version = str(first[5] or "")
            for row in rows[1:]:
                if (
                    str(row[2] or "") != vendor_name
                    or str(row[3] or "") != vendor_version
                    or str(row[4] or "") != source_version
                    or str(row[5] or "") != rule_version
                ):
                    return None
            curve = {
                str(tenor): Decimal(str(rate_pct))
                for tenor, rate_pct, _vn, _vv, _sv, _rv in rows
            }
            return {
                "trade_date": trade_date,
                "curve_type": curve_type,
                "curve": curve,
                "vendor_name": vendor_name,
                "vendor_version": vendor_version,
                "source_version": source_version,
                "rule_version": rule_version,
            }
        finally:
            conn.close()

    def replace_curve_snapshots(self, *, trade_date: str, snapshots: list[YieldCurveSnapshot], rule_version: str) -> None:
        conn = duckdb.connect(self.path, read_only=False)
        try:
            conn.execute("begin transaction")
            ensure_yield_curve_tables(conn)
            curve_types = sorted({snapshot.curve_type for snapshot in snapshots})
            if curve_types:
                conn.executemany(
                    f"delete from {FORMAL_FACT_TABLE} where trade_date = ? and curve_type = ?",
                    [(trade_date, curve_type) for curve_type in curve_types],
                )
            rows: list[tuple[object, ...]] = []
            for snapshot in snapshots:
                for point in snapshot.points:
                    rows.append(
                        (
                            snapshot.trade_date,
                            snapshot.curve_type,
                            point.tenor,
                            point.rate_pct,
                            snapshot.vendor_name,
                            snapshot.vendor_version,
                            snapshot.source_version,
                            rule_version,
                        )
                    )
            if rows:
                conn.executemany(
                    f"""
                    insert into {FORMAL_FACT_TABLE} (
                      trade_date,
                      curve_type,
                      tenor,
                      rate_pct,
                      vendor_name,
                      vendor_version,
                      source_version,
                      rule_version
                    ) values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
        finally:
            conn.close()


def ensure_yield_curve_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        f"""
        create table if not exists {FORMAL_FACT_TABLE} (
            trade_date varchar,
            curve_type varchar,
            tenor varchar,
            rate_pct decimal(18, 8),
            vendor_name varchar,
            vendor_version varchar,
            source_version varchar,
            rule_version varchar
        )
        """
    )
    conn.execute(
        f"""
        create or replace view {READ_VIEW} as
        select
          trade_date,
          curve_type,
          tenor,
          rate_pct,
          vendor_name,
          vendor_version,
          source_version
        from {FORMAL_FACT_TABLE}
        """
    )


def _connect(path: str, *, read_only: bool) -> duckdb.DuckDBPyConnection | None:
    try:
        return duckdb.connect(path, read_only=read_only)
    except duckdb.Error:
        return None


def _relation_exists(conn: duckdb.DuckDBPyConnection, relation_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_name = ?
        union all
        select 1
        from information_schema.views
        where table_name = ?
        limit 1
        """,
        [relation_name, relation_name],
    ).fetchone()
    return row is not None
