from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tests.helpers import load_module
from backend.app.agent.runtime.action_token import agent_action_confirmation_token_matches


def test_portfolio_overview_intent_routes_to_balance_analysis_repo(tmp_path, monkeypatch):
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

    calls: list[tuple[str, str, str]] = []

    class StubBalanceAnalysisRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def fetch_formal_overview(
            self,
            *,
            report_date: str,
            position_scope: str,
            currency_basis: str,
        ) -> dict[str, object]:
            calls.append((report_date, position_scope, currency_basis))
            return {
                "detail_row_count": 3,
                "total_market_value_amount": 1000,
                "total_amortized_cost_amount": 950,
                "total_accrued_interest_amount": 12,
                "source_version": "sv_balance_1",
                "rule_version": "rv_balance_1",
            }

    monkeypatch.setattr(service_module, "BalanceAnalysisRepository", StubBalanceAnalysisRepository)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="portfolio overview",
            filters={"report_date": "2026-03-31"},
            position_scope="asset",
            currency_basis="CNY",
        )
    )

    assert calls == [("2026-03-31", "asset", "CNY")]
    assert envelope.result_meta.result_kind == "agent.portfolio_overview"
    assert envelope.result_meta.basis == "formal"
    assert envelope.evidence.tables_used == [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    ]
    market_value_card = next(card for card in envelope.cards if card.title == "Total Market Value")
    assert market_value_card.value == "1,000.00000000 元"
    assert market_value_card.spec == {
        "metric_id": "MTR-BAL-001",
        "source_field": "total_market_value_amount",
        "raw_value": "1000.00000000",
        "raw_unit": "yuan",
        "raw_precision": 8,
        "numeric": {
            "raw": 1000.0,
            "unit": "yuan",
            "display": "1,000.00000000 元",
            "precision": 8,
            "sign_aware": False,
        },
    }
    assert envelope.result_meta.amount_currency_basis == "CNY"
    assert envelope.result_meta.requested_report_date == "2026-03-31"
    assert envelope.result_meta.resolved_report_date == "2026-03-31"
    assert envelope.result_meta.as_of_date == "2026-03-31"
    assert envelope.result_meta.date_basis == "balance_analysis_report_date"
    assert envelope.result_meta.fallback_date is None
    assert envelope.result_meta.source_surface == "formal_balance"


def test_portfolio_overview_empty_scope_does_not_synthesize_financial_zeroes(tmp_path, monkeypatch):
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

    class EmptyBalanceAnalysisRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def fetch_formal_overview(
            self,
            *,
            report_date: str,
            position_scope: str,
            currency_basis: str,
        ) -> dict[str, object]:
            return {
                "detail_row_count": 0,
                "total_market_value_amount": 0,
                "total_amortized_cost_amount": 0,
                "total_accrued_interest_amount": 0,
                "source_version": None,
                "rule_version": None,
            }

    monkeypatch.setattr(service_module, "BalanceAnalysisRepository", EmptyBalanceAnalysisRepository)
    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="portfolio overview",
            position_scope="liability",
            currency_basis="CNY",
        )
    )

    assert envelope.result_meta.result_kind == "agent.portfolio_overview"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.evidence.evidence_rows == 0
    assert not any(card.type == "metric" for card in envelope.cards)
    assert any(card.type == "status" for card in envelope.cards)
    assert "0.00000000" not in envelope.answer


def test_portfolio_overview_native_currency_does_not_claim_yuan_unit(tmp_path, monkeypatch):
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

    class NativeBalanceAnalysisRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def fetch_formal_overview(
            self,
            *,
            report_date: str,
            position_scope: str,
            currency_basis: str,
        ) -> dict[str, object]:
            assert currency_basis == "native"
            return {
                "detail_row_count": 2,
                "total_market_value_amount": 1000,
                "total_amortized_cost_amount": 950,
                "total_accrued_interest_amount": 12,
                "source_version": "sv_native_1",
                "rule_version": "rv_native_1",
            }

    monkeypatch.setattr(service_module, "BalanceAnalysisRepository", NativeBalanceAnalysisRepository)
    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="portfolio overview",
            currency_basis="native",
        )
    )

    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.result_meta.amount_currency_basis == "native"
    assert not any(card.type == "metric" for card in envelope.cards)
    assert all(not card.spec or "numeric" not in card.spec for card in envelope.cards)


@pytest.mark.parametrize(
    ("source_version_missing_count", "rule_version_missing_count", "missing_field"),
    [
        (1, 0, "source_version"),
        (0, 2, "rule_version"),
    ],
)
def test_portfolio_overview_formal_use_requires_complete_cny_lineage(
    tmp_path,
    monkeypatch,
    source_version_missing_count: int,
    rule_version_missing_count: int,
    missing_field: str,
):
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

    class IncompleteLineageBalanceAnalysisRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def fetch_formal_overview(
            self,
            *,
            report_date: str,
            position_scope: str,
            currency_basis: str,
        ) -> dict[str, object]:
            return {
                "detail_row_count": 2,
                "lineage_row_count": 2,
                "source_version_missing_count": source_version_missing_count,
                "rule_version_missing_count": rule_version_missing_count,
                "total_market_value_amount": 1000,
                "total_amortized_cost_amount": 950,
                "total_accrued_interest_amount": 12,
                "source_version": "sv_balance_1",
                "rule_version": "rv_balance_1",
            }

    monkeypatch.setattr(
        service_module,
        "BalanceAnalysisRepository",
        IncompleteLineageBalanceAnalysisRepository,
    )
    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="portfolio overview",
            currency_basis="CNY",
        )
    )

    assert envelope.result_meta.result_kind == "agent.portfolio_overview"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.result_meta.amount_currency_basis == "CNY"
    assert missing_field in (envelope.result_meta.amount_currency_basis_note or "")
    assert envelope.evidence.evidence_rows == 2
    assert not any(card.type == "metric" for card in envelope.cards)
    status_card = next(card for card in envelope.cards if card.type == "status")
    assert status_card.title == "Governed Lineage Incomplete"
    assert missing_field in status_card.value
    assert missing_field in envelope.answer
    assert "元" not in envelope.answer


def test_portfolio_overview_complete_lineage_preserves_valid_zero_amounts(tmp_path, monkeypatch):
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

    class ZeroAmountBalanceAnalysisRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def fetch_formal_overview(
            self,
            *,
            report_date: str,
            position_scope: str,
            currency_basis: str,
        ) -> dict[str, object]:
            return {
                "detail_row_count": 2,
                "lineage_row_count": 2,
                "source_version_missing_count": 0,
                "rule_version_missing_count": 0,
                "total_market_value_amount": 0,
                "total_amortized_cost_amount": 0,
                "total_accrued_interest_amount": 0,
                "source_version": "sv_balance_1",
                "rule_version": "rv_balance_1",
            }

    monkeypatch.setattr(
        service_module,
        "BalanceAnalysisRepository",
        ZeroAmountBalanceAnalysisRepository,
    )
    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="portfolio overview",
            currency_basis="CNY",
        )
    )

    assert envelope.result_meta.result_kind == "agent.portfolio_overview"
    assert envelope.result_meta.formal_use_allowed is True
    market_value_card = next(card for card in envelope.cards if card.title == "Total Market Value")
    assert market_value_card.spec["numeric"]["raw"] == 0.0


def test_portfolio_amount_card_preserves_missing_value_as_null_numeric():
    service_module = load_module(
        "backend.app.services.agent_service",
        "backend/app/services/agent_service.py",
    )

    card = service_module._portfolio_amount_card(
        title="Total Market Value",
        metric_id="MTR-BAL-001",
        source_field="total_market_value_amount",
        value=None,
    )

    assert card["value"] == "—"
    assert card["spec"]["raw_value"] is None
    assert card["spec"]["numeric"] == {
        "raw": None,
        "unit": "yuan",
        "display": "—",
        "precision": 8,
        "sign_aware": False,
    }


def test_market_value_phrase_routes_to_portfolio_overview_not_market_data(tmp_path, monkeypatch):
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

    calls: list[tuple[str, str, str]] = []

    class StubBalanceAnalysisRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def fetch_formal_overview(self, *, report_date: str, position_scope: str, currency_basis: str) -> dict[str, object]:
            calls.append((report_date, position_scope, currency_basis))
            return {
                "detail_row_count": 1,
                "total_market_value_amount": 800,
                "total_amortized_cost_amount": 790,
                "total_accrued_interest_amount": 6,
                "source_version": "sv_balance_2",
                "rule_version": "rv_balance_2",
            }

    monkeypatch.setattr(service_module, "BalanceAnalysisRepository", StubBalanceAnalysisRepository)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="portfolio market value")
    )

    assert calls == [("2026-03-31", "all", "CNY")]
    assert envelope.evidence.filters_applied["currency_basis"] == "CNY"
    assert envelope.result_meta.result_kind == "agent.portfolio_overview"
    assert any(card.title == "Total Market Value" for card in envelope.cards)


def test_explicit_context_intent_routes_without_keyword_guessing(tmp_path):
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    calls: list[str] = []
    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "pnl_summary": lambda request: {
                "answer": calls.append(request.question) or "pnl ok",
                "basis": "formal",
                "result_kind": "agent.pnl_summary",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": 1,
                "cards": [{"type": "metric", "title": "Total PnL", "value": "9"}],
            }
        },
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="解释当前页面",
            context={"intent": "pnl_summary"},
        )
    )

    assert calls == ["解释当前页面"]
    assert envelope.result_meta.result_kind == "agent.pnl_summary"
    assert "Total PnL=9" in envelope.answer


def test_real_chinese_business_keywords_route_to_governed_intents(tmp_path):
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    def handler(intent: str):
        return lambda request: {
            "answer": f"{intent} ok",
            "basis": "formal",
            "result_kind": f"agent.{intent}",
            "formal_use_allowed": True,
            "source_version": "sv_test",
            "quality_flag": "ok",
            "row_count": 1,
            "cards": [{"type": "metric", "title": intent, "value": "1"}],
        }

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "portfolio_overview": handler("portfolio_overview"),
            "pnl_summary": handler("pnl_summary"),
            "credit_exposure": handler("credit_exposure"),
            "market_data": handler("market_data"),
        },
    )

    cases = [
        ("\u8bf7\u770b\u7ec4\u5408\u6982\u89c8", "agent.portfolio_overview"),
        ("\u8bf7\u6c47\u603b\u4eca\u65e5\u635f\u76ca", "agent.pnl_summary"),
        ("\u4fe1\u7528\u98ce\u9669\u548c\u96c6\u4e2d\u5ea6\u600e\u4e48\u6837", "agent.credit_exposure"),
        ("\u6700\u65b0\u5b8f\u89c2\u5e02\u573a\u6570\u636e", "agent.market_data"),
    ]

    for question, expected_kind in cases:
        envelope = tool.execute(request_module.AgentQueryRequest(question=question))
        assert envelope.result_meta.result_kind == expected_kind


def test_generic_dashboard_page_question_routes_to_page_default_intent(tmp_path):
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "portfolio_overview": lambda request: {
                "answer": "dashboard overview ok",
                "basis": "formal",
                "result_kind": "agent.portfolio_overview",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": 1,
                "cards": [{"type": "metric", "title": "Total Market Value", "value": "100"}],
            }
        },
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="解释当前页面的主要结论和风险点",
            page_context=request_module.AgentPageContext(
                page_id="dashboard",
                current_filters={"report_date": "2026-03-31"},
            ),
        )
    )

    assert envelope.result_meta.result_kind == "agent.portfolio_overview"
    assert "dashboard overview ok" in envelope.answer


def test_generic_pnl_attribution_page_question_routes_to_pnl_bridge(tmp_path):
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "pnl_summary": lambda request: {
                "answer": "pnl summary ok",
                "basis": "formal",
                "result_kind": "agent.pnl_summary",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": 1,
            },
            "pnl_bridge": lambda request: {
                "answer": "pnl bridge ok",
                "basis": "formal",
                "result_kind": "agent.pnl_bridge",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": 1,
                "cards": [{"type": "metric", "title": "Residual", "value": "0.2"}],
            },
        },
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="解释当前页面的主要结论",
            page_context=request_module.AgentPageContext(
                page_id="pnl-attribution",
                current_filters={"report_date": "2026-03-31"},
            ),
        )
    )

    assert envelope.result_meta.result_kind == "agent.pnl_bridge"
    assert "Residual=0.2" in envelope.answer


def test_specific_duration_question_with_page_context_beats_page_default_intent(tmp_path):
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "portfolio_overview": lambda request: {
                "answer": "dashboard overview ok",
                "basis": "formal",
                "result_kind": "agent.portfolio_overview",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": 1,
            },
            "duration_risk": lambda request: {
                "answer": "duration ok",
                "basis": "formal",
                "result_kind": "agent.duration_risk",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": 1,
                "cards": [{"type": "metric", "title": "Portfolio DV01", "value": "12"}],
            },
        },
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="当前页面久期风险在哪里",
            page_context=request_module.AgentPageContext(
                page_id="dashboard",
                current_filters={"report_date": "2026-03-31"},
            ),
        )
    )

    assert envelope.result_meta.result_kind == "agent.duration_risk"
    assert "Portfolio DV01=12" in envelope.answer


def test_follow_up_question_reuses_last_local_agent_intent(tmp_path):
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "duration_risk": lambda request: {
                "answer": "duration ok",
                "basis": "formal",
                "result_kind": "agent.duration_risk",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": 1,
                "cards": [{"type": "metric", "title": "Portfolio DV01", "value": "12"}],
            }
        },
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="继续看这个",
            context={
                "conversation": {
                    "recent_turns": [
                        {
                            "question": "当前久期风险在哪里？",
                            "answer": "口径边界：basis=formal；可正式使用；result_kind=agent.duration_risk；report_date=2026-03-31。",
                            "trace_id": "tr_agent_duration_risk_abc",
                        }
                    ]
                }
            },
        )
    )

    assert envelope.result_meta.result_kind == "agent.duration_risk"
    assert "Portfolio DV01=12" in envelope.answer


def test_follow_up_question_uses_structured_result_kind_when_answer_has_no_marker(tmp_path):
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "duration_risk": lambda request: {
                "answer": "duration ok",
                "basis": "formal",
                "result_kind": "agent.duration_risk",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": 1,
                "cards": [{"type": "metric", "title": "Portfolio DV01", "value": "12"}],
            }
        },
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="continue this",
            context={
                "conversation": {
                    "recent_turns": [
                        {
                            "question": "show duration risk",
                            "answer": "The previous answer mentioned DV01, but no marker text.",
                            "result_kind": "agent.duration_risk",
                            "trace_id": "tr_previous_without_intent_suffix",
                        }
                    ]
                }
            },
        )
    )

    assert envelope.result_meta.result_kind == "agent.duration_risk"
    assert "Portfolio DV01=12" in envelope.answer


def test_unrelated_question_with_conversation_context_does_not_reuse_previous_intent(tmp_path):
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "duration_risk": lambda request: {
                "answer": "duration ok",
                "basis": "formal",
                "result_kind": "agent.duration_risk",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": 1,
            }
        },
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="tell me a joke",
            context={
                "conversation": {
                    "recent_turns": [
                        {
                            "result_kind": "agent.duration_risk",
                            "answer": "Previous governed answer.",
                        }
                    ]
                }
            },
        )
    )

    assert envelope.result_meta.result_kind == "agent.unknown"
    assert any(card.title == "Supported Queries" for card in envelope.cards)


def test_agent_answers_use_business_analysis_sections(tmp_path):
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "portfolio_overview": lambda request: {
                "answer": "2026-03-31 的组合概览已返回，当前口径共 3 条明细，总资产规模 1000。",
                "basis": "formal",
                "result_kind": "agent.portfolio_overview",
                "formal_use_allowed": True,
                "source_version": "sv_balance_1",
                "rule_version": "rv_balance_1",
                "cache_version": "cv_agent_portfolio_overview_v1",
                "quality_flag": "ok",
                "row_count": 3,
                "tables_used": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
                "filters_applied": {
                    "report_date": "2026-03-31",
                    "currency_basis": "CNY",
                    "position_scope": "asset",
                },
                "cards": [
                    {"type": "metric", "title": "Total Market Value", "value": "1000"},
                    {"type": "metric", "title": "Detail Rows", "value": "3"},
                ],
                "next_drill": [{"dimension": "portfolio", "label": "按组合查看"}],
            }
        },
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="组合概览",
            position_scope="asset",
            currency_basis="CNY",
        )
    )

    assert envelope.answer.startswith("结论：")
    for section in ("关键数字：", "证据：", "口径边界：", "下一步："):
        assert section in envelope.answer
    assert "fact_formal_zqtz_balance_daily、fact_formal_tyw_balance_daily" in envelope.answer
    assert "formal" in envelope.answer
    assert "CNY" in envelope.answer
    assert "按组合查看" in envelope.answer


def test_next_drill_suggested_actions_include_page_context_payload(tmp_path):
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "portfolio_overview": lambda request: {
                "answer": "ok",
                "basis": "formal",
                "result_kind": "agent.portfolio_overview",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": 1,
                "next_drill": [{"dimension": "instrument_id", "label": "Inspect instrument"}],
            }
        },
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="portfolio overview",
            page_context=request_module.AgentPageContext(
                page_id="recon-exceptions",
                current_filters={"report_date": "2026-03-31", "status": "unmatched"},
                selected_rows=[{"book_id": "B001", "instrument_id": "IB123"}],
                context_note="user selected one exception row",
            ),
        )
    )

    assert len(envelope.suggested_actions) == 1
    action = envelope.suggested_actions[0]
    assert action.type == "inspect_drill"
    assert action.requires_confirmation is True
    assert action.confirmation_token
    assert action.payload == {
        "dimension": "instrument_id",
        "page_context": {
            "page_id": "recon-exceptions",
            "current_filters": {"report_date": "2026-03-31", "status": "unmatched"},
            "selected_rows": [{"book_id": "B001", "instrument_id": "IB123"}],
            "context_note": "user selected one exception row",
        },
    }
    assert agent_action_confirmation_token_matches(
        token=action.confirmation_token,
        action_type=action.type,
        label=action.label,
        payload=action.payload,
    )


def test_next_drill_inspect_labels_include_first_selected_row_summary(tmp_path):
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "portfolio_overview": lambda request: {
                "answer": "ok",
                "basis": "formal",
                "result_kind": "agent.portfolio_overview",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": 1,
                "next_drill": [{"dimension": "break_reason", "label": "Inspect drill"}],
            }
        },
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="portfolio overview",
            page_context=request_module.AgentPageContext(
                page_id="recon-exceptions",
                selected_rows=[
                    {
                        "book_id": "BOOK-A",
                        "instrument_id": "INST-9",
                        "recon_type": "cash_vs_position",
                        "status": "unmatched",
                        "ignored": "not part of the summary",
                    },
                    {"book_id": "BOOK-B", "instrument_id": "INST-10"},
                ],
            ),
        )
    )

    assert envelope.suggested_actions[0].label == (
        "Inspect drill for book_id=BOOK-A, instrument_id=INST-9, "
        "recon_type=cash_vs_position, status=unmatched"
    )


def test_agent_report_date_context_precedence_filters_context_current_filters_latest(tmp_path, monkeypatch):
    service_module = load_module(
        "backend.app.services.agent_service",
        "backend/app/services/agent_service.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    available_dates = ["2026-03-31", "2026-02-28", "2026-01-31", "2025-12-31"]

    assert service_module._latest_or_requested(
        request_module.AgentQueryRequest(
            question="组合概览",
            filters={"report_date": "2026-02-28"},
            context={
                "report_date": "2026-01-31",
                "current_filters": {"report_date": "2025-12-31"},
            },
        ),
        available_dates,
    ) == "2026-02-28"
    assert service_module._latest_or_requested(
        request_module.AgentQueryRequest(
            question="组合概览",
            context={
                "page_id": "dashboard",
                "report_date": "2026-01-31",
                "current_filters": {"report_date": "2025-12-31"},
            },
        ),
        available_dates,
    ) == "2026-01-31"
    assert service_module._latest_or_requested(
        request_module.AgentQueryRequest(
            question="组合概览",
            context={"current_filters": {"report_date": "2025-12-31"}},
        ),
        available_dates,
    ) == "2025-12-31"
    assert service_module._latest_or_requested(
        request_module.AgentQueryRequest(
            question="组合概览",
            page_context=request_module.AgentPageContext(
                page_id="dashboard",
                current_filters={"report_date": "2026-02-28"},
            ),
        ),
        available_dates,
    ) == "2026-02-28"
    assert service_module._latest_or_requested(
        request_module.AgentQueryRequest(question="组合概览"),
        available_dates,
    ) == "2026-03-31"


def test_pnl_summary_intent_routes_to_pnl_repo(tmp_path, monkeypatch):
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

    calls: list[str] = []

    class StubPnlRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_union_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def overview_totals(self, report_date: str) -> dict[str, object]:
            calls.append(report_date)
            return {
                "formal_fi_row_count": 2,
                "nonstd_bridge_row_count": 1,
                "interest_income_514": 10,
                "fair_value_change_516": 20,
                "capital_gain_517": 30,
                "manual_adjustment": 0,
                "total_pnl": 60,
            }

    monkeypatch.setattr(service_module, "PnlRepository", StubPnlRepository)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="请给我看一下损益概览")
    )

    assert calls == ["2026-03-31"]
    assert envelope.result_meta.result_kind == "agent.pnl_summary"
    assert envelope.result_meta.basis == "formal"
    assert envelope.result_meta.filters_applied["report_date"] == "2026-03-31"
    assert envelope.evidence.tables_used == ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"]
    assert envelope.evidence.sql_executed
    assert all(sql.lower().startswith("select") for sql in envelope.evidence.sql_executed)
    assert any("from fact_formal_pnl_fi" in sql for sql in envelope.evidence.sql_executed)
    assert envelope.result_meta.sql_executed == envelope.evidence.sql_executed
    assert any(card.title == "Total PnL" for card in envelope.cards)


def _duration_risk_upstream(
    report_date: str,
    *,
    bond_count: int = 3,
    quality_flag: str = "ok",
) -> dict[str, object]:
    def numeric(raw: float, unit: str, display: str) -> dict[str, object]:
        return {
            "raw": raw,
            "unit": unit,
            "display": display,
            "precision": 2,
            "sign_aware": False,
        }

    return {
        "result": {
            "report_date": report_date,
            "portfolio_modified_duration": numeric(4.1, "ratio", "4.10"),
            "portfolio_dv01": numeric(12.34, "dv01", "12.34"),
            "portfolio_convexity": numeric(0.88, "ratio", "0.88"),
            "rate_risk_market_value": numeric(900.0, "yuan", "900.00"),
            "duration_excluded_market_value": numeric(100.0, "yuan", "100.00"),
            "duration_excluded_count": 1,
            "bond_count": bond_count,
            "quality_flag": quality_flag,
            "warnings": [],
        },
        "result_meta": {
            "basis": "formal",
            "formal_use_allowed": True,
            "quality_flag": quality_flag,
            "source_version": "sv_risk_tensor_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_risk_tensor_test",
            "cache_version": "cv_risk_tensor_test",
            "vendor_status": "ok",
            "fallback_mode": "none",
        },
    }


def test_duration_risk_intent_routes_to_formal_risk_tensor(tmp_path, monkeypatch):
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

    calls: list[str] = []

    class StubRiskTensorRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

    def fake_risk_tensor_envelope(*, report_date: str, **_: object) -> dict[str, object]:
        calls.append(report_date)
        return _duration_risk_upstream(report_date, quality_flag="warning")

    risk_service_module = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    monkeypatch.setattr(service_module, "RiskTensorRepository", StubRiskTensorRepository)
    monkeypatch.setattr(risk_service_module, "risk_tensor_envelope", fake_risk_tensor_envelope)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="组合久期和DV01风险怎么样")
    )

    assert calls == ["2026-03-31"]
    assert envelope.result_meta.result_kind == "agent.duration_risk"
    assert envelope.result_meta.basis == "formal"
    assert envelope.result_meta.filters_applied["report_date"] == "2026-03-31"
    assert envelope.result_meta.requested_report_date is None
    assert envelope.result_meta.resolved_report_date == "2026-03-31"
    assert envelope.result_meta.as_of_date == "2026-03-31"
    assert envelope.result_meta.date_basis == "formal_snapshot"
    assert envelope.result_meta.source_surface == "risk_tensor"
    assert envelope.result_meta.amount_currency_basis == "CNY"
    assert envelope.result_meta.formal_use_allowed is True
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.result_meta.source_version == "sv_risk_tensor_test"
    assert envelope.result_meta.vendor_version == "vv_none"
    assert envelope.result_meta.rule_version == "rv_risk_tensor_test"
    assert envelope.result_meta.cache_version == "cv_risk_tensor_test"
    assert envelope.result_meta.vendor_status == "ok"
    assert envelope.result_meta.fallback_mode == "none"
    assert envelope.evidence.tables_used == ["fact_formal_risk_tensor_daily"]
    assert envelope.evidence.sql_executed
    assert all(sql.lower().startswith("select") for sql in envelope.evidence.sql_executed)
    assert any("from fact_formal_risk_tensor_daily" in sql for sql in envelope.evidence.sql_executed)

    cards = {card.title: card for card in envelope.cards}
    assert "Portfolio Duration" not in cards
    assert cards["Portfolio Modified Duration"].spec == {
        "metric_id": "MTR-RSK-010",
        "source_field": "portfolio_modified_duration",
        "raw_value": "4.1",
        "raw_unit": "ratio",
        "raw_precision": 2,
        "numeric": {
            "raw": 4.1,
            "unit": "ratio",
            "display": "4.10",
            "precision": 2,
            "sign_aware": False,
        },
    }
    assert cards["Portfolio DV01"].spec["metric_id"] == "MTR-RSK-001"
    assert cards["Portfolio DV01"].spec["numeric"]["unit"] == "dv01"
    assert cards["Portfolio Convexity"].spec["metric_id"] == "MTR-RSK-009"
    assert cards["Rate Risk Market Value"].spec["metric_id"] == "MTR-RSK-021"
    assert cards["Rate Risk Market Value"].spec["numeric"]["unit"] == "yuan"
    assert cards["Duration Excluded Market Value"].spec["metric_id"] == "MTR-RSK-104"
    assert cards["Duration Excluded Market Value"].spec["numeric"]["unit"] == "yuan"
    assert cards["Duration Excluded Count"].spec["metric_id"] == "MTR-RSK-103"
    assert cards["Duration Excluded Count"].spec["numeric"]["unit"] == "count"
    assert cards["Duration Excluded Count"].spec["numeric"]["precision"] == 0
    assert "组合修正久期" in envelope.answer
    assert "CNY/1bp" in envelope.answer


def test_duration_risk_empty_tensor_does_not_synthesize_formal_metrics(tmp_path, monkeypatch):
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

    class StubRiskTensorRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

    def fake_risk_tensor_envelope(*, report_date: str, **_: object) -> dict[str, object]:
        return _duration_risk_upstream(
            report_date,
            bond_count=0,
            quality_flag="warning",
        )

    risk_service_module = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    monkeypatch.setattr(service_module, "RiskTensorRepository", StubRiskTensorRepository)
    monkeypatch.setattr(risk_service_module, "risk_tensor_envelope", fake_risk_tensor_envelope)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="组合久期和DV01风险怎么样")
    )

    assert envelope.result_meta.result_kind == "agent.duration_risk"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.evidence.evidence_rows == 0
    assert all(card.spec is None or "metric_id" not in card.spec for card in envelope.cards)
    assert "没有可用的风险张量债券数据" in envelope.answer


def test_duration_risk_preserves_valid_zero_dv01(tmp_path, monkeypatch):
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

    class StubRiskTensorRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

    def fake_risk_tensor_envelope(*, report_date: str, **_: object) -> dict[str, object]:
        upstream = _duration_risk_upstream(report_date)
        result = upstream["result"]
        assert isinstance(result, dict)
        result["portfolio_dv01"] = {
            "raw": 0.0,
            "unit": "dv01",
            "display": "0.00",
            "precision": 2,
            "sign_aware": False,
        }
        return upstream

    risk_service_module = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    monkeypatch.setattr(service_module, "RiskTensorRepository", StubRiskTensorRepository)
    monkeypatch.setattr(risk_service_module, "risk_tensor_envelope", fake_risk_tensor_envelope)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="组合久期和DV01风险怎么样")
    )

    dv01_card = next(card for card in envelope.cards if card.title == "Portfolio DV01")
    assert envelope.result_meta.formal_use_allowed is True
    assert dv01_card.spec["numeric"]["raw"] == 0.0
    assert dv01_card.spec["numeric"]["display"] == "0.00"


@pytest.mark.parametrize(
    "field_name",
    [
        "portfolio_modified_duration",
        "portfolio_dv01",
        "portfolio_convexity",
        "rate_risk_market_value",
        "duration_excluded_market_value",
    ],
)
def test_duration_risk_missing_required_numeric_raw_fails_closed(
    tmp_path,
    monkeypatch,
    field_name: str,
):
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

    class StubRiskTensorRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

    def fake_risk_tensor_envelope(*, report_date: str, **_: object) -> dict[str, object]:
        upstream = _duration_risk_upstream(report_date)
        result = upstream["result"]
        assert isinstance(result, dict)
        numeric = dict(result[field_name])
        numeric["raw"] = None
        result[field_name] = numeric
        return upstream

    risk_service_module = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    monkeypatch.setattr(service_module, "RiskTensorRepository", StubRiskTensorRepository)
    monkeypatch.setattr(risk_service_module, "risk_tensor_envelope", fake_risk_tensor_envelope)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="组合久期和DV01风险怎么样")
    )

    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert "Numeric contract 不完整" in envelope.answer
    assert not any(card.type == "metric" for card in envelope.cards)
    status_card = next(card for card in envelope.cards if card.type == "status")
    assert status_card.title == "Duration Numeric Contract Incomplete"


def test_duration_risk_missing_required_numeric_display_fails_closed(tmp_path, monkeypatch):
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

    class StubRiskTensorRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

    def fake_risk_tensor_envelope(*, report_date: str, **_: object) -> dict[str, object]:
        upstream = _duration_risk_upstream(report_date)
        result = upstream["result"]
        assert isinstance(result, dict)
        numeric = dict(result["portfolio_dv01"])
        numeric["display"] = ""
        result["portfolio_dv01"] = numeric
        return upstream

    risk_service_module = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    monkeypatch.setattr(service_module, "RiskTensorRepository", StubRiskTensorRepository)
    monkeypatch.setattr(risk_service_module, "risk_tensor_envelope", fake_risk_tensor_envelope)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="组合久期和DV01风险怎么样")
    )

    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert "missing raw/display values" in (envelope.cards[0].value or "").lower()
    assert not any(card.type == "metric" for card in envelope.cards)


def test_duration_risk_wrong_required_numeric_unit_fails_closed(tmp_path, monkeypatch):
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

    class StubRiskTensorRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

    def fake_risk_tensor_envelope(*, report_date: str, **_: object) -> dict[str, object]:
        upstream = _duration_risk_upstream(report_date)
        result = upstream["result"]
        assert isinstance(result, dict)
        numeric = dict(result["rate_risk_market_value"])
        numeric["unit"] = "ratio"
        result["rate_risk_market_value"] = numeric
        return upstream

    risk_service_module = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    monkeypatch.setattr(service_module, "RiskTensorRepository", StubRiskTensorRepository)
    monkeypatch.setattr(risk_service_module, "risk_tensor_envelope", fake_risk_tensor_envelope)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="组合久期和DV01风险怎么样")
    )

    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert "suppressed" in (envelope.result_meta.amount_currency_basis_note or "").lower()
    assert not any(card.type == "metric" for card in envelope.cards)


def test_duration_risk_native_currency_request_fails_closed(tmp_path, monkeypatch):
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

    class StubRiskTensorRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

    def fake_risk_tensor_envelope(*, report_date: str, **_: object) -> dict[str, object]:
        return _duration_risk_upstream(report_date)

    risk_service_module = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    monkeypatch.setattr(service_module, "RiskTensorRepository", StubRiskTensorRepository)
    monkeypatch.setattr(risk_service_module, "risk_tensor_envelope", fake_risk_tensor_envelope)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="组合久期和DV01风险怎么样",
            currency_basis="native",
        )
    )

    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.result_meta.amount_currency_basis == "CNY"
    assert all(card.spec is None or "metric_id" not in card.spec for card in envelope.cards)
    assert "native" in envelope.answer
    assert "Risk Tensor 仅提供 CNY" in envelope.answer


@pytest.mark.parametrize("historical_date", ["2024-01-01", "2025-11-20", "2026-02-28"])
def test_duration_risk_uses_explicit_historical_report_date_when_governed(
    tmp_path,
    monkeypatch,
    historical_date: str,
):
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

    calls: list[str] = []

    class StubRiskTensorRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31", "2025-11-20", "2026-02-28", "2024-01-01"]

    def fake_risk_tensor_envelope(*, report_date: str, **_: object) -> dict[str, object]:
        calls.append(report_date)
        return _duration_risk_upstream(report_date)

    risk_service_module = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    monkeypatch.setattr(service_module, "RiskTensorRepository", StubRiskTensorRepository)
    monkeypatch.setattr(risk_service_module, "risk_tensor_envelope", fake_risk_tensor_envelope)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="组合久期和DV01风险怎么样",
            filters={"report_date": historical_date},
        )
    )

    assert calls == [historical_date]
    assert envelope.result_meta.result_kind == "agent.duration_risk"
    assert envelope.result_meta.filters_applied["report_date"] == historical_date
    assert envelope.result_meta.filters_applied["report_date_resolution"] == "explicit"
    assert envelope.result_meta.requested_report_date == historical_date
    assert envelope.result_meta.resolved_report_date == historical_date
    assert envelope.result_meta.fallback_date is None


def test_duration_risk_returns_error_envelope_when_explicit_date_not_governed(tmp_path, monkeypatch):
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

    class StubRiskTensorRepository:
        def __init__(self, path: str):
            pass

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

    def fail_risk_tensor_envelope(**_: object) -> dict[str, object]:
        raise AssertionError("should not query")

    risk_service_module = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    monkeypatch.setattr(service_module, "RiskTensorRepository", StubRiskTensorRepository)
    monkeypatch.setattr(risk_service_module, "risk_tensor_envelope", fail_risk_tensor_envelope)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="组合久期和DV01风险怎么样",
            filters={"report_date": "2025-11-20"},
        )
    )

    assert envelope.result_meta.result_kind == "agent.duration_risk"
    assert envelope.result_meta.formal_use_allowed is False
    assert "2025-11-20" in envelope.answer
    assert "governed dates" in envelope.answer


def test_gitnexus_intent_reads_repo_index_metadata_from_question_path(tmp_path, monkeypatch):
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

    repo_path = tmp_path / "gitnexus-demo-repo"
    gitnexus_dir = repo_path / ".gitnexus"
    wiki_dir = gitnexus_dir / "wiki"
    wiki_dir.mkdir(parents=True)
    (gitnexus_dir / "meta.json").write_text(
        json.dumps(
            {
                "repoPath": str(repo_path),
                "lastCommit": "10aa27673481f5c024642d0a1990a01954ad09e3",
                "indexedAt": "2026-03-15T13:33:15.839Z",
                "stats": {
                    "files": 1934,
                    "nodes": 8462,
                    "edges": 23878,
                    "communities": 756,
                    "processes": 300,
                },
            }
        ),
        encoding="utf-8",
    )
    (repo_path / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "gitnexus": {
                        "command": "npx",
                        "args": ["-y", "gitnexus@latest", "mcp"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_GITNEXUS_ALLOWED_REPO_ROOTS", str(tmp_path))
    (wiki_dir / "overview.md").write_text("# Overview", encoding="utf-8")
    (wiki_dir / "flows.md").write_text("# Flows", encoding="utf-8")

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question=rf"{repo_path}\.gitnexus 请给我看 GitNexus 仓库图谱状态",
        )
    )

    assert envelope.result_meta.result_kind == "agent.gitnexus_status"
    assert envelope.result_meta.basis == "analytical"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.filters_applied["repo_path"] == str(repo_path)
    assert envelope.evidence.tables_used == [".gitnexus/meta.json", ".mcp.json", ".gitnexus/wiki"]
    assert any(card.title == "Nodes" and card.value == "8462" for card in envelope.cards)
    assert any(card.title == "Processes" and card.value == "300" for card in envelope.cards)
    assert any(card.title == "MCP GitNexus" and card.value == "enabled" for card in envelope.cards)
    assert any(card.title == "Wiki Documents" and card.value == "2" for card in envelope.cards)
    assert any(
        card.title == "GitNexus Context"
        and card.value == f"gitnexus://repo/{repo_path.name}/context"
        for card in envelope.cards
    )
    assert any(
        card.title == "GitNexus Processes"
        and card.value == f"gitnexus://repo/{repo_path.name}/processes"
        for card in envelope.cards
    )
    assert "GitNexus 索引状态已返回" in envelope.answer


def test_gitnexus_intent_prefers_explicit_repo_path_filter_over_question_text(tmp_path, monkeypatch):
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

    wrong_repo = tmp_path / "wrong-repo"
    right_repo = tmp_path / "right-repo"
    for repo_path, nodes in ((wrong_repo, 11), (right_repo, 22)):
        gitnexus_dir = repo_path / ".gitnexus"
        gitnexus_dir.mkdir(parents=True)
        (gitnexus_dir / "meta.json").write_text(
            json.dumps(
                {
                    "repoPath": str(repo_path),
                    "indexedAt": "2026-03-15T13:33:15.839Z",
                    "stats": {
                        "nodes": nodes,
                        "edges": 99,
                        "communities": 3,
                        "processes": 4,
                    },
                }
            ),
            encoding="utf-8",
        )
    monkeypatch.setenv("MOSS_GITNEXUS_ALLOWED_REPO_ROOTS", str(tmp_path))

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question=rf"{wrong_repo}\.gitnexus 请给我看 GitNexus processes",
            filters={"repo_path": str(right_repo)},
        )
    )

    assert envelope.result_meta.filters_applied["repo_path"] == str(right_repo)


def test_gitnexus_intent_rejects_repo_path_outside_allowed_root(tmp_path):
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

    with tempfile.TemporaryDirectory(prefix="moss-gitnexus-outside-") as outside_root:
        outside_repo = Path(outside_root) / "outside-repo"
        (outside_repo / ".gitnexus").mkdir(parents=True)
        (outside_repo / ".gitnexus" / "meta.json").write_text(
            json.dumps(
                {
                    "repoPath": str(outside_repo),
                    "indexedAt": "2026-03-15T13:33:15.839Z",
                    "stats": {"nodes": 1, "edges": 1, "communities": 1, "processes": 1},
                }
            ),
            encoding="utf-8",
        )

        tool = tool_module.AnalysisViewTool(
            "test.duckdb",
            str(tmp_path),
            intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
        )
        envelope = tool.execute(
            request_module.AgentQueryRequest(
                question="GitNexus repo status",
                filters={"repo_path": str(outside_repo)},
            )
        )

        assert envelope.result_meta.result_kind == "agent.gitnexus_status"
        assert envelope.result_meta.quality_flag == "error"
        assert "outside allowed roots" in envelope.answer


def test_gitnexus_intent_expands_mcp_context_and_processes_into_structured_cards(tmp_path, monkeypatch):
    gitnexus_service_module = load_module(
        "backend.app.services.gitnexus_service",
        "backend/app/services/gitnexus_service.py",
    )
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

    repo_path = tmp_path / "mcp-repo"
    gitnexus_dir = repo_path / ".gitnexus"
    gitnexus_dir.mkdir(parents=True)
    (gitnexus_dir / "meta.json").write_text(
        json.dumps(
            {
                "repoPath": str(repo_path),
                "indexedAt": "2026-03-15T13:33:15.839Z",
                "stats": {"nodes": 100, "edges": 200, "communities": 3, "processes": 4},
            }
        ),
        encoding="utf-8",
    )
    (repo_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"gitnexus": {"command": "npx", "args": ["-y", "gitnexus@latest", "mcp"]}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_GITNEXUS_ALLOWED_REPO_ROOTS", str(tmp_path))

    class StubGitNexusMcpClient:
        def __init__(self, target_repo_path):
            assert str(target_repo_path) == str(repo_path)

        def read_bundle(self, process_name=None):
            assert process_name is None
            return {
                "repo_name": "mcp-repo",
                "context": {
                    "project": "mcp-repo",
                    "stats": {"files": 10, "symbols": 20, "processes": 4},
                    "tools": [
                        {"name": "query", "description": "Process-grouped code intelligence"},
                        {"name": "context", "description": "360-degree symbol view"},
                    ],
                    "resources": [
                        {"uri": "gitnexus://repo/mcp-repo/context", "description": "overview"},
                        {"uri": "gitnexus://repo/mcp-repo/processes", "description": "flows"},
                    ],
                },
                "processes": [
                    {"name": "CheckoutFlow", "type": "cross_community", "steps": 6},
                    {"name": "AuditFlow", "type": "intra_community", "steps": 3},
                ],
                "process": None,
            }

    monkeypatch.setattr(gitnexus_service_module, "GitNexusMcpClient", StubGitNexusMcpClient)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="请给我看 GitNexus context 和 processes",
            filters={"repo_path": str(repo_path)},
        )
    )

    assert any(card.title == "GitNexus Tools" and card.type == "table" for card in envelope.cards)
    assert any(card.title == "GitNexus Resources" and card.type == "table" for card in envelope.cards)
    assert any(card.title == "GitNexus Processes Table" and card.type == "table" for card in envelope.cards)

    tools_card = next(card for card in envelope.cards if card.title == "GitNexus Tools")
    assert tools_card.data[0]["tool"] == "query"
    processes_card = next(card for card in envelope.cards if card.title == "GitNexus Processes Table")
    assert processes_card.data[0]["name"] == "CheckoutFlow"


def test_gitnexus_mcp_command_ignores_repo_local_executable_config(tmp_path):
    mcp_module = load_module(
        "backend.app.services.gitnexus_mcp_client",
        "backend/app/services/gitnexus_mcp_client.py",
    )
    repo_path = tmp_path / "malicious-repo"
    repo_path.mkdir()
    (repo_path / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "gitnexus": {
                        "command": "malicious.exe",
                        "args": ["--run-me"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    command = mcp_module._resolve_gitnexus_command(repo_path)

    assert command != ["malicious.exe", "--run-me"]
    assert command[:2] == ["node", "scripts/mcp/gitnexus_mcp_launcher.mjs"]


def test_gitnexus_intent_reads_specific_process_trace_from_mcp(tmp_path, monkeypatch):
    gitnexus_service_module = load_module(
        "backend.app.services.gitnexus_service",
        "backend/app/services/gitnexus_service.py",
    )
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

    repo_path = tmp_path / "mcp-process-repo"
    gitnexus_dir = repo_path / ".gitnexus"
    gitnexus_dir.mkdir(parents=True)
    (gitnexus_dir / "meta.json").write_text(
        json.dumps(
            {
                "repoPath": str(repo_path),
                "indexedAt": "2026-03-15T13:33:15.839Z",
                "stats": {"nodes": 100, "edges": 200, "communities": 3, "processes": 4},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_GITNEXUS_ALLOWED_REPO_ROOTS", str(tmp_path))

    class StubGitNexusMcpClient:
        def __init__(self, target_repo_path):
            assert str(target_repo_path) == str(repo_path)

        def read_bundle(self, process_name=None):
            assert process_name == "CheckoutFlow"
            return {
                "repo_name": "mcp-process-repo",
                "context": None,
                "processes": [],
                "process": {
                    "name": "CheckoutFlow",
                    "type": "cross_community",
                    "step_count": 3,
                    "trace": [
                        {"step": 1, "symbol": "start_checkout", "file": "backend/app/api.py"},
                        {"step": 2, "symbol": "calculate_total", "file": "backend/app/services/order.py"},
                        {"step": 3, "symbol": "save_order", "file": "backend/app/repositories/order_repo.py"},
                    ],
                },
            }

    monkeypatch.setattr(gitnexus_service_module, "GitNexusMcpClient", StubGitNexusMcpClient)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="请给我看 GitNexus process",
            filters={"repo_path": str(repo_path), "process_name": "CheckoutFlow"},
        )
    )

    process_card = next(card for card in envelope.cards if card.title == "GitNexus Process Trace")
    assert process_card.type == "table"
    assert process_card.data[1]["symbol"] == "calculate_total"
    assert process_card.data[0]["module_group"] == "api"
    assert process_card.data[0]["edge_label"] == "api -> services"
    assert process_card.data[1]["module_group"] == "services"
    assert process_card.data[1]["edge_label"] == "services -> repositories"
    assert process_card.data[2]["module_group"] == "repositories"
    assert process_card.data[2]["edge_label"] == ""
    assert process_card.spec["columns"] == ["step", "symbol", "file", "module_group", "edge_label"]


def test_gitnexus_intent_parses_process_name_from_question(tmp_path, monkeypatch):
    gitnexus_service_module = load_module(
        "backend.app.services.gitnexus_service",
        "backend/app/services/gitnexus_service.py",
    )
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

    repo_path = tmp_path / "mcp-process-question-repo"
    gitnexus_dir = repo_path / ".gitnexus"
    gitnexus_dir.mkdir(parents=True)
    (gitnexus_dir / "meta.json").write_text(
        json.dumps(
            {
                "repoPath": str(repo_path),
                "indexedAt": "2026-03-15T13:33:15.839Z",
                "stats": {"nodes": 100, "edges": 200, "communities": 3, "processes": 4},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_GITNEXUS_ALLOWED_REPO_ROOTS", str(tmp_path))

    class StubGitNexusMcpClient:
        def __init__(self, target_repo_path):
            assert str(target_repo_path) == str(repo_path)

        def read_bundle(self, process_name=None):
            assert process_name == "CheckoutFlow"
            return {
                "repo_name": "mcp-process-question-repo",
                "context": None,
                "processes": [],
                "process": {
                    "name": "CheckoutFlow",
                    "type": "cross_community",
                    "step_count": 1,
                    "trace": [{"step": 1, "symbol": "start_checkout", "file": "backend/app/api.py"}],
                },
            }

    monkeypatch.setattr(gitnexus_service_module, "GitNexusMcpClient", StubGitNexusMcpClient)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="请给我看 GitNexus process/CheckoutFlow",
            filters={"repo_path": str(repo_path)},
        )
    )

    assert envelope.result_meta.filters_applied["process_name"] == "CheckoutFlow"
    process_card = next(card for card in envelope.cards if card.title == "GitNexus Process Trace")
    assert process_card.data[0]["symbol"] == "start_checkout"
    assert process_card.data[0]["module_group"] == "api"
    assert process_card.data[0]["edge_label"] == ""


def test_unknown_intent_returns_help_message(tmp_path):
    module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = module.AnalysisViewTool("test.duckdb", str(tmp_path))
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="帮我算一个目前不支持的复杂策略")
    )

    assert "暂不支持该类查询" in envelope.answer
    assert envelope.result_meta.result_kind == "agent.unknown"
    assert envelope.evidence.evidence_rows == 0
    assert any(card.title == "Supported Queries" for card in envelope.cards)


def test_ordinary_analysis_question_returns_local_conversation_envelope(tmp_path):
    module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = module.AnalysisViewTool("test.duckdb", str(tmp_path))
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="please analyze the main risk and explain what it means",
            page_context={
                "page_id": "dashboard",
                "current_filters": {"report_date": "2026-03-31"},
                "selected_rows": [{"portfolio_id": "core"}],
                "context_note": "dashboard first screen",
            },
        )
    )

    assert envelope.result_meta.result_kind == "agent.analysis_chat"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.evidence.tables_used == []
    assert envelope.evidence.evidence_rows == 0
    assert envelope.evidence.evidence_strength == "local_fallback"
    assert envelope.result_meta.evidence_strength == "local_fallback"
    assert envelope.evidence.filters_applied == {
        "page_id": "dashboard",
        "report_date": "2026-03-31",
        "selected_rows": 1,
    }
    assert "did not run a formal metric query" in envelope.answer
    assert any(card.title == "Local Analysis Conversation" for card in envelope.cards)
    assert any(card.title == "Available Governed Paths" for card in envelope.cards)


def test_chinese_ordinary_analysis_question_gets_chinese_local_answer(tmp_path):
    module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = module.AnalysisViewTool("test.duckdb", str(tmp_path))
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="\u5e2e\u6211\u5224\u65ad\u4eca\u5929\u7684\u4e3b\u8981\u98ce\u9669",
            context={
                "conversation": {
                    "recent_turns": [
                        {
                            "question": "\u5148\u524d\u7684\u98ce\u9669\u7ed3\u8bba",
                            "answer": "\u4e0a\u4e00\u8f6e\u56de\u7b54",
                            "result_kind": "agent.analysis_chat",
                        }
                    ]
                }
            },
        )
    )

    assert envelope.result_meta.result_kind == "agent.analysis_chat"
    assert "\u672c\u5730\u5206\u6790\u5bf9\u8bdd" in envelope.answer
    assert "\u672a\u8fd0\u884c\u6b63\u5f0f\u6307\u6807\u67e5\u8be2" in envelope.answer
    assert envelope.evidence.filters_applied["conversation_turns"] == 1
    assert envelope.evidence.filters_applied["latest_result_kind"] == "agent.analysis_chat"
    assert any(card.title == "\u672c\u5730\u5206\u6790\u5bf9\u8bdd" for card in envelope.cards)
    assert any(card.title == "\u53ef\u7ee7\u7eed\u67e5\u8be2\u7684\u6cbb\u7406\u8def\u5f84" for card in envelope.cards)
    assert any(action.label == "\u7ec4\u5408\u6982\u89c8" for action in envelope.suggested_actions)


def test_financial_workflow_context_returns_plan_envelope(tmp_path):
    module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = module.AnalysisViewTool("test.duckdb", str(tmp_path))
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="Prepare a risk memo plan",
            basis="scenario",
            context={"workflow_id": "risk_memo"},
        )
    )

    assert envelope.result_meta.result_kind == "agent.workflow.risk_memo"
    assert envelope.result_meta.basis == "scenario"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.source_version == "sv_anthropic_financial_workflow_reference"
    assert envelope.result_meta.rule_version == "rv_agent_financial_workflow_catalog_v1"
    assert envelope.evidence.tables_used == []
    assert envelope.evidence.evidence_rows == 0
    assert envelope.evidence.quality_flag == "warning"
    assert [card.title for card in envelope.cards] == [
        "Workflow Plan",
        "Mapped MOSS Intents",
        "Governance Notes",
    ]
    assert envelope.cards[1].data == [
        {"order": 1, "intent": "duration_risk"},
        {"order": 2, "intent": "credit_exposure"},
        {"order": 3, "intent": "risk_tensor"},
    ]
    assert envelope.suggested_actions[0].type == "execute_intent"
    assert envelope.suggested_actions[0].payload["intent"] == "duration_risk"
    assert envelope.suggested_actions[0].confirmation_token
    assert agent_action_confirmation_token_matches(
        token=envelope.suggested_actions[0].confirmation_token,
        action_type=envelope.suggested_actions[0].type,
        label=envelope.suggested_actions[0].label,
        payload=envelope.suggested_actions[0].payload,
    )


def test_financial_workflow_slash_command_returns_plan_envelope(tmp_path):
    module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    tool = module.AnalysisViewTool("test.duckdb", str(tmp_path))
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="/pnl-review for March close")
    )

    assert envelope.result_meta.result_kind == "agent.workflow.pnl_review"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.evidence.evidence_rows == 0
    assert envelope.suggested_actions[0].payload["intent"] == "pnl_summary"
    assert envelope.suggested_actions[0].confirmation_token


def test_unknown_workflow_id_falls_back_to_existing_intent_routing(tmp_path):
    module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    calls: list[str] = []
    tool = module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "pnl_summary": lambda request: {
                "answer": "ok",
                "basis": "formal",
                "result_kind": "agent.pnl_summary",
                "formal_use_allowed": True,
                "source_version": "sv_test",
                "quality_flag": "ok",
                "row_count": calls.append(request.context["workflow_id"]) or 1,
                "cards": [{"type": "metric", "title": "Total PnL", "value": "1"}],
            }
        },
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="PnL summary",
            context={"workflow_id": "not_registered"},
        )
    )

    assert calls == ["not_registered"]
    assert envelope.result_meta.result_kind == "agent.pnl_summary"
    assert envelope.result_meta.formal_use_allowed is True


def test_financial_workflow_execute_mode_runs_mapped_intents_in_order(tmp_path):
    module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    calls: list[str] = []

    def handler(intent: str):
        def _inner(request):
            calls.append(intent)
            return {
                "answer": f"{intent} result",
                "basis": "formal",
                "result_kind": f"agent.{intent}",
                "formal_use_allowed": True,
                "source_version": f"sv_{intent}",
                "rule_version": "rv_test",
                "cache_version": f"cv_{intent}",
                "quality_flag": "ok",
                "row_count": 2,
                "tables_used": [f"fact_{intent}"],
                "filters_applied": {"intent": intent},
                "cards": [{"type": "metric", "title": intent, "value": "2"}],
            }

        return _inner

    tool = module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "duration_risk": handler("duration_risk"),
            "credit_exposure": handler("credit_exposure"),
            "risk_tensor": handler("risk_tensor"),
        },
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="/risk-memo",
            context={"workflow_mode": "execute"},
        )
    )

    assert calls == ["duration_risk", "credit_exposure", "risk_tensor"]
    assert envelope.result_meta.result_kind == "agent.workflow.risk_memo"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "ok"
    assert envelope.evidence.evidence_rows == 6
    assert envelope.evidence.tables_used == [
        "fact_duration_risk",
        "fact_credit_exposure",
        "fact_risk_tensor",
    ]
    steps_card = next(card for card in envelope.cards if card.title == "Workflow Execution Steps")
    assert steps_card.data == [
        {"order": 1, "intent": "duration_risk", "status": "ok", "quality_flag": "ok", "evidence_rows": 2},
        {"order": 2, "intent": "credit_exposure", "status": "ok", "quality_flag": "ok", "evidence_rows": 2},
        {"order": 3, "intent": "risk_tensor", "status": "ok", "quality_flag": "ok", "evidence_rows": 2},
    ]
    memo_card = envelope.cards[0]
    assert memo_card.title == "Workflow Memo"
    assert memo_card.type == "markdown"
    assert "duration_risk result" in memo_card.value
    assert "credit_exposure result" in memo_card.value
    assert "risk_tensor result" in memo_card.value
    assert "数据质量提示" not in memo_card.value
    assert "非正式结果，仅供分析参考（formal_use_allowed=false）" in memo_card.value
    assert envelope.suggested_actions == []


def test_financial_workflow_execute_mode_reports_step_failure_without_side_effects(tmp_path):
    module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    def ok_handler(request):
        return {
            "answer": "duration ok",
            "basis": "formal",
            "result_kind": "agent.duration_risk",
            "formal_use_allowed": True,
            "source_version": "sv_duration",
            "quality_flag": "ok",
            "row_count": 1,
            "tables_used": ["fact_duration"],
            "cards": [{"type": "metric", "title": "Duration", "value": "1"}],
        }

    def failing_handler(request):
        raise ValueError("No governed risk tensor date is available.")

    tool = module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "duration_risk": ok_handler,
            "credit_exposure": ok_handler,
            "risk_tensor": failing_handler,
        },
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="/risk-memo",
            context={"workflow_mode": "execute"},
        )
    )

    assert envelope.result_meta.result_kind == "agent.workflow.risk_memo"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.evidence.evidence_rows == 2
    steps_card = next(card for card in envelope.cards if card.title == "Workflow Execution Steps")
    assert steps_card.data[-1] == {
        "order": 3,
        "intent": "risk_tensor",
        "status": "error",
        "quality_flag": "warning",
        "evidence_rows": 0,
    }
    memo_card = next(card for card in envelope.cards if card.title == "Workflow Memo")
    assert memo_card.type == "markdown"
    assert "duration ok" in memo_card.value
    assert "risk_tensor: 执行失败" in memo_card.value
    assert "数据质量提示" in memo_card.value
    assert "非正式结果，仅供分析参考（formal_use_allowed=false）" in memo_card.value
    assert "risk_tensor" in envelope.answer


def test_manual_intent_result_meta_stays_formal_for_scenario_request(tmp_path, monkeypatch):
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

    class StubPnlRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_union_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def overview_totals(self, report_date: str) -> dict[str, object]:
            return {
                "formal_fi_row_count": 1,
                "nonstd_bridge_row_count": 0,
                "interest_income_514": 10,
                "fair_value_change_516": 0,
                "capital_gain_517": 0,
                "manual_adjustment": 0,
                "total_pnl": 10,
            }

    monkeypatch.setattr(service_module, "PnlRepository", StubPnlRepository)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="PnL summary",
            basis="scenario",
        )
    )

    assert envelope.result_meta.basis == "formal"
    assert envelope.result_meta.formal_use_allowed is True
    assert envelope.result_meta.scenario_flag is False


def test_audit_log_is_appended(tmp_path, monkeypatch):
    service_module = load_module(
        "backend.app.services.agent_service",
        "backend/app/services/agent_service.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )
    response_module = load_module(
        "backend.app.agent.schemas.agent_response",
        "backend/app/agent/schemas/agent_response.py",
    )

    class StubRegistry:
        def __init__(self, duckdb_path: str, governance_dir: str, intent_handlers=None):
            assert duckdb_path == "test.duckdb"
            assert governance_dir == str(tmp_path)

        def execute_query(self, request):
            return response_module.AgentEnvelope(
                answer="ok",
                cards=[],
                evidence=response_module.AgentEvidence(
                    tables_used=["fact_formal_pnl_fi"],
                    filters_applied={"report_date": "2026-03-31"},
                    evidence_rows=1,
                    quality_flag="ok",
                ),
                result_meta=response_module.AgentResultMeta(
                    trace_id="tr_agent_audit",
                    basis="formal",
                    result_kind="agent.pnl_summary",
                    formal_use_allowed=True,
                    source_version="sv_agent_test",
                    vendor_version="vv_none",
                    rule_version="rv_agent_mvp_v1",
                    cache_version="cv_agent_pnl_summary_v1",
                    quality_flag="ok",
                    scenario_flag=False,
                    tables_used=["fact_formal_pnl_fi"],
                    filters_applied={"report_date": "2026-03-31"},
                    sql_executed=[],
                    evidence_rows=1,
                ),
            )

    monkeypatch.setattr(service_module, "ToolRegistry", StubRegistry)

    service_module.execute_agent_query(
        request_module.AgentQueryRequest(
            question="PnL summary",
            context={"user_id": "u_test"},
        ),
        duckdb_path="test.duckdb",
        governance_dir=str(tmp_path),
    )

    content = (tmp_path / "agent_audit.jsonl").read_text(encoding="utf-8")
    payload = json.loads(content.splitlines()[-1])
    assert payload["user_id"] == "u_test"
    assert payload["query_text"] == "PnL summary"
    assert payload["tools_used"] == ["analysis_view_tool", "evidence_tool", "intent:pnl_summary"]
    assert payload["tables_used"] == ["fact_formal_pnl_fi"]
    assert payload["trace_id"] == "tr_agent_audit"
