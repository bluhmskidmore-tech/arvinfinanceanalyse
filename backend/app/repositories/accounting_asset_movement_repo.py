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
        "row_key": "asset_long_term_equity_investment",
        "row_label": "长期股权投资（亿元）",
        "side": "asset",
        "sort_order": 94,
        "include_prefixes": ("145",),
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
_ZQTZ_ASSET_ROWS = [
    {
        "row_key": "asset_zqtz_central_bank_bill",
        "row_label": "央行票据",
        "sort_order": 60,
        "match_keywords": ("央行票据", "央票"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 央行票据/央票",
    },
    {
        "row_key": "asset_zqtz_treasury_bond",
        "row_label": "国债（含凭证式国债）",
        "sort_order": 62,
        "match_keywords": ("国债", "记账式国债", "凭证式国债"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 国债/记账式国债/凭证式国债",
    },
    {
        "row_key": "asset_zqtz_local_government_bond",
        "row_label": "地方政府债",
        "sort_order": 64,
        "match_keywords": ("地方政府债", "地方债", "地方政府债券"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 地方政府债/地方债/地方政府债券",
    },
    {
        "row_key": "asset_zqtz_policy_financial_bond",
        "row_label": "政策性金融债",
        "sort_order": 66,
        "match_keywords": ("政策性金融债", "政金债", "政策性银行债"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 政策性金融债/政金债/政策性银行债",
    },
    {
        "row_key": "asset_zqtz_railway_bond",
        "row_label": "铁道债",
        "sort_order": 68,
        "match_keywords": ("铁道债", "中国铁路", "铁道"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 铁道债/中国铁路/铁道",
    },
    {
        "row_key": "asset_zqtz_commercial_financial_bond",
        "row_label": "商业性金融债",
        "sort_order": 70,
        "match_keywords": ("商业性金融债", "次级债券", "商业银行债", "非银行金融债"),
        "exclude_instrument_codes": ("HK0001155867",),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 商业性金融债/次级债券/商业银行债/非银行金融债",
    },
    {
        "row_key": "asset_zqtz_interbank_cd",
        "row_label": "同业存单",
        "sort_order": 72,
        "match_keywords": ("同业存单", "NCD"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 同业存单/NCD",
    },
    {
        "row_key": "asset_zqtz_nonfinancial_enterprise_bond",
        "row_label": "非金融企业债券",
        "sort_order": 74,
        "match_keywords": (
            "非金融企业债券",
            "企业债",
            "公司债",
            "中期票据",
            "短期融资券",
            "信用债券-企业",
            "信用债券-公用事业",
        ),
        "exclude_instrument_prefixes": ("US",),
        "exclude_name_contains": ("铁道",),
        "include_foreign_currency": True,
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 非金融企业债券/企业债/公司债/中期票据/短期融资券/信用债券-企业/信用债券-公用事业，剔除铁道债/外国债券清单",
    },
    {
        "row_key": "asset_zqtz_abs",
        "row_label": "资产支持证券",
        "sort_order": 76,
        "match_keywords": ("资产支持证券", "ABS", "资产证券化"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 资产支持证券/ABS/资产证券化",
    },
    {
        "row_key": "asset_zqtz_foreign_bond",
        "row_label": "外国债券",
        "sort_order": 78,
        "instrument_prefixes": ("US", "HK0001155867"),
        "source_note": "ZQTZSHOW 外国债券按披露表外债清单：US* + HK0001155867",
    },
    {
        "row_key": "asset_zqtz_public_fund",
        "row_label": "公募基金",
        "sort_order": 80,
        "bond_types": ("其他",),
        "instrument_prefixes": ("SA",),
        "source_note": "ZQTZSHOW bond_type=其他 and instrument_code prefix=SA",
    },
    {
        "row_key": "asset_zqtz_non_bottom_investment",
        "row_label": "非底层投资资产",
        "sort_order": 82,
        "bond_types": ("其他",),
        "instrument_prefixes": ("G0", "J0", "J1", "J4"),
        "source_note": "ZQTZSHOW bond_type=其他 and instrument_code prefix in G0/J0/J1/J4",
    },
    {
        "row_key": "asset_zqtz_detail_trust_plan",
        "row_label": "信托计划",
        "sort_order": 83,
        "bond_types": ("其他",),
        "instrument_prefixes": ("G0",),
        "source_note": "ZQTZSHOW 其中项：instrument_code prefix=G0",
    },
    {
        "row_key": "asset_zqtz_detail_securities_asset_management_plan",
        "row_label": "证券业资管计划",
        "sort_order": 84,
        "bond_types": ("其他",),
        "instrument_prefixes": ("J0", "J1", "J4"),
        "source_note": "ZQTZSHOW 其中项：instrument_code prefix in J0/J1/J4",
    },
    {
        "row_key": "asset_zqtz_detail_structured_finance_broker",
        "row_label": "其中：结构化融资（券商）",
        "sort_order": 85,
        "bond_types": ("其他",),
        "instrument_prefixes": ("J4",),
        "source_note": "ZQTZSHOW 其中项：instrument_code prefix=J4",
    },
    {
        "row_key": "asset_zqtz_detail_foreign_currency_delegated",
        "row_label": "其中：外币委外",
        "sort_order": 86,
        "bond_types": ("其他",),
        "instrument_prefixes": ("J1",),
        "source_note": "ZQTZSHOW 其中项：instrument_code prefix=J1",
    },
    {
        "row_key": "asset_zqtz_detail_local_currency_delegated_market_value",
        "row_label": "其中：本币委外（市值法）",
        "sort_order": 87,
        "bond_types": ("其他",),
        "instrument_prefixes": ("J0",),
        "instrument_codes": ("J02205260102", "J02503280102", "J02512240102"),
        "source_note": "ZQTZSHOW 其中项：J0 市值法产品清单",
    },
    {
        "row_key": "asset_zqtz_detail_local_currency_special_account_cost",
        "row_label": "其中：本币专户（成本法）",
        "sort_order": 88,
        "bond_types": ("其他",),
        "instrument_prefixes": ("J0",),
        "exclude_instrument_codes": ("J02205260102", "J02503280102", "J02512240102"),
        "source_note": "ZQTZSHOW 其中项：J0 剔除市值法产品后的成本法专户",
    },
    {
        "row_key": "asset_zqtz_other_debt_financing",
        "row_label": "其他债权融资类产品",
        "sort_order": 90,
        "bond_types": ("其他",),
        "instrument_prefixes": ("JM",),
        "source_note": "ZQTZSHOW bond_type=其他 and instrument_code prefix=JM",
    },
]


@dataclass
class AccountingAssetMovementRepository:
    path: str

    def _connect(self) -> duckdb.DuckDBPyConnection:
        try:
            return duckdb.connect(self.path, read_only=True)
        except duckdb.Error as exc:
            if "different configuration" not in str(exc).lower():
                raise
            return duckdb.connect(self.path, read_only=False)

    def list_report_dates(self, *, currency_basis: str = "CNX") -> list[str]:
        try:
            conn = self._connect()
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
            conn = self._connect()
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
            conn = self._connect()
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
            conn = self._connect()
            rows: list[dict[str, object]] = []
            for date_value in report_dates:
                rows.extend(
                    self._fetch_ledger_business_rows(
                        conn,
                        report_date=date_value,
                        currency_basis=currency_basis,
                    )
                )
                rows.extend(
                    self._fetch_zqtz_asset_rows(
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

    def fetch_basis_movement_components(
        self,
        *,
        report_date: str,
        currency_basis: str = "CNX",
    ) -> dict[str, object]:
        table = "product_category_pnl_canonical_fact"
        try:
            conn = self._connect()
            if not self._table_exists(conn, table):
                return {
                    "status": "unsupported_missing_columns",
                    "missing_columns": [table],
                    "components": [],
                }
            required_columns = [
                "report_date",
                "currency",
                "account_code",
                "account_name",
                "beginning_balance",
                "ending_balance",
            ]
            missing_columns = [
                column
                for column in required_columns
                if not self._column_exists(conn, table, column)
            ]
            if missing_columns:
                return {
                    "status": "unsupported_missing_columns",
                    "missing_columns": missing_columns,
                    "components": [],
                }
            source_version_expr = (
                "coalesce(string_agg(distinct nullif(source_version, ''), '__' order by nullif(source_version, '')), '')"
                if self._column_exists(conn, table, "source_version")
                else "''"
            )
            rule_version_expr = (
                "coalesce(string_agg(distinct nullif(rule_version, ''), '__' order by nullif(rule_version, '')), '')"
                if self._column_exists(conn, table, "rule_version")
                else "''"
            )
            rows = conn.execute(
                f"""
                select
                  case
                    when account_code like '141%' then 'TPL'
                    when account_code like '142%' or account_code like '143%' then 'AC'
                    when account_code like '1440101%' then 'OCI'
                  end as basis_bucket,
                  account_code,
                  coalesce(account_name, '') as account_name,
                  coalesce(sum(beginning_balance), 0) as previous_balance,
                  coalesce(sum(ending_balance), 0) as current_balance,
                  {source_version_expr} as source_version,
                  {rule_version_expr} as rule_version
                from {table}
                where cast(report_date as varchar) = ?
                  and currency = ?
                  and account_code not like '144020%'
                  and (
                    account_code like '141%'
                    or account_code like '142%'
                    or account_code like '143%'
                    or account_code like '1440101%'
                  )
                group by 1, account_code, account_name
                order by 1, account_code
                """,
                [report_date, currency_basis],
            ).fetchall()
        except duckdb.Error as exc:
            return {
                "status": "unsupported_missing_columns",
                "missing_columns": [str(exc)],
                "components": [],
            }
        finally:
            if "conn" in locals():
                conn.close()

        components = [
            {
                "basis_bucket": str(row[0]),
                "account_code": str(row[1]),
                "account_name": str(row[2] or ""),
                "previous_balance": Decimal(str(row[3] or "0")),
                "current_balance": Decimal(str(row[4] or "0")),
                "source_version": str(row[5] or ""),
                "rule_version": str(row[6] or ""),
            }
            for row in rows
            if row[0] is not None
        ]
        return {
            "status": "supported" if components else "no_data",
            "missing_columns": [],
            "components": components,
        }

    def fetch_zqtz_asset_drilldown_rows(
        self,
        *,
        report_dates: list[str],
        currency_basis: str = "CNX",
    ) -> dict[str, object]:
        table = "fact_formal_zqtz_balance_daily"
        zqtz_currency_basis = "CNY" if currency_basis.upper() == "CNX" else currency_basis
        if not report_dates:
            return {
                "status": "no_data",
                "missing_columns": [],
                "zqtz_currency_basis": zqtz_currency_basis,
                "rows": [],
            }
        try:
            conn = self._connect()
            if not self._table_exists(conn, table):
                return {
                    "status": "unsupported_missing_columns",
                    "missing_columns": [table],
                    "zqtz_currency_basis": zqtz_currency_basis,
                    "rows": [],
                }
            filter_sql, filter_params = self._zqtz_primary_asset_predicate(conn)
            if filter_sql == "false":
                return {
                    "status": "no_data",
                    "missing_columns": [],
                    "zqtz_currency_basis": zqtz_currency_basis,
                    "rows": [],
                }
            missing_columns = [
                column
                for column in ("maturity_date", "issuer_name", "rating", "industry_name")
                if not self._column_exists(conn, table, column)
            ]
            select_exprs = {
                column: (
                    f"cast({column} as varchar) as {column}"
                    if column not in missing_columns
                    else f"cast(null as varchar) as {column}"
                )
                for column in ("maturity_date", "issuer_name", "rating", "industry_name")
            }
            amount_expr = self._zqtz_amount_expression(conn)
            rows = conn.execute(
                f"""
                select
                  cast(report_date as varchar) as report_date,
                  {amount_expr} as amount,
                  {select_exprs["maturity_date"]},
                  {select_exprs["issuer_name"]},
                  {select_exprs["rating"]},
                  {select_exprs["industry_name"]}
                from {table}
                where cast(report_date as varchar) in (select unnest(?))
                  and currency_basis = ?
                  and position_scope = 'asset'
                  and ({filter_sql})
                """,
                [report_dates, zqtz_currency_basis, *filter_params],
            ).fetchall()
        except duckdb.Error as exc:
            return {
                "status": "unsupported_missing_columns",
                "missing_columns": [str(exc)],
                "zqtz_currency_basis": zqtz_currency_basis,
                "rows": [],
            }
        finally:
            if "conn" in locals():
                conn.close()

        keys = [
            "report_date",
            "amount",
            "maturity_date",
            "issuer_name",
            "rating",
            "industry_name",
        ]
        return {
            "status": "supported",
            "missing_columns": missing_columns,
            "zqtz_currency_basis": zqtz_currency_basis,
            "rows": [
                {
                    key: Decimal(str(value or "0")) if key == "amount" else value
                    for key, value in zip(keys, row, strict=True)
                }
                for row in rows
            ],
        }

    def _fetch_rows_for_dates(
        self,
        *,
        report_dates: list[str],
        currency_basis: str,
    ) -> list[dict[str, object]]:
        if not report_dates:
            return []
        try:
            conn = self._connect()
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
            conn = self._connect()
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
        amount_expr = self._zqtz_amount_expression(conn)
        fetched = conn.execute(
            f"""
            select
              coalesce(sum({amount_expr}), 0) as current_balance,
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

    def _fetch_zqtz_asset_rows(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        report_date: str,
        currency_basis: str,
    ) -> list[dict[str, object]]:
        return [
            self._fetch_zqtz_asset_row(
                conn,
                report_date=report_date,
                currency_basis=currency_basis,
                row_def=row_def,
            )
            for row_def in _ZQTZ_ASSET_ROWS
        ]

    def _fetch_zqtz_asset_row(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        report_date: str,
        currency_basis: str,
        row_def: dict[str, object],
    ) -> dict[str, object]:
        full_row_def = {**row_def, "side": "asset"}
        source_note = str(row_def.get("source_note", "ZQTZSHOW asset classification"))
        zqtz_currency_basis = "CNY" if currency_basis.upper() == "CNX" else currency_basis
        if not self._table_exists(conn, "fact_formal_zqtz_balance_daily"):
            return self._business_row(
                report_date=report_date,
                currency_basis=currency_basis,
                row_def=full_row_def,
                current_balance=Decimal("0"),
                source_kind="zqtz",
                source_note=source_note,
                source_version="",
                rule_version="",
            )

        filter_sql, params = self._zqtz_asset_predicate(conn, row_def)
        if filter_sql == "false":
            return self._business_row(
                report_date=report_date,
                currency_basis=currency_basis,
                row_def=full_row_def,
                current_balance=Decimal("0"),
                source_kind="zqtz",
                source_note=source_note,
                source_version="",
                rule_version="",
            )

        amount_expr = self._zqtz_amount_expression(conn)
        fetched = conn.execute(
            f"""
            select
              coalesce(sum({amount_expr}), 0) as current_balance,
              coalesce(string_agg(distinct nullif(source_version, ''), '__' order by nullif(source_version, '')), '') as source_version,
              coalesce(string_agg(distinct nullif(rule_version, ''), '__' order by nullif(rule_version, '')), '') as rule_version
            from fact_formal_zqtz_balance_daily
            where cast(report_date as varchar) = ?
              and currency_basis = ?
              and position_scope = 'asset'
              and ({filter_sql})
            """,
            [report_date, zqtz_currency_basis, *params],
        ).fetchone()
        return self._business_row(
            report_date=report_date,
            currency_basis=currency_basis,
            row_def=full_row_def,
            current_balance=Decimal(str(fetched[0] if fetched else "0")),
            source_kind="zqtz",
            source_note=source_note,
            source_version=str(fetched[1] if fetched else ""),
            rule_version=str(fetched[2] if fetched else ""),
        )

    def _zqtz_asset_predicate(
        self,
        conn: duckdb.DuckDBPyConnection,
        row_def: dict[str, object],
    ) -> tuple[str, list[str]]:
        table = "fact_formal_zqtz_balance_daily"
        parts: list[str] = []
        params: list[str] = []
        match_keywords = tuple(str(value) for value in row_def.get("match_keywords", ()))
        if match_keywords:
            keyword_sql, keyword_params = self._zqtz_keyword_predicate(conn, match_keywords)
            if keyword_sql == "false":
                return "false", []
            parts.append(f"({keyword_sql})")
            params.extend(keyword_params)

        bond_types = tuple(str(value) for value in row_def.get("bond_types", ()))
        if bond_types:
            bond_type_parts: list[str] = []
            placeholders = ", ".join("?" for _ in bond_types)
            if self._column_exists(conn, table, "bond_type"):
                bond_type_parts.append(f"bond_type in ({placeholders})")
                params.extend(bond_types)
            if self._column_exists(conn, table, "business_type_primary"):
                bond_type_parts.append(f"business_type_primary in ({placeholders})")
                params.extend(bond_types)
            if not bond_type_parts:
                return "false", []
            parts.append("(" + " or ".join(bond_type_parts) + ")")

        exclude_bond_types = tuple(str(value) for value in row_def.get("exclude_bond_types", ()))
        if exclude_bond_types:
            if not self._column_exists(conn, table, "bond_type"):
                return "false", []
            placeholders = ", ".join("?" for _ in exclude_bond_types)
            parts.append(f"(bond_type is null or bond_type not in ({placeholders}))")
            params.extend(exclude_bond_types)

        instrument_prefixes = tuple(str(value) for value in row_def.get("instrument_prefixes", ()))
        if instrument_prefixes:
            if not self._column_exists(conn, table, "instrument_code"):
                return "false", []
            parts.append(
                "("
                + " or ".join("upper(instrument_code) like ?" for _ in instrument_prefixes)
                + ")"
            )
            params.extend(f"{prefix.upper()}%" for prefix in instrument_prefixes)

        exclude_instrument_prefixes = tuple(
            str(value) for value in row_def.get("exclude_instrument_prefixes", ())
        )
        if exclude_instrument_prefixes:
            if not self._column_exists(conn, table, "instrument_code"):
                return "false", []
            for prefix in exclude_instrument_prefixes:
                parts.append("(instrument_code is null or upper(instrument_code) not like ?)")
                params.append(f"{prefix.upper()}%")

        instrument_codes = tuple(str(value) for value in row_def.get("instrument_codes", ()))
        if instrument_codes:
            if not self._column_exists(conn, table, "instrument_code"):
                return "false", []
            placeholders = ", ".join("?" for _ in instrument_codes)
            parts.append(f"upper(instrument_code) in ({placeholders})")
            params.extend(code.upper() for code in instrument_codes)

        exclude_instrument_codes = tuple(
            str(value) for value in row_def.get("exclude_instrument_codes", ())
        )
        if exclude_instrument_codes:
            if not self._column_exists(conn, table, "instrument_code"):
                return "false", []
            placeholders = ", ".join("?" for _ in exclude_instrument_codes)
            parts.append(
                f"(instrument_code is null or upper(instrument_code) not in ({placeholders}))"
            )
            params.extend(code.upper() for code in exclude_instrument_codes)

        name_contains = tuple(str(value) for value in row_def.get("name_contains", ()))
        if name_contains:
            if not self._column_exists(conn, table, "instrument_name"):
                return "false", []
            parts.append(
                "(" + " or ".join("instrument_name like ?" for _ in name_contains) + ")"
            )
            params.extend(f"%{value}%" for value in name_contains)

        exclude_name_contains = tuple(
            str(value) for value in row_def.get("exclude_name_contains", ())
        )
        if exclude_name_contains:
            if not self._column_exists(conn, table, "instrument_name"):
                return "false", []
            for value in exclude_name_contains:
                parts.append("(instrument_name is null or instrument_name not like ?)")
                params.append(f"%{value}%")

        accounting_bases = tuple(str(value) for value in row_def.get("accounting_bases", ()))
        if accounting_bases:
            if not self._column_exists(conn, table, "accounting_basis"):
                return "false", []
            placeholders = ", ".join("?" for _ in accounting_bases)
            parts.append(f"accounting_basis in ({placeholders})")
            params.extend(accounting_bases)

        currency_codes_exclude = tuple(str(value) for value in row_def.get("currency_codes_exclude", ()))
        if currency_codes_exclude:
            if not self._column_exists(conn, table, "currency_code"):
                return "false", []
            placeholders = ", ".join("?" for _ in currency_codes_exclude)
            parts.append(f"coalesce(currency_code, '') not in ({placeholders})")
            params.extend(currency_codes_exclude)
        elif (bond_types or match_keywords) and not instrument_prefixes and not row_def.get(
            "include_foreign_currency"
        ):
            if self._column_exists(conn, table, "currency_code"):
                parts.append("(currency_code is null or currency_code = '' or currency_code = 'CNY')")
            elif row_def.get("row_key") != "asset_zqtz_interbank_cd":
                return "false", []

        if not parts:
            return "false", []
        return " and ".join(parts), params

    def _zqtz_primary_asset_predicate(
        self,
        conn: duckdb.DuckDBPyConnection,
    ) -> tuple[str, list[str]]:
        clauses: list[str] = []
        params: list[str] = []
        for row_def in _ZQTZ_ASSET_ROWS:
            if str(row_def.get("row_key", "")).startswith("asset_zqtz_detail_"):
                continue
            clause, clause_params = self._zqtz_asset_predicate(conn, row_def)
            if clause == "false":
                continue
            clauses.append(f"({clause})")
            params.extend(clause_params)
        if not clauses:
            return "false", []
        return " or ".join(clauses), params

    def _zqtz_keyword_predicate(
        self,
        conn: duckdb.DuckDBPyConnection,
        keywords: tuple[str, ...],
    ) -> tuple[str, list[str]]:
        table = "fact_formal_zqtz_balance_daily"
        searchable_columns = [
            column
            for column in (
                "sub_type",
                "business_type_final",
                "business_type_primary",
                "bond_type",
                "instrument_name",
                "asset_class",
            )
            if self._column_exists(conn, table, column)
        ]
        terms: list[str] = []
        params: list[str] = []
        for keyword in keywords:
            for column in searchable_columns:
                terms.append(f"{column} like ?")
                params.append(f"%{keyword}%")

        if self._table_exists(conn, "phase1_zqtz_preview_rows") and self._column_exists(
            conn,
            table,
            "instrument_code",
        ):
            preview_terms: list[str] = []
            preview_params: list[str] = []
            for column in ("sub_type", "business_type_final", "business_type_primary"):
                if not self._column_exists(conn, "phase1_zqtz_preview_rows", column):
                    continue
                for keyword in keywords:
                    preview_terms.append(f"p.{column} like ?")
                    preview_params.append(f"%{keyword}%")
            if preview_terms:
                lineage_terms = []
                for column in ("ingest_batch_id", "source_version"):
                    if self._column_exists(conn, table, column) and self._column_exists(
                        conn,
                        "phase1_zqtz_preview_rows",
                        column,
                    ):
                        lineage_terms.append(
                            f"and coalesce(p.{column}, '') = coalesce(fact_formal_zqtz_balance_daily.{column}, '')"
                        )
                terms.append(
                    """
                    exists (
                      select 1
                      from phase1_zqtz_preview_rows p
                      where cast(p.report_date as varchar) = cast(fact_formal_zqtz_balance_daily.report_date as varchar)
                        and p.instrument_code = fact_formal_zqtz_balance_daily.instrument_code
                        {lineage_sql}
                        and (
                    """
                    .format(lineage_sql="\n                        ".join(lineage_terms))
                    + " or ".join(preview_terms)
                    + "))"
                )
                params.extend(preview_params)

        if not terms:
            return "false", []
        return " or ".join(terms), params

    def _zqtz_amount_expression(self, conn: duckdb.DuckDBPyConnection) -> str:
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
        voucher_terms = []
        if self._column_exists(conn, table, "business_type_primary"):
            voucher_terms.append("business_type_primary = '凭证式国债'")
        if self._column_exists(conn, table, "bond_type"):
            voucher_terms.append("bond_type = '凭证式国债'")
        if self._column_exists(conn, table, "instrument_name"):
            voucher_terms.append("instrument_name like '%凭证式%'")
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

    def fetch_structure_diagnostic_inputs(
        self,
        *,
        report_dates: list[str],
        currency_basis: str = "CNX",
    ) -> dict[str, dict[str, Decimal]]:
        if not report_dates:
            return {}
        try:
            conn = self._connect()
            if not self._table_exists(conn, "product_category_pnl_canonical_fact"):
                return {}
            rows = conn.execute(
                """
                select
                  cast(report_date as varchar) as report_date,
                  coalesce(sum(
                    case
                      when account_code like '1440101%'
                       and (account_code = '14401010004' or account_name like '%公允价值变动%')
                      then ending_balance
                      else 0
                    end
                  ), 0) as oci_fair_value_balance,
                  coalesce(sum(
                    case
                      when account_code like '141%'
                       and account_name like '%公允价值变动%'
                      then ending_balance
                      else 0
                    end
                  ), 0) as fvtpl_fair_value_balance
                from product_category_pnl_canonical_fact
                where cast(report_date as varchar) in (select unnest(?))
                  and currency = ?
                group by 1
                """,
                [report_dates, currency_basis],
            ).fetchall()
        except duckdb.Error:
            return {}
        finally:
            if "conn" in locals():
                conn.close()

        return {
            str(row[0]): {
                "oci_fair_value_balance": Decimal(str(row[1] or "0")),
                "fvtpl_fair_value_balance": Decimal(str(row[2] or "0")),
            }
            for row in rows
        }

    def fetch_difference_attribution_inputs(
        self,
        *,
        report_date: str,
        currency_basis: str = "CNX",
    ) -> dict[str, Decimal]:
        out = {
            "ledger_voucher_cost": Decimal("0"),
            "ledger_voucher_accrued_interest": Decimal("0"),
            "formal_voucher_amortized_cost": Decimal("0"),
            "formal_voucher_accrued_interest": Decimal("0"),
        }
        try:
            conn = self._connect()
            if self._table_exists(conn, "product_category_pnl_canonical_fact"):
                ledger = conn.execute(
                    """
                    select
                      coalesce(sum(case when account_code = '14301010001' then ending_balance else 0 end), 0),
                      coalesce(sum(case when account_code = '14301010002' then ending_balance else 0 end), 0)
                    from product_category_pnl_canonical_fact
                    where cast(report_date as varchar) = ?
                      and currency = ?
                    """,
                    [report_date, currency_basis],
                ).fetchone()
                out["ledger_voucher_cost"] = Decimal(str(ledger[0] if ledger else "0"))
                out["ledger_voucher_accrued_interest"] = Decimal(
                    str(ledger[1] if ledger else "0")
                )

            if self._table_exists(conn, "fact_formal_zqtz_balance_daily"):
                zqtz_currency_basis = "CNY" if currency_basis.upper() == "CNX" else currency_basis
                voucher_predicates: list[str] = []
                voucher_params: list[str] = []
                if self._column_exists(conn, "fact_formal_zqtz_balance_daily", "business_type_primary"):
                    voucher_predicates.append("business_type_primary = ?")
                    voucher_params.append("凭证式国债")
                if self._column_exists(conn, "fact_formal_zqtz_balance_daily", "bond_type"):
                    voucher_predicates.append("bond_type = ?")
                    voucher_params.append("凭证式国债")
                if self._column_exists(conn, "fact_formal_zqtz_balance_daily", "instrument_name"):
                    voucher_predicates.append("instrument_name like ?")
                    voucher_params.append("%凭证式%")
                amortized_amount_expr = (
                    "coalesce(amortized_cost_amount, 0)"
                    if self._column_exists(
                        conn,
                        "fact_formal_zqtz_balance_daily",
                        "amortized_cost_amount",
                    )
                    else "0"
                )
                market_amount_expr = (
                    "coalesce(market_value_amount, 0)"
                    if self._column_exists(
                        conn,
                        "fact_formal_zqtz_balance_daily",
                        "market_value_amount",
                    )
                    else "0"
                )
                face_amount_expr = (
                    "coalesce(face_value_amount, 0)"
                    if self._column_exists(
                        conn,
                        "fact_formal_zqtz_balance_daily",
                        "face_value_amount",
                    )
                    else "0"
                )
                voucher_cost_basis_expr = (
                    f"coalesce(nullif({amortized_amount_expr}, 0), "
                    f"nullif({market_amount_expr}, 0), {face_amount_expr}, 0)"
                )
                accrued_expr = (
                    "coalesce(accrued_interest_amount, 0)"
                    if self._column_exists(
                        conn,
                        "fact_formal_zqtz_balance_daily",
                        "accrued_interest_amount",
                    )
                    else "0"
                )
                if not voucher_predicates:
                    return out
                formal = conn.execute(
                    f"""
                    select
                      coalesce(sum({voucher_cost_basis_expr}), 0),
                      coalesce(sum({accrued_expr}), 0)
                    from fact_formal_zqtz_balance_daily
                    where cast(report_date as varchar) = ?
                      and currency_basis = ?
                      and position_scope = 'asset'
                      and ({" or ".join(voucher_predicates)})
                    """,
                    [report_date, zqtz_currency_basis, *voucher_params],
                ).fetchone()
                out["formal_voucher_amortized_cost"] = Decimal(
                    str(formal[0] if formal else "0")
                )
                out["formal_voucher_accrued_interest"] = Decimal(
                    str(formal[1] if formal else "0")
                )
        except duckdb.Error:
            return out
        finally:
            if "conn" in locals():
                conn.close()
        return out

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
