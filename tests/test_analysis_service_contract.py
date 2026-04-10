from __future__ import annotations

import pytest

from tests.helpers import load_module


def test_analysis_query_requires_scenario_rate_for_scenario_basis():
    module = load_module(
        "backend.app.schemas.analysis_service",
        "backend/app/schemas/analysis_service.py",
    )

    AnalysisQuery = module.AnalysisQuery

    with pytest.raises(Exception):
        AnalysisQuery(
            consumer="analysis_service",
            analysis_key="product_category_pnl",
            report_date="2026-02-28",
            basis="scenario",
        )


def test_analysis_query_rejects_scenario_rate_for_formal_basis():
    module = load_module(
        "backend.app.schemas.analysis_service",
        "backend/app/schemas/analysis_service.py",
    )

    AnalysisQuery = module.AnalysisQuery

    with pytest.raises(Exception):
        AnalysisQuery(
            consumer="analysis_service",
            analysis_key="product_category_pnl",
            report_date="2026-02-28",
            basis="formal",
            scenario_rate_pct=2.5,
        )


def test_analysis_result_envelope_wraps_result_meta_and_normalized_payload():
    schema_module = load_module(
        "backend.app.schemas.analysis_service",
        "backend/app/schemas/analysis_service.py",
    )
    result_meta_module = load_module(
        "backend.app.schemas.result_meta",
        "backend/app/schemas/result_meta.py",
    )

    envelope = schema_module.AnalysisResultEnvelope(
        result_meta=result_meta_module.ResultMeta(
            trace_id="tr_analysis_contract",
            basis="analytical",
            result_kind="analysis.contract",
            formal_use_allowed=False,
            source_version="sv_test",
            vendor_version="vv_none",
            rule_version="rv_test",
            cache_version="cv_test",
            quality_flag="ok",
            scenario_flag=False,
        ),
        result=schema_module.AnalysisResultPayload(
            report_date="2026-02-28",
            analysis_key="analysis.contract",
            basis="analytical",
            summary={"row_count": 1},
            rows=[{"id": "row-1"}],
            facets={"details": [{"id": "detail-1"}]},
        ),
    )

    dumped = envelope.model_dump(mode="json")

    assert dumped["result_meta"]["result_kind"] == "analysis.contract"
    assert dumped["result"]["analysis_key"] == "analysis.contract"
    assert dumped["result"]["summary"]["row_count"] == 1
    assert dumped["result"]["facets"]["details"][0]["id"] == "detail-1"


def test_build_default_analysis_service_registers_known_adapters():
    service_module = load_module(
        "backend.app.services.analysis_service",
        "backend/app/services/analysis_service.py",
    )

    service = service_module.build_default_analysis_service(duckdb_path="placeholder.duckdb")

    assert service.supported_analysis_keys() == {
        "bond_action_attribution",
        "product_category_pnl",
    }
