from __future__ import annotations

from backend.app.schemas.result_meta import ResultMeta


def build_formal_result_meta(
    *,
    trace_id: str,
    result_kind: str,
    cache_version: str,
    source_version: str,
    rule_version: str,
    vendor_version: str = "vv_none",
) -> ResultMeta:
    return ResultMeta(
        trace_id=trace_id,
        basis="formal",
        result_kind=result_kind,
        formal_use_allowed=True,
        source_version=source_version,
        vendor_version=vendor_version,
        rule_version=rule_version,
        cache_version=cache_version,
        quality_flag="ok",
        scenario_flag=False,
    )


def build_formal_result_envelope(
    *,
    result_meta: ResultMeta,
    result_payload: dict[str, object],
) -> dict[str, object]:
    return {
        "result_meta": result_meta.model_dump(mode="json"),
        "result": result_payload,
    }
