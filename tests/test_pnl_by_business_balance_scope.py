from decimal import Decimal

import pytest

from backend.app.services import pnl_service
from backend.app.tasks.pnl_by_business_precompute import (
    PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS,
    _build_pnl_by_business_analysis_payloads_for_precompute,
)


@pytest.mark.parametrize("dimension", [
    "monthly", "portfolio", "accounting", "currency", "cost_center", "instrument",
    "bond_bucket", "bond_bucket_monthly",
])
def test_global_analysis_uses_parent_balance_scope_and_retains_unallocated_pnl(dimension):
    common = {
        "report_date": "2026-08-31", "accounting_basis": "FVOCI", "invest_type_std": "A",
        "currency_code": "CNY", "currency_basis": "CNY", "portfolio_name": "FIOA", "cost_center": "5010",
    }
    classified = {
        **common, "instrument_code": "TEST-TREASURY", "instrument_name": "国债测试券",
        "bond_type": "国债", "business_type_primary": "国债",
        "avg_amount": Decimal("365000000"), "current_amount": Decimal("365000000"),
    }
    unclassified = {
        **common, "instrument_code": "UNCLASSIFIED", "instrument_name": "待归属测试券",
        "bond_type": "其他", "business_type_primary": "其他债券",
        "avg_amount": Decimal("200000000"), "current_amount": Decimal("200000000"),
    }
    pnl_rows = [
        {**classified, "source_kind": "formal_fi", "interest_income_514": Decimal("100"), "total_pnl": Decimal("100")},
        {**unclassified, "source_kind": "formal_fi", "interest_income_514": Decimal("7"), "total_pnl": Decimal("7")},
    ]
    # A date with only unmatched balances still represents an observed source date;
    # the main table includes this date in its denominator too.
    balance_rows = [classified, unclassified, {**unclassified, "report_date": "2026-08-30"}]
    kwargs = {
        "pnl_rows": pnl_rows, "balance_rows": balance_rows, "loaded_dates": ["2026-08-31"],
        "period_start": "2026-08-01", "period_end": "2026-08-31", "ftp_rate_pct": Decimal("1.6"),
    }
    monthly, = pnl_service._build_pnl_by_business_monthly_buckets(
        pnl_rows=tuple(pnl_rows), balance_rows=tuple(balance_rows),
        loaded_dates=kwargs["loaded_dates"], ftp_rate_pct=kwargs["ftp_rate_pct"],
    )
    assert monthly.coverage_days == 2
    assert monthly.summary.avg_balance == Decimal("182500000")
    assert monthly.unallocated_pnl == Decimal("7")
    live = pnl_service._build_pnl_by_business_analysis_rows(**kwargs, business_key=None, dimension=dimension)
    variants = [live]
    if dimension in PNL_BY_BUSINESS_GLOBAL_ANALYSIS_DIMENSIONS:
        payloads = _build_pnl_by_business_analysis_payloads_for_precompute(**kwargs, year=2026, source_tables=[])
        cached = next(p.rows for p in payloads if p.business_key is None and p.dimension == dimension)
        assert [r.model_dump() for r in live] == [r.model_dump() for r in cached]
        variants.append(cached)
    for rows in variants:
        assert sum(r.avg_balance for r in rows) == monthly.summary.avg_balance
        assert sum(r.current_balance for r in rows) == monthly.summary.current_balance
        assert sum(r.total_pnl for r in rows) == monthly.source_total_pnl == Decimal("107")
        assert sum(r.ftp_cost or Decimal("0") for r in rows) == monthly.summary.ftp_cost
        if dimension == "instrument":
            unmatched, = [r for r in rows if r.dimension_key == "UNCLASSIFIED"]
            assert unmatched.total_pnl == Decimal("7")
            assert unmatched.avg_balance == 0 and unmatched.current_balance == 0
            assert unmatched.ftp_cost is None
