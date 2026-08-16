"""盘前操作清单与 walk-forward 判定两个本地意图的路由、执行与空态用例。

仿照 tests/test_agent_intent_routing.py 的既有模式：
- 路由解析走 resolve_local_request；
- 执行面用 AnalysisViewTool + _build_intent_handlers，上游服务按既有 stub 惯例
  monkeypatch（pretrade）或用 MOSS_WALK_FORWARD_REPORT_PATH 环境变量指向合成
  报告（walk-forward，读真实 strategy_report_service 裁剪链路）。
"""
from __future__ import annotations

import json

import pytest

from tests.helpers import ROOT, load_module


def _expected_report_reference(report_file) -> str:
    """与 handler 的证据引用口径一致：仓内路径相对化（posix），仓外保持原样。"""
    try:
        return report_file.resolve().relative_to(ROOT).as_posix()
    except (OSError, ValueError):
        return str(report_file)

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


def _load_agent_modules():
    service_module = load_module(
        "backend.app.services.agent_service",
        "backend/app/services/agent_service.py",
    )
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )
    return service_module, tool_module, request_module


@pytest.mark.parametrize(
    ("question", "expected_route", "expected_intent"),
    [
        ("今天盘前该做什么", "local", "pretrade_checklist"),
        ("今天有什么可以买的", "local", "pretrade_checklist"),
        ("给我盘前操作清单", "local", "pretrade_checklist"),
        ("开盘 checklist 有哪些拦截", "local", "pretrade_checklist"),
        ("盘前可以买什么", "local", "pretrade_checklist"),
        ("策略样本外表现怎么样", "local", "walk_forward_verdict"),
        ("walk-forward 验证结果如何", "local", "walk_forward_verdict"),
        ("哪个策略靠谱", "local", "walk_forward_verdict"),
        ("回测验证的结论是什么", "local", "walk_forward_verdict"),
        # 「样本外…收益」不得被 pnl_summary 的「收益」守卫截走（新意图优先级在前）。
        ("策略样本外收益怎么样", "local", "walk_forward_verdict"),
        # 既有词表行为保持不变。
        ("今天的利率怎么样", "local", "market_data"),
        ("投资收益怎么样", "local", "pnl_summary"),
        ("帮我算一个目前不支持的复杂策略", "provider", None),
    ],
)
def test_pretrade_and_walk_forward_keyword_routing(question, expected_route, expected_intent):
    resolution_module = load_module(
        "backend.app.agent.runtime.local_request_resolution",
        "backend/app/agent/runtime/local_request_resolution.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    resolution = resolution_module.resolve_local_request(
        request_module.AgentQueryRequest(question=question)
    )

    assert resolution.route == expected_route
    assert resolution.intent == expected_intent


def _pretrade_upstream_stub() -> dict[str, object]:
    """与 pretrade_checklist_service.pretrade_checklist_envelope 输出同构的合成 envelope。"""
    items = [
        {
            "candidate_rank": 1,
            "stock_code": "600001.SH",
            "stock_name": "示例甲",
            "sector_name": "银行",
            "selection_close": 10.0,
            "close_value": 10.5,
            "trade_status": "交易",
            "is_suspended": False,
            "limit_check": {
                "status": "none",
                "price_source": "stk_limit",
                "up_limit": 11.55,
                "down_limit": 9.45,
            },
            "amount_rmb": 123456789.0,
            "adj_factor_missing": False,
            "buyable_status": "buyable",
            "block_reasons": [],
            "data_flags": [],
            "position_hint": {"stock_code": "600001.SH", "equal_weight": 0.5},
        },
        {
            "candidate_rank": 2,
            "stock_code": "600002.SH",
            "stock_name": "示例乙",
            "sector_name": "地产",
            "selection_close": 8.0,
            "close_value": None,
            "trade_status": "停牌",
            "is_suspended": True,
            "limit_check": {
                "status": "unknown",
                "price_source": "missing",
                "up_limit": None,
                "down_limit": None,
            },
            "amount_rmb": None,
            "adj_factor_missing": True,
            "buyable_status": "blocked_suspended",
            "block_reasons": ["suspended"],
            "data_flags": ["adj_factor_missing", "limit_price_missing"],
            "position_hint": None,
        },
        {
            "candidate_rank": 3,
            "stock_code": "600003.SH",
            "stock_name": "示例丙",
            "sector_name": "科技",
            "selection_close": 20.0,
            "close_value": 22.0,
            "trade_status": "交易",
            "is_suspended": False,
            "limit_check": {
                "status": "limit_up",
                "price_source": "stk_limit",
                "up_limit": 22.0,
                "down_limit": 18.0,
            },
            "amount_rmb": 987654321.0,
            "adj_factor_missing": False,
            "buyable_status": "blocked_limit",
            "block_reasons": ["limit_up"],
            "data_flags": [],
            "position_hint": None,
        },
    ]
    return {
        "result_meta": {
            "basis": "analytical",
            "quality_flag": "warning",
            "formal_use_allowed": False,
            "source_version": "sv_pretrade_checklist_2026-08-07",
            "rule_version": "rv_pretrade_checklist_v1",
            "cache_version": "cv_pretrade_checklist_v1",
            "tables_used": [
                "livermore_candidate_history",
                "choice_stock_daily_observation",
                "stock_limit_price_daily",
                "stock_adjustment_factor",
            ],
            "as_of_date": "2026-08-07",
        },
        "result": {
            "as_of_date": "2026-08-07",
            "signal_kind": "factor_screen",
            "checklist_status": "stale",
            "candidate_count": 3,
            "top_n": 10,
            "staleness": {
                "status": "stale",
                "today": "2026-08-13",
                "calendar_gap_days": 6,
                "stale_calendar_days": 5,
            },
            "gate": {
                "status": "missing",
                "state": None,
                "exposure": None,
                "source": None,
                "note": "门控敞口在该信号日无持久化点位且不可回放，字段缺省，不代表门控放行。",
            },
            "position_size_hint": {"items": []},
            "items": items,
            "summary": {
                "buyable_count": 1,
                "blocked_count": 2,
                "review_count": 0,
                "data_missing_count": 0,
            },
            "disclaimer": "观察面输出：盘前检查仅供复核参考，不构成交易指令。",
        },
    }


def test_pretrade_checklist_intent_summarizes_service_payload(tmp_path, monkeypatch):
    service_module, tool_module, request_module = _load_agent_modules()
    pretrade_module = load_module(
        "backend.app.services.pretrade_checklist_service",
        "backend/app/services/pretrade_checklist_service.py",
    )

    calls: list[tuple[str, str | None]] = []

    def fake_pretrade_checklist_envelope(
        *,
        duckdb_path: str,
        as_of_date: str | None = None,
        **_: object,
    ) -> dict[str, object]:
        calls.append((duckdb_path, as_of_date))
        return _pretrade_upstream_stub()

    monkeypatch.setattr(
        pretrade_module,
        "pretrade_checklist_envelope",
        fake_pretrade_checklist_envelope,
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="今天盘前该做什么",
            filters={"as_of_date": "2026-08-07"},
        )
    )

    assert calls == [("test.duckdb", "2026-08-07")]
    assert envelope.result_meta.result_kind == "agent.pretrade_checklist"
    assert envelope.result_meta.basis == "analytical"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.result_meta.resolved_report_date == "2026-08-07"
    # 摘要：信号日 + stale 警示 + 可买列表 + 拦截原因。
    assert "2026-08-07" in envelope.answer
    assert "可买 1 只" in envelope.answer
    assert "拦截 2 只" in envelope.answer
    assert "超过 stale 阈值 5 天" in envelope.answer
    assert "600001.SH 示例甲" in envelope.answer
    assert "停牌" in envelope.answer
    assert "涨停" in envelope.answer
    assert "不构成交易指令" in envelope.answer
    # 证据引用：来源表 + 只读 SQL 披露 + 过滤条件。
    assert envelope.evidence.tables_used == [
        "livermore_candidate_history",
        "choice_stock_daily_observation",
        "stock_limit_price_daily",
        "stock_adjustment_factor",
    ]
    assert envelope.evidence.sql_executed == service_module._PRETRADE_CHECKLIST_SQL_DISCLOSURE
    assert envelope.evidence.evidence_rows == 3
    assert envelope.evidence.filters_applied["signal_kind"] == "factor_screen"
    assert envelope.evidence.filters_applied["checklist_status"] == "stale"
    assert envelope.evidence.filters_applied["report_date"] == "2026-08-07"
    assert envelope.evidence.filters_applied["report_date_resolution"] == "explicit"
    card_titles = [card.title for card in envelope.cards]
    assert "Stale Signal Warning" in card_titles
    assert "Gate Exposure Degraded" in card_titles
    assert "Buyable Candidates" in card_titles
    assert "Blocked / Review Candidates" in card_titles
    blocked_card = next(card for card in envelope.cards if card.title == "Blocked / Review Candidates")
    assert blocked_card.data[0]["stock_code"] == "600002.SH"
    assert blocked_card.data[0]["status_label"] == "停牌拦截"
    assert blocked_card.data[0]["block_reasons"] == "停牌"
    assert blocked_card.data[1]["block_reasons"] == "涨停"


def test_pretrade_checklist_unavailable_degrades_with_friendly_answer(tmp_path, monkeypatch):
    service_module, tool_module, request_module = _load_agent_modules()
    pretrade_module = load_module(
        "backend.app.services.pretrade_checklist_service",
        "backend/app/services/pretrade_checklist_service.py",
    )

    monkeypatch.setattr(
        pretrade_module,
        "pretrade_checklist_envelope",
        lambda **_: None,
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="今天有什么可以买的")
    )

    assert envelope.result_meta.result_kind == "agent.pretrade_checklist"
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.result_meta.formal_use_allowed is False
    assert "盘前操作清单数据未生成" in envelope.answer
    assert envelope.evidence.evidence_rows == 0
    assert any(card.title == "Pretrade Checklist Unavailable" for card in envelope.cards)
    # 不得因数据缺失落入 error envelope（降级是业务空态，不是查询失败）。
    assert "查询失败" not in envelope.answer


def _walk_forward_report_stub() -> dict[str, object]:
    """与 scripts/run_walk_forward_validation.py 落盘结构同构的最小合成报告。"""
    return {
        "generated_at": "2026-08-13 09:00:00+0800",
        "engine_version": "pbt_v2_path_mode",
        "mode": "path",
        "issues": [],
        "schedules": [
            {
                "schedule": {
                    "label": "train12_valid3",
                    "train_months": 12,
                    "valid_months": 3,
                    "step_months": 3,
                    "objective": "excess_vs_gate",
                    "min_windows_for_verdict": 4,
                },
                "windows": [{}, {}, {}, {}],
                "equal_weight": {
                    "livermore": {
                        "verdict": "oos_supported",
                        "verdict_reason": "chain excess positive across windows",
                        "oos_window_count": 4,
                        "in_sample": {"excess_vs_gate": 0.081234},
                        "oos_chain_excess": 0.041111,
                        "excess_sign_consistency": {
                            "observed_windows": 4,
                            "positive_windows": 3,
                            "negative_windows": 1,
                            "positive_ratio": 0.75,
                        },
                        "decay_cumulative": {"status": "ok", "ratio": 0.5},
                        "windows": [
                            {"excess_vs_gate": 0.02},
                            {"excess_vs_gate": -0.01},
                            {"excess_vs_gate": 0.03},
                            {"excess_vs_gate": 0.01},
                        ],
                    },
                    "momentum": {
                        "verdict": "insufficient_windows",
                        "verdict_reason": "only 2 observed windows",
                        "oos_window_count": 2,
                        "in_sample": {"excess_vs_gate": 0.02},
                        "oos_chain_excess": None,
                        "excess_sign_consistency": {
                            "observed_windows": 2,
                            "positive_windows": 1,
                            "negative_windows": 1,
                            "positive_ratio": 0.5,
                        },
                        "decay_cumulative": {"status": "insufficient", "ratio": None},
                        "windows": [
                            {"excess_vs_gate": 0.01},
                            {"excess_vs_gate": -0.02},
                        ],
                    },
                },
                "risk_budget": {
                    "livermore": {
                        "grid": [0.005, 0.01],
                        "policy_param": 0.01,
                        "selected": {"verdict": "oos_supported", "oos_chain_excess": 0.03},
                        "windows": [{"window_id": "w1", "selected": 0.01, "oracle": 0.01}],
                        "drift": {
                            "switch_rate": 0.25,
                            "switch_count": 1,
                            "mode_value": 0.01,
                            "mode_share": 0.75,
                            "observed_windows": 4,
                            "distinct_values": 2,
                        },
                    },
                },
            }
        ],
    }


def test_walk_forward_verdict_intent_reads_report_and_summarizes_per_strategy(
    tmp_path, monkeypatch
):
    service_module, tool_module, request_module = _load_agent_modules()
    report_file = tmp_path / "walk-forward-synthetic.json"
    report_file.write_text(
        json.dumps(_walk_forward_report_stub(), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_WALK_FORWARD_REPORT_PATH", str(report_file))

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="策略样本外表现怎么样")
    )

    assert envelope.result_meta.result_kind == "agent.walk_forward_verdict"
    assert envelope.result_meta.basis == "analytical"
    assert envelope.result_meta.formal_use_allowed is False
    # 每策略一行判定摘要 + 关键数字。
    assert "样本外支持 1" in envelope.answer
    assert "样本不足 1" in envelope.answer
    assert "livermore[train12_valid3]：样本外支持" in envelope.answer
    assert "0.041111" in envelope.answer
    assert "0.75" in envelope.answer
    assert "momentum[train12_valid3]：样本不足" in envelope.answer
    assert "未重算任何指标" in envelope.answer
    # 证据引用：报告文件路径；纯文件读取，无 DuckDB SQL。
    expected_ref = _expected_report_reference(report_file)
    assert envelope.evidence.tables_used == [expected_ref]
    assert envelope.evidence.sql_executed == []
    assert envelope.evidence.filters_applied["report_path"] == expected_ref
    verdict_card = next(
        card for card in envelope.cards if card.title == "Walk-Forward Strategy Verdicts"
    )
    assert len(verdict_card.data) == 2
    assert verdict_card.data[0]["strategy"] == "livermore"
    assert verdict_card.data[0]["verdict_label"] == "样本外支持"
    assert verdict_card.data[0]["rpt_switch_rate"] == 0.25
    assert verdict_card.data[1]["strategy"] == "momentum"
    assert verdict_card.data[1]["verdict_label"] == "样本不足"
    assert any(card.title == "Walk-Forward Report" for card in envelope.cards)


def test_walk_forward_verdict_missing_report_degrades(tmp_path, monkeypatch):
    service_module, tool_module, request_module = _load_agent_modules()
    monkeypatch.setenv(
        "MOSS_WALK_FORWARD_REPORT_PATH",
        str(tmp_path / "missing-walk-forward.json"),
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="walk-forward 验证结果如何")
    )

    assert envelope.result_meta.result_kind == "agent.walk_forward_verdict"
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.result_meta.formal_use_allowed is False
    assert "策略样本外验证报告未生成" in envelope.answer
    assert envelope.evidence.evidence_rows == 0
    assert envelope.evidence.sql_executed == []
    assert any(card.title == "Walk-Forward Report Unavailable" for card in envelope.cards)
