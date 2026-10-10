from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.services.macro_toolkit_refresh_receipt_service import (
    CORE_LATEST_OBSERVATION_KEYS,
    MacroToolkitRefreshReceiptHealth,
    load_macro_toolkit_refresh_receipt_health,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


def _receipt(*, status: str = "success") -> dict[str, object]:
    steps = [
        {
            "step": step,
            "status": "success",
            "attempt_count": 1,
            "result": {"row_count": 10},
        }
        for step in (
            "choice_policy_rate_7d",
            "choice_crisis_aa_5y",
            "commodity_daily_ingest",
            "public_cross_asset_headlines",
            "tushare_ncd_shibor",
        )
    ]
    steps.append(
        {
            "step": "cffex_member_rank",
            "status": "success",
            "attempt_count": 1,
            "result": {"row_count": 10},
        }
    )
    return {
        "schema_version": 1,
        "generated_at": "2026-08-25T01:00:00+00:00",
        "run_kind": "scheduled",
        "invocation_mode": "run_once",
        "task_name": "refresh_macro_toolkit_freshness",
        "source_version": "macro_toolkit_freshness_refresh_v4",
        "status": status,
        "exit_code": 0 if status == "success" else 1,
        "warnings": [],
        "result": {
            "status": status,
            "steps": steps,
            "latest_observation_dates": {
                key: "2026-08-24" for key in CORE_LATEST_OBSERVATION_KEYS
            },
        },
    }


def _write(path: Path, receipt: dict[str, object]) -> None:
    path.write_text(json.dumps(receipt), encoding="utf-8")


def test_explicit_failure_details_are_exposed_without_opening_the_gate(
    tmp_path: Path,
) -> None:
    receipt = _receipt(status="failed")
    receipt["failure_category"] = "scheduler_configuration_error"
    receipt["failure_message"] = "configured source IP is not assigned to this host"
    result = receipt["result"]
    assert isinstance(result, dict)
    result["failure_category"] = "upstream_unavailable"
    result["failure_message"] = "lower-priority result failure"
    steps = result["steps"]
    assert isinstance(steps, list)
    steps[0] = {
        "step": "choice_policy_rate_7d",
        "status": "failed",
        "attempt_count": 2,
        "reason": "lower-priority step failure",
        "result": {"row_count": 0},
    }
    path = tmp_path / "receipt.json"
    _write(path, receipt)

    health = load_macro_toolkit_refresh_receipt_health(path)
    payload = health.as_payload()

    assert health.status == "blocked"
    assert health.ready is False
    assert health.failure_category == "scheduler_configuration_error"
    assert health.failure_message == "configured source IP is not assigned to this host"
    assert health.step_statuses["choice_policy_rate_7d"] == {
        "status": "failed",
        "row_count": 0,
        "attempt_count": 2,
        "reason": "lower-priority step failure",
    }
    assert payload["failure_category"] == "scheduler_configuration_error"
    assert payload["failure_message"] == health.failure_message
    assert payload["step_statuses"] == health.step_statuses
    assert any(
        "调度配置错误" in warning
        and health.failure_message in warning
        and "方向性结论已关闭" in warning
        for warning in health.analysis_warnings()
    )


def test_failed_step_reason_is_the_message_fallback(tmp_path: Path) -> None:
    receipt = _receipt(status="failed")
    result = receipt["result"]
    assert isinstance(result, dict)
    steps = result["steps"]
    assert isinstance(steps, list)
    steps[0] = {
        "step": "choice_policy_rate_7d",
        "status": "error",
        "attempt_count": 3,
        "reason": "Choice access permission is pending",
    }
    path = tmp_path / "receipt.json"
    _write(path, receipt)

    health = load_macro_toolkit_refresh_receipt_health(path)

    assert health.status == "blocked"
    assert health.ready is False
    assert health.failure_category == "refresh_execution_failure"
    assert health.failure_message == "Choice access permission is pending"
    assert health.step_statuses["choice_policy_rate_7d"] == {
        "status": "error",
        "attempt_count": 3,
        "reason": "Choice access permission is pending",
    }


@pytest.mark.parametrize("message_source", ["receipt", "result", "step"])
def test_failure_detail_preserves_safe_reason_without_credentials_paths_or_stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, message_source: str
) -> None:
    monkeypatch.setenv("MOSS_API_KEY", "synthetic-environment-secret")
    receipt = _receipt(status="failed")
    receipt["failure_category"] = "upstream_unavailable"
    result = receipt["result"]
    message = (
        "vendor rejected token=synthetic-assigned-secret Bearer synthetic-auth-secret "
        "at C:\\Private\\refresh.py /private/refresh.py with synthetic-environment-secret "
        "Traceback (most recent call last): File internal.py, line 9, private_stack()"
    )
    if message_source == "receipt":
        receipt["failure_message"] = message
    elif message_source == "result":
        result["failure_message"] = message
    else:
        result["steps"][0] = {
            "step": "choice_policy_rate_7d", "status": "failed", "reason": message,
        }
    path = tmp_path / "receipt.json"
    _write(path, receipt)

    health = load_macro_toolkit_refresh_receipt_health(path)
    public_text = json.dumps(
        {"health": health.as_payload(), "warnings": health.analysis_warnings()},
        ensure_ascii=False,
    )

    assert health.status == "blocked"
    assert health.ready is False
    assert "vendor rejected" in public_text
    assert "上游暂不可用" in public_text
    assert "方向性结论已关闭" in public_text
    for sensitive in (
        "synthetic-assigned-secret", "synthetic-auth-secret", "synthetic-environment-secret",
        "Private", "/private/refresh.py", "Traceback", "private_stack", "internal.py",
    ):
        assert sensitive not in public_text


def test_old_success_receipt_and_direct_construction_remain_compatible(
    tmp_path: Path,
) -> None:
    path = tmp_path / "receipt.json"
    _write(path, _receipt())

    health = load_macro_toolkit_refresh_receipt_health(path)

    assert health.status == "ready"
    assert health.ready is True
    assert health.failure_category is None
    assert health.failure_message is None
    assert health.step_statuses["commodity_daily_ingest"] == {
        "status": "success",
        "row_count": 10,
        "attempt_count": 1,
    }
    assert health.as_payload()["failure_category"] is None

    legacy_constructor = MacroToolkitRefreshReceiptHealth(
        status="missing",
        ready=False,
        cache_fingerprint="missing",
        generated_at=None,
        run_status=None,
        source_version=None,
        missing_fields=("receipt",),
        warnings=(),
        latest_observation_dates={},
    )
    assert legacy_constructor.failure_category is None
    assert legacy_constructor.failure_message is None
    assert legacy_constructor.step_statuses == {}
