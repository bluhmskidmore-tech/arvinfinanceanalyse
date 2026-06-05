from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import load_module
from tests.test_golden_samples_capture_ready import (
    _load_json,
    _run_sample_request,
    _setup_exec_overview,
    _setup_exec_pnl_attr,
    _setup_exec_summary,
)


ROOT = Path(__file__).resolve().parents[1]


def test_release_gated_exec_samples_match_release_suite_metadata():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    assert module.EXECUTIVE_RELEASE_SAMPLE_IDS == [
        "GS-EXEC-OVERVIEW-A",
        "GS-EXEC-PNL-ATTR-A",
        "GS-EXEC-SUMMARY-A",
    ]


def test_gs_exec_overview_release_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_exec_overview(tmp_path, monkeypatch)

    request = _load_json("GS-EXEC-OVERVIEW-A", "request.json")
    assert request["path"] == "/ui/home/overview"
    assert request["params"]["report_date"] == "2026-02-28"

    actual = _run_sample_request("GS-EXEC-OVERVIEW-A", tmp_path, monkeypatch)
    meta = actual["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["result_kind"] == "executive.overview"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["source_version"] == "sv_balance_union__sv_exec_dashboard_v1"
    assert meta["rule_version"] == "rv_balance_union__rv_exec_dashboard_v1"
    assert meta["cache_version"] == "cv_exec_dashboard_v1"
    assert meta["filters_applied"]["requested_report_date"] == "2026-02-28"
    assert meta["filters_applied"]["effective_report_dates"] == {
        "balance": "2026-02-28",
        "pnl": "2026-02-28",
        "liability": "2026-02-28",
        "risk": "2026-02-28",
    }

    metrics = {metric["id"]: metric for metric in actual["result"]["metrics"]}
    assert metrics["aum"]["caliber_label"] == "本币资产口径"
    assert metrics["aum"]["value"]["display"] == "3,572.76 亿"
    assert metrics["yield"]["value"]["display"] == "+4.69 亿"
    assert metrics["nim"]["value"]["display"] == "+1.00%"
    assert metrics["dv01"]["value"]["display"] == "13,826,218"


def test_gs_exec_pnl_attr_release_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_exec_pnl_attr(tmp_path, monkeypatch)

    request = _load_json("GS-EXEC-PNL-ATTR-A", "request.json")
    assert request["path"] == "/ui/pnl/attribution"
    assert request["params"]["report_date"] == "2026-02-28"

    actual = _run_sample_request("GS-EXEC-PNL-ATTR-A", tmp_path, monkeypatch)
    meta = actual["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["result_kind"] == "executive.pnl-attribution"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["source_version"] == "sv_exec_dashboard_v1__sv_pc_a__sv_pc_b__sv_pc_c"
    assert meta["rule_version"] == "rv_exec_dashboard_v1__rv_pc_a__rv_pc_b__rv_pc_c"
    assert meta["cache_version"] == "cv_exec_dashboard_v1"
    assert meta["filters_applied"]["report_date"] == "2026-02-28"

    result = actual["result"]
    assert result["total"]["display"] == "+1.75 亿"
    segments = {segment["id"]: segment for segment in result["segments"]}
    assert set(segments) == {"carry", "roll", "credit", "trading", "other"}
    assert segments["carry"]["amount"]["display"] == "+3.00 亿"
    assert segments["roll"]["amount"]["display"] == "-3.00 亿"
    assert segments["credit"]["amount"]["display"] == "+0.50 亿"
    assert segments["trading"]["amount"]["display"] == "+1.00 亿"
    assert segments["other"]["amount"]["display"] == "+0.25 亿"


def test_gs_exec_summary_release_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_exec_summary(tmp_path, monkeypatch)

    request = _load_json("GS-EXEC-SUMMARY-A", "request.json")
    assert request["path"] == "/ui/home/summary"
    assert request["params"]["report_date"] == "2026-02-28"

    actual = _run_sample_request("GS-EXEC-SUMMARY-A", tmp_path, monkeypatch)
    meta = actual["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["result_kind"] == "executive.summary"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["source_version"] == "sv_summary_requested"
    assert meta["rule_version"] == "rv_summary_requested"
    assert meta["cache_version"] == "cv_exec_dashboard_v1"

    result = actual["result"]
    assert result["report_date"] == "2026-02-28"
    assert result["title"] == "本周管理摘要"
    assert [point["label"] for point in result["points"]] == ["收益", "风险", "建议"]
