import pytest

from tests.helpers import load_module


def test_result_meta_schema_defines_governance_fields():
    module = load_module("backend.app.schemas.result_meta", "backend/app/schemas/result_meta.py")
    result_meta_model = getattr(module, "ResultMeta", None)
    if result_meta_model is None:
        pytest.fail("backend.app.schemas.result_meta must define ResultMeta")

    fields = set(result_meta_model.model_fields)
    assert {
        "trace_id",
        "basis",
        "source_version",
        "vendor_version",
        "rule_version",
        "cache_version",
        "quality_flag",
        "vendor_status",
        "fallback_mode",
        "formal_use_allowed",
        "generated_at",
    } <= fields
    assert "result_kind" in fields
    assert "scenario_flag" in fields


def test_result_meta_accepts_stale_quality_flag_for_degraded_analytical_reads():
    module = load_module("backend.app.schemas.result_meta", "backend/app/schemas/result_meta.py")

    payload = module.ResultMeta(
        trace_id="tr_macro_stale",
        basis="analytical",
        result_kind="macro.choice.latest",
        formal_use_allowed=False,
        source_version="sv_choice_macro_20260411",
        vendor_version="vv_choice_20260411T090000Z",
        rule_version="rv_choice_macro_thin_slice_v1",
        cache_version="cv_choice_macro_thin_slice_v1",
        quality_flag="stale",
        scenario_flag=False,
    )

    assert payload.quality_flag == "stale"
    assert payload.vendor_status == "ok"
    assert payload.fallback_mode == "none"
