from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.pnl import compute_pnl_by_business_yield_and_ftp
from tests.helpers import load_module

precompute_module = load_module(
    "backend.app.tasks.pnl_by_business_precompute",
    "backend/app/tasks/pnl_by_business_precompute.py",
)


def test_precompute_ftp_values_match_core_finance_function():
    total_pnl = Decimal("130000")
    avg_balance = Decimal("100000000")
    calendar_days = 31

    annualized_yield_pct = precompute_module._analysis_annualized_yield_pct(
        total_pnl,
        avg_balance,
        calendar_days,
    )
    ftp_values = precompute_module._analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
    )

    expected = compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=precompute_module.FTP_RATE_PCT,
    )

    assert annualized_yield_pct == expected.annualized_yield_pct
    assert ftp_values["ftp_cost"] == expected.ftp_cost
    assert ftp_values["ftp_net_pnl"] == expected.ftp_net_pnl
    assert ftp_values["ftp_net_annualized_yield_pct"] == expected.ftp_net_annualized_yield_pct


def test_precompute_ftp_values_match_core_finance_function_without_denominator():
    total_pnl = Decimal("130000")
    avg_balance = Decimal("0")
    calendar_days = 31

    annualized_yield_pct = precompute_module._analysis_annualized_yield_pct(
        total_pnl,
        avg_balance,
        calendar_days,
    )
    ftp_values = precompute_module._analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
    )

    expected = compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=precompute_module.FTP_RATE_PCT,
    )

    assert annualized_yield_pct is None
    assert ftp_values["ftp_cost"] is None
    assert ftp_values["ftp_net_pnl"] is None
    assert ftp_values["ftp_net_annualized_yield_pct"] is None
    assert expected.annualized_yield_pct is None
