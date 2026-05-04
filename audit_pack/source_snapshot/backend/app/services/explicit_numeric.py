from __future__ import annotations

from dataclasses import asdict, is_dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping

from pydantic import BaseModel

from backend.app.schemas.common_numeric import Numeric, NumericUnit, numeric_from_raw


NUMERIC_JSON_KEYS = frozenset({"raw", "unit", "display", "precision", "sign_aware"})
_Q8 = Decimal("0.00000001")


def is_numeric_json(value: Any) -> bool:
    return isinstance(value, dict) and NUMERIC_JSON_KEYS <= set(value.keys())


def numeric_json_to_q8_string(value: dict[str, Any]) -> str:
    """Format a governed Numeric JSON dict as a fixed 8dp decimal string (bond analytics formal contract)."""
    raw = value.get("raw")
    dec = Decimal("0") if raw is None else Decimal(str(raw))
    return format(dec.quantize(_Q8, rounding=ROUND_HALF_UP), "f")


def collapse_numeric_json_to_q8_strings(obj: Any) -> Any:
    """Recursively replace Numeric-shaped dicts with Q8 decimal strings; pass through other JSON values."""
    if is_numeric_json(obj):
        return numeric_json_to_q8_string(obj)
    if isinstance(obj, list):
        return [collapse_numeric_json_to_q8_strings(item) for item in obj]
    if isinstance(obj, dict):
        return {k: collapse_numeric_json_to_q8_strings(v) for k, v in obj.items()}
    return obj


def numeric_json(raw: Any, unit: NumericUnit, sign_aware: bool) -> dict[str, Any]:
    if raw is None:
        return numeric_from_raw(raw=None, unit=unit, sign_aware=sign_aware).model_dump(mode="json")
    if isinstance(raw, Decimal):
        raw_value = float(raw)
    elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
        raw_value = float(raw)
    else:
        raw_value = float(str(raw))
    return numeric_from_raw(raw=raw_value, unit=unit, sign_aware=sign_aware).model_dump(mode="json")


def promote_flat_payload(payload: Any, model_cls: type) -> Any:
    if is_dataclass(payload):
        out = asdict(payload)
    elif isinstance(payload, BaseModel):
        out = payload.model_dump(mode="python")
    elif isinstance(payload, dict):
        out = dict(payload)
    else:
        return payload

    field_map: Mapping[str, tuple[NumericUnit, bool]] = getattr(model_cls, "_NUMERIC_FIELDS", {}) or {}
    for field_name, (unit, sign_aware) in field_map.items():
        if field_name not in out:
            continue
        value = out[field_name]
        if value is None or isinstance(value, Numeric) or is_numeric_json(value):
            continue
        out[field_name] = numeric_json(value, unit, sign_aware)
    return out


def promote_payload_numerics(
    payload: Any,
    model_cls: type,
    *,
    list_fields: Mapping[str, type] | None = None,
    object_fields: Mapping[str, type] | None = None,
) -> Any:
    out = promote_flat_payload(payload, model_cls)
    if not isinstance(out, dict):
        return out

    for field_name, child_cls in (object_fields or {}).items():
        value = out.get(field_name)
        if value is None:
            continue
        promoted = promote_flat_payload(value, child_cls)
        if isinstance(promoted, dict):
            out[field_name] = promoted

    for field_name, child_cls in (list_fields or {}).items():
        value = out.get(field_name)
        if not isinstance(value, list):
            continue
        out[field_name] = [
            promote_flat_payload(item, child_cls) if isinstance(item, dict) or is_dataclass(item) else item
            for item in value
        ]

    return out
