from datetime import date, timedelta

import pytest

from backend.app.core_finance.macro.monetary_policy_stance import compute_monetary_policy_stance
from backend.app.services.macro_toolkit_analysis_service import _capability_result_card

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_macro_toolkit]


@pytest.mark.parametrize("prior_tool", [None, "CN_MLF", "CN_RRP"])
def test_policy_component_needs_same_tool_historical_pair(prior_tool):
    report = date(2026, 6, 30)
    rows = [dict(biz_date=report-timedelta(days=i), curve_id=cid, tenor=tenor, rate_value=rate)
            for i in range(30) for cid, tenor, rate in [
                ('CN_GOVT', '1Y', 1.5), ('CN_GOVT', '3Y', 1.7), ('CN_GOVT', '10Y', 2.1),
                ('CN_CREDIT_AAA', '3Y', 2), ('CN_CREDIT_AA', '3Y', 2.2), ('CN_DR', '7D', 1.8)]]
    rows.append(dict(biz_date=report, curve_id="CN_RRP", tenor="7D", rate_value=1.8))
    if prior_tool:
        rows.append(dict(biz_date=report-timedelta(days=21), curve_id=prior_tool,
                         tenor="7D" if prior_tool == "CN_RRP" else "1Y", rate_value=1.7))
    payload = compute_monetary_policy_stance(rows, report_date=report)
    card = _capability_result_card(dict(key="monetary_policy_stance", legacy_module="M7", label="policy", group="macro"), payload)
    if prior_tool == "CN_RRP":
        assert payload["data_status"] == "complete"
        assert len(payload["components"]) == 5
    else:
        assert payload["key_metrics"]["policy_change_21d_bp"] is None
        assert payload["data_status"] == "degraded"
        assert card["status"] != "complete"
        assert "POLICY_RATE_HISTORY_UNPAIRED" in card["warnings"]
