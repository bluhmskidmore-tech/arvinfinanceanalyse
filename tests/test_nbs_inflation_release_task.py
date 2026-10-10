from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from backend.app.tasks import nbs_inflation_release_ingest as task_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_data,
]


@dataclass
class _Settings:
    duckdb_path: str
    governance_path: str


def test_task_validates_and_passes_source_ip_to_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class AdapterStub:
        def __init__(self, *, source_ip: str | None = None) -> None:
            captured["adapter_source_ip"] = source_ip

    class ServiceStub:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def ingest_release_month(
            self,
            ingest_batch_id: str,
            *,
            reference_date: date,
            reference_month: str | None,
        ) -> dict[str, object]:
            assert ingest_batch_id == "nbs-inflation-source-bound"
            assert reference_date == date(2026, 9, 16)
            assert reference_month == "2026-08"
            return {
                "status": "success",
                "reference_month": reference_month,
                "reference_months": [reference_month],
                "results": [],
                "materialized_rows": 2,
            }

    monkeypatch.setattr(
        task_module,
        "get_settings",
        lambda: _Settings(
            str(tmp_path / "task.duckdb"),
            str(tmp_path / "governance"),
        ),
    )
    monkeypatch.setattr(
        task_module,
        "resolve_vendor_source_ip",
        lambda value: captured.setdefault("resolved_from", value) or "192.0.2.10",
    )
    monkeypatch.setattr(task_module, "NbsInflationReleaseAdapter", AdapterStub)
    monkeypatch.setattr(task_module, "NbsInflationReleaseIngestService", ServiceStub)

    result = task_module.run_nbs_inflation_release_ingest_once(
        "nbs-inflation-source-bound",
        reference_date=date(2026, 9, 16),
        reference_month="2026-08",
        source_ip="192.0.2.10",
    )

    assert result["status"] == "success"
    assert result["source_ip"] == "192.0.2.10"
    assert captured["resolved_from"] == "192.0.2.10"
    assert captured["adapter_source_ip"] == "192.0.2.10"


def test_task_cli_passes_source_ip_without_writing_in_test(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        task_module,
        "run_nbs_inflation_release_ingest_once",
        lambda **kwargs: calls.append(kwargs)
        or {"status": "success", "materialized_rows": 2},
    )

    assert (
        task_module.main(
            ["--reference-month", "2026-08", "--source-ip", "192.0.2.10"]
        )
        == 0
    )

    assert calls == [
        {"reference_month": "2026-08", "source_ip": "192.0.2.10"}
    ]
    assert json.loads(capsys.readouterr().out)["status"] == "success"


@pytest.mark.parametrize("failure_type", [task_module.NbsInflationReleaseError, RuntimeError, TypeError])
def test_nbs_failure_cli_receipt_omits_private_provider_payload(tmp_path, monkeypatch, capsys, failure_type):
    from unittest.mock import Mock

    marker = "synthetic-nbs-provider-private-token"
    monkeypatch.setattr(task_module, "get_settings", lambda: _Settings(str(tmp_path / "unused.duckdb"), str(tmp_path / "governance")))
    monkeypatch.setattr(task_module, "resolve_vendor_source_ip", Mock(side_effect=failure_type(marker)))
    connect = Mock(side_effect=AssertionError("failure must stop before opening DuckDB"))
    monkeypatch.setattr(task_module.duckdb, "connect", connect)
    assert task_module.main(["--reference-month", "2026-08", "--source-ip", "192.0.2.10"]) == 1
    output = capsys.readouterr().out
    receipt = json.loads(output)
    assert receipt["status"] == ("blocked" if failure_type is task_module.NbsInflationReleaseError else "error")
    assert receipt["reference_month"] == "2026-08"
    assert receipt["source_ip"] == "192.0.2.10"
    assert receipt["ingest_batch_id"].startswith("nbs-inflation-")
    connect.assert_not_called()
    assert marker not in output
    assert failure_type.__name__ in receipt["error"]
