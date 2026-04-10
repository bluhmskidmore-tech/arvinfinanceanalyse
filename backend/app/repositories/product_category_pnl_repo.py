from __future__ import annotations

import json
from dataclasses import dataclass

import duckdb


@dataclass
class ProductCategoryPnlRepository:
    path: str

    def list_report_dates(self) -> list[str]:
        conn = duckdb.connect(self.path, read_only=True)
        try:
            rows = conn.execute(
                """
                select distinct report_date
                from product_category_pnl_formal_read_model
                order by report_date desc
                """
            ).fetchall()
        except duckdb.Error:
            return []
        finally:
            conn.close()
        return [str(row[0]) for row in rows]

    def latest_source_version(self) -> str:
        conn = duckdb.connect(self.path, read_only=True)
        try:
            row = conn.execute(
                """
                select source_version
                from product_category_pnl_formal_read_model
                order by report_date desc, sort_order asc
                limit 1
                """
            ).fetchone()
        except duckdb.Error:
            return "sv_product_category_empty"
        finally:
            conn.close()
        if row is None:
            return "sv_product_category_empty"
        return str(row[0])

    def fetch_rows(self, report_date: str, view: str, *, scenario: bool = False) -> list[dict[str, object]]:
        table_name = "product_category_pnl_scenario_read_model" if scenario else "product_category_pnl_formal_read_model"
        conn = duckdb.connect(self.path, read_only=True)
        try:
            rows = conn.execute(
                """
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
                from %s
                where report_date = ? and view = ?
                order by sort_order
                """ % table_name,
                [report_date, view],
            ).fetchall()
        except duckdb.Error:
            return []
        finally:
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
