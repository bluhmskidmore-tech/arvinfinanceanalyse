from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import load_module


def _load_risk_script():
    return load_module(
        "scripts.run_risk_tensor_materialize",
        "scripts/run_risk_tensor_materialize.py",
    )


def _load_movement_script():
    return load_module(
        "scripts.run_accounting_asset_movement_refresh",
        "scripts/run_accounting_asset_movement_refresh.py",
    )


class _FakeActor:
    actor_name = "materialize_risk_tensor_facts"

    def __init__(self) -> None:
        self.fn_calls: list[dict[str, object]] = []
        self.send_calls: list[dict[str, object]] = []

    def fn(self, **kwargs: object) -> dict[str, object]:
        self.fn_calls.append(kwargs)
        return {
            "status": "completed",
            "run_id": kwargs["run_id"],
            "report_date": kwargs["report_date"],
        }

    def send(self, **kwargs: object) -> object:
        self.send_calls.append(kwargs)
        return type("Message", (), {"message_id": "risk-msg-1"})()


def test_risk_tensor_operator_wrapper_runs_task_actor_sync(tmp_path: Path) -> None:
    module = _load_risk_script()
    actor = _FakeActor()
    module.materialize_risk_tensor_facts = actor

    result = module.run_risk_tensor_materialize(
        report_date="2026-05-31",
        duckdb_path=tmp_path / "moss.duckdb",
        governance_dir=tmp_path / "governance",
        run_id="risk-run-1",
        enqueue=False,
    )

    assert result == {
        "status": "completed",
        "run_id": "risk-run-1",
        "report_date": "2026-05-31",
    }
    assert actor.fn_calls == [
        {
            "report_date": "2026-05-31",
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "governance_dir": str(tmp_path / "governance"),
            "run_id": "risk-run-1",
        }
    ]
    assert actor.send_calls == []


def test_risk_tensor_operator_wrapper_can_enqueue_task_actor(tmp_path: Path) -> None:
    module = _load_risk_script()
    actor = _FakeActor()
    module.materialize_risk_tensor_facts = actor

    result = module.run_risk_tensor_materialize(
        report_date="2026-05-31",
        duckdb_path=tmp_path / "moss.duckdb",
        governance_dir=tmp_path / "governance",
        run_id="risk-run-2",
        enqueue=True,
    )

    assert result == {
        "status": "queued",
        "actor": "materialize_risk_tensor_facts",
        "message_id": "risk-msg-1",
        "report_date": "2026-05-31",
        "run_id": "risk-run-2",
    }
    assert actor.send_calls == [
        {
            "report_date": "2026-05-31",
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "governance_dir": str(tmp_path / "governance"),
            "run_id": "risk-run-2",
        }
    ]
    assert actor.fn_calls == []


def test_risk_tensor_operator_wrapper_dry_run_emits_no_task_call(
    tmp_path: Path,
) -> None:
    module = _load_risk_script()
    actor = _FakeActor()
    module.materialize_risk_tensor_facts = actor

    result = module.run_risk_tensor_materialize(
        report_date="2026-05-31",
        duckdb_path=tmp_path / "moss.duckdb",
        governance_dir=tmp_path / "governance",
        run_id="risk-run-3",
        dry_run=True,
    )

    assert result == {
        "status": "dry_run",
        "would_call": {
            "report_date": "2026-05-31",
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "governance_dir": str(tmp_path / "governance"),
            "run_id": "risk-run-3",
        },
        "boundary": {
            "operator_entrypoint": True,
            "writes_duckdb_via_task": True,
            "uses_api_or_service_write_path": False,
            "changes_schema": False,
        },
    }
    assert actor.fn_calls == []
    assert actor.send_calls == []


def test_risk_tensor_operator_wrapper_cli_outputs_json(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_risk_script()
    actor = _FakeActor()
    module.materialize_risk_tensor_facts = actor

    exit_code = module.main(
        [
            "--report-date",
            "2026-05-31",
            "--duckdb-path",
            str(tmp_path / "moss.duckdb"),
            "--governance-dir",
            str(tmp_path / "governance"),
            "--run-id",
            "risk-run-4",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "dry_run"
    assert payload["would_call"]["run_id"] == "risk-run-4"
    assert actor.fn_calls == []
    assert actor.send_calls == []


def test_accounting_movement_operator_wrapper_runs_task_sync_wrapper(
    tmp_path: Path,
) -> None:
    module = _load_movement_script()
    calls: list[dict[str, object]] = []

    def fake_refresh(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "status": "completed",
            "run_id": kwargs["run_id"],
            "movement_refreshed_dates": kwargs["report_dates"],
        }

    module.refresh_accounting_asset_movement_window_sync = fake_refresh

    result = module.run_accounting_asset_movement_refresh(
        report_dates=["2026-05-31"],
        anchor_report_date="2026-05-31",
        duckdb_path=tmp_path / "moss.duckdb",
        governance_dir=tmp_path / "governance",
        currency_basis="CNX",
        product_category_refreshed_dates=["2026-05-31"],
        formal_balance_refreshed_dates=["2026-05-31"],
        run_id="movement-run-1",
    )

    assert result == {
        "status": "completed",
        "run_id": "movement-run-1",
        "movement_refreshed_dates": ["2026-05-31"],
    }
    assert calls == [
        {
            "report_dates": ["2026-05-31"],
            "anchor_report_date": "2026-05-31",
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "governance_dir": str(tmp_path / "governance"),
            "currency_basis": "CNX",
            "product_category_refreshed_dates": ["2026-05-31"],
            "formal_balance_refreshed_dates": ["2026-05-31"],
            "run_id": "movement-run-1",
        }
    ]


def test_accounting_movement_operator_wrapper_dry_run_emits_no_task_call(
    tmp_path: Path,
) -> None:
    module = _load_movement_script()
    calls: list[dict[str, object]] = []

    def fake_refresh(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"status": "unexpected"}

    module.refresh_accounting_asset_movement_window_sync = fake_refresh

    result = module.run_accounting_asset_movement_refresh(
        report_dates=["2026-05-31"],
        anchor_report_date="2026-05-31",
        duckdb_path=tmp_path / "moss.duckdb",
        governance_dir=tmp_path / "governance",
        currency_basis="CNX",
        product_category_refreshed_dates=["2026-05-31"],
        formal_balance_refreshed_dates=["2026-05-31"],
        run_id="movement-run-2",
        dry_run=True,
    )

    assert result == {
        "status": "dry_run",
        "would_call": {
            "report_dates": ["2026-05-31"],
            "anchor_report_date": "2026-05-31",
            "duckdb_path": str(tmp_path / "moss.duckdb"),
            "governance_dir": str(tmp_path / "governance"),
            "currency_basis": "CNX",
            "product_category_refreshed_dates": ["2026-05-31"],
            "formal_balance_refreshed_dates": ["2026-05-31"],
            "run_id": "movement-run-2",
        },
        "boundary": {
            "operator_entrypoint": True,
            "writes_duckdb_via_task": True,
            "uses_api_or_service_write_path": False,
            "changes_schema": False,
        },
    }
    assert calls == []


def test_accounting_movement_operator_wrapper_cli_outputs_json(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_movement_script()
    calls: list[dict[str, object]] = []

    def fake_refresh(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"status": "unexpected"}

    module.refresh_accounting_asset_movement_window_sync = fake_refresh

    exit_code = module.main(
        [
            "--report-date",
            "2026-05-31",
            "--duckdb-path",
            str(tmp_path / "moss.duckdb"),
            "--governance-dir",
            str(tmp_path / "governance"),
            "--run-id",
            "movement-run-3",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "dry_run"
    assert payload["would_call"]["report_dates"] == ["2026-05-31"]
    assert payload["would_call"]["product_category_refreshed_dates"] == [
        "2026-05-31"
    ]
    assert payload["would_call"]["formal_balance_refreshed_dates"] == [
        "2026-05-31"
    ]
    assert calls == []
