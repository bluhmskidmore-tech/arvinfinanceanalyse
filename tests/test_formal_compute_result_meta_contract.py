from __future__ import annotations

from tests.helpers import load_module


def test_build_formal_result_meta_emits_explicit_formal_flags():
    runtime_mod = load_module(
        "backend.app.services.formal_result_runtime",
        "backend/app/services/formal_result_runtime.py",
    )

    meta = runtime_mod.build_formal_result_meta(
        trace_id="tr_balance_analysis_dates",
        result_kind="balance-analysis.dates",
        cache_version="cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        source_version="sv_balance_20251231",
        rule_version="rv_balance_analysis_formal_materialize_v1",
        vendor_version="vv_none",
    )

    assert meta.basis == "formal"
    assert meta.formal_use_allowed is True
    assert meta.scenario_flag is False
    assert meta.cache_version == "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1"


def test_build_formal_result_envelope_serializes_meta_and_result_payload():
    runtime_mod = load_module(
        "backend.app.services.formal_result_runtime",
        "backend/app/services/formal_result_runtime.py",
    )
    meta = runtime_mod.build_formal_result_meta(
        trace_id="tr_balance_analysis_dates",
        result_kind="balance-analysis.dates",
        cache_version="cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        source_version="sv_balance_20251231",
        rule_version="rv_balance_analysis_formal_materialize_v1",
        vendor_version="vv_none",
    )

    envelope = runtime_mod.build_formal_result_envelope(
        result_meta=meta,
        result_payload={"report_dates": ["2025-12-31"]},
    )

    assert envelope["result_meta"]["result_kind"] == "balance-analysis.dates"
    assert envelope["result"]["report_dates"] == ["2025-12-31"]


def test_build_formal_result_meta_from_lineage_uses_lineage_and_defaults():
    runtime_mod = load_module(
        "backend.app.services.formal_result_runtime",
        "backend/app/services/formal_result_runtime.py",
    )

    meta = runtime_mod.build_formal_result_meta_from_lineage(
        trace_id="tr_balance_analysis_dates",
        result_kind="balance-analysis.dates",
        lineage={
            "cache_version": "cv_balance_analysis_from_manifest",
            "source_version": "sv_balance_analysis_manifest",
            "rule_version": "rv_balance_analysis_manifest",
        },
        default_cache_version="cv_balance_analysis_default",
    )

    assert meta.cache_version == "cv_balance_analysis_from_manifest"
    assert meta.source_version == "sv_balance_analysis_manifest"
    assert meta.rule_version == "rv_balance_analysis_manifest"
    assert meta.vendor_version == "vv_none"
    assert meta.formal_use_allowed is True
    assert meta.scenario_flag is False


def test_build_formal_result_meta_from_lineage_uses_overrides_as_fallback_and_enforces_missing_field_contract():
    runtime_mod = load_module(
        "backend.app.services.formal_result_runtime",
        "backend/app/services/formal_result_runtime.py",
    )

    meta = runtime_mod.build_formal_result_meta_from_lineage(
        trace_id="tr_balance_analysis_detail",
        result_kind="balance-analysis.detail",
        lineage=None,
        default_cache_version="cv_balance_analysis_default",
        source_version="sv_balance_analysis_detail_rows",
        rule_version="rv_balance_analysis_detail_rows",
        vendor_version="vv_balance_analysis_detail_rows",
        missing_field_message=lambda field_name: f"missing {field_name}",
    )

    assert meta.cache_version == "cv_balance_analysis_default"
    assert meta.source_version == "sv_balance_analysis_detail_rows"
    assert meta.rule_version == "rv_balance_analysis_detail_rows"
    assert meta.vendor_version == "vv_balance_analysis_detail_rows"

    try:
        runtime_mod.build_formal_result_meta_from_lineage(
            trace_id="tr_balance_analysis_detail",
            result_kind="balance-analysis.detail",
            lineage=None,
            default_cache_version="cv_balance_analysis_default",
            missing_field_message=lambda field_name: f"missing {field_name}",
        )
    except RuntimeError as exc:
        assert str(exc) == "missing source_version"
    else:
        raise AssertionError("Expected missing source_version runtime error")


def test_build_formal_result_meta_from_lineage_can_prefer_explicit_overrides():
    runtime_mod = load_module(
        "backend.app.services.formal_result_runtime",
        "backend/app/services/formal_result_runtime.py",
    )

    meta = runtime_mod.build_formal_result_meta_from_lineage(
        trace_id="tr_balance_analysis_override",
        result_kind="balance-analysis.detail",
        lineage={
            "source_version": "sv_lineage",
            "rule_version": "rv_lineage",
            "vendor_version": "vv_lineage",
        },
        default_cache_version="cv_balance_analysis_default",
        source_version="sv_override",
        rule_version="rv_override",
        vendor_version="vv_override",
        prefer_override=True,
    )

    assert meta.source_version == "sv_override"
    assert meta.rule_version == "rv_override"
    assert meta.vendor_version == "vv_override"


def test_build_formal_result_envelope_from_lineage_serializes_meta_and_result_payload():
    runtime_mod = load_module(
        "backend.app.services.formal_result_runtime",
        "backend/app/services/formal_result_runtime.py",
    )

    envelope = runtime_mod.build_formal_result_envelope_from_lineage(
        trace_id="tr_risk_tensor_dates",
        result_kind="risk.tensor.dates",
        lineage={
            "cache_version": "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v1",
            "source_version": "sv_risk_tensor_20260331",
            "rule_version": "rv_risk_tensor_formal_materialize_v1",
            "vendor_version": "vv_none",
        },
        default_cache_version="cv_default",
        result_payload={"report_dates": ["2026-03-31"]},
    )

    assert envelope["result_meta"]["result_kind"] == "risk.tensor.dates"
    assert envelope["result_meta"]["cache_version"] == "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v1"
    assert envelope["result_meta"]["source_version"] == "sv_risk_tensor_20260331"
    assert envelope["result"]["report_dates"] == ["2026-03-31"]


def test_build_formal_result_meta_from_lineage_can_pin_default_cache_version():
    runtime_mod = load_module(
        "backend.app.services.formal_result_runtime",
        "backend/app/services/formal_result_runtime.py",
    )

    meta = runtime_mod.build_formal_result_meta_from_lineage(
        trace_id="tr_pnl_overview",
        result_kind="pnl.overview",
        lineage={
            "cache_version": "cv_manifest_override_should_not_apply",
            "source_version": "sv_pnl_manifest",
            "rule_version": "rv_pnl_manifest",
            "vendor_version": "vv_pnl_manifest",
        },
        default_cache_version="cv_pnl_formal__rv_pnl_phase2_materialize_v1",
        use_lineage_cache_version=False,
    )

    assert meta.cache_version == "cv_pnl_formal__rv_pnl_phase2_materialize_v1"
    assert meta.source_version == "sv_pnl_manifest"
    assert meta.rule_version == "rv_pnl_manifest"
    assert meta.vendor_version == "vv_pnl_manifest"

