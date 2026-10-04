from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.schemas.campisi_attribution_read import (
    CampisiEnhancedEnvelope,
    CampisiFourEffectsReadEnvelope,
    CampisiMaturityBucketEnvelope,
)
from backend.app.services import campisi_attribution_service as service

_START = "2026-01-01"
_END = "2026-01-31"
_HEALTHY_META = {"quality_flag": "ok", "vendor_status": "ok", "fallback_mode": "none"}
_BOND = {
    "instrument_code": "QUALITY-01.IB",
    "portfolio_name": "FIOA",
    "cost_center": "5010",
    "accounting_class": "FVTPL",
    "currency_code": "CNY",
    "market_value": Decimal("1000"),
    "face_value": Decimal("1000"),
    "accrued_interest": Decimal("3"),
    "coupon_rate": Decimal("0.03"),
    "ytm": Decimal("0.032"),
    "maturity_date": "2029-01-01",
    "asset_class_std": "treasury",
    "rating": "AAA",
}


def _bridge(meta: dict[str, Any] | None) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "result": {
            "summary": {"row_count": 1, "total_actual_pnl": {"raw": 35.0}},
            "rows": [{
                "instrument_code": "QUALITY-01.IB",
                "portfolio_name": "FIOA",
                "cost_center": "5010",
                "accounting_basis": "FVTPL",
                "beginning_dirty_mv": {"raw": 1000.0},
                "ending_dirty_mv": {"raw": 1100.0},
                "carry": {"raw": 5.0},
                "roll_down": {"raw": 1.0},
                "treasury_curve": {"raw": 2.0},
                "credit_spread": {"raw": 3.0},
                "fx_translation": {"raw": 4.0},
                "realized_trading": {"raw": 6.0},
                "manual_adjustment": {"raw": 0.0},
                "unrealized_fv": {"raw": 14.0},
                "actual_pnl": {"raw": 35.0},
                "residual": {"raw": 14.0},
                "quality_flag": "ok",
            }],
        },
    }
    if meta is not None:
        envelope["result_meta"] = deepcopy(meta)
    return envelope


@pytest.fixture
def install_bridge(monkeypatch: pytest.MonkeyPatch, tmp_path):
    service.clear_campisi_four_effects_runtime_cache()
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "campisi-quality.duckdb",
        governance_path=tmp_path / "governance",
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    monkeypatch.setattr(service, "BondAnalyticsRepository", lambda _path: SimpleNamespace(
        list_report_dates=lambda: [_END, _START],
        fetch_bond_analytics_rows=lambda **_kwargs: [deepcopy(_BOND)],
    ))
    monkeypatch.setattr(service, "YieldCurveRepository", lambda _path: SimpleNamespace())

    def install(envelope: dict[str, Any]):
        monkeypatch.setattr(service, "_try_fetch_cached_formal_bridge", lambda **_kwargs: deepcopy(envelope))
        monkeypatch.setattr(service, "_try_fetch_formal_bridge", lambda **_kwargs: deepcopy(envelope))
        return settings

    yield install
    service.clear_campisi_four_effects_runtime_cache()


@pytest.mark.parametrize("endpoint,model", [
    (service.campisi_four_effects_envelope, CampisiFourEffectsReadEnvelope),
    (service.campisi_enhanced_envelope, CampisiEnhancedEnvelope),
    (service.campisi_maturity_bucket_envelope, CampisiMaturityBucketEnvelope),
])
@pytest.mark.parametrize("upstream,expected", [
    ({"quality_flag": "error", "vendor_status": "vendor_stale", "fallback_mode": "latest_snapshot",
      "fallback_date": "2026-01-29"}, ("error", "vendor_stale", "latest_snapshot", "2026-01-29")),
    ({"quality_flag": "stale", "vendor_status": "vendor_stale", "fallback_mode": "latest_snapshot",
      "as_of_date": _END}, ("stale", "vendor_stale", "latest_snapshot", None)),
    (_HEALTHY_META, ("ok", "ok", "none", None)),
    ({**_HEALTHY_META, "quality_flag": "error"}, ("error", "ok", "none", None)),
    (None, ("warning", "ok", "none", None)),
    ({"quality_flag": "ok", "fallback_mode": "none"}, ("warning", "ok", "none", None)),
    ({**_HEALTHY_META, "vendor_status": "vendor_unavailable"}, ("ok", "vendor_unavailable", "none", None)),
])
def test_all_bridge_consumers_preserve_source_quality(install_bridge, endpoint, model, upstream, expected):
    install_bridge(_bridge(upstream))

    envelope = endpoint(start_date=_START, end_date=_END)

    model.model_validate(envelope)
    meta = envelope["result_meta"]
    assert tuple(meta[key] for key in ("quality_flag", "vendor_status", "fallback_mode", "fallback_date")) == expected
    payload = envelope["result"]
    if "totals" in payload:
        assert payload["totals"]["total_return"] == 35.0
    else:
        assert sum(bucket["total_return"] for bucket in payload["buckets"].values()) == 35.0
    if "formal_closure" in payload:
        assert payload["formal_closure"]["status"] == "closed"
        assert payload["formal_closure"]["residual_to_formal_pnl"] == 0.0
        assert payload["formal_closure"]["bridge_fallback_date"] == expected[3]


def test_amount_difference_still_warns_with_healthy_source(install_bridge):
    bridge = _bridge(_HEALTHY_META)
    bridge["result"]["summary"]["total_actual_pnl"]["raw"] = 45.0
    install_bridge(bridge)

    envelope = service.campisi_four_effects_envelope(start_date=_START, end_date=_END)

    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result"]["formal_closure"]["status"] == "warning"
    assert envelope["result"]["formal_closure"]["residual_to_formal_pnl"] == 10.0


@pytest.mark.parametrize("endpoint,model", [
    (service.campisi_four_effects_envelope, CampisiFourEffectsReadEnvelope),
    (service.campisi_enhanced_envelope, CampisiEnhancedEnvelope),
    (service.campisi_maturity_bucket_envelope, CampisiMaturityBucketEnvelope),
])
def test_matched_formal_bridge_retains_actual_pnl_for_quantity_changes(install_bridge, monkeypatch, endpoint, model):
    install_bridge(_bridge(_HEALTHY_META))
    monkeypatch.setattr(service, "BondAnalyticsRepository", lambda _path: SimpleNamespace(
        list_report_dates=lambda: [_END, _START],
        fetch_bond_analytics_rows=lambda **kwargs: [{**deepcopy(_BOND),
            "face_value": 2000 if kwargs["report_date"] == _END else 1000,
            "market_value": 2000 if kwargs["report_date"] == _END else 1000}],
    ))
    envelope = endpoint(start_date=_START, end_date=_END)
    model.model_validate(envelope)
    payload = envelope["result"]
    total = payload["totals"]["total_return"] if "totals" in payload else sum(
        row["total_return"] for row in payload["buckets"].values()
    )
    assert total == 35
    assert "position_change" not in payload["input_quality"]
    assert envelope["result_meta"]["formal_use_allowed"] is True


@pytest.mark.parametrize("quality", ["error", "stale"])
def test_upstream_quality_is_not_downgraded_by_local_warning(quality):
    meta = service._meta_with_quality(
        "campisi.four_effects", {"warnings": ["Local pricing field is missing."]},
        {"status": "closed", "bridge_quality_flag": quality,
         "bridge_vendor_status": "ok", "bridge_fallback_mode": "none"},
    )
    assert meta.quality_flag == quality


def test_cached_four_effects_state_retains_comparison_bridge_quality(install_bridge):
    bridge = _bridge({"quality_flag": "error", "vendor_status": "vendor_stale",
                      "fallback_mode": "latest_snapshot", "fallback_date": "2026-01-29"})
    settings = install_bridge(bridge)
    positions = service._merge_positions([_BOND], [_BOND])
    state = {
        "result": service._formal_bridge_to_campisi_result(
            bridge_envelope=bridge, positions=positions,
            start_date=date.fromisoformat(_START), end_date=date.fromisoformat(_END),
        ),
        "input_quality": service._build_input_quality(rows_start=[_BOND], rows_end=[_BOND], positions=positions),
        "filters": {"requested_end_date": _END, "resolved_end_date": _END},
        "anchor_start": _START, "anchor_end": _END, "evidence_rows": 2,
    }

    envelope = service._campisi_four_effects_envelope_from_state(
        state=state, settings=settings, formal_bridge=bridge,
    )

    CampisiFourEffectsReadEnvelope.model_validate(envelope)
    assert envelope["result_meta"]["quality_flag"] == "error"
    assert envelope["result_meta"]["vendor_status"] == "vendor_stale"
    assert envelope["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert envelope["result_meta"]["fallback_date"] == "2026-01-29"
    assert envelope["result"]["formal_closure"]["status"] == "closed"


def test_no_bridge_consumer_and_local_report_date_fallback_keep_existing_semantics():
    healthy = service._meta_with_quality("campisi.enhanced", {"warnings": []})
    assert healthy.quality_flag == "ok"
    local_fallback = service._meta_with_quality(
        "campisi.four_effects", {"warnings": ["Local input warning."]},
        upstream_meta=_HEALTHY_META,
        filters_applied={"requested_end_date": "2026-02-01", "resolved_end_date": _END},
    )
    assert local_fallback.quality_flag == "warning"
    assert local_fallback.fallback_mode == "latest_snapshot"
    assert local_fallback.fallback_date == _END


@pytest.mark.parametrize("source_date", ["2026-01-29", None])
def test_upstream_fallback_date_is_not_replaced_by_local_report_date(source_date):
    meta = service._meta_with_quality(
        "campisi.four_effects", {"warnings": []},
        upstream_meta={**_HEALTHY_META, "fallback_mode": "latest_snapshot", "fallback_date": source_date},
        filters_applied={"requested_end_date": "2026-02-01", "resolved_end_date": _END},
    )
    assert meta.fallback_mode == "latest_snapshot"
    assert meta.fallback_date == source_date
    assert meta.requested_report_date == "2026-02-01"
    assert meta.resolved_report_date == _END
