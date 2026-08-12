from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import duckdb

from backend.app.repositories.duckdb_repo import DuckDBRepository, read_only_connection

RELATION_FACT_CHOICE_MACRO_DAILY = "fact_choice_macro_daily"
RELATION_FACT_FORMAL_YIELD_CURVE_DAILY = "fact_formal_yield_curve_daily"
RELATION_FACT_FORMAL_RISK_TENSOR_DAILY = "fact_formal_risk_tensor_daily"
RELATION_FACT_FORMAL_BOND_ANALYTICS_DAILY = "fact_formal_bond_analytics_daily"
RELATION_CHOICE_MARKET_SNAPSHOT = "choice_market_snapshot"

_MACRO_BOND_LINKAGE_READ_RELATIONS = frozenset(
    {
        RELATION_FACT_CHOICE_MACRO_DAILY,
        RELATION_FACT_FORMAL_YIELD_CURVE_DAILY,
        RELATION_FACT_FORMAL_RISK_TENSOR_DAILY,
        RELATION_FACT_FORMAL_BOND_ANALYTICS_DAILY,
        RELATION_CHOICE_MARKET_SNAPSHOT,
    }
)

EMPTY_SOURCE_VERSION = "sv_macro_bond_linkage_empty"
LOOKBACK_DAYS = 365


class MacroBondLinkageRepository(DuckDBRepository):
    """Read-only macro-bond linkage inputs via shared DuckDB helpers.

    Owns the cross-domain join surface used by ``macro_bond_linkage_service``:
    Choice macro daily, formal yield curve, risk tensor / bond analytics fallback,
    and Choice market snapshot equity axes. Table names are whitelist-gated.
    """

    def relation_exists(
        self,
        relation_name: str,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> bool:
        if relation_name not in _MACRO_BOND_LINKAGE_READ_RELATIONS:
            return False
        if conn is not None:
            return self._relation_exists_on_conn(conn, relation_name)
        try:
            with read_only_connection(self.path) as scoped:
                return self._relation_exists_on_conn(scoped, relation_name)
        except (OSError, duckdb.Error):
            return False

    def load_macro_inputs(
        self,
        report_date: date,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> dict[str, Any]:
        if conn is not None:
            return self._load_macro_inputs_impl(conn, report_date)
        try:
            with read_only_connection(self.path) as scoped:
                return self._load_macro_inputs_impl(scoped, report_date)
        except (OSError, duckdb.Error):
            return self._empty_macro_inputs()

    def load_yield_inputs(
        self,
        report_date: date,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> dict[str, Any]:
        if conn is not None:
            return self._load_yield_inputs_impl(conn, report_date)
        try:
            with read_only_connection(self.path) as scoped:
                return self._load_yield_inputs_impl(scoped, report_date)
        except (OSError, duckdb.Error):
            return self._empty_yield_inputs()

    def load_portfolio_metrics(
        self,
        report_date: date,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> dict[str, Any]:
        if conn is not None:
            return self._load_portfolio_metrics_impl(conn, report_date)
        try:
            with read_only_connection(self.path) as scoped:
                return self._load_portfolio_metrics_impl(scoped, report_date)
        except (OSError, duckdb.Error):
            return self._unavailable_portfolio_metrics(
                ["组合 DV01/CS01 不可用，组合冲击估算将按 0 返回。"]
            )

    def fetch_equity_axis_latest_rows(
        self,
        report_date: date,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> tuple[list[tuple[Any, ...]], str | None]:
        """Return latest equity-axis snapshot rows, or ``([], warning)`` on query failure."""
        if conn is not None:
            return self._fetch_equity_axis_latest_rows_impl(conn, report_date)
        with self.scoped_connection() as scoped:
            if scoped is None:
                return [], None
            return self._fetch_equity_axis_latest_rows_impl(scoped, report_date)

    def _load_macro_inputs_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        report_date: date,
    ) -> dict[str, Any]:
        if not self._relation_exists_on_conn(conn, RELATION_FACT_CHOICE_MACRO_DAILY):
            return self._empty_macro_inputs()

        start_date = report_date - timedelta(days=LOOKBACK_DAYS + 30)
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

        for (
            series_id,
            series_name,
            trade_date_value,
            value_numeric,
            source_version,
            vendor_version,
            rule_version,
        ) in rows:
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

    def _load_yield_inputs_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        report_date: date,
    ) -> dict[str, Any]:
        if not self._relation_exists_on_conn(conn, RELATION_FACT_FORMAL_YIELD_CURVE_DAILY):
            return self._empty_yield_inputs()

        start_date = report_date - timedelta(days=LOOKBACK_DAYS + 30)
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

        for (
            trade_date_value,
            curve_type,
            tenor,
            rate_pct,
            vendor_version,
            source_version,
            rule_version,
        ) in rows:
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

    def _load_portfolio_metrics_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        report_date: date,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        if self._relation_exists_on_conn(conn, RELATION_FACT_FORMAL_RISK_TENSOR_DAILY):
            row = conn.execute(
                """
                select
                  cast(report_date as date) as resolved_report_date,
                  cast(portfolio_dv01 as decimal(24, 8)) as portfolio_dv01,
                  cast(cs01 as decimal(24, 8)) as cs01,
                  cast(total_market_value as decimal(24, 8)) as total_market_value,
                  coalesce(source_version, '') as source_version,
                  coalesce(rule_version, '') as rule_version
                from fact_formal_risk_tensor_daily
                where try_cast(report_date as date) <= ?
                order by try_cast(report_date as date) desc
                limit 1
                """,
                [report_date.isoformat()],
            ).fetchone()
            if row is not None:
                resolved_report_date = _coerce_date(row[0])
                if resolved_report_date is not None and resolved_report_date != report_date:
                    warnings.append(
                        f"风险张量使用最近日期 {resolved_report_date.isoformat()}，目标日期为 {report_date.isoformat()}。"
                    )
                return {
                    "portfolio_dv01": _coerce_decimal(row[1]),
                    "portfolio_cs01": _coerce_decimal(row[2]),
                    "portfolio_market_value": _coerce_decimal(row[3]),
                    "source_version": str(row[4] or EMPTY_SOURCE_VERSION),
                    "rule_version": str(row[5] or ""),
                    "warnings": warnings,
                }

        if self._relation_exists_on_conn(conn, RELATION_FACT_FORMAL_BOND_ANALYTICS_DAILY):
            row = conn.execute(
                """
                with latest as (
                  select max(try_cast(report_date as date)) as resolved_report_date
                  from fact_formal_bond_analytics_daily
                  where try_cast(report_date as date) <= ?
                )
                select
                  latest.resolved_report_date,
                  cast(coalesce(sum(dv01), 0) as decimal(24, 8)) as portfolio_dv01,
                  cast(coalesce(sum(case when is_credit then spread_dv01 else 0 end), 0) as decimal(24, 8)) as portfolio_cs01,
                  cast(coalesce(sum(market_value), 0) as decimal(24, 8)) as portfolio_market_value,
                  coalesce(string_agg(distinct source_version, '__'), '') as source_version,
                  coalesce(string_agg(distinct rule_version, '__'), '') as rule_version
                from fact_formal_bond_analytics_daily, latest
                where try_cast(fact_formal_bond_analytics_daily.report_date as date) = latest.resolved_report_date
                group by latest.resolved_report_date
                """,
                [report_date.isoformat()],
            ).fetchone()
            if row is None:
                row = (None, Decimal("0"), Decimal("0"), Decimal("0"), EMPTY_SOURCE_VERSION, "")
            resolved_report_date = _coerce_date(row[0])
            if resolved_report_date is None:
                warnings.append("风险张量缺失，且 bond analytics 未提供可用组合 DV01/CS01。")
            elif resolved_report_date == report_date:
                warnings.append("风险张量缺失，组合 DV01/CS01 已回退到 bond analytics 聚合结果。")
            else:
                warnings.append(
                    "风险张量缺失，组合 DV01/CS01 已回退到 "
                    f"{resolved_report_date.isoformat()} bond analytics 聚合结果。"
                )
            return {
                "portfolio_dv01": _coerce_decimal(row[1]),
                "portfolio_cs01": _coerce_decimal(row[2]),
                "portfolio_market_value": _coerce_decimal(row[3]),
                "source_version": str(row[4] or EMPTY_SOURCE_VERSION),
                "rule_version": str(row[5] or ""),
                "warnings": warnings,
            }

        return self._unavailable_portfolio_metrics(
            ["组合 DV01/CS01 不可用，组合冲击估算将按 0 返回。"]
        )

    def _fetch_equity_axis_latest_rows_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        report_date: date,
    ) -> tuple[list[tuple[Any, ...]], str | None]:
        if not self._relation_exists_on_conn(conn, RELATION_CHOICE_MARKET_SNAPSHOT):
            return [], None
        try:
            rows = conn.execute(
                """
                select series_id, cast(trade_date as date) as trade_date, cast(value_numeric as double) as value_numeric
                from (
                  select
                    series_id,
                    trade_date,
                    value_numeric,
                    row_number() over (partition by series_id order by cast(trade_date as date) desc) as rn
                  from choice_market_snapshot
                  where series_id in (
                    'CA.CSI300',
                    'CA.CSI300_PCT_CHG',
                    'CA.CSI300_PE',
                    'CA.MEGA_CAP_WEIGHT',
                    'CA.MEGA_CAP_TOP5_WEIGHT',
                    'E1000180',
                    'EMM00166466'
                  )
                    and cast(trade_date as date) <= ?
                    and value_numeric is not null
                )
                where rn = 1
                """,
                [report_date.isoformat()],
            ).fetchall()
        except duckdb.Error as exc:
            return [], f"choice_market_snapshot equity axes unavailable: {exc}"
        return list(rows), None

    @staticmethod
    def _relation_exists_on_conn(conn: duckdb.DuckDBPyConnection, relation_name: str) -> bool:
        if relation_name not in _MACRO_BOND_LINKAGE_READ_RELATIONS:
            return False
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

    @staticmethod
    def _empty_macro_inputs() -> dict[str, Any]:
        return {
            "series": {},
            "latest": {},
            "series_name_map": {},
            "trade_date_count": 0,
            "source_versions": [EMPTY_SOURCE_VERSION],
            "vendor_versions": [],
            "rule_versions": [],
        }

    @staticmethod
    def _empty_yield_inputs() -> dict[str, Any]:
        return {
            "series": {},
            "source_versions": [],
            "vendor_versions": [],
            "rule_versions": [],
        }

    @staticmethod
    def _unavailable_portfolio_metrics(warnings: list[str]) -> dict[str, Any]:
        return {
            "portfolio_dv01": Decimal("0"),
            "portfolio_cs01": Decimal("0"),
            "portfolio_market_value": Decimal("0"),
            "source_version": EMPTY_SOURCE_VERSION,
            "rule_version": "",
            "warnings": warnings,
        }


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


def _non_empty_values(values: list[str]) -> list[str]:
    return [value for value in values if str(value).strip()]
