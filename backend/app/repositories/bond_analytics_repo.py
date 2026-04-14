from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import duckdb

from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.core_finance.bond_analytics.read_models import (
    build_krd_distribution,
    summarize_accounting_audit,
    summarize_credit,
    summarize_portfolio_risk,
)
from backend.app.core_finance.bond_analytics.engine import BondAnalyticsRow


FACT_TABLE = "fact_formal_bond_analytics_daily"
SNAPSHOT_TABLE = "zqtz_bond_daily_snapshot"
BALANCE_ZQTZ_FACT_TABLE = "fact_formal_zqtz_balance_daily"

_DASHBOARD_ASSET_GROUP_COLUMNS = frozenset({"bond_type", "rating", "portfolio_name", "tenor_bucket"})


@dataclass
class BondAnalyticsRepository:
    path: str

    def list_report_dates(self) -> list[str]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            rows = conn.execute(
                f"""
                select distinct cast(report_date as varchar)
                from {FACT_TABLE}
                order by cast(report_date as varchar) desc
                """
            ).fetchall()
            return [str(row[0]) for row in rows]
        finally:
            conn.close()

    def load_snapshot_rows(self, report_date: str) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, SNAPSHOT_TABLE):
                return []
            rows = conn.execute(
                f"""
                select report_date, instrument_code, instrument_name, portfolio_name, cost_center,
                       account_category, asset_class, bond_type, issuer_name, industry_name, rating,
                       currency_code, face_value_native, market_value_native, amortized_cost_native,
                       accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
                       overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
                       ingest_batch_id, trace_id
                from {SNAPSHOT_TABLE}
                where report_date = ?
                order by instrument_code, portfolio_name, cost_center, currency_code
                """,
                [report_date],
            ).fetchall()
            columns = [
                "report_date",
                "instrument_code",
                "instrument_name",
                "portfolio_name",
                "cost_center",
                "account_category",
                "asset_class",
                "bond_type",
                "issuer_name",
                "industry_name",
                "rating",
                "currency_code",
                "face_value_native",
                "market_value_native",
                "amortized_cost_native",
                "accrued_interest_native",
                "coupon_rate",
                "ytm_value",
                "maturity_date",
                "next_call_date",
                "overdue_days",
                "is_issuance_like",
                "interest_mode",
                "source_version",
                "rule_version",
                "ingest_batch_id",
                "trace_id",
            ]
            return [dict(zip(columns, row, strict=True)) for row in rows]
        finally:
            conn.close()

    def replace_bond_analytics_rows(
        self,
        *,
        report_date: str,
        rows: list[BondAnalyticsRow],
    ) -> None:
        conn = duckdb.connect(self.path, read_only=False)
        try:
            conn.execute("begin transaction")
            ensure_bond_analytics_tables(conn)
            conn.execute(
                f"delete from {FACT_TABLE} where report_date = ?",
                [report_date],
            )
            if rows:
                conn.executemany(
                    f"""
                    insert into {FACT_TABLE} (
                      report_date, instrument_code, instrument_name, portfolio_name, cost_center,
                      asset_class_raw, asset_class_std, bond_type, issuer_name, industry_name, rating,
                      accounting_class, accounting_rule_id, currency_code, face_value, market_value_native, market_value,
                      amortized_cost, accrued_interest, coupon_rate, interest_mode, interest_payment_frequency, interest_rate_style, ytm, maturity_date, next_call_date,
                      years_to_maturity, tenor_bucket, macaulay_duration, modified_duration,
                      convexity, dv01, is_credit, spread_dv01, source_version, rule_version,
                      ingest_batch_id, trace_id
                    ) values (
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    [
                        (
                            row.report_date.isoformat(),
                            row.instrument_code,
                            row.instrument_name,
                            row.portfolio_name,
                            row.cost_center,
                            row.asset_class_raw,
                            row.asset_class_std,
                            row.bond_type,
                            row.issuer_name,
                            row.industry_name,
                            row.rating,
                            row.accounting_class,
                            row.accounting_rule_id,
                            row.currency_code,
                            row.face_value,
                            row.market_value_native,
                            row.market_value,
                            row.amortized_cost,
                            row.accrued_interest,
                            row.coupon_rate,
                            row.interest_mode,
                            row.interest_payment_frequency,
                            row.interest_rate_style,
                            row.ytm,
                            row.maturity_date.isoformat() if row.maturity_date else None,
                            row.next_call_date.isoformat() if row.next_call_date else None,
                            row.years_to_maturity,
                            row.tenor_bucket,
                            row.macaulay_duration,
                            row.modified_duration,
                            row.convexity,
                            row.dv01,
                            row.is_credit,
                            row.spread_dv01,
                            row.source_version,
                            row.rule_version,
                            row.ingest_batch_id,
                            row.trace_id,
                        )
                        for row in rows
                    ],
                )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
        finally:
            conn.close()

    def fetch_bond_analytics_rows(
        self,
        *,
        report_date: str,
        asset_class: str = "all",
        accounting_class: str = "all",
    ) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            interest_mode_expr = (
                "interest_mode"
                if _column_exists(conn, FACT_TABLE, "interest_mode")
                else "'' as interest_mode"
            )
            interest_payment_frequency_expr = (
                "interest_payment_frequency"
                if _column_exists(conn, FACT_TABLE, "interest_payment_frequency")
                else "'annual' as interest_payment_frequency"
            )
            interest_rate_style_expr = (
                "interest_rate_style"
                if _column_exists(conn, FACT_TABLE, "interest_rate_style")
                else "'unknown' as interest_rate_style"
            )
            next_call_date_expr = (
                "next_call_date"
                if _column_exists(conn, FACT_TABLE, "next_call_date")
                else "null as next_call_date"
            )
            market_value_native_expr = (
                "market_value_native"
                if _column_exists(conn, FACT_TABLE, "market_value_native")
                else "null as market_value_native"
            )
            where_parts = ["report_date = ?"]
            params: list[object] = [report_date]
            if asset_class != "all":
                where_parts.append("asset_class_std = ?")
                params.append(asset_class)
            if accounting_class != "all":
                where_parts.append("accounting_class = ?")
                params.append(accounting_class)
            rows = conn.execute(
                f"""
                select report_date, instrument_code, instrument_name, portfolio_name, cost_center,
                       asset_class_raw, asset_class_std, bond_type, issuer_name, industry_name, rating,
                       accounting_class, accounting_rule_id, currency_code, face_value, {market_value_native_expr}, market_value,
                       amortized_cost, accrued_interest, coupon_rate, {interest_mode_expr}, {interest_payment_frequency_expr}, {interest_rate_style_expr}, ytm, maturity_date, {next_call_date_expr},
                       years_to_maturity, tenor_bucket, macaulay_duration, modified_duration,
                       convexity, dv01, is_credit, spread_dv01, source_version, rule_version,
                       ingest_batch_id, trace_id
                from {FACT_TABLE}
                where {' and '.join(where_parts)}
                order by instrument_code
                """,
                params,
            ).fetchall()
            columns = [
                "report_date",
                "instrument_code",
                "instrument_name",
                "portfolio_name",
                "cost_center",
                "asset_class_raw",
                "asset_class_std",
                "bond_type",
                "issuer_name",
                "industry_name",
                "rating",
                "accounting_class",
                "accounting_rule_id",
                "currency_code",
                "face_value",
                "market_value_native",
                "market_value",
                "amortized_cost",
                "accrued_interest",
                "coupon_rate",
                "interest_mode",
                "interest_payment_frequency",
                "interest_rate_style",
                "ytm",
                "maturity_date",
                "next_call_date",
                "years_to_maturity",
                "tenor_bucket",
                "macaulay_duration",
                "modified_duration",
                "convexity",
                "dv01",
                "is_credit",
                "spread_dv01",
                "source_version",
                "rule_version",
                "ingest_batch_id",
                "trace_id",
            ]
            return [dict(zip(columns, row, strict=True)) for row in rows]
        finally:
            conn.close()

    def fetch_portfolio_risk_summary(
        self,
        *,
        report_date: str,
    ) -> dict[str, object]:
        rows = self.fetch_bond_analytics_rows(report_date=report_date)
        return summarize_portfolio_risk(rows)

    def fetch_krd_distribution(
        self,
        *,
        report_date: str,
    ) -> list[dict[str, object]]:
        rows = self.fetch_bond_analytics_rows(report_date=report_date)
        return build_krd_distribution(rows)

    def fetch_credit_summary(
        self,
        *,
        report_date: str,
    ) -> dict[str, object]:
        all_rows = self.fetch_bond_analytics_rows(report_date=report_date)
        credit_rows = self.fetch_bond_analytics_rows(report_date=report_date, asset_class="credit")
        return summarize_credit(credit_rows, total_rows=all_rows)

    def fetch_accounting_audit(
        self,
        *,
        report_date: str,
    ) -> list[dict[str, object]]:
        rows = self.fetch_bond_analytics_rows(report_date=report_date)
        return summarize_accounting_audit(rows)["rows"]

    def fetch_risk_overview_snapshot(self, *, report_date: str) -> dict[str, object] | None:
        conn = _connect_read_only(self.path)
        if conn is None:
            return None
        try:
            if not _table_exists(conn, FACT_TABLE):
                return None
            row = conn.execute(
                f"""
                select
                  cast(report_date as varchar) as report_date,
                  sum(modified_duration * market_value) / nullif(sum(market_value), 0) as portfolio_modified_duration,
                  sum(dv01) as portfolio_dv01,
                  sum(case when is_credit then market_value else 0 end) / nullif(sum(market_value), 0) * 100 as credit_market_value_ratio_pct,
                  sum(years_to_maturity * market_value) / nullif(sum(market_value), 0) as weighted_years_to_maturity
                from {FACT_TABLE}
                where cast(report_date as varchar) = ?
                group by report_date
                """,
                [report_date],
            ).fetchone()
            if row is None or row[0] is None:
                return None
            columns = [
                "report_date",
                "portfolio_modified_duration",
                "portfolio_dv01",
                "credit_market_value_ratio_pct",
                "weighted_years_to_maturity",
            ]
            return dict(zip(columns, row, strict=True))
        finally:
            conn.close()

    def fetch_latest_risk_overview_snapshot(self) -> dict[str, object] | None:
        report_dates = self.list_report_dates()
        if not report_dates:
            return None
        return self.fetch_risk_overview_snapshot(report_date=report_dates[0])

    def resolve_prior_curve_anchor_report_date(self, *, report_date: str) -> str | None:
        conn = _connect_read_only(self.path)
        if conn is None:
            return None
        try:
            if not _table_exists(conn, BALANCE_ZQTZ_FACT_TABLE):
                return None
            row = conn.execute(
                f"""
                select distinct cast(report_date as varchar) as rd
                from {BALANCE_ZQTZ_FACT_TABLE}
                where cast(report_date as varchar) < ?
                  and position_scope = 'asset'
                  and currency_basis = 'CNY'
                order by rd desc
                limit 1
                """,
                [report_date],
            ).fetchone()
            return str(row[0]) if row and row[0] else None
        finally:
            conn.close()

    def fetch_dashboard_headline_kpis(
        self,
        report_date: str,
        prev_report_date: str | None = None,
    ) -> dict[str, object]:
        conn = _connect_read_only(self.path)
        if conn is None:
            empty = _empty_dashboard_headline_kpis_row()
            return {"current": empty, "previous": empty if prev_report_date else None}
        try:
            if not _table_exists(conn, FACT_TABLE):
                empty = _empty_dashboard_headline_kpis_row()
                return {"current": empty, "previous": empty if prev_report_date else None}
            current = _fetch_one_period_headline_kpis(conn, report_date)
            previous = (
                _fetch_one_period_headline_kpis(conn, prev_report_date)
                if prev_report_date
                else None
            )
            return {"current": current, "previous": previous}
        finally:
            conn.close()

    def fetch_dashboard_asset_structure(self, report_date: str, group_by: str) -> list[dict[str, object]]:
        if group_by not in _DASHBOARD_ASSET_GROUP_COLUMNS:
            raise ValueError(
                f"group_by must be one of {sorted(_DASHBOARD_ASSET_GROUP_COLUMNS)}, got {group_by!r}"
            )
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            rows = conn.execute(
                f"""
                select
                  cast({group_by} as varchar) as category,
                  coalesce(sum(market_value), 0) as total_market_value,
                  count(*)::bigint as bond_count
                from {FACT_TABLE}
                where cast(report_date as varchar) = ?
                group by {group_by}
                order by total_market_value desc
                """,
                [report_date],
            ).fetchall()
            return [
                {
                    "category": str(row[0]) if row[0] is not None else "",
                    "total_market_value": row[1],
                    "bond_count": int(row[2]),
                }
                for row in rows
            ]
        finally:
            conn.close()

    def fetch_dashboard_yield_distribution(self, report_date: str) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            rows = conn.execute(
                f"""
                select
                  yield_bucket,
                  coalesce(sum(market_value), 0) as total_market_value,
                  count(*)::bigint as bond_count,
                  min(ytm) as sort_ytm
                from (
                  select
                    market_value,
                    ytm,
                    case
                      when ytm is null then null
                      when ytm < 0.015 then '<1.5%'
                      when ytm < 0.020 then '1.5%-2.0%'
                      when ytm < 0.025 then '2.0%-2.5%'
                      when ytm < 0.030 then '2.5%-3.0%'
                      when ytm < 0.035 then '3.0%-3.5%'
                      when ytm < 0.040 then '3.5%-4.0%'
                      else '>4.0%'
                    end as yield_bucket
                  from {FACT_TABLE}
                  where cast(report_date as varchar) = ?
                    and ytm is not null
                ) t
                where yield_bucket is not null
                group by yield_bucket
                order by sort_ytm
                """,
                [report_date],
            ).fetchall()
            return [
                {
                    "yield_bucket": str(row[0]),
                    "total_market_value": row[1],
                    "bond_count": int(row[2]),
                }
                for row in rows
            ]
        finally:
            conn.close()

    def fetch_dashboard_portfolio_comparison(self, report_date: str) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            rows = conn.execute(
                f"""
                select
                  portfolio_name,
                  coalesce(sum(market_value), 0) as total_market_value,
                  case
                    when coalesce(sum(market_value), 0) > 0
                    then sum(ytm * market_value) / sum(market_value)
                    else 0
                  end as weighted_ytm,
                  case
                    when coalesce(sum(market_value), 0) > 0
                    then sum(modified_duration * market_value) / sum(market_value)
                    else 0
                  end as weighted_duration,
                  coalesce(sum(dv01), 0) as total_dv01,
                  count(*)::bigint as bond_count
                from {FACT_TABLE}
                where cast(report_date as varchar) = ?
                group by portfolio_name
                order by total_market_value desc
                """,
                [report_date],
            ).fetchall()
            return [
                {
                    "portfolio_name": str(row[0]) if row[0] is not None else "",
                    "total_market_value": row[1],
                    "weighted_ytm": row[2],
                    "weighted_duration": row[3],
                    "total_dv01": row[4],
                    "bond_count": int(row[5]),
                }
                for row in rows
            ]
        finally:
            conn.close()

    def fetch_dashboard_spread_by_bond_type(self, report_date: str) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            rows = conn.execute(
                f"""
                select
                  bond_type,
                  median(ytm) as median_yield,
                  count(*)::bigint as bond_count,
                  coalesce(sum(market_value), 0) as total_market_value
                from {FACT_TABLE}
                where cast(report_date as varchar) = ?
                group by bond_type
                order by total_market_value desc
                """,
                [report_date],
            ).fetchall()
            return [
                {
                    "bond_type": str(row[0]) if row[0] is not None else "",
                    "median_yield": row[1],
                    "bond_count": int(row[2]),
                    "total_market_value": row[3],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def fetch_dashboard_maturity_structure(self, report_date: str) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            rows = conn.execute(
                f"""
                select
                  maturity_bucket,
                  coalesce(sum(market_value), 0) as total_market_value,
                  count(*)::bigint as bond_count,
                  min(years_to_maturity) as sort_ytm
                from (
                  select
                    market_value,
                    years_to_maturity,
                    case
                      when years_to_maturity <= 0.0192 then '7天内'
                      when years_to_maturity <= 0.0822 then '8-30天'
                      when years_to_maturity <= 0.2466 then '31-90天'
                      when years_to_maturity <= 0.2740 then '91天-1年'
                      when years_to_maturity <= 3 then '1-3年'
                      when years_to_maturity <= 5 then '3-5年'
                      else '5年以上'
                    end as maturity_bucket
                  from {FACT_TABLE}
                  where cast(report_date as varchar) = ?
                    and years_to_maturity is not null
                ) t
                group by maturity_bucket
                order by sort_ytm
                """,
                [report_date],
            ).fetchall()
            return [
                {
                    "maturity_bucket": str(row[0]),
                    "total_market_value": row[1],
                    "bond_count": int(row[2]),
                }
                for row in rows
            ]
        finally:
            conn.close()

    def fetch_dashboard_industry_distribution(self, report_date: str, top_n: int = 10) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            rows = conn.execute(
                f"""
                select
                  industry_name,
                  coalesce(sum(market_value), 0) as total_market_value,
                  count(*)::bigint as bond_count
                from {FACT_TABLE}
                where cast(report_date as varchar) = ?
                  and industry_name is not null
                  and cast(industry_name as varchar) != ''
                group by industry_name
                order by total_market_value desc
                limit ?
                """,
                [report_date, int(top_n)],
            ).fetchall()
            return [
                {
                    "industry_name": str(row[0]) if row[0] is not None else "",
                    "total_market_value": row[1],
                    "bond_count": int(row[2]),
                }
                for row in rows
            ]
        finally:
            conn.close()

    def fetch_dashboard_risk_indicators(self, report_date: str) -> dict[str, object]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return _empty_dashboard_risk_indicators_row()
        try:
            if not _table_exists(conn, FACT_TABLE):
                return _empty_dashboard_risk_indicators_row()
            row = conn.execute(
                f"""
                select
                  coalesce(sum(market_value), 0) as total_market_value,
                  coalesce(sum(dv01), 0) as total_dv01,
                  case
                    when coalesce(sum(market_value), 0) > 0
                    then sum(modified_duration * market_value) / sum(market_value)
                    else 0
                  end as weighted_duration,
                  case
                    when coalesce(sum(market_value), 0) > 0
                    then sum(case when is_credit then market_value else 0 end) / sum(market_value)
                    else 0
                  end as credit_ratio,
                  case
                    when coalesce(sum(market_value), 0) > 0
                    then sum(convexity * market_value) / sum(market_value)
                    else 0
                  end as weighted_convexity,
                  coalesce(sum(spread_dv01), 0) as total_spread_dv01,
                  case
                    when coalesce(sum(face_value), 0) > 0
                    then sum(case when years_to_maturity <= 1 then face_value else 0 end) / sum(face_value)
                    else 0
                  end as reinvestment_ratio_1y
                from {FACT_TABLE}
                where cast(report_date as varchar) = ?
                """,
                [report_date],
            ).fetchone()
            if row is None:
                return _empty_dashboard_risk_indicators_row()
            keys = (
                "total_market_value",
                "total_dv01",
                "weighted_duration",
                "credit_ratio",
                "weighted_convexity",
                "total_spread_dv01",
                "reinvestment_ratio_1y",
            )
            return _normalize_dashboard_risk_row(dict(zip(keys, row, strict=True)))
        finally:
            conn.close()


def _normalize_dashboard_risk_row(data: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in data.items():
        out[key] = _decimal(value) if value is not None else Decimal("0")
    return out


def _empty_dashboard_headline_kpis_row() -> dict[str, object]:
    z = Decimal("0")
    return {
        "bond_count": 0,
        "total_face_value": z,
        "total_market_value": z,
        "unrealized_pnl": z,
        "total_amortized_cost": z,
        "total_accrued_interest": z,
        "weighted_ytm": z,
        "weighted_duration": z,
        "weighted_coupon": z,
        "credit_spread_median": None,
        "total_dv01": z,
    }


def _fetch_one_period_headline_kpis(
    conn: duckdb.DuckDBPyConnection,
    report_date: str,
) -> dict[str, object]:
    row = conn.execute(
        f"""
        select
          count(*)::bigint as bond_count,
          coalesce(sum(face_value), 0) as total_face_value,
          coalesce(sum(market_value), 0) as total_market_value,
          coalesce(sum(market_value - amortized_cost), 0) as unrealized_pnl,
          coalesce(sum(amortized_cost), 0) as total_amortized_cost,
          coalesce(sum(accrued_interest), 0) as total_accrued_interest,
          case
            when coalesce(sum(market_value), 0) > 0
            then sum(ytm * market_value) / sum(market_value)
            else 0
          end as weighted_ytm,
          case
            when coalesce(sum(market_value), 0) > 0
            then sum(modified_duration * market_value) / sum(market_value)
            else 0
          end as weighted_duration,
          case
            when coalesce(sum(face_value), 0) > 0
            then sum(coupon_rate * face_value) / sum(face_value)
            else 0
          end as weighted_coupon,
          median(case when is_credit then ytm end) as credit_spread_median,
          coalesce(sum(dv01), 0) as total_dv01
        from {FACT_TABLE}
        where cast(report_date as varchar) = ?
        """,
        [report_date],
    ).fetchone()
    if row is None:
        return _empty_dashboard_headline_kpis_row()
    return {
        "bond_count": int(row[0] or 0),
        "total_face_value": _decimal(row[1]),
        "total_market_value": _decimal(row[2]),
        "unrealized_pnl": _decimal(row[3]),
        "total_amortized_cost": _decimal(row[4]),
        "total_accrued_interest": _decimal(row[5]),
        "weighted_ytm": _decimal(row[6]),
        "weighted_duration": _decimal(row[7]),
        "weighted_coupon": _decimal(row[8]),
        "credit_spread_median": None if row[9] is None else _decimal(row[9]),
        "total_dv01": _decimal(row[10]),
    }


def _empty_dashboard_risk_indicators_row() -> dict[str, object]:
    z = Decimal("0")
    return {
        "total_market_value": z,
        "total_dv01": z,
        "weighted_duration": z,
        "credit_ratio": z,
        "weighted_convexity": z,
        "total_spread_dv01": z,
        "reinvestment_ratio_1y": z,
    }


def ensure_bond_analytics_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_name = ?
        limit 1
        """,
        [table_name],
    ).fetchone()
    return row is not None


def _column_exists(conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.columns
        where table_name = ?
          and column_name = ?
        limit 1
        """,
        [table_name, column_name],
    ).fetchone()
    return row is not None


def _connect_read_only(path: str) -> duckdb.DuckDBPyConnection | None:
    try:
        return duckdb.connect(path, read_only=True)
    except duckdb.IOException:
        return None


def _decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _empty_risk_summary() -> dict[str, object]:
    return {
        "bond_count": 0,
        "total_market_value": Decimal("0"),
        "portfolio_duration": Decimal("0"),
        "portfolio_modified_duration": Decimal("0"),
        "portfolio_convexity": Decimal("0"),
        "portfolio_dv01": Decimal("0"),
    }


def _empty_credit_summary() -> dict[str, object]:
    return {
        "total_market_value": Decimal("0"),
        "credit_bond_count": 0,
        "credit_market_value": Decimal("0"),
        "weighted_avg_spread_duration": Decimal("0"),
        "weighted_avg_ytm": Decimal("0"),
        "spread_dv01": Decimal("0"),
        "oci_credit_exposure": Decimal("0"),
        "oci_spread_dv01": Decimal("0"),
        "tpl_spread_dv01": Decimal("0"),
    }
