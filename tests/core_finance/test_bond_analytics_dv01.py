from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.bond_analytics.dv01 import (
    build_dv01_tenor_bucket_payloads,
    build_dv01_top_bond_payloads,
    build_dv01_top_issuer_payloads,
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
