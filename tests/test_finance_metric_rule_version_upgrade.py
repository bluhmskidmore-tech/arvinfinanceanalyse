from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

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


def test_candidate_schema_rejects_source_impact_report_month_drift() -> None:
    envelope = candidate_financial_indicator_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
    )
    drifted = deepcopy(envelope)
    drifted["result"]["source_version_impact"]["report_month"] = "202605"

    with pytest.raises(ValidationError, match="source impact report_month"):
        CandidateFinancialIndicatorEnvelope.model_validate(drifted)


@pytest.mark.parametrize("source_field", ["current_ledger_sha256", "daily_sha256"])
def test_candidate_schema_rejects_source_impact_hash_drift(source_field: str) -> None:
    envelope = candidate_financial_indicator_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
    )
    drifted = deepcopy(envelope)
    drifted["result"]["source_version_impact"][source_field] = "0" * 64

    with pytest.raises(ValidationError, match="source impact source hashes"):
        CandidateFinancialIndicatorEnvelope.model_validate(drifted)


def test_candidate_schema_rejects_a_mismatch_status_when_digests_are_equal() -> None:
    envelope = candidate_financial_indicator_envelope(
        source_dir=str(SOURCE_DIR),
        report_month="202606",
    )
    drifted = deepcopy(envelope)
    impact = drifted["result"]["source_version_impact"]
    impact["status"] = "numeric_digest_mismatch"
    impact["numeric_changed_count"] = None
    impact["serialization_only_count"] = 0
    impact["serialization_only_metric_ids"] = []

    with pytest.raises(ValidationError, match="mismatched impact digests"):
        CandidateFinancialIndicatorEnvelope.model_validate(drifted)
