"""DV01 portfolio calculations for bond analytics read models."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.app.core_finance.bond_analytics.common import safe_decimal

ZERO = Decimal("0")


def parse_dv01_shocks(value: object) -> list[Decimal]:
    shocks: list[Decimal] = []
    for raw in str(value or "1,10,25,50").split(","):
        text = raw.strip()
        if not text:
            continue
        shock = safe_decimal(text).copy_abs()
        if shock == ZERO:
            continue
        if shock not in shocks:
            shocks.append(shock)
    return shocks or [Decimal("1"), Decimal("10"), Decimal("25"), Decimal("50")]


def expand_parallel_shocks(shocks: list[Decimal]) -> list[Decimal]:
    expanded: list[Decimal] = []
    for shock in shocks:
        expanded.extend([shock, -shock])
    return expanded


def build_dv01_shock_scenario_payloads(
    *,
    total_dv01: Decimal,
    shocks: list[Decimal],
) -> list[dict[str, object]]:
    return [
        {
            "scenario_name": f"rate_{'up' if shock > ZERO else 'down'}_{abs(shock)}bp",
            "shock_bp": shock,
            "estimated_pnl": -(total_dv01 * shock),
        }
        for shock in expand_parallel_shocks(shocks)
    ]


def face_weighted_modified_duration(rows: list[dict[str, object]]) -> Decimal:
    total_face_value = sum((safe_decimal(row.get("face_value")) for row in rows), ZERO)
    if total_face_value == ZERO:
        return ZERO
    return (
        sum(
            (
                safe_decimal(row.get("face_value")) * safe_decimal(row.get("modified_duration"))
                for row in rows
            ),
            ZERO,
        )
        / total_face_value
    )


def total_abs_dv01(rows: list[dict[str, object]]) -> Decimal:
    return sum((safe_decimal(row.get("dv01")).copy_abs() for row in rows), ZERO)


def dv01_share(dv01: Decimal, total_abs_dv01: Decimal) -> Decimal:
    denominator = total_abs_dv01.copy_abs()
    if denominator == ZERO:
        return ZERO
    return abs(dv01) / denominator


def build_dv01_tenor_bucket_payloads(
    rows: list[dict[str, object]],
    *,
    total_abs_dv01: Decimal,
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        tenor = str(row.get("tenor_bucket") or "UNKNOWN").strip() or "UNKNOWN"
        grouped.setdefault(tenor, []).append(row)

    result: list[dict[str, object]] = []
    for tenor, bucket_rows in grouped.items():
        face_value = sum((safe_decimal(row.get("face_value")) for row in bucket_rows), ZERO)
        market_value = sum((safe_decimal(row.get("market_value")) for row in bucket_rows), ZERO)
        dv01 = sum((safe_decimal(row.get("dv01")) for row in bucket_rows), ZERO)
        result.append(
            {
                "tenor_bucket": tenor,
                "face_value": face_value,
                "market_value": market_value,
                "face_weighted_modified_duration": face_weighted_modified_duration(bucket_rows),
                "dv01": dv01,
                "dv01_share": dv01_share(dv01, total_abs_dv01),
                "position_count": len(bucket_rows),
            }
        )
    return sorted(result, key=lambda row: (safe_decimal(row["dv01"]).copy_abs(), str(row["tenor_bucket"])), reverse=True)


def build_dv01_top_bond_payloads(
    rows: list[dict[str, object]],
    *,
    total_abs_dv01: Decimal,
    top_n: int,
) -> list[dict[str, object]]:
    ordered = sorted(
        rows,
        key=lambda row: (safe_decimal(row.get("dv01")).copy_abs(), str(row.get("instrument_code") or "")),
        reverse=True,
    )
    return [
        {
            "instrument_code": str(row.get("instrument_code") or ""),
            "instrument_name": _optional_text(row.get("instrument_name")),
            "issuer_name": _optional_text(row.get("issuer_name")),
            "rating": _optional_text(row.get("rating")),
            "tenor_bucket": str(row.get("tenor_bucket") or ""),
            "accounting_class": str(row.get("accounting_class") or ""),
            "face_value": safe_decimal(row.get("face_value")),
            "market_value": safe_decimal(row.get("market_value")),
            "modified_duration": safe_decimal(row.get("modified_duration")),
            "dv01": safe_decimal(row.get("dv01")),
            "dv01_share": dv01_share(safe_decimal(row.get("dv01")), total_abs_dv01),
        }
        for row in ordered[:top_n]
    ]


def build_dv01_top_issuer_payloads(
    rows: list[dict[str, object]],
    *,
    total_abs_dv01: Decimal,
    top_n: int,
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        issuer = str(row.get("issuer_name") or "UNKNOWN").strip() or "UNKNOWN"
        grouped.setdefault(issuer, []).append(row)

    items: list[dict[str, object]] = []
    for issuer, issuer_rows in grouped.items():
        face_value = sum((safe_decimal(row.get("face_value")) for row in issuer_rows), ZERO)
        market_value = sum((safe_decimal(row.get("market_value")) for row in issuer_rows), ZERO)
        dv01 = sum((safe_decimal(row.get("dv01")) for row in issuer_rows), ZERO)
        items.append(
            {
                "issuer_name": issuer,
                "face_value": face_value,
                "market_value": market_value,
                "face_weighted_modified_duration": face_weighted_modified_duration(issuer_rows),
                "dv01": dv01,
                "dv01_share": dv01_share(dv01, total_abs_dv01),
                "position_count": len(issuer_rows),
            }
        )
    return sorted(items, key=lambda row: (safe_decimal(row["dv01"]).copy_abs(), str(row["issuer_name"])), reverse=True)[:top_n]


def build_dv01_reconciliation_payloads(
    rows: list[dict[str, object]],
    *,
    total_abs_dv01: Decimal,
) -> list[dict[str, object]]:
    ordered = sorted(
        rows,
        key=lambda row: (safe_decimal(row.get("dv01")).copy_abs(), str(row.get("instrument_code") or "")),
        reverse=True,
    )
    return [
        {
            "report_date": row.get("report_date"),
            "instrument_code": str(row.get("instrument_code") or ""),
            "instrument_name": _optional_text(row.get("instrument_name")),
            "accounting_class": str(row.get("accounting_class") or ""),
            "issuer_name": _optional_text(row.get("issuer_name")),
            "rating": _optional_text(row.get("rating")),
            "tenor_bucket": str(row.get("tenor_bucket") or ""),
            "face_value": safe_decimal(row.get("face_value")),
            "market_value": safe_decimal(row.get("market_value")),
            "modified_duration": safe_decimal(row.get("modified_duration")),
            "dv01": safe_decimal(row.get("dv01")),
            "dv01_share": dv01_share(safe_decimal(row.get("dv01")), total_abs_dv01),
            "source_version": str(row.get("source_version") or ""),
            "rule_version": str(row.get("rule_version") or ""),
            "trace_id": str(row.get("trace_id") or ""),
        }
        for row in ordered
    ]


def dv01_scope_summary(rows: list[dict[str, object]]) -> dict[str, Decimal]:
    return {
        "total_face_value": sum((safe_decimal(row.get("face_value")) for row in rows), ZERO),
        "total_market_value": sum((safe_decimal(row.get("market_value")) for row in rows), ZERO),
        "face_weighted_modified_duration": face_weighted_modified_duration(rows),
        "total_dv01": sum((safe_decimal(row.get("dv01")) for row in rows), ZERO),
    }


DV01_RISK_LEVEL_NO_DATA = "no_data"
DV01_RISK_LEVEL_NO_LIMIT_CONFIGURED = "no_limit_configured"


def dv01_action_risk_level(
    *,
    total_dv01: Decimal,
    warning_dv01: Decimal,
    limit_dv01: Decimal,
    has_rows: bool,
    limit_configured: bool = True,
) -> str:
    """Grade DV01 exposure against a limit, or report that no limit exists.

    A missing limit is not the same as a limit of zero: without a governed
    limit there is no threshold to breach, so the caller must get
    ``no_limit_configured`` rather than a breach graded off a placeholder.
    """
    if not has_rows:
        return DV01_RISK_LEVEL_NO_DATA
    if not limit_configured or limit_dv01 <= ZERO:
        return DV01_RISK_LEVEL_NO_LIMIT_CONFIGURED
    if total_dv01 >= limit_dv01:
        return "breach"
    if total_dv01 >= warning_dv01:
        return "watch"
    return "ok"


def build_dv01_action_scenario_payloads(
    *,
    total_dv01: Decimal,
    warning_dv01: Decimal,
    limit_dv01: Decimal,
    has_rows: bool,
    shocks: list[Decimal] | tuple[Decimal, ...],
    limit_configured: bool = True,
) -> list[dict[str, object]]:
    if not has_rows:
        return []
    if not limit_configured or limit_dv01 <= ZERO:
        return []
    return [
        {
            "scenario_name": f"rate_up_{shock}bp",
            "shock_bp": shock,
            "estimated_loss": (total_dv01 * shock).copy_abs(),
            "loss_threshold": (limit_dv01 * shock).copy_abs(),
            "risk_level": dv01_action_scenario_level(
                estimated_loss=(total_dv01 * shock).copy_abs(),
                warning_loss=(warning_dv01 * shock).copy_abs(),
                limit_loss=(limit_dv01 * shock).copy_abs(),
            ),
        }
        for shock in shocks
    ]


def dv01_action_scenario_level(
    *,
    estimated_loss: Decimal,
    warning_loss: Decimal,
    limit_loss: Decimal,
) -> str:
    if estimated_loss >= limit_loss:
        return "breach"
    if estimated_loss >= warning_loss:
        return "watch"
    return "ok"


def build_dv01_action_tenor_payloads(
    rows: list[dict[str, object]],
    *,
    total_abs_dv01: Decimal,
    dv01_to_reduce: Decimal,
    top_n: int,
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        tenor = str(row.get("tenor_bucket") or "UNKNOWN").strip() or "UNKNOWN"
        grouped.setdefault(tenor, []).append(row)

    items: list[dict[str, object]] = []
    for tenor, bucket_rows in grouped.items():
        dv01 = sum((safe_decimal(row.get("dv01")) for row in bucket_rows), ZERO)
        items.append(
            {
                "tenor_bucket": tenor,
                "dv01": dv01,
                "dv01_share": dv01_share(dv01, total_abs_dv01),
                "suggested_reduction_dv01": suggested_reduction_for_share(
                    dv01,
                    total_abs_dv01,
                    dv01_to_reduce,
                ),
                "position_count": len(bucket_rows),
            }
        )
    return sorted(items, key=lambda row: (safe_decimal(row["dv01"]).copy_abs(), str(row["tenor_bucket"])), reverse=True)[:top_n]


def build_dv01_action_issuer_payloads(
    rows: list[dict[str, object]],
    *,
    total_abs_dv01: Decimal,
    dv01_to_reduce: Decimal,
    top_n: int,
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        issuer = str(row.get("issuer_name") or "UNKNOWN").strip() or "UNKNOWN"
        grouped.setdefault(issuer, []).append(row)

    items: list[dict[str, object]] = []
    for issuer, issuer_rows in grouped.items():
        dv01 = sum((safe_decimal(row.get("dv01")) for row in issuer_rows), ZERO)
        items.append(
            {
                "issuer_name": issuer,
                "dv01": dv01,
                "dv01_share": dv01_share(dv01, total_abs_dv01),
                "suggested_reduction_dv01": suggested_reduction_for_share(
                    dv01,
                    total_abs_dv01,
                    dv01_to_reduce,
                ),
                "position_count": len(issuer_rows),
            }
        )
    return sorted(items, key=lambda row: (safe_decimal(row["dv01"]).copy_abs(), str(row["issuer_name"])), reverse=True)[:top_n]


def build_dv01_action_bond_payloads(
    rows: list[dict[str, object]],
    *,
    total_abs_dv01: Decimal,
    dv01_to_reduce: Decimal,
    top_n: int,
) -> list[dict[str, object]]:
    ordered = sorted(
        rows,
        key=lambda row: (safe_decimal(row.get("dv01")).copy_abs(), str(row.get("instrument_code") or "")),
        reverse=True,
    )
    return [
        {
            "instrument_code": str(row.get("instrument_code") or ""),
            "instrument_name": _optional_text(row.get("instrument_name")),
            "issuer_name": _optional_text(row.get("issuer_name")),
            "rating": _optional_text(row.get("rating")),
            "tenor_bucket": str(row.get("tenor_bucket") or ""),
            "accounting_class": str(row.get("accounting_class") or ""),
            "face_value": safe_decimal(row.get("face_value")),
            "market_value": safe_decimal(row.get("market_value")),
            "modified_duration": safe_decimal(row.get("modified_duration")),
            "dv01": safe_decimal(row.get("dv01")),
            "dv01_share": dv01_share(safe_decimal(row.get("dv01")), total_abs_dv01),
            "suggested_reduction_dv01": suggested_reduction_for_share(
                safe_decimal(row.get("dv01")),
                total_abs_dv01,
                dv01_to_reduce,
            ),
        }
        for row in ordered[:top_n]
    ]


def suggested_reduction_for_share(dv01: Decimal, total_abs_dv01: Decimal, dv01_to_reduce: Decimal) -> Decimal:
    if dv01_to_reduce <= ZERO or total_abs_dv01 <= ZERO:
        return ZERO
    return dv01_to_reduce * dv01_share(dv01, total_abs_dv01)


def build_dv01_movement_bond_payloads(
    *,
    current_rows: list[dict[str, object]],
    previous_rows: list[dict[str, object]],
    current_all_rows: list[dict[str, object]],
    previous_all_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    current_positions = _rows_by_position(current_rows)
    previous_positions = _rows_by_position(previous_rows)
    current_all = {**current_positions, **_rows_by_position(current_all_rows)}
    previous_all = {**previous_positions, **_rows_by_position(previous_all_rows)}
    by_bond: dict[str, list[dict[str, object]]] = {}
    for current_key, previous_key in _pair_movement_positions(current_all, previous_all):
        current_row = current_positions.get(current_key) if current_key is not None else None
        previous_row = previous_positions.get(previous_key) if previous_key is not None else None
        if current_row is None and previous_row is None:
            continue
        current_all_row = current_all.get(current_key) if current_key is not None else None
        previous_all_row = previous_all.get(previous_key) if previous_key is not None else None
        row = current_row or previous_row or {}
        instrument_code = str(row["instrument_code"])
        current_dv01 = safe_decimal((current_row or {}).get("dv01"))
        previous_dv01 = safe_decimal((previous_row or {}).get("dv01"))
        estimated_dv01 = safe_decimal((current_row or {}).get("_estimated_dv01"))
        by_bond.setdefault(instrument_code, []).append(
            {
                "instrument_code": instrument_code,
                "portfolio_name": _optional_text(row.get("portfolio_name")),
                "cost_center": _optional_text(row.get("cost_center")),
                "currency_code": _optional_text(row.get("currency_code")),
                "instrument_name": _optional_text(row.get("instrument_name")),
                "issuer_name": _optional_text(row.get("issuer_name")),
                "rating": _optional_text(row.get("rating")),
                "tenor_bucket": str(row.get("tenor_bucket") or ""),
                "previous_accounting_class": _optional_text(
                    (previous_row or previous_all_row or {}).get("accounting_class")
                ),
                "current_accounting_class": _optional_text(
                    (current_row or current_all_row or {}).get("accounting_class")
                ),
                "previous_face_value": safe_decimal((previous_row or {}).get("face_value")),
                "current_face_value": safe_decimal((current_row or {}).get("face_value")),
                "previous_modified_duration": safe_decimal((previous_row or {}).get("modified_duration")),
                "current_modified_duration": safe_decimal((current_row or {}).get("modified_duration")),
                "previous_dv01": previous_dv01,
                "current_dv01": current_dv01,
                "_previous_position_exists": previous_row is not None,
                "_current_position_exists": current_row is not None,
                "dv01_delta": current_dv01 - previous_dv01,
                "estimated_dv01_from_face_duration": estimated_dv01,
                "dv01_estimate_gap": current_dv01 - estimated_dv01,
                "reason_label": dv01_movement_reason(
                    current_row=current_row,
                    previous_row=previous_row,
                    current_all_row=current_all_row,
                    previous_all_row=previous_all_row,
                ),
            }
        )
    items: list[dict[str, object]] = []
    for _instrument_code, positions in sorted(by_bond.items()):
        item = dict(positions[0])
        for field in (
            "previous_face_value", "current_face_value", "previous_dv01", "current_dv01",
            "dv01_delta", "estimated_dv01_from_face_duration", "dv01_estimate_gap",
        ):
            item[field] = sum((safe_decimal(position[field]) for position in positions), ZERO)
        for period in ("previous", "current"):
            item[f"{period}_modified_duration"] = face_weighted_modified_duration([
                {"face_value": position[f"{period}_face_value"],
                 "modified_duration": position[f"{period}_modified_duration"]}
                for position in positions
            ])
            classes = sorted({str(position[f"{period}_accounting_class"]) for position in positions
                              if position[f"{period}_accounting_class"]})
            item[f"{period}_accounting_class"] = ", ".join(classes) or None
        item["reason_label"] = "、".join(sorted({str(position["reason_label"]) for position in positions}))
        # Attribution must use the paired holdings, never the weighted bond summary.
        # This private field is ignored by the outward DV01MovementBondItem schema.
        item["_position_movements"] = positions
        items.append(item)
    return items


def build_dv01_movement_attribution_payloads(
    movement_rows: list[dict[str, object]],
    *,
    total_delta_dv01: Decimal,
) -> list[dict[str, object]]:
    driver_order = [
        ("new_position", "新增", ZERO, 0),
        ("exited_position", "退出/到期", ZERO, 0),
        ("classification_change", "分类变化", ZERO, 0),
        ("face_value_change", "面值变化", ZERO, 0),
        ("duration_change", "久期变化", ZERO, 0),
    ]
    totals: dict[str, dict[str, Decimal | int | str]] = {
        key: {"label": label, "dv01_delta": value, "position_count": count}
        for key, label, value, count in driver_order
    }
    position_rows: list[dict[str, object]] = []
    for row in movement_rows:
        positions = row.get("_position_movements")
        position_rows.extend(positions if isinstance(positions, list) else [row])
    for row in position_rows:
        current_dv01 = safe_decimal(row.get("current_dv01"))
        previous_dv01 = safe_decimal(row.get("previous_dv01"))
        current_face = safe_decimal(row.get("current_face_value"))
        previous_face = safe_decimal(row.get("previous_face_value"))
        current_duration = safe_decimal(row.get("current_modified_duration"))
        previous_duration = safe_decimal(row.get("previous_modified_duration"))
        current_class = str(row.get("current_accounting_class") or "")
        previous_class = str(row.get("previous_accounting_class") or "")

        if previous_class and current_class and previous_class != current_class:
            delta = current_dv01 - previous_dv01
            _add_driver_delta(totals, "classification_change", delta)
            continue
        previous_exists = bool(row.get("_previous_position_exists", previous_dv01 != ZERO))
        current_exists = bool(row.get("_current_position_exists", current_dv01 != ZERO))
        if not previous_exists and current_exists:
            _add_driver_delta(totals, "new_position", current_dv01)
            continue
        if previous_exists and not current_exists:
            _add_driver_delta(totals, "exited_position", -previous_dv01)
            continue

        face_delta = (current_face - previous_face) * previous_duration * Decimal("0.0001")
        duration_delta = previous_face * (current_duration - previous_duration) * Decimal("0.0001")
        if face_delta != ZERO:
            _add_driver_delta(totals, "face_value_change", face_delta)
        if duration_delta != ZERO:
            _add_driver_delta(totals, "duration_change", duration_delta)

    explained_delta = sum((safe_decimal(item["dv01_delta"]) for item in totals.values()), ZERO)
    residual_delta = total_delta_dv01 - explained_delta
    denominator = total_delta_dv01.copy_abs()
    items = [
        {
            "driver_key": key,
            "driver_label": str(item["label"]),
            "dv01_delta": safe_decimal(item["dv01_delta"]),
            "dv01_delta_share": movement_share(safe_decimal(item["dv01_delta"]), denominator),
            "position_count": int(item["position_count"]),
        }
        for key, item in totals.items()
    ]
    items.append(
        {
            "driver_key": "residual",
            "driver_label": "口径/价格残差",
            "dv01_delta": residual_delta,
            "dv01_delta_share": movement_share(residual_delta, denominator),
            "position_count": 0,
        }
    )
    return items


def estimated_dv01_from_face_duration(row: dict[str, object] | None) -> Decimal:
    if not row:
        return ZERO
    return safe_decimal(row.get("face_value")) * safe_decimal(row.get("modified_duration")) * Decimal("0.0001")


def dv01_movement_reason(
    *,
    current_row: dict[str, object] | None,
    previous_row: dict[str, object] | None,
    current_all_row: dict[str, object] | None,
    previous_all_row: dict[str, object] | None,
) -> str:
    if previous_row is None and current_row is not None:
        if previous_all_row is not None:
            return "分类转入"
        return "新增"
    if previous_row is not None and current_row is None:
        if current_all_row is not None:
            return "分类转出"
        return "退出/到期"
    previous_face = safe_decimal((previous_row or {}).get("face_value"))
    current_face = safe_decimal((current_row or {}).get("face_value"))
    previous_duration = safe_decimal((previous_row or {}).get("modified_duration"))
    current_duration = safe_decimal((current_row or {}).get("modified_duration"))
    if current_face != previous_face and current_duration != previous_duration:
        return "面值和久期变化"
    if current_face != previous_face:
        return "面值变化"
    if current_duration != previous_duration:
        return "久期变化"
    return "DV01口径差异"


def movement_share(value: Decimal, denominator: Decimal) -> Decimal:
    if denominator == ZERO:
        return ZERO
    return value / denominator.copy_abs()


def _rows_by_position(rows: list[dict[str, object]]) -> dict[tuple[str, ...], dict[str, object]]:
    # Match the formal repository's holding grain. Source/trace IDs vary by date.
    fields = ("instrument_code", "portfolio_name", "cost_center", "currency_code", "accounting_class")
    grouped: dict[tuple[str, ...], list[dict[str, object]]] = {}
    for row in rows:
        key = tuple(str(row.get(field) or "").strip() for field in fields)
        if key[0]:
            grouped.setdefault(key, []).append(row)
    result: dict[tuple[str, ...], dict[str, object]] = {}
    def description_key(row: dict[str, object]) -> tuple[str, ...]:
        return tuple(str(row.get(field) or "") for field in ("instrument_name", "issuer_name", "rating", "tenor_bucket"))

    for key, holdings in sorted(grouped.items()):
        # Duplicate holding rows are additive, just as they are in the scope total.
        # Choose descriptive fields deterministically when source rows disagree.
        item = dict(sorted(holdings, key=description_key)[0])
        item.update(zip(fields, key, strict=True))
        item["face_value"] = sum((safe_decimal(row.get("face_value")) for row in holdings), ZERO)
        item["dv01"] = sum((safe_decimal(row.get("dv01")) for row in holdings), ZERO)
        item["modified_duration"] = face_weighted_modified_duration(holdings)
        item["_estimated_dv01"] = sum((estimated_dv01_from_face_duration(row) for row in holdings), ZERO)
        result[key] = item
    return result


def _pair_movement_positions(
    current: dict[tuple[str, ...], dict[str, object]],
    previous: dict[tuple[str, ...], dict[str, object]],
) -> list[tuple[tuple[str, ...] | None, tuple[str, ...] | None]]:
    pairs: list[tuple[tuple[str, ...] | None, tuple[str, ...] | None]] = []
    groups: dict[tuple[str, ...], tuple[set[tuple[str, ...]], set[tuple[str, ...]]]] = {}
    for index, rows in enumerate((current, previous)):
        for key in rows:
            groups.setdefault(key[:-1], (set(), set()))[index].add(key)
    for _, (current_keys, previous_keys) in sorted(groups.items()):
        common = current_keys & previous_keys
        pairs.extend((key, key) for key in sorted(common))
        current_keys -= common
        previous_keys -= common
        # A category transfer is identifiable only within the same holding and
        # with a unique unmatched category on each date; never cross portfolios.
        if len(current_keys) == len(previous_keys) == 1:
            pairs.append((next(iter(current_keys)), next(iter(previous_keys))))
        else:
            pairs.extend((key, None) for key in sorted(current_keys))
            pairs.extend((None, key) for key in sorted(previous_keys))
    return pairs


def _add_driver_delta(
    totals: dict[str, dict[str, Decimal | int | str]],
    key: str,
    delta: Decimal,
) -> None:
    totals[key]["dv01_delta"] = safe_decimal(totals[key]["dv01_delta"]) + delta
    totals[key]["position_count"] = int(totals[key]["position_count"]) + 1


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
