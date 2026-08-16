from __future__ import annotations

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
