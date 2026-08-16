from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.services.macro_toolkit_refresh_receipt_service import (
    CORE_LATEST_OBSERVATION_KEYS,
    load_macro_toolkit_refresh_receipt_health,
)

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_macro_toolkit,
]


def _scheduled_receipt(
    *,
    status: str = "success",
    cffex_status: str = "success",
) -> dict[str, object]:
    latest_dates = {key: "2026-08-08" for key in CORE_LATEST_OBSERVATION_KEYS}
    return {
        "schema_version": 1,
        "generated_at": "2026-08-09T10:30:00+00:00",
        "run_kind": "scheduled",
        "invocation_mode": "run_once",
        "task_name": "refresh_macro_toolkit_freshness",
        "source_version": "macro_toolkit_freshness_refresh_v3",
        "status": status,
        "exit_code": 0,
        "warnings": [],
        "result": {
            "status": status,
            "steps": [
                {
                    "step": "commodity_daily_ingest",
                    "status": "success",
                    "result": {"row_count": 210},
                },
                {
                    "step": "public_cross_asset_headlines",
                    "status": "success",
                    "result": {"row_count": 4467},
                },
                {
                    "step": "choice_policy_rate_7d",
                    "status": "success",
                    "result": {"row_count": 31},
                },
                {
                    "step": "tushare_ncd_shibor",
                    "status": "success",
                    "result": {"row_count": 35},
                },
                {
                    "step": "cffex_member_rank",
                    "status": cffex_status,
                    "result": {"row_count": 154} if cffex_status == "success" else {},
                },
            ],
            "latest_observation_dates": latest_dates,
        },
    }


def _write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.write_text(json.dumps(receipt), encoding="utf-8")


def test_missing_or_invalid_receipt_fails_closed(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"

    missing = load_macro_toolkit_refresh_receipt_health(receipt_path)
    assert missing.status == "missing"
    assert missing.ready is False
    assert missing.cache_fingerprint == "missing"
    assert missing.missing_fields == ("receipt",)

    receipt_path.write_text("not-json", encoding="utf-8")
    invalid = load_macro_toolkit_refresh_receipt_health(receipt_path)
    assert invalid.status == "invalid"
    assert invalid.ready is False
    assert invalid.cache_fingerprint.startswith("invalid:")
    assert invalid.missing_fields == ("receipt",)


@pytest.mark.parametrize("row_count", [0, -1, None, "not-a-number"])
def test_required_step_without_positive_rows_blocks_analysis(
    tmp_path: Path,
    row_count: object,
) -> None:
    receipt = _scheduled_receipt()
    steps = receipt["result"]["steps"]
    steps[0]["result"]["row_count"] = row_count
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(receipt_path, receipt)

    health = load_macro_toolkit_refresh_receipt_health(receipt_path)

    assert health.status == "blocked"
    assert health.ready is False
    assert "receipt.result.steps.commodity_daily_ingest.row_count" in health.missing_fields


def test_missing_core_latest_date_blocks_analysis(tmp_path: Path) -> None:
    receipt = _scheduled_receipt()
    receipt["result"]["latest_observation_dates"]["CA.CSI300"] = None
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(receipt_path, receipt)

    health = load_macro_toolkit_refresh_receipt_health(receipt_path)

    assert health.status == "blocked"
    assert health.ready is False
    assert "receipt.result.latest_observation_dates.CA.CSI300" in health.missing_fields


def test_running_receipt_blocks_directional_analysis(tmp_path: Path) -> None:
    receipt = _scheduled_receipt(status="running")
    receipt["exit_code"] = None
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(receipt_path, receipt)

    health = load_macro_toolkit_refresh_receipt_health(receipt_path)

    assert health.status == "blocked"
    assert health.ready is False
    assert "receipt.status" in health.missing_fields
    assert "receipt.exit_code" in health.missing_fields


def test_valid_receipt_is_ready_and_content_change_breaks_fingerprint(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    receipt = _scheduled_receipt()
    _write_receipt(receipt_path, receipt)
    first = load_macro_toolkit_refresh_receipt_health(receipt_path)

    receipt["result"]["steps"][0]["result"]["row_count"] = 211
    _write_receipt(receipt_path, receipt)
    second = load_macro_toolkit_refresh_receipt_health(receipt_path)

    assert first.status == "ready"
    assert first.ready is True
    assert first.latest_observation_dates["CA.CSI300"] == "2026-08-08"
    assert second.status == "ready"
    assert second.cache_fingerprint != first.cache_fingerprint


def test_degraded_receipt_with_optional_cffex_degradation_remains_usable(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(
        receipt_path,
        _scheduled_receipt(status="degraded", cffex_status="degraded"),
    )

    health = load_macro_toolkit_refresh_receipt_health(receipt_path)

    assert health.status == "ready_with_warning"
    assert health.ready is True
    assert any("CFFEX" in warning for warning in health.warnings)
