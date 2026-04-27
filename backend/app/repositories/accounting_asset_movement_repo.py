from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import duckdb

_LEDGER_BUSINESS_ROWS = [
    {
        "row_key": "asset_interbank_lending",
        "row_label": "资产端-拆放同业",
        "side": "asset",
        "sort_order": 10,
        "include_prefixes": ("120", "121"),
        "exclude_prefixes": (),
        "exact_codes": (),
    },
    {
        "row_key": "asset_reverse_repo",
        "row_label": "资产端-买入返售",
        "side": "asset",
        "sort_order": 20,
        "include_prefixes": ("140",),
        "exclude_prefixes": ("14004", "14005"),
        "exact_codes": (),
    },
    {
        "row_key": "asset_interbank_current_deposit",
        "row_label": "资产端-同业存放-活期",
        "side": "asset",
        "sort_order": 30,
        "include_prefixes": ("114",),
        "exclude_prefixes": (),
        "exact_codes": (),
    },
    {
        "row_key": "asset_domestic_interbank_term_deposit",
        "row_label": "资产端-存放同业境内-定期",
        "side": "asset",
        "sort_order": 40,
        "include_prefixes": ("115",),
        "exclude_prefixes": (),
        "exact_codes": (),
    },
    {
        "row_key": "asset_overseas_interbank_term_deposit",
        "row_label": "资产端-存放同业境外-定期",
        "side": "asset",
        "sort_order": 50,
        "include_prefixes": ("116",),
        "exclude_prefixes": (),
        "exact_codes": (),
    },
    {
        "row_key": "liability_interbank_deposits",
        "row_label": "负债端-同业存放",
        "side": "liability",
        "sort_order": 110,
        "include_prefixes": ("234", "235"),
        "exclude_prefixes": (),
        "exact_codes": (),
    },
    {
        "row_key": "liability_interbank_borrowings",
        "row_label": "负债端-同业拆入",
        "side": "liability",
        "sort_order": 120,
        "include_prefixes": ("241", "242"),
        "exclude_prefixes": (),
        "exact_codes": (),
    },
    {
        "row_key": "liability_repo",
        "row_label": "负债端-卖出回购",
        "side": "liability",
        "sort_order": 130,
        "include_prefixes": ("255",),
        "exclude_prefixes": (),
        "exact_codes": (),
    },
    {
        "row_key": "liability_interbank_cd",
        "row_label": "负债端-同业存单",
        "side": "liability",
        "sort_order": 140,
        "include_prefixes": (),
        "exclude_prefixes": (),
        "exact_codes": ("27205000001", "27206000001"),
    },
]

_ZQTZ_NCD_ROW = {
    "row_key": "asset_zqtz_interbank_cd",
    "row_label": "资产端-同业存单",
    "side": "asset",
    "sort_order": 60,
}


@dataclass
class AccountingAssetMovementRepository:
    path: str

    def list_report_dates(self, *, currency_basis: str = "CNX") -> list[str]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
                """
                select distinct cast(report_date as varchar)
                from fact_accounting_asset_movement_monthly
                where currency_basis = ?
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

    def latest_source_version(self, *, currency_basis: str = "CNX") -> str:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            row = conn.execute(
                """
                select source_version
                from fact_accounting_asset_movement_monthly
                where currency_basis = ?
                order by report_date desc, sort_order asc
                limit 1
                """,
                [currency_basis],
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

    def fetch_recent_business_rows(
        self,
        *,
        report_date: str,
        currency_basis: str = "CNX",
        month_count: int = 6,
    ) -> list[dict[str, object]]:
        report_dates = self._fetch_recent_report_dates(
            report_date=report_date,
            currency_basis=currency_basis,
            month_count=month_count,
        )
        if not report_dates:
            return []
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows: list[dict[str, object]] = []
            for date_value in report_dates:
                rows.extend(
                    self._fetch_ledger_business_rows(
                        conn,
                        report_date=date_value,
                        currency_basis=currency_basis,
                    )
                )
                rows.append(
                    self._fetch_zqtz_asset_ncd_row(
                        conn,
                        report_date=date_value,
                        currency_basis=currency_basis,
                    )
                )
        except duckdb.Error:
            return []
        finally:
            if "conn" in locals():
                conn.close()
        return sorted(
            rows,
            key=lambda row: (str(row["report_date"]), -int(row["sort_order"])),
            reverse=True,
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

    def _fetch_recent_report_dates(
        self,
        *,
        report_date: str,
        currency_basis: str,
        month_count: int,
    ) -> list[str]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            rows = conn.execute(
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
        return [str(row[0]) for row in rows]

    def _fetch_ledger_business_rows(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        report_date: str,
        currency_basis: str,
    ) -> list[dict[str, object]]:
        if not self._table_exists(conn, "product_category_pnl_canonical_fact"):
            return [
                self._business_row(
                    report_date=report_date,
                    currency_basis=currency_basis,
                    row_def=row_def,
                    current_balance=Decimal("0"),
                    source_version="",
                    rule_version="",
                )
                for row_def in _LEDGER_BUSINESS_ROWS
            ]

        rows: list[dict[str, object]] = []
        for row_def in _LEDGER_BUSINESS_ROWS:
            where_sql, params = self._ledger_business_predicate(row_def)
            fetched = conn.execute(
                f"""
                select
                  coalesce(sum(ending_balance), 0) as current_balance,
                  coalesce(string_agg(distinct nullif(source_version, ''), '__' order by nullif(source_version, '')), '') as source_version,
                  coalesce(string_agg(distinct nullif(rule_version, ''), '__' order by nullif(rule_version, '')), '') as rule_version
                from product_category_pnl_canonical_fact
                where cast(report_date as varchar) = ?
                  and currency = ?
                  and ({where_sql})
                """,
                [report_date, currency_basis, *params],
            ).fetchone()
            rows.append(
                self._business_row(
                    report_date=report_date,
                    currency_basis=currency_basis,
                    row_def=row_def,
                    current_balance=Decimal(str(fetched[0] if fetched else "0")),
                    source_version=str(fetched[1] if fetched else ""),
                    rule_version=str(fetched[2] if fetched else ""),
                )
            )
        return rows

    def _fetch_zqtz_asset_ncd_row(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        report_date: str,
        currency_basis: str,
    ) -> dict[str, object]:
        row_def = _ZQTZ_NCD_ROW
        zqtz_currency_basis = "CNY" if currency_basis.upper() == "CNX" else currency_basis
        if not self._table_exists(conn, "fact_formal_zqtz_balance_daily"):
            return self._business_row(
                report_date=report_date,
                currency_basis=currency_basis,
                row_def=row_def,
                current_balance=Decimal("0"),
                source_kind="zqtz",
                source_note="ZQTZSHOW 业务种类1=同业存单",
                source_version="",
                rule_version="",
            )
        has_business_type_primary = self._column_exists(
            conn,
            "fact_formal_zqtz_balance_daily",
            "business_type_primary",
        )
        has_bond_type = self._column_exists(conn, "fact_formal_zqtz_balance_daily", "bond_type")
        if not has_business_type_primary and not has_bond_type:
            return self._business_row(
                report_date=report_date,
                currency_basis=currency_basis,
                row_def=row_def,
                current_balance=Decimal("0"),
                source_kind="zqtz",
                source_note="ZQTZSHOW 业务种类1=同业存单",
                source_version="",
                rule_version="",
            )
        if has_business_type_primary and has_bond_type:
            ncd_filter_sql = (
                "(business_type_primary = '同业存单' or "
                "(business_type_primary is null and bond_type = '同业存单'))"
            )
        elif has_business_type_primary:
            ncd_filter_sql = "business_type_primary = '同业存单'"
        else:
            ncd_filter_sql = "bond_type = '同业存单'"
        fetched = conn.execute(
            f"""
            select
              coalesce(sum(market_value_amount), 0) as current_balance,
              coalesce(string_agg(distinct nullif(source_version, ''), '__' order by nullif(source_version, '')), '') as source_version,
              coalesce(string_agg(distinct nullif(rule_version, ''), '__' order by nullif(rule_version, '')), '') as rule_version
            from fact_formal_zqtz_balance_daily
            where cast(report_date as varchar) = ?
              and currency_basis = ?
              and position_scope = 'asset'
              and {ncd_filter_sql}
            """,
            [report_date, zqtz_currency_basis],
        ).fetchone()
        return self._business_row(
            report_date=report_date,
            currency_basis=currency_basis,
            row_def=row_def,
            current_balance=Decimal(str(fetched[0] if fetched else "0")),
            source_kind="zqtz",
            source_note="ZQTZSHOW 业务种类1=同业存单",
            source_version=str(fetched[1] if fetched else ""),
            rule_version=str(fetched[2] if fetched else ""),
        )

    def _ledger_business_predicate(self, row_def: dict[str, object]) -> tuple[str, list[str]]:
        parts: list[str] = []
        params: list[str] = []
        exact_codes = tuple(row_def["exact_codes"])
        if exact_codes:
            placeholders = ", ".join("?" for _ in exact_codes)
            parts.append(f"account_code in ({placeholders})")
            params.extend(str(code) for code in exact_codes)
        include_prefixes = tuple(row_def["include_prefixes"])
        if include_prefixes:
            parts.append(
                "(" + " or ".join("account_code like ?" for _ in include_prefixes) + ")"
            )
            params.extend(f"{prefix}%" for prefix in include_prefixes)
        if not parts:
            parts.append("false")
        exclude_prefixes = tuple(row_def["exclude_prefixes"])
        for prefix in exclude_prefixes:
            parts.append("account_code not like ?")
            params.append(f"{prefix}%")
        return " and ".join(parts), params

    def _business_row(
        self,
        *,
        report_date: str,
        currency_basis: str,
        row_def: dict[str, object],
        current_balance: Decimal,
        source_version: str,
        rule_version: str,
        source_kind: str = "ledger",
        source_note: str = "总账对账科目余额",
    ) -> dict[str, object]:
        report_month = str(report_date)[:7]
        return {
            "report_date": report_date,
            "report_month": report_month,
            "currency_basis": currency_basis,
            "side": str(row_def["side"]),
            "sort_order": int(row_def["sort_order"]),
            "row_key": str(row_def["row_key"]),
            "row_label": str(row_def["row_label"]),
            "current_balance": current_balance,
            "source_kind": source_kind,
            "source_note": source_note,
            "source_version": source_version,
            "rule_version": rule_version,
        }

    def _table_exists(self, conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
        row = conn.execute(
            """
            select count(*)
            from information_schema.tables
            where table_name = ?
            """,
            [table_name],
        ).fetchone()
        return bool(row and row[0])

    def _column_exists(
        self,
        conn: duckdb.DuckDBPyConnection,
        table_name: str,
        column_name: str,
    ) -> bool:
        row = conn.execute(
            """
            select count(*)
            from information_schema.columns
            where table_name = ?
              and column_name = ?
            """,
            [table_name, column_name],
        ).fetchone()
        return bool(row and row[0])
