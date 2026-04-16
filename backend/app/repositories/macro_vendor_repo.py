from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb


@dataclass
class MacroVendorRepository:
    path: str

    def list_macro_vendor_catalog_rows(self) -> list[tuple[object, ...]]:
        def _query(conn: duckdb.DuckDBPyConnection, tables: set[str]) -> list[tuple[object, ...]]:
            if "phase1_macro_vendor_catalog" not in tables:
                return []

            available_columns = {
                str(row[1])
                for row in conn.execute("pragma table_info('phase1_macro_vendor_catalog')").fetchall()
            }
            select_columns = [
                "series_id",
                "series_name",
                "vendor_name",
                "vendor_version",
                "frequency",
                "unit",
                _catalog_column_expr("refresh_tier", available_columns, "NULL"),
                _catalog_column_expr("fetch_mode", available_columns, "NULL"),
                _catalog_column_expr("fetch_granularity", available_columns, "NULL"),
                _catalog_column_expr("policy_note", available_columns, "NULL"),
            ]
            return conn.execute(
                f"""
                select
                  {", ".join(select_columns)}
                from phase1_macro_vendor_catalog
                order by vendor_name, series_id
                """
            ).fetchall()

        return self._read_with_tables(_query, [])

    def list_macro_vendor_source_versions(self, series_ids: list[str]) -> list[str]:
        if not series_ids:
            return []

        def _query(conn: duckdb.DuckDBPyConnection, tables: set[str]) -> list[str]:
            if "choice_market_snapshot" not in tables:
                return []

            placeholders = ", ".join(["?"] * len(series_ids))
            rows = conn.execute(
                f"""
                select distinct source_version
                from choice_market_snapshot
                where series_id in ({placeholders})
                  and source_version is not null and source_version <> ''
                order by source_version
                """,
                series_ids,
            ).fetchall()
            return [str(row[0]) for row in rows if row and row[0]]

        return self._read_with_tables(_query, [])

    def list_choice_macro_recent_rows(self) -> list[tuple[object, ...]]:
        def _query(conn: duckdb.DuckDBPyConnection, tables: set[str]) -> list[tuple[object, ...]]:
            if "fact_choice_macro_daily" not in tables:
                return []
            return _load_choice_macro_recent_rows(conn, tables)

        return self._read_with_tables(_query, [])

    def load_choice_macro_catalog_map(self) -> dict[str, dict[str, object]]:
        return self._read_with_tables(_load_choice_macro_catalog_map, {})

    def load_choice_macro_series_name_map(self) -> dict[str, str]:
        def _query(conn: duckdb.DuckDBPyConnection, tables: set[str]) -> dict[str, str]:
            if "phase1_macro_vendor_catalog" not in tables:
                return {}

            return {
                str(row[0]): str(row[1])
                for row in conn.execute(
                    """
                    select distinct series_id, series_name
                    from phase1_macro_vendor_catalog
                    """
                ).fetchall()
            }

        return self._read_with_tables(_query, {})

    def load_latest_fx_mid_rows(
        self,
        *,
        base_currencies: list[str],
    ) -> dict[tuple[str, str], dict[str, object]]:
        if not base_currencies:
            return {}

        def _query(
            conn: duckdb.DuckDBPyConnection,
            tables: set[str],
        ) -> dict[tuple[str, str], dict[str, object]]:
            if "fx_daily_mid" not in tables:
                return {}

            placeholders = ", ".join(["?"] * len(base_currencies))
            rows = conn.execute(
                f"""
                with ranked as (
                  select
                    base_currency,
                    quote_currency,
                    cast(trade_date as varchar) as trade_date,
                    cast(observed_trade_date as varchar) as observed_trade_date,
                    cast(mid_rate as double) as mid_rate,
                    source_name,
                    coalesce(vendor_name, '') as vendor_name,
                    coalesce(vendor_version, '') as vendor_version,
                    source_version,
                    is_business_day,
                    is_carry_forward,
                    row_number() over (
                      partition by upper(base_currency), upper(quote_currency)
                      order by trade_date desc
                    ) as rn
                  from fx_daily_mid
                  where upper(base_currency) in ({placeholders})
                    and upper(quote_currency) = 'CNY'
                )
                select
                  base_currency,
                  quote_currency,
                  trade_date,
                  observed_trade_date,
                  mid_rate,
                  source_name,
                  vendor_name,
                  vendor_version,
                  source_version,
                  is_business_day,
                  is_carry_forward
                from ranked
                where rn = 1
                """,
                [item.upper() for item in base_currencies],
            ).fetchall()

            result: dict[tuple[str, str], dict[str, object]] = {}
            for row in rows:
                key = (str(row[0]).upper(), str(row[1]).upper())
                result[key] = {
                    "base_currency": str(row[0]).upper(),
                    "quote_currency": str(row[1]).upper(),
                    "trade_date": str(row[2]) if row[2] is not None else None,
                    "observed_trade_date": str(row[3]) if row[3] is not None else None,
                    "mid_rate": float(row[4]) if row[4] is not None else None,
                    "source_name": str(row[5]) if row[5] is not None else None,
                    "vendor_name": str(row[6]) if row[6] is not None else None,
                    "vendor_version": str(row[7]) if row[7] is not None else None,
                    "source_version": str(row[8]) if row[8] is not None else None,
                    "is_business_day": bool(row[9]) if row[9] is not None else None,
                    "is_carry_forward": bool(row[10]) if row[10] is not None else None,
                }
            return result

        return self._read_with_tables(_query, {})

    def _read_with_tables(
        self,
        query: Any,
        default: Any,
    ) -> Any:
        duckdb_file = Path(self.path)
        if not duckdb_file.exists():
            return default

        try:
            conn = duckdb.connect(str(duckdb_file), read_only=True)
        except duckdb.Error:
            return default

        try:
            tables = {row[0] for row in conn.execute("show tables").fetchall()}
            return query(conn, tables)
        except duckdb.Error:
            return default
        finally:
            conn.close()


def _load_choice_macro_recent_rows(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
) -> list[tuple[object, ...]]:
    if "choice_market_snapshot" in tables:
        snapshot_count = conn.execute(
            "select count(*) from choice_market_snapshot"
        ).fetchone()
        if snapshot_count and int(snapshot_count[0]) > 0:
            return conn.execute(
                """
                with active_series as (
                  select distinct series_id
                  from choice_market_snapshot
                ),
                ranked as (
                  select
                    fact.series_id,
                    fact.series_name,
                    fact.trade_date,
                    fact.value_numeric,
                    fact.frequency,
                    fact.unit,
                    fact.source_version,
                    fact.vendor_version,
                    fact.quality_flag,
                    row_number() over(partition by fact.series_id order by fact.trade_date desc) as rn
                  from fact_choice_macro_daily as fact
                  inner join active_series on active_series.series_id = fact.series_id
                )
                select
                  series_id,
                  series_name,
                  trade_date,
                  value_numeric,
                  frequency,
                  unit,
                  source_version,
                  vendor_version,
                  quality_flag,
                  rn
                from ranked
                where rn <= 3
                order by series_id, rn
                """
            ).fetchall()

    return conn.execute(
        """
        with ranked as (
          select
            series_id,
            series_name,
            trade_date,
            value_numeric,
            frequency,
            unit,
            source_version,
            vendor_version,
            quality_flag,
            row_number() over(partition by series_id order by trade_date desc) as rn
          from fact_choice_macro_daily
        )
        select
          series_id,
          series_name,
          trade_date,
          value_numeric,
          frequency,
          unit,
          source_version,
          vendor_version,
          quality_flag,
          rn
        from ranked
        where rn <= 3
        order by series_id, rn
        """
    ).fetchall()


def _load_choice_macro_catalog_map(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
) -> dict[str, dict[str, object]]:
    if "phase1_macro_vendor_catalog" not in tables:
        return {}

    available_columns = {
        str(row[1])
        for row in conn.execute("pragma table_info('phase1_macro_vendor_catalog')").fetchall()
    }
    select_columns = [
        "series_id",
        _catalog_column_expr("refresh_tier", available_columns, "NULL"),
        _catalog_column_expr("fetch_mode", available_columns, "NULL"),
        _catalog_column_expr("fetch_granularity", available_columns, "NULL"),
        _catalog_column_expr("policy_note", available_columns, "NULL"),
        "frequency",
        "unit",
    ]
    rows = conn.execute(
        f"""
        select
          {", ".join(select_columns)}
        from phase1_macro_vendor_catalog
        """
    ).fetchall()

    catalog_by_series: dict[str, dict[str, object]] = {}
    for (
        series_id,
        refresh_tier,
        fetch_mode,
        fetch_granularity,
        policy_note,
        frequency,
        unit,
    ) in rows:
        catalog_by_series[str(series_id)] = {
            "refresh_tier": _as_optional_string(refresh_tier),
            "fetch_mode": _as_optional_string(fetch_mode),
            "fetch_granularity": _as_optional_string(fetch_granularity),
            "policy_note": _as_optional_string(policy_note),
            "frequency": str(frequency or ""),
            "unit": str(unit or ""),
        }
    return catalog_by_series


def _catalog_column_expr(column: str, available_columns: set[str], fallback_sql: str) -> str:
    if column in available_columns:
        return column
    return f"{fallback_sql} as {column}"


def _as_optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
