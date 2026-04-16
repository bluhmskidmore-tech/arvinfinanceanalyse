from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb


@dataclass
class MacroBondLinkageRepository:
    path: str

    def load_analysis_inputs(
        self,
        *,
        report_date: date,
        lookback_days: int,
        empty_source_version: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
        conn = self._connect_read_only()
        if conn is None:
            return None

        try:
            macro_inputs = _load_macro_inputs(
                conn,
                report_date=report_date,
                lookback_days=lookback_days,
                empty_source_version=empty_source_version,
            )
            yield_inputs = _load_yield_inputs(
                conn,
                report_date=report_date,
                lookback_days=lookback_days,
            )
            portfolio_metrics = _load_portfolio_metrics(
                conn,
                report_date=report_date,
                empty_source_version=empty_source_version,
            )
            return macro_inputs, yield_inputs, portfolio_metrics
        finally:
            conn.close()

    def _connect_read_only(self) -> duckdb.DuckDBPyConnection | None:
        duckdb_file = Path(self.path)
        if not duckdb_file.exists():
            return None
        try:
            return duckdb.connect(str(duckdb_file), read_only=True)
        except duckdb.Error:
            return None


def _load_macro_inputs(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: date,
    lookback_days: int,
    empty_source_version: str,
) -> dict[str, Any]:
    if not _relation_exists(conn, "fact_choice_macro_daily"):
        return {
            "series": {},
            "latest": {},
            "series_name_map": {},
            "trade_date_count": 0,
            "source_versions": [empty_source_version],
            "vendor_versions": [],
            "rule_versions": [],
        }

    start_date = report_date - timedelta(days=lookback_days + 30)
    rows = conn.execute(
        """
        select
          series_id,
          series_name,
          cast(trade_date as date) as trade_date,
          cast(value_numeric as double) as value_numeric,
          coalesce(source_version, '') as source_version,
          coalesce(vendor_version, '') as vendor_version,
          coalesce(rule_version, '') as rule_version
        from fact_choice_macro_daily
        where cast(trade_date as date) <= ?
          and cast(trade_date as date) >= ?
          and value_numeric is not null
        order by series_id, cast(trade_date as date)
        """,
        [report_date.isoformat(), start_date.isoformat()],
    ).fetchall()

    series: dict[str, list[tuple[date, float]]] = {}
    latest: dict[str, tuple[date, float]] = {}
    series_name_map: dict[str, str] = {}
    trade_dates: set[date] = set()
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    rule_versions: list[str] = []

    for series_id, series_name, trade_date_value, value_numeric, source_version, vendor_version, rule_version in rows:
        series_id_text = str(series_id)
        point_date = _coerce_date(trade_date_value)
        if point_date is None:
            continue
        value = float(value_numeric)
        series.setdefault(series_id_text, []).append((point_date, value))
        latest[series_id_text] = (point_date, value)
        series_name_map[series_id_text] = str(series_name or series_id_text)
        trade_dates.add(point_date)
        source_versions.append(str(source_version))
        vendor_versions.append(str(vendor_version))
        rule_versions.append(str(rule_version))

    return {
        "series": series,
        "latest": latest,
        "series_name_map": series_name_map,
        "trade_date_count": len(trade_dates),
        "source_versions": _non_empty_values(source_versions),
        "vendor_versions": _non_empty_values(vendor_versions),
        "rule_versions": _non_empty_values(rule_versions),
    }


def _load_yield_inputs(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: date,
    lookback_days: int,
) -> dict[str, Any]:
    if not _relation_exists(conn, "fact_formal_yield_curve_daily"):
        return {
            "series": {},
            "source_versions": [],
            "vendor_versions": [],
            "rule_versions": [],
        }

    start_date = report_date - timedelta(days=lookback_days + 30)
    rows = conn.execute(
        """
        select
          cast(trade_date as date) as trade_date,
          curve_type,
          tenor,
          cast(rate_pct as double) as rate_pct,
          coalesce(vendor_version, '') as vendor_version,
          coalesce(source_version, '') as source_version,
          coalesce(rule_version, '') as rule_version
        from fact_formal_yield_curve_daily
        where cast(trade_date as date) <= ?
          and cast(trade_date as date) >= ?
          and rate_pct is not null
        order by cast(trade_date as date), curve_type, tenor
        """,
        [report_date.isoformat(), start_date.isoformat()],
    ).fetchall()

    series: dict[str, list[tuple[date, float]]] = {}
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    rule_versions: list[str] = []
    daily_points: dict[tuple[date, str], dict[str, float]] = {}

    for trade_date_value, curve_type, tenor, rate_pct, vendor_version, source_version, rule_version in rows:
        point_date = _coerce_date(trade_date_value)
        if point_date is None:
            continue
        key = f"{curve_type}_{tenor}"
        series.setdefault(key, []).append((point_date, float(rate_pct)))
        daily_points.setdefault((point_date, str(tenor)), {})[str(curve_type)] = float(rate_pct)
        source_versions.append(str(source_version))
        vendor_versions.append(str(vendor_version))
        rule_versions.append(str(rule_version))

    for (trade_date_value, tenor), point_map in daily_points.items():
        if "aaa_credit" in point_map and "treasury" in point_map:
            spread_key = f"credit_spread_{tenor}"
            spread_value = point_map["aaa_credit"] - point_map["treasury"]
            series.setdefault(spread_key, []).append((trade_date_value, spread_value))

    return {
        "series": series,
        "source_versions": _non_empty_values(source_versions),
        "vendor_versions": _non_empty_values(vendor_versions),
        "rule_versions": _non_empty_values(rule_versions),
    }


def _load_portfolio_metrics(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: date,
    empty_source_version: str,
) -> dict[str, Any]:
    warnings: list[str] = []
    if _relation_exists(conn, "fact_formal_risk_tensor_daily"):
        row = conn.execute(
            """
            select
              cast(portfolio_dv01 as decimal(24, 8)) as portfolio_dv01,
              cast(cs01 as decimal(24, 8)) as cs01,
              cast(total_market_value as decimal(24, 8)) as total_market_value,
              coalesce(source_version, '') as source_version,
              coalesce(rule_version, '') as rule_version
            from fact_formal_risk_tensor_daily
            where report_date = ?
            limit 1
            """,
            [report_date.isoformat()],
        ).fetchone()
        if row is not None:
            return {
                "portfolio_dv01": _coerce_decimal(row[0]),
                "portfolio_cs01": _coerce_decimal(row[1]),
                "portfolio_market_value": _coerce_decimal(row[2]),
                "source_version": str(row[3] or empty_source_version),
                "rule_version": str(row[4] or ""),
                "warnings": warnings,
            }

    if _relation_exists(conn, "fact_formal_bond_analytics_daily"):
        row = conn.execute(
            """
            select
              cast(coalesce(sum(dv01), 0) as decimal(24, 8)) as portfolio_dv01,
              cast(coalesce(sum(case when is_credit then spread_dv01 else 0 end), 0) as decimal(24, 8)) as portfolio_cs01,
              cast(coalesce(sum(market_value), 0) as decimal(24, 8)) as portfolio_market_value,
              coalesce(string_agg(distinct source_version, '__'), '') as source_version,
              coalesce(string_agg(distinct rule_version, '__'), '') as rule_version
            from fact_formal_bond_analytics_daily
            where report_date = ?
            """,
            [report_date.isoformat()],
        ).fetchone()
        warnings.append("风险张量缺失，组合 DV01/CS01 已回退到 bond analytics 聚合结果。")
        return {
            "portfolio_dv01": _coerce_decimal(row[0]),
            "portfolio_cs01": _coerce_decimal(row[1]),
            "portfolio_market_value": _coerce_decimal(row[2]),
            "source_version": str(row[3] or empty_source_version),
            "rule_version": str(row[4] or ""),
            "warnings": warnings,
        }

    warnings.append("组合 DV01/CS01 不可用，组合冲击估算将按 0 返回。")
    return {
        "portfolio_dv01": Decimal("0"),
        "portfolio_cs01": Decimal("0"),
        "portfolio_market_value": Decimal("0"),
        "source_version": empty_source_version,
        "rule_version": "",
        "warnings": warnings,
    }


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


def _non_empty_values(values: list[str]) -> list[str]:
    return [value for value in values if str(value).strip()]


def _coerce_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    return date.fromisoformat(text)


def _coerce_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or "0"))
