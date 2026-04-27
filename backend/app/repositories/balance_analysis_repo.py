from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import duckdb

from backend.app.repositories.duckdb_migrations import (
    apply_pending_migrations_on_connection,
    ensure_balance_zqtz_legacy_columns,
)
from backend.app.core_finance.balance_analysis import (
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
    TywSnapshotRow,
    ZqtzSnapshotRow,
)
from backend.app.repositories.currency_codes import normalize_currency_code
from backend.app.repositories.duckdb_repo import DuckDBRepository


def _zqtz_snapshot_row_from_tuple(row: tuple) -> ZqtzSnapshotRow:
    return ZqtzSnapshotRow(
        report_date=row[0],
        instrument_code=row[1],
        instrument_name=row[2] or "",
        portfolio_name=row[3] or "",
        cost_center=row[4] or "",
        account_category=row[5] or "",
        asset_class=row[6] or "",
        bond_type=row[7] or "",
        issuer_name=row[9] or "",
        industry_name=row[10] or "",
        rating=row[11] or "",
        currency_code=normalize_currency_code(row[12] or ""),
        face_value_native=row[13],
        market_value_native=row[14],
        amortized_cost_native=row[15],
        accrued_interest_native=row[16],
        coupon_rate=row[17],
        ytm_value=row[18],
        maturity_date=row[19],
        overdue_days=row[21],
        value_date=row[28],
        customer_attribute=str(row[29] or ""),
        is_issuance_like=bool(row[22]),
        interest_mode=row[23] or "",
        source_version=row[24] or "",
        rule_version=row[25] or "",
        ingest_batch_id=row[26] or "",
        trace_id=row[27] or "",
        business_type_primary=row[8] or "",
    )


def _tyw_snapshot_row_from_tuple(row: tuple) -> TywSnapshotRow:
    return TywSnapshotRow(
        report_date=row[0],
        position_id=row[1],
        product_type=row[2] or "",
        position_side=row[3] or "",
        counterparty_name=row[4] or "",
        account_type=row[5] or "",
        special_account_type=row[6] or "",
        core_customer_type=row[7] or "",
        currency_code=normalize_currency_code(row[8] or ""),
        principal_native=row[9],
        accrued_interest_native=row[10],
        funding_cost_rate=row[11],
        maturity_date=row[12],
        source_version=row[13] or "",
        rule_version=row[14] or "",
        ingest_batch_id=row[15] or "",
        trace_id=row[16] or "",
    )


@dataclass
class BalanceAnalysisRepository(DuckDBRepository):
    path: str

    def list_report_dates(self) -> list[str]:
        return sorted(
            set(self._list_report_dates("fact_formal_zqtz_balance_daily"))
            | set(self._list_report_dates("fact_formal_tyw_balance_daily")),
            reverse=True,
        )

    def load_zqtz_snapshot_rows(
        self,
        report_date: str,
        *,
        ingest_batch_id: str | None = None,
    ) -> list[ZqtzSnapshotRow]:
        where_parts = ["report_date = ?"]
        params: list[object] = [report_date]
        if ingest_batch_id:
            where_parts.append("ingest_batch_id = ?")
            params.append(ingest_batch_id)
        rows = self._fetch_rows(
            f"""
            select report_date, instrument_code, instrument_name, portfolio_name, cost_center,
                   account_category, asset_class, bond_type, business_type_primary, issuer_name, industry_name, rating,
                   currency_code, face_value_native, market_value_native, amortized_cost_native,
                   accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
                   overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
                   ingest_batch_id, trace_id, value_date, customer_attribute
            from zqtz_bond_daily_snapshot
            where {' and '.join(where_parts)}
            order by instrument_code, portfolio_name, cost_center, currency_code
            """,
            params,
        )
        return [_zqtz_snapshot_row_from_tuple(row) for row in rows]

    def load_tyw_snapshot_rows(
        self,
        report_date: str,
        *,
        ingest_batch_id: str | None = None,
    ) -> list[TywSnapshotRow]:
        where_parts = ["report_date = ?"]
        params: list[object] = [report_date]
        if ingest_batch_id:
            where_parts.append("ingest_batch_id = ?")
            params.append(ingest_batch_id)
        rows = self._fetch_rows(
            f"""
            select report_date, position_id, product_type, position_side, counterparty_name,
                   account_type, special_account_type, core_customer_type, currency_code,
                   principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
                   source_version, rule_version, ingest_batch_id, trace_id
            from tyw_interbank_daily_snapshot
            where {' and '.join(where_parts)}
            order by position_id
            """,
            params,
        )
        return [_tyw_snapshot_row_from_tuple(row) for row in rows]

    def list_zqtz_snapshot_ingest_batch_ids(self, report_date: str) -> list[str]:
        rows = self._fetch_rows(
            """
            select distinct ingest_batch_id
            from zqtz_bond_daily_snapshot
            where report_date = ?
              and coalesce(trim(ingest_batch_id), '') <> ''
            order by ingest_batch_id
            """,
            [report_date],
        )
        return [str(row[0]) for row in rows]

    def list_tyw_snapshot_ingest_batch_ids(self, report_date: str) -> list[str]:
        rows = self._fetch_rows(
            """
            select distinct ingest_batch_id
            from tyw_interbank_daily_snapshot
            where report_date = ?
              and coalesce(trim(ingest_batch_id), '') <> ''
            order by ingest_batch_id
            """,
            [report_date],
        )
        return [str(row[0]) for row in rows]

    def count_zqtz_snapshot_rows(
        self,
        report_date: str,
        *,
        ingest_batch_id: str | None = None,
    ) -> int:
        where_parts = ["report_date = ?"]
        params: list[object] = [report_date]
        if ingest_batch_id:
            where_parts.append("ingest_batch_id = ?")
            params.append(ingest_batch_id)
        rows = self._fetch_rows(
            f"""
            select count(*)
            from zqtz_bond_daily_snapshot
            where {' and '.join(where_parts)}
            """,
            params,
        )
        return int(rows[0][0])

    def count_tyw_snapshot_rows(
        self,
        report_date: str,
        *,
        ingest_batch_id: str | None = None,
    ) -> int:
        where_parts = ["report_date = ?"]
        params: list[object] = [report_date]
        if ingest_batch_id:
            where_parts.append("ingest_batch_id = ?")
            params.append(ingest_batch_id)
        rows = self._fetch_rows(
            f"""
            select count(*)
            from tyw_interbank_daily_snapshot
            where {' and '.join(where_parts)}
            """,
            params,
        )
        return int(rows[0][0])

    def lookup_fx_rate(self, *, report_date: str, base_currency: str) -> tuple[Decimal, str]:
        base_currency_normalized = normalize_currency_code(base_currency)
        if base_currency_normalized in {"CNY", "CNX"}:
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
            [report_date, base_currency_normalized],
        )
        if not rows:
            raise ValueError(
                f"Missing fx rate for base_currency={base_currency_normalized} report_date={report_date}"
            )
        return rows[0][0], rows[0][1] or ""

    def fetch_zqtz_snapshot_native_face_values(
        self,
        *,
        report_date: str,
    ) -> dict[tuple[str, str, str, str], Decimal]:
        """Face values from raw zqtz snapshot (for pnl.bridge native column enrichment)."""
        if not self._table_exists("zqtz_bond_daily_snapshot"):
            return {}
        rows = self._fetch_rows(
            """
            select instrument_code, portfolio_name, cost_center, currency_code, face_value_native
            from zqtz_bond_daily_snapshot
            where report_date = ?
            """,
            [report_date],
        )
        return {
            (
                str(instrument_code or ""),
                str(portfolio_name or ""),
                str(cost_center or ""),
                str(currency_code or "").upper(),
            ): Decimal(str(face_value_native))
            for instrument_code, portfolio_name, cost_center, currency_code, face_value_native in rows
            if face_value_native is not None
        }

    def resolve_fx_mid_rates_map(self, *, report_date: str) -> dict[str, Decimal] | None:
        """Map upper currency code to CNY mid rate for ``report_date`` (with trade_date LOCF fallback)."""
        if not self._table_exists("fx_daily_mid"):
            return None
        rows = self._fetch_rows(
            """
            select base_currency, mid_rate
            from fx_daily_mid
            where trade_date = ?
              and quote_currency = 'CNY'
            """,
            [report_date],
        )
        if not rows:
            rows = self._fetch_rows(
                """
                select base_currency, mid_rate
                from fx_daily_mid
                where trade_date <= ?
                  and quote_currency = 'CNY'
                order by trade_date desc
                limit 10
                """,
                [report_date],
            )
        if not rows:
            return None
        resolved: dict[str, Decimal] = {}
        for base_currency, mid_rate in rows:
            base = str(base_currency or "").upper().strip()
            if not base or base in resolved:
                continue
            resolved[base] = Decimal(str(mid_rate))
        return resolved or None

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
                      business_type_primary,
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
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            row.business_type_primary,
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
                   account_category, asset_class, bond_type, business_type_primary, issuer_name, industry_name, rating, invest_type_std,
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
            "business_type_primary",
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


def ensure_balance_analysis_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)
    ensure_balance_zqtz_legacy_columns(conn)
