from __future__ import annotations

from decimal import Decimal

import pytest
from backend.app.core_finance.stock_portfolio_risk import (
    LIMIT_GATE_STATUS,
    compute_stock_portfolio_risk,
)


def _assert_descriptive_metrics_unavailable(payload: dict[str, object]) -> None:
    for key in (
        "target_weight_sum_ratio",
        "gross_exposure_ratio",
        "net_exposure_ratio",
        "cash_ratio",
        "closure_residual_ratio",
        "top1_weight_ratio",
        "top5_weight_ratio",
        "hhi_ratio",
        "hhi_index",
        "sector_exposures",
    ):
        assert payload[key] is None, key


def _assert_gate_stays_blocked(payload: dict[str, object]) -> None:
    assert payload["limit_gate"] == {
        "status": LIMIT_GATE_STATUS,
        "reason_code": "missing_approved_policy",
        "approved_policy_present": False,
    }


def test_computes_decimal_exposure_concentration_and_sector_metrics() -> None:
    payload = compute_stock_portfolio_risk(
        [
            {"stock_code": "600001.SH", "sector_name": "科技", "target_weight": "0.40"},
            {"stock_code": "600002.SH", "sector_name": "金融", "target_weight": Decimal("0.30")},
            {"stock_code": "600003.SH", "sector_name": "科技", "target_weight": "0.10"},
        ]
    )

    assert payload["data_status"] == "complete"
    assert payload["reason_codes"] == []
    assert payload["observation_only"] is True
    assert payload["formal_use_allowed"] is False
    assert payload["target_weight_sum_ratio"] == Decimal("0.80")
    assert payload["gross_exposure_ratio"] == Decimal("0.80")
    assert payload["net_exposure_ratio"] == Decimal("0.80")
    assert payload["cash_ratio"] == Decimal("0.20")
    assert payload["closure_residual_ratio"] == Decimal("0.00")
    assert payload["top1_weight_ratio"] == Decimal("0.40")
    assert payload["top5_weight_ratio"] == Decimal("0.80")
    assert payload["hhi_ratio"] == Decimal("0.40625")
    assert payload["hhi_index"] == Decimal("4062.50000")
    assert payload["sector_exposures"] == [
        {"sector_name": "科技", "exposure_ratio": Decimal("0.50")},
        {"sector_name": "金融", "exposure_ratio": Decimal("0.30")},
    ]
    _assert_gate_stays_blocked(payload)


def test_single_position_locks_hhi_ratio_and_index_scales() -> None:
    payload = compute_stock_portfolio_risk(
        [{"stock_code": "600001.SH", "sector_name": "科技", "target_weight": "0.4"}]
    )

    assert payload["hhi_ratio"] == Decimal("1")
    assert payload["hhi_index"] == Decimal("10000")
    assert payload["top1_weight_ratio"] == Decimal("0.4")
    assert payload["cash_ratio"] == Decimal("0.6")


def test_top5_excludes_lower_ranked_weights_beyond_five_names() -> None:
    weights = ["0.20", "0.18", "0.16", "0.14", "0.12", "0.10"]

    payload = compute_stock_portfolio_risk(
        [
            {
                "stock_code": f"60000{index}.SH",
                "sector_name": "科技",
                "target_weight": weight,
            }
            for index, weight in enumerate(weights)
        ]
    )

    assert payload["data_status"] == "complete"
    assert payload["target_weight_sum_ratio"] == Decimal("0.90")
    assert payload["top1_weight_ratio"] == Decimal("0.20")
    assert payload["top5_weight_ratio"] == Decimal("0.80")


def test_empty_input_fails_closed_instead_of_inventing_all_cash_portfolio() -> None:
    payload = compute_stock_portfolio_risk([])

    assert payload["data_status"] == "unavailable"
    assert payload["reason_codes"] == ["empty_target_lines"]
    _assert_descriptive_metrics_unavailable(payload)
    _assert_gate_stays_blocked(payload)


@pytest.mark.parametrize(
    ("line", "reason_code"),
    [
        ({"sector_name": "科技", "target_weight": "0.2"}, "missing_stock_code"),
        ({"stock_code": "600001.SH", "target_weight": "0.2"}, "missing_sector_name"),
        ({"stock_code": "600001.SH", "sector_name": "科技"}, "missing_target_weight"),
        ({"stock_code": "600001.SH", "sector_name": "科技", "target_weight": ""}, "missing_target_weight"),
    ],
)
def test_missing_required_values_fail_closed(
    line: dict[str, object],
    reason_code: str,
) -> None:
    payload = compute_stock_portfolio_risk([line])

    assert payload["data_status"] == "unavailable"
    assert reason_code in payload["reason_codes"]
    _assert_descriptive_metrics_unavailable(payload)


@pytest.mark.parametrize(
    ("line", "reason_code"),
    [
        ({"stock_code": 600001, "sector_name": "科技", "target_weight": "0.2"}, "invalid_stock_code"),
        ({"stock_code": "600001.SH", "sector_name": False, "target_weight": "0.2"}, "invalid_sector_name"),
        (None, "target_line_not_mapping"),
    ],
)
def test_invalid_line_or_identifier_types_fail_closed(
    line: object,
    reason_code: str,
) -> None:
    payload = compute_stock_portfolio_risk([line])  # type: ignore[list-item]

    assert payload["data_status"] == "unavailable"
    assert reason_code in payload["reason_codes"]
    _assert_descriptive_metrics_unavailable(payload)


@pytest.mark.parametrize(
    "weight",
    [Decimal("NaN"), Decimal("Infinity"), float("nan"), float("inf"), "not-a-number", True],
)
def test_nonfinite_or_nonnumeric_weight_fails_closed(weight: object) -> None:
    payload = compute_stock_portfolio_risk(
        [{"stock_code": "600001.SH", "sector_name": "科技", "target_weight": weight}]
    )

    assert payload["data_status"] == "unavailable"
    assert "invalid_target_weight" in payload["reason_codes"]
    _assert_descriptive_metrics_unavailable(payload)


@pytest.mark.parametrize("weight", ["-0.01", "1.01"])
def test_weight_outside_zero_to_one_fails_closed(weight: str) -> None:
    payload = compute_stock_portfolio_risk(
        [{"stock_code": "600001.SH", "sector_name": "科技", "target_weight": weight}]
    )

    assert payload["data_status"] == "unavailable"
    assert payload["reason_codes"] == ["target_weight_out_of_range"]
    _assert_descriptive_metrics_unavailable(payload)


def test_total_weight_above_one_fails_closed() -> None:
    payload = compute_stock_portfolio_risk(
        [
            {"stock_code": "600001.SH", "sector_name": "科技", "target_weight": "0.6"},
            {"stock_code": "600002.SH", "sector_name": "金融", "target_weight": "0.5"},
        ]
    )

    assert payload["data_status"] == "unavailable"
    assert payload["reason_codes"] == ["total_target_weight_exceeds_one"]
    _assert_descriptive_metrics_unavailable(payload)


def test_duplicate_stock_code_is_case_and_whitespace_insensitive() -> None:
    payload = compute_stock_portfolio_risk(
        [
            {"stock_code": " 600001.sh ", "sector_name": "科技", "target_weight": "0.2"},
            {"stock_code": "600001.SH", "sector_name": "金融", "target_weight": "0.1"},
        ]
    )

    assert payload["data_status"] == "unavailable"
    assert payload["reason_codes"] == ["duplicate_stock_code"]
    _assert_descriptive_metrics_unavailable(payload)


def test_explicit_zero_weight_portfolio_closes_to_cash_but_hhi_is_unavailable() -> None:
    payload = compute_stock_portfolio_risk(
        [{"stock_code": "600001.SH", "sector_name": "科技", "target_weight": "0"}]
    )

    assert payload["data_status"] == "partial"
    assert payload["reason_codes"] == ["zero_invested_weight"]
    assert payload["gross_exposure_ratio"] == Decimal("0")
    assert payload["net_exposure_ratio"] == Decimal("0")
    assert payload["cash_ratio"] == Decimal("1")
    assert payload["closure_residual_ratio"] == Decimal("0")
    assert payload["hhi_ratio"] is None
    assert payload["hhi_index"] is None
    _assert_gate_stays_blocked(payload)


def test_limit_gate_never_claims_pass_for_valid_descriptive_output() -> None:
    payload = compute_stock_portfolio_risk(
        [{"stock_code": "600001.SH", "sector_name": "科技", "target_weight": "0.5"}]
    )

    assert payload["limit_gate"]["status"] == "blocked_missing_approved_policy"
    assert payload["limit_gate"]["status"] != "PASS"
