"""PnL service adapters must reuse their governed calculation sources."""

from backend.app.core_finance import pnl_by_business_insights
from backend.app.services import pnl_bond_bucket_merge
from backend.app.services import pnl_by_business_candidate_insights
from backend.app.services import pnl_by_business_unallocated
from backend.app.services import pnl_service_shared_utils


def test_pnl_service_adapters_reuse_shared_leaf_utilities() -> None:
    assert (
        pnl_bond_bucket_merge._calendar_days is pnl_service_shared_utils._calendar_days
    )
    assert (
        pnl_by_business_unallocated._decimal_value
        is pnl_service_shared_utils._decimal_value
    )
    assert pnl_by_business_unallocated._norm_text is pnl_service_shared_utils._norm_text


def test_candidate_service_reuses_governed_trailing_month_window_source() -> None:
    assert (
        pnl_by_business_candidate_insights._trailing_month_keys
        is pnl_by_business_insights.trailing_month_keys
    )
