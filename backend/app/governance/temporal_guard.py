from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timezone


class TemporalGuardError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class TemporalDatasetContract:
    dataset_name: str
    published_at_field: str | None = None
    effective_from_field: str | None = None
    effective_to_field: str | None = None


def filter_rows_as_of(
    *,
    rows: Sequence[Mapping[str, object]],
    contract: TemporalDatasetContract,
    as_of_date: str | date,
) -> list[Mapping[str, object]]:
    _validate_contract(contract)
    anchor_moment = _coerce_moment(as_of_date, field_name="as_of_date")
    selected: list[Mapping[str, object]] = []
    for index, row in enumerate(rows):
        published_at = _required_row_moment(
            row=row,
            field_name=contract.published_at_field or "",
            dataset_name=contract.dataset_name,
            row_index=index,
        )
        effective_from = _required_row_moment(
            row=row,
            field_name=contract.effective_from_field or "",
            dataset_name=contract.dataset_name,
            row_index=index,
        )
        effective_to = _optional_row_moment(
            row=row,
            field_name=contract.effective_to_field,
            dataset_name=contract.dataset_name,
            row_index=index,
        )
        if published_at > anchor_moment:
            continue
        if effective_from > anchor_moment:
            continue
        if effective_to is not None and anchor_moment >= effective_to:
            continue
        selected.append(row)
    if not selected:
        raise TemporalGuardError(
            f"No point-in-time rows satisfied dataset={contract.dataset_name!r} as_of_date={anchor_moment.isoformat()}."
        )
    return selected


def _validate_contract(contract: TemporalDatasetContract) -> None:
    if not contract.dataset_name.strip():
        raise TemporalGuardError("Temporal contract dataset_name is required.")
    if not str(contract.published_at_field or "").strip():
        raise TemporalGuardError(
            f"Temporal contract for {contract.dataset_name!r} is incomplete: published_at_field is required."
        )
    if not str(contract.effective_from_field or "").strip():
        raise TemporalGuardError(
            f"Temporal contract for {contract.dataset_name!r} is incomplete: effective_from_field is required."
        )


def _required_row_moment(
    *,
    row: Mapping[str, object],
    field_name: str,
    dataset_name: str,
    row_index: int,
) -> datetime:
    raw_value = row.get(field_name)
    if raw_value in (None, ""):
        raise TemporalGuardError(
            f"Temporal row missing required field {field_name!r} for dataset={dataset_name!r} row_index={row_index}."
        )
    return _coerce_moment(raw_value, field_name=field_name)


def _optional_row_moment(
    *,
    row: Mapping[str, object],
    field_name: str | None,
    dataset_name: str,
    row_index: int,
) -> datetime | None:
    normalized_field_name = str(field_name or "").strip()
    if not normalized_field_name:
        return None
    raw_value = row.get(normalized_field_name)
    if raw_value in (None, ""):
        return None
    try:
        return _coerce_moment(raw_value, field_name=normalized_field_name)
    except TemporalGuardError as exc:
        raise TemporalGuardError(
            f"Temporal row has invalid {normalized_field_name!r} for dataset={dataset_name!r} row_index={row_index}."
        ) from exc


def _coerce_moment(value: object, *, field_name: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        raise TemporalGuardError(f"{field_name} must be a non-empty date value.")
    try:
        normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
        if "T" in normalized or "+" in normalized[10:] or normalized.endswith("00:00"):
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return datetime.combine(date.fromisoformat(normalized[:10]), time.min, tzinfo=timezone.utc)
    except ValueError as exc:
        raise TemporalGuardError(f"{field_name} must be a valid ISO date value.") from exc
