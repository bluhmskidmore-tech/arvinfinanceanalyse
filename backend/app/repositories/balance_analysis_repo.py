from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import duckdb

from backend.app.core_finance.balance_analysis import (
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
    TywSnapshotRow,
    ZqtzSnapshotRow,
)


@dataclass
class BalanceAnalysisRepository:
    path: str

    def list_report_dates(self) -> list[str]:
        return sorted(
            set(self._list_report_dates("fact_formal_zqtz_balance_daily"))
            | set(self._list_report_dates("fact_formal_tyw_balance_daily")),
            reverse=True,
        )

    def load_zqtz_snapshot_rows(self, report_date: str) -> list[ZqtzSnapshotRow]:
        rows = self._fetch_rows(
            """
            select report_date, instrument_code, instrument_name, portfolio_name, cost_center,
                   account_category, asset_class, bond_type, issuer_name, industry_name, rating,
                   currency_code, face_value_native, market_value_native, amortized_cost_native,
                   accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
                   overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
                   ingest_batch_id, trace_id, value_date, customer_attribute
            from zqtz_bond_daily_snapshot
            where report_date = ?
            order by instrument_code, portfolio_name, cost_center, currency_code
            """,
            [report_date],
        )
        return [
            ZqtzSnapshotRow(
                report_date=row[0],
                instrument_code=row[1],
                instrument_name=row[2] or "",
                portfolio_name=row[3] or "",
                cost_center=row[4] or "",
                account_category=row[5] or "",
                asset_class=row[6] or "",
                bond_type=row[7] or "",
                issuer_name=row[8] or "",
                industry_name=row[9] or "",
                rating=row[10] or "",
                currency_code=row[11] or "",
                face_value_native=row[12],
                market_value_native=row[13],
                amortized_cost_native=row[14],
                accrued_interest_native=row[15],
                coupon_rate=row[16],
                ytm_value=row[17],
                maturity_date=row[18],
                overdue_days=row[20],
                value_date=row[27],
                customer_attribute=str(row[28] or ""),
                is_issuance_like=bool(row[21]),
                interest_mode=row[22] or "",
                source_version=row[23] or "",
                rule_version=row[24] or "",
                ingest_batch_id=row[25] or "",
                trace_id=row[26] or "",
            )
            for row in rows
        ]

    def load_tyw_snapshot_rows(self, report_date: str) -> list[TywSnapshotRow]:
        rows = self._fetch_rows(
            """
            select report_date, position_id, product_type, position_side, counterparty_name,
                   account_type, special_account_type, core_customer_type, currency_code,
                   principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
                   source_version, rule_version, ingest_batch_id, trace_id
            from tyw_interbank_daily_snapshot
            where report_date = ?
            order by position_id
            """,
            [report_date],
        )
        return [
            TywSnapshotRow(
                report_date=row[0],
                position_id=row[1],
                product_type=row[2] or "",
                position_side=row[3] or "",
                counterparty_name=row[4] or "",
                account_type=row[5] or "",
                special_account_type=row[6] or "",
                core_customer_type=row[7] or "",
                currency_code=row[8] or "",
                principal_native=row[9],
                accrued_interest_native=row[10],
                funding_cost_rate=row[11],
                maturity_date=row[12],
                source_version=row[13] or "",
                rule_version=row[14] or "",
                ingest_batch_id=row[15] or "",
                trace_id=row[16] or "",
            )
            for row in rows
        ]

    def lookup_fx_rate(self, *, report_date: str, base_currency: str) -> tuple[Decimal, str]:
        if str(base_currency).upper() == "CNY":
            return Decimal("1"), "sv_fx_identity"
        rows = self._fetch_rows(
            """
            select mid_rate, source_version
            from fx_daily_mid
            where trade_date = ?
              and upper(base_currency) = upper(?)
              and upper(quote_currency) = 'CNY'
            limit 1
            """,
            [report_date, base_currency],
        )
        if not rows:
            raise ValueError(f"Missing fx rate for base_currency={base_currency} report_date={report_date}")
        return rows[0][0], rows[0][1] or ""

    def replace_formal_balance_rows(
        self,
        *,
        report_date: str,
        zqtz_rows: list[FormalZqtzBalanceFactRow],
        tyw_rows: list[FormalTywBalanceFactRow],
    ) -> None:
        conn = duckdb.connect(self.path, read_only=False)
        try:
            conn.execute("begin transaction")
            ensure_balance_analysis_tables(conn)
            conn.execute(
                "delete from fact_formal_zqtz_balance_daily where report_date = ?",
                [report_date],
            )
            conn.execute(
                "delete from fact_formal_tyw_balance_daily where report_date = ?",
                [report_date],
            )
            if zqtz_rows:
                conn.executemany(
                    """
                    insert into fact_formal_zqtz_balance_daily (
                      report_date,
                      instrument_code,
                      instrument_name,
                      portfolio_name,
                      cost_center,
                      account_category,
                      asset_class,
                      bond_type,
                      issuer_name,
                      industry_name,
                      rating,
                      invest_type_std,
                      accounting_basis,
                      position_scope,
                      currency_basis,
                      currency_code,
                      face_value_amount,
                      market_value_amount,
                      amortized_cost_amount,
                      accrued_interest_amount,
                      coupon_rate,
                      ytm_value,
                      maturity_date,
                      interest_mode,
                      is_issuance_like,
                      overdue_principal_days,
                      overdue_interest_days,
                      value_date,
                      customer_attribute,
                      source_version,
                      rule_version,
                      ingest_batch_id,
                      trace_id
                    ) values
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row.report_date.isoformat(),
                            row.instrument_code,
                            row.instrument_name,
                            row.portfolio_name,
                            row.cost_center,
                            row.account_category,
                            row.asset_class,
                            row.bond_type,
                            row.issuer_name,
                            row.industry_name,
                            row.rating,
                            row.invest_type_std,
                            row.accounting_basis,
                            row.position_scope,
                            row.currency_basis,
                            row.currency_code,
                            row.face_value_amount,
                            row.market_value_amount,
                            row.amortized_cost_amount,
                            row.accrued_interest_amount,
                            row.coupon_rate,
                            row.ytm_value,
                            row.maturity_date.isoformat() if row.maturity_date else None,
                            row.interest_mode,
                            row.is_issuance_like,
                            row.overdue_principal_days,
                            row.overdue_interest_days,
                            row.value_date.isoformat() if row.value_date else None,
                            row.customer_attribute,
                            row.source_version,
                            row.rule_version,
                            row.ingest_batch_id,
                            row.trace_id,
                        )
                        for row in zqtz_rows
                    ],
                )
            if tyw_rows:
                conn.executemany(
                    """
                    insert into fact_formal_tyw_balance_daily (
                      report_date,
                      position_id,
                      product_type,
                      position_side,
                      counterparty_name,
                      account_type,
                      special_account_type,
                      core_customer_type,
                      invest_type_std,
                      accounting_basis,
                      position_scope,
                      currency_basis,
                      currency_code,
                      principal_amount,
                      accrued_interest_amount,
                      funding_cost_rate,
                      maturity_date,
                      source_version,
                      rule_version,
                      ingest_batch_id,
                      trace_id
                    ) values
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row.report_date.isoformat(),
                            row.position_id,
                            row.product_type,
                            row.position_side,
                            row.counterparty_name,
                            row.account_type,
                            row.special_account_type,
                            row.core_customer_type,
                            row.invest_type_std,
                            row.accounting_basis,
                            row.position_scope,
                            row.currency_basis,
                            row.currency_code,
                            row.principal_amount,
                            row.accrued_interest_amount,
                            row.funding_cost_rate,
                            row.maturity_date.isoformat() if row.maturity_date else None,
                            row.source_version,
                            row.rule_version,
                            row.ingest_batch_id,
                            row.trace_id,
                        )
                        for row in tyw_rows
                    ],
                )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
        finally:
            conn.close()

    def fetch_pnl_bridge_zqtz_balance_rows(self, *, report_date: str) -> list[dict[str, object]]:
        """ZQTZ formal balance rows for pnl.bridge: asset scope, CNY basis."""
        try:
            if not self._table_exists("fact_formal_zqtz_balance_daily"):
                return []
            return self.fetch_formal_zqtz_rows(
                report_date=report_date,
                position_scope="asset",
                currency_basis="CNY",
            )
        except OSError as exc:
            raise RuntimeError("Formal balance storage is unavailable for pnl.bridge.") from exc
        except duckdb.Error as exc:
            raise RuntimeError("Formal balance query failed for pnl.bridge.") from exc

    def resolve_prior_pnl_bridge_balance_report_date(self, *, report_date: str) -> str | None:
        """Most recent distinct balance report_date strictly before ``report_date`` (asset / CNY)."""
        try:
            if not self._table_exists("fact_formal_zqtz_balance_daily"):
                return None
            rows = self._fetch_rows(
                """
                select distinct cast(report_date as varchar) as rd
                from fact_formal_zqtz_balance_daily
                where cast(report_date as varchar) < ?
                  and position_scope = 'asset'
                  and currency_basis = 'CNY'
                order by rd desc
                limit 1
                """,
                [report_date],
            )
        except OSError as exc:
            raise RuntimeError("Formal balance storage is unavailable for pnl.bridge.") from exc
        except duckdb.Error as exc:
            raise RuntimeError("Formal balance query failed for pnl.bridge.") from exc
        return str(rows[0][0]) if rows else None

    def fetch_formal_zqtz_rows(
        self,
        *,
        report_date: str,
        position_scope: str = "all",
        currency_basis: str = "CNY",
    ) -> list[dict[str, object]]:
        where_parts = ["report_date = ?", "currency_basis = ?"]
        params: list[object] = [report_date, currency_basis]
        if position_scope != "all":
            where_parts.append("position_scope = ?")
            params.append(position_scope)
        rows = self._fetch_rows(
            f"""
            select report_date, instrument_code, instrument_name, portfolio_name, cost_center,
                   account_category, asset_class, bond_type, issuer_name, industry_name, rating, invest_type_std,
                   accounting_basis, position_scope, currency_basis, currency_code, face_value_amount,
                   market_value_amount, amortized_cost_amount, accrued_interest_amount, coupon_rate,
                   ytm_value, maturity_date, interest_mode, is_issuance_like, overdue_principal_days,
                   overdue_interest_days, value_date, customer_attribute, source_version,
                   rule_version, ingest_batch_id, trace_id
            from fact_formal_zqtz_balance_daily
            where {' and '.join(where_parts)}
            order by instrument_code, portfolio_name, cost_center
            """,
            params,
        )
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
            "invest_type_std",
            "accounting_basis",
            "position_scope",
            "currency_basis",
            "currency_code",
            "face_value_amount",
            "market_value_amount",
            "amortized_cost_amount",
            "accrued_interest_amount",
            "coupon_rate",
            "ytm_value",
            "maturity_date",
            "interest_mode",
            "is_issuance_like",
            "overdue_principal_days",
            "overdue_interest_days",
            "value_date",
            "customer_attribute",
            "source_version",
            "rule_version",
            "ingest_batch_id",
            "trace_id",
        ]
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def fetch_formal_tyw_rows(
        self,
        *,
        report_date: str,
        position_scope: str = "all",
        currency_basis: str = "CNY",
    ) -> list[dict[str, object]]:
        where_parts = ["report_date = ?", "currency_basis = ?"]
        params: list[object] = [report_date, currency_basis]
        if position_scope != "all":
            where_parts.append("position_scope = ?")
            params.append(position_scope)
        rows = self._fetch_rows(
            f"""
            select report_date, position_id, product_type, position_side, counterparty_name,
                   account_type, special_account_type, core_customer_type, invest_type_std,
                   accounting_basis, position_scope, currency_basis, currency_code, principal_amount,
                   accrued_interest_amount, funding_cost_rate, maturity_date, source_version,
                   rule_version, ingest_batch_id, trace_id
            from fact_formal_tyw_balance_daily
            where {' and '.join(where_parts)}
            order by position_id
            """,
            params,
        )
        columns = [
            "report_date",
            "position_id",
            "product_type",
            "position_side",
            "counterparty_name",
            "account_type",
            "special_account_type",
            "core_customer_type",
            "invest_type_std",
            "accounting_basis",
            "position_scope",
            "currency_basis",
            "currency_code",
            "principal_amount",
            "accrued_interest_amount",
            "funding_cost_rate",
            "maturity_date",
            "source_version",
            "rule_version",
            "ingest_batch_id",
            "trace_id",
        ]
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def fetch_formal_overview(
        self,
        *,
        report_date: str,
        position_scope: str = "all",
        currency_basis: str = "CNY",
    ) -> dict[str, object]:
        zqtz_where_parts = ["report_date = ?", "currency_basis = ?"]
        tyw_where_parts = ["report_date = ?", "currency_basis = ?"]
        zqtz_params: list[object] = [report_date, currency_basis]
        tyw_params: list[object] = [report_date, currency_basis]
        if position_scope != "all":
            zqtz_where_parts.append("position_scope = ?")
            tyw_where_parts.append("position_scope = ?")
            zqtz_params.append(position_scope)
            tyw_params.append(position_scope)

        rows = self._fetch_rows(
            f"""
            with zqtz as (
              select
                count(*) as detail_row_count,
                count(
                  distinct (
                    instrument_code || '|' || portfolio_name || '|' || cost_center || '|' ||
                    position_scope || '|' || currency_basis || '|' || invest_type_std || '|' || accounting_basis
                  )
                ) as summary_row_count,
                coalesce(sum(market_value_amount), 0) as total_market_value_amount,
                coalesce(sum(amortized_cost_amount), 0) as total_amortized_cost_amount,
                coalesce(sum(accrued_interest_amount), 0) as total_accrued_interest_amount
              from fact_formal_zqtz_balance_daily
              where {' and '.join(zqtz_where_parts)}
            ),
            tyw as (
              select
                count(*) as detail_row_count,
                count(
                  distinct (
                    position_id || '|' || counterparty_name || '|' || product_type || '|' ||
                    position_scope || '|' || currency_basis || '|' || invest_type_std || '|' || accounting_basis
                  )
                ) as summary_row_count,
                coalesce(sum(principal_amount), 0) as total_market_value_amount,
                coalesce(sum(principal_amount), 0) as total_amortized_cost_amount,
                coalesce(sum(accrued_interest_amount), 0) as total_accrued_interest_amount
              from fact_formal_tyw_balance_daily
              where {' and '.join(tyw_where_parts)}
            )
            select
              ? as report_date,
              ? as position_scope,
              ? as currency_basis,
              zqtz.detail_row_count + tyw.detail_row_count as detail_row_count,
              zqtz.summary_row_count + tyw.summary_row_count as summary_row_count,
              zqtz.total_market_value_amount + tyw.total_market_value_amount as total_market_value_amount,
              zqtz.total_amortized_cost_amount + tyw.total_amortized_cost_amount as total_amortized_cost_amount,
              zqtz.total_accrued_interest_amount + tyw.total_accrued_interest_amount as total_accrued_interest_amount,
              (
                select string_agg(source_version, '__' order by source_version)
                from (
                  select distinct source_version
                  from fact_formal_zqtz_balance_daily
                  where {' and '.join(zqtz_where_parts)} and source_version <> ''
                  union
                  select distinct source_version
                  from fact_formal_tyw_balance_daily
                  where {' and '.join(tyw_where_parts)} and source_version <> ''
                )
              ) as source_version,
              (
                select string_agg(rule_version, '__' order by rule_version)
                from (
                  select distinct rule_version
                  from fact_formal_zqtz_balance_daily
                  where {' and '.join(zqtz_where_parts)} and rule_version <> ''
                  union
                  select distinct rule_version
                  from fact_formal_tyw_balance_daily
                  where {' and '.join(tyw_where_parts)} and rule_version <> ''
                )
              ) as rule_version
            from zqtz
            cross join tyw
            """,
            [
                *zqtz_params,
                *tyw_params,
                report_date,
                position_scope,
                currency_basis,
                *zqtz_params,
                *tyw_params,
                *zqtz_params,
                *tyw_params,
            ],
        )
        row = rows[0]
        columns = [
            "report_date",
            "position_scope",
            "currency_basis",
            "detail_row_count",
            "summary_row_count",
            "total_market_value_amount",
            "total_amortized_cost_amount",
            "total_accrued_interest_amount",
            "source_version",
            "rule_version",
        ]
        return dict(zip(columns, row, strict=True))

    def fetch_formal_summary_table(
        self,
        *,
        report_date: str,
        position_scope: str = "all",
        currency_basis: str = "CNY",
        limit: int | None = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        cte_sql, params = self._formal_summary_table_cte(
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
        )
        total_rows = int(
            self._fetch_rows(
                f"""
                {cte_sql}
                select count(*) from summary_rows
                """,
                params,
            )[0][0]
        )

        rows_sql = f"""
            {cte_sql}
            select row_key, source_family, display_name, owner_name, category_name,
                   position_scope, currency_basis, invest_type_std, accounting_basis,
                   detail_row_count, market_value_amount, amortized_cost_amount, accrued_interest_amount
            from summary_rows
            order by market_value_amount desc, source_family asc, display_name asc, owner_name asc, category_name asc
        """
        row_params = list(params)
        if limit is not None:
            rows_sql += "\nlimit ? offset ?"
            row_params.extend([limit, offset])

        row_tuples = self._fetch_rows(rows_sql, row_params)
        columns = [
            "row_key",
            "source_family",
            "display_name",
            "owner_name",
            "category_name",
            "position_scope",
            "currency_basis",
            "invest_type_std",
            "accounting_basis",
            "detail_row_count",
            "market_value_amount",
            "amortized_cost_amount",
            "accrued_interest_amount",
        ]
        return {
            "total_rows": total_rows,
            "rows": [dict(zip(columns, row, strict=True)) for row in row_tuples],
        }

    def fetch_formal_basis_breakdown(
        self,
        *,
        report_date: str,
        position_scope: str = "all",
        currency_basis: str = "CNY",
    ) -> list[dict[str, object]]:
        zqtz_where_parts = ["report_date = ?", "currency_basis = ?"]
        tyw_where_parts = ["report_date = ?", "currency_basis = ?"]
        zqtz_params: list[object] = [report_date, currency_basis]
        tyw_params: list[object] = [report_date, currency_basis]
        if position_scope != "all":
            zqtz_where_parts.append("position_scope = ?")
            tyw_where_parts.append("position_scope = ?")
            zqtz_params.append(position_scope)
            tyw_params.append(position_scope)

        rows = self._fetch_rows(
            f"""
            select * from (
              select
                'zqtz' as source_family,
                invest_type_std,
                accounting_basis,
                position_scope,
                currency_basis,
                count(*) as detail_row_count,
                coalesce(sum(market_value_amount), 0) as market_value_amount,
                coalesce(sum(amortized_cost_amount), 0) as amortized_cost_amount,
                coalesce(sum(accrued_interest_amount), 0) as accrued_interest_amount
              from fact_formal_zqtz_balance_daily
              where {' and '.join(zqtz_where_parts)}
              group by invest_type_std, accounting_basis, position_scope, currency_basis

              union all

              select
                'tyw' as source_family,
                invest_type_std,
                accounting_basis,
                position_scope,
                currency_basis,
                count(*) as detail_row_count,
                coalesce(sum(principal_amount), 0) as market_value_amount,
                coalesce(sum(principal_amount), 0) as amortized_cost_amount,
                coalesce(sum(accrued_interest_amount), 0) as accrued_interest_amount
              from fact_formal_tyw_balance_daily
              where {' and '.join(tyw_where_parts)}
              group by invest_type_std, accounting_basis, position_scope, currency_basis
            ) as basis_rows
            order by source_family asc, invest_type_std asc, accounting_basis asc,
                     position_scope asc, currency_basis asc
            """,
            [*zqtz_params, *tyw_params],
        )
        columns = [
            "source_family",
            "invest_type_std",
            "accounting_basis",
            "position_scope",
            "currency_basis",
            "detail_row_count",
            "market_value_amount",
            "amortized_cost_amount",
            "accrued_interest_amount",
        ]
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def _formal_summary_table_cte(
        self,
        *,
        report_date: str,
        position_scope: str,
        currency_basis: str,
    ) -> tuple[str, list[object]]:
        zqtz_where_parts = ["report_date = ?", "currency_basis = ?"]
        tyw_where_parts = ["report_date = ?", "currency_basis = ?"]
        zqtz_params: list[object] = [report_date, currency_basis]
        tyw_params: list[object] = [report_date, currency_basis]
        if position_scope != "all":
            zqtz_where_parts.append("position_scope = ?")
            tyw_where_parts.append("position_scope = ?")
            zqtz_params.append(position_scope)
            tyw_params.append(position_scope)

        cte_sql = f"""
            with summary_rows as (
              select
                'zqtz:' || instrument_code || ':' || portfolio_name || ':' || cost_center || ':' || currency_basis || ':' || position_scope || ':' || invest_type_std || ':' || accounting_basis as row_key,
                'zqtz' as source_family,
                instrument_code as display_name,
                portfolio_name as owner_name,
                cost_center as category_name,
                position_scope,
                currency_basis,
                invest_type_std,
                accounting_basis,
                count(*) as detail_row_count,
                coalesce(sum(market_value_amount), 0) as market_value_amount,
                coalesce(sum(amortized_cost_amount), 0) as amortized_cost_amount,
                coalesce(sum(accrued_interest_amount), 0) as accrued_interest_amount
              from fact_formal_zqtz_balance_daily
              where {' and '.join(zqtz_where_parts)}
              group by instrument_code, portfolio_name, cost_center, position_scope, currency_basis,
                       invest_type_std, accounting_basis

              union all

              select
                'tyw:' || position_id || ':' || currency_basis || ':' || position_scope || ':' || invest_type_std || ':' || accounting_basis as row_key,
                'tyw' as source_family,
                position_id as display_name,
                counterparty_name as owner_name,
                product_type as category_name,
                position_scope,
                currency_basis,
                invest_type_std,
                accounting_basis,
                count(*) as detail_row_count,
                coalesce(sum(principal_amount), 0) as market_value_amount,
                coalesce(sum(principal_amount), 0) as amortized_cost_amount,
                coalesce(sum(accrued_interest_amount), 0) as accrued_interest_amount
              from fact_formal_tyw_balance_daily
              where {' and '.join(tyw_where_parts)}
              group by position_id, counterparty_name, product_type, position_scope, currency_basis,
                       invest_type_std, accounting_basis
            )
        """
        return cte_sql, [*zqtz_params, *tyw_params]

    def _list_report_dates(self, table_name: str) -> list[str]:
        try:
            rows = self._fetch_rows(
                f"""
                select distinct report_date
                from {table_name}
                order by report_date desc
                """
            )
        except duckdb.Error as exc:
            raise RuntimeError("Formal balance-analysis storage is unavailable.") from exc
        return [str(row[0]) for row in rows]

    def _fetch_rows(self, query: str, params: list[object] | None = None) -> list[tuple]:
        conn = duckdb.connect(self.path, read_only=True)
        try:
            return conn.execute(query, params or []).fetchall()
        finally:
            conn.close()

    def _table_exists(self, table_name: str) -> bool:
        conn = duckdb.connect(self.path, read_only=True)
        try:
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
        finally:
            conn.close()


def ensure_balance_analysis_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table if not exists fact_formal_zqtz_balance_daily (
          report_date varchar,
          instrument_code varchar,
          instrument_name varchar,
          portfolio_name varchar,
          cost_center varchar,
          account_category varchar,
          asset_class varchar,
          bond_type varchar,
          issuer_name varchar,
          industry_name varchar,
          rating varchar,
          invest_type_std varchar,
          accounting_basis varchar,
          position_scope varchar,
          currency_basis varchar,
          currency_code varchar,
          face_value_amount decimal(24, 8),
          market_value_amount decimal(24, 8),
          amortized_cost_amount decimal(24, 8),
          accrued_interest_amount decimal(24, 8),
          coupon_rate decimal(18, 8),
          ytm_value decimal(18, 8),
          maturity_date varchar,
          interest_mode varchar,
          is_issuance_like boolean,
          source_version varchar,
          rule_version varchar,
          ingest_batch_id varchar,
          trace_id varchar
        )
        """
    )
    _ensure_zqtz_formal_enrichment_columns(conn)
    conn.execute(
        """
        create table if not exists fact_formal_tyw_balance_daily (
          report_date varchar,
          position_id varchar,
          product_type varchar,
          position_side varchar,
          counterparty_name varchar,
          account_type varchar,
          special_account_type varchar,
          core_customer_type varchar,
          invest_type_std varchar,
          accounting_basis varchar,
          position_scope varchar,
          currency_basis varchar,
          currency_code varchar,
          principal_amount decimal(24, 8),
          accrued_interest_amount decimal(24, 8),
          funding_cost_rate decimal(18, 8),
          maturity_date varchar,
          source_version varchar,
          rule_version varchar,
          ingest_batch_id varchar,
          trace_id varchar
        )
        """
    )
    if not _column_exists(conn, "fact_formal_zqtz_balance_daily", "account_category"):
        conn.execute("alter table fact_formal_zqtz_balance_daily add column account_category varchar")


def _ensure_zqtz_formal_enrichment_columns(conn: duckdb.DuckDBPyConnection) -> None:
    for column_name, ddl in (
        ("overdue_principal_days", "integer"),
        ("overdue_interest_days", "integer"),
        ("value_date", "varchar"),
        ("customer_attribute", "varchar"),
    ):
        if not _column_exists(conn, "fact_formal_zqtz_balance_daily", column_name):
            conn.execute(f"alter table fact_formal_zqtz_balance_daily add column {column_name} {ddl}")


def _column_exists(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    column_name: str,
) -> bool:
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
