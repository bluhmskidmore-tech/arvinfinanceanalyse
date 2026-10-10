from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from backend.app.core_finance import finance_metric_engine
from backend.app.core_finance.finance_metric_engine import load_finance_metric_rules
from backend.app.core_finance.finance_metric_source_impact import (
    _canonical_decimal_text,
    build_finance_metric_source_impact,
    load_finance_metric_source_impact,
)
from backend.app.schemas.candidate_financial_indicators import (
    CandidateFinancialIndicatorEnvelope,
)
from backend.app.services.candidate_financial_indicator_service import (
    candidate_financial_indicator_envelope,
)
from tests.test_candidate_financial_indicator_schema import (
    _envelope as _schema_envelope,
    _refresh_readiness_evidence_key,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data_input" / "pnl_总账对账-日均"
CURRENT_RULE_VERSION = "qdb-finance-2026-v1.0.1"
HISTORICAL_RULE_VERSION = "qdb-finance-2026-v1.0.0"


def test_source_impact_decimal_canonicalization_preserves_integer_place_value() -> None:
    assert _canonical_decimal_text(Decimal("1000")) == "1000"
    assert _canonical_decimal_text(Decimal("1.2300")) == "1.23"
    assert _canonical_decimal_text(Decimal("0.000")) == "0"


def test_source_impact_does_not_publish_an_unchanged_claim_for_partial_metrics() -> None:
    contract = load_finance_metric_source_impact()

    impact = build_finance_metric_source_impact(
        report_month=contract["report_month"],
        rule_version=contract["current_rule_version"],
        ledger_sha256=contract["current_ledger_sha256"],
        daily_sha256=contract["daily_sha256"],
        metric_values={},
    )

    assert impact is not None
    assert impact["status"] == "comparison_incomplete"
    assert impact["compared_metric_count"] == 0
    assert impact["numeric_changed_count"] is None
    assert impact["serialization_only_metric_ids"] == []


def test_source_impact_does_not_publish_an_unchanged_claim_for_digest_mismatch() -> None:
    contract = load_finance_metric_source_impact()

    impact = build_finance_metric_source_impact(
        report_month=contract["report_month"],
        rule_version=contract["current_rule_version"],
        ledger_sha256=contract["current_ledger_sha256"],
        daily_sha256=contract["daily_sha256"],
        metric_values={f"metric.{index:03d}": Decimal("0") for index in range(186)},
    )

    assert impact is not None
    assert impact["status"] == "numeric_digest_mismatch"
    assert impact["numeric_changed_count"] is None
    assert impact["serialization_only_count"] == 0


def test_source_impact_is_omitted_outside_the_pinned_source_pair() -> None:
    contract = load_finance_metric_source_impact()

    impact = build_finance_metric_source_impact(
        report_month=contract["report_month"],
        rule_version=contract["current_rule_version"],
        ledger_sha256="0" * 64,
        daily_sha256=contract["daily_sha256"],
        metric_values={},
    )

    assert impact is None


def test_source_version_impact_is_omitted_when_manual_values_change_the_candidate() -> None:
    envelope = candidate_financial_indicator_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
        manual_overrides={"input.adjustment.noninterest.r010": Decimal("1")},
    )

    assert envelope["result"]["source_version_impact"] is None


def _source_hashes(rules: dict[str, object]) -> dict[str, str]:
    metadata = rules["metadata"]
    assert isinstance(metadata, dict)
    derived_from = metadata["derived_from"]
    assert isinstance(derived_from, list)
    return {
        str(item["file"]): str(item["sha256"])
        for item in derived_from
        if isinstance(item, dict)
    }


def test_default_rule_version_locks_the_current_202606_source_pair() -> None:
    rules = load_finance_metric_rules()
    source_hashes = _source_hashes(rules)

    assert rules["metadata"]["rule_version"] == CURRENT_RULE_VERSION
    for file_name in ("总账对账202606.xlsx", "日均202606.xlsx"):
        source_path = SOURCE_DIR / file_name
        assert source_hashes[file_name] == hashlib.sha256(source_path.read_bytes()).hexdigest()


def test_historical_rule_version_remains_available_for_replay() -> None:
    rules = load_finance_metric_rules(rule_version=HISTORICAL_RULE_VERSION)

    assert rules["metadata"]["rule_version"] == HISTORICAL_RULE_VERSION
    assert rules["rule_hash"] == "7f1b9d47dece2db850ef69cd9ab13b2520ad3bc09d6a2bce3a48ac6017777567"
    assert _source_hashes(rules)["总账对账202606.xlsx"].startswith("0ba128f1")


def test_v101_changes_only_version_provenance_and_the_ledger_source_lock() -> None:
    historical_path = finance_metric_engine.RULE_ASSETS[HISTORICAL_RULE_VERSION]
    current_path = finance_metric_engine.RULE_ASSETS[CURRENT_RULE_VERSION]
    historical = json.loads(historical_path.read_text(encoding="utf-8"))
    current = json.loads(current_path.read_text(encoding="utf-8"))

    current["metadata"]["rule_version"] = historical["metadata"]["rule_version"]
    current["metadata"]["generated_on"] = historical["metadata"]["generated_on"]
    current_ledger = next(
        item
        for item in current["metadata"]["derived_from"]
        if item["file"] == "总账对账202606.xlsx"
    )
    historical_ledger = next(
        item
        for item in historical["metadata"]["derived_from"]
        if item["file"] == "总账对账202606.xlsx"
    )
    current_ledger["sha256"] = historical_ledger["sha256"]

    assert current == historical


def test_named_rule_version_rejects_an_asset_with_different_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        finance_metric_engine.RULE_ASSETS,
        CURRENT_RULE_VERSION,
        finance_metric_engine.RULE_ASSETS[HISTORICAL_RULE_VERSION],
    )

    with pytest.raises(ValueError, match="requested rule_version"):
        load_finance_metric_rules(rule_version=CURRENT_RULE_VERSION)


def test_current_sources_pass_source_lock_without_becoming_formal() -> None:
    envelope = candidate_financial_indicator_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
    )
    result = envelope["result"]

    assert result["rule_version"] == CURRENT_RULE_VERSION
    assert result["source_alignment"] == "matched"
    assert result["formal_use_allowed"] is False
    assert result["calculation_status"] == "warning"
    assert result["promotion_readiness"]["status"] == "blocked"
    assert result["promotion_readiness"]["blocking_count"] == 4
    assert result["summary"]["validation_warning_failed"] == 1
    assert result["summary"]["manual_default_count"] == 19


def test_current_sources_expose_a_numeric_source_version_impact_check() -> None:
    envelope = candidate_financial_indicator_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
    )
    impact = envelope["result"]["source_version_impact"]

    assert impact["contract_version"] == "candidate-source-version-impact-v1"
    assert impact["status"] == "numerically_unchanged"
    assert impact["reference_rule_version"] == HISTORICAL_RULE_VERSION
    assert impact["current_rule_version"] == CURRENT_RULE_VERSION
    assert impact["metric_total"] == 186
    assert impact["compared_metric_count"] == 186
    assert impact["numeric_changed_count"] == 0
    assert impact["serialization_only_count"] == 8
    assert impact["formal_use_allowed"] is False


def _synthetic_source_impact_envelope() -> dict[str, Any]:
    """synthetic_fabricated: schema-only data, never source or historical acceptance.

    Reuse the existing schema envelope; all hashes and digests below are fabricated.
    The month and comparison counts exercise the contract, not actual source replay.
    """
    envelope = _schema_envelope()
    result = envelope["result"]
    source_version = "sv_synthetic_source_impact_schema_v1"
    envelope["result_meta"].update(
        trace_id="tr_synthetic_source_impact_schema",
        source_version=source_version,
        rule_version=CURRENT_RULE_VERSION,
        amount_currency_basis_note="Synthetic schema fixture; no business certification.",
        evidence_rows=0,
    )
    result.update(
        source_version=source_version,
        rule_version=CURRENT_RULE_VERSION,
        source_alignment="matched",
    )
    source_hashes = {}
    for source in result["sources"]:
        source["file_name"] = f"synthetic-{source['source_kind']}-202606.xlsx"
        source["locked_sha256"] = source["sha256"]
        source["locked_hash_match"] = True
        source_hashes[source["source_kind"]] = source["sha256"]
    metric = result["metrics"][0]
    metric["name"] = "Synthetic schema metric"
    metric["value"] = "1"
    metric["lineage"][0].update(
        raw_yuan="-100000000",
        contribution_yi="1",
        evidence_refs=["synthetic_fabricated.ledger!G1"],
    )
    result["gaps"] = [
        {
            "gap_id": "synthetic_fabricated.manual_inputs",
            "severity": "warning",
            "kind": "manual_input",
            "title": "Synthetic default manual inputs",
            "detail": "Schema fixture has no approved business inputs.",
            "metric_ids": [],
        }
    ]
    result["source_version_impact"] = {
        "contract_version": "candidate-source-version-impact-v1",
        "impact_asset_sha256": "a" * 64,
        "status": "numerically_unchanged",
        "comparison_basis": "canonical_decimal_value",
        "report_month": "202606",
        "reference_rule_version": HISTORICAL_RULE_VERSION,
        "current_rule_version": CURRENT_RULE_VERSION,
        "reference_result_sha256": "b" * 64,
        "reference_ledger_sha256": "c" * 64,
        "current_ledger_sha256": source_hashes["ledger"],
        "daily_sha256": source_hashes["daily"],
        "metric_total": 186,
        "compared_metric_count": 186,
        "reference_numeric_digest": "d" * 64,
        "current_numeric_digest": "d" * 64,
        "numeric_changed_count": 0,
        "serialization_only_count": 0,
        "serialization_only_metric_ids": [],
        "formal_use_allowed": False,
        "certification_effect": "none",
    }
    readiness = result["promotion_readiness"]
    source_check = next(
        check for check in readiness["checks"] if check["check_id"] == "source_evidence"
    )
    source_check.update(
        summary="Synthetic hashes are not approved source evidence.",
        evidence_refs=["synthetic_fabricated.source_pair"],
    )
    pack = readiness["evidence_pack"]
    source_requirement = next(
        item for item in pack["owner_requirements"] if item["category"] == "source_evidence"
    )
    source_requirement["evidence_refs"] = ["synthetic_fabricated.source_pair"]
    pack.update(
        source_version=source_version,
        rule_version=CURRENT_RULE_VERSION,
        source_alignment="matched",
    )
    _refresh_readiness_evidence_key(envelope)
    validated = CandidateFinancialIndicatorEnvelope.model_validate(envelope)
    assert validated.result.source_version_impact is not None
    assert validated.result_meta.formal_use_allowed is False
    assert validated.result.formal_use_allowed is False
    assert validated.result.promotion_readiness.status == "blocked"
    return envelope


def test_candidate_schema_rejects_source_impact_report_month_drift() -> None:
    envelope = _synthetic_source_impact_envelope()
    drifted = deepcopy(envelope)
    drifted["result"]["source_version_impact"]["report_month"] = "202605"

    with pytest.raises(ValidationError, match="source impact report_month"):
        CandidateFinancialIndicatorEnvelope.model_validate(drifted)


@pytest.mark.parametrize("source_field", ["current_ledger_sha256", "daily_sha256"])
def test_candidate_schema_rejects_source_impact_hash_drift(source_field: str) -> None:
    envelope = _synthetic_source_impact_envelope()
    drifted = deepcopy(envelope)
    drifted["result"]["source_version_impact"][source_field] = "0" * 64

    with pytest.raises(ValidationError, match="source impact source hashes"):
        CandidateFinancialIndicatorEnvelope.model_validate(drifted)


def test_candidate_schema_rejects_a_mismatch_status_when_digests_are_equal() -> None:
    envelope = _synthetic_source_impact_envelope()
    drifted = deepcopy(envelope)
    impact = drifted["result"]["source_version_impact"]
    impact["status"] = "numeric_digest_mismatch"
    impact["numeric_changed_count"] = None
    impact["serialization_only_count"] = 0
    impact["serialization_only_metric_ids"] = []

    with pytest.raises(ValidationError, match="mismatched impact digests"):
        CandidateFinancialIndicatorEnvelope.model_validate(drifted)
