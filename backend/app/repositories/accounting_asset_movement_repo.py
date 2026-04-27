from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass
class AccountingAssetMovementRepository:
    path: str

    def list_report_dates(self, *, currency_basis: str = "CNX") -> list[str]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                """
                select distinct cast(report_date as varchar)
                from product_category_pnl_canonical_fact
                where currency = ?
                  and (
                    account_code like '141%'
                    or account_code like '142%'
                    or account_code like '143%'
                    or account_code like '1440101%'
                  )
                order by cast(report_date as varchar) desc
                """,
                [currency_basis],
            ).fetchall()
        except duckdb.Error:
            return []
        finally:
            if "conn" in locals():
                conn.close()
        return [str(row[0]) for row in rows]

    def latest_source_version(self) -> str:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            row = conn.execute(
                """
                select source_version
                from fact_accounting_asset_movement_monthly
                order by report_date desc, sort_order asc
                limit 1
                """
            ).fetchone()
        except duckdb.Error:
            return "sv_accounting_asset_movement_empty"
        finally:
            if "conn" in locals():
                conn.close()
        if row is None:
            return "sv_accounting_asset_movement_empty"
        return str(row[0])

    def fetch_rows(
        self,
        *,
        report_date: str,
        currency_basis: str = "CNX",
    ) -> list[dict[str, object]]:
        return self._fetch_rows_for_dates(
            report_dates=[report_date],
            currency_basis=currency_basis,
        )

    def fetch_recent_rows(
        self,
        *,
        report_date: str,
        currency_basis: str = "CNX",
        month_count: int = 6,
    ) -> list[dict[str, object]]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            date_rows = conn.execute(
                """
                select distinct cast(report_date as varchar)
                from fact_accounting_asset_movement_monthly
                where currency_basis = ?
                  and cast(report_date as varchar) <= ?
                order by cast(report_date as varchar) desc
                limit ?
                """,
                [currency_basis, report_date, month_count],
            ).fetchall()
        except duckdb.Error:
            return []
        finally:
            if "conn" in locals():
                conn.close()

        report_dates = [str(row[0]) for row in date_rows]
        if not report_dates:
            return []
        return self._fetch_rows_for_dates(
            report_dates=report_dates,
            currency_basis=currency_basis,
        )

    def _fetch_rows_for_dates(
        self,
        *,
        report_dates: list[str],
        currency_basis: str,
    ) -> list[dict[str, object]]:
        if not report_dates:
            return []
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                """
                select
                  report_date,
                  report_month,
                  currency_basis,
                  sort_order,
                  basis_bucket,
                  previous_balance,
                  current_balance,
                  balance_change,
                  change_pct,
                  contribution_pct,
                  zqtz_amount,
                  gl_amount,
                  reconciliation_diff,
                  reconciliation_status,
                  source_version,
                  rule_version
                from fact_accounting_asset_movement_monthly
                where report_date in (select unnest(?))
                  and currency_basis = ?
                order by report_date desc, sort_order
                """,
                [report_dates, currency_basis],
            ).fetchall()
        except duckdb.Error:
            return []
        finally:
            if "conn" in locals():
                conn.close()

        keys = [
            "report_date",
            "report_month",
            "currency_basis",
            "sort_order",
            "basis_bucket",
            "previous_balance",
            "current_balance",
            "balance_change",
            "change_pct",
            "contribution_pct",
            "zqtz_amount",
            "gl_amount",
            "reconciliation_diff",
            "reconciliation_status",
            "source_version",
            "rule_version",
        ]
        return [dict(zip(keys, row, strict=True)) for row in rows]
