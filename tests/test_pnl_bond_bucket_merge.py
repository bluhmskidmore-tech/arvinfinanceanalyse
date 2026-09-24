"""Merged "other" display bucket for /pnl/by-business-analysis (dimension=bond_bucket).

The dashboard cockpit renders 信用债 / 利率债 / 其他, where 其他 merges the formal
金融债 + 其它债券 buckets. The merged annualized yield must equal the backend
formal口径: re-apply `compute_pnl_by_business_yield_and_ftp` to the summed
`total_pnl` / `avg_balance`, never a frontend weighted average of per-row yields.
"""

from decimal import Decimal

from backend.app.core_finance.pnl import compute_pnl_by_business_yield_and_ftp
from backend.app.schemas.pnl import PnlByBusinessAnalysisPayload, PnlByBusinessAnalysisRow
from backend.app.services.pnl_bond_bucket_merge import (
    MERGED_OTHER_BUCKET_KEY,
    MERGED_OTHER_BUCKET_LABEL,
    attach_bond_bucket_merged_rows,
)


def _row(
    dimension_key: str,
    dimension_label: str,
    *,
    total_pnl: str,
    avg_balance: str,
    annualized_yield_pct: str | None,
    asset_count: int = 1,
) -> PnlByBusinessAnalysisRow:
    return PnlByBusinessAnalysisRow(
        dimension_key=dimension_key,
        dimension_label=dimension_label,
        interest_income=Decimal(total_pnl),
        fair_value_change=Decimal("0.00"),
        capital_gain=Decimal("0.00"),
        manual_adjustment=Decimal("0.00"),
        total_pnl=Decimal(total_pnl),
        avg_balance=Decimal(avg_balance),
        current_balance=Decimal(avg_balance),
        annualized_yield_pct=Decimal(annualized_yield_pct) if annualized_yield_pct is not None else None,
        ftp_rate_pct=Decimal("1.600000"),
        ftp_cost=None,
        ftp_net_pnl=None,
        ftp_net_annualized_yield_pct=None,
        asset_count=asset_count,
    )


def _payload(
    rows: list[PnlByBusinessAnalysisRow],
    *,
    dimension: str = "bond_bucket",
    period_start_date: str = "2026-01-01",
    period_end_date: str = "2026-12-31",
) -> PnlByBusinessAnalysisPayload:
    return PnlByBusinessAnalysisPayload(
        year=2026,
        as_of_date=period_end_date,
        business_key=None,
        dimension=dimension,
        period_start_date=period_start_date,
        period_end_date=period_end_date,
        source_tables=["fact_formal_pnl_fi"],
        rows=rows,
    )


def test_merged_other_bucket_uses_backend_yield_formula_on_summed_values():
    # Full-year period => calendar_days = 365, annualization factor = 1.
    payload = attach_bond_bucket_merged_rows(
        _payload(
            [
                _row("rate_bond", "利率债", total_pnl="100.00", avg_balance="1000.00", annualized_yield_pct="10.000000", asset_count=3),
                _row("credit_bond", "信用债", total_pnl="80.00", avg_balance="800.00", annualized_yield_pct="10.000000", asset_count=4),
                _row("financial_bond", "金融债", total_pnl="60.00", avg_balance="600.00", annualized_yield_pct="10.000000", asset_count=2),
                _row("other_bond", "其它债券", total_pnl="40.00", avg_balance="400.00", annualized_yield_pct="10.000000", asset_count=1),
            ]
        )
    )

    assert len(payload.merged_bucket_rows) == 1
    merged = payload.merged_bucket_rows[0]
    assert merged.dimension_key == MERGED_OTHER_BUCKET_KEY
    assert merged.dimension_label == MERGED_OTHER_BUCKET_LABEL
    # Sums cover only 金融债 + 其它债券.
    assert merged.total_pnl == Decimal("100.00")
    assert merged.avg_balance == Decimal("1000.00")
    assert merged.current_balance == Decimal("1000.00")
    assert merged.asset_count == 3
    # (100 / 1000) * 365/365 * 100 = 10.000000
    assert merged.annualized_yield_pct == Decimal("10.000000")
    expected = compute_pnl_by_business_yield_and_ftp(
        total_pnl=Decimal("100.00"),
        avg_balance=Decimal("1000.00"),
        calendar_days=365,
        ftp_rate_pct=Decimal("1.600000"),
    )
    assert merged.annualized_yield_pct == expected.annualized_yield_pct
    assert merged.ftp_rate_pct == expected.ftp_rate_pct
    assert merged.ftp_cost == expected.ftp_cost == Decimal("16.00")
    assert merged.ftp_net_pnl == expected.ftp_net_pnl == Decimal("84.00")
    assert merged.ftp_net_annualized_yield_pct == expected.ftp_net_annualized_yield_pct == Decimal("8.400000")
    # Formal rows are left untouched.
    assert [row.dimension_key for row in payload.rows] == [
        "rate_bond",
        "credit_bond",
        "financial_bond",
        "other_bond",
    ]


def test_merged_other_bucket_differs_from_frontend_row_weighting_when_balance_is_zero():
    # The old frontend weighting dropped rows with avg_balance <= 0 entirely,
    # losing their PnL. The formal口径 keeps summed PnL over summed balance.
    payload = attach_bond_bucket_merged_rows(
        _payload(
            [
                _row("financial_bond", "金融债", total_pnl="60.00", avg_balance="0.00", annualized_yield_pct=None),
                _row("other_bond", "其它债券", total_pnl="40.00", avg_balance="400.00", annualized_yield_pct="10.000000"),
            ]
        )
    )

    merged = payload.merged_bucket_rows[0]
    # (100 / 400) * 365/365 * 100 = 25.000000; frontend weighting would say 10.00.
    assert merged.annualized_yield_pct == Decimal("25.000000")


def test_merged_bucket_yield_is_none_when_summed_balance_is_zero():
    payload = attach_bond_bucket_merged_rows(
        _payload(
            [
                _row("financial_bond", "金融债", total_pnl="60.00", avg_balance="0.00", annualized_yield_pct=None),
                _row("other_bond", "其它债券", total_pnl="40.00", avg_balance="0.00", annualized_yield_pct=None),
            ]
        )
    )

    merged = payload.merged_bucket_rows[0]
    assert merged.annualized_yield_pct is None
    assert merged.ftp_cost is None
    assert merged.ftp_net_pnl is None
    assert merged.ftp_net_annualized_yield_pct is None


def test_merged_bucket_rows_stay_empty_for_other_dimensions_and_missing_sources():
    monthly = attach_bond_bucket_merged_rows(
        _payload(
            [_row("2026-12-31::financial_bond", "2026-12-31 金融债", total_pnl="60.00", avg_balance="600.00", annualized_yield_pct="10.000000")],
            dimension="bond_bucket_monthly",
        )
    )
    assert monthly.merged_bucket_rows == []

    without_sources = attach_bond_bucket_merged_rows(
        _payload(
            [_row("rate_bond", "利率债", total_pnl="100.00", avg_balance="1000.00", annualized_yield_pct="10.000000")]
        )
    )
    assert without_sources.merged_bucket_rows == []
