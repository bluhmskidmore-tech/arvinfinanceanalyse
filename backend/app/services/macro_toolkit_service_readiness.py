"""宏观工具箱模型就绪度 / 产物健康 / 运行清单支撑。

代码自 macro_toolkit_service.py 门面拆分逐字迁入；语义与行为不变。
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
from backend.app.core_finance.macro.toolkit.runner import iter_toolkit_scripts
from backend.app.services.macro_toolkit_service_support import (
    MACRO_TOOLKIT_FORMAL_USE_ALLOWED,
    MACRO_TOOLKIT_MODEL_READINESS_SURFACE,
    MACRO_TOOLKIT_OBSERVATION_ONLY,
    MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS,
    MACRO_TOOLKIT_RUN_CHAIN_ENDPOINT,
)


_MACRO_MODEL_DEFINITIONS: tuple[dict[str, object], ...] = (
    {
        "id": "merrill_clock",
        "label": "Merrill Clock",
        "script_name": "merrill_clock_cn",
        "expected_outputs": ("merrill_clock_latest.csv", "merrill_clock_history.csv"),
        "notes": ("Macro cycle and asset allocation candidate signal.",),
    },
    {
        "id": "crisis_score",
        "label": "Crisis Score",
        "script_name": "crisis_score_cn",
        "expected_outputs": ("crisis_score_latest.csv", "crisis_score_history.csv"),
        "notes": ("Stress score candidate signal.",),
    },
    {
        "id": "bond_futures_basis",
        "label": "Bond Futures Basis / IRR / Safety Margin",
        "script_name": "bond_futures_data",
        "expected_outputs": ("bond_futures_latest.csv", "bond_futures_history.csv"),
        "notes": ("Treasury futures basis and safety-margin evidence.",),
    },
    {
        "id": "bond_futures_four_factor",
        "label": "Bond Futures Four-Factor Trend",
        "script_name": "bond_futures_signals",
        "expected_outputs": ("bond_signals_latest.csv",),
        "notes": ("MA, channel, MACD and Bollinger style treasury-futures signal evidence.",),
    },
    {
        "id": "funding_conditions",
        "label": "Funding Conditions / Flow",
        "script_name": "merrill_clock_cn",
        "expected_outputs": ("merrill_clock_latest.csv",),
        "notes": ("Funding condition is evidenced through DR007/NCD inputs and Merrill liquidity momentum, not a standalone formal metric.",),
    },
    {
        "id": "crowding",
        "label": "Crowding",
        "script_name": "crowding_cn",
        "expected_outputs": ("crowding_latest.csv", "crowding_history.csv"),
        "notes": ("Crowding candidate signal.",),
    },
    {
        "id": "dcc_garch",
        "label": "DCC-GARCH",
        "script_name": "dcc_garch_cn",
        "expected_outputs": ("dcc_latest.csv", "dcc_results.csv"),
        "notes": ("Dynamic conditional correlation candidate signal.",),
    },
    {
        "id": "cta_trend",
        "label": "CTA Trend",
        "script_name": "cta_trend_cn",
        "expected_outputs": ("cta_results.csv",),
        "notes": ("CTA trend candidate signal.",),
    },
    {
        "id": "final_signal",
        "label": "Final Signal Aggregator",
        "script_name": "signal_aggregator",
        "expected_outputs": ("final_signal.csv",),
        "notes": ("Aggregates macro, bond futures, crisis and crowding evidence.",),
    },
    {
        "id": "risk_monitor",
        "label": "Risk Monitor",
        "script_name": "risk_monitor",
        "expected_outputs": ("risk_state.csv", "risk_log.csv"),
        "notes": ("Risk warning threshold monitor.",),
    },
)


def _macro_readiness_degraded_reason(
    *,
    readiness: str,
    script_available: bool,
    missing_outputs: list[str],
    stale_outputs: list[str],
    degraded_outputs: list[str],
) -> str | None:
    if not script_available:
        return "script_unavailable"
    if missing_outputs:
        return "missing_expected_outputs"
    if stale_outputs:
        return "stale_expected_outputs"
    if degraded_outputs:
        return "indeterminate_output_dates"
    if readiness == "registered_only":
        return "no_expected_outputs_registered"
    return None


def _macro_readiness_evidence_level(*, readiness: str, present_count: int) -> str:
    if readiness == "artifact_backed":
        return "fresh_artifacts"
    if present_count:
        return "partial_artifacts"
    return "registered_script_only"


def _macro_readiness_date_basis(outputs: list[dict[str, object]]) -> str:
    statuses = {str(item["freshness_status"]) for item in outputs}
    if not outputs or statuses == {"missing"}:
        return "missing"
    bases = {
        str(item["freshness_basis"])
        for item in outputs
        if item.get("freshness_basis") and item["freshness_status"] != "missing"
    }
    if "csv_content" in bases:
        return "csv_content"
    if "file_modified_date" in bases:
        return "file_modified_date"
    return "unknown"


def _macro_artifact_receipt(
    *,
    model_id: str,
    script_name: str,
    readiness: str,
    outputs: list[dict[str, object]],
    degraded_reason: str | None,
    data_asof: str | None,
) -> dict[str, object]:
    return {
        "status": readiness,
        "model_id": model_id,
        "script_name": script_name,
        "artifact_paths": sorted(str(item["name"]) for item in outputs if item["freshness_status"] != "missing"),
        "missing_artifacts": sorted(str(item["name"]) for item in outputs if item["freshness_status"] == "missing"),
        "degraded_reason": degraded_reason,
        "data_asof": data_asof,
        "generated_at": datetime.now(UTC).isoformat(),
        "runtime_endpoint": MACRO_TOOLKIT_RUN_CHAIN_ENDPOINT,
        "page_surface": MACRO_TOOLKIT_MODEL_READINESS_SURFACE,
        "formal_use_allowed": MACRO_TOOLKIT_FORMAL_USE_ALLOWED,
        "observation_only": MACRO_TOOLKIT_OBSERVATION_ONLY,
    }


def _macro_output_health(
    name: str,
    file_payload: dict[str, object] | None,
    *,
    reference_date: str | None,
) -> dict[str, object]:
    if file_payload is None:
        return {
            "name": name,
            "freshness_status": "missing",
            "freshness_basis": "missing",
            "modified_at": None,
            "modified_date": None,
            "content_date": None,
            "content_date_min": None,
            "content_date_max": None,
            "content_date_invalid_count": 0,
            "reference_date": reference_date,
        }
    modified_at = str(file_payload.get("modified_at") or "").strip() or None
    modified_date = _macro_output_modified_date(modified_at)
    content_dates = _macro_output_content_dates(file_payload)
    content_date = content_dates["max"]
    content_date_min = content_dates["min"]
    content_date_max = content_dates["max"]
    content_date_invalid_count = int(content_dates["invalid_count"] or 0)
    has_content_date_column = bool(content_dates["date_column"])
    freshness_basis = "csv_content" if has_content_date_column else "file_modified_date"
    freshness_status = _macro_output_health_status(
        name=name,
        content_date=content_date,
        content_date_min=content_date_min,
        content_date_max=content_date_max,
        content_date_invalid_count=content_date_invalid_count,
        has_content_date_column=has_content_date_column,
        modified_date=modified_date,
        reference_date=reference_date,
    )
    return {
        "name": name,
        "freshness_status": freshness_status,
        "freshness_basis": freshness_basis,
        "modified_at": modified_at,
        "modified_date": modified_date,
        "content_date": content_date,
        "content_date_min": content_date_min,
        "content_date_max": content_date_max,
        "content_date_invalid_count": content_date_invalid_count,
        "reference_date": reference_date,
    }


def _macro_output_modified_date(modified_at: str | None) -> str | None:
    if not modified_at:
        return None
    try:
        parsed = datetime.fromisoformat(modified_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.date().isoformat()
    return parsed.astimezone(UTC).date().isoformat()


def _macro_output_content_dates(file_payload: dict[str, object]) -> dict[str, str | int | None]:
    path_value = file_payload.get("path")
    if not path_value:
        return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
    path = Path(str(path_value))
    if not path.is_file():
        return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
    try:
        columns = pd.read_csv(path, nrows=0).columns
        date_column = next((column for column in MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS if column in columns), None)
        if date_column is None:
            return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
        frame = pd.read_csv(path, usecols=[date_column])
    except (OSError, UnicodeError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
    if frame.empty:
        return {"min": None, "max": None, "invalid_count": 0, "date_column": date_column}
    raw_dates = frame[date_column].dropna()
    parsed = pd.to_datetime(raw_dates, errors="coerce")
    invalid_count = int(parsed.isna().sum())
    parsed = parsed.dropna()
    if parsed.empty:
        return {"min": None, "max": None, "invalid_count": invalid_count, "date_column": date_column}
    return {
        "min": parsed.min().date().isoformat(),
        "max": parsed.max().date().isoformat(),
        "invalid_count": invalid_count,
        "date_column": date_column,
    }


def _macro_output_health_status(
    *,
    name: str,
    content_date: str | None,
    content_date_min: str | None,
    content_date_max: str | None,
    content_date_invalid_count: int,
    has_content_date_column: bool,
    modified_date: str | None,
    reference_date: str | None,
) -> str:
    if content_date_invalid_count:
        return "invalid_date"
    if has_content_date_column and not content_date:
        return "unknown"
    if _is_generation_evidence_artifact(name):
        return _macro_generation_freshness(content_date or modified_date, reference_date)
    if _is_monthly_cadence_artifact(name):
        return _macro_monthly_output_freshness(content_date, reference_date)
    if content_date_min and content_date_max and content_date_min != content_date_max:
        if _is_history_artifact(name):
            return _macro_output_freshness(content_date, reference_date)
        return "mixed"
    if has_content_date_column:
        return _macro_output_freshness(content_date, reference_date)
    return _macro_generation_freshness(modified_date, reference_date)


def _is_history_artifact(name: str) -> bool:
    stem = Path(name).stem.lower()
    return stem.endswith("_history") or stem.endswith("_results") or stem.endswith("_log")


def _is_generation_evidence_artifact(name: str) -> bool:
    return Path(name).name.lower() in {"risk_state.csv", "risk_log.csv"}


# 内容为月度频率的产物：新鲜度按月度容差判定（日度精确相等口径会让它们结构性 stale）。
_MONTHLY_CADENCE_ARTIFACTS = frozenset({"merrill_clock_latest.csv", "merrill_clock_history.csv"})


def _is_monthly_cadence_artifact(name: str) -> bool:
    return Path(name).name.lower() in _MONTHLY_CADENCE_ARTIFACTS


def _macro_monthly_output_freshness(output_date: str | None, reference_date: str | None) -> str:
    """月度产物新鲜度：内容月份不早于基准日上月即 current。

    月度宏观数据（如 CPI/PMI/社融）在次月中上旬才发布，"基准月或上月"的内容
    即为最新可得；早于上月说明该发布的数据未入库，判 stale。
    """
    if not output_date:
        return "unknown"
    if not reference_date:
        return "present"
    try:
        output_day = date.fromisoformat(output_date[:10])
        reference_day = date.fromisoformat(reference_date[:10])
    except ValueError:
        return "unknown"
    output_month = output_day.year * 12 + output_day.month
    reference_month = reference_day.year * 12 + reference_day.month
    if output_month > reference_month:
        return "future"
    return "current" if output_month >= reference_month - 1 else "stale"


def _macro_output_freshness(output_date: str | None, reference_date: str | None) -> str:
    if not output_date:
        return "unknown"
    if not reference_date:
        return "present"
    try:
        output_day = date.fromisoformat(output_date[:10])
        reference_day = date.fromisoformat(reference_date[:10])
    except ValueError:
        return "unknown"
    if output_day > reference_day:
        return "future"
    return "current" if output_day == reference_day else "stale"


def _macro_generation_freshness(modified_date: str | None, reference_date: str | None) -> str:
    status = _macro_output_freshness(modified_date, reference_date)
    return "current" if status == "future" else status


def _macro_run_manifest() -> list[dict[str, object]]:
    labels_by_script = {
        "merrill_clock_cn": "Merrill Clock",
        "crisis_score_cn": "Crisis Score",
        "bond_futures_data": "Bond Futures Basis / IRR / Safety Margin",
        "bond_futures_signals": "Bond Futures Four-Factor Trend",
        "crowding_cn": "Crowding",
        "dcc_garch_cn": "DCC-GARCH",
        "cta_trend_cn": "CTA Trend",
        "signal_aggregator": "Final Signal Aggregator",
        "risk_monitor": "Risk Monitor",
    }
    outputs_by_script: dict[str, list[str]] = {}
    for model in _MACRO_MODEL_DEFINITIONS:
        script_name = str(model["script_name"])
        outputs_by_script.setdefault(script_name, [])
        outputs_by_script[script_name].extend(str(name) for name in model["expected_outputs"])
    ordered_scripts = (
        "merrill_clock_cn",
        "crisis_score_cn",
        "bond_futures_data",
        "bond_futures_signals",
        "crowding_cn",
        "dcc_garch_cn",
        "cta_trend_cn",
        "signal_aggregator",
        "risk_monitor",
    )
    registry = {script.name: script for script in iter_toolkit_scripts()}
    manifest: list[dict[str, object]] = []
    for order, script_name in enumerate(ordered_scripts, start=1):
        script = registry[script_name]
        manifest.append(
            {
                "order": order,
                "script_name": script_name,
                "label": labels_by_script[script_name],
                "expected_outputs": sorted(set(outputs_by_script.get(script_name, []))),
                "available": script.path.exists(),
            }
        )
    return manifest


def _macro_run_degraded_reason(*, status: str, missing_outputs: list[str]) -> str | None:
    if status != "completed":
        return "script_execution_not_completed"
    if missing_outputs:
        return "missing_expected_outputs_after_run"
    return None


def _macro_run_blocker(
    *,
    degraded_reason: str | None,
    script_name: str,
    missing_outputs: list[str],
) -> dict[str, object] | None:
    if degraded_reason != "missing_expected_outputs_after_run":
        return None
    return {
        "type": degraded_reason,
        "script_name": script_name,
        "missing_outputs": missing_outputs,
    }


def _macro_run_data_asof(*, expected_outputs: list[str], outputs: list[dict[str, object]]) -> str | None:
    files_by_name = {str(item["name"]): item for item in outputs}
    content_dates: list[str] = []
    for name in expected_outputs:
        content_date = _macro_output_health(name, files_by_name.get(name), reference_date=None).get("content_date")
        if content_date:
            content_dates.append(str(content_date))
    return max(content_dates, default=None)
