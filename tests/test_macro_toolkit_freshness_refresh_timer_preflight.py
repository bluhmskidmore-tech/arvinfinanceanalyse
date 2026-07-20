from __future__ import annotations

import json
from pathlib import Path

from scripts.macro_toolkit_freshness_refresh_timer_preflight import run_preflight

SCHEDULER_TASK_NAME = "MOSS-MacroToolkitFreshness"
RECEIPT_TASK_NAME = "refresh_macro_toolkit_freshness"
SOURCE_VERSION = "macro_toolkit_freshness_refresh_v3"
CORE_LATEST_DATES = {
    "fact_commodity_futures_daily": "2026-07-20",
    "CA.CSI300": "2026-07-20",
    "CA.CSI500": "2026-07-20",
    "CA.COPPER": "2026-07-20",
    "NHCI.NH": "2026-07-17",
    "NCD.SHIBOR.1M": "2026-07-20",
    "NCD.SHIBOR.3M": "2026-07-20",
    "NCD.SHIBOR.6M": "2026-07-20",
    "NCD.SHIBOR.9M": "2026-07-20",
    "NCD.SHIBOR.1Y": "2026-07-20",
    "EMM00088132": "2026-07-20",
}


def _write_repo_documents(tmp_path: Path) -> dict[str, Path]:
    checklist_path = tmp_path / "checklist.md"
    packet_path = tmp_path / "packet.md"
    evidence_path = tmp_path / "evidence.md"
    checklist_path.write_text(
        "\n".join(
            [
                "Owner: macro-ops",
                f"Rollback: Disable Windows task `{SCHEDULER_TASK_NAME}`.",
            ]
        ),
        encoding="utf-8",
    )
    packet_path.write_text(
        "\n".join(
            [
                "Timer host: approved Windows host",
                "Write window: daily 06:30 host-local; single-writer DuckDB",
                "Log path: F:\\MOSS-V3\\data\\logs\\macro_toolkit_freshness_refresh.log",
                "Approved command: python scripts/macro_toolkit_freshness_refresh.py --run-once",
            ]
        ),
        encoding="utf-8",
    )
    evidence_path.write_text(
        "First scheduled run evidence: shadow --run-once must not count\n",
        encoding="utf-8",
    )
    return {
        "checklist_path": checklist_path,
        "packet_path": packet_path,
        "evidence_path": evidence_path,
    }


def _scheduled_receipt(
    *,
    run_kind: str = "scheduled",
    invocation_mode: str = "run_once",
    status: str = "success",
    cffex_status: str = "success",
    cffex_row_count: int = 7,
) -> dict[str, object]:
    cffex_result: dict[str, object] = (
        {"row_count": cffex_row_count}
        if cffex_status == "success"
        else {"attempts": [{"status": "zero_rows", "row_count": 0}]}
    )
    result = {
        "status": status,
        "source_version": SOURCE_VERSION,
        "steps": [
            {
                "step": "commodity_daily_ingest",
                "status": "success",
                "result": {"row_count": 12},
            },
            {
                "step": "public_cross_asset_headlines",
                "status": "success",
                "result": {"row_count": 100},
            },
            {
                "step": "choice_policy_rate_7d",
                "status": "success",
                "result": {"row_count": 21},
            },
            {
                "step": "tushare_ncd_shibor",
                "status": "success",
                "result": {"row_count": 35},
            },
            {
                "step": "cffex_member_rank",
                "status": cffex_status,
                "result": cffex_result,
            },
        ],
        "latest_observation_dates": dict(CORE_LATEST_DATES),
    }
    return {
        "schema_version": 1,
        "generated_at": "2026-07-20T10:35:00+00:00",
        "run_kind": run_kind,
        "invocation_mode": invocation_mode,
        "task_name": RECEIPT_TASK_NAME,
        "commit_sha": "0123456789abcdef",
        "source_version": SOURCE_VERSION,
        "status": status,
        "exit_code": 0,
        "result": result,
        "warnings": [],
    }


def _write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.write_text(json.dumps(receipt), encoding="utf-8")


def _ready_scheduler(task_name: str) -> dict[str, object]:
    assert task_name == SCHEDULER_TASK_NAME
    return {
        "TaskName": SCHEDULER_TASK_NAME,
        "Enabled": True,
        "State": "Ready",
        "LastRunTime": "2026-07-20T06:30:00-04:00",
        "LastTaskResult": 0,
    }


def test_pre_enable_ignores_first_scheduled_run_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    paths = _write_repo_documents(tmp_path)

    def scheduler_must_not_run(_task_name: str) -> dict[str, object]:
        raise AssertionError("pre-enable must not inspect Task Scheduler")

    result = run_preflight(
        **paths,
        receipt_path=tmp_path / "not-created-yet.json",
        scheduler_probe=scheduler_must_not_run,
    )

    assert result["repo_status"] == "repo-complete"
    assert result["ops_status"] == "ready"
    assert result["packet_safe"] is True
    assert result["missing_fields"] == []
    assert result["stage"] == "pre-enable"
    assert result["receipt_status"] == "not_checked"
    assert result["scheduler_status"] == "not_checked"
    assert result["warnings"] == []


def test_post_enable_accepts_valid_scheduled_run(tmp_path) -> None:
    paths = _write_repo_documents(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(receipt_path, _scheduled_receipt())

    result = run_preflight(
        **paths,
        stage="post-enable",
        receipt_path=receipt_path,
        task_name=SCHEDULER_TASK_NAME,
        scheduler_probe=_ready_scheduler,
    )

    assert result["repo_status"] == "repo-complete"
    assert result["ops_status"] == "ready"
    assert result["receipt_status"] == "ready"
    assert result["scheduler_status"] == "ready"
    assert result["missing_fields"] == []
    assert result["warnings"] == []


def test_post_enable_rejects_shadow_receipt(tmp_path) -> None:
    paths = _write_repo_documents(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(receipt_path, _scheduled_receipt(run_kind="shadow"))

    result = run_preflight(
        **paths,
        stage="post-enable",
        receipt_path=receipt_path,
        task_name=SCHEDULER_TASK_NAME,
        scheduler_probe=_ready_scheduler,
    )

    assert result["ops_status"] == "blocked"
    assert result["receipt_status"] == "blocked"
    assert "receipt.run_kind" in result["missing_fields"]


def test_post_enable_rejects_queued_acknowledgement(tmp_path) -> None:
    paths = _write_repo_documents(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt = _scheduled_receipt(invocation_mode="enqueue", status="queued")
    receipt["result"] = {
        "status": "queued",
        "actor": RECEIPT_TASK_NAME,
        "message_id": "queued-1",
    }
    _write_receipt(receipt_path, receipt)

    result = run_preflight(
        **paths,
        stage="post-enable",
        receipt_path=receipt_path,
        task_name=SCHEDULER_TASK_NAME,
        scheduler_probe=_ready_scheduler,
    )

    assert result["ops_status"] == "blocked"
    assert result["receipt_status"] == "blocked"
    assert "receipt.invocation_mode" in result["missing_fields"]
    assert "receipt.status" in result["missing_fields"]


def test_post_enable_rejects_successful_cffex_with_zero_rows(tmp_path) -> None:
    paths = _write_repo_documents(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(receipt_path, _scheduled_receipt(cffex_row_count=0))

    result = run_preflight(
        **paths,
        stage="post-enable",
        receipt_path=receipt_path,
        task_name=SCHEDULER_TASK_NAME,
        scheduler_probe=_ready_scheduler,
    )

    assert result["ops_status"] == "blocked"
    assert result["receipt_status"] == "blocked"
    assert "receipt.result.steps.cffex_member_rank.row_count" in result["missing_fields"]


def test_post_enable_accepts_degraded_cffex_with_warning(tmp_path) -> None:
    paths = _write_repo_documents(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(
        receipt_path,
        _scheduled_receipt(status="degraded", cffex_status="degraded"),
    )

    result = run_preflight(
        **paths,
        stage="post-enable",
        receipt_path=receipt_path,
        task_name=SCHEDULER_TASK_NAME,
        scheduler_probe=_ready_scheduler,
    )

    assert result["ops_status"] == "ready_with_warning"
    assert result["receipt_status"] == "ready_with_warning"
    assert result["scheduler_status"] == "ready"
    assert any("cffex" in warning.lower() for warning in result["warnings"])


def test_post_enable_rejects_never_run_scheduler(tmp_path) -> None:
    paths = _write_repo_documents(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(receipt_path, _scheduled_receipt())

    def never_run_scheduler(_task_name: str) -> dict[str, object]:
        return {
            "TaskName": SCHEDULER_TASK_NAME,
            "Enabled": True,
            "State": "Ready",
            "LastRunTime": "1999-11-30T00:00:00-05:00",
            "LastTaskResult": 0,
        }

    result = run_preflight(
        **paths,
        stage="post-enable",
        receipt_path=receipt_path,
        task_name=SCHEDULER_TASK_NAME,
        scheduler_probe=never_run_scheduler,
    )

    assert result["ops_status"] == "blocked"
    assert result["scheduler_status"] == "blocked"
    assert "scheduler.last_run_time" in result["missing_fields"]


def test_post_enable_rejects_missing_or_invalid_receipt(tmp_path) -> None:
    paths = _write_repo_documents(tmp_path)
    missing_path = tmp_path / "missing.json"

    missing = run_preflight(
        **paths,
        stage="post-enable",
        receipt_path=missing_path,
        task_name=SCHEDULER_TASK_NAME,
        scheduler_probe=_ready_scheduler,
    )
    assert missing["ops_status"] == "blocked"
    assert missing["receipt_status"] == "missing"
    assert "receipt" in missing["missing_fields"]

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{not-json", encoding="utf-8")
    invalid = run_preflight(
        **paths,
        stage="post-enable",
        receipt_path=invalid_path,
        task_name=SCHEDULER_TASK_NAME,
        scheduler_probe=_ready_scheduler,
    )
    assert invalid["ops_status"] == "blocked"
    assert invalid["receipt_status"] == "invalid"
    assert "receipt" in invalid["missing_fields"]


def test_post_enable_rejects_required_zero_rows_and_missing_core_date(tmp_path) -> None:
    paths = _write_repo_documents(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt = _scheduled_receipt()
    result_payload = receipt["result"]
    assert isinstance(result_payload, dict)
    steps = result_payload["steps"]
    assert isinstance(steps, list)
    commodity = steps[0]
    assert isinstance(commodity, dict)
    commodity_result = commodity["result"]
    assert isinstance(commodity_result, dict)
    commodity_result["row_count"] = 0
    latest_dates = result_payload["latest_observation_dates"]
    assert isinstance(latest_dates, dict)
    latest_dates["NCD.SHIBOR.1Y"] = None
    _write_receipt(receipt_path, receipt)

    result = run_preflight(
        **paths,
        stage="post-enable",
        receipt_path=receipt_path,
        task_name=SCHEDULER_TASK_NAME,
        scheduler_probe=_ready_scheduler,
    )

    assert result["ops_status"] == "blocked"
    assert "receipt.result.steps.commodity_daily_ingest.row_count" in result["missing_fields"]
    assert (
        "receipt.result.latest_observation_dates.NCD.SHIBOR.1Y"
        in result["missing_fields"]
    )


def test_post_enable_requires_task1_policy_rate_step_and_date(tmp_path) -> None:
    paths = _write_repo_documents(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt = _scheduled_receipt()
    result_payload = receipt["result"]
    assert isinstance(result_payload, dict)
    steps = result_payload["steps"]
    assert isinstance(steps, list)
    result_payload["steps"] = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("step") != "choice_policy_rate_7d"
    ]
    latest_dates = result_payload["latest_observation_dates"]
    assert isinstance(latest_dates, dict)
    latest_dates.pop("EMM00088132")
    _write_receipt(receipt_path, receipt)

    result = run_preflight(
        **paths,
        stage="post-enable",
        receipt_path=receipt_path,
        task_name=SCHEDULER_TASK_NAME,
        scheduler_probe=_ready_scheduler,
    )

    assert result["ops_status"] == "blocked"
    assert "receipt.result.steps.choice_policy_rate_7d" in result["missing_fields"]
    assert (
        "receipt.result.latest_observation_dates.EMM00088132"
        in result["missing_fields"]
    )
