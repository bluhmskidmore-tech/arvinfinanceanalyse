"""宏观工具箱决策链结果只读端点（/ui/macro/toolkit/model-chain-results）契约测试。

覆盖 build_model_chain_results 纯函数的七步结构、模型字段、DCC 宽表转置、
headline 规则（含 NaN / 缺文件退化），以及 FastAPI 端点的 envelope 结构与
真实产物目录冒烟。
"""

from __future__ import annotations

import re
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
    ("risk_management", 4, "风险管理", ["crisis_score", "risk_monitor"]),
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
    assert len(models) == 12
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
