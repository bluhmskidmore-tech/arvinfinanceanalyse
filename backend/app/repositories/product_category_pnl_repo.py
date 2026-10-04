from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
from backend.app.core_finance.product_category_pnl import CanonicalFactRow, ManualAdjustment
from backend.app.repositories.duckdb_read_context import resolve_effective_read_path
from backend.app.repositories.governance_repo import GovernanceRepository

PRODUCT_CATEGORY_ADJUSTMENT_STREAM = "product_category_pnl_adjustments"

# 正式读模型行查询：fetch_rows 执行与外部证据披露（如 agent sql_executed）共用同一份常量。
PRODUCT_CATEGORY_PNL_ROWS_SQL = """
select
  category_id,
  category_name,
  side,
  level,
  view,
  report_date,
  baseline_ftp_rate_pct,
  cnx_scale,
  cny_scale,
  foreign_scale,
  cnx_cash,
  cny_cash,
  foreign_cash,
  cny_ftp,
  foreign_ftp,
  cny_net,
  foreign_net,
  business_net_income,
  weighted_yield,
  is_total,
  children_json,
  source_version,
  rule_version
from product_category_pnl_formal_read_model
where report_date = ? and view = ?
order by sort_order
"""


class ProductCategoryPnlStorageError(RuntimeError):
    pass


@dataclass
class ProductCategoryPnlRepository:
    path: str

    def fetch_canonical_ytd_facts(self, anchor: date) -> dict[date, list[CanonicalFactRow]] | None:
        """Load already-adjusted canonical facts through an existing same-year anchor."""
        report_date = anchor.isoformat()
        try:
            conn = duckdb.connect(resolve_effective_read_path(self.path), read_only=True)
        except (OSError, duckdb.Error):
            return None

        try:
            dates_rows = conn.execute(
                """
                select distinct report_date
                from product_category_pnl_canonical_fact
                where report_date <= ? and substr(report_date, 1, 4) = ?
                order by report_date
                """,
                [report_date, str(anchor.year)],
            ).fetchall()
            date_strings = [str(row[0]) for row in dates_rows]
            if report_date not in date_strings:
                return None

            facts_by: dict[date, list[CanonicalFactRow]] = {}
            for date_string in date_strings:
                rows = conn.execute(
                    """
                    select report_date, account_code, currency, account_name,
                           beginning_balance, ending_balance, monthly_pnl,
                           daily_avg_balance, annual_avg_balance, days_in_period
                    from product_category_pnl_canonical_fact
                    where report_date = ?
                    order by account_code, currency
                    """,
                    [date_string],
                ).fetchall()
                facts_by[date.fromisoformat(date_string)] = [
                    CanonicalFactRow(
                        report_date=date.fromisoformat(str(row[0])),
                        account_code=str(row[1]),
                        currency=str(row[2]),
                        account_name=str(row[3]),
                        beginning_balance=Decimal(str(row[4])),
                        ending_balance=Decimal(str(row[5])),
                        monthly_pnl=Decimal(str(row[6])),
                        daily_avg_balance=Decimal(str(row[7])),
                        annual_avg_balance=Decimal(str(row[8])),
                        days_in_period=int(row[9]),
                    )
                    for row in rows
                ]
            return facts_by
        except duckdb.Error:
            return None
        finally:
            conn.close()

    def list_report_dates(self) -> list[str]:
        try:
            conn = duckdb.connect(resolve_effective_read_path(self.path), read_only=True)
            rows = conn.execute(
                """
                select distinct report_date
                from product_category_pnl_formal_read_model
                order by report_date desc
                """
            ).fetchall()
        except duckdb.Error as exc:
            if _is_missing_read_model_error(exc):
                return []
            raise ProductCategoryPnlStorageError(
                "Product-category read model is temporarily unavailable."
            ) from exc
        finally:
            if "conn" in locals():
                conn.close()
        return [str(row[0]) for row in rows]

    def latest_source_version(self) -> str:
        try:
            conn = duckdb.connect(resolve_effective_read_path(self.path), read_only=True)
            row = conn.execute(
                """
                select source_version
                from product_category_pnl_formal_read_model
                order by report_date desc, sort_order asc
                limit 1
                """
            ).fetchone()
        except duckdb.Error as exc:
            if _is_missing_read_model_error(exc):
                return "sv_product_category_empty"
            raise ProductCategoryPnlStorageError(
                "Product-category read model is temporarily unavailable."
            ) from exc
        finally:
            if "conn" in locals():
                conn.close()
        if row is None:
            return "sv_product_category_empty"
        return str(row[0])

    def fetch_home_headline_values(
        self,
        *,
        report_date: str,
        views: list[str],
    ) -> dict[str, dict[str, object]]:
        requested_views = [str(view).strip() for view in dict.fromkeys(views) if str(view or "").strip()]
        if not requested_views:
            return {}
        categories = ("grand_total", "intermediate_business_income")
        view_placeholders = ", ".join(["?"] * len(requested_views))
        category_placeholders = ", ".join(["?"] * len(categories))
        try:
            conn = duckdb.connect(resolve_effective_read_path(self.path), read_only=True)
            rows = conn.execute(
                f"""
                select view, category_id, business_net_income
                from product_category_pnl_formal_read_model
                where report_date = ?
                  and view in ({view_placeholders})
                  and category_id in ({category_placeholders})
                """,
                [report_date, *requested_views, *categories],
            ).fetchall()
        except duckdb.Error as exc:
            if _is_missing_read_model_error(exc):
                return {}
            raise ProductCategoryPnlStorageError(
                "Product-category read model is temporarily unavailable."
            ) from exc
        finally:
            if "conn" in locals():
                conn.close()
        result: dict[str, dict[str, object]] = {view: {} for view in requested_views}
        for view, category_id, business_net_income in rows:
            result.setdefault(str(view), {})[str(category_id)] = business_net_income
        return result

    def fetch_rows(self, report_date: str, view: str) -> list[dict[str, object]]:
        """Load persisted formal read-model rows only. Scenario FTP is overlaid in analysis_adapters, not stored here."""
        try:
            conn = duckdb.connect(resolve_effective_read_path(self.path), read_only=True)
            rows = conn.execute(
                PRODUCT_CATEGORY_PNL_ROWS_SQL,
                [report_date, view],
            ).fetchall()
        except duckdb.Error as exc:
            if _is_missing_read_model_error(exc):
                return []
            raise ProductCategoryPnlStorageError(
                "Product-category read model is temporarily unavailable."
            ) from exc
        finally:
            if "conn" in locals():
                conn.close()

        keys = [
            "category_id",
            "category_name",
            "side",
            "level",
            "view",
            "report_date",
            "baseline_ftp_rate_pct",
            "cnx_scale",
            "cny_scale",
            "foreign_scale",
            "cnx_cash",
            "cny_cash",
            "foreign_cash",
            "cny_ftp",
            "foreign_ftp",
            "cny_net",
            "foreign_net",
            "business_net_income",
            "weighted_yield",
            "is_total",
            "children_json",
            "source_version",
            "rule_version",
        ]
        parsed_rows: list[dict[str, object]] = []
        for row in rows:
            item = dict(zip(keys, row, strict=True))
            item["children"] = json.loads(str(item.pop("children_json") or "[]"))
            parsed_rows.append(item)
        return parsed_rows


def load_product_category_manual_adjustments(
    governance_path: Path, report_date: date,
    *, events: Sequence[dict[str, object]] | None = None,
) -> list[ManualAdjustment]:
    """Read the latest event per adjustment before selecting the requested month."""
    rows = (
        GovernanceRepository(base_dir=governance_path).read_all(PRODUCT_CATEGORY_ADJUSTMENT_STREAM)
        if events is None else events
    )
    latest_by_id: dict[str, dict[str, object]] = {}
    legacy_rows: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        adjustment_id = str(row.get("adjustment_id") or "")
        if not adjustment_id:
            legacy_rows.append(row | {"adjustment_id": f"legacy-{index}"})
            continue
        existing = latest_by_id.get(adjustment_id)
        if existing is None or str(row.get("created_at", "")) >= str(existing.get("created_at", "")):
            latest_by_id[adjustment_id] = row

    adjustments: list[ManualAdjustment] = []
    for row in [*legacy_rows, *latest_by_id.values()]:
        # A historical move must not retain its old-month event.
        if str(row.get("report_date")) != report_date.isoformat():
            continue
        adjustments.append(
            ManualAdjustment(
                report_date=report_date,
                operator=str(row.get("operator", "")),
                approval_status=str(row.get("approval_status", "")),
                account_code=str(row.get("account_code", "")),
                currency=str(row.get("currency", "")),
                account_name=str(row.get("account_name", "")),
                beginning_balance=_decimal_or_none(row.get("beginning_balance")),
                ending_balance=_decimal_or_none(row.get("ending_balance")),
                monthly_pnl=_decimal_or_none(row.get("monthly_pnl")),
                daily_avg_balance=_decimal_or_none(row.get("daily_avg_balance")),
                annual_avg_balance=_decimal_or_none(row.get("annual_avg_balance")),
            )
        )
    return adjustments


def _decimal_or_none(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _is_missing_read_model_error(exc: duckdb.Error) -> bool:
    message = str(exc).lower()
    if (
        ("cannot open file" in message or "cannot open database" in message)
        and any(
            marker in message
            for marker in (
                "no such file",
                "database does not exist",
                "system cannot find",
                "找不到指定",
                "不存在",
            )
        )
    ):
        return True
    return (
        "product_category_pnl_formal_read_model" in message
        and (
            "does not exist" in message
            or "catalog error" in message
            or "table with name" in message
        )
    )
