from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.helpers import load_module


def _load_module():
    return load_module(
        "scripts.run_global_data_refresh",
        "scripts/run_global_data_refresh.py",
    )


def test_global_data_refresh_dry_run_is_explicit_and_write_free():
    module = _load_module()

    payload = module.run_global_data_refresh(
        report_date="2026-07-31",
        dry_run=True,
    )

    assert payload["status"] == "dry_run"
    assert payload["report_date"] == "2026-07-31"
    assert payload["fx_source_path"] is None
    assert payload["fx_input_mode"] == "provider_refresh"
    assert payload["use_existing_fx_only"] is False
    assert payload["expected_fx_source_version"] is None
    assert payload["curve_input_mode"] == "provider_refresh"
    assert payload["use_existing_curves_only"] is False
    assert payload["expected_curve_snapshots"] is None
    assert tuple(payload["steps"]) == module.GLOBAL_REFRESH_STEP_NAMES
    assert "fx_daily_mid" in payload["required_date_tables"]


def test_global_data_refresh_steps_fail_fast_and_preserve_receipt():
    module = _load_module()
    called = []

    def _completed():
        called.append("completed")
        return {"status": "completed", "row_count": 1}

    def _failed():
        called.append("failed")
        return {"status": "failed", "error_message": "fixture failure"}

    def _must_not_run():
        called.append("must_not_run")
        return {"status": "completed"}

    with pytest.raises(module.GlobalDataRefreshFailed) as caught:
        module._execute_refresh_steps(
            report_date="2026-07-31",
            run_id="global-test",
            steps=[
                ("first", _completed),
                ("second", _failed),
                ("third", _must_not_run),
            ],
        )

    receipt = caught.value.receipt
    assert called == ["completed", "failed"]
    assert receipt["status"] == "failed"
    assert receipt["failed_step"] == "second"
    assert [step["status"] for step in receipt["steps"]] == ["completed", "failed"]


def test_global_data_refresh_steps_complete_in_declared_order():
    module = _load_module()
    called = []

    def _step(name):
        def _execute():
            called.append(name)
            return {"status": "completed", "name": name}

        return _execute

    receipt = module._execute_refresh_steps(
        report_date="2026-07-31",
        run_id="global-test",
        steps=[("one", _step("one")), ("two", _step("two"))],
    )

    assert called == ["one", "two"]
    assert receipt["status"] == "completed"
    assert [step["name"] for step in receipt["steps"]] == ["one", "two"]


def test_global_data_refresh_rejects_ambiguous_date_and_missing_explicit_fx(tmp_path):
    module = _load_module()

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        module.run_global_data_refresh(report_date="latest", dry_run=True)

    with pytest.raises(FileNotFoundError, match="Explicit FX source"):
        module.run_global_data_refresh(
            report_date="2026-07-31",
            fx_source_path=str(tmp_path / "missing.csv"),
            dry_run=True,
        )


def test_progress_marks_completion_only_after_final_verification():
    module = _load_module()
    events = []

    def record(receipt):
        events.append((receipt["status"], receipt.get("current_step")))

    def reject():
        raise ValueError("required report date missing")

    with pytest.raises(module.GlobalDataRefreshFailed):
        module._execute_refresh_steps(
            report_date="2026-08-31", run_id="progress-test",
            steps=[("formal_balance", lambda: {"status": "completed"}), ("verify", reject)],
            on_progress=record,
        )
    assert ("running", "verify") in events
    assert events[-1][0] == "failed"
    assert all(status != "completed" for status, _ in events)


def test_resource_budget_failure_preserves_limits_in_step_receipt():
    from backend.app.tasks.pnl_by_business_resource_scope import (
        PnlByBusinessResourceBudgetExceeded,
    )

    module = _load_module()
    resource_limits = {
        "profile": "bounded_v1",
        "stage": "before_page_envelope_persist",
    }

    def exceed_budget():
        raise PnlByBusinessResourceBudgetExceeded(
            "injected resource budget breach",
            receipt=resource_limits,
        )

    with pytest.raises(module.GlobalDataRefreshFailed) as caught:
        module._execute_refresh_steps(
            report_date="2026-08-31",
            run_id="resource-failure",
            steps=[("pnl_by_business_page_prepare", exceed_budget)],
        )

    failed_step = caught.value.receipt["steps"][-1]
    assert failed_step["failure_category"] == "resource_over_budget"
    assert failed_step["resource_limits"] == resource_limits


def test_global_existing_fx_dry_run_records_effective_mode_and_expected_version():
    module = _load_module()

    payload = module.run_global_data_refresh(
        report_date="2026-08-31",
        use_existing_fx_only=True,
        expected_fx_source_version=" sv_fx_choice_fixture ",
        dry_run=True,
    )

    assert payload["fx_input_mode"] == "existing_canonical"
    assert payload["use_existing_fx_only"] is True
    assert payload["expected_fx_source_version"] == "sv_fx_choice_fixture"


@pytest.mark.parametrize("invalid", [0, 1, "true", None])
def test_global_existing_fx_mode_rejects_non_boolean_values(invalid):
    module = _load_module()

    with pytest.raises(TypeError, match="use_existing_fx_only must be a bool"):
        module.run_global_data_refresh(
            report_date="2026-08-31",
            use_existing_fx_only=invalid,
            dry_run=True,
        )


@pytest.mark.parametrize("invalid", ["", " ", 123])
def test_global_existing_fx_mode_rejects_invalid_expected_version(invalid):
    module = _load_module()
    expected_error = TypeError if invalid == 123 else ValueError

    with pytest.raises(expected_error, match="expected_fx_source_version"):
        module.run_global_data_refresh(
            report_date="2026-08-31",
            use_existing_fx_only=True,
            expected_fx_source_version=invalid,
            dry_run=True,
        )


def test_global_existing_fx_mode_requires_expected_version_and_excludes_other_inputs():
    module = _load_module()

    with pytest.raises(ValueError, match="requires expected_fx_source_version"):
        module.run_global_data_refresh(
            report_date="2026-08-31",
            use_existing_fx_only=True,
            dry_run=True,
        )
    with pytest.raises(ValueError, match="requires use_existing_fx_only=True"):
        module.run_global_data_refresh(
            report_date="2026-08-31",
            expected_fx_source_version="sv_fx_choice_fixture",
            dry_run=True,
        )
    with pytest.raises(ValueError, match="conflicts with an explicit fx_source_path"):
        module.run_global_data_refresh(
            report_date="2026-08-31",
            fx_source_path="unused.csv",
            use_existing_fx_only=True,
            expected_fx_source_version="sv_fx_choice_fixture",
            dry_run=True,
        )


def test_build_refresh_steps_forwards_existing_fx_contract(monkeypatch):
    module = _load_module()
    pipeline_mod = load_module(
        "backend.app.tasks.formal_balance_pipeline",
        "backend/app/tasks/formal_balance_pipeline.py",
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        pipeline_mod,
        "run_formal_balance_pipeline_sync",
        lambda **kwargs: calls.append(dict(kwargs)) or {"status": "completed"},
    )
    settings = SimpleNamespace(
        duckdb_path="data/moss.duckdb",
        governance_path="data/governance",
        data_input_root="data/input",
        local_archive_path="data/archive",
        financial_publication_enabled=False,
    )

    steps = module._build_refresh_steps(
        settings=settings,
        report_date="2026-08-31",
        run_id="global-test",
        fx_source_path=None,
        use_existing_fx_only=True,
        expected_fx_source_version="sv_fx_choice_fixture",
    )
    steps[0][1]()

    assert calls[0]["use_existing_fx_only"] is True
    assert calls[0]["expected_fx_source_version"] == "sv_fx_choice_fixture"


@pytest.mark.parametrize("step_status", ["completed", "failed"])
def test_global_receipt_and_callbacks_record_existing_fx_contract(monkeypatch, step_status):
    module = _load_module()
    settings = SimpleNamespace(
        duckdb_path="data/moss.duckdb",
        financial_publication_enabled=False,
        financial_publication_root="",
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "acquire_lock", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(
        module,
        "_build_refresh_steps",
        lambda **_kwargs: [("formal_balance", lambda: {"status": step_status})],
    )
    callbacks: list[dict[str, object]] = []
    kwargs = {
        "report_date": "2026-08-31",
        "use_existing_fx_only": True,
        "expected_fx_source_version": "sv_fx_choice_fixture",
        "on_progress": lambda payload: callbacks.append(dict(payload)),
    }

    if step_status == "failed":
        with pytest.raises(module.GlobalDataRefreshFailed) as caught:
            module.run_global_data_refresh(**kwargs)
        receipt = caught.value.receipt
    else:
        receipt = module.run_global_data_refresh(**kwargs)

    assert receipt["fx_input_mode"] == "existing_canonical"
    assert receipt["use_existing_fx_only"] is True
    assert receipt["expected_fx_source_version"] == "sv_fx_choice_fixture"
    assert callbacks
    assert all(item["fx_input_mode"] == "existing_canonical" for item in callbacks)
    assert all(item["use_existing_fx_only"] is True for item in callbacks)
    assert all(
        item["expected_fx_source_version"] == "sv_fx_choice_fixture" for item in callbacks
    )


def test_progress_reports_each_step_without_premature_completion():
    module = _load_module()
    events = []

    def record(receipt):
        events.append(
            (
                receipt["status"],
                receipt.get("current_step"),
                tuple((step["name"], step["status"]) for step in receipt["steps"]),
            )
        )

    def fail_verification():
        raise ValueError("required report date missing")

    with pytest.raises(module.GlobalDataRefreshFailed):
        module._execute_refresh_steps(
            report_date="2026-07-31",
            run_id="progress-test",
            steps=[
                ("formal_balance", lambda: {"status": "completed"}),
                ("verify", fail_verification),
            ],
            on_progress=record,
        )

    assert events[0] == ("running", "formal_balance", ())
    assert events[1] == ("running", None, (("formal_balance", "completed"),))
    assert events[2][0:2] == ("running", "verify")
    assert events[-1][0] == "failed"
    assert events[-1][2][-1] == ("verify", "failed")
    assert all(status != "completed" for status, _, _ in events)



def test_public_global_refresh_forwards_progress_and_completes_after_final_step(
    monkeypatch, tmp_path
):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=tmp_path / "db.duckdb"),
    )
    monkeypatch.setattr(module, "acquire_lock", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(
        module,
        "_build_refresh_steps",
        lambda **_kwargs: [("verify", lambda: {"status": "completed"})],
    )
    events = []

    result = module.run_global_data_refresh(
        report_date="2026-07-31",
        on_progress=lambda receipt: events.append(
            (receipt["status"], receipt.get("current_step"), len(receipt["steps"]))
        ),
    )

    assert result["status"] == "completed"
    assert events == [
        ("running", "verify", 0),
        ("running", None, 1),
        ("completed", None, 1),
    ]



def test_report_date_verification_fails_closed_when_count_query_has_no_row(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(module, "REQUIRED_DATE_TABLES", (("sample", "report_date", 1),))
    connection = Mock()
    connection.execute.side_effect = [
        Mock(fetchall=Mock(return_value=[("sample",)])),
        Mock(fetchone=Mock(return_value=None)),
    ]
    monkeypatch.setattr(module, "read_only_connection", lambda _path: nullcontext(connection))

    with pytest.raises(RuntimeError, match="COUNT query returned no row"):
        module._verify_report_date(
            duckdb_path=str(tmp_path / "moss.duckdb"),
            choice_macro_catalog_file=tmp_path / "choice.csv",
            report_date="2026-07-31",
        )
