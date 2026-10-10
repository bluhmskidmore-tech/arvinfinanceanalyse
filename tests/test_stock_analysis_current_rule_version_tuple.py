from __future__ import annotations

import copy
import hashlib
import json

import pytest

from backend.app.core_finance import cycle_macro_score, gate_macro_overlay
from backend.app.core_finance.livermore_stock_candidates import (
    EXP3B_STOCK_CANDIDATE_POLICY,
)
from backend.app.core_finance.livermore_stock_candidates import (
    FORMULA_VERSION as STOCK_CANDIDATE_FORMULA_VERSION,
)
from backend.app.core_finance.matched_baseline import (
    FORMULA_VERSION as MATCHED_BASELINE_FORMULA_VERSION,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    build_stock_analysis_calendar_receipt,
)
from backend.app.governance.stock_analysis_current_rule_certificate import (
    ALLOWED_DECISION_METRIC_BASIS,
    CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
    REQUIRED_VERSION_TUPLE_FIELDS,
)
from backend.app.governance.stock_analysis_current_rule_version_tuple import (
    MACRO_FORMULA_CONTRACT,
    MARKET_GATE_CONTRACT,
    CurrentRuleVersionTupleError,
    build_stock_analysis_current_rule_version_tuple,
    validate_stock_analysis_current_rule_version_tuple,
)
from backend.app.repositories.stock_analysis_theme_overlay_reader import (
    BACKFILL_DISABLED_FINGERPRINT,
)
from backend.app.services.livermore_signal_confluence_service import (
    LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
)
from backend.app.services.market_data_livermore_service import (
    RULE_VERSION as MARKET_DATA_LIVERMORE_RULE_VERSION,
)
from backend.app.tasks import livermore_candidate_history_materialize
from backend.app.tasks import (
    stock_analysis_current_rule_cohort_bundle_producer as producer,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

NOW = "2026-08-23T12:00:00+08:00"


def _canonical_sha(payload: object) -> str:
    return (
        hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        .hexdigest()
        .upper()
    )


def _calendar_receipt(*, approved: bool = True) -> dict[str, object]:
    return build_stock_analysis_calendar_receipt(
        calendar_rows=[
            {
                "exchange": "SSE",
                "cal_date": "2026-08-21",
                "is_open": 1,
                "pretrade_date": "2026-08-20",
            }
        ],
        request_start_date="2026-08-21",
        request_end_date="2026-08-21",
        fetched_at=NOW,
        authority_status="approved" if approved else "provisional",
        owner_approval_id="OWNER-CURRENT-RULE-001" if approved else None,
    )


def _source(
    table: str,
    *,
    source_version: str | None = None,
    vendor_version: str | None = "vv-choice",
    rule_version: str | None = "rv-source-v1",
    run_id: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "table": table,
        "source_version": source_version or f"sv-{table}",
        "run_id": run_id or f"run-{table}",
        "available_at": "2026-08-21",
    }
    if vendor_version is not None:
        row["vendor_version"] = vendor_version
    if rule_version is not None:
        row["rule_version"] = rule_version
    return row


def _source_receipt(*sources: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "receipt_kind": "pit_source_availability_v1",
        "captured_at": NOW,
        "sources": list(sources),
    }


def _sources() -> list[dict[str, object]]:
    return [
        _source("choice_stock_daily_observation"),
        _source("choice_stock_universe"),
        _source(
            "stock_adjustment_factor",
            vendor_version=None,
            rule_version=None,
        ),
        _source("fact_choice_macro_daily"),
    ]


def _catalog() -> dict[str, object]:
    return {
        "catalog_version": "choice-stock-catalog-v1",
        "vendor_name": "choice",
        "generated_from": "governed-test",
        "fields": [],
    }


def _build(
    *,
    calendar_receipt: dict[str, object] | None = None,
    receipts: list[dict[str, object]] | None = None,
    catalog: str | bytes | dict[str, object] | None = None,
    theme_fingerprint: str = BACKFILL_DISABLED_FINGERPRINT,
) -> dict[str, object]:
    return build_stock_analysis_current_rule_version_tuple(
        approved_calendar_receipt=calendar_receipt or _calendar_receipt(),
        source_availability_receipts=receipts or [_source_receipt(*_sources())],
        choice_catalog_json=catalog or _catalog(),
        theme_overlay_fingerprint=theme_fingerprint,
    )


def test_builder_freezes_current_authoritative_constants_and_complete_contract() -> (
    None
):
    result = _build()

    assert tuple(result) == REQUIRED_VERSION_TUPLE_FIELDS
    assert (
        result["candidate_rule_version"]
        == livermore_candidate_history_materialize.RULE_VERSION
    )
    assert (
        result["stock_candidate_selection_formula_version"]
        == STOCK_CANDIDATE_FORMULA_VERSION
    )
    assert (
        result["candidate_outcome_formula_version"]
        == livermore_candidate_history_materialize.FORMULA_VERSION
    )
    assert (
        result["execution_formula_version"]
        == livermore_candidate_history_materialize.EXECUTION_FORMULA_VERSION
    )
    assert (
        result["matched_baseline_formula_version"] == MATCHED_BASELINE_FORMULA_VERSION
    )
    assert (
        result["signal_confluence_rule_version"]
        == LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION
    )
    assert result["candidate_rule_version"] == "rv_livermore_candidate_history_v1"
    assert (
        result["stock_candidate_selection_formula_version"]
        == "rv_livermore_stock_candidates_bundle_v7"
    )
    assert (
        result["candidate_outcome_formula_version"]
        == "fv_livermore_candidate_forward_close_dual_adjust_v2"
    )
    assert (
        result["execution_formula_version"]
        == "fv_livermore_candidate_execution_dual_adjust_v5"
    )
    assert (
        result["matched_baseline_formula_version"] == "fv_livermore_matched_baseline_v4"
    )
    assert (
        result["signal_confluence_rule_version"]
        == "rv_livermore_signal_confluence_v3_authoritative_macro_lineage"
    )
    assert result["stock_candidate_selection_policy"] == EXP3B_STOCK_CANDIDATE_POLICY
    assert result["decision_metric_basis"] == ALLOWED_DECISION_METRIC_BASIS
    assert result["coverage_authority_mode"] == CURRENT_RULE_COVERAGE_AUTHORITY_MODE
    assert result["strict_coverage"] is True
    assert result["fallback_covered"] is False
    assert result["theme_overlay_fingerprint"] == BACKFILL_DISABLED_FINGERPRINT

    expected_market_gate = _canonical_sha(
        {
            "contract": MARKET_GATE_CONTRACT,
            "market_data_livermore_rule_version": MARKET_DATA_LIVERMORE_RULE_VERSION,
            "gate_macro_overlay_formula_version": (
                gate_macro_overlay.GATE_MACRO_OVERLAY_FORMULA_VERSION
            ),
        }
    )
    expected_macro = _canonical_sha(
        {
            "contract": MACRO_FORMULA_CONTRACT,
            "series_ids": {
                "pmi": cycle_macro_score.PMI_SERIES_ID,
                "credit_impulse_primary": cycle_macro_score.SOCIAL_FINANCING_YOY_SERIES_ID,
                "credit_impulse_fallback": cycle_macro_score.M2_YOY_SERIES_ID,
                "price_spread_pe": cycle_macro_score.CSI300_PE_SERIES_ID,
                "price_spread_cn10y": cycle_macro_score.CN10Y_SERIES_ID,
            },
            "weights": {
                "pmi": cycle_macro_score.MACRO_WEIGHT_PMI,
                "credit_impulse": cycle_macro_score.MACRO_WEIGHT_CREDIT_IMPULSE,
                "price_spread": cycle_macro_score.MACRO_WEIGHT_PRICE_SPREAD,
            },
            "gate_macro_overlay_formula_version": (
                gate_macro_overlay.GATE_MACRO_OVERLAY_FORMULA_VERSION
            ),
        }
    )
    assert result["market_gate_rule_version"] == expected_market_gate
    assert result["macro_formula_version"] == expected_macro


def test_hashes_are_stable_across_receipt_source_and_catalog_json_order() -> None:
    sources = _sources()
    first = _build(
        receipts=[
            _source_receipt(*sources[:2]),
            _source_receipt(*sources[2:]),
        ],
        catalog=json.dumps(_catalog(), indent=2, ensure_ascii=False),
    )
    reordered_catalog = {
        "fields": [],
        "generated_from": "governed-test",
        "vendor_name": "choice",
        "catalog_version": "choice-stock-catalog-v1",
    }
    second = _build(
        receipts=[
            _source_receipt(*reversed(sources[2:])),
            _source_receipt(*reversed(sources[:2])),
        ],
        catalog=json.dumps(reordered_catalog, separators=(",", ":")).encode("utf-8"),
        theme_fingerprint=BACKFILL_DISABLED_FINGERPRINT.upper(),
    )

    assert second == first
    assert first["choice_catalog_fingerprint"] == _canonical_sha(_catalog())


def test_source_versions_are_domain_separated_and_change_only_for_affected_family() -> (
    None
):
    base = _build()
    with_candidate_extra = _build(
        receipts=[
            _source_receipt(*_sources(), _source("choice_stock_sector_membership"))
        ]
    )
    with_macro_extra = _build(
        receipts=[_source_receipt(*_sources(), _source("livermore_gate_history"))]
    )

    source_fields = (
        "candidate_source_version",
        "execution_source_version",
        "matched_baseline_source_version",
        "macro_source_version",
    )
    assert len({base[field] for field in source_fields}) == len(source_fields)
    assert (
        with_candidate_extra["candidate_source_version"]
        != base["candidate_source_version"]
    )
    assert (
        with_candidate_extra["execution_source_version"]
        == base["execution_source_version"]
    )
    assert (
        with_candidate_extra["matched_baseline_source_version"]
        == base["matched_baseline_source_version"]
    )
    assert with_candidate_extra["macro_source_version"] == base["macro_source_version"]
    assert with_macro_extra["macro_source_version"] != base["macro_source_version"]
    assert (
        with_macro_extra["candidate_source_version"] == base["candidate_source_version"]
    )


@pytest.mark.parametrize(
    ("tables_to_remove", "message"),
    [
        (
            {"choice_stock_daily_observation", "choice_stock_universe"},
            "candidate source family",
        ),
        ({"stock_adjustment_factor"}, "execution/matched source family"),
        ({"fact_choice_macro_daily"}, "macro source family"),
    ],
)
def test_missing_required_source_family_fails_closed(
    tables_to_remove: set[str],
    message: str,
) -> None:
    sources = [row for row in _sources() if row["table"] not in tables_to_remove]

    with pytest.raises(CurrentRuleVersionTupleError, match=message):
        _build(receipts=[_source_receipt(*sources)])


def test_optional_source_versions_normalize_to_empty_strings() -> None:
    sources_missing = _sources()
    sources_explicit = copy.deepcopy(sources_missing)
    factor = next(
        row for row in sources_explicit if row["table"] == "stock_adjustment_factor"
    )
    factor["vendor_version"] = ""
    factor["rule_version"] = ""

    assert _build(receipts=[_source_receipt(*sources_missing)]) == _build(
        receipts=[_source_receipt(*sources_explicit)]
    )


def test_provisional_or_tampered_calendar_fails_closed() -> None:
    with pytest.raises(
        CurrentRuleVersionTupleError, match="authority_status must equal approved"
    ):
        _build(calendar_receipt=_calendar_receipt(approved=False))

    tampered = _calendar_receipt()
    tampered["semantics"] = "prospective_calendar"
    with pytest.raises(
        CurrentRuleVersionTupleError, match="approved_calendar_receipt is invalid"
    ):
        _build(calendar_receipt=tampered)


@pytest.mark.parametrize(
    "fingerprint",
    ["too-short", "g" * 64, ""],
)
def test_invalid_theme_overlay_fingerprint_is_rejected(fingerprint: str) -> None:
    with pytest.raises(CurrentRuleVersionTupleError, match="theme_overlay_fingerprint"):
        _build(theme_fingerprint=fingerprint)


@pytest.mark.parametrize(
    "catalog",
    [
        "{not-json}",
        '{"catalog_version":"v1","catalog_version":"v2","fields":[]}',
        "{}",
        "[]",
        '{"catalog_version":"v1","vendor_name":"wrong","fields":[]}',
    ],
)
def test_invalid_choice_catalog_is_rejected(catalog: str) -> None:
    with pytest.raises(CurrentRuleVersionTupleError, match="choice_catalog_json"):
        _build(catalog=catalog)


def test_duplicate_source_key_across_receipts_is_rejected() -> None:
    sources = _sources()
    with pytest.raises(
        CurrentRuleVersionTupleError, match="duplicate source availability key"
    ):
        _build(
            receipts=[
                _source_receipt(*sources),
                _source_receipt(copy.deepcopy(sources[0])),
            ]
        )


def test_result_is_accepted_byte_for_byte_by_bundle_producer_freeze_contract() -> None:
    result = _build()

    assert producer._freeze_version_tuple(result) == result
    assert validate_stock_analysis_current_rule_version_tuple(result) == (True, ())


def test_validator_rejects_missing_or_drifted_current_contract_fields() -> None:
    missing = _build()
    missing.pop("candidate_source_version")
    valid, errors = validate_stock_analysis_current_rule_version_tuple(missing)
    assert valid is False
    assert any(
        "missing required fields: candidate_source_version" in error for error in errors
    )

    drifted = _build()
    drifted["market_gate_rule_version"] = "0" * 64
    valid, errors = validate_stock_analysis_current_rule_version_tuple(drifted)
    assert valid is False
    assert any(
        "market_gate_rule_version does not match current contract" in error
        for error in errors
    )
