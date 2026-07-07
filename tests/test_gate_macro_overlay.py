from __future__ import annotations

from datetime import date, timedelta

import duckdb

from backend.app.core_finance.gate_macro_overlay import (
    GATE_MACRO_OVERLAY_FORMULA_VERSION,
    MACRO_CONTEXT_STATUS_EXPIRED,
    MACRO_CONTEXT_STATUS_LOOK_AHEAD,
    MACRO_CONTEXT_STATUS_MISSING,
    MACRO_CONTEXT_STATUS_READY,
    MACRO_CYCLE_STATE_CONTRACTION,
    MACRO_CYCLE_STATE_EXPANSION,
    MACRO_CYCLE_STATE_NEUTRAL,
    MACRO_CYCLE_STATE_RECESSION,
    MACRO_EXPOSURE_CAP_BY_STATE,
    MacroCycleObservation,
    apply_macro_gate_overlay,
    classify_macro_cycle_state,
)
from backend.app.services.market_data_livermore_service import livermore_strategy_envelope


def _gate(*, exposure: float = 0.75, state: str = "HOT") -> dict[str, object]:
    return {
        "state": state,
        "exposure": exposure,
        "passed_conditions": 3,
        "available_conditions": 4,
        "required_conditions": 4,
        "conditions": [{"key": "csi300_close_gt_ma60", "status": "pass"}],
    }


def _macro(
    score: float | None,
    *,
    component_dates: tuple[tuple[str, str, str, str], ...] | None = None,
) -> MacroCycleObservation:
    if component_dates is None:
        component_dates = (
            ("PMI", "M0017126", "monthly", "2026-06-30"),
            ("credit_impulse", "M5525763", "monthly", "2026-06-30"),
            ("price_spread", "CA.CSI300_PE", "daily", "2026-07-06"),
        )
    return MacroCycleObservation(
        macro_score=score,
        component_dates=component_dates,
        evidence="unit-test macro evidence",
    )


def test_classify_macro_cycle_state_thresholds() -> None:
    assert classify_macro_cycle_state(0.10) == MACRO_CYCLE_STATE_RECESSION
    assert classify_macro_cycle_state(0.2499) == MACRO_CYCLE_STATE_RECESSION
    assert classify_macro_cycle_state(0.25) == MACRO_CYCLE_STATE_CONTRACTION
    assert classify_macro_cycle_state(0.3999) == MACRO_CYCLE_STATE_CONTRACTION
    assert classify_macro_cycle_state(0.40) == MACRO_CYCLE_STATE_NEUTRAL
    assert classify_macro_cycle_state(0.5999) == MACRO_CYCLE_STATE_NEUTRAL
    assert classify_macro_cycle_state(0.60) == MACRO_CYCLE_STATE_EXPANSION
    assert classify_macro_cycle_state(1.0) == MACRO_CYCLE_STATE_EXPANSION


def test_recession_macro_caps_exposure_golden_sample() -> None:
    """Golden sample: HOT gate 0.75 with recession macro (score 0.18) is capped to 0.25."""
    gate = apply_macro_gate_overlay(
        _gate(exposure=0.75, state="HOT"),
        gate_as_of_date="2026-07-06",
        macro=_macro(0.18),
    )

    assert gate["exposure_raw"] == 0.75
    assert gate["exposure"] == 0.25
    assert gate["formula_version"] == GATE_MACRO_OVERLAY_FORMULA_VERSION
    macro_context = gate["macro_context"]
    assert macro_context["status"] == MACRO_CONTEXT_STATUS_READY
    assert macro_context["cycle_state"] == MACRO_CYCLE_STATE_RECESSION
    assert macro_context["macro_score"] == 0.18
    assert macro_context["gate_as_of_date"] == "2026-07-06"
    overlay = gate["macro_overlay"]
    assert overlay["applied"] is True
    assert overlay["exposure_cap"] == MACRO_EXPOSURE_CAP_BY_STATE[MACRO_CYCLE_STATE_RECESSION] == 0.25
    assert overlay["exposure_raw"] == 0.75
    assert overlay["exposure_adjusted"] == 0.25
    assert "min(exposure_raw" in str(overlay["rule"])
    # Gate legs and state semantics are untouched by the overlay.
    assert gate["state"] == "HOT"
    assert gate["passed_conditions"] == 3


def test_contraction_macro_caps_exposure_to_half() -> None:
    gate = apply_macro_gate_overlay(
        _gate(exposure=0.75, state="HOT"),
        gate_as_of_date="2026-07-06",
        macro=_macro(0.30),
    )

    assert gate["exposure_raw"] == 0.75
    assert gate["exposure"] == 0.5
    assert gate["macro_context"]["cycle_state"] == MACRO_CYCLE_STATE_CONTRACTION
    assert gate["macro_overlay"]["applied"] is True
    assert gate["macro_overlay"]["exposure_cap"] == 0.5


def test_cap_never_raises_low_exposure() -> None:
    gate = apply_macro_gate_overlay(
        _gate(exposure=0.25, state="WARM"),
        gate_as_of_date="2026-07-06",
        macro=_macro(0.30),
    )

    assert gate["exposure"] == 0.25
    assert gate["exposure_raw"] == 0.25
    assert gate["macro_overlay"]["applied"] is False


def test_neutral_and_expansion_do_not_adjust() -> None:
    for score, expected_state in ((0.45, MACRO_CYCLE_STATE_NEUTRAL), (0.80, MACRO_CYCLE_STATE_EXPANSION)):
        gate = apply_macro_gate_overlay(
            _gate(exposure=0.75, state="HOT"),
            gate_as_of_date="2026-07-06",
            macro=_macro(score),
        )
        assert gate["exposure"] == 0.75
        assert gate["exposure_raw"] == 0.75
        assert gate["macro_context"]["cycle_state"] == expected_state
        assert gate["macro_overlay"]["applied"] is False
        assert gate["macro_overlay"]["exposure_cap"] is None


def test_missing_macro_keeps_gate_behavior_identical() -> None:
    base = _gate(exposure=0.75, state="HOT")
    for macro in (None, _macro(None)):
        gate = apply_macro_gate_overlay(
            dict(base),
            gate_as_of_date="2026-07-06",
            macro=macro,
        )
        # Pre-existing keys are byte-identical to the raw gate.
        for key, value in base.items():
            assert gate[key] == value
        assert gate["exposure"] == gate["exposure_raw"] == 0.75
        assert gate["macro_context"]["status"] == MACRO_CONTEXT_STATUS_MISSING
        assert gate["macro_context"]["cycle_state"] is None
        assert gate["macro_overlay"]["applied"] is False


def test_macro_score_without_component_dates_is_treated_as_missing() -> None:
    gate = apply_macro_gate_overlay(
        _gate(exposure=0.75, state="HOT"),
        gate_as_of_date="2026-07-06",
        macro=_macro(0.10, component_dates=()),
    )

    assert gate["exposure"] == 0.75
    assert gate["macro_context"]["status"] == MACRO_CONTEXT_STATUS_MISSING
    assert gate["macro_overlay"]["applied"] is False


def test_expired_macro_component_disables_adjustment() -> None:
    gate = apply_macro_gate_overlay(
        _gate(exposure=0.75, state="HOT"),
        gate_as_of_date="2026-07-06",
        macro=_macro(
            0.10,
            component_dates=(
                # Monthly PMI is 187 calendar days old -> expired (>100d for monthly cadence).
                ("PMI", "M0017126", "monthly", "2026-01-01"),
                ("credit_impulse", "M5525763", "monthly", "2026-06-30"),
            ),
        ),
    )

    assert gate["exposure"] == 0.75
    assert gate["exposure_raw"] == 0.75
    assert gate["macro_context"]["status"] == MACRO_CONTEXT_STATUS_EXPIRED
    assert gate["macro_context"]["cycle_state"] is None
    assert gate["macro_overlay"]["applied"] is False


def test_look_ahead_macro_component_disables_adjustment() -> None:
    gate = apply_macro_gate_overlay(
        _gate(exposure=0.75, state="HOT"),
        gate_as_of_date="2026-07-06",
        macro=_macro(
            0.10,
            component_dates=(
                ("PMI", "M0017126", "monthly", "2026-06-30"),
                # Dated after the gate trade date -> look-ahead, must not adjust.
                ("price_spread", "CA.CSI300_PE", "daily", "2026-07-08"),
            ),
        ),
    )

    assert gate["exposure"] == 0.75
    assert gate["macro_context"]["status"] == MACRO_CONTEXT_STATUS_LOOK_AHEAD
    assert gate["macro_overlay"]["applied"] is False


def test_lag_days_disclosure_uses_as_of_lte_gate_date() -> None:
    gate = apply_macro_gate_overlay(
        _gate(exposure=0.75, state="HOT"),
        gate_as_of_date="2026-07-06",
        macro=_macro(
            0.18,
            component_dates=(
                ("PMI", "M0017126", "monthly", "2026-05-31"),
                ("credit_impulse", "M5525763", "monthly", "2026-05-31"),
                ("price_spread", "CA.CSI300_PE", "daily", "2026-07-04"),
            ),
        ),
    )

    macro_context = gate["macro_context"]
    assert macro_context["status"] == MACRO_CONTEXT_STATUS_READY
    # data_date is the freshest macro input actually used; lag_days measured against gate T.
    assert macro_context["data_date"] == "2026-07-04"
    assert macro_context["lag_days"] == 2
    # Worst-case component lag (monthly PMI/credit at 2026-05-31) is also disclosed.
    assert macro_context["max_component_lag_days"] == 36
    components = {row["input_family"]: row for row in macro_context["components"]}
    assert components["PMI"]["business_date"] == "2026-05-31"
    assert components["PMI"]["age_days"] == 36
    assert components["price_spread"]["age_days"] == 2


# --- service-level wiring -------------------------------------------------


def _seed_broad_index_history(conn: duckdb.DuckDBPyConnection, *, start: date, days: int) -> None:
    conn.execute(
        """
        create table fact_choice_macro_daily (
          series_id varchar,
          series_name varchar,
          trade_date varchar,
          value_numeric double,
          frequency varchar,
          unit varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          quality_flag varchar,
          run_id varchar
        )
        """
    )
    rows = []
    for offset in range(days):
        trade_date = (start + timedelta(days=offset)).isoformat()
        rows.append(
            (
                "CA.CSI300",
                "CSI300 close",
                trade_date,
                3200.0 + offset * 8,
                "daily",
                "index",
                "sv_choice_macro_csi300",
                "vv_tushare_csi300",
                "rv_choice_macro_public_history_v1",
                "ok",
                f"choice_macro_refresh:{trade_date}",
            )
        )
    conn.executemany(
        "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _seed_deteriorating_macro_series(conn: duckdb.DuckDBPyConnection) -> None:
    """PMI 44 -> signal 0; SF impulse -3.4ppt -> signal 0; PE 40 / CN10Y 2.1 -> spread signal 0.28.

    MacroScore = (0.40*0 + 0.35*0 + 0.25*0.28) / 1.0 = 0.07 -> recession.
    """
    conn.executemany(
        "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("CA.CSI300_PE", "CSI300 PE", "2026-04-06", 40.0, "daily", "x", "sv_pe", "vv_pe", "rv", "ok", "run-pe"),
            ("EMM00166466", "China 10Y yield", "2026-04-06", 2.1, "daily", "%", "sv_y", "vv_y", "rv", "ok", "run-y"),
            ("M0017126", "Manufacturing PMI", "2026-03-31", 44.0, "monthly", "index", "sv_pmi", "vv_pmi", "rv", "ok", "run-pmi"),
            ("M5525763", "Social financing YoY", "2026-02-28", 8.4, "monthly", "%", "sv_sf", "vv_sf", "rv", "ok", "run-sf-1"),
            ("M5525763", "Social financing YoY", "2026-03-31", 5.0, "monthly", "%", "sv_sf", "vv_sf", "rv", "ok", "run-sf-2"),
        ],
    )


def test_service_deteriorating_macro_caps_gate_exposure(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        # 65 rising closes ending 2026-04-06 -> WARM gate, raw exposure 0.5.
        _seed_broad_index_history(conn, start=date(2026, 2, 1), days=65)
        _seed_deteriorating_macro_series(conn)
    finally:
        conn.close()

    envelope = livermore_strategy_envelope(duckdb_path=str(duckdb_path))
    market_gate = envelope["result"]["market_gate"]

    assert market_gate["state"] == "WARM"
    assert market_gate["exposure_raw"] == 0.5
    assert market_gate["exposure"] == 0.25
    assert market_gate["formula_version"] == GATE_MACRO_OVERLAY_FORMULA_VERSION
    macro_context = market_gate["macro_context"]
    assert macro_context["status"] == MACRO_CONTEXT_STATUS_READY
    assert macro_context["cycle_state"] == MACRO_CYCLE_STATE_RECESSION
    assert macro_context["gate_as_of_date"] == "2026-04-06"
    assert 0.0 <= macro_context["macro_score"] < 0.25
    assert market_gate["macro_overlay"]["applied"] is True
    assert market_gate["macro_overlay"]["exposure_cap"] == 0.25


def test_service_missing_macro_keeps_gate_exposure_unchanged(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        # Broad index only; no PMI / SF / PE / CN10Y rows land at all.
        _seed_broad_index_history(conn, start=date(2026, 2, 1), days=65)
    finally:
        conn.close()

    envelope = livermore_strategy_envelope(duckdb_path=str(duckdb_path))
    market_gate = envelope["result"]["market_gate"]

    assert market_gate["state"] == "WARM"
    assert market_gate["exposure"] == 0.5
    assert market_gate["exposure_raw"] == 0.5
    assert market_gate["macro_context"]["status"] == MACRO_CONTEXT_STATUS_MISSING
    assert market_gate["macro_context"]["cycle_state"] is None
    assert market_gate["macro_overlay"]["applied"] is False
    # Existing gate semantics stay intact.
    assert market_gate["passed_conditions"] == 2
    assert market_gate["available_conditions"] == 2
    assert market_gate["required_conditions"] == 4
