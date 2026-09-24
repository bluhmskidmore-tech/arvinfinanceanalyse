from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.schemas.pnl import PnlByBusinessManualAdjustmentRequest
from backend.app.services import pnl_service


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        governance_path=str(tmp_path / "governance"),
        duckdb_path=str(tmp_path / "moss.duckdb"),
    )


def _adjustment_request() -> PnlByBusinessManualAdjustmentRequest:
    return PnlByBusinessManualAdjustmentRequest(
        report_date="2025-12-31",
        row_key="asset_zqtz_policy_financial_bond",
        business_type="Policy Financial Bond",
        operator="DELTA",
        approval_status="pending",
        manual_adjustment=Decimal("25.00"),
        reason="unit test",
    )


def test_request_rejects_impossible_calendar_report_date() -> None:
    with pytest.raises(ValueError, match="report_date must be a real calendar date"):
        PnlByBusinessManualAdjustmentRequest(
            report_date="2026-02-31",
            row_key="asset_zqtz_policy_financial_bond",
            manual_adjustment=Decimal("25.00"),
        )


def test_approve_rejects_non_available_month_end_cutoff(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def list_union_report_dates(self):
            return ["2025-12-31"]

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_enqueue_pnl_by_business_precompute_refresh",
        lambda *_args, **_kwargs: pytest.fail("invalid cutoff must not enqueue precompute"),
    )
    created = pnl_service.create_pnl_by_business_manual_adjustment(
        settings,
        _adjustment_request().model_copy(update={"report_date": "2025-11-30"}),
        created_by="maker",
    )

    with pytest.raises(ValueError, match="not an available month-end cutoff"):
        pnl_service.approve_pnl_by_business_manual_adjustment(
            settings,
            adjustment_id=created["adjustment_id"],
            approved_by="checker",
        )

    current = pnl_service.list_pnl_by_business_manual_adjustments(
        settings,
        report_date="2025-11-30",
    )["adjustments"][0]
    assert current["approval_status"] == "pending"


def test_approve_rejects_when_created_by_is_empty(tmp_path):
    settings = _settings(tmp_path)
    created = pnl_service.create_pnl_by_business_manual_adjustment(
        settings,
        _adjustment_request(),
        created_by="",
    )
    assert created["created_by"] == ""

    with pytest.raises(PermissionError, match="missing created_by"):
        pnl_service.approve_pnl_by_business_manual_adjustment(
            settings,
            adjustment_id=created["adjustment_id"],
            approved_by="checker",
        )


def test_approve_rejects_when_approved_by_is_empty(tmp_path):
    settings = _settings(tmp_path)
    created = pnl_service.create_pnl_by_business_manual_adjustment(
        settings,
        _adjustment_request(),
        created_by="maker",
    )

    with pytest.raises(PermissionError, match="Approver identity is required"):
        pnl_service.approve_pnl_by_business_manual_adjustment(
            settings,
            adjustment_id=created["adjustment_id"],
            approved_by="   ",
        )


def test_approve_rejects_when_maker_equals_checker(tmp_path):
    settings = _settings(tmp_path)
    created = pnl_service.create_pnl_by_business_manual_adjustment(
        settings,
        _adjustment_request(),
        created_by="maker",
    )

    with pytest.raises(PermissionError, match="cannot approve the same adjustment"):
        pnl_service.approve_pnl_by_business_manual_adjustment(
            settings,
            adjustment_id=created["adjustment_id"],
            approved_by="maker",
        )


def test_approve_succeeds_when_checker_differs_from_maker(tmp_path, monkeypatch):
    settings = _settings(tmp_path)

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def list_union_report_dates(self):
            return ["2025-12-31"]

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_enqueue_pnl_by_business_precompute_refresh",
        lambda *_args, **_kwargs: True,
    )
    created = pnl_service.create_pnl_by_business_manual_adjustment(
        settings,
        _adjustment_request(),
        created_by="maker",
    )

    approved = pnl_service.approve_pnl_by_business_manual_adjustment(
        settings,
        adjustment_id=created["adjustment_id"],
        approved_by="checker",
    )
    assert approved["approval_status"] == "approved"
    assert approved["approved_by"] == "checker"
    assert approved["created_by"] == "maker"
