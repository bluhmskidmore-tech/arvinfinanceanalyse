from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import duckdb


@dataclass
class PnlRepository:
    path: str

    def list_union_report_dates(self) -> list[str]:
        return sorted(
            set(self.list_formal_fi_report_dates()) | set(self.list_nonstd_bridge_report_dates()),
            reverse=True,
        )

    def list_formal_fi_report_dates(self) -> list[str]:
        return self._list_report_dates("fact_formal_pnl_fi")

    def list_nonstd_bridge_report_dates(self) -> list[str]:
        return self._list_report_dates("fact_nonstd_pnl_bridge")

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

    def _list_report_dates(self, table_name: str) -> list[str]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
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
            raise RuntimeError("Formal pnl storage is unavailable.") from exc
        finally:
            if "conn" in locals():
                conn.close()
        return [dict(zip(columns, row, strict=True)) for row in rows]
