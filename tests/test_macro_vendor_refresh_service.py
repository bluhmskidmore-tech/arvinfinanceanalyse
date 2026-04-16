from __future__ import annotations

import sys

import pytest

from tests.helpers import load_module


def _load_settings_module():
    sys.modules.pop("backend.app.governance.settings", None)
    return load_module(
        "backend.app.governance.settings",
        "backend/app/governance/settings.py",
    )


def _load_macro_vendor_service_module():
    sys.modules.pop("backend.app.services.macro_vendor_service", None)
    return load_module(
        "backend.app.services.macro_vendor_service",
        "backend/app/services/macro_vendor_service.py",
    )


def test_queue_choice_macro_refresh_enqueues_actor_without_sync_fallback(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))

    settings_module = _load_settings_module()
    service_module = _load_macro_vendor_service_module()
    settings = settings_module.get_settings()
    sent: dict[str, object] = {}

    monkeypatch.setattr(
        service_module.refresh_choice_macro_snapshot,
        "send",
        lambda **kwargs: sent.update(kwargs),
    )
    monkeypatch.setattr(
        service_module.refresh_choice_macro_snapshot,
        "fn",
        lambda **_: (_ for _ in ()).throw(AssertionError("sync fallback must not run")),
    )

    payload = service_module.queue_choice_macro_refresh(settings, backfill_days=7)

    assert payload["status"] == "queued"
    assert payload["job_name"] == "choice_macro_refresh"
    assert payload["trigger_mode"] == "async"
    assert payload["cache_key"] == "choice_macro.latest"
    assert sent == {
        "duckdb_path": str(settings.duckdb_path),
        "governance_dir": str(settings.governance_path),
        "backfill_days": 7,
        "run_id": payload["run_id"],
    }

    records = service_module.GovernanceRepository(
        base_dir=settings.governance_path
    ).read_all(service_module.CACHE_BUILD_RUN_STREAM)
    queued = [record for record in records if record.get("run_id") == payload["run_id"]][-1]
    assert queued["status"] == "queued"
    assert queued["source_version"] == "sv_choice_macro_pending"
    assert queued["vendor_version"] == "vv_none"
    assert queued["lock"] == service_module.CHOICE_MACRO_LOCK.key


def test_queue_choice_macro_refresh_marks_run_failed_when_dispatch_fails(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))

    settings_module = _load_settings_module()
    service_module = _load_macro_vendor_service_module()
    settings = settings_module.get_settings()

    monkeypatch.setattr(
        service_module.refresh_choice_macro_snapshot,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("broker unavailable")),
    )
    monkeypatch.setattr(
        service_module.refresh_choice_macro_snapshot,
        "fn",
        lambda **_: (_ for _ in ()).throw(AssertionError("sync fallback must not run")),
    )

    with pytest.raises(service_module.ChoiceMacroRefreshServiceError) as excinfo:
        service_module.queue_choice_macro_refresh(settings)

    assert str(excinfo.value) == "Choice-macro refresh queue dispatch failed."

    records = service_module.GovernanceRepository(
        base_dir=settings.governance_path
    ).read_all(service_module.CACHE_BUILD_RUN_STREAM)
    latest = records[-1]
    assert latest["status"] == "failed"
    assert latest["job_name"] == "choice_macro_refresh"
    assert latest["cache_key"] == "choice_macro.latest"
    assert latest["error_message"] == "Choice-macro refresh queue dispatch failed."
