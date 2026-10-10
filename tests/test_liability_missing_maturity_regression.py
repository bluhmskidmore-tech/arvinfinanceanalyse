"""PAGE-LIAB regression: missing dates must not manufacture maturity pressure."""
from decimal import Decimal

import pytest

from backend.app.core_finance.liability_analytics_compat import compute_liabilities_monthly, compute_liabilities_monthly_detail
from backend.app.core_finance.liability_cockpit import compute_cockpit_warnings
from backend.app.schemas.liability_analytics import LiabilityMonthlyDetailItem

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_liability_analytics]


def test_undated_liabilities_do_not_trigger_short_term_refinancing_alert():
    rows = [{
        "report_date": "2026-08-31",
        "is_asset_side": False,
        "principal_native": Decimal("44307000000"),
        "product_type": "同业存放",
        "counterparty_name": "测试银行",
        "maturity_date": None,
        "funding_cost_rate": Decimal("1.4"),
    }]
    result = compute_cockpit_warnings("2026-08-31", [], rows)
    assert not any(item["id"] == "alert_short_term_maturity" for item in result["alert_events"])
    assert not any(item["id"] == "watch_short_term_maturity" for item in result["watch_items"])
    assert any(item["id"] == "watch_missing_maturity" for item in result["watch_items"])

    monthly = compute_liabilities_monthly(2026, [], rows)
    month = monthly["months"][0]
    buckets = {item["bucket"]: item["avg_balance"] for item in month["term_buckets"]}
    assert buckets["0-3M"] == 0
    assert buckets["到期日未提供"] == month["avg_total_liabilities"]


def test_monthly_concentration_total_excludes_issuance_and_self_counterparties():
    common = {"report_date": "2026-08-31", "is_asset_side": False, "product_type": "同业存放"}
    rows = [
        {**common, "counterparty_name": "测试银行", "principal_native": "60000000"},
        {**common, "counterparty_name": "测试信托", "principal_native": "40000000"},
        {**common, "counterparty_name": "青岛银行股份有限公司", "principal_native": "20000000"},
    ]
    issued = [{"report_date": "2026-08-31", "is_issuance_like": True, "market_value_native": "80000000"}]
    result = compute_liabilities_monthly_detail(2026, "2026-08", issued, rows)
    detail = LiabilityMonthlyDetailItem.model_validate(result["detail"])
    assert detail.counterparty_total.raw == 100_000_000
    assert detail.counterparty_details[0].proportion.raw == 0.6
