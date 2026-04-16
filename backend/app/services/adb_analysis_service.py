"""
日均资产负债（ADB）分析服务层。

- service 只负责参数解析、仓储调用、payload builder 编排与 analytical envelope 组装。
- DuckDB/formal-fact 读取由 `backend.app.repositories.adb_repo` 负责。
- ADB 纯计算由 `backend.app.core_finance.adb_analysis` 负责。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from backend.app.core_finance.adb_analysis import (
    ADB_SINGLE_SNAPSHOT_DETAIL,
    build_adb_comparison_payload,
    build_adb_daily_payload,
    build_adb_monthly_payload,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.adb_repo import AdbRepository
from backend.app.services.formal_result_runtime import build_result_envelope

ADB_CACHE_VERSION = "cv_adb_analysis_v1"
ADB_EMPTY_SOURCE_VERSION = "sv_adb_empty"
ADB_RULE_VERSION = "rv_adb_analysis_v1"


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def _merge_versions(values: list[str], default: str) -> str:
    merged = sorted({str(value or "").strip() for value in values if str(value or "").strip()})
    return "__".join(merged) or default


def _build_analytical_envelope(
    *,
    result_kind: str,
    result_payload: dict[str, Any],
    source_versions: list[str],
    rule_versions: list[str],
    quality_flag: str = "ok",
) -> dict[str, Any]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_{result_kind.replace('.', '_')}",
        result_kind=result_kind,
        cache_version=ADB_CACHE_VERSION,
        source_version=_merge_versions(source_versions, ADB_EMPTY_SOURCE_VERSION),
        rule_version=_merge_versions(rule_versions, ADB_RULE_VERSION),
        quality_flag=quality_flag,
        vendor_version="vv_none",
        result_payload=result_payload,
    )


def calculate_adb(
    duckdb_path: str,
    start_date: date,
    end_date: date,
) -> tuple[dict[str, Any], list[str], list[str]]:
    repo = AdbRepository(duckdb_path)
    bonds_df, interbank_df, source_versions, rule_versions = repo.load_raw_data(start_date, end_date)
    payload = build_adb_daily_payload(
        bonds_df=bonds_df,
        interbank_df=interbank_df,
        start_date=start_date,
        end_date=end_date,
    )
    return payload, source_versions, rule_versions


def get_adb_comparison(
    duckdb_path: str,
    start_date: date,
    end_date: date,
    top_n: int = 20,
    simulate_if_single_snapshot: bool = True,
) -> tuple[dict[str, Any], list[str], list[str]]:
    repo = AdbRepository(duckdb_path)
    bonds_df, interbank_df, source_versions, rule_versions = repo.load_raw_data(start_date, end_date)
    payload = build_adb_comparison_payload(
        bonds_df=bonds_df,
        interbank_df=interbank_df,
        start_date=start_date,
        end_date=end_date,
        top_n=top_n,
        simulate_if_single_snapshot=simulate_if_single_snapshot,
    )
    return payload, source_versions, rule_versions


def calculate_monthly_adb(duckdb_path: str, year: int) -> tuple[dict[str, Any], list[str], list[str]]:
    today = date.today()
    start_date = date(year, 1, 1)
    end_date = min(date(year, 12, 31), today)
    repo = AdbRepository(duckdb_path)
    bonds_df, interbank_df, source_versions, rule_versions = repo.load_raw_data(start_date, end_date)
    payload = build_adb_monthly_payload(
        bonds_df=bonds_df,
        interbank_df=interbank_df,
        year=year,
        as_of_date=end_date,
    )
    return payload, source_versions, rule_versions


def adb_envelope_for_dates(start_date: str, end_date: str) -> dict[str, Any]:
    settings = get_settings()
    payload, source_versions, rule_versions = calculate_adb(
        str(settings.duckdb_path),
        _parse_date(start_date),
        _parse_date(end_date),
    )
    return _build_analytical_envelope(
        result_kind="adb.daily",
        result_payload=payload,
        source_versions=source_versions,
        rule_versions=rule_versions,
    )


def adb_comparison_envelope(start_date: str, end_date: str, top_n: int = 20) -> dict[str, Any]:
    settings = get_settings()
    payload, source_versions, rule_versions = get_adb_comparison(
        str(settings.duckdb_path),
        _parse_date(start_date),
        _parse_date(end_date),
        top_n=top_n,
    )
    simulated = bool(payload.get("simulated"))
    if simulated and not str(payload.get("detail") or "").strip():
        payload = {**payload, "detail": ADB_SINGLE_SNAPSHOT_DETAIL}
    return _build_analytical_envelope(
        result_kind="adb.comparison",
        result_payload=payload,
        source_versions=source_versions,
        rule_versions=rule_versions,
        quality_flag="warning" if simulated else "ok",
    )


def adb_monthly_envelope(year: int) -> dict[str, Any]:
    settings = get_settings()
    payload, source_versions, rule_versions = calculate_monthly_adb(
        str(settings.duckdb_path),
        year,
    )
    return _build_analytical_envelope(
        result_kind="adb.monthly",
        result_payload=payload,
        source_versions=source_versions,
        rule_versions=rule_versions,
    )
