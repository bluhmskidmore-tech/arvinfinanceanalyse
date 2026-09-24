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
