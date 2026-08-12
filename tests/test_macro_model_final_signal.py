"""宏观工具箱链条终点回归测试：signal_aggregator 三层过滤 + risk_monitor 风控状态机。

覆盖本次修复：
1. signal_aggregator 置信度语义 = 实证通过层数（拦截提前返回时写入已通过层数；
   输入缺失降级通过的层不计入置信度）。
2. risk_monitor 止损事件日志不再向 _log_event 传未定义的 pnl_pct 参数（原为 TypeError）。
3. risk_monitor.record_exit 空头出场盈亏符号修正。
4. risk_monitor 事中动态监测接线（观点23/24 与 Step4）：build_monitor_alerts 纯函数
   （波动率>30% / DCC 平均相关>0.70/0.85 / Crisis Score≥1/2/3 分级告警、缺产物降级
   MONITOR_GAP）与 run_intraday_monitor 写 risk_log 行为。

观察口径（observation-only）脚本测试，全部使用内存构造的小 fixture 与 tmp_path，
不读取 data/ 真实产物，不触碰 DuckDB。
"""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "backend" / "app" / "core_finance" / "macro" / "toolkit" / "scripts"


def _load_script_module(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def aggregator():
    return _load_script_module("signal_aggregator.py", "macro_signal_aggregator_under_test")


@pytest.fixture(scope="module")
def risk_monitor_mod():
    return _load_script_module("risk_monitor.py", "macro_risk_monitor_under_test")


# ============================================================
# signal_aggregator fixtures
# ============================================================

SIGNAL_DATE = "2026-08-11"


def _merrill(direction: str, note: str = "测试宏观说明") -> dict:
    return {
        "日期": SIGNAL_DATE,
        "bond_direction": direction,
        "bond_note": note,
        "growth": 0.18,
        "inflation": 0.84,
        "liquidity": -0.62,
        "regime": "过热",
        "bond_score": -0.494,
    }


def _basis_df(long_ok: bool, short_ok: bool, note: str = "净基差测试说明") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "品种": "T",
                "日期": SIGNAL_DATE,
                "安全边际_多": long_ok,
                "安全边际_空": short_ok,
                "安全边际说明": note,
            }
        ]
    )


def _crowding_df(signal: str, c_pct: float = 0.5, note: str = "拥挤度测试说明") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "品种": "T",
                "日期": SIGNAL_DATE,
                "拥挤度信号": signal,
                "C分位数": c_pct,
                "说明": note,
            }
        ]
    )


CRISIS_CALM = {"日期": SIGNAL_DATE, "score": -0.05, "status": "宽松"}


# ============================================================
# 第一层：宏观方向门
# ============================================================


def test_layer1_wait_direction_blocks_everything(aggregator):
    result = aggregator.run_three_layer_filter(
        "T",
        _merrill("观望", note="宏观信号不明确(g=+0.18,i=+0.84,l=-0.62)"),
        _basis_df(long_ok=True, short_ok=False),
        _crowding_df("中性"),
        CRISIS_CALM,
        signal_date=SIGNAL_DATE,
    )
    assert result["第一层_通过"] is False
    assert result["最终信号"] == "空仓"
    assert result["仓位比例"] == 0.0
    assert result["置信度"] == 0
    assert result["信号说明"].startswith("第一层拦截")
    assert "宏观信号不明确" in result["信号说明"]


# ============================================================
# 第二层：安全边际门（拦截时置信度应计入已通过的第一层）
# ============================================================


def test_layer2_block_keeps_layer1_confidence(aggregator):
    result = aggregator.run_three_layer_filter(
        "T",
        _merrill("多"),
        _basis_df(long_ok=False, short_ok=False, note="净基差中性(50%)，安全边际不足，等待"),
        _crowding_df("中性"),
        CRISIS_CALM,
        signal_date=SIGNAL_DATE,
    )
    assert result["第一层_通过"] is True
    assert result["第二层_通过"] is False
    assert result["最终信号"] == "空仓"
    assert result["置信度"] == 1
    assert result["信号说明"].startswith("第二层拦截")
    assert "安全边际不足" in result["信号说明"]


def test_layer2_checks_direction_specific_margin(aggregator):
    """方向为空时应检查 安全边际_空 而非 安全边际_多。"""
    result = aggregator.run_three_layer_filter(
        "T",
        _merrill("空"),
        _basis_df(long_ok=True, short_ok=False),
        _crowding_df("中性"),
        CRISIS_CALM,
        signal_date=SIGNAL_DATE,
    )
    assert result["第二层_通过"] is False
    assert result["信号说明"].startswith("第二层拦截")


# ============================================================
# 第三层：拥挤度反向过滤（拦截时置信度应计入已通过的两层）
# ============================================================


def test_layer3_block_counts_two_verified_layers(aggregator):
    result = aggregator.run_three_layer_filter(
        "T",
        _merrill("多"),
        _basis_df(long_ok=True, short_ok=False),
        _crowding_df("警惕多头", c_pct=0.97),
        CRISIS_CALM,
        signal_date=SIGNAL_DATE,
    )
    assert result["第一层_通过"] is True
    assert result["第二层_通过"] is True
    assert result["第三层_通过"] is False
    assert result["最终信号"] == "空仓"
    assert result["置信度"] == 2
    assert result["信号说明"].startswith("第三层拦截")
    assert "多头拥挤" in result["信号说明"]


def test_layer3_short_direction_blocked_by_short_crowding(aggregator):
    result = aggregator.run_three_layer_filter(
        "T",
        _merrill("空"),
        _basis_df(long_ok=False, short_ok=True),
        _crowding_df("做多", c_pct=0.02),
        CRISIS_CALM,
        signal_date=SIGNAL_DATE,
    )
    assert result["第三层_通过"] is False
    assert result["置信度"] == 2
    assert "空头拥挤" in result["信号说明"]


# ============================================================
# 全部通过：凯利仓位 + Crisis 缩放 + 置信度
# ============================================================


def test_all_layers_pass_half_kelly_position(aggregator):
    result = aggregator.run_three_layer_filter(
        "T",
        _merrill("多"),
        _basis_df(long_ok=True, short_ok=False),
        _crowding_df("中性"),
        CRISIS_CALM,
        signal_date=SIGNAL_DATE,
    )
    assert result["最终信号"] == "多"
    assert result["置信度"] == 3
    # T 品种：胜率 0.70、盈亏比 2.0，半凯利 = ((2*0.7-0.3)/2)*0.5 = 0.275
    expected = aggregator.kelly_position(0.70, 2.0, half_kelly=True)
    assert expected == pytest.approx(0.275, abs=1e-9)
    assert result["仓位比例"] == pytest.approx(expected, abs=1e-9)
    assert result["日期"] == SIGNAL_DATE


def test_crisis_score_scales_position_down(aggregator):
    crisis_high = {"日期": SIGNAL_DATE, "score": 2.5, "status": "危机"}
    result = aggregator.run_three_layer_filter(
        "T",
        _merrill("多"),
        _basis_df(long_ok=True, short_ok=False),
        _crowding_df("中性"),
        crisis_high,
        signal_date=SIGNAL_DATE,
    )
    base = aggregator.kelly_position(0.70, 2.0, half_kelly=True)
    assert result["仓位比例"] == pytest.approx(round(base * 0.5, 3), abs=1e-9)
    assert "危机评分" in result["信号说明"]


def test_degraded_inputs_pass_but_lower_confidence(aggregator):
    """第二/三层输入缺失时降级放行，但置信度只计实证通过的第一层。"""
    result = aggregator.run_three_layer_filter(
        "T",
        _merrill("多"),
        pd.DataFrame(),
        pd.DataFrame(),
        CRISIS_CALM,
        signal_date=SIGNAL_DATE,
    )
    assert result["第二层_通过"] is True
    assert result["第三层_通过"] is True
    assert result["最终信号"] == "多"
    assert result["置信度"] == 1
    assert "降级" in result["信号说明"]


# ============================================================
# risk_monitor：状态机与事件日志
# ============================================================


@pytest.fixture()
def isolated_monitor(risk_monitor_mod, tmp_path, monkeypatch):
    monkeypatch.setattr(risk_monitor_mod, "STATE_FILE", tmp_path / "risk_state.csv")
    monkeypatch.setattr(risk_monitor_mod, "LOG_FILE", tmp_path / "risk_log.csv")
    return risk_monitor_mod.RiskMonitor(initial_capital=1_000_000.0)


def _read_log(risk_monitor_mod) -> pd.DataFrame:
    return pd.read_csv(risk_monitor_mod.LOG_FILE, encoding="utf-8-sig")


def test_stop_loss_logs_event_without_typeerror(risk_monitor_mod, isolated_monitor):
    """修复回归：止损触发时 _log_event 不应因未定义的 pnl_pct 参数抛 TypeError。"""
    monitor = isolated_monitor
    monitor.record_entry("T", 100.0)

    check = monitor.check_position("T", "多", 100.0, 98.0)

    assert check["action"] == "stop_loss"
    assert check["pnl_pct"] == pytest.approx(-0.02, abs=1e-9)
    assert "T" not in monitor.state["entry_prices"]

    log = _read_log(risk_monitor_mod)
    stop_rows = log[log["event_type"] == "STOP_LOSS"]
    assert len(stop_rows) == 1
    assert stop_rows.iloc[0]["symbol"] == "T"
    # 亏损比例记入 drawdown_pct 列（百分数）
    assert stop_rows.iloc[0]["drawdown_pct"] == pytest.approx(-2.0, abs=1e-6)


def test_short_position_stop_loss_uses_inverted_pnl(isolated_monitor):
    """空头持仓价格上涨 2% 应触发止损。"""
    monitor = isolated_monitor
    monitor.record_entry("TL", 100.0)

    check = monitor.check_position("TL", "空", 100.0, 102.0)

    assert check["action"] == "stop_loss"
    assert check["pnl_pct"] == pytest.approx(-0.02, abs=1e-9)


def test_position_within_stop_loss_holds(isolated_monitor):
    monitor = isolated_monitor
    check = monitor.check_position("T", "多", 100.0, 99.0)
    assert check["action"] == "hold"
    assert check["pnl_pct"] == pytest.approx(-0.01, abs=1e-9)


def test_record_exit_short_direction_pnl_sign(risk_monitor_mod, isolated_monitor):
    """修复回归：空头出场盈亏符号取反（价格下跌应为盈利）。"""
    monitor = isolated_monitor
    monitor.record_entry("T", 100.0)
    monitor.record_exit("T", 98.0, direction="空")

    log = _read_log(risk_monitor_mod)
    exit_rows = log[log["event_type"] == "EXIT"]
    assert len(exit_rows) == 1
    assert "+2.00%" in str(exit_rows.iloc[0]["detail"])
    assert "T" not in monitor.state["entry_prices"]


def test_max_drawdown_forces_close_all_and_sets_cooling(risk_monitor_mod, isolated_monitor):
    """最大回撤 3% 硬约束：强制全平 + 冷静期 + FORCE_CLOSE_ALL 日志。"""
    monitor = isolated_monitor

    check = monitor.check_portfolio(960_000.0)  # 相对峰值 100 万回撤 4%

    assert check["action"] == "force_close_all"
    assert check["drawdown"] == pytest.approx(0.04, abs=1e-9)
    assert monitor.in_cooling_period() is True

    log = _read_log(risk_monitor_mod)
    force_rows = log[log["event_type"] == "FORCE_CLOSE_ALL"]
    assert len(force_rows) == 1
    assert force_rows.iloc[0]["drawdown_pct"] == pytest.approx(4.0, abs=1e-6)


def test_peak_value_ratchets_up_and_normal_hold(isolated_monitor):
    monitor = isolated_monitor

    first = monitor.check_portfolio(1_050_000.0)
    assert first["action"] == "hold"
    assert monitor.state["peak_value"] == pytest.approx(1_050_000.0)

    second = monitor.check_portfolio(1_029_000.0)  # 相对新峰值回撤 2%
    assert second["action"] == "hold"
    assert second["drawdown"] == pytest.approx(0.02, abs=1e-9)
    assert monitor.in_cooling_period() is False


def test_daily_check_blocks_new_positions_during_cooling(isolated_monitor):
    monitor = isolated_monitor
    monitor.set_cooling_period(days=3)

    outcome = monitor.daily_check(
        current_prices={"T": 109.0},
        positions={"T": {"direction": "多", "size": 0.25}},
        current_value=1_000_000.0,
    )

    assert outcome["status"] == "cooling"
    assert outcome["actions"] == []


# ============================================================
# risk_monitor：事中动态监测（观点23/24 与 Step4 接线）
# ============================================================

RISK_LOG_COLUMNS = ["datetime", "event_type", "symbol", "detail", "current_value", "drawdown_pct"]


def _garch_frame(rows) -> pd.DataFrame:
    """rows: [(资产, 年化波动率%), ...]"""
    return pd.DataFrame(
        [{"资产": asset, "年化波动率%": vol, "波动率状态": "测试"} for asset, vol in rows]
    )


def _dcc_frame(avg_corr) -> pd.DataFrame:
    return pd.DataFrame([{"日期": SIGNAL_DATE, "平均相关系数": avg_corr, "预警状态": "测试"}])


def _crisis_frame(score) -> pd.DataFrame:
    return pd.DataFrame([{"日期": SIGNAL_DATE, "Crisis Score": score, "市场状态": "测试"}])


def _normal_inputs():
    """三维度全部低于阈值的正常输入。"""
    return (
        _garch_frame([("hs300", 15.38), ("crude_oil", 29.99)]),
        _dcc_frame(0.2764),
        _crisis_frame(-0.068),
    )


def test_monitor_normal_inputs_produce_no_alerts(risk_monitor_mod):
    garch, dcc, crisis = _normal_inputs()
    assert risk_monitor_mod.build_monitor_alerts(garch, dcc, crisis) == []


def test_monitor_vol_boundary_30_pct(risk_monitor_mod):
    """波动率阈值为严格大于 30：恰好 30.0 不告警，超过则告警且清单只含超标资产。"""
    garch = _garch_frame(
        [("hs300", 30.0), ("crude_oil", 63.49), ("csi500", 30.01), ("copper", 11.65)]
    )
    alerts = risk_monitor_mod.build_monitor_alerts(garch, _dcc_frame(0.30), _crisis_frame(0.0))

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["event_type"] == "VOL_ALERT"
    assert alert["level"] == "warning"
    assert "crude_oil" in alert["symbol"]
    assert "csi500" in alert["symbol"]
    assert "hs300" not in alert["symbol"]
    assert "copper" not in alert["symbol"]
    assert "63.49" in alert["detail"]
    assert "降仓防御" in alert["detail"]
    assert "尾部对冲" in alert["detail"]


def test_monitor_corr_boundaries(risk_monitor_mod):
    """相关性阈值严格大于：0.70 不告警；(0.70, 0.85] warning；>0.85 critical。"""
    garch, _, crisis = _normal_inputs()

    assert risk_monitor_mod.build_monitor_alerts(garch, _dcc_frame(0.70), crisis) == []

    warn = risk_monitor_mod.build_monitor_alerts(garch, _dcc_frame(0.71), crisis)
    assert len(warn) == 1
    assert warn[0]["event_type"] == "CORR_ALERT"
    assert warn[0]["level"] == "warning"
    assert "警惕相关性跃升" in warn[0]["detail"]

    edge = risk_monitor_mod.build_monitor_alerts(garch, _dcc_frame(0.85), crisis)
    assert edge[0]["level"] == "warning"

    crit = risk_monitor_mod.build_monitor_alerts(garch, _dcc_frame(0.86), crisis)
    assert len(crit) == 1
    assert crit[0]["event_type"] == "CORR_ALERT"
    assert crit[0]["level"] == "critical"
    assert "分散化失效" in crit[0]["detail"]
    assert "降仓或对冲" in crit[0]["detail"]


def test_monitor_corr_uses_last_row(risk_monitor_mod):
    """dcc_latest 多行时取最末行。"""
    garch, _, crisis = _normal_inputs()
    dcc = pd.concat([_dcc_frame(0.90), _dcc_frame(0.30)], ignore_index=True)
    assert risk_monitor_mod.build_monitor_alerts(garch, dcc, crisis) == []


def test_monitor_crisis_boundaries(risk_monitor_mod):
    """Crisis Score 分级：<1 无告警；≥1 警惕；≥2 高风险；≥3 危机应急。"""
    garch, dcc, _ = _normal_inputs()

    assert risk_monitor_mod.build_monitor_alerts(garch, dcc, _crisis_frame(0.99)) == []

    watch = risk_monitor_mod.build_monitor_alerts(garch, dcc, _crisis_frame(1.0))
    assert len(watch) == 1
    assert watch[0]["event_type"] == "CRISIS_ALERT"
    assert watch[0]["level"] == "warning"
    assert "警惕状态" in watch[0]["detail"]

    high = risk_monitor_mod.build_monitor_alerts(garch, dcc, _crisis_frame(2.0))
    assert high[0]["level"] == "critical"
    assert "高风险，降低整体暴露" in high[0]["detail"]

    emergency = risk_monitor_mod.build_monitor_alerts(garch, dcc, _crisis_frame(3.0))
    assert emergency[0]["level"] == "critical"
    assert "危机状态，启动应急预案" in emergency[0]["detail"]


def test_monitor_missing_inputs_degrade_to_gap_records(risk_monitor_mod):
    """None/空/缺列 → 各维度一条 MONITOR_GAP(info)，注明缺失产物，不抛异常。"""
    crisis_missing_col = pd.DataFrame([{"日期": SIGNAL_DATE, "市场状态": "宽松"}])

    alerts = risk_monitor_mod.build_monitor_alerts(None, pd.DataFrame(), crisis_missing_col)

    assert len(alerts) == 3
    assert all(a["event_type"] == "MONITOR_GAP" for a in alerts)
    assert all(a["level"] == "info" for a in alerts)
    details = "|".join(a["detail"] for a in alerts)
    assert "garch_results.csv" in details
    assert "dcc_latest.csv" in details
    assert "crisis_score_latest.csv" in details


def test_monitor_nan_values_degrade_to_gap(risk_monitor_mod):
    """最末行数值为 NaN 时该维度降级 MONITOR_GAP，不抛异常。"""
    garch, _, _ = _normal_inputs()
    alerts = risk_monitor_mod.build_monitor_alerts(
        garch, _dcc_frame(float("nan")), _crisis_frame(float("nan"))
    )
    assert [a["event_type"] for a in alerts] == ["MONITOR_GAP", "MONITOR_GAP"]


def _write_monitor_outputs(outdir: Path, garch=None, dcc=None, crisis=None):
    outdir.mkdir(parents=True, exist_ok=True)
    if garch is not None:
        garch.to_csv(outdir / "garch_results.csv", index=False, encoding="utf-8-sig")
    if dcc is not None:
        dcc.to_csv(outdir / "dcc_latest.csv", index=False, encoding="utf-8-sig")
    if crisis is not None:
        crisis.to_csv(outdir / "crisis_score_latest.csv", index=False, encoding="utf-8-sig")


def test_intraday_monitor_writes_alerts_to_risk_log(risk_monitor_mod, isolated_monitor, tmp_path):
    """告警逐条写入 risk_log.csv，沿用既有 6 列 schema，级别记入 detail。"""
    outdir = tmp_path / "out"
    _write_monitor_outputs(
        outdir,
        garch=_garch_frame([("crude_oil", 63.49)]),
        dcc=_dcc_frame(0.90),
        crisis=_crisis_frame(3.2),
    )

    alerts = risk_monitor_mod.run_intraday_monitor(isolated_monitor, output_dir=outdir)

    assert [a["event_type"] for a in alerts] == ["VOL_ALERT", "CORR_ALERT", "CRISIS_ALERT"]

    log = _read_log(risk_monitor_mod)
    assert list(log.columns) == RISK_LOG_COLUMNS
    assert log["event_type"].tolist() == ["VOL_ALERT", "CORR_ALERT", "CRISIS_ALERT"]

    vol_row = log.iloc[0]
    assert vol_row["symbol"] == "crude_oil"
    assert "level=warning" in vol_row["detail"]
    assert vol_row["current_value"] == pytest.approx(0.0)
    assert vol_row["drawdown_pct"] == pytest.approx(0.0)

    corr_row = log.iloc[1]
    assert corr_row["symbol"] == "ALL"
    assert "level=critical" in corr_row["detail"]
    assert "分散化失效" in corr_row["detail"]

    crisis_row = log.iloc[2]
    assert "level=critical" in crisis_row["detail"]
    assert "启动应急预案" in crisis_row["detail"]


def test_intraday_monitor_missing_products_log_gap_rows(
    risk_monitor_mod, isolated_monitor, tmp_path
):
    """产物文件缺失时写 MONITOR_GAP 行而不是抛异常。"""
    outdir = tmp_path / "out"
    _write_monitor_outputs(outdir, garch=_garch_frame([("hs300", 10.0)]))  # 只有 garch

    alerts = risk_monitor_mod.run_intraday_monitor(isolated_monitor, output_dir=outdir)

    assert [a["event_type"] for a in alerts] == ["MONITOR_GAP", "MONITOR_GAP"]
    log = _read_log(risk_monitor_mod)
    assert log["event_type"].tolist() == ["MONITOR_GAP", "MONITOR_GAP"]
    assert all("level=info" in d for d in log["detail"])


def test_intraday_monitor_normal_prints_but_writes_no_log(
    risk_monitor_mod, isolated_monitor, tmp_path, capsys
):
    """无告警：stdout 打印"监测正常"，不写任何日志行（避免日志膨胀）。"""
    outdir = tmp_path / "out"
    garch, dcc, crisis = _normal_inputs()
    _write_monitor_outputs(outdir, garch=garch, dcc=dcc, crisis=crisis)

    alerts = risk_monitor_mod.run_intraday_monitor(isolated_monitor, output_dir=outdir)

    assert alerts == []
    assert "监测正常" in capsys.readouterr().out
    assert not risk_monitor_mod.LOG_FILE.exists()
