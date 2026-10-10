from __future__ import annotations

import pytest

from backend.app.services import stock_portfolio_construction_service as service


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

_RISK_ARGS = {
    "portfolio_id": "SHADOW-STOCK-RESEARCH",
    "as_of_date": "2026-09-05",
    "target_rows": [
        {
            "stock_code": "000001.SZ",
            "sector_name": "银行",
            "target_weight": 0.25,
        }
    ],
    "source_gate": {"status": "ready"},
}


class _UnexpectedRiskBuilderError(Exception):
    pass


@pytest.mark.parametrize("error", [RuntimeError("offline"), _UnexpectedRiskBuilderError("failed")])
def test_shadow_risk_failure_is_visible(error: Exception) -> None:
    def _raise(_lines: object) -> dict[str, object]:
        raise error

    result = service._build_risk_snapshot(builder=_raise, **_RISK_ARGS)

    assert result["status"] == "error"
    assert result["metrics"] == {}
    assert result["warnings"] == [f"stock_portfolio_risk_builder_failed:{type(error).__name__}"]
