from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pytest

from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.pnl_precompute_state import (
    current_pnl_by_business_event_revision_on_connection,
    invalidate_pnl_by_business_precompute_on_connection,
)
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.schemas.pnl import PnlByBusinessManualAdjustmentRequest
from backend.app.services.pnl_by_business_adjustment_handoff import (
    PnlByBusinessAdjustmentHandoffError,
    begin_pnl_by_business_adjustment_handoff,
    mark_pnl_by_business_adjustment_content_committed,
    pending_pnl_by_business_adjustment_handoffs,
    pnl_by_business_adjustment_handoff_status,
    require_pnl_by_business_adjustment_handoff_content,
)
from backend.app.tasks import pnl_by_business_precompute


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        governance_path=str(tmp_path / "governance"),
        duckdb_path=str(tmp_path / "moss.duckdb"),
    )


def _pnl_service():
    return import_module("backend.app.services.pnl_service")


def _request() -> PnlByBusinessManualAdjustmentRequest:
    return PnlByBusinessManualAdjustmentRequest(
        report_date="2025-06-30",
        row_key="asset_zqtz_policy_financial_bond",
        business_type="Policy Financial Bond",
        operator="DELTA",
        approval_status="pending",
        manual_adjustment=Decimal("25.00"),
        reason="durable handoff test",
    )


def _approved_event(tmp_path: Path) -> tuple[SimpleNamespace, dict[str, object]]:
    pnl_service = _pnl_service()
    settings = _settings(tmp_path)
    created = pnl_service.create_pnl_by_business_manual_adjustment(
        settings,
        _request(),
        created_by="maker",
    )
    return settings, {
        **created,
        "event_type": "approved",
        "created_at": datetime.now(UTC).isoformat(),
        "approval_status": "approved",
        "approved_by": "checker",
    }


def test_adjustment_write_failure_leaves_pending_receipt_before_content(
    tmp_path,
    monkeypatch,
) -> None:
    pnl_service = _pnl_service()
    settings = _settings(tmp_path)
    created = pnl_service.create_pnl_by_business_manual_adjustment(
        settings,
        _request(),
        created_by="maker",
    )
    monkeypatch.setattr(
        pnl_service,
        "_require_available_pnl_by_business_adjustment_cutoff",
        lambda *_args, **_kwargs: None,
    )
    original_append = GovernanceRepository.append

    def fail_adjustment_append(self, stream, payload):
        if stream == pnl_service.PNL_BY_BUSINESS_ADJUSTMENT_STREAM:
            raise OSError("simulated governance content failure")
        return original_append(self, stream, payload)

    monkeypatch.setattr(GovernanceRepository, "append", fail_adjustment_append)

    with pytest.raises(OSError, match="simulated governance content failure"):
        pnl_service.approve_pnl_by_business_manual_adjustment(
            settings,
            adjustment_id=str(created["adjustment_id"]),
            approved_by="checker",
        )

    pending = pending_pnl_by_business_adjustment_handoffs(settings.governance_path)
    assert len(pending) == 1
    assert pending[0]["status"] == "pending"
    assert pending[0]["dependency_dates"] == ["2025-06-30"]
    status = pnl_by_business_adjustment_handoff_status(
        settings.governance_path,
        dependency_dates=["2025-12-31"],
    )
    assert status["pending"] is True
    with pytest.raises(PnlByBusinessAdjustmentHandoffError):
        require_pnl_by_business_adjustment_handoff_content(
            settings.governance_path,
            handoffs=pending,
        )


def test_worker_confirmation_is_idempotent_across_commit_before_ack_retry(
    tmp_path,
    monkeypatch,
) -> None:
    pnl_service = _pnl_service()
    settings, approved = _approved_event(tmp_path)
    handoff = begin_pnl_by_business_adjustment_handoff(
        settings.governance_path,
        adjustment_id=str(approved["adjustment_id"]),
        dependency_dates=["2025-06-30"],
        reason="adjustment_approved",
        expected_adjustment_event=approved,
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        pnl_service.PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
        approved,
    )
    handoff = mark_pnl_by_business_adjustment_content_committed(
        settings.governance_path,
        handoff=handoff,
    )
    original_ack = pnl_by_business_precompute.acknowledge_pnl_by_business_adjustment_handoff
    monkeypatch.setattr(
        pnl_by_business_precompute,
        "acknowledge_pnl_by_business_adjustment_handoff",
        Mock(side_effect=OSError("simulated crash before ack")),
    )

    with pytest.raises(OSError, match="simulated crash before ack"):
        pnl_by_business_precompute.confirm_pnl_by_business_adjustment_handoffs_under_writer(
            duckdb_path=settings.duckdb_path,
            governance_dir=settings.governance_path,
            handoff_ids=[str(handoff["handoff_id"])],
            year=2025,
            target_dates=["2025-06-30", "2025-12-31"],
        )

    with duckdb.connect(settings.duckdb_path, read_only=True) as conn:
        assert current_pnl_by_business_event_revision_on_connection(conn) == 1
    monkeypatch.setattr(
        pnl_by_business_precompute,
        "acknowledge_pnl_by_business_adjustment_handoff",
        original_ack,
    )
    result = pnl_by_business_precompute.confirm_pnl_by_business_adjustment_handoffs_under_writer(
        duckdb_path=settings.duckdb_path,
        governance_dir=settings.governance_path,
        handoff_ids=[str(handoff["handoff_id"])],
        year=2025,
        target_dates=["2025-06-30", "2025-12-31"],
    )

    assert result["dependency_revision"] == 1
    assert result["acknowledged"] is True
    with duckdb.connect(settings.duckdb_path, read_only=True) as conn:
        assert current_pnl_by_business_event_revision_on_connection(conn) == 1
    assert pending_pnl_by_business_adjustment_handoffs(settings.governance_path) == []


def test_queue_deduplicates_by_revision_and_exact_date_coverage(
    tmp_path,
    monkeypatch,
) -> None:
    pnl_service = _pnl_service()
    settings = _settings(tmp_path)
    dispatch = Mock()
    monkeypatch.setattr(
        pnl_service.rebuild_pnl_by_business_precompute,
        "send",
        dispatch,
    )
    common = {
        "year": 2025,
        "as_of_date": None,
        "trigger_reason": "test_recovery",
        "raise_on_dispatch_failure": False,
        "raise_on_duplicate": False,
        "scope": "persistent_dirty",
    }
    first = pnl_service._queue_pnl_by_business_precompute_refresh(
        settings,
        **common,
        as_of_dates=["2025-06-30", "2025-12-31"],
        dependency_revision=7,
    )
    reused = pnl_service._queue_pnl_by_business_precompute_refresh(
        settings,
        **common,
        as_of_dates=["2025-06-30", "2025-12-31"],
        dependency_revision=7,
    )
    partial = pnl_service._queue_pnl_by_business_precompute_refresh(
        settings,
        **common,
        as_of_dates=["2025-06-30", "2025-09-30", "2025-12-31"],
        dependency_revision=7,
    )
    next_revision = pnl_service._queue_pnl_by_business_precompute_refresh(
        settings,
        **common,
        as_of_dates=["2025-06-30"],
        dependency_revision=8,
    )

    assert first is not None
    assert reused is not None and reused["reused"] is True
    assert reused["run_id"] == first["run_id"]
    assert partial is not None and partial["target_as_of_dates"] == ["2025-09-30"]
    assert next_revision is not None
    assert dispatch.call_count == 3
    assert dispatch.call_args_list[1].kwargs["as_of_dates"] == ["2025-09-30"]
    assert dispatch.call_args_list[2].kwargs["dependency_revision"] == 8


def test_dirty_recovery_without_available_cutoff_keeps_intent_undispatched(
    tmp_path,
    monkeypatch,
) -> None:
    pnl_service = _pnl_service()
    settings = _settings(tmp_path)
    dispatch = Mock()
    monkeypatch.setattr(
        pnl_service.rebuild_pnl_by_business_precompute,
        "send",
        dispatch,
    )
    monkeypatch.setattr(
        pnl_service,
        "_available_pnl_by_business_precompute_cutoffs",
        Mock(side_effect=ValueError("No available month-end cutoffs found for year=2025.")),
    )
    with duckdb.connect(settings.duckdb_path, read_only=False) as conn:
        conn.execute("begin transaction")
        invalidate_pnl_by_business_precompute_on_connection(
            conn,
            changed_report_dates=["2025-06-15"],
            reason="daily_balance_replace",
        )
        conn.execute("commit")
    pending = PnlRepository(
        settings.duckdb_path
    ).list_pending_pnl_by_business_precompute()[0]

    result = pnl_service.recover_pending_pnl_by_business_precompute(
        settings,
        pending=dict(pending),
    )

    assert result is None
    dispatch.assert_not_called()
    remaining = PnlRepository(
        settings.duckdb_path
    ).list_pending_pnl_by_business_precompute()
    assert remaining == [pending]
    assert remaining[0]["target_dates"] == ()
