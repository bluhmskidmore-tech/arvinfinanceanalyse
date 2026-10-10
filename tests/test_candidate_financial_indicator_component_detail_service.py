from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from backend.app.services import (
    candidate_financial_indicator_period_comparison_service as service,
)


SOURCE_DIR = Path(__file__).resolve().parents[1] / "data_input" / "pnl_总账对账-日均"
REAL_LEDGER_WORKBOOKS = tuple(
    SOURCE_DIR / f"总账对账{month}.xlsx"
    for month in ("202604", "202605", "202606")
)


def _parent() -> dict[str, object]:
    return service.candidate_financial_indicator_period_comparison_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
    )


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_LEDGER_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
@pytest.mark.parametrize(
    ("metric_id", "expected_count", "expected_total"),
    [
        ("income.interest.loan.total", 21, "-0.3473924741"),
        ("expense.interest.deposit.total", 14, "0.0830909629"),
        ("income.interest.investment", 18, "-1.7260319538"),
        ("income.interest.interbank_net", 19, "-0.5727880768"),
    ],
)
def test_real_component_detail_is_lazy_source_backed_and_reconciled(
    metric_id: str,
    expected_count: int,
    expected_total: str,
) -> None:
    parent = _parent()

    payload = service.candidate_financial_indicator_component_detail_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
        metric_id=metric_id,
        parent_idempotency_key=parent["idempotency_key"],
    )

    contributing = [item for item in payload["rows"] if item["row_status"] == "contributing"]
    assert payload["contract_version"] == (
        "candidate-financial-indicator-component-detail-v1"
    )
    assert payload["status"] == "available"
    assert payload["quality_status"] == "standard_candidate"
    assert payload["foot_status"] == "passed"
    assert payload["formal_use_allowed"] is False
    assert payload["driver_status"] == "unclear"
    assert len(contributing) == expected_count
    assert payload["account_contribution_total_yi"] == expected_total
    assert payload["contribution_reconciliation_yi"] == "0"
    assert payload["source_periods"] == parent["source_periods"]
    assert payload["idempotency_key"] == service.candidate_financial_indicator_component_detail_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
        metric_id=metric_id,
        parent_idempotency_key=parent["idempotency_key"],
    )["idempotency_key"]
    assert parent["contract_version"] == "candidate-financial-indicator-period-comparison-v2"


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_LEDGER_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
def test_real_investment_detail_exposes_top_source_locator_despite_microloan_gap() -> None:
    parent = _parent()
    assert parent["full_scope_reason_code"] == "missing_required_sheet"
    assert parent["full_scope_gaps"][0]["required_sheet"] == "微贷"

    payload = service.candidate_financial_indicator_component_detail_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
        metric_id="income.interest.investment",
        parent_idempotency_key=parent["idempotency_key"],
    )

    assert payload["status"] == "available"
    top = payload["rows"][0]
    assert top["account_code"] == "51402010003"
    assert top["contribution_to_net_delta_yi"] == "-1.3160266974"
    assert top["source_evidence"][0]["sheet"] == "综本"
    assert top["source_evidence"][0]["row"] == 1041
    assert top["source_evidence"][0]["ending_cell"] == "G1041"


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_LEDGER_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
def test_stale_parent_returns_empty_explanation_without_loading_detail_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _parent()
    monkeypatch.setattr(
        service,
        "candidate_financial_indicator_period_comparison_envelope",
        lambda **_kwargs: parent,
    )
    monkeypatch.setattr(
        service,
        "_load_ledger_only_period",
        lambda **_kwargs: pytest.fail("stale detail must not reload ledger sources"),
    )

    payload = service.candidate_financial_indicator_component_detail_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
        metric_id="income.interest.investment",
        parent_idempotency_key="0" * 64,
    )

    assert payload["status"] == "stale_parent"
    assert payload["quality_status"] == "not_evaluable"
    assert payload["foot_status"] == "not_evaluable"
    assert payload["rows"] == []
    assert payload["parent_current_value_yi"] is None
    assert payload["reasons"] == ["parent_idempotency_key_mismatch"]


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_LEDGER_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
def test_non_evaluable_parent_bridge_blocks_detail_source_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = deepcopy(_parent())
    parent["net_interest_component_bridge"].update(
        {
            "status": "not_evaluable",
            "quality_status": "not_evaluable",
            "foot_status": "failed",
            "reasons": ["parent_bridge_failed"],
        }
    )
    monkeypatch.setattr(
        service,
        "candidate_financial_indicator_period_comparison_envelope",
        lambda **_kwargs: parent,
    )
    monkeypatch.setattr(
        service,
        "_load_ledger_only_period",
        lambda **_kwargs: pytest.fail(
            "non-evaluable parent bridge must not load detail sources"
        ),
    )

    payload = service.candidate_financial_indicator_component_detail_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
        metric_id="income.interest.investment",
        parent_idempotency_key=parent["idempotency_key"],
    )

    assert payload["status"] == "not_evaluable"
    assert payload["quality_status"] == "not_evaluable"
    assert payload["foot_status"] == "not_evaluable"
    assert payload["rows"] == []
    assert payload["reasons"] == ["parent_bridge_not_evaluable"]


@pytest.mark.skipif(
    not all(path.is_file() for path in REAL_LEDGER_WORKBOOKS),
    reason="requires local governed source workbooks for 202604/202605/202606",
)
def test_component_detail_rejects_source_hash_drift_from_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _parent()
    real_loader = service._load_ledger_only_period
    monkeypatch.setattr(
        service,
        "candidate_financial_indicator_period_comparison_envelope",
        lambda **_kwargs: parent,
    )

    def drifted_loader(*, root: Path, report_month: str):
        source = real_loader(root=root, report_month=report_month)
        if report_month == "202605":
            return replace(source, ledger_sha256="f" * 64)
        return source

    monkeypatch.setattr(service, "_load_ledger_only_period", drifted_loader)

    with pytest.raises(
        service.CandidateFinancialIndicatorPeriodComparisonRequestError,
        match="source evidence does not match the visible parent",
    ):
        service.candidate_financial_indicator_component_detail_envelope(
            source_dir=str(SOURCE_DIR),
            report_month="202606",
            metric_id="income.interest.investment",
            parent_idempotency_key=parent["idempotency_key"],
        )


@pytest.mark.parametrize(
    "metric_id",
    ["income.interest.net", "income.interest.investment.extra", ""],
)
def test_component_detail_rejects_metrics_outside_fixed_allowlist(metric_id: str) -> None:
    with pytest.raises(
        service.CandidateFinancialIndicatorPeriodComparisonRequestError,
        match="metric_id",
    ):
        service.candidate_financial_indicator_component_detail_envelope(
            source_dir="unused",
            report_month="202606",
            metric_id=metric_id,
            parent_idempotency_key="0" * 64,
        )
