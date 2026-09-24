"""债券及宏观日报（generate_bond_macro_report）段落构建函数的口径测试。

覆盖：三层拦截最终信号段（合成 CSV 数据）、GARCH 绝对阈值三档新口径文案、
CTA 止损统计口径、导航仪告警段构建与无告警退化。
"""

from __future__ import annotations

import pandas as pd

from backend.app.core_finance.macro.toolkit.scripts import (
    generate_bond_macro_report as report,
)


def _final_signal_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "品种": "TS",
                "日期": "2026-08-11",
                "第一层_方向": "空",
                "第一层_通过": True,
                "第二层_通过": True,
                "第三层_通过": True,
                "最终信号": "空",
                "仓位比例": 0.238,
                "置信度": 3,
                "信号说明": "宏观空(过热) | 安全边际OK | 拥挤度OK",
            },
            {
                "品种": "T",
                "日期": "2026-08-11",
                "第一层_方向": "空",
                "第一层_通过": True,
                "第二层_通过": False,
                "第三层_通过": False,
                "最终信号": "空仓",
                "仓位比例": 0.0,
                "置信度": 1,
                "信号说明": "第二层拦截：净基差中性(2%)，安全边际不足，等待",
            },
            {
                "品种": "TL",
                "日期": "2026-08-11",
                "第一层_方向": "空",
                "第一层_通过": True,
                "第二层_通过": True,
                "第三层_通过": False,
                "最终信号": "空仓",
                "仓位比例": 0.0,
                "置信度": 2,
                "信号说明": "第三层拦截：空头拥挤(3%)，反向过滤",
            },
        ]
    )


def _bond_signals_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "品种": "TS",
                "信号方向": "空",
                "信号强度": "中",
                "双均线": "空",
                "唐奇安": "多",
                "MACD": "空",
                "布林带": "多",
                "说明": "2多/2空，中势空",
            },
            {
                "品种": "T",
                "信号方向": "多",
                "信号强度": "强",
                "双均线": "多",
                "唐奇安": "多",
                "MACD": "多",
                "布林带": "空",
                "说明": "3多/1空，强势多",
            },
        ]
    )


def _crowding_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"品种": "TS", "C分位数": 0.446, "拥挤度信号": "中性"},
            {"品种": "T", "C分位数": 0.016, "拥挤度信号": "做多"},
        ]
    )


def _garch_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "资产": "copper",
                "波动率状态": "低波动",
                "年化波动率%": 11.65,
                "操作建议": "适合卖权/均值回归策略",
                "约束校验": "通过",
                "样本外相关性": 0.763,
            },
            {
                "资产": "hs300",
                "波动率状态": "中波动",
                "年化波动率%": 15.38,
                "操作建议": "适合趋势跟踪/风险平价策略",
                "约束校验": "通过",
                "样本外相关性": 0.714,
            },
            {
                "资产": "crude_oil",
                "波动率状态": "高波动",
                "年化波动率%": 63.49,
                "操作建议": "适合CTA/尾部对冲，降仓防御",
                "约束校验": "通过",
                "样本外相关性": 0.712,
            },
        ]
    )


def test_final_signal_table_renders_gates_position_and_confidence() -> None:
    table = report._make_final_signal_table(_final_signal_frame())

    assert list(table["品种"]) == ["TS", "T", "TL"]
    ts_row = table.iloc[0]
    assert ts_row["第一层宏观方向门"] == "空｜通过"
    assert ts_row["最终信号"] == "空"
    assert ts_row["仓位比例"] == "23.8%"
    assert ts_row["置信度"] == "3/3"
    t_row = table.iloc[1]
    assert t_row["第二层安全边际门"] == "未通过"
    assert t_row["最终信号"] == "空仓"
    tl_row = table.iloc[2]
    assert tl_row["第二层安全边际门"] == "通过"
    assert tl_row["第三层拥挤度门"] == "未通过"


def test_final_signal_table_treats_text_booleans_like_csv_roundtrip() -> None:
    frame = _final_signal_frame().astype(
        {"第一层_通过": str, "第二层_通过": str, "第三层_通过": str}
    )

    table = report._make_final_signal_table(frame)

    assert table.iloc[0]["第二层安全边际门"] == "通过"
    assert table.iloc[1]["第二层安全边际门"] == "未通过"


def test_final_signal_takeaways_cover_gates_tech_contrast_and_crowding() -> None:
    lines = report._final_signal_takeaways(
        _final_signal_frame(),
        _bond_signals_frame(),
        _crowding_frame(),
    )
    text = "\n".join(lines)

    assert "TS 空（仓位 23.8%，置信度 3/3）" in lines[0]
    assert "T、TL 被拦截空仓" in lines[0]
    assert "第二层拦截：净基差中性(2%)，安全边际不足，等待" in text
    assert "第三层拦截：空头拥挤(3%)，反向过滤" in text
    assert "第一层为宏观方向门" in text
    assert "第二层为净基差安全边际" in text
    assert "第三层为拥挤度反向过滤" in text
    assert "技术面不参与三层门控，仅作对照参考" in text
    assert "拥挤度证据（第三层门依据）：TS 中性（分位 45%）、T 做多（分位 2%）" in text
    # T 最终空仓（被拦截），不算方向分歧；本组合成数据中无开仓方向分歧品种
    assert "方向不一致" not in text


def test_final_signal_takeaways_flag_direction_divergence_for_open_positions() -> None:
    final_frame = _final_signal_frame()
    signals = _bond_signals_frame()
    signals.loc[signals["品种"] == "TS", "信号方向"] = "多"

    text = "\n".join(report._final_signal_takeaways(final_frame, signals, None))

    assert "技术面与最终信号方向不一致的品种：TS" in text
    assert "以最终信号为链条结论" in text


def test_final_signal_takeaways_degrade_without_optional_inputs() -> None:
    lines = report._final_signal_takeaways(_final_signal_frame(), None, None)
    text = "\n".join(lines)

    assert "三层拦截最终信号（2026-08-11）" in lines[0]
    assert "四因子技术面对照" not in text
    assert "拥挤度证据" not in text


def test_final_signal_headline_reports_missing_artifact() -> None:
    assert "暂未生成" in report._final_signal_headline(None)
    assert "暂未生成" in report._final_signal_headline(pd.DataFrame())
    assert report._final_signal_takeaways(None) == [report._final_signal_headline(None)]


def test_tech_crowding_table_merges_by_symbol() -> None:
    table = report._make_tech_crowding_table(_bond_signals_frame(), _crowding_frame())

    assert list(table["品种"]) == ["TS", "T"]
    assert table.iloc[0]["技术面方向"] == "空"
    assert table.iloc[0]["拥挤度分位"] == "45%"
    assert table.iloc[1]["拥挤度信号"] == "做多"
    assert len(report._make_tech_crowding_table(None, None)) == 0


def test_garch_takeaways_use_absolute_threshold_three_regimes() -> None:
    lines = report._garch_takeaways(_garch_frame())
    text = "\n".join(lines)

    assert "低波动（<15%）、中波动（15%-30%）、高波动（>30%）" in text
    assert "高波动资产：原油（年化 63.49%，适合CTA/尾部对冲，降仓防御）" in text
    assert "中波动资产：沪深300（年化 15.38%" in text
    assert "低波动资产：铜（年化 11.65%，适合卖权/均值回归策略）" in text
    assert "全部资产通过笔记约束" in text
    assert "样本外波动率预测相关性介于 0.712 至 0.763" in text
    assert "极端波动" not in text
    assert "亮红灯" not in text


def test_garch_takeaways_surface_constraint_failures() -> None:
    frame = _garch_frame()
    frame.loc[frame["资产"] == "crude_oil", "约束校验"] = "不满足: 持久性>=1"

    text = "\n".join(report._garch_takeaways(frame))

    assert "原油（不满足: 持久性>=1）" in text
    assert "全部资产通过笔记约束" not in text


def test_cta_takeaway_lines_report_stop_loss_statistics() -> None:
    cta = pd.DataFrame(
        [
            {
                "资产": "黄金",
                "合成信号": -0.1,
                "操作建议": "震荡观望",
                "策略夏普比率": 1.778,
                "止损次数": 1,
                "减仓天数": 36,
            },
            {
                "资产": "铜",
                "合成信号": 0.762,
                "操作建议": "强多头",
                "策略夏普比率": -0.114,
                "止损次数": 7,
                "减仓天数": 11,
            },
        ]
    )

    lines = report._cta_takeaway_lines(cta)
    text = "\n".join(lines)

    assert "趋势最强资产为'铜'" in lines[0]
    assert "回测三列（策略年化收益%、策略夏普比率、买持年化收益%）为含止损口径" in text
    assert "累计触发止损 8 次、波动减仓 47 天" in text
    assert "黄金 1次/36天、铜 7次/11天" in text


def _risk_log_frame(rows: list[tuple[str, str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "datetime": ts,
                "event_type": event,
                "symbol": symbol,
                "detail": detail,
                "current_value": 0.0,
                "drawdown_pct": 0.0,
            }
            for ts, event, symbol, detail in rows
        ]
    )


def test_risk_alert_takeaways_present_tail_alerts() -> None:
    frame = _risk_log_frame(
        [
            ("2026-08-11 23:33:18", "DAILY_CHECK", "ALL", "active_positions=0"),
            (
                "2026-08-12 06:57:11",
                "VOL_ALERT",
                "crude_oil",
                "年化波动率>30%: crude_oil=63.49%",
            ),
            ("2026-08-12 09:04:09", "DAILY_CHECK", "ALL", "active_positions=2"),
        ]
    )

    lines = report._risk_alert_takeaways(frame)

    assert "1 条告警" in lines[0]
    assert (
        lines[1]
        == "2026-08-12 06:57:11｜VOL_ALERT｜crude_oil｜年化波动率>30%: crude_oil=63.49%"
    )


def test_risk_alert_takeaways_only_scan_tail_rows() -> None:
    old_alert = [("2026-08-01 08:00:00", "VOL_ALERT", "gold", "旧告警，超出尾部窗口")]
    recent_checks = [
        (f"2026-08-12 0{i}:00:00", "DAILY_CHECK", "ALL", "active_positions=0")
        for i in range(10)
    ]

    lines = report._risk_alert_takeaways(
        _risk_log_frame(old_alert + recent_checks), tail_rows=10
    )

    assert len(lines) == 1
    assert "导航仪监测正常" in lines[0]
    assert "无告警事件" in lines[0]


def test_risk_alert_takeaways_degrade_when_log_missing() -> None:
    assert "暂未生成" in report._risk_alert_takeaways(None)[0]
    assert "暂未生成" in report._risk_alert_takeaways(pd.DataFrame())[0]
