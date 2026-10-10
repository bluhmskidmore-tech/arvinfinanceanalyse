"""Home 快照/收益趋势支撑纯工具(自 executive_service.py 门面拆分,逐字迁移)。

本模块只包含无副作用的支撑函数与不可变常量:home income 基准告警解析与
数值换算、cache_build_run 完成记录选择、治理文件/DuckDB 文件边缘指纹。
不读 settings、不触门面缓存全局、不写日志;可变缓存与锁全部留在门面。
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from backend.app.schemas.common_numeric import Numeric
from backend.app.services.bond_analytics_service import (
    BENCHMARK_EXCESS_RECON_GAP,
    BOND_ANALYTICS_FOREIGN_CURRENCY_FALLBACK_WARNING,
)
from backend.app.services.executive_service_formatting import _BASIS_POINTS_PER_PERCENT

_HOME_INCOME_BENCHMARK_ID = "CDB_INDEX"
_HOME_INCOME_BENCHMARK_PERIOD_TYPE = "MoM"
_HOME_INCOME_CURVE_FALLBACK_PREFIX = "YIELD_CURVE_LATEST_FALLBACK"
_HOME_INCOME_MAX_CURVE_FALLBACK_DAYS = 7


_HOME_CACHE_GOVERNANCE_FILES = ("cache_manifest.jsonl", "cache_build_run.jsonl")
_HOME_CACHE_GOVERNANCE_TAIL_BYTES = 8192


def _latest_completed_cache_build_run(
    rows: list[dict[str, object]],
    *,
    cache_key: str,
    job_name: str,
    report_date: str,
    require_source_version: bool = False,
) -> dict[str, object] | None:
    for row in reversed(rows):
        if str(row.get("cache_key") or "").strip() != cache_key:
            continue
        if str(row.get("status") or "").strip() != "completed":
            continue
        if str(row.get("job_name") or "").strip() != job_name:
            continue
        if str(row.get("report_date") or "").strip() != report_date:
            continue
        if require_source_version and not str(row.get("source_version") or "").strip():
            continue
        return row
    return None


def _home_income_null_pnl() -> Numeric:
    return Numeric(
        raw=None,
        unit="yuan",
        display="-",
        precision=2,
        sign_aware=True,
    )


def _numeric_raw_and_unit_from_payload(value: object) -> tuple[float | None, str | None]:
    if isinstance(value, Numeric):
        return value.raw, value.unit
    if isinstance(value, dict):
        raw_value = value.get("raw")
        unit_value = value.get("unit")
    else:
        raw_value = getattr(value, "raw", value)
        unit_value = getattr(value, "unit", None)
    if raw_value is None:
        return None, str(unit_value) if unit_value else None
    try:
        return float(raw_value), str(unit_value) if unit_value else None
    except (TypeError, ValueError):
        return None, str(unit_value) if unit_value else None


def _home_income_pct_points_from_payload(value: object) -> float | None:
    raw, unit = _numeric_raw_and_unit_from_payload(value)
    if raw is None:
        return None
    if unit == "pct":
        return raw * _BASIS_POINTS_PER_PERCENT
    if unit == "bp":
        return raw / _BASIS_POINTS_PER_PERCENT
    # Bond analytics collapses governed pct Numerics to flat Q8 strings while
    # preserving their canonical decimal-ratio raw value.
    return raw * _BASIS_POINTS_PER_PERCENT


def _home_income_bp_points_from_payload(value: object) -> float | None:
    raw, unit = _numeric_raw_and_unit_from_payload(value)
    if raw is None:
        return None
    if unit == "pct":
        return raw * _BASIS_POINTS_PER_PERCENT
    return raw / _BASIS_POINTS_PER_PERCENT


def _home_income_benchmark_warning(point_date: str, reason: object) -> str:
    text = str(reason or "").strip()
    if not text:
        text = "benchmark/excess return unavailable"
    return f"{point_date} {_HOME_INCOME_BENCHMARK_ID}: {text}"


def _home_income_warning_date(text: str, marker: str) -> date | None:
    marker_index = text.find(marker)
    if marker_index < 0:
        return None
    try:
        return date.fromisoformat(text[marker_index + len(marker): marker_index + len(marker) + 10])
    except ValueError:
        return None


def _is_bounded_home_income_curve_fallback(reason: object) -> bool:
    text = str(reason or "")
    if _HOME_INCOME_CURVE_FALLBACK_PREFIX not in text:
        return False
    resolved_date = _home_income_warning_date(text, "from trade_date=")
    requested_date = _home_income_warning_date(text, "requested_trade_date=")
    if resolved_date is None or requested_date is None:
        return False
    fallback_days = (requested_date - resolved_date).days
    return 0 <= fallback_days <= _HOME_INCOME_MAX_CURVE_FALLBACK_DAYS


def _is_home_income_amount_disclosure_warning(reason: object) -> bool:
    return BOND_ANALYTICS_FOREIGN_CURRENCY_FALLBACK_WARNING in str(reason or "")


def _is_home_income_reconciliation_warning(reason: object) -> bool:
    return BENCHMARK_EXCESS_RECON_GAP in str(reason or "")


def _home_income_blocking_benchmark_reasons(
    benchmark_warnings: list[object],
    *,
    vendor_status: str,
) -> list[object]:
    has_bounded_curve_fallback = any(
        _is_bounded_home_income_curve_fallback(warning)
        for warning in benchmark_warnings
    )
    blocking_reasons: list[object] = [
        warning
        for warning in benchmark_warnings
        if not (
            _is_bounded_home_income_curve_fallback(warning)
            or _is_home_income_amount_disclosure_warning(warning)
            or _is_home_income_reconciliation_warning(warning)
        )
    ]
    if vendor_status != "ok" and not (
        vendor_status == "vendor_stale" and has_bounded_curve_fallback and not blocking_reasons
    ):
        blocking_reasons.append(f"vendor_status={vendor_status}")
    return blocking_reasons


_HomeGovernanceFileFingerprint = tuple[str, int, int, str]


def _duckdb_file_edge_hash(path: Path, *, stat_size: int) -> str | None:
    try:
        with path.open("rb") as handle:
            head = handle.read(_HOME_CACHE_GOVERNANCE_TAIL_BYTES)
            if stat_size > _HOME_CACHE_GOVERNANCE_TAIL_BYTES:
                handle.seek(-_HOME_CACHE_GOVERNANCE_TAIL_BYTES, 2)
                tail = handle.read(_HOME_CACHE_GOVERNANCE_TAIL_BYTES)
            else:
                tail = b""
    except OSError:
        return None
    digest = hashlib.sha256()
    digest.update(head)
    digest.update(tail)
    return digest.hexdigest()


def _governance_file_fingerprint(
    base_dir: object,
    stream: str,
) -> _HomeGovernanceFileFingerprint | None:
    base_path = Path(str(base_dir))
    path = base_path / f"{stream}.jsonl"
    try:
        stat = path.stat()
    except OSError:
        return None
    if not path.is_file():
        return None
    try:
        with path.open("rb") as handle:
            if stat.st_size > _HOME_CACHE_GOVERNANCE_TAIL_BYTES:
                handle.seek(-_HOME_CACHE_GOVERNANCE_TAIL_BYTES, 2)
            content = handle.read()
    except OSError:
        return None
    return (stream, stat.st_size, stat.st_mtime_ns, hashlib.sha256(content).hexdigest())


def _selected_governance_files_fingerprint(
    base_dir: object,
) -> tuple[tuple[str, int, int, str], ...] | None:
    base_path = Path(str(base_dir))
    if not str(base_dir or "").strip():
        return None
    fingerprint: list[tuple[str, int, int, str]] = []
    for filename in _HOME_CACHE_GOVERNANCE_FILES:
        path = base_path / filename
        try:
            stat = path.stat()
        except OSError:
            return None
        if not path.is_file():
            return None
        try:
            with path.open("rb") as handle:
                if stat.st_size > _HOME_CACHE_GOVERNANCE_TAIL_BYTES:
                    handle.seek(-_HOME_CACHE_GOVERNANCE_TAIL_BYTES, 2)
                content = handle.read()
        except OSError:
            return None
        fingerprint.append((filename, stat.st_size, stat.st_mtime_ns, hashlib.sha256(content).hexdigest()))
    return tuple(fingerprint)
