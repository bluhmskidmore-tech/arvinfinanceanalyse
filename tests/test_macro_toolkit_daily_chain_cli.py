"""每日模型链 CLI（scripts/macro_toolkit_daily_chain.py）的调度语义回归。

只锁 CLI 层行为：dry-run 计划、回执结构与退出码、失败语义、链外脚本清单顺序。
不实跑任何模型脚本（dry-run 或 monkeypatch），不碰 DuckDB 写路径。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "macro_toolkit_daily_chain_cli",
    ROOT / "scripts" / "macro_toolkit_daily_chain.py",
)
assert _SPEC is not None and _SPEC.loader is not None
cli = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = cli
_SPEC.loader.exec_module(cli)

pytestmark = pytest.mark.unit


def test_extra_scripts_cover_offchain_models_in_dependency_order() -> None:
    assert cli.EXTRA_MODEL_SCRIPTS == (
        "garch_multi_asset",
        "regime_switch_cn",
        "risk_parity_cn",
        "rebalance_cn",
        "performance_metrics_cn",
        "backtest_cn",
    )
    # rebalance/performance/backtest 消费 risk_parity 产物，必须排在其后。
    order = {name: index for index, name in enumerate(cli.EXTRA_MODEL_SCRIPTS)}
    assert order["risk_parity_cn"] < order["rebalance_cn"]
    assert order["risk_parity_cn"] < order["performance_metrics_cn"]
    assert order["risk_parity_cn"] < order["backtest_cn"]


def test_dry_run_writes_receipt_and_exits_zero(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli.macro_toolkit_service,
        "run_macro_toolkit_chain",
        lambda **kwargs: {"status": "dry_run", "chain_id": "macro_toolkit_chain:test", "readiness_after": {}},
    )
    receipt_path = tmp_path / "receipt.json"
    exit_code = cli.main(["--dry-run", "--receipt-path", str(receipt_path), "--run-kind", "scheduled"])
    assert exit_code == 0

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["task_name"] == "macro_toolkit_daily_chain"
    assert receipt["run_kind"] == "scheduled"
    assert receipt["invocation_mode"] == "dry_run"
    assert receipt["status"] == "dry_run"
    assert receipt["exit_code"] == 0
    result = receipt["result"]
    assert [step["script"] for step in result["extra_scripts"]] == list(cli.EXTRA_MODEL_SCRIPTS)
    assert all(step["status"] == "dry_run" for step in result["extra_scripts"])

    stdout = capsys.readouterr().out
    assert '"status": "dry_run"' in stdout


def test_extra_script_failure_turns_run_into_failed_exit_one(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        cli.macro_toolkit_service,
        "run_macro_toolkit_chain",
        lambda **kwargs: {"status": "completed", "chain_id": "macro_toolkit_chain:test", "readiness_after": {}},
    )

    def _fake_run(script_name: str) -> object:
        if script_name == "rebalance_cn":
            raise RuntimeError("synthetic model failure")
        return object()

    monkeypatch.setattr(cli, "run_toolkit_script", _fake_run)
    receipt_path = tmp_path / "receipt.json"
    exit_code = cli.main(["--run-once", "--receipt-path", str(receipt_path)])
    assert exit_code == 1

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["exit_code"] == 1
    steps = {step["script"]: step for step in receipt["result"]["extra_scripts"]}
    assert steps["rebalance_cn"]["status"] == "error"
    assert "synthetic model failure" in str(steps["rebalance_cn"]["error"])
    # 单个模型失败不阻断后续模型执行。
    assert steps["performance_metrics_cn"]["status"] == "completed"
    assert steps["backtest_cn"]["status"] == "completed"


def test_chain_exception_still_writes_failed_receipt(tmp_path, monkeypatch) -> None:
    def _boom(**kwargs) -> dict[str, object]:
        raise RuntimeError("chain lock unavailable")

    monkeypatch.setattr(cli.macro_toolkit_service, "run_macro_toolkit_chain", _boom)
    receipt_path = tmp_path / "receipt.json"
    exit_code = cli.main(["--run-once", "--receipt-path", str(receipt_path)])
    assert exit_code == 1

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert "chain lock unavailable" in str(receipt["result"]["error"])


def test_degraded_chain_counts_as_success(monkeypatch) -> None:
    # 产物 stale/degraded 是数据新鲜度语义，不是执行失败；调度器不应报红。
    monkeypatch.setattr(
        cli.macro_toolkit_service,
        "run_macro_toolkit_chain",
        lambda **kwargs: {"status": "degraded", "chain_id": "macro_toolkit_chain:test", "readiness_after": {}},
    )
    monkeypatch.setattr(cli, "run_toolkit_script", lambda name: object())
    exit_code = cli.main(["--run-once"])
    assert exit_code == 0
