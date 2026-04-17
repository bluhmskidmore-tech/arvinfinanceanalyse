"""Read-only DuckDB access for positions / snapshot drill-down APIs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

import duckdb

from backend.app.repositories.duckdb_repo import DuckDBRepository

Q8 = Decimal("0.00000001")
ONE_HUNDRED = Decimal("100")
RATING_ORDER = {
    "AAA": 1,
    "AA+": 2,
    "AA": 3,
    "AA-": 4,
    "A+": 5,
    "A": 6,
    "A-": 7,
    "BBB+": 8,
    "BBB": 9,
    "BBB-": 10,
    "BB+": 11,
    "BB": 12,
    "BB-": 13,
    "B+": 14,
    "B": 15,
    "B-": 16,
    "CCC": 17,
    "CC": 18,
    "C": 19,
    "D": 20,
    "未评级": 99,
}


def _fmt_amount(val: object | None) -> str:
    if val is None:
        return "0"
    d = Decimal(str(val))
    return format(d.quantize(Q8, rounding=ROUND_HALF_UP), "f")


def _fmt_opt(val: object | None) -> str | None:
    if val is None:
        return None
    d = Decimal(str(val))
    return format(d.quantize(Q8, rounding=ROUND_HALF_UP), "f")


def _normalize_rate_decimal(val: object | None, *, is_interbank: bool) -> Decimal | None:
    if val is None:
        return None
    rate = Decimal(str(val))
    if is_interbank:
        if rate > 1:
            rate = rate / ONE_HUNDRED
        return rate.quantize(Q8, rounding=ROUND_HALF_UP)
    if rate > 1 and rate <= ONE_HUNDRED:
        rate = rate / ONE_HUNDRED
    return rate.quantize(Q8, rounding=ROUND_HALF_UP)


def _fmt_rate(val: object | None, *, is_interbank: bool) -> str | None:
    normalized = _normalize_rate_decimal(val, is_interbank=is_interbank)
    if normalized is None:
        return None
    return format(normalized, "f")


def _map_direction(position_side: str | None) -> str:
    side = position_side or ""
    low = side.lower()
    if "资产" in side or "asset" in low:
        return "Asset"
    return "Liability"


def _asset_side_predicate(column: str = "position_side") -> str:
    return (
        f"(instr(lower(coalesce({column}, '')), 'asset') > 0 "
        f"OR instr(coalesce({column}, ''), '资产') > 0)"
    )


def _rating_sort_key(item: dict[str, object]) -> tuple[int, str]:
    rating = str(item.get("rating") or "").strip() or "未评级"
    return (RATING_ORDER.get(rating, 50), rating)


@dataclass
class PositionsRepository(DuckDBRepository):
    guard_path_exists: bool = True

    def resolve_latest_report_date(self) -> str | None:
        latest_dates: list[str] = []
        if self._table_exists("zqtz_bond_daily_snapshot"):
            rows = self._fetch_rows("select max(report_date) from zqtz_bond_daily_snapshot")
            if rows and rows[0][0] is not None:
                latest_dates.append(str(rows[0][0]))
        if self._table_exists("tyw_interbank_daily_snapshot"):
            rows = self._fetch_rows("select max(report_date) from tyw_interbank_daily_snapshot")
            if rows and rows[0][0] is not None:
                latest_dates.append(str(rows[0][0]))
        return max(latest_dates) if latest_dates else None

    def collect_lineage_versions(
        self,
        *,
        zqtz_where_sql: str,
        zqtz_params: list[object],
        tyw_where_sql: str,
        tyw_params: list[object],
    ) -> tuple[list[str], list[str]]:
        src: list[str] = []
        rule: list[str] = []
        if self._table_exists("zqtz_bond_daily_snapshot"):
            rows = self._fetch_rows(
                f"""
                select distinct source_version, rule_version
                from zqtz_bond_daily_snapshot
                where {zqtz_where_sql}
                """,
                zqtz_params,
            )
            for s, r in rows:
                if s:
                    src.append(str(s))
                if r:
                    rule.append(str(r))
        if self._table_exists("tyw_interbank_daily_snapshot"):
            rows = self._fetch_rows(
                f"""
                select distinct source_version, rule_version
                from tyw_interbank_daily_snapshot
                where {tyw_where_sql}
                """,
                tyw_params,
            )
            for s, r in rows:
                if s:
                    src.append(str(s))
                if r:
                    rule.append(str(r))
        return src, rule

    def list_bond_sub_types(self, report_date: str) -> list[str]:
        report_date = report_date.strip() or str(self.resolve_latest_report_date() or "")
        if not report_date.strip() or not self._table_exists("zqtz_bond_daily_snapshot"):
            return []
        rows = self._fetch_rows(
            """
            select distinct bond_type
            from zqtz_bond_daily_snapshot
            where report_date = ?::date and bond_type is not null
              and trim(CAST(bond_type AS VARCHAR)) <> ''
            order by bond_type
            """,
            [report_date],
        )
        return [str(r[0]) for r in rows]

    def list_bonds(
        self,
        report_date: str,
        sub_type: str | None,
        page: int,
        page_size: int,
        include_issued: bool,
    ) -> tuple[list[dict[str, object]], int]:
        if not self._table_exists("zqtz_bond_daily_snapshot"):
            return [], 0
        where = ["report_date = ?::date"]
        params: list[object] = [report_date]
        if sub_type:
            where.append("bond_type = ?")
            params.append(sub_type)
        if not include_issued:
            where.append("NOT COALESCE(is_issuance_like, FALSE)")
        where_sql = " AND ".join(where)

        count_rows = self._fetch_rows(
            f"select count(*) from zqtz_bond_daily_snapshot where {where_sql}",
            params,
        )
        total = int(count_rows[0][0]) if count_rows else 0
        offset = max(page - 1, 0) * max(page_size, 1)
        limit = max(page_size, 1)
        rows = self._fetch_rows(
            f"""
            select instrument_code, issuer_name, bond_type, asset_class,
                   market_value_native, face_value_native, amortized_cost_native, ytm_value
            from zqtz_bond_daily_snapshot
            where {where_sql}
            order by instrument_code, portfolio_name, cost_center
            limit ? offset ?
            """,
            [*params, limit, offset],
        )
        items: list[dict[str, object]] = []
        for row in rows:
            market_value = Decimal(str(row[4] or 0))
            face_value = Decimal(str(row[5] or 0))
            net_price = None
            if face_value > 0 and market_value > 0:
                net_price = (market_value / face_value * ONE_HUNDRED).quantize(Q8, rounding=ROUND_HALF_UP)
            items.append(
                {
                    "bond_code": str(row[0] or ""),
                    "credit_name": str(row[1]) if row[1] is not None else None,
                    "sub_type": str(row[2]) if row[2] is not None else None,
                    "asset_class": str(row[3]) if row[3] is not None else None,
                    "market_value": _fmt_opt(row[4]),
                    "face_value": _fmt_opt(row[5]),
                    "valuation_net_price": format(net_price, "f") if net_price is not None else None,
                    "yield_rate": _fmt_rate(row[7], is_interbank=False),
                }
            )
        return items, total

    def list_interbank_product_types(self, report_date: str) -> list[str]:
        report_date = report_date.strip() or str(self.resolve_latest_report_date() or "")
        if not report_date.strip() or not self._table_exists("tyw_interbank_daily_snapshot"):
            return []
        rows = self._fetch_rows(
            """
            select distinct product_type
            from tyw_interbank_daily_snapshot
            where report_date = ?::date
              and product_type is not null
              and trim(CAST(product_type AS VARCHAR)) <> ''
            order by product_type
            """,
            [report_date],
        )
        return [str(r[0]) for r in rows]

    def list_interbank(
        self,
        report_date: str,
        product_type: str | None,
        direction: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, object]], int]:
        if not self._table_exists("tyw_interbank_daily_snapshot"):
            return [], 0
        where = ["report_date = ?::date"]
        params: list[object] = [report_date]
        if product_type:
            where.append("product_type = ?")
            params.append(product_type)
        if direction and direction != "ALL":
            if direction == "Asset":
                where.append(_asset_side_predicate())
            elif direction == "Liability":
                where.append(f"NOT ({_asset_side_predicate()})")
        where_sql = " AND ".join(where)

        count_rows = self._fetch_rows(
            f"select count(*) from tyw_interbank_daily_snapshot where {where_sql}",
            params,
        )
        total = int(count_rows[0][0]) if count_rows else 0
        offset = max(page - 1, 0) * max(page_size, 1)
        limit = max(page_size, 1)
        rows = self._fetch_rows(
            f"""
            select position_id, counterparty_name, product_type, position_side,
                   principal_native, funding_cost_rate, maturity_date
            from tyw_interbank_daily_snapshot
            where {where_sql}
            order by position_id
            limit ? offset ?
            """,
            [*params, limit, offset],
        )
        items: list[dict[str, object]] = []
        for row in rows:
            items.append(
                {
                    "deal_id": str(row[0] or ""),
                    "counterparty": str(row[1]) if row[1] is not None else None,
                    "product_type": str(row[2]) if row[2] is not None else None,
                    "direction": _map_direction(str(row[3]) if row[3] is not None else None),
                    "amount": _fmt_amount(row[4]),
                    "interest_rate": _fmt_rate(row[5], is_interbank=True),
                    "maturity_date": str(row[6]) if row[6] is not None else None,
                }
            )
        return items, total

    def _bond_range_where(self, start_date: str, end_date: str, sub_type: str | None) -> tuple[str, list[object]]:
        where = [
            "report_date BETWEEN ?::date AND ?::date",
            "issuer_name IS NOT NULL",
            "trim(CAST(issuer_name AS VARCHAR)) <> ''",
        ]
        params: list[object] = [start_date, end_date]
        if sub_type:
            where.append("bond_type = ?")
            params.append(sub_type)
        return " AND ".join(where), params

    def _tyw_range_where(
        self, start_date: str, end_date: str, product_type: str | None, asset_only: bool | None = None
    ) -> tuple[str, list[object]]:
        where = [
            "report_date BETWEEN ?::date AND ?::date",
            "counterparty_name IS NOT NULL",
            "trim(CAST(counterparty_name AS VARCHAR)) <> ''",
        ]
        params: list[object] = [start_date, end_date]
        if product_type:
            where.append("product_type = ?")
            params.append(product_type)
        if asset_only is True:
            where.append(_asset_side_predicate())
        elif asset_only is False:
            where.append(f"NOT ({_asset_side_predicate()})")
        return " AND ".join(where), params

    def aggregate_counterparty_bonds(
        self,
        start_date: str,
        end_date: str,
        sub_type: str | None,
        top_n: int | None,
        page: int,
        page_size: int,
    ) -> dict[str, object]:
        if not self._table_exists("zqtz_bond_daily_snapshot"):
            return self._empty_counterparty_bonds(start_date, end_date)
        where_sql, params = self._bond_range_where(start_date, end_date, sub_type)
        nd_rows = self._fetch_rows(
            f"select count(distinct report_date) from zqtz_bond_daily_snapshot where {where_sql}",
            params,
        )
        num_days = int(nd_rows[0][0]) if nd_rows else 0

        agg_rows = self._fetch_rows(
            f"""
            select issuer_name,
              sum(market_value_native) as total_amount,
              count(*) as transaction_count,
              sum(coalesce(ytm_value, 0) * coalesce(market_value_native, 0)) as w_ytm_num,
              sum(coalesce(coupon_rate, 0) * coalesce(market_value_native, 0)) as w_cpn_num,
              sum(coalesce(market_value_native, 0)) as mv_sum
            from zqtz_bond_daily_snapshot
            where {where_sql}
            group by issuer_name
            order by total_amount desc nulls last
            """,
            params,
        )
        items_all = self._rows_to_counterparty_items(agg_rows, num_days)
        tot_mv_rows = self._fetch_rows(
            f"""
            select
              sum(coalesce(market_value_native, 0)),
              sum(coalesce(ytm_value, 0) * coalesce(market_value_native, 0)),
              sum(coalesce(coupon_rate, 0) * coalesce(market_value_native, 0))
            from zqtz_bond_daily_snapshot
            where {where_sql}
            """,
            params,
        )
        g_mv = tot_mv_rows[0][0] if tot_mv_rows else None
        g_wytm = tot_mv_rows[0][1] if tot_mv_rows else None
        g_wcpn = tot_mv_rows[0][2] if tot_mv_rows else None
        grand_total = Decimal(str(g_mv or 0))
        total_amount_str = _fmt_amount(grand_total)
        total_avg = _fmt_amount((grand_total / Decimal(num_days)) if num_days else Decimal(0))
        tw_r = _weighted_rate_str(g_wytm, g_mv)
        tw_c = _weighted_rate_str(g_wcpn, g_mv)

        capped = items_all
        if top_n is not None and top_n > 0:
            capped = items_all[:top_n]
        offset = max(page - 1, 0) * max(page_size, 1)
        limit = max(page_size, 1)
        page_items = capped[offset : offset + limit]

        return {
            "start_date": start_date,
            "end_date": end_date,
            "num_days": num_days,
            "items": page_items,
            "total_amount": total_amount_str,
            "total_avg_daily": total_avg,
            "total_weighted_rate": tw_r,
            "total_weighted_coupon_rate": tw_c,
            "total_customers": len(items_all),
        }

    def _empty_counterparty_bonds(self, start_date: str, end_date: str) -> dict[str, object]:
        return {
            "start_date": start_date,
            "end_date": end_date,
            "num_days": 0,
            "items": [],
            "total_amount": "0",
            "total_avg_daily": "0",
            "total_weighted_rate": None,
            "total_weighted_coupon_rate": None,
            "total_customers": 0,
        }

    def _rows_to_counterparty_items(
        self, agg_rows: list[tuple], num_days: int
    ) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        denom = Decimal(num_days) if num_days else Decimal(0)
        for row in agg_rows:
            name, total_amt, txn, w_ytm_n, w_cpn_n, mv_sum = row
            mv = Decimal(str(mv_sum or 0))
            avg_daily = (Decimal(str(total_amt or 0)) / denom) if denom else Decimal(0)
            items.append(
                {
                    "customer_name": str(name or ""),
                    "total_amount": _fmt_amount(total_amt),
                    "avg_daily_balance": _fmt_amount(avg_daily),
                    "weighted_rate": _weighted_rate_str(w_ytm_n, mv_sum),
                    "weighted_coupon_rate": _weighted_rate_str(w_cpn_n, mv_sum),
                    "transaction_count": int(txn or 0),
                }
            )
        return items

    def aggregate_counterparty_interbank_split(
        self,
        start_date: str,
        end_date: str,
        product_type: str | None,
        top_n: int | None,
    ) -> dict[str, object]:
        if not self._table_exists("tyw_interbank_daily_snapshot"):
            return self._empty_interbank_split(start_date, end_date)

        where_all, params_all = self._tyw_range_where(start_date, end_date, product_type, None)
        nd_global = self._fetch_rows(
            f"select count(distinct report_date) from tyw_interbank_daily_snapshot where {where_all}",
            params_all,
        )
        num_days_global = int(nd_global[0][0]) if nd_global else 0

        def one_side(asset_only: bool) -> dict[str, object]:
            where_sql, params = self._tyw_range_where(start_date, end_date, product_type, asset_only)
            nd_rows = self._fetch_rows(
                f"select count(distinct report_date) from tyw_interbank_daily_snapshot where {where_sql}",
                params,
            )
            n_days = int(nd_rows[0][0]) if nd_rows else 0
            agg_rows = self._fetch_rows(
                f"""
                select
                  counterparty_name,
                  sum(principal_native) as total_amount,
                  count(*) as transaction_count,
                  sum(coalesce(funding_cost_rate, 0) * coalesce(principal_native, 0)) as w_rate_num,
                  sum(coalesce(principal_native, 0)) as mv_sum
                from tyw_interbank_daily_snapshot
                where {where_sql}
                group by counterparty_name
                order by total_amount desc nulls last
                """,
                params,
            )
            items_all: list[dict[str, object]] = []
            denom = Decimal(n_days) if n_days else Decimal(0)
            for row in agg_rows:
                cp, total_amt, txn, w_rn, pr_sum = row
                avg_daily = (Decimal(str(total_amt or 0)) / denom) if denom else Decimal(0)
                items_all.append(
                    {
                        "customer_name": str(cp or ""),
                        "total_amount": _fmt_amount(total_amt),
                        "avg_daily_balance": _fmt_amount(avg_daily),
                        "weighted_rate": _weighted_rate_str(w_rn, pr_sum),
                        "weighted_coupon_rate": None,
                        "transaction_count": int(txn or 0),
                    }
                )
            tot_rows = self._fetch_rows(
                f"""
                select
                  sum(coalesce(principal_native, 0)),
                  sum(coalesce(funding_cost_rate, 0) * coalesce(principal_native, 0))
                from tyw_interbank_daily_snapshot
                where {where_sql}
                """,
                params,
            )
            g_pr = tot_rows[0][0] if tot_rows else None
            g_wr = tot_rows[0][1] if tot_rows else None
            grand = Decimal(str(g_pr or 0))
            capped = items_all if top_n is None or top_n <= 0 else items_all[:top_n]
            return {
                "num_days": n_days,
                "total_amount": _fmt_amount(grand),
                "total_avg_daily": _fmt_amount((grand / denom) if denom else Decimal(0)),
                "total_weighted_rate": _weighted_rate_str(g_wr, g_pr),
                "customer_count": len(items_all),
                "items": capped,
            }

        asset = one_side(True)
        liability = one_side(False)
        return {
            "start_date": start_date,
            "end_date": end_date,
            "num_days": num_days_global,
            "asset_total_amount": str(asset["total_amount"]),
            "asset_total_avg_daily": str(asset["total_avg_daily"]),
            "asset_total_weighted_rate": asset["total_weighted_rate"],
            "asset_customer_count": int(asset["customer_count"]),
            "liability_total_amount": str(liability["total_amount"]),
            "liability_total_avg_daily": str(liability["total_avg_daily"]),
            "liability_total_weighted_rate": liability["total_weighted_rate"],
            "liability_customer_count": int(liability["customer_count"]),
            "asset_items": asset["items"],
            "liability_items": liability["items"],
        }

    def _empty_interbank_split(self, start_date: str, end_date: str) -> dict[str, object]:
        return {
            "start_date": start_date,
            "end_date": end_date,
            "num_days": 0,
            "asset_total_amount": "0",
            "asset_total_avg_daily": "0",
            "asset_total_weighted_rate": None,
            "asset_customer_count": 0,
            "liability_total_amount": "0",
            "liability_total_avg_daily": "0",
            "liability_total_weighted_rate": None,
            "liability_customer_count": 0,
            "asset_items": [],
            "liability_items": [],
        }

    def aggregate_rating_stats(
        self, start_date: str, end_date: str, sub_type: str | None
    ) -> dict[str, object]:
        if not self._table_exists("zqtz_bond_daily_snapshot"):
            return self._empty_rating_industry(start_date, end_date, "rating")
        where_sql, params = self._bond_range_where(start_date, end_date, sub_type)
        nd_rows = self._fetch_rows(
            f"select count(distinct report_date) from zqtz_bond_daily_snapshot where {where_sql}",
            params,
        )
        num_days = int(nd_rows[0][0]) if nd_rows else 0
        rows = self._fetch_rows(
            f"""
            select
              case
                when rating is null or trim(CAST(rating AS VARCHAR)) = '' then '未评级'
                else CAST(rating AS VARCHAR)
              end as rating_bucket,
              sum(market_value_native) as total_amount,
              count(*) as bond_count,
              sum(coalesce(ytm_value, 0) * coalesce(market_value_native, 0)) as w_ytm_num
            from zqtz_bond_daily_snapshot
            where {where_sql}
            group by rating_bucket
            order by total_amount desc nulls last
            """,
            params,
        )
        grand_rows = self._fetch_rows(
            f"select sum(market_value_native) from zqtz_bond_daily_snapshot where {where_sql}",
            params,
        )
        grand = Decimal(str(grand_rows[0][0] or 0)) if grand_rows else Decimal(0)
        denom_days = Decimal(num_days) if num_days else Decimal(0)
        items: list[dict[str, object]] = []
        for row in rows:
            label, total_amt, bcount, w_ytm_n = row
            amt = Decimal(str(total_amt or 0))
            pct = (amt / grand * Decimal(100)) if grand else Decimal(0)
            avg_daily = (amt / denom_days) if denom_days else Decimal(0)
            mv = amt
            items.append(
                {
                    "rating": str(label),
                    "total_amount": _fmt_amount(amt),
                    "avg_daily_balance": _fmt_amount(avg_daily),
                    "weighted_rate": _weighted_rate_str(w_ytm_n, mv),
                    "bond_count": int(bcount or 0),
                    "percentage": _fmt_amount(pct),
                }
            )
        items.sort(key=_rating_sort_key)
        return {
            "start_date": start_date,
            "end_date": end_date,
            "num_days": num_days,
            "items": items,
            "total_amount": _fmt_amount(grand),
            "total_avg_daily": _fmt_amount((grand / denom_days) if denom_days else Decimal(0)),
        }

    def aggregate_industry_stats(
        self, start_date: str, end_date: str, sub_type: str | None, top_n: int | None
    ) -> dict[str, object]:
        if not self._table_exists("zqtz_bond_daily_snapshot"):
            return self._empty_rating_industry(start_date, end_date, "industry")
        where_sql, params = self._bond_range_where(start_date, end_date, sub_type)
        nd_rows = self._fetch_rows(
            f"select count(distinct report_date) from zqtz_bond_daily_snapshot where {where_sql}",
            params,
        )
        num_days = int(nd_rows[0][0]) if nd_rows else 0
        limit_clause = ""
        lim_params: list[object] = []
        if top_n is not None and top_n > 0:
            limit_clause = " limit ?"
            lim_params.append(top_n)
        rows = self._fetch_rows(
            f"""
            select
              case
                when industry_name is null or trim(CAST(industry_name AS VARCHAR)) = '' then '未分类'
                else CAST(industry_name AS VARCHAR)
              end as ind_bucket,
              sum(market_value_native) as total_amount,
              count(*) as bond_count,
              sum(coalesce(ytm_value, 0) * coalesce(market_value_native, 0)) as w_ytm_num
            from zqtz_bond_daily_snapshot
            where {where_sql}
            group by ind_bucket
            order by total_amount desc nulls last
            {limit_clause}
            """,
            [*params, *lim_params],
        )
        grand_rows = self._fetch_rows(
            f"select sum(market_value_native) from zqtz_bond_daily_snapshot where {where_sql}",
            params,
        )
        grand = Decimal(str(grand_rows[0][0] or 0)) if grand_rows else Decimal(0)
        denom_days = Decimal(num_days) if num_days else Decimal(0)
        items: list[dict[str, object]] = []
        for row in rows:
            label, total_amt, bcount, w_ytm_n = row
            amt = Decimal(str(total_amt or 0))
            pct = (amt / grand * Decimal(100)) if grand else Decimal(0)
            avg_daily = (amt / denom_days) if denom_days else Decimal(0)
            mv = amt
            items.append(
                {
                    "industry": str(label),
                    "total_amount": _fmt_amount(amt),
                    "avg_daily_balance": _fmt_amount(avg_daily),
                    "weighted_rate": _weighted_rate_str(w_ytm_n, mv),
                    "bond_count": int(bcount or 0),
                    "percentage": _fmt_amount(pct),
                }
            )
        return {
            "start_date": start_date,
            "end_date": end_date,
            "num_days": num_days,
            "items": items,
            "total_amount": _fmt_amount(grand),
            "total_avg_daily": _fmt_amount((grand / denom_days) if denom_days else Decimal(0)),
        }

    def _empty_rating_industry(self, start_date: str, end_date: str, _kind: str) -> dict[str, object]:
        return {
            "start_date": start_date,
            "end_date": end_date,
            "num_days": 0,
            "items": [],
            "total_amount": "0",
            "total_avg_daily": "0",
        }

    def get_customer_bond_details(self, customer_name: str, report_date: str) -> dict[str, object]:
        report_date = report_date.strip() or str(self.resolve_latest_report_date() or "")
        if (
            not customer_name.strip()
            or not report_date.strip()
            or not self._table_exists("zqtz_bond_daily_snapshot")
        ):
            return {
                "customer_name": customer_name,
                "report_date": report_date,
                "total_market_value": "0",
                "bond_count": 0,
                "items": [],
            }
        rows = self._fetch_rows(
            """
            select instrument_code, bond_type, asset_class, market_value_native,
                   ytm_value, maturity_date, rating, industry_name
            from zqtz_bond_daily_snapshot
            where report_date = ?::date
              and issuer_name = ?
            order by instrument_code
            """,
            [report_date, customer_name],
        )
        items: list[dict[str, object]] = []
        total = Decimal(0)
        for row in rows:
            mv = Decimal(str(row[3] or 0))
            total += mv
            rating_v = row[6]
            ind_v = row[7]
            items.append(
                {
                    "bond_code": str(row[0] or ""),
                    "sub_type": str(row[1]) if row[1] is not None else None,
                    "asset_class": str(row[2]) if row[2] is not None else None,
                    "market_value": _fmt_amount(row[3]),
                    "yield_rate": _fmt_opt(row[4]),
                    "maturity_date": str(row[5]) if row[5] is not None else None,
                    "rating": str(rating_v) if rating_v is not None else "",
                    "industry": str(ind_v) if ind_v is not None else "",
                }
            )
        return {
            "customer_name": customer_name,
            "report_date": report_date,
            "total_market_value": _fmt_amount(total),
            "bond_count": len(items),
            "items": items,
        }

    def get_customer_balance_trend(self, customer_name: str, end_date: str, days: int) -> dict[str, object]:
        d = max(days, 1)
        try:
            end_d = date.fromisoformat(end_date)
            start_d = end_d - timedelta(days=d - 1)
            window_start = start_d.isoformat()
        except ValueError:
            window_start = end_date
        if not customer_name.strip() or not end_date.strip() or not self._table_exists(
            "zqtz_bond_daily_snapshot"
        ):
            return {
                "customer_name": customer_name,
                "start_date": window_start,
                "end_date": end_date,
                "days": d,
                "items": [],
            }
        rows = self._fetch_rows(
            """
            select report_date, sum(market_value_native) as bal
            from zqtz_bond_daily_snapshot
            where issuer_name = ?
              and report_date between (?::date - (CAST(? AS INTEGER) - 1)) and ?::date
            group by report_date
            order by report_date asc
            """,
            [customer_name, end_date, d, end_date],
        )
        items: list[dict[str, object]] = []
        for row in rows:
            rd = row[0]
            items.append(
                {
                    "date": str(rd) if rd is not None else "",
                    "balance": _fmt_amount(row[1]),
                }
            )
        start_date = str(rows[0][0]) if rows else window_start
        return {
            "customer_name": customer_name,
            "start_date": start_date,
            "end_date": end_date,
            "days": d,
            "items": items,
        }


def _weighted_rate_str(num: object | None, denom_mv: object | None) -> str | None:
    d = Decimal(str(denom_mv or 0))
    if d == 0:
        return None
    n = Decimal(str(num or 0))
    r = (n / d).quantize(Q8, rounding=ROUND_HALF_UP)
    return format(r, "f")
