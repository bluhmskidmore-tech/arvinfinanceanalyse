from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.schemas.campisi_attribution_read import (
    CampisiEnhancedEnvelope,
    CampisiFourEffectsReadEnvelope,
    CampisiMaturityBucketEnvelope,
)
from backend.app.services import campisi_attribution_service as campisi_svc
from tests.test_campisi_attribution_service import (
    _bond_row,
    _clear_four_effects_cache,
    _flat_treasury,
    _install_full_service_fakes,
)
from tests.test_campisi_four_effects_detail_summary import (
    _install_four_effects_bridge_fixture,
)


def test_model_discloses_included_unusable_maturity_in_full_and_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_four_effects_cache()
    start_rows = [
        _bond_row(
            code="MISSING",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            maturity_date=None,
            asset_class="国债",
            coupon_rate=Decimal("0"),
        ),
        _bond_row(
            code="INVALID",
            market_value=Decimal("-50"),
            face_value=Decimal("-50"),
            maturity_date="invalid",
            asset_class="国债",
            coupon_rate=Decimal("0"),
        ),
        _bond_row(
            code="VALID",
            market_value=Decimal("500"),
            face_value=Decimal("500"),
            maturity_date=date(2027, 1, 1),
            asset_class="国债",
            coupon_rate=Decimal("0"),
        ),
    ]
    end_rows = [
        {**start_rows[0], "market_value": Decimal("990")},
        {**start_rows[1], "market_value": Decimal("-45")},
        {**start_rows[2], "market_value": Decimal("500")},
    ]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-01"],
        rows_by_date={"2026-01-01": start_rows, "2026-01-31": end_rows},
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("2")),
        },
    )
    monkeypatch.setattr(
        campisi_svc, "_try_fetch_cached_formal_bridge", lambda **_kwargs: None
    )

    full_envelope = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01", end_date="2026-01-31"
    )
    full = full_envelope["result"]
    summary = campisi_svc.campisi_four_effects_summary_envelope(
        start_date="2026-01-01", end_date="2026-01-31"
    )["result"]

    assert {
        row["bond_code"]
        for row in full["by_bond"]
        if row["maturity_bucket"] == "UNKNOWN"
    } == {
        "MISSING",
        "INVALID",
    }
    assert full["input_quality"]["included_maturity_unavailable"] == {
        "positions": 2,
        "market_value_start_abs": 1050.0,
        "model_residual": -5.0,
    }
    assert summary["by_bond"] == []
    assert summary["input_quality"] == full["input_quality"]
    assert summary["totals"] == full["totals"]
    serialized = CampisiFourEffectsReadEnvelope.model_validate(
        full_envelope
    ).model_dump(exclude_unset=True)
    assert (
        serialized["result"]["input_quality"]["included_maturity_unavailable"]
        == (full["input_quality"]["included_maturity_unavailable"])
    )
    assert any(
        "仅为模型剩余项" in warning and "不代表选券能力" in warning
        for warning in full["warnings"]
    )


def test_formal_bridge_unknown_bucket_is_not_labeled_as_model_quality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_four_effects_bridge_fixture(monkeypatch)
    monkeypatch.setattr(
        campisi_svc, "_formal_maturity_bucket", lambda *_args: "UNKNOWN"
    )

    result = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01", end_date="2026-01-31"
    )["result"]

    assert result["basis"] == "formal_report_pnl_bridge"
    assert result["by_bond"][0]["maturity_bucket"] == "UNKNOWN"
    assert "included_maturity_unavailable" not in result["input_quality"]
    assert "position_change" not in result["input_quality"]


def test_model_exclusions_are_consistent_across_four_enhanced_and_buckets(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _clear_four_effects_cache()
    duckdb_path = tmp_path / "campisi-exclusion-cache.duckdb"
    duckdb_path.write_bytes(b"seed")
    held = _bond_row(
        code="HELD",
        market_value=Decimal("1000"),
        face_value=Decimal("1000"),
        maturity_date=date(2027, 1, 1),
        asset_class="国债",
        coupon_rate=Decimal("0"),
    )
    held_unknown = _bond_row(
        code="HELD_UNKNOWN",
        market_value=Decimal("200"),
        face_value=Decimal("200"),
        maturity_date=None,
        asset_class="国债",
        coupon_rate=Decimal("0"),
    )
    start_only = _bond_row(
        code="START_ONLY",
        market_value=Decimal("300"),
        face_value=Decimal("300"),
        maturity_date=None,
        asset_class="国债",
        coupon_rate=Decimal("0"),
    )
    end_only = _bond_row(
        code="END_ONLY",
        market_value=Decimal("400"),
        face_value=Decimal("400"),
        maturity_date=None,
        asset_class="国债",
        coupon_rate=Decimal("0"),
    )
    changed = _bond_row(
        code="PRINCIPAL_CHANGED",
        market_value=Decimal("500"),
        face_value=Decimal("500"),
        maturity_date=None,
        asset_class="国债",
        coupon_rate=Decimal("0"),
    )
    missing = _bond_row(
        code="PRINCIPAL_MISSING",
        market_value=Decimal("600"),
        face_value=None,
        maturity_date=None,
        asset_class="国债",
        coupon_rate=Decimal("0"),
    )
    start_rows = [held, held_unknown, start_only, changed, missing]
    end_rows = [
        {**held, "market_value": Decimal("990")},
        {**held_unknown, "market_value": Decimal("195")},
        end_only,
        {**changed, "market_value": Decimal("505"), "face_value": Decimal("450")},
        {**missing, "market_value": Decimal("610"), "face_value": Decimal("600")},
    ]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-01"],
        rows_by_date={"2026-01-01": start_rows, "2026-01-31": end_rows},
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("2")),
        },
        duckdb_path=str(duckdb_path),
    )
    monkeypatch.setattr(
        campisi_svc, "_try_fetch_cached_formal_bridge", lambda **_kwargs: None
    )
    window = {"start_date": "2026-01-01", "end_date": "2026-01-31"}

    cold_bucket_envelope = campisi_svc.campisi_maturity_bucket_envelope(**window)
    _clear_four_effects_cache()
    full_envelope = campisi_svc.campisi_four_effects_envelope(**window)
    summary_envelope = campisi_svc.campisi_four_effects_summary_envelope(**window)
    enhanced_envelope = campisi_svc.campisi_enhanced_envelope(**window)
    warm_bucket_envelope = campisi_svc.campisi_maturity_bucket_envelope(**window)

    full = full_envelope["result"]
    summary = summary_envelope["result"]
    enhanced = enhanced_envelope["result"]
    cold = cold_bucket_envelope["result"]
    warm = warm_bucket_envelope["result"]
    expected_codes = {"HELD", "HELD_UNKNOWN"}
    assert {row["bond_code"] for row in full["by_bond"]} == expected_codes
    assert {row["bond_code"] for row in enhanced["by_bond"]} == expected_codes
    assert full["totals"]["market_value_start"] == 1200.0
    assert full["totals"]["total_return"] == -15.0
    assert enhanced["totals"]["market_value_start"] == 1200.0
    assert enhanced["totals"]["total_return"] == -15.0
    assert summary["by_bond"] == []
    assert summary["totals"] == full["totals"]
    assert summary["input_quality"] == full["input_quality"]

    for envelope in (
        full_envelope,
        summary_envelope,
        enhanced_envelope,
        cold_bucket_envelope,
        warm_bucket_envelope,
    ):
        assert envelope["result_meta"]["formal_use_allowed"] is False
        coverage = envelope["result"]["input_quality"]["position_change"]
        assert coverage["status"] == "partial"
        assert coverage["unavailable_bonds"] == 4
        assert coverage["covered_bonds"] == 2
        assert coverage["unavailable_market_value_start"] == 1400.0
        assert coverage["unavailable_market_value_end"] == 1515.0
        assert any(
            "排除后的零值不代表完整组合零收益" in warning
            for warning in envelope["result"]["warnings"]
        )
    assert full["input_quality"]["included_maturity_unavailable"] == {
        "positions": 1,
        "market_value_start_abs": 200.0,
        "model_residual": -5.0,
    }
    assert cold["buckets"] == warm["buckets"]
    assert cold["buckets"]["UNKNOWN"]["market_value_start"] == 200.0
    assert cold["buckets"]["UNKNOWN"]["total_return"] == -5.0
    assert sum(bucket["total_return"] for bucket in cold["buckets"].values()) == -15.0
    CampisiFourEffectsReadEnvelope.model_validate(full_envelope)
    CampisiEnhancedEnvelope.model_validate(enhanced_envelope)
    CampisiMaturityBucketEnvelope.model_validate(cold_bucket_envelope)


def test_model_all_excluded_reports_unavailable_without_phantom_zero_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_four_effects_cache()
    start_only = _bond_row(
        code="START_ONLY",
        market_value=Decimal("100"),
        face_value=Decimal("100"),
        maturity_date=None,
        asset_class="国债",
        coupon_rate=Decimal("0"),
    )
    end_only = _bond_row(
        code="END_ONLY",
        market_value=Decimal("200"),
        face_value=Decimal("200"),
        maturity_date=None,
        asset_class="国债",
        coupon_rate=Decimal("0"),
    )
    changed = _bond_row(
        code="CHANGED",
        market_value=Decimal("300"),
        face_value=Decimal("300"),
        maturity_date=None,
        asset_class="国债",
        coupon_rate=Decimal("0"),
    )
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-01"],
        rows_by_date={
            "2026-01-01": [start_only, changed],
            "2026-01-31": [
                end_only,
                {
                    **changed,
                    "market_value": Decimal("310"),
                    "face_value": Decimal("290"),
                },
            ],
        },
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("2")),
        },
    )
    monkeypatch.setattr(
        campisi_svc, "_try_fetch_cached_formal_bridge", lambda **_kwargs: None
    )
    window = {"start_date": "2026-01-01", "end_date": "2026-01-31"}

    full_envelope = campisi_svc.campisi_four_effects_envelope(**window)
    summary_envelope = campisi_svc.campisi_four_effects_summary_envelope(**window)
    enhanced_envelope = campisi_svc.campisi_enhanced_envelope(**window)
    bucket_envelope = campisi_svc.campisi_maturity_bucket_envelope(**window)

    for envelope in (
        full_envelope,
        summary_envelope,
        enhanced_envelope,
        bucket_envelope,
    ):
        assert envelope["result_meta"]["formal_use_allowed"] is False
        coverage = envelope["result"]["input_quality"]["position_change"]
        assert coverage["status"] == "unavailable"
        assert coverage["unavailable_bonds"] == 3
        assert coverage["covered_bonds"] == 0
        assert coverage["unavailable_market_value_start"] == 400.0
        assert coverage["unavailable_market_value_end"] == 510.0
        assert (
            "included_maturity_unavailable" not in envelope["result"]["input_quality"]
        )
        assert any(
            "排除后的零值不代表完整组合零收益" in warning
            for warning in envelope["result"]["warnings"]
        )
    assert full_envelope["result"]["by_bond"] == []
    assert summary_envelope["result"]["by_bond"] == []
    assert (
        summary_envelope["result"]["input_quality"]
        == full_envelope["result"]["input_quality"]
    )
    assert enhanced_envelope["result"]["by_bond"] == []
    assert full_envelope["result"]["totals"]["total_return"] == 0.0
    assert enhanced_envelope["result"]["totals"]["total_return"] == 0.0
    buckets = bucket_envelope["result"]["buckets"]
    assert "UNKNOWN" not in buckets
    assert all(bucket["total_return"] == 0.0 for bucket in buckets.values())
