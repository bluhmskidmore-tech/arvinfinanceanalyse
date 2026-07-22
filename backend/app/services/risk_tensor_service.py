from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import date
from pathlib import Path

from backend.app.governance.formal_compute_lineage import resolve_formal_manifest_lineage
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
)
from backend.app.repositories.risk_tensor_repo import (
    FACT_TABLE,
    RiskTensorRepository,
    load_current_tyw_liability_lineage_by_report_date,
    load_current_tyw_liability_rule_version,
    load_current_tyw_liability_source_version,
    load_latest_bond_analytics_lineage,
    load_latest_bond_analytics_lineage_by_report_date,
)
from backend.app.schemas.risk_tensor import RiskTensorPayload
from backend.app.services.explicit_numeric import promote_flat_payload
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope_from_lineage,
)
from backend.app.services.runtime_cache import get_runtime_cache

# 与 risk_tensor_materialize 对齐；只读路径不得 import tasks（broker/actor 注册）。
CACHE_KEY = "risk_tensor:materialize:formal"
CACHE_VERSION = "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v5"
RULE_VERSION = "rv_risk_tensor_formal_materialize_v5"

_RISK_TENSOR_CACHE_TTL_SECONDS = 300.0
_RISK_TENSOR_CACHE = get_runtime_cache(
    "risk_tensor.read_models",
    ttl_seconds=_RISK_TENSOR_CACHE_TTL_SECONDS,
)
_RiskTensorCacheKey = tuple[object, ...]
_MATERIALIZED_DURATION_SCOPE_FIELDS = (
    "rate_risk_market_value",
    "rate_risk_dv01",
    "rate_risk_modified_duration",
    "duration_excluded_market_value",
    "duration_excluded_count",
)


def _duckdb_storage_identity(duckdb_path: str) -> tuple[str, int, int] | None:
    path = Path(duckdb_path)
    if not path.exists():
        return None
    try:
        stat = path.stat()
        return (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None


def _governance_storage_identity(
    governance_dir: str,
) -> tuple[tuple[str, int, int], ...]:
    base_dir = Path(governance_dir)
    identities: list[tuple[str, int, int]] = []
    for stream in (CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM):
        path = base_dir / f"{stream}.jsonl"
        resolved_path = str(path.resolve())
        try:
            stat = path.stat()
            identities.append((resolved_path, stat.st_mtime_ns, stat.st_size))
        except OSError:
            identities.append((resolved_path, -1, -1))
    return tuple(identities)


def _risk_tensor_cache_key(
    endpoint: str,
    duckdb_path: str,
    governance_dir: str,
    *parts: object,
) -> _RiskTensorCacheKey | None:
    storage = _duckdb_storage_identity(duckdb_path)
    if storage is None:
        return None
    resolved_path, mtime_ns, size = storage
    governance_storage = _governance_storage_identity(governance_dir)
    return (
        endpoint,
        resolved_path,
        mtime_ns,
        size,
        governance_storage,
        RULE_VERSION,
        CACHE_VERSION,
        *parts,
    )


def _with_fresh_trace(envelope: dict[str, object]) -> dict[str, object]:
    response = deepcopy(envelope)
    meta = response.get("result_meta")
    if isinstance(meta, dict):
        meta["trace_id"] = _trace_id()
    return response


def invalidate_risk_tensor_read_cache() -> None:
    _RISK_TENSOR_CACHE.clear()


def risk_tensor_dates_envelope(
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, object]:
    cache_key = _risk_tensor_cache_key(
        "dates",
        duckdb_path,
        governance_dir,
    )
    if cache_key is not None:
        return _with_fresh_trace(
            _RISK_TENSOR_CACHE.get_or_set(
                cache_key,
                lambda: _risk_tensor_dates_envelope_uncached(
                    duckdb_path=duckdb_path,
                    governance_dir=governance_dir,
                ),
            )
        )
    return _risk_tensor_dates_envelope_uncached(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
    )


def _risk_tensor_dates_envelope_uncached(
    *,
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, object]:
    repo = RiskTensorRepository(str(duckdb_path))
    candidate_rows = repo.list_report_date_lineage_rows()
    candidate_report_dates = [str(row["report_date"]) for row in candidate_rows]
    report_dates: list[str] = []
    blocked_report_dates: list[dict[str, str]] = []
    try:
        bond_lineage_by_report_date = load_latest_bond_analytics_lineage_by_report_date(
            governance_dir=governance_dir,
        )
    except TimeoutError as exc:
        raise RuntimeError("Risk tensor lineage store is temporarily unavailable.") from exc
    tyw_liability_lineage_by_report_date = load_current_tyw_liability_lineage_by_report_date(
        duckdb_path=str(duckdb_path),
    )
    for row in candidate_rows:
        candidate_report_date = str(row["report_date"])
        bond_lineage = bond_lineage_by_report_date.get(candidate_report_date, {})
        tyw_liability_lineage = tyw_liability_lineage_by_report_date.get(candidate_report_date, {})
        stale_reason = _risk_tensor_freshness_error_from_values(
            report_date_text=candidate_report_date,
            row=row,
            upstream_source_version=str(bond_lineage.get("source_version") or ""),
            upstream_rule_version=str(bond_lineage.get("rule_version") or ""),
            upstream_cache_version=str(bond_lineage.get("cache_version") or ""),
            current_tyw_liability_source_version=str(
                tyw_liability_lineage.get("source_version") or ""
            ),
            current_tyw_liability_rule_version=str(
                tyw_liability_lineage.get("rule_version") or ""
            ),
        )
        if stale_reason is not None:
            blocked_report_dates.append(
                {
                    "report_date": candidate_report_date,
                    "reason": stale_reason,
                }
            )
            continue
        report_dates.append(candidate_report_date)

    latest_report_date = report_dates[0] if report_dates else None
    manifest_lineage: dict[str, object] | None = None
    source_version_value = "sv_risk_tensor_empty"
    rule_version_value = RULE_VERSION
    vendor_version_value = "vv_none"
    if candidate_report_dates:
        manifest_lineage = resolve_formal_manifest_lineage(
            governance_dir=governance_dir,
            cache_key=CACHE_KEY,
        )

    return build_formal_result_envelope_from_lineage(
        trace_id=_trace_id(),
        result_kind="risk.tensor.dates",
        lineage=manifest_lineage,
        default_cache_version=CACHE_VERSION,
        source_version=source_version_value,
        rule_version=rule_version_value,
        vendor_version=vendor_version_value,
        source_surface="risk_tensor",
        requested_report_date=latest_report_date,
        resolved_report_date=latest_report_date,
        as_of_date=latest_report_date,
        date_basis="formal_snapshot" if latest_report_date else None,
        result_payload={
            "report_dates": report_dates,
            "blocked_report_dates": blocked_report_dates,
        },
    )


def risk_tensor_envelope(
    duckdb_path: str,
    governance_dir: str,
    report_date: str | date,
) -> dict[str, object]:
    report_date_value = _coerce_report_date(report_date)
    report_date_text = report_date_value.isoformat()
    cache_key = _risk_tensor_cache_key(
        "tensor",
        duckdb_path,
        governance_dir,
        report_date_text,
    )
    if cache_key is not None:
        return _with_fresh_trace(
            _RISK_TENSOR_CACHE.get_or_set(
                cache_key,
                lambda: _risk_tensor_envelope_uncached(
                    duckdb_path=duckdb_path,
                    governance_dir=governance_dir,
                    report_date_value=report_date_value,
                    report_date_text=report_date_text,
                ),
            )
        )
    return _risk_tensor_envelope_uncached(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date_value=report_date_value,
        report_date_text=report_date_text,
    )


def _risk_tensor_envelope_uncached(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date_value: date,
    report_date_text: str,
) -> dict[str, object]:
    repo = RiskTensorRepository(str(duckdb_path))
    row = repo.fetch_risk_tensor_row(report_date_text)

    if row is None:
        upstream_lineage = load_latest_bond_analytics_lineage(
            governance_dir=governance_dir,
            report_date=report_date_text,
        )
        if upstream_lineage is None:
            raise ValueError(f"No risk tensor data found for report_date={report_date_text}.")
        raise RuntimeError(
            f"Risk tensor fact missing for report_date={report_date_text} while bond analytics lineage exists."
        )

    stale_reason = _risk_tensor_freshness_error(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date_text=report_date_text,
        row=row,
    )
    if stale_reason is not None:
        raise RuntimeError(stale_reason)

    projection_quality_fields = (
        "missing_maturity_market_value",
        "missing_maturity_count",
        "floating_rate_proxy_market_value",
        "floating_rate_proxy_count",
        "payment_frequency_fallback_market_value",
        "payment_frequency_fallback_count",
        "bullet_value_date_fallback_market_value",
        "bullet_value_date_fallback_count",
    )
    projection_quality_available = all(row.get(field) is not None for field in projection_quality_fields)
    row_warnings = list(row["warnings"])
    if not projection_quality_available:
        row_warnings.append(
            "Projection-quality proxy metrics are unavailable for this legacy risk tensor row; "
            "zero must not be inferred."
        )
    payload_quality_flag = str(row["quality_flag"])
    if not projection_quality_available:
        payload_quality_flag = "warning"

    payload = RiskTensorPayload.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date_value,
                "portfolio_dv01": row["portfolio_dv01"],
                "regulatory_dv01": row["regulatory_dv01"],
                "krd_1y": row["krd_1y"],
                "krd_3y": row["krd_3y"],
                "krd_5y": row["krd_5y"],
                "krd_7y": row["krd_7y"],
                "krd_10y": row["krd_10y"],
                "krd_30y": row["krd_30y"],
                "cs01": row["cs01"],
                "portfolio_convexity": row["portfolio_convexity"],
                "portfolio_modified_duration": row["portfolio_modified_duration"],
                "issuer_concentration_hhi": row["issuer_concentration_hhi"],
                "issuer_top5_weight": row["issuer_top5_weight"],
                "asset_cashflow_30d": row["asset_cashflow_30d"],
                "asset_cashflow_90d": row["asset_cashflow_90d"],
                "liability_cashflow_30d": row["liability_cashflow_30d"],
                "liability_cashflow_90d": row["liability_cashflow_90d"],
                "liquidity_gap_30d": row["liquidity_gap_30d"],
                "liquidity_gap_90d": row["liquidity_gap_90d"],
                "liquidity_gap_30d_ratio": row["liquidity_gap_30d_ratio"],
                "total_market_value": row["total_market_value"],
                "rate_risk_market_value": row["rate_risk_market_value"],
                "rate_risk_dv01": row["rate_risk_dv01"],
                "rate_risk_modified_duration": row["rate_risk_modified_duration"],
                "duration_excluded_market_value": row["duration_excluded_market_value"],
                "duration_excluded_count": row["duration_excluded_count"],
                "missing_maturity_market_value": row.get("missing_maturity_market_value"),
                "missing_maturity_count": row.get("missing_maturity_count"),
                "floating_rate_proxy_market_value": row.get("floating_rate_proxy_market_value"),
                "floating_rate_proxy_count": row.get("floating_rate_proxy_count"),
                "payment_frequency_fallback_market_value": row.get(
                    "payment_frequency_fallback_market_value"
                ),
                "payment_frequency_fallback_count": row.get("payment_frequency_fallback_count"),
                "bullet_value_date_fallback_market_value": row.get(
                    "bullet_value_date_fallback_market_value"
                ),
                "bullet_value_date_fallback_count": row.get("bullet_value_date_fallback_count"),
                "projection_quality_status": (
                    "available" if projection_quality_available else "unavailable_legacy"
                ),
                "bond_count": int(row["bond_count"]),
                "quality_flag": payload_quality_flag,
                "warnings": row_warnings,
            },
            RiskTensorPayload,
        )
    )
    envelope = build_formal_result_envelope_from_lineage(
        trace_id=_trace_id(),
        result_kind="risk.tensor",
        lineage=row,
        default_cache_version=CACHE_VERSION,
        source_version=str(row["source_version"]),
        rule_version=str(row.get("rule_version") or RULE_VERSION),
        vendor_version="vv_none",
        quality_flag=payload.quality_flag,
        source_surface="risk_tensor",
        requested_report_date=report_date_text,
        resolved_report_date=report_date_text,
        as_of_date=report_date_text,
        date_basis="formal_snapshot",
        fallback_date=None,
        result_payload=payload.model_dump(mode="json"),
    )
    envelope["result_meta"]["tables_used"] = [FACT_TABLE]
    envelope["result_meta"]["evidence_rows"] = 1
    return envelope


def risk_tensor_history_envelope(
    duckdb_path: str,
    governance_dir: str,
    report_date: str | date,
    periods: int,
) -> dict[str, object]:
    report_date_value = _coerce_report_date(report_date)
    report_date_text = report_date_value.isoformat()
    periods_value = max(2, min(int(periods), 60))
    cache_key = _risk_tensor_cache_key(
        "tensor_history",
        duckdb_path,
        governance_dir,
        report_date_text,
        periods_value,
    )
    if cache_key is not None:
        return _with_fresh_trace(
            _RISK_TENSOR_CACHE.get_or_set(
                cache_key,
                lambda: _risk_tensor_history_envelope_uncached(
                    duckdb_path=duckdb_path,
                    governance_dir=governance_dir,
                    report_date_value=report_date_value,
                    report_date_text=report_date_text,
                    periods_value=periods_value,
                ),
            )
        )
    return _risk_tensor_history_envelope_uncached(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date_value=report_date_value,
        report_date_text=report_date_text,
        periods_value=periods_value,
    )


def _risk_tensor_history_envelope_uncached(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date_value: date,
    report_date_text: str,
    periods_value: int,
) -> dict[str, object]:
    repo = RiskTensorRepository(str(duckdb_path))
    latest_row = repo.fetch_risk_tensor_row(report_date_text)

    if latest_row is None:
        upstream_lineage = load_latest_bond_analytics_lineage(
            governance_dir=governance_dir,
            report_date=report_date_text,
        )
        if upstream_lineage is None:
            raise ValueError(f"No risk tensor data found for report_date={report_date_text}.")
        raise RuntimeError(
            f"Risk tensor fact missing for report_date={report_date_text} while bond analytics lineage exists."
        )

    stale_reason = _risk_tensor_freshness_error(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date_text=report_date_text,
        row=latest_row,
    )
    if stale_reason is not None:
        raise RuntimeError(stale_reason)

    rows_desc = repo.fetch_risk_tensor_history(report_date_text, periods_value)
    if not rows_desc:
        raise ValueError(f"No risk tensor history found for report_date={report_date_text}.")

    points = [
        {
            "report_date": str(row["report_date"]),
            "portfolio_dv01": _history_scalar(row["portfolio_dv01"]),
            "regulatory_dv01": _history_scalar(row["regulatory_dv01"]),
            "portfolio_modified_duration": _history_scalar(row["portfolio_modified_duration"]),
            "portfolio_convexity": _history_scalar(row["portfolio_convexity"]),
            "cs01": _history_scalar(row["cs01"]),
            "issuer_concentration_hhi": _history_scalar(row["issuer_concentration_hhi"]),
            "issuer_top5_weight": _history_scalar(row["issuer_top5_weight"]),
            "liquidity_gap_30d": _history_scalar(row["liquidity_gap_30d"]),
        }
        for row in reversed(rows_desc)
    ]
    payload = {
        "report_date": report_date_text,
        "periods": len(points),
        "window": {"from": points[0]["report_date"], "to": points[-1]["report_date"]},
        "points": points,
    }
    envelope = build_formal_result_envelope_from_lineage(
        trace_id=_trace_id(),
        result_kind="risk.tensor.history",
        lineage=latest_row,
        default_cache_version=CACHE_VERSION,
        source_version=str(latest_row["source_version"]),
        rule_version=str(latest_row.get("rule_version") or RULE_VERSION),
        vendor_version="vv_none",
        quality_flag=str(latest_row["quality_flag"]),
        source_surface="risk_tensor",
        requested_report_date=report_date_text,
        resolved_report_date=report_date_text,
        as_of_date=report_date_text,
        date_basis="formal_snapshot",
        fallback_date=None,
        result_payload=payload,
    )
    envelope["result_meta"]["tables_used"] = [FACT_TABLE]
    envelope["result_meta"]["evidence_rows"] = len(points)
    return envelope


def _history_scalar(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _risk_tensor_freshness_error(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date_text: str,
    row: dict[str, object] | None,
) -> str | None:
    if row is None:
        return f"Risk tensor fact missing for report_date={report_date_text}."

    upstream_lineage = load_latest_bond_analytics_lineage(
        governance_dir=governance_dir,
        report_date=report_date_text,
    )
    if upstream_lineage is None or not upstream_lineage["source_version"]:
        upstream_source_version = ""
        upstream_rule_version = ""
        upstream_cache_version = ""
    else:
        upstream_source_version = upstream_lineage["source_version"]
        upstream_rule_version = upstream_lineage["rule_version"]
        upstream_cache_version = upstream_lineage["cache_version"]

    current_tyw_liability_source_version = load_current_tyw_liability_source_version(
        duckdb_path=str(duckdb_path),
        report_date=report_date_text,
    )
    current_tyw_liability_rule_version = load_current_tyw_liability_rule_version(
        duckdb_path=str(duckdb_path),
        report_date=report_date_text,
    )

    return _risk_tensor_freshness_error_from_values(
        report_date_text=report_date_text,
        row=row,
        upstream_source_version=upstream_source_version,
        upstream_rule_version=upstream_rule_version,
        upstream_cache_version=upstream_cache_version,
        current_tyw_liability_source_version=current_tyw_liability_source_version,
        current_tyw_liability_rule_version=current_tyw_liability_rule_version,
    )


def _risk_tensor_freshness_error_from_values(
    *,
    report_date_text: str,
    row: dict[str, object] | None,
    upstream_source_version: str,
    upstream_rule_version: str,
    upstream_cache_version: str,
    current_tyw_liability_source_version: str,
    current_tyw_liability_rule_version: str,
) -> str | None:
    if row is None:
        return f"Risk tensor fact missing for report_date={report_date_text}."

    stored_rule_version = str(row.get("rule_version") or "").strip()
    if stored_rule_version != RULE_VERSION:
        return (
            f"Risk tensor stale against rule version for report_date={report_date_text}; "
            f"expected {RULE_VERSION}, got {stored_rule_version or 'missing'}. Rematerialize required."
        )

    stored_cache_version = str(row.get("cache_version") or "").strip()
    if stored_cache_version != CACHE_VERSION:
        return (
            f"Risk tensor stale against cache version for report_date={report_date_text}; "
            f"expected {CACHE_VERSION}, got {stored_cache_version or 'missing'}. Rematerialize required."
        )

    missing_duration_scope = [
        field_name
        for field_name in _MATERIALIZED_DURATION_SCOPE_FIELDS
        if row.get(field_name) is None
    ]
    if missing_duration_scope:
        return (
            "Risk tensor materialized duration-scope metrics missing for "
            f"report_date={report_date_text}: {', '.join(missing_duration_scope)}. "
            "Rematerialize required."
        )

    if not upstream_source_version or not upstream_rule_version or not upstream_cache_version:
        return (
            f"Bond analytics lineage missing for report_date={report_date_text}; "
            "cannot validate risk tensor freshness."
        )

    if str(row.get("upstream_source_version") or "").strip() != upstream_source_version:
        return f"Risk tensor stale against bond analytics lineage for report_date={report_date_text}."

    if str(row.get("upstream_rule_version") or "").strip() != upstream_rule_version:
        return f"Risk tensor stale against bond analytics rule lineage for report_date={report_date_text}."

    if str(row.get("upstream_cache_version") or "").strip() != upstream_cache_version:
        return f"Risk tensor stale against bond analytics cache lineage for report_date={report_date_text}."

    stored_tyw_liability_source_version = str(row.get("liability_source_version") or "").strip()
    if current_tyw_liability_source_version and (
        stored_tyw_liability_source_version != current_tyw_liability_source_version
    ):
        return f"Risk tensor stale against TYW liability lineage for report_date={report_date_text}."

    stored_tyw_liability_rule_version = str(row.get("liability_rule_version") or "").strip()
    if current_tyw_liability_rule_version and (
        stored_tyw_liability_rule_version != current_tyw_liability_rule_version
    ):
        return f"Risk tensor stale against TYW liability lineage for report_date={report_date_text}."
    return None


def _coerce_report_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
