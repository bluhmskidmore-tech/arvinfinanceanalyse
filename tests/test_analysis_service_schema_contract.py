from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.analysis_service import (
    AnalysisQuery,
    AnalysisResultEnvelope,
    AnalysisResultPayload,
    AnalysisWarning,
    AttributionSlice,
    DrillTarget,
)
from backend.app.schemas.result_meta import ResultMeta


def test_analysis_query_valid_formal_without_scenario_rate():
    q = AnalysisQuery(
        consumer="c",
        analysis_key="k",
        report_date="2026-02-28",
        basis="formal",
    )
    assert q.scenario_rate_pct is None
    assert q.filters == {}


def test_analysis_query_valid_scenario_with_scenario_rate():
    q = AnalysisQuery(
        consumer="c",
        analysis_key="k",
        report_date="2026-02-28",
        basis="scenario",
        scenario_rate_pct=2.5,
    )
    assert q.scenario_rate_pct == 2.5


def test_analysis_query_invalid_scenario_without_scenario_rate():
    with pytest.raises(ValueError, match="scenario_rate_pct is required"):
        AnalysisQuery(
            consumer="c",
            analysis_key="k",
            report_date="2026-02-28",
            basis="scenario",
        )


def test_analysis_query_invalid_non_scenario_with_scenario_rate():
    with pytest.raises(ValueError, match="only allowed when basis=scenario"):
        AnalysisQuery(
            consumer="c",
            analysis_key="k",
            report_date="2026-02-28",
            basis="formal",
            scenario_rate_pct=1.0,
        )


def test_analysis_warning_default_level():
    w = AnalysisWarning(code="x", message="m")
    assert w.level == "warning"


def test_drill_target_validation_minimal():
    t = DrillTarget(target_kind="cube", target_id="t1", label="L")
    assert t.target_id == "t1"


def test_attribution_slice_defaults():
    s = AttributionSlice(slice_id="s1", label="L", dimension="d", value="v")
    assert s.share_pct == "0"
    assert s.tone == "neutral"
    assert s.drill_targets == []


def test_analysis_result_payload_defaults():
    p = AnalysisResultPayload(
        report_date="2026-02-28",
        analysis_key="k",
        basis="formal",
    )
    assert p.summary == {}
    assert p.rows == []
    assert p.facets == {}
    assert p.attribution == []
    assert p.warnings == []
    assert p.drill_targets == []


def test_analysis_result_envelope_normalizes_result_meta_instance():
    meta = ResultMeta(
        trace_id="tr_analysis_schema",
        basis="analytical",
        result_kind="analysis.schema",
        formal_use_allowed=False,
        source_version="sv1",
        vendor_version="vv1",
        rule_version="rv1",
        cache_version="cv1",
    )
    env = AnalysisResultEnvelope(
        result_meta=meta,
        result=AnalysisResultPayload(
            report_date="2026-02-28",
            analysis_key="k",
            basis="analytical",
        ),
    )
    assert isinstance(env.result_meta, ResultMeta)
    dumped = env.model_dump(mode="json")
    assert dumped["result_meta"]["trace_id"] == "tr_analysis_schema"


def test_analysis_query_extra_forbidden():
    with pytest.raises(ValidationError):
        AnalysisQuery(
            consumer="c",
            analysis_key="k",
            report_date="2026-02-28",
            basis="formal",
            unexpected=1,  # type: ignore[call-arg]
        )
