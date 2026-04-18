from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Literal

from backend.app.schemas.result_meta import ResultMeta

ResultBasis = Literal["formal", "scenario", "analytical"]
QualityFlag = Literal["ok", "warning", "error", "stale"]
VendorStatus = Literal["ok", "vendor_stale", "vendor_unavailable"]
FallbackMode = Literal["none", "latest_snapshot"]

_BASIS_FIXED_FLAGS: dict[ResultBasis, tuple[bool, bool]] = {
    "formal": (True, False),
    "scenario": (False, True),
    "analytical": (False, False),
}

_BASIS_DEFAULT_QUALITY: dict[ResultBasis, QualityFlag] = {
    "formal": "ok",
    "scenario": "warning",
    "analytical": "warning",
}

LineageFieldMessageBuilder = Callable[[str], str]


def _build_result_meta(
    *,
    basis: ResultBasis,
    trace_id: str,
    result_kind: str,
    cache_version: str,
    source_version: str,
    rule_version: str,
    quality_flag: QualityFlag | None,
    vendor_version: str,
    vendor_status: VendorStatus,
    fallback_mode: FallbackMode,
    filters_applied: Mapping[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    next_drill: list[str | dict[str, object]] | None = None,
) -> ResultMeta:
    formal_use_allowed, scenario_flag = _BASIS_FIXED_FLAGS[basis]
    return ResultMeta(
        trace_id=trace_id,
        basis=basis,
        result_kind=result_kind,
        formal_use_allowed=formal_use_allowed,
        source_version=source_version,
        vendor_version=vendor_version,
        rule_version=rule_version,
        cache_version=cache_version,
        quality_flag=quality_flag or _BASIS_DEFAULT_QUALITY[basis],
        vendor_status=vendor_status,
        fallback_mode=fallback_mode,
        scenario_flag=scenario_flag,
        filters_applied=dict(filters_applied or {}),
        tables_used=list(tables_used or []),
        evidence_rows=evidence_rows,
        next_drill=list(next_drill or []),
    )


def build_analytical_result_meta(
    *,
    trace_id: str,
    result_kind: str,
    cache_version: str,
    source_version: str,
    rule_version: str,
    quality_flag: QualityFlag | None = None,
    vendor_version: str = "vv_none",
    vendor_status: VendorStatus = "ok",
    fallback_mode: FallbackMode = "none",
    filters_applied: Mapping[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    next_drill: list[str | dict[str, object]] | None = None,
) -> ResultMeta:
    return _build_result_meta(
        basis="analytical",
        trace_id=trace_id,
        result_kind=result_kind,
        cache_version=cache_version,
        source_version=source_version,
        rule_version=rule_version,
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status=vendor_status,
        fallback_mode=fallback_mode,
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        next_drill=next_drill,
    )


def build_scenario_result_meta(
    *,
    trace_id: str,
    result_kind: str,
    cache_version: str,
    source_version: str,
    rule_version: str,
    quality_flag: QualityFlag | None = None,
    vendor_version: str = "vv_none",
    vendor_status: VendorStatus = "ok",
    fallback_mode: FallbackMode = "none",
    filters_applied: Mapping[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    next_drill: list[str | dict[str, object]] | None = None,
) -> ResultMeta:
    return _build_result_meta(
        basis="scenario",
        trace_id=trace_id,
        result_kind=result_kind,
        cache_version=cache_version,
        source_version=source_version,
        rule_version=rule_version,
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status=vendor_status,
        fallback_mode=fallback_mode,
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        next_drill=next_drill,
    )


def build_formal_result_meta(
    *,
    trace_id: str,
    result_kind: str,
    cache_version: str,
    source_version: str,
    rule_version: str,
    quality_flag: QualityFlag | None = None,
    vendor_version: str = "vv_none",
    vendor_status: VendorStatus = "ok",
    fallback_mode: FallbackMode = "none",
    filters_applied: Mapping[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    next_drill: list[str | dict[str, object]] | None = None,
) -> ResultMeta:
    return _build_result_meta(
        basis="formal",
        trace_id=trace_id,
        result_kind=result_kind,
        cache_version=cache_version,
        source_version=source_version,
        rule_version=rule_version,
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status=vendor_status,
        fallback_mode=fallback_mode,
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        next_drill=next_drill,
    )


def build_formal_result_meta_from_lineage(
    *,
    trace_id: str,
    result_kind: str,
    lineage: Mapping[str, object] | None,
    default_cache_version: str,
    use_lineage_cache_version: bool = True,
    source_version: object | None = None,
    rule_version: object | None = None,
    vendor_version: object | None = None,
    prefer_override: bool = False,
    quality_flag: QualityFlag | None = None,
    vendor_status: VendorStatus = "ok",
    fallback_mode: FallbackMode = "none",
    missing_field_message: LineageFieldMessageBuilder | None = None,
) -> ResultMeta:
    return build_formal_result_meta(
        trace_id=trace_id,
        result_kind=result_kind,
        cache_version=(
            _resolve_lineage_field(
                lineage=lineage,
                field_name="cache_version",
                default=default_cache_version,
                prefer_override=prefer_override,
                missing_field_message=missing_field_message,
            )
            if use_lineage_cache_version
            else default_cache_version
        ),
        source_version=_resolve_lineage_field(
            lineage=lineage,
            field_name="source_version",
            override=source_version,
            prefer_override=prefer_override,
            missing_field_message=missing_field_message,
        ),
        rule_version=_resolve_lineage_field(
            lineage=lineage,
            field_name="rule_version",
            override=rule_version,
            prefer_override=prefer_override,
            missing_field_message=missing_field_message,
        ),
        vendor_version=_resolve_lineage_field(
            lineage=lineage,
            field_name="vendor_version",
            override=vendor_version,
            default="vv_none",
            prefer_override=prefer_override,
            missing_field_message=missing_field_message,
        ),
        quality_flag=quality_flag,
        vendor_status=vendor_status,
        fallback_mode=fallback_mode,
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


def build_formal_result_envelope_from_lineage(
    *,
    trace_id: str,
    result_kind: str,
    lineage: Mapping[str, object] | None,
    default_cache_version: str,
    use_lineage_cache_version: bool = True,
    result_payload: dict[str, object],
    source_version: object | None = None,
    rule_version: object | None = None,
    vendor_version: object | None = None,
    prefer_override: bool = False,
    quality_flag: QualityFlag | None = None,
    vendor_status: VendorStatus = "ok",
    fallback_mode: FallbackMode = "none",
    missing_field_message: LineageFieldMessageBuilder | None = None,
) -> dict[str, object]:
    return build_formal_result_envelope(
        result_meta=build_formal_result_meta_from_lineage(
            trace_id=trace_id,
            result_kind=result_kind,
            lineage=lineage,
            default_cache_version=default_cache_version,
            use_lineage_cache_version=use_lineage_cache_version,
            source_version=source_version,
            rule_version=rule_version,
            vendor_version=vendor_version,
            prefer_override=prefer_override,
            quality_flag=quality_flag,
            vendor_status=vendor_status,
            fallback_mode=fallback_mode,
            missing_field_message=missing_field_message,
        ),
        result_payload=result_payload,
    )


def _resolve_lineage_field(
    *,
    lineage: Mapping[str, object] | None,
    field_name: str,
    override: object | None = None,
    default: str | None = None,
    prefer_override: bool = False,
    missing_field_message: LineageFieldMessageBuilder | None = None,
) -> str:
    candidates = (
        (override, lineage.get(field_name) if lineage is not None else None)
        if prefer_override
        else (lineage.get(field_name) if lineage is not None else None, override)
    )
    for candidate in candidates:
        resolved = str(candidate or "").strip()
        if resolved:
            return resolved

    if default is not None:
        resolved_default = str(default).strip()
        if resolved_default:
            return resolved_default

    if missing_field_message is not None:
        raise RuntimeError(missing_field_message(field_name))
    raise RuntimeError(f"Formal result lineage field unavailable: {field_name}.")


def build_result_envelope(
    *,
    basis: ResultBasis,
    trace_id: str,
    result_kind: str,
    cache_version: str,
    source_version: str,
    rule_version: str,
    result_payload: dict[str, object],
    quality_flag: QualityFlag | None = None,
    vendor_version: str = "vv_none",
    vendor_status: VendorStatus = "ok",
    fallback_mode: FallbackMode = "none",
    filters_applied: Mapping[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    next_drill: list[str | dict[str, object]] | None = None,
) -> dict[str, object]:
    meta = _build_result_meta(
        basis=basis,
        trace_id=trace_id,
        result_kind=result_kind,
        cache_version=cache_version,
        source_version=source_version,
        rule_version=rule_version,
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status=vendor_status,
        fallback_mode=fallback_mode,
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        next_drill=next_drill,
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=result_payload,
    )
