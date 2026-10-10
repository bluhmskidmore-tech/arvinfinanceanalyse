from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tests.helpers import load_module
from backend.app.agent.runtime.action_token import agent_action_confirmation_token_matches

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


def _balance_overview_upstream(
    *,
    overview: dict[str, object],
    report_date: str,
    position_scope: str,
    currency_basis: str,
) -> dict[str, object]:
    return {
        "result": {
            "report_date": report_date,
            "position_scope": position_scope,
            "currency_basis": currency_basis,
            "detail_row_count": overview.get("detail_row_count", 0),
            "summary_row_count": overview.get("summary_row_count", 1),
            "total_market_value_amount": overview.get("total_market_value_amount"),
            "total_amortized_cost_amount": overview.get("total_amortized_cost_amount"),
            "total_accrued_interest_amount": overview.get("total_accrued_interest_amount"),
        },
        "result_meta": {
            "basis": "formal",
            "formal_use_allowed": True,
            "scenario_flag": False,
            "source_version": overview.get("source_version") or "sv_balance_upstream",
            "vendor_version": "vv_none",
            "rule_version": overview.get("rule_version") or "rv_balance_upstream",
            "cache_version": "cv_balance_upstream",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "requested_report_date": report_date,
            "resolved_report_date": report_date,
            "as_of_date": report_date,
            "date_basis": "balance_analysis_report_date",
            "fallback_date": None,
            "source_surface": "formal_balance",
            "amount_currency_basis": currency_basis,
        },
    }


def _patch_balance_overview_envelope(monkeypatch, overview: dict[str, object]) -> None:
    balance_service_module = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    def fake_balance_overview_envelope(**kwargs: object) -> dict[str, object]:
        return _balance_overview_upstream(
            overview=overview,
            report_date=str(kwargs["report_date"]),
            position_scope=str(kwargs["position_scope"]),
            currency_basis=str(kwargs["currency_basis"]),
        )

    monkeypatch.setattr(
        balance_service_module,
        "balance_analysis_overview_envelope",
        fake_balance_overview_envelope,
    )


def _product_pnl_upstream(
    *,
    rows: list[dict[str, object]],
    report_date: str,
    view: str,
) -> dict[str, object]:
    asset_total = next((row for row in rows if row.get("category_id") == "asset_total"), {})
    liability_total = next((row for row in rows if row.get("category_id") == "liability_total"), {})
    grand_total = next((row for row in rows if row.get("category_id") == "grand_total"), {})
    return {
        "result": {
            "report_date": report_date,
            "view": view,
            "available_views": [view],
            "rows": rows,
            "asset_total": asset_total,
            "liability_total": liability_total,
            "grand_total": grand_total,
        },
        "result_meta": {
            "basis": "formal",
            "formal_use_allowed": bool(grand_total),
            "scenario_flag": False,
            "source_version": "sv_product_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_product_test",
            "cache_version": "cv_product_test",
            "quality_flag": "ok" if grand_total else "warning",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "requested_report_date": report_date,
            "resolved_report_date": report_date,
            "as_of_date": report_date,
            "date_basis": "product_category_report_date",
            "fallback_date": None,
            "source_surface": "formal_pnl",
        },
    }


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

    overview = {
        "detail_row_count": 3,
        "total_market_value_amount": 1000,
        "total_amortized_cost_amount": 950,
        "total_accrued_interest_amount": 12,
        "source_version": "sv_balance_1",
        "rule_version": "rv_balance_1",
    }

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
            return overview

    monkeypatch.setattr(service_module, "BalanceAnalysisRepository", StubBalanceAnalysisRepository)
    _patch_balance_overview_envelope(monkeypatch, overview)

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
            context={"user_id": "user_a"},
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

    overview = {
        "detail_row_count": 0,
        "total_market_value_amount": 0,
        "total_amortized_cost_amount": 0,
        "total_accrued_interest_amount": 0,
        "source_version": None,
        "rule_version": None,
    }

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
            return overview

    monkeypatch.setattr(service_module, "BalanceAnalysisRepository", EmptyBalanceAnalysisRepository)
    _patch_balance_overview_envelope(monkeypatch, overview)
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
            context={"user_id": "user_a"},
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

    overview = {
        "detail_row_count": 2,
        "total_market_value_amount": 1000,
        "total_amortized_cost_amount": 950,
        "total_accrued_interest_amount": 12,
        "source_version": "sv_native_1",
        "rule_version": "rv_native_1",
    }

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
            return overview

    monkeypatch.setattr(service_module, "BalanceAnalysisRepository", NativeBalanceAnalysisRepository)
    _patch_balance_overview_envelope(monkeypatch, overview)
    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="portfolio overview",
            currency_basis="native",
            context={"user_id": "user_a"},
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

    overview = {
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
            return overview

    monkeypatch.setattr(
        service_module,
        "BalanceAnalysisRepository",
        IncompleteLineageBalanceAnalysisRepository,
    )
    _patch_balance_overview_envelope(monkeypatch, overview)
    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="portfolio overview",
            currency_basis="CNY",
            context={"user_id": "user_a"},
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

    overview = {
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
            return overview

    monkeypatch.setattr(
        service_module,
        "BalanceAnalysisRepository",
        ZeroAmountBalanceAnalysisRepository,
    )
    _patch_balance_overview_envelope(monkeypatch, overview)
    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )

    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="portfolio overview",
            currency_basis="CNY",
            context={"user_id": "user_a"},
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

    overview = {
        "detail_row_count": 1,
        "total_market_value_amount": 800,
        "total_amortized_cost_amount": 790,
        "total_accrued_interest_amount": 6,
        "source_version": "sv_balance_2",
        "rule_version": "rv_balance_2",
    }

    class StubBalanceAnalysisRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def fetch_formal_overview(self, *, report_date: str, position_scope: str, currency_basis: str) -> dict[str, object]:
            calls.append((report_date, position_scope, currency_basis))
            return overview

    monkeypatch.setattr(service_module, "BalanceAnalysisRepository", StubBalanceAnalysisRepository)
    _patch_balance_overview_envelope(monkeypatch, overview)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="portfolio market value",
            context={"user_id": "user_a"},
        )
    )

    assert calls == [("2026-03-31", "all", "CNY")]
    assert envelope.evidence.filters_applied["currency_basis"] == "CNY"
    assert envelope.result_meta.result_kind == "agent.portfolio_overview"
    assert any(card.title == "Total Market Value" for card in envelope.cards)


@pytest.mark.parametrize(
    ("question", "page_id", "expected_route", "expected_intent"),
    [
        ("context", None, "provider", None),
        ("processes", None, "provider", None),
        ("duration", None, "provider", None),
        ("market value", None, "provider", None),
        ("decode context", None, "provider", None),
        ("report processes", None, "provider", None),
        ("brisk duration", None, "provider", None),
        ("fundamental market value", None, "provider", None),
        ("GitNexus context", None, "local", "gitnexus_status"),
        ("repository processes", None, "local", "gitnexus_status"),
        ("bond duration", None, "local", "duration_risk"),
        ("portfolio market value", None, "local", "portfolio_overview"),
        ("duration", "bond-analytics", "local", "duration_risk"),
        ("market value", "dashboard", "local", "portfolio_overview"),
    ],
)
def test_ambiguous_english_intent_terms_require_domain_or_page_context(
    question,
    page_id,
    expected_route,
    expected_intent,
):
    resolution_module = load_module(
        "backend.app.agent.runtime.local_request_resolution",
        "backend/app/agent/runtime/local_request_resolution.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )
    page_context = (
        request_module.AgentPageContext(page_id=page_id)
        if page_id is not None
        else None
    )

    resolution = resolution_module.resolve_local_request(
        request_module.AgentQueryRequest(
            question=question,
            page_context=page_context,
        )
    )

    assert resolution.route == expected_route
    assert resolution.intent == expected_intent


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
        # 不带「今日」等相对日词：报告日绑定型意图才允许沿用 latest 兜底。
        ("\u8bf7\u6c47\u603b\u635f\u76ca", "agent.pnl_summary"),
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
                            "trace_id": "tr_agent_duration_risk_0123456789ab",
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


def test_follow_up_does_not_reuse_agent_marker_quoted_in_free_text_answer():
    resolution_module = load_module(
        "backend.app.agent.runtime.local_request_resolution",
        "backend/app/agent/runtime/local_request_resolution.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    resolution = resolution_module.resolve_local_request(
        request_module.AgentQueryRequest(
            question="继续",
            context={
                "conversation": {
                    "recent_turns": [
                        {
                            "answer": (
                                "新闻摘录提到某系统返回了 agent.pnl_bridge 标记，"
                                "这里只是在长文本中引用该字面量，并非本轮结果元数据。"
                            ),
                        }
                    ]
                }
            },
        )
    )

    assert resolution.reason == "analysis_chat"
    assert resolution.intent == "analysis_chat"


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
            context={"user_id": "user_a"},
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
            context={"user_id": "user_a"},
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
        "confirmation_scope": {"user_id": "user_a"},
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
            context={"user_id": "user_a"},
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

    def fake_pnl_overview_envelope(*, report_date: str, **_: object) -> dict[str, object]:
        calls.append(report_date)
        return _formal_pnl_overview_upstream(report_date)

    pnl_service_module = load_module(
        "backend.app.services.pnl_service",
        "backend/app/services/pnl_service.py",
    )
    monkeypatch.setattr(
        pnl_service_module,
        "pnl_overview_envelope",
        fake_pnl_overview_envelope,
    )

    monkeypatch.setattr(service_module, "PnlRepository", StubPnlRepository)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="请给我看一下损益概览",
            context={"user_id": "user_a"},
        )
    )

    assert calls == ["2026-03-31"]
    assert envelope.result_meta.result_kind == "agent.pnl_summary"
    assert envelope.result_meta.basis == "formal"
    assert envelope.result_meta.filters_applied["report_date"] == "2026-03-31"
    assert envelope.result_meta.filters_applied["position_scope"] == "all"
    assert envelope.result_meta.filters_applied["currency_basis"] == "CNX"
    assert "requested_position_scope" not in envelope.result_meta.filters_applied
    assert "requested_currency_basis" not in envelope.result_meta.filters_applied
    assert envelope.evidence.tables_used == ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"]
    assert envelope.evidence.sql_executed
    assert all(sql.lower().startswith("select") for sql in envelope.evidence.sql_executed)
    assert any("from fact_formal_pnl_fi" in sql for sql in envelope.evidence.sql_executed)
    assert envelope.result_meta.sql_executed == envelope.evidence.sql_executed
    assert any(card.title == "Total PnL" for card in envelope.cards)


def _formal_pnl_overview_upstream(
    report_date: str,
    *,
    formal_fi_row_count: int = 2,
    nonstd_bridge_row_count: int = 1,
    formal_use_allowed: bool = True,
) -> dict[str, object]:
    return {
        "result": {
            "report_date": report_date,
            "formal_fi_row_count": formal_fi_row_count,
            "nonstd_bridge_row_count": nonstd_bridge_row_count,
            "interest_income_514": "10.00",
            "fair_value_change_516": "20.00",
            "capital_gain_517": "30.00",
            "manual_adjustment": "0.00",
            "total_pnl": "60.00",
            "reconciliation_checks": {},
        },
        "result_meta": {
            "trace_id": f"tr_pnl_overview_{report_date}",
            "basis": "formal",
            "result_kind": "pnl.overview",
            "formal_use_allowed": formal_use_allowed,
            "source_version": "sv_pnl_formal",
            "vendor_version": "vv_none",
            "rule_version": "rv_pnl_formal",
            "cache_version": "cv_pnl_formal",
            "cache_key": "pnl_materialized",
            "quality_flag": "ok" if formal_use_allowed else "warning",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "requested_report_date": report_date,
            "resolved_report_date": report_date,
            "as_of_date": report_date,
            "source_surface": "formal_pnl",
            "amount_currency_basis": "CNX",
            "amount_currency_basis_note": "Test fixture uses the requested CNX basis.",
            "generated_at": "2026-04-01T00:00:00Z",
            "data_built_at": "2026-03-31T23:00:00Z",
        },
    }


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
            "portfolio_modified_duration": numeric(4.1, "years", "4.10"),
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
        request_module.AgentQueryRequest(
            question="组合久期和DV01风险怎么样",
            context={"user_id": "user_a"},
        )
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
        "raw_unit": "years",
        "raw_precision": 2,
        "numeric": {
            "raw": 4.1,
            "unit": "years",
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
        request_module.AgentQueryRequest(
            question="组合久期和DV01风险怎么样",
            context={"user_id": "user_a"},
        )
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
        request_module.AgentQueryRequest(
            question="组合久期和DV01风险怎么样",
            context={"user_id": "user_a"},
        )
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
        request_module.AgentQueryRequest(
            question="组合久期和DV01风险怎么样",
            context={"user_id": "user_a"},
        )
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
        request_module.AgentQueryRequest(
            question="组合久期和DV01风险怎么样",
            context={"user_id": "user_a"},
        )
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
        request_module.AgentQueryRequest(
            question="组合久期和DV01风险怎么样",
            context={"user_id": "user_a"},
        )
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
            context={"user_id": "user_a"},
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
            context={"user_id": "user_a"},
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
            context={"user_id": "user_a"},
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
            context={"user_id": "user_a"},
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
            context={"user_id": "user_a"},
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
            context={"user_id": "user_a"},
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
            context={"user_id": "user_a"},
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
            context={"user_id": "user_a"},
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
                "user_id": "user_a",
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
            context={"workflow_id": "risk_memo", "user_id": "user_a"},
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
        request_module.AgentQueryRequest(
            question="/pnl-review for March close",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.result_meta.result_kind == "agent.workflow.pnl_review"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.evidence.evidence_rows == 0
    assert envelope.suggested_actions[0].payload["intent"] == "pnl_summary"
    assert envelope.suggested_actions[0].confirmation_token


def test_unknown_workflow_id_returns_error_envelope_instead_of_silent_fallback(tmp_path):
    """显式 workflow_id 未命中目录必须 fail-closed 返回错误 envelope，
    不再静默降级到问题级扫描（拼错的 id 曾被送去 provider 开放聊天）。"""
    module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    resolution_module = load_module(
        "backend.app.agent.runtime.local_request_resolution",
        "backend/app/agent/runtime/local_request_resolution.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    request = request_module.AgentQueryRequest(
        question="PnL summary",
        context={"workflow_id": "not_registered"},
    )
    resolution = resolution_module.resolve_local_request(request)
    assert resolution.route == "local"
    assert resolution.reason == "unknown_workflow"

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
    envelope = tool.execute(request)

    assert calls == []
    assert envelope.result_meta.result_kind == "agent.unknown_workflow"
    assert envelope.result_meta.quality_flag == "error"
    assert envelope.result_meta.formal_use_allowed is False
    assert "not_registered" in envelope.answer
    assert "portfolio_review" in envelope.answer
    assert "research_radar_brief" in envelope.answer


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

    monkeypatch.setattr(service_module, "PnlRepository", StubPnlRepository)
    pnl_service_module = load_module(
        "backend.app.services.pnl_service",
        "backend/app/services/pnl_service.py",
    )
    monkeypatch.setattr(
        pnl_service_module,
        "pnl_overview_envelope",
        lambda *, report_date, **_: _formal_pnl_overview_upstream(
            report_date,
            formal_fi_row_count=1,
            nonstd_bridge_row_count=0,
        ),
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="PnL summary",
            basis="scenario",
            context={"user_id": "user_a"},
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


@pytest.mark.parametrize(
    ("question", "expected_route", "expected_intent"),
    [
        # 「收益率」是市场/曲线语义，不得因包含「收益」误入 pnl_summary。
        ("国债收益率曲线怎么走", "local", "market_data"),
        ("最新收益率水平如何", "local", "market_data"),
        # 「利率风险」是利率风险语义，不得因包含「利率」误入 market_data。
        ("利率风险敞口有多大", "local", "duration_risk"),
        # 非「收益率」的「收益」仍保持 pnl_summary 既有优先级。
        ("请汇总收益", "local", "pnl_summary"),
        ("投资收益怎么样", "local", "pnl_summary"),
        # 普通利率问法仍归 market_data。
        ("今天的利率怎么样", "local", "market_data"),
    ],
)
def test_chinese_ambiguous_finance_terms_route_with_domain_guards(
    question,
    expected_route,
    expected_intent,
):
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


def test_risk_tensor_missing_formal_marker_fails_closed(tmp_path, monkeypatch):
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
        upstream = _duration_risk_upstream(report_date, quality_flag="ok")
        upstream["result_meta"].pop("formal_use_allowed")
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
        request_module.AgentQueryRequest(
            question="风险张量怎么样",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.result_meta.result_kind == "agent.risk_tensor"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert "缺少 formal_use_allowed" in envelope.answer
    assert "fail-closed" in envelope.answer


def test_pnl_bridge_missing_formal_marker_fails_closed(tmp_path, monkeypatch):
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

        def list_formal_fi_report_dates(self) -> list[str]:
            return ["2026-03-31"]

    def fake_pnl_bridge_envelope(*, report_date: str, **_: object) -> dict[str, object]:
        return {
            "result": {"summary": {"row_count": 3}},
            "result_meta": {
                "basis": "formal",
                "quality_flag": "ok",
                "source_version": "sv_bridge_test",
            },
        }

    bridge_service_module = load_module(
        "backend.app.services.pnl_bridge_service",
        "backend/app/services/pnl_bridge_service.py",
    )
    monkeypatch.setattr(service_module, "PnlRepository", StubPnlRepository)
    monkeypatch.setattr(bridge_service_module, "pnl_bridge_envelope", fake_pnl_bridge_envelope)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="请做归因拆解",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.result_meta.result_kind == "agent.pnl_bridge"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert "缺少 formal_use_allowed" in envelope.answer
    assert "fail-closed" in envelope.answer


def test_pnl_summary_without_formal_fi_rows_fails_closed(tmp_path, monkeypatch):
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

    monkeypatch.setattr(service_module, "PnlRepository", StubPnlRepository)
    pnl_service_module = load_module(
        "backend.app.services.pnl_service",
        "backend/app/services/pnl_service.py",
    )
    monkeypatch.setattr(
        pnl_service_module,
        "pnl_overview_envelope",
        lambda *, report_date, **_: _formal_pnl_overview_upstream(
            report_date,
            formal_fi_row_count=0,
            nonstd_bridge_row_count=3,
        ),
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="请汇总损益",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.result_meta.result_kind == "agent.pnl_summary"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert "没有正式 FI 明细" in envelope.answer


def test_credit_exposure_without_credit_rows_fails_closed(tmp_path, monkeypatch):
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

    class StubBondAnalyticsRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def fetch_credit_summary(self, *, report_date: str) -> dict[str, object]:
            return {
                "credit_bond_count": 0,
                "credit_market_value": None,
                "spread_dv01": None,
                "oci_credit_exposure": None,
            }

    monkeypatch.setattr(service_module, "BondAnalyticsRepository", StubBondAnalyticsRepository)
    bond_service_module = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    monkeypatch.setattr(
        bond_service_module,
        "bond_analytics_credit_exposure_governance_meta",
        lambda **_: {
            "basis": "formal",
            "formal_use_allowed": True,
            "scenario_flag": False,
            "source_version": "sv_bond_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_bond_test",
            "cache_version": "cv_bond_test",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
        },
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="信用暴露情况如何",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.result_meta.result_kind == "agent.credit_exposure"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert "没有受治理的信用债敞口记录" in envelope.answer


def test_product_pnl_missing_grand_total_row_fails_closed(tmp_path, monkeypatch):
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

    rows = [
        {
            "category_id": "asset_total",
            "business_net_income": "120.5",
            "source_version": "sv_product_test",
            "rule_version": "rv_product_test",
        }
    ]

    class StubProductCategoryPnlRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

    monkeypatch.setattr(
        service_module,
        "ProductCategoryPnlRepository",
        StubProductCategoryPnlRepository,
    )
    product_service_module = load_module(
        "backend.app.services.product_category_pnl_service",
        "backend/app/services/product_category_pnl_service.py",
    )
    monkeypatch.setattr(
        product_service_module,
        "product_category_pnl_envelope",
        lambda duckdb_path, *, report_date, view, scenario_rate_pct=None: _product_pnl_upstream(
            rows=rows,
            report_date=report_date,
            view=view,
        ),
    )

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="产品损益视图",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.result_meta.result_kind == "agent.product_pnl"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.quality_flag == "warning"
    assert "缺少 grand_total 汇总行" in envelope.answer
    grand_total_card = next(card for card in envelope.cards if card.title == "Grand Total")
    assert grand_total_card.value == ""


def _scope_test_handler(calls: list[str]):
    def handler(request):
        calls.append(request.question)
        return {
            "answer": "pnl ok",
            "basis": "formal",
            "result_kind": "agent.pnl_summary",
            "formal_use_allowed": True,
            "source_version": "sv_test",
            "quality_flag": "ok",
            "row_count": 1,
            "cards": [],
            "next_drill": [{"dimension": "portfolio", "label": "按组合查看"}],
        }

    return handler


def test_confirmation_token_issuance_binds_user_and_run_scope(tmp_path):
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
        intent_handlers={"pnl_summary": _scope_test_handler(calls)},
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="请汇总损益",
            context={"user_id": "user_a", "run_id": "run_001"},
        )
    )

    assert calls == ["请汇总损益"]
    assert envelope.suggested_actions
    action = envelope.suggested_actions[0]
    assert action.payload["confirmation_scope"] == {
        "user_id": "user_a",
        "run_id": "run_001",
    }
    assert action.confirmation_token
    # scope 位于 payload 内，既有校验端无需改动即可覆盖 HMAC 完整性。
    assert agent_action_confirmation_token_matches(
        token=action.confirmation_token,
        action_type=action.type,
        label=action.label,
        payload=action.payload,
    )


def test_confirmation_token_issuance_without_user_context_fails_closed(tmp_path):
    """请求上下文缺 user_id 时拒绝签发确认 token（fail-closed），不产出未绑定动作。

    生产路径路由层总会注入 user_id；本用例锁定绕过路由直接调用时的安全底线。
    """
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
        intent_handlers={"pnl_summary": _scope_test_handler(calls)},
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(question="请汇总损益")
    )

    # 签发失败在意图分支内被兜底为 error envelope：无 suggested action 泄出。
    assert envelope.result_meta.quality_flag == "error"
    assert envelope.suggested_actions == []
    assert "confirmation_scope.user_id" in envelope.answer


def test_scope_bound_action_is_rejected_for_other_user(tmp_path):
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
        intent_handlers={"pnl_summary": _scope_test_handler(calls)},
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="请汇总今日损益",
            context={
                "user_id": "user_b",
                "intent": "pnl_summary",
                "suggested_action": {
                    "type": "execute_intent",
                    "label": "Execute PnL summary",
                    "payload": {
                        "intent": "pnl_summary",
                        "confirmation_scope": {"user_id": "user_a", "run_id": "run_001"},
                    },
                },
            },
        )
    )

    assert calls == []
    assert envelope.result_meta.result_kind == "agent.action_scope"
    assert envelope.result_meta.quality_flag == "error"
    assert envelope.result_meta.formal_use_allowed is False
    assert "user scope" in envelope.answer


def test_scope_less_legacy_action_still_executes_for_any_user(tmp_path):
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
        intent_handlers={"pnl_summary": _scope_test_handler(calls)},
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="请汇总今日损益",
            context={
                "user_id": "user_b",
                "intent": "pnl_summary",
                "suggested_action": {
                    "type": "execute_intent",
                    "label": "Execute PnL summary",
                    "payload": {"intent": "pnl_summary"},
                },
            },
        )
    )

    assert calls == ["请汇总今日损益"]
    assert envelope.result_meta.result_kind == "agent.pnl_summary"


@pytest.mark.parametrize(
    ("question", "expected_intent"),
    [
        # 金融语义的「影响分析」不得再被 gitnexus_status 截走。
        ("帮我做一下组合久期影响分析", "duration_risk"),
        ("信用利差影响分析", "credit_exposure"),
        # 与 仓库/代码 域词同现时才路由 gitnexus。
        ("帮我做仓库影响分析", "gitnexus_status"),
        ("代码影响分析", "gitnexus_status"),
    ],
)
def test_impact_analysis_requires_code_domain_words_for_gitnexus(question, expected_intent):
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

    assert resolution.route == "local"
    assert resolution.intent == expected_intent


def test_page_context_question_with_history_prefers_page_default_over_follow_up():
    """回归（B15-2）：「这个页面…」+ page_id + 会话历史必须走 page_default，
    不得被 follow-up 裸指代词（「这个」）劫持而复用上一轮意图。"""
    resolution_module = load_module(
        "backend.app.agent.runtime.local_request_resolution",
        "backend/app/agent/runtime/local_request_resolution.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )
    conversation_context = {
        "conversation": {
            "recent_turns": [
                {"result_kind": "agent.duration_risk", "answer": "上一轮久期结论。"}
            ]
        }
    }

    resolution = resolution_module.resolve_local_request(
        request_module.AgentQueryRequest(
            question="这个页面的数据怎么样",
            page_context=request_module.AgentPageContext(page_id="dashboard"),
            context=dict(conversation_context),
        )
    )
    assert resolution.reason == "page_default"
    assert resolution.intent == "portfolio_overview"

    # 对照：没有可用页面上下文时保持既有 follow-up 语义。
    fallback = resolution_module.resolve_local_request(
        request_module.AgentQueryRequest(
            question="这个页面的数据怎么样",
            context=dict(conversation_context),
        )
    )
    assert fallback.reason == "follow_up"
    assert fallback.intent == "duration_risk"


def test_standalone_workbench_plain_analysis_routes_to_provider_after_page_defaults():
    """独立工作台的普通解释问答应交给受管 provider；嵌入页默认意图仍优先。"""
    resolution_module = load_module(
        "backend.app.agent.runtime.local_request_resolution",
        "backend/app/agent/runtime/local_request_resolution.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    standalone = resolution_module.resolve_local_request(
        request_module.AgentQueryRequest(
            question="解释当前页面的主要结论和风险点",
            routing_surface="standalone_workbench",
        )
    )
    assert standalone.route == "provider"
    assert standalone.reason == "standalone_workbench_chat"
    assert standalone.intent is None

    embedded = resolution_module.resolve_local_request(
        request_module.AgentQueryRequest(
            question="解释当前页面的主要结论和风险点",
            routing_surface="standalone_workbench",
            page_context=request_module.AgentPageContext(page_id="dashboard"),
        )
    )
    assert embedded.route == "local"
    assert embedded.reason == "page_default"
    assert embedded.intent == "portfolio_overview"


def _risk_tensor_upstream_with_cs01(report_date: str) -> dict[str, object]:
    upstream = _duration_risk_upstream(report_date, quality_flag="ok")
    upstream["result"]["cs01"] = {
        "raw": 3.21,
        "unit": "cs01",
        "display": "3.21",
        "precision": 2,
        "sign_aware": False,
    }
    return upstream


def test_risk_tensor_latest_date_uses_risk_tensor_fact_not_bond_analytics(tmp_path, monkeypatch):
    """回归（B15-3）：bond analytics 领先张量落表时，risk_tensor 的 latest
    日期必须取自张量事实表本身（与 duration_risk 对齐），否则上游直接 raise。"""
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
            # 张量事实表滞后：最新只有 2026-03-31。
            return ["2026-03-31"]

    class StubBondAnalyticsRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            # bond analytics 已经推进到 2026-04-01。
            return ["2026-04-01", "2026-03-31"]

    def fake_risk_tensor_envelope(*, report_date: str, **_: object) -> dict[str, object]:
        if report_date != "2026-03-31":
            raise RuntimeError(
                f"Risk tensor fact missing for report_date={report_date} "
                "while bond analytics lineage exists."
            )
        return _risk_tensor_upstream_with_cs01(report_date)

    risk_service_module = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    monkeypatch.setattr(service_module, "RiskTensorRepository", StubRiskTensorRepository)
    monkeypatch.setattr(service_module, "BondAnalyticsRepository", StubBondAnalyticsRepository)
    monkeypatch.setattr(risk_service_module, "risk_tensor_envelope", fake_risk_tensor_envelope)

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=service_module._build_intent_handlers("test.duckdb", str(tmp_path)),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="风险张量怎么样",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.result_meta.result_kind == "agent.risk_tensor"
    assert envelope.result_meta.quality_flag != "error"
    assert envelope.result_meta.filters_applied["report_date"] == "2026-03-31"
    assert "查询失败" not in envelope.answer


def test_risk_tensor_metric_cards_render_numeric_display_not_raw_dict(tmp_path, monkeypatch):
    """回归（B15-4）：risk_tensor 指标卡必须复用 Numeric display 渲染，
    不得把 promote_flat_payload 产出的 {'raw': ...} 字典串直接落在卡面与关键数字行。"""
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
        return _risk_tensor_upstream_with_cs01(report_date)

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
            question="风险张量怎么样",
            context={"user_id": "user_a"},
        )
    )

    cards = {card.title: card for card in envelope.cards}
    assert cards["Portfolio DV01"].value == "12.34 dv01"
    assert cards["CS01"].value == "3.21 cs01"
    assert cards["Portfolio Convexity"].value == "0.88 ratio"
    assert cards["Portfolio DV01"].spec == {
        "numeric": {
            "raw": 12.34,
            "unit": "dv01",
            "display": "12.34",
            "precision": 2,
            "sign_aware": False,
        }
    }
    assert "{'raw'" not in envelope.answer
    assert "Portfolio DV01=12.34 dv01" in envelope.answer


def test_intent_from_text_requires_exact_registered_result_kind():
    """结构化 result_kind 仅接受单一、精确且已注册的 agent 标记。"""
    resolution_module = load_module(
        "backend.app.agent.runtime.local_request_resolution",
        "backend/app/agent/runtime/local_request_resolution.py",
    )

    assert resolution_module._intent_from_text("agent.pnl_bridge") == "pnl_bridge"
    assert resolution_module._intent_from_text("agent.market_data") == "market_data"
    assert resolution_module._intent_from_text(
        "agent.news 之后又出现 agent.pnl_bridge"
    ) is None
    assert resolution_module._intent_from_text("agent.unregistered") is None


def test_cube_query_evidence_discloses_report_date_and_parameterized_sql(tmp_path):
    """回归（B15-6）：cube_query 路径必须披露 report_date/fact_table 过滤锚点
    与只读参数化 SQL 模板（过滤值保持 ? 占位），不再是零披露的动态 SQL 面。"""
    tool_module = load_module(
        "backend.app.agent.tools.analysis_view_tool",
        "backend/app/agent/tools/analysis_view_tool.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )
    cube_service_module = load_module(
        "backend.app.services.cube_query_service",
        "backend/app/services/cube_query_service.py",
    )

    class FakeCubeRepo:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def fetchall(self, sql: str, params=None):
            text = " ".join(str(sql).split()).lower()
            if text.startswith("select count(*) from ("):
                return [(1,)]
            if text.startswith("select count(*)"):
                return [(2,)]
            if "distinct source_version" in text:
                return [("sv_cube_test",)]
            if "distinct rule_version" in text:
                return [("rv_cube_test",)]
            if text.startswith("select distinct"):
                return [("credit",)]
            return [("credit", 100.0)]

    tool = tool_module.AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        cube_query_service=cube_service_module.CubeQueryService(repo_factory=FakeCubeRepo),
    )
    envelope = tool.execute(
        request_module.AgentQueryRequest(
            question="cube query",
            context={
                "user_id": "user_a",
                "cube_query": {
                    "report_date": "2026-03-31",
                    "fact_table": "bond_analytics",
                    "measures": ["sum(market_value)"],
                    "dimensions": ["asset_class_std"],
                    "filters": {"asset_class_std": ["credit"]},
                }
            },
        )
    )

    assert envelope.result_meta.result_kind == "cube_query.bond_analytics"
    assert envelope.evidence.filters_applied["report_date"] == "2026-03-31"
    assert envelope.evidence.filters_applied["fact_table"] == "bond_analytics"
    assert envelope.evidence.filters_applied["asset_class_std"] == ["credit"]
    assert envelope.evidence.sql_executed
    for sql in envelope.evidence.sql_executed:
        assert sql.startswith("select")
        assert "fact_formal_bond_analytics_daily" in sql
        assert "report_date = ?" in sql
        # 过滤值/日期不得内嵌进披露文本，全部保持 `?` 绑定占位。
        assert "2026-03-31" not in sql
        assert "'credit'" not in sql
    assert any("asset_class_std in (?)" in sql for sql in envelope.evidence.sql_executed)
    assert any("limit ? offset ?" in sql for sql in envelope.evidence.sql_executed)


def test_audit_filters_preserve_zero_and_false_values():
    """回归（B15-7）：`0 == False` 不得导致 offset=0/min_amount=0 等合法过滤值
    被审计过滤器丢弃；None 与空串仍剔除。"""
    service_module = load_module(
        "backend.app.services.agent_service",
        "backend/app/services/agent_service.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    request = request_module.AgentQueryRequest(
        question="最新新闻",
        filters={
            "offset": 0,
            "min_amount": 0.0,
            "error_only": False,
            "limit": 20,
            "empty": "",
            "missing": None,
        },
    )
    merged = service_module._audit_filters(
        request,
        "2026-03-31",
        resolution="latest_default",
        extra={"page_size": 0, "note": ""},
    )

    assert merged["offset"] == 0
    assert merged["min_amount"] == 0.0
    assert merged["error_only"] is False
    assert merged["limit"] == 20
    assert merged["page_size"] == 0
    assert "empty" not in merged
    assert "missing" not in merged
    assert "note" not in merged
    assert merged["report_date"] == "2026-03-31"
    assert merged["report_date_resolution"] == "latest_default"


def test_evidence_tool_normalizes_quality_flag_outside_contract(caplog):
    """回归（B15-12）：AgentEvidence.quality_flag 值域收敛到 ok/warning/error/stale；
    handler 笔误产生的枚举外值归一化为 warning 并记日志，合法值原样保留。"""
    import logging

    evidence_module = load_module(
        "backend.app.agent.tools.evidence_tool",
        "backend/app/agent/tools/evidence_tool.py",
    )
    tool = evidence_module.EvidenceTool()

    with caplog.at_level(logging.WARNING):
        typo = tool.build_evidence(
            tables_used=["fact_formal_pnl_fi"],
            filters_applied={},
            row_count=1,
            quality_flag="warnnig",
        )
    assert typo.quality_flag == "warning"
    assert "outside the contract enum" in caplog.text

    assert (
        tool.build_evidence(
            tables_used=["fact_formal_pnl_fi"],
            filters_applied={},
            row_count=1,
            quality_flag="error",
        ).quality_flag
        == "error"
    )
    assert (
        tool.build_evidence(
            tables_used=[],
            filters_applied={},
            row_count=0,
            quality_flag="stale",
        ).quality_flag
        == "stale"
    )
    # 大小写归一：治理证据充分时 "OK" 收敛为合法小写 "ok"。
    assert (
        tool.build_evidence(
            tables_used=["fact_formal_pnl_fi"],
            filters_applied={},
            row_count=1,
            quality_flag="OK",
        ).quality_flag
        == "ok"
    )


def _resolve(question: str, **kwargs):
    resolution_module = load_module(
        "backend.app.agent.runtime.local_request_resolution",
        "backend/app/agent/runtime/local_request_resolution.py",
    )
    request_module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )
    return resolution_module.resolve_local_request(
        request_module.AgentQueryRequest(question=question, **kwargs)
    )


@pytest.mark.parametrize(
    ("question", "expected_intent"),
    [
        # 短 ASCII 词只在词边界成立时命中，不再被更长的 token 吃掉。
        ("ftp", "product_pnl"),
        ("krd", "risk_tensor"),
        ("pnl summary", "pnl_summary"),
    ],
)
def test_short_ascii_keywords_match_on_word_boundaries(question, expected_intent):
    assert _resolve(question).intent == expected_intent


@pytest.mark.parametrize(
    "question",
    [
        # total_pnl / sftp / krda 里的子串不再触发本地意图。
        "please explain total_pnl_reconciliation_flag",
        "sftp upload failed",
    ],
)
def test_longer_tokens_containing_short_keywords_no_longer_route_locally(question):
    resolution = _resolve(question)
    assert resolution.intent not in {"product_pnl", "pnl_summary", "risk_tensor"}


@pytest.mark.parametrize(
    ("question", "expected_intent"),
    [
        # 特化表：更具体的意图直接压制必然被一起命中的泛化意图，不澄清。
        ("产品损益视图", "product_pnl"),
        ("损益归因拆解", "pnl_bridge"),
        ("利率风险敞口有多大", "duration_risk"),
        ("信用利差怎么样", "credit_exposure"),
        ("风险张量里的久期贡献", "risk_tensor"),
        ("盘前损益怎么看", "pretrade_checklist"),
        ("策略样本外收益怎么样", "walk_forward_verdict"),
    ],
)
def test_specialized_intent_wins_over_its_generalization_without_clarification(
    question,
    expected_intent,
):
    resolution = _resolve(question)

    assert resolution.reason == "governed_keyword"
    assert resolution.intent == expected_intent
    assert resolution.semantic_status is None


def test_cross_family_multi_intent_question_asks_for_clarification():
    resolution = _resolve("请看损益和新闻")

    assert resolution.route == "local"
    assert resolution.semantic_status == "clarification_required"
    assert resolution.semantic_reason_code == "multiple_intents"
    assert set(resolution.intent_candidates) == {"pnl_summary", "news"}


def test_page_default_intent_disambiguates_cross_family_multi_intent():
    # pnl-overview 不在 _PAGE_DEFAULT_INTENTS 里，无法消歧，仍需澄清。
    resolution = _resolve("请看损益和新闻", page_context={"page_id": "pnl-overview"})
    assert resolution.semantic_status == "clarification_required"

    disambiguated = _resolve(
        "组合概览和新闻都看一下",
        page_context={"page_id": "dashboard"},
    )
    assert disambiguated.reason == "governed_keyword"
    assert disambiguated.intent == "portfolio_overview"


def test_negated_base_intent_is_removed_from_candidates():
    routed = _resolve("不要看损益，看新闻")

    assert routed.reason == "governed_keyword"
    assert routed.intent == "news"


def test_all_candidates_negated_asks_for_clarification():
    resolution = _resolve("不要看损益")

    assert resolution.semantic_status == "clarification_required"
    assert resolution.semantic_reason_code == "negated_intent_reference"
    assert resolution.intent_candidates == ("pnl_summary",)


@pytest.mark.parametrize(
    "question",
    ["请汇总今日损益", "昨天的组合概览", "前天的信用利差", "show yesterday duration risk"],
)
def test_relative_day_without_explicit_report_date_asks_for_clarification(question):
    resolution = _resolve(question)

    assert resolution.route == "local"
    assert resolution.semantic_status == "clarification_required"
    assert resolution.semantic_reason_code == "relative_date_requires_explicit_report_date"


@pytest.mark.parametrize(
    ("question", "kwargs", "expected_intent"),
    [
        # 显式 ISO 报告日（问题里 / filters 里）仍直接路由。
        ("请汇总 2026-03-31 的损益", {}, "pnl_summary"),
        ("请汇总今日损益", {"filters": {"report_date": "2026-03-31"}}, "pnl_summary"),
        # 模糊时间词保持既有 latest 语义。
        ("最近的损益怎么样", {}, "pnl_summary"),
        ("当前组合概览", {}, "portfolio_overview"),
        # 非报告日绑定型意图的「今天」就是最新可用，不受影响。
        ("今天的利率怎么样", {}, "market_data"),
        ("今天盘前该做什么", {}, "pretrade_checklist"),
        ("今天有什么新闻", {}, "news"),
    ],
)
def test_relative_date_guard_does_not_widen_beyond_report_date_bound_intents(
    question,
    kwargs,
    expected_intent,
):
    resolution = _resolve(question, **kwargs)

    assert resolution.reason == "governed_keyword"
    assert resolution.intent == expected_intent


def test_intent_clarification_envelope_explains_the_blocking_reason(tmp_path):
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
        intent_handlers={"pnl_summary": _scope_test_handler(calls)},
    )

    for question, marker in (
        ("请看损益和新闻", "多个不同业务口径"),
        ("请汇总今日损益", "YYYY-MM-DD"),
    ):
        envelope = tool.execute(request_module.AgentQueryRequest(question=question))
        assert envelope.result_meta.result_kind == "agent.ontology_clarification"
        assert envelope.semantic_context is not None
        assert envelope.semantic_context.status == "clarification_required"
        assert envelope.semantic_context.result_check == "blocked"
        assert marker in envelope.answer
    assert calls == []


@pytest.mark.parametrize("mode", ["intent", "workflow", "research"])
@pytest.mark.parametrize("failure_type", [ValueError, TypeError])
def test_analysis_failure_api_omits_private_payload(tmp_path, monkeypatch, mode, failure_type):
    import sys
    from tests.test_agent_api import _confirmation_client
    tool_module = load_module("backend.app.agent.tools.analysis_view_tool", "backend/app/agent/tools/analysis_view_tool.py")
    calls = []
    marker = "synthetic-agent-handler-private-token"
    def fail(request):
        calls.append("failed")
        raise failure_type(marker)
    def ok(request):
        calls.append("continued")
        return {"answer": "synthetic analysis", "basis": "analytical", "formal_use_allowed": False,
                "source_version": "sv_test", "quality_flag": "warning", "row_count": 0, "cards": []}
    tool = tool_module.AnalysisViewTool("unused.duckdb", str(tmp_path), intent_handlers={
        "duration_risk": fail, "credit_exposure": ok, "risk_tensor": ok, "research_radar_brief": fail,
    })
    client, _ = _confirmation_client(monkeypatch, tmp_path)
    route = sys.modules["backend.app.api.routes.agent"]
    monkeypatch.setattr(route, "execute_agent_query", lambda request, **kwargs: tool.execute(request))
    payload = {"question": "synthetic", "context": {"intent": "duration_risk"}}
    if mode == "workflow":
        payload = {"question": "/risk-memo", "context": {"workflow_mode": "execute"}}
    elif mode == "research":
        payload = {"question": "synthetic", "context": {"intent": "research_radar_brief", "workflow_mode": "execute"}}
    response = client.post("/api/agent/query", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["result_meta"]["formal_use_allowed"] is False
    assert result["result_meta"]["quality_flag"] == ("warning" if mode == "workflow" else "error")
    assert calls == (["failed", "continued", "continued"] if mode == "workflow" else ["failed"])
    assert marker not in response.text
    assert failure_type.__name__ in response.text


@pytest.mark.parametrize("message", [
    "GitNexus repo_path is outside allowed roots: synthetic-whitelist-private-token",
    "Requested report_date=2025-11-20 is not in available governed dates ['synthetic-whitelist-private-token'].",
    "Formal pnl storage is unavailable. synthetic-whitelist-private-token",
])
def test_analysis_safe_error_categories_never_copy_private_suffix(tmp_path, message):
    module = load_module("backend.app.agent.tools.analysis_view_tool", "backend/app/agent/tools/analysis_view_tool.py")
    request_module = load_module("backend.app.agent.schemas.agent_request", "backend/app/agent/schemas/agent_request.py")
    def fail(request):
        raise ValueError(message)
    tool = module.AnalysisViewTool("unused.duckdb", str(tmp_path), intent_handlers={"duration_risk": fail})
    result = tool.execute(request_module.AgentQueryRequest(question="synthetic", context={"intent": "duration_risk"}))
    assert result.result_meta.formal_use_allowed is False
    assert result.result_meta.quality_flag == "error"
    assert "synthetic-whitelist-private-token" not in result.model_dump_json()
