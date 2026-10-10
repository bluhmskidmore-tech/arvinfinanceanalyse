from __future__ import annotations

from datetime import date

EXPECTED_CURVE_SNAPSHOT_KEYS = frozenset(
    {
        "anchor_date",
        "curve_type",
        "snapshot_date",
        "source_version",
        "vendor_name",
        "vendor_version",
        "rule_version",
    }
)
CURVE_RECOVERY_TYPES = frozenset({"treasury", "cdb", "aaa_credit"})


def normalize_curve_recovery_options(
    *,
    use_existing_curves_only: bool,
    expected_curve_snapshots: object,
) -> list[dict[str, str]] | None:
    if type(use_existing_curves_only) is not bool:
        raise TypeError("use_existing_curves_only must be a bool.")
    if not use_existing_curves_only:
        if expected_curve_snapshots is not None:
            raise ValueError(
                "expected_curve_snapshots requires use_existing_curves_only=True."
            )
        return None
    if expected_curve_snapshots is None:
        raise ValueError("use_existing_curves_only=True requires expected_curve_snapshots.")
    if type(expected_curve_snapshots) is not list:
        raise TypeError("expected_curve_snapshots must be a list.")
    if not expected_curve_snapshots:
        raise ValueError("expected_curve_snapshots must not be empty.")

    normalized: list[dict[str, str]] = []
    seen_grains: set[tuple[str, str]] = set()
    for index, item in enumerate(expected_curve_snapshots):
        if type(item) is not dict:
            raise TypeError(f"expected_curve_snapshots[{index}] must be an object.")
        item_keys = set(item)
        if item_keys != EXPECTED_CURVE_SNAPSHOT_KEYS:
            missing = sorted(EXPECTED_CURVE_SNAPSHOT_KEYS - item_keys)
            extra = sorted(str(key) for key in item_keys - EXPECTED_CURVE_SNAPSHOT_KEYS)
            raise ValueError(
                f"expected_curve_snapshots[{index}] has invalid keys; "
                f"missing={missing}, extra={extra}."
            )

        normalized_item: dict[str, str] = {}
        for key in EXPECTED_CURVE_SNAPSHOT_KEYS:
            raw_value = item[key]
            if not isinstance(raw_value, str):
                raise TypeError(
                    f"expected_curve_snapshots[{index}].{key} must be a string."
                )
            normalized_value = raw_value.strip()
            if not normalized_value:
                raise ValueError(
                    f"expected_curve_snapshots[{index}].{key} must be non-empty."
                )
            normalized_item[key] = normalized_value

        for date_key in ("anchor_date", "snapshot_date"):
            try:
                parsed_date = date.fromisoformat(normalized_item[date_key])
            except ValueError as exc:
                raise ValueError(
                    f"expected_curve_snapshots[{index}].{date_key} must be a canonical ISO date."
                ) from exc
            if parsed_date.isoformat() != normalized_item[date_key]:
                raise ValueError(
                    f"expected_curve_snapshots[{index}].{date_key} must be a canonical ISO date."
                )

        if normalized_item["curve_type"] not in CURVE_RECOVERY_TYPES:
            raise ValueError(
                f"expected_curve_snapshots[{index}].curve_type must be one of "
                f"{sorted(CURVE_RECOVERY_TYPES)}."
            )

        grain = (normalized_item["anchor_date"], normalized_item["curve_type"])
        if grain in seen_grains:
            raise ValueError(
                "expected_curve_snapshots contains a duplicate anchor_date/curve_type grain: "
                f"{grain[0]}/{grain[1]}."
            )
        seen_grains.add(grain)
        normalized.append(normalized_item)

    return sorted(
        normalized,
        key=lambda item: (
            item["anchor_date"],
            item["curve_type"],
            item["snapshot_date"],
        ),
    )
