"""Merged "other" bucket for the `/pnl/by-business-analysis` bond_bucket dimension.

The dashboard cockpit (PAGE-DASH-001) displays asset-class rows as
信用债 / 利率债 / 其他, where 其他 merges the formal 金融债 (`financial_bond`)
and 其它债券 (`other_bond`) buckets. The frontend must not recompute formal
yields, so the merged bucket is derived here from the same formal per-bucket
amounts, re-applying the identical `core_finance` annualized-yield formula to
the summed `total_pnl` / `avg_balance` over the payload period.
"""

from datetime import datetime
from decimal import Decimal

from backend.app.core_finance.pnl import compute_pnl_by_business_yield_and_ftp
from backend.app.schemas.pnl import PnlByBusinessAnalysisPayload, PnlByBusinessAnalysisRow

MERGED_OTHER_BUCKET_KEY = "other_merged"
MERGED_OTHER_BUCKET_LABEL = "其他"
MERGED_OTHER_SOURCE_BUCKET_KEYS: tuple[str, ...] = ("financial_bond", "other_bond")

_TWOPLACES = Decimal("0.01")


def attach_bond_bucket_merged_rows(
    payload: PnlByBusinessAnalysisPayload,
) -> PnlByBusinessAnalysisPayload:
    """Populate `merged_bucket_rows` for the bond_bucket dimension.

    Other dimensions are returned unchanged (empty `merged_bucket_rows`).
    """
    if payload.dimension != "bond_bucket":
        return payload
    source_rows = [row for row in payload.rows if row.dimension_key in MERGED_OTHER_SOURCE_BUCKET_KEYS]
    if not source_rows:
        return payload
    merged = _merge_bucket_rows(
        source_rows,
        dimension_key=MERGED_OTHER_BUCKET_KEY,
        dimension_label=MERGED_OTHER_BUCKET_LABEL,
        calendar_days=_calendar_days(payload.period_start_date, payload.period_end_date),
    )
    return payload.model_copy(update={"merged_bucket_rows": [merged]})


def _merge_bucket_rows(
    rows: list[PnlByBusinessAnalysisRow],
    *,
    dimension_key: str,
    dimension_label: str,
    calendar_days: int,
) -> PnlByBusinessAnalysisRow:
    total_pnl = _sum_amount(row.total_pnl for row in rows)
    avg_balance = _sum_amount(row.avg_balance for row in rows)
    yield_ftp = compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=rows[0].ftp_rate_pct,
    )
    return PnlByBusinessAnalysisRow(
        dimension_key=dimension_key,
        dimension_label=dimension_label,
        interest_income=_sum_amount(row.interest_income for row in rows),
        fair_value_change=_sum_amount(row.fair_value_change for row in rows),
        capital_gain=_sum_amount(row.capital_gain for row in rows),
        manual_adjustment=_sum_amount(row.manual_adjustment for row in rows),
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        current_balance=_sum_amount(row.current_balance for row in rows),
        annualized_yield_pct=yield_ftp.annualized_yield_pct,
        ftp_rate_pct=yield_ftp.ftp_rate_pct,
        ftp_cost=yield_ftp.ftp_cost,
        ftp_net_pnl=yield_ftp.ftp_net_pnl,
        ftp_net_annualized_yield_pct=yield_ftp.ftp_net_annualized_yield_pct,
        asset_count=sum(row.asset_count for row in rows),
    )


def _sum_amount(values) -> Decimal:
    return sum(values, Decimal("0")).quantize(_TWOPLACES)


def _calendar_days(start_date: str, end_date: str) -> int:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    return max((end - start).days + 1, 0)
