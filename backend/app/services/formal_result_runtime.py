from __future__ import annotations

from typing import Literal

from backend.app.schemas.result_meta import ResultMeta


def build_analytical_result_meta(
    *,
    trace_id: str,
    result_kind: str,
    cache_version: str,
    source_version: str,
    rule_version: str,
    formal_use_allowed: bool = False,
    scenario_flag: bool = False,
    quality_flag: Literal["ok", "warning", "error", "stale"] = "warning",
    vendor_version: str = "vv_none",
) -> ResultMeta:
    return ResultMeta(
        trace_id=trace_id,
        basis="analytical",
        result_kind=result_kind,
        formal_use_allowed=formal_use_allowed,
        source_version=source_version,
        vendor_version=vendor_version,
        rule_version=rule_version,
        cache_version=cache_version,
        quality_flag=quality_flag,
        scenario_flag=scenario_flag,
    )


def build_scenario_result_meta(
    *,
    trace_id: str,
    result_kind: str,
    cache_version: str,
    source_version: str,
    rule_version: str,
    formal_use_allowed: bool = False,
    quality_flag: Literal["ok", "warning", "error", "stale"] = "warning",
    vendor_version: str = "vv_none",
) -> ResultMeta:
    return ResultMeta(
        trace_id=trace_id,
        basis="scenario",
        result_kind=result_kind,
        formal_use_allowed=formal_use_allowed,
        source_version=source_version,
        vendor_version=vendor_version,
        rule_version=rule_version,
        cache_version=cache_version,
        quality_flag=quality_flag,
        scenario_flag=True,
    )


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
