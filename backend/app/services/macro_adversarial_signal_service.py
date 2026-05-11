from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from backend.app.core_finance.macro.toolkit.paths import OUTPUT_DIR

_FINAL_SIGNAL_FILE = "final_signal.csv"
_CROWDING_FILE = "crowding_latest.csv"

_FINAL_SIGNAL_COLUMNS = {
    "symbol": ("品种", "symbol"),
    "as_of_date": ("日期", "date", "as_of_date"),
    "signal": ("最终信号", "signal"),
    "position_scale": ("仓位比例", "position_scale"),
    "confidence": ("置信度", "confidence"),
    "note": ("信号说明", "说明", "note"),
    "third_layer_pass": ("第三层_通过", "third_layer_pass"),
}

_CROWDING_COLUMNS = {
    "symbol": ("品种", "\u935d\u4f7a\ue752", "symbol"),
    "as_of_date": ("日期", "\u93c3\u30e6\u6e61", "date", "as_of_date"),
    "crowding_percentile": ("C分位数", "C_pct", "C\u9352\u55d5\u7d85\u93c1?", "\u9352\u55d5\u7d85\u93c1?", "percentile"),
    "crowding_signal": ("拥挤度信号", "\u93b7\u30e6\u5c0b\u6434\ufe3f\u4fca\u9359?", "signal"),
    "note": ("说明", "\u7487\u5b58\u69d1", "note"),
}


def load_macro_adversarial_signal_payload(
    output_dir: str | Path | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    base_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    final_signal_path = base_dir / _FINAL_SIGNAL_FILE
    crowding_path = base_dir / _CROWDING_FILE

    if final_signal_path.exists():
        return _load_final_signal_payload(final_signal_path)

    if crowding_path.exists():
        return _load_crowding_payload(crowding_path)

    diagnostics = [f"{_FINAL_SIGNAL_FILE} missing", f"{_CROWDING_FILE} missing"]
    return _missing_payload(diagnostics)


def _load_final_signal_payload(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    frame = _read_csv(path)
    missing_columns = _missing_columns(frame, _FINAL_SIGNAL_COLUMNS)
    if missing_columns:
        return _error_payload(
            mode="final_signal",
            diagnostics=[f"{path.name} missing columns: {', '.join(missing_columns)}"],
            source_version="macro_toolkit.final_signal.csv",
            tables_used=["macro_toolkit_output.final_signal.csv"],
        )

    diagnostics: list[str] = []
    items: list[dict[str, object]] = []

    for index, row in frame.iterrows():
        symbol = _text_value(row, frame, _FINAL_SIGNAL_COLUMNS, "symbol") or f"row_{index}"
        as_of_date = _text_value(row, frame, _FINAL_SIGNAL_COLUMNS, "as_of_date")
        signal = _text_value(row, frame, _FINAL_SIGNAL_COLUMNS, "signal") or "空仓"
        note = _text_value(row, frame, _FINAL_SIGNAL_COLUMNS, "note") or ""
        position_scale = _finite_float(row, frame, _FINAL_SIGNAL_COLUMNS, "position_scale")
        if position_scale is None:
            diagnostics.append(f"{path.name} row {index + 1} position_scale non-finite")
        confidence = _finite_float(row, frame, _FINAL_SIGNAL_COLUMNS, "confidence")
        if confidence is None:
            diagnostics.append(f"{path.name} row {index + 1} confidence non-finite")
        third_layer_pass = _bool_value(row, frame, _FINAL_SIGNAL_COLUMNS, "third_layer_pass")
        if third_layer_pass is None:
            diagnostics.append(f"{path.name} row {index + 1} third_layer_pass invalid")

        risk_gate = "pass"
        effective_scale = position_scale or 0.0
        if third_layer_pass is False:
            risk_gate = "block"
            effective_scale = 0.0
        elif third_layer_pass is None:
            risk_gate = "error"
            effective_scale = 0.0

        items.append(
            {
                "symbol": symbol,
                "as_of_date": as_of_date,
                "signal": signal,
                "position_scale": round(effective_scale, 6),
                "confidence": int(confidence) if confidence is not None else None,
                "risk_gate": risk_gate,
                "note": note,
            }
        )

    if diagnostics:
        return _error_payload(
            mode="final_signal",
            diagnostics=diagnostics,
            source_version="macro_toolkit.final_signal.csv",
            tables_used=["macro_toolkit_output.final_signal.csv"],
            as_of_date=_max_as_of_date(items),
            items=items,
        )

    payload = {
        "status": "ok",
        "mode": "final_signal",
        "overlay_kind": "macro_risk",
        "observation_only": True,
        "risk_gate": "block" if any(item["risk_gate"] == "block" for item in items) else "pass",
        "position_scale": max((float(item["position_scale"]) for item in items), default=0.0),
        "items": items,
        "diagnostics": [],
    }
    meta = {
        "source_version": "macro_toolkit.final_signal.csv",
        "vendor_version": "macro_toolkit.local_csv",
        "tables_used": ["macro_toolkit_output.final_signal.csv"],
        "evidence_rows": len(items),
        "quality_flag": "ok",
        "vendor_status": "ok",
        "fallback_mode": "none",
        "as_of_date": _max_as_of_date(items),
    }
    return payload, meta


def _load_crowding_payload(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    frame = _read_csv(path)
    missing_columns = _missing_columns(frame, _CROWDING_COLUMNS)
    if missing_columns:
        return _error_payload(
            mode="crowding_latest",
            diagnostics=[f"{path.name} missing columns: {', '.join(missing_columns)}"],
            source_version="macro_toolkit.crowding_latest.csv",
            tables_used=["macro_toolkit_output.crowding_latest.csv"],
            fallback_mode="latest_snapshot",
            vendor_status="vendor_stale",
        )

    diagnostics: list[str] = []
    items: list[dict[str, object]] = []

    for index, row in frame.iterrows():
        percentile = _finite_float(row, frame, _CROWDING_COLUMNS, "crowding_percentile")
        if percentile is None:
            diagnostics.append(f"{path.name} row {index + 1} crowding_percentile non-finite")
        items.append(
            {
                "symbol": _text_value(row, frame, _CROWDING_COLUMNS, "symbol") or f"row_{index}",
                "as_of_date": _text_value(row, frame, _CROWDING_COLUMNS, "as_of_date"),
                "crowding_percentile": percentile,
                "crowding_signal": _text_value(row, frame, _CROWDING_COLUMNS, "crowding_signal") or "未知",
                "position_scale": 0.0,
                "risk_gate": "degraded",
                "note": _text_value(row, frame, _CROWDING_COLUMNS, "note") or "",
            }
        )

    payload = {
        "status": "degraded",
        "mode": "crowding_latest",
        "overlay_kind": "macro_risk",
        "observation_only": True,
        "risk_gate": "degraded",
        "position_scale": 0.0,
        "items": items,
        "diagnostics": diagnostics,
    }
    meta = {
        "source_version": "macro_toolkit.crowding_latest.csv",
        "vendor_version": "macro_toolkit.local_csv",
        "tables_used": ["macro_toolkit_output.crowding_latest.csv"],
        "evidence_rows": len(items),
        "quality_flag": "warning",
        "vendor_status": "vendor_stale",
        "fallback_mode": "latest_snapshot",
        "as_of_date": _max_as_of_date(items),
    }
    return payload, meta


def _missing_payload(diagnostics: list[str]) -> tuple[dict[str, object], dict[str, object]]:
    payload = {
        "status": "missing",
        "mode": "missing",
        "overlay_kind": "macro_risk",
        "observation_only": True,
        "risk_gate": "missing",
        "position_scale": 0.0,
        "items": [],
        "diagnostics": diagnostics,
    }
    meta = {
        "source_version": "macro_toolkit.adversarial_signal.missing",
        "vendor_version": "macro_toolkit.local_csv",
        "tables_used": [],
        "evidence_rows": 0,
        "quality_flag": "error",
        "vendor_status": "vendor_unavailable",
        "fallback_mode": "none",
        "as_of_date": None,
    }
    return payload, meta


def _error_payload(
    *,
    mode: str,
    diagnostics: list[str],
    source_version: str,
    tables_used: list[str],
    as_of_date: str | None = None,
    items: list[dict[str, object]] | None = None,
    vendor_status: str = "vendor_unavailable",
    fallback_mode: str = "none",
) -> tuple[dict[str, object], dict[str, object]]:
    payload = {
        "status": "error",
        "mode": mode,
        "overlay_kind": "macro_risk",
        "observation_only": True,
        "risk_gate": "error",
        "position_scale": 0.0,
        "items": list(items or []),
        "diagnostics": diagnostics,
    }
    meta = {
        "source_version": source_version,
        "vendor_version": "macro_toolkit.local_csv",
        "tables_used": tables_used,
        "evidence_rows": len(items or []),
        "quality_flag": "error",
        "vendor_status": vendor_status,
        "fallback_mode": fallback_mode,
        "as_of_date": as_of_date,
    }
    return payload, meta


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def _missing_columns(frame: pd.DataFrame, specs: dict[str, tuple[str, ...]]) -> list[str]:
    missing: list[str] = []
    for field, candidates in specs.items():
        if _resolve_column(frame.columns, candidates) is None:
            missing.append(field)
    return missing


def _text_value(
    row: pd.Series,
    frame: pd.DataFrame,
    specs: dict[str, tuple[str, ...]],
    field: str,
) -> str | None:
    column = _resolve_column(frame.columns, specs[field])
    if column is None:
        return None
    value = row.get(column)
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _finite_float(
    row: pd.Series,
    frame: pd.DataFrame,
    specs: dict[str, tuple[str, ...]],
    field: str,
) -> float | None:
    text = _text_value(row, frame, specs, field)
    if text is None:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def _bool_value(
    row: pd.Series,
    frame: pd.DataFrame,
    specs: dict[str, tuple[str, ...]],
    field: str,
) -> bool | None:
    text = _text_value(row, frame, specs, field)
    if text is None:
        return None
    normalized = text.strip().lower()
    if normalized in {"true", "1", "yes", "y", "是", "通过"}:
        return True
    if normalized in {"false", "0", "no", "n", "否", "未通过"}:
        return False
    return None


def _resolve_column(columns: pd.Index, candidates: tuple[str, ...]) -> str | None:
    exact = {str(column).strip(): str(column) for column in columns}
    for candidate in candidates:
        if candidate in exact:
            return exact[candidate]

    normalized = {_normalize_column_name(column): str(column) for column in columns}
    for candidate in candidates:
        normalized_candidate = _normalize_column_name(candidate)
        if normalized_candidate in normalized:
            return normalized[normalized_candidate]
    return None


def _normalize_column_name(value: object) -> str:
    text = str(value or "").strip().lower()
    for marker in (" ", "_", "-", "/", "\\", "(", ")", "[", "]", "?", "？", ":", "："):
        text = text.replace(marker, "")
    return text


def _max_as_of_date(items: list[dict[str, object]]) -> str | None:
    values = [str(item.get("as_of_date") or "").strip() for item in items if str(item.get("as_of_date") or "").strip()]
    return max(values) if values else None
