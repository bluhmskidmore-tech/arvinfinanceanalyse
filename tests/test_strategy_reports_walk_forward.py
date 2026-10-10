"""walk-forward 策略报告展示面：service 裁剪逻辑 + 路由契约。

- service 层用合成 JSON 验证裁剪字段(中位/均值、rpt 序列、verdict 透传、容错)。
- 路由层验证 404(报告缺失)、403(无读权限)、200(裁剪 envelope) 契约。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.services.strategy_report_service import (
    WALK_FORWARD_REPORT_PATH_ENV,
    build_walk_forward_summary,
    load_walk_forward_report,
    resolve_walk_forward_report_path,
    walk_forward_summary_envelope,
)
from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_market_data,
]


def _synthetic_report() -> dict[str, object]:
    return {
        "generated_at": "2026-08-12T15:11:00+08:00",
        "engine_version": "wf-2026.08",
        "mode": "detailed",
        "issues": ["adjusted_return missing block"],
        "schedules": [
            {
                "schedule": {
                    "label": "primary_6t_2v_2s",
                    "train_months": 6,
                    "valid_months": 2,
                    "step_months": 2,
                    "objective": "sharpe",
                    "purge_enabled": True,
                    "min_windows_for_verdict": 3,
                    "detailed": True,
                },
                "windows": [
                    {"window_id": "S1W1"},
                    {"window_id": "S1W2"},
                    {"window_id": "S1W3"},
                    {"window_id": "S1W4"},
                ],
                "segments": [],
                "equal_weight": {
                    "uptrend_momentum": {
                        "verdict": "oos_weakened",
                        "verdict_reason": "样本外优势缩水",
                        "oos_window_count": 3,
                        "oos_chain_excess": 0.012,
                        "in_sample": {"excess_vs_gate": 0.08, "cumulative_return": 0.2},
                        "excess_sign_consistency": {
                            "observed_windows": 3,
                            "positive_windows": 2,
                            "negative_windows": 1,
                            "zero_windows": 0,
                            "positive_ratio": 0.6667,
                        },
                        "decay_cumulative": {"delta": -0.05, "ratio": 0.4, "status": "weakened"},
                        "windows": [
                            {"window_id": "S1W1", "excess_vs_gate": 0.01},
                            {"window_id": "S1W2", "excess_vs_gate": -0.02},
                            {"window_id": "S1W3", "excess_vs_gate": 0.03},
                            {"window_id": "S1W4", "excess_vs_gate": None},
                        ],
                    },
                },
                "risk_budget": {
                    "uptrend_momentum": {
                        "grid": [0.0025, 0.005],
                        "policy_param": 0.005,
                        "selected": {
                            "verdict": "oos_weakened",
                            "oos_chain_excess": 0.01,
                            "oos_window_count": 3,
                        },
                        "drift": {
                            "observed_windows": 3,
                            "distinct_values": 2,
                            "switch_count": 2,
                            "switch_rate": 0.6667,
                            "mode_value": 0.005,
                            "mode_share": 0.5,
                            "mean_abs_step": 0.0025,
                        },
                        "windows": [
                            {"window_id": "S1W1", "selected": 0.005, "oracle": 0.0025},
                            {"window_id": "S1W2", "selected": 0.0025, "oracle": 0.0025},
                            {"window_id": "S1W3", "selected": 0.005, "oracle": 0.005},
                            {"window_id": "S1W4", "selected": None, "oracle": None},
                        ],
                    },
                    "only_risk_budget_strategy": {
                        "grid": [0.0025],
                        "policy_param": 0.0025,
                        "drift": {"observed_windows": 0},
                        "windows": [],
                    },
                },
            }
        ],
    }


@pytest.mark.unit
def test_build_walk_forward_summary_trims_synthetic_report() -> None:
    summary = build_walk_forward_summary(_synthetic_report())

    assert summary["generated_at"] == "2026-08-12T15:11:00+08:00"
    assert summary["engine_version"] == "wf-2026.08"
    assert summary["issue_count"] == 1
    assert len(summary["schedules"]) == 1

    schedule = summary["schedules"][0]
    assert schedule["label"] == "primary_6t_2v_2s"
    assert schedule["train_months"] == 6
    assert schedule["valid_months"] == 2
    assert schedule["window_count"] == 4
    # equal_weight 与 risk_budget 的策略名取并集并排序。
    names = [row["strategy"] for row in schedule["strategies"]]
    assert names == ["only_risk_budget_strategy", "uptrend_momentum"]

    row = schedule["strategies"][1]
    assert row["verdict"] == "oos_weakened"
    assert row["verdict_reason"] == "样本外优势缩水"
    assert row["oos_window_count"] == 3
    assert row["in_sample_excess"] == 0.08
    # 逐窗样本外超额 [0.01, -0.02, 0.03]，None 不参与。
    assert row["oos_excess_median"] == 0.01
    assert row["oos_excess_mean"] == pytest.approx(0.006667)
    assert row["oos_chain_excess"] == 0.012
    assert row["excess_sign_consistency"]["positive_ratio"] == 0.6667
    assert row["excess_sign_consistency"]["positive_windows"] == 2
    assert row["excess_sign_consistency"]["observed_windows"] == 3
    assert row["decay_cumulative_status"] == "weakened"

    risk_budget = row["risk_budget"]
    assert risk_budget["policy_param"] == 0.005
    assert risk_budget["selected_verdict"] == "oos_weakened"
    assert risk_budget["switch_rate"] == 0.6667
    assert risk_budget["switch_count"] == 2
    assert risk_budget["mode_value"] == 0.005
    assert [entry["selected"] for entry in risk_budget["window_params"]] == [0.005, 0.0025, 0.005, None]
    assert [entry["oracle"] for entry in risk_budget["window_params"]] == [0.0025, 0.0025, 0.005, None]

    # 只出现在 risk_budget 的策略：equal_weight 字段整体缺失但不报错。
    only_rb = schedule["strategies"][0]
    assert only_rb["verdict"] is None
    assert only_rb["in_sample_excess"] is None
    assert only_rb["oos_excess_median"] is None
    assert only_rb["risk_budget"]["policy_param"] == 0.0025


@pytest.mark.unit
def test_load_walk_forward_report_missing_or_broken_returns_none(tmp_path: Path) -> None:
    assert load_walk_forward_report(tmp_path / "not-there.json") is None
    broken = tmp_path / "broken.json"
    broken.write_text("{not-json", encoding="utf-8")
    assert load_walk_forward_report(broken) is None
    non_object = tmp_path / "list.json"
    non_object.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_walk_forward_report(non_object) is None


@pytest.mark.unit
def test_walk_forward_summary_envelope_none_when_missing(tmp_path: Path) -> None:
    assert walk_forward_summary_envelope(tmp_path / "absent.json") is None


def _walk_forward_report_defect(path: Path) -> str | None:
    """把 load_walk_forward_report 归一成 None 的各个分支还原成可读的损坏原因。

    service 侧把"缺失/不可解析/顶层非 dict"统一成 None 是路由层要的语义(映射 404)，
    这里不改它；测试侧自行检查文件状态，好让"已提交工件被截断/损坏/误删"三种情况
    在失败信息里能区分开。返回 None 表示文件可用。
    """
    if not path.exists():
        return f"文件不存在: {path}"
    if not path.is_file():
        return f"路径存在但不是普通文件: {path}"
    size = path.stat().st_size
    try:
        raw_text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return f"文件不是合法 UTF-8({exc}); 磁盘 {size} 字节: {path}"
    except OSError as exc:
        return f"文件不可读({type(exc).__name__}: {exc}); 磁盘 {size} 字节: {path}"
    if not raw_text.strip():
        return f"文件内容为空; 磁盘 {size} 字节: {path}"
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return f"JSON 解析失败({exc}); 磁盘 {size} 字节，疑似被截断或损坏: {path}"
    if not isinstance(parsed, dict):
        return f"JSON 顶层是 {type(parsed).__name__} 而非 object; 磁盘 {size} 字节: {path}"
    return None


@pytest.mark.unit
def test_real_report_summary_stays_under_50kb(monkeypatch: pytest.MonkeyPatch) -> None:
    """真实首跑报告裁剪后的体积锚点(fail-closed)。

    依赖资产 docs/strategy-reports/walk-forward-first-run.json 是随仓库提交的工件
    (git 已跟踪、非 gitignore、非 LFS)，任何 checkout 都应在场。因此缺失或损坏属于
    仓库完整性回归，必须报红；这里不留跳过口子。
    """
    monkeypatch.delenv(WALK_FORWARD_REPORT_PATH_ENV, raising=False)
    report_path = resolve_walk_forward_report_path()

    defect = _walk_forward_report_defect(report_path)
    assert defect is None, (
        f"仓库内已提交的 walk-forward 报告不可用({defect})；"
        "该文件随仓库提交，缺失/损坏是仓库完整性回归而非环境缺失"
    )

    envelope = walk_forward_summary_envelope()
    assert envelope is not None, f"报告文件自检通过但 envelope 仍为 None，读取/裁剪链路异常: {report_path}"

    result = envelope["result"]
    assert result["schedules"], f"报告 schedules 为空，工件疑似被清空或改写: {report_path}"
    assert all(schedule["strategies"] for schedule in result["schedules"]), (
        f"存在无策略行的 schedule，报告结构疑似退化: {report_path}"
    )

    body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    assert len(body) < 50 * 1024, (
        f"裁剪后 envelope {len(body)} 字节，超出 50KB 展示预算"
        f"(原始报告 {report_path.stat().st_size} 字节): {report_path}"
    )


def _strategy_reports_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    report_path: Path,
    grant_read: bool = True,
) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    sqlite_path = tmp_path / "strategy-reports-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_USER_ID", "strategy-reports-test-user")
    monkeypatch.setenv(WALK_FORWARD_REPORT_PATH_ENV, str(report_path))
    get_settings.cache_clear()
    if grant_read:
        UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
            user_id="*",
            role=None,
            resource="strategy_reports",
            action="read",
        )
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    return TestClient(load_module("backend.app.main", "backend/app/main.py").app)


def test_walk_forward_route_returns_404_when_report_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _strategy_reports_client(
        tmp_path, monkeypatch, report_path=tmp_path / "missing-report.json"
    )
    response = client.get("/api/strategy-reports/walk-forward")
    assert response.status_code == 404
    assert "not available" in response.json()["detail"]


def test_walk_forward_route_forbidden_without_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_synthetic_report(), ensure_ascii=False), encoding="utf-8")
    client = _strategy_reports_client(
        tmp_path, monkeypatch, report_path=report_path, grant_read=False
    )
    response = client.get("/api/strategy-reports/walk-forward")
    assert response.status_code == 403


def test_walk_forward_route_returns_trimmed_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_synthetic_report(), ensure_ascii=False), encoding="utf-8")
    client = _strategy_reports_client(tmp_path, monkeypatch, report_path=report_path)

    response = client.get("/api/strategy-reports/walk-forward")
    assert response.status_code == 200
    payload = response.json()

    meta = payload["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["result_kind"] == "strategy_reports.walk_forward"
    assert meta["quality_flag"] == "warning"  # 合成报告带 1 条 issue

    result = payload["result"]
    assert result["issue_count"] == 1
    schedule = result["schedules"][0]
    assert schedule["label"] == "primary_6t_2v_2s"
    row = next(r for r in schedule["strategies"] if r["strategy"] == "uptrend_momentum")
    assert row["verdict"] == "oos_weakened"
    assert row["oos_excess_median"] == 0.01
    assert row["risk_budget"]["switch_rate"] == 0.6667
    # 展示裁剪目标：响应体 < 50KB。
    assert len(response.content) < 50 * 1024
