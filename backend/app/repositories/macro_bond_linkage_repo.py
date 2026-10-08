from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
import json
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
                ["组合 DV01/CS01 不可用，组合冲击估算保持缺失。"]
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
            cursor = conn.execute(
                """select * from fact_formal_risk_tensor_daily
                   where try_cast(report_date as date) <= ?
                   order by try_cast(report_date as date) desc limit 1""",
                [report_date.isoformat()],
            )
            row = cursor.fetchone()
            if row is not None:
                record = dict(zip([item[0] for item in cursor.description], row))
                resolved = _coerce_date(record["report_date"])
                if resolved != report_date:
                    warnings.append(f"风险张量使用最近日期 {resolved.isoformat()}，目标日期为 {report_date.isoformat()}。")
                inputs = {
                    "portfolio_dv01": _coerce_decimal(record.get("portfolio_dv01")),
                    "portfolio_cs01": _coerce_decimal(record.get("cs01")),
                    "portfolio_market_value": _coerce_decimal(record.get("total_market_value")),
                    "risk_report_date": resolved.isoformat(),
                    "source_table": RELATION_FACT_FORMAL_RISK_TENSOR_DAILY,
                    "source_version": str(record.get("source_version") or EMPTY_SOURCE_VERSION),
                    "rule_version": str(record.get("rule_version") or ""),
                    "coverage": {
                        "basis": "risk_tensor_published_scope",
                        "row_count": record.get("bond_count"),
                        "duration_excluded_count": record.get("duration_excluded_count"),
                        "rate_risk_market_value": _coerce_decimal(record.get("rate_risk_market_value")),
                        "quality_flag": record.get("quality_flag"),
                    },
                    "entities": self._portfolio_entities(conn, resolved),
                    "warnings": warnings,
                }
                raw_warnings = record.get("warnings_json")
                if raw_warnings:
                    try:
                        published_warnings = json.loads(str(raw_warnings))
                        if isinstance(published_warnings, list):
                            warnings.extend(str(item) for item in published_warnings)
                    except (TypeError, ValueError):
                        warnings.append("风险张量质量说明无法解析。")
                if record.get("bond_count") == 0:
                    # The tensor materializer publishes structural zeros for an
                    # empty input set; those are not observed zero sensitivities.
                    for key in ("portfolio_dv01", "portfolio_cs01", "portfolio_market_value"):
                        inputs[key] = None
                    warnings.append("风险张量发布范围为空，组合风险及情景估算不可用。")
                if any(inputs[key] is None for key in ("portfolio_dv01", "portfolio_cs01", "portfolio_market_value")):
                    warnings.append("风险张量存在缺失风险输入，相关情景影响保持缺失。")
                return inputs

        if self._relation_exists_on_conn(conn, RELATION_FACT_FORMAL_BOND_ANALYTICS_DAILY):
            latest = conn.execute(
                """select max(try_cast(report_date as date)) from fact_formal_bond_analytics_daily
                   where try_cast(report_date as date) <= ?""", [report_date.isoformat()],
            ).fetchone()
            resolved = _coerce_date(latest[0]) if latest else None
            if resolved is not None:
                entities = self._portfolio_entities(conn, resolved)
                row_count = len(entities)
                dv01_values = [row["dv01"] for row in entities]
                # An explicit non-credit classification is a known structural zero;
                # an unknown classification or missing credit sensitivity is not.
                cs01_values = [Decimal(0) if row["is_credit"] is False else
                               row["spread_dv01"] if row["is_credit"] is True else None
                               for row in entities]
                market_values = [row["market_value"] for row in entities]
                def complete_sum(values):
                    return sum(values, Decimal(0)) if values and all(v is not None for v in values) else None
                warnings.append(f"风险张量缺失，组合 DV01/CS01 已回退到 {resolved.isoformat()} bond analytics 聚合结果。")
                if any(v is None for v in [*dv01_values, *cs01_values, *market_values]):
                    warnings.append("bond analytics 风险输入覆盖不完整，缺失分项不按零计入组合估算。")
                return {
                    "portfolio_dv01": complete_sum(dv01_values),
                    "portfolio_cs01": complete_sum(cs01_values),
                    "portfolio_market_value": complete_sum(market_values),
                    "risk_report_date": resolved.isoformat(),
                    "source_table": RELATION_FACT_FORMAL_BOND_ANALYTICS_DAILY,
                    "source_version": "__".join(sorted({r["source_version"] for r in entities if r["source_version"]})) or EMPTY_SOURCE_VERSION,
                    "rule_version": "__".join(sorted({r["rule_version"] for r in entities if r["rule_version"]})),
                    "coverage": {
                        "basis": "bond_analytics_row_count",
                        "row_count": row_count,
                        "dv01_observed_count": sum(v is not None for v in dv01_values),
                        "cs01_observed_count": sum(v is not None for v in cs01_values),
                        "market_value_observed_count": sum(v is not None for v in market_values),
                    },
                    "entities": entities,
                    "warnings": warnings,
                }
        return self._unavailable_portfolio_metrics(
            ["组合 DV01/CS01 不可用，组合冲击估算保持缺失。"]
        )

    def _portfolio_entities(self, conn: duckdb.DuckDBPyConnection, report_date: date) -> list[dict[str, Any]]:
        if not self._relation_exists_on_conn(conn, RELATION_FACT_FORMAL_BOND_ANALYTICS_DAILY):
            return []
        cursor = conn.execute(
            """select * from fact_formal_bond_analytics_daily
               where try_cast(report_date as date) = ?
               order by instrument_code, portfolio_name, cost_center, accounting_class, currency_code, source_version""",
            [report_date.isoformat()],
        )
        columns = [item[0] for item in cursor.description]
        entities = []
        for index, row in enumerate(cursor.fetchall()):
            source = dict(zip(columns, row))
            entity = {key: source.get(key) for key in (
                "instrument_code", "instrument_name", "portfolio_name", "cost_center",
                "accounting_class", "currency_code", "is_credit",
            )}
            entity.update({key: _coerce_decimal(source.get(key)) for key in ("dv01", "spread_dv01", "market_value")})
            entity.update({"report_date": report_date.isoformat(),
                           "source_version": str(source.get("source_version") or ""),
                           "rule_version": str(source.get("rule_version") or "")})
            identity = json.dumps([report_date.isoformat(), *[entity[key] for key in (
                "instrument_code", "portfolio_name", "cost_center", "accounting_class", "currency_code", "source_version")], index], ensure_ascii=False)
            entity["entity_id"] = hashlib.sha256(identity.encode()).hexdigest()[:20]
            entities.append(entity)
        return entities

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
            "portfolio_dv01": None,
            "portfolio_cs01": None,
            "portfolio_market_value": None,
            "risk_report_date": None,
            "source_table": None,
            "coverage": {"basis": "unavailable", "row_count": None},
            "entities": [],
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


def _coerce_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (ValueError, ArithmeticError):
        return None
    return number if number.is_finite() else None


def _non_empty_values(values: list[str]) -> list[str]:
    return [value for value in values if str(value).strip()]
