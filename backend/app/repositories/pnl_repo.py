from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

import duckdb


def _position_book_key(portfolio_name: object, cost_center: object) -> str:
    pn = str(portfolio_name or "").strip()
    cc = str(cost_center or "").strip()
    return f"{pn}::{cc}"


@dataclass
class PnlRepository:
    path: str

    def list_union_report_dates(self) -> list[str]:
        return sorted(
            set(self.list_formal_fi_report_dates()) | set(self.list_nonstd_bridge_report_dates()),
            reverse=True,
        )

    def list_formal_fi_report_dates(self) -> list[str]:
        return self._list_report_dates("fact_formal_pnl_fi")

    def list_nonstd_bridge_report_dates(self) -> list[str]:
        return self._list_report_dates("fact_nonstd_pnl_bridge")

    def fetch_zqtz_sub_type_map(self, report_dates: list[str]) -> dict[tuple[str, str], str]:
        dates = sorted({str(d) for d in report_dates if str(d or "").strip()})
        if not dates:
            return {}
        placeholders = ",".join(["?" for _ in dates])
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                f"""
                select cast(report_date as varchar), instrument_code, sub_type
                from fact_formal_zqtz_balance_daily
                where cast(report_date as varchar) in ({placeholders})
                  and nullif(trim(coalesce(instrument_code, '')), '') is not null
                  and nullif(trim(coalesce(sub_type, '')), '') is not null
                order by cast(report_date as varchar), instrument_code, portfolio_name, cost_center, currency_basis
                """,
                dates,
            ).fetchall()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return {}
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        out: dict[tuple[str, str], str] = {}
        for report_date, instrument_code, sub_type in rows:
            key = (str(report_date), str(instrument_code or "").strip())
            if key[1]:
                out.setdefault(key, str(sub_type or "").strip())
        return out

    def fetch_latest_fx_rates(self, report_date: str, base_currencies: set[str]) -> dict[str, Decimal]:
        required = sorted({currency.strip().upper() for currency in base_currencies if currency.strip()})
        if not required:
            return {}
        placeholders = ", ".join(["?"] * len(required))
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                f"""
                with ranked as (
                  select
                    upper(base_currency) as base_currency,
                    mid_rate,
                    row_number() over (
                      partition by upper(base_currency)
                      order by try_cast(trade_date as date) desc nulls last, cast(trade_date as varchar) desc
                    ) as rn
                  from fx_daily_mid
                  where try_cast(trade_date as date) <= ?::date
                    and upper(quote_currency) = 'CNY'
                    and upper(base_currency) in ({placeholders})
                )
                select base_currency, mid_rate
                from ranked
                where rn = 1
                """,
                [report_date, *required],
            ).fetchall()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return {}
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return {str(base): Decimal(str(rate)) for base, rate in rows if base and rate is not None}

    def fetch_formal_fi_rows(self, report_date: str) -> list[dict[str, object]]:
        return self._fetch_rows(
            "fact_formal_pnl_fi",
            report_date,
            [
                "report_date",
                "instrument_code",
                "portfolio_name",
                "cost_center",
                "invest_type_std",
                "accounting_basis",
                "currency_basis",
                "interest_income_514",
                "fair_value_change_516",
                "capital_gain_517",
                "manual_adjustment",
                "total_pnl",
                "source_version",
                "rule_version",
                "ingest_batch_id",
                "trace_id",
            ],
        )

    def fetch_nonstd_bridge_rows(self, report_date: str) -> list[dict[str, object]]:
        return self._fetch_rows(
            "fact_nonstd_pnl_bridge",
            report_date,
            [
                "report_date",
                "bond_code",
                "portfolio_name",
                "cost_center",
                "interest_income_514",
                "fair_value_change_516",
                "capital_gain_517",
                "manual_adjustment",
                "total_pnl",
                "source_version",
                "rule_version",
                "ingest_batch_id",
                "trace_id",
            ],
        )

    def merged_capital_gain_517_by_position_for_dates(self, report_dates: list[str]) -> dict[str, Decimal]:
        """Sum formal FI + nonstd bridge ``capital_gain_517`` by ``instrument::{portfolio}::{cost_center``.

        Missing tables or unreadable DuckDB paths yield an empty map without raising.
        """
        if not report_dates:
            return {}
        dates = sorted({str(d) for d in report_dates})
        placeholders = ",".join(["?" for _ in dates])
        acc: dict[str, Decimal] = defaultdict(Decimal)
        try:
            conn = duckdb.connect(self.path, read_only=True)
        except duckdb.Error:
            return {}
        try:
            for table, inst_column in (
                ("fact_formal_pnl_fi", "instrument_code"),
                ("fact_nonstd_pnl_bridge", "bond_code"),
            ):
                try:
                    rows = conn.execute(
                        f"""
                        select {inst_column}, portfolio_name, cost_center,
                               coalesce(sum(cast(capital_gain_517 as decimal(24,8))), 0)
                        from {table}
                        where cast(report_date as varchar) in ({placeholders})
                        group by 1, 2, 3
                        """,
                        dates,
                    ).fetchall()
                except duckdb.Error:
                    continue
                for inst, pn, cc, amt in rows:
                    inst_code = str(inst or "").strip()
                    if not inst_code:
                        continue
                    pk = f"{inst_code}::{_position_book_key(pn, cc)}"
                    acc[pk] += Decimal(str(amt))
        finally:
            conn.close()
        return dict(acc)

    def overview_totals(self, report_date: str) -> dict[str, object]:
        formal_rows = self.fetch_formal_fi_rows(report_date)
        nonstd_rows = self.fetch_nonstd_bridge_rows(report_date)

        def _sum(rows: list[dict[str, object]], key: str):
            return sum((row[key] for row in rows), 0)

        return {
            "formal_fi_row_count": len(formal_rows),
            "nonstd_bridge_row_count": len(nonstd_rows),
            "interest_income_514": _sum(formal_rows, "interest_income_514") + _sum(nonstd_rows, "interest_income_514"),
            "fair_value_change_516": _sum(formal_rows, "fair_value_change_516") + _sum(nonstd_rows, "fair_value_change_516"),
            "capital_gain_517": _sum(formal_rows, "capital_gain_517") + _sum(nonstd_rows, "capital_gain_517"),
            "manual_adjustment": _sum(formal_rows, "manual_adjustment") + _sum(nonstd_rows, "manual_adjustment"),
            "total_pnl": _sum(formal_rows, "total_pnl") + _sum(nonstd_rows, "total_pnl"),
        }

    def fetch_by_business_rows(self, report_date: str) -> list[dict[str, object]]:
        return self._fetch_by_business_rows(where_sql="p.report_date = ?", params=[report_date])

    def fetch_yearly_business_rows(self, year: int) -> list[dict[str, object]]:
        return self._fetch_by_business_rows(
            where_sql="substr(cast(p.report_date as varchar), 1, 4) = ?",
            params=[str(year)],
        )

    def count_untraced_formal_fi_rows(self, report_date: str) -> int:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            row = conn.execute(
                """
                select count(*)
                from fact_formal_pnl_fi p
                left join fact_formal_zqtz_balance_daily z
                  on z.report_date = p.report_date
                 and trim(coalesce(z.instrument_code, '')) = trim(coalesce(p.instrument_code, ''))
                 and trim(coalesce(z.portfolio_name, '')) = trim(coalesce(p.portfolio_name, ''))
                 and trim(coalesce(z.cost_center, '')) = trim(coalesce(p.cost_center, ''))
                 and trim(coalesce(z.currency_basis, '')) = trim(coalesce(p.currency_basis, ''))
                 and z.position_scope = 'asset'
                where p.report_date = ?
                  and nullif(trim(coalesce(z.business_type_primary, '')), '') is null
                """,
                [report_date],
            ).fetchone()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return 0
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return int(row[0] if row else 0)

    def sum_formal_total_pnl_for_year(self, year: int) -> Decimal:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            row = conn.execute(
                """
                select coalesce(sum(total_pnl), 0)
                from fact_formal_pnl_fi
                where substr(cast(report_date as varchar), 1, 4) = ?
                """,
                [str(year)],
            ).fetchone()
        except duckdb.Error as exc:
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        if row is None:
            return Decimal("0")
        return Decimal(str(row[0]))

    def sum_formal_total_pnl_through_report_date(self, report_date: str) -> Decimal:
        year = str(report_date)[:4]
        try:
            conn = duckdb.connect(self.path, read_only=True)
            row = conn.execute(
                """
                select coalesce(sum(total_pnl), 0)
                from fact_formal_pnl_fi
                where substr(cast(report_date as varchar), 1, 4) = ?
                  and cast(report_date as varchar) <= ?
                """,
                [year, report_date],
            ).fetchone()
        except duckdb.Error as exc:
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        if row is None:
            return Decimal("0")
        return Decimal(str(row[0]))

    def _list_report_dates(self, table_name: str) -> list[str]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                f"""
                select distinct report_date
                from {table_name}
                order by report_date desc
                """
            ).fetchall()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return []
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return [str(row[0]) for row in rows]

    def _fetch_rows(
        self,
        table_name: str,
        report_date: str,
        columns: list[str],
    ) -> list[dict[str, object]]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                f"""
                select {", ".join(columns)}
                from {table_name}
                where report_date = ?
                order by 1, 2
                """,
                [report_date],
            ).fetchall()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return []
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def _fetch_by_business_rows(self, *, where_sql: str, params: list[object]) -> list[dict[str, object]]:
        columns = [
            "report_date",
            "business_type_primary",
            "business_type",
            "currency_basis",
            "interest_income_514",
            "fair_value_change_516",
            "capital_gain_517",
            "manual_adjustment",
            "total_pnl",
            "scale_amount",
            "yield_pct",
            "pnl_row_count",
            "balance_row_count",
        ]
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                f"""
                with pnl_rows as (
                  select
                    cast(report_date as varchar) as report_date,
                    instrument_code,
                    portfolio_name,
                    cost_center,
                    currency_basis,
                    nullif(trim(coalesce(invest_type_std, '')), '') as fallback_business_type,
                    interest_income_514,
                    fair_value_change_516,
                    capital_gain_517,
                    manual_adjustment,
                    total_pnl
                  from fact_formal_pnl_fi p
                  where {where_sql}
                  union all
                  select
                    cast(report_date as varchar) as report_date,
                    bond_code as instrument_code,
                    portfolio_name,
                    cost_center,
                    'CNY' as currency_basis,
                    null as fallback_business_type,
                    interest_income_514,
                    fair_value_change_516,
                    capital_gain_517,
                    manual_adjustment,
                    total_pnl
                  from fact_nonstd_pnl_bridge p
                  where {where_sql}
                ), balance_by_position as (
                  select
                    cast(report_date as varchar) as report_date,
                    instrument_code,
                    portfolio_name,
                    cost_center,
                    currency_basis,
                    coalesce(
                      nullif(trim(coalesce(business_type_primary, '')), ''),
                      nullif(trim(coalesce(sub_type, '')), ''),
                      nullif(trim(coalesce(asset_class, '')), '')
                    ) as business_type_primary,
                    coalesce(sum(market_value_amount), 0) as scale_amount,
                    count(*) as balance_row_count
                  from fact_formal_zqtz_balance_daily
                  where position_scope = 'asset'
                  group by 1, 2, 3, 4, 5, 6
                ), balance_choice as (
                  select *
                  from (
                    select
                      report_date,
                      instrument_code,
                      portfolio_name,
                      cost_center,
                      business_type_primary,
                      currency_basis,
                      scale_amount,
                      balance_row_count,
                      row_number() over (
                        partition by report_date, instrument_code, portfolio_name, cost_center, currency_basis
                        order by
                          case when business_type_primary is null then 1 else 0 end,
                          business_type_primary
                      ) as rn
                    from balance_by_position
                  ) ranked
                  where rn = 1
                ), joined as (
                  select
                    cast(p.report_date as varchar) as report_date,
                    coalesce(b.business_type_primary, p.fallback_business_type, '未分类') as business_type_primary,
                    p.currency_basis,
                    p.interest_income_514,
                    p.fair_value_change_516,
                    p.capital_gain_517,
                    p.manual_adjustment,
                    p.total_pnl,
                    coalesce(b.scale_amount, 0) as scale_amount,
                    coalesce(b.balance_row_count, 0) as balance_row_count
                  from pnl_rows p
                  left join balance_choice b
                    on b.report_date = cast(p.report_date as varchar)
                   and (
                     trim(coalesce(b.instrument_code, '')) = trim(coalesce(p.instrument_code, ''))
                     or trim(coalesce(b.instrument_code, '')) = replace(trim(coalesce(p.instrument_code, '')), 'BOND-', '')
                     or ('BOND-' || trim(coalesce(b.instrument_code, ''))) = trim(coalesce(p.instrument_code, ''))
                   )
                   and trim(coalesce(b.portfolio_name, '')) = trim(coalesce(p.portfolio_name, ''))
                   and trim(coalesce(b.cost_center, '')) = trim(coalesce(p.cost_center, ''))
                   and trim(coalesce(b.currency_basis, '')) = trim(coalesce(p.currency_basis, ''))
                ), grouped as (
                  select
                    report_date,
                    business_type_primary,
                    business_type_primary as business_type,
                    currency_basis,
                    coalesce(sum(interest_income_514), 0) as interest_income_514,
                    coalesce(sum(fair_value_change_516), 0) as fair_value_change_516,
                    coalesce(sum(capital_gain_517), 0) as capital_gain_517,
                    coalesce(sum(manual_adjustment), 0) as manual_adjustment,
                    coalesce(sum(total_pnl), 0) as total_pnl,
                    coalesce(sum(scale_amount), 0) as scale_amount,
                    count(*) as pnl_row_count,
                    coalesce(sum(balance_row_count), 0) as balance_row_count
                  from joined
                  group by 1, 2, 3, 4
                )
                select
                  report_date,
                  business_type_primary,
                  business_type,
                  currency_basis,
                  interest_income_514,
                  fair_value_change_516,
                  capital_gain_517,
                  manual_adjustment,
                  total_pnl,
                  scale_amount,
                  case when scale_amount = 0 then null else total_pnl / scale_amount * 100 end as yield_pct,
                  pnl_row_count,
                  balance_row_count
                from grouped
                order by report_date asc, total_pnl desc, business_type_primary asc, currency_basis asc
                """,
                [*params, *params],
            ).fetchall()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return []
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return [dict(zip(columns, row, strict=True)) for row in rows]
