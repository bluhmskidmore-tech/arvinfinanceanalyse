from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.schemas.pnl import PnlByBusinessManualAdjustmentRequest
from backend.app.services import pnl_service


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(governance_path=str(tmp_path / "governance"))


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


def test_approve_succeeds_when_checker_differs_from_maker(tmp_path):
    settings = _settings(tmp_path)
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
