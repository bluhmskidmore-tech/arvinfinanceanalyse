from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import duckdb
from backend.app.core_finance.pnl import (
    PNL_514_VAT_EFFECTIVE_END_DATE,
    PNL_514_VAT_EFFECTIVE_START_DATE,
    PNL_FORMAL_FACT_RULE_VERSION,
)
from backend.app.repositories.task_write_guard import require_repository_task_write_scope

# Shared by `backend.app.tasks.pnl_by_business_precompute` (writer) and
# `backend.app.services.pnl_service` (reader) so neither layer needs to
# import the other. Bump this whenever the `/pnl-by-business` read-model
# calculation rules change, so stale materialized rows are invalidated and
# callers fall back to a live recompute instead of serving outdated values.
PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION = "rv_pnl_by_business_precompute_v7"


def _position_book_key(portfolio_name: object, cost_center: object) -> str:
    pn = str(portfolio_name or "").strip()
    cc = str(cost_center or "").strip()
    return f"{pn}::{cc}"


_UNTRACED_COUNT_SQL = """
                select count(*)
                from fact_formal_pnl_fi p
                where p.report_date = ?
                  and not exists (
                    select 1
                    from fact_formal_zqtz_balance_daily z
                    where z.report_date = p.report_date
                      and (
                        trim(coalesce(z.instrument_code, '')) = trim(coalesce(p.instrument_code, ''))
                        or trim(coalesce(z.instrument_code, '')) = replace(trim(coalesce(p.instrument_code, '')), 'BOND-', '')
                        or ('BOND-' || trim(coalesce(z.instrument_code, ''))) = trim(coalesce(p.instrument_code, ''))
                      )
                      and trim(coalesce(z.portfolio_name, '')) = trim(coalesce(p.portfolio_name, ''))
                      and trim(coalesce(z.cost_center, '')) = trim(coalesce(p.cost_center, ''))
                      and trim(coalesce(z.currency_basis, '')) = trim(coalesce(p.currency_basis, ''))
                      and z.position_scope = 'asset'
                      and nullif(trim(coalesce(z.business_type_primary, '')), '') is not null
                  )
                  and (
                    select count(distinct nullif(trim(coalesce(z.business_type_primary, '')), ''))
                    from fact_formal_zqtz_balance_daily z
                    where z.report_date = p.report_date
                      and (
                        trim(coalesce(z.instrument_code, '')) = trim(coalesce(p.instrument_code, ''))
                        or trim(coalesce(z.instrument_code, '')) = replace(trim(coalesce(p.instrument_code, '')), 'BOND-', '')
                        or ('BOND-' || trim(coalesce(z.instrument_code, ''))) = trim(coalesce(p.instrument_code, ''))
                      )
                      and trim(coalesce(z.portfolio_name, '')) = trim(coalesce(p.portfolio_name, ''))
                      and trim(coalesce(z.currency_basis, '')) = trim(coalesce(p.currency_basis, ''))
                      and z.position_scope = 'asset'
                      and nullif(trim(coalesce(z.business_type_primary, '')), '') is not null
                  ) <> 1
                """


@dataclass
class PnlRepository:
    path: str

    def list_union_report_dates(self) -> list[str]:
        fact_tables = ("fact_formal_pnl_fi", "fact_nonstd_pnl_bridge")
        try:
            conn = duckdb.connect(self.path, read_only=True)
            available_tables = [table_name for table_name in fact_tables if self._table_exists(conn, table_name)]
            if not available_tables:
                raise RuntimeError("Formal pnl storage is unavailable.")
            report_dates: set[str] = set()
            for table_name in available_tables:
                rows = conn.execute(
                    f"""
                    select distinct report_date
                    from {table_name}
                    order by report_date desc
                    """
                ).fetchall()
                report_dates.update(str(row[0]) for row in rows)
        except duckdb.Error as exc:
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return sorted(report_dates, reverse=True)

    def list_formal_fi_report_dates(self) -> list[str]:
        return self._list_report_dates("fact_formal_pnl_fi")

    def list_nonstd_bridge_report_dates(self) -> list[str]:
        return self._list_report_dates("fact_nonstd_pnl_bridge")

    def fetch_pnl_by_business_precompute(
        self,
        *,
        year: int,
        as_of_date: str,
        result_kind: str,
        dimension: str,
        business_key: str,
        expected_rule_version: str = PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
        supplemental_source_version: str = "",
    ) -> dict[str, object] | None:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            if not self._table_exists(conn, "fact_pnl_by_business_precompute"):
                return None
            row = conn.execute(
                """
                select payload_json, source_version, rule_version
                from fact_pnl_by_business_precompute
                where year = ?
                  and as_of_date = ?
                  and result_kind = ?
                  and dimension = ?
                  and business_key = ?
                order by generated_at desc
                limit 1
                """,
                [year, as_of_date, result_kind, dimension, business_key],
            ).fetchone()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower() or "does not exist" in str(exc).lower():
                return None
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        if row is None or row[0] in (None, ""):
            return None
        if str(row[2] or "") != expected_rule_version:
            return None
        source_version = self.pnl_by_business_precompute_source_version(
            year=year,
            as_of_date=as_of_date,
            supplemental_source_version=supplemental_source_version,
        )
        if str(row[1] or "") != source_version:
            return None
        return json.loads(str(row[0]))

    def fetch_pnl_by_business_precompute_metadata(
        self,
        *,
        year: int,
        as_of_date: str,
        supplemental_source_version: str = "",
        verify_current: bool = True,
    ) -> dict[str, object] | None:
        """Return page-read-model provenance without deserializing its large payloads."""
        try:
            conn = duckdb.connect(self.path, read_only=True)
            if not self._table_exists(conn, "fact_pnl_by_business_precompute"):
                return None
            row = conn.execute(
                """
                select source_version, rule_version, generated_at, count(*) over () as record_count
                from fact_pnl_by_business_precompute
                where year = ? and as_of_date = ?
                order by case when result_kind = 'monthly' then 0 else 1 end, generated_at desc
                limit 1
                """,
                [year, as_of_date],
            ).fetchone()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower() or "does not exist" in str(exc).lower():
                return None
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        if row is None:
            return None
        source_version = str(row[0] or "")
        rule_version = str(row[1] or "")
        expected_source_version = (
            self.pnl_by_business_precompute_source_version(
                year=year,
                as_of_date=as_of_date,
                supplemental_source_version=supplemental_source_version,
            )
            if verify_current
            else None
        )
        return {
            "year": year,
            "as_of_date": as_of_date,
            "source_version": source_version,
            "rule_version": rule_version,
            "generated_at": str(row[2] or "") or None,
            "record_count": int(row[3] or 0),
            "is_current": (
                verify_current
                and source_version == expected_source_version
                and rule_version == PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION
            ),
        }

    def pnl_by_business_precompute_source_version(
        self,
        *,
        year: int,
        as_of_date: str,
        supplemental_source_version: str = "",
    ) -> str:
        y = f"{year:04d}"
        try:
            conn = duckdb.connect(self.path, read_only=True)
            report_dates: list[str] = []
            for table_name in ("fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"):
                if not self._table_exists(conn, table_name):
                    continue
                rows = conn.execute(
                    f"""
                    select distinct cast(report_date as varchar)
                    from {table_name}
                    where substr(cast(report_date as varchar), 1, 4) = ?
                      and cast(report_date as varchar) <= ?
                    """,
                    [y, as_of_date],
                ).fetchall()
                report_dates.extend(str(row[0]) for row in rows)
            period_start = f"{min(report_dates)[:7]}-01" if report_dates else f"{y}-01-01"
            fingerprint = {
                "version": "v4",
                "year": year,
                "as_of_date": as_of_date,
                "period_start": period_start,
                "report_dates": sorted(set(report_dates)),
                "formal_fi": self._pnl_precompute_fact_stats(
                    conn,
                    table_name="fact_formal_pnl_fi",
                    year=y,
                    as_of_date=as_of_date,
                ),
                "nonstd_bridge": self._pnl_precompute_fact_stats(
                    conn,
                    table_name="fact_nonstd_pnl_bridge",
                    year=y,
                    as_of_date=as_of_date,
                ),
                "zqtz_balance": self._pnl_precompute_balance_stats(
                    conn,
                    period_start=period_start,
                    as_of_date=as_of_date,
                ),
                "supplemental_source_version": supplemental_source_version,
            }
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower() or "does not exist" in str(exc).lower():
                return "sv_pnl_by_business_precompute_v4:unavailable"
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return "sv_pnl_by_business_precompute_v4:" + json.dumps(
            fingerprint,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _pnl_precompute_fact_stats(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        table_name: str,
        year: str,
        as_of_date: str,
    ) -> dict[str, str]:
        if not self._table_exists(conn, table_name):
            return self._empty_pnl_precompute_stats()
        signature_columns = (
            "report_date",
            "instrument_code",
            "bond_code",
            "instrument_name",
            "portfolio_name",
            "cost_center",
            "currency_basis",
            "fx_base_currency",
            "currency_code",
            "invest_type_std",
            "accounting_basis",
            "asset_class",
            "sub_type",
            "business_type_primary",
            "business_type_final",
            "source_version",
            "rule_version",
            "ingest_batch_id",
            "trace_id",
            "interest_income_514",
            "fair_value_change_516",
            "capital_gain_517",
            "manual_adjustment",
            "total_pnl",
        )
        available_columns = {
            str(row[0]).lower()
            for row in conn.execute(
                """
                select column_name
                from information_schema.columns
                where lower(table_name) = lower(?)
                """,
                [table_name],
            ).fetchall()
        }
        signature_exprs = {
            column: (
                f"coalesce(cast({column} as varchar), '')"
                if column.lower() in available_columns
                else "cast('' as varchar)"
            )
            for column in signature_columns
        }
        row_hash = "hash(" + ", ".join(
            signature_exprs[column] for column in signature_columns
        ) + ")"
        row = conn.execute(
            f"""
            select
              count(*) as row_count,
              coalesce(sum(interest_income_514), 0) as interest_income,
              coalesce(sum(fair_value_change_516), 0) as fair_value_change,
              coalesce(sum(capital_gain_517), 0) as capital_gain,
              coalesce(sum(manual_adjustment), 0) as manual_adjustment,
              coalesce(sum(total_pnl), 0) as total_pnl,
              coalesce(min(nullif(trim(rule_version), '')), '') as min_rule_version,
              coalesce(max(nullif(trim(rule_version), '')), '') as max_rule_version,
              count(distinct coalesce(nullif(trim(rule_version), ''), '<blank>')) as rule_version_count,
              coalesce(bit_xor({row_hash}), 0) as row_hash_xor,
              coalesce(sum(cast({row_hash} as hugeint)), 0) as row_hash_sum
            from {table_name}
            where substr(cast(report_date as varchar), 1, 4) = ?
              and cast(report_date as varchar) <= ?
            """,
            [year, as_of_date],
        ).fetchone()
        return self._pnl_precompute_stats_from_row(row)

    def _pnl_precompute_balance_stats(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        period_start: str,
        as_of_date: str,
    ) -> dict[str, str]:
        table_name = "fact_formal_zqtz_balance_daily"
        if not self._table_exists(conn, table_name):
            return {
                "row_count": "0",
                "avg_amount": "0",
                "current_amount": "0",
                "metadata_signature": "0:0",
            }
        current_amount_expr = self._zqtz_current_amount_expression(conn)
        metadata_columns = (
            "report_date",
            "instrument_code",
            "instrument_name",
            "portfolio_name",
            "cost_center",
            "currency_basis",
            "currency_code",
            "position_scope",
            "accounting_basis",
            "invest_type_std",
            "account_category",
            "asset_class",
            "bond_type",
            "sub_type",
            "business_type_primary",
            "business_type_final",
            "source_version",
            "rule_version",
        )
        available_columns = {
            str(row[0]).lower()
            for row in conn.execute(
                """
                select column_name
                from information_schema.columns
                where lower(table_name) = lower(?)
                """,
                [table_name],
            ).fetchall()
        }
        metadata_exprs = {
            column: (
                f"coalesce(cast({column} as varchar), '')"
                if column.lower() in available_columns
                else "cast('' as varchar)"
            )
            for column in metadata_columns
        }
        metadata_row_hash = "hash(" + ", ".join(
            [metadata_exprs[column] for column in metadata_columns]
            + [
                "coalesce(cast(market_value_amount as varchar), '')",
                f"coalesce(cast({current_amount_expr} as varchar), '')",
            ]
        ) + ")"
        row = conn.execute(
            f"""
            select
              count(*) as row_count,
              coalesce(sum(market_value_amount), 0) as avg_amount,
              coalesce(sum({current_amount_expr}), 0) as current_amount,
              coalesce(bit_xor({metadata_row_hash}), 0) as metadata_hash_xor,
              coalesce(sum(cast({metadata_row_hash} as hugeint)), 0) as metadata_hash_sum
            from fact_formal_zqtz_balance_daily
            where cast(report_date as date) between ?::date and ?::date
              and coalesce(currency_basis, '') = 'CNY'
              and coalesce(position_scope, '') = 'asset'
            """,
            [period_start, as_of_date],
        ).fetchone()
        if row is None:
            return {
                "row_count": "0",
                "avg_amount": "0",
                "current_amount": "0",
                "metadata_signature": "0:0",
            }
        return {
            "row_count": str(row[0] or 0),
            "avg_amount": str(row[1] or 0),
            "current_amount": str(row[2] or 0),
            "metadata_signature": f"{row[3] or 0}:{row[4] or 0}",
        }

    def _empty_pnl_precompute_stats(self) -> dict[str, str]:
        return {
            "row_count": "0",
            "interest_income": "0",
            "fair_value_change": "0",
            "capital_gain": "0",
            "manual_adjustment": "0",
            "total_pnl": "0",
            "min_rule_version": "",
            "max_rule_version": "",
            "rule_version_count": "0",
            "metadata_signature": "0:0",
        }

    def _pnl_precompute_stats_from_row(self, row: tuple[object, ...] | None) -> dict[str, str]:
        if row is None:
            return self._empty_pnl_precompute_stats()
        return {
            "row_count": str(row[0] or 0),
            "interest_income": str(row[1] or 0),
            "fair_value_change": str(row[2] or 0),
            "capital_gain": str(row[3] or 0),
            "manual_adjustment": str(row[4] or 0),
            "total_pnl": str(row[5] or 0),
            "min_rule_version": str(row[6] or ""),
            "max_rule_version": str(row[7] or ""),
            "rule_version_count": str(row[8] or 0),
            "metadata_signature": f"{row[9] or 0}:{row[10] or 0}",
        }

    def require_formal_pnl_rule_version(
        self,
        *,
        start_date: str,
        end_date: str,
        expected_rule_version: str,
    ) -> None:
        stale_versions: list[str] = []
        try:
            conn = duckdb.connect(self.path, read_only=True)
            for table_name in ("fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"):
                if not self._table_exists(conn, table_name):
                    continue
                rows = conn.execute(
                    f"""
                    select
                      coalesce(nullif(trim(rule_version), ''), '<blank>') as rule_version,
                      count(*) as row_count
                    from {table_name}
                    where cast(report_date as date) between ?::date and ?::date
                    group by 1
                    order by 1
                    """,
                    [start_date, end_date],
                ).fetchall()
                stale_versions.extend(
                    f"{table_name}={row[0]}({row[1]})"
                    for row in rows
                    if str(row[0]) != expected_rule_version
                )
        except duckdb.Error as exc:
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        if stale_versions:
            details = ", ".join(stale_versions)
            raise RuntimeError(
                "Formal pnl facts contain stale rule versions for "
                f"{start_date}..{end_date}; expected {expected_rule_version}: {details}"
            )

    def require_current_formal_pnl_rule_version(self, *, year: int, as_of_date: str) -> None:
        requested_start = date(year, 1, 1)
        requested_end = date.fromisoformat(as_of_date)
        effective_start = max(requested_start, PNL_514_VAT_EFFECTIVE_START_DATE)
        effective_end = min(requested_end, PNL_514_VAT_EFFECTIVE_END_DATE)
        if effective_start > effective_end:
            return
        self.require_formal_pnl_rule_version(
            start_date=effective_start.isoformat(),
            end_date=effective_end.isoformat(),
            expected_rule_version=PNL_FORMAL_FACT_RULE_VERSION,
        )

    def replace_pnl_by_business_precompute(
        self,
        *,
        year: int,
        as_of_date: str,
        records: list[dict[str, object]],
    ) -> None:
        require_repository_task_write_scope("replace_pnl_by_business_precompute")
        in_transaction = False
        try:
            conn = duckdb.connect(self.path, read_only=False)
            conn.execute(
                """
                create table if not exists fact_pnl_by_business_precompute (
                  year integer,
                  as_of_date varchar,
                  result_kind varchar,
                  dimension varchar,
                  business_key varchar,
                  payload_json varchar,
                  source_version varchar,
                  rule_version varchar,
                  generated_at varchar
                )
                """
            )
            conn.execute("begin transaction")
            in_transaction = True
            conn.execute(
                "delete from fact_pnl_by_business_precompute where year = ? and as_of_date = ?",
                [year, as_of_date],
            )
            if records:
                conn.executemany(
                    """
                    insert into fact_pnl_by_business_precompute values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        [
                            int(record["year"]),
                            str(record["as_of_date"]),
                            str(record["result_kind"]),
                            str(record["dimension"]),
                            str(record["business_key"]),
                            str(record["payload_json"]),
                            str(record["source_version"]),
                            str(record["rule_version"]),
                            str(record["generated_at"]),
                        ]
                        for record in records
                    ],
                )
            conn.execute("commit")
            in_transaction = False
        except duckdb.Error as exc:
            if "conn" in locals() and in_transaction:
                conn.execute("rollback")
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()

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

    def fetch_formal_fx_rates(self, report_date: str, base_currencies: set[str]) -> dict[str, Decimal]:
        required = sorted({currency.strip().upper() for currency in base_currencies if currency.strip()})
        required_fx = [currency for currency in required if currency not in {"CNY", "CNX", "RMB"}]
        if not required_fx:
            return {}
        placeholders = ", ".join(["?"] * len(required_fx))
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                f"""
                select
                  upper(base_currency) as base_currency,
                  mid_rate,
                  is_business_day,
                  is_carry_forward,
                  cast(observed_trade_date as varchar) as observed_trade_date
                from fx_daily_mid
                where try_cast(trade_date as date) = ?::date
                  and upper(quote_currency) = 'CNY'
                  and upper(base_currency) in ({placeholders})
                """,
                [report_date, *required_fx],
            ).fetchall()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return {}
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()

        rates: dict[str, Decimal] = {}
        for base_currency, mid_rate, is_business_day, is_carry_forward, observed_trade_date in rows:
            if base_currency is None or mid_rate is None:
                continue
            base = str(base_currency)
            business_day = bool(is_business_day)
            carry_forward = bool(is_carry_forward)
            observed_trade_date_str = str(observed_trade_date) if observed_trade_date is not None else None
            if business_day:
                if carry_forward:
                    raise ValueError(
                        f"Invalid formal fx metadata for base_currency={base} report_date={report_date}: "
                        "business-day row cannot be carry-forward."
                    )
                rates[base] = Decimal(str(mid_rate))
                continue
            if not carry_forward or observed_trade_date_str is None:
                raise ValueError(
                    f"Invalid formal fx carry-forward metadata for base_currency={base} report_date={report_date}: "
                    "non-business-day row must carry forward an observed prior trade date."
                )
            if date.fromisoformat(observed_trade_date_str) >= date.fromisoformat(report_date):
                raise ValueError(
                    f"Invalid formal fx carry-forward metadata for base_currency={base} report_date={report_date}: "
                    f"observed_trade_date={observed_trade_date_str} must be before report_date."
                )
            rates[base] = Decimal(str(mid_rate))

        missing = [currency for currency in required_fx if currency not in rates]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"Missing formal fx rate for base_currency={missing_text} report_date={report_date}")
        return rates

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

    def fetch_tpl_pnl_summary(self, report_date: str) -> dict[str, object]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            row = conn.execute(
                """
                select
                  coalesce(sum(fair_value_change_516), 0) as tpl_fair_value_change,
                  coalesce(sum(total_pnl), 0) as tpl_total_pnl,
                  count(*) as row_count
                from fact_formal_pnl_fi
                where report_date = ?
                  and (
                    upper(coalesce(accounting_basis, '')) like '%TPL%'
                    or upper(coalesce(accounting_basis, '')) like '%FVTPL%'
                    or coalesce(accounting_basis, '') like '%交易性%'
                  )
                """,
                [report_date],
            ).fetchone()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return {"tpl_fair_value_change": 0, "tpl_total_pnl": 0, "row_count": 0}
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return {
            "tpl_fair_value_change": row[0] if row else 0,
            "tpl_total_pnl": row[1] if row else 0,
            "row_count": row[2] if row else 0,
        }

    def fetch_tpl_pnl_summary_by_report_date(self, report_dates: list[str]) -> dict[str, dict[str, object]]:
        requested = [str(report_date) for report_date in dict.fromkeys(report_dates) if str(report_date or "")]
        if not requested:
            return {}
        empty = {
            report_date: {
                "tpl_fair_value_change": 0,
                "tpl_total_pnl": 0,
                "row_count": 0,
            }
            for report_date in requested
        }
        placeholders = ", ".join("?" for _ in requested)
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                f"""
                select
                  cast(report_date as varchar) as report_date,
                  coalesce(sum(fair_value_change_516), 0) as tpl_fair_value_change,
                  coalesce(sum(total_pnl), 0) as tpl_total_pnl,
                  count(*) as row_count
                from fact_formal_pnl_fi
                where cast(report_date as varchar) in ({placeholders})
                  and (
                    upper(coalesce(accounting_basis, '')) like '%TPL%'
                    or upper(coalesce(accounting_basis, '')) like '%FVTPL%'
                    or coalesce(accounting_basis, '') like '%交易性%'
                  )
                group by 1
                """,
                requested,
            ).fetchall()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return empty
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        out = dict(empty)
        for report_date, tpl_fair_value_change, tpl_total_pnl, row_count in rows:
            out[str(report_date)] = {
                "tpl_fair_value_change": tpl_fair_value_change,
                "tpl_total_pnl": tpl_total_pnl,
                "row_count": row_count,
            }
        return out

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

    def fetch_by_business_summary_rows(self, report_date: str) -> list[dict[str, object]]:
        return self._fetch_by_business_rows(where_sql="p.report_date = ?", params=[report_date])

    def fetch_by_business_summary_rows_by_report_date(
        self,
        report_dates: list[str],
    ) -> dict[str, list[dict[str, object]]]:
        requested = [str(report_date) for report_date in dict.fromkeys(report_dates) if str(report_date or "")]
        if not requested:
            return {}
        placeholders = ", ".join("?" for _ in requested)
        rows = self._fetch_by_business_rows(where_sql=f"cast(p.report_date as varchar) in ({placeholders})", params=requested)
        out = {report_date: [] for report_date in requested}
        for row in rows:
            report_date = str(row.get("report_date") or "")
            if report_date in out:
                out[report_date].append(row)
        return out

    def fetch_yearly_business_rows(self, year: int) -> list[dict[str, object]]:
        return self._fetch_by_business_rows(
            where_sql="substr(cast(p.report_date as varchar), 1, 4) = ?",
            params=[str(year)],
        )

    def count_untraced_formal_fi_rows(self, report_date: str) -> int:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            row = conn.execute(_UNTRACED_COUNT_SQL, [report_date]).fetchone()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return 0
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return int(row[0] if row else 0)

    def count_untraced_formal_fi_rows_for_dates(self, report_dates: list[str]) -> dict[str, int]:
        """近似诊断趋势用批量版本：在同一连接内逐日复用 :data:`_UNTRACED_COUNT_SQL`。

        与 :meth:`count_untraced_formal_fi_rows` 对每个 ``report_date`` 的结果必须逐一相等
        （见 ``tests/test_pnl_by_business_candidate_insights_contract.py`` 回归测试）；
        这里只是把逐日 connect/close 合并为一次连接，不改变 SQL 或口径。
        """
        dates = [str(d) for d in dict.fromkeys(report_dates) if str(d or "").strip()]
        if not dates:
            return {}
        try:
            conn = duckdb.connect(self.path, read_only=True)
            counts: dict[str, int] = {}
            for report_date in dates:
                row = conn.execute(_UNTRACED_COUNT_SQL, [report_date]).fetchone()
                counts[report_date] = int(row[0] if row else 0)
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return {report_date: 0 for report_date in dates}
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return counts

    def count_formal_fi_rows_for_dates(self, report_dates: list[str]) -> dict[str, int]:
        """按 ``report_date`` 统计 ``fact_formal_pnl_fi`` 总行数，用于诊断趋势占比分母。"""
        requested = [str(report_date) for report_date in dict.fromkeys(report_dates) if str(report_date or "")]
        if not requested:
            return {}
        empty = {report_date: 0 for report_date in requested}
        placeholders = ", ".join("?" for _ in requested)
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                f"""
                select cast(report_date as varchar) as report_date, count(*) as row_count
                from fact_formal_pnl_fi
                where cast(report_date as varchar) in ({placeholders})
                group by 1
                """,
                requested,
            ).fetchall()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return empty
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        out = dict(empty)
        for report_date, row_count in rows:
            out[str(report_date)] = int(row_count or 0)
        return out

    def fetch_untraced_formal_fi_breakdown(self, report_date: str) -> list[dict[str, object]]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                """
                with pnl as (
                  select
                    cast(report_date as varchar) as report_date,
                    trim(coalesce(instrument_code, '')) as instrument_code,
                    trim(coalesce(portfolio_name, '')) as portfolio_name,
                    trim(coalesce(cost_center, '')) as cost_center,
                    trim(coalesce(currency_basis, '')) as currency_basis,
                    coalesce(nullif(trim(coalesce(invest_type_std, '')), ''), '未分类') as invest_type_std,
                    interest_income_514,
                    fair_value_change_516,
                    capital_gain_517,
                    manual_adjustment,
                    total_pnl
                  from fact_formal_pnl_fi
                  where report_date = ?
                ), same_day_balance as (
                  select
                    cast(report_date as varchar) as report_date,
                    trim(coalesce(instrument_code, '')) as instrument_code,
                    trim(coalesce(portfolio_name, '')) as portfolio_name,
                    trim(coalesce(cost_center, '')) as cost_center,
                    trim(coalesce(currency_basis, '')) as currency_basis,
                    nullif(trim(coalesce(business_type_primary, '')), '') as business_type_primary
                  from fact_formal_zqtz_balance_daily
                  where report_date = ?
                    and position_scope = 'asset'
                ), historical_balance as (
                  select
                    trim(coalesce(instrument_code, '')) as instrument_code,
                    trim(coalesce(portfolio_name, '')) as portfolio_name,
                    trim(coalesce(currency_basis, '')) as currency_basis,
                    min(nullif(trim(coalesce(maturity_date, '')), '')) as maturity_date_hint,
                    count(*) as historical_balance_rows,
                    coalesce(sum(case when cast(report_date as varchar) = ? then 1 else 0 end), 0) as same_day_any_asset_rows,
                    coalesce(sum(
                      case
                        when cast(report_date as varchar) = ?
                         and nullif(trim(coalesce(business_type_primary, '')), '') is not null
                        then 1
                        else 0
                      end
                    ), 0) as same_day_classified_asset_rows
                  from fact_formal_zqtz_balance_daily
                  where position_scope = 'asset'
                  group by 1, 2, 3
                ), trace_classification as (
                  select
                    p.report_date,
                    p.instrument_code,
                    p.portfolio_name,
                    p.cost_center,
                    p.currency_basis,
                    count(distinct case when z.business_type_primary is not null then z.business_type_primary end)
                      as relaxed_business_type_count,
                    count(distinct case
                      when z.cost_center = p.cost_center and z.business_type_primary is not null
                      then z.business_type_primary
                    end) as strict_business_type_count
                  from pnl p
                  left join same_day_balance z
                    on (
                      z.instrument_code = p.instrument_code
                      or z.instrument_code = replace(p.instrument_code, 'BOND-', '')
                      or ('BOND-' || z.instrument_code) = p.instrument_code
                    )
                   and z.portfolio_name = p.portfolio_name
                   and z.currency_basis = p.currency_basis
                  group by 1, 2, 3, 4, 5
                ), untraced as (
                  select
                    p.*,
                    case
                      when coalesce(h.same_day_any_asset_rows, 0) = 0
                       and coalesce(h.historical_balance_rows, 0) > 0
                       and h.maturity_date_hint <= ?
                        then 'matured_before_or_on_report_date'
                      when coalesce(h.same_day_any_asset_rows, 0) = 0
                       and coalesce(h.historical_balance_rows, 0) > 0
                        then 'position_absent_before_maturity'
                      when coalesce(h.same_day_any_asset_rows, 0) = 0
                        then 'never_seen_in_zqtz_asset_balance'
                      when coalesce(h.same_day_classified_asset_rows, 0) = 0
                        then 'same_day_balance_without_primary_type'
                      when coalesce(tc.strict_business_type_count, 0) = 0
                       and coalesce(tc.relaxed_business_type_count, 0) > 1
                        then 'same_day_balance_multiple_primary_types'
                      else 'unexpected_untraced'
                    end as reason_code
                  from pnl p
                  left join historical_balance h
                    on (
                      h.instrument_code = p.instrument_code
                      or h.instrument_code = replace(p.instrument_code, 'BOND-', '')
                      or ('BOND-' || h.instrument_code) = p.instrument_code
                    )
                   and h.portfolio_name = p.portfolio_name
                   and h.currency_basis = p.currency_basis
                  left join trace_classification tc
                    on tc.report_date = p.report_date
                   and tc.instrument_code = p.instrument_code
                   and tc.portfolio_name = p.portfolio_name
                   and tc.cost_center = p.cost_center
                   and tc.currency_basis = p.currency_basis
                  where not exists (
                    select 1
                    from same_day_balance z
                    where (
                      z.instrument_code = p.instrument_code
                      or z.instrument_code = replace(p.instrument_code, 'BOND-', '')
                      or ('BOND-' || z.instrument_code) = p.instrument_code
                    )
                      and z.portfolio_name = p.portfolio_name
                      and z.currency_basis = p.currency_basis
                      and z.cost_center = p.cost_center
                      and z.business_type_primary is not null
                  )
                    and coalesce(tc.relaxed_business_type_count, 0) <> 1
                )
                select
                  reason_code,
                  invest_type_std,
                  count(*) as pnl_row_count,
                  coalesce(sum(total_pnl), 0) as total_pnl,
                  coalesce(sum(abs(total_pnl)), 0) as abs_pnl,
                  coalesce(sum(interest_income_514), 0) as interest_income_514,
                  coalesce(sum(fair_value_change_516), 0) as fair_value_change_516,
                  coalesce(sum(capital_gain_517), 0) as capital_gain_517,
                  coalesce(sum(manual_adjustment), 0) as manual_adjustment
                from untraced
                group by 1, 2
                order by abs_pnl desc, reason_code asc, invest_type_std asc
                """,
                [report_date, report_date, report_date, report_date, report_date],
            ).fetchall()
        except duckdb.Error as exc:
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        columns = [
            "reason_code",
            "invest_type_std",
            "pnl_row_count",
            "total_pnl",
            "abs_pnl",
            "interest_income_514",
            "fair_value_change_516",
            "capital_gain_517",
            "manual_adjustment",
        ]
        return [dict(zip(columns, row, strict=True)) for row in rows]

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

    def sum_nonstd_bridge_total_pnl_through_report_date(self, report_date: str) -> Decimal:
        year = str(report_date)[:4]
        try:
            conn = duckdb.connect(self.path, read_only=True)
            row = conn.execute(
                """
                select coalesce(sum(total_pnl), 0)
                from fact_nonstd_pnl_bridge
                where substr(cast(report_date as varchar), 1, 4) = ?
                  and cast(report_date as varchar) <= ?
                """,
                [year, report_date],
            ).fetchone()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return Decimal("0")
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        if row is None:
            return Decimal("0")
        return Decimal(str(row[0]))

    def _sum_total_pnl_through_report_dates(
        self,
        *,
        table_name: str,
        report_dates: list[str],
    ) -> dict[str, Decimal]:
        dates = [str(d).strip() for d in report_dates if str(d or "").strip()]
        if not dates:
            return {}
        values_sql = ", ".join(["(?)"] * len(dates))
        try:
            conn = duckdb.connect(self.path, read_only=True)
            if not self._table_exists(conn, table_name):
                return {}
            rows = conn.execute(
                f"""
                with requested(report_date) as (
                  values {values_sql}
                )
                select
                  requested.report_date,
                  coalesce(sum(p.total_pnl), 0) as total_pnl
                from requested
                left join {table_name} p
                  on substr(cast(p.report_date as varchar), 1, 4) = substr(requested.report_date, 1, 4)
                 and cast(p.report_date as varchar) <= requested.report_date
                group by requested.report_date
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
        return {str(report_date): Decimal(str(total_pnl or 0)) for report_date, total_pnl in rows}

    def sum_formal_total_pnl_through_report_dates(
        self,
        report_dates: list[str],
    ) -> dict[str, Decimal]:
        return self._sum_total_pnl_through_report_dates(
            table_name="fact_formal_pnl_fi",
            report_dates=report_dates,
        )

    def sum_nonstd_bridge_total_pnl_through_report_dates(
        self,
        report_dates: list[str],
    ) -> dict[str, Decimal]:
        return self._sum_total_pnl_through_report_dates(
            table_name="fact_nonstd_pnl_bridge",
            report_dates=report_dates,
        )

    def formal_pnl_ytd_has_rows(self, *, year: int, as_of_date: str) -> bool:
        """当年 ``as_of_date``（含）以前是否存在 formal FI 或 nonstd 桥接行。"""
        y = str(year)
        try:
            conn = duckdb.connect(self.path, read_only=True)
            row = conn.execute(
                """
                select (
                  (select count(*) from fact_formal_pnl_fi p
                    where substr(cast(p.report_date as varchar), 1, 4) = ?
                      and cast(p.report_date as varchar) <= ?)
                  +
                  (select count(*) from fact_nonstd_pnl_bridge b
                    where substr(cast(b.report_date as varchar), 1, 4) = ?
                      and cast(b.report_date as varchar) <= ?)
                ) as cnt
                """,
                [y, as_of_date, y, as_of_date],
            ).fetchone()
        except duckdb.Error as exc:
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return int(row[0] or 0) > 0

    def fetch_formal_fi_ytd_by_position(self, *, year: int, as_of_date: str) -> list[dict[str, object]]:
        """按 (instrument, portfolio, cost_center, currency_basis) 汇总当年至 ``as_of_date`` 的 FI 损益。"""
        y = str(year)
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                """
                select
                  instrument_code,
                  portfolio_name,
                  cost_center,
                  currency_basis,
                  max(nullif(trim(coalesce(invest_type_std, '')), '')) as invest_type_std,
                  coalesce(sum(interest_income_514), 0) as interest_income_514,
                  coalesce(sum(fair_value_change_516), 0) as fair_value_change_516,
                  coalesce(sum(capital_gain_517), 0) as capital_gain_517,
                  coalesce(sum(manual_adjustment), 0) as manual_adjustment,
                  coalesce(sum(total_pnl), 0) as total_pnl
                from fact_formal_pnl_fi
                where substr(cast(report_date as varchar), 1, 4) = ?
                  and cast(report_date as varchar) <= ?
                group by instrument_code, portfolio_name, cost_center, currency_basis
                order by instrument_code, portfolio_name, cost_center, currency_basis
                """,
                [y, as_of_date],
            ).fetchall()
        except duckdb.Error as exc:
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        columns = [
            "instrument_code",
            "portfolio_name",
            "cost_center",
            "currency_basis",
            "invest_type_std",
            "interest_income_514",
            "fair_value_change_516",
            "capital_gain_517",
            "manual_adjustment",
            "total_pnl",
        ]
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def fetch_nonstd_bridge_ytd_by_position(self, *, year: int, as_of_date: str) -> list[dict[str, object]]:
        """按 (bond_code, portfolio, cost_center) 汇总当年至 ``as_of_date`` 的 nonstd 桥接损益。"""
        y = str(year)
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                """
                select
                  bond_code as instrument_code,
                  portfolio_name,
                  cost_center,
                  'CNY' as currency_basis,
                  '' as invest_type_std,
                  coalesce(sum(interest_income_514), 0) as interest_income_514,
                  coalesce(sum(fair_value_change_516), 0) as fair_value_change_516,
                  coalesce(sum(capital_gain_517), 0) as capital_gain_517,
                  coalesce(sum(manual_adjustment), 0) as manual_adjustment,
                  coalesce(sum(total_pnl), 0) as total_pnl
                from fact_nonstd_pnl_bridge
                where substr(cast(report_date as varchar), 1, 4) = ?
                  and cast(report_date as varchar) <= ?
                group by bond_code, portfolio_name, cost_center
                order by bond_code, portfolio_name, cost_center
                """,
                [y, as_of_date],
            ).fetchall()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return []
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        columns = [
            "instrument_code",
            "portfolio_name",
            "cost_center",
            "currency_basis",
            "invest_type_std",
            "interest_income_514",
            "fair_value_change_516",
            "capital_gain_517",
            "manual_adjustment",
            "total_pnl",
        ]
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def max_formal_or_nonstd_report_date_in_year(self, *, year: int, as_of_cap: str | None) -> str | None:
        """当年已物化的最大报表日（FI ∪ nonstd），且不超过 ``as_of_cap``（若提供）。"""
        y = f"{year:04d}"
        cap = as_of_cap or "9999-12-31"
        candidates: list[str] = []
        for d in self.list_formal_fi_report_dates():
            s = str(d)
            if s.startswith(y) and s <= cap:
                candidates.append(s)
        for d in self.list_nonstd_bridge_report_dates():
            s = str(d)
            if s.startswith(y) and s <= cap:
                candidates.append(s)
        return max(candidates) if candidates else None

    def fetch_by_business_analysis_pnl_rows(self, *, year: int, as_of_date: str) -> list[dict[str, object]]:
        y = str(year)
        columns = [
            "source_kind",
            "report_date",
            "instrument_code",
            "instrument_name",
            "asset_class",
            "portfolio_name",
            "cost_center",
            "currency_basis",
            "invest_type_std",
            "accounting_basis",
            "interest_income_514",
            "fair_value_change_516",
            "capital_gain_517",
            "manual_adjustment",
            "total_pnl",
        ]
        try:
            conn = duckdb.connect(self.path, read_only=True)
            instrument_name_expr = self._optional_column_expr(
                conn,
                "fact_formal_pnl_fi",
                "instrument_name",
            )
            asset_class_expr = self._optional_column_expr(
                conn,
                "fact_formal_pnl_fi",
                "asset_class",
            )
            rows = conn.execute(
                f"""
                select *
                from (
                  select
                    'formal_fi' as source_kind,
                    cast(report_date as varchar) as report_date,
                    instrument_code,
                    {instrument_name_expr} as instrument_name,
                    {asset_class_expr} as asset_class,
                    portfolio_name,
                    cost_center,
                    coalesce(nullif(trim(currency_basis), ''), 'CNY') as currency_basis,
                    coalesce(invest_type_std, '') as invest_type_std,
                    coalesce(accounting_basis, '') as accounting_basis,
                    interest_income_514,
                    fair_value_change_516,
                    capital_gain_517,
                    manual_adjustment,
                    total_pnl
                  from fact_formal_pnl_fi
                  where substr(cast(report_date as varchar), 1, 4) = ?
                    and cast(report_date as varchar) <= ?
                  union all
                  select
                    'nonstd_bridge' as source_kind,
                    cast(report_date as varchar) as report_date,
                    bond_code as instrument_code,
                    cast('' as varchar) as instrument_name,
                    cast('' as varchar) as asset_class,
                    portfolio_name,
                    cost_center,
                    'CNY' as currency_basis,
                    '' as invest_type_std,
                    '' as accounting_basis,
                    interest_income_514,
                    fair_value_change_516,
                    capital_gain_517,
                    manual_adjustment,
                    total_pnl
                  from fact_nonstd_pnl_bridge
                  where substr(cast(report_date as varchar), 1, 4) = ?
                    and cast(report_date as varchar) <= ?
                ) rows
                order by report_date, source_kind, instrument_code, portfolio_name, cost_center
                """,
                [y, as_of_date, y, as_of_date],
            ).fetchall()
        except duckdb.Error as exc:
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def fetch_by_business_analysis_balance_rows(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, object]]:
        columns = [
            "report_date",
            "instrument_code",
            "instrument_name",
            "portfolio_name",
            "cost_center",
            "account_category",
            "asset_class",
            "bond_type",
            "sub_type",
            "business_type_primary",
            "business_type_final",
            "invest_type_std",
            "accounting_basis",
            "position_scope",
            "currency_basis",
            "currency_code",
            "avg_amount",
            "current_amount",
        ]
        try:
            conn = duckdb.connect(self.path, read_only=True)
            if not self._table_exists(conn, "fact_formal_zqtz_balance_daily"):
                return []
            table = "fact_formal_zqtz_balance_daily"
            current_amount_expr = self._zqtz_current_amount_expression(conn)
            optional = {
                "instrument_name": self._optional_column_expr(conn, table, "instrument_name"),
                "account_category": self._optional_column_expr(conn, table, "account_category"),
                "asset_class": self._optional_column_expr(conn, table, "asset_class"),
                "bond_type": self._optional_column_expr(conn, table, "bond_type"),
                "sub_type": self._optional_column_expr(conn, table, "sub_type"),
                "business_type_primary": self._optional_column_expr(conn, table, "business_type_primary"),
                "business_type_final": self._optional_column_expr(conn, table, "business_type_final"),
                "invest_type_std": self._optional_column_expr(conn, table, "invest_type_std"),
                "accounting_basis": self._optional_column_expr(conn, table, "accounting_basis"),
                "currency_code": self._optional_column_expr(conn, table, "currency_code"),
            }
            rows = conn.execute(
                f"""
                select
                  cast(report_date as varchar) as report_date,
                  coalesce(instrument_code, '') as instrument_code,
                  {optional["instrument_name"]} as instrument_name,
                  coalesce(portfolio_name, '') as portfolio_name,
                  coalesce(cost_center, '') as cost_center,
                  {optional["account_category"]} as account_category,
                  {optional["asset_class"]} as asset_class,
                  {optional["bond_type"]} as bond_type,
                  {optional["sub_type"]} as sub_type,
                  {optional["business_type_primary"]} as business_type_primary,
                  {optional["business_type_final"]} as business_type_final,
                  {optional["invest_type_std"]} as invest_type_std,
                  {optional["accounting_basis"]} as accounting_basis,
                  coalesce(position_scope, '') as position_scope,
                  coalesce(currency_basis, '') as currency_basis,
                  {optional["currency_code"]} as currency_code,
                  coalesce(market_value_amount, 0) as avg_amount,
                  {current_amount_expr} as current_amount
                from fact_formal_zqtz_balance_daily
                where cast(report_date as date) between ?::date and ?::date
                  and coalesce(currency_basis, '') = 'CNY'
                  and coalesce(position_scope, '') = 'asset'
                order by report_date, instrument_code, portfolio_name, cost_center
                """,
                [start_date, end_date],
            ).fetchall()
        except duckdb.Error as exc:
            if "cannot open database" in str(exc).lower():
                return []
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def _list_report_dates(self, table_name: str) -> list[str]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            if not self._table_exists(conn, table_name):
                return []
            rows = conn.execute(
                f"""
                select distinct report_date
                from {table_name}
                order by report_date desc
                """
            ).fetchall()
        except duckdb.Error as exc:
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

    def _table_exists(self, conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
        row = conn.execute(
            """
            select count(*)
            from information_schema.tables
            where lower(table_name) = lower(?)
            """,
            [table_name],
        ).fetchone()
        return bool(row and int(row[0] or 0) > 0)

    def _column_exists(self, conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> bool:
        row = conn.execute(
            """
            select count(*)
            from information_schema.columns
            where lower(table_name) = lower(?) and lower(column_name) = lower(?)
            """,
            [table_name, column_name],
        ).fetchone()
        return bool(row and int(row[0] or 0) > 0)

    def _optional_column_expr(self, conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> str:
        if self._column_exists(conn, table_name, column_name):
            return f"coalesce({column_name}, '')"
        return "cast('' as varchar)"

    def _zqtz_current_amount_expression(self, conn: duckdb.DuckDBPyConnection) -> str:
        table = "fact_formal_zqtz_balance_daily"
        market_amount_expr = (
            "coalesce(market_value_amount, 0)"
            if self._column_exists(conn, table, "market_value_amount")
            else "0"
        )
        face_amount_expr = (
            "coalesce(face_value_amount, 0)"
            if self._column_exists(conn, table, "face_value_amount")
            else "0"
        )
        interest_addend = (
            " + coalesce(accrued_interest_amount, 0)"
            if self._column_exists(conn, table, "accrued_interest_amount")
            else ""
        )
        if self._column_exists(conn, table, "amortized_cost_amount") and self._column_exists(
            conn,
            table,
            "accounting_basis",
        ):
            standard_amount_expr = (
                "case when accounting_basis = 'AC' "
                f"then coalesce(amortized_cost_amount, {market_amount_expr}) "
                f"else {market_amount_expr} end"
            )
        else:
            standard_amount_expr = market_amount_expr
        voucher_terms = []
        if self._column_exists(conn, table, "business_type_primary"):
            voucher_terms.append("business_type_primary = '凭证式国债'")
        if self._column_exists(conn, table, "bond_type"):
            voucher_terms.append("bond_type = '凭证式国债'")
        if self._column_exists(conn, table, "instrument_name"):
            voucher_terms.append("instrument_name like '%凭证式%'")
        voucher_amount_expr = (
            f"case when {standard_amount_expr} = 0 "
            f"then coalesce(nullif({market_amount_expr}, 0), {face_amount_expr}, 0) "
            f"else {standard_amount_expr} end"
        )
        if voucher_terms:
            return (
                "case when ("
                + " or ".join(voucher_terms)
                + f") then {voucher_amount_expr} else {standard_amount_expr} end"
                f"{interest_addend}"
            )
        return f"{standard_amount_expr}{interest_addend}"

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
                ), pnl_report_dates as (
                  select distinct report_date from pnl_rows
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
                    and cast(report_date as varchar) in (select report_date from pnl_report_dates)
                  group by 1, 2, 3, 4, 5, 6
                ), balance_strict_choice as (
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
                ), balance_relaxed_by_business as (
                  select
                    report_date,
                    instrument_code,
                    portfolio_name,
                    currency_basis,
                    business_type_primary,
                    coalesce(sum(scale_amount), 0) as scale_amount,
                    coalesce(sum(balance_row_count), 0) as balance_row_count
                  from balance_by_position
                  where business_type_primary is not null
                  group by 1, 2, 3, 4, 5
                ), balance_relaxed_choice as (
                  select
                    report_date,
                    instrument_code,
                    portfolio_name,
                    currency_basis,
                    min(business_type_primary) as business_type_primary,
                    coalesce(sum(scale_amount), 0) as scale_amount,
                    coalesce(sum(balance_row_count), 0) as balance_row_count
                  from balance_relaxed_by_business
                  group by 1, 2, 3, 4
                  having count(distinct business_type_primary) = 1
                ), joined as (
                  select
                    cast(p.report_date as varchar) as report_date,
                    coalesce(bs.business_type_primary, br.business_type_primary, p.fallback_business_type, '未分类') as business_type_primary,
                    p.currency_basis,
                    p.interest_income_514,
                    p.fair_value_change_516,
                    p.capital_gain_517,
                    p.manual_adjustment,
                    p.total_pnl,
                    case
                      when bs.business_type_primary is not null then bs.scale_amount
                      when br.business_type_primary is not null then br.scale_amount
                      else 0
                    end as scale_amount,
                    case
                      when bs.business_type_primary is not null then bs.balance_row_count
                      when br.business_type_primary is not null then br.balance_row_count
                      else 0
                    end as balance_row_count
                  from pnl_rows p
                  left join balance_strict_choice bs
                    on bs.report_date = cast(p.report_date as varchar)
                   and (
                     trim(coalesce(bs.instrument_code, '')) = trim(coalesce(p.instrument_code, ''))
                     or trim(coalesce(bs.instrument_code, '')) = replace(trim(coalesce(p.instrument_code, '')), 'BOND-', '')
                     or ('BOND-' || trim(coalesce(bs.instrument_code, ''))) = trim(coalesce(p.instrument_code, ''))
                   )
                   and trim(coalesce(bs.portfolio_name, '')) = trim(coalesce(p.portfolio_name, ''))
                   and trim(coalesce(bs.cost_center, '')) = trim(coalesce(p.cost_center, ''))
                   and trim(coalesce(bs.currency_basis, '')) = trim(coalesce(p.currency_basis, ''))
                  left join balance_relaxed_choice br
                    on bs.business_type_primary is null
                   and br.report_date = cast(p.report_date as varchar)
                   and (
                     trim(coalesce(br.instrument_code, '')) = trim(coalesce(p.instrument_code, ''))
                     or trim(coalesce(br.instrument_code, '')) = replace(trim(coalesce(p.instrument_code, '')), 'BOND-', '')
                     or ('BOND-' || trim(coalesce(br.instrument_code, ''))) = trim(coalesce(p.instrument_code, ''))
                   )
                   and trim(coalesce(br.portfolio_name, '')) = trim(coalesce(p.portfolio_name, ''))
                   and trim(coalesce(br.currency_basis, '')) = trim(coalesce(p.currency_basis, ''))
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
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return [dict(zip(columns, row, strict=True)) for row in rows]
