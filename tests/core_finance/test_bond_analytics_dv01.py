from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.bond_analytics.dv01 import (
    build_dv01_action_bond_payloads,
    build_dv01_action_issuer_payloads,
    build_dv01_action_scenario_payloads,
    build_dv01_action_tenor_payloads,
    build_dv01_movement_attribution_payloads,
    build_dv01_movement_bond_payloads,
    build_dv01_tenor_bucket_payloads,
    build_dv01_top_bond_payloads,
    build_dv01_top_issuer_payloads,
    dv01_action_risk_level,
    dv01_share,
    expand_parallel_shocks,
    face_weighted_modified_duration,
    parse_dv01_shocks,
    total_abs_dv01,
)


def _rows() -> list[dict[str, object]]:
    return [
        {
            "instrument_code": "POS-001",
            "instrument_name": "Positive DV01",
            "issuer_name": "Issuer A",
            "rating": "AAA",
            "tenor_bucket": "3Y",
            "accounting_class": "OCI",
            "face_value": Decimal("100"),
            "market_value": Decimal("101"),
            "modified_duration": Decimal("3"),
            "dv01": Decimal("100"),
        },
        {
            "instrument_code": "NEG-001",
            "instrument_name": "Negative DV01",
            "issuer_name": "Issuer B",
            "rating": "AAA",
            "tenor_bucket": "5Y",
            "accounting_class": "OCI",
            "face_value": Decimal("300"),
            "market_value": Decimal("99"),
            "modified_duration": Decimal("5"),
            "dv01": Decimal("-40"),
        },
    ]


def test_dv01_core_uses_absolute_exposure_denominator_for_shares() -> None:
    rows = _rows()
    total_abs = total_abs_dv01(rows)

    assert total_abs == Decimal("140")
    assert dv01_share(Decimal("100"), total_abs) == Decimal("100") / Decimal("140")
    assert dv01_share(Decimal("-40"), total_abs) == Decimal("40") / Decimal("140")

    tenor_buckets = build_dv01_tenor_bucket_payloads(rows, total_abs_dv01=total_abs)
    top_bonds = build_dv01_top_bond_payloads(rows, total_abs_dv01=total_abs, top_n=2)
    top_issuers = build_dv01_top_issuer_payloads(rows, total_abs_dv01=total_abs, top_n=2)

    assert tenor_buckets[0]["tenor_bucket"] == "3Y"
    assert top_bonds[0]["instrument_code"] == "POS-001"
    assert top_issuers[0]["issuer_name"] == "Issuer A"
    assert tenor_buckets[0]["dv01_share"] == Decimal("100") / Decimal("140")
    assert top_bonds[1]["dv01_share"] == Decimal("40") / Decimal("140")
    assert top_issuers[1]["dv01_share"] == Decimal("40") / Decimal("140")


def test_dv01_core_keeps_face_weighted_duration_and_parallel_shock_order() -> None:
    rows = _rows()

    assert face_weighted_modified_duration(rows) == Decimal("18") / Decimal("4")
    assert parse_dv01_shocks("10, 0, -10, 25, 10") == [Decimal("10"), Decimal("25")]
    assert expand_parallel_shocks([Decimal("10"), Decimal("25")]) == [
        Decimal("10"),
        Decimal("-10"),
        Decimal("25"),
        Decimal("-25"),
    ]


def test_dv01_core_builds_movement_rows_and_attribution_payloads() -> None:
    previous_rows = [
        _movement_row("A-001", face="1000000", duration="3", dv01="300", accounting_class="OCI"),
        _movement_row("X-001", face="100000", duration="5", dv01="50", accounting_class="OCI"),
    ]
    current_rows = [
        _movement_row("A-001", face="1100000", duration="3.5", dv01="390", accounting_class="OCI"),
        _movement_row("N-001", face="200000", duration="5", dv01="100", accounting_class="OCI"),
        _movement_row("C-001", face="100000", duration="4", dv01="40", accounting_class="OCI"),
    ]
    previous_all_rows = [
        *previous_rows,
        _movement_row("C-001", face="100000", duration="4", dv01="40", accounting_class="TPL"),
    ]
    current_all_rows = [*current_rows]

    movement_rows = build_dv01_movement_bond_payloads(
        current_rows=current_rows,
        previous_rows=previous_rows,
        current_all_rows=current_all_rows,
        previous_all_rows=previous_all_rows,
    )
    attribution = build_dv01_movement_attribution_payloads(
        movement_rows,
        total_delta_dv01=Decimal("180"),
    )

    by_code = {row["instrument_code"]: row for row in movement_rows}
    assert by_code["A-001"]["estimated_dv01_from_face_duration"] == Decimal("385.00000")
    assert by_code["A-001"]["dv01_estimate_gap"] == Decimal("5.00000")
    assert by_code["A-001"]["reason_label"]
    assert by_code["C-001"]["previous_accounting_class"] == "TPL"

    by_driver = {row["driver_key"]: row for row in attribution}
    assert by_driver["new_position"]["dv01_delta"] == Decimal("100")
    assert by_driver["exited_position"]["dv01_delta"] == Decimal("-50")
    assert by_driver["face_value_change"]["dv01_delta"] == Decimal("30.00")
    assert by_driver["duration_change"]["dv01_delta"] == Decimal("50.0000")
    assert by_driver["classification_change"]["dv01_delta"] == Decimal("40")
    assert by_driver["residual"]["dv01_delta"] == Decimal("10.0000")
    assert sum(row["dv01_delta"] for row in attribution) == Decimal("180")


def test_dv01_core_builds_action_plan_payloads() -> None:
    rows = [
        _movement_row(
            "A-001",
            face="1000000",
            duration="8",
            dv01="800",
            accounting_class="OCI",
            issuer_name="Issuer A",
            tenor_bucket="7-10Y",
        ),
        _movement_row(
            "B-001",
            face="500000",
            duration="7",
            dv01="350",
            accounting_class="OCI",
            issuer_name="Issuer A",
            tenor_bucket="7-10Y",
        ),
    ]
    total_abs = total_abs_dv01(rows)

    assert dv01_action_risk_level(
        total_dv01=Decimal("1150"),
        warning_dv01=Decimal("900"),
        limit_dv01=Decimal("1000"),
        has_rows=True,
    ) == "breach"
    assert dv01_action_risk_level(
        total_dv01=Decimal("0"),
        warning_dv01=Decimal("900"),
        limit_dv01=Decimal("1000"),
        has_rows=False,
    ) == "no_data"

    scenarios = build_dv01_action_scenario_payloads(
        total_dv01=Decimal("1150"),
        warning_dv01=Decimal("900"),
        limit_dv01=Decimal("1000"),
        has_rows=True,
        shocks=[Decimal("10"), Decimal("25")],
    )
    tenor_actions = build_dv01_action_tenor_payloads(
        rows,
        total_abs_dv01=total_abs,
        dv01_to_reduce=Decimal("250"),
        top_n=2,
    )
    issuer_actions = build_dv01_action_issuer_payloads(
        rows,
        total_abs_dv01=total_abs,
        dv01_to_reduce=Decimal("250"),
        top_n=2,
    )
    bond_actions = build_dv01_action_bond_payloads(
        rows,
        total_abs_dv01=total_abs,
        dv01_to_reduce=Decimal("250"),
        top_n=2,
    )

    assert scenarios[0]["scenario_name"] == "rate_up_10bp"
    assert scenarios[0]["estimated_loss"] == Decimal("11500")
    assert scenarios[0]["loss_threshold"] == Decimal("10000")
    assert scenarios[0]["risk_level"] == "breach"
    assert scenarios[1]["scenario_name"] == "rate_up_25bp"
    assert build_dv01_action_scenario_payloads(
        total_dv01=Decimal("0"),
        warning_dv01=Decimal("900"),
        limit_dv01=Decimal("1000"),
        has_rows=False,
        shocks=[Decimal("10")],
    ) == []

    assert tenor_actions[0]["tenor_bucket"] == "7-10Y"
    assert tenor_actions[0]["dv01"] == Decimal("1150")
    assert tenor_actions[0]["dv01_share"] == Decimal("1")
    assert tenor_actions[0]["suggested_reduction_dv01"] == Decimal("250")
    assert tenor_actions[0]["position_count"] == 2

    assert issuer_actions[0]["issuer_name"] == "Issuer A"
    assert issuer_actions[0]["suggested_reduction_dv01"] == Decimal("250")

    assert bond_actions[0]["instrument_code"] == "A-001"
    assert bond_actions[0]["dv01_share"] == Decimal("800") / Decimal("1150")
    assert bond_actions[0]["suggested_reduction_dv01"] == Decimal("250") * Decimal("800") / Decimal("1150")
    assert bond_actions[1]["instrument_code"] == "B-001"


def _movement_row(
    instrument_code: str,
    *,
    face: str,
    duration: str,
    dv01: str,
    accounting_class: str,
    issuer_name: str | None = None,
    tenor_bucket: str = "3-5Y",
) -> dict[str, object]:
    return {
        "instrument_code": instrument_code,
        "instrument_name": f"{instrument_code} Bond",
        "issuer_name": issuer_name or f"{instrument_code} Issuer",
        "rating": "AAA",
        "tenor_bucket": tenor_bucket,
        "accounting_class": accounting_class,
        "face_value": Decimal(face),
        "market_value": Decimal(face),
        "modified_duration": Decimal(duration),
        "dv01": Decimal(dv01),
    }
