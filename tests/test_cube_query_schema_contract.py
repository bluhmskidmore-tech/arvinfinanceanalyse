from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.cube_query import CubeQueryRequest, CubeQueryResponse, DrillPath
from backend.app.schemas.result_meta import ResultMeta


def test_cube_query_request_defaults():
    req = CubeQueryRequest(
        report_date="2026-03-31",
        fact_table="bond_analytics",
        measures=["sum(x)"],
    )
    assert req.dimensions == []
    assert req.filters == {}
    assert req.order_by == []
    assert req.limit == 100
    assert req.offset == 0
    assert req.basis == "formal"


@pytest.mark.parametrize(
    "fact_table",
    ["bond_analytics", "pnl", "balance", "product_category"],
)
def test_cube_query_request_accepts_allowed_fact_tables(fact_table: str):
    req = CubeQueryRequest(
        report_date="2026-03-31",
        fact_table=fact_table,
        measures=["sum(x)"],
    )
    assert req.fact_table == fact_table


def test_cube_query_request_rejects_unsupported_fact_table():
    with pytest.raises(ValueError, match="Unsupported fact_table"):
        CubeQueryRequest(
            report_date="2026-03-31",
            fact_table="other",
            measures=["sum(x)"],
        )


def test_cube_query_request_limit_bounds():
    with pytest.raises(ValidationError):
        CubeQueryRequest(
            report_date="2026-03-31",
            fact_table="pnl",
            measures=["sum(x)"],
            limit=0,
        )
    with pytest.raises(ValidationError):
        CubeQueryRequest(
            report_date="2026-03-31",
            fact_table="pnl",
            measures=["sum(x)"],
            limit=1001,
        )


def test_drill_path_defaults():
    path = DrillPath(dimension="d", label="L")
    assert path.available_values == []
    assert path.current_filter is None


def test_cube_query_response_normalizes_result_meta_instance():
    meta = ResultMeta(
        trace_id="tr_cube",
        basis="formal",
        result_kind="cube.test",
        formal_use_allowed=True,
        source_version="sv1",
        vendor_version="vv1",
        rule_version="rv1",
        cache_version="cv1",
    )
    resp = CubeQueryResponse(
        report_date="2026-03-31",
        fact_table="bond_analytics",
        measures=["m"],
        dimensions=[],
        rows=[{"a": 1}],
        total_rows=1,
        drill_paths=[],
        result_meta=meta,
    )
    assert isinstance(resp.result_meta, ResultMeta)
    assert resp.result_meta.trace_id == "tr_cube"
    dumped = resp.model_dump(mode="python")
    assert dumped["rows"] == [{"a": 1}]
    assert dumped["total_rows"] == 1
    assert dumped["drill_paths"] == []
    assert dumped["result_meta"]["result_kind"] == "cube.test"


def test_cube_query_request_extra_forbidden():
    with pytest.raises(ValidationError):
        CubeQueryRequest(
            report_date="2026-03-31",
            fact_table="pnl",
            measures=["m"],
            extra_field=1,  # type: ignore[call-arg]
        )
