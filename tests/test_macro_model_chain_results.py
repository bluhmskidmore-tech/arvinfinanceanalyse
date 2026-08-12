"""宏观工具箱决策链结果只读端点（/ui/macro/toolkit/model-chain-results）契约测试。

覆盖 build_model_chain_results 纯函数的七步结构、模型字段、DCC 宽表转置、
headline 规则（含 NaN / 缺文件退化），以及 FastAPI 端点的 envelope 结构与
真实产物目录冒烟。
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.api.routes.macro_toolkit import router as macro_toolkit_router
from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.services.macro_toolkit_service import build_model_chain_results

MACRO_TOOLKIT_READ_HEADERS = {"X-User-Id": "macro-toolkit-read-user", "X-User-Role": "viewer"}

REAL_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "macro_toolkit" / "output"

EXPECTED_STEPS: list[tuple[str, int, str, list[str]]] = [
    ("market_state", 1, "市场状态识别", ["merrill_clock", "garch", "dcc_garch", "regime"]),
    ("strategy_selection", 2, "策略选择", ["cta_trend"]),
    ("allocation", 3, "资产配置", ["risk_parity"]),
    ("risk_management", 4, "风险管理", ["crisis_score", "risk_monitor", "monitor_alerts"]),
    ("rebalance", 5, "再平衡", ["rebalance"]),
    ("performance", 6, "绩效评估", ["performance", "backtest"]),
    ("final_signal", 7, "决策链输出", ["final_signal"]),
]

MODEL_FIELDS = {
    "id",
    "label",
    "script_name",
    "artifact",
    "artifact_status",
    "as_of",
    "headline",
    "columns",
    "rows",
    # trend 契约：全部模型对象恒有该键，无历史数据源时为 None。
    "trend",
}

ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _write_csv(directory: Path, name: str, text: str) -> None:
    (directory / name).write_text(text, encoding="utf-8-sig")


def _seed_full_output_dir(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _write_csv(
        directory,
        "merrill_clock_latest.csv",
        "日期,增长动量,通胀动量,流动性动量,传统象限,bond_direction,bond_note\n"
        "2026-06,0.228,0.836,-0.615,过热,空,利率上行压力\n",
    )
    _write_csv(
        directory,
        "garch_results.csv",
        "资产,最优模型,年化波动率%,波动率状态,操作建议\n"
        "hs300,GARCH / t,15.378212,中波动,适合趋势跟踪/风险平价策略\n"
        "crude_oil,GJR-GARCH / t,63.491167,高波动,适合CTA/尾部对冲\n",
    )
    _write_csv(
        directory,
        "dcc_latest.csv",
        "日期,hs300_gold,gold_copper,平均相关系数,预警状态\n"
        "2026-08-11,0.339,0.4988,0.2764,正常\n",
    )
    _write_csv(
        directory,
        "regime_results.csv",
        "资产,当前状态,策略建议,年化波动率%\n"
        "沪深300,高波动,防御（降仓 / 对冲）,25.40\n"
        "铜,弱震荡,轻仓均值回归,9.74\n",
    )
    _write_csv(
        directory,
        "cta_results.csv",
        "资产,合成信号,趋势强度,操作建议,策略年化收益%,策略夏普比率\n"
        "沪深300,-0.604,强趋势,强空头,-3.92,-0.510\n"
        "铜,0.762,强趋势,强多头,-1.82,-0.302\n"
        "原油,0.648,强趋势,强多头,6.86,0.208\n",
    )
    _write_csv(
        directory,
        "risk_parity_results.csv",
        "资产,风险平价权重%,风险预算权重%,年化波动率%\n"
        "沪深300,21.2580,23.0706,20.0549\n"
        "铜期货,24.6362,20.5013,17.9159\n",
    )
    _write_csv(
        directory,
        "crisis_score_latest.csv",
        "日期,Crisis Score,市场状态,操作建议,股市波动率z,信用利差z\n"
        "2026-08-11,-0.068,宽松,可适当加仓，风险偏好环境,0.938,\n",
    )
    _write_csv(
        directory,
        "risk_state.csv",
        "date,peak_value,cooling_until,entry_prices\n2026-08-12,1000000.0,,{}\n",
    )
    _write_csv(
        directory,
        "risk_log.csv",
        "datetime,event_type,symbol,detail,current_value,drawdown_pct\n"
        "2026-08-10 19:10:00,DAILY_CHECK,ALL,active_positions=0,0.0,0.0\n"
        "2026-08-11 19:10:00,DAILY_CHECK,ALL,active_positions=0,0.0,0.0\n"
        "2026-08-12 06:57:11,VOL_ALERT,crude_oil,年化波动率>30%: crude_oil=63.49%,0.0,0.0\n"
        "2026-08-12 06:57:11,DAILY_CHECK,ALL,active_positions=0,0.0,0.0\n",
    )
    _write_csv(
        directory,
        "rebalance_results.csv",
        "策略,年化收益%,年化波动%,夏普比率,再平衡次数,累计收益%\n"
        "不再平衡,17.5710,14.8693,1.0808,0,49.9788\n"
        "阈值触发(5%),19.0658,14.5369,1.2084,5,54.7991\n",
    )
    _write_csv(
        directory,
        "performance_results.csv",
        "资产/组合,年化收益%,年化波动%,最大回撤%,夏普比率,索提诺比率,Calmar比率,评级\n"
        "沪深300,8.01,18.18,-18.07,0.3578,0.5182,0.4431,需优化\n"
        "黄金期货,29.68,22.80,-30.37,1.2361,1.3448,0.9774,优秀\n",
    )
    _write_csv(
        directory,
        "backtest_results.csv",
        "策略,年化收益%,年化波动%,夏普比率,索提诺比率,最大回撤%,Calmar比率,胜率%,累计收益%\n"
        "买持等权,18.73,14.99,1.150,1.502,-13.70,1.367,54.8,53.61\n"
        "全模型综合,26.86,14.35,1.767,2.244,-12.50,2.149,57.5,81.26\n",
    )
    _write_csv(
        directory,
        "final_signal.csv",
        "品种,日期,第一层_方向,第一层_通过,第二层_通过,第三层_通过,最终信号,仓位比例,置信度,信号说明\n"
        "TS,2026-08-11,空,True,False,False,空仓,0.0,1,第二层拦截\n"
        "T,2026-08-11,空,True,False,False,空仓,0.0,1,第二层拦截\n",
    )


def _models_by_id(result: dict[str, object]) -> dict[str, dict[str, object]]:
    models: dict[str, dict[str, object]] = {}
    for step in result["steps"]:
        for model in step["models"]:
            models[str(model["id"])] = model
    return models


def test_build_model_chain_results_exposes_seven_steps_in_contract_order(tmp_path: Path) -> None:
    _seed_full_output_dir(tmp_path)

    result = build_model_chain_results(tmp_path)

    assert result["as_of_date"] == "2026-08-11"
    assert result["observation_only"] is True
    assert result["formal_use_allowed"] is False
    assert [
        (step["key"], step["step_no"], step["label"], [model["id"] for model in step["models"]])
        for step in result["steps"]
    ] == EXPECTED_STEPS


def test_build_model_chain_results_models_carry_full_contract_fields(tmp_path: Path) -> None:
    _seed_full_output_dir(tmp_path)

    models = _models_by_id(build_model_chain_results(tmp_path))

    assert set(models) == {model_id for _, _, _, ids in EXPECTED_STEPS for model_id in ids}
    for model in models.values():
        assert set(model) == MODEL_FIELDS
        assert model["artifact_status"] == "ok"
        assert isinstance(model["headline"], str) and model["headline"]
        assert len(model["columns"]) > 0
        assert all(len(row) == len(model["columns"]) for row in model["rows"])
        assert all(isinstance(cell, str) for row in model["rows"] for cell in row)

    merrill = models["merrill_clock"]
    assert merrill["label"] == "美林时钟（中国版）"
    assert merrill["script_name"] == "merrill_clock_cn"
    assert merrill["artifact"] == "merrill_clock_latest.csv"
    assert merrill["as_of"] == "2026-06"
    assert merrill["columns"] == ["日期", "增长动量", "通胀动量", "流动性动量", "传统象限", "债券方向"]
    assert merrill["rows"] == [["2026-06", "0.228", "0.836", "-0.615", "过热", "空"]]

    # 无日期列的产物用文件修改日（YYYY-MM-DD）作为 as_of。
    assert ISO_DATE_PATTERN.match(str(models["garch"]["as_of"]))

    # 全列原样的产物保留 CSV 表头与行序，NaN 输出 "—"。
    crisis = models["crisis_score"]
    assert crisis["columns"] == ["日期", "Crisis Score", "市场状态", "操作建议", "股市波动率z", "信用利差z"]
    assert crisis["rows"][0][-1] == "—"

    backtest = models["backtest"]
    assert backtest["columns"] == ["策略", "年化收益%", "夏普比率", "最大回撤%", "胜率%", "累计收益%"]
    assert backtest["rows"][1] == ["全模型综合", "26.86", "1.767", "-12.50", "57.5", "81.26"]

    final_signal = models["final_signal"]
    assert final_signal["columns"] == ["品种", "日期", "第一层_方向", "最终信号", "仓位比例", "置信度", "信号说明"]


def test_build_model_chain_results_headline_rules(tmp_path: Path) -> None:
    _seed_full_output_dir(tmp_path)

    models = _models_by_id(build_model_chain_results(tmp_path))

    assert models["merrill_clock"]["headline"] == "象限 过热 · 债券方向 空"
    assert models["garch"]["headline"] == "高波动 1/2 · 最高 crude_oil 63.491167%"
    assert models["dcc_garch"]["headline"] == "平均相关 0.2764 · 正常"
    assert models["regime"]["headline"] == "高波动 1/2"
    assert models["cta_trend"]["headline"] == "强多头 铜、原油 · 强空头 沪深300"
    assert models["risk_parity"]["headline"] == "风险平价最大权重 铜期货 24.6362%"
    assert models["crisis_score"]["headline"] == "-0.068 · 宽松"
    assert models["risk_monitor"]["headline"] == "无冷却 · 正常运行"
    assert models["monitor_alerts"]["headline"] == "告警 1 条 · VOL_ALERT 1"
    assert models["rebalance"]["headline"] == "最优 阈值触发(5%) · 夏普 1.2084"
    assert models["performance"]["headline"] == "最佳 黄金期货 · 夏普 1.2361"
    assert models["backtest"]["headline"] == "最优 全模型综合 · 夏普 1.767"
    assert models["final_signal"]["headline"] == "空仓 2/2"


def test_dcc_wide_table_transposed_to_pair_rows(tmp_path: Path) -> None:
    _seed_full_output_dir(tmp_path)

    dcc = _models_by_id(build_model_chain_results(tmp_path))["dcc_garch"]

    assert dcc["columns"] == ["资产对", "相关系数"]
    assert dcc["rows"] == [["hs300_gold", "0.339"], ["gold_copper", "0.4988"]]
    assert dcc["as_of"] == "2026-08-11"


def test_monitor_alerts_tail_window_keeps_latest_events(tmp_path: Path) -> None:
    _seed_full_output_dir(tmp_path)
    # 写入 9 行事件：tail 窗口（6 行）应只保留最新 6 行、行序不变。
    header = "datetime,event_type,symbol,detail,current_value,drawdown_pct\n"
    lines = [
        f"2026-08-{day:02d} 19:10:00,DAILY_CHECK,ALL,active_positions=0,0.0,0.0\n"
        for day in range(1, 9)
    ]
    lines.append("2026-08-12 06:57:11,VOL_ALERT,crude_oil,年化波动率>30%,0.0,0.0\n")
    _write_csv(tmp_path, "risk_log.csv", header + "".join(lines))

    alerts = _models_by_id(build_model_chain_results(tmp_path))["monitor_alerts"]

    assert alerts["columns"] == ["时间", "事件", "对象", "说明"]
    assert len(alerts["rows"]) == 6
    assert alerts["rows"][0][0] == "2026-08-04 19:10:00"
    assert alerts["rows"][-1][1] == "VOL_ALERT"
    assert alerts["headline"] == "告警 1 条 · VOL_ALERT 1"


def test_cta_columns_include_stop_loss_statistics(tmp_path: Path) -> None:
    _seed_full_output_dir(tmp_path)
    _write_csv(
        tmp_path,
        "cta_results.csv",
        "资产,合成信号,趋势强度,操作建议,策略年化收益%,策略夏普比率,止损次数,减仓天数\n"
        "沪深300,-0.604,强趋势,强空头,0.62,-0.095,8,0\n"
        "原油,0.648,强趋势,强多头,7.92,0.314,3,94\n",
    )

    cta = _models_by_id(build_model_chain_results(tmp_path))["cta_trend"]

    assert cta["columns"][-2:] == ["止损次数", "减仓天数"]
    assert cta["rows"][0][-2:] == ["8", "0"]
    assert cta["rows"][1][-2:] == ["3", "94"]


def test_headline_edge_cases_degrade_gracefully(tmp_path: Path) -> None:
    _seed_full_output_dir(tmp_path)
    # 数值列全部无法解析 → headline 退化为 详见明细。
    _write_csv(
        tmp_path,
        "garch_results.csv",
        "资产,最优模型,年化波动率%,波动率状态,操作建议\nhs300,GARCH,abc,高波动,x\n",
    )
    # 值缺失（NaN）在 headline 占位输出 "—"。
    _write_csv(
        tmp_path,
        "merrill_clock_latest.csv",
        "日期,增长动量,通胀动量,流动性动量,传统象限,bond_direction\n2026-06,0.1,0.2,0.3,,空\n",
    )
    # cooling_until 非空 → 冷却提示。
    _write_csv(
        tmp_path,
        "risk_state.csv",
        "date,peak_value,cooling_until,entry_prices\n2026-08-12,1000000.0,2026-09-01,{}\n",
    )
    # 最终信号多值分组计数。
    _write_csv(
        tmp_path,
        "final_signal.csv",
        "品种,日期,第一层_方向,最终信号,仓位比例,置信度,信号说明\n"
        "TS,2026-08-11,多,多,0.3,2,a\n"
        "TF,2026-08-11,空,空仓,0.0,1,b\n"
        "T,2026-08-11,多,多,0.3,2,c\n"
        "TL,2026-08-11,空,空仓,0.0,1,d\n",
    )

    models = _models_by_id(build_model_chain_results(tmp_path))

    assert models["garch"]["headline"] == "详见明细"
    assert models["merrill_clock"]["headline"] == "象限 — · 债券方向 空"
    assert models["risk_monitor"]["headline"] == "冷却至 2026-09-01"
    assert models["final_signal"]["headline"] == "多 2 · 空仓 2"


def test_missing_empty_and_unparsable_artifacts_do_not_raise(tmp_path: Path) -> None:
    # 目录仅含：一个表头无数据行的文件 + 一个完全空文件；其余全部缺失。
    _write_csv(tmp_path, "merrill_clock_latest.csv", "日期,增长动量\n")
    (tmp_path / "garch_results.csv").write_bytes(b"")

    result = build_model_chain_results(tmp_path)

    assert result["as_of_date"] is None
    models = _models_by_id(result)
    assert len(models) == 13
    for model in models.values():
        assert model["artifact_status"] == "missing"
        assert model["as_of"] is None
        assert model["headline"] == "产物缺失"
        assert model["columns"] == []
        assert model["rows"] == []


def _grant_macro_toolkit_read_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, grant: bool = True) -> None:
    sqlite_path = tmp_path / "macro-toolkit-read-scope.db"
    auth_dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", auth_dsn)
    monkeypatch.delenv("MOSS_GOVERNANCE_SQL_DSN", raising=False)
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    if grant:
        UserScopeRepository(auth_dsn).grant_scope(
            user_id="*",
            role=None,
            resource="macro_toolkit",
            action="read",
        )


@pytest.fixture
def macro_toolkit_client():
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    yield TestClient(app, raise_server_exceptions=False)
    get_settings.cache_clear()


def test_model_chain_results_endpoint_returns_contract_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    macro_toolkit_client: TestClient,
) -> None:
    _grant_macro_toolkit_read_scope(tmp_path, monkeypatch)
    output_dir = tmp_path / "output"
    _seed_full_output_dir(output_dir)
    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", output_dir)

    response = macro_toolkit_client.get(
        "/ui/macro/toolkit/model-chain-results", headers=MACRO_TOOLKIT_READ_HEADERS
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    meta = payload["result_meta"]
    assert meta["result_kind"] == "macro_toolkit.model_chain_results"
    assert meta["quality_flag"] == "ok"
    assert meta["fallback_mode"] == "none"
    assert meta["as_of_date"] == "2026-08-11"
    assert payload["result"] == build_model_chain_results(output_dir)


def test_model_chain_results_endpoint_flags_warning_when_artifact_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    macro_toolkit_client: TestClient,
) -> None:
    _grant_macro_toolkit_read_scope(tmp_path, monkeypatch)
    output_dir = tmp_path / "output"
    _seed_full_output_dir(output_dir)
    (output_dir / "garch_results.csv").unlink()
    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", output_dir)

    response = macro_toolkit_client.get(
        "/ui/macro/toolkit/model-chain-results", headers=MACRO_TOOLKIT_READ_HEADERS
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["quality_flag"] == "warning"
    garch = _models_by_id(payload["result"])["garch"]
    assert garch["artifact_status"] == "missing"
    assert garch["headline"] == "产物缺失"


def test_model_chain_results_endpoint_requires_read_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    macro_toolkit_client: TestClient,
) -> None:
    _grant_macro_toolkit_read_scope(tmp_path, monkeypatch, grant=False)

    response = macro_toolkit_client.get(
        "/ui/macro/toolkit/model-chain-results", headers=MACRO_TOOLKIT_READ_HEADERS
    )

    assert response.status_code == 403, response.text


def test_model_chain_results_endpoint_smoke_against_real_output_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    macro_toolkit_client: TestClient,
) -> None:
    if not REAL_OUTPUT_DIR.is_dir():
        pytest.skip("real macro toolkit output dir unavailable")
    _grant_macro_toolkit_read_scope(tmp_path, monkeypatch)
    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", REAL_OUTPUT_DIR)

    response = macro_toolkit_client.get(
        "/ui/macro/toolkit/model-chain-results", headers=MACRO_TOOLKIT_READ_HEADERS
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["quality_flag"] in {"ok", "warning"}
    result = payload["result"]
    assert [step["key"] for step in result["steps"]] == [key for key, _, _, _ in EXPECTED_STEPS]
    for step in result["steps"]:
        for model in step["models"]:
            assert model["artifact_status"] in {"ok", "missing"}
            assert isinstance(model["headline"], str) and model["headline"]


# ---------------------------------------------------------------------------
# 模型卡 trend 序列（可选历史折线）契约
# ---------------------------------------------------------------------------

TREND_MODEL_IDS = {"merrill_clock", "dcc_garch", "crisis_score", "final_signal"}


def _seed_trend_history_files(directory: Path) -> None:
    """按真实历史产物的实际表头（英文列名）铺设四个 trend 数据源。"""
    _write_csv(
        directory,
        "merrill_clock_history.csv",
        "date,growth_momentum,inflation_momentum,liquidity_momentum,regime\n"
        "2026-05-01,0.11,0.21,-0.31,复苏\n"
        "2026-06-01,0.12,0.22,-0.32,过热\n"
        "2026-07-01,0.13,0.23,-0.33,过热\n",
    )
    _write_csv(
        directory,
        "dcc_results.csv",
        "date,avg_corr,warning\n"
        "2026-08-08,0.27,正常\n"
        "2026-08-09,0.28,正常\n"
        "2026-08-10,abc,正常\n"
        "2026-08-11,0.31,正常\n",
    )
    _write_csv(
        directory,
        "crisis_score_history.csv",
        "date,crisis_score,equity_vol_z\n2026-08-10,-0.70,-0.70\n2026-08-11,-0.68,-0.68\n",
    )
    _write_csv(
        directory,
        "final_signal_history.csv",
        "日期,品种,最终信号,仓位比例,置信度\n"
        "2026-08-10,TS,多,0.275,3\n"
        "2026-08-10,TF,空仓,0.0,1\n"
        "2026-08-10,T,观望,0.0,0\n"
        "2026-08-10,TL,空,0.238,3\n"
        "2026-08-11,TS,空,0.238,3\n"
        "2026-08-11,TF,空仓,0.0,1\n"
        "2026-08-11,T,多,0.275,3\n"
        "2026-08-11,TL,空,0.238,3\n",
    )


def test_model_chain_trend_contract_structure(tmp_path: Path) -> None:
    _seed_full_output_dir(tmp_path)
    _seed_trend_history_files(tmp_path)

    models = _models_by_id(build_model_chain_results(tmp_path))

    # 全部 13 个模型对象恒有 trend 键；无历史数据源的模型恒为 None。
    for model_id, model in models.items():
        assert "trend" in model
        if model_id not in TREND_MODEL_IDS:
            assert model["trend"] is None

    merrill = models["merrill_clock"]["trend"]
    assert merrill["label"] == "三维动量（月度）"
    assert [series["name"] for series in merrill["series"]] == ["增长动量", "通胀动量", "流动性动量"]
    assert merrill["series"][0]["points"] == [
        ["2026-05-01", 0.11],
        ["2026-06-01", 0.12],
        ["2026-07-01", 0.13],
    ]
    assert merrill["series"][2]["points"][-1] == ["2026-07-01", -0.33]

    dcc = models["dcc_garch"]["trend"]
    assert dcc["label"] == "平均相关系数（日度）"
    assert [series["name"] for series in dcc["series"]] == ["平均相关系数"]
    # 数值无法解析的行（abc）跳过，日期文本保留 CSV 原值。
    assert dcc["series"][0]["points"] == [
        ["2026-08-08", 0.27],
        ["2026-08-09", 0.28],
        ["2026-08-11", 0.31],
    ]

    crisis = models["crisis_score"]["trend"]
    assert crisis["label"] == "危机评分（日度）"
    assert [series["name"] for series in crisis["series"]] == ["Crisis Score"]
    assert crisis["series"][0]["points"] == [["2026-08-10", -0.7], ["2026-08-11", -0.68]]

    final = models["final_signal"]["trend"]
    assert final["label"] == "信号轨迹（+1 多 / 0 观望 / -1 空）"
    assert [series["name"] for series in final["series"]] == ["TS", "TF", "T", "TL"]


def test_model_chain_final_signal_trend_signal_mapping(tmp_path: Path) -> None:
    _seed_full_output_dir(tmp_path)
    _write_csv(
        tmp_path,
        "final_signal_history.csv",
        "日期,品种,最终信号,仓位比例,置信度\n"
        "2026-08-08,TS,多,0.275,3\n"
        "2026-08-09,TS,空仓,0.0,1\n"
        "2026-08-10,TS,观望,0.0,0\n"
        "2026-08-11,TS,空,0.238,3\n"
        "2026-08-12,TS,未知信号,0.0,0\n"
        "2026-08-08,TF,多,0.275,3\n"
        "2026-08-09,TF,多,0.275,3\n"
        "2026-08-08,T,空,0.238,3\n",
    )

    trend = _models_by_id(build_model_chain_results(tmp_path))["final_signal"]["trend"]

    by_name = {series["name"]: series["points"] for series in trend["series"]}
    # 含"多"=+1；含"空仓"/"观望"=0；含"空"（非空仓）=-1；其他（未知信号）跳过。
    assert by_name["TS"] == [
        ["2026-08-08", 1.0],
        ["2026-08-09", 0.0],
        ["2026-08-10", 0.0],
        ["2026-08-11", -1.0],
    ]
    assert by_name["TF"] == [["2026-08-08", 1.0], ["2026-08-09", 1.0]]
    # T 仅 1 个有效点、TL 无行：有效点 <2 的线被剔除。
    assert set(by_name) == {"TS", "TF"}


def test_model_chain_trend_degrades_to_null_without_usable_history(tmp_path: Path) -> None:
    _seed_full_output_dir(tmp_path)

    # 历史文件全部缺失 → 四个 trend 模型均为 None，不抛错。
    models = _models_by_id(build_model_chain_results(tmp_path))
    for model_id in TREND_MODEL_IDS:
        assert models[model_id]["trend"] is None

    # 有效点 <2 / 数值全不可解析 / 文件为空损坏 → 同样退化为 None。
    _write_csv(tmp_path, "dcc_results.csv", "date,avg_corr\n2026-08-11,0.31\n")
    _write_csv(
        tmp_path,
        "crisis_score_history.csv",
        "date,crisis_score\n2026-08-10,abc\n2026-08-11,\n",
    )
    (tmp_path / "merrill_clock_history.csv").write_bytes(b"")

    models = _models_by_id(build_model_chain_results(tmp_path))
    assert models["dcc_garch"]["trend"] is None
    assert models["crisis_score"]["trend"] is None
    assert models["merrill_clock"]["trend"] is None


def test_model_chain_trend_caps_points_at_tail_120(tmp_path: Path) -> None:
    _seed_full_output_dir(tmp_path)
    start = date(2026, 1, 1)
    lines = [
        f"{(start + timedelta(days=offset)).isoformat()},{0.2 + offset * 0.001:.4f}\n"
        for offset in range(130)
    ]
    _write_csv(tmp_path, "dcc_results.csv", "date,avg_corr\n" + "".join(lines))

    trend = _models_by_id(build_model_chain_results(tmp_path))["dcc_garch"]["trend"]

    points = trend["series"][0]["points"]
    assert len(points) == 120
    # 130 个点仅保留尾部 120 个：前 10 个被裁剪。
    assert points[0] == [(start + timedelta(days=10)).isoformat(), pytest.approx(0.21)]
    assert points[-1] == [(start + timedelta(days=129)).isoformat(), pytest.approx(0.329)]


# ---------------------------------------------------------------------------
# 调度健康 scheduler payload 契约
# ---------------------------------------------------------------------------


def _write_daily_chain_receipt(logs_dir: Path) -> None:
    (logs_dir / "macro_toolkit_daily_chain_receipt.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_name": "macro_toolkit_daily_chain",
                "status": "degraded",
                "exit_code": 0,
                "generated_at": "2026-08-12T01:04:59+00:00",
                "run_kind": "scheduled",
                "invocation_mode": "run_once",
                "result": {
                    "chain": {"status": "degraded"},
                    "extra_scripts": [
                        {"script": f"script_{index}", "status": "completed"} for index in range(6)
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_freshness_receipt(logs_dir: Path) -> None:
    (logs_dir / "macro_toolkit_freshness_refresh_receipt.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_name": "refresh_macro_toolkit_freshness",
                "status": "failed",
                "exit_code": 1,
                "generated_at": "2026-08-11T11:40:48+00:00",
                "run_kind": "scheduled",
                "result": {
                    "steps": [
                        {"step": "a", "status": "success"},
                        {"step": "b", "status": "success"},
                        {"step": "c", "status": "failed"},
                        {"step": "d", "status": "failed"},
                        {"step": "e", "status": "degraded"},
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_model_chain_scheduler_summarizes_both_receipts(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    _seed_full_output_dir(output_dir)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    _write_daily_chain_receipt(logs_dir)
    _write_freshness_receipt(logs_dir)

    scheduler = build_model_chain_results(output_dir, logs_dir=logs_dir)["scheduler"]

    assert scheduler["daily_chain"] == {
        "task_name": "macro_toolkit_daily_chain",
        "status": "degraded",
        "exit_code": 0,
        "generated_at": "2026-08-12T01:04:59+00:00",
        "run_kind": "scheduled",
        "summary": "链 degraded · 链外脚本 6/6 完成",
    }
    assert scheduler["freshness"] == {
        "task_name": "refresh_macro_toolkit_freshness",
        "status": "failed",
        "exit_code": 1,
        "generated_at": "2026-08-11T11:40:48+00:00",
        "run_kind": "scheduled",
        "summary": "步骤 2 成功 / 2 失败 / 1 降级",
    }


def test_model_chain_scheduler_degrades_to_null_when_receipts_unreadable(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    _seed_full_output_dir(output_dir)

    # logs 目录不存在 → 两个键均为 None；顶层 scheduler 恒存在。
    result = build_model_chain_results(output_dir, logs_dir=tmp_path / "missing-logs")
    assert result["scheduler"] == {"daily_chain": None, "freshness": None}

    # 回执损坏（非法 JSON / 非对象 JSON）→ 对应键为 None，不抛错。
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "macro_toolkit_daily_chain_receipt.json").write_text("{not json", encoding="utf-8")
    (logs_dir / "macro_toolkit_freshness_refresh_receipt.json").write_text("[1,2]", encoding="utf-8")
    result = build_model_chain_results(output_dir, logs_dir=logs_dir)
    assert result["scheduler"] == {"daily_chain": None, "freshness": None}


def test_model_chain_scheduler_default_logs_dir_derived_from_output_dir(tmp_path: Path) -> None:
    """默认 logs_dir 从 output_dir 推导：data/macro_toolkit/output → data/logs。"""
    output_dir = tmp_path / "data" / "macro_toolkit" / "output"
    _seed_full_output_dir(output_dir)
    logs_dir = tmp_path / "data" / "logs"
    logs_dir.mkdir(parents=True)
    _write_daily_chain_receipt(logs_dir)

    scheduler = build_model_chain_results(output_dir)["scheduler"]

    assert scheduler["daily_chain"]["task_name"] == "macro_toolkit_daily_chain"
    assert scheduler["daily_chain"]["summary"] == "链 degraded · 链外脚本 6/6 完成"
    assert scheduler["freshness"] is None
