from __future__ import annotations

import json
from dataclasses import dataclass

import duckdb

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

    def list_report_dates(self) -> list[str]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
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
            conn = duckdb.connect(self.path, read_only=True)
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
            conn = duckdb.connect(self.path, read_only=True)
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
            conn = duckdb.connect(self.path, read_only=True)
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
