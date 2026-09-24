from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
from backend.app.core_finance.liability_analytics_compat import to_float

FORMAL_ZQTZ_YIELD_COLUMNS = {
    "report_date",
    "instrument_code",
    "instrument_name",
    "portfolio_name",
    "asset_class",
    "bond_type",
    "invest_type_std",
    "position_scope",
    "currency_basis",
    "currency_code",
    "face_value_amount",
    "market_value_amount",
    "amortized_cost_amount",
    "coupon_rate",
    "ytm_value",
    "maturity_date",
    "source_version",
    "rule_version",
}

IB_ASSET_PREDICATE = (
    "(instr(lower(coalesce(position_side, '')), 'asset') > 0 "
    "or instr(coalesce(position_side, ''), '资产') > 0)"
)


NCD_TEXT = "\u540c\u4e1a\u5b58\u5355"
TRADING_TEXT = "\u4ea4\u6613"
RECEIVABLE_INVESTMENT_TEXT = "\u5e94\u6536\u6295\u8d44"


@dataclass
class LiabilityAnalyticsRepository:
    path: str

    def _connect(self) -> duckdb.DuckDBPyConnection | None:
        if not Path(self.path).exists():
            return None
        return duckdb.connect(self.path, read_only=True)

    def _table_exists(self, conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
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

    def _table_columns(self, conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
        rows = conn.execute(f"pragma table_info('{table_name}')").fetchall()
        return {str(row[1]) for row in rows}

    def _formal_zqtz_yield_read_available(self, conn: duckdb.DuckDBPyConnection) -> bool:
        if not self._table_exists(conn, "fact_formal_zqtz_balance_daily"):
            return False
        return FORMAL_ZQTZ_YIELD_COLUMNS.issubset(
            self._table_columns(conn, "fact_formal_zqtz_balance_daily")
        )

    @staticmethod
    def _group_rows_by_report_date(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row["report_date"]), []).append(row)
        return grouped

    @staticmethod
    def _fetch_dict_rows(
        conn: duckdb.DuckDBPyConnection,
        query: str,
        params: list[object] | None = None,
    ) -> list[dict[str, Any]]:
        cursor = conn.execute(query, params or [])
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

    def _fetch_snapshot_zqtz_yield_rows_for_dates(
        self,
        conn: duckdb.DuckDBPyConnection,
        dates: list[str],
    ) -> list[dict[str, Any]]:
        if not dates or not self._table_exists(conn, "zqtz_bond_daily_snapshot"):
            return []
        placeholders = ", ".join(["?::date"] * len(dates))
        return self._fetch_dict_rows(
            conn,
            f"""
            select report_date, instrument_name, asset_class, bond_type, is_issuance_like,
                   face_value_native, market_value_native, amortized_cost_native,
                   coupon_rate, ytm_value, source_version, rule_version
            from zqtz_bond_daily_snapshot
            where report_date in ({placeholders})
            order by report_date desc
            """,
            dates,
        )

    def _fetch_snapshot_zqtz_rows_for_dates(
        self,
        conn: duckdb.DuckDBPyConnection,
        dates: list[str],
    ) -> list[dict[str, Any]]:
        if not dates or not self._table_exists(conn, "zqtz_bond_daily_snapshot"):
            return []
        placeholders = ", ".join(["?::date"] * len(dates))
        return self._fetch_dict_rows(
            conn,
            f"""
            select report_date, instrument_code, instrument_name, asset_class, bond_type, is_issuance_like,
                   face_value_native, market_value_native, amortized_cost_native,
                   coupon_rate, ytm_value, maturity_date, source_version, rule_version,
                   cast(NULL as varchar) as asset_type
            from zqtz_bond_daily_snapshot
            where report_date in ({placeholders})
            order by report_date desc, instrument_code
            """,
            dates,
        )

    def _fetch_zqtz_rows_for_dates_with_connection(
        self,
        conn: duckdb.DuckDBPyConnection,
        dates: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        formal_rows = self._fetch_formal_zqtz_cny_yield_rows_for_dates(conn, dates)
        rows_by_date = self._group_rows_by_report_date(formal_rows)
        missing_dates = [d for d in dates if d not in rows_by_date]
        if missing_dates:
            snapshot_rows = self._fetch_snapshot_zqtz_rows_for_dates(conn, missing_dates)
            rows_by_date.update(self._group_rows_by_report_date(snapshot_rows))
        return rows_by_date

    def _fetch_formal_zqtz_cny_yield_rows_for_dates(
        self,
        conn: duckdb.DuckDBPyConnection,
        dates: list[str],
    ) -> list[dict[str, Any]]:
        if not dates or not self._formal_zqtz_yield_read_available(conn):
            return []
        placeholders = ", ".join(["?::date"] * len(dates))
        return self._fetch_dict_rows(
            conn,
            f"""
            select cast(report_date as varchar) as report_date,
                   instrument_code,
                   instrument_name,
                   asset_class,
                   invest_type_std as asset_type,
                   bond_type,
                   case when position_scope = 'liability' then true else false end as is_issuance_like,
                   face_value_amount as face_value_native,
                   market_value_amount as market_value_native,
                   amortized_cost_amount as amortized_cost_native,
                   coupon_rate,
                   ytm_value,
                   maturity_date,
                   source_version,
                   rule_version
            from fact_formal_zqtz_balance_daily
            where report_date in ({placeholders})
              and currency_basis = 'CNY'
              and position_scope in ('asset', 'liability')
            order by report_date desc, instrument_code
            """,
            dates,
        )

    def _fetch_zqtz_yield_rows_for_dates_with_connection(
        self,
        conn: duckdb.DuckDBPyConnection,
        dates: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        formal_rows = self._fetch_formal_zqtz_cny_yield_rows_for_dates(conn, dates)
        rows_by_date = self._group_rows_by_report_date(formal_rows)
        missing_dates = [d for d in dates if d not in rows_by_date]
        if missing_dates:
            snapshot_rows = self._fetch_snapshot_zqtz_yield_rows_for_dates(conn, missing_dates)
            rows_by_date.update(self._group_rows_by_report_date(snapshot_rows))
        return rows_by_date

    def resolve_latest_report_date(self) -> str | None:
        conn = self._connect()
        if conn is None:
            return None
        try:
            candidates: list[str] = []
            if self._table_exists(conn, "zqtz_bond_daily_snapshot"):
                row = conn.execute(
                    "select cast(max(report_date) as varchar) from zqtz_bond_daily_snapshot"
                ).fetchone()
                if row and row[0]:
                    candidates.append(str(row[0]))
            if self._table_exists(conn, "tyw_interbank_daily_snapshot"):
                row = conn.execute(
                    "select cast(max(report_date) as varchar) from tyw_interbank_daily_snapshot"
                ).fetchone()
                if row and row[0]:
                    candidates.append(str(row[0]))
            if not candidates:
                return None
            return max(candidates)
        finally:
            conn.close()

    def list_report_dates(self) -> list[str]:
        conn = self._connect()
        if conn is None:
            return []
        try:
            dates: set[str] = set()
            if self._table_exists(conn, "zqtz_bond_daily_snapshot"):
                dates.update(
                    str(row[0])
                    for row in conn.execute(
                        """
                        select distinct cast(report_date as varchar)
                        from zqtz_bond_daily_snapshot
                        order by cast(report_date as varchar) desc
                        """
                    ).fetchall()
                    if row[0]
                )
            if self._table_exists(conn, "tyw_interbank_daily_snapshot"):
                dates.update(
                    str(row[0])
                    for row in conn.execute(
                        """
                        select distinct cast(report_date as varchar)
                        from tyw_interbank_daily_snapshot
                        order by cast(report_date as varchar) desc
                        """
                    ).fetchall()
                    if row[0]
                )
            return sorted(dates, reverse=True)
        finally:
            conn.close()

    def fetch_zqtz_rows(self, report_date: str) -> list[dict[str, Any]]:
        return self.fetch_zqtz_rows_for_dates([report_date]).get(str(report_date).strip(), [])

    def fetch_zqtz_rows_for_dates(self, report_dates: list[str]) -> dict[str, list[dict[str, Any]]]:
        dates = [str(d).strip() for d in report_dates if str(d or "").strip()]
        if not dates:
            return {}
        conn = self._connect()
        if conn is None:
            return {}
        try:
            return self._fetch_zqtz_rows_for_dates_with_connection(conn, dates)
        finally:
            conn.close()

    def fetch_zqtz_yield_rows_for_dates(self, report_dates: list[str]) -> dict[str, list[dict[str, Any]]]:
        dates = [str(d).strip() for d in report_dates if str(d or "").strip()]
        if not dates:
            return {}
        conn = self._connect()
        if conn is None:
            return {}
        try:
            return self._fetch_zqtz_yield_rows_for_dates_with_connection(conn, dates)
        finally:
            conn.close()

    def fetch_zqtz_yield_rows(self, report_date: str) -> list[dict[str, Any]]:
        return self.fetch_zqtz_yield_rows_for_dates([report_date]).get(str(report_date), [])

    def fetch_tyw_rows(self, report_date: str) -> list[dict[str, Any]]:
        conn = self._connect()
        if conn is None:
            return []
        try:
            if not self._table_exists(conn, "tyw_interbank_daily_snapshot"):
                return []
            return self._fetch_dict_rows(
                conn,
                f"""
                select report_date, position_id, product_type, position_side, counterparty_name,
                       core_customer_type, principal_native, funding_cost_rate, maturity_date,
                       source_version, rule_version,
                       case when {IB_ASSET_PREDICATE} then true else false end as is_asset_side
                from tyw_interbank_daily_snapshot
                where report_date = ?::date
                """,
                [report_date],
            )
        finally:
            conn.close()

    def fetch_tyw_rows_for_dates(self, report_dates: list[str]) -> dict[str, list[dict[str, Any]]]:
        dates = [str(d).strip() for d in report_dates if str(d or "").strip()]
        if not dates:
            return {}
        conn = self._connect()
        if conn is None:
            return {}
        try:
            if not self._table_exists(conn, "tyw_interbank_daily_snapshot"):
                return {}
            placeholders = ", ".join(["?::date"] * len(dates))
            rows = self._fetch_dict_rows(
                conn,
                f"""
                select report_date, position_id, product_type, position_side, counterparty_name,
                       core_customer_type, principal_native, funding_cost_rate, maturity_date,
                       source_version, rule_version,
                       case when {IB_ASSET_PREDICATE} then true else false end as is_asset_side
                from tyw_interbank_daily_snapshot
                where report_date in ({placeholders})
                order by report_date desc, position_id
                """,
                dates,
            )
        finally:
            conn.close()
        return self._group_rows_by_report_date(rows)

    def fetch_tyw_yield_rows_for_dates(self, report_dates: list[str]) -> dict[str, list[dict[str, Any]]]:
        dates = [str(d).strip() for d in report_dates if str(d or "").strip()]
        if not dates:
            return {}
        conn = self._connect()
        if conn is None:
            return {}
        try:
            if not self._table_exists(conn, "tyw_interbank_daily_snapshot"):
                return {}
            placeholders = ", ".join(["?::date"] * len(dates))
            rows = self._fetch_dict_rows(
                conn,
                f"""
                select report_date, principal_native, funding_cost_rate, source_version, rule_version,
                       case when {IB_ASSET_PREDICATE} then true else false end as is_asset_side
                from tyw_interbank_daily_snapshot
                where report_date in ({placeholders})
                order by report_date desc
                """,
                dates,
            )
        finally:
            conn.close()
        return self._group_rows_by_report_date(rows)

    def fetch_yield_rows_for_dates(
        self,
        report_dates: list[str],
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
        dates = [str(d).strip() for d in report_dates if str(d or "").strip()]
        if not dates:
            return {}, {}
        conn = self._connect()
        if conn is None:
            return {}, {}
        try:
            placeholders = ", ".join(["?::date"] * len(dates))
            tyw_rows: list[dict[str, Any]] = []
            zqtz_rows_by_date = self._fetch_zqtz_yield_rows_for_dates_with_connection(conn, dates)
            if self._table_exists(conn, "tyw_interbank_daily_snapshot"):
                tyw_rows = self._fetch_dict_rows(
                    conn,
                    f"""
                    select report_date, principal_native, funding_cost_rate, source_version, rule_version,
                           case when {IB_ASSET_PREDICATE} then true else false end as is_asset_side
                    from tyw_interbank_daily_snapshot
                    where report_date in ({placeholders})
                    order by report_date desc
                    """,
                    dates,
                )
            return zqtz_rows_by_date, self._group_rows_by_report_date(tyw_rows)
        finally:
            conn.close()

    @staticmethod
    def _build_yield_kpi_payloads(
        *,
        zqtz_rows: list[object],
        tyw_rows: list[object],
    ) -> dict[str, dict[str, Any]]:
        sums: dict[str, dict[str, Decimal]] = {}
        lineage: dict[str, dict[str, set[str]]] = {}

        def ensure(report_date: object) -> dict[str, Decimal]:
            key = str(report_date)
            lineage.setdefault(key, {"source_version": set(), "rule_version": set()})
            return sums.setdefault(
                key,
                {
                    "asset_num": Decimal("0"),
                    "asset_den": Decimal("0"),
                    "liability_num": Decimal("0"),
                    "liability_den": Decimal("0"),
                    "market_liability_num": Decimal("0"),
                    "market_liability_den": Decimal("0"),
                },
            )

        def add_lineage(report_date: object, source_version: object, rule_version: object) -> None:
            bucket = lineage.setdefault(str(report_date), {"source_version": set(), "rule_version": set()})
            for raw, field in ((source_version, "source_version"), (rule_version, "rule_version")):
                for token in str(raw or "").split("|"):
                    token = token.strip()
                    if token:
                        bucket[field].add(token)

        for row in zqtz_rows:
            bucket = ensure(row[0])
            bucket["asset_num"] += Decimal(str(row[1] or "0"))
            bucket["asset_den"] += Decimal(str(row[2] or "0"))
            bucket["liability_num"] += Decimal(str(row[3] or "0"))
            bucket["liability_den"] += Decimal(str(row[4] or "0"))
            bucket["market_liability_num"] += Decimal(str(row[5] or "0"))
            bucket["market_liability_den"] += Decimal(str(row[6] or "0"))
            add_lineage(row[0], row[7], row[8])

        for row in tyw_rows:
            bucket = ensure(row[0])
            bucket["asset_num"] += Decimal(str(row[1] or "0"))
            bucket["asset_den"] += Decimal(str(row[2] or "0"))
            bucket["liability_num"] += Decimal(str(row[3] or "0"))
            bucket["liability_den"] += Decimal(str(row[4] or "0"))
            bucket["market_liability_num"] += Decimal(str(row[3] or "0"))
            bucket["market_liability_den"] += Decimal(str(row[4] or "0"))
            add_lineage(row[0], row[5], row[6])

        payloads: dict[str, dict[str, Any]] = {}
        for report_date, values in sums.items():
            asset_yield = (
                values["asset_num"] / values["asset_den"]
                if values["asset_den"] > 0
                else None
            )
            liability_cost = (
                values["liability_num"] / values["liability_den"]
                if values["liability_den"] > 0
                else None
            )
            market_liability_cost = (
                values["market_liability_num"] / values["market_liability_den"]
                if values["market_liability_den"] > 0
                else liability_cost
            )
            nim = (
                asset_yield - market_liability_cost
                if asset_yield is not None and market_liability_cost is not None
                else None
            )
            payloads[report_date] = {
                "report_date": report_date,
                "kpi": {
                    "asset_yield": to_float(asset_yield),
                    "liability_cost": to_float(liability_cost),
                    "market_liability_cost": to_float(market_liability_cost),
                    "nim": to_float(nim),
                },
                "source_version": "|".join(sorted(lineage.get(report_date, {}).get("source_version", set()))),
                "rule_version": "|".join(sorted(lineage.get(report_date, {}).get("rule_version", set()))),
            }
        return payloads

    def fetch_yield_kpis_for_dates(self, report_dates: list[str]) -> dict[str, dict[str, Any]]:
        dates = [str(d).strip() for d in report_dates if str(d or "").strip()]
        if not dates:
            return {}
        try:
            conn = self._connect()
        except duckdb.Error:
            return {}
        if conn is None:
            return {}
        try:
            placeholders = ", ".join(["?::date"] * len(dates))
            rows = conn.execute(
                f"""
                with zqtz_prepared as (
                  select
                    cast(report_date as varchar) as report_date,
                    position_scope,
                    invest_type_std,
                    asset_class,
                    bond_type,
                    instrument_name,
                    maturity_date,
                    case
                      when position_scope = 'liability' then
                        coalesce(amortized_cost_amount, market_value_amount, face_value_amount, 0)
                      when invest_type_std = 'H' then
                        coalesce(amortized_cost_amount, market_value_amount, face_value_amount, 0)
                      else
                        coalesce(market_value_amount, face_value_amount, 0)
                    end as amount,
                    case
                      when position_scope = 'liability'
                           and (instr(coalesce(bond_type, ''), ?) > 0
                                or instr(coalesce(instrument_name, ''), ?) > 0)
                        then coalesce(face_value_amount, market_value_amount, 0)
                      else 0
                    end as ncd_amount,
                    case
                      when ytm_value is not null and ytm_value <> 0 then ytm_value
                      when coupon_rate is not null and coupon_rate <> 0 then coupon_rate
                      else null
                    end as asset_rate,
                    coupon_rate as liability_rate,
                    source_version,
                    rule_version
                  from fact_formal_zqtz_balance_daily
                  where report_date in ({placeholders})
                    and currency_basis = 'CNY'
                    and position_scope in ('asset', 'liability')
                ),
                zqtz_agg as (
                select
                  report_date,
                  sum(
                    case
                      when position_scope = 'asset'
                           and maturity_date is not null
                           and coalesce(amount, 0) > 0
                           and asset_rate is not null
                           and instr(coalesce(asset_class, ''), ?) = 0
                           and (
                             invest_type_std in ('H', 'A')
                             or instr(coalesce(asset_class, ''), ?) > 0
                           )
                        then amount * case
                          when asset_rate > 0.5 and asset_rate <= 100 then asset_rate / 100
                          else asset_rate
                        end
                      else 0
                    end
                  ) as asset_num,
                  sum(
                    case
                      when position_scope = 'asset'
                           and maturity_date is not null
                           and coalesce(amount, 0) > 0
                           and asset_rate is not null
                           and instr(coalesce(asset_class, ''), ?) = 0
                           and (
                             invest_type_std in ('H', 'A')
                             or instr(coalesce(asset_class, ''), ?) > 0
                           )
                        then amount
                      else 0
                    end
                  ) as asset_den,
                  sum(
                    case
                      when position_scope = 'liability'
                           and coalesce(amount, 0) > 0
                           and liability_rate is not null
                        then amount * case
                          when liability_rate > 0.5 and liability_rate <= 100 then liability_rate / 100
                          else liability_rate
                        end
                      else 0
                    end
                  ) as liability_num,
                  sum(
                    case
                      when position_scope = 'liability'
                           and coalesce(amount, 0) > 0
                           and liability_rate is not null
                        then amount
                      else 0
                    end
                  ) as liability_den,
                  sum(
                    case
                      when position_scope = 'liability'
                           and coalesce(ncd_amount, 0) > 0
                           and liability_rate is not null
                        then ncd_amount * case
                          when liability_rate > 0.5 and liability_rate <= 100 then liability_rate / 100
                          else liability_rate
                        end
                      else 0
                    end
                  ) as market_liability_num,
                  sum(
                    case
                      when position_scope = 'liability'
                           and coalesce(ncd_amount, 0) > 0
                           and liability_rate is not null
                        then ncd_amount
                      else 0
                    end
                  ) as market_liability_den,
                  string_agg(distinct source_version, '|') as source_version,
                  string_agg(distinct rule_version, '|') as rule_version
                from zqtz_prepared
                group by report_date
                ),
                tyw_agg as (
                  select
                    cast(report_date as varchar) as report_date,
                    sum(
                      case
                        when coalesce(principal_native, 0) > 0
                             and funding_cost_rate is not null
                             and ({IB_ASSET_PREDICATE})
                          then principal_native * (funding_cost_rate / 100)
                        else 0
                      end
                    ) as asset_num,
                    sum(
                      case
                        when coalesce(principal_native, 0) > 0
                             and funding_cost_rate is not null
                             and ({IB_ASSET_PREDICATE})
                          then principal_native
                        else 0
                      end
                    ) as asset_den,
                    sum(
                      case
                        when coalesce(principal_native, 0) > 0
                             and funding_cost_rate is not null
                             and not ({IB_ASSET_PREDICATE})
                          then principal_native * (funding_cost_rate / 100)
                        else 0
                      end
                    ) as liability_num,
                    sum(
                      case
                        when coalesce(principal_native, 0) > 0
                             and funding_cost_rate is not null
                             and not ({IB_ASSET_PREDICATE})
                          then principal_native
                        else 0
                      end
                    ) as liability_den,
                    sum(
                      case
                        when coalesce(principal_native, 0) > 0
                             and funding_cost_rate is not null
                             and not ({IB_ASSET_PREDICATE})
                          then principal_native * (funding_cost_rate / 100)
                        else 0
                      end
                    ) as market_liability_num,
                    sum(
                      case
                        when coalesce(principal_native, 0) > 0
                             and funding_cost_rate is not null
                             and not ({IB_ASSET_PREDICATE})
                          then principal_native
                        else 0
                      end
                    ) as market_liability_den,
                    string_agg(distinct source_version, '|') as source_version,
                    string_agg(distinct rule_version, '|') as rule_version
                  from tyw_interbank_daily_snapshot
                  where report_date in ({placeholders})
                  group by report_date
                ),
                combined as (
                  select * from zqtz_agg
                  union all
                  select * from tyw_agg
                )
                select
                  report_date,
                  sum(asset_num) as asset_num,
                  sum(asset_den) as asset_den,
                  sum(liability_num) as liability_num,
                  sum(liability_den) as liability_den,
                  sum(market_liability_num) as market_liability_num,
                  sum(market_liability_den) as market_liability_den,
                  string_agg(source_version, '|') as source_version,
                  string_agg(rule_version, '|') as rule_version
                from combined
                group by report_date
                """,
                [
                    NCD_TEXT,
                    NCD_TEXT,
                    *dates,
                    TRADING_TEXT,
                    RECEIVABLE_INVESTMENT_TEXT,
                    TRADING_TEXT,
                    RECEIVABLE_INVESTMENT_TEXT,
                    *dates,
                ],
            ).fetchall()
        except duckdb.Error:
            return {}
        finally:
            conn.close()

        return self._build_yield_kpi_payloads(zqtz_rows=rows, tyw_rows=[])

    def fetch_zqtz_liability_rows_for_year(self, year: int) -> list[dict[str, Any]]:
        conn = self._connect()
        if conn is None:
            return []
        try:
            if not self._table_exists(conn, "zqtz_bond_daily_snapshot"):
                return []
            return self._fetch_dict_rows(
                conn,
                """
                select report_date, instrument_code, instrument_name, asset_class, bond_type,
                       face_value_native, market_value_native, amortized_cost_native,
                       coupon_rate, maturity_date, source_version, rule_version
                from zqtz_bond_daily_snapshot
                where report_date between ?::date and ?::date
                  and coalesce(is_issuance_like, false)
                """,
                [f"{year:04d}-01-01", f"{year:04d}-12-31"],
            )
        finally:
            conn.close()

    def fetch_tyw_liability_rows_for_year(self, year: int) -> list[dict[str, Any]]:
        conn = self._connect()
        if conn is None:
            return []
        try:
            if not self._table_exists(conn, "tyw_interbank_daily_snapshot"):
                return []
            return self._fetch_dict_rows(
                conn,
                f"""
                select report_date, position_id, product_type, position_side, counterparty_name,
                       core_customer_type, principal_native, funding_cost_rate, maturity_date,
                       source_version, rule_version
                from tyw_interbank_daily_snapshot
                where report_date between ?::date and ?::date
                  and not ({IB_ASSET_PREDICATE})
                """,
                [f"{year:04d}-01-01", f"{year:04d}-12-31"],
            )
        finally:
            conn.close()
