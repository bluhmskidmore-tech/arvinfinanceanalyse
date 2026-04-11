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

