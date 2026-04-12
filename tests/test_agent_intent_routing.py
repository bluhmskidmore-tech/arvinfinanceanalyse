from __future__ import annotations

import json

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
    assert "GitNexus 索引状态已返回" in envelope.answer


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
