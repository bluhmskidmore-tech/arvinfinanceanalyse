from __future__ import annotations

from tests.helpers import load_module


def _build_cube_response():
    cube_schema_module = load_module("backend.app.schemas.cube_query", "backend/app/schemas/cube_query.py")
    result_meta_module = load_module("backend.app.schemas.result_meta", "backend/app/schemas/result_meta.py")
    return cube_schema_module.CubeQueryResponse(
        report_date="2026-03-31",
        fact_table="bond_analytics",
        measures=["sum(market_value)"],
        dimensions=["asset_class_std"],
        rows=[{"asset_class_std": "credit", "market_value": "350.00000000"}],
        total_rows=1,
        drill_paths=[
            cube_schema_module.DrillPath(
                dimension="asset_class_std",
                label="asset_class_std",
                available_values=["credit", "rate"],
                current_filter=["credit"],
            )
        ],
        result_meta=result_meta_module.ResultMeta(
            trace_id="tr_cube_tool",
            basis="formal",
            result_kind="cube_query.bond_analytics",
            formal_use_allowed=True,
            source_version="sv_cube",
            vendor_version="vv_none",
            rule_version="rv_cube",
            cache_version="cv_cube",
            quality_flag="ok",
            scenario_flag=False,
        ),
    )


def test_analysis_view_tool_executes_registered_cube_query_intent():
    request_module = load_module("backend.app.agent.schemas.agent_request", "backend/app/agent/schemas/agent_request.py")
    tool_module = load_module("backend.app.agent.tools.analysis_view_tool", "backend/app/agent/tools/analysis_view_tool.py")
    captured: dict[str, object] = {}

    class FakeCubeQueryService:
        def execute(self, request, duckdb_path):
            captured["request"] = request
            captured["duckdb_path"] = duckdb_path
            return _build_cube_response()

    tool = tool_module.AnalysisViewTool(
        duckdb_path="analytics.duckdb",
        cube_query_service=FakeCubeQueryService(),
    )

    response = tool.execute(
        request_module.AgentQueryRequest(
            question="show credit market value",
            basis="formal",
            context={
                "intent": "cube_query",
                "cube_query": {
                    "report_date": "2026-03-31",
                    "fact_table": "bond_analytics",
                    "measures": ["sum(market_value)"],
                    "dimensions": ["asset_class_std"],
                    "filters": {"asset_class_std": ["credit"]},
                },
            },
        )
    )

    assert captured["duckdb_path"] == "analytics.duckdb"
    assert captured["request"].fact_table == "bond_analytics"
    assert response.answer.startswith("Retrieved 1 row")
    assert response.cards[0].type == "table"
    assert response.evidence.tables_used == ["fact_formal_bond_analytics_daily"]
    assert response.result_meta.tables_used == ["fact_formal_bond_analytics_daily"]
    assert response.next_drill[0].dimension == "asset_class_std"


def test_analysis_view_tool_falls_back_to_cube_query_when_intent_is_unknown():
    request_module = load_module("backend.app.agent.schemas.agent_request", "backend/app/agent/schemas/agent_request.py")
    tool_module = load_module("backend.app.agent.tools.analysis_view_tool", "backend/app/agent/tools/analysis_view_tool.py")
    captured: dict[str, object] = {}

    class FakeCubeQueryService:
        def execute(self, request, duckdb_path):
            captured["request"] = request
            captured["duckdb_path"] = duckdb_path
            return _build_cube_response()

    tool = tool_module.AnalysisViewTool(
        duckdb_path="analytics.duckdb",
        cube_query_service=FakeCubeQueryService(),
    )

    response = tool.execute(
        request_module.AgentQueryRequest(
            question="fallback to cube query",
            basis="formal",
            context={
                "intent": "unmatched",
                "cube_query": {
                    "report_date": "2026-03-31",
                    "fact_table": "bond_analytics",
                    "measures": ["sum(market_value)"],
                },
            },
        )
    )

    assert captured["duckdb_path"] == "analytics.duckdb"
    assert captured["request"].fact_table == "bond_analytics"
    assert response.result_meta.result_kind == "cube_query.bond_analytics"
