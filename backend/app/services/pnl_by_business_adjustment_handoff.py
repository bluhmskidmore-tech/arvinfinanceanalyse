from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services.pnl_by_business_adjustments import (
    active_pnl_by_business_manual_adjustments_for_period,
    pnl_by_business_manual_adjustment_source_version,
)

PNL_BY_BUSINESS_ADJUSTMENT_HANDOFF_STREAM = "pnl_by_business_adjustment_handoffs"
PNL_BY_BUSINESS_ADJUSTMENT_HANDOFF_PROTOCOL = "pnl_by_business_adjustment_handoff_v1"


class PnlByBusinessAdjustmentHandoffError(RuntimeError):
    pass


class PnlByBusinessAdjustmentHandoffStatus(TypedDict):
    pending: bool
    handoff_ids: tuple[str, ...]
    dependency_dates: tuple[str, ...]
    last_event_at: str | None
    error_message: str | None
    reason: str | None
    source_versions: dict[str, str]
    protocol_version: str


def begin_pnl_by_business_adjustment_handoff(
    governance_path: str | Path,
    *,
    adjustment_id: str,
    dependency_dates: Iterable[str],
    reason: str,
    expected_adjustment_event: Mapping[str, object],
) -> dict[str, object]:
    dates = _normalize_dates(dependency_dates)
    if not dates:
        raise ValueError("dependency_dates must not be empty for an adjustment handoff")
    now = datetime.now(UTC).isoformat()
    record: dict[str, object] = {
        "handoff_id": f"pba-handoff-{uuid4()}",
        "event_type": "pending",
        "status": "pending",
        "created_at": now,
        "adjustment_id": str(adjustment_id),
        "dependency_dates": list(dates),
        "reason": str(reason or "manual_adjustment_state_change"),
        "expected_adjustment_event_digest": _adjustment_event_digest(
            expected_adjustment_event
        ),
        "protocol_version": PNL_BY_BUSINESS_ADJUSTMENT_HANDOFF_PROTOCOL,
        "error_message": "",
    }
    _append_handoff(governance_path, record)
    return record


def mark_pnl_by_business_adjustment_content_committed(
    governance_path: str | Path,
    *,
    handoff: Mapping[str, object],
) -> dict[str, object]:
    dates = _handoff_dependency_dates(handoff)
    record = {
        **dict(handoff),
        "event_type": "content_committed",
        "status": "content_committed",
        "created_at": datetime.now(UTC).isoformat(),
        "source_versions": pnl_by_business_current_adjustment_source_versions(
            governance_path,
            dependency_dates=dates,
        ),
        "error_message": "",
    }
    _append_handoff(governance_path, record)
    return record


def mark_pnl_by_business_adjustment_dispatch_failed(
    governance_path: str | Path,
    *,
    handoff: Mapping[str, object],
    error_message: str,
) -> dict[str, object]:
    record = {
        **dict(handoff),
        "event_type": "dispatch_failed",
        "status": "dispatch_failed",
        "created_at": datetime.now(UTC).isoformat(),
        "error_message": str(error_message or "queue dispatch failed"),
    }
    _append_handoff(governance_path, record)
    return record


def acknowledge_pnl_by_business_adjustment_handoff(
    governance_path: str | Path,
    *,
    handoff: Mapping[str, object],
    dependency_revision: int,
    source_versions: Mapping[str, str],
) -> dict[str, object]:
    record = {
        **dict(handoff),
        "event_type": "acknowledged",
        "status": "acknowledged",
        "created_at": datetime.now(UTC).isoformat(),
        "dependency_revision": int(dependency_revision),
        "source_versions": dict(source_versions),
        "error_message": "",
    }
    _append_handoff(governance_path, record)
    return record


def pending_pnl_by_business_adjustment_handoffs(
    governance_path: str | Path,
    *,
    handoff_ids: Iterable[str] | None = None,
) -> list[dict[str, object]]:
    selected_ids = {
        str(value).strip() for value in (handoff_ids or ()) if str(value).strip()
    }
    latest = _latest_handoffs(governance_path)
    return [
        record
        for handoff_id, record in sorted(latest.items())
        if (not selected_ids or handoff_id in selected_ids)
        and str(record.get("status") or "") != "acknowledged"
    ]


def pnl_by_business_adjustment_handoff_status(
    governance_path: str | Path,
    *,
    dependency_dates: Iterable[str],
) -> PnlByBusinessAdjustmentHandoffStatus:
    requested_dates = _normalize_dates(dependency_dates)
    relevant: list[dict[str, object]] = []
    for record in _latest_handoffs(governance_path).values():
        dirty_dates = _handoff_dependency_dates(record)
        if _dates_affect_cutoffs(dirty_dates=dirty_dates, cutoffs=requested_dates):
            relevant.append(record)
    pending = [
        record
        for record in relevant
        if str(record.get("status") or "") != "acknowledged"
    ]
    latest = max(
        relevant,
        key=lambda record: str(record.get("created_at") or ""),
        default=None,
    )
    latest_pending = max(
        pending,
        key=lambda record: str(record.get("created_at") or ""),
        default=None,
    )
    latest_error = max(
        (
            record
            for record in pending
            if str(record.get("error_message") or "")
        ),
        key=lambda record: str(record.get("created_at") or ""),
        default=None,
    )
    reason_record = latest_pending or latest
    return {
        "pending": bool(pending),
        "handoff_ids": tuple(
            sorted(str(record.get("handoff_id") or "") for record in pending)
        ),
        "dependency_dates": requested_dates,
        "last_event_at": (
            str(latest.get("created_at") or "") or None if latest else None
        ),
        "error_message": (
            str(latest_error.get("error_message") or "") or None
            if latest_error
            else None
        ),
        "reason": str(reason_record.get("reason") or "") or None if reason_record else None,
        "source_versions": pnl_by_business_current_adjustment_source_versions(
            governance_path,
            dependency_dates=requested_dates,
        ),
        "protocol_version": PNL_BY_BUSINESS_ADJUSTMENT_HANDOFF_PROTOCOL,
    }


def pnl_by_business_current_adjustment_source_versions(
    governance_path: str | Path,
    *,
    dependency_dates: Iterable[str],
) -> dict[str, str]:
    versions: dict[str, str] = {}
    for cutoff in _normalize_dates(dependency_dates):
        parsed = date.fromisoformat(cutoff)
        adjustments = active_pnl_by_business_manual_adjustments_for_period(
            governance_path,
            year=parsed.year,
            period_end=cutoff,
        )
        versions[cutoff] = pnl_by_business_manual_adjustment_source_version(adjustments)
    return versions


def require_pnl_by_business_adjustment_handoff_content(
    governance_path: str | Path,
    *,
    handoffs: Iterable[Mapping[str, object]],
) -> dict[str, str]:
    adjustment_event_digests = {
        _adjustment_event_digest(record)
        for record in GovernanceRepository(base_dir=governance_path).read_all(
            "pnl_by_business_adjustments"
        )
    }
    dependency_dates: set[str] = set()
    for handoff in handoffs:
        expected_digest = str(
            handoff.get("expected_adjustment_event_digest") or ""
        )
        if not expected_digest or expected_digest not in adjustment_event_digests:
            raise PnlByBusinessAdjustmentHandoffError(
                "Adjustment handoff content is not durably present in governance storage."
            )
        dependency_dates.update(_handoff_dependency_dates(handoff))
    return pnl_by_business_current_adjustment_source_versions(
        governance_path,
        dependency_dates=dependency_dates,
    )


def _latest_handoffs(
    governance_path: str | Path,
) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for record in GovernanceRepository(base_dir=governance_path).read_all(
        PNL_BY_BUSINESS_ADJUSTMENT_HANDOFF_STREAM
    ):
        handoff_id = str(record.get("handoff_id") or "").strip()
        if not handoff_id:
            continue
        existing = latest.get(handoff_id)
        if existing is None or str(record.get("created_at") or "") >= str(
            existing.get("created_at") or ""
        ):
            latest[handoff_id] = dict(record)
    return latest


def _append_handoff(
    governance_path: str | Path,
    record: Mapping[str, object],
) -> None:
    GovernanceRepository(base_dir=governance_path).append(
        PNL_BY_BUSINESS_ADJUSTMENT_HANDOFF_STREAM,
        dict(record),
    )


def _adjustment_event_digest(record: Mapping[str, object]) -> str:
    canonical = json.dumps(
        dict(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _normalize_dates(values: Iterable[object]) -> tuple[str, ...]:
    normalized = {
        date.fromisoformat(str(value).strip()).isoformat()
        for value in values
        if str(value or "").strip()
    }
    return tuple(sorted(normalized))


def _handoff_dependency_dates(record: Mapping[str, object]) -> tuple[str, ...]:
    raw_dates = record.get("dependency_dates")
    if not isinstance(raw_dates, Sequence) or isinstance(
        raw_dates, (str, bytes, bytearray)
    ):
        raise PnlByBusinessAdjustmentHandoffError(
            "Adjustment handoff is missing a valid dependency_dates sequence."
        )
    dates = _normalize_dates(raw_dates)
    if not dates:
        raise PnlByBusinessAdjustmentHandoffError(
            "Adjustment handoff dependency_dates must not be empty."
        )
    return dates


def _dates_affect_cutoffs(
    *,
    dirty_dates: Iterable[str],
    cutoffs: Iterable[str],
) -> bool:
    for dirty_date in dirty_dates:
        parsed_dirty = date.fromisoformat(dirty_date)
        for cutoff in cutoffs:
            parsed_cutoff = date.fromisoformat(cutoff)
            if parsed_dirty.year == parsed_cutoff.year and dirty_date <= cutoff:
                return True
    return False
