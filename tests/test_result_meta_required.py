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
        "formal_use_allowed",
        "generated_at",
    } <= fields
    assert "result_kind" in fields
    assert "scenario_flag" in fields
