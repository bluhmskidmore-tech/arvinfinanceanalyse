from __future__ import annotations

import json

import pytest

from tests.helpers import load_module


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
    assert any(card.title == "Total Market Value" for card in envelope.cards)


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

    calls: list[str] = []

    class StubBalanceAnalysisRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def fetch_formal_overview(self, *, report_date: str, position_scope: str, currency_basis: str) -> dict[str, object]:
            calls.append(report_date)
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

    assert calls == ["2026-03-31"]
    assert envelope.result_meta.result_kind == "agent.portfolio_overview"
    assert any(card.title == "Total Market Value" for card in envelope.cards)


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
    assert action.payload == {
        "dimension": "instrument_id",
        "page_context": {
            "page_id": "recon-exceptions",
            "current_filters": {"report_date": "2026-03-31", "status": "unmatched"},
            "selected_rows": [{"book_id": "B001", "instrument_id": "IB123"}],
            "context_note": "user selected one exception row",
        },
    }


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
    assert any(card.title == "Total PnL" for card in envelope.cards)


def test_duration_risk_intent_routes_to_bond_analytics(tmp_path, monkeypatch):
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

    class StubBondAnalyticsRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def fetch_portfolio_risk_summary(self, *, report_date: str) -> dict[str, object]:
            calls.append(report_date)
            return {
                "bond_count": 3,
                "total_market_value": 1000,
                "portfolio_duration": 4.25,
                "portfolio_modified_duration": 4.1,
                "portfolio_convexity": 0.88,
                "portfolio_dv01": 12.34,
            }

    monkeypatch.setattr(service_module, "BondAnalyticsRepository", StubBondAnalyticsRepository)

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
    assert envelope.evidence.tables_used == ["fact_formal_bond_analytics_daily"]
    assert any(card.title == "Portfolio DV01" for card in envelope.cards)


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

    class StubBondAnalyticsRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31", "2025-11-20", "2026-02-28", "2024-01-01"]

        def fetch_portfolio_risk_summary(self, *, report_date: str) -> dict[str, object]:
            calls.append(report_date)
            return {
                "bond_count": 1,
                "total_market_value": 100,
                "portfolio_duration": 3.0,
                "portfolio_modified_duration": 2.9,
                "portfolio_convexity": 0.5,
                "portfolio_dv01": 1.0,
            }

    monkeypatch.setattr(service_module, "BondAnalyticsRepository", StubBondAnalyticsRepository)

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

    class StubBondAnalyticsRepository:
        def __init__(self, path: str):
            pass

        def list_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def fetch_portfolio_risk_summary(self, *, report_date: str) -> dict[str, object]:
            raise AssertionError("should not query")

    monkeypatch.setattr(service_module, "BondAnalyticsRepository", StubBondAnalyticsRepository)

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


def test_gitnexus_intent_reads_repo_index_metadata_from_question_path(tmp_path):
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


def test_gitnexus_intent_prefers_explicit_repo_path_filter_over_question_text(tmp_path):
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
    assert any(card.title == "Nodes" and card.value == "22" for card in envelope.cards)


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
    assert payload["tools_used"] == ["analysis_view_tool", "evidence_tool"]
    assert payload["tables_used"] == ["fact_formal_pnl_fi"]
    assert payload["trace_id"] == "tr_agent_audit"
