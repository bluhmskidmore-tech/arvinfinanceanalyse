from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import duckdb
from backend.app.core_finance.zqtz_asset_bond_category import ZQTZ_ASSET_BOND_ROWS as _ZQTZ_ASSET_ROWS
from backend.app.repositories.duckdb_repo import read_only_connection

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


def _is_missing_table_error(exc: duckdb.Error) -> bool:
    message = str(exc).lower()
    return (
        isinstance(exc, duckdb.CatalogException)
        and "table with name" in message
        and "does not exist" in message
    )


_ZQTZ_NCD_ROW = {
    "row_key": "asset_zqtz_interbank_cd",
    "row_label": "资产端-同业存单",
    "side": "asset",
    "sort_order": 60,
}

_MOVEMENT_FACT_TABLE = "fact_accounting_asset_movement_monthly"
# registry slice 42 追加的落库控制结论列。
_MOVEMENT_CONTROL_COLUMNS = ("chain_status", "position_source_basis")


@dataclass
class AccountingAssetMovementRepository:
    path: str
    _table_exists_cache: dict[str, bool] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _column_exists_cache: dict[tuple[str, str], bool] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(self.path, read_only=True)

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
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
            return []
        finally:
            if "conn" in locals():
                conn.close()
        return [str(row[0]) for row in rows]

    def list_control_report_dates(self, *, currency_basis: str = "CNX") -> list[str]:
        try:
            conn = self._connect()
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
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
            return []
        finally:
            if "conn" in locals():
                conn.close()
        return [str(row[0]) for row in rows]

    def fetch_missing_control_dates(
        self,
        *,
        report_dates: list[str],
        currency_basis: str,
    ) -> list[str]:
        """report_dates lacking product_category_pnl_canonical_fact control-account rows.

        Fails open (treats every requested date as missing) on any DuckDB error
        or absent table, so refresh callers retry materialization rather than
        silently skipping it.
        """
        if not report_dates:
            return []
        try:
            with read_only_connection(self.path) as conn:
                if not self._table_exists(conn, "product_category_pnl_canonical_fact"):
                    return report_dates
                rows = conn.execute(
                    """
                    select cast(report_date as varchar) as report_date, count(*) as row_count
                    from product_category_pnl_canonical_fact
                    where cast(report_date as varchar) in (select unnest(?))
                      and currency = ?
                      and (
                        account_code like '141%'
                        or account_code like '142%'
                        or account_code like '143%'
                        or account_code like '1440101%'
                      )
                    group by 1
                    """,
                    [report_dates, currency_basis],
                ).fetchall()
        except duckdb.Error:
            return report_dates

        available_dates = {str(row[0]) for row in rows if int(row[1] or 0) > 0}
        return [
            current_report_date
            for current_report_date in report_dates
            if current_report_date not in available_dates
        ]

    def control_source_versions(
        self,
        *,
        currency_basis: str = "CNX",
    ) -> dict[str, str]:
        try:
            conn = self._connect()
            rows = conn.execute(
                """
                select
                  cast(report_date as varchar),
                  coalesce(
                    string_agg(
                      distinct nullif(source_version, ''),
                      '__' order by nullif(source_version, '')
                    ),
                    ''
                  )
                from product_category_pnl_canonical_fact
                where currency = ?
                  and (
                    account_code like '141%'
                    or account_code like '142%'
                    or account_code like '143%'
                    or account_code like '1440101%'
                  )
                group by 1
                order by 1 desc
                """,
                [currency_basis],
            ).fetchall()
        except duckdb.Error as exc:
            message = str(exc).lower()
            if _is_missing_table_error(exc) or "source_version" in message:
                return {}
            raise
        finally:
            if "conn" in locals():
                conn.close()
        return {str(row[0]): str(row[1] or "") for row in rows}

    def latest_control_report_date(self, *, currency_basis: str = "CNX") -> str | None:
        try:
            conn = self._connect()
            row = conn.execute(
                """
                select max(cast(report_date as varchar))
                from product_category_pnl_canonical_fact
                where currency = ?
                  and (
                    account_code like '141%'
                    or account_code like '142%'
                    or account_code like '143%'
                    or account_code like '1440101%'
                  )
                """,
                [currency_basis],
            ).fetchone()
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
            return None
        finally:
            if "conn" in locals():
                conn.close()
        if row is None or row[0] is None:
            return None
        return str(row[0])

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
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
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

    def fetch_reconciliation_breaches(
        self,
        *,
        currency_basis: str = "CNX",
        report_dates: list[str] | None = None,
    ) -> list[dict[str, object]]:
        """已落库的、reconciliation_status != 'matched' 的行。

        对账控制的只读取证入口：全部返回 matched 说明控制没有在比对独立数据源，
        或者两侧真的完全一致——两者可以用 fetch_position_source_coverage 区分。
        """
        date_filter = (
            "and cast(report_date as varchar) in (select unnest(?))"
            if report_dates
            else ""
        )
        params: list[object] = [currency_basis]
        if report_dates:
            params.append(report_dates)
        try:
            with read_only_connection(self.path) as conn:
                if not self._table_exists(conn, _MOVEMENT_FACT_TABLE):
                    return []
                control_columns = ", ".join(
                    column
                    if self._column_exists(conn, _MOVEMENT_FACT_TABLE, column)
                    else f"cast(null as varchar) as {column}"
                    for column in _MOVEMENT_CONTROL_COLUMNS
                )
                rows = conn.execute(
                    f"""
                    select
                      cast(report_date as varchar),
                      basis_bucket,
                      reconciliation_status,
                      coalesce(zqtz_amount, 0),
                      coalesce(gl_amount, 0),
                      coalesce(reconciliation_diff, 0),
                      {control_columns}
                    from fact_accounting_asset_movement_monthly
                    where currency_basis = ?
                      and coalesce(reconciliation_status, '') <> 'matched'
                      {date_filter}
                    order by cast(report_date as varchar), basis_bucket
                    """,
                    params,
                ).fetchall()
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
            return []
        keys = (
            "report_date",
            "basis_bucket",
            "reconciliation_status",
            "zqtz_amount",
            "gl_amount",
            "reconciliation_diff",
            *_MOVEMENT_CONTROL_COLUMNS,
        )
        numeric_keys = {"zqtz_amount", "gl_amount", "reconciliation_diff"}
        return [
            {
                key: (
                    Decimal(str(value or "0"))
                    if key in numeric_keys
                    # 控制结论列保留 None：迁移落地前写入的行"未记录"，不能被
                    # str() 成 'None' 混进已判定的取值里。
                    else (None if key in _MOVEMENT_CONTROL_COLUMNS and value is None else str(value))
                )
                for key, value in zip(keys, row, strict=True)
            }
            for row in rows
        ]

    def fetch_chain_continuity_gaps(
        self,
        *,
        currency_basis: str = "CNX",
        tolerance: Decimal = Decimal("0.01"),
    ) -> list[dict[str, object]]:
        """逐桶比较 previous_balance(M) 与 current_balance(M-1)，返回超容差的衔接。

        行内的 balance_change := current - previous 在代数上必然闭合，对跨月
        衔接零覆盖；这个方法是从读模型侧证伪该口径的唯一手段。
        """
        try:
            with read_only_connection(self.path) as conn:
                if not self._table_exists(conn, "fact_accounting_asset_movement_monthly"):
                    return []
                rows = conn.execute(
                    """
                    with ordered as (
                      select
                        cast(report_date as varchar) as report_date,
                        basis_bucket,
                        coalesce(previous_balance, 0) as previous_balance,
                        coalesce(current_balance, 0) as current_balance,
                        lag(cast(report_date as varchar)) over w as prior_report_date,
                        lag(coalesce(current_balance, 0)) over w as prior_current_balance
                      from fact_accounting_asset_movement_monthly
                      where currency_basis = ?
                      window w as (
                        partition by basis_bucket
                        order by cast(report_date as varchar)
                      )
                    )
                    select
                      report_date,
                      basis_bucket,
                      prior_report_date,
                      prior_current_balance,
                      previous_balance,
                      previous_balance - prior_current_balance as gap
                    from ordered
                    where prior_report_date is not null
                      and abs(previous_balance - prior_current_balance) > ?
                    order by report_date, basis_bucket
                    """,
                    [currency_basis, tolerance],
                ).fetchall()
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
            return []
        keys = (
            "report_date",
            "basis_bucket",
            "prior_report_date",
            "prior_current_balance",
            "previous_balance",
            "gap",
        )
        return [
            {
                key: Decimal(str(value or "0")) if key not in {"report_date", "basis_bucket", "prior_report_date"} else str(value)
                for key, value in zip(keys, row, strict=True)
            }
            for row in rows
        ]

    def fetch_position_source_coverage(
        self,
        *,
        report_dates: list[str],
        currency_basis: str = "CNX",
    ) -> dict[str, dict[str, object]]:
        """每个报告日在独立头寸源里实际可用的 currency_basis 与行数。

        总账用 CNX 标记本外币折人民币口径，fact_formal_zqtz_balance_daily 用
        CNY 表示同一口径（native 才是原币），所以这里按 CNX -> CNY 的既有别名
        回退。两个口径都没有行时 resolved_currency_basis 为 None，调用方必须把
        该日视为"对账无对手方"，不能当成对平。
        """
        if not report_dates:
            return {}
        table = "fact_formal_zqtz_balance_daily"
        candidates = ("CNX", "CNY") if currency_basis.upper() == "CNX" else (currency_basis,)
        coverage: dict[str, dict[str, object]] = {
            report_date: {
                "resolved_currency_basis": None,
                "row_count": 0,
                "candidates": list(candidates),
            }
            for report_date in report_dates
        }
        try:
            with read_only_connection(self.path) as conn:
                if not self._table_exists(conn, table):
                    return coverage
                rows = conn.execute(
                    f"""
                    select
                      cast(report_date as varchar),
                      currency_basis,
                      count(*)
                    from {table}
                    where cast(report_date as varchar) in (select unnest(?))
                      and currency_basis in (select unnest(?))
                      and position_scope = 'asset'
                    group by 1, 2
                    """,
                    [report_dates, list(candidates)],
                ).fetchall()
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
            return coverage

        counts_by_date: dict[str, dict[str, int]] = {}
        for report_date, basis, row_count in rows:
            counts_by_date.setdefault(str(report_date), {})[str(basis)] = int(row_count or 0)
        for report_date, counts in counts_by_date.items():
            for candidate in candidates:
                if counts.get(candidate, 0) > 0:
                    coverage[report_date] = {
                        "resolved_currency_basis": candidate,
                        "row_count": counts[candidate],
                        "candidates": list(candidates),
                    }
                    break
        return coverage

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
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
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
            rows: list[dict[str, Any]] = []
            for date_value in report_dates:
                rows.extend(
                    self._fetch_ledger_business_rows(
                        conn,
                        report_date=date_value,
                        currency_basis=currency_basis,
                    )
                )
            rows.extend(
                self._fetch_zqtz_asset_rows_for_dates(
                    conn,
                    report_dates=report_dates,
                    currency_basis=currency_basis,
                )
            )
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
            return []
        finally:
            if "conn" in locals():
                conn.close()
        ordered: list[dict[str, Any]] = sorted(
            rows,
            key=lambda row: (str(row["report_date"]), -int(row["sort_order"])),
            reverse=True,
        )
        return ordered

    def fetch_zqtz_asset_business_rows(
        self,
        *,
        report_date: str,
        currency_basis: str = "CNX",
    ) -> list[dict[str, object]]:
        try:
            conn = self._connect()
            return self._fetch_zqtz_asset_rows(
                conn,
                report_date=report_date,
                currency_basis=currency_basis,
            )
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
            return []
        finally:
            if "conn" in locals():
                conn.close()

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
            if not _is_missing_table_error(exc):
                raise
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
            required_columns = ("report_date", "currency_basis", "position_scope")
            missing_required_columns = [
                column
                for column in required_columns
                if not self._column_exists(conn, table, column)
            ]
            if missing_required_columns:
                return {
                    "status": "unsupported_missing_columns",
                    "missing_columns": missing_required_columns,
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
            concentration_columns = ("maturity_date", "issuer_name", "rating", "industry_name")
            descriptor_columns = (
                "bond_type",
                "business_type_primary",
                "business_type_final",
                "sub_type",
                "instrument_name",
            )
            missing_columns = [
                column
                for column in concentration_columns
                if not self._column_exists(conn, table, column)
            ]
            select_exprs = {
                column: (
                    f"cast({column} as varchar) as {column}"
                    if self._column_exists(conn, table, column)
                    else f"cast(null as varchar) as {column}"
                )
                for column in (*concentration_columns, *descriptor_columns)
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
                  {select_exprs["industry_name"]},
                  {select_exprs["bond_type"]},
                  {select_exprs["business_type_primary"]},
                  {select_exprs["business_type_final"]},
                  {select_exprs["sub_type"]},
                  {select_exprs["instrument_name"]}
                from {table}
                where cast(report_date as varchar) in (select unnest(?))
                  and currency_basis = ?
                  and position_scope = 'asset'
                  and ({filter_sql})
                """,
                [report_dates, zqtz_currency_basis, *filter_params],
            ).fetchall()
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
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
            "bond_type",
            "business_type_primary",
            "business_type_final",
            "sub_type",
            "instrument_name",
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
            # 控制结论列由 registry slice 42 追加。迁移应用前这两列不存在，读路径
            # 必须继续供数（按未记录处理），不能因为一次尚未落地的迁移而 500。
            control_columns = ", ".join(
                column
                if self._column_exists(conn, _MOVEMENT_FACT_TABLE, column)
                else f"cast(null as varchar) as {column}"
                for column in _MOVEMENT_CONTROL_COLUMNS
            )
            rows = conn.execute(
                f"""
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
                  rule_version,
                  {control_columns}
                from fact_accounting_asset_movement_monthly
                where report_date in (select unnest(?))
                  and currency_basis = ?
                order by report_date desc, sort_order
                """,
                [report_dates, currency_basis],
            ).fetchall()
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
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
            *_MOVEMENT_CONTROL_COLUMNS,
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
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
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

    def _fetch_zqtz_asset_rows_for_dates(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        report_dates: list[str],
        currency_basis: str,
    ) -> list[dict[str, object]]:
        if not report_dates:
            return []

        table = "fact_formal_zqtz_balance_daily"
        table_exists = self._table_exists(conn, table)
        zqtz_currency_basis = "CNY" if currency_basis.upper() == "CNX" else currency_basis
        amount_expr = self._zqtz_amount_expression(conn) if table_exists else "0"
        rows_by_date: dict[str, list[dict[str, object]]] = {
            report_date: [] for report_date in report_dates
        }

        for row_def in _ZQTZ_ASSET_ROWS:
            full_row_def = {**row_def, "side": "asset"}
            source_note = str(row_def.get("source_note", "ZQTZSHOW asset classification"))
            fetched_by_date: dict[str, tuple[object, object, object]] = {}
            if table_exists:
                filter_sql, params = self._zqtz_asset_predicate(conn, row_def)
                if filter_sql != "false":
                    fetched_rows = conn.execute(
                        f"""
                        select
                          cast(report_date as varchar) as report_date,
                          coalesce(sum({amount_expr}), 0) as current_balance,
                          coalesce(string_agg(distinct nullif(source_version, ''), '__' order by nullif(source_version, '')), '') as source_version,
                          coalesce(string_agg(distinct nullif(rule_version, ''), '__' order by nullif(rule_version, '')), '') as rule_version
                        from {table}
                        where cast(report_date as varchar) in (select unnest(?))
                          and currency_basis = ?
                          and position_scope = 'asset'
                          and ({filter_sql})
                        group by 1
                        """,
                        [report_dates, zqtz_currency_basis, *params],
                    ).fetchall()
                    fetched_by_date = {
                        str(report_date): (current_balance, source_version, rule_version)
                        for report_date, current_balance, source_version, rule_version in fetched_rows
                    }

            for report_date in report_dates:
                fetched = fetched_by_date.get(report_date)
                rows_by_date[report_date].append(
                    self._business_row(
                        report_date=report_date,
                        currency_basis=currency_basis,
                        row_def=full_row_def,
                        current_balance=Decimal(str(fetched[0] if fetched else "0")),
                        source_kind="zqtz",
                        source_note=source_note,
                        source_version=str(fetched[1] if fetched else ""),
                        rule_version=str(fetched[2] if fetched else ""),
                    )
                )

        return [
            row
            for report_date in report_dates
            for row in rows_by_date[report_date]
        ]

    def _fetch_zqtz_asset_row(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        report_date: str,
        currency_basis: str,
        # row_def 来自 ZQTZ_ASSET_BOND_ROWS（声明为 dict[str, Any]），与上游注解对齐。
        row_def: dict[str, Any],
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
        # row_def 来自 ZQTZ_ASSET_BOND_ROWS（声明为 dict[str, Any]），与上游注解对齐。
        row_def: dict[str, Any],
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

    def _ledger_business_predicate(self, row_def: dict[str, Any]) -> tuple[str, list[str]]:
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
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
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
        except duckdb.Error as exc:
            if not _is_missing_table_error(exc):
                raise
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
        row_def: dict[str, Any],
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
        if table_name in self._table_exists_cache:
            return self._table_exists_cache[table_name]
        row = conn.execute(
            """
            select count(*)
            from information_schema.tables
            where table_name = ?
            """,
            [table_name],
        ).fetchone()
        exists = bool(row and row[0])
        self._table_exists_cache[table_name] = exists
        return exists

    def _column_exists(
        self,
        conn: duckdb.DuckDBPyConnection,
        table_name: str,
        column_name: str,
    ) -> bool:
        cache_key = (table_name, column_name)
        if cache_key in self._column_exists_cache:
            return self._column_exists_cache[cache_key]
        row = conn.execute(
            """
            select count(*)
            from information_schema.columns
            where table_name = ?
              and column_name = ?
            """,
            [table_name, column_name],
        ).fetchone()
        exists = bool(row and row[0])
        self._column_exists_cache[cache_key] = exists
        return exists
